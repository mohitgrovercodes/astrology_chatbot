# src/safety/input_validator.py
# src\safety\input_validator.py
"""
Input Validator - Flexible Birth Data Validation
=================================================

Validates user birth data with flexibility and helpful error messages.
Designed to accept various formats and guide users to correct input.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import re


class ValidationStatus(Enum):
    """Status of validation."""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"  # Some fields valid, some missing/invalid
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass
class ValidationResult:
    """Result of input validation."""
    status: ValidationStatus
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    normalized_data: Optional[Dict[str, Any]] = None
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def get_friendly_message(self) -> str:
        """Get a user-friendly message about the validation."""
        if self.is_valid:
            if self.warnings:
                return "Your birth data looks good, though I have a small note: " + "; ".join(self.warnings)
            return "Your birth data is ready for analysis."
        else:
            if self.suggestions:
                return "I need a bit more clarity on your birth data: " + "; ".join(self.errors) + \
                       " Here's what might help: " + "; ".join(self.suggestions)
            return "I need some adjustments to your birth data: " + "; ".join(self.errors)


class InputValidator:
    """
    Flexible validator for birth data and other user inputs.
    Prioritizes helpfulness over strict rejection.
    """
    
    # Date format patterns
    DATE_PATTERNS = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),          # 1990-03-15
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%m/%d/%Y"),          # 03/15/1990
        (r"(\d{1,2})-(\d{1,2})-(\d{4})", "%d-%m-%Y"),          # 15-03-1990
        (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "%d.%m.%Y"),        # 15.03.1990
        (r"(\w+)\s+(\d{1,2}),?\s*(\d{4})", "month_name"),      # March 15, 1990
        (r"(\d{1,2})\s+(\w+),?\s*(\d{4})", "day_month_year"),  # 15 March 1990
    ]
    
    # Time format patterns
    TIME_PATTERNS = [
        (r"(\d{1,2}):(\d{2}):?(\d{2})?", "24h"),               # 14:30 or 14:30:00
        (r"(\d{1,2}):(\d{2})\s*(am|pm)", "12h"),               # 2:30 PM
        (r"(\d{1,2})\s*(am|pm)", "12h_short"),                 # 2 PM
    ]
    
    # Month names for parsing
    MONTH_NAMES = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12,
    }
    
    def __init__(self):
        """Initialize the input validator."""
        pass
    
    def validate_birth_data(
        self,
        date_of_birth: Optional[str] = None,
        time_of_birth: Optional[str] = None,
        place_of_birth: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timezone: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate birth data with flexible parsing.
        
        Returns ValidationResult with status, errors, and normalized data.
        """
        errors = []
        warnings = []
        suggestions = []
        normalized = {}
        
        # 1. Validate date
        if date_of_birth:
            date_result = self._validate_date(date_of_birth)
            if date_result[0]:
                normalized["date_of_birth"] = date_result[1]
                if date_result[2]:  # Warning
                    warnings.append(date_result[2])
            else:
                errors.append(f"Date format unclear: {date_of_birth}")
                suggestions.append("Try formats like YYYY-MM-DD, MM/DD/YYYY, or 'March 15, 1990'")
        else:
            errors.append("Date of birth is needed for accurate calculations")
            suggestions.append("Please provide your date of birth")
        
        # 2. Validate time
        if time_of_birth:
            time_result = self._validate_time(time_of_birth)
            if time_result[0]:
                normalized["time_of_birth"] = time_result[1]
                if time_result[2]:
                    warnings.append(time_result[2])
            else:
                # Time is less critical - can work with approximation
                warnings.append(f"Time format unclear: {time_of_birth}, using noon as approximation")
                normalized["time_of_birth"] = "12:00:00"
                normalized["time_approximate"] = True
        else:
            warnings.append("Without exact birth time, I'll use noon as an approximation for house positions")
            normalized["time_of_birth"] = "12:00:00"
            normalized["time_approximate"] = True
        
        # 3. Validate location
        if latitude is not None and longitude is not None:
            coord_result = self._validate_coordinates(latitude, longitude)
            if coord_result[0]:
                normalized["latitude"] = latitude
                normalized["longitude"] = longitude
                if coord_result[1]:
                    warnings.append(coord_result[1])
            else:
                errors.append(f"Coordinates seem invalid: lat={latitude}, lon={longitude}")
                suggestions.append("Latitude should be -90 to 90, longitude -180 to 180")
        elif place_of_birth:
            normalized["place_of_birth"] = place_of_birth
            # Note: In production, would do geocoding here
            warnings.append(f"Using place name '{place_of_birth}' - coordinates will be looked up")
        else:
            errors.append("Birth location is needed for house calculations")
            suggestions.append("Please provide either coordinates or a city/place name")
        
        # 4. Validate timezone
        if timezone:
            normalized["timezone"] = timezone
        else:
            # Will be inferred from coordinates in production
            warnings.append("Timezone will be inferred from birth location")
        
        # Determine overall status
        if not errors:
            status = ValidationStatus.VALID
            is_valid = True
        elif normalized.get("date_of_birth") and (normalized.get("latitude") or normalized.get("place_of_birth")):
            status = ValidationStatus.PARTIAL
            is_valid = True  # Can still do basic calculations
        else:
            status = ValidationStatus.INVALID
            is_valid = False
        
        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            normalized_data=normalized
        )
    
    def _validate_date(self, date_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize a date string.
        
        Returns: (is_valid, normalized_date, warning)
        """
        date_str = date_str.strip()
        
        # Try standard formats first
        for pattern, fmt in self.DATE_PATTERNS:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    if fmt == "month_name":
                        # Handle "March 15, 1990"
                        month_name = match.group(1).lower()
                        day = int(match.group(2))
                        year = int(match.group(3))
                        month = self.MONTH_NAMES.get(month_name)
                        if month:
                            parsed = datetime(year, month, day)
                    elif fmt == "day_month_year":
                        # Handle "15 March 1990"
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        year = int(match.group(3))
                        month = self.MONTH_NAMES.get(month_name)
                        if month:
                            parsed = datetime(year, month, day)
                    else:
                        parsed = datetime.strptime(date_str, fmt)
                    
                    # Validate reasonable range
                    warning = None
                    if parsed.year < 1900:
                        warning = "Birth year before 1900 may have limited historical data"
                    elif parsed.year > datetime.now().year:
                        return False, None, "Birth year cannot be in the future"
                    
                    # Normalize to ISO format
                    return True, parsed.strftime("%Y-%m-%d"), warning
                    
                except (ValueError, TypeError):
                    continue
        
        return False, None, None
    
    def _validate_time(self, time_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize a time string.
        
        Returns: (is_valid, normalized_time, warning)
        """
        time_str = time_str.strip().lower()
        
        # Try 24-hour format: 14:30 or 14:30:00
        match = re.match(r"(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            second = int(match.group(3)) if match.group(3) else 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                return True, f"{hour:02d}:{minute:02d}:{second:02d}", None
        
        # Try 12-hour format: 2:30 PM
        match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)$", time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            is_pm = match.group(3) == "pm"
            
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return True, f"{hour:02d}:{minute:02d}:00", None
        
        # Try short format: 2 PM
        match = re.match(r"(\d{1,2})\s*(am|pm)$", time_str)
        if match:
            hour = int(match.group(1))
            is_pm = match.group(2) == "pm"
            
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            
            if 0 <= hour <= 23:
                return True, f"{hour:02d}:00:00", "Using hour only, minute set to :00"
        
        return False, None, None
    
    def _validate_coordinates(
        self, latitude: float, longitude: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate geographic coordinates.
        
        Returns: (is_valid, warning)
        """
        warning = None
        
        # Check basic ranges
        if not (-90 <= latitude <= 90):
            return False, "Latitude must be between -90 and 90"
        
        if not (-180 <= longitude <= 180):
            return False, "Longitude must be between -180 and 180"
        
        # Check for suspicious values (likely defaults or errors)
        if latitude == 0 and longitude == 0:
            warning = "Coordinates (0,0) is in the Atlantic Ocean - is this correct?"
        
        # Check for extreme latitudes (polar regions)
        if abs(latitude) > 66.5:
            warning = "Polar region detected - some calculations may be approximate"
        
        return True, warning
    
    def validate_query(self, query: str) -> ValidationResult:
        """
        Validate a user query for basic issues.
        
        Args:
            query: The user's query text
            
        Returns:
            ValidationResult with any issues found
        """
        errors = []
        warnings = []
        suggestions = []
        
        if not query or not query.strip():
            errors.append("Query is empty")
            suggestions.append("Please type your question")
        elif len(query.strip()) < 3:
            warnings.append("Query is very short")
            suggestions.append("Could you share more details about what you'd like to know?")
        elif len(query) > 2000:
            warnings.append("Query is quite long")
            suggestions.append("I'll focus on the main question")
        
        is_valid = len(errors) == 0
        status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID
        
        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )


# Convenience function
def validate_birth_data(
    date_of_birth: Optional[str] = None,
    time_of_birth: Optional[str] = None,
    place_of_birth: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[str] = None
) -> ValidationResult:
    """Quick validation of birth data."""
    validator = InputValidator()
    return validator.validate_birth_data(
        date_of_birth=date_of_birth,
        time_of_birth=time_of_birth,
        place_of_birth=place_of_birth,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone
    )


# ========================================================================
# TESTING
# ========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("INPUT VALIDATOR TESTS")
    print("=" * 60)
    
    validator = InputValidator()
    
    # Test 1: Valid complete data
    print("\n1. Valid complete data:")
    result = validator.validate_birth_data(
        date_of_birth="1990-03-15",
        time_of_birth="14:30:00",
        latitude=26.9124,
        longitude=75.7873,
        timezone="Asia/Kolkata"
    )
    print(f"   Status: {result.status.value}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Message: {result.get_friendly_message()}")
    
    # Test 2: Various date formats
    print("\n2. Various date formats:")
    test_dates = [
        "1990-03-15",
        "03/15/1990",
        "March 15, 1990",
        "15 March 1990",
    ]
    for date in test_dates:
        r = validator.validate_birth_data(date_of_birth=date, latitude=0, longitude=0)
        norm_date = r.normalized_data.get("date_of_birth", "FAILED")
        print(f"   {date:20} -> {norm_date}")
    
    # Test 3: Time formats
    print("\n3. Various time formats:")
    test_times = [
        "14:30",
        "14:30:00",
        "2:30 PM",
        "2 PM",
    ]
    for time in test_times:
        r = validator.validate_birth_data(
            date_of_birth="1990-01-01",
            time_of_birth=time,
            latitude=0, longitude=0
        )
        norm_time = r.normalized_data.get("time_of_birth", "FAILED")
        print(f"   {time:15} -> {norm_time}")
    
    # Test 4: Missing data handling
    print("\n4. Missing time (graceful degradation):")
    result = validator.validate_birth_data(
        date_of_birth="1990-03-15",
        latitude=26.9124,
        longitude=75.7873
    )
    print(f"   Status: {result.status.value}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Warnings: {result.warnings}")
    
    print("\n" + "=" * 60)
    print("[DONE] All tests complete!")
    print("=" * 60)
