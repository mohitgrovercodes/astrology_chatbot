# src/tools/tools.py
# src\tools\tools.py
"""
LangChain Tool Wrappers for Astrology Calculation Engines
==========================================================

This module provides LangChain @tool decorated wrappers around the
deterministic Vedic and Western astrology calculation engines.

These tools are used by the LangGraph orchestration layer to perform
calculations when needed during a conversation.

Design Principles:
-----------------
1. Thin wrapper - no calculation logic here
2. Input validation using existing schemas
3. Serialized output for LLM consumption
4. Error handling with informative messages
5. Type hints for LangChain's benefit
"""

from typing import Dict, Any, Optional, Literal
from datetime import datetime
import time


from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Import calculation engines
from src.engines.vedic.vedic_engine import VedicEngine, generate_vedic_chart
from src.engines.western.western_engine import WesternAstroEngine, generate_western_chart
from src.engines.core.ephemeris import HouseSystem

# Import utilities
from src.utils.schemas import BirthDataInput, ChartOptions
from src.utils.serializers import serialize_vedic_chart, serialize_western_chart
from src.utils.validators import validate_birth_data
from src.utils.formatters import format_for_llm, format_chart_summary
from src.engines.core.datetime_utils import parse_birth_datetime
from src.engines.core.exceptions import AstrologyEngineError
from src.engines.vedic.vedic_constants import Ayanamsa


# =============================================================================
# TOOL INPUT SCHEMAS
# =============================================================================

class ChartCalculationInput(BaseModel):
    """Input schema for chart calculation tools."""
    
    date: str = Field(
        ...,
        description="Birth date in YYYY-MM-DD format",
        examples=["1990-03-15"]
    )
    
    time: str = Field(
        ...,
        description="Birth time in HH:MM format (24-hour)",
        examples=["15:30", "03:45"]
    )
    
    latitude: float = Field(
        ...,
        description="Birth place latitude (-90 to +90)",
        examples=[26.9124, 40.7128]
    )
    
    longitude: float = Field(
        ...,
        description="Birth place longitude (-180 to +180)",
        examples=[75.7873, -74.0060]
    )
    
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone string (auto-detected if not provided)",
        examples=["Asia/Kolkata", "America/New_York"]
    )
    
    ayanamsa: Optional[str] = Field(
        "LAHIRI",
        description="Ayanamsa system for Vedic charts"
    )
    
    house_system: Optional[str] = Field(
        "WHOLE_SIGN",
        description="House system to use"
    )


# =============================================================================
# VEDIC CHART CALCULATION TOOL
# =============================================================================

