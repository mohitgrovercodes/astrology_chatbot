"""
Response Quality — timeline analysis and QA helpers for NakshatraAI predictions.

Problem: ~1,300 lines of quality-assessment and timeline-analysis code lived inline
inside `EnhancedLangGraphOrchestrator`, making the 8k-line god-module hard to read
and impossible to unit-test in isolation.

What this module does:
- Timeline helpers: extract/filter month-year range keys, collect dasha windows,
  infer topic from text, analyse overlap and layer coverage.
- Quality gates: assess_initial_timeline_quality, assess_detailed_answer_quality —
  lightweight structural QA that decides whether a rewrite pass is needed.
- Rewrite prompt builders: build_initial_timeline_rewrite_prompt,
  build_detailed_quality_rewrite_prompt — one-shot prompts that fix quality issues.
- Coherence: build_coherence_hint — adds logical sequencing constraints (marriage
  before children, education before career) from conversation history.
- Context: analyze_query_context — LLM-based query-variant detection.

What is NOT handled:
- LLM invocation for rewrites (caller keeps self.llm.invoke).
- State access or session data — all inputs are plain Python values.
- Prompt-building for the main prediction (see _build_prediction_prompt).

Usage:
    from src.orchestration.response_quality import (
        assess_initial_timeline_quality,
        assess_detailed_answer_quality,
        build_initial_timeline_rewrite_prompt,
        build_detailed_quality_rewrite_prompt,
        build_coherence_hint,
        analyze_query_context,
        inject_deterministic_initial_timeline_diversity,
        collect_recent_cross_topic_window_keys,
        collect_recent_planet_factors,
        collect_future_candidate_window_keys,
        collect_future_timing_years,
        extract_month_year_range_keys,
        filter_non_ended_range_keys,
        infer_topic_from_text,
    )
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Month lookup shared across several functions ─────────────────────────────

_MONTH_MAP: Dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_RANGE_RE = re.compile(
    r"(?i)\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\s+((?:19|20)\d{2})\b"
    r"\s*(?:to|until|till|se|tak|→|-|–|—)\s*"
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\s+((?:19|20)\d{2})\b"
)

_DOMAIN_TOPICS = frozenset(
    {"marriage", "children", "career", "finance", "health", "property", "foreign"}
)


# ── Pure text / timeline helpers ──────────────────────────────────────────────


def infer_topic_from_text(text: str) -> str:
    """Return the astrological domain keyword present in *text*, or 'general'."""
    q = (text or "").lower()
    if any(w in q for w in ["marriage", "marry", "shadi", "shaadi", "vivah", "wedding", "partner", "spouse", "relationship", "rishta"]):
        return "marriage"
    if any(w in q for w in ["career", "job", "naukri", "profession", "business", "promotion", "salary", "interview"]):
        return "career"
    if any(w in q for w in ["finance", "money", "wealth", "gold", "invest", "investment", "paisa", "dhan", "arthik"]):
        return "finance"
    if any(w in q for w in ["health", "sehat", "swasthya", "illness", "disease", "bimari"]):
        return "health"
    if any(w in q for w in ["children", "child", "santaan", "bacche", "baccha", "baby", "birth", "pregnancy", "pregnant", "garbh", "prasav", "fertility"]):
        return "children"
    if any(w in q for w in ["property", "ghar", "home", "house", "flat", "plot", "real estate", "zameen", "land"]):
        return "property"
    if any(w in q for w in ["foreign", "abroad", "videsh", "travel", "visa", "immigration", "overseas"]):
        return "foreign"
    return "general"


def extract_month_year_range_keys(text: str) -> set:
    """Return normalised 'YYYY-MM|YYYY-MM' range keys found in *text*."""
    keys: set = set()
    for m in _RANGE_RE.finditer(text or ""):
        sm, sy = m.group(1), int(m.group(2))
        em, ey = m.group(3), int(m.group(4))
        s_m = _MONTH_MAP.get((sm or "").lower(), 1)
        e_m = _MONTH_MAP.get((em or "").lower(), 12)
        start_key = f"{sy:04d}-{s_m:02d}"
        end_key = f"{ey:04d}-{e_m:02d}"
        if end_key < start_key:
            start_key, end_key = end_key, start_key
        keys.add(f"{start_key}|{end_key}")
    return keys


def filter_non_ended_range_keys(keys: set, today_ym: Optional[str] = None) -> set:
    """Keep only range keys whose end month >= today_ym (current/future)."""
    anchor = today_ym or datetime.utcnow().strftime("%Y-%m")
    kept: set = set()
    for k in keys or set():
        try:
            parts = (k or "").split("|")
            if len(parts) == 2 and parts[1] >= anchor:
                kept.add(k)
        except Exception:
            continue
    return kept


def collect_future_timing_years(
    dasha_data: Optional[Dict[str, Any]],
    max_years_ahead: int = 5,
) -> List[int]:
    """Return sorted future years present in the dasha timeline payload."""
    data = dasha_data or {}
    today = datetime.utcnow().date()
    max_year = today.year + max(1, int(max_years_ahead))
    years: set = set()

    def _add(date_str: str) -> None:
        try:
            d = datetime.strptime((date_str or "").strip(), "%Y-%m-%d").date()
            if d >= today and d.year <= max_year:
                years.add(d.year)
        except Exception:
            pass

    for pd in data.get("upcoming_pratyantardashas", []) or []:
        _add(pd.get("start", "")); _add(pd.get("end", ""))
    for ad in data.get("upcoming_antardashas", []) or []:
        _add(ad.get("start", "")); _add(ad.get("end", ""))
    for x in data.get("next_antardasha_first_pratyantar", []) or []:
        _add(x.get("antardasha_start", ""))
        _add(x.get("first_pratyantar_start", ""))
        _add(x.get("first_pratyantar_end", ""))
    return sorted(years)


def collect_future_candidate_window_keys(dasha_data: Optional[Dict[str, Any]]) -> set:
    """Collect candidate month-range keys from future dasha windows."""
    data = dasha_data or {}
    today = datetime.utcnow().date().isoformat()
    keys: set = set()

    def _key(start_iso: str, end_iso: str) -> str:
        s = (start_iso or "").strip()
        e = (end_iso or "").strip()
        if not s or not e:
            return ""
        try:
            sd = datetime.strptime(s, "%Y-%m-%d").date()
            ed = datetime.strptime(e, "%Y-%m-%d").date()
        except Exception:
            return ""
        a = f"{sd.year:04d}-{sd.month:02d}"
        b = f"{ed.year:04d}-{ed.month:02d}"
        if b < a:
            a, b = b, a
        return f"{a}|{b}"

    for pd in data.get("upcoming_pratyantardashas", []) or []:
        if (pd.get("start") or "9999-12-31") <= today:
            continue
        k = _key(pd.get("start", ""), pd.get("end", ""))
        if k:
            keys.add(k)
    for x in data.get("next_antardasha_first_pratyantar", []) or []:
        if (x.get("first_pratyantar_start") or "9999-12-31") <= today:
            continue
        k = _key(x.get("first_pratyantar_start", ""), x.get("first_pratyantar_end", ""))
        if k:
            keys.add(k)
    return filter_non_ended_range_keys(keys)


def collect_recent_planet_factors(
    conversation_history: Optional[List[Dict[str, Any]]],
    max_turns: int = 3,
) -> List[str]:
    """Return up to 4 planet names that appeared as factors in recent assistant turns."""
    _all_planets = [
        "Venus", "Jupiter", "Saturn", "Mars", "Mercury", "Sun", "Moon", "Rahu", "Ketu",
        "Shukra", "Brihaspati", "Shani", "Mangal", "Budh", "Surya", "Chandra",
    ]
    history = conversation_history or []
    recent: List[str] = []
    seen = 0
    for i in range(len(history) - 1, -1, -1):
        msg = history[i] or {}
        if (msg.get("role") or "").lower() != "assistant":
            continue
        seen += 1
        if seen > max_turns:
            break
        content = msg.get("content") or ""
        for planet in _all_planets:
            if planet.lower() in content.lower() and planet not in recent:
                recent.append(planet)
    return recent[:4]


def collect_recent_cross_topic_window_keys(
    conversation_history: Optional[List[Dict[str, Any]]],
    current_query_type: str,
    max_assistant_turns: int = 8,
) -> Dict[str, Any]:
    """
    Collect month-range keys used in recent assistant turns for topics OTHER than
    current_query_type. Used to enforce cross-topic timeline novelty.
    """
    history = conversation_history or []
    keys: set = set()
    samples: List[str] = []
    seen_assistant = 0
    _current_domain = current_query_type if current_query_type in _DOMAIN_TOPICS else None

    for idx in range(len(history) - 1, -1, -1):
        msg = history[idx] or {}
        if (msg.get("role") or "").lower() != "assistant":
            continue
        seen_assistant += 1
        if seen_assistant > max_assistant_turns:
            break

        metadata = msg.get("metadata") or {}
        topic = (metadata.get("topic") or "").lower().strip()
        if topic not in _DOMAIN_TOPICS:
            preceding_user = ""
            assistant_text = msg.get("content") or ""
            for j in range(idx - 1, -1, -1):
                m2 = history[j] or {}
                if (m2.get("role") or "").lower() == "user":
                    preceding_user = m2.get("content") or ""
                    break
            topic = infer_topic_from_text(preceding_user)
            if topic == "general":
                topic = infer_topic_from_text(assistant_text)

        if topic == "general" or topic == (_current_domain or current_query_type or "general"):
            continue

        raw_windows: list = metadata.get("timing_windows") or []
        extracted = set(raw_windows) if raw_windows else extract_month_year_range_keys(msg.get("content") or "")
        if not extracted:
            continue

        extracted = filter_non_ended_range_keys(extracted)
        if not extracted:
            continue

        keys.update(extracted)
        if len(samples) < 4:
            for k in sorted(extracted):
                if k not in samples:
                    samples.append(k)
                if len(samples) >= 4:
                    break

    return {"keys": keys, "samples": samples}


# ── Timeline layer / overlap analysis ─────────────────────────────────────────


def assess_timeline_layer_coverage(answer: str) -> Dict[str, Any]:
    """
    Detect whether the response uses a realistic multi-layer timeline:
    present trend + short trigger + longer supportive phase + future favorable reason.
    """
    text = answer or ""
    lower = text.lower()

    present_markers = re.findall(
        r"(?i)\b(currently|right now|at present|ongoing|"
        r"is samay|abhi|filhaal|vartaman|iss waqt|"
        r"aaj kal|is waqt|is period|is dauran|is dasha|is pratyantar|"
        r"at this time|in this period|during this|in this phase)\b",
        lower,
    )
    short_markers = re.findall(
        r"(?i)\b(trigger|sub[-\s]?window|next\s+\d{1,2}\s*(?:week|weeks|month|months)|"
        r"coming\s+(?:few\s+)?months|aane wale kuch mahino|agle\s+\d{1,2}\s+mahine|"
        r"short(?:-|\s)?term|near[-\s]?term|q[1-4]\s*(?:20\d{2})?|"
        r"ke dauran|is mahine|agle mahine|pehle\s+\d{1,2}|first\s+\d{1,2}\s*months|"
        r"coming\s+quarter|iss period|iss pratyantar|near future|jald[iy])\b",
        lower,
    )
    long_markers = re.findall(
        r"(?i)\b(supportive phase|broader phase|long[-\s]?range|long[-\s]?term|"
        r"next\s+\d{1,2}\s*(?:year|years)|\d{1,2}\s*-\s*\d{1,2}\s*months|"
        r"saalon|aane wale\s+\d{1,2}\s+saal|maturation|stabilization|"
        r"iske baad|baad mein|second half|doosri half|agle saal|baad ke|"
        r"broader|extended|longer|over the next|multi-year|year[-\s]?long)\b",
        lower,
    )
    _month_year_count = len(re.findall(
        r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(?:19|20)\d{2}\b",
        text,
    ))
    future_markers = re.findall(
        r"(?i)\b(future|aane wale|upcoming|second half|first half|early|mid|late|"
        r"(?:19|20)\d{2})\b",
        lower,
    )
    favorable_markers = re.findall(
        r"(?i)\b(favorable|supportive|positive|opportunity|anukul|shubh|behtar|sahayak)\b",
        lower,
    )
    reason_markers = re.findall(
        r"(?i)\b(because|due to|as|since|therefore|isliye|kyunki|kaaran|vajah)\b",
        lower,
    )

    timeline_expr = 0
    timeline_expr += len(re.findall(r"(?i)\b(?:from|between|se|tak|to)\b.{0,30}\b(?:19|20)\d{2}\b", text))
    timeline_expr += len(re.findall(r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(?:19|20)\d{2}\b", text))
    timeline_expr += len(re.findall(r"(?i)\b(?:next|coming|upcoming|aane wale|agle)\s+\d{1,2}\s*(?:week|weeks|month|months|year|years|mahine|saal)\b", text))

    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    distinct_year_count = len(set(years))
    has_future_favorable_with_reason = bool(future_markers) and bool(favorable_markers) and bool(reason_markers)

    # Fallback: explicit month-year windows substitute for structural keywords in Hinglish.
    _has_short_trigger = bool(short_markers) or _month_year_count >= 1
    _has_long_supportive = bool(long_markers) or _month_year_count >= 2

    return {
        "has_present_layer": bool(present_markers),
        "has_short_trigger_layer": _has_short_trigger,
        "has_long_supportive_layer": _has_long_supportive,
        "has_future_favorable_with_reason": has_future_favorable_with_reason,
        "present_marker_count": len(present_markers),
        "short_marker_count": len(short_markers),
        "long_marker_count": len(long_markers),
        "future_marker_count": len(future_markers),
        "favorable_marker_count": len(favorable_markers),
        "reason_marker_count": len(reason_markers),
        "timeline_expression_count": timeline_expr,
        "distinct_year_count": distinct_year_count,
    }


def analyze_timeline_overlap(answer: str) -> Dict[str, Any]:
    """
    Detect collapsed timeline behavior where multiple major claims reuse
    the same short month-range.
    """
    text = answer or ""
    range_re = re.compile(
        r"(?i)\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
        r")\s+((?:19|20)\d{2})\b"
        r"\s*(?:to|until|till|se|tak|→|-|–|—)\s*"
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
        r")\s+((?:19|20)\d{2})\b"
    )
    ranges = []
    for m in range_re.finditer(text):
        sm, sy, em, ey = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        s_m = _MONTH_MAP.get(sm.lower(), 1)
        e_m = _MONTH_MAP.get(em.lower(), 12)
        s_idx = sy * 12 + s_m
        e_idx = ey * 12 + e_m
        if e_idx < s_idx:
            s_idx, e_idx = e_idx, s_idx
        ranges.append((s_idx, e_idx, m.group(0)))

    max_overlap_count = 0
    has_short_range = False
    samples: List[str] = []
    for i, (s1, e1, txt1) in enumerate(ranges):
        if (e1 - s1 + 1) <= 4:
            has_short_range = True
        overlap_count = sum(
            1 for j, (s2, e2, _) in enumerate(ranges)
            if i != j and max(s1, s2) <= min(e1, e2)
        ) + 1
        if overlap_count > max_overlap_count:
            max_overlap_count = overlap_count
            samples = [txt1]
        elif overlap_count == max_overlap_count and overlap_count > 1:
            samples.append(txt1)

    years = sorted({int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text)})
    range_years: set = set()
    for s_idx, e_idx, _ in ranges:
        range_years.add(s_idx // 12)
        range_years.add(e_idx // 12)

    return {
        "range_count": len(ranges),
        "max_overlap_count": max_overlap_count,
        "collapsed_overlap_detected": max_overlap_count >= 2 and has_short_range,
        "distinct_years": years,
        "distinct_range_years": sorted(range_years),
        "shared_range_samples": samples[:3],
    }


# ── LLM-based helpers ──────────────────────────────────────────────────────────


def llm_check_future_favorable(text: str, fast_llm=None) -> bool:
    """
    Language-agnostic fallback: ask the LLM whether the response mentions
    a future favorable period with a reason. Called only when regex markers
    miss it (non-English responses). Fails open to avoid penalising the answer.
    """
    if fast_llm is None:
        return True
    try:
        prompt = (
            "Does the following astrological response mention:\n"
            "1. A FUTURE favorable or positive time period (e.g. an upcoming month, year, or dasha period), AND\n"
            "2. At least one REASON why that period is favorable (e.g. a planet, dasha lord, transit, or yoga)?\n\n"
            "Answer only YES or NO — nothing else.\n\n"
            f"Response:\n\"\"\"\n{text[:1500]}\n\"\"\""
        )
        result = fast_llm.invoke(prompt)
        answer = (result.content if hasattr(result, "content") else str(result)).strip().upper()
        verdict = answer.startswith("Y")
        logger.info("[LLM_QA] future_favorable check: %s (raw='%s')", verdict, answer[:10])
        return verdict
    except Exception as e:
        logger.info("[LLM_QA] future_favorable check skipped: %s", e)
        return True  # fail open


def analyze_query_context(
    query: str,
    conversation_history: Optional[List[Dict[str, Any]]],
    fast_llm=None,
) -> str:
    """
    LLM-based query-variant detection. Returns a context note to inject into
    the phase prompt, or "" when no special framing is needed.
    """
    if fast_llm is None:
        return ""
    try:
        history = conversation_history or []
        snippet_parts = []
        for msg in history[-4:]:
            role = (msg.get("role") or "").lower()
            content = (msg.get("content") or "").strip()
            if not content or content.startswith("Welcome"):
                continue
            if role == "user":
                snippet_parts.append(f"User: {content[:200]}")
            elif role == "assistant":
                snippet_parts.append(f"Astrologer: {content[:300]}")
        snippet = "\n".join(snippet_parts)

        prompt = (
            "You are a Vedic astrology assistant helping an AI astrologer understand "
            "the precise intent of a user's query.\n\n"
            f"Recent conversation:\n{snippet}\n\n"
            f"Current query: {query}\n\n"
            "Task: Does the current query have a SPECIFIC CONTEXT that requires "
            "different astrological indicators than the default for its topic?\n\n"
            "Examples of context shifts:\n"
            "- 'Meri doosri shadi kab hogi?' after a first-marriage answer → second marriage "
            "(9th house lord, Rahu, 2nd house — NOT 7th house which was already discussed)\n"
            "- 'Mera doosra bachha kab hoga?' after a first-child answer → second child "
            "(3rd from 5th = 7th house for second child)\n"
            "- 'Foreign job kab milega?' after a general career answer → foreign work "
            "(12th house, 9th house, Rahu — not just 10th house)\n"
            "- 'Mere career mein promotion kab hoga?' → specific career sub-topic\n\n"
            "If no special context is needed, return exactly: NONE\n\n"
            "If a context shift is detected, return a brief 2-4 sentence instruction "
            "for the astrologer in this format:\n"
            "CONTEXT: <plain English instruction — which houses/planets to use, "
            "what NOT to repeat from prior answer, what to address directly>\n\n"
            "Return ONLY 'NONE' or 'CONTEXT: ...' — nothing else."
        )

        result = fast_llm.invoke(prompt)
        raw = (getattr(result, "content", None) or str(result) or "").strip()
        if not raw or raw.upper().startswith("NONE"):
            return ""
        if raw.upper().startswith("CONTEXT:"):
            return f"QUERY CONTEXT NOTE (from conversation analysis):\n{raw[len('CONTEXT:'):].strip()}"
        return ""
    except Exception:
        return ""


# ── Quality assessment ─────────────────────────────────────────────────────────


def assess_initial_timeline_quality(
    answer: str,
    language: str = "en",
    fast_llm=None,
) -> Tuple[bool, Dict[str, Any]]:
    """Lightweight QA for initial short responses — structure, timing, future window."""
    text = answer or ""
    word_count = len(re.findall(r"\S+", text))
    _current_year = datetime.utcnow().year
    _all_years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text)]
    past_year_mentions = len([y for y in _all_years if y < _current_year - 1])
    month_year_mentions = len(re.findall(
        r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(?:19|20)\d{2}\b",
        text,
    ))
    duration_only_mentions = len(re.findall(
        r"(?i)\b\d{1,2}\s*-\s*\d{1,2}\s*(?:months?|mahine|saal|years?)\b", text
    ))
    timeline_layers = assess_timeline_layer_coverage(text)
    _today_ym = datetime.utcnow().strftime("%Y-%m")
    _distinct_range_keys = filter_non_ended_range_keys(
        extract_month_year_range_keys(text), today_ym=_today_ym,
    )

    def _parse_key_to_metrics(k: str) -> Optional[Tuple[int, int]]:
        try:
            _s, _e = k.split("|")
            _sy, _sm = [int(x) for x in _s.split("-")]
            _ey, _em = [int(x) for x in _e.split("-")]
            _s_idx = _sy * 12 + _sm
            _e_idx = _ey * 12 + _em
            if _e_idx < _s_idx:
                _s_idx, _e_idx = _e_idx, _s_idx
            return _s_idx, (_e_idx - _s_idx + 1)
        except Exception:
            return None

    _window_metrics = [m for m in (_parse_key_to_metrics(k) for k in _distinct_range_keys) if m]

    def _duration_band(months: int) -> str:
        if months <= 4:
            return "short"
        if months <= 10:
            return "medium"
        return "long"

    issues: List[str] = []
    if word_count < 80:
        issues.append("short_answer_too_brief_for_rich_timeline")
    if not timeline_layers.get("has_present_layer"):
        issues.append("missing_present_context_in_short_answer")
    if not timeline_layers.get("has_future_favorable_with_reason"):
        if not llm_check_future_favorable(text, fast_llm):
            issues.append("missing_future_favorable_reason_in_short_answer")
    if month_year_mentions < 1:
        issues.append("insufficient_explicit_month_year_windows_in_short_answer")
    if len(_distinct_range_keys) < 1:
        issues.append("insufficient_distinct_month_year_windows_in_short_answer")
    if duration_only_mentions > 0 and month_year_mentions < 1:
        issues.append("duration_only_timeline_without_explicit_month_year_ranges")
    if past_year_mentions > 0:
        issues.append("contains_past_year_timeline_reference")

    quality = {
        "word_count": word_count,
        "month_year_mentions": month_year_mentions,
        "distinct_range_count": len(_distinct_range_keys),
        "past_year_mentions": past_year_mentions,
        "duration_only_mentions": duration_only_mentions,
        "timeline_layers": timeline_layers,
        "issues": issues,
    }
    return (len(issues) == 0), quality


def assess_detailed_answer_quality(
    answer: str,
    factor_profile: Optional[Dict[str, Any]] = None,
    language: str = "en",
    fast_llm=None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Lightweight structural QA for detailed responses. Checks depth, timing
    richness, factor coverage, style-leak markers, and timeline overlap.
    """
    text = answer or ""
    word_count = len(re.findall(r"\S+", text))
    numbered_points = len(re.findall(r"(?m)^\s*\d{1,2}\s*[\).:-]", text))

    _current_year = datetime.utcnow().year
    _all_years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text)]
    year_mentions = len(_all_years)
    past_year_mentions = len([y for y in _all_years if y < _current_year - 1])
    month_year_mentions = len(re.findall(
        r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(?:19|20)\d{2}\b",
        text,
    ))
    duration_only_mentions = len(re.findall(
        r"(?i)\b\d{1,2}\s*-\s*\d{1,2}\s*(?:months?|mahine|saal|years?)\b", text
    ))
    timing_range_markers = len(re.findall(
        r"(?i)\b(from|between|until|through|to|se|tak)\b|के बीच|से लेकर|तक", text
    ))

    timeline_layers = assess_timeline_layer_coverage(text)
    timeline_overlap = analyze_timeline_overlap(text)

    _forbidden_labels = [
        r"(?i)\bcross[- ]year window\b",
        r"(?i)\bshort trigger (?:window|phase)\b",
        r"(?i)\blong supportive (?:window|phase)\b",
        r"(?i)\bmaturation horizon\b",
        r"(?i)\btimeline ladder\b",
    ]
    _style_leak_detected = any(re.search(pat, text) for pat in _forbidden_labels)

    _min_detail_words = 280
    _max_detail_words = 520

    issues: List[str] = []
    if _style_leak_detected:
        issues.append("structural_label_style_leak_in_user_facing_text")
    if word_count < _min_detail_words:
        issues.append("answer_too_short_for_detailed_mode")
    if word_count > _max_detail_words:
        issues.append("answer_too_long_for_detailed_mode")
    if year_mentions < 3:
        issues.append("too_few_year_mentions_for_long_short_timelines")
    if timing_range_markers < 2 and month_year_mentions < 4:
        issues.append("missing_clear_long_and_short_timeline_ranges")
    if duration_only_mentions > 0 and month_year_mentions < 3:
        issues.append("duration_only_timeline_without_explicit_month_year_ranges")
    if past_year_mentions > 0:
        issues.append("contains_past_year_timeline_reference")
    if not timeline_layers.get("has_present_layer"):
        issues.append("missing_present_trend_layer")
    if not timeline_layers.get("has_short_trigger_layer"):
        issues.append("missing_short_trigger_layer")
    if not timeline_layers.get("has_long_supportive_layer"):
        issues.append("missing_long_supportive_layer")
    if not timeline_layers.get("has_future_favorable_with_reason"):
        if not llm_check_future_favorable(text, fast_llm):
            issues.append("missing_future_favorable_timeline_reason")
    if (timeline_layers.get("timeline_expression_count", 0) < 3
            or timeline_layers.get("distinct_year_count", 0) < 2):
        issues.append("timeline_not_varied_enough")
    if timeline_overlap.get("collapsed_overlap_detected"):
        issues.append("multiple_major_claims_collapsed_into_same_short_window")
        if len(timeline_overlap.get("distinct_range_years", [])) < 2:
            issues.append("missing_distinct_cross_year_secondary_window")

    available_categories = (factor_profile or {}).get("available_categories", []) or []
    underutilized_available = (factor_profile or {}).get("underutilized_available", []) or []

    category_patterns = {
        "house_lords": r"(?i)\b(?:house\s+lord|lagnesh|lord of the|1st house|2nd house|3rd house|4th house|5th house|6th house|7th house|8th house|9th house|10th house|11th house|12th house)\b",
        "dasha_stack": r"(?i)\b(?:mahadasha|antardasha|dasha)\b",
        "pratyantar_windows": r"(?i)\b(?:pratyantar|pratyantardasha)\b",
        "gochara_transits": r"(?i)\b(?:gochar|gochara|transit|transiting)\b",
        "yogas": r"(?i)\byoga\b",
        "divisional_confirmation": r"(?i)\b(?:navamsa|dashamsa|dasamsa|divisional chart|d9|d10)\b",
        "planetary_conditions": r"(?i)\b(?:retrograde|combust|deeply combust|stationary)\b",
        "vargottama": r"(?i)\bvargottama\b",
        "vimshopaka": r"(?i)\b(?:vimshopaka|bala)\b",
        "planetary_wars": r"(?i)\b(?:graha yuddha|planetary war)\b",
        "house_occupancy": r"(?i)\b(?:house occupancy|planets in (?:the )?\d+(?:st|nd|rd|th) house)\b",
        "aspects": r"(?i)\baspect\b",
        "validation_findings": r"(?i)\b(?:validation|overall strength|critical failure|can proceed)\b",
        "synthesis_strengths_challenges": r"(?i)\b(?:chart strengths|chart challenges)\b",
    }

    mentioned_categories = [
        cat for cat in available_categories
        if (pat := category_patterns.get(cat)) and re.search(pat, text)
    ]
    underutilized_mentioned = [c for c in underutilized_available if c in mentioned_categories]

    if available_categories:
        min_required = min(6, max(4, len(available_categories) // 2))
        if len(mentioned_categories) < min_required:
            issues.append("insufficient_factor_coverage_from_available_data")
    if len(underutilized_available) >= 2 and len(underutilized_mentioned) < 2:
        issues.append("underutilized_factors_not_reflected_enough")

    missing_available_categories = [c for c in available_categories if c not in mentioned_categories]
    quality = {
        "word_count": word_count,
        "min_words_threshold": _min_detail_words,
        "numbered_points": numbered_points,
        "year_mentions": year_mentions,
        "past_year_mentions": past_year_mentions,
        "month_year_mentions": month_year_mentions,
        "duration_only_mentions": duration_only_mentions,
        "timing_range_markers": timing_range_markers,
        "timeline_layers": timeline_layers,
        "timeline_overlap": timeline_overlap,
        "available_factor_count": len(available_categories),
        "factor_coverage_count": len(mentioned_categories),
        "available_categories": available_categories,
        "mentioned_categories": mentioned_categories,
        "missing_available_categories": missing_available_categories,
        "underutilized_available_count": len(underutilized_available),
        "underutilized_mentioned_count": len(underutilized_mentioned),
        "underutilized_available": underutilized_available,
        "underutilized_mentioned": underutilized_mentioned,
        "issues": issues,
    }
    return (len(issues) == 0), quality


# ── Deterministic diversity injection ─────────────────────────────────────────


def inject_deterministic_initial_timeline_diversity(
    answer: str,
    dasha_data: Optional[Dict[str, Any]],
    language: str = "en",
    recent_cross_topic_keys: Optional[set] = None,
    min_lead_months: int = 2,
) -> str:
    """
    Deterministic fallback when LLM rewrites still fail timeline diversity.
    Appends one or two future month-year windows so at least two distinct windows exist.
    """
    text = (answer or "").strip()
    data = dasha_data or {}
    recent_keys = set(recent_cross_topic_keys or set())
    today = datetime.utcnow().date()
    today_ym = today.strftime("%Y-%m")

    def _parse_iso(value: str):
        try:
            return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
        except Exception:
            return None

    def _key_from_dates(start_iso: str, end_iso: str) -> str:
        s = _parse_iso(start_iso)
        e = _parse_iso(end_iso)
        if not s or not e:
            return ""
        a = f"{s.year:04d}-{s.month:02d}"
        b = f"{e.year:04d}-{e.month:02d}"
        if b < a:
            a, b = b, a
        return f"{a}|{b}"

    def _to_month_label(ym: str) -> str:
        y, m = [int(x) for x in ym.split("-")]
        return datetime(y, m, 1).strftime("%B %Y")

    def _duration_band(start_iso: str, end_iso: str) -> str:
        s = _parse_iso(start_iso)
        e = _parse_iso(end_iso)
        if not s or not e:
            return "unknown"
        months = max(1, (e.year - s.year) * 12 + (e.month - s.month) + 1)
        if months <= 4:
            return "short"
        if months <= 10:
            return "medium"
        return "long"

    def _lead_months(start_iso: str) -> Optional[int]:
        s = _parse_iso(start_iso)
        if not s:
            return None
        return max(0, (s.year - today.year) * 12 + (s.month - today.month))

    existing_keys = filter_non_ended_range_keys(
        extract_month_year_range_keys(text), today_ym=today_ym,
    )
    reused_in_text = set(existing_keys).intersection(recent_keys)

    candidates: List[Dict[str, Any]] = []
    for source_key, entries in [
        ("upcoming_pratyantardashas", data.get("upcoming_pratyantardashas", []) or []),
        ("next_antardasha_first_pratyantar", data.get("next_antardasha_first_pratyantar", []) or []),
        ("upcoming_antardashas", data.get("upcoming_antardashas", []) or []),
    ]:
        for entry in entries:
            if source_key == "next_antardasha_first_pratyantar":
                st = entry.get("first_pratyantar_start")
                en = entry.get("first_pratyantar_end")
            else:
                st = entry.get("start")
                en = entry.get("end")
            if not st or not en or st <= today.isoformat():
                continue
            lead = _lead_months(st)
            if lead is None or lead < min_lead_months:
                continue
            key = _key_from_dates(st, en)
            if key:
                candidates.append({"key": key, "start": st, "end": en, "band": _duration_band(st, en), "lead": lead})

    dedup: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        k = c["key"]
        if k not in dedup or c["lead"] < dedup[k]["lead"]:
            dedup[k] = c
    pool = sorted(dedup.values(), key=lambda x: (x["lead"], x["start"]))

    preferred = [c for c in pool if c["key"] not in recent_keys and c["key"] not in existing_keys]
    usable = preferred or [c for c in pool if c["key"] not in existing_keys]
    if not usable:
        return text

    selected: List[Dict[str, Any]] = []
    for c in usable:
        if not selected:
            selected.append(c)
            continue
        s0 = _parse_iso(selected[0]["start"])
        s1 = _parse_iso(c["start"])
        spaced = bool(s0 and s1 and abs((s1.year - s0.year) * 12 + (s1.month - s0.month)) >= 3)
        if c["band"] != selected[0]["band"] or spaced:
            selected.append(c)
            break
    if len(selected) == 1:
        for c in usable:
            if c["key"] != selected[0]["key"]:
                selected.append(c)
                break

    if not selected:
        return text

    # Strip sentences whose month-year overlaps with cross-topic windows.
    _cross_topic_start_months: set = {_rk.split("|")[0] for _rk in recent_keys if "|" in _rk}
    _needs_cleanup = bool(reused_in_text) or bool(_cross_topic_start_months)
    if _needs_cleanup and preferred:
        cleaned = text
        for _rk in reused_in_text:
            try:
                _s_ym, _e_ym = _rk.split("|")
                _s_lbl = _to_month_label(_s_ym)
                _e_lbl = _to_month_label(_e_ym)
                cleaned = re.sub(
                    rf"(?is)\b[^.!?\n]*{re.escape(_s_lbl)}[^.!?\n]*(?:to|se|tak|until|till|→|-|–|—)\s*{re.escape(_e_lbl)}[^.!?\n]*[.!?]?",
                    " ", cleaned,
                )
                cleaned = re.sub(
                    rf"(?is)\b[^.!?\n]*{re.escape(_s_lbl)}[^.!?\n]*{re.escape(_e_lbl)}[^.!?\n]*[.!?]?",
                    " ", cleaned,
                )
            except Exception:
                continue
        for _sm in _cross_topic_start_months:
            try:
                _sm_lbl = _to_month_label(_sm)
                cleaned = re.sub(rf"(?is)[^.!?\n]*\b{re.escape(_sm_lbl)}\b[^.!?\n]*[.!?]?", " ", cleaned)
            except Exception:
                continue
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned and len(cleaned) > 50:
            text = cleaned

    _is_hi = (language or "").lower().startswith("hi")
    if _is_hi:
        if len(selected) >= 2:
            addendum = (
                f"Ek secondary supportive window {_to_month_label(selected[0]['key'].split('|')[0])} se "
                f"{_to_month_label(selected[0]['key'].split('|')[1])} tak bhi banta hai. "
                f"Iske baad {_to_month_label(selected[1]['key'].split('|')[0])} se "
                f"{_to_month_label(selected[1]['key'].split('|')[1])} tak ka phase momentum ko aur strong kar sakta hai."
            )
        else:
            addendum = (
                f"Ek secondary supportive window {_to_month_label(selected[0]['key'].split('|')[0])} se "
                f"{_to_month_label(selected[0]['key'].split('|')[1])} tak bhi dikh raha hai."
            )
    elif len(selected) >= 2:
        addendum = (
            f"A secondary supportive window also appears from {_to_month_label(selected[0]['key'].split('|')[0])} to "
            f"{_to_month_label(selected[0]['key'].split('|')[1])}. "
            f"After that, the {_to_month_label(selected[1]['key'].split('|')[0])} to "
            f"{_to_month_label(selected[1]['key'].split('|')[1])} phase can carry the momentum forward."
        )
    else:
        addendum = (
            f"A secondary supportive window also appears from {_to_month_label(selected[0]['key'].split('|')[0])} to "
            f"{_to_month_label(selected[0]['key'].split('|')[1])}."
        )

    return (text + "\n\n" + addendum).strip()


# ── Coherence hint ─────────────────────────────────────────────────────────────


def build_coherence_hint(
    conversation_history: Optional[List[Dict[str, Any]]],
    current_topic: str,
    current_query: str = "",
) -> str:
    """
    Build logical coherence constraints from conversation context — e.g. children
    cannot precede marriage, career milestones cannot precede graduation.
    """
    hints: List[str] = []
    history = conversation_history or []
    effective_topic = current_topic if current_topic in _DOMAIN_TOPICS else infer_topic_from_text(current_query)

    if effective_topic == "children":
        _marriage_kws = {"shadi", "shaadi", "marriage", "vivah", "rishta", "wedding"}
        marriage_window_end: Optional[str] = None
        for i in range(len(history) - 1, -1, -1):
            msg = history[i] or {}
            if (msg.get("role") or "").lower() != "assistant":
                continue
            meta = msg.get("metadata") or {}
            is_marriage_turn = (meta.get("topic") or "").lower() == "marriage"
            if not is_marriage_turn:
                for j in range(i - 1, -1, -1):
                    m2 = history[j] or {}
                    if (m2.get("role") or "").lower() == "user":
                        if any(k in (m2.get("content") or "").lower() for k in _marriage_kws):
                            is_marriage_turn = True
                        break
            if not is_marriage_turn:
                continue
            raw_windows: list = meta.get("timing_windows") or []
            marriage_keys = set(raw_windows) if raw_windows else extract_month_year_range_keys(msg.get("content") or "")
            if marriage_keys:
                end_months = sorted(k.split("|")[1] for k in marriage_keys if "|" in k)
                if end_months:
                    marriage_window_end = end_months[0]
            break

        if marriage_window_end:
            try:
                _mwe_dt = datetime.strptime(marriage_window_end, "%Y-%m")
                _child_earliest_year = _mwe_dt.year + 1
                _child_earliest_month_str = f"{_mwe_dt.strftime('%B')} {_child_earliest_year}"
                hints.append(
                    f"COHERENCE CONSTRAINT: Marriage timing was discussed as ending around {marriage_window_end}. "
                    f"Children/santaan timing MUST NOT overlap with or precede the marriage window. "
                    f"The earliest possible child timing is {_child_earliest_month_str} (at least 12 months after marriage). "
                    f"A timing window that overlaps with the marriage window is logically impossible — discard it even if the dasha data shows it."
                )
            except Exception:
                hints.append(
                    "COHERENCE CONSTRAINT: Marriage timing was already discussed. "
                    "Children/santaan timing MUST come at least 12-18 months AFTER the marriage window ends — never suggest children in the same period as marriage."
                )
        else:
            hints.append(
                "COHERENCE CONSTRAINT: The user may not yet be married. If suggesting children timing, "
                "place it at least 1-2 years after a reasonable marriage window, and acknowledge this naturally."
            )

    elif effective_topic == "career" and any(
        any(k in (m.get("content") or "").lower() for k in ("exam", "study", "college", "degree", "padhai", "education"))
        for m in history[-6:] if (m.get("role") or "") == "user"
    ):
        hints.append(
            "COHERENCE CONSTRAINT: The user appears to be a student. Career/job timing should be placed "
            "after a plausible graduation date — do not suggest promotions or business milestones before the user has finished education."
        )

    return "\n".join(hints) if hints else ""


# ── Rewrite prompt builders ────────────────────────────────────────────────────


def build_initial_timeline_rewrite_prompt(
    query: str,
    draft_answer: str,
    language: str,
    quality: Dict[str, Any],
) -> str:
    issue_list = quality.get("issues", []) or ["insufficient_timeline_structure"]
    issues = ", ".join(issue_list)
    _allow_novelty = "reused_cross_topic_timeline_window_despite_available_alternatives" in issue_list
    _timing_lock = (
        "10) CRITICAL — Keep planet-lord logic and factual chart grounding unchanged. "
        "You MAY replace a repeated timeline window with a distinct valid future window from computed dasha data "
        "when needed for novelty, but do not invent dates or swap facts arbitrarily."
        if _allow_novelty else
        "10) CRITICAL — Do NOT change planet names, pratyantar lords, or timing windows already stated in the "
        "current answer. For example, if the current answer says \"Venus pratyantar April–June 2026\", "
        "your rewrite must also reference Venus (not Ketu or any other planet) for that window. "
        "Only improve structure and clarity; never swap astrological facts."
    )
    novelty_guard = (
        "\n11) CRITICAL NOVELTY: Avoid reusing the same month-year window that was already used in a recent different topic, "
        "when another valid future window exists in computed dasha data. Keep astrology correct, but choose a distinct window."
        if _allow_novelty else ""
    )
    return (
        f"You are refining a short astrology answer for stronger practical timeline quality.\n"
        f"Keep facts grounded in the same computed data already provided. Do NOT invent chart facts.\n\n"
        f"User query: \"{query}\"\n"
        f"Language code to preserve: {language}\n"
        f"Detected issues: {issues}\n\n"
        f"Current answer:\n\"\"\"\n{draft_answer}\n\"\"\"\n\n"
        f"Rewrite requirements (MANDATORY):\n"
        f"1) Keep the SAME language/script style and warm tone.\n"
        f"2) Keep target length around 150-200 words.\n"
        f"3) Include 2-3 critical astrological factors with practical meaning.\n"
        f"4) Use a 3-layer timeline architecture naturally:\n"
        f"   - Present context (what is active now or in current phase),\n"
        f"   - Primary timing layer with explicit month-year range,\n"
        f"   - Secondary timing layer with explicit month-year range from a DIFFERENT horizon.\n"
        f"   Horizon mix must avoid repetitive all-short windows:\n"
        f"   - At least one of the two timing layers must be MID or BROAD (not both short pratyantar-like).\n"
        f"5) For the favorable future window, explicitly include WHY it is favorable (factor -> timing logic -> practical outcome).\n"
        f"6) Use explicit month-year windows for each timing layer (minimum 2 distinct month-year ranges); avoid duration-only phrasing like \"6-18 months\".\n"
        f"6b) The two timing layers must be genuinely diverse:\n"
        f"   - Their duration profiles should differ (for example one short trigger + one medium/long supportive phase),\n"
        f"   - Their start months should not be near-identical when alternative valid windows exist.\n"
        f"7) Use only future-facing or ongoing-to-future timing; no ended past windows.\n"
        f"8) No exact day-level dates.\n"
        f"9) Write timelines in natural human phrasing. Do NOT use framework labels like\n"
        f"   \"short trigger window\", \"long supportive phase\", \"maturation horizon\", \"timeline ladder\",\n"
        f"   \"Cross-Year Window\", or any structural heading that sounds like an internal template label.\n"
        f"{_timing_lock}\n{novelty_guard}\n\n"
        f"Return ONLY the improved answer text."
    )


def build_detailed_quality_rewrite_prompt(
    query: str,
    draft_answer: str,
    language: str,
    quality: Dict[str, Any],
    factor_profile: Optional[Dict[str, Any]] = None,
) -> str:
    """Build one-shot regeneration prompt when a detailed answer misses structure goals."""
    issues = quality.get("issues", []) or ["insufficient_structure"]
    issue_text = ", ".join(str(i) for i in issues)
    _allow_novelty = "reused_cross_topic_timeline_window_despite_available_alternatives" in issues
    available_categories = (factor_profile or {}).get("available_categories", []) or quality.get("available_categories", [])
    underutilized_available = (factor_profile or {}).get("underutilized_available", []) or quality.get("underutilized_available", [])
    missing_categories = quality.get("missing_available_categories", []) or []
    timeline_overlap = quality.get("timeline_overlap", {}) or {}
    overlap_samples = ", ".join(timeline_overlap.get("shared_range_samples", [])[:2]) if timeline_overlap.get("shared_range_samples") else "none"

    overlap_guard = (
        "\n11) IMPORTANT: Do not collapse multiple major claims into the same 3-4 month band. "
        "If two claims overlap in a short period, include one additional distinct cross-year "
        "window with a separate reason-chain and practical implication."
        f"\n   Detected overlapping examples in draft: {overlap_samples}"
        if "multiple_major_claims_collapsed_into_same_short_window" in issues else ""
    )
    _needs_cross_year = any(x in issues for x in [
        "timeline_not_varied_enough",
        "multiple_major_claims_collapsed_into_same_short_window",
        "missing_distinct_cross_year_secondary_window",
    ])
    cross_year_guard = (
        "\n10) CROSS-YEAR DIVERSITY: When all near-term pratyantar windows fall within the same "
        "calendar year, explicitly mention at least one broader antardasha-level window that "
        "extends into a different year (e.g. 'after this antardasha ends in [year], the next "
        "phase [planet] Antardasha brings...') to ensure the response covers more than one year."
        if _needs_cross_year else ""
    )
    novelty_guard = (
        "\n12) CROSS-TOPIC NOVELTY: The draft reuses a month-year range recently used in another topic. "
        "If another astrologically valid window exists in ranked candidates, replace at least the primary "
        "or secondary window with a distinct one while preserving factual consistency."
        if "reused_cross_topic_timeline_window_despite_available_alternatives" in issues else ""
    )
    timing_lock = (
        "10) CRITICAL — Keep planet-lord logic and factual chart grounding unchanged. "
        "You MAY replace a repeated timeline window with a distinct valid future window from ranked/candidate dasha windows "
        "when needed for novelty, but do not invent dates or swap facts arbitrarily."
        if _allow_novelty else
        "10) CRITICAL — Do NOT change planet names, pratyantar lords, or timing windows already stated in the "
        "current answer. If the current answer says a specific planet governs a specific timing window, "
        "your rewrite must preserve that planet-timing pairing exactly. Only improve depth, structure, and "
        "coverage. Never swap one planet for another (e.g. do not change Venus to Ketu or vice versa)."
    )
    return (
        f"You are refining an astrology answer to meet strict quality requirements.\n"
        f"Keep all factual claims grounded in the computed chart/dasha/transit data already used.\n"
        f"Do NOT invent new planetary placements or dates.\n\n"
        f"User query: \"{query}\"\n"
        f"Language code to preserve: {language}\n\n"
        f"Current answer (needs improvement):\n\"\"\"\n{draft_answer}\n\"\"\"\n\n"
        f"Problems detected: {issue_text}\n"
        f"Available computed factor categories: {', '.join(available_categories) if available_categories else 'unknown'}\n"
        f"Underutilized categories available now: {', '.join(underutilized_available) if underutilized_available else 'none'}\n"
        f"Categories missing in current draft: {', '.join(missing_categories[:10]) if missing_categories else 'none'}\n\n"
        f"Rewrite requirements (MANDATORY):\n"
        f"1) Keep the SAME language/script style as the current answer.\n"
        f"2) Write in flowing prose — NO numbered lists, NO bold markdown headers. The response must read like a natural astrologer speaking, not a report.\n"
        f"3) Target 380-500 words.\n"
        f"4) Cover at least 5 distinct astrological factors naturally woven into paragraphs. For each factor, use reason chain: astrological factor → interpretation → practical implication.\n"
        f"5) Include layered timing with reasoning:\n"
        f"   - one near-term activation period from relevant pratyantar (explicit month-year range),\n"
        f"   - one broader future period that may cross years,\n"
        f"   - for every major prediction claim, include at least one future favorable/supportive timeline and why it is favorable.\n"
        f"6) Use broad coverage from available computed categories above — include at least 5 available categories.\n"
        f"7) Include at least 2 underutilized categories when available (e.g., gochara/transits, yogas, divisional confirmation, vargottama, planetary conditions, house occupancy, aspects).\n"
        f"8) Keep tone warm, expert, and empathetic.\n"
        f"9) Do NOT write framework labels in user-facing text (e.g., \"short trigger window\",\n"
        f"   \"long supportive phase\", \"maturation horizon\", \"timeline ladder\", \"Cross-Year Window\",\n"
        f"   or any label that reads like an internal structural template). Use natural conversational phrasing.\n"
        f"{timing_lock}\n{cross_year_guard}{overlap_guard}{novelty_guard}\n"
        f"Return ONLY the improved final answer text."
    )
