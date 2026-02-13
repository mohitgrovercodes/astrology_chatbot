# src\engines\western\western_aspects.py
"""
Aspect Calculations for Western Astrology
=========================================

This module handles the calculation and analysis of aspects between
planets in a Western astrological chart. Aspects are angular relationships
that describe how planets interact with each other.

Key Concepts:
------------
- Aspects are measured in degrees along the ecliptic
- Orbs define how close to exact an aspect must be
- Applying vs Separating aspects (whether getting closer or farther)
- Exact aspects are most powerful

Usage Example:
-------------
    >>> from western.aspects import calculate_aspect, calculate_all_aspects
    >>> 
    >>> # Check if two planets form an aspect
    >>> aspect = calculate_aspect(45.0, 135.0)  # 90Â° apart = square
    >>> if aspect:
    ...     print(f"{aspect.aspect_type.name} with {aspect.orb}Â° orb")
    >>> 
    >>> # Get all aspects in a chart
    >>> aspects = calculate_all_aspects(planet_positions)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

from src.engines.core.celestial_bodies import CelestialBody
from src.engines.core.ephemeris import PlanetPosition
from src.engines.western.western_constants import AspectType, AspectInfo, ASPECT_DATA, MAJOR_ASPECTS
from src.engines.western.western_signs import calculate_angular_distance


class AspectStrength(Enum):
    """
    Classification of aspect strength based on orb tightness.
    
    - EXACT: Within 1Â° of exact (most powerful)
    - CLOSE: 1-3Â° orb (strong)
    - MODERATE: 3-6Â° orb (moderate)
    - WIDE: 6-8Â° orb (weak but present)
    """
    EXACT = "exact"
    CLOSE = "close"
    MODERATE = "moderate"
    WIDE = "wide"


class AspectDirection(Enum):
    """
    Whether an aspect is applying (getting tighter) or separating.
    
    - APPLYING: Faster planet is approaching slower planet
    - SEPARATING: Faster planet is moving away from slower planet
    - STATIC: Neither planet is moving (rare)
    """
    APPLYING = "applying"
    SEPARATING = "separating"
    STATIC = "static"


@dataclass(frozen=True)
class Aspect:
    """
    Represents an aspect between two planets.
    
    Attributes:
        planet1: First planet (usually slower/outer planet)
        planet2: Second planet (usually faster/inner planet)
        aspect_type: Type of aspect (conjunction, trine, square, etc.)
        orb: How far from exact (in degrees)
        exact_angle: The theoretical exact angle for this aspect
        actual_angle: The actual angular distance between planets
        strength: Classification of aspect strength
        direction: Whether applying or separating
        is_major: Whether this is a major Ptolemaic aspect
        is_hard: Hard aspect (challenging) vs soft (flowing)
    """
    planet1: CelestialBody
    planet2: CelestialBody
    aspect_type: AspectType
    orb: float
    exact_angle: int
    actual_angle: float
    strength: AspectStrength
    direction: Optional[AspectDirection]
    is_major: bool
    is_hard: Optional[bool]
    
    @property
    def is_exact(self) -> bool:
        """Check if aspect is exact (within 1Â° orb)."""
        return self.orb < 1.0
    
    @property
    def is_close(self) -> bool:
        """Check if aspect is close (within 3Â° orb)."""
        return self.orb < 3.0
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"{self.planet1.name} {self.aspect_type.name} "
            f"{self.planet2.name} (orb: {self.orb:.2f}Â°)"
        )


def get_aspect_info(aspect_type: AspectType) -> AspectInfo:
    """
    Get information about an aspect type.
    
    Args:
        aspect_type: The aspect type to look up
        
    Returns:
        AspectInfo with default orb, angle, etc.
    """
    return ASPECT_DATA[aspect_type]


def calculate_aspect_orb(
    angle: float,
    aspect_type: AspectType,
    custom_orb: Optional[float] = None
) -> float:
    """
    Calculate the orb (deviation from exact) for a potential aspect.
    
    Args:
        angle: Actual angular distance between planets
        aspect_type: Type of aspect to check
        custom_orb: Custom orb allowance (overrides default)
        
    Returns:
        Orb in degrees (how far from exact)
    """
    aspect_info = get_aspect_info(aspect_type)
    exact_angle = aspect_info.angle
    
    # Calculate how far from exact
    deviation = abs(angle - exact_angle)
    
    return deviation


def classify_aspect_strength(orb: float, aspect_type: AspectType) -> AspectStrength:
    """
    Classify aspect strength based on orb tightness.
    
    Args:
        orb: Orb in degrees
        aspect_type: Type of aspect
        
    Returns:
        AspectStrength classification
    """
    if orb < 1.0:
        return AspectStrength.EXACT
    elif orb < 3.0:
        return AspectStrength.CLOSE
    elif orb < 6.0:
        return AspectStrength.MODERATE
    else:
        return AspectStrength.WIDE


def determine_aspect_direction(
    pos1: PlanetPosition,
    pos2: PlanetPosition
) -> AspectDirection:
    """
    Determine if an aspect is applying or separating.
    
    An aspect is applying if the faster-moving planet is approaching
    the slower one. It's separating if moving away.
    
    Args:
        pos1: Position of first planet
        pos2: Position of second planet
        
    Returns:
        AspectDirection (APPLYING, SEPARATING, or STATIC)
    """
    # If either planet is stationary, return STATIC
    if abs(pos1.speed_longitude) < 0.01 or abs(pos2.speed_longitude) < 0.01:
        return AspectDirection.STATIC
    
    # Determine which is faster (larger absolute speed)
    if abs(pos1.speed_longitude) > abs(pos2.speed_longitude):
        faster, slower = pos1, pos2
    else:
        faster, slower = pos2, pos1
    
    # Calculate current and future distances
    current_distance = calculate_angular_distance(
        faster.longitude, slower.longitude
    )
    
    # Project 1 day forward
    future_faster = (faster.longitude + faster.speed_longitude) % 360
    future_slower = (slower.longitude + slower.speed_longitude) % 360
    
    future_distance = calculate_angular_distance(
        future_faster, future_slower
    )
    
    # If distance is decreasing, it's applying
    if future_distance < current_distance:
        return AspectDirection.APPLYING
    else:
        return AspectDirection.SEPARATING


def calculate_aspect(
    longitude1: float,
    longitude2: float,
    aspect_type: AspectType,
    max_orb: Optional[float] = None,
    pos1: Optional[PlanetPosition] = None,
    pos2: Optional[PlanetPosition] = None,
) -> Optional[Aspect]:
    """
    Check if two positions form a specific aspect.
    
    Args:
        longitude1: Longitude of first planet
        longitude2: Longitude of second planet
        aspect_type: Which aspect to check for
        max_orb: Maximum orb to allow (defaults to aspect's standard orb)
        pos1: Full position data for first planet (for direction calculation)
        pos2: Full position data for second planet
        
    Returns:
        Aspect object if aspect is present within orb, None otherwise
    """
    aspect_info = get_aspect_info(aspect_type)
    allowed_orb = max_orb if max_orb is not None else aspect_info.default_orb
    
    # Calculate actual angular distance
    actual_angle = calculate_angular_distance(longitude1, longitude2)
    
    # Calculate orb
    orb = calculate_aspect_orb(actual_angle, aspect_type)
    
    # Check if within orb
    if orb > allowed_orb:
        return None
    
    # Classify strength
    strength = classify_aspect_strength(orb, aspect_type)
    
    # Determine direction if we have velocity data
    direction = None
    if pos1 is not None and pos2 is not None:
        direction = determine_aspect_direction(pos1, pos2)
    
    # Get planet bodies if available
    planet1 = pos1.body if pos1 else None
    planet2 = pos2.body if pos2 else None
    
    return Aspect(
        planet1=planet1,
        planet2=planet2,
        aspect_type=aspect_type,
        orb=orb,
        exact_angle=aspect_info.angle,
        actual_angle=actual_angle,
        strength=strength,
        direction=direction,
        is_major=aspect_info.is_major,
        is_hard=aspect_info.is_hard,
    )


def find_aspects_between_planets(
    pos1: PlanetPosition,
    pos2: PlanetPosition,
    aspect_types: Optional[Tuple[AspectType, ...]] = None,
    max_orb: Optional[float] = None,
) -> List[Aspect]:
    """
    Find all aspects between two planets.
    
    Args:
        pos1: Position of first planet
        pos2: Position of second planet
        aspect_types: Which aspects to check (defaults to major aspects)
        max_orb: Maximum orb to allow
        
    Returns:
        List of Aspect objects (may be empty)
    """
    if aspect_types is None:
        aspect_types = MAJOR_ASPECTS
    
    aspects = []
    
    for aspect_type in aspect_types:
        aspect = calculate_aspect(
            pos1.longitude,
            pos2.longitude,
            aspect_type,
            max_orb=max_orb,
            pos1=pos1,
            pos2=pos2,
        )
        
        if aspect is not None:
            aspects.append(aspect)
    
    return aspects


def calculate_all_aspects(
    positions: Dict[CelestialBody, PlanetPosition],
    aspect_types: Optional[Tuple[AspectType, ...]] = None,
    max_orb: Optional[float] = None,
    include_moon_nodes: bool = False,
) -> List[Aspect]:
    """
    Calculate all aspects in a chart.
    
    This finds every aspect between every pair of planets.
    
    Args:
        positions: Dictionary mapping planets to their positions
        aspect_types: Which aspects to check (defaults to major aspects)
        max_orb: Maximum orb to allow
        include_moon_nodes: Whether to include Rahu/Ketu (not typical in Western)
        
    Returns:
        List of all Aspect objects found
        
    Example:
        >>> aspects = calculate_all_aspects(positions)
        >>> for asp in aspects:
        ...     print(f"{asp.planet1.name} {asp.aspect_type.name} {asp.planet2.name}")
    """
    if aspect_types is None:
        aspect_types = MAJOR_ASPECTS
    
    aspects = []
    
    # Get list of planets to check
    planets = list(positions.keys())
    
    # Filter out nodes if requested
    if not include_moon_nodes:
        planets = [
            p for p in planets 
            if p not in (CelestialBody.RAHU, CelestialBody.KETU, 
                        CelestialBody.MEAN_NODE, CelestialBody.TRUE_NODE)
        ]
    
    # Check every pair of planets
    for i, planet1 in enumerate(planets):
        for planet2 in planets[i+1:]:  # Only check each pair once
            pos1 = positions[planet1]
            pos2 = positions[planet2]
            
            planet_aspects = find_aspects_between_planets(
                pos1, pos2, aspect_types, max_orb
            )
            
            aspects.extend(planet_aspects)
    
    return aspects


def get_aspects_to_planet(
    aspects: List[Aspect],
    planet: CelestialBody
) -> List[Aspect]:
    """
    Get all aspects involving a specific planet.
    
    Args:
        aspects: List of all aspects in chart
        planet: Planet to filter for
        
    Returns:
        List of aspects where this planet is involved
    """
    return [
        asp for asp in aspects 
        if asp.planet1 == planet or asp.planet2 == planet
    ]


def get_aspects_by_type(
    aspects: List[Aspect],
    aspect_type: AspectType
) -> List[Aspect]:
    """
    Get all aspects of a specific type.
    
    Args:
        aspects: List of all aspects
        aspect_type: Type to filter for
        
    Returns:
        List of aspects of this type
    """
    return [asp for asp in aspects if asp.aspect_type == aspect_type]


def get_hard_aspects(aspects: List[Aspect]) -> List[Aspect]:
    """
    Get all hard (challenging) aspects.
    
    Hard aspects include: squares, oppositions, semi-squares,
    sesquiquadrates, and quincunxes.
    
    Args:
        aspects: List of all aspects
        
    Returns:
        List of hard aspects only
    """
    return [asp for asp in aspects if asp.is_hard is True]


def get_soft_aspects(aspects: List[Aspect]) -> List[Aspect]:
    """
    Get all soft (flowing) aspects.
    
    Soft aspects include: trines, sextiles, semi-sextiles,
    quintiles, and biquintiles.
    
    Args:
        aspects: List of all aspects
        
    Returns:
        List of soft aspects only
    """
    return [asp for asp in aspects if asp.is_hard is False]


def count_aspect_patterns(aspects: List[Aspect]) -> Dict[str, int]:
    """
    Count aspects by type for statistical analysis.
    
    Args:
        aspects: List of all aspects
        
    Returns:
        Dictionary mapping aspect type names to counts
        
    Example:
        >>> counts = count_aspect_patterns(aspects)
        >>> print(f"Squares: {counts.get('SQUARE', 0)}")
    """
    counts = {}
    for aspect in aspects:
        aspect_name = aspect.aspect_type.name
        counts[aspect_name] = counts.get(aspect_name, 0) + 1
    return counts


@dataclass(frozen=True)
class AspectGrid:
    """
    Complete aspect grid for a chart.
    
    This organizes all aspects into an easy-to-query structure.
    
    Attributes:
        aspects: List of all aspects
        by_planet: Dictionary mapping each planet to its aspects
        by_type: Dictionary mapping aspect types to list of aspects
        major_aspects: Only major (Ptolemaic) aspects
        hard_aspects: Only hard/challenging aspects
        soft_aspects: Only soft/flowing aspects
    """
    aspects: Tuple[Aspect, ...]
    by_planet: Dict[CelestialBody, List[Aspect]]
    by_type: Dict[AspectType, List[Aspect]]
    major_aspects: Tuple[Aspect, ...]
    hard_aspects: Tuple[Aspect, ...]
    soft_aspects: Tuple[Aspect, ...]
    
    @property
    def aspect_count(self) -> int:
        """Total number of aspects."""
        return len(self.aspects)
    
    @property
    def exact_aspects(self) -> List[Aspect]:
        """Get all exact aspects (orb < 1Â°)."""
        return [asp for asp in self.aspects if asp.is_exact]
    
    def get_planet_aspects(self, planet: CelestialBody) -> List[Aspect]:
        """Get all aspects involving a planet."""
        return self.by_planet.get(planet, [])
    
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
            
        Returns:
            True if aspect exists
        """
        for aspect in self.aspects:
            planets_match = (
                {aspect.planet1, aspect.planet2} == {planet1, planet2}
            )
            
            if aspect_type is None:
                if planets_match:
                    return True
            else:
                if planets_match and aspect.aspect_type == aspect_type:
                    return True
        
        return False


def compute_aspect_grid(
    positions: Dict[CelestialBody, PlanetPosition],
    aspect_types: Optional[Tuple[AspectType, ...]] = None,
) -> AspectGrid:
    """
    Compute complete aspect grid for a chart.
    
    This is the main function to use for getting all aspects in an
    organized, queryable structure.
    
    Args:
        positions: Dictionary of planet positions
        aspect_types: Which aspects to calculate
        
    Returns:
        AspectGrid with all aspects organized
        
    Example:
        >>> grid = compute_aspect_grid(positions)
        >>> print(f"Total aspects: {grid.aspect_count}")
        >>> sun_aspects = grid.get_planet_aspects(CelestialBody.SUN)
    """
    # Calculate all aspects
    aspects = calculate_all_aspects(positions, aspect_types)
    
    # Organize by planet
    by_planet: Dict[CelestialBody, List[Aspect]] = {}
    for aspect in aspects:
        if aspect.planet1 not in by_planet:
            by_planet[aspect.planet1] = []
        if aspect.planet2 not in by_planet:
            by_planet[aspect.planet2] = []
        
        by_planet[aspect.planet1].append(aspect)
        by_planet[aspect.planet2].append(aspect)
    
    # Organize by type
    by_type: Dict[AspectType, List[Aspect]] = {}
    for aspect in aspects:
        if aspect.aspect_type not in by_type:
            by_type[aspect.aspect_type] = []
        by_type[aspect.aspect_type].append(aspect)
    
    # Filter for categories
    major = tuple(asp for asp in aspects if asp.is_major)
    hard = tuple(asp for asp in aspects if asp.is_hard is True)
    soft = tuple(asp for asp in aspects if asp.is_hard is False)
    
    return AspectGrid(
        aspects=tuple(aspects),
        by_planet=by_planet,
        by_type=by_type,
        major_aspects=major,
        hard_aspects=hard,
        soft_aspects=soft,
    )
