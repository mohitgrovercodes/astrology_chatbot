# src\engines\western\western_dignities.py
"""
Essential Dignities for Western Astrology
=========================================

This module calculates essential dignities - a planet's inherent strength
based on its zodiac sign position. This is one of the oldest astrological
techniques, dating back to Hellenistic astrology and refined by medieval
astrologers.

Essential Dignities (in order of strength):
------------------------------------------
1. Domicile/Rulership (+5): Planet in its own sign
2. Exaltation (+4): Planet in sign where it functions especially well
3. Triplicity (+3): Planet in compatible element (modern interpretation)
4. Neutral (0): Planet in other signs
5. Detriment (-4): Planet in sign opposite its rulership
6. Fall (-5): Planet in sign opposite its exaltation

Usage Example:
-------------
    >>> from western.dignities import calculate_dignity, get_dignity_score
    >>> 
    >>> # Check Sun's dignity in Leo (domicile)
    >>> dignity = calculate_dignity(CelestialBody.SUN, ZodiacSign.LEO)
    >>> print(dignity.dignity_type)  # EssentialDignity.DOMICILE
    >>> print(dignity.score)  # 5
    >>> 
    >>> # Get total dignity score for a chart
    >>> score = get_dignity_score(planet_positions)

Reference:
---------
Traditional system from Ptolemy's Tetrabiblos and William Lilly's
Christian Astrology. Modern interpretations include triplicity
(elemental harmony) as a dignity.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.engines.core.celestial_bodies import CelestialBody
from src.engines.core.ephemeris import PlanetPosition
from src.engines.western.western_constants import (
    ZodiacSign, EssentialDignity,
    Element, SIGN_DATA,
    DOMICILE_RULERS, EXALTATION, DETRIMENT, FALL
)
from src.engines.western.western_signs import longitude_to_sign, get_sign_info


@dataclass(frozen=True)
class PlanetDignity:
    """
    A planet's dignity status.
    
    Attributes:
        planet: The celestial body
        sign: Sign the planet is in
        dignity_type: Type of dignity (domicile, exaltation, etc.)
        score: Numerical score (-5 to +5)
        is_dignified: Whether planet is strong (positive dignity)
        is_debilitated: Whether planet is weak (negative dignity)
        description: Human-readable description
    """
    planet: CelestialBody
    sign: ZodiacSign
    dignity_type: EssentialDignity
    score: int
    is_dignified: bool
    is_debilitated: bool
    description: str
    
    @property
    def is_neutral(self) -> bool:
        """Check if planet is in neutral dignity."""
        return self.dignity_type == EssentialDignity.NEUTRAL
    
    @property
    def is_strong(self) -> bool:
        """Check if planet is strong (domicile or exaltation)."""
        return self.score >= 4
    
    @property
    def is_weak(self) -> bool:
        """Check if planet is weak (detriment or fall)."""
        return self.score <= -4


def is_planet_in_domicile(planet: CelestialBody, sign: ZodiacSign) -> bool:
    """
    Check if planet is in its domicile (rulership).
    
    Args:
        planet: The planet to check
        sign: The zodiac sign
        
    Returns:
        True if planet rules this sign
        
    Example:
        >>> is_planet_in_domicile(CelestialBody.MARS, ZodiacSign.ARIES)
        True
        >>> is_planet_in_domicile(CelestialBody.MARS, ZodiacSign.TAURUS)
        False
    """
    rulers = DOMICILE_RULERS.get(sign, [])
    if isinstance(rulers, list):
        return planet in rulers
    return planet == rulers


def is_planet_in_exaltation(planet: CelestialBody, sign: ZodiacSign) -> bool:
    """
    Check if planet is in its exaltation.
    
    Args:
        planet: The planet to check
        sign: The zodiac sign
        
    Returns:
        True if planet is exalted in this sign
        
    Example:
        >>> is_planet_in_exaltation(CelestialBody.SUN, ZodiacSign.ARIES)
        True
        >>> is_planet_in_exaltation(CelestialBody.MOON, ZodiacSign.TAURUS)
        True
    """
    exaltation_data = EXALTATION.get(planet)
    if not exaltation_data:
        return False
    return exaltation_data[0] == sign


def is_planet_in_detriment(planet: CelestialBody, sign: ZodiacSign) -> bool:
    """
    Check if planet is in its detriment.
    
    Detriment is the sign opposite the planet's rulership.
    
    Args:
        planet: The planet to check
        sign: The zodiac sign
        
    Returns:
        True if planet is in detriment
        
    Example:
        >>> is_planet_in_detriment(CelestialBody.MARS, ZodiacSign.LIBRA)
        True  # Mars rules Aries, opposite of Libra
    """
    detriment_signs = DETRIMENT.get(planet, [])
    if isinstance(detriment_signs, list):
        return sign in detriment_signs
    return sign == detriment_signs


def is_planet_in_fall(planet: CelestialBody, sign: ZodiacSign) -> bool:
    """
    Check if planet is in its fall.
    
    Fall is the sign opposite the planet's exaltation.
    
    Args:
        planet: The planet to check
        sign: The zodiac sign
        
    Returns:
        True if planet is in fall
        
    Example:
        >>> is_planet_in_fall(CelestialBody.SUN, ZodiacSign.LIBRA)
        True  # Sun exalted in Aries, fall in Libra
    """
    exaltation_data = FALL.get(planet)
    if not exaltation_data:
        return False
    return exaltation_data[0] == sign


def check_triplicity(planet: CelestialBody, sign: ZodiacSign) -> bool:
    """
    Check if planet is in compatible element (triplicity).
    
    In modern Western astrology, some consider planets stronger
    when in compatible elements:
    - Personal planets (Sun, Moon, Mercury, Venus, Mars) benefit
      from their element's triplicity
    
    Note: Traditional astrology has more complex triplicity rulers.
    This is a simplified modern interpretation.
    
    Args:
        planet: The planet to check
        sign: The zodiac sign
        
    Returns:
        True if there's elemental harmony
    """
    sign_info = get_sign_info(sign)
    
    # Simplified modern interpretation
    # In traditional astrology, each planet has triplicity rulers
    # that vary by day/night chart
    
    # For now, return False (not implemented in simplified version)
    # Full traditional triplicity would require day/night chart determination
    return False


def calculate_dignity(
    planet: CelestialBody,
    sign: ZodiacSign,
    include_triplicity: bool = False
) -> PlanetDignity:
    """
    Calculate a planet's essential dignity.
    
    This is the main function for dignity calculation.
    
    Args:
        planet: The celestial body
        sign: Sign the planet is in
        include_triplicity: Whether to include triplicity (modern)
        
    Returns:
        PlanetDignity with full analysis
        
    Example:
        >>> dignity = calculate_dignity(CelestialBody.VENUS, ZodiacSign.TAURUS)
        >>> print(f"{dignity.planet.name} in {dignity.sign.name}")
        >>> print(f"Dignity: {dignity.dignity_type.name} (score: {dignity.score})")
    """
    # Check each dignity level in order
    
    # 1. Domicile (strongest positive)
    if is_planet_in_domicile(planet, sign):
        return PlanetDignity(
            planet=planet,
            sign=sign,
            dignity_type=EssentialDignity.DOMICILE,
            score=5,
            is_dignified=True,
            is_debilitated=False,
            description=f"{planet.name} in domicile (rules {sign.name})"
        )
    
    # 2. Exaltation (strong positive)
    if is_planet_in_exaltation(planet, sign):
        return PlanetDignity(
            planet=planet,
            sign=sign,
            dignity_type=EssentialDignity.EXALTATION,
            score=4,
            is_dignified=True,
            is_debilitated=False,
            description=f"{planet.name} exalted in {sign.name}"
        )
    
    # 3. Fall (strong negative)
    if is_planet_in_fall(planet, sign):
        return PlanetDignity(
            planet=planet,
            sign=sign,
            dignity_type=EssentialDignity.FALL,
            score=-5,
            is_dignified=False,
            is_debilitated=True,
            description=f"{planet.name} in fall in {sign.name}"
        )
    
    # 4. Detriment (negative)
    if is_planet_in_detriment(planet, sign):
        return PlanetDignity(
            planet=planet,
            sign=sign,
            dignity_type=EssentialDignity.DETRIMENT,
            score=-4,
            is_dignified=False,
            is_debilitated=True,
            description=f"{planet.name} in detriment in {sign.name}"
        )
    
    # 5. Neutral (no special dignity)
    return PlanetDignity(
        planet=planet,
        sign=sign,
        dignity_type=EssentialDignity.NEUTRAL,
        score=0,
        is_dignified=False,
        is_debilitated=False,
        description=f"{planet.name} neutral in {sign.name}"
    )


def calculate_dignity_from_position(
    planet: CelestialBody,
    position: PlanetPosition
) -> PlanetDignity:
    """
    Calculate dignity from a planet position.
    
    Convenience wrapper that extracts the sign from position.
    
    Args:
        planet: The planet
        position: Planet's position data
        
    Returns:
        PlanetDignity with analysis
    """
    sign = longitude_to_sign(position.longitude)
    return calculate_dignity(planet, sign)


def calculate_all_dignities(
    positions: Dict[CelestialBody, PlanetPosition]
) -> Dict[CelestialBody, PlanetDignity]:
    """
    Calculate dignities for all planets in a chart.
    
    Args:
        positions: Dictionary of planet positions
        
    Returns:
        Dictionary mapping planets to their dignities
        
    Example:
        >>> dignities = calculate_all_dignities(positions)
        >>> for planet, dignity in dignities.items():
        ...     print(f"{planet.name}: {dignity.dignity_type.name} ({dignity.score})")
    """
    dignities = {}
    
    for planet, position in positions.items():
        dignity = calculate_dignity_from_position(planet, position)
        dignities[planet] = dignity
    
    return dignities


def get_dignity_score(
    positions: Dict[CelestialBody, PlanetPosition]
) -> int:
    """
    Calculate total dignity score for a chart.
    
    This sums all individual planet dignity scores to give an
    overall measure of chart strength.
    
    Args:
        positions: Planet positions
        
    Returns:
        Total dignity score (can be negative)
        
    Interpretation:
        - High positive: Chart has strong dignity
        - Around zero: Average/balanced
        - Negative: Chart has debilitated planets
    """
    dignities = calculate_all_dignities(positions)
    return sum(d.score for d in dignities.values())


def get_dignified_planets(
    dignities: Dict[CelestialBody, PlanetDignity]
) -> List[Tuple[CelestialBody, PlanetDignity]]:
    """
    Get list of dignified planets (in domicile or exaltation).
    
    Args:
        dignities: Planet dignities
        
    Returns:
        List of (planet, dignity) tuples for dignified planets
    """
    return [
        (planet, dignity) 
        for planet, dignity in dignities.items()
        if dignity.is_dignified
    ]


def get_debilitated_planets(
    dignities: Dict[CelestialBody, PlanetDignity]
) -> List[Tuple[CelestialBody, PlanetDignity]]:
    """
    Get list of debilitated planets (in detriment or fall).
    
    Args:
        dignities: Planet dignities
        
    Returns:
        List of (planet, dignity) tuples for debilitated planets
    """
    return [
        (planet, dignity)
        for planet, dignity in dignities.items()
        if dignity.is_debilitated
    ]


def get_neutral_planets(
    dignities: Dict[CelestialBody, PlanetDignity]
) -> List[Tuple[CelestialBody, PlanetDignity]]:
    """
    Get list of planets in neutral dignity.
    
    Args:
        dignities: Planet dignities
        
    Returns:
        List of (planet, dignity) tuples for neutral planets
    """
    return [
        (planet, dignity)
        for planet, dignity in dignities.items()
        if dignity.is_neutral
    ]


@dataclass(frozen=True)
class DignityAnalysis:
    """
    Complete dignity analysis for a chart.
    
    Attributes:
        dignities: All planet dignities
        total_score: Sum of all dignity scores
        dignified_planets: Planets in domicile or exaltation
        debilitated_planets: Planets in detriment or fall
        neutral_planets: Planets with no special dignity
        strongest_planet: Planet with highest dignity
        weakest_planet: Planet with lowest dignity
    """
    dignities: Dict[CelestialBody, PlanetDignity]
    total_score: int
    dignified_planets: Tuple[Tuple[CelestialBody, PlanetDignity], ...]
    debilitated_planets: Tuple[Tuple[CelestialBody, PlanetDignity], ...]
    neutral_planets: Tuple[Tuple[CelestialBody, PlanetDignity], ...]
    strongest_planet: Optional[Tuple[CelestialBody, PlanetDignity]]
    weakest_planet: Optional[Tuple[CelestialBody, PlanetDignity]]
    
    @property
    def has_dignified_planets(self) -> bool:
        """Check if chart has any dignified planets."""
        return len(self.dignified_planets) > 0
    
    @property
    def has_debilitated_planets(self) -> bool:
        """Check if chart has any debilitated planets."""
        return len(self.debilitated_planets) > 0
    
    @property
    def dignity_ratio(self) -> float:
        """
        Calculate ratio of dignified to debilitated planets.
        
        Returns:
            Positive number indicating balance
            >1 = more dignified than debilitated
            <1 = more debilitated than dignified
        """
        dignified_count = len(self.dignified_planets)
        debilitated_count = len(self.debilitated_planets)
        
        if debilitated_count == 0:
            return float('inf') if dignified_count > 0 else 1.0
        
        return dignified_count / debilitated_count


def compute_dignity_analysis(
    positions: Dict[CelestialBody, PlanetPosition]
) -> DignityAnalysis:
    """
    Compute complete dignity analysis for a chart.
    
    This is the main function to use for comprehensive dignity assessment.
    
    Args:
        positions: Planet positions
        
    Returns:
        DignityAnalysis with complete breakdown
        
    Example:
        >>> analysis = compute_dignity_analysis(positions)
        >>> print(f"Total dignity score: {analysis.total_score}")
        >>> print(f"Dignified planets: {len(analysis.dignified_planets)}")
        >>> if analysis.strongest_planet:
        ...     planet, dignity = analysis.strongest_planet
        ...     print(f"Strongest: {planet.name} ({dignity.score})")
    """
    # Calculate all dignities
    dignities = calculate_all_dignities(positions)
    
    # Get categories
    dignified = tuple(get_dignified_planets(dignities))
    debilitated = tuple(get_debilitated_planets(dignities))
    neutral = tuple(get_neutral_planets(dignities))
    
    # Find strongest and weakest
    sorted_by_score = sorted(
        dignities.items(),
        key=lambda x: x[1].score,
        reverse=True
    )
    
    strongest = sorted_by_score[0] if sorted_by_score else None
    weakest = sorted_by_score[-1] if sorted_by_score else None
    
    # Calculate total score
    total_score = sum(d.score for d in dignities.values())
    
    return DignityAnalysis(
        dignities=dignities,
        total_score=total_score,
        dignified_planets=dignified,
        debilitated_planets=debilitated,
        neutral_planets=neutral,
        strongest_planet=strongest,
        weakest_planet=weakest,
    )


def get_planetary_strength_ranking(
    positions: Dict[CelestialBody, PlanetPosition]
) -> List[Tuple[CelestialBody, int]]:
    """
    Rank planets by dignity strength.
    
    Args:
        positions: Planet positions
        
    Returns:
        List of (planet, score) tuples, sorted strongest to weakest
        
    Example:
        >>> ranking = get_planetary_strength_ranking(positions)
        >>> for i, (planet, score) in enumerate(ranking, 1):
        ...     print(f"{i}. {planet.name}: {score}")
    """
    dignities = calculate_all_dignities(positions)
    
    return sorted(
        [(planet, dignity.score) for planet, dignity in dignities.items()],
        key=lambda x: x[1],
        reverse=True
    )
