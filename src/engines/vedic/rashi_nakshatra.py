# src/engines/vedic/rashi_nakshatra.py
# src\engines\vedic\rashi_nakshatra.py
"""
Layer 2: Vedic Mapping - Rashi & Nakshatra Logic
=================================================

This layer takes raw astronomical positions (longitudes) and maps them to
Vedic astrological concepts: Rashis (zodiac signs), Nakshatras (lunar mansions),
planetary dignities, and house placements.

This is where astronomy becomes astrology. A longitude of 45.5Â° is just a number
in Layer 1, but here it becomes "15Â°30' Vrishabha (Taurus), in Rohini Nakshatra,
4th Pada" - concepts that carry astrological meaning.

What This Layer Computes:
-------------------------
1. Rashi (Sign) placements - which sign each planet is in
2. Nakshatra placements - which lunar mansion, which pada (quarter)
3. Lagna (Ascendant) - the rising sign and its nakshatra
4. Planetary dignity - exalted, debilitated, own sign, friend/enemy sign
5. House placements (Bhava) - which house each planet occupies

What This Layer Does NOT Do:
----------------------------
- Divisional charts (that's Layer 3)
- Dasha calculations (that's Layer 3)
- Yoga detection (that's Layer 3)
- Any interpretation of what these placements "mean"

Dependencies:
- Layer 1 (graha_stats.py) for motion/combustion data
- constants.py for reference tables
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum

from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS
from src.engines.core.ephemeris import PlanetPosition, HouseCusps, HouseSystem
from src.engines.vedic.vedic_constants import (
    Rashi, Nakshatra,
    RASHI_LORDS, RASHI_SANSKRIT_NAMES, RASHI_ENGLISH_NAMES,
    NAKSHATRA_NAMES, NAKSHATRA_LORDS, NAKSHATRA_SPAN, PADA_SPAN,
    EXALTATION_DEGREES, DEBILITATION_SIGNS, MOOLTRIKONA, OWN_SIGNS,
    NATURAL_RELATIONSHIPS, Relationship,
    RASHI_TATTVA, RASHI_MODALITY, RASHI_IS_ODD,
    Tattva, Modality,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class Dignity(Enum):
    """
    Planetary dignity states in order of strength.
    
    A planet's dignity determines its capacity to produce results.
    Exalted planets are strongest, debilitated are weakest.
    """
    EXALTED = "exalted"                 # Uccha - strongest
    MOOLTRIKONA = "mooltrikona"         # Special own sign - very strong
    OWN_SIGN = "own_sign"               # Swakshetra - strong
    GREAT_FRIEND = "great_friend"       # Adhimitram - good
    FRIEND = "friend"                   # Mitram - favorable
    NEUTRAL = "neutral"                 # Samam - average
    ENEMY = "enemy"                     # Shatru - weak
    GREAT_ENEMY = "great_enemy"         # Adhishatru - very weak
    DEBILITATED = "debilitated"         # Neecha - weakest


@dataclass(frozen=True)
class RashiPosition:
    """
    A planet's position in terms of Rashi (zodiac sign).
    
    Attributes:
        body: The celestial body
        rashi: The zodiac sign (0-11)
        degree: Degrees within the sign (0-30)
        minute: Arc minutes within the degree
        second: Arc seconds
        rashi_lord: Planetary ruler of this sign
    """
    body: CelestialBody
    rashi: Rashi
    degree: int
    minute: int
    second: float
    rashi_lord: CelestialBody
    
    @property
    def rashi_name(self) -> str:
        """Sanskrit name of the sign."""
        return RASHI_SANSKRIT_NAMES[self.rashi.value]
    
    @property
    def rashi_english(self) -> str:
        """English name of the sign."""
        return RASHI_ENGLISH_NAMES[self.rashi.value]
    
    def format_position(self) -> str:
        """Format as '15Â°30'45\" Vrishabha'."""
        return f"{self.degree}Â°{self.minute}'{self.second:.0f}\" {self.rashi_name}"


@dataclass(frozen=True)
class NakshatraPosition:
    """
    A planet's position in terms of Nakshatra (lunar mansion).
    
    Attributes:
        body: The celestial body
        nakshatra: The nakshatra (0-26)
        pada: The pada/quarter (1-4)
        degree_in_nakshatra: Degrees within this nakshatra (0-13.33)
        nakshatra_lord: Planetary ruler for Dasha calculations
    """
    body: CelestialBody
    nakshatra: Nakshatra
    pada: int  # 1-4
    degree_in_nakshatra: float
    nakshatra_lord: CelestialBody
    
    @property
    def nakshatra_name(self) -> str:
        """Name of the nakshatra."""
        return NAKSHATRA_NAMES[self.nakshatra.value]
    
    def format_position(self) -> str:
        """Format as 'Rohini 3rd Pada'."""
        ordinals = ["1st", "2nd", "3rd", "4th"]
        return f"{self.nakshatra_name} {ordinals[self.pada - 1]} Pada"


