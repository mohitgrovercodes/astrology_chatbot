"""
Shared response post-processing and semantic validation.

This module was extracted from `src/api/routes/chat_stateless.py` so:
- chat routes stay focused on orchestration + persistence
- validator logic has a single source of truth
"""

from __future__ import annotations

import json as _json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.api.config import settings
from src.llm.factory import LLMFactory
from config.logger import get_logger

logger = get_logger("response_postprocessor")


_response_validator_llm = None


def _get_response_validator_llm():
    """Lazily create a low-temperature LLM for semantic response validation."""
    global _response_validator_llm
    if _response_validator_llm is None:
        _response_validator_llm = LLMFactory.create(
            purpose="classification",
            temperature=0.1,
        )
    return _response_validator_llm


def _normalized_word_tokens(text: str) -> List[str]:
    """Normalize free text to alphanumeric tokens for stable style matching."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [tok for tok in cleaned.split() if tok]


def _edge_signature(text: str, take_words: int = 9) -> Dict[str, str]:
    """
    Build compact opening/closing signatures for repetition checks.
    Uses normalized tokens so small punctuation differences do not evade matching.
    """
    toks = _normalized_word_tokens(text)
    if not toks:
        return {"opening": "", "closing": ""}
    opening = " ".join(toks[:take_words])
    closing = " ".join(toks[-take_words:])
    return {"opening": opening, "closing": closing}


def _recent_assistant_messages(
    recent_history: List[Dict[str, Any]],
    max_messages: int = 4,
) -> List[str]:
    """Return latest assistant messages from history for session-style memory."""
    msgs: List[str] = []
    for msg in reversed(recent_history or []):
        if msg.get("role") == "assistant" and msg.get("content"):
            msgs.append(str(msg.get("content")))
        if len(msgs) >= max_messages:
            break
    return list(reversed(msgs))


def _build_repetition_guard_context(
    candidate_answer: str,
    recent_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build session-level repetition guard context used by the validator.
    Tracks opening/closing signatures from recent assistant turns.
    """
    recent_answers = _recent_assistant_messages(recent_history, max_messages=4)
    recent_edges = [_edge_signature(a) for a in recent_answers]
    candidate_edge = _edge_signature(candidate_answer)

    opening_repeated = bool(
        candidate_edge["opening"]
        and any(candidate_edge["opening"] == e["opening"] for e in recent_edges if e["opening"])
    )
    closing_repeated = bool(
        candidate_edge["closing"]
        and any(candidate_edge["closing"] == e["closing"] for e in recent_edges if e["closing"])
    )

    return {
        "recent_openings": [e["opening"] for e in recent_edges if e["opening"]],
        "recent_closings": [e["closing"] for e in recent_edges if e["closing"]],
        "opening_repeated": opening_repeated,
        "closing_repeated": closing_repeated,
        "likely_repetition": opening_repeated or closing_repeated,
    }


