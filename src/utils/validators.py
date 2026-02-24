# src/utils/validators.py
# src\utils\validators.py
"""
Input Validators
================

Validates user inputs before passing to calculation engines.
Provides user-friendly error messages.
"""

from datetime import datetime
from typing import Tuple, Optional
import pytz

from .schemas import BirthDataInput
from src.engines.core.exceptions import ValidationError, DateTimeError


class BirthDataValidator:
    """Validates birth data inputs."""
    
    @staticmethod
    def validate_date_range(date_str: str) -> bool:
        """Check if date is within reasonable range (1900-2100)."""
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date.year < 1900:
                raise ValidationError(
                    "Birth year must be 1900 or later",
                    details={"provided_year": date.year}
                )
            if date.year > 2100:
                raise ValidationError(
                    "Birth year must be 2100 or earlier",
                    details={"provided_year": date.year}
                )
            return True
        except ValueError as e:
            raise ValidationError(f"Invalid date format: {e}")
    
    @staticmethod
    def validate_timezone(timezone_str: str) -> bool:
        """Validate timezone string."""
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValidationError(
                f"Unknown timezone: {timezone_str}",
                details={"provided_timezone": timezone_str}
            )
    
    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> bool:
        """Validate geographic coordinates."""
        if not -90 <= latitude <= 90:
            raise ValidationError(
                f"Latitude must be between -90 and 90 degrees",
                details={"provided_latitude": latitude}
            )
        
        if not -180 <= longitude <= 180:
            raise ValidationError(
                f"Longitude must be between -180 and 180 degrees",
                details={"provided_longitude": longitude}
            )
        
        return True
    
    @classmethod
    def validate_all(cls, birth_data: BirthDataInput) -> Tuple[bool, Optional[str]]:
        """
        Validate all fields in birth data.
        
        Returns:
            (is_valid, error_message)
        """
        try:
            cls.validate_date_range(birth_data.date)
            cls.validate_coordinates(birth_data.latitude, birth_data.longitude)
            
            if birth_data.timezone:
                cls.validate_timezone(birth_data.timezone)
            
            return True, None
            
        except ValidationError as e:
            return False, str(e)


def validate_birth_data(birth_data: BirthDataInput) -> BirthDataInput:
    """
    Validate birth data and return validated object.
    
    Args:
        birth_data: BirthDataInput to validate
        
    Returns:
        Validated BirthDataInput
        
    Raises:
        ValidationError: If validation fails
    """
    is_valid, error_msg = BirthDataValidator.validate_all(birth_data)
    
    if not is_valid:
        raise ValidationError(error_msg)
    
    return birth_data