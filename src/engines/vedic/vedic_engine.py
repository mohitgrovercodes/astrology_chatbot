"""
Vedic Astrology Engine - Main Orchestrator
===========================================

This is the main entry point for all Vedic astrology calculations.
It orchestrates the four computational layers:

Layer 1: Ephemeris (from core) â†’ Raw planetary positions
Layer 2: Graha Stats â†’ Speed, retrograde, combustion
Layer 3: Rashi/Nakshatra Mapping â†’ Vedic position interpretation
Layer 4: Advanced â†’ Dashas, Vargas, Yogas, Aspects

Usage:
------
    from nakshatra_chatbot.engine.vedic import VedicEngine

    # Initialize engine
    engine = VedicEngine()
    
    # Generate complete chart
    chart = engine.generate_chart(
        birth_date=datetime(1990, 3, 15, 15, 30),
        latitude=26.9124,
        longitude=75.7873
    )
    
    # Access various calculations
    print(chart.lagna.rashi_name)
    print(chart.get_planet_position(CelestialBody.SUN))
    print(chart.dasha.get_current_mahadasha(datetime.now()))
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS
from src.engines.core.ephemeris import (
    Ayanamsa, HouseSystem,
    PlanetPosition, HouseCusps,
    get_all_sidereal_positions,
    get_house_cusps,
    get_ayanamsa_value,
)
from src.engines.core.datetime_utils import datetime_to_julian_day, julian_day_to_datetime
from src.engines.core.coordinates import GeoPosition, create_position

from src.engines.vedic.vedic_constants import Rashi, Nakshatra, VargaChart, Ayanamsa
from src.engines.vedic.graha_stats import AllGrahaStats, compute_all_graha_stats
from src.engines.vedic.rashi_nakshatra import VedicMapping, compute_vedic_mapping, LagnaData
from src.engines.vedic.dasha_systems import VimshottariDasha, compute_vimshottari_dasha
from src.engines.vedic.aspects_yogas import AspectGrid, YogaAnalysis, compute_aspect_grid, detect_all_yogas
from src.engines.vedic.divisional_charts import AllVargaPositions, compute_all_vargas


# =============================================================================
# MAIN DATA STRUCTURES
# =============================================================================

@dataclass
class BirthData:
    """
    Input birth data for chart calculation.
    """
    date: datetime
    latitude: float
    longitude: float
    timezone_str: Optional[str] = None
    altitude: float = 0.0
    
    @property
    def position(self) -> GeoPosition:
        return create_position(self.latitude, self.longitude, self.altitude)


@dataclass
class VedicChart:
    """
    Complete Vedic horoscope with all calculations.
    
    This is the main output of the Vedic Engine - a comprehensive
    data structure containing all computed astrological data.
    """
    # Input data
    birth_data: BirthData
    julian_day: float
    ayanamsa: Ayanamsa
    ayanamsa_value: float
    house_system: HouseSystem
    
    # Layer 1: Raw positions
    positions: Dict[CelestialBody, PlanetPosition]
    house_cusps: HouseCusps
    
    # Layer 2: Graha statistics
    graha_stats: AllGrahaStats
    
    # Layer 3: Vedic mapping
    vedic_mapping: VedicMapping
    
    # Layer 4: Advanced calculations
    dasha: VimshottariDasha
    aspects: AspectGrid
    yogas: YogaAnalysis
    vargas: Dict[CelestialBody, AllVargaPositions]
    
    # Convenience accessors
    @property
    def lagna(self) -> LagnaData:
        """Get Lagna (Ascendant) data."""
        return self.vedic_mapping.lagna
    
    @property
    def rashi(self) -> Rashi:
        """
        Get the native's Rashi (Moon Sign).
        
        In Vedic astrology, "Rashi" commonly refers to the Moon's sign,
        not the Sun's sign. This is the zodiac sign where the Moon was
        positioned at the time of birth.
        
        For Sun sign, use: chart.sun_sign
        For any planet's sign: chart.get_planet_rashi(planet)
        """
        return self.vedic_mapping.rashi_positions[CelestialBody.MOON].rashi
    
    @property
    def rashi_name(self) -> str:
        """Get the Rashi name (Moon Sign name)."""
        return self.rashi.name.title()
    
    @property
    def sun_sign(self) -> Rashi:
        """
        Get the Sun Sign (Western-style zodiac sign).
        
        Note: In Vedic astrology, Moon sign (Rashi) is more important.
        """
        return self.vedic_mapping.rashi_positions[CelestialBody.SUN].rashi
    
    @property
    def moon_nakshatra(self) -> Nakshatra:
        """Get the Moon's Nakshatra (birth star)."""
        return self.vedic_mapping.nakshatra_positions[CelestialBody.MOON].nakshatra
    
    def get_planet_rashi(self, body: CelestialBody) -> Rashi:
        """Get the Rashi for a planet."""
        return self.vedic_mapping.rashi_positions[body].rashi
    
    def get_planet_nakshatra(self, body: CelestialBody) -> Nakshatra:
        """Get the Nakshatra for a planet."""
        return self.vedic_mapping.nakshatra_positions[body].nakshatra
    
    def get_planet_house(self, body: CelestialBody) -> int:
        """Get the house number for a planet."""
        return self.vedic_mapping.bhava_placements[body].bhava
    
    def is_planet_retrograde(self, body: CelestialBody) -> bool:
        """Check if a planet is retrograde."""
        return self.graha_stats.is_retrograde(body)
    
    def is_planet_combust(self, body: CelestialBody) -> bool:
        """Check if a planet is combust."""
        return self.graha_stats.is_combust(body)
    
    def get_current_dasha(self, date: Optional[datetime] = None) -> Dict:
        """Get current Dasha periods."""
        target = date or datetime.now()
        return self.dasha.get_current_periods(target)
    
    def get_planets_in_house(self, house: int) -> List[CelestialBody]:
        """Get planets in a specific house."""
        return self.vedic_mapping.get_planets_in_house(house)
    
    def get_present_yogas(self) -> List:
        """Get all yogas that are present in this chart."""
        return [y for y in self.yogas.detected_yogas if y.is_present]