def validate_and_sanitize_response(
    question: str,
    answer: str,
    intent_analysis: Dict[str, Any],
    recent_history: List[Dict[str, Any]],
    context_window: int = 20,
    min_numbered_points: int = 0,
    detected_language: Optional[str] = None,
) -> str:
    """
    Use a small LLM to semantically validate and, if needed, rewrite the draft
    answer so that it stays consistent with the user's intent and recent context.

    This replaces brittle word-level pattern matching with holistic,
    sentence-level understanding.
    """
    draft_answer = answer or ""
    today_iso = datetime.utcnow().date().isoformat()
    q_lower = (question or "").lower()
    a_lower = draft_answer.lower()
    repetition_ctx = _build_repetition_guard_context(draft_answer, recent_history)

    # Conditional validator: only rewrite when contradiction-risk or tone-risk is
    # likely, OR when we explicitly require numbered reasoning points (detailed mode).
    # This avoids flattening naturally good responses while still enforcing structure
    # when requested.
    risk_keywords = (
        "divorce", "separation", "talaq", "breakup", "remarriage",
        "children", "pregnancy", "job", "career", "marriage", "shaadi"
    )
    contradiction_markers = (
        "definitely", "guaranteed", "100%", "certainly happen"
    )
    likely_sensitive = any(k in q_lower for k in risk_keywords)
    likely_overconfident = any(m in a_lower for m in contradiction_markers)
    likely_short_or_generic = len(draft_answer.split()) < 25
    likely_repetition = bool(repetition_ctx.get("likely_repetition"))
    needs_numbering_enforcement = bool(min_numbered_points and min_numbered_points > 0)
    should_validate = (
        likely_sensitive
        or likely_overconfident
        or likely_short_or_generic
        or likely_repetition
        or needs_numbering_enforcement
    )

    if not should_validate:
        logger.debug(
            "[VALIDATOR] skip: "
            f"likely_sensitive={likely_sensitive}, likely_overconfident={likely_overconfident}, "
            f"likely_short_or_generic={likely_short_or_generic}, likely_repetition={likely_repetition}, "
            f"needs_numbering_enforcement={needs_numbering_enforcement}"
        )
        return draft_answer

    logger.info(
        "[VALIDATOR] run semantic validator: "
        f"likely_sensitive={likely_sensitive}, "
        f"likely_overconfident={likely_overconfident}, "
        f"likely_short_or_generic={likely_short_or_generic}, "
        f"likely_repetition={likely_repetition}, "
        f"needs_numbering_enforcement={needs_numbering_enforcement}, "
        f"min_numbered_points={min_numbered_points}, "
        f"detected_language={detected_language!r}"
    )

    def _count_numbered_points(text: str) -> int:
        """
        Best-effort counter for clearly numbered lines like:
        '1) ...', '2. ...', '1 - ...'. Used to enforce minimum structured
        astrological reasoning points in detailed responses.
        """
        if not text:
            return 0
        count = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Arabic digits: 1) 2. 3-
            if re.match(r"^[0-9]+[\)\.\-\:]\s+", stripped):
                count += 1
                continue
            # Basic Devanagari digits: १) २. ३-
            if re.match(r"^[\u0966-\u096f]+[\)\.\-\:]\s+", stripped):
                count += 1
                continue
        return count

    def _safe_score(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _looks_like_meta_review(text: str) -> bool:
        """
        Guardrail: sometimes validator LLM returns critique text ("The draft answer...")
        instead of a user-facing rewrite. Never surface that to end users.
        """
        t = (text or "").strip().lower()
        if not t:
            return False
        meta_markers = (
            "the draft answer",
            "does not adequately",
            "lacks",
            "the user's inquiry",
            "the response should",
            "this draft",
        )
        return any(m in t for m in meta_markers)

    def _add_months(base_date, months: int):
        m = max(0, int(months))
        y = base_date.year + (base_date.month - 1 + m) // 12
        mm = (base_date.month - 1 + m) % 12 + 1
        return base_date.replace(year=y, month=mm, day=1)

    def _normalize_timeline_text(text: str) -> str:
        """
        Deterministic timeline hygiene:
        1) Convert duration-only ranges (e.g., 6-18 months / 6-18 mahine) to month-year windows.
        2) Fix past-year + future-verb mismatch (e.g., "2025 se shuru hoga").
        3) Remove ended past month/year prediction ranges and replace with future-facing fallback.
        """
        if not text:
            return text

        now = datetime.utcnow().date().replace(day=1)
        current_year = now.year

        def _duration_repl(match):
            a = int(match.group(1))
            b = int(match.group(2))
            unit = (match.group(3) or "").lower()
            if b < a:
                a, b = b, a
            if b > 48:
                return match.group(0)
            s = _add_months(now, a)
            e = _add_months(now, b)
            if any(k in unit for k in ("mahine", "saal")):
                return f"{s.strftime('%B %Y')} se {e.strftime('%B %Y')} tak"
            return f"from {s.strftime('%B %Y')} to {e.strftime('%B %Y')}"

        text = re.sub(
            r"(?i)\b(\d{1,2})\s*-\s*(\d{1,2})\s*(months?|mahine|years?|saal)\b",
            _duration_repl,
            text,
        )

        def _past_future_repl(match):
            year = int(match.group(1))
            middle = match.group(2) or ""
            verb = (match.group(3) or "").lower()
            if year >= current_year:
                return match.group(0)
            if "will" in verb:
                fixed_verb = "started and is currently active"
            else:
                fixed_verb = "shuru ho chuka hai aur abhi active hai"
            return f"{year}{middle}{fixed_verb}"

        text = re.sub(
            r"(?i)\b((?:19|20)\d{2})([^.\n]{0,40}?)(shuru\s+hoga|shuru\s+hogi|shuru\s+honge|will\s+start|will\s+begin)\b",
            _past_future_repl,
            text,
        )

        month_re = (
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        )
        range_re = re.compile(
            rf"(?i)\b({month_re}\s+(?:19|20)\d{{2}})\s*(?:to|until|till|se|tak|→|-|–|—)\s*({month_re}\s+(?:19|20)\d{{2}})\b"
        )
        year_range_re = re.compile(
            r"(?i)\b((?:19|20)\d{2})\s*(?:to|until|till|se|tak|-|–|—)\s*((?:19|20)\d{2})\b"
        )

        def _parse_my(val: str):
            v = (val or "").strip()
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return datetime.strptime(v, fmt).date().replace(day=1)
                except Exception:
                    continue
            return None

        predictive_markers = (
            "favorable", "supportive", "opportunity", "chance", "hoga", "hogi", "milega",
            "milegi", "shubh", "anukul", "sambhavna", "trip", "travel", "marriage", "shadi",
            "career", "job", "finance",
        )

        sentences = re.split(r"(?<=[.!?।])\s+", text)
        kept = []
        removed = 0
        for s in sentences:
            st = s.strip()
            if not st:
                continue
            lower = st.lower()
            has_predictive = any(m in lower for m in predictive_markers)
            drop = False

            m = range_re.search(st)
            if m and has_predictive:
                end_d = _parse_my(m.group(2))
                if end_d and end_d < now:
                    drop = True

            if not drop:
                y = year_range_re.search(st)
                if y and has_predictive:
                    if int(y.group(2)) < now.year:
                        drop = True

            if drop:
                removed += 1
                continue
            kept.append(st)

        if removed > 0:
            start = _add_months(now, 2)
            end = _add_months(now, 8)
            has_dev = any("\u0900" <= ch <= "\u097F" for ch in text)
            is_hinglish = (not has_dev) and any(tok in text.lower() for tok in ["aap", "hai", "ke", "mein", "shadi", "samay"])
            if has_dev:
                fallback = (
                    f"आगे के लिए अधिक व्यावहारिक और सहायक समय {start.strftime('%B %Y')} से {end.strftime('%B %Y')} के बीच दिखता है।"
                )
            elif is_hinglish:
                fallback = (
                    f"Aage ke liye practical supportive period {start.strftime('%B %Y')} se {end.strftime('%B %Y')} tak dikh raha hai."
                )
            else:
                fallback = (
                    f"A practical supportive future period appears between {start.strftime('%B %Y')} and {end.strftime('%B %Y')}."
                )
            kept.append(fallback)

        text = " ".join(kept).strip()
        return text

    def _has_ended_past_timeline_reference(text: str) -> bool:
        if not text:
            return False
        now = datetime.utcnow().date().replace(day=1)
        month_re = (
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        )
        range_re = re.compile(
            rf"(?i)\b({month_re}\s+(?:19|20)\d{{2}})\s*(?:to|until|till|se|tak|→|-|–|—)\s*({month_re}\s+(?:19|20)\d{{2}})\b"
        )
        year_range_re = re.compile(
            r"(?i)\b((?:19|20)\d{2})\s*(?:to|until|till|se|tak|-|–|—)\s*((?:19|20)\d{2})\b"
        )

        def _parse_my(val: str):
            v = (val or "").strip()
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return datetime.strptime(v, fmt).date().replace(day=1)
                except Exception:
                    continue
            return None

        for m in range_re.finditer(text):
            end_d = _parse_my(m.group(2))
            if end_d and end_d < now:
                return True
        for y in year_range_re.finditer(text):
            if int(y.group(2)) < now.year:
                return True
        return False

    def _is_mostly_english(text: str) -> bool:
        if not text:
            return False
        words = re.findall(r"[A-Za-z]+", text.lower())
        if not words:
            return False
        common = {
            "the", "and", "for", "with", "your", "you", "this", "that", "will", "from",
            "period", "future", "relationship", "marriage", "insight", "summary", "context",
        }
        hit = sum(1 for w in words if w in common)
        return (hit / max(1, len(words))) > 0.08

    def _has_hinglish_markers(text: str) -> bool:
        t = (text or "").lower()
        markers = ["aap", "hai", "hain", "ki", "ka", "ke", "mein", "se", "tak", "samay", "shadi", "kya"]
        return sum(1 for m in markers if m in t) >= 3

    def _language_or_script_violation(text: str, expected: Optional[str]) -> bool:
        exp = (expected or "").strip().lower()
        if not exp:
            return False
        dev_count = sum(1 for ch in (text or "") if "\u0900" <= ch <= "\u097F")

        if exp == "hi":
            return dev_count < 8
        if exp == "hi-lat":
            # Hinglish should be in Latin script and not plain generic English.
            if dev_count > 0:
                return True
            return _is_mostly_english(text) and not _has_hinglish_markers(text)
        if exp == "en":
            return dev_count > 0
        return False

    def _has_robotic_heading_leak(text: str) -> bool:
        if not text:
            return False
        heading_patterns = [
            r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(current dasha context|upcoming pratyantar period|future activation period|broader future period|long-term perspective)\*?\*?\s*:",
            r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(chart strengths and positive aspects|gochara insights|yogas and potential challenges)\*?\*?\s*:",
            r"(?i)\blet'?s delve deeper\b",
        ]
        return any(re.search(p, text) for p in heading_patterns)

    try:
        conv_snippet: List[str] = []
        for msg in (recent_history or [])[-context_window:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conv_snippet.append(f"{role.upper()}: {content}")
        conv_text = "\n".join(conv_snippet) or "No previous messages"

        analysis = intent_analysis or {}

        validator_prompt = f"""You are a semantic validator AND style judge for an astrology chatbot.

Your job is to check whether the assistant's draft answer is:
- logically correct and non-contradictory
- emotionally appropriate to what the user asked
- consistent with the recent conversation history
- written in the natural voice of a warm, expert astrologer (NOT a generic AI assistant)

You MUST rely on MEANING, not keyword matching. Think about what the user is
really asking and whether the answer respects that.

You must pay special attention to these cases:

1) DIVORCE / SEPARATION QUERIES
   - When the user asks about divorce or separation, the answer MUST:
     • Acknowledge that the user is asking about possible strain, distance, or separation.
     • Focus on relationship pressure/tension phases, and talk gently about communication,
       boundaries, or counseling.
   - The answer MUST NOT:
     • Re-start the discussion as if it is a "happy marriage timing" or "favourable time for marriage".
     • Celebrate getting a new partner, strong romantic progress, or "bahut hi accha/sukhad samay"
       for marriage immediately after a divorce question.
   - Only talk about favourable marriage / remarriage timing if the user explicitly asks
     about remarriage in a later question.

2) TIMELINE COHERENCE
   - If the chat already stated a clear FUTURE window for a life event (marriage, job, career,
     foreign travel, children, etc.), do NOT allow a later answer to confidently state a
     completely different, non-overlapping window for the SAME topic unless you clearly frame
     it as a refinement or secondary/supporting period.
   - For example, if the initial answer said "2027 ke beech se 2028 ke aas-paas shadi ke strong
     yog dikh rahe hain", the detailed follow-up should EITHER reuse that 2027–2028 window,
     OR explain it as "core" and then optionally add a nearby supporting sub‑window, not jump
     to something like "2024 ke end tak" as the main window.
   - When the chat already gave a specific timing, prefer to KEEP that timing and add depth
     (houses, dashas, yogas, divisional charts) rather than inventing a new, contradictory one.
   - For divorce/separation specifically, do NOT push it clearly BEFORE a strong future marriage
     window that you already stated. In such cases, soften the timing for divorce (e.g.,
     "aane wale kuch saalon mein") and emphasize emotional themes rather than hard earlier dates.

3) GENERAL COHERENCE
   - Avoid sentences that directly contradict what was said just before
     (e.g., "no children possible" right after "strong chance for children in 2028").
   - Avoid robotic repetition of the same phrasing; keep the tone natural and human.
   - If the DRAFT answer already ends with a clear, user-facing follow-up question
     (for example, inviting them to ask more about a specific topic), your revised
     answer MUST also end with a natural follow-up question in the SAME spirit and
     on the SAME topic, unless the conversation has clearly moved on. Do NOT strip
     away the closing question and leave the user hanging.
   - When the user's question is a simple, everyday request (e.g. "meri shadi kab hogi",
     "job kab milegi", "ghar kab kharid paunga") and does NOT contain astrological
     jargon, the SHORT initial answer must also avoid explicit house/planet/dasha
     terminology (no "7th house", "lord", "Venus", "Mars", "dasha", etc.). In such
     cases, if the draft uses these technical terms in a brief timing answer, rewrite
     them into plain-life language (supportive phase, opportunity, pressure, etc.)
     while keeping the timing window and meaning intact.

   - FUTURE-ONLY TIMING (NON-NEGOTIABLE):
     • TODAY is {today_iso}.
     • Do NOT output past timing windows as prediction windows.
    • Any explicit month/year/date ranges in the revised answer must start in the future (after TODAY), not active-now.
    • If a range has already started (ongoing) or has passed, reframe it into future/supportive windows from TODAY onward.
    • Unless user explicitly asks for urgent/immediate timing, avoid ultra-near windows and prefer windows starting at least ~2 months ahead.
     • For user-facing timelines, prefer explicit month-year ranges ("Aug 2026 to Nov 2026")
       and avoid duration-only phrases like "6-18 months" / "6-18 mahine" as final timing.

4) LIFE-EVENT ORDERING (CRITICAL)
   - NEVER make the timeline of major life events obviously backwards relative to what
     the conversation already established. Examples of IMPOSSIBLE orderings:
       • Predicting divorce clearly BEFORE a strong future marriage window that you
         already stated in this conversation.
       • Saying the user will have children clearly BEFORE marriage, when earlier
         messages framed marriage as a necessary prior step.
       • Saying a second marriage window that begins clearly BEFORE the first marriage
         window you already gave.
   - When you detect such a conflict, you MUST:
       • Keep the emotional truth (e.g., "tension", "distance", "responsibility for family"),
         but soften or widen the timing ("aane wale kuch saalon mein", "2026 ke baad ke kuch
         saal") instead of giving a hard, earlier year or narrow window that breaks the
         logical order.
       • If needed, explicitly say that astrology shows phases of pressure or change rather
         than a precise date, so you do not contradict the already stated sequence of events.

5) TONE & VOICE QUALITY (LLM-AS-A-JUDGE)
   - The final answer must sound like a professional, warm astrologer speaking directly
     to the user, not like a generic AI model or technical report.
   - Strongly avoid generic "AI-speak" phrases such as: "let's delve into", "as an AI",
     "cutting-edge", "state-of-the-art model", "this is a testament to", or anything that
     breaks the illusion of a human astrologer.
   - Prefer astro-appropriate, probabilistic wording:
       • Instead of "guaranteed", "definitely", "certain", prefer "strong support", "zyada sambhavna",
         "indicates", "tends to manifest", "suggests a phase where...".
       • Emphasize free will, effort and practical choices over fate or fixed destiny.
   - Preserve the user's language and script from the draft answer. If the draft is in Hindi
     or Hinglish, your revision must also be in the same language/script (do NOT switch to English).
   - You may gently improve phrasing, flow and warmth as long as you do not change factual content,
     dates, or key timing windows already stated in the draft.

6) EMOTIONAL MIRROR + SESSION REPETITION GUARD
   - The opening line should briefly mirror the user's emotional intent when appropriate
     (e.g., concern, confusion, urgency, hope) before analysis.
   - Avoid repeating the same opening/closing style used in recent assistant replies.
   - If this draft repeats recent opening/closing signatures, rewrite with fresh phrasing
     while preserving facts and timing.

RECENT STYLE MEMORY (normalized phrase signatures from latest assistant turns):
- Recent openings: {_json.dumps(repetition_ctx.get("recent_openings", []), ensure_ascii=False)}
- Recent closings: {_json.dumps(repetition_ctx.get("recent_closings", []), ensure_ascii=False)}
- Candidate flags: opening_repeated={repetition_ctx.get("opening_repeated")}, closing_repeated={repetition_ctx.get("closing_repeated")}

EXAMPLE CORRECTIONS (FEW-SHOT GUIDANCE)

Example 1 – BAD marriage tone after divorce question:
- CONTEXT:
  - Earlier answer: "2027 ke shuruat se 2028 ke beech shaadi ke sabse strong yog dikh rahe hain..."
  - USER now: "Meri divorce kab hoga?"
- DRAFT: "Aapke liye shadi ka samay abhi bahut hi favourable dikh raha hai..."
- YOU SHOULD REWRITE AS (Hindi tone preserved, but meaning fixed):
  "Aapke sawal se yeh samajh aata hai ki aap apne rishte mein alag hone ya bade badlav ki sambhavana ke baare mein soch rahe hain. Chart ke hisaab se aane wale kuch saalon mein aise phases aa sakte hain jahan tanav, doori ya uljhan zyada mehsoos ho, khaas taur par 2026 ke doosre aadhe se 2027 ke dauran. Is daur ko jaldi decision ke bajay khuli baat-cheet, boundaries clear karne aur zarurat pade to counseling ke zariye handle karna zyada sehatmand rahega. Astrology yeh batati hai ki yeh ek pressure phase hai jahan aapko apni emotional safety, respect aur bhavishya ke baare mein soch-samajh kar kadam rakhna chahiye. Kya aap chahenge ki main aapko is phase ke exact months aur chart ke un factors ke baare mein bataun jo yeh tanav dikhate hain?"

Example 2 – BAD divorce before earlier marriage window:
- CONTEXT:
  - Earlier: "Shaadi ke liye sabse strong window 2027–2028 ke beech dikh rahi hai."
  - USER now: "Mera divorce kab hoga?"
- DRAFT: "2026 ke beech tak divorce hone ke chances strong hain."
- YOU SHOULD REWRITE AS:
  "Pehle humne dekha tha ki 2027–2028 ke aas-paas shaadi ke liye strong support dikh raha hai, isliye usse pehle hi exact divorce saal batana theek nahi hoga. Chart yeh dikhata hai ki shaadi ke baad kuch saalon mein zimmedariyon aur expectations ke chalte rishte par pressure aa sakta hai, jahan tanav ya doori mehsoos ho. Is tarah ke daur ko samvaad, practical support aur zarurat pade to counseling se kaafi had tak sambhala ja sakta hai. Agar aap separation ke baare mein soch rahe hain, to pehle apni emotional aur financial safety par dhyan dena zaruri hai, na ki sirf tareekh par."

Example 3 – GOOD draft you should keep:
- CONTEXT:
  - USER: "Mujhe government job kab milegi?"
- DRAFT:
  "Aapke liye sarkari naukri ke liye sabse zyada support 2026 ke doosre aadhe se lekar 2027 ke pehle hisson tak dikhai deta hai. Is dauran exams, interviews aur selection ke liye active rehna aapke liye zyada fruitful ho sakta hai. Agar aap is period mein focused preparation karein, to ek stable government job milne ke chances mazboot dikhai dete hain."
- In this case, "is_coherent": true, "needs_revision": false, "revised_answer": "".

CONVERSATION (last {context_window} messages):
{conv_text}

LATEST USER QUESTION:
USER: "{question}"

INTENT ANALYSIS (for your reference):
{_json.dumps(analysis, ensure_ascii=False)}

DRAFT ASSISTANT ANSWER (in user's language):
ASSISTANT_DRAFT:
\"\"\"{draft_answer}\"\"\"

IMPORTANT DECISION RULE:
- If draft is already coherent, context-appropriate and naturally phrased, preserve it — UNLESS
  a specific numbered structure has been requested.
- Rewrite when there is a real contradiction, tone/voice mismatch, obvious generic AI phrasing,
  major coherence break, OR when the answer fails to provide the minimum number of numbered
  astrological reasoning points requested.
- Your revised answer must be direct user-facing astrology guidance, NEVER a reviewer note,
  audit explanation, or critique of the draft.

STRUCTURE ENFORCEMENT (if requested):
- When 'min_numbered_points' is > 0, you MUST ensure that the final answer contains AT LEAST
  that many clearly numbered points (for example: "1)", "2)", "3)", etc.), and you should
  NOT artificially stop at that number if more distinct, meaningful factors are available.
- Each numbered point should describe a distinct astrological factor AND what it means for
  the user. These points can appear after a short narrative introduction, but they must be
  present and easy for the user to see and count.

Respond in STRICT JSON ONLY, no extra text, like this:
{{
  "is_coherent": true/false,
  "needs_revision": true/false,
  "reason": "short explanation of any problem you see",
  "revised_answer": "a fully corrected answer in the SAME LANGUAGE as the draft, or empty string if no change is needed",
  "human_warmth_score": 1-10,
  "authentic_astrologer_voice_score": 1-10,
  "repetition_risk_score": 1-10,
  "min_numbered_points": """ + str(int(min_numbered_points or 0)) + """
}}"""

        llm = _get_response_validator_llm()
        resp = llm.invoke(validator_prompt)
        raw = getattr(resp, "content", str(resp))
        data = _json.loads(raw)

        if isinstance(data, dict):
            logger.debug(
                "[VALIDATOR] model verdict: "
                f"needs_revision={data.get('needs_revision')}, "
                f"repetition_risk_score={data.get('repetition_risk_score')}, "
                f"human_warmth_score={data.get('human_warmth_score')}, "
                f"authentic_astrologer_voice_score={data.get('authentic_astrologer_voice_score')}, "
                f"min_numbered_points={data.get('min_numbered_points')}"
            )

        final_answer = draft_answer
        if isinstance(data, dict) and data.get("needs_revision") and data.get("revised_answer"):
            candidate = str(data.get("revised_answer", "")).strip()
            if _looks_like_meta_review(candidate):
                logger.warning("[VALIDATOR] Ignoring meta-review text returned as revised_answer; keeping draft.")
            else:
                logger.info("[VALIDATOR] Accepted revised answer from validator.")
                final_answer = candidate
        else:
            logger.debug("[VALIDATOR] no LLM revision accepted (keeping draft unless deterministic fixes trigger).")

        # Secondary style gate: enforce warmth/authenticity/repetition quality
        # even when the model marks the draft as coherent.
        if isinstance(data, dict):
            warmth = _safe_score(data.get("human_warmth_score", 10), 10)
            authenticity = _safe_score(data.get("authentic_astrologer_voice_score", 10), 10)
            repetition_risk = _safe_score(data.get("repetition_risk_score", 1), 1)
            min_warmth = max(1, min(10, int(getattr(settings, "STYLE_MIN_HUMAN_WARMTH_SCORE", 7))))
            min_auth = max(1, min(10, int(getattr(settings, "STYLE_MIN_AUTHENTIC_ASTROLOGER_VOICE_SCORE", 7))))
            max_repeat = max(1, min(10, int(getattr(settings, "STYLE_MAX_REPETITION_RISK_SCORE", 4))))
            # Style rewrite disabled — few-shot examples handle warmth and tone.
            # Previously caused a second LLM call that added latency and could override
            # the natural prose written by the model following the golden examples.
            needs_style_rewrite = False

            if needs_style_rewrite and not (data.get("needs_revision") and data.get("revised_answer")):
                logger.info(
                    "[VALIDATOR] Style rewrite triggered "
                    f"(warmth={warmth}<{min_warmth}, "
                    f"authenticity={authenticity}<{min_auth}, "
                    f"repetition_risk={repetition_risk}>{max_repeat})"
                )
                style_rewrite_prompt = f"""You are a response polishing editor for an astrology assistant.

Rewrite the answer so that it:
- keeps the SAME factual content, timing windows, and astrological meaning
- stays in the SAME language/script
- sounds warm, natural, and like a real expert astrologer
- starts with a brief emotional mirror of the user's concern (1 line max)
- avoids repeating recent opening/closing phrasing
- remains concise and user-facing (not a report)

Do NOT invent new dates, planets, houses, or claims.

RECENT STYLE MEMORY:
- Openings: {_json.dumps(repetition_ctx.get("recent_openings", []), ensure_ascii=False)}
- Closings: {_json.dumps(repetition_ctx.get("recent_closings", []), ensure_ascii=False)}

USER QUESTION:
\"\"\"{question}\"\"\"

ANSWER TO REWRITE:
\"\"\"{final_answer}\"\"\"

Return ONLY the rewritten answer text."""
                style_resp = llm.invoke(style_rewrite_prompt)
                polished = getattr(style_resp, "content", str(style_resp)).strip()
                if polished:
                    final_answer = polished

        # Deterministic post-check: if we explicitly require numbered points
        # and the current answer still does not meet the minimum, trigger a
        # second, focused rewrite pass that ONLY enforces numbered structure.
        if needs_numbering_enforcement:
            required_points = int(min_numbered_points or 0)
            current_points = _count_numbered_points(final_answer)
            if current_points < required_points:
                logger.info(
                    f"[VALIDATOR] Numbering enforcement: found {current_points} "
                    f"points, required {required_points}. Forcing rewrite."
                )
                rewrite_prompt = f"""You are an astrology editor.

Rewrite the assistant's answer so that it:
- keeps the SAME timing windows, planets, houses and factual content
- stays in the SAME LANGUAGE and script as the original answer
- sounds like a warm, professional astrologer
- and MOST IMPORTANTLY, presents AT LEAST {required_points} clearly numbered
  astrological reasoning points (for example: "1) ...", "2) ...", "3) ...").

Guidelines:
- You may add short connector sentences, but do NOT invent new dates or change years.
- Group related ideas into numbered points so that each point describes ONE key factor
  (house lord, dasha/pratyantar, yoga, planetary condition, divisional chart insight, etc.)
  and directly states what it means for this person's life.
- You may keep a short 1–2 sentence introduction BEFORE the numbered list.
- CRITICAL: If the original answer ends with a question about a DIFFERENT life area (e.g. career, health, marriage, children, finances), you MUST preserve that exact question at the very end of your rewrite. Do NOT replace it with an offer for more detail or further explanation.

Return ONLY the rewritten answer text, no JSON, no explanation.

ORIGINAL ANSWER:
\"\"\"{final_answer}\"\"\"
"""
                resp2 = llm.invoke(rewrite_prompt)
                rewritten = getattr(resp2, "content", str(resp2)).strip()
                if rewritten and not _looks_like_meta_review(rewritten):
                    logger.info("[VALIDATOR] Applied forced numbered-structure rewrite")
                    final_answer = rewritten

                # After the LLM rewrite, run a deterministic fallback to guarantee
                # visible numbering if the model still did not meet the requirement.
                post_points = _count_numbered_points(final_answer)
                if post_points < required_points:
                    logger.info(
                        f"[VALIDATOR] Deterministic numbering fallback: found {post_points}, "
                        f"required {required_points}. Prefixing numbered points."
                    )
                    lines = final_answer.splitlines()
                    numbered_lines: List[str] = []
                    point_idx = 1
                    for line in lines:
                        stripped = line.strip()
                        if (
                            stripped
                            and point_idx <= required_points
                            and not re.match(r"^[0-9\u0966-\u096f]+[\)\.\-\:]\s+", stripped)
                        ):
                            numbered_lines.append(f"{point_idx}) {line.lstrip()}")
                            point_idx += 1
                        else:
                            numbered_lines.append(line)
                    final_answer = "\\n".join(numbered_lines)

        final_answer = _normalize_timeline_text(final_answer)

        # HARD FAIL-SAFE: never return ended past prediction ranges.
        # 1) One forced rewrite pass.
        # 2) If still present, deterministic cleanup via timeline normalizer.
        if _has_ended_past_timeline_reference(final_answer):
            logger.warning("[VALIDATOR] Ended past timeline detected post-normalization. Forcing one additional rewrite.")
            hard_fix_prompt = f"""You are fixing timeline safety in an astrology answer.

TODAY is {today_iso}.

Rewrite the answer so that:
- it keeps the SAME main astrological meaning and language/script
- it removes any ended past prediction ranges
- all prediction windows are strictly future-starting month-year ranges (not already started)
- unless user explicitly asked immediate timing, avoid windows that begin in the same/next month
- no exact day-level dates

Return ONLY the corrected answer text.

ANSWER:
\"\"\"{final_answer}\"\"\"
"""
            hard_resp = llm.invoke(hard_fix_prompt)
            hard_text = getattr(hard_resp, "content", str(hard_resp)).strip()
            if hard_text and not _looks_like_meta_review(hard_text):
                final_answer = _normalize_timeline_text(hard_text)

        if _has_ended_past_timeline_reference(final_answer):
            logger.warning("[VALIDATOR] Ended past timeline still present after forced rewrite. Applying deterministic final cleanup.")
            final_answer = _normalize_timeline_text(final_answer)

        # HARD FAIL-SAFE: keep language/script consistent and avoid robotic report headings.
        if _language_or_script_violation(final_answer, detected_language) or _has_robotic_heading_leak(final_answer):
            logger.warning(
                "[VALIDATOR] Language/script or heading-style violation detected. Forcing one natural-voice rewrite."
            )
            _lang = (detected_language or "same as draft").strip()
            style_fix_prompt = f"""You are fixing final response style for an astrology chatbot.

Rewrite the answer so that:
- it stays in { _lang } language/script (or same as draft if unknown),
- it sounds like natural conversational astrologer guidance,
- it does NOT use report-like headings such as:
  "Current Dasha Context", "Upcoming Pratyantar Period", "Broader Future Period", "Long-term Perspective",
- it does NOT use phrases like "Let's delve deeper",
- it preserves the same factual meaning and timing windows.

Return ONLY the corrected answer text.

ANSWER:
\"\"\"{final_answer}\"\"\"
"""
            style_fix_resp = llm.invoke(style_fix_prompt)
            style_fixed = getattr(style_fix_resp, "content", str(style_fix_resp)).strip()
            if style_fixed and not _looks_like_meta_review(style_fixed):
                final_answer = _normalize_timeline_text(style_fixed)
                # deterministic phrase cleanup if model still leaked headings
                final_answer = re.sub(
                    r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(current dasha context|upcoming pratyantar period|future activation period|broader future period|long-term perspective|chart strengths and positive aspects|gochara insights|yogas and potential challenges)\*?\*?\s*:\s*",
                    "",
                    final_answer,
                )
                final_answer = re.sub(r"(?i)\blet'?s delve deeper\b", "Chaliye detail mein samajhte hain", final_answer)

        # Final hard guard: never return reviewer/meta text to end users.
        if _looks_like_meta_review(final_answer):
            logger.warning("[VALIDATOR] Final answer looked like meta-review text; reverting to draft answer.")
            final_answer = draft_answer

        return final_answer
    except Exception as e:
        logger.info(f"[VALIDATOR] Error in LLM response validator: {e}")
        return draft_answer