@dataclass(frozen=True)
class DignityStatus:
    """
    Complete dignity analysis for a planet.
    
    Attributes:
        body: The celestial body
        dignity: Primary dignity status
        is_in_own_sign: Whether in a sign it rules
        is_exalted: Whether exalted
        is_debilitated: Whether debilitated
        is_in_mooltrikona: Whether in mooltrikona portion
        sign_lord_relationship: Relationship with the sign lord
        dispositor: The planet ruling the sign this planet occupies
    """
    body: CelestialBody
    dignity: Dignity
    is_in_own_sign: bool
    is_exalted: bool
    is_debilitated: bool
    is_in_mooltrikona: bool
    sign_lord_relationship: Relationship
    dispositor: CelestialBody


@dataclass(frozen=True)
class LagnaData:
    """
    Ascendant (Lagna) data.
    
    The Lagna is the rising sign at the moment of birth. It's the
    most important point in a Vedic horoscope, defining the houses.
    """
    longitude: float
    rashi: Rashi
    degree: int
    minute: int
    nakshatra: Nakshatra
    nakshatra_pada: int
    nakshatra_lord: CelestialBody
    
    @property
    def rashi_name(self) -> str:
        return RASHI_SANSKRIT_NAMES[self.rashi.value]
    
    @property
    def nakshatra_name(self) -> str:
        return NAKSHATRA_NAMES[self.nakshatra.value]


@dataclass(frozen=True)
class BhavaPlacement:
    """
    A planet's house (Bhava) placement.
    
    In Whole Sign houses (default), the house is simply counted
    from the Lagna sign.
    """
    body: CelestialBody
    bhava: int  # 1-12
    bhava_lord: CelestialBody
    degrees_from_cusp: float


@dataclass
class VedicMapping:
    """
    Complete Vedic mapping for all planets.
    
    This is the main output of Layer 2 - all planets mapped to
    Rashis, Nakshatras, houses, and dignities.
    """
    rashi_positions: Dict[CelestialBody, RashiPosition]
    nakshatra_positions: Dict[CelestialBody, NakshatraPosition]
    dignities: Dict[CelestialBody, DignityStatus]
    bhava_placements: Dict[CelestialBody, BhavaPlacement]
    lagna: LagnaData
    
    # Additional computed data
    sign_occupancy: Dict[Rashi, List[CelestialBody]]  # Which planets in each sign
    house_occupancy: Dict[int, List[CelestialBody]]   # Which planets in each house
    
    def get_planets_in_sign(self, rashi: Rashi) -> List[CelestialBody]:
        """Get all planets in a specific sign."""
        return self.sign_occupancy.get(rashi, [])
    
    def get_planets_in_house(self, house: int) -> List[CelestialBody]:
        """Get all planets in a specific house (1-12)."""
        return self.house_occupancy.get(house, [])
    
    def get_house_lord(self, house: int) -> CelestialBody:
        """Get the lord of a specific house (1-12)."""
        # In Whole Sign houses, house n is the (lagna_sign + n - 1) % 12 sign
        sign_index = (self.lagna.rashi.value + house - 1) % 12
        return RASHI_LORDS[sign_index]


# =============================================================================
# COMPUTATION FUNCTIONS - RASHI
# =============================================================================

