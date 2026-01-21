"""
Core Astronomical Calculation Module
====================================

This module provides the foundational astronomical calculations that both
Vedic and Western astrology engines depend on. It wraps the Swiss Ephemeris
library and provides clean, type-safe interfaces.

Architecture:
------------
The core module is the lowest layer in our calculation stack:

    [Orchestration Layer - LLM, RAG]
            ↓
    [Vedic Engine] [Western Engine]
            ↓           ↓
    ====[ Core Module ]====
        - Ephemeris (Swiss Ephemeris wrapper)
        - DateTime (Julian Day conversions)
        - Coordinates (Geographic positions)
        - Celestial Bodies (Planet definitions)

All modules above this layer depend on core, but core has no dependencies
on other parts of our system (only external libraries).

Key Components:
--------------
- CelestialBody: Enum of all planets and points
- PlanetPosition: Position data from ephemeris
- GeoPosition: Geographic coordinates
- datetime_to_julian_day: Time conversion
- get_sidereal_position: Sidereal planetary positions
- get_house_cusps: House cusp calculations

Thread Safety:
-------------
Swiss Ephemeris uses global state for ayanamsa settings. If you need
thread-safe operation, ensure each thread sets the ayanamsa before
calling sidereal functions.
"""

# Celestial bodies and planet data
from src.engines.core.celestial_bodies import (
    CelestialBody,
    PlanetInfo,
    VEDIC_GRAHAS,
    CLASSICAL_PLANETS,
    WESTERN_PLANETS,
    NATURAL_BENEFICS,
    NATURAL_MALEFICS,
    get_planet_info,
)

# Geographic coordinates
from src.engines.core.coordinates import (
    GeoPosition,
    create_position,
    parse_dms_to_decimal,
    decimal_to_dms,
    COMMON_LOCATIONS,
    get_common_location,
)

# Date/time utilities
from src.engines.core.datetime_utils import (
    datetime_to_julian_day,
    julian_day_to_datetime,
    get_timezone_for_location,
    get_utc_offset_hours,
    get_sidereal_time,
    get_delta_t,
    datetime_to_julian_century,
    format_datetime_vedic,
    parse_birth_datetime,
    JD_UNIX_EPOCH,
    J2000,
)

# Swiss Ephemeris wrapper
from src.engines.core.ephemeris import (
    HouseSystem,
    PlanetPosition,
    HouseCusps,
    get_planet_position,
    get_sidereal_position,
    get_all_positions,
    get_all_sidereal_positions,
    get_ayanamsa_value,
    get_house_cusps,
    get_sidereal_house_cusps,
)

# Custom exceptions
from src.engines.core.exceptions import (
    AstrologyEngineError,
    EphemerisError,
    DateTimeError,
    CoordinateError,
    CalculationError,
    ValidationError,
    ConfigurationError,
    DataError,
)

# Import Ayanamsa from vedic (this is OK because vedic imports from core, not the other way around)
from src.engines.vedic.vedic_constants import Ayanamsa


__all__ = [
    # Celestial Bodies
    "CelestialBody",
    "PlanetInfo",
    "VEDIC_GRAHAS",
    "CLASSICAL_PLANETS",
    "WESTERN_PLANETS",
    "NATURAL_BENEFICS",
    "NATURAL_MALEFICS",
    "get_planet_info",
    
    # Coordinates
    "GeoPosition",
    "create_position",
    "parse_dms_to_decimal",
    "decimal_to_dms",
    "COMMON_LOCATIONS",
    "get_common_location",
    
    # DateTime
    "datetime_to_julian_day",
    "julian_day_to_datetime",
    "get_timezone_for_location",
    "get_utc_offset_hours",
    "get_sidereal_time",
    "get_delta_t",
    "datetime_to_julian_century",
    "format_datetime_vedic",
    "parse_birth_datetime",
    "JD_UNIX_EPOCH",
    "J2000",
    
    # Ephemeris
    "Ayanamsa",
    "HouseSystem",
    "PlanetPosition",
    "HouseCusps",
    "get_planet_position",
    "get_sidereal_position",
    "get_all_positions",
    "get_all_sidereal_positions",
    "get_ayanamsa_value",
    "get_house_cusps",
    "get_sidereal_house_cusps",
    
    # Exceptions
    "AstrologyEngineError",
    "EphemerisError",
    "DateTimeError",
    "CoordinateError",
    "CalculationError",
    "ValidationError",
    "ConfigurationError",
    "DataError",
]