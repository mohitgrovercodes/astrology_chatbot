# src/engines/vedic/graha_stats.py
# src\engines\vedic\graha_stats.py
"""
Layer 1: Raw Astronomy - Graha (Planet) Statistics
===================================================

This is the first computational layer in our pipeline. It takes raw ephemeris
data (planetary longitudes from Swiss Ephemeris) and computes immediate
astronomical facts about each planet:

- Speed (degrees per day)
- Retrograde status
- Combustion status (too close to Sun)
- Planetary war status (too close to another planet)

What This Layer Does NOT Do:
----------------------------
- It doesn't interpret what retrograde "means"
- It doesn't know about Rashis or Nakshatras (that's Layer 2)
- It doesn't compute Dashas or Yogas (that's Layer 3-4)

This layer is pure astronomy - it could theoretically be used by Western
astrology too, though we've included combustion thresholds from Vedic texts.

Dependencies:
- engine/core/ephemeris.py (planetary positions)
- vedic/constants.py (combustion thresholds)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
from datetime import datetime

from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS
from src.engines.core.ephemeris import (
    PlanetPosition,
    get_all_sidereal_positions,
    get_sidereal_position,
)
from src.engines.vedic.vedic_constants import (
    Ayanamsa,
    COMBUSTION_DEGREES,
    COMBUSTION_DEGREES_RETROGRADE,
    PLANETARY_WAR_ORB,
    WAR_PARTICIPANTS,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class MotionStatus(Enum):
    """Direction of planetary motion."""
    DIRECT = "direct"           # Normal forward motion
    RETROGRADE = "retrograde"   # Apparent backward motion
    STATIONARY = "stationary"   # Changing direction (very slow)


class CombustionStatus(Enum):
    """Combustion (proximity to Sun) status."""
    NOT_COMBUST = "not_combust"
    COMBUST = "combust"
    DEEPLY_COMBUST = "deeply_combust"  # Within 3 degrees


@dataclass(frozen=True)
class GrahaMotion:
    """
    Motion data for a single planet.
    
    Attributes:
        body: The celestial body
        speed: Longitudinal speed in degrees/day
        status: Direct, retrograde, or stationary
        is_fast: True if moving faster than average
    """
    body: CelestialBody
    speed: float
    status: MotionStatus
    is_fast: bool
    
    @property
    def is_retrograde(self) -> bool:
        return self.status == MotionStatus.RETROGRADE
    
    @property
    def is_stationary(self) -> bool:
        return self.status == MotionStatus.STATIONARY


@dataclass(frozen=True)
class CombustionData:
    """
    Combustion data for a planet.
    
    Combustion occurs when a planet is too close to the Sun.
    A combust planet is considered weakened.
    
    Attributes:
        body: The planet being checked
        is_combust: True if combust
        distance_from_sun: Angular distance from Sun in degrees
        combustion_threshold: The threshold for this planet
        status: Detailed combustion status
    """
    body: CelestialBody
    is_combust: bool
    distance_from_sun: float
    combustion_threshold: float
    status: CombustionStatus


@dataclass(frozen=True)
class PlanetaryWar:
    """
    Data about a planetary war between two planets.
    
    Planetary war (Graha Yuddha) occurs when two planets are within
    1 degree of each other. Only Tara Grahas (Mars, Mercury, Jupiter,
    Venus, Saturn) can participate.
    
    The winner is typically determined by brightness (not computed here)
    or by having more northern latitude.
    
    Attributes:
        planet1: First planet in the war
        planet2: Second planet in the war
        separation: Angular distance between them
        winner: Planet with more northern latitude (preliminary winner)
        loser: The other planet
    """
    planet1: CelestialBody
    planet2: CelestialBody
    separation: float
    winner: CelestialBody
    loser: CelestialBody


@dataclass
class AllGrahaStats:
    """
    Complete astronomical statistics for all planets at a moment in time.
    
    This is the main output of Layer 1 - it contains all computed
    astronomical facts that other layers will use.
    """
    positions: Dict[CelestialBody, PlanetPosition]
    motions: Dict[CelestialBody, GrahaMotion]
    combustions: Dict[CelestialBody, CombustionData]
    planetary_wars: List[PlanetaryWar]
    julian_day: float
    ayanamsa_value: float
    
    def get_position(self, body: CelestialBody) -> PlanetPosition:
        """Get position for a specific planet."""
        return self.positions[body]
    
    def is_retrograde(self, body: CelestialBody) -> bool:
        """Check if a planet is retrograde."""
        return self.motions[body].is_retrograde
    
    def is_combust(self, body: CelestialBody) -> bool:
        """Check if a planet is combust."""
        return self.combustions.get(body, CombustionData(
            body=body, is_combust=False, distance_from_sun=999.0,
            combustion_threshold=0.0, status=CombustionStatus.NOT_COMBUST
        )).is_combust
    
    def get_wars_for(self, body: CelestialBody) -> List[PlanetaryWar]:
        """Get all planetary wars involving a specific planet."""
        return [war for war in self.planetary_wars 
                if war.planet1 == body or war.planet2 == body]


# =============================================================================
# AVERAGE SPEEDS (for determining fast/slow motion)
# =============================================================================

# Average daily motion in degrees (approximate)
AVERAGE_SPEEDS: Dict[CelestialBody, float] = {
    CelestialBody.SUN: 0.9856,      # About 1Â° per day
    CelestialBody.MOON: 13.176,     # About 13Â° per day
    CelestialBody.MERCURY: 1.383,   # Variable, often retrograde
    CelestialBody.VENUS: 1.2,       # Variable
    CelestialBody.MARS: 0.524,      # About 0.5Â° per day
    CelestialBody.JUPITER: 0.083,   # About 5' per day
    CelestialBody.SATURN: 0.033,    # About 2' per day
    CelestialBody.RAHU: -0.053,     # Always retrograde (mean motion)
    CelestialBody.KETU: -0.053,     # Always retrograde (mean motion)
}

# Threshold for considering a planet "stationary" (degrees/day)
STATIONARY_THRESHOLD: float = 0.02


# =============================================================================
# COMPUTATION FUNCTIONS
# =============================================================================

def compute_motion_status(position: PlanetPosition) -> GrahaMotion:
    """
    Determine the motion status of a planet from its position data.
    
    Args:
        position: PlanetPosition containing speed information
        
    Returns:
        GrahaMotion with status and speed analysis
    """
    speed = position.speed_longitude
    body = position.body
    
    # Determine motion status
    if abs(speed) < STATIONARY_THRESHOLD:
        status = MotionStatus.STATIONARY
    elif speed < 0:
        status = MotionStatus.RETROGRADE
    else:
        status = MotionStatus.DIRECT
    
    # Determine if moving faster than average
    avg_speed = AVERAGE_SPEEDS.get(body, 1.0)
    is_fast = abs(speed) > abs(avg_speed)
    
    return GrahaMotion(
        body=body,
        speed=speed,
        status=status,
        is_fast=is_fast
    )


def compute_combustion(
    planet_position: PlanetPosition,
    sun_position: PlanetPosition
) -> CombustionData:
    """
    Determine if a planet is combust (too close to the Sun).
    
    Combustion weakens a planet's significations. The Sun itself
    and the lunar nodes (Rahu/Ketu) are never considered combust.
    
    Args:
        planet_position: Position of the planet to check
        sun_position: Position of the Sun
        
    Returns:
        CombustionData with combustion status and details
    """
    body = planet_position.body
    
    # Sun is never combust, neither are Rahu/Ketu
    if body in (CelestialBody.SUN, CelestialBody.RAHU, CelestialBody.KETU):
        return CombustionData(
            body=body,
            is_combust=False,
            distance_from_sun=0.0 if body == CelestialBody.SUN else 999.0,
            combustion_threshold=0.0,
            status=CombustionStatus.NOT_COMBUST
        )
    
    # Calculate angular distance from Sun
    distance = abs(planet_position.longitude - sun_position.longitude)
    # Handle wrap-around at 360Â°
    if distance > 180:
        distance = 360 - distance
    
    # Get combustion threshold
    is_retrograde = planet_position.speed_longitude < 0
    if is_retrograde and body in COMBUSTION_DEGREES_RETROGRADE:
        threshold = COMBUSTION_DEGREES_RETROGRADE[body]
    else:
        threshold = COMBUSTION_DEGREES.get(body, 10.0)
    
    # Determine status
    if distance <= 3.0:
        status = CombustionStatus.DEEPLY_COMBUST
        is_combust = True
    elif distance <= threshold:
        status = CombustionStatus.COMBUST
        is_combust = True
    else:
        status = CombustionStatus.NOT_COMBUST
        is_combust = False
    
    return CombustionData(
        body=body,
        is_combust=is_combust,
        distance_from_sun=distance,
        combustion_threshold=threshold,
        status=status
    )


def compute_planetary_wars(
    positions: Dict[CelestialBody, PlanetPosition]
) -> List[PlanetaryWar]:
    """
    Detect all planetary wars in the current planetary configuration.
    
    A planetary war occurs when two Tara Grahas (Mars, Mercury, Jupiter,
    Venus, Saturn) are within 1 degree of each other.
    
    Args:
        positions: Dictionary of all planetary positions
        
    Returns:
        List of PlanetaryWar instances (may be empty)
    """
    wars: List[PlanetaryWar] = []
    
    # Get positions of war participants only
    participants = [(body, positions[body]) 
                   for body in WAR_PARTICIPANTS 
                   if body in positions]
    
    # Check each pair
    for i in range(len(participants)):
        for j in range(i + 1, len(participants)):
            body1, pos1 = participants[i]
            body2, pos2 = participants[j]
            
            # Calculate separation
            separation = abs(pos1.longitude - pos2.longitude)
            if separation > 180:
                separation = 360 - separation
            
            # Check if within war orb
            if separation <= PLANETARY_WAR_ORB:
                # Determine winner by northern latitude
                # (planet further north wins)
                if pos1.latitude >= pos2.latitude:
                    winner, loser = body1, body2
                else:
                    winner, loser = body2, body1
                
                wars.append(PlanetaryWar(
                    planet1=body1,
                    planet2=body2,
                    separation=separation,
                    winner=winner,
                    loser=loser
                ))
    
    return wars


def compute_all_graha_stats(
    julian_day: float,
    bodies: Tuple[CelestialBody, ...] = VEDIC_GRAHAS,
    ayanamsa: Ayanamsa = Ayanamsa.LAHIRI,
    precomputed_positions: Optional[Dict[CelestialBody, PlanetPosition]] = None
) -> AllGrahaStats:
    """
    Compute complete astronomical statistics for all planets.

    This is the main entry point for Layer 1. It computes positions,
    motion status, combustion, and planetary wars for all specified bodies.

    Args:
        julian_day: Julian Day number for the calculation
        bodies: Tuple of planets to calculate (default: 9 Vedic grahas)
        ayanamsa: Ayanamsa to use for sidereal positions
        precomputed_positions: Optional pre-computed positions to avoid
            duplicate Swiss Ephemeris calls. If None, positions are computed.

    Returns:
        AllGrahaStats containing all computed data
    """
    # Use pre-computed positions if provided, otherwise compute them
    positions = precomputed_positions or get_all_sidereal_positions(julian_day, bodies, ayanamsa)
    
    # Get ayanamsa value for reference
    from src.engines.core.ephemeris import get_ayanamsa_value
    ayanamsa_value = get_ayanamsa_value(julian_day, ayanamsa)
    
    # Compute motion for each planet
    motions: Dict[CelestialBody, GrahaMotion] = {}
    for body, position in positions.items():
        motions[body] = compute_motion_status(position)
    
    # Compute combustion for each planet
    combustions: Dict[CelestialBody, CombustionData] = {}
    sun_position = positions.get(CelestialBody.SUN)
    if sun_position:
        for body, position in positions.items():
            combustions[body] = compute_combustion(position, sun_position)
    
    # Compute planetary wars
    wars = compute_planetary_wars(positions)
    
    return AllGrahaStats(
        positions=positions,
        motions=motions,
        combustions=combustions,
        planetary_wars=wars,
        julian_day=julian_day,
        ayanamsa_value=ayanamsa_value
    )


# =============================================================================
# INDIVIDUAL PLANET QUERIES (Convenience Functions)
# =============================================================================

def get_graha_speed(position: PlanetPosition) -> float:
    """Get the speed of a planet in degrees per day."""
    return position.speed_longitude


def is_graha_retrograde(position: PlanetPosition) -> bool:
    """Check if a planet is retrograde."""
    return position.speed_longitude < 0


def is_graha_stationary(position: PlanetPosition) -> bool:
    """Check if a planet is stationary (very slow motion)."""
    return abs(position.speed_longitude) < STATIONARY_THRESHOLD


def is_graha_fast(position: PlanetPosition) -> bool:
    """Check if a planet is moving faster than its average speed."""
    avg = AVERAGE_SPEEDS.get(position.body, 1.0)
    return abs(position.speed_longitude) > abs(avg)


def get_distance_from_sun(
    planet_longitude: float,
    sun_longitude: float
) -> float:
    """
    Calculate the angular distance between a planet and the Sun.
    
    Args:
        planet_longitude: Planet's longitude in degrees
        sun_longitude: Sun's longitude in degrees
        
    Returns:
        Angular distance in degrees (0-180)
    """
    distance = abs(planet_longitude - sun_longitude)
    if distance > 180:
        distance = 360 - distance
    return distance