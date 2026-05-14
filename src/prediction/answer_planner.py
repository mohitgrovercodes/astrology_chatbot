# src/prediction/answer_planner.py
"""
Deterministic Answer Planner for NakshatraAI V2.

Problem solved (Improvement #3):
  The LLM currently receives: full chart data + synthesis dump + dasha stack +
  FactorScorer focus block + RAG chunks — a rich corpus — but no committed plan.
  It must simultaneously choose what to say, how to order it, what tone to use,
  and when to anchor timing.  The result is inconsistent structure: sometimes
  timing-first, sometimes quality-first, sometimes a "both are true" hedge.

What this module does:
  Before the LLM sees ANY of the above, we deterministically commit to:

    1. primary_factors   — ordered list of 2–3 factors from FactorScorer (already
                           ranked by domain × dasha × validation).
    2. committed_timing  — the single best PAD window from timeline_windows
                           (highest confidence, domain-matched first).
    3. divisional_chart  — which D-chart the LLM should reference for this domain.
    4. tone_stance       — one of "encouraging" | "balanced" | "cautious_honest"
                           computed from overall_strength + polarity + question_mode.
    5. narrative_anchor  — a plain-English template sentence that the LLM must
                           use as its structural anchor (not quoted verbatim).

  The resulting `AnswerPlan.plan_block` is injected as a **committed plan** block
  at the top of the reasoning scratchpad, BEFORE the scratchpad instructions.
  This forces the LLM to reason within the plan rather than improvise one.

Usage:
    from src.prediction.answer_planner import build_answer_plan, AnswerPlan

    plan = build_answer_plan(
        factor_plan=factor_plan,          # from factor_scorer.score_factors()
        astro_evidence=astro_evidence,    # from astro_intelligence_layer.build_astro_evidence()
        synthesis=state.get('synthesis'), # from ChartSynthesisEngine
        validation_result=state.get('validation_result'),
        intent_analysis=intent_analysis,  # semantic_frame.to_legacy_intent_analysis()
    )
    # plan.plan_block → inject at top of reasoning_scratchpad_block
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Domain → primary divisional chart  (D-number, Sanskrit name, what it reveals)
# ──────────────────────────────────────────────────────────────────────────────
_DOMAIN_DIVISIONAL: Dict[str, Dict[str, str]] = {
    "marriage":    {"chart": "D-9",  "name": "Navamsha",         "reveals": "marriage timing, partner qualities, dharma in relationships"},
    "divorce":     {"chart": "D-9",  "name": "Navamsha",         "reveals": "relationship strain; D-6 (Shashthamsha) for conflict patterns"},
    "career":      {"chart": "D-10", "name": "Dashamsha",        "reveals": "professional standing, authority, career trajectory"},
    "finance":     {"chart": "D-2",  "name": "Hora",             "reveals": "accumulated wealth; D-11 for gains"},
    "children":    {"chart": "D-7",  "name": "Saptamsha",        "reveals": "progeny strength, timing for children"},
    "health":      {"chart": "D-6",  "name": "Shashthamsha",     "reveals": "disease predisposition, recovery potential"},
    "home":        {"chart": "D-4",  "name": "Chaturthamsha",    "reveals": "immovable property, ancestral home, peace of mind"},
    "foreign":     {"chart": "D-12", "name": "Dwadashamsha",     "reveals": "foreign settlement potential, parental karma, long journeys"},
    "education":   {"chart": "D-24", "name": "Chaturvimshamsha", "reveals": "depth of learning, academic achievement"},
    "spirituality":{"chart": "D-20", "name": "Vimshamsha",       "reveals": "spiritual practice, past-life karma, liberation path"},
    "general":     {"chart": "D-1",  "name": "Rashi",            "reveals": "overall life trajectory and current planetary periods"},
}


# ──────────────────────────────────────────────────────────────────────────────
# Tone stance thresholds
# ──────────────────────────────────────────────────────────────────────────────
_TONE_ENCOURAGING   = "encouraging"
_TONE_BALANCED      = "balanced"
_TONE_CAUTIOUS      = "cautious_honest"


def _compute_tone(
    overall_strength: float,
    polarity: str,
    question_mode: str,
    has_critical_failures: bool,
) -> str:
    """
    Map validation strength + semantic polarity → tone stance.

    Rules (priority order):
      1. Critical failures present              → cautious_honest regardless of strength
      2. overall_strength >= 7.0 and not negative polarity → encouraging
      3. overall_strength <= 3.5 or polarity == 'negative' → cautious_honest
      4. timing question mode                   → balanced (timing questions need precision, not cheerfulness)
      5. Default                                → balanced
    """
    if has_critical_failures:
        return _TONE_CAUTIOUS

    if overall_strength >= 7.0 and polarity not in ("negative", "challenging"):
        return _TONE_ENCOURAGING

    if overall_strength <= 3.5 or polarity in ("negative", "challenging"):
        return _TONE_CAUTIOUS

    if question_mode in ("timing", "prediction"):
        return _TONE_BALANCED

    return _TONE_BALANCED


# ──────────────────────────────────────────────────────────────────────────────
# Narrative anchor templates
# ──────────────────────────────────────────────────────────────────────────────
# Keys: (question_mode, tone_stance, has_timing_window)
# The anchor is a structural instruction, not a verbatim quote.
_NARRATIVE_ANCHORS: Dict[tuple, str] = {
    # timing + encouraging
    ("timing",   _TONE_ENCOURAGING, True):  (
        "Affirm the strongest factor first (brief, specific), then introduce the "
        "committed timing window as the primary answer, then close with one actionable step."
    ),
    ("timing",   _TONE_ENCOURAGING, False): (
        "Affirm the strongest factor, then explain WHY timing is uncertain from the dasha "
        "stack, then offer the closest supportive period as a working estimate."
    ),
    ("timing",   _TONE_CAUTIOUS, True):  (
        "Acknowledge the challenge or delay plainly (no sugarcoating), then offer the "
        "committed window as the most realistic timeframe, then add one constructive suggestion."
    ),
    ("timing",   _TONE_CAUTIOUS, False): (
        "Be honest that chart factors create delay or uncertainty, and explain why without "
        "false hope. Offer a general period range based on dasha progression."
    ),
    ("timing",   _TONE_BALANCED, True):  (
        "Name the active dasha combination, connect it to the domain, introduce the "
        "committed window, then briefly note supporting or limiting factors."
    ),
    ("timing",   _TONE_BALANCED, False): (
        "Explain the active dasha combination and its expected effects on the domain, "
        "then give a qualitative timing estimate based on dasha progression."
    ),
    # advice + encouraging
    ("advice",   _TONE_ENCOURAGING, True):  (
        "Lead with the strongest asset the chart shows for this domain, then advise "
        "leveraging the upcoming favorable window, then give one practical step."
    ),
    ("advice",   _TONE_ENCOURAGING, False): (
        "Lead with the chart's strongest asset, explain what this period favors, "
        "then give two concrete actions the person can take now."
    ),
    ("advice",   _TONE_CAUTIOUS, True):  (
        "Name the key challenge honestly, then reframe it as something manageable with "
        "specific effort, then point to the upcoming window as the right time to act."
    ),
    ("advice",   _TONE_CAUTIOUS, False): (
        "Name the key challenges honestly but constructively. Explain what kind of "
        "effort or remediation helps. Avoid generic platitudes."
    ),
    ("advice",   _TONE_BALANCED, True):  (
        "Describe the chart's mixed picture for this domain (strength + challenge), "
        "then advise on the best window to act, then one specific step."
    ),
    ("advice",   _TONE_BALANCED, False): (
        "Describe the chart's mixed picture, explain what supports and what limits "
        "this domain, then give balanced, actionable guidance."
    ),
    # qualities / describe
    ("qualities", _TONE_ENCOURAGING, True):  (
        "Describe the strongest positive indicators first, acknowledge any nuances, "
        "then note how the upcoming period activates these qualities."
    ),
    ("qualities", _TONE_ENCOURAGING, False): (
        "Describe the strongest positive indicators for this domain in concrete terms. "
        "Be specific — cite the planets and placements, not generalities."
    ),
    ("qualities", _TONE_CAUTIOUS, True):  (
        "Describe the chart factors honestly — both strengths and complications. "
        "Note how the upcoming period may help resolve or accentuate them."
    ),
    ("qualities", _TONE_CAUTIOUS, False): (
        "Describe the chart factors honestly, including complications. "
        "Be specific about what creates the challenge and what might ease it."
    ),
    ("qualities", _TONE_BALANCED, True):  (
        "Describe the domain indicators in a balanced way, then note how the "
        "upcoming period modulates them."
    ),
    ("qualities", _TONE_BALANCED, False): (
        "Describe the domain indicators in a balanced way — what the chart shows, "
        "not what the person wants to hear."
    ),
}

# Fallback anchor used when mode/tone combo not in table
_DEFAULT_ANCHOR = (
    "Identify the 2–3 factors that matter most for this specific question. "
    "Be concrete (cite planets, houses, dashas). Avoid generic statements. "
    "If timing is asked, commit to the most likely window from the plan above."
)


def _get_narrative_anchor(question_mode: str, tone: str, has_timing: bool) -> str:
    """Look up the narrative anchor template, falling back gracefully."""
    mode = question_mode if question_mode in ("timing", "advice", "qualities") else "advice"
    key = (mode, tone, has_timing)
    return _NARRATIVE_ANCHORS.get(key, _DEFAULT_ANCHOR)


# ──────────────────────────────────────────────────────────────────────────────
# AnswerPlan dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AnswerPlan:
    """
    Deterministic answer plan committed before the LLM runs.

    All fields are computed from structured data — no LLM call required.
    `plan_block` is the ready-to-inject prompt text.
    """
    domain: str = "general"
    question_mode: str = "summary"
    tone_stance: str = _TONE_BALANCED
    overall_strength: float = 5.0
    has_critical_failures: bool = False
    polarity: str = "neutral"

    # Primary factors: list of dicts with keys: text, category, why
    primary_factors: List[Dict[str, str]] = field(default_factory=list)

    # Best timing window: dict with start_month, end_month, label, confidence, reason
    committed_timing: Optional[Dict[str, Any]] = None

    # Divisional chart to emphasize
    divisional_info: Dict[str, str] = field(default_factory=dict)

    # Narrative anchor instruction
    narrative_anchor: str = ""

    @property
    def plan_block(self) -> str:
        """
        Produces the committed plan block for injection into the prompt's
        reasoning scratchpad section.  Returns empty string if we have
        nothing meaningful to commit (e.g. no synthesis data available).
        """
        if not self.primary_factors and self.committed_timing is None:
            return ""

        sep = "═" * 72
        lines = [
            "",
            sep,
            "COMMITTED ANSWER PLAN  (deterministic — reason within this plan; do NOT contradict it)",
            sep,
            f"  Domain        : {self.domain.upper()}",
            f"  Question mode : {self.question_mode.upper()}",
            f"  Tone stance   : {self.tone_stance.upper()}  "
            f"(overall_strength={self.overall_strength:.1f}/10"
            + ("; CRITICAL FAILURES present — be honest" if self.has_critical_failures else "")
            + ")",
            "",
        ]

        # Primary factors
        if self.primary_factors:
            lines.append("  Factors to address (in this order):")
            for i, f in enumerate(self.primary_factors, 1):
                cat = f.get("category", "factor").upper()
                text = f.get("text", "")
                why = f.get("why", "")
                lines.append(f"    {i}. [{cat}] {text}")
                if why:
                    lines.append(f"         → {why}")
            lines.append("")

        # Committed timing window
        if self.committed_timing:
            w = self.committed_timing
            conf_pct = int(w.get("confidence", 0.0) * 100)
            lines.append("  Committed timing window:")
            lines.append(
                f"    → {w.get('label', 'timing window')}: "
                f"{w.get('start_month', '?')} → {w.get('end_month', '?')}  "
                f"(confidence={conf_pct}%, {w.get('reason', '')})"
            )
            lines.append("")
        else:
            lines.append("  Timing window: none committed (chart lacks clear near-term PAD signal)")
            lines.append("")

        # Divisional chart
        if self.divisional_info:
            dc = self.divisional_info
            lines.append(
                f"  Divisional chart: {dc.get('chart')} ({dc.get('name')}) "
                f"— reveals {dc.get('reveals', '')}"
            )
            lines.append("")

        # Narrative anchor
        if self.narrative_anchor:
            lines.append("  Response structure (follow this arc):")
            lines.append(f"    {self.narrative_anchor}")
            lines.append("")

        lines.append(sep)
        lines.append("")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Public builder function
# ──────────────────────────────────────────────────────────────────────────────

def build_answer_plan(
    factor_plan: Any,                          # FactorPlan from factor_scorer
    astro_evidence: Optional[Dict[str, Any]],  # from build_astro_evidence()
    synthesis: Optional[Dict[str, Any]],       # from ChartSynthesisEngine
    validation_result: Optional[Dict[str, Any]],
    intent_analysis: Optional[Dict[str, Any]], # from semantic_frame.to_legacy_intent_analysis()
) -> AnswerPlan:
    """
    Build a deterministic AnswerPlan from structured data.

    All inputs are optional/nullable — the function degrades gracefully.
    Returns an AnswerPlan whose `.plan_block` is ready for prompt injection.
    """
    ia = intent_analysis or {}
    ev = astro_evidence or {}
    vr = validation_result or {}
    syn = synthesis or {}

    # ── Basic frame fields ────────────────────────────────────────────────────
    domain = (
        ia.get("domain")
        or ev.get("domain")
        or "general"
    ).lower()

    question_mode = (ia.get("question_mode") or "summary").lower()
    polarity = (ia.get("polarity") or "neutral").lower()

    # ── Validation signals ────────────────────────────────────────────────────
    overall_strength: float = float(vr.get("overall_strength") or 5.0)
    critical_failures: list = vr.get("critical_failures") or []
    has_critical = bool(critical_failures)

    # ── Tone ──────────────────────────────────────────────────────────────────
    tone = _compute_tone(overall_strength, polarity, question_mode, has_critical)

    # ── Primary factors from FactorPlan ───────────────────────────────────────
    primary_factors: List[Dict[str, str]] = []
    if factor_plan is not None and hasattr(factor_plan, "top_factors"):
        for sf in factor_plan.top_factors[:3]:
            primary_factors.append({
                "text":     sf.text,
                "category": sf.category,
                "why":      sf.why,
            })

    # ── Committed timing window ───────────────────────────────────────────────
    committed_timing: Optional[Dict[str, Any]] = None
    timeline_windows = ev.get("timeline_windows") or []
    if timeline_windows:
        # Already sorted by (-confidence, start) in build_timeline_windows.
        # Pick the highest-confidence window that has both start_month and end_month.
        for w in timeline_windows:
            if w.get("start_month") and w.get("end_month"):
                committed_timing = w
                break

    # ── Divisional chart ──────────────────────────────────────────────────────
    divisional_info = _DOMAIN_DIVISIONAL.get(domain, _DOMAIN_DIVISIONAL["general"])

    # ── Narrative anchor ──────────────────────────────────────────────────────
    has_timing = committed_timing is not None
    narrative_anchor = _get_narrative_anchor(question_mode, tone, has_timing)

    plan = AnswerPlan(
        domain=domain,
        question_mode=question_mode,
        tone_stance=tone,
        overall_strength=overall_strength,
        has_critical_failures=has_critical,
        polarity=polarity,
        primary_factors=primary_factors,
        committed_timing=committed_timing,
        divisional_info=divisional_info,
        narrative_anchor=narrative_anchor,
    )

    logger.info(
        "[ANSWER_PLAN] domain=%s mode=%s tone=%s factors=%d timing=%s",
        domain,
        question_mode,
        tone,
        len(primary_factors),
        committed_timing.get("label", "none") if committed_timing else "none",
    )

    return plan
