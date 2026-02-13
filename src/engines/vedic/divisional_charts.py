# src\engines\vedic\divisional_charts.py
"""
Divisional Charts (Varga Charts) - Complete Implementation
==========================================================

Divisional charts (Vargas) are one of the most powerful and unique features 
of Vedic astrology. They work by mathematically dividing each zodiac sign 
into smaller portions, effectively creating "zoomed in" views of specific 
life areas.

How It Works (Conceptually):
---------------------------
Imagine the zodiac as a 360Â° circle. In the main birth chart (D1), each 
sign spans 30Â°. But what if we want more detail about, say, your marriage 
prospects? The Navamsa (D9) chart divides each sign into 9 equal parts of 
3Â°20' each, giving us 9x more precision for analyzing dharma and marriage.

The Mathematical Principle:
--------------------------
For a Dn chart (where n is the divisor):
1. Each sign is divided into n equal parts
2. Each part spans 30Â°/n degrees  
3. The planet's position determines which division it falls in
4. That division maps to a sign based on rules from BPHS

Why Different Rules for Different Vargas?
-----------------------------------------
The mapping rules aren't arbitrary - they encode astrological meaning:
- D2 (Hora): Only maps to Leo (Sun) or Cancer (Moon) - wealth comes from 
  soul (Sun) or mind/masses (Moon)
- D9 (Navamsa): The 108 navamsas correspond to the 108 padas of nakshatras
- D30 (Trimsamsa): Irregular divisions based on planetary dignities

Charts Implemented (from BPHS):
------------------------------
D1  - Rashi (birth chart)
D2  - Hora (wealth, resources)
D3  - Drekkana (siblings, courage, initiative)
D4  - Chaturthamsa (fortune, property, fixed assets)
D7  - Saptamsa (children, progeny)
D9  - Navamsa (spouse, dharma, spiritual path) *** MOST IMPORTANT ***
D10 - Dasamsa (career, profession, public life)
D12 - Dwadasamsa (parents)
D16 - Shodasamsa (vehicles, conveyances, luxuries)
D20 - Vimsamsa (spiritual progress, upasana)
D24 - Chaturvimsamsa (education, learning, knowledge)
D27 - Saptavimsamsa (strength and weakness)
D30 - Trimsamsa (evils, misfortune, inauspicious)
D40 - Khavedamsa (auspicious/inauspicious effects)
D45 - Akshavedamsa (general well-being)
D60 - Shashtyamsa (all matters - most detailed)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import IntEnum

from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS
from src.engines.vedic.vedic_constants import Rashi, VargaChart, RASHI_LORDS


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class VargaPosition:
    """
    A planet's position in a specific divisional chart.
    
    Attributes:
        body: The celestial body
        varga: Which divisional chart this is from
        rashi: The zodiac sign in this varga chart
        d1_rashi: The sign in the main birth chart (for reference)
        division_number: Which division within the D1 sign (1 to n)
    """
    body: CelestialBody
    varga: VargaChart
    rashi: Rashi
    d1_rashi: Rashi
    division_number: int
    
    @property
    def rashi_lord(self) -> CelestialBody:
        """Get the lord of the varga rashi."""
        return RASHI_LORDS[self.rashi.value]
    
    @property
    def is_vargottama(self) -> bool:
        """
        Check if planet is vargottama (same sign in D1 and D9).
        Vargottama planets are considered strengthened.
        Only applicable for D9 (Navamsa).
        """
        return self.varga == VargaChart.D9 and self.rashi == self.d1_rashi


@dataclass
class AllVargaPositions:
    """Collection of all varga positions for a single planet."""
    body: CelestialBody
    positions: Dict[VargaChart, VargaPosition]
    
    def get_position(self, varga: VargaChart) -> Optional[VargaPosition]:
        """Get position in a specific varga chart."""
        return self.positions.get(varga)
    
    @property
    def is_vargottama(self) -> bool:
        """Check if planet is vargottama (same sign in D1 and D9)."""
        d9_pos = self.positions.get(VargaChart.D9)
        return d9_pos.is_vargottama if d9_pos else False
    
    def get_sign_count(self) -> Dict[Rashi, int]:
        """
        Count how many vargas have this planet in each sign.
        Useful for Vimshopaka Bala (varga strength) calculations.
        """
        counts: Dict[Rashi, int] = {}
        for pos in self.positions.values():
            counts[pos.rashi] = counts.get(pos.rashi, 0) + 1
        return counts


# =============================================================================
# INDIVIDUAL VARGA CALCULATION FUNCTIONS
# =============================================================================

def compute_d1(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D1 (Rashi) - The main birth chart.
    Each sign is itself - no division needed.
    """
    return d1_rashi


