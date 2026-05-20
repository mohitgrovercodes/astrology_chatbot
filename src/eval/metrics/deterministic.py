# src/eval/metrics/deterministic.py
"""
Deterministic eval metrics — pure rule-based checks, no LLM.

Each check is a callable that returns a CheckResult with:
  - name:   stable identifier (logged in scorecard)
  - passed: bool
  - score:  0.0-1.0 (granular pass strength; usually 0 or 1 for hard checks)
  - detail: short human-readable explanation
  - data:   structured evidence for diff/debug

Checks read from a turn-level CheckContext that bundles the user message,
assistant response, scenario expectations, and per-turn telemetry from the
API's metadata["eval"] block.

Adding a new check:
  1. Write `def check_xxx(ctx) -> CheckResult`
  2. Add to DETERMINISTIC_CHECKS tuple at the bottom
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Data shapes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CheckContext:
    """Per-turn input bundle for deterministic checks."""

    # Scenario expectations
    scenario_id: str
    scenario_tags: List[str]
    expected_domain: Optional[str] = None
    expected_language: Optional[str] = None
    expected_phase: Optional[str] = None  # "INITIAL" | "AWAITING_DETAIL" | "FOLLOWUP_LOOP"

    # The turn under test
    user_message: str = ""
    assistant_response: str = ""

    # Telemetry from the API (metadata["eval"] block)
    semantic_frame: Dict[str, Any] = field(default_factory=dict)
    accuracy_gate: Dict[str, Any] = field(default_factory=dict)
    accuracy_gate_fired: bool = False
    focus_factors: List[Dict[str, Any]] = field(default_factory=list)
    conversation_phase: Dict[str, Any] = field(default_factory=dict)
    response_timing_windows: List[str] = field(default_factory=list)
    response_topic: Optional[str] = None
    validation_diagnostics: Dict[str, Any] = field(default_factory=dict)
    processing_time_s: float = 0.0

    # Chart data — used by timing accuracy check (looked up via SessionManager)
    dasha_data: Dict[str, Any] = field(default_factory=dict)

    # Cross-turn context
    turn_index: int = 0
    prior_phase: Optional[str] = None  # phase before this turn began


# ──────────────────────────────────────────────────────────────────────────────
# Domain inference from tags (scenario tags → expected domain)
# ──────────────────────────────────────────────────────────────────────────────

_DOMAIN_TAGS = {
    "marriage", "career", "finance", "health", "children",
    "foreign", "education", "home", "spirituality", "divorce",
}

_LANG_TAGS = {
    "english", "hindi", "hinglish", "tamil", "telugu",
    "malayalam", "marathi", "punjabi",
}

# Tag → language code map (must match LanguageDetector codes)
_TAG_TO_LANG = {
    "english": "en",
    "hindi": "hi",
    "hinglish": "hi-lat",
    "tamil": "ta",
    "telugu": "te",
    "malayalam": "ml",
    "marathi": "mr",
    "punjabi": "pa",
}


def infer_expected_domain(tags: List[str]) -> Optional[str]:
    """Pick the first domain tag (scenarios may also have non-domain tags)."""
    for t in tags:
        if t in _DOMAIN_TAGS:
            return t
    return None


def infer_expected_language(tags: List[str]) -> Optional[str]:
    """Map a language tag to a language code."""
    for t in tags:
        if t in _TAG_TO_LANG:
            return _TAG_TO_LANG[t]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

# Match "April 2026", "Apr 2026", "April-August 2026", "2026-04 to 2026-08", etc.
_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
)
_MONTH_YEAR_RE = re.compile(
    rf"\b(?:{_MONTH_NAMES})\s+(?:\d{{1,2}}\s*[-,]\s*)?\d{{4}}\b"
    rf"|\b\d{{4}}-\d{{2}}(?:-\d{{2}})?\b",
    re.IGNORECASE,
)

# Crude language fingerprints — used as a sanity check on top of langdetect when
# the API metadata didn't surface a language. Native-script presence is reliable.
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_TAMIL_RE = re.compile(r"[஀-௿]")
_TELUGU_RE = re.compile(r"[ఀ-౿]")
_MALAYALAM_RE = re.compile(r"[ഀ-ൿ]")
_GURMUKHI_RE = re.compile(r"[਀-੿]")
_HINGLISH_TOKENS = (" hai ", " hain ", " kya ", " mein ", " ki ", " ka ", " ke ",
                    " ho ", " toh ", " agar ", " aap ", " mera ", " meri ", " mere ")


def _detect_response_language(text: str, expected: Optional[str]) -> str:
    """
    Cheap language fingerprint for the response. Returns one of:
      en | hi | hi-lat | ta | te | ml | mr | pa | unknown
    """
    if not text:
        return "unknown"
    if _DEVANAGARI_RE.search(text):
        # Could be hi or mr. Use expected if it's mr; otherwise hi.
        return "mr" if expected == "mr" else "hi"
    if _TAMIL_RE.search(text):
        return "ta"
    if _TELUGU_RE.search(text):
        return "te"
    if _MALAYALAM_RE.search(text):
        return "ml"
    if _GURMUKHI_RE.search(text):
        return "pa"
    # No native script — could be English or romanized Indian language
    lower = " " + text.lower() + " "
    if any(tok in lower for tok in _HINGLISH_TOKENS):
        return "hi-lat"
    return "en"


def _expected_word_range(phase: Optional[str]) -> Tuple[int, int]:
    """Length window for each phase, sourced from orchestrator policy."""
    if phase == "INITIAL" or phase is None:
        return 80, 200    # initial short answer, with a small buffer
    if phase == "AWAITING_DETAIL":
        return 80, 250    # next short cycle from a pivot
    if phase == "FOLLOWUP_LOOP":
        return 200, 560   # detailed analysis
    return 80, 600


def _extract_month_year_strings(text: str) -> List[str]:
    return [m.group(0) for m in _MONTH_YEAR_RE.finditer(text or "")]


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────

def check_response_nonempty(ctx: CheckContext) -> CheckResult:
    text = (ctx.assistant_response or "").strip()
    ok = len(text) > 20
    return CheckResult(
        name="response_nonempty",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"response length = {len(text)} chars",
    )


def check_length_in_range(ctx: CheckContext) -> CheckResult:
    text = (ctx.assistant_response or "").strip()
    words = len(text.split())
    lo, hi = _expected_word_range(ctx.expected_phase)
    ok = lo <= words <= hi
    return CheckResult(
        name="length_in_range",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"{words} words (expected {lo}-{hi} for phase={ctx.expected_phase or 'INITIAL'})",
        data={"word_count": words, "range": [lo, hi]},
    )


def check_language_match(ctx: CheckContext) -> CheckResult:
    if not ctx.expected_language:
        return CheckResult(name="language_match", passed=True, score=1.0,
                           detail="no language tag on scenario; skipped")
    detected = _detect_response_language(ctx.assistant_response, ctx.expected_language)
    ok = detected == ctx.expected_language
    return CheckResult(
        name="language_match",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"expected={ctx.expected_language}, detected={detected}",
        data={"expected": ctx.expected_language, "detected": detected},
    )


def check_has_month_year(ctx: CheckContext) -> CheckResult:
    """Predictions should cite at least one explicit month-year window."""
    # Skip for chitchat-tagged scenarios
    if "chitchat" in ctx.scenario_tags:
        return CheckResult(name="has_month_year", passed=True, score=1.0,
                           detail="chitchat scenario; skipped")
    hits = _extract_month_year_strings(ctx.assistant_response)
    ok = bool(hits)
    return CheckResult(
        name="has_month_year",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"{len(hits)} explicit month-year mentions" if ok
               else "no explicit month-year window found",
        data={"matches": hits[:5]},
    )


def check_no_past_dates(ctx: CheckContext) -> CheckResult:
    """No timing window may reference a year strictly before the current year."""
    if "chitchat" in ctx.scenario_tags:
        return CheckResult(name="no_past_dates", passed=True, score=1.0,
                           detail="chitchat scenario; skipped")
    # Extract years from month-year strings
    today_year = datetime.utcnow().year
    text = ctx.assistant_response or ""
    years = set()
    for m in re.finditer(r"\b(20\d{2})\b", text):
        years.add(int(m.group(1)))
    past = sorted(y for y in years if y < today_year)
    ok = len(past) == 0
    return CheckResult(
        name="no_past_dates",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail="no past years cited" if ok
               else f"past years cited: {past}",
        data={"all_years": sorted(years), "past_years": past},
    )


def check_domain_match(ctx: CheckContext) -> CheckResult:
    """The semantic frame's domain should match the scenario's expected domain."""
    if not ctx.expected_domain:
        return CheckResult(name="domain_match", passed=True, score=1.0,
                           detail="no domain tag on scenario; skipped")
    actual = (ctx.semantic_frame or {}).get("domain") or "general"
    ok = actual == ctx.expected_domain
    return CheckResult(
        name="domain_match",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"expected={ctx.expected_domain}, actual={actual}",
        data={"expected": ctx.expected_domain, "actual": actual},
    )


def check_accuracy_gate_clean(ctx: CheckContext) -> CheckResult:
    """The factor-accuracy gate should not have flagged mismatched claims."""
    fired = bool(ctx.accuracy_gate_fired)
    # Count mismatches if surfaced
    n_mismatches = 0
    if isinstance(ctx.accuracy_gate, dict):
        for key in ("mismatched_claims", "mismatches", "errors"):
            v = ctx.accuracy_gate.get(key)
            if isinstance(v, list):
                n_mismatches = max(n_mismatches, len(v))
    ok = not fired and n_mismatches == 0
    return CheckResult(
        name="accuracy_gate_clean",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail="no factor mismatches" if ok
               else f"{n_mismatches} mismatched claim(s) flagged",
        data={"fired": fired, "n_mismatches": n_mismatches},
    )


def check_phase_transitioned_correctly(ctx: CheckContext) -> CheckResult:
    """
    For multi-turn scenarios, the phase should advance as expected:
      INITIAL  →  AWAITING_DETAIL  (after first prediction turn)
      AWAITING_DETAIL + 'yes/haan'  →  FOLLOWUP_LOOP
      FOLLOWUP_LOOP + 'yes'  →  AWAITING_DETAIL (new topic cycle)
    Single-turn scenarios are auto-passed.
    """
    if ctx.turn_index == 0:
        return CheckResult(name="phase_transition", passed=True, score=1.0,
                           detail="first turn; no transition to check")
    if not ctx.conversation_phase:
        return CheckResult(name="phase_transition", passed=False, score=0.0,
                           detail="conversation_phase missing from telemetry",
                           data={"prior": ctx.prior_phase})
    current = ctx.conversation_phase.get("phase")
    valid_transitions = {
        "INITIAL": {"AWAITING_DETAIL"},
        "AWAITING_DETAIL": {"FOLLOWUP_LOOP", "AWAITING_DETAIL"},
        "FOLLOWUP_LOOP": {"AWAITING_DETAIL", "FOLLOWUP_LOOP"},
        None: {"AWAITING_DETAIL", "FOLLOWUP_LOOP", "INITIAL"},
    }
    allowed = valid_transitions.get(ctx.prior_phase, {"AWAITING_DETAIL", "FOLLOWUP_LOOP", "INITIAL"})
    ok = current in allowed
    return CheckResult(
        name="phase_transition",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"{ctx.prior_phase} → {current} ({'OK' if ok else 'unexpected'})",
        data={"prior": ctx.prior_phase, "current": current, "allowed": sorted(allowed)},
    )


def check_factor_coverage(ctx: CheckContext) -> CheckResult:
    """
    At least one factor from the focus_factors plan should be referenced in
    the response. We do a name-token check (case-insensitive).
    """
    if not ctx.focus_factors:
        return CheckResult(name="factor_coverage", passed=True, score=1.0,
                           detail="no focus_factors in telemetry; skipped")
    text = (ctx.assistant_response or "").lower()
    matched = []
    for f in ctx.focus_factors[:5]:
        name = (f.get("name") or "").lower()
        if not name:
            continue
        # split multi-word names; check any token (length > 3) appears
        tokens = [t for t in re.split(r"[\s,/().]+", name) if len(t) > 3]
        if any(t in text for t in tokens):
            matched.append(name)
    ok = len(matched) >= 1
    return CheckResult(
        name="factor_coverage",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail=f"{len(matched)}/{min(5, len(ctx.focus_factors))} top factors mentioned",
        data={"matched": matched[:5], "available": [f.get("name") for f in ctx.focus_factors[:5]]},
    )


def check_no_meta_reviewer_leak(ctx: CheckContext) -> CheckResult:
    """
    The post-validator sometimes leaks reviewer-style text. Hard-fail if found.
    """
    text = (ctx.assistant_response or "").lower()
    bad_markers = (
        "[reviewer]", "(reviewer)", "draft answer",
        "the assistant should", "the assistant's response",
        "as a vedic astrologer", "i would rewrite",
        "let me rewrite", "here is the rewritten",
    )
    leaks = [m for m in bad_markers if m in text]
    ok = not leaks
    return CheckResult(
        name="no_meta_reviewer_leak",
        passed=ok,
        score=1.0 if ok else 0.0,
        detail="no reviewer leak" if ok else f"leaked: {leaks}",
        data={"leaked_markers": leaks},
    )


def check_processing_time_budget(ctx: CheckContext) -> CheckResult:
    """
    Soft latency budget. 45s default for prediction turns, 10s for chitchat.
    A miss does not block 'passed' for the scenario, just logs.
    """
    budget = 10.0 if "chitchat" in ctx.scenario_tags else 45.0
    t = ctx.processing_time_s or 0.0
    ok = t <= budget
    return CheckResult(
        name="processing_time_budget",
        passed=ok,
        score=1.0 if ok else max(0.0, 1.0 - (t - budget) / budget),
        detail=f"{t:.1f}s (budget {budget:.0f}s)",
        data={"elapsed_s": t, "budget_s": budget},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Registry + runner
# ──────────────────────────────────────────────────────────────────────────────

DETERMINISTIC_CHECKS: Tuple[Callable[[CheckContext], CheckResult], ...] = (
    check_response_nonempty,
    check_length_in_range,
    check_language_match,
    check_has_month_year,
    check_no_past_dates,
    check_domain_match,
    check_accuracy_gate_clean,
    check_phase_transitioned_correctly,
    check_factor_coverage,
    check_no_meta_reviewer_leak,
    check_processing_time_budget,
)


def run_deterministic_checks(ctx: CheckContext) -> List[CheckResult]:
    """Run every registered check against the context. Failures don't raise."""
    results: List[CheckResult] = []
    for check in DETERMINISTIC_CHECKS:
        try:
            results.append(check(ctx))
        except Exception as exc:
            results.append(CheckResult(
                name=check.__name__,
                passed=False,
                score=0.0,
                detail=f"check raised: {type(exc).__name__}: {exc}",
            ))
    return results
