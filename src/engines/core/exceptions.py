# src\engines\core\exceptions.py
"""
Custom Exceptions for the Nakshatra Chatbot Astrology Engine
============================================================

This module defines a hierarchy of exceptions used throughout the astrology
calculation engine. Having specific exceptions allows for better error handling,
debugging, and user feedback.

Exception Hierarchy:
    AstrologyEngineError (base)
    ├── EphemerisError (Swiss Ephemeris issues)
    ├── DateTimeError (date/time conversion problems)
    ├── CoordinateError (invalid geographic coordinates)
    ├── CalculationError (mathematical/astrological calculation failures)
    ├── ValidationError (input validation failures)
    ├── ConfigurationError (missing or invalid configuration)
    └── DataError (data loading/parsing issues)
"""

from typing import Any, Dict, Optional


class AstrologyEngineError(Exception):
    """
    Base exception for all astrology engine errors.
    
    All custom exceptions in this module inherit from this class,
    allowing callers to catch all engine-related errors with a single
    except clause if desired.
    
    Attributes:
        message: Human-readable error description
        details: Optional dictionary with additional context
        original_error: The underlying exception that caused this error, if any
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)
    
    def __str__(self) -> str:
        base_msg = self.message
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg = f"{base_msg} [{detail_str}]"
        if self.original_error:
            base_msg = f"{base_msg} (caused by: {self.original_error})"
        return base_msg


class EphemerisError(AstrologyEngineError):
    """
    Errors related to Swiss Ephemeris calculations.
    
    Raised when:
    - Ephemeris files are missing or corrupted
    - Planet calculation fails
    - Invalid celestial body requested
    - Date outside ephemeris range
    """
    pass


class DateTimeError(AstrologyEngineError):
    """
    Errors related to date/time processing.
    
    Raised when:
    - Invalid date format provided
    - Date outside valid range
    - Timezone detection fails
    - Julian Day conversion errors
    """
    pass


class CoordinateError(AstrologyEngineError):
    """
    Errors related to geographical coordinates.
    
    Raised when:
    - Latitude out of range (-90 to +90)
    - Longitude out of range (-180 to +180)
    - Invalid coordinate format
    """
    pass


class CalculationError(AstrologyEngineError):
    """
    Errors during astrological calculations.
    
    Raised when:
    - Mathematical overflow/underflow
    - Invalid intermediate results
    - Algorithm convergence failure
    - Division by zero scenarios
    """
    pass


class ValidationError(AstrologyEngineError):
    """
    Errors during input validation.
    
    Raised when:
    - Required fields missing
    - Field values out of acceptable range
    - Invalid enum values
    - Type mismatches
    """
    pass


class ConfigurationError(AstrologyEngineError):
    """
    Errors related to configuration.
    
    Raised when:
    - Required configuration missing
    - Invalid configuration values
    - Conflicting settings
    """
    pass


class DataError(AstrologyEngineError):
    """
    Errors related to data loading and parsing.
    
    Raised when:
    - Data file not found
    - Invalid data format
    - Parsing failures
    - Data integrity issues
    """
    pass
