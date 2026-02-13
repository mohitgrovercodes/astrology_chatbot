# src\engines\core\datetime_utils.py
"""
Date/Time Utilities for Astronomical Calculations
=================================================

This module handles the critical conversion between civil time (what we use
in everyday life) and Julian Day (what astronomers use for calculations).

Why Julian Day?
--------------
Astronomers use Julian Day (JD) because it provides a continuous count of
days since January 1, 4713 BC. This makes astronomical calculations much
easier since you don't have to worry about calendar reforms, leap years,
month lengths, or timezone conversions.

Key Functions:
- datetime_to_julian_day: Convert civil time to JD
- julian_day_to_datetime: Convert JD back to civil time
- get_timezone_for_location: Auto-detect timezone from coordinates

Important Notes:
---------------
1. Julian Day starts at NOON (12:00), not midnight
2. We use Julian Day (UT), which is based on Universal Time
3. For ephemeris calculations, we need Julian Day in Ephemeris Time (TT)
   but the difference is negligible for most astrological purposes
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import pytz

try:
    from timezonefinder import TimezoneFinder
    TIMEZONE_FINDER_AVAILABLE = True
except ImportError:
    TimezoneFinder = None
    TIMEZONE_FINDER_AVAILABLE = False

from .exceptions import DateTimeError


# Constants for Julian Day calculations
JD_UNIX_EPOCH = 2440587.5  # Julian Day at 1970-01-01 00:00:00 UTC
SECONDS_PER_DAY = 86400.0
J2000 = 2451545.0  # Julian Day for J2000.0 epoch (2000-01-01 12:00:00 TT)

# Timezone finder singleton (lazy loaded)
_tz_finder: Optional[TimezoneFinder] = None


def _get_timezone_finder():
    """Get or create the timezone finder singleton."""
    global _tz_finder
    if not TIMEZONE_FINDER_AVAILABLE:
        return None
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return _tz_finder


def get_timezone_for_location(latitude: float, longitude: float) -> str:
    """
    Get the timezone string for a geographic location.
    
    This uses the TimezoneFinder library which contains a database of
    timezone boundaries. It works offline and is very accurate.
    
    Args:
        latitude: Latitude in degrees (-90 to +90)
        longitude: Longitude in degrees (-180 to +180)
        
    Returns:
        Timezone string like 'Asia/Kolkata', 'America/New_York', etc.
        Returns 'UTC' if timezone cannot be determined (e.g., open ocean)
        
    Example:
        >>> get_timezone_for_location(26.9124, 75.7873)
        'Asia/Kolkata'
    """
    try:
        tz_finder = _get_timezone_finder()
        if tz_finder is None:
            # TimezoneFinder not available, return UTC
            return "UTC"
        tz_str = tz_finder.timezone_at(lat=latitude, lng=longitude)
        if tz_str is None:
            return "UTC"
        return tz_str
    except Exception as e:
        # If anything fails, return UTC
        return "UTC"


def get_utc_offset_hours(
    dt: datetime,
    timezone_str: str
) -> float:
    """
    Get the UTC offset in hours for a given datetime and timezone.
    
    This accounts for Daylight Saving Time by checking the specific date.
    
    Args:
        dt: The datetime to check
        timezone_str: Timezone string like 'Asia/Kolkata'
        
    Returns:
        Offset from UTC in hours (e.g., +5.5 for India)
    """
    try:
        tz = pytz.timezone(timezone_str)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
        offset = dt.utcoffset()
        if offset is None:
            return 0.0
        return offset.total_seconds() / 3600
    except Exception as e:
        raise DateTimeError(
            f"Failed to get UTC offset",
            details={"timezone": timezone_str},
            original_error=e
        )


def datetime_to_julian_day(
    dt: datetime,
    timezone_str: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
) -> float:
    """
    Convert a datetime to Julian Day (UT).
    
    The Julian Day is the continuous count of days since the beginning
    of the Julian Period (January 1, 4713 BC in the proleptic Julian calendar).
    It's the standard time measure used in astronomical calculations.
    
    Args:
        dt: The datetime to convert
        timezone_str: Optional timezone string (e.g., 'Asia/Kolkata')
                     If not provided and lat/lon given, timezone is auto-detected
        latitude: Optional latitude for auto timezone detection
        longitude: Optional longitude for auto timezone detection
        
    Returns:
        Julian Day as a float (e.g., 2460000.5 for a recent date)
        
    Notes:
        - If dt is timezone-naive and no timezone info provided, UTC is assumed
        - The returned JD is always in Universal Time (UT)
        
    Example:
        >>> from datetime import datetime
        >>> jd = datetime_to_julian_day(
        ...     datetime(1990, 3, 15, 15, 30),
        ...     latitude=26.9124,
        ...     longitude=75.7873
        ... )
        >>> print(f"JD: {jd:.6f}")
    """
    try:
        # Handle timezone
        if dt.tzinfo is None:
            # Naive datetime - try to determine timezone
            if timezone_str:
                tz = pytz.timezone(timezone_str)
                dt = tz.localize(dt)
            elif latitude is not None and longitude is not None:
                tz_str = get_timezone_for_location(latitude, longitude)
                tz = pytz.timezone(tz_str)
                dt = tz.localize(dt)
            else:
                # Assume UTC if no timezone info available
                dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to UTC
        dt_utc = dt.astimezone(timezone.utc)
        
        # Calculate Julian Day from Unix timestamp
        timestamp = dt_utc.timestamp()
        jd = (timestamp / SECONDS_PER_DAY) + JD_UNIX_EPOCH
        
        return jd
        
    except Exception as e:
        if isinstance(e, DateTimeError):
            raise
        raise DateTimeError(
            f"Failed to convert datetime to Julian Day",
            details={"datetime": str(dt), "timezone": timezone_str},
            original_error=e
        )


def julian_day_to_datetime(
    jd: float,
    timezone_str: str = "UTC"
) -> datetime:
    """
    Convert Julian Day back to a datetime.
    
    Args:
        jd: Julian Day number
        timezone_str: Target timezone for the result (default: UTC)
        
    Returns:
        datetime object in the specified timezone
        
    Example:
        >>> dt = julian_day_to_datetime(2451545.0, "UTC")  # J2000.0
        >>> print(dt)  # 2000-01-01 12:00:00
    """
    try:
        # Convert JD to Unix timestamp
        timestamp = (jd - JD_UNIX_EPOCH) * SECONDS_PER_DAY
        
        # Create UTC datetime
        dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        # Convert to target timezone if not UTC
        if timezone_str != "UTC":
            tz = pytz.timezone(timezone_str)
            return dt_utc.astimezone(tz)
        
        return dt_utc
        
    except Exception as e:
        raise DateTimeError(
            f"Failed to convert Julian Day to datetime",
            details={"julian_day": jd, "timezone": timezone_str},
            original_error=e
        )


def get_delta_t(jd: float) -> float:
    """
    Calculate Delta T (TT - UT) for a given Julian Day.
    
    Delta T is the difference between Terrestrial Time (TT) and Universal
    Time (UT). It accounts for the gradual slowing of Earth's rotation.
    
    For most astrological purposes, this correction is negligible, but
    for high-precision work it should be considered.
    
    Args:
        jd: Julian Day
        
    Returns:
        Delta T in seconds
        
    Note:
        This uses a simplified polynomial approximation. For dates far
        from the present, accuracy decreases.
    """
    # Convert JD to year
    year = 2000.0 + (jd - J2000) / 365.25
    
    # Simplified polynomial for recent years (2005-2050)
    if 2005 <= year <= 2050:
        t = year - 2000
        delta_t = 62.92 + 0.32217 * t + 0.005589 * t**2
        return delta_t
    elif 1986 <= year < 2005:
        t = year - 2000
        delta_t = 63.86 + 0.3345 * t - 0.060374 * t**2
        return delta_t
    else:
        # For other years, use a rough approximation
        return 69.0  # Approximate value for 2020


def datetime_to_julian_century(dt: datetime) -> float:
    """
    Convert datetime to Julian centuries since J2000.0.
    
    Many astronomical formulas use Julian centuries as their time parameter.
    
    Args:
        dt: datetime object
        
    Returns:
        Julian centuries since J2000.0
    """
    jd = datetime_to_julian_day(dt)
    return (jd - J2000) / 36525.0


def get_sidereal_time(jd: float, longitude: float = 0.0) -> float:
    """
    Calculate Local Sidereal Time for a given JD and longitude.
    
    Sidereal time is the "star time" - it tracks Earth's rotation relative
    to the stars rather than the Sun. It's essential for determining
    the Ascendant and house cusps.
    
    Args:
        jd: Julian Day
        longitude: Geographic longitude in degrees (positive = East)
        
    Returns:
        Local Sidereal Time in degrees (0-360)
    """
    # Julian centuries since J2000.0
    T = (jd - J2000) / 36525.0
    
    # Mean sidereal time at Greenwich (in degrees)
    # Using the formula from the Astronomical Almanac
    theta0 = (280.46061837 + 360.98564736629 * (jd - J2000) +
              0.000387933 * T**2 - T**3 / 38710000.0)
    
    # Add longitude to get local sidereal time
    lst = theta0 + longitude
    
    # Normalize to 0-360
    lst = lst % 360
    if lst < 0:
        lst += 360
    
    return lst


def format_datetime_vedic(dt: datetime) -> str:
    """
    Format datetime in traditional Vedic style.
    
    Args:
        dt: datetime object
        
    Returns:
        Formatted string like "15 Mar 1990, 03:30 PM"
    """
    return dt.strftime("%d %b %Y, %I:%M %p")


def parse_birth_datetime(
    date_str: str,
    time_str: str,
    timezone_str: str
) -> datetime:
    """
    Parse birth date and time strings into a timezone-aware datetime.
    
    Args:
        date_str: Date in format "YYYY-MM-DD" or "DD/MM/YYYY"
        time_str: Time in format "HH:MM" or "HH:MM:SS"
        timezone_str: Timezone string
        
    Returns:
        Timezone-aware datetime
    """
    # Try different date formats
    date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]
    date_parsed = None
    
    for fmt in date_formats:
        try:
            date_parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    
    if date_parsed is None:
        raise DateTimeError(f"Could not parse date: {date_str}")
    
    # Parse time
    time_formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]
    time_parsed = None
    
    for fmt in time_formats:
        try:
            time_parsed = datetime.strptime(time_str, fmt).time()
            break
        except ValueError:
            continue
    
    if time_parsed is None:
        raise DateTimeError(f"Could not parse time: {time_str}")
    
    # Combine and localize
    dt = datetime.combine(date_parsed, time_parsed)
    tz = pytz.timezone(timezone_str)
    return tz.localize(dt)
