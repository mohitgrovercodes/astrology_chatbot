# src/engines/vedic/aspects_yogas.py
# src\engines\vedic\aspects_yogas.py
"""
Layer 3C: Aspects (Drishti) and Yoga Detection
==============================================

This module handles two critical Vedic calculations:

1. ASPECTS (DRISHTI):
   In Vedic astrology, aspects work differently than Western:
   - All planets aspect the 7th house (opposite) from themselves
   - Mars, Jupiter, Saturn have additional special aspects
   - Rahu/Ketu typically follow Jupiter/Saturn aspects

2. YOGAS (Planetary Combinations):
   Yogas are specific planetary configurations that indicate certain
   life themes. This module DETECTS yogas (pure math) - it does NOT
   interpret their meaning.

   Categories of Yogas detected:
   - Pancha Mahapurusha Yogas (5 great person yogas)
   - Dhana Yogas (wealth combinations)
   - Raja Yogas (power combinations)
   - Arishtya/Difficult Yogas
   - Spiritual Yogas

Note: This module checks IF conditions are met, not WHAT it means.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from enum import Enum

from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS
from src.engines.vedic.vedic_constants import (
    Rashi, RASHI_LORDS, 
    SPECIAL_ASPECTS, DEFAULT_ASPECTS,
    EXALTATION_DEGREES, OWN_SIGNS, MOOLTRIKONA,
)
from src.engines.vedic.rashi_nakshatra import VedicMapping, BhavaPlacement, DignityStatus, Dignity


# =============================================================================
# ASPECT (DRISHTI) DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class Aspect:
    """
    Represents an aspect from one planet to a house or another planet.
    
    Attributes:
        aspecting_planet: The planet casting the aspect
        aspected_house: The house being aspected (1-12)
        aspected_planets: Planets in that house receiving the aspect
        aspect_type: "full" (7th), "special" (Mars 4,8; Jupiter 5,9; Saturn 3,10)
        strength: Aspect strength (1.0 = full)
    """
    aspecting_planet: CelestialBody
    aspected_house: int
    aspected_planets: Tuple[CelestialBody, ...]
    aspect_type: str  # "full" or "special"
    strength: float


@dataclass
class AspectGrid:
    """
    Complete aspect analysis for a chart.
    
    Contains:
    - Which houses each planet aspects
    - Which planets aspect each house
    - Mutual aspects between planets
    """
    planet_to_houses: Dict[CelestialBody, List[int]]
    house_aspects: Dict[int, List[Aspect]]
    planet_aspects: Dict[CelestialBody, List[Aspect]]
    mutual_aspects: List[Tuple[CelestialBody, CelestialBody]]
    
    def get_planets_aspecting_house(self, house: int) -> List[CelestialBody]:
        """Get all planets aspecting a specific house."""
        return [asp.aspecting_planet for asp in self.house_aspects.get(house, [])]
    
    def get_houses_aspected_by(self, planet: CelestialBody) -> List[int]:
        """Get all houses aspected by a specific planet."""
        return self.planet_to_houses.get(planet, [])
    
    def has_mutual_aspect(self, p1: CelestialBody, p2: CelestialBody) -> bool:
        """Check if two planets mutually aspect each other."""
        return (p1, p2) in self.mutual_aspects or (p2, p1) in self.mutual_aspects


# =============================================================================
# YOGA DATA STRUCTURES
# =============================================================================

class YogaCategory(Enum):
    """Categories of Vedic yogas."""
    MAHAPURUSHA = "mahapurusha"      # Five great person yogas
    DHANA = "dhana"                   # Wealth yogas
    RAJA = "raja"                     # Power/authority yogas
    PARIVARTANA = "parivartana"       # Exchange yogas
    SPIRITUAL = "spiritual"           # Spiritual/moksha yogas
    ARISHTYA = "arishtya"            # Difficult/challenging yogas
    NABHASA = "nabhasa"              # Pattern-based yogas
    CHANDRA = "chandra"              # Moon-based yogas


@dataclass(frozen=True)
class YogaDetection:
    """
    A detected yoga in the chart.
    
    Attributes:
        name: Name of the yoga
        category: Type of yoga
        is_present: True if yoga is formed
        forming_planets: Planets involved in forming this yoga
        forming_houses: Houses involved
        strength: Relative strength (0-1, based on dignity etc.)
        conditions_met: List of specific conditions that were satisfied
    """
    name: str
    category: YogaCategory
    is_present: bool
    forming_planets: Tuple[CelestialBody, ...]
    forming_houses: Tuple[int, ...]
    strength: float
    conditions_met: Tuple[str, ...]


@dataclass
class YogaAnalysis:
    """Complete yoga analysis for a chart."""
    detected_yogas: List[YogaDetection]
    mahapurusha_yogas: List[YogaDetection]
    dhana_yogas: List[YogaDetection]
    raja_yogas: List[YogaDetection]
    spiritual_yogas: List[YogaDetection]
    arishtya_yogas: List[YogaDetection]
    
    def get_yogas_by_category(self, category: YogaCategory) -> List[YogaDetection]:
        """Get all yogas of a specific category."""
        return [y for y in self.detected_yogas if y.category == category]
    
    def get_yogas_for_planet(self, planet: CelestialBody) -> List[YogaDetection]:
        """Get all yogas involving a specific planet."""
        return [y for y in self.detected_yogas if planet in y.forming_planets]


# =============================================================================
# ASPECT CALCULATIONS
# =============================================================================

def compute_aspected_houses(
    planet: CelestialBody,
    planet_house: int
) -> Dict[int, float]:
    """
    Determine which houses a planet aspects and with what strength.
    
    Args:
        planet: The aspecting planet
        planet_house: The house the planet occupies (1-12)
        
    Returns:
        Dictionary of {aspected_house: strength}
    """
    aspects = {}
    
    # Check if planet has special aspects
    special = SPECIAL_ASPECTS.get(planet, DEFAULT_ASPECTS)
    
    for house_distance, strength in special.items():
        # Calculate the aspected house (1-indexed).
        # "Xth house from planet_house" means: planet_house + X - 1 (1-based counting).
        # Formula: ((planet_house + house_distance - 2) % 12) + 1
        aspected = ((planet_house + house_distance - 2) % 12) + 1
        aspects[aspected] = strength
    
    return aspects


def compute_aspect_grid(
    bhava_placements: Dict[CelestialBody, BhavaPlacement],
    house_occupancy: Dict[int, List[CelestialBody]]
) -> AspectGrid:
    """
    Compute complete aspect analysis for a chart.
    
    Args:
        bhava_placements: House placement for each planet
        house_occupancy: Planets in each house
        
    Returns:
        AspectGrid with complete aspect data
    """
    planet_to_houses: Dict[CelestialBody, List[int]] = {}
    house_aspects: Dict[int, List[Aspect]] = {h: [] for h in range(1, 13)}
    planet_aspects: Dict[CelestialBody, List[Aspect]] = {}
    mutual_aspect_set: Set[Tuple[CelestialBody, CelestialBody]] = set()
    
    # For each planet, compute its aspects
    for planet, bhava in bhava_placements.items():
        aspected_houses = compute_aspected_houses(planet, bhava.bhava)
        planet_to_houses[planet] = list(aspected_houses.keys())
        planet_aspects[planet] = []
        
        for house, strength in aspected_houses.items():
            planets_in_house = house_occupancy.get(house, [])
            # 7th house from planet using corrected formula: ((bhava + 5) % 12) + 1
            seventh = ((bhava.bhava + 5) % 12) + 1
            aspect_type = "full" if house == seventh else "special"
            
            asp = Aspect(
                aspecting_planet=planet,
                aspected_house=house,
                aspected_planets=tuple(planets_in_house),
                aspect_type=aspect_type,
                strength=strength
            )
            
            house_aspects[house].append(asp)
            planet_aspects[planet].append(asp)
            
            # Check for mutual aspects
            for aspected_planet in planets_in_house:
                if aspected_planet != planet:
                    other_aspects = compute_aspected_houses(
                        aspected_planet, 
                        bhava_placements[aspected_planet].bhava
                    )
                    if bhava.bhava in other_aspects:
                        pair = tuple(sorted([planet.value, aspected_planet.value]))
                        mutual_aspect_set.add(
                            (CelestialBody(pair[0]), CelestialBody(pair[1]))
                        )
    
    return AspectGrid(
        planet_to_houses=planet_to_houses,
        house_aspects=house_aspects,
        planet_aspects=planet_aspects,
        mutual_aspects=list(mutual_aspect_set)
    )


# =============================================================================
# YOGA DETECTION - PANCHA MAHAPURUSHA YOGAS
# =============================================================================

def detect_mahapurusha_yogas(
    bhava_placements: Dict[CelestialBody, BhavaPlacement],
    dignities: Dict[CelestialBody, DignityStatus]
) -> List[YogaDetection]:
    """
    Detect the five Mahapurusha (great person) Yogas.
    
    These yogas are formed when Mars, Mercury, Jupiter, Venus, or Saturn
    is in a Kendra (1, 4, 7, 10) AND in its own sign or exaltation.
    
    - Ruchaka Yoga: Mars in Kendra in own/exalted sign
    - Bhadra Yoga: Mercury in Kendra in own/exalted sign
    - Hamsa Yoga: Jupiter in Kendra in own/exalted sign
    - Malavya Yoga: Venus in Kendra in own/exalted sign
    - Shasha Yoga: Saturn in Kendra in own/exalted sign
    """
    yogas = []
    kendra_houses = [1, 4, 7, 10]
    
    yoga_names = {
        CelestialBody.MARS: "Ruchaka",
        CelestialBody.MERCURY: "Bhadra",
        CelestialBody.JUPITER: "Hamsa",
        CelestialBody.VENUS: "Malavya",
        CelestialBody.SATURN: "Shasha",
    }
    
    for planet, yoga_name in yoga_names.items():
        bhava = bhava_placements.get(planet)
        dignity = dignities.get(planet)
        
        if not bhava or not dignity:
            continue
        
        is_in_kendra = bhava.bhava in kendra_houses
        is_strong = dignity.is_exalted or dignity.is_in_own_sign
        
        conditions = []
        if is_in_kendra:
            conditions.append(f"{planet.name} in house {bhava.bhava} (Kendra)")
        if dignity.is_exalted:
            conditions.append(f"{planet.name} is exalted")
        if dignity.is_in_own_sign:
            conditions.append(f"{planet.name} in own sign")
        
        yoga_formed = is_in_kendra and is_strong
        
        # Calculate strength (exalted > own sign)
        strength = 0.0
        if yoga_formed:
            strength = 1.0 if dignity.is_exalted else 0.8
        
        yogas.append(YogaDetection(
            name=f"{yoga_name} Yoga",
            category=YogaCategory.MAHAPURUSHA,
            is_present=yoga_formed,
            forming_planets=(planet,),
            forming_houses=(bhava.bhava,) if is_in_kendra else (),
            strength=strength,
            conditions_met=tuple(conditions)
        ))
    
    return yogas


# =============================================================================
# YOGA DETECTION - RAJA YOGAS
# =============================================================================

def detect_raja_yogas(
    bhava_placements: Dict[CelestialBody, BhavaPlacement],
    lagna_sign: Rashi
) -> List[YogaDetection]:
    """
    Detect Raja Yogas (combinations for power and authority).
    
    Basic Raja Yoga: Lord of a Kendra (1,4,7,10) conjunct or aspecting
    lord of a Trikona (1,5,9).
    
    This is a simplified detection - full analysis requires aspect checking.
    """
    yogas = []
    
    # Determine Kendra and Trikona lords based on Lagna
    kendra_houses = [1, 4, 7, 10]
    trikona_houses = [1, 5, 9]
    
    def get_house_lord(house: int) -> CelestialBody:
        sign_index = (lagna_sign.value + house - 1) % 12
        return RASHI_LORDS[sign_index]
    
    kendra_lords = {get_house_lord(h) for h in kendra_houses}
    trikona_lords = {get_house_lord(h) for h in trikona_houses}
    
    # Check for conjunction of Kendra lord with Trikona lord
    # Group planets by house
    house_groups: Dict[int, List[CelestialBody]] = {}
    for planet, bhava in bhava_placements.items():
        if bhava.bhava not in house_groups:
            house_groups[bhava.bhava] = []
        house_groups[bhava.bhava].append(planet)
    
    # Check each house for Raja Yoga conjunction
    for house, planets in house_groups.items():
        kendra_in_house = [p for p in planets if p in kendra_lords]
        trikona_in_house = [p for p in planets if p in trikona_lords]
        
        # Need at least one of each (or same planet being both)
        for kp in kendra_in_house:
            for tp in trikona_in_house:
                # 1st lord is both Kendra and Trikona - special case
                is_same = kp == tp
                
                yogas.append(YogaDetection(
                    name="Raja Yoga" if not is_same else "Lagna Lord Raja Yoga",
                    category=YogaCategory.RAJA,
                    is_present=True,
                    forming_planets=(kp,) if is_same else (kp, tp),
                    forming_houses=(house,),
                    strength=0.8,
                    conditions_met=(
                        f"Kendra lord {kp.name} conjunct Trikona lord {tp.name} in house {house}",
                    )
                ))
    
    return yogas


# =============================================================================
# YOGA DETECTION - DHANA YOGAS
# =============================================================================

def detect_dhana_yogas(
    bhava_placements: Dict[CelestialBody, BhavaPlacement],
    lagna_sign: Rashi
) -> List[YogaDetection]:
    """
    Detect Dhana Yogas (wealth combinations).
    
    Dhana Yogas typically involve the 2nd house (wealth), 11th house (gains),
    and connections between their lords and Kendra/Trikona lords.
    """
    yogas = []
    
    def get_house_lord(house: int) -> CelestialBody:
        sign_index = (lagna_sign.value + house - 1) % 12
        return RASHI_LORDS[sign_index]
    
    lord_2 = get_house_lord(2)
    lord_11 = get_house_lord(11)
    
    # Check if 2nd and 11th lords are conjunct
    house_2 = bhava_placements.get(lord_2)
    house_11 = bhava_placements.get(lord_11)
    
    if house_2 and house_11 and house_2.bhava == house_11.bhava:
        yogas.append(YogaDetection(
            name="Dhana Yoga (2-11 lords conjunction)",
            category=YogaCategory.DHANA,
            is_present=True,
            forming_planets=(lord_2, lord_11),
            forming_houses=(house_2.bhava,),
            strength=0.75,
            conditions_met=(
                f"2nd lord {lord_2.name} conjunct 11th lord {lord_11.name}",
            )
        ))
    
    # Check for benefics in 2nd house
    planets_in_2 = [p for p, b in bhava_placements.items() if b.bhava == 2]
    benefics = [CelestialBody.JUPITER, CelestialBody.VENUS, CelestialBody.MERCURY]
    benefics_in_2 = [p for p in planets_in_2 if p in benefics]
    
    if benefics_in_2:
        yogas.append(YogaDetection(
            name="Dhana Yoga (benefic in 2nd)",
            category=YogaCategory.DHANA,
            is_present=True,
            forming_planets=tuple(benefics_in_2),
            forming_houses=(2,),
            strength=0.6,
            conditions_met=tuple(f"{p.name} in 2nd house" for p in benefics_in_2)
        ))
    
    return yogas


# =============================================================================
# MAIN YOGA ANALYSIS FUNCTION
# =============================================================================

def detect_all_yogas(
    mapping: VedicMapping
) -> YogaAnalysis:
    """
    Detect all yogas in a chart.
    
    This is the main entry point for yoga detection.
    
    Args:
        mapping: VedicMapping from Layer 2
        
    Returns:
        YogaAnalysis with all detected yogas
    """
    all_yogas = []
    
    # Detect Mahapurusha Yogas
    mahapurusha = detect_mahapurusha_yogas(
        mapping.bhava_placements,
        mapping.dignities
    )
    all_yogas.extend(mahapurusha)
    
    # Detect Raja Yogas
    raja = detect_raja_yogas(
        mapping.bhava_placements,
        mapping.lagna.rashi
    )
    all_yogas.extend(raja)
    
    # Detect Dhana Yogas
    dhana = detect_dhana_yogas(
        mapping.bhava_placements,
        mapping.lagna.rashi
    )
    all_yogas.extend(dhana)
    
    # Filter to only present yogas for categorized lists
    present_yogas = [y for y in all_yogas if y.is_present]
    
    return YogaAnalysis(
        detected_yogas=all_yogas,
        mahapurusha_yogas=[y for y in present_yogas if y.category == YogaCategory.MAHAPURUSHA],
        dhana_yogas=[y for y in present_yogas if y.category == YogaCategory.DHANA],
        raja_yogas=[y for y in present_yogas if y.category == YogaCategory.RAJA],
        spiritual_yogas=[y for y in present_yogas if y.category == YogaCategory.SPIRITUAL],
        arishtya_yogas=[y for y in present_yogas if y.category == YogaCategory.ARISHTYA],
    )