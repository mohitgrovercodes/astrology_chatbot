# src/integrations/astrology_api/__init__.py
# src\integrations\astrology_api\__init__.py
"""
Astrology API Integration Module

Extended client and production services for astrology data.
"""

from .client import (
    AstrologyAPIClient,
    BirthDetailsRequest,
    BirthDetailsResponse,
    AstrologyAPIError,
    AuthenticationError,
    ValidationError,
    RateLimitError,
    get_birth_details,
)

from .extended_client import ExtendedAstrologyAPIClient

__all__ = [
    # Base client
    "AstrologyAPIClient",
    "BirthDetailsRequest",
    "BirthDetailsResponse",
    "AstrologyAPIError",
    "AuthenticationError",
    "ValidationError",
    "RateLimitError",
    "get_birth_details",
    
    # Extended client
    "ExtendedAstrologyAPIClient",
]
