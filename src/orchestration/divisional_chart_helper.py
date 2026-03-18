# src/orchestration/divisional_chart_helper.py
"""
Helper functions for adding divisional chart context to predictions.
Maps query types to relevant divisional charts according to classical texts.
"""

from typing import Dict, List, Optional

# Classical divisional chart meanings
CHART_MEANINGS = {
    'D1': 'Rasi - Main birth chart',
    'D2': 'Hora - Wealth and finances',
    'D3': 'Drekkana - Siblings and courage',
    'D4': 'Chaturthamsa - Property and assets',
    'D6': 'Shashtamsa - Health and diseases',
    'D7': 'Saptamsa - Children and progeny',
    'D9': 'Navamsa - Spouse, marriage, and dharma',
    'D10': 'Dasamsa - Career and profession',
    'D11': 'Rudramsa - Gains and income',
    'D12': 'Dwadasamsa - Parents',
    'D16': 'Shodasamsa - Vehicles and luxuries',
    'D20': 'Vimsamsa - Spirituality and worship',
    'D24': 'Chaturvimsamsa - Education and learning',
    'D27': 'Saptavimsamsa - Strengths and weaknesses',
    'D30': 'Trimsamsa - Evils and misfortunes',
    'D40': 'Khavedamsa - Auspicious and inauspicious effects',
    'D45': 'Akshavedamsa - Character and conduct',
    'D60': 'Shashtyamsa - Past life and karma',
}

# Query type to divisional chart mapping (primary and secondary)
DIVISIONAL_CHART_MAP = {
    'marriage': {
        'primary': ['D9'],
        'secondary': ['D7'],
        'key_planets': ['Venus', 'Mars', 'Jupiter'],
        'analysis_focus': 'spouse nature, marriage timing, marital happiness'
    },
    'career': {
        'primary': ['D10'],
        'secondary': ['D24'],
        'key_planets': ['Saturn', 'Sun', 'Mercury', 'Jupiter'],
        'analysis_focus': 'profession, status, authority, career success'
    },
    'children': {
        'primary': ['D7'],
        'secondary': ['D9'],
        'key_planets': ['Jupiter', 'Sun', 'Moon'],
        'analysis_focus': 'progeny, children personality, child-related matters'
    },
    'finance': {
        'primary': ['D2'],
        'secondary': ['D11'],
        'key_planets': ['Jupiter', 'Mercury', 'Venus', 'Moon'],
        'analysis_focus': 'wealth accumulation, financial gains, prosperity'
    },
    'health': {
        'primary': ['D6'],
        'secondary': ['D12'],
        'key_planets': ['Sun', 'Moon', 'Mars', 'Saturn'],
        'analysis_focus': 'diseases, ailments, health issues, recovery'
    },
    'education': {
        'primary': ['D24'],
        'secondary': ['D9', 'D10'],
        'key_planets': ['Mercury', 'Jupiter', 'Sun'],
        'analysis_focus': 'learning, degrees, academic success, knowledge'
    },
    'property': {
        'primary': ['D4'],
        'secondary': ['D16'],
        'key_planets': ['Mars', 'Saturn', 'Moon', 'Venus'],
        'analysis_focus': 'real estate, house, land, vehicles, fixed assets'
    },
    'spirituality': {
        'primary': ['D9', 'D20'],
        'secondary': ['D45'],
        'key_planets': ['Jupiter', 'Ketu', 'Moon'],
        'analysis_focus': 'spiritual inclination, dharma, religious practices'
    },
    'parents': {
        'primary': ['D12'],
        'secondary': ['D4'],
        'key_planets': ['Sun', 'Moon', 'Jupiter'],
        'analysis_focus': 'father (D12), mother (D4), parental relationships'
    },
    'siblings': {
        'primary': ['D3'],
        'secondary': [],
        'key_planets': ['Mars', 'Mercury'],
        'analysis_focus': 'brothers, sisters, courage, communication'
    },
    # Foreign travel / settlement — D9 (long journeys, dharma, distant lands) + D12 (foreign residence, losses, moksha)
    'foreign': {
        'primary': ['D9', 'D12'],
        'secondary': ['D3'],
        'key_planets': ['Rahu', 'Venus', 'Moon', 'Jupiter'],
        'analysis_focus': 'foreign travel, settlement abroad, long journeys, immigration, residence in distant lands'
    },
    'foreign_travel': {
        'primary': ['D9', 'D12'],
        'secondary': ['D3'],
        'key_planets': ['Rahu', 'Venus', 'Moon', 'Jupiter'],
        'analysis_focus': 'foreign travel, settlement abroad, long journeys, immigration, residence in distant lands'
    },
}


