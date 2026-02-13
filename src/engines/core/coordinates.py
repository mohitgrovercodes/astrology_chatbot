# src\engines\core\coordinates.py
"""
Geographic Coordinates and Position Handling
=============================================

This module handles geographic positions on Earth, which are essential
for calculating local ascendants, house cusps, and other location-dependent
astrological factors.

Key Concepts:
------------
- Latitude: North-South position (-90Â° to +90Â°)
- Longitude: East-West position (-180Â° to +180Â°)
- Altitude: Height above sea level (affects some calculations)

Coordinate Systems:
------------------
- Geographic: Standard lat/lon coordinates
- Geocentric: Earth-centered coordinates used in some ephemeris calculations
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import math

from .exceptions import CoordinateError, ValidationError


@dataclass(frozen=True)
class GeoPosition:
    """
    Geographic position on Earth.
    
    This immutable dataclass represents a location on Earth's surface.
    It validates inputs and provides useful derived properties for
    astronomical calculations.
    
    Attributes:
        latitude: Latitude in degrees (-90 to +90, positive = North)
        longitude: Longitude in degrees (-180 to +180, positive = East)
        altitude: Altitude in meters above sea level (default: 0)
    
    Example:
        >>> jaipur = GeoPosition(latitude=26.9124, longitude=75.7873)
        >>> print(f"Hemisphere: {'N' if jaipur.is_northern_hemisphere else 'S'}")
        Hemisphere: N
    """
    latitude: float
    longitude: float
    altitude: float = 0.0
    
    def __post_init__(self):
        """Validate coordinates after initialization."""
        if not -90 <= self.latitude <= 90:
            raise CoordinateError(
                f"Latitude must be between -90 and 90 degrees",
                details={"provided_latitude": self.latitude}
            )
        if not -180 <= self.longitude <= 180:
            raise CoordinateError(
                f"Longitude must be between -180 and 180 degrees",
                details={"provided_longitude": self.longitude}
            )
        if self.altitude < -500 or self.altitude > 10000:
            raise CoordinateError(
                f"Altitude seems unrealistic (should be -500m to 10000m)",
                details={"provided_altitude": self.altitude}
            )
    
    @property
    def is_northern_hemisphere(self) -> bool:
        """Check if location is in the Northern Hemisphere."""
        return self.latitude >= 0
    
    @property
    def is_southern_hemisphere(self) -> bool:
        """Check if location is in the Southern Hemisphere."""
        return self.latitude < 0
    
    @property
    def is_eastern_hemisphere(self) -> bool:
        """Check if location is in the Eastern Hemisphere."""
        return self.longitude >= 0
    
    @property
    def is_western_hemisphere(self) -> bool:
        """Check if location is in the Western Hemisphere."""
        return self.longitude < 0
    
    @property
    def is_tropical(self) -> bool:
        """Check if location is in the tropics (-23.5Â° to +23.5Â°)."""
        return -23.5 <= self.latitude <= 23.5
    
    @property
    def is_polar(self) -> bool:
        """Check if location is in polar regions (|lat| > 66.5Â°)."""
        return abs(self.latitude) > 66.5
    
    @property
    def latitude_radians(self) -> float:
        """Get latitude in radians."""
        return math.radians(self.latitude)
    
    @property
    def longitude_radians(self) -> float:
        """Get longitude in radians."""
        return math.radians(self.longitude)
    
    def distance_to(self, other: 'GeoPosition') -> float:
        """
        Calculate approximate distance to another position in kilometers.
        
        Uses the Haversine formula for great-circle distance.
        
        Args:
            other: Another GeoPosition
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = self.latitude_radians, self.longitude_radians
        lat2, lon2 = other.latitude_radians, other.longitude_radians
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def as_tuple(self) -> Tuple[float, float, float]:
        """Return coordinates as a tuple (lat, lon, alt)."""
        return (self.latitude, self.longitude, self.altitude)
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.4f}Â°{lat_dir}, {abs(self.longitude):.4f}Â°{lon_dir}"


