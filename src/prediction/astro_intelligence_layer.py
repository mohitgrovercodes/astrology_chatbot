"""
Deterministic astrology intelligence layer.

Purpose:
- Build machine-readable evidence before narrative generation.
- Keep LLM focused on computed signals instead of free-form inference.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src.prediction.timeline_reasoner import build_timeline_windows


@dataclass
class AstroSignal:
    name: str
    value: str
    confidence: float
    rationale: str


def _safe_upper(value: Optional[str]) -> str:
    return (value or "").upper()


def infer_query_domain(
    query: str,
    fallback_domain: str = "general",
    intent_domain: Optional[str] = None,
) -> str:
    """
    Infer a concrete domain label for the query.

    Priority:
    1) Explicit intent_domain (from validation/intent classifier), if mapped.
    2) Heuristics over the original user query text.
    3) Fallback label (usually "general").
    """
    # 1) Use structured intent domain if available and recognized
    normalized_intent = (intent_domain or "").strip().lower()
    if normalized_intent in {
        "marriage",
        "divorce",
        "career",
        "finance",
        "children",
        "health",
        "home",
        "foreign",
    }:
        return normalized_intent

    # 2) Heuristic inference from the raw query
    q = (query or "").lower()

    # Treat destructive-phrasing around marriage/relationship as divorce queries.
    # Examples: "meri shaadi kab tootegi", "mera rishta kab tootega", "relationship kab khatam hoga".
    if (
        any(w in q for w in ["shaadi", "shadi", "rishta", "relationship", "marriage"])
        and any(
            w in q
            for w in [
                "toot", "tut", "tootegi", "tootega", "tutegi", "tutega",
                "toot jayegi", "toot jayega", "khatam", "khatam hogi", "khatam hoga",
                "tod du", "tod doon", "tod dungi", "todunga",
            ]
        )
    ):
        return "divorce"

    if any(w in q for w in ["divorce", "separation", "talaq", "breakup"]):
        return "divorce"
    if any(w in q for w in ["marriage", "shaadi", "partner", "relationship", "spouse"]):
        return "marriage"
    if any(w in q for w in ["career", "job", "profession", "promotion", "work", "naukri"]):
        return "career"
    if any(w in q for w in ["money", "finance", "wealth", "income", "paisa", "dhan"]):
        return "finance"
    if any(w in q for w in ["child", "children", "pregnancy", "santan", "baby"]):
        return "children"
    if any(w in q for w in ["health", "illness", "disease", "surgery", "sehat"]):
        return "health"
    if any(w in q for w in ["home", "house", "property", "ghar", "real estate"]):
        return "home"
    if any(w in q for w in ["foreign", "abroad", "visa", "overseas", "immigration"]):
        return "foreign"

    # 3) Fallback
    return fallback_domain


def build_astro_evidence(
    query: str,
    chart_data: Dict[str, Any],
    dasha_data: Dict[str, Any],
    transit_data: Dict[str, Any],
    domain_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build deterministic evidence payload consumed by prompt and API.

    domain_hint is expected to come from higher-level intent/validation layers
    (e.g., "marriage", "career", "health"). When present, we treat it as an
    explicit intent_domain signal for maximum consistency across the system.
    """
    domain = infer_query_domain(
        query,
        fallback_domain=domain_hint or "general",
        intent_domain=domain_hint,
    )

    active_md = _safe_upper((dasha_data or {}).get("mahadasha", {}).get("planet"))
    active_ad = _safe_upper((dasha_data or {}).get("antardasha", {}).get("planet"))
    active_pd = _safe_upper((dasha_data or {}).get("pratyantardasha", {}).get("planet"))
    lagna_sign = ((chart_data or {}).get("lagna") or {}).get("sign", "Unknown")

    transits = (transit_data or {}).get("transits", {})
    jupiter_sign = transits.get("JUPITER") or transits.get("Jupiter") or "Unknown"
    saturn_sign = transits.get("SATURN") or transits.get("Saturn") or "Unknown"

    signals: List[AstroSignal] = [
        AstroSignal(
            name="active_dasha_stack",
            value=f"{active_md}/{active_ad}/{active_pd}",
            confidence=0.88,
            rationale="Directly sourced from computed dasha payload.",
        ),
        AstroSignal(
            name="lagna_anchor",
            value=str(lagna_sign),
            confidence=0.9,
            rationale="Lagna is the primary personalization anchor.",
        ),
        AstroSignal(
            name="major_transits",
            value=f"Jupiter:{jupiter_sign}, Saturn:{saturn_sign}",
            confidence=0.82,
            rationale="Jupiter/Saturn transits are high-impact timing modifiers.",
        ),
    ]

    # ── Dasha date signals ──────────────────────────────────────────────────
    md_start = (dasha_data or {}).get("mahadasha", {}).get("start")
    md_end   = (dasha_data or {}).get("mahadasha", {}).get("end")
    ad_start = (dasha_data or {}).get("antardasha", {}).get("start")
    ad_end   = (dasha_data or {}).get("antardasha", {}).get("end")
    pd_start = (dasha_data or {}).get("pratyantardasha", {}).get("start")
    pd_end   = (dasha_data or {}).get("pratyantardasha", {}).get("end")

    if md_end and ad_end:
        signals.append(AstroSignal(
            name="dasha_dates",
            value=(
                f"MD {active_md}: {md_start} to {md_end} | "
                f"AD {active_ad}: {ad_start} to {ad_end}"
                + (f" | PD {active_pd}: {pd_start} to {pd_end}" if pd_end else "")
            ),
            confidence=0.95,
            rationale="Exact dasha start/end dates from Swiss Ephemeris calculation.",
        ))

    # ── Yoga signals ────────────────────────────────────────────────────────
    yogas = (chart_data or {}).get("yogas", [])
    if yogas:
        # Group by category, prioritise high-strength yogas
        mahapurusha = [y for y in yogas if y.get("category") == "mahapurusha"]
        raja        = [y for y in yogas if y.get("category") == "raja"]
        dhana       = [y for y in yogas if y.get("category") == "dhana"]
        spiritual   = [y for y in yogas if y.get("category") == "spiritual"]
        arishtya    = [y for y in yogas if y.get("category") == "arishtya"]

        # Mahapurusha yogas — most significant
        if mahapurusha:
            names = ", ".join(y["name"] for y in mahapurusha[:3])
            signals.append(AstroSignal(
                name="mahapurusha_yogas",
                value=names,
                confidence=0.92,
                rationale="Pancha Mahapurusha yogas amplify results in their Dasha period.",
            ))

        # Raja/Dhana for wealth and authority queries
        if raja or dhana:
            all_rd = raja + dhana
            names = ", ".join(
                f"{y['name']} (str={y.get('strength', 0):.1f})"
                for y in sorted(all_rd, key=lambda x: x.get("strength", 0), reverse=True)[:4]
            )
            signals.append(AstroSignal(
                name="raja_dhana_yogas",
                value=names,
                confidence=0.85,
                rationale="Raja/Dhana yogas indicate periods of authority, wealth, and achievement.",
            ))

        # Arishtya yogas — challenges to note
        if arishtya:
            names = ", ".join(y["name"] for y in arishtya[:2])
            signals.append(AstroSignal(
                name="arishtya_yogas",
                value=names,
                confidence=0.80,
                rationale="Arishtya yogas flag periods needing caution or remediation.",
            ))

    # ── Vimshopaka Bala for domain-relevant planet ──────────────────────────
    vimshopaka = (chart_data or {}).get("vimshopaka", {})
    if vimshopaka:
        DOMAIN_KEY_PLANETS = {
            "marriage":  ["VENUS", "JUPITER"],
            "divorce":   ["SATURN", "MARS"],
            "career":    ["SATURN", "SUN"],
            "finance":   ["VENUS", "JUPITER"],
            "children":  ["JUPITER", "MOON"],
            "health":    ["SATURN", "MARS"],
            "home":      ["MOON", "MARS"],
            "foreign":   ["RAHU", "JUPITER"],
            "general":   ["JUPITER", "SATURN"],
        }
        key_planets = DOMAIN_KEY_PLANETS.get(domain, DOMAIN_KEY_PLANETS["general"])
        vims_parts = [
            f"{p}={vimshopaka[p]:.1f}/20"
            for p in key_planets
            if p in vimshopaka
        ]
        if vims_parts:
            signals.append(AstroSignal(
                name="vimshopaka_strength",
                value=", ".join(vims_parts),
                confidence=0.83,
                rationale=(
                    "Vimshopaka Bala (0–20) measures planetary strength across multiple divisional charts. "
                    "Score ≥14 = strong, 8–13 = moderate, <8 = weak."
                ),
            ))

    # ── Planetary wars (Graha Yuddha) ───────────────────────────────────────
    wars = (chart_data or {}).get("planetary_wars", [])
    if wars:
        war_parts = [
            f"{w['winner']} defeats {w['loser']} ({w['separation_degrees']}°)"
            for w in wars
        ]
        signals.append(AstroSignal(
            name="planetary_wars",
            value="; ".join(war_parts),
            confidence=0.78,
            rationale=(
                "Graha Yuddha: loser planet's significations are significantly weakened "
                "in its Dasha/Antardasha period."
            ),
        ))

    windows = build_timeline_windows(
        query_domain=domain,
        dasha_data=dasha_data or {},
        chart_data=chart_data or {},
    )

    return {
        "domain": domain,
        "signals": [s.__dict__ for s in signals],
        "timeline_windows": windows,
        "confidence_band": "medium" if windows else "low",
    }


def format_evidence_for_prompt(evidence: Dict[str, Any]) -> str:
    if not evidence:
        return ""
    lines = [
        "ASTRO INTELLIGENCE LAYER (deterministic evidence):",
        f"- Domain: {evidence.get('domain', 'general')}",
        f"- Confidence band: {evidence.get('confidence_band', 'low')}",
        "- Signals:",
    ]
    for s in evidence.get("signals", [])[:5]:
        lines.append(
            f"  • {s.get('name')}: {s.get('value')} "
            f"(conf {s.get('confidence')}, reason: {s.get('rationale')})"
        )
    if evidence.get("timeline_windows"):
        lines.append("- Candidate timing windows:")
        for w in evidence["timeline_windows"][:4]:
            lines.append(
                f"  • {w.get('label')} {w.get('start_month')} -> {w.get('end_month')} "
                f"(confidence={w.get('confidence')})"
            )
    lines.append(
        "- Use this evidence as the primary reasoning substrate. "
        "Narrate naturally; do not copy bullets verbatim."
    )
    return "\n".join(lines)
