"""
Event timeline reasoner.

Builds deterministic window candidates from upcoming pratyantardasha data.
"""

from typing import Dict, List, Any
from datetime import datetime


DOMAIN_PRIORITIES = {
    "marriage": {"VENUS", "JUPITER"},
    "divorce": {"SATURN", "MARS", "RAHU", "KETU"},
    "career": {"SATURN", "SUN", "MERCURY"},
    "finance": {"VENUS", "JUPITER"},
    "children": {"JUPITER", "MOON"},
    "health": {"SATURN", "MARS", "RAHU", "KETU"},
    "home": {"MOON", "MARS"},
    "foreign": {"RAHU"},
}


def _fmt_month(date_value: str) -> str:
    try:
        dt = datetime.fromisoformat(date_value)
        return dt.strftime("%b %Y")
    except Exception:
        return date_value or "Unknown"


def build_timeline_windows(
    query_domain: str,
    dasha_data: Dict[str, Any],
    chart_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build domain-filtered timing windows with confidence scores.
    """
    del chart_data  # Reserved for future deterministic weighting.

    preferred = DOMAIN_PRIORITIES.get((query_domain or "general").lower(), set())
    upcoming = (dasha_data or {}).get("upcoming_pratyantardashas", []) or []

    windows: List[Dict[str, Any]] = []
    for item in upcoming[:20]:
        planet = (item.get("planet") or "").upper()
        start = item.get("start")
        end = item.get("end")
        if not start or not end:
            continue

        confidence = 0.85 if planet in preferred else 0.55
        label = f"{planet} pratyantar" if planet else "pratyantar window"

        windows.append(
            {
                "label": label,
                "start": start,
                "end": end,
                "start_month": _fmt_month(start),
                "end_month": _fmt_month(end),
                "confidence": round(confidence, 2),
                "reason": "domain-priority match" if planet in preferred else "secondary support",
            }
        )

    windows.sort(key=lambda w: (-w["confidence"], w["start"]))
    return windows[:6]
