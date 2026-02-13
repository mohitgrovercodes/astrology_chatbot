# src\utils\formatters.py
"""
Output Formatters for LLM Consumption
======================================

Formats chart data into natural language summaries and
LLM-optimized structures.
"""

from typing import Dict, Any, List


def format_for_llm(chart_data: Dict[str, Any], query: str = "") -> str:
    """
    Format chart data as natural language for LLM consumption.
    
    Args:
        chart_data: Serialized chart from serializers
        query: Optional user query for context
        
    Returns:
        Formatted string suitable for LLM prompting
    """
    
    chart_type = chart_data.get("chart_type", "unknown")
    
    if chart_type == "vedic":
        return _format_vedic_for_llm(chart_data, query)
    elif chart_type == "western":
        return _format_western_for_llm(chart_data, query)
    else:
        return "Unknown chart type"


def _format_vedic_for_llm(chart_data: Dict[str, Any], query: str) -> str:
    """Format Vedic chart for LLM."""
    
    lagna = chart_data.get("lagna", {})
    planets = chart_data.get("planets", {})
    yogas = chart_data.get("yogas", [])
    dasha = chart_data.get("dasha", {})
    
    sections = [
        "# Vedic Birth Chart Analysis\n"
    ]
    
    # Birth data
    birth_data = chart_data.get("birth_data", {})
    sections.append(f"Birth Time: {birth_data.get('datetime', 'Unknown')}")
    sections.append(f"Location: Lat {birth_data.get('location', {}).get('latitude')}, "
                   f"Lon {birth_data.get('location', {}).get('longitude')}\n")
    
    # Lagna
    sections.append(f"## Ascendant (Lagna)")
    sections.append(f"- Sign: {lagna.get('sign')} ({lagna.get('sign_sanskrit')})")
    sections.append(f"- Degree: {lagna.get('degree')}°{lagna.get('minute')}'")
    sections.append(f"- Nakshatra: {lagna.get('nakshatra')} "
                   f"(Pada {lagna.get('nakshatra_pada')})\n")
    
    # Planets
    sections.append("## Planetary Positions\n")
    for planet_name, planet_data in planets.items():
        retro_str = " (R)" if planet_data.get("retrograde") else ""
        combust_str = " [Combust]" if planet_data.get("combust") else ""
        
        sections.append(
            f"**{planet_name}**: {planet_data.get('sign')} "
            f"{planet_data.get('degree')}°{planet_data.get('minute')}', "
            f"House {planet_data.get('house')}, "
            f"{planet_data.get('nakshatra')} Pada {planet_data.get('nakshatra_pada')}"
            f"{retro_str}{combust_str}"
        )
        
        dignity = planet_data.get('dignity', {})
        if dignity.get('is_exalted'):
            sections.append(f"  -> Exalted (very strong)")
        elif dignity.get('is_debilitated'):
            sections.append(f"  -> Debilitated (weak)")
        elif dignity.get('is_own_sign'):
            sections.append(f"  -> In own sign (strong)")
    
    sections.append("")
    
    # Yogas
    if yogas:
        sections.append("## Present Yogas\n")
        for yoga in yogas[:10]:  # Limit to top 10
            forming_planets = ", ".join(yoga.get('forming_planets', []))
            sections.append(
                f"**{yoga.get('name')}** ({yoga.get('category')}): "
                f"Strength {yoga.get('strength'):.1f}/1.0"
            )
            sections.append(f"  Planets: {forming_planets}\n")
    
    # Dasha
    if dasha.get('mahadasha'):
        md = dasha['mahadasha']
        sections.append(f"## Current Dasha Period\n")
        sections.append(f"**Mahadasha**: {md.get('lord')}")
        sections.append(f"  Period: {md.get('start')} to {md.get('end')}")
        
        if dasha.get('antardasha'):
            ad = dasha['antardasha']
            sections.append(f"**Antardasha**: {ad.get('lord')}")
            sections.append(f"  Period: {ad.get('start')} to {ad.get('end')}\n")
    
    # User query context
    if query:
        sections.append(f"## User Query\n{query}\n")
    
    return "\n".join(sections)


def _format_western_for_llm(chart_data: Dict[str, Any], query: str) -> str:
    """Format Western chart for LLM."""
    
    key_points = chart_data.get("key_points", {})
    planets = chart_data.get("planets", {})
    aspects = chart_data.get("aspects", [])
    
    sections = [
        "# Western Natal Chart Analysis\n"
    ]
    
    # Birth data
    birth_data = chart_data.get("birth_data", {})
    sections.append(f"Birth Time: {birth_data.get('datetime', 'Unknown')}")
    sections.append(f"Location: {birth_data.get('location', {})}\n")
    
    # Sun, Moon, Ascendant
    sections.append("## Key Points\n")
    sections.append(f"**Sun Sign**: {key_points.get('sun_sign')}")
    sections.append(f"**Moon Sign**: {key_points.get('moon_sign')}")
    asc = key_points.get('ascendant', {})
    sections.append(f"**Ascendant**: {asc.get('sign')} {asc.get('degree')}°")
    mc = key_points.get('midheaven', {})
    sections.append(f"**Midheaven**: {mc.get('sign')} {mc.get('degree')}°\n")
    
    # Planets
    sections.append("## Planetary Positions\n")
    for planet_name, planet_data in planets.items():
        retro = " (R)" if planet_data.get("retrograde") else ""
        sections.append(
            f"**{planet_name}**: {planet_data.get('sign')} "
            f"{planet_data.get('degree_in_sign')}°, "
            f"House {planet_data.get('house')}{retro}"
        )
    
    sections.append("")
    
    # Major aspects
    if aspects:
        sections.append("## Major Aspects\n")
        for aspect in aspects[:15]:  # Top 15
            sections.append(
                f"{aspect.get('planet1')} {aspect.get('aspect_type')} "
                f"{aspect.get('planet2')} (orb: {aspect.get('orb')}°)"
            )
    
    if query:
        sections.append(f"\n## User Query\n{query}\n")
    
    return "\n".join(sections)


def format_chart_summary(chart_data: Dict[str, Any]) -> str:
    """
    Create a concise summary of chart highlights.
    
    Args:
        chart_data: Serialized chart
        
    Returns:
        Brief summary string
    """
    
    chart_type = chart_data.get("chart_type", "unknown")
    
    if chart_type == "vedic":
        lagna = chart_data.get("lagna", {})
        yogas = chart_data.get("yogas", [])
        present_yogas = [y for y in yogas if y.get('is_present')]
        
        return (
            f"Vedic Chart: {lagna.get('sign')} Lagna, "
            f"{lagna.get('nakshatra')} Nakshatra, "
            f"{len(present_yogas)} significant yogas present"
        )
    
    elif chart_type == "western":
        key = chart_data.get("key_points", {})
        aspects = chart_data.get("aspects", [])
        
        return (
            f"Western Chart: Sun in {key.get('sun_sign')}, "
            f"Moon in {key.get('moon_sign')}, "
            f"{key.get('ascendant', {}).get('sign')} Rising, "
            f"{len(aspects)} major aspects"
        )
    
    return "Chart calculated successfully"