def compute_d2_hora(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D2 (Hora) - Wealth and resources.
    
    Each sign is divided into 2 parts of 15Â° each.
    This chart only uses Leo (Sun's sign) and Cancer (Moon's sign).
    
    Rules from BPHS:
    - Odd signs: First 15Â° = Leo, Second 15Â° = Cancer
    - Even signs: First 15Â° = Cancer, Second 15Â° = Leo
    
    The symbolism: Wealth comes either from the soul's radiance (Sun/Leo)
    or from emotional intelligence and masses (Moon/Cancer).
    """
    sign_longitude = longitude % 30
    is_first_half = sign_longitude < 15
    is_odd_sign = (d1_rashi.value % 2) == 0  # 0-indexed: Aries=0 (odd)
    
    if is_odd_sign:
        return Rashi.SIMHA if is_first_half else Rashi.KARKA
    else:
        return Rashi.KARKA if is_first_half else Rashi.SIMHA


def compute_d3_drekkana(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D3 (Drekkana) - Siblings, courage, and initiative.
    
    Each sign is divided into 3 parts of 10Â° each.
    
    Rules from BPHS:
    - First 10Â° (0-10): Same sign
    - Second 10Â° (10-20): 5th sign from the original
    - Third 10Â° (20-30): 9th sign from the original
    
    The trinal (1-5-9) relationship reflects the fire trine quality
    associated with initiative and courage.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 10)
    
    # Offsets: Same sign, 5th from it, 9th from it (0-indexed: 0, 4, 8)
    offsets = [0, 4, 8]
    return Rashi((d1_rashi.value + offsets[division]) % 12)


def compute_d4_chaturthamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D4 (Chaturthamsa) - Fortune, property, and fixed assets.
    
    Each sign is divided into 4 parts of 7Â°30' each.
    
    Rules: Starts from the sign itself and progresses by 3 signs (90Â°).
    This reflects the kendras (quadrants) which represent stability
    and material foundation.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 7.5)
    
    # Progress by 3 signs for each division (kendra-like progression)
    return Rashi((d1_rashi.value + division * 3) % 12)


def compute_d7_saptamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D7 (Saptamsa) - Children and progeny.
    
    Each sign is divided into 7 parts of 4Â°17'8.57" each.
    
    Rules from BPHS:
    - For odd signs: Start counting from the sign itself
    - For even signs: Start counting from the 7th sign (opposite)
    
    The 7 represents the 7th house of partnerships which leads to children.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / (30 / 7))
    is_odd_sign = (d1_rashi.value % 2) == 0
    
    if is_odd_sign:
        return Rashi((d1_rashi.value + division) % 12)
    else:
        return Rashi((d1_rashi.value + 6 + division) % 12)


def compute_d9_navamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D9 (Navamsa) - THE MOST IMPORTANT divisional chart after D1.
    
    Used for: Marriage, spouse, dharma, inner self, spiritual potential.
    
    Each sign is divided into 9 parts of 3Â°20' (= 13.33Â°/4 = one pada).
    The 108 navamsas correspond to the 108 nakshatra padas.
    
    Rules from BPHS:
    - Fire signs (Aries, Leo, Sag): Start from Aries
    - Earth signs (Taurus, Virgo, Cap): Start from Capricorn
    - Air signs (Gemini, Libra, Aqua): Start from Libra
    - Water signs (Cancer, Scorp, Pisces): Start from Cancer
    
    This creates a continuous sequence where the navamsas cycle through
    all 12 signs three times across the 27 nakshatras.
    """
    sign_longitude = longitude % 30
    navamsa_division = int(sign_longitude / (30 / 9))
    
    # Determine starting sign based on element
    # Element pattern: Fire(0), Earth(1), Air(2), Water(3)
    element = d1_rashi.value % 4
    
    starting_signs = [
        Rashi.MESHA,    # Fire signs start from Aries
        Rashi.MAKARA,   # Earth signs start from Capricorn
        Rashi.TULA,     # Air signs start from Libra
        Rashi.KARKA,    # Water signs start from Cancer
    ]
    
    # Calculate position within the element group (0, 1, or 2)
    # Fire signs: Aries(0), Leo(4), Sag(8) â†’ positions 0, 1, 2
    element_group_position = d1_rashi.value // 4
    
    # Total navamsa offset from the starting sign
    total_offset = (element_group_position * 9) + navamsa_division
    
    return Rashi((starting_signs[element].value + total_offset) % 12)


def compute_d10_dasamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D10 (Dasamsa) - Career, profession, and public standing.
    
    Each sign is divided into 10 parts of 3Â° each.
    
    Rules from BPHS:
    - For odd signs: Start from the sign itself
    - For even signs: Start from the 9th sign from it
    
    The 10 represents the 10th house of career and karma.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 3)
    is_odd_sign = (d1_rashi.value % 2) == 0
    
    if is_odd_sign:
        return Rashi((d1_rashi.value + division) % 12)
    else:
        return Rashi((d1_rashi.value + 8 + division) % 12)


