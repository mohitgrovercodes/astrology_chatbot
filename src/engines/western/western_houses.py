# src\engines\western\western_houses.py
"""
House Calculations for Western Astrology
========================================

This module handles house calculations using various house systems.
Houses divide the chart into 12 sectors representing different life areas.

Key Concepts:
------------
- House System: Method for calculating house cusps
- Angular Houses (1, 4, 7, 10): Action and events
- Succedent Houses (2, 5, 8, 11): Resources and stability
- Cadent Houses (3, 6, 9, 12): Thoughts and transitions
- Intercepted Signs: Signs fully contained within a house

Common House Systems:
--------------------
- Placidus: Most popular modern system
- Koch: Birthplace system
- Equal House: 30Â° houses from Ascendant
- Whole Sign: Each house = one complete sign
- Porphyry: Space division (same as Sripati)

Usage Example:
-------------
    >>> from western.houses import compute_house_placements
    >>> 
    >>> placements = compute_house_placements(
    ...     positions=planet_positions,
    ...     cusps=house_cusps
    ... )
    >>> 
    >>> sun_house = placements[CelestialBody.SUN].house
    >>> print(f"Sun in house {sun_house}")
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from src.engines.core.celestial_bodies import CelestialBody
from src.engines.core.ephemeris import PlanetPosition, HouseCusps, HouseSystem
from src.engines.western.western_constants import HouseClassification, HOUSE_CLASSIFICATIONS, ZodiacSign
from src.engines.western.western_signs import longitude_to_sign


@dataclass(frozen=True)
class HousePlacement:
    """
    A planet's placement in a house.
    
    Attributes:
        planet: The celestial body
        house: House number (1-12)
        longitude: Planet's ecliptic longitude
        sign: Zodiac sign the planet is in
        house_type: Angular, Succedent, or Cadent
        distance_from_cusp: Degrees from the house cusp
    """
    planet: CelestialBody
    house: int
    longitude: float
    sign: ZodiacSign
    house_type: HouseClassification
    distance_from_cusp: float
    
    @property
    def is_angular(self) -> bool:
        """Check if planet is in an angular house."""
        return self.house_type == HouseClassification.ANGULAR
    
    @property
    def is_succedent(self) -> bool:
        """Check if planet is in a succedent house."""
        return self.house_type == HouseClassification.SUCCEDENT
    
    @property
    def is_cadent(self) -> bool:
        """Check if planet is in a cadent house."""
        return self.house_type == HouseClassification.CADENT
    
    @property
    def is_near_cusp(self) -> bool:
        """
        Check if planet is near house cusp (within 5Â°).
        
        Planets near cusps are considered to be entering the
        influence of that house, even if technically in previous house.
        """
        return self.distance_from_cusp < 5.0


@dataclass(frozen=True)
class HouseOccupancy:
    """
    Information about what's in each house.
    
    Attributes:
        house_number: House number (1-12)
        cusp_longitude: Longitude where house begins
        cusp_sign: Sign on the house cusp
        planets: List of planets in this house
        is_empty: Whether house has no planets
        house_type: Angular, Succedent, or Cadent
    """
    house_number: int
    cusp_longitude: float
    cusp_sign: ZodiacSign
    planets: Tuple[CelestialBody, ...]
    is_empty: bool
    house_type: HouseClassification
    
    @property
    def planet_count(self) -> int:
        """Number of planets in this house."""
        return len(self.planets)
    
    @property
    def is_angular(self) -> bool:
        """Check if this is an angular house."""
        return self.house_type == HouseType.ANGULAR


def calculate_house_from_longitude(
    longitude: float,
    cusps: HouseCusps,
    house_system: HouseSystem = HouseSystem.PLACIDUS
) -> int:
    """
    Determine which house a longitude falls in.
    
    This handles the circular nature of the zodiac and accounts for
    different house systems.
    
    Args:
        longitude: Ecliptic longitude to check
        cusps: House cusp positions
        house_system: House system being used
        
    Returns:
        House number (1-12)
        
    Algorithm:
        For each house, check if longitude falls between current
        cusp and next cusp. Handle wrap-around at 360Â°/0Â°.
    """
    # Normalize longitude to 0-360
    longitude = longitude % 360
    
    # Get all 12 cusps
    cusp_list = list(cusps.cusps)
    
    # Check each house
    for house in range(1, 13):
        cusp_start = cusp_list[house - 1]
        
        # Next cusp (wrap to house 1 if we're at house 12)
        if house == 12:
            cusp_end = cusp_list[0]
        else:
            cusp_end = cusp_list[house]
        
        # Check if longitude is in this house
        # Handle wrap-around case
        if cusp_start <= cusp_end:
            # Normal case: e.g., house goes from 30Â° to 60Â°
            if cusp_start <= longitude < cusp_end:
                return house
        else:
            # Wrap-around case: e.g., house goes from 350Â° to 20Â°
            if longitude >= cusp_start or longitude < cusp_end:
                return house
    
    # Fallback (shouldn't happen, but just in case)
    return 1


def calculate_distance_from_cusp(
    longitude: float,
    cusp_longitude: float
) -> float:
    """
    Calculate distance from a house cusp.
    
    Args:
        longitude: Planet's longitude
        cusp_longitude: House cusp longitude
        
    Returns:
        Degrees past the cusp (0-30 typically)
    """
    # Normalize both
    longitude = longitude % 360
    cusp = cusp_longitude % 360
    
    # Calculate forward distance
    if longitude >= cusp:
        distance = longitude - cusp
    else:
        distance = (360 - cusp) + longitude
    
    return distance


def compute_house_placement(
    planet: CelestialBody,
    position: PlanetPosition,
    cusps: HouseCusps,
    house_system: HouseSystem = HouseSystem.PLACIDUS
) -> HousePlacement:
    """
    Calculate a single planet's house placement.
    
    Args:
        planet: The planet
        position: Planet's position
        cusps: House cusps
        house_system: House system
        
    Returns:
        HousePlacement with all details
    """
    house = calculate_house_from_longitude(
        position.longitude, cusps, house_system
    )
    
    # Get cusp longitude for this house
    cusp_longitude = cusps.cusps[house - 1]
    
    # Calculate distance from cusp
    distance = calculate_distance_from_cusp(
        position.longitude, cusp_longitude
    )
    
    return HousePlacement(
        planet=planet,
        house=house,
        longitude=position.longitude,
        sign=longitude_to_sign(position.longitude),
        house_type=HOUSE_CLASSIFICATIONS[house],
        distance_from_cusp=distance
    )


def compute_all_house_placements(
    positions: Dict[CelestialBody, PlanetPosition],
    cusps: HouseCusps,
    house_system: HouseSystem = HouseSystem.PLACIDUS
) -> Dict[CelestialBody, HousePlacement]:
    """
    Calculate house placements for all planets.
    
    Args:
        positions: Dictionary of planet positions
        cusps: House cusps
        house_system: House system
        
    Returns:
        Dictionary mapping planets to their house placements
    """
    placements = {}
    
    for planet, position in positions.items():
        placement = compute_house_placement(
            planet, position, cusps, house_system
        )
        placements[planet] = placement
    
    return placements


def compute_house_occupancy(
    placements: Dict[CelestialBody, HousePlacement],
    cusps: HouseCusps
) -> Dict[int, HouseOccupancy]:
    """
    Organize planets by which house they're in.
    
    Args:
        placements: Planet house placements
        cusps: House cusps
        
    Returns:
        Dictionary mapping house numbers to HouseOccupancy info
    """
    # Initialize all houses
    occupancy = {}
    
    for house in range(1, 13):
        cusp_lon = cusps.cusps[house - 1]
        
        # Find planets in this house
        planets_in_house = [
            planet for planet, placement in placements.items()
            if placement.house == house
        ]
        
        occupancy[house] = HouseOccupancy(
            house_number=house,
            cusp_longitude=cusp_lon,
            cusp_sign=longitude_to_sign(cusp_lon),
            planets=tuple(planets_in_house),
            is_empty=len(planets_in_house) == 0,
            house_type=HOUSE_CLASSIFICATIONS[house]
        )
    
    return occupancy


def get_planets_in_house(
    placements: Dict[CelestialBody, HousePlacement],
    house: int
) -> List[CelestialBody]:
    """
    Get all planets in a specific house.
    
    Args:
        placements: Planet house placements
        house: House number (1-12)
        
    Returns:
        List of planets in that house
    """
    return [
        planet for planet, placement in placements.items()
        if placement.house == house
    ]


def get_empty_houses(
    occupancy: Dict[int, HouseOccupancy]
) -> List[int]:
    """
    Get list of empty houses.
    
    Empty houses are interpreted through their cusp sign's ruler.
    
    Args:
        occupancy: House occupancy data
        
    Returns:
        List of house numbers with no planets
    """
    return [
        house for house, occ in occupancy.items()
        if occ.is_empty
    ]


def get_stellium_houses(
    occupancy: Dict[int, HouseOccupancy],
    min_planets: int = 3
) -> List[Tuple[int, int]]:
    """
    Find houses with stelliums (3+ planets).
    
    A stellium indicates a strong focus on that house's themes.
    
    Args:
        occupancy: House occupancy data
        min_planets: Minimum planets to count as stellium (default 3)
        
    Returns:
        List of (house_number, planet_count) tuples
        
    Example:
        >>> stelliums = get_stellium_houses(occupancy)
        >>> for house, count in stelliums:
        ...     print(f"Stellium in house {house}: {count} planets")
    """
    stelliums = []
    
    for house, occ in occupancy.items():
        if occ.planet_count >= min_planets:
            stelliums.append((house, occ.planet_count))
    
    return sorted(stelliums, key=lambda x: x[1], reverse=True)


def get_angular_planets(
    placements: Dict[CelestialBody, HousePlacement]
) -> List[CelestialBody]:
    """
    Get planets in angular houses (1, 4, 7, 10).
    
    Angular planets are especially powerful and action-oriented.
    
    Args:
        placements: Planet house placements
        
    Returns:
        List of planets in angular houses
    """
    return [
        planet for planet, placement in placements.items()
        if placement.is_angular
    ]


def check_intercepted_signs(
    cusps: HouseCusps
) -> Dict[int, Tuple[ZodiacSign, ...]]:
    """
    Find intercepted signs in the chart.
    
    An intercepted sign is completely contained within a house,
    with no house cusp in that sign. This happens with unequal
    house systems at extreme latitudes.
    
    Args:
        cusps: House cusps
        
    Returns:
        Dictionary mapping house numbers to tuple of intercepted signs
        
    Note:
        Intercepted signs are said to represent hidden or blocked energies.
    """
    intercepted = {}
    
    for house in range(1, 13):
        cusp_start = cusps.cusps[house - 1]
        
        # Next cusp
        if house == 12:
            cusp_end = cusps.cusps[0]
        else:
            cusp_end = cusps.cusps[house]
        
        sign_start = longitude_to_sign(cusp_start)
        sign_end = longitude_to_sign(cusp_end)
        
        # Check if house spans more than 2 signs
        signs_spanned = []
        current_sign = sign_start
        
        # Walk through signs
        for _ in range(12):  # Max possible signs
            if current_sign == sign_end:
                break
            
            signs_spanned.append(current_sign)
            current_sign = ZodiacSign((current_sign.value + 1) % 12)
        
        # If more than 2 signs, middle ones are intercepted
        if len(signs_spanned) > 2:
            intercepted[house] = tuple(signs_spanned[1:-1])
    
    return intercepted


@dataclass(frozen=True)
class HouseInterpretation:
    """
    Traditional meanings for each house.
    
    Attributes:
        house: House number
        keywords: Core themes
        life_areas: Specific life areas
        question_areas: Questions this house answers
    """
    house: int
    keywords: Tuple[str, ...]
    life_areas: Tuple[str, ...]
    question_areas: Tuple[str, ...]


# Traditional house meanings
HOUSE_MEANINGS: Dict[int, HouseInterpretation] = {
    1: HouseInterpretation(
        house=1,
        keywords=("self", "identity", "appearance", "personality", "vitality"),
        life_areas=("physical body", "first impressions", "outlook on life", "beginnings"),
        question_areas=("Who am I?", "How do I appear?", "What's my approach to life?")
    ),
    2: HouseInterpretation(
        house=2,
        keywords=("money", "values", "possessions", "self-worth", "resources"),
        life_areas=("income", "material security", "talents", "what you value"),
        question_areas=("What do I own?", "What do I value?", "How do I earn?")
    ),
    3: HouseInterpretation(
        house=3,
        keywords=("communication", "learning", "siblings", "short trips", "mind"),
        life_areas=("education", "neighbors", "writing", "daily thoughts", "local travel"),
        question_areas=("How do I think?", "How do I communicate?", "What's nearby?")
    ),
    4: HouseInterpretation(
        house=4,
        keywords=("home", "family", "roots", "foundation", "private life"),
        life_areas=("parents", "ancestry", "real estate", "emotional security", "end of life"),
        question_areas=("Where do I come from?", "What's my foundation?", "Where is home?")
    ),
    5: HouseInterpretation(
        house=5,
        keywords=("creativity", "pleasure", "children", "romance", "self-expression"),
        life_areas=("hobbies", "entertainment", "dating", "speculation", "joy"),
        question_areas=("What do I create?", "What brings me joy?", "How do I play?")
    ),
    6: HouseInterpretation(
        house=6,
        keywords=("work", "health", "service", "routine", "pets"),
        life_areas=("daily job", "wellness", "habits", "employees", "small animals"),
        question_areas=("How do I serve?", "What's my routine?", "How's my health?")
    ),
    7: HouseInterpretation(
        house=7,
        keywords=("partnerships", "marriage", "contracts", "open enemies", "balance"),
        life_areas=("spouse", "business partners", "serious relationships", "equality"),
        question_areas=("Who is my other?", "How do I relate?", "What do I project?")
    ),
    8: HouseInterpretation(
        house=8,
        keywords=("transformation", "shared resources", "death", "intimacy", "power"),
        life_areas=("inheritance", "taxes", "other people's money", "psychology", "taboo"),
        question_areas=("What transforms me?", "What do we share?", "What's hidden?")
    ),
    9: HouseInterpretation(
        house=9,
        keywords=("philosophy", "travel", "higher education", "beliefs", "expansion"),
        life_areas=("religion", "long trips", "publishing", "foreign cultures", "meaning"),
        question_areas=("What do I believe?", "Where do I explore?", "What's the meaning?")
    ),
    10: HouseInterpretation(
        house=10,
        keywords=("career", "reputation", "public life", "achievement", "authority"),
        life_areas=("profession", "status", "legacy", "mother figure", "vocation"),
        question_areas=("What's my calling?", "How am I known?", "What do I achieve?")
    ),
    11: HouseInterpretation(
        house=11,
        keywords=("friends", "groups", "hopes", "wishes", "community"),
        life_areas=("social circles", "organizations", "ideals", "collective goals"),
        question_areas=("Who are my people?", "What do I hope for?", "How do I contribute?")
    ),
    12: HouseInterpretation(
        house=12,
        keywords=("subconscious", "solitude", "sacrifice", "hidden enemies", "spirituality"),
        life_areas=("dreams", "institutions", "self-undoing", "karma", "transcendence"),
        question_areas=("What's hidden?", "What do I sacrifice?", "How do I transcend?")
    ),
}


def get_house_meaning(house: int) -> HouseInterpretation:
    """
    Get traditional meanings for a house.
    
    Args:
        house: House number (1-12)
        
    Returns:
        HouseInterpretation with keywords and themes
    """
    return HOUSE_MEANINGS[house]
