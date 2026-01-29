"""
LangChain Tools for Astrology Calculation Engines.

Wraps Vedic and Western engines as tools for LangGraph orchestration.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
import json

# Import your calculation engines
from src.engines.vedic.vedic_engine import VedicEngine, generate_vedic_chart
from src.engines.western.western_engine import WesternAstroEngine
from src.engines.core.celestial_bodies import CelestialBody


# =============================================================================
# VEDIC TOOLS
# =============================================================================

@tool
def calculate_vedic_birth_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None
) -> dict:
    """
    Calculate a complete Vedic (Jyotish) birth chart.
    
    Args:
        birth_date: Birth date in format 'YYYY-MM-DD' (e.g., '1990-03-15')
        birth_time: Birth time in format 'HH:MM:SS' (e.g., '14:30:00')
        latitude: Birth place latitude (e.g., 28.6139 for Delhi)
        longitude: Birth place longitude (e.g., 77.2090 for Delhi)
        timezone: Timezone string (e.g., 'Asia/Kolkata'), auto-detected if None
        
    Returns:
        Dictionary with complete Vedic chart data including:
        - Lagna (Ascendant)
        - Rashi (Moon Sign)
        - All planetary positions in rashis and nakshatras
        - House placements (bhavas)
        - Current Vimshottari Dasha periods
        - Yogas present in the chart
        
    Example:
        >>> result = calculate_vedic_birth_chart(
        ...     birth_date="1990-03-15",
        ...     birth_time="14:30:00",
        ...     latitude=26.9124,
        ...     longitude=75.7873
        ... )
        >>> print(result['lagna'])  # Ascendant sign
        >>> print(result['rashi'])  # Moon sign
    """
    try:
        # Parse datetime
        dt_str = f"{birth_date} {birth_time}"
        birth_datetime = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        # Generate chart
        chart = generate_vedic_chart(
            birth_date=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone
        )
        
        # Extract key data for LLM consumption
        result = {
            "chart_type": "vedic",
            "birth_date": birth_date,
            "birth_time": birth_time,
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            
            # Primary chart points
            "lagna": {
                "rashi": chart.lagna.rashi.name.title(),
                "degree": chart.lagna.longitude,
                "nakshatra": chart.lagna.nakshatra.name.title() if hasattr(chart.lagna, 'nakshatra') else None
            },
            
            "rashi": chart.rashi.name.title(),  # Moon sign
            "sun_sign": chart.sun_sign.name.title(),
            "moon_nakshatra": chart.moon_nakshatra.name.title(),
            
            # Planetary positions
            "planets": {},
            
            # Dasha periods
            "current_dasha": chart.get_current_dasha(),
            
            # Yogas (condensed)
            "yogas": [
                {
                    "name": yoga.name,
                    "category": yoga.category.name if hasattr(yoga, 'category') else None,
                    "strength": yoga.strength if hasattr(yoga, 'strength') else None
                }
                for yoga in chart.get_present_yogas()[:10]  # Top 10 yogas
            ]
        }
        
        # Add planetary details
        from src.engines.core.celestial_bodies import VEDIC_GRAHAS
        for planet in VEDIC_GRAHAS:
            try:
                result["planets"][planet.name.lower()] = {
                    "rashi": chart.get_planet_rashi(planet).name.title(),
                    "nakshatra": chart.get_planet_nakshatra(planet).name.title(),
                    "house": chart.get_planet_house(planet),
                    "degree": chart.positions[planet].longitude,
                    "retrograde": chart.is_planet_retrograde(planet),
                    "combust": chart.is_planet_combust(planet)
                }
            except Exception:
                pass
        
        return result
        
    except Exception as e:
        return {
            "error": True,
            "message": f"Failed to calculate Vedic chart: {str(e)}",
            "details": "Please check birth data format and try again."
        }


@tool
def calculate_vedic_transits(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    transit_date: Optional[str] = None
) -> dict:
    """
    Calculate current or future planetary transits for a Vedic chart.
    
    Args:
        birth_date: Birth date in format 'YYYY-MM-DD'
        birth_time: Birth time in format 'HH:MM:SS'
        latitude: Birth place latitude
        longitude: Birth place longitude
        transit_date: Date for transits in 'YYYY-MM-DD' (default: today)
        
    Returns:
        Dictionary with transit positions relative to natal chart
    """
    try:
        # Parse birth datetime
        dt_str = f"{birth_date} {birth_time}"
        birth_datetime = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        # Generate natal chart
        engine = VedicEngine()
        chart = engine.generate_chart(
            birth_date=birth_datetime,
            latitude=latitude,
            longitude=longitude
        )
        
        # Parse transit date
        if transit_date:
            transit_dt = datetime.strptime(transit_date, "%Y-%m-%d")
        else:
            transit_dt = datetime.now()
        
        # Compute transits
        transit_positions = engine.compute_transits(chart, transit_dt)
        transit_houses = engine.get_transit_to_natal_houses(chart, transit_dt)
        
        # Format results
        result = {
            "chart_type": "vedic_transits",
            "transit_date": transit_dt.strftime("%Y-%m-%d"),
            "transits": {}
        }
        
        from src.engines.core.celestial_bodies import VEDIC_GRAHAS
        for planet in VEDIC_GRAHAS:
            if planet in transit_positions:
                pos = transit_positions[planet]
                result["transits"][planet.name.lower()] = {
                    "degree": pos.longitude,
                    "natal_house": transit_houses.get(planet, None)
                }
        
        return result
        
    except Exception as e:
        return {
            "error": True,
            "message": f"Failed to calculate transits: {str(e)}"
        }


# =============================================================================
# WESTERN TOOLS
# =============================================================================

@tool
def calculate_western_birth_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None
) -> dict:
    """
    Calculate a complete Western astrology birth chart.
    
    Args:
        birth_date: Birth date in format 'YYYY-MM-DD'
        birth_time: Birth time in format 'HH:MM:SS'
        latitude: Birth place latitude
        longitude: Birth place longitude
        timezone: Timezone string (e.g., 'America/New_York')
        
    Returns:
        Dictionary with complete Western chart data including:
        - Sun, Moon, Ascendant signs
        - All planetary positions in signs and houses
        - Major aspects between planets
        - Essential dignities
        
    Example:
        >>> result = calculate_western_birth_chart(
        ...     birth_date="1990-03-15",
        ...     birth_time="14:30:00",
        ...     latitude=40.7128,
        ...     longitude=-74.0060,
        ...     timezone="America/New_York"
        ... )
        >>> print(result['sun_sign'])
        >>> print(result['ascendant'])
    """
    try:
        # Parse datetime
        dt_str = f"{birth_date} {birth_time}"
        birth_datetime = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        # Generate chart
        engine = WesternAstroEngine()
        chart = engine.generate_chart(
            birth_datetime=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone
        )
        
        # Extract key data
        result = {
            "chart_type": "western",
            "birth_date": birth_date,
            "birth_time": birth_time,
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            
            # Primary chart points
            "sun_sign": chart.sun_sign.name.title(),
            "moon_sign": chart.moon_sign.name.title(),
            "ascendant": chart.ascendant.name.title(),
            
            # Planetary positions
            "planets": {},
            
            # Major aspects (condensed)
            "aspects": [
                {
                    "planet1": aspect.body1.name.lower(),
                    "planet2": aspect.body2.name.lower(),
                    "aspect_type": aspect.aspect_type.name.lower(),
                    "orb": round(aspect.orb, 2)
                }
                for aspect in chart.aspects.aspects[:15]  # Top 15 aspects
            ]
        }
        
        # Add planetary details
        from src.engines.core.celestial_bodies import WESTERN_PLANETS
        for planet in WESTERN_PLANETS:
            try:
                result["planets"][planet.name.lower()] = {
                    "sign": chart.get_planet_sign(planet).name.title(),
                    "house": chart.get_planet_house(planet),
                    "degree": chart.positions[planet].longitude,
                    "retrograde": chart.positions[planet].speed < 0
                }
            except Exception:
                pass
        
        return result
        
    except Exception as e:
        return {
            "error": True,
            "message": f"Failed to calculate Western chart: {str(e)}",
            "details": "Please check birth data format and try again."
        }


# =============================================================================
# QUERY CLASSIFICATION TOOL
# =============================================================================

@tool
def classify_astrology_query(query: str) -> dict:
    """
    Classify user's astrology query to determine if it requires calculation.
    
    Args:
        query: User's question or request
        
    Returns:
        Dictionary with classification:
        - type: 'calculation', 'interpretation', 'chitchat', or 'blocked'
        - system: 'vedic', 'western', or 'both'
        - calculation_type: 'birth_chart', 'transits', 'dasha', etc.
        - requires_birth_data: boolean
        
    Example:
        >>> classify_astrology_query("Calculate my birth chart. Born March 15, 1990")
        {
            "type": "calculation",
            "system": "vedic",
            "calculation_type": "birth_chart",
            "requires_birth_data": True
        }
    """
    q_lower = query.lower()
    
    # Calculation indicators
    calculation_keywords = [
        "calculate", "compute", "generate", "my chart",
        "birth chart", "horoscope", "natal chart",
        "my dasha", "current dasha", "transit",
        "born on", "birthday", "date of birth"
    ]
    
    is_calculation = any(kw in q_lower for kw in calculation_keywords)
    
    # System detection
    system = "vedic"  # Default
    if any(w in q_lower for w in ["western", "tropical", "placidus"]):
        system = "western"
    elif any(w in q_lower for w in ["vedic", "jyotish", "sidereal", "rashi"]):
        system = "vedic"
    
    # Calculation type
    calc_type = None
    if is_calculation:
        if any(w in q_lower for w in ["transit", "current position"]):
            calc_type = "transits"
        elif any(w in q_lower for w in ["dasha", "period"]):
            calc_type = "dasha"
        else:
            calc_type = "birth_chart"
    
    # Blocked topics
    blocked_keywords = [
        "when will i die", "death date", "time of death",
        "cure cancer", "medical diagnosis", "disease treatment",
        "lottery numbers", "gambling", "stock market prediction"
    ]
    is_blocked = any(kw in q_lower for kw in blocked_keywords)
    
    return {
        "type": "blocked" if is_blocked else ("calculation" if is_calculation else "interpretation"),
        "system": system,
        "calculation_type": calc_type,
        "requires_birth_data": is_calculation,
        "confidence": "high" if (is_calculation or is_blocked) else "medium"
    }


# =============================================================================
# BIRTH DATA EXTRACTION TOOL
# =============================================================================

@tool
def extract_birth_data_from_query(query: str) -> dict:
    """
    Extract birth date, time, and location from user's query.
    
    Args:
        query: User's message that may contain birth data
        
    Returns:
        Dictionary with extracted data:
        - has_date: boolean
        - has_time: boolean
        - has_location: boolean
        - birth_date: 'YYYY-MM-DD' or None
        - birth_time: 'HH:MM:SS' or None
        - location_text: extracted location string or None
        - missing_fields: list of what's missing
        
    Example:
        >>> extract_birth_data_from_query("Born March 15, 1990 at 2:30 PM in Delhi")
        {
            "has_date": True,
            "has_time": True,
            "has_location": True,
            "birth_date": "1990-03-15",
            "birth_time": "14:30:00",
            "location_text": "Delhi"
        }
    """
    import re
    from dateutil import parser as date_parser
    
    result = {
        "has_date": False,
        "has_time": False,
        "has_location": False,
        "birth_date": None,
        "birth_time": None,
        "location_text": None,
        "missing_fields": []
    }
    
    # Date extraction (simple patterns)
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY or DD/MM/YYYY
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            try:
                parsed_date = date_parser.parse(match.group())
                result["birth_date"] = parsed_date.strftime("%Y-%m-%d")
                result["has_date"] = True
                break
            except:
                pass
    
    # Time extraction
    time_patterns = [
        r'\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?',
        r'at\s+(\d{1,2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            try:
                time_str = match.group().replace('at', '').strip()
                parsed_time = date_parser.parse(time_str)
                result["birth_time"] = parsed_time.strftime("%H:%M:%S")
                result["has_time"] = True
                break
            except:
                pass
    
    # Location extraction (simple - looks for "in <place>")
    location_pattern = r'(?:in|at|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    match = re.search(location_pattern, query)
    if match:
        result["location_text"] = match.group(1)
        result["has_location"] = True
    
    # Determine missing fields
    if not result["has_date"]:
        result["missing_fields"].append("birth_date")
    if not result["has_time"]:
        result["missing_fields"].append("birth_time")
    if not result["has_location"]:
        result["missing_fields"].append("location")
    
    return result


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# All available tools for LangGraph
ALL_ASTROLOGY_TOOLS = [
    calculate_vedic_birth_chart,
    calculate_vedic_transits,
    calculate_western_birth_chart,
    classify_astrology_query,
    extract_birth_data_from_query,
]


def get_calculation_tools() -> List:
    """Get list of calculation tools for LangGraph."""
    return [
        calculate_vedic_birth_chart,
        calculate_vedic_transits,
        calculate_western_birth_chart,
    ]


def get_classification_tools() -> List:
    """Get list of classification/utility tools."""
    return [
        classify_astrology_query,
        extract_birth_data_from_query,
    ]


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ASTROLOGY CALCULATION TOOLS - Test Suite")
    print("=" * 70)
    print()
    
    # Test 1: Vedic Birth Chart
    print("Test 1: Calculate Vedic Birth Chart")
    result = calculate_vedic_birth_chart.invoke({
        "birth_date": "1990-03-15",
        "birth_time": "14:30:00",
        "latitude": 26.9124,
        "longitude": 75.7873
    })
    
    if "error" not in result:
        print(f"  ✓ Lagna: {result['lagna']['rashi']}")
        print(f"  ✓ Rashi (Moon Sign): {result['rashi']}")
        print(f"  ✓ Moon Nakshatra: {result['moon_nakshatra']}")
        print(f"  ✓ Current Dasha: {list(result['current_dasha'].keys())}")
        print(f"  ✓ Yogas Present: {len(result['yogas'])}")
    else:
        print(f"  ✗ Error: {result['message']}")
    print()
    
    # Test 2: Query Classification
    print("Test 2: Classify Queries")
    test_queries = [
        "Calculate my birth chart",
        "What does Mars in 7th house mean?",
        "When will I die?",
        "Hello, how are you?"
    ]
    
    for query in test_queries:
        classification = classify_astrology_query.invoke({"query": query})
        print(f"  Query: '{query}'")
        print(f"  → Type: {classification['type']}, System: {classification['system']}")
    print()
    
    # Test 3: Birth Data Extraction
    print("Test 3: Extract Birth Data")
    test_text = "I was born on March 15, 1990 at 2:30 PM in Delhi, India"
    extracted = extract_birth_data_from_query.invoke({"query": test_text})
    print(f"  Text: '{test_text}'")
    print(f"  → Date: {extracted.get('birth_date', 'Not found')}")
    print(f"  → Time: {extracted.get('birth_time', 'Not found')}")
    print(f"  → Location: {extracted.get('location_text', 'Not found')}")
    print(f"  → Missing: {extracted.get('missing_fields', [])}")
    print()
    
    print("=" * 70)
    print("✅ Tool tests complete!")
    print("=" * 70)