def compute_d12_dwadasamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D12 (Dwadasamsa) - Parents.
    
    Each sign is divided into 12 parts of 2Â°30' each.
    
    Rules: Simply starts from the sign itself and cycles through all 12.
    This is the simplest mapping - each division goes to the next sign.
    
    The 12 divisions naturally map to the 12 signs, showing genetic/karmic
    inheritance from parents.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 2.5)
    
    return Rashi((d1_rashi.value + division) % 12)


def compute_d16_shodasamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D16 (Shodasamsa) - Vehicles, conveyances, and luxuries.
    
    Each sign is divided into 16 parts of 1Â°52'30" each.
    
    Rules from BPHS (based on modality):
    - Movable signs (Aries, Cancer, Libra, Cap): Start from Aries
    - Fixed signs (Taurus, Leo, Scorpio, Aqua): Start from Leo
    - Dual signs (Gemini, Virgo, Sag, Pisces): Start from Sagittarius
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / (30 / 16))
    
    # Modality: 0=Movable, 1=Fixed, 2=Dual
    modality = d1_rashi.value % 3
    starting_signs = [Rashi.MESHA, Rashi.SIMHA, Rashi.DHANU]
    
    return Rashi((starting_signs[modality].value + division) % 12)


def compute_d20_vimsamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D20 (Vimsamsa) - Spiritual progress and religious practices.
    
    Each sign is divided into 20 parts of 1Â°30' each.
    
    Rules from BPHS (based on modality):
    - Movable signs: Start from Aries
    - Fixed signs: Start from Sagittarius
    - Dual signs: Start from Leo
    
    Note: The starting signs differ from D16!
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 1.5)
    
    modality = d1_rashi.value % 3
    starting_signs = [Rashi.MESHA, Rashi.DHANU, Rashi.SIMHA]
    
    return Rashi((starting_signs[modality].value + division) % 12)


