# src/prediction/accuracy_gate.py
"""
Factor Accuracy Gate for NakshatraAI (Improvement #9).

Problem solved:
  The LLM is instructed not to fabricate placements, but the prompt-level
  rule has no enforcement. A response claiming "Venus in the 10th house" for
  a chart where Venus is in the 5th passes all existing gates silently.

What this module does:
  After the LLM generates its answer, extract every (planet, house) and
  (planet, sign) claim made in plain text and cross-check them against the
  known chart_data. Mismatches are flagged as violations.

Design principles:
  - Pure deterministic logic — no LLM call, never blocks the pipeline.
  - Non-rewriting — violations are logged and stored on state; the gate
    does NOT attempt to rewrite the answer (unlike the timeline gate).
    Rewriting over factual errors risks making things worse and adds latency.
  - Graceful degradation — any parsing error returns an empty result.
  - English-only — Hindi/transliterated claims are not checked (too noisy).

What is NOT checked (intentional scope limit):
  - House-lord claims ("7th lord Venus") — derived from the chart, not a
    direct placement assertion. Would need a house-lord lookup to verify.
  - Aspect claims ("Venus aspects the 7th") — computed relationship, not
    a planet-in-house placement.
  - Dignity labels ("Venus exalted") — correct in isolation but complex
    to verify without full dignity tables.
  - Rahu/Ketu aliases ("North Node", "South Node", "Dragon's Head") — too
    many phrasings; skip to avoid false positives.

Usage:
    from src.prediction.accuracy_gate import check_factor_accuracy

    result = check_factor_accuracy(answer_text, state.get('chart_data'))
    if result.violations:
        logger.warning("[ACCURACY_GATE] %d violation(s): %s",
                       len(result.violations), result.violations)
    state['accuracy_gate'] = result.to_dict()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_PLANET_NAMES = [
    "SUN", "MOON", "MARS", "MERCURY", "JUPITER", "VENUS", "SATURN", "RAHU", "KETU",
]

_SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    # Sanskrit/Vedic names that appear in some outputs
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanus", "Makara", "Kumbha", "Meena",
]

# Canonical sign mapping: normalise Sanskrit→English
_SIGN_CANONICAL: Dict[str, str] = {
    "Mesha": "Aries", "Vrishabha": "Taurus", "Mithuna": "Gemini",
    "Karka": "Cancer", "Simha": "Leo", "Kanya": "Virgo",
    "Tula": "Libra", "Vrishchika": "Scorpio", "Dhanus": "Sagittarius",
    "Makara": "Capricorn", "Kumbha": "Aquarius", "Meena": "Pisces",
}

# Planet regex alternation (case-insensitive)
_PLANET_ALT = "|".join(_PLANET_NAMES)

# Sign regex alternation (case-insensitive)
_SIGN_ALT = "|".join(re.escape(s) for s in _SIGN_NAMES)

# Pattern: "{Planet} in [the|your|my]? {N}[st|nd|rd|th] house"
# Also matches "in house {N}"
_PLANET_HOUSE_RE = re.compile(
    rf"(?P<planet>{_PLANET_ALT})"            # planet name
    r"[\w\s,''\']*?"                          # optional filler (non-greedy)
    r"(?:in|placed in|posited in|sitting in)" # placement verb
    r"[\w\s]*?"                               # optional filler
    r"(?:the|your|my|his|her|its)?\s*"        # optional possessive
    r"(?P<house>\d{{1,2}})"                   # house number
    r"(?:st|nd|rd|th)?\s*house",              # ordinal suffix + "house"
    re.IGNORECASE,
)

# Pattern: "{Planet} in house {N}"
_PLANET_IN_HOUSE_NUM_RE = re.compile(
    rf"(?P<planet>{_PLANET_ALT})"
    r"[\w\s,''\']*?"
    r"(?:in|placed in|posited in)\s+house\s+"
    r"(?P<house>\d{{1,2}})",
    re.IGNORECASE,
)

# Pattern: "{Planet} in [the]? {Sign}"
# We require sign to be a capitalised word (not mid-sentence lowercase noise).
_PLANET_SIGN_RE = re.compile(
    rf"(?P<planet>{_PLANET_ALT})"
    r"[\w\s,''\']*?"
    r"(?:in|placed in|posited in)"
    r"(?:\s+(?:the|sign\s+of))?\s+"
    r"(?P<sign>" + _SIGN_ALT + r")\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FactorAccuracyResult:
    """Structured result from the factor accuracy gate."""
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    checked_claims: int = 0
    skipped_claims: int = 0   # claims where chart_data had no matching planet

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# Extraction helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_planet_house_claims(text: str) -> List[Tuple[str, int]]:
    """Return list of (planet_upper, house_number) pairs from the answer text."""
    claims: List[Tuple[str, int]] = []
    seen: set = set()

    for pattern in (_PLANET_HOUSE_RE, _PLANET_IN_HOUSE_NUM_RE):
        for m in pattern.finditer(text):
            planet = m.group("planet").upper()
            try:
                house = int(m.group("house"))
            except (ValueError, IndexError):
                continue
            if not 1 <= house <= 12:
                continue
            key = (planet, house)
            if key not in seen:
                seen.add(key)
                claims.append(key)

    return claims


def _extract_planet_sign_claims(text: str) -> List[Tuple[str, str]]:
    """Return list of (planet_upper, sign_canonical) pairs from the answer text."""
    claims: List[Tuple[str, str]] = []
    seen: set = set()

    for m in _PLANET_SIGN_RE.finditer(text):
        planet = m.group("planet").upper()
        sign_raw = m.group("sign").capitalize()
        sign = _SIGN_CANONICAL.get(sign_raw, sign_raw)
        key = (planet, sign)
        if key not in seen:
            seen.add(key)
            claims.append(key)

    return claims


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def check_factor_accuracy(
    answer: str,
    chart_data: Optional[Dict[str, Any]],
) -> FactorAccuracyResult:
    """
    Verify that planet-house and planet-sign claims in `answer` match `chart_data`.

    Returns a FactorAccuracyResult. Never raises — all errors are swallowed and
    logged so the gate never blocks the response pipeline.

    Args:
        answer:     The LLM-generated answer text.
        chart_data: The canonical chart dict from state['chart_data'].
                    Expected shape: {'planets': {'VENUS': {'house': 5, 'sign': 'Taurus', ...}, ...}}
    """
    result = FactorAccuracyResult()

    if not answer or not chart_data:
        return result

    try:
        planets_data: Dict[str, Any] = chart_data.get("planets") or {}

        # ── planet-house checks ──────────────────────────────────────────────
        house_claims = _extract_planet_house_claims(answer)
        for planet, claimed_house in house_claims:
            result.checked_claims += 1
            planet_info = planets_data.get(planet)
            if not planet_info:
                result.skipped_claims += 1
                continue

            try:
                actual_house = int(planet_info.get("house") or 0)
            except (TypeError, ValueError):
                result.skipped_claims += 1
                continue

            if actual_house < 1:
                result.skipped_claims += 1
                continue

            if actual_house != claimed_house:
                msg = (
                    f"{planet} claimed in H{claimed_house} "
                    f"but chart shows H{actual_house}"
                )
                result.violations.append(msg)
                result.passed = False

        # ── planet-sign checks ───────────────────────────────────────────────
        sign_claims = _extract_planet_sign_claims(answer)
        for planet, claimed_sign in sign_claims:
            result.checked_claims += 1
            planet_info = planets_data.get(planet)
            if not planet_info:
                result.skipped_claims += 1
                continue

            actual_sign = (planet_info.get("sign") or "").strip()
            if not actual_sign:
                result.skipped_claims += 1
                continue

            # Normalise both sides for comparison
            if actual_sign.lower() != claimed_sign.lower():
                msg = (
                    f"{planet} claimed in {claimed_sign} "
                    f"but chart shows {actual_sign}"
                )
                result.violations.append(msg)
                result.passed = False

    except Exception as exc:
        logger.debug("[ACCURACY_GATE] Error during check (skipped): %s", exc)

    if result.violations:
        logger.warning(
            "[ACCURACY_GATE] %d violation(s) in answer "
            "(checked=%d, skipped=%d): %s",
            len(result.violations),
            result.checked_claims,
            result.skipped_claims,
            " | ".join(result.violations),
        )
    else:
        logger.debug(
            "[ACCURACY_GATE] passed (checked=%d, skipped=%d)",
            result.checked_claims,
            result.skipped_claims,
        )

    return result