def longitude_to_rashi(longitude: float) -> Tuple[Rashi, int, int, float]:
    """
    Convert ecliptic longitude to Rashi position.
    
    Args:
        longitude: Ecliptic longitude in degrees (0-360)
        
    Returns:
        Tuple of (Rashi, degrees, minutes, seconds)
        
    Example:
        >>> rashi, deg, min, sec = longitude_to_rashi(45.5)
        >>> print(f"{deg}Â°{min}' {RASHI_SANSKRIT_NAMES[rashi.value]}")
        15Â°30' Vrishabha
    """
    # Normalize to 0-360
    longitude = longitude % 360.0
    
    # Determine sign (each sign is 30Â°)
    rashi_index = int(longitude // 30)
    rashi = Rashi(rashi_index)
    
    # Degrees within sign
    sign_longitude = longitude % 30
    degrees = int(sign_longitude)
    
    # Minutes and seconds
    remainder = (sign_longitude - degrees) * 60
    minutes = int(remainder)
    seconds = (remainder - minutes) * 60
    
    return rashi, degrees, minutes, seconds


def compute_rashi_position(
    body: CelestialBody,
    longitude: float
) -> RashiPosition:
    """
    Compute the Rashi position for a planet.
    
    Args:
        body: The celestial body
        longitude: Its ecliptic longitude in degrees
        
    Returns:
        RashiPosition with full sign position data
    """
    rashi, degree, minute, second = longitude_to_rashi(longitude)
    
    return RashiPosition(
        body=body,
        rashi=rashi,
        degree=degree,
        minute=minute,
        second=second,
        rashi_lord=RASHI_LORDS[rashi.value]
    )


# =============================================================================
# COMPUTATION FUNCTIONS - NAKSHATRA
# =============================================================================

def longitude_to_nakshatra(longitude: float) -> Tuple[Nakshatra, int, float]:
    """
    Convert ecliptic longitude to Nakshatra and Pada.
    
    Each nakshatra spans 13Â°20' (13.333... degrees).
    Each pada spans 3Â°20' (3.333... degrees).
    
    Args:
        longitude: Ecliptic longitude in degrees (0-360)
        
    Returns:
        Tuple of (Nakshatra, pada (1-4), degrees within nakshatra)
        
    Example:
        >>> nak, pada, deg = longitude_to_nakshatra(45.5)
        >>> print(f"{NAKSHATRA_NAMES[nak.value]} Pada {pada}")
        Rohini Pada 4
    """
    # Normalize to 0-360
    longitude = longitude % 360.0
    
    # Determine nakshatra (each is 13.333... degrees)
    nakshatra_index = int(longitude / NAKSHATRA_SPAN)
    nakshatra = Nakshatra(nakshatra_index % 27)
    
    # Degrees within this nakshatra
    degree_in_nakshatra = longitude % NAKSHATRA_SPAN
    
    # Determine pada (each is 3.333... degrees)
    pada = int(degree_in_nakshatra / PADA_SPAN) + 1
    pada = min(pada, 4)  # Ensure max is 4
    
    return nakshatra, pada, degree_in_nakshatra


def compute_nakshatra_position(
    body: CelestialBody,
    longitude: float
) -> NakshatraPosition:
    """
    Compute the Nakshatra position for a planet.
    
    Args:
        body: The celestial body
        longitude: Its ecliptic longitude in degrees
        
    Returns:
        NakshatraPosition with full nakshatra data
    """
    nakshatra, pada, degree_in_nak = longitude_to_nakshatra(longitude)
    
    return NakshatraPosition(
        body=body,
        nakshatra=nakshatra,
        pada=pada,
        degree_in_nakshatra=degree_in_nak,
        nakshatra_lord=NAKSHATRA_LORDS[nakshatra.value]
    )


# =============================================================================
# COMPUTATION FUNCTIONS - DIGNITY
# =============================================================================

def get_natural_relationship(
    planet: CelestialBody,
    sign_lord: CelestialBody
) -> Relationship:
    """
    Determine the natural relationship between a planet and a sign lord.
    
    Args:
        planet: The planet whose dignity we're checking
        sign_lord: The lord of the sign the planet is in
        
    Returns:
        Relationship (friend, enemy, or neutral)
    """
    if planet == sign_lord:
        # Planet in own sign - not a "relationship" but we return neutral
        return Relationship.NEUTRAL
    
    rel_data = NATURAL_RELATIONSHIPS.get(planet)
    if not rel_data:
        return Relationship.NEUTRAL
    
    if sign_lord in rel_data.get("friends", ()):
        return Relationship.FRIEND
    elif sign_lord in rel_data.get("enemies", ()):
        return Relationship.ENEMY
    else:
        return Relationship.NEUTRAL


def compute_dignity(
    body: CelestialBody,
    longitude: float
) -> DignityStatus:
    """
    Compute the dignity status of a planet.
    
    This determines how "comfortable" a planet is in its current position.
    
    Order of precedence:
    1. Exaltation (strongest)
    2. Mooltrikona
    3. Own Sign
    4. Debilitation (weakest)
    5. Otherwise based on relationship with sign lord
    
    Args:
        body: The celestial body
        longitude: Its ecliptic longitude
        
    Returns:
        DignityStatus with complete dignity analysis
    """
    # Get rashi
    rashi, degree, _, _ = longitude_to_rashi(longitude)
    rashi_index = rashi.value
    sign_lord = RASHI_LORDS[rashi_index]
    
    # Check for Rahu/Ketu - they don't own signs
    if body in (CelestialBody.RAHU, CelestialBody.KETU):
        is_in_own = False
    else:
        is_in_own = rashi_index in OWN_SIGNS.get(body, ())
    
    # Check exaltation
    is_exalted = False
    exalt_data = EXALTATION_DEGREES.get(body)
    if exalt_data and exalt_data[0] == rashi_index:
        is_exalted = True
    
    # Check debilitation
    is_debilitated = DEBILITATION_SIGNS.get(body) == rashi_index
    
    # Check mooltrikona
    is_in_mooltrikona = False
    mool_data = MOOLTRIKONA.get(body)
    if mool_data:
        mool_sign, mool_start, mool_end = mool_data
        sign_degree = longitude % 30
        if mool_sign == rashi_index and mool_start <= sign_degree <= mool_end:
            is_in_mooltrikona = True
    
    # Get relationship with sign lord
    sign_lord_rel = get_natural_relationship(body, sign_lord)
    
    # Determine primary dignity
    if is_exalted:
        dignity = Dignity.EXALTED
    elif is_debilitated:
        dignity = Dignity.DEBILITATED
    elif is_in_mooltrikona:
        dignity = Dignity.MOOLTRIKONA
    elif is_in_own:
        dignity = Dignity.OWN_SIGN
    elif sign_lord_rel == Relationship.FRIEND:
        dignity = Dignity.FRIEND
    elif sign_lord_rel == Relationship.ENEMY:
        dignity = Dignity.ENEMY
    else:
        dignity = Dignity.NEUTRAL
    
    return DignityStatus(
        body=body,
        dignity=dignity,
        is_in_own_sign=is_in_own,
        is_exalted=is_exalted,
        is_debilitated=is_debilitated,
        is_in_mooltrikona=is_in_mooltrikona,
        sign_lord_relationship=sign_lord_rel,
        dispositor=sign_lord
    )


# =============================================================================
# COMPUTATION FUNCTIONS - LAGNA (ASCENDANT)
# =============================================================================

def compute_lagna(ascendant_longitude: float) -> LagnaData:
    """
    Compute Lagna (Ascendant) data from the ascendant longitude.
    
    The Lagna is the point of the ecliptic rising on the eastern horizon.
    It defines the first house and is the foundation of the horoscope.
    
    Args:
        ascendant_longitude: The ascendant longitude in degrees
        
    Returns:
        LagnaData with complete ascendant information
    """
    rashi, degree, minute, _ = longitude_to_rashi(ascendant_longitude)
    nakshatra, pada, _ = longitude_to_nakshatra(ascendant_longitude)
    
    return LagnaData(
        longitude=ascendant_longitude,
        rashi=rashi,
        degree=degree,
        minute=minute,
        nakshatra=nakshatra,
        nakshatra_pada=pada,
        nakshatra_lord=NAKSHATRA_LORDS[nakshatra.value]
    )


# =============================================================================
# COMPUTATION FUNCTIONS - BHAVA (HOUSE) PLACEMENT
# =============================================================================

def compute_bhava_placement(
    body: CelestialBody,
    planet_longitude: float,
    lagna: LagnaData,
    house_system: HouseSystem = HouseSystem.WHOLE_SIGN
) -> BhavaPlacement:
    """
    Compute the house (Bhava) placement for a planet.
    
    In Whole Sign houses (the Vedic default), each sign starting from
    Lagna is a house. The Lagna sign is house 1, the next sign is house 2, etc.
    
    Args:
        body: The celestial body
        planet_longitude: The planet's longitude
        lagna: Lagna data
        house_system: House system to use (default: Whole Sign)
        
    Returns:
        BhavaPlacement with house placement data
    """
    # For Whole Sign houses
    if house_system == HouseSystem.WHOLE_SIGN:
        planet_sign = int(planet_longitude // 30) % 12
        lagna_sign = lagna.rashi.value
        
        # House number (1-indexed)
        house = ((planet_sign - lagna_sign) % 12) + 1
        
        # House lord is the lord of the sign that is this house
        house_sign = (lagna_sign + house - 1) % 12
        house_lord = RASHI_LORDS[house_sign]
        
        # Degrees from house cusp (start of sign)
        degrees_from_cusp = planet_longitude % 30
    else:
        # For other house systems, would need house cusps
        # For now, fall back to whole sign
        planet_sign = int(planet_longitude // 30) % 12
        lagna_sign = lagna.rashi.value
        house = ((planet_sign - lagna_sign) % 12) + 1
        house_sign = (lagna_sign + house - 1) % 12
        house_lord = RASHI_LORDS[house_sign]
        degrees_from_cusp = planet_longitude % 30
    
    return BhavaPlacement(
        body=body,
        bhava=house,
        bhava_lord=house_lord,
        degrees_from_cusp=degrees_from_cusp
    )


# =============================================================================
# MAIN COMPUTATION FUNCTION
# =============================================================================

def compute_vedic_mapping(
    positions: Dict[CelestialBody, PlanetPosition],
    ascendant_longitude: float,
    house_system: HouseSystem = HouseSystem.WHOLE_SIGN
) -> VedicMapping:
    """
    Compute complete Vedic mapping for all planets.
    
    This is the main entry point for Layer 2. It takes planetary positions
    from Layer 1 and maps them to all Vedic concepts.
    
    Args:
        positions: Dictionary of planetary positions from Layer 1
        ascendant_longitude: The ascendant longitude in degrees
        house_system: House system to use (default: Whole Sign)
        
    Returns:
        VedicMapping with complete Vedic position data
        
    Example:
        >>> from src.engines.vedic.graha_stats import compute_all_graha_stats
        >>> stats = compute_all_graha_stats(jd)
        >>> mapping = compute_vedic_mapping(stats.positions, ascendant_longitude)
        >>> print(mapping.lagna.rashi_name)
    """
    # Compute Lagna first (needed for house calculations)
    lagna = compute_lagna(ascendant_longitude)
    
    # Compute for each planet
    rashi_positions: Dict[CelestialBody, RashiPosition] = {}
    nakshatra_positions: Dict[CelestialBody, NakshatraPosition] = {}
    dignities: Dict[CelestialBody, DignityStatus] = {}
    bhava_placements: Dict[CelestialBody, BhavaPlacement] = {}
    
    for body, position in positions.items():
        longitude = position.longitude
        
        rashi_positions[body] = compute_rashi_position(body, longitude)
        nakshatra_positions[body] = compute_nakshatra_position(body, longitude)
        dignities[body] = compute_dignity(body, longitude)
        bhava_placements[body] = compute_bhava_placement(
            body, longitude, lagna, house_system
        )
    
    # Compute sign occupancy
    sign_occupancy: Dict[Rashi, List[CelestialBody]] = {r: [] for r in Rashi}
    for body, rashi_pos in rashi_positions.items():
        sign_occupancy[rashi_pos.rashi].append(body)
    
    # Compute house occupancy
    house_occupancy: Dict[int, List[CelestialBody]] = {h: [] for h in range(1, 13)}
    for body, bhava in bhava_placements.items():
        house_occupancy[bhava.bhava].append(body)
    
    return VedicMapping(
        rashi_positions=rashi_positions,
        nakshatra_positions=nakshatra_positions,
        dignities=dignities,
        bhava_placements=bhava_placements,
        lagna=lagna,
        sign_occupancy=sign_occupancy,
        house_occupancy=house_occupancy
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_sign_element(rashi: Rashi) -> Tattva:
    """Get the element (Tattva) of a sign."""
    return RASHI_TATTVA[rashi.value]


def get_sign_modality(rashi: Rashi) -> Modality:
    """Get the modality of a sign (movable/fixed/dual)."""
    return RASHI_MODALITY[rashi.value]


def is_sign_odd(rashi: Rashi) -> bool:
    """Check if a sign is odd (masculine) or even (feminine)."""
    return RASHI_IS_ODD[rashi.value]


def get_dispositor_chain(
    body: CelestialBody,
    dignities: Dict[CelestialBody, DignityStatus],
    max_depth: int = 10
) -> List[CelestialBody]:
    """
    Get the dispositor chain for a planet.
    
    The dispositor of a planet is the lord of the sign it occupies.
    Following the chain shows the "flow of influence" until we reach
    a planet in its own sign (final dispositor).
    
    Args:
        body: Starting planet
        dignities: Dignity data for all planets
        max_depth: Maximum chain length (prevents infinite loops)
        
    Returns:
        List of planets in the dispositor chain
    """
    chain = [body]
    current = body
    
    for _ in range(max_depth):
        dignity = dignities.get(current)
        if not dignity:
            break
        
        dispositor = dignity.dispositor
        
        # If planet is in own sign, chain ends
        if dignity.is_in_own_sign:
            break
        
        # If we've seen this planet before, we have a loop
        if dispositor in chain:
            chain.append(dispositor)  # Show the loop connection
            break
        
        chain.append(dispositor)
        current = dispositor
    
    return chain