def compute_d24_chaturvimsamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D24 (Chaturvimsamsa/Siddhamsa) - Education and learning.
    
    Each sign is divided into 24 parts of 1Â°15' each.
    
    Rules from BPHS:
    - Odd signs: Start from Leo (5th sign - creativity, intelligence)
    - Even signs: Start from Cancer (4th sign - mind, education)
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 1.25)
    is_odd_sign = (d1_rashi.value % 2) == 0
    
    if is_odd_sign:
        return Rashi((Rashi.SIMHA.value + division) % 12)
    else:
        return Rashi((Rashi.KARKA.value + division) % 12)


def compute_d27_saptavimsamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D27 (Saptavimsamsa/Bhamsa) - Strength and weakness.
    
    Each sign is divided into 27 parts (matching the 27 nakshatras).
    Each part spans 1Â°6'40" (30Â°/27).
    
    Rules from BPHS (based on element):
    - Fire signs: Start from Aries
    - Earth signs: Start from Cancer
    - Air signs: Start from Libra
    - Water signs: Start from Capricorn
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / (30 / 27))
    
    element = d1_rashi.value % 4
    starting_signs = [Rashi.MESHA, Rashi.KARKA, Rashi.TULA, Rashi.MAKARA]
    
    return Rashi((starting_signs[element].value + division) % 12)


