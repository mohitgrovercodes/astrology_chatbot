# src\tools\calculation_tools.py
"""
Calculation Tools for NakshatraAI Orchestrator.

LangChain Tool wrappers for Vedic astrology calculation engines.
These tools connect the LangGraph orchestrator with the VedicEngine.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from langchain_core.tools import tool

# Import your existing engines
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.engines.vedic.vedic_engine import VedicEngine
from src.engines.core.celestial_bodies import CelestialBody
from src.engines.vedic.vedic_constants import (
    Ayanamsa,
    RASHI_SANSKRIT_NAMES,
    NAKSHATRA_NAMES
)


# =============================================================================
# TOOL 1: BIRTH CHART CALCULATOR
# =============================================================================

@tool
def calculate_vedic_birth_chart(
    date_of_birth: str,
    time_of_birth: str,
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """
    Calculate complete Vedic birth chart.
    
    Args:
        date_of_birth: Date in "YYYY-MM-DD" format (e.g., "1990-03-15")
        time_of_birth: Time in "HH:MM:SS" format (e.g., "14:30:00")
        latitude: Latitude in decimal degrees (e.g., 26.9124 for Jaipur)
        longitude: Longitude in decimal degrees (e.g., 75.7873 for Jaipur)
        timezone: Timezone string (e.g., "Asia/Kolkata")
    
    Returns:
        Dictionary with chart data including lagna, moon sign, planetary positions
    """
    try:
        # Parse date and time
        date_str = f"{date_of_birth} {time_of_birth}"
        birth_datetime = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        
        # Initialize engine and generate chart
        engine = VedicEngine(ayanamsa=Ayanamsa.LAHIRI)
        chart = engine.generate_chart(
            birth_date=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone
        )
        
        # Extract key information
        result = {
            "lagna": chart.lagna.rashi_name,  # Ascendant sign
            "lagna_degree": f"{chart.lagna.rashi_name} {chart.lagna.degree}°{chart.lagna.minute}'",
            "moon_sign": chart.rashi_name,  # Moon sign (Rashi) - property
            "sun_sign": RASHI_SANSKRIT_NAMES[chart.sun_sign.value],  # Convert Rashi enum to name
            "moon_nakshatra": NAKSHATRA_NAMES[chart.moon_nakshatra.value],  # Convert Nakshatra enum to name
            
            # All planetary positions
            "planets": {
                "Sun": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.SUN).value],
                    "nakshatra": NAKSHATRA_NAMES[chart.get_planet_nakshatra(CelestialBody.SUN).value],
                    "house": chart.get_planet_house(CelestialBody.SUN)
                },
                "Moon": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MOON).value],
                    "nakshatra": NAKSHATRA_NAMES[chart.get_planet_nakshatra(CelestialBody.MOON).value],
                    "house": chart.get_planet_house(CelestialBody.MOON)
                },
                "Mars": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MARS).value],
                    "house": chart.get_planet_house(CelestialBody.MARS)
                },
                "Mercury": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MERCURY).value],
                    "house": chart.get_planet_house(CelestialBody.MERCURY)
                },
                "Jupiter": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.JUPITER).value],
                    "house": chart.get_planet_house(CelestialBody.JUPITER)
                },
                "Venus": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.VENUS).value],
                    "house": chart.get_planet_house(CelestialBody.VENUS)
                },
                "Saturn": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.SATURN).value],
                    "house": chart.get_planet_house(CelestialBody.SATURN)
                },
                "Rahu": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.RAHU).value],
                    "house": chart.get_planet_house(CelestialBody.RAHU)
                },
                "Ketu": {
                    "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.KETU).value],
                    "house": chart.get_planet_house(CelestialBody.KETU)
                }
            },
            
            # House information (cusps are longitudes in degrees)
            "houses": {
                f"House_{i}": chart.house_cusps.cusps[i-1] if i <= len(chart.house_cusps.cusps) else 0.0
                for i in range(1, 13)
            },
            
            # Birth details
            "birth_info": {
                "date": date_of_birth,
                "time": time_of_birth,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "ayanamsa": "Lahiri"
            }
        }
        
        return result
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "lagna": "Error",
            "moon_sign": "Error",
            "sun_sign": "Error"
        }

def format_chart_for_llm(chart: VedicEngine) -> Dict[str, Any]:
    """Helper to format a VedicChart object into the dictionary the LLM expects."""
    from src.engines.vedic.vedic_constants import RASHI_SANSKRIT_NAMES, NAKSHATRA_NAMES
    
    return {
        "lagna": chart.lagna.rashi_name,
        "lagna_degree": f"{chart.lagna.rashi_name} {chart.lagna.degree}°{chart.lagna.minute}'",
        "moon_sign": chart.rashi_name,
        "sun_sign": RASHI_SANSKRIT_NAMES[chart.sun_sign.value],
        "moon_nakshatra": NAKSHATRA_NAMES[chart.moon_nakshatra.value],
        "planets": {
            "Sun": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.SUN).value],
                "nakshatra": NAKSHATRA_NAMES[chart.get_planet_nakshatra(CelestialBody.SUN).value],
                "house": chart.get_planet_house(CelestialBody.SUN)
            },
            "Moon": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MOON).value],
                "nakshatra": NAKSHATRA_NAMES[chart.get_planet_nakshatra(CelestialBody.MOON).value],
                "house": chart.get_planet_house(CelestialBody.MOON)
            },
            "Mars": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MARS).value],
                "house": chart.get_planet_house(CelestialBody.MARS)
            },
            "Mercury": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.MERCURY).value],
                "house": chart.get_planet_house(CelestialBody.MERCURY)
            },
            "Jupiter": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.JUPITER).value],
                "house": chart.get_planet_house(CelestialBody.JUPITER)
            },
            "Venus": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.VENUS).value],
                "house": chart.get_planet_house(CelestialBody.VENUS)
            },
            "Saturn": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.SATURN).value],
                "house": chart.get_planet_house(CelestialBody.SATURN)
            },
            "Rahu": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.RAHU).value],
                "house": chart.get_planet_house(CelestialBody.RAHU)
            },
            "Ketu": {
                "rashi": RASHI_SANSKRIT_NAMES[chart.get_planet_rashi(CelestialBody.KETU).value],
                "house": chart.get_planet_house(CelestialBody.KETU)
            }
        },
        "houses": {
            f"House_{i}": chart.house_cusps.cusps[i-1] if i <= len(chart.house_cusps.cusps) else 0.0
            for i in range(1, 13)
        },
        "birth_info": {
            "date": chart.birth_data.date.strftime("%Y-%m-%d"),
            "time": chart.birth_data.date.strftime("%H:%M:%S"),
            "latitude": chart.birth_data.latitude,
            "longitude": chart.birth_data.longitude,
            "timezone": chart.birth_data.timezone_str,
            "ayanamsa": "Lahiri"
        }
    }


# =============================================================================
# TOOL 2: DASHA CALCULATOR
# =============================================================================

@tool
def calculate_current_dasha(
    date_of_birth: str,
    time_of_birth: str,
    latitude: float,
    longitude: float,
    current_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate current Vimshottari dasha periods.
    
    Args:
        date_of_birth: Date in "YYYY-MM-DD" format
        time_of_birth: Time in "HH:MM:SS" format
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        current_date: Optional date for dasha calculation (defaults to today)
    
    Returns:
        Dictionary with current mahadasha, antardasha, and pratyantardasha
    """
    try:
        # Parse birth date and time
        date_str = f"{date_of_birth} {time_of_birth}"
        birth_datetime = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        
        # Parse current date (or use today)
        if current_date:
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        else:
            current_dt = datetime.now()
        
        # Generate chart with dasha
        engine = VedicEngine()
        chart = engine.generate_chart(
            birth_date=birth_datetime,
            latitude=latitude,
            longitude=longitude
        )
        
        # Get current dasha periods using get_current_dasha which returns a dict
        current_periods = chart.get_current_dasha(current_dt)
        
        current_maha = current_periods.get("mahadasha")
        current_antar = current_periods.get("antardasha")
        current_pratyantar = current_periods.get("pratyantardasha")
        
        
        # Get Moon details for Dasha calculation transparency
        try:
            moon_longitude = chart.positions[CelestialBody.MOON].longitude
            moon_nakshatra_name = NAKSHATRA_NAMES[chart.moon_nakshatra.value]
            
            # Get Dasha balance info - may not always be available
            try:
                dasha_balance = chart.dasha.dasha_balance
                first_dasha_lord = dasha_balance.first_lord.name
                balance_years = f"{dasha_balance.remaining_years:.2f}"
            except (AttributeError, KeyError):
                # If dasha_balance not available, use current Mahadasha lord
                first_dasha_lord = current_maha.lord.name if current_maha else "Unknown"
                balance_years = "N/A"
            
            calculation_details = {
                "moon_longitude": f"{moon_longitude:.2f}°",
                "moon_nakshatra": moon_nakshatra_name,
                "first_dasha_lord": first_dasha_lord,
                "balance_at_birth_years": balance_years
            }
        except Exception as e:
            print(f"[WARNING] Could not extract calculation details: {e}")
            calculation_details = {
                "moon_longitude": "Not available",
                "moon_nakshatra": "Not available",
                "first_dasha_lord": "Not available",
                "balance_at_birth_years": "Not available"
            }
        
        result = {
            "mahadasha": {
                "planet": current_maha.lord.name if current_maha else "Unknown",
                "start_date": current_maha.start_date.strftime("%Y-%m-%d") if current_maha else "Unknown",
                "end_date": current_maha.end_date.strftime("%Y-%m-%d") if current_maha else "Unknown",
                "remaining_years": (current_maha.end_date - current_dt).days / 365.25 if current_maha else 0
            },
            "antardasha": {
                "planet": current_antar.lord.name if current_antar else "Unknown",
                "start_date": current_antar.start_date.strftime("%Y-%m-%d") if current_antar else "Unknown",
                "end_date": current_antar.end_date.strftime("%Y-%m-%d") if current_antar else "Unknown",
                "remaining_months": (current_antar.end_date - current_dt).days / 30.44 if current_antar else 0
            },
            "pratyantardasha": {
                "planet": current_pratyantar.lord.name if current_pratyantar else "Unknown",
                "start_date": current_pratyantar.start_date.strftime("%Y-%m-%d") if current_pratyantar else "Unknown",
                "end_date": current_pratyantar.end_date.strftime("%Y-%m-%d") if current_pratyantar else "Unknown"
            },
            "dasha_sequence": f"{current_maha.lord.name if current_maha else 'Unknown'}/{current_antar.lord.name if current_antar else 'Unknown'}/{current_pratyantar.lord.name if current_pratyantar else 'Unknown'}",
            # Calculation transparency fields
            "calculation_details": calculation_details
        }
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "mahadasha": {"planet": "Error"},
            "antardasha": {"planet": "Error"},
            "dasha_sequence": "Error"
        }