def create_position(
    latitude: float,
    longitude: float,
    altitude: float = 0.0
) -> GeoPosition:
    """
    Create a geographic position with validation.
    
    This is a convenience function that creates a GeoPosition instance
    with validation. It's useful when you want explicit function-style
    creation rather than class instantiation.
    
    Args:
        latitude: Latitude in degrees (-90 to +90)
        longitude: Longitude in degrees (-180 to +180)
        altitude: Altitude in meters (default: 0)
        
    Returns:
        Validated GeoPosition instance
        
    Raises:
        CoordinateError: If coordinates are invalid
        
    Example:
        >>> pos = create_position(26.9124, 75.7873)  # Jaipur
        >>> print(pos)
        26.9124Â°N, 75.7873Â°E
    """
    return GeoPosition(latitude=latitude, longitude=longitude, altitude=altitude)


def parse_dms_to_decimal(
    degrees: int,
    minutes: int,
    seconds: float,
    direction: str
) -> float:
    """
    Convert degrees-minutes-seconds to decimal degrees.
    
    Args:
        degrees: Degree component (positive integer)
        minutes: Minutes component (0-59)
        seconds: Seconds component (0-60)
        direction: 'N', 'S', 'E', or 'W'
        
    Returns:
        Decimal degrees (negative for S or W)
        
    Example:
        >>> parse_dms_to_decimal(26, 54, 44, 'N')
        26.912222...
    """
    if direction.upper() not in ('N', 'S', 'E', 'W'):
        raise ValidationError(f"Direction must be N, S, E, or W, got: {direction}")
    
    decimal = abs(degrees) + minutes / 60 + seconds / 3600
    
    if direction.upper() in ('S', 'W'):
        decimal = -decimal
    
    return decimal


def decimal_to_dms(decimal_degrees: float) -> Tuple[int, int, float, str]:
    """
    Convert decimal degrees to degrees-minutes-seconds.
    
    Args:
        decimal_degrees: Decimal degree value
        
    Returns:
        Tuple of (degrees, minutes, seconds, direction)
        
    Example:
        >>> decimal_to_dms(26.9124)
        (26, 54, 44.64, 'N' or 'E')
    """
    is_negative = decimal_degrees < 0
    decimal_degrees = abs(decimal_degrees)
    
    degrees = int(decimal_degrees)
    minutes_float = (decimal_degrees - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    # Direction depends on whether this is lat or lon - caller must determine
    direction = '-' if is_negative else '+'
    
    return (degrees, minutes, seconds, direction)


# Common city coordinates for testing and convenience
COMMON_LOCATIONS = {
    "jaipur": GeoPosition(26.9124, 75.7873),
    "delhi": GeoPosition(28.6139, 77.2090),
    "mumbai": GeoPosition(19.0760, 72.8777),
    "bangalore": GeoPosition(12.9716, 77.5946),
    "chennai": GeoPosition(13.0827, 80.2707),
    "kolkata": GeoPosition(22.5726, 88.3639),
    "hyderabad": GeoPosition(17.3850, 78.4867),
    "pune": GeoPosition(18.5204, 73.8567),
    "varanasi": GeoPosition(25.3176, 82.9739),
    "london": GeoPosition(51.5074, -0.1278),
    "new_york": GeoPosition(40.7128, -74.0060),
    "los_angeles": GeoPosition(34.0522, -118.2437),
    "tokyo": GeoPosition(35.6762, 139.6503),
    "sydney": GeoPosition(-33.8688, 151.2093),
}


def get_common_location(city: str) -> Optional[GeoPosition]:
    """
    Get coordinates for a common city.
    
    Args:
        city: City name (case-insensitive)
        
    Returns:
        GeoPosition if found, None otherwise
    """
    return COMMON_LOCATIONS.get(city.lower())
