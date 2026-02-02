"""
Western Astrology Engine - Main Orchestrator
============================================

This is the main entry point for all Western astrology calculations.
It orchestrates multiple calculation layers to produce a complete
Western natal chart.

Calculation Layers:
------------------
Layer 1: Ephemeris â†’ Raw planetary positions (tropical)
Layer 2: Signs â†’ Zodiac sign placements
Layer 3: Houses â†’ House placements and cusps
Layer 4: Aspects â†’ Angular relationships between planets
Layer 5: Dignities â†’ Essential dignity analysis

Usage:
------
    from jyotish_ai.engine.western import WesternAstroEngine
    from datetime import datetime
    
    # Initialize engine
    engine = WesternAstroEngine()
    
    # Generate complete chart
    chart = engine.generate_chart(
        birth_datetime=datetime(1990, 3, 15, 15, 30),
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York"
    )
    
    # Access various calculations
    print(f"Sun Sign: {chart.sun_sign}")
    print(f"Ascendant: {chart.ascendant}")
    print(f"Moon in house: {chart.get_planet_house(CelestialBody.MOON)}")
    
    # Iterate over aspects
    for aspect in chart.aspects.aspects:
        print(f"{aspect}")
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.engines.core.celestial_bodies import CelestialBody, WESTERN_PLANETS
from src.engines.core.ephemeris import (
    HouseSystem, PlanetPosition, HouseCusps,
    get_all_positions, get_house_cusps
)
from src.engines.core.datetime_utils import datetime_to_julian_day
from src.engines.core.coordinates import GeoPosition, create_position

from src.engines.western.western_constants import ZodiacSign, AspectType
from src.engines.western.western_signs import longitude_to_sign, get_sign_info, format_position
from src.engines.western.western_aspects import AspectGrid, Aspect, compute_aspect_grid
from src.engines.western.western_houses import (
    HousePlacement, HouseOccupancy,
    compute_all_house_placements, compute_house_occupancy,
    get_planets_in_house, get_angular_planets
)
from src.engines.western.western_dignities import (
    PlanetDignity, DignityAnalysis,
    compute_dignity_analysis
)


# =============================================================================
# MAIN DATA STRUCTURES
# =============================================================================

@dataclass
class BirthData:
    """
    Input birth data for chart calculation.
    
    Attributes:
        datetime: Date and time of birth
        latitude: Geographic latitude
        longitude: Geographic longitude
        timezone: Timezone string (e.g., "America/New_York")
        altitude: Altitude in meters (default: 0)
    """
    datetime: datetime
    latitude: float
    longitude: float
    timezone: Optional[str] = None
    altitude: float = 0.0
    
    @property
    def position(self) -> GeoPosition:
        """Get geographic position."""
        return create_position(self.latitude, self.longitude, self.altitude)


@dataclass
class WesternChart:
    """
    Complete Western natal chart with all calculations.
    
    This is the main output of the Western Engine - a comprehensive
    data structure containing all computed astrological data.
    
    Attributes:
        birth_data: Input birth information
        julian_day: Julian Day number for birth moment
        house_system: House system used
        positions: Raw planetary positions (tropical)
        house_cusps: House cusp positions
        house_placements: Planets in houses
        house_occupancy: Which planets are in each house
        aspects: Complete aspect grid
        dignities: Essential dignity analysis
    """
    # Input data
    birth_data: BirthData
    julian_day: float
    house_system: HouseSystem
    
    # Layer 1: Raw positions (tropical)
    positions: Dict[CelestialBody, PlanetPosition]
    house_cusps: HouseCusps
    
    # Layer 2: House placements
    house_placements: Dict[CelestialBody, HousePlacement]
    house_occupancy: Dict[int, HouseOccupancy]
    
    # Layer 3: Aspects
    aspects: AspectGrid
    
    # Layer 4: Dignities
    dignities: DignityAnalysis
    
    # =========================================================================
    # CONVENIENCE ACCESSORS - PRIMARY CHART POINTS
    # =========================================================================
    
    @property
    def sun_sign(self) -> ZodiacSign:
        """
        Get the Sun sign (Western zodiac sign).
        
        In Western astrology, this is the primary sign used for
        horoscopes and popular astrology.
        """
        return longitude_to_sign(self.positions[CelestialBody.SUN].longitude)
    
    @property
    def sun_sign_name(self) -> str:
        """Get the Sun sign name."""
        return self.sun_sign.name.title()
    
    @property
    def moon_sign(self) -> ZodiacSign:
        """Get the Moon sign."""
        return longitude_to_sign(self.positions[CelestialBody.MOON].longitude)
    
    @property
    def moon_sign_name(self) -> str:
        """Get the Moon sign name."""
        return self.moon_sign.name.title()
    
    @property
    def ascendant(self) -> float:
        """Get the Ascendant (Rising Sign) longitude."""
        return self.house_cusps.ascendant
    
    @property
    def ascendant_sign(self) -> ZodiacSign:
        """Get the Ascendant (Rising) sign."""
        return longitude_to_sign(self.ascendant)
    
    @property
    def ascendant_sign_name(self) -> str:
        """Get the Ascendant sign name."""
        return self.ascendant_sign.name.title()
    
    @property
    def midheaven(self) -> float:
        """Get the Midheaven (MC) longitude."""
        return self.house_cusps.mc
    
    @property
    def midheaven_sign(self) -> ZodiacSign:
        """Get the Midheaven sign."""
        return longitude_to_sign(self.midheaven)
    
    @property
    def descendant(self) -> float:
        """Get the Descendant (7th house cusp) longitude."""
        return self.house_cusps.descendant
    
    @property
    def ic(self) -> float:
        """Get the IC (4th house cusp) longitude."""
        return self.house_cusps.ic
    
    def get_house_cusp(self, house: int) -> float:
        """Get the longitude of a specific house cusp (1-12)."""
        return self.house_cusps.get_house_cusp(house)
    
    # =========================================================================
    # PLANET ACCESSORS
    # =========================================================================
    
    def get_planet_position(self, planet: CelestialBody) -> PlanetPosition:
        """Get raw position data for a planet."""
        return self.positions[planet]
    
    def get_planet_sign(self, planet: CelestialBody) -> ZodiacSign:
        """Get the sign a planet is in."""
        return longitude_to_sign(self.positions[planet].longitude)
    
    def get_planet_house(self, planet: CelestialBody) -> int:
        """Get the house number a planet is in."""
        return self.house_placements[planet].house
    
    @property
    def dignity_score(self) -> int:
        """Get the total essential dignity score for the chart."""
        return sum(d.score for d in self.dignities.dignities.values())
    
    def get_planet_dignity(self, planet: CelestialBody) -> PlanetDignity:
        """Get essential dignity for a planet."""
        dignity = self.dignities.dignities.get(planet)
        if dignity:
            return dignity
            
        # Fallback if not calculated
        return PlanetDignity(
            planet=planet,
            sign=longitude_to_sign(self.positions[planet].longitude),
            dignity_type=EssentialDignity.NEUTRAL,
            score=0,
            is_dignified=False,
            is_debilitated=False,
            description="Dignity not calculated"
        )
    
    def format_planet_position(
        self,
        planet: CelestialBody,
        include_seconds: bool = False
    ) -> str:
        """
        Format a planet's position as human-readable string.
        
        Example: "15Â°30' Taurus"
        """
        longitude = self.positions[planet].longitude
        return format_position(longitude, include_seconds)
    
    def is_planet_retrograde(self, planet: CelestialBody) -> bool:
        """Check if a planet is retrograde."""
        return self.positions[planet].is_retrograde
    
    # =========================================================================
    # HOUSE ACCESSORS
    # =========================================================================
    
    def get_planets_in_house(self, house: int) -> List[CelestialBody]:
        """Get all planets in a specific house."""
        return list(self.house_occupancy[house].planets)
    
    def get_house_cusp(self, house: int) -> float:
        """Get the cusp longitude of a specific house."""
        return self.house_cusps.get_house_cusp(house)
    
    def get_house_cusp_sign(self, house: int) -> ZodiacSign:
        """Get the sign on a house cusp."""
        return self.house_occupancy[house].cusp_sign
    
    def get_empty_houses(self) -> List[int]:
        """Get list of houses with no planets."""
        return [
            house for house, occ in self.house_occupancy.items()
            if occ.is_empty
        ]
    
    def get_angular_planets(self) -> List[CelestialBody]:
        """Get planets in angular houses (1, 4, 7, 10)."""
        return get_angular_planets(self.house_placements)
    
    # =========================================================================
    # ASPECT ACCESSORS
    # =========================================================================
    
    def get_aspects_to_planet(self, planet: CelestialBody) -> List[Aspect]:
        """Get all aspects involving a specific planet."""
        return self.aspects.get_planet_aspects(planet)
    
    def get_aspects_by_type(self, aspect_type: AspectType) -> List[Aspect]:
        """Get all aspects of a specific type."""
        return self.aspects.by_type.get(aspect_type, [])
    
    def has_aspect_between(
        self,
        planet1: CelestialBody,
        planet2: CelestialBody,
        aspect_type: Optional[AspectType] = None
    ) -> bool:
        """
        Check if two planets have an aspect.
        
        Args:
            planet1: First planet
            planet2: Second planet
            aspect_type: Specific aspect type (or any if None)
        """
        return self.aspects.has_aspect_between(planet1, planet2, aspect_type)
    
    @property
    def exact_aspects(self) -> List[Aspect]:
        """Get all exact aspects (orb < 1Â°)."""
        return self.aspects.exact_aspects
    
    @property
    def major_aspects(self) -> List[Aspect]:
        """Get all major (Ptolemaic) aspects."""
        return list(self.aspects.major_aspects)
    
    # =========================================================================
    # DIGNITY ACCESSORS
    # =========================================================================
    
    @property
    def dignified_planets(self) -> List[Tuple[CelestialBody, PlanetDignity]]:
        """Get planets in domicile or exaltation."""
        return list(self.dignities.dignified_planets)
    
    @property
    def debilitated_planets(self) -> List[Tuple[CelestialBody, PlanetDignity]]:
        """Get planets in detriment or fall."""
        return list(self.dignities.debilitated_planets)
    
    @property
    def dignity_score(self) -> int:
        """Get total dignity score for the chart."""
        return self.dignities.total_score
    
    # =========================================================================
    # CHART SUMMARY
    # =========================================================================
    
    def summary(self) -> str:
        """
        Get a human-readable summary of the chart.
        
        Returns:
            Multi-line string with key chart features
        """
        lines = [
            "=" * 60,
            "WESTERN NATAL CHART",
            "=" * 60,
            f"Birth: {self.birth_data.datetime}",
            f"Location: {self.birth_data.latitude:.4f}, {self.birth_data.longitude:.4f}",
            "",
            "PRIMARY POINTS:",
            f"  Sun Sign: {self.sun_sign_name} ({self.format_planet_position(CelestialBody.SUN)})",
            f"  Moon Sign: {self.moon_sign_name} ({self.format_planet_position(CelestialBody.MOON)})",
            f"  Ascendant: {self.ascendant_sign_name} ({format_position(self.ascendant)})",
            f"  Midheaven: {self.midheaven_sign.name.title()} ({format_position(self.midheaven)})",
            "",
            f"ASPECTS: {self.aspects.aspect_count} total",
            f"  Major aspects: {len(self.aspects.major_aspects)}",
            f"  Exact aspects: {len(self.exact_aspects)}",
            "",
            f"DIGNITIES:",
            f"  Total score: {self.dignity_score}",
            f"  Dignified planets: {len(self.dignified_planets)}",
            f"  Debilitated planets: {len(self.debilitated_planets)}",
            "=" * 60,
        ]
        return "\n".join(lines)


# =============================================================================
# WESTERN ENGINE CLASS
# =============================================================================

class WesternAstroEngine:
    """
    Main Western Astrology Calculation Engine.
    
    This class orchestrates all calculations and provides a clean
    interface for generating Western natal charts.
    
    Attributes:
        house_system: Default house system (default: Placidus)
        include_outer_planets: Whether to include Uranus, Neptune, Pluto
    """
    
    def __init__(
        self,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
        include_outer_planets: bool = True,
    ):
        """
        Initialize the Western Engine.
        
        Args:
            house_system: House system to use (default: Placidus)
            include_outer_planets: Include modern planets (default: True)
        """
        self.house_system = house_system
        self.include_outer_planets = include_outer_planets
    
    def generate_chart(
        self,
        birth_datetime: datetime,
        latitude: float,
        longitude: float,
        timezone: Optional[str] = None,
        altitude: float = 0.0,
        house_system: Optional[HouseSystem] = None,
    ) -> WesternChart:
        """
        Generate a complete Western natal chart.
        
        This is the main entry point. It runs all calculation layers
        and returns a comprehensive WesternChart object.
        
        Args:
            birth_datetime: Date and time of birth
            latitude: Birth place latitude (-90 to +90)
            longitude: Birth place longitude (-180 to +180)
            timezone: Timezone string (e.g., "America/New_York")
            altitude: Altitude in meters (default: 0)
            house_system: Override default house system
            
        Returns:
            WesternChart with all calculations
            
        Example:
            >>> engine = WesternEngine()
            >>> chart = engine.generate_chart(
            ...     birth_datetime=datetime(1990, 3, 15, 15, 30),
            ...     latitude=40.7128,
            ...     longitude=-74.0060,
            ...     timezone="America/New_York"
            ... )
            >>> print(f"Sun Sign: {chart.sun_sign_name}")
            >>> print(f"Ascendant: {chart.ascendant_sign_name}")
        """
        # Use provided or default settings
        house_system = house_system or self.house_system
        
        # Create birth data object
        birth_data = BirthData(
            datetime=birth_datetime,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            altitude=altitude
        )
        
        # Step 1: Convert to Julian Day
        jd = datetime_to_julian_day(
            birth_datetime,
            timezone_str=timezone,
            latitude=latitude,
            longitude=longitude
        )
        
        # Step 2: Determine which planets to calculate
        if self.include_outer_planets:
            planets = WESTERN_PLANETS
        else:
            # Classical 7 planets only
            planets = tuple([
                p for p in WESTERN_PLANETS
                if p not in (CelestialBody.URANUS, CelestialBody.NEPTUNE, CelestialBody.PLUTO)
            ])
        
        # Layer 1: Get planetary positions (tropical - no ayanamsa)
        positions = get_all_positions(jd, planets)
        
        # Layer 2: Calculate house cusps
        cusps = get_house_cusps(jd, latitude, longitude, house_system)
        
        # Layer 3: House placements
        house_placements = compute_all_house_placements(
            positions, cusps, house_system
        )
        house_occupancy = compute_house_occupancy(house_placements, cusps)
        
        # Layer 4: Aspects
        aspects = compute_aspect_grid(positions)
        
        # Layer 5: Dignities
        dignities = compute_dignity_analysis(positions)
        
        return WesternChart(
            birth_data=birth_data,
            julian_day=jd,
            house_system=house_system,
            positions=positions,
            house_cusps=cusps,
            house_placements=house_placements,
            house_occupancy=house_occupancy,
            aspects=aspects,
            dignities=dignities,
        )
    
    def compute_transits(
        self,
        chart: WesternChart,
        transit_datetime: datetime
    ) -> Dict[CelestialBody, PlanetPosition]:
        """
        Compute current planetary transits.
        
        Args:
            chart: The natal chart
            transit_datetime: Date/time for transit calculation
            
        Returns:
            Dictionary of current planet positions
        """
        jd = datetime_to_julian_day(
            transit_datetime,
            latitude=chart.birth_data.latitude,
            longitude=chart.birth_data.longitude
        )
        
        if self.include_outer_planets:
            planets = WESTERN_PLANETS
        else:
            planets = tuple([
                p for p in WESTERN_PLANETS
                if p not in (CelestialBody.URANUS, CelestialBody.NEPTUNE, CelestialBody.PLUTO)
            ])
        
        return get_all_positions(jd, planets)
    
    def get_transit_to_natal_aspects(
        self,
        chart: WesternChart,
        transit_datetime: datetime
    ) -> List[Aspect]:
        """
        Calculate aspects between transit planets and natal planets.
        
        Args:
            chart: The natal chart
            transit_datetime: Date/time for transits
            
        Returns:
            List of aspects between transit and natal positions
        """
        from src.engines.western.western_aspects import calculate_all_aspects
        
        # Get transit positions
        transits = self.compute_transits(chart, transit_datetime)
        
        # Create combined position dict with prefixes
        # This is a simplified version - a full implementation would
        # need to track which is natal vs transit
        aspects = []
        
        # For now, just return empty - full transit-to-natal aspect
        # calculation would require additional logic
        # TODO: Implement transit-to-natal aspect calculation
        
        return aspects


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_western_chart(
    birth_datetime: datetime,
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None,
    house_system: HouseSystem = HouseSystem.PLACIDUS
) -> WesternChart:
    """
    Convenience function to generate a Western chart without instantiating engine.
    
    Args:
        birth_datetime: Date and time of birth
        latitude: Birth place latitude
        longitude: Birth place longitude
        timezone: Timezone string (optional)
        house_system: House system to use (default: Placidus)
        
    Returns:
        WesternChart with all calculations
        
    Example:
        >>> chart = generate_western_chart(
        ...     birth_datetime=datetime(1990, 3, 15, 15, 30),
        ...     latitude=40.7128,
        ...     longitude=-74.0060,
        ...     timezone="America/New_York"
        ... )
        >>> print(chart.summary())
    """
    engine = WesternAstroEngine(house_system=house_system)
    return engine.generate_chart(
        birth_datetime=birth_datetime,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone
    )


def quick_chart(
    year: int,
    month: int,
    day: int,
    hour: int = 12,
    minute: int = 0,
    latitude: float = 0.0,
    longitude: float = 0.0,
    timezone: str = "UTC"
) -> WesternChart:
    """
    Quick chart generation with simple inputs.
    
    Args:
        year: Birth year
        month: Birth month (1-12)
        day: Birth day (1-31)
        hour: Birth hour (0-23, default: 12)
        minute: Birth minute (0-59, default: 0)
        latitude: Birth latitude (default: 0)
        longitude: Birth longitude (default: 0)
        timezone: Timezone string (default: "UTC")
        
    Returns:
        WesternChart
    """
    birth_datetime = datetime(year, month, day, hour, minute)
    return generate_western_chart(
        birth_datetime, latitude, longitude, timezone
    )