@tool
def calculate_vedic_chart(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None,
    ayanamsa: str = "LAHIRI",
    house_system: str = "WHOLE_SIGN",
    include_summary: bool = True
) -> Dict[str, Any]:
    """
    Calculate a complete Vedic (Jyotish) birth chart.
    
    This tool computes:
    - Planetary positions (sidereal zodiac)
    - Lagna (Ascendant) and house placements
    - Nakshatras and padas
    - Planetary dignities
    - Yogas (planetary combinations)
    - Vimshottari Dasha periods
    
    Args:
        date: Birth date in YYYY-MM-DD format
        time: Birth time in HH:MM format (24-hour)
        latitude: Geographic latitude (-90 to +90)
        longitude: Geographic longitude (-180 to +180)
        timezone: IANA timezone (auto-detected if not provided)
        ayanamsa: Ayanamsa system (LAHIRI, RAMAN, KRISHNAMURTI, etc.)
        house_system: House system (WHOLE_SIGN, PLACIDUS, EQUAL, etc.)
        include_summary: Whether to include a text summary
        
    Returns:
        Dictionary with complete chart data serialized for LLM consumption
        
    Example:
        >>> result = calculate_vedic_chart(
        ...     date="1990-03-15",
        ...     time="15:30",
        ...     latitude=26.9124,
        ...     longitude=75.7873,
        ...     timezone="Asia/Kolkata"
        ... )
        >>> print(result['lagna']['sign'])
        'Taurus'
    """
    start_time = time.time()
    
    try:
        # Validate input
        birth_data = BirthDataInput(
            date=date,
            time=time,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone
        )
        
        validate_birth_data(birth_data)
        
        # Parse datetime
        birth_datetime = parse_birth_datetime(
            date, time, timezone or "UTC"
        )
        
        # Map ayanamsa string to enum
        ayanamsa_map = {
            "LAHIRI": Ayanamsa.LAHIRI,
            "RAMAN": Ayanamsa.RAMAN,
            "KRISHNAMURTI": Ayanamsa.KRISHNAMURTI,
            "FAGAN_BRADLEY": Ayanamsa.FAGAN_BRADLEY,
        }
        ayanamsa_enum = ayanamsa_map.get(ayanamsa.upper(), Ayanamsa.LAHIRI)
        
        # Map house system string to enum
        house_system_map = {
            "WHOLE_SIGN": HouseSystem.WHOLE_SIGN,
            "PLACIDUS": HouseSystem.PLACIDUS,
            "EQUAL": HouseSystem.EQUAL,
            "KOCH": HouseSystem.KOCH,
        }
        house_system_enum = house_system_map.get(
            house_system.upper(), HouseSystem.WHOLE_SIGN
        )
        
        # Generate chart using the calculation engine
        chart = generate_vedic_chart(
            birth_date=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone,
            ayanamsa=ayanamsa_enum,
            house_system=house_system_enum
        )
        
        # Serialize for LLM consumption
        serialized = serialize_vedic_chart(chart)
        
        # Add computation metadata
        computation_time = (time.time() - start_time) * 1000
        serialized['_computation'] = {
            'time_ms': round(computation_time, 2),
            'engine': 'vedic',
            'ayanamsa': ayanamsa,
            'house_system': house_system
        }
        
        # Add human-readable summary if requested
        if include_summary:
            serialized['_summary'] = format_chart_summary(serialized)
        
        return serialized
        
    except AstrologyEngineError as e:
        return {
            'error': True,
            'error_type': 'calculation_error',
            'message': str(e),
            'details': e.details if hasattr(e, 'details') else {}
        }
    except Exception as e:
        return {
            'error': True,
            'error_type': 'unexpected_error',
            'message': f"Failed to calculate Vedic chart: {str(e)}"
        }


# =============================================================================
# WESTERN CHART CALCULATION TOOL
# =============================================================================

@tool
def calculate_western_chart(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None,
    house_system: str = "PLACIDUS",
    include_summary: bool = True
) -> Dict[str, Any]:
    """
    Calculate a complete Western (Tropical) birth chart.
    
    This tool computes:
    - Planetary positions (tropical zodiac)
    - Ascendant and house placements
    - Planetary aspects (conjunctions, trines, squares, etc.)
    - Essential dignities (domicile, exaltation, etc.)
    - Major chart patterns
    
    Args:
        date: Birth date in YYYY-MM-DD format
        time: Birth time in HH:MM format (24-hour)
        latitude: Geographic latitude (-90 to +90)
        longitude: Geographic longitude (-180 to +180)
        timezone: IANA timezone (auto-detected if not provided)
        house_system: House system (PLACIDUS, KOCH, EQUAL, WHOLE_SIGN)
        include_summary: Whether to include a text summary
        
    Returns:
        Dictionary with complete chart data serialized for LLM consumption
        
    Example:
        >>> result = calculate_western_chart(
        ...     date="1990-03-15",
        ...     time="15:30",
        ...     latitude=40.7128,
        ...     longitude=-74.0060,
        ...     timezone="America/New_York"
        ... )
        >>> print(result['key_points']['sun_sign'])
        'Pisces'
    """
    start_time = time.time()
    
    try:
        # Validate input
        birth_data = BirthDataInput(
            date=date,
            time=time,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone
        )
        
        validate_birth_data(birth_data)
        
        # Parse datetime
        birth_datetime = parse_birth_datetime(
            date, time, timezone or "UTC"
        )
        
        # Map house system string to enum
        house_system_map = {
            "PLACIDUS": HouseSystem.PLACIDUS,
            "KOCH": HouseSystem.KOCH,
            "EQUAL": HouseSystem.EQUAL,
            "WHOLE_SIGN": HouseSystem.WHOLE_SIGN,
            "CAMPANUS": HouseSystem.CAMPANUS,
        }
        house_system_enum = house_system_map.get(
            house_system.upper(), HouseSystem.PLACIDUS
        )
        
        # Generate chart using the calculation engine
        chart = generate_western_chart(
            birth_datetime=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system_enum
        )
        
        # Serialize for LLM consumption
        serialized = serialize_western_chart(chart)
        
        # Add computation metadata
        computation_time = (time.time() - start_time) * 1000
        serialized['_computation'] = {
            'time_ms': round(computation_time, 2),
            'engine': 'western',
            'house_system': house_system
        }
        
        # Add human-readable summary if requested
        if include_summary:
            serialized['_summary'] = format_chart_summary(serialized)
        
        return serialized
        
    except AstrologyEngineError as e:
        return {
            'error': True,
            'error_type': 'calculation_error',
            'message': str(e),
            'details': e.details if hasattr(e, 'details') else {}
        }
    except Exception as e:
        return {
            'error': True,
            'error_type': 'unexpected_error',
            'message': f"Failed to calculate Western chart: {str(e)}"
        }


