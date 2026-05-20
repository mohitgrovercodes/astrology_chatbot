# src/eval/metrics/llm_judge.py
"""
LLM judge for soft qualities deterministic checks can't catch.

One Gemini Flash call per response. Scores four dimensions on a 0-3 scale:
  - warmth:             empathetic acknowledgment of user's emotional state
  - voice_match:        sounds like a real astrologer vs robotic / template
  - jargon_handled:     technical terms explained in plain language
  - closing_appropriate: phase-correct closing (offer of detail / pivot / acknowledgment)

The judge prompt is strict-JSON. Parsing tolerates markdown fences and is
defensive against partial responses. Failures degrade gracefully (return None
for the call rather than crashing the harness).

Cost: ~$0.0001-0.0003 per scenario depending on response length. With 27
scenarios, a full eval run is ~$0.005-0.01 in LLM judge fees.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


LLM_JUDGE_DIMENSIONS = ("warmth", "voice_match", "jargon_handled", "closing_appropriate")
MAX_SCORE_PER_DIM = 3
LLM_JUDGE_MAX_TOTAL = len(LLM_JUDGE_DIMENSIONS) * MAX_SCORE_PER_DIM  # 12


@dataclass
class JudgeResult:
    warmth: int = 0
    voice_match: int = 0
    jargon_handled: int = 0
    closing_appropriate: int = 0
    reasoning: str = ""
    raw_response: Optional[str] = None
    error: Optional[str] = None

    @property
    def total(self) -> int:
        return self.warmth + self.voice_match + self.jargon_handled + self.closing_appropriate

    @property
    def normalised(self) -> float:
        """0.0 - 1.0"""
        return self.total / LLM_JUDGE_MAX_TOTAL if LLM_JUDGE_MAX_TOTAL else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total"] = self.total
        d["normalised"] = round(self.normalised, 3)
        d["max_total"] = LLM_JUDGE_MAX_TOTAL
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────────────

_JUDGE_PROMPT = """You are evaluating a Vedic astrology chatbot's response to a user.

USER QUESTION:
"{question}"

SCENARIO CONTEXT:
  Phase: {phase}
  Domain: {domain}
  Language: {language}
  User tone: {user_tone}

BOT RESPONSE:
\"\"\"
{response}
\"\"\"

GOLDEN REFERENCE (for tone only — do NOT compare chart facts; user charts differ):
\"\"\"
{golden}
\"\"\"

Rate the BOT RESPONSE on FOUR dimensions, each 0-3 (0=fails, 1=weak, 2=acceptable, 3=excellent):

1. warmth (0-3)
   - 3 = opens with empathetic acknowledgment of user's emotional state ("samajh sakta hoon", "I hear you")
   - 2 = warm but generic
   - 1 = neutral / mechanical
   - 0 = cold or dismissive
   IF the user question is a chitchat greeting/thanks/farewell, give 3 for any natural friendly reply.

2. voice_match (0-3)
   - 3 = sounds like an experienced astrologer talking to a client
   - 2 = professional but slightly templated
   - 1 = mostly templated, repetitive structure
   - 0 = robotic, AI-bot register

3. jargon_handled (0-3)
   - 3 = every technical term (dasha, antardasha, pratyantar, house number) explained in plain language IN CONTEXT
   - 2 = most terms explained
   - 1 = some unexplained jargon
   - 0 = dense jargon, would confuse a non-astrologer
   IF the response uses ZERO jargon (e.g. chitchat), give 3.

4. closing_appropriate (0-3)
   For phase=INITIAL: response should END with an offer to explain in deeper detail
                      (e.g. "Would you like me to explain the reasoning?")
   For phase=AWAITING_DETAIL (detailed answer): response should END with a CROSS-DOMAIN
                      follow-up question pivoting to a different life area
   For phase=FOLLOWUP_LOOP (new pivot topic): response should END with an offer of further depth
   - 3 = closes correctly for the phase
   - 2 = closes with a question but not quite phase-appropriate
   - 1 = closes flatly with no invitation
   - 0 = ends mid-thought or with reviewer/meta text
   IF the user question is chitchat, give 3 for any natural close.

Respond with ONLY this JSON, no markdown fences, no commentary:
{{
  "warmth": <0-3>,
  "voice_match": <0-3>,
  "jargon_handled": <0-3>,
  "closing_appropriate": <0-3>,
  "reasoning": "<one sentence: what was strongest and what was weakest>"
}}
"""


def _coerce_score(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        try:
            n = int(round(float(value)))
        except (TypeError, ValueError):
            return 0
    if n < 0:
        return 0
    if n > MAX_SCORE_PER_DIM:
        return MAX_SCORE_PER_DIM
    return n


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Robust JSON extraction — handles markdown fences and trailing text."""
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text.lower():
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1).strip()
    elif text.startswith("```"):
        m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    text = text.strip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Last resort: extract first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def judge_response_tone(
    question: str,
    response: str,
    golden: str = "",
    phase: str = "INITIAL",
    domain: str = "general",
    language: str = "en",
    user_tone: str = "neutral",
    fast_llm=None,
) -> JudgeResult:
    """
    Score the response on tone/voice/jargon/closing using one LLM call.

    If `fast_llm` is None, returns a zero-score JudgeResult with an error
    flag so the scorecard can still aggregate the deterministic scores.
    """
    if fast_llm is None:
        return JudgeResult(error="no fast_llm provided")

    prompt = _JUDGE_PROMPT.format(
        question=(question or "").replace('"', "'")[:400],
        response=(response or "").replace('"""', "'''")[:1500],
        golden=(golden or "").replace('"""', "'''")[:1500],
        phase=phase or "INITIAL",
        domain=domain or "general",
        language=language or "en",
        user_tone=user_tone or "neutral",
    )

    try:
        out = fast_llm.invoke(prompt)
        raw = out.content if hasattr(out, "content") else str(out)
    except Exception as exc:
        logger.warning("[JUDGE] LLM call failed: %s", exc)
        return JudgeResult(error=f"llm_error: {type(exc).__name__}: {exc}")

    parsed = _extract_json(raw)
    if parsed is None:
        logger.warning("[JUDGE] Could not parse judge JSON")
        return JudgeResult(raw_response=raw[:500], error="unparseable_json")

    return JudgeResult(
        warmth=_coerce_score(parsed.get("warmth")),
        voice_match=_coerce_score(parsed.get("voice_match")),
        jargon_handled=_coerce_score(parsed.get("jargon_handled")),
        closing_appropriate=_coerce_score(parsed.get("closing_appropriate")),
        reasoning=str(parsed.get("reasoning") or "")[:300],
        raw_response=raw[:500],
    )
