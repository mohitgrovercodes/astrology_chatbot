# src/engines/vedic/vedic_engine.py
# src\engines\vedic\vedic_engine.py
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
from typing import Dict, List, Optional, Tuple, Any
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize chart to a dictionary for caching."""
        import json
        from enum import Enum
        from dataclasses import is_dataclass, asdict
        
        def _serialize(obj):
            if is_dataclass(obj):
                result = {}
                for field in obj.__dataclass_fields__:
                    val = getattr(obj, field)
                    result[field] = _serialize(val)
                return result
            elif isinstance(obj, Enum):
                return {"__enum__": obj.__class__.__name__, "value": obj.value}
            elif isinstance(obj, datetime):
                return {"__datetime__": obj.isoformat()}
            elif isinstance(obj, dict):
                return {str(k.name if isinstance(k, Enum) else k): _serialize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_serialize(v) for v in obj]
            return obj

        return _serialize(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VedicChart':
        """Reconstruct chart from dictionary."""
        from src.engines.core.celestial_bodies import CelestialBody
        from src.engines.vedic.vedic_constants import Rashi, Nakshatra, VargaChart
        
        def _deserialize(obj):
            if isinstance(obj, dict):
                if "__datetime__" in obj:
                    return datetime.fromisoformat(obj["__datetime__"])
                if "__enum__" in obj:
                    enum_name = obj["__enum__"]
                    val = obj["value"]
                    if enum_name == "CelestialBody": return CelestialBody(val)
                    if enum_name == "Rashi": return Rashi(val)
                    if enum_name == "Nakshatra": return Nakshatra(val)
                    if enum_name == "Ayanamsa": return Ayanamsa(val)
                    if enum_name == "HouseSystem": return HouseSystem(val)
                    if enum_name == "VargaChart": return VargaChart(val)
                    if enum_name == "YogaCategory": return YogaCategory(val)
                return {k: _deserialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_deserialize(v) for v in obj]
            return obj
            
        # This is a complex reconstruction. For now, we'll store and return a simplified
        # version or just the serialized dict for the LLM. 
        # However, to maintain compatibility with the generate_chart return type,
        # we'll use a trick: return a Namespace-like object if full reconstruction is too brittle,
        # OR perform full reconstruction here. 
        # Given the "Principal Engineer" persona, I will implement full reconstruction.
        
        # NOTE: Full reconstruction requires importing all nested classes.
        # This implementation is a placeholder for the logic.
        return _reconstruct_vedic_chart(data)

def _reconstruct_vedic_chart(data: Dict[str, Any]) -> VedicChart:
    """Helper to reconstruct the complex VedicChart object with strict schema adherence."""
    from src.engines.core.celestial_bodies import CelestialBody
    from src.engines.core.ephemeris import (
        PlanetPosition, HouseCusps, Ayanamsa, HouseSystem
    )
    from src.engines.vedic.vedic_constants import Rashi, Nakshatra, VargaChart
    from src.engines.vedic.graha_stats import (
        AllGrahaStats, GrahaMotion, CombustionData, PlanetaryWar,
        MotionStatus, CombustionStatus
    )
    from src.engines.vedic.rashi_nakshatra import (
        VedicMapping, LagnaData, BhavaPlacement, DignityStatus, 
        RashiPosition, NakshatraPosition, Dignity, Relationship
    )
    from src.engines.vedic.dasha_systems import VimshottariDasha, DashaBalance, DashaPeriod
    from src.engines.vedic.aspects_yogas import (
        AspectGrid, YogaAnalysis, Aspect, YogaDetection, YogaCategory
    )
    
    def _d(obj):
        """Deep deserialization helper for markers (__datetime__, __enum__)."""
        if isinstance(obj, dict):
            if "__datetime__" in obj:
                return datetime.fromisoformat(obj["__datetime__"])
            if "__enum__" in obj:
                ename, evalue = obj["__enum__"], obj["value"]
                # Resolve Enum classes
                if ename == "CelestialBody": return CelestialBody(evalue)
                if ename == "Rashi": return Rashi(evalue)
                if ename == "Nakshatra": return Nakshatra(evalue)
                if ename == "Ayanamsa": return Ayanamsa(evalue)
                if ename == "HouseSystem": return HouseSystem(evalue)
                if ename == "VargaChart": return VargaChart(evalue)
                if ename == "YogaCategory": return YogaCategory(evalue)
                if ename == "Dignity": return Dignity(evalue)
                if ename == "Relationship": return Relationship(evalue)
                if ename == "MotionStatus": return MotionStatus(evalue)
                if ename == "CombustionStatus": return CombustionStatus(evalue)
            return {k: _d(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_d(v) for v in obj]
        return obj

    # 1. Basic Fields
    birth_data = BirthData(**_d(data['birth_data']))
    
    # 2. Layer 1: Positions and House Cusps
    positions = {CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): PlanetPosition(**_d(v)) 
                 for k, v in data['positions'].items()}
    house_cusps = HouseCusps(**_d(data['house_cusps']))
    
    # 3. Layer 2: Graha Stats (Astronomical facts)
    gs_raw = data['graha_stats']
    graha_stats = AllGrahaStats(
        positions={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): PlanetPosition(**_d(v)) 
                   for k, v in gs_raw['positions'].items()},
        motions={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): GrahaMotion(**_d(v)) 
                 for k, v in gs_raw['motions'].items()},
        combustions={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): CombustionData(**_d(v)) 
                     for k, v in gs_raw['combustions'].items()},
        planetary_wars=[PlanetaryWar(**_d(w)) for w in gs_raw['planetary_wars']],
        julian_day=gs_raw['julian_day'],
        ayanamsa_value=gs_raw['ayanamsa_value']
    )
    
    # 4. Layer 3: Vedic Mapping (Rashi, Nakshatra, Houses, Dignities)
    vm_raw = data['vedic_mapping']
    vedic_mapping = VedicMapping(
        rashi_positions={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): RashiPosition(**_d(v)) 
                         for k, v in vm_raw['rashi_positions'].items()},
        nakshatra_positions={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): NakshatraPosition(**_d(v)) 
                             for k, v in vm_raw['nakshatra_positions'].items()},
        dignities={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): DignityStatus(**_d(v)) 
                   for k, v in vm_raw['dignities'].items()},
        bhava_placements={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): BhavaPlacement(**_d(v)) 
                          for k, v in vm_raw['bhava_placements'].items()},
        lagna=LagnaData(**_d(vm_raw['lagna'])),
        sign_occupancy={Rashi(int(k) if k.isdigit() else Rashi[k].value): _d(v) 
                        for k, v in vm_raw['sign_occupancy'].items()},
        house_occupancy={int(k): _d(v) for k, v in vm_raw['house_occupancy'].items()}
    )
    
    # 5. Layer 4: Dasha System
    dasha_raw = data['dasha']
    mahadashas = []
    for m_raw in dasha_raw['mahadashas']:
        mahadashas.append(DashaPeriod(
            lord=CelestialBody(m_raw['lord']['value']),
            start_date=_d(m_raw['start_date']),
            end_date=_d(m_raw['end_date']),
            duration_years=m_raw['duration_years'],
            level=m_raw['level'],
            parent=None
        ))
    
    dasha = VimshottariDasha(
        birth_date=_d(dasha_raw['birth_date']),
        moon_nakshatra=Nakshatra(dasha_raw['moon_nakshatra']['value']),
        moon_longitude=dasha_raw['moon_longitude'],
        dasha_balance=DashaBalance(
            first_lord=CelestialBody(dasha_raw['dasha_balance']['first_lord']['value']),
            elapsed_years=dasha_raw['dasha_balance']['elapsed_years'],
            remaining_years=dasha_raw['dasha_balance']['remaining_years'],
            total_years=dasha_raw['dasha_balance']['total_years']
        ),
        mahadashas=mahadashas
    )
    
    # 6. Layer 4: Aspects and Yogas
    # 6. Layer 4: Aspects and Yogas
    aspects_raw = data['aspects']
    
    def _ensure_list(obj):
        if isinstance(obj, (list, tuple)): return list(obj)
        return [obj] if obj is not None else []

    aspects = AspectGrid(
        planet_to_houses={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): v 
                          for k, v in aspects_raw['planet_to_houses'].items()},
        house_aspects={int(k): [Aspect(
            aspecting_planet=_d(a['aspecting_planet']),
            aspected_house=a['aspected_house'],
            aspected_planets=tuple(_d(_ensure_list(a['aspected_planets']))),
            aspect_type=a['aspect_type'],
            strength=a['strength']
        ) for a in l] for k, l in aspects_raw['house_aspects'].items()},
        planet_aspects={CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): [Aspect(
            aspecting_planet=_d(a['aspecting_planet']),
            aspected_house=a['aspected_house'],
            aspected_planets=tuple(_d(_ensure_list(a['aspected_planets']))),
            aspect_type=a['aspect_type'],
            strength=a['strength']
        ) for a in l] for k, l in aspects_raw['planet_aspects'].items()},
        mutual_aspects=[tuple(_d(pair)) for pair in aspects_raw['mutual_aspects']]
    )
    
    yoga_raw = data['yogas']
    def _recon_yogas(yl):
        return [YogaDetection(
            name=y['name'],
            category=_d(y['category']),
            is_present=y['is_present'],
            forming_planets=tuple(_d(_ensure_list(y['forming_planets']))),
            forming_houses=tuple(_ensure_list(y['forming_houses'])),
            strength=y['strength'],
            conditions_met=tuple(_ensure_list(y['conditions_met']))
        ) for y in yl]
        
    yogas = YogaAnalysis(
        detected_yogas=_recon_yogas(yoga_raw['detected_yogas']),
        mahapurusha_yogas=_recon_yogas(yoga_raw['mahapurusha_yogas']),
        dhana_yogas=_recon_yogas(yoga_raw['dhana_yogas']),
        raja_yogas=_recon_yogas(yoga_raw['raja_yogas']),
        spiritual_yogas=_recon_yogas(yoga_raw['spiritual_yogas']),
        arishtya_yogas=_recon_yogas(yoga_raw['arishtya_yogas'])
    )
    
    # 7. Divisional Charts
    from src.engines.vedic.divisional_charts import AllVargaPositions
    vargas = {CelestialBody(int(k) if k.isdigit() else CelestialBody[k].value): AllVargaPositions(**_d(v)) 
              for k, v in data['vargas'].items()}
    
    # Construct final chart object
    return VedicChart(
        birth_data=birth_data,
        julian_day=data['julian_day'],
        ayanamsa=_d(data['ayanamsa']),
        ayanamsa_value=data['ayanamsa_value'],
        house_system=_d(data['house_system']),
        positions=positions,
        house_cusps=house_cusps,
        graha_stats=graha_stats,
        vedic_mapping=vedic_mapping,
        dasha=dasha,
        aspects=aspects,
        yogas=yogas,
        vargas=vargas
    )


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