# =============================================================================
# VEDIC ENGINE CLASS
# =============================================================================

class VedicEngine:
    """
    Main Vedic Astrology Calculation Engine.
    
    This class orchestrates all calculations and provides a clean
    interface for generating Vedic horoscopes.
    
    Attributes:
        ayanamsa: Default Ayanamsa to use (default: Lahiri)
        house_system: Default house system (default: Whole Sign)
    """
    
    def __init__(
        self,
        ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
        house_system: HouseSystem = HouseSystem.WHOLE_SIGN
    ):
        """
        Initialize the Vedic Engine.
        
        Args:
            ayanamsa: Ayanamsa for sidereal calculations
            house_system: House system to use
        """
        self.ayanamsa = ayanamsa
        self.house_system = house_system
    
    def generate_chart(
        self,
        birth_date: datetime,
        latitude: float,
        longitude: float,
        timezone_str: Optional[str] = None,
        altitude: float = 0.0,
        ayanamsa: Optional[Ayanamsa] = None,
        house_system: Optional[HouseSystem] = None,
    ) -> VedicChart:
        """
        Generate a complete Vedic horoscope.
        
        This is the main entry point. It runs all four computational
        layers and returns a comprehensive VedicChart object.
        
        Args:
            birth_date: Date and time of birth
            latitude: Birth place latitude
            longitude: Birth place longitude
            timezone_str: Timezone string (or auto-detect from coordinates)
            altitude: Altitude in meters (default: 0)
            ayanamsa: Override default Ayanamsa
            house_system: Override default house system
            
        Returns:
            VedicChart with all calculations
            
        Example:
            >>> engine = VedicEngine()
            >>> chart = engine.generate_chart(
            ...     birth_date=datetime(1990, 3, 15, 15, 30),
            ...     latitude=26.9124,
            ...     longitude=75.7873
            ... )
            >>> print(f"Lagna: {chart.lagna.rashi_name}")
            >>> print(f"Moon: {chart.get_planet_rashi(CelestialBody.MOON)}")
        """
        # Use provided or default settings
        ayanamsa = ayanamsa or self.ayanamsa
        house_system = house_system or self.house_system
        
        # Create birth data object
        birth_data = BirthData(
            date=birth_date,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone_str,
            altitude=altitude
        )
        
        # Step 1: Convert to Julian Day
        jd = datetime_to_julian_day(
            birth_date,
            timezone_str=timezone_str,
            latitude=latitude,
            longitude=longitude
        )
        
        # Step 2: Get ayanamsa value
        ayanamsa_value = get_ayanamsa_value(jd, ayanamsa)
        
        # Step 3: Calculate house cusps (for ascendant)
        cusps = get_house_cusps(jd, latitude, longitude, house_system)
        ascendant_longitude = (cusps.ascendant - ayanamsa_value) % 360  # Sidereal
        
        # Layer 1: Get planetary positions (sidereal)
        positions = get_all_sidereal_positions(jd, VEDIC_GRAHAS, ayanamsa)
        
        # Layer 2: Compute graha statistics
        graha_stats = compute_all_graha_stats(jd, VEDIC_GRAHAS, ayanamsa)
        
        # Layer 3: Vedic mapping
        vedic_mapping = compute_vedic_mapping(
            positions, ascendant_longitude, house_system
        )
        
        # Layer 4A: Dasha calculation (based on Moon's nakshatra)
        moon_pos = positions[CelestialBody.MOON]
        dasha = compute_vimshottari_dasha(birth_date, moon_pos.longitude)
        
        # Layer 4B: Aspects
        aspects = compute_aspect_grid(
            vedic_mapping.bhava_placements,
            vedic_mapping.house_occupancy
        )
        
        # Layer 4C: Yoga detection
        yogas = detect_all_yogas(vedic_mapping)
        
        # Layer 4D: Divisional Charts (All 16)
        graha_longitudes = {body: pos.longitude for body, pos in positions.items()}
        vargas = compute_all_vargas(graha_longitudes, tuple(VargaChart))
        
        return VedicChart(
            birth_data=birth_data,
            julian_day=jd,
            ayanamsa=ayanamsa,
            ayanamsa_value=ayanamsa_value,
            house_system=house_system,
            positions=positions,
            house_cusps=cusps,
            graha_stats=graha_stats,
            vedic_mapping=vedic_mapping,
            dasha=dasha,
            aspects=aspects,
            yogas=yogas,
            vargas=vargas
        )
    
    def compute_transits(
        self,
        chart: VedicChart,
        transit_date: datetime
    ) -> Dict[CelestialBody, PlanetPosition]:
        """
        Compute current planetary transits relative to birth chart.
        
        Args:
            chart: The birth chart
            transit_date: Date for transit calculation
            
        Returns:
            Dictionary of transit positions
        """
        jd = datetime_to_julian_day(
            transit_date,
            latitude=chart.birth_data.latitude,
            longitude=chart.birth_data.longitude
        )
        return get_all_sidereal_positions(jd, VEDIC_GRAHAS, chart.ayanamsa)
    
    def get_transit_to_natal_houses(
        self,
        chart: VedicChart,
        transit_date: datetime
    ) -> Dict[CelestialBody, int]:
        """
        Get which natal house each transit planet is in.
        
        Args:
            chart: The birth chart
            transit_date: Date for transit calculation
            
        Returns:
            Dictionary mapping transit planets to natal houses
        """
        transits = self.compute_transits(chart, transit_date)
        lagna_sign = chart.lagna.rashi.value
        
        result = {}
        for body, pos in transits.items():
            planet_sign = int(pos.longitude // 30) % 12
            house = ((planet_sign - lagna_sign) % 12) + 1
            result[body] = house
        
        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_vedic_chart(
    birth_date: datetime,
    latitude: float,
    longitude: float,
    timezone_str: Optional[str] = None,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
    house_system: HouseSystem = HouseSystem.WHOLE_SIGN
) -> VedicChart:
    """
    Convenience function to generate a Vedic chart without instantiating engine.
    
    Args:
        birth_date: Date and time of birth
        latitude: Birth place latitude
        longitude: Birth place longitude
        timezone_str: Timezone string (optional)
        ayanamsa: Ayanamsa to use
        house_system: House system to use
        
    Returns:
        VedicChart with all calculations
    """
    engine = VedicEngine(ayanamsa=ayanamsa, house_system=house_system)
    return engine.generate_chart(
        birth_date=birth_date,
        latitude=latitude,
        longitude=longitude,
        timezone_str=timezone_str
    )
