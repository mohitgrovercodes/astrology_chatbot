# src/tools/tools.py
"""
LangChain Tool Wrappers for Astrology Calculation Engines
==========================================================

This module provides LangChain @tool decorated wrappers around the
deterministic Vedic and Western astrology calculation engines.

These tools are used by the LangGraph orchestration layer to perform
calculations when needed during a conversation.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import time as time_module

from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Import calculation engines
from src.engines.vedic.vedic_engine import generate_vedic_chart, VedicEngine
from src.engines.western.western_engine import generate_western_chart
from src.engines.core.ephemeris import HouseSystem
from src.engines.core.celestial_bodies import CelestialBody

# Import utilities
from src.utils.schemas import BirthDataInput
from src.utils.serializers import serialize_vedic_chart, serialize_western_chart
from src.utils.validators import validate_birth_data
from src.engines.core.datetime_utils import parse_birth_datetime
from src.engines.core.exceptions import AstrologyEngineError
from src.engines.vedic.vedic_constants import Ayanamsa, RASHI_SANSKRIT_NAMES, NAKSHATRA_NAMES


# =============================================================================
# TOOL INPUT SCHEMAS
# =============================================================================

class ChartCalculationInput(BaseModel):
    """Input schema for chart calculation tools."""
    date: str = Field(..., description="Birth date in YYYY-MM-DD format", examples=["1990-03-15"])
    time: str = Field(..., description="Birth time in HH:MM:SS format (24-hour)", examples=["14:30:00"])
    latitude: float = Field(..., description="Birth place latitude (-90 to +90)", examples=[26.9124])
    longitude: float = Field(..., description="Birth place longitude (-180 to +180)", examples=[75.7873])
    timezone: Optional[str] = Field("Asia/Kolkata", description="IANA timezone string", examples=["Asia/Kolkata"])
    ayanamsa: Optional[str] = Field("LAHIRI", description="Ayanamsa system (LAHIRI, RAMAN, etc.)")
    house_system: Optional[str] = Field("WHOLE_SIGN", description="House system to use")


class DashaCalculationInput(BaseModel):
    """Input schema for dasha calculation."""
    date_of_birth: str = Field(..., description="Date in YYYY-MM-DD format")
    time_of_birth: str = Field(..., description="Time in HH:MM:SS format")
    latitude: float = Field(...)
    longitude: float = Field(...)
    current_date: Optional[str] = Field(None, description="Optional date for dasha calculation (YYYY-MM-DD)")


class TransitCalculationInput(BaseModel):
    """Input schema for transit calculation."""
    current_date: Optional[str] = Field(None, description="Date for transit calculation (YYYY-MM-DD)")
    latitude: Optional[float] = Field(26.9124, description="Observer latitude")
    longitude: Optional[float] = Field(75.7873, description="Observer longitude")


# =============================================================================
# VEDIC CHART CALCULATION TOOL
# =============================================================================

@tool(args_schema=ChartCalculationInput)
def calculate_vedic_chart(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata",
    ayanamsa: str = "LAHIRI",
    house_system: str = "WHOLE_SIGN"
) -> Dict[str, Any]:
    """
    Calculate a complete Vedic (Jyotish) birth chart.
    Returns planetary positions, houses, nakshatras, dashas, and yogas.
    """
    start_perf = time_module.perf_counter()
    try:
        # Map constants
        ayanamsa_enum = getattr(Ayanamsa, ayanamsa.upper(), Ayanamsa.LAHIRI)
        house_system_enum = getattr(HouseSystem, house_system.upper(), HouseSystem.WHOLE_SIGN)

        # Parse datetime
        full_dt_str = f"{date} {time}"
        try:
            birth_dt = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            birth_dt = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M")

        # Generate chart
        chart = generate_vedic_chart(
            birth_date=birth_dt,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone,
            ayanamsa=ayanamsa_enum,
            house_system=house_system_enum
        )

        # Serialize using enhanced global serializer
        serialized = serialize_vedic_chart(chart)
        
        # Add performance metrics
        serialized["_runtime_ms"] = round((time_module.perf_counter() - start_perf) * 1000, 2)
        return serialized

    except Exception as e:
        return {"error": str(e), "status": "failed"}


# =============================================================================
# WESTERN CHART CALCULATION TOOL
# =============================================================================

@tool(args_schema=ChartCalculationInput)
def calculate_western_chart(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    timezone: str = "UTC",
    house_system: str = "PLACIDUS"
) -> Dict[str, Any]:
    """
    Calculate a complete Western (Tropical) birth chart.
    Returns planetary positions, houses, and major aspects.
    """
    try:
        house_enum = getattr(HouseSystem, house_system.upper(), HouseSystem.PLACIDUS)
        
        full_dt_str = f"{date} {time}"
        try:
            birth_dt = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            birth_dt = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M")

        chart = generate_western_chart(
            birth_datetime=birth_dt,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_enum
        )
        return serialize_western_chart(chart)
    except Exception as e:
        return {"error": str(e), "status": "failed"}


# =============================================================================
# DASHA CALCULATION TOOL
# =============================================================================

@tool(args_schema=DashaCalculationInput)
def calculate_current_dasha(
    date_of_birth: str,
    time_of_birth: str,
    latitude: float,
    longitude: float,
    current_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate current Vimshottari dasha periods (Mahadasha, Antardasha, Pratyantardasha).
    """
    try:
        birth_dt_str = f"{date_of_birth} {time_of_birth}"
        try:
            birth_dt = datetime.strptime(birth_dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            birth_dt = datetime.strptime(birth_dt_str, "%Y-%m-%d %H:%M")
        
        calc_dt = datetime.strptime(current_date, "%Y-%m-%d") if current_date else datetime.now()
        
        engine = VedicEngine()
        chart = engine.generate_chart(birth_date=birth_dt, latitude=latitude, longitude=longitude)
        
        periods = chart.get_current_dasha(calc_dt)
        
        from src.engines.vedic.dasha_systems import compute_pratyantardashas

        # Get upcoming antardashas for timeline context
        all_ads = chart.dasha.get_antardashas(periods["mahadasha"])
        upcoming_ads = []
        for ad in all_ads:
            if ad.end_date > calc_dt:
                upcoming_ads.append({
                    "planet": ad.lord.name,
                    "start": ad.start_date.strftime("%Y-%m-%d"),
                    "end": ad.end_date.strftime("%Y-%m-%d")
                })

        # Upcoming pratyantardashas within the current Antardasha (precise week-level timing)
        # Only include periods that END in the future — fully elapsed periods are excluded.
        # A period currently in progress (started in past, ends in future) is included
        # and flagged as "in_progress" so the LLM knows not to cite its start as future.
        current_ad = periods["antardasha"]
        all_pds = compute_pratyantardashas(current_ad)
        upcoming_pds = []
        for pd in all_pds:
            if pd.end_date > calc_dt:
                in_progress = pd.start_date <= calc_dt < pd.end_date
                upcoming_pds.append({
                    "planet": pd.lord.name,
                    "start": pd.start_date.strftime("%Y-%m-%d"),
                    "end": pd.end_date.strftime("%Y-%m-%d"),
                    "duration_days": pd.duration_days,
                    "status": "IN PROGRESS (started in past)" if in_progress else "upcoming"
                })

        # First pratyantardasha of each upcoming Antardasha (cross-level convergence timing)
        next_ad_first_pd = []
        for ad in upcoming_ads[:3]:  # Only next 3 Antardashas to keep output manageable
            # Re-fetch the DashaPeriod object for this upcoming AD
            for ad_obj in all_ads:
                if ad_obj.lord.name == ad["planet"] and ad_obj.start_date.strftime("%Y-%m-%d") == ad["start"]:
                    first_pds = compute_pratyantardashas(ad_obj)
                    if first_pds:
                        fp = first_pds[0]
                        next_ad_first_pd.append({
                            "antardasha_planet": ad["planet"],
                            "antardasha_start": ad["start"],
                            "first_pratyantar_planet": fp.lord.name,
                            "first_pratyantar_start": fp.start_date.strftime("%Y-%m-%d"),
                            "first_pratyantar_end": fp.end_date.strftime("%Y-%m-%d")
                        })
                    break

        # Format for LLM consumption
        result = {
            "mahadasha": {
                "planet": periods["mahadasha"].lord.name,
                "start": periods["mahadasha"].start_date.strftime("%Y-%m-%d"),
                "end": periods["mahadasha"].end_date.strftime("%Y-%m-%d")
            },
            "antardasha": {
                "planet": periods["antardasha"].lord.name,
                "start": periods["antardasha"].start_date.strftime("%Y-%m-%d"),
                "end": periods["antardasha"].end_date.strftime("%Y-%m-%d")
            },
            "pratyantardasha": {
                "planet": periods["pratyantardasha"].lord.name,
                "start": periods["pratyantardasha"].start_date.strftime("%Y-%m-%d"),
                "end": periods["pratyantardasha"].end_date.strftime("%Y-%m-%d")
            },
            "upcoming_pratyantardashas": upcoming_pds,
            "upcoming_antardashas": upcoming_ads,
            "next_antardasha_first_pratyantar": next_ad_first_pd,
            "dasha_sequence": f"{periods['mahadasha'].lord.name}/{periods['antardasha'].lord.name}/{periods['pratyantardasha'].lord.name}",
            "calculation_details": {
                "moon_longitude": round(chart.dasha.moon_longitude, 2),
                "moon_nakshatra": chart.dasha.moon_nakshatra.name,
                "first_dasha_lord": chart.dasha.dasha_balance.first_lord.name,
                "balance_at_birth_years": round(chart.dasha.dasha_balance.remaining_years, 2)
            }
        }
        return result
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# TRANSIT CALCULATION TOOL
# =============================================================================

@tool(args_schema=TransitCalculationInput)
def calculate_current_transits(
    current_date: Optional[str] = None,
    latitude: float = 26.9124,
    longitude: float = 75.7873
) -> Dict[str, Any]:
    """
    Calculate current planetary transits for a given date and location.
    """
    try:
        transit_dt = datetime.strptime(current_date, "%Y-%m-%d") if current_date else datetime.now()
        
        engine = VedicEngine()
        transit_chart = engine.generate_chart(birth_date=transit_dt, latitude=latitude, longitude=longitude)
        
        transits = {}
        for planet in [CelestialBody.SUN, CelestialBody.MOON, CelestialBody.MARS, CelestialBody.MERCURY, 
                       CelestialBody.JUPITER, CelestialBody.VENUS, CelestialBody.SATURN, CelestialBody.RAHU, CelestialBody.KETU]:
            transits[planet.name] = RASHI_SANSKRIT_NAMES[transit_chart.get_planet_rashi(planet).value]
            
        return {
            "date": transit_dt.strftime("%Y-%m-%d"),
            "transits": transits,
            "retrograde_status": {
                p.name: transit_chart.is_planet_retrograde(p)
                for p in [CelestialBody.MERCURY, CelestialBody.VENUS, CelestialBody.MARS, CelestialBody.JUPITER, CelestialBody.SATURN]
            }
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# TOOL REGISTRY
# =============================================================================

def get_calculation_tools() -> Dict[str, Any]:
    """Returns a dictionary of all available astrology calculation tools."""
    return {
        "calculate_vedic_chart": calculate_vedic_chart,
        "calculate_western_chart": calculate_western_chart,
        "calculate_current_dasha": calculate_current_dasha,
        "calculate_current_transits": calculate_current_transits
    }

# Legacy support
ASTROLOGY_TOOLS = list(get_calculation_tools().values())