def compute_d30_trimsamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D30 (Trimsamsa) - Evils and misfortune.
    
    This chart is UNIQUE because it has IRREGULAR divisions.
    The sign is divided into 5 unequal parts ruled by the 5 
    non-luminary planets (Mars, Saturn, Jupiter, Mercury, Venus).
    
    For ODD signs, the divisions are:
    - 0-5Â°: Mars (Aries)
    - 5-10Â°: Saturn (Aquarius)
    - 10-18Â°: Jupiter (Sagittarius)
    - 18-25Â°: Mercury (Gemini)
    - 25-30Â°: Venus (Libra)
    
    For EVEN signs, the order is REVERSED:
    - 0-5Â°: Venus (Libra)
    - 5-12Â°: Mercury (Gemini)
    - 12-20Â°: Jupiter (Sagittarius)
    - 20-25Â°: Saturn (Aquarius)
    - 25-30Â°: Mars (Aries)
    """
    sign_longitude = longitude % 30
    is_odd_sign = (d1_rashi.value % 2) == 0
    
    if is_odd_sign:
        boundaries = [5, 10, 18, 25, 30]
        rulers = [Rashi.MESHA, Rashi.KUMBHA, Rashi.DHANU, Rashi.MITHUNA, Rashi.TULA]
    else:
        boundaries = [5, 12, 20, 25, 30]
        rulers = [Rashi.TULA, Rashi.MITHUNA, Rashi.DHANU, Rashi.KUMBHA, Rashi.MESHA]
    
    for i, boundary in enumerate(boundaries):
        if sign_longitude < boundary:
            return rulers[i]
    
    return rulers[-1]


def compute_d40_khavedamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D40 (Khavedamsa) - Auspicious and inauspicious effects (matrilineal).
    
    Each sign is divided into 40 parts of 0Â°45' each.
    
    Rules from BPHS:
    - Odd signs: Start from Aries
    - Even signs: Start from Libra
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 0.75)
    is_odd_sign = (d1_rashi.value % 2) == 0
    
    if is_odd_sign:
        return Rashi((Rashi.MESHA.value + division) % 12)
    else:
        return Rashi((Rashi.TULA.value + division) % 12)


def compute_d45_akshavedamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D45 (Akshavedamsa) - General well-being (patrilineal).
    
    Each sign is divided into 45 parts of 0Â°40' each.
    
    Rules from BPHS (based on modality):
    - Movable signs: Start from Aries
    - Fixed signs: Start from Leo
    - Dual signs: Start from Sagittarius
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / (30 / 45))
    
    modality = d1_rashi.value % 3
    starting_signs = [Rashi.MESHA, Rashi.SIMHA, Rashi.DHANU]
    
    return Rashi((starting_signs[modality].value + division) % 12)


def compute_d60_shashtyamsa(longitude: float, d1_rashi: Rashi) -> Rashi:
    """
    D60 (Shashtyamsa) - The most detailed varga, applicable to all matters.
    
    Each sign is divided into 60 parts of 0Â°30' (30 arc-minutes) each.
    
    Rules: Simply cycles through signs starting from the sign itself.
    
    The 60 divisions are also given individual names and deities in 
    classical texts, each with specific significations.
    """
    sign_longitude = longitude % 30
    division = int(sign_longitude / 0.5)
    
    return Rashi((d1_rashi.value + division) % 12)


# =============================================================================
# VARGA COMPUTATION DISPATCHER
# =============================================================================

# Map each VargaChart to its calculation function
VARGA_CALCULATORS = {
    VargaChart.D1: compute_d1,
    VargaChart.D2: compute_d2_hora,
    VargaChart.D3: compute_d3_drekkana,
    VargaChart.D4: compute_d4_chaturthamsa,
    VargaChart.D7: compute_d7_saptamsa,
    VargaChart.D9: compute_d9_navamsa,
    VargaChart.D10: compute_d10_dasamsa,
    VargaChart.D12: compute_d12_dwadasamsa,
    VargaChart.D16: compute_d16_shodasamsa,
    VargaChart.D20: compute_d20_vimsamsa,
    VargaChart.D24: compute_d24_chaturvimsamsa,
    VargaChart.D27: compute_d27_saptavimsamsa,
    VargaChart.D30: compute_d30_trimsamsa,
    VargaChart.D40: compute_d40_khavedamsa,
    VargaChart.D45: compute_d45_akshavedamsa,
    VargaChart.D60: compute_d60_shashtyamsa,
}


# =============================================================================
# MAIN COMPUTATION FUNCTIONS
# =============================================================================

def compute_varga_position(
    body: CelestialBody,
    longitude: float,
    varga: VargaChart
) -> VargaPosition:
    """
    Compute a planet's position in a specific divisional chart.
    
    Args:
        body: The celestial body
        longitude: The planet's sidereal longitude in the D1 chart
        varga: Which divisional chart to calculate
        
    Returns:
        VargaPosition with the sign in that varga
        
    Example:
        >>> # Moon at 15Â° Taurus in D1
        >>> pos = compute_varga_position(CelestialBody.MOON, 45.0, VargaChart.D9)
        >>> print(f"Moon's Navamsa: {pos.rashi.name}")
    """
    # Get D1 rashi from longitude
    d1_rashi = Rashi(int(longitude // 30) % 12)
    
    # Get the calculator for this varga
    calculator = VARGA_CALCULATORS.get(varga)
    if not calculator:
        raise ValueError(f"No calculator implemented for varga {varga}")
    
    # Calculate the varga rashi
    varga_rashi = calculator(longitude, d1_rashi)
    
    # Calculate which division within the D1 sign
    sign_longitude = longitude % 30
    divisor = varga.value
    division_size = 30 / divisor
    division_number = int(sign_longitude / division_size) + 1
    division_number = min(division_number, divisor)  # Cap at max
    
    return VargaPosition(
        body=body,
        varga=varga,
        rashi=varga_rashi,
        d1_rashi=d1_rashi,
        division_number=division_number
    )


def compute_all_vargas_for_planet(
    body: CelestialBody,
    longitude: float,
    vargas: Tuple[VargaChart, ...] = tuple(VargaChart)
) -> AllVargaPositions:
    """
    Compute all varga positions for a single planet.
    
    Args:
        body: The celestial body
        longitude: The planet's D1 longitude
        vargas: Which vargas to calculate (default: all 16)
        
    Returns:
        AllVargaPositions containing positions in all requested vargas
    """
    positions = {}
    for varga in vargas:
        try:
            positions[varga] = compute_varga_position(body, longitude, varga)
        except ValueError:
            continue  # Skip vargas without calculators
    
    return AllVargaPositions(body=body, positions=positions)


def compute_all_vargas(
    longitudes: Dict[CelestialBody, float],
    vargas: Tuple[VargaChart, ...] = (
        VargaChart.D1, VargaChart.D9, VargaChart.D10
    )
) -> Dict[CelestialBody, AllVargaPositions]:
    """
    Compute varga positions for all planets.
    
    Args:
        longitudes: Dictionary mapping planets to their D1 longitudes
        vargas: Which vargas to calculate (default: D1, D9, D10 - most commonly used)
        
    Returns:
        Dictionary mapping each planet to all its varga positions
        
    Example:
        >>> # Assuming you have planet longitudes from the main chart
        >>> all_vargas = compute_all_vargas(longitudes, (D1, D9, D10))
        >>> for planet, vargas in all_vargas.items():
        ...     d9 = vargas.get_position(VargaChart.D9)
        ...     print(f"{planet.name} Navamsa: {d9.rashi.name}")
    """
    result = {}
    for body, longitude in longitudes.items():
        result[body] = compute_all_vargas_for_planet(body, longitude, vargas)
    return result


# =============================================================================
# SPECIAL ANALYSIS FUNCTIONS
# =============================================================================

def find_vargottama_planets(
    all_vargas: Dict[CelestialBody, AllVargaPositions]
) -> List[CelestialBody]:
    """
    Find all planets that are vargottama (same sign in D1 and D9).
    
    Vargottama planets are considered strengthened and give good results
    related to their significations.
    
    Args:
        all_vargas: Dictionary of all varga positions from compute_all_vargas()
        
    Returns:
        List of planets that are vargottama
    """
    return [body for body, positions in all_vargas.items() 
            if positions.is_vargottama]


def get_varga_vimshopaka(
    all_vargas: Dict[CelestialBody, AllVargaPositions],
    scheme: str = "shadvarga"
) -> Dict[CelestialBody, float]:
    """
    Calculate Vimshopaka Bala (twenty-point strength) from vargas.
    
    This is a strength calculation based on the dignity of planets
    across multiple divisional charts. Different schemes use different
    sets of vargas.
    
    Schemes:
    - shadvarga: D1, D2, D3, D9, D12, D30 (6 vargas)
    - saptavarga: Above + D7 (7 vargas)
    - dashavarga: Above + D16, D20, D24, D40 (10 vargas)
    - shodashavarga: All 16 vargas
    
    Args:
        all_vargas: Dictionary of all varga positions
        scheme: Which scheme to use
        
    Returns:
        Dictionary mapping planets to their Vimshopaka score (0-20)
    
    Note: This is a simplified calculation. Full Vimshopaka also considers
    planetary dignity in each varga, not just sign placement.
    """
    schemes = {
        "shadvarga": (VargaChart.D1, VargaChart.D2, VargaChart.D3, 
                      VargaChart.D9, VargaChart.D12, VargaChart.D30),
        "saptavarga": (VargaChart.D1, VargaChart.D2, VargaChart.D3,
                       VargaChart.D7, VargaChart.D9, VargaChart.D12, 
                       VargaChart.D30),
        "dashavarga": (VargaChart.D1, VargaChart.D2, VargaChart.D3,
                       VargaChart.D7, VargaChart.D9, VargaChart.D10,
                       VargaChart.D12, VargaChart.D16, VargaChart.D30,
                       VargaChart.D60),
    }
    
    vargas_to_use = schemes.get(scheme, schemes["shadvarga"])
    max_score = len(vargas_to_use) * 20 / len(vargas_to_use)  # Normalize to 20
    
    scores = {}
    for body, positions in all_vargas.items():
        # Count favorable placements (simplified: own sign or exaltation)
        # Full implementation would check dignity in each varga
        score = 0
        for varga in vargas_to_use:
            pos = positions.get_position(varga)
            if pos:
                # Simple scoring: 1 point per varga (placeholder)
                # Real implementation checks dignity
                score += 1
        
        # Normalize to 20
        scores[body] = (score / len(vargas_to_use)) * 20
    
    return scores
