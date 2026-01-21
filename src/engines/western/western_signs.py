"""
Zodiac Sign Utilities for Western Astrology
===========================================

This module provides functions for working with tropical zodiac signs,
including conversions between longitude and signs, element/modality
groupings, and sign relationships.

Usage Example:
-------------
    >>> from western.signs import longitude_to_sign, get_sign_info
    >>> 
    >>> # Convert longitude to sign
    >>> sign = longitude_to_sign(45.5)
    >>> print(sign)  # ZodiacSign.TAURUS
    >>> 
    >>> # Get sign information
    >>> info = get_sign_info(ZodiacSign.TAURUS)
    >>> print(f"{info.name} - {info.element.name} {info.modality.name}")
    >>> # "Taurus - EARTH FIXED"
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass

from src.engines.core.celestial_bodies import CelestialBody
from src.engines.western.western_constants import (
    ZodiacSign, SignInfo, SIGN_DATA,
    Element, Modality, Polarity,
    FIRE_SIGNS, EARTH_SIGNS, AIR_SIGNS, WATER_SIGNS,
    CARDINAL_SIGNS, FIXED_SIGNS, MUTABLE_SIGNS,
    MASCULINE_SIGNS, FEMININE_SIGNS,
    DOMICILE_RULERS,
)


def longitude_to_sign(longitude: float) -> ZodiacSign:
    """
    Convert ecliptic longitude to zodiac sign.
    
    In the tropical zodiac:
    - 0Â° - 30Â° = Aries
    - 30Â° - 60Â° = Taurus
    - ...and so on
    
    Args:
        longitude: Ecliptic longitude in degrees (0-360)
        
    Returns:
        The ZodiacSign corresponding to that longitude
        
    Example:
        >>> longitude_to_sign(0.0)    # 0Â° Aries
        ZodiacSign.ARIES
        >>> longitude_to_sign(45.5)   # 15.5Â° Taurus
        ZodiacSign.TAURUS
        >>> longitude_to_sign(359.9)  # 29.9Â° Pisces
        ZodiacSign.PISCES
    """
    # Normalize longitude to 0-360 range
    normalized = longitude % 360
    
    # Each sign is 30 degrees
    sign_index = int(normalized // 30) % 12
    
    return ZodiacSign(sign_index)


def get_degree_in_sign(longitude: float) -> float:
    """
    Get the degree position within a sign (0-30).
    
    Args:
        longitude: Ecliptic longitude in degrees
        
    Returns:
        Degrees within the current sign (0.0 - 29.999...)
        
    Example:
        >>> get_degree_in_sign(45.5)  # 15.5Â° Taurus
        15.5
        >>> get_degree_in_sign(0.0)   # 0Â° Aries
        0.0
    """
    return (longitude % 360) % 30


def get_sign_info(sign: ZodiacSign) -> SignInfo:
    """
    Get comprehensive information about a zodiac sign.
    
    Args:
        sign: The ZodiacSign to look up
        
    Returns:
        SignInfo dataclass with all sign properties
        
    Example:
        >>> info = get_sign_info(ZodiacSign.LEO)
        >>> print(f"{info.name}: {info.element.name} {info.modality.name}")
        Leo: FIRE FIXED
        >>> print(f"Ruled by: {info.ruler.name}")
        Ruled by: SUN
    """
    return SIGN_DATA[sign]


def format_position(longitude: float, include_seconds: bool = False) -> str:
    """
    Format a longitude as a human-readable position string.
    
    Args:
        longitude: Ecliptic longitude in degrees
        include_seconds: Whether to include arc-seconds in output
        
    Returns:
        Formatted string like "15Â°30' Taurus" or "15Â°30'45\" Taurus"
        
    Example:
        >>> format_position(45.5)
        "15Â°30' Taurus"
        >>> format_position(45.508333, include_seconds=True)
        "15Â°30'30\" Taurus"
    """
    sign = longitude_to_sign(longitude)
    degree_in_sign = get_degree_in_sign(longitude)
    
    degrees = int(degree_in_sign)
    minutes_decimal = (degree_in_sign - degrees) * 60
    minutes = int(minutes_decimal)
    
    sign_name = get_sign_info(sign).name
    
    if include_seconds:
        seconds = int((minutes_decimal - minutes) * 60)
        return f"{degrees}Â°{minutes:02d}'{seconds:02d}\" {sign_name}"
    else:
        return f"{degrees}Â°{minutes:02d}' {sign_name}"


def get_opposite_sign(sign: ZodiacSign) -> ZodiacSign:
    """
    Get the opposite sign in the zodiac (180Â° away).
    
    Opposition pairs are on the same polarity but different elements:
    - Aries â†” Libra (Cardinal Fire/Air)
    - Taurus â†” Scorpio (Fixed Earth/Water)
    - etc.
    
    Args:
        sign: The zodiac sign
        
    Returns:
        The opposite sign
        
    Example:
        >>> get_opposite_sign(ZodiacSign.ARIES)
        ZodiacSign.LIBRA
        >>> get_opposite_sign(ZodiacSign.CANCER)
        ZodiacSign.CAPRICORN
    """
    return ZodiacSign((sign.value + 6) % 12)


def signs_are_compatible_element(sign1: ZodiacSign, sign2: ZodiacSign) -> bool:
    """
    Check if two signs have compatible elements.
    
    Compatible element pairs:
    - Fire â†” Air (active, outward)
    - Earth â†” Water (receptive, inward)
    
    Same element is also compatible (trine relationship).
    
    Args:
        sign1: First zodiac sign
        sign2: Second zodiac sign
        
    Returns:
        True if elements are compatible
    """
    info1 = get_sign_info(sign1)
    info2 = get_sign_info(sign2)
    
    # Same element = compatible
    if info1.element == info2.element:
        return True
    
    # Fire and Air are compatible
    if {info1.element, info2.element} == {Element.FIRE, Element.AIR}:
        return True
    
    # Earth and Water are compatible
    if {info1.element, info2.element} == {Element.EARTH, Element.WATER}:
        return True
    
    return False


def get_signs_by_element(element: Element) -> Tuple[ZodiacSign, ...]:
    """
    Get all signs of a specific element (trine relationship).
    
    Args:
        element: The element to filter by
        
    Returns:
        Tuple of three signs in that element
        
    Example:
        >>> get_signs_by_element(Element.FIRE)
        (ZodiacSign.ARIES, ZodiacSign.LEO, ZodiacSign.SAGITTARIUS)
    """
    element_map = {
        Element.FIRE: FIRE_SIGNS,
        Element.EARTH: EARTH_SIGNS,
        Element.AIR: AIR_SIGNS,
        Element.WATER: WATER_SIGNS,
    }
    return element_map[element]


def get_signs_by_modality(modality: Modality) -> Tuple[ZodiacSign, ...]:
    """
    Get all signs of a specific modality (square relationship).
    
    Args:
        modality: The modality to filter by
        
    Returns:
        Tuple of four signs in that modality
        
    Example:
        >>> get_signs_by_modality(Modality.CARDINAL)
        (ZodiacSign.ARIES, ZodiacSign.CANCER, ZodiacSign.LIBRA, ZodiacSign.CAPRICORN)
    """
    modality_map = {
        Modality.CARDINAL: CARDINAL_SIGNS,
        Modality.FIXED: FIXED_SIGNS,
        Modality.MUTABLE: MUTABLE_SIGNS,
    }
    return modality_map[modality]


def get_signs_by_polarity(polarity: Polarity) -> Tuple[ZodiacSign, ...]:
    """
    Get all signs of a specific polarity.
    
    Args:
        polarity: The polarity to filter by
        
    Returns:
        Tuple of six signs with that polarity
    """
    if polarity == Polarity.MASCULINE:
        return MASCULINE_SIGNS
    else:
        return FEMININE_SIGNS


def get_ruling_planets(sign: ZodiacSign, include_modern: bool = True) -> List[CelestialBody]:
    """
    Get the ruling planet(s) for a sign.
    
    Args:
        sign: The zodiac sign
        include_modern: Whether to include modern rulerships
                       (Uranus, Neptune, Pluto)
        
    Returns:
        List of ruling planets (may contain 1 or 2 planets)
        
    Example:
        >>> get_ruling_planets(ZodiacSign.SCORPIO, include_modern=True)
        [CelestialBody.MARS, CelestialBody.PLUTO]
        >>> get_ruling_planets(ZodiacSign.SCORPIO, include_modern=False)
        [CelestialBody.MARS]
    """
    rulers = DOMICILE_RULERS[sign].copy()
    
    if not include_modern:
        # Filter out modern planets
        modern_planets = {CelestialBody.URANUS, CelestialBody.NEPTUNE, CelestialBody.PLUTO}
        rulers = [r for r in rulers if r not in modern_planets]
    
    return rulers


def calculate_angular_distance(longitude1: float, longitude2: float) -> float:
    """
    Calculate the angular distance between two points on the ecliptic.
    
    This always returns the shorter arc (0-180 degrees).
    
    Args:
        longitude1: First longitude in degrees
        longitude2: Second longitude in degrees
        
    Returns:
        Angular distance in degrees (0-180)
        
    Example:
        >>> calculate_angular_distance(0, 90)   # Square
        90.0
        >>> calculate_angular_distance(0, 270)  # Also square (shorter arc)
        90.0
        >>> calculate_angular_distance(0, 180)  # Opposition
        180.0
    """
    # Normalize both to 0-360
    lon1 = longitude1 % 360
    lon2 = longitude2 % 360
    
    # Calculate difference
    diff = abs(lon2 - lon1)
    
    # Return shorter arc
    return min(diff, 360 - diff)


def signs_are_same_element(sign1: ZodiacSign, sign2: ZodiacSign) -> bool:
    """
    Check if two signs share the same element (trine relationship).
    
    Args:
        sign1: First zodiac sign
        sign2: Second zodiac sign
        
    Returns:
        True if both signs are in the same element
    """
    info1 = get_sign_info(sign1)
    info2 = get_sign_info(sign2)
    return info1.element == info2.element


def signs_are_same_modality(sign1: ZodiacSign, sign2: ZodiacSign) -> bool:
    """
    Check if two signs share the same modality (square relationship).
    
    Args:
        sign1: First zodiac sign
        sign2: Second zodiac sign
        
    Returns:
        True if both signs have the same modality
    """
    info1 = get_sign_info(sign1)
    info2 = get_sign_info(sign2)
    return info1.modality == info2.modality


def signs_are_same_polarity(sign1: ZodiacSign, sign2: ZodiacSign) -> bool:
    """
    Check if two signs share the same polarity.
    
    Args:
        sign1: First zodiac sign
        sign2: Second zodiac sign
        
    Returns:
        True if both signs have the same polarity
    """
    info1 = get_sign_info(sign1)
    info2 = get_sign_info(sign2)
    return info1.polarity == info2.polarity


@dataclass(frozen=True)
class SignRelationship:
    """
    Describes the relationship between two zodiac signs.
    
    Attributes:
        sign1: First sign
        sign2: Second sign
        angle: Angular separation in 30Â° increments (0-6)
        same_element: Whether signs share element (trine)
        same_modality: Whether signs share modality (square)
        same_polarity: Whether signs share polarity
        relationship_name: Traditional name for this relationship
    """
    sign1: ZodiacSign
    sign2: ZodiacSign
    angle: int  # In 30Â° increments (0-6)
    same_element: bool
    same_modality: bool
    same_polarity: bool
    relationship_name: str


def get_sign_relationship(sign1: ZodiacSign, sign2: ZodiacSign) -> SignRelationship:
    """
    Analyze the relationship between two zodiac signs.
    
    Sign relationships are based on the angular distance:
    - 0 signs apart = Same sign (conjunction)
    - 1 sign apart = Semi-sextile (30Â°)
    - 2 signs apart = Sextile (60Â°)
    - 3 signs apart = Square (90Â°)
    - 4 signs apart = Trine (120Â°)
    - 5 signs apart = Quincunx (150Â°)
    - 6 signs apart = Opposition (180Â°)
    
    Args:
        sign1: First zodiac sign
        sign2: Second zodiac sign
        
    Returns:
        SignRelationship dataclass with analysis
    """
    # Calculate sign distance (0-6)
    distance = abs(sign2.value - sign1.value)
    if distance > 6:
        distance = 12 - distance
    
    # Determine relationship name
    relationship_names = {
        0: "Conjunction",
        1: "Semi-sextile",
        2: "Sextile",
        3: "Square",
        4: "Trine",
        5: "Quincunx",
        6: "Opposition",
    }
    
    return SignRelationship(
        sign1=sign1,
        sign2=sign2,
        angle=distance,
        same_element=signs_are_same_element(sign1, sign2),
        same_modality=signs_are_same_modality(sign1, sign2),
        same_polarity=signs_are_same_polarity(sign1, sign2),
        relationship_name=relationship_names[distance]
    )
