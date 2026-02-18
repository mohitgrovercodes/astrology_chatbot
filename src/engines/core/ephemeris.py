# src/engines/core/ephemeris.py
# src\engines\core\ephemeris.py
"""
Swiss Ephemeris Wrapper for Planetary Calculations
==================================================

This module provides a clean, Pythonic interface to the Swiss Ephemeris
library (pyswisseph), which calculates precise planetary positions based
on NASA's JPL ephemeris data.

Why Swiss Ephemeris?
-------------------
Swiss Ephemeris is the gold standard for astrological software because:
1. It's based on NASA's JPL Development Ephemeris (DE431)
2. Accuracy is within 0.001 arc-seconds for the main planets
3. Covers the date range 13,000 BC to 17,000 AD
4. Provides both tropical and sidereal calculations
5. Supports multiple house systems and ayanamsas

Key Concepts:
------------
- Tropical Zodiac: Based on the seasons (vernal equinox = 0Â° Aries)
- Sidereal Zodiac: Based on fixed stars (used in Vedic astrology)
- Ayanamsa: The angular difference between tropical and sidereal zodiacs
- Ephemeris Time (TT): Uniform time scale for astronomical calculations
- House System: Method for dividing the sky into 12 houses

Usage Example:
-------------
    from nakshatra_chatbot.engine.core.ephemeris import         get_sidereal_position, Ayanamsa, CelestialBody
    )
    
    # Get Moon's position in sidereal zodiac
    moon_pos = get_sidereal_position(jd, CelestialBody.MOON, Ayanamsa.LAHIRI)
    print(f"Moon at {moon_pos.longitude}Â° sidereal")
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import swisseph as swe

from .celestial_bodies import CelestialBody, VEDIC_GRAHAS
from .exceptions import EphemerisError


class Ayanamsa(IntEnum):
    """
    Ayanamsa (precession correction) systems for sidereal calculations.
    
    The ayanamsa is the angular difference between the tropical and sidereal
    zodiacs. Different traditions use different ayanamsas, which is why
    Vedic astrologers may give slightly different positions.
    
    Common values (as of 2024):
    - LAHIRI: ~24.17Â° (most popular in India, used by Indian government)
    - RAMAN: ~22.47Â° (created by B.V. Raman)
    - KRISHNAMURTI: ~23.76Â° (KP system)
    - FAGAN_BRADLEY: ~24.85Â° (Western sidereal)
    """
    LAHIRI = swe.SIDM_LAHIRI                    # Official Indian standard
    RAMAN = swe.SIDM_RAMAN                      # B.V. Raman's ayanamsa
    KRISHNAMURTI = swe.SIDM_KRISHNAMURTI        # KP Astrology
    FAGAN_BRADLEY = swe.SIDM_FAGAN_BRADLEY      # Western sidereal
    TRUE_CITRA = swe.SIDM_TRUE_CITRA            # Citra at 0Â° Libra
    TRUE_REVATI = swe.SIDM_TRUE_REVATI          # Revati at 29Â°50' Pisces
    TRUE_PUSHYA = swe.SIDM_TRUE_PUSHYA          # Pushya at 16Â° Cancer
    YUKTESHWAR = swe.SIDM_YUKTESHWAR            # Sri Yukteshwar
    JN_BHASIN = swe.SIDM_JN_BHASIN              # J.N. Bhasin
    

class HouseSystem(IntEnum):
    """
    House calculation systems.
    
    Different house systems divide the sky differently, resulting in
    different house cusps. The choice of house system is important
    and depends on tradition and personal preference.
    
    Vedic astrology traditionally uses:
    - WHOLE_SIGN: Simplest system, entire sign = one house
    - EQUAL: Equal 30Â° houses from Ascendant
    - SRIPATI: Also known as Porphyry in the West
    
    Western astrology commonly uses:
    - PLACIDUS: Most popular in modern Western astrology
    - KOCH: Popular in German-speaking countries
    - CAMPANUS: Space-based division
    """
    PLACIDUS = ord('P')
    KOCH = ord('K')
    PORPHYRY = ord('O')      # Same as Sripati
    REGIOMONTANUS = ord('R')
    CAMPANUS = ord('C')
    EQUAL = ord('E')
    WHOLE_SIGN = ord('W')
    MERIDIAN = ord('X')
    MORINUS = ord('M')
    ALCABITIUS = ord('B')
    TOPOCENTRIC = ord('T')
    
    # Alias for Vedic astrologers
    SRIPATI = ord('O')       # Sripati is same as Porphyry


@dataclass(frozen=True)
class PlanetPosition:
    """
    Position and motion data for a celestial body.
    
    This dataclass contains all the information returned by Swiss Ephemeris
    for a single planetary calculation, including position, speed, and
    derived properties useful for astrological analysis.
    
    Attributes:
        body: The celestial body this position is for
        longitude: Ecliptic longitude in degrees (0-360)
        latitude: Ecliptic latitude in degrees (usually small, <10Â°)
        distance: Distance from Earth in Astronomical Units (AU)
        speed_longitude: Daily motion in longitude (degrees/day)
        speed_latitude: Daily motion in latitude
        speed_distance: Daily change in distance
        
    Derived Properties:
        is_retrograde: True if planet appears to move backwards
        sign_index: Zodiac sign (0=Aries to 11=Pisces)
        degree_in_sign: Degrees within current sign (0-30)
    """
    body: CelestialBody
    longitude: float          # 0-360 degrees on the ecliptic
    latitude: float           # degrees north/south of ecliptic
    distance: float           # AU from Earth
    speed_longitude: float    # degrees per day
    speed_latitude: float
    speed_distance: float
    
    @property
    def is_retrograde(self) -> bool:
        """
        Check if the planet is retrograde.
        
        A planet appears retrograde when its daily motion is negative,
        meaning it appears to move backwards through the zodiac from
        Earth's perspective. This is an optical illusion caused by the
        relative orbital speeds of Earth and the planet.
        
        Note: The Sun and Moon are never retrograde. Rahu/Ketu have
        complex motion that's always somewhat "retrograde" in nature.
        """
        return self.speed_longitude < 0
    
    @property
    def sign_index(self) -> int:
        """
        Get the zodiac sign index (0-11).
        
        Returns:
            0 = Aries (Mesha)
            1 = Taurus (Vrishabha)
            ...
            11 = Pisces (Meena)
        """
        return int(self.longitude // 30) % 12
    
    @property
    def degree_in_sign(self) -> float:
        """
        Get the degrees within the current sign (0-30).
        
        For example, if longitude is 45.5Â°, the planet is at 15.5Â° Taurus
        (sign_index=1, degree_in_sign=15.5).
        """
        return self.longitude % 30
    
    @property
    def nakshatra_index(self) -> int:
        """Get the nakshatra index (0-26) based on longitude."""
        return int(self.longitude / (360 / 27)) % 27
    
    @property
    def is_stationary(self) -> bool:
        """Check if planet is nearly stationary (very slow motion)."""
        return abs(self.speed_longitude) < 0.02  # Less than 0.02Â°/day


@dataclass(frozen=True)
class HouseCusps:
    """
    House cusp positions calculated by Swiss Ephemeris.
    
    The house cusps define where each of the 12 houses begins.
    This also includes important angles like the Ascendant (ASC)
    and Midheaven (MC).
    
    Attributes:
        cusps: Tuple of 12 house cusp longitudes (house 1 to 12)
        ascendant: Longitude of the Ascendant (1st house cusp)
        mc: Longitude of the Midheaven (10th house cusp)
        armc: ARMC (Right Ascension of MC) in degrees
        vertex: Longitude of the Vertex
        equatorial_ascendant: Longitude of the Equatorial Ascendant
    """
    cusps: Tuple[float, ...]  # 12 house cusps
    ascendant: float
    mc: float                 # Midheaven (Medium Coeli)
    armc: float               # Right Ascension of MC
    vertex: float
    equatorial_ascendant: float
    
    def get_house_cusp(self, house: int) -> float:
        """Get the cusp of a specific house (1-12)."""
        if not 1 <= house <= 12:
            raise ValueError(f"House must be 1-12, got {house}")
        return self.cusps[house - 1]
    
    @property
    def ic(self) -> float:
        """Get the IC (Imum Coeli), opposite to MC."""
        return (self.mc + 180) % 360
    
    @property
    def descendant(self) -> float:
        """Get the Descendant (7th house cusp), opposite to Ascendant."""
        return (self.ascendant + 180) % 360


def _get_swe_body_id(body: CelestialBody) -> int:
    """
    Convert our CelestialBody enum to Swiss Ephemeris body ID.
    
    Most bodies map directly, but Ketu requires special handling
    since it's not a separate body in Swiss Ephemeris.
    """
    if body == CelestialBody.KETU:
        return -1  # Special marker for Ketu
    return int(body)


def get_planet_position(
    jd: float,
    body: CelestialBody,
    flags: int = swe.FLG_SWIEPH | swe.FLG_SPEED
) -> PlanetPosition:
    """
    Calculate the position of a single planet (tropical zodiac).
    
    This is the core function that interfaces with Swiss Ephemeris
    to get planetary positions. By default, it returns tropical
    (Western) positions.
    
    Args:
        jd: Julian Day number
        body: Which celestial body to calculate
        flags: Swiss Ephemeris calculation flags (default includes speed)
        
    Returns:
        PlanetPosition with complete position and motion data
        
    Raises:
        EphemerisError: If calculation fails
    """
    # Handle Ketu specially - it's always opposite to Rahu
    if body == CelestialBody.KETU:
        rahu_pos = get_planet_position(jd, CelestialBody.RAHU, flags)
        return PlanetPosition(
            body=CelestialBody.KETU,
            longitude=(rahu_pos.longitude + 180) % 360,
            latitude=-rahu_pos.latitude,
            distance=rahu_pos.distance,
            speed_longitude=rahu_pos.speed_longitude,
            speed_latitude=-rahu_pos.speed_latitude,
            speed_distance=rahu_pos.speed_distance,
        )
    
    swe_id = _get_swe_body_id(body)
    
    try:
        result, ret_flag = swe.calc_ut(jd, swe_id, flags)
        
        if ret_flag < 0:
            raise EphemerisError(
                f"Swiss Ephemeris calculation failed for {body.name}",
                details={"julian_day": jd, "return_flag": ret_flag}
            )
        
        return PlanetPosition(
            body=body,
            longitude=result[0],
            latitude=result[1],
            distance=result[2],
            speed_longitude=result[3],
            speed_latitude=result[4],
            speed_distance=result[5],
        )
        
    except Exception as e:
        if isinstance(e, EphemerisError):
            raise
        raise EphemerisError(
            f"Failed to calculate position for {body.name}",
            details={"julian_day": jd},
            original_error=e
        )


def get_sidereal_position(
    jd: float,
    body: CelestialBody,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI
) -> PlanetPosition:
    """
    Calculate the sidereal (Vedic) position of a planet.
    
    This returns the position in the sidereal zodiac, which is what
    Vedic astrology uses. The sidereal zodiac is based on fixed stars
    rather than the seasons.
    
    Args:
        jd: Julian Day number
        body: Which celestial body to calculate
        ayanamsa: Which ayanamsa system to use (default: Lahiri)
        
    Returns:
        PlanetPosition with sidereal longitude
        
    Example:
        >>> from datetime import datetime
        >>> jd = datetime_to_julian_day(datetime(1990, 3, 15, 15, 30), ...)
        >>> moon = get_sidereal_position(jd, CelestialBody.MOON)
        >>> print(f"Moon: {moon.longitude:.2f}Â° sidereal")
    """
    # Set the sidereal mode
    swe.set_sid_mode(int(ayanamsa))
    
    # Calculate with sidereal flag
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    
    return get_planet_position(jd, body, flags)


def get_all_positions(
    jd: float,
    bodies: Tuple[CelestialBody, ...] = VEDIC_GRAHAS,
    flags: int = swe.FLG_SWIEPH | swe.FLG_SPEED
) -> Dict[CelestialBody, PlanetPosition]:
    """
    Calculate positions for multiple planets at once.
    
    This is a convenience function that calculates positions for a
    list of celestial bodies. It's more efficient than calling
    get_planet_position multiple times when you need multiple planets.
    
    Args:
        jd: Julian Day number
        bodies: Tuple of bodies to calculate (default: all 9 Vedic grahas)
        flags: Swiss Ephemeris calculation flags
        
    Returns:
        Dictionary mapping each body to its position
    """
    return {body: get_planet_position(jd, body, flags) for body in bodies}


def get_all_sidereal_positions(
    jd: float,
    bodies: Tuple[CelestialBody, ...] = VEDIC_GRAHAS,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI
) -> Dict[CelestialBody, PlanetPosition]:
    """
    Calculate sidereal positions for multiple planets.
    
    This is the primary function for Vedic astrology calculations,
    returning positions for all specified bodies in the sidereal zodiac.
    
    Args:
        jd: Julian Day number
        bodies: Which bodies to calculate (default: 9 Vedic grahas)
        ayanamsa: Which ayanamsa to use (default: Lahiri)
        
    Returns:
        Dictionary mapping each body to its sidereal position
    """
    swe.set_sid_mode(int(ayanamsa))
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    
    return {body: get_planet_position(jd, body, flags) for body in bodies}


def get_ayanamsa_value(
    jd: float,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI
) -> float:
    """
    Get the ayanamsa value (precession correction) for a given date.
    
    The ayanamsa value changes over time due to precession of the
    equinoxes (about 50.3 arc-seconds per year). This function returns
    the exact value for any given date.
    
    Args:
        jd: Julian Day number
        ayanamsa: Which ayanamsa system to use
        
    Returns:
        Ayanamsa value in degrees
        
    Example:
        >>> ayanamsa = get_ayanamsa_value(2451545.0, Ayanamsa.LAHIRI)
        >>> print(f"Lahiri ayanamsa on J2000: {ayanamsa:.4f}Â°")
        Lahiri ayanamsa on J2000: 23.8526Â°
    """
    swe.set_sid_mode(int(ayanamsa))
    return swe.get_ayanamsa_ut(jd)


def get_house_cusps(
    jd: float,
    latitude: float,
    longitude: float,
    house_system: HouseSystem = HouseSystem.WHOLE_SIGN
) -> HouseCusps:
    """
    Calculate house cusps for a given location and time.
    
    The house cusps define where each astrological house begins.
    Different house systems calculate these differently, leading to
    different house placements for planets.
    
    Args:
        jd: Julian Day number
        latitude: Geographic latitude (-90 to +90)
        longitude: Geographic longitude (-180 to +180)
        house_system: Which house system to use
        
    Returns:
        HouseCusps with all 12 cusps and important angles
        
    Notes:
        - For Whole Sign houses, cusps are at 0Â° of each sign
        - The Ascendant is always the same regardless of house system
        - At extreme latitudes, some house systems may fail
    """
    try:
        # Swiss Ephemeris expects house system as a single character
        hsys = bytes([house_system])
        
        cusps, angles = swe.houses(jd, latitude, longitude, hsys)
        
        # Determine house cusps based on return length
        # Standard: cusps[0] unused, cusps[1-12] are houses
        # Alternative: cusps[0-11] are houses
        if len(cusps) >= 13:
            cusp_data = tuple(cusps[1:13])
        else:
            cusp_data = tuple(cusps[:12])
            
        return HouseCusps(
            cusps=cusp_data,
            ascendant=angles[0],
            mc=angles[1],
            armc=angles[2],
            vertex=angles[3],
            equatorial_ascendant=angles[4] if len(angles) > 4 else 0.0,
        )
        
    except Exception as e:
        raise EphemerisError(
            f"Failed to calculate house cusps",
            details={
                "latitude": latitude,
                "longitude": longitude,
                "house_system": house_system.name
            },
            original_error=e
        )


def get_sidereal_house_cusps(
    jd: float,
    latitude: float,
    longitude: float,
    house_system: HouseSystem = HouseSystem.WHOLE_SIGN,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI
) -> HouseCusps:
    """
    Calculate house cusps in the sidereal zodiac.
    
    This is the function to use for Vedic astrology, as it returns
    house cusps in the sidereal (star-based) zodiac.
    
    Args:
        jd: Julian Day number
        latitude: Geographic latitude
        longitude: Geographic longitude
        house_system: House system to use
        ayanamsa: Ayanamsa for sidereal conversion
        
    Returns:
        HouseCusps with sidereal longitudes
    """
    # Get tropical cusps first
    tropical_cusps = get_house_cusps(jd, latitude, longitude, house_system)
    
    # Get ayanamsa to subtract
    ayan = get_ayanamsa_value(jd, ayanamsa)
    
    # Convert all values to sidereal
    def to_sidereal(lon: float) -> float:
        return (lon - ayan) % 360
    
    return HouseCusps(
        cusps=tuple(to_sidereal(c) for c in tropical_cusps.cusps),
        ascendant=to_sidereal(tropical_cusps.ascendant),
        mc=to_sidereal(tropical_cusps.mc),
        armc=tropical_cusps.armc,  # ARMC doesn't need conversion
        vertex=to_sidereal(tropical_cusps.vertex),
        equatorial_ascendant=to_sidereal(tropical_cusps.equatorial_ascendant),
    )