# =============================================================================
# TOOL 3: TRANSIT CALCULATOR
# =============================================================================

@tool
def calculate_current_transits(
    current_date: Optional[str] = None,
    latitude: float = 26.9124,  # Default: Jaipur
    longitude: float = 75.7873
) -> Dict[str, Any]:
    """
    Calculate current planetary transits.
    
    Args:
        current_date: Date for transit calculation (defaults to today)
        latitude: Observer latitude (for house calculations)
        longitude: Observer longitude
    
    Returns:
        Dictionary with current transit positions of all planets
    """
    try:
        # Parse date or use today
        if current_date:
            transit_datetime = datetime.strptime(current_date, "%Y-%m-%d")
        else:
            transit_datetime = datetime.now()
        
        # Generate "chart" for current moment (these are the transits)
        engine = VedicEngine()
        transit_chart = engine.generate_chart(
            birth_date=transit_datetime,
            latitude=latitude,
            longitude=longitude
        )
        
        result = {
            "date": transit_datetime.strftime("%Y-%m-%d"),
            "transits": {
                "Sun": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.SUN).value],
                "Moon": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.MOON).value],
                "Mars": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.MARS).value],
                "Mercury": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.MERCURY).value],
                "Jupiter": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.JUPITER).value],
                "Venus": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.VENUS).value],
                "Saturn": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.SATURN).value],
                "Rahu": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.RAHU).value],
                "Ketu": RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(CelestialBody.KETU).value]
            },
            "retrograde_status": {
                planet.name: transit_chart.is_planet_retrograde(planet)
                for planet in [
                    CelestialBody.MERCURY, CelestialBody.VENUS, CelestialBody.MARS,
                    CelestialBody.JUPITER, CelestialBody.SATURN
                ]
            }
        }
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "transits": {}
        }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Dictionary of all available tools