def get_divisional_chart_context(
    query_type: str,
    chart_data: Dict,
    include_secondary: bool = True,
    verbose: bool = True,
    original_query: str = ""  # NEW: to detect specific keywords
) -> str:
    """
    Generate divisional chart context for LLM prompt based on query type.
    
    Args:
        query_type: Type of query (marriage, career, children, etc.)
        chart_data: Chart data dictionary with divisional_charts_simple
        include_secondary: Whether to include secondary divisional charts
        verbose: Whether to include detailed explanations
        original_query: The actual user query (for smart detection)
        
    Returns:
        Formatted string with divisional chart information
    """
    # SMART DETECTION: Check if finance query is actually about property/house
    if query_type == 'finance' and original_query:
        property_keywords = ['house', 'property', 'home', 'real estate', 'land', 
                           'vehicle', 'car', 'apartment', 'flat', 'asset']
        query_lower = original_query.lower()
        if any(keyword in query_lower for keyword in property_keywords):
            print(f"[DIVISIONAL] Smart detection: finance->property based on keywords")
            query_type = 'property'
    
    if query_type not in DIVISIONAL_CHART_MAP:
        return ""
    
    mapping = DIVISIONAL_CHART_MAP[query_type]
    # Use 'vargas' which has {"D9": {"planets": {...}}} — the nested format this function expects.
    # 'divisional_charts_simple' is a flattened {"D9": {planet: sign}} and lacks the 'planets' key.
    divisional_simple = chart_data.get('vargas') or chart_data.get('divisional_charts_simple', {})
    
    if not divisional_simple:
        return ""
    
    context = "\n\nDIVISIONAL CHART ANALYSIS:\n"
    
    # Primary divisional charts
    charts_to_include = mapping['primary']
    if include_secondary:
        charts_to_include += mapping['secondary']
    
    for chart_name in charts_to_include:
        if chart_name not in divisional_simple:
            continue
            
        chart_info = divisional_simple[chart_name]
        if not chart_info.get('planets'):
            continue
        
        context += f"\n[{chart_name}] {CHART_MEANINGS.get(chart_name, 'Unknown')}\n"
        
        if verbose:
            context += f"Focus: {mapping['analysis_focus']}\n"
            context += f"Key Planets: {', '.join(mapping['key_planets'])}\n\n"
        
        context += f"Lagna: {chart_info.get('lagna', 'Unknown')}\n"
        context += "\nPlanetary Positions:\n"

        # Classical dignity lookup for quick strength assessment in varga
        _EXALT = {
            'Sun': 'Mesha', 'Moon': 'Vrishabha', 'Mars': 'Makara', 'Mercury': 'Kanya',
            'Jupiter': 'Karka', 'Venus': 'Meena', 'Saturn': 'Tula',
        }
        _OWN = {
            'Sun': ['Simha'], 'Moon': ['Karka'], 'Mars': ['Mesha', 'Vrischika'],
            'Mercury': ['Mithuna', 'Kanya'], 'Jupiter': ['Dhanu', 'Meena'],
            'Venus': ['Vrishabha', 'Tula'], 'Saturn': ['Makara', 'Kumbha'],
        }
        _DEBIL = {
            'Sun': 'Tula', 'Moon': 'Vrischika', 'Mars': 'Karka', 'Mercury': 'Meena',
            'Jupiter': 'Makara', 'Venus': 'Kanya', 'Saturn': 'Mesha',
        }

        def _varga_dignity(planet: str, rashi: str) -> str:
            r = rashi.strip().title()
            if _EXALT.get(planet, '') == r:
                return 'exalted'
            if r in _OWN.get(planet, []):
                return 'own sign'
            if _DEBIL.get(planet, '') == r:
                return 'debilitated'
            return ''

        # Show key planets first
        key_planets = mapping['key_planets']
        other_planets = []

        for planet, rashi in chart_info.get('planets', {}).items():
            dignity_note = _varga_dignity(planet, rashi)
            dignity_str = f" [{dignity_note}]" if dignity_note else ""
            if planet in key_planets:
                context += f"  • {planet:10} -> {rashi:15}{dignity_str}  * (Key for {query_type})\n"
            else:
                other_planets.append((planet, rashi, dignity_str))

        # Show other planets
        if verbose and other_planets:
            context += "\nOther Planets:\n"
            for planet, rashi, dignity_str in other_planets:
                context += f"  • {planet:10} -> {rashi}{dignity_str}\n"

        context += "\n"
    
    if verbose:
        primary_chart = charts_to_include[0]
        primary_name = CHART_MEANINGS.get(primary_chart, primary_chart)
        context += (
            f"Analysis guidance: Use {primary_chart} ({primary_name}) as the primary reference for {query_type} analysis.\n"
            f"When citing this chart in your response, use its classical name ({primary_name.split(' - ')[0].strip()}) "
            f"rather than the code '{primary_chart}'. "
            f"For example: 'In the Navamsa chart...' rather than 'In D9...'\n"
        )

    return context


def get_all_divisional_charts_summary(chart_data: Dict) -> str:
    """
    Generate a comprehensive summary of all available divisional charts.
    
    Args:
        chart_data: Chart data dictionary with divisional_charts_simple
        
    Returns:
        Formatted string with all divisional charts
    """
    divisional_simple = chart_data.get('divisional_charts_simple', {})
    
    if not divisional_simple:
        return "\n[No divisional charts available]\n"
    
    context = "\n\nDIVISIONAL CHARTS AVAILABLE:\n"
    
    available_charts = sorted(divisional_simple.keys())
    
    for chart_name in available_charts:
        chart_info = divisional_simple[chart_name]
        if chart_info.get('planets'):
            planet_count = len(chart_info['planets'])
            context += f"  ✓ {chart_name:6} - {CHART_MEANINGS.get(chart_name, 'Unknown'):40} ({planet_count} planets)\n"
    
    return context


# Example usage in orchestrator:
"""
from src.orchestration.divisional_chart_helper import get_divisional_chart_context

# In _build_prediction_prompt or similar:
divisional_context = get_divisional_chart_context(
    query_type=validation_result.query_type,
    chart_data=chart_data,
    include_secondary=True,
    verbose=True,
    original_query=query  # Pass the original query for smart detection
)

prompt += divisional_context
"""