# =============================================================================
# CHART COMPARISON TOOL
# =============================================================================

@tool
def calculate_both_charts(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate both Vedic and Western charts for comparison.
    
    This is useful when a user wants to understand the differences
    between the two astrological systems.
    
    Args:
        date: Birth date in YYYY-MM-DD format
        time: Birth time in HH:MM format (24-hour)
        latitude: Geographic latitude (-90 to +90)
        longitude: Geographic longitude (-180 to +180)
        timezone: IANA timezone (auto-detected if not provided)
        
    Returns:
        Dictionary containing both Vedic and Western chart data
    """
    try:
        vedic = calculate_vedic_chart(
            date=date,
            time=time,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            include_summary=False
        )
        
        western = calculate_western_chart(
            date=date,
            time=time,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            include_summary=False
        )
        
        return {
            'vedic': vedic,
            'western': western,
            '_summary': (
                f"Vedic: {vedic.get('_summary', 'Calculated')} | "
                f"Western: {western.get('_summary', 'Calculated')}"
            )
        }
        
    except Exception as e:
        return {
            'error': True,
            'message': f"Failed to calculate both charts: {str(e)}"
        }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Export all tools for easy import
ASTROLOGY_TOOLS = [
    calculate_vedic_chart,
    calculate_western_chart,
    calculate_both_charts,
]


def get_tool_by_name(name: str):
    """
    Get a tool by its name.
    
    Args:
        name: Tool name (function name)
        
    Returns:
        The tool function
        
    Raises:
        ValueError: If tool not found
    """
    tool_map = {tool.name: tool for tool in ASTROLOGY_TOOLS}
    
    if name not in tool_map:
        raise ValueError(
            f"Tool '{name}' not found. Available tools: {list(tool_map.keys())}"
        )
    
    return tool_map[name]


# =============================================================================
# USAGE EXAMPLE (for testing)
# =============================================================================

if __name__ == "__main__":
    # Test the tools
    print("Testing Vedic Chart Calculation Tool...")
    
    result = calculate_vedic_chart(
        date="1990-03-15",
        time="15:30",
        latitude=26.9124,
        longitude=75.7873,
        timezone="Asia/Kolkata"
    )
    
    if result.get('error'):
        print(f"Error: {result.get('message')}")
    else:
        print(f"[OK] Vedic chart calculated successfully")
        print(f"  Lagna: {result.get('lagna', {}).get('sign')}")
        print(f"  Computation time: {result.get('_computation', {}).get('time_ms')}ms")
        print(f"  Summary: {result.get('_summary')}")
    
    print("\nTesting Western Chart Calculation Tool...")
    
    result = calculate_western_chart(
        date="1990-03-15",
        time="15:30",
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York"
    )
    
    if result.get('error'):
        print(f"Error: {result.get('message')}")
    else:
        print(f"[OK] Western chart calculated successfully")
        sun_sign = result.get('key_points', {}).get('sun_sign')
        print(f"  Sun Sign: {sun_sign}")
        print(f"  Computation time: {result.get('_computation', {}).get('time_ms')}ms")
        print(f"  Summary: {result.get('_summary')}")