CALCULATION_TOOLS = {
    "vedic_birth_chart": calculate_vedic_birth_chart,
    "current_dasha": calculate_current_dasha,
    "current_transits": calculate_current_transits
}


def get_calculation_tools() -> Dict[str, Any]:
    """
    Get all calculation tools for orchestrator.
    
    Returns:
        Dictionary of tool_name -> tool_function
    """
    return CALCULATION_TOOLS


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("CALCULATION TOOLS - Test Suite")
    print("="*70)
    print()
    
    # Test data (Arjun Kumar from dummy users)
    test_data = {
        "date_of_birth": "1990-03-15",
        "time_of_birth": "14:30:00",
        "latitude": 26.9124,
        "longitude": 75.7873,
        "timezone": "Asia/Kolkata"
    }
    
    # Test 1: Birth Chart
    print("Test 1: Birth Chart Calculation")
    print("-" * 70)
    chart = calculate_vedic_birth_chart.invoke(test_data)
    
    if "error" in chart:
        print(f"❌ Error: {chart['error']}")
    else:
        print(f"[OK] Lagna: {chart['lagna']}")
        print(f"[OK] Moon Sign: {chart['moon_sign']}")
        print(f"[OK] Sun Sign: {chart['sun_sign']}")
        print(f"[OK] Moon Nakshatra: {chart['moon_nakshatra']}")
        print(f"[OK] Jupiter: {chart['planets']['Jupiter']['rashi']} in House {chart['planets']['Jupiter']['house']}")
    print()
    
    # Test 2: Dasha
    print("Test 2: Current Dasha Calculation")
    print("-" * 70)
    dasha = calculate_current_dasha.invoke({
        "date_of_birth": test_data["date_of_birth"],
        "time_of_birth": test_data["time_of_birth"],
        "latitude": test_data["latitude"],
        "longitude": test_data["longitude"]
    })
    
    if "error" in dasha:
        print(f"❌ Error: {dasha['error']}")
    else:
        print(f"[OK] Mahadasha: {dasha['mahadasha']['planet']}")
        print(f"  Period: {dasha['mahadasha']['start_date']} to {dasha['mahadasha']['end_date']}")
        print(f"[OK] Antardasha: {dasha['antardasha']['planet']}")
        print(f"[OK] Dasha Sequence: {dasha['dasha_sequence']}")
    print()
    
    # Test 3: Transits
    print("Test 3: Current Transits")
    print("-" * 70)
    transits = calculate_current_transits.invoke({})
    
    if "error" in transits:
        print(f"❌ Error: {transits['error']}")
    else:
        print(f"[OK] Date: {transits['date']}")
        print(f"[OK] Jupiter: {transits['transits']['Jupiter']}")
        print(f"[OK] Saturn: {transits['transits']['Saturn']}")
        print(f"[OK] Mars: {transits['transits']['Mars']}")
    print()
    
    print("="*70)
    print("[DONE] All tests complete!")
    print("="*70)