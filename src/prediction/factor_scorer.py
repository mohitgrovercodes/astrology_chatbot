# src/prediction/factor_scorer.py
"""
Validation-Aware Factor Scorer for NakshatraAI.

Problem solved:
  ChartSynthesisEngine produces up to 8 strengths, 8 challenges, 5 yogas, and
  4 key-house summaries. _format_enhanced_analysis() dumps all of them into the
  prompt in no particular relevance order, leaving the LLM to guess what matters
  for THIS query. The result is generic "here is everything" answers instead of
  laser-focused "here is the 2-3 things that actually drive your question" answers.

What this module does:
  Scores every candidate factor using three orthogonal signals:

    1. Domain–planet affinity   — how closely does this planet/house relate to the
                                   life area the user is asking about (marriage,
                                   career, finance, etc.)?

    2. Dasha activation         — is the planet currently the MD/AD/PAD lord?
                                   Active dasha lords dominate timing and intensity.

    3. Validation signal        — does the validation engine flag this planet/house
                                   as a critical failure? If overall_strength < 5 the
                                   challenges are more diagnostic; if ≥ 7 the strengths
                                   are more actionable. Question mode (timing/advice/
                                   qualities/summary) tilts the weights.

  The top 2–3 factors (by combined score) are returned as a structured
  `FactorPlan` that gets injected as a "FOCUS FACTORS" preamble in
  _format_enhanced_analysis(), before the full detailed dump.

  This keeps the LLM's attention on the right things without removing the
  detailed section (which serves the CoT scratchpad and quality gates).

Usage:
    from src.prediction.factor_scorer import score_factors, FactorPlan

    plan = score_factors(
        synthesis=state['synthesis'],
        validation_result=state.get('validation_result'),
        dasha_data=state.get('dasha_data'),
        domain="marriage",
        question_mode="timing",      # from semantic_frame
    )
    # plan.focus_block → inject at top of enhanced analysis section
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Domain × planet affinity table
# Higher = more diagnostically relevant for this domain.
# ──────────────────────────────────────────────────────────────────────────────
_DOMAIN_PLANET_AFFINITY: Dict[str, Dict[str, float]] = {
    "marriage": {
        "VENUS": 1.0, "JUPITER": 0.85, "MOON": 0.70,
        "MARS": 0.55, "RAHU": 0.45, "SATURN": 0.40,
        "SUN": 0.35, "MERCURY": 0.30, "KETU": 0.25,
    },
    "divorce": {
        "VENUS": 1.0, "MARS": 0.85, "SATURN": 0.80,
        "RAHU": 0.70, "KETU": 0.55, "MOON": 0.50,
        "SUN": 0.35, "JUPITER": 0.30, "MERCURY": 0.20,
    },
    "career": {
        "SATURN": 1.0, "SUN": 0.90, "MERCURY": 0.75,
        "MARS": 0.65, "JUPITER": 0.60, "RAHU": 0.50,
        "VENUS": 0.40, "MOON": 0.35, "KETU": 0.25,
    },
    "finance": {
        "JUPITER": 1.0, "VENUS": 0.85, "MERCURY": 0.80,
        "SATURN": 0.65, "SUN": 0.55, "MARS": 0.50,
        "MOON": 0.45, "RAHU": 0.40, "KETU": 0.20,
    },
    "health": {
        "SUN": 0.85, "MOON": 0.80, "MARS": 0.75,
        "SATURN": 0.70, "KETU": 0.55, "RAHU": 0.50,
        "JUPITER": 0.40, "VENUS": 0.35, "MERCURY": 0.30,
    },
    "children": {
        "JUPITER": 1.0, "MOON": 0.85, "VENUS": 0.70,
        "SUN": 0.55, "MARS": 0.45, "SATURN": 0.40,
        "MERCURY": 0.30, "RAHU": 0.30, "KETU": 0.25,
    },
    "foreign": {
        "RAHU": 0.90, "JUPITER": 0.80, "SATURN": 0.70,
        "KETU": 0.60, "MOON": 0.50, "MARS": 0.45,
        "VENUS": 0.40, "SUN": 0.35, "MERCURY": 0.30,
    },
    "education": {
        "MERCURY": 1.0, "JUPITER": 0.90, "MOON": 0.65,
        "SUN": 0.60, "VENUS": 0.45, "SATURN": 0.40,
        "MARS": 0.35, "RAHU": 0.30, "KETU": 0.25,
    },
    "home": {
        "MOON": 0.90, "MARS": 0.80, "SATURN": 0.70,
        "VENUS": 0.60, "JUPITER": 0.55, "SUN": 0.40,
        "MERCURY": 0.35, "RAHU": 0.30, "KETU": 0.25,
    },
    "spirituality": {
        "KETU": 1.0, "JUPITER": 0.90, "SATURN": 0.70,
        "MOON": 0.65, "SUN": 0.60, "RAHU": 0.45,
        "VENUS": 0.40, "MARS": 0.30, "MERCURY": 0.25,
    },
    "general": {
        "JUPITER": 0.70, "SATURN": 0.70, "MOON": 0.65,
        "SUN": 0.60, "VENUS": 0.60, "MARS": 0.55,
        "MERCURY": 0.55, "RAHU": 0.50, "KETU": 0.40,
    },
}

# Key houses per domain (1-indexed). Used to boost house-level factors.
_DOMAIN_KEY_HOUSES: Dict[str, List[int]] = {
    "marriage":    [7, 2, 5, 8, 1],
    "divorce":     [7, 6, 8, 12, 3],
    "career":      [10, 6, 2, 11, 1],
    "finance":     [2, 11, 5, 9, 1],
    "health":      [1, 6, 8, 12],
    "children":    [5, 9, 1],
    "foreign":     [12, 9, 3, 7],
    "education":   [4, 5, 2, 9, 1],
    "home":        [4, 1, 2, 12],
    "spirituality":[9, 5, 12, 1],
    "general":     [1, 7, 10, 4],
}

# Planet extraction regex — covers "VENUS", "Venus", "jupiter", also "7th lord" handled separately
_PLANET_RE = re.compile(
    r"\b(SUN|MOON|MARS|MERCURY|JUPITER|VENUS|SATURN|RAHU|KETU)\b",
    re.IGNORECASE,
)

# House extraction regex — "7th house", "H7", "house 7"
_HOUSE_RE = re.compile(
    r"\b(?:H(\d{1,2})|(\d{1,2})(?:st|nd|rd|th)\s+house|house\s+(\d{1,2}))\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ScoredFactor:
    """A single astrological factor with its relevance score and why-label."""
    text: str                        # The factor string as it came from synthesis
    category: str                    # "strength" | "challenge" | "yoga" | "house"
    planets: List[str]               # Planets mentioned/detected in this factor
    houses: List[int]                # House numbers mentioned
    domain_score: float = 0.0       # Affinity for this domain
    dasha_score: float = 0.0        # Boost from active dasha involvement
    validation_score: float = 0.0   # Boost from validation engine flags
    base_score: float = 0.0         # Planet strength from synthesis.planetary_strengths
    combined_score: float = 0.0     # Final ranking score
    why: str = ""                    # Short human-readable reason for selection

    @property
    def is_actionable(self) -> bool:
        return self.combined_score >= 4.0


@dataclass
class FactorPlan:
    """Top-ranked factors for this specific query, ready for prompt injection."""
    top_factors: List[ScoredFactor] = field(default_factory=list)
    domain: str = "general"
    question_mode: str = "summary"
    focus_summary: str = ""

    @property
    def focus_block(self) -> str:
        """
        Returns a compact prompt block to inject at the top of the enhanced
        analysis section. Empty string if no factors were scored.
        """
        if not self.top_factors:
            return ""

        lines = [
            f"▶ FOCUS FACTORS for this query  [{self.domain.upper()} / {self.question_mode.upper()}]",
            "  (Ranked by domain relevance × dasha activation × validation signal)",
            "",
        ]
        for i, f in enumerate(self.top_factors, 1):
            cat_tag = f.category.upper()
            lines.append(f"  {i}. [{cat_tag}] {f.text}")
            if f.why:
                lines.append(f"     → {f.why}")
        lines.append("")
        if self.focus_summary:
            lines.append(f"  SYNTHESIS HINT: {self.focus_summary}")
            lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_planets(text: str) -> List[str]:
    """Extract all planet names (normalised to uppercase) from a string."""
    return list({m.upper() for m in _PLANET_RE.findall(text)})


def _extract_houses(text: str) -> List[int]:
    """Extract house numbers from strings like '7th house', 'H7', 'house 7'."""
    results = set()
    for m in _HOUSE_RE.finditer(text):
        for g in m.groups():
            if g:
                try:
                    results.add(int(g))
                except ValueError:
                    pass
    return list(results)


def _active_dasha_planets(dasha_data: Optional[Dict]) -> Dict[str, float]:
    """
    Return {planet_name: activation_weight} for currently active dasha lords.
    MD > AD > PAD in weight.
    """
    if not dasha_data:
        return {}
    result: Dict[str, float] = {}

    def _add(key: str, weight: float) -> None:
        raw = dasha_data.get(key)
        planet = None
        if isinstance(raw, dict):
            planet = raw.get("planet") or raw.get("lord")
        elif isinstance(raw, str):
            planet = raw
        if planet:
            p = planet.upper().strip()
            # Take the highest weight if the same planet appears in multiple tiers
            result[p] = max(result.get(p, 0.0), weight)

    _add("mahadasha",        1.5)
    _add("antardasha",       1.3)
    _add("pratyantardasha",  1.15)
    return result


def _validation_flagged_planets(validation_result: Optional[Dict]) -> Dict[str, float]:
    """
    Return {planet_name: urgency_weight} for planets mentioned in critical failures.
    These factors NEED to be surfaced — the LLM must address them.
    """
    if not validation_result:
        return {}
    flagged: Dict[str, float] = {}
    for failure in validation_result.get("critical_failures", []):
        text = f"{failure.get('rule_name', '')} {failure.get('reason', '')}"
        for planet in _extract_planets(text):
            flagged[planet] = max(flagged.get(planet, 0.0), 1.2)
    return flagged


def _domain_planet_affinity(planet: str, domain: str) -> float:
    table = _DOMAIN_PLANET_AFFINITY.get(domain) or _DOMAIN_PLANET_AFFINITY["general"]
    return table.get(planet.upper(), 0.3)


def _domain_house_affinity(house: int, domain: str) -> float:
    key_houses = _DOMAIN_KEY_HOUSES.get(domain) or _DOMAIN_KEY_HOUSES["general"]
    try:
        idx = key_houses.index(house)
        # Decay by position: 1st key house → 1.0, 2nd → 0.8, etc.
        return max(0.2, 1.0 - idx * 0.2)
    except ValueError:
        return 0.1


def _build_why(
    factor: ScoredFactor,
    active_planets: Dict[str, float],
    flagged_planets: Dict[str, float],
    domain: str,
    question_mode: str,
) -> str:
    """Compose a short 'why this matters now' label for a factor."""
    reasons: List[str] = []

    for planet in factor.planets:
        p = planet.upper()
        if p in active_planets:
            tier = "MD lord" if active_planets[p] >= 1.5 else ("AD lord" if active_planets[p] >= 1.3 else "PAD lord")
            reasons.append(f"{p} is current {tier}")
        if p in flagged_planets:
            reasons.append(f"{p} flagged by validation")

    if factor.category == "yoga":
        reasons.append("yoga active for this domain")
    elif factor.category == "challenge" and question_mode in ("timing", "advice"):
        reasons.append("obstacle to address")
    elif factor.category == "strength" and question_mode in ("timing", "qualities"):
        reasons.append("supporting force")

    for h in factor.houses:
        if _domain_house_affinity(h, domain) >= 0.8:
            reasons.append(f"H{h} is primary house for {domain}")

    return "; ".join(reasons[:3]) if reasons else f"relevant to {domain}"


# ──────────────────────────────────────────────────────────────────────────────
# Score individual factors
# ──────────────────────────────────────────────────────────────────────────────

def _score_factor(
    text: str,
    category: str,
    domain: str,
    question_mode: str,
    active_planets: Dict[str, float],
    flagged_planets: Dict[str, float],
    planetary_strengths: Dict[str, float],
    overall_strength: float,
) -> ScoredFactor:
    """Compute a combined relevance score for one factor string."""
    planets = _extract_planets(text)
    houses = _extract_houses(text)

    # ── 1. Domain affinity ───────────────────────────────────────────────
    planet_affinity = max(
        (_domain_planet_affinity(p, domain) for p in planets),
        default=0.3,
    )
    house_affinity = max(
        (_domain_house_affinity(h, domain) for h in houses),
        default=0.1,
    )
    domain_score = max(planet_affinity, house_affinity)

    # ── 2. Dasha activation ──────────────────────────────────────────────
    dasha_score = max(
        (active_planets.get(p, 1.0) for p in planets),
        default=1.0,
    )
    # Planets not in active dasha get weight 1.0 (neutral, not penalised)
    # Active dasha lords get 1.15–1.5 (boost only)

    # ── 3. Validation signal ─────────────────────────────────────────────
    validation_score = max(
        (flagged_planets.get(p, 1.0) for p in planets),
        default=1.0,
    )

    # ── 4. Intrinsic planet strength from synthesis ──────────────────────
    strength_vals = [planetary_strengths.get(p, 5.0) for p in planets]
    avg_strength = sum(strength_vals) / len(strength_vals) if strength_vals else 5.0
    base_score = avg_strength / 10.0  # normalise to 0–1

    # ── 5. Question-mode tilt ────────────────────────────────────────────
    qmode_tilt = 1.0
    if question_mode == "timing":
        # Timing queries: dasha-activated factors matter most
        if dasha_score > 1.0:
            qmode_tilt = 1.3
        if category == "challenge":
            qmode_tilt *= 1.1  # challenges create delays — mention them
    elif question_mode == "advice":
        # Advice queries: actionable challenges + strong yogas matter
        if category == "challenge":
            qmode_tilt = 1.2
        elif category == "yoga":
            qmode_tilt = 1.15
    elif question_mode == "qualities":
        # Qualities queries: dignities and yogas matter most
        if category in ("yoga", "strength"):
            qmode_tilt = 1.2
    # summary: balanced — no tilt

    # ── 6. Chart strength context ────────────────────────────────────────
    # Weak chart (overall_strength < 5): challenges are more diagnostic
    # Strong chart (overall_strength >= 7): strengths are more actionable
    strength_context_tilt = 1.0
    if overall_strength < 5.0 and category == "challenge":
        strength_context_tilt = 1.15
    elif overall_strength >= 7.0 and category == "strength":
        strength_context_tilt = 1.15

    # ── 7. Combined score ────────────────────────────────────────────────
    # Weights: domain (40%) × dasha (30%) × validation (15%) × base (15%)
    combined = (
        domain_score * 10.0 * 0.40
        + dasha_score * 10.0 * 0.30
        + validation_score * 10.0 * 0.15
        + base_score * 10.0 * 0.15
    ) * qmode_tilt * strength_context_tilt

    factor = ScoredFactor(
        text=text,
        category=category,
        planets=planets,
        houses=houses,
        domain_score=round(domain_score * 10.0, 2),
        dasha_score=round(dasha_score * 10.0, 2),
        validation_score=round(validation_score * 10.0, 2),
        base_score=round(base_score * 10.0, 2),
        combined_score=round(combined, 2),
    )
    factor.why = _build_why(factor, active_planets, flagged_planets, domain, question_mode)
    return factor


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def score_factors(
    synthesis: Optional[Dict[str, Any]],
    validation_result: Optional[Dict[str, Any]] = None,
    dasha_data: Optional[Dict[str, Any]] = None,
    domain: str = "general",
    question_mode: str = "summary",
    top_n: int = 3,
) -> FactorPlan:
    """
    Score all synthesis factors and return the top `top_n` most relevant ones.

    Args:
        synthesis:         Output of ChartSynthesisEngine.synthesize().
        validation_result: VedicValidationEngine result dict.
        dasha_data:        Current dasha dict from DashaTool.
        domain:            Semantic domain (marriage/career/...) from SemanticFrame.
        question_mode:     Query mode (timing/advice/qualities/summary) from SemanticFrame.
        top_n:             How many factors to surface (default 3).

    Returns:
        FactorPlan with ranked top factors and focus_block ready for prompt injection.
    """
    if not synthesis:
        logger.debug("[FACTOR_SCORER] No synthesis data — returning empty plan")
        return FactorPlan(domain=domain, question_mode=question_mode)

    # Normalise domain
    domain = (domain or "general").lower()
    if domain not in _DOMAIN_PLANET_AFFINITY:
        domain = "general"

    # Pre-compute context
    active_planets = _active_dasha_planets(dasha_data)
    flagged_planets = _validation_flagged_planets(validation_result)
    overall_strength = float((validation_result or {}).get("overall_strength", 5.0))
    planetary_strengths: Dict[str, float] = synthesis.get("planetary_strengths") or {}

    logger.debug(
        f"[FACTOR_SCORER] domain={domain} qmode={question_mode} "
        f"active_planets={list(active_planets)} flagged={list(flagged_planets)} "
        f"overall_strength={overall_strength:.1f}"
    )

    # Collect all candidate factors
    candidates: List[ScoredFactor] = []

    def _add(text: str, category: str) -> None:
        if not text or not text.strip():
            return
        sf = _score_factor(
            text=text.strip(),
            category=category,
            domain=domain,
            question_mode=question_mode,
            active_planets=active_planets,
            flagged_planets=flagged_planets,
            planetary_strengths=planetary_strengths,
            overall_strength=overall_strength,
        )
        candidates.append(sf)

    # Chart strengths
    for s in (synthesis.get("chart_strengths") or []):
        _add(str(s), "strength")

    # Chart challenges
    for c in (synthesis.get("chart_challenges") or []):
        _add(str(c), "challenge")

    # Yogas (name + description as combined text)
    for y in (synthesis.get("yogas_detected") or []):
        if isinstance(y, dict):
            yoga_text = f"{y.get('name', '')} — {y.get('description', '')}".strip(" —")
        else:
            yoga_text = str(y)
        _add(yoga_text, "yoga")

    # Key house summaries (lord + placement)
    for ha in (synthesis.get("key_houses") or []):
        if not isinstance(ha, dict):
            continue
        lord = ha.get("lord", "")
        house_num = ha.get("house", "")
        assessment = ha.get("assessment", "")
        strength = ha.get("lord_strength", 5.0)
        placement = ha.get("lord_placement", {}) or {}
        place_house = placement.get("house", "")
        place_dignity = placement.get("dignity", "")
        house_text = (
            f"H{house_num} lord {lord} ({assessment}, {strength:.1f}/10) "
            f"placed in H{place_house} {place_dignity}".strip()
        )
        _add(house_text, "house")

    if not candidates:
        logger.debug("[FACTOR_SCORER] No candidates extracted from synthesis")
        return FactorPlan(domain=domain, question_mode=question_mode)

    # Sort by combined_score descending
    candidates.sort(key=lambda f: f.combined_score, reverse=True)

    # Take top_n, but ensure at least one challenge is included when overall_strength < 5
    # and at least one strength when overall_strength >= 7 (balance the picture)
    top = candidates[:top_n]
    categories_present = {f.category for f in top}

    if overall_strength < 5.0 and "challenge" not in categories_present:
        # Find the highest-scoring challenge not already in top
        best_challenge = next(
            (f for f in candidates if f.category == "challenge" and f not in top), None
        )
        if best_challenge:
            top[-1] = best_challenge  # replace lowest scorer

    if overall_strength >= 7.0 and "strength" not in categories_present and "yoga" not in categories_present:
        best_strength = next(
            (f for f in candidates if f.category in ("strength", "yoga") and f not in top), None
        )
        if best_strength:
            top[-1] = best_strength

    # Build focus summary
    planet_names = []
    for f in top:
        planet_names.extend(f.planets)
    seen: set = set()
    deduped_planets = [p for p in planet_names if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]

    if deduped_planets:
        summary_parts = [f"Key planets for {domain}: {', '.join(deduped_planets[:4])}"]
        if active_planets:
            active_in_top = [p for p in deduped_planets if p in active_planets]
            if active_in_top:
                tiers = []
                for p in active_in_top:
                    w = active_planets[p]
                    tier = "MD" if w >= 1.5 else ("AD" if w >= 1.3 else "PAD")
                    tiers.append(f"{p} ({tier})")
                summary_parts.append(f"Dasha-activated: {', '.join(tiers)}")
        focus_summary = ". ".join(summary_parts) + "."
    else:
        focus_summary = f"Focus on the most relevant factors for {domain}."

    plan = FactorPlan(
        top_factors=top,
        domain=domain,
        question_mode=question_mode,
        focus_summary=focus_summary,
    )

    logger.info(
        f"[FACTOR_SCORER] Top {len(top)} factors for {domain}/{question_mode}: "
        + " | ".join(f"{f.category}({f.combined_score:.1f})" for f in top)
    )
    return plan
