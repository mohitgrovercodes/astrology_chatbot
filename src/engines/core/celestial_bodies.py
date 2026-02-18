# src/engines/core/celestial_bodies.py
# src\engines\core\celestial_bodies.py
"""
Celestial Bodies - Planets, Nodes, and Points Used in Astrology
================================================================

This module defines all celestial bodies used in both Vedic and Western
astrology. It uses Swiss Ephemeris body IDs for direct compatibility
with the pyswisseph library.

Key Concepts:
------------
- Grahas (Vedic): The 9 influential bodies - Sun, Moon, Mars, Mercury,
  Jupiter, Venus, Saturn, Rahu, and Ketu
- Nodes: Rahu (North Node) and Ketu (South Node) - the Moon's orbital
  intersection points with the ecliptic
- Outer Planets: Uranus, Neptune, Pluto - used in Western astrology

Swiss Ephemeris Body IDs:
------------------------
The CelestialBody enum values match Swiss Ephemeris constants for
direct compatibility. See: https://www.astro.com/swisseph/
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple, Dict, Optional


class CelestialBody(IntEnum):
    """
    Celestial bodies used in astrological calculations.
    
    The integer values correspond to Swiss Ephemeris body IDs,
    allowing direct use with the swisseph library.
    
    Note on Nodes:
    - MEAN_NODE (10): Average position of the Moon's ascending node
    - TRUE_NODE (11): Actual oscillating position of the ascending node
    - For Vedic astrology, we typically use MEAN_NODE as Rahu
    - KETU (111) is a custom ID - calculated as 180Â° opposite to Rahu
    """
    # Classical planets (visible to naked eye)
    SUN = 0
    MOON = 1
    MERCURY = 2
    VENUS = 3
    MARS = 4
    JUPITER = 5
    SATURN = 6
    
    # Outer planets (discovered with telescopes)
    URANUS = 7
    NEPTUNE = 8
    PLUTO = 9
    
    # Lunar nodes
    MEAN_NODE = 10      # Mean North Node (Rahu)
    TRUE_NODE = 11      # True/Osculating North Node
    
    # Other points
    MEAN_APOGEE = 12    # Black Moon Lilith (Mean)
    OSCU_APOGEE = 13    # Black Moon Lilith (Osculating)
    CHIRON = 15         # Centaur/asteroid
    
    # Vedic aliases - for clarity in Jyotish calculations
    RAHU = 10           # Same as MEAN_NODE
    KETU = 111          # Custom ID - South Node (calculated as Rahu + 180Â°)
    
    @property
    def is_vedic_graha(self) -> bool:
        """Check if this body is one of the 9 Vedic Grahas."""
        return self in VEDIC_GRAHAS
    
    @property
    def is_outer_planet(self) -> bool:
        """Check if this is a modern outer planet."""
        return self in (self.URANUS, self.NEPTUNE, self.PLUTO)
    
    @property
    def is_node(self) -> bool:
        """Check if this is a lunar node."""
        return self in (self.MEAN_NODE, self.TRUE_NODE, self.RAHU, self.KETU)
    
    @property
    def is_luminary(self) -> bool:
        """Check if this is the Sun or Moon."""
        return self in (self.SUN, self.MOON)


@dataclass(frozen=True)
class PlanetInfo:
    """
    Comprehensive information about a celestial body.
    
    This dataclass stores both astronomical and astrological data
    for each planet, supporting both Vedic and Western traditions.
    
    Attributes:
        body: The CelestialBody enum value
        english_name: Common English name
        sanskrit_name: Traditional Sanskrit/Hindi name for Vedic astrology
        symbol: Unicode astrological symbol
        is_graha: Whether this is one of the 9 Vedic Grahas
        is_benefic: Natural benefic status (True=benefic, False=malefic, None=neutral)
        orbital_period_days: Approximate orbital period around the Sun
    """
    body: CelestialBody
    english_name: str
    sanskrit_name: str
    symbol: str
    is_graha: bool = True
    is_benefic: Optional[bool] = None
    orbital_period_days: Optional[float] = None


# Complete planet information database
PLANET_INFO: Dict[CelestialBody, PlanetInfo] = {
    CelestialBody.SUN: PlanetInfo(
        CelestialBody.SUN, "Sun", "Surya", "â˜‰",
        is_graha=True, is_benefic=None, orbital_period_days=365.25
    ),
    CelestialBody.MOON: PlanetInfo(
        CelestialBody.MOON, "Moon", "Chandra", "â˜½",
        is_graha=True, is_benefic=True, orbital_period_days=27.32
    ),
    CelestialBody.MARS: PlanetInfo(
        CelestialBody.MARS, "Mars", "Mangala", "â™‚",
        is_graha=True, is_benefic=False, orbital_period_days=686.98
    ),
    CelestialBody.MERCURY: PlanetInfo(
        CelestialBody.MERCURY, "Mercury", "Budha", "â˜¿",
        is_graha=True, is_benefic=None, orbital_period_days=87.97
    ),
    CelestialBody.JUPITER: PlanetInfo(
        CelestialBody.JUPITER, "Jupiter", "Guru", "â™ƒ",
        is_graha=True, is_benefic=True, orbital_period_days=4332.59
    ),
    CelestialBody.VENUS: PlanetInfo(
        CelestialBody.VENUS, "Venus", "Shukra", "â™€",
        is_graha=True, is_benefic=True, orbital_period_days=224.70
    ),
    CelestialBody.SATURN: PlanetInfo(
        CelestialBody.SATURN, "Saturn", "Shani", "â™„",
        is_graha=True, is_benefic=False, orbital_period_days=10759.22
    ),
    CelestialBody.RAHU: PlanetInfo(
        CelestialBody.RAHU, "Rahu", "Rahu", "â˜Š",
        is_graha=True, is_benefic=False, orbital_period_days=6793.48
    ),
    CelestialBody.KETU: PlanetInfo(
        CelestialBody.KETU, "Ketu", "Ketu", "â˜‹",
        is_graha=True, is_benefic=False, orbital_period_days=6793.48
    ),
    CelestialBody.URANUS: PlanetInfo(
        CelestialBody.URANUS, "Uranus", "Uranus", "â™…",
        is_graha=False, is_benefic=None, orbital_period_days=30688.5
    ),
    CelestialBody.NEPTUNE: PlanetInfo(
        CelestialBody.NEPTUNE, "Neptune", "Neptune", "â™†",
        is_graha=False, is_benefic=None, orbital_period_days=60182.0
    ),
    CelestialBody.PLUTO: PlanetInfo(
        CelestialBody.PLUTO, "Pluto", "Pluto", "â™‡",
        is_graha=False, is_benefic=None, orbital_period_days=90560.0
    ),
    CelestialBody.CHIRON: PlanetInfo(
        CelestialBody.CHIRON, "Chiron", "Chiron", "âš·",
        is_graha=False, is_benefic=None, orbital_period_days=18500.0
    ),
}


def get_planet_info(body: CelestialBody) -> PlanetInfo:
    """
    Get comprehensive information about a celestial body.
    
    Args:
        body: The celestial body to look up
        
    Returns:
        PlanetInfo dataclass with all available information
        
    Example:
        >>> info = get_planet_info(CelestialBody.MARS)
        >>> print(f"{info.sanskrit_name} ({info.symbol})")
        Mangala (â™‚)
    """
    return PLANET_INFO.get(
        body,
        PlanetInfo(body, body.name.title(), body.name.title(), "?", is_graha=False)
    )


# The 9 Vedic Grahas (planets) in traditional order
VEDIC_GRAHAS: Tuple[CelestialBody, ...] = (
    CelestialBody.SUN,
    CelestialBody.MOON,
    CelestialBody.MARS,
    CelestialBody.MERCURY,
    CelestialBody.JUPITER,
    CelestialBody.VENUS,
    CelestialBody.SATURN,
    CelestialBody.RAHU,
    CelestialBody.KETU,
)

# Classical 7 planets (excluding Rahu/Ketu)
CLASSICAL_PLANETS: Tuple[CelestialBody, ...] = (
    CelestialBody.SUN,
    CelestialBody.MOON,
    CelestialBody.MARS,
    CelestialBody.MERCURY,
    CelestialBody.JUPITER,
    CelestialBody.VENUS,
    CelestialBody.SATURN,
)

# Western planets including outer planets
WESTERN_PLANETS: Tuple[CelestialBody, ...] = (
    CelestialBody.SUN,
    CelestialBody.MOON,
    CelestialBody.MERCURY,
    CelestialBody.VENUS,
    CelestialBody.MARS,
    CelestialBody.JUPITER,
    CelestialBody.SATURN,
    CelestialBody.URANUS,
    CelestialBody.NEPTUNE,
    CelestialBody.PLUTO,
)

# Natural benefics in Vedic astrology
NATURAL_BENEFICS: Tuple[CelestialBody, ...] = (
    CelestialBody.JUPITER,
    CelestialBody.VENUS,
    CelestialBody.MOON,  # When waxing
    CelestialBody.MERCURY,  # When unafflicted
)

# Natural malefics in Vedic astrology
NATURAL_MALEFICS: Tuple[CelestialBody, ...] = (
    CelestialBody.SUN,
    CelestialBody.MARS,
    CelestialBody.SATURN,
    CelestialBody.RAHU,
    CelestialBody.KETU,
)
