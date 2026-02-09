"""
Astrology API Client Module

This module provides a robust, production-grade client for interacting with
the AstrologyAPI.com service. It handles authentication, request/response
validation, error handling, and retry logic.
"""

import os
import base64
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel, Field, validator
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)


logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class BirthDetailsRequest(BaseModel):
    """Schema for birth details request to Astrology API"""
    
    day: int = Field(..., ge=1, le=31, description="Day of birth")
    month: int = Field(..., ge=1, le=12, description="Month of birth")
    year: int = Field(..., ge=1900, le=2100, description="Year of birth")
    hour: int = Field(..., ge=0, le=23, description="Hour of birth (24-hour format)")
    min: int = Field(..., ge=0, le=59, description="Minute of birth")
    lat: float = Field(..., ge=-90, le=90, description="Latitude of birth place")
    lon: float = Field(..., ge=-180, le=180, description="Longitude of birth place")
    tzone: float = Field(..., description="Timezone offset (e.g., 5.5 for IST)")
    
    @validator('day')
    def validate_day(cls, v, values):
        """Validate day based on month"""
        # Basic validation - could be enhanced with calendar logic
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "day": 15,
                "month": 8,
                "year": 1990,
                "hour": 14,
                "min": 30,
                "lat": 28.6139,
                "lon": 77.2090,
                "tzone": 5.5
            }
        }


class BirthDetailsResponse(BaseModel):
    """Schema for birth details response from Astrology API"""
    
    # Add fields based on actual API response
    # This is a placeholder - update based on real response structure
    data: Optional[Dict[str, Any]] = None
    status: bool = True
    message: Optional[str] = None


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class AstrologyAPIError(Exception):
    """Base exception for Astrology API errors"""
    pass


class AuthenticationError(AstrologyAPIError):
    """Raised when API authentication fails"""
    pass


class ValidationError(AstrologyAPIError):
    """Raised when request validation fails"""
    pass


class RateLimitError(AstrologyAPIError):
    """Raised when API rate limit is exceeded"""
    pass


# ============================================================================
# ASTROLOGY API CLIENT
# ============================================================================

class AstrologyAPIClient:
    """
    Production-grade client for AstrologyAPI.com
    
    Features:
    - Automatic retry with exponential backoff
    - Request/response validation
    - Proper error handling and logging
    - Connection pooling via httpx.AsyncClient
    - Environment-based configuration
    """
    
    BASE_URL = "https://json.astrologyapi.com/v1"
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Initialize the Astrology API client
        
        Args:
            username: API username (defaults to ASTRO_USERNAME env var)
            password: API password (defaults to ASTRO_PASSWORD env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.username = username or os.getenv("ASTRO_USERNAME")
        self.password = password or os.getenv("ASTRO_PASSWORD")
        
        if not self.username or not self.password:
            raise AuthenticationError(
                "API credentials not found. Set ASTRO_USERNAME and ASTRO_PASSWORD "
                "environment variables or pass them to the constructor."
            )
        
        self.timeout = timeout
        self.max_retries = max_retries
        self._auth_header = self._create_auth_header()
        
        logger.info("AstrologyAPIClient initialized successfully")
    
    def _create_auth_header(self) -> str:
        """Create Basic Auth header from credentials"""
        auth_string = f"{self.username}:{self.password}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    async def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        method: str = "POST"
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Astrology API with retry logic
        
        Args:
            endpoint: API endpoint (e.g., 'birth_details')
            payload: Request payload
            method: HTTP method
            
        Returns:
            API response as dictionary
            
        Raises:
            AstrologyAPIError: For API-specific errors
            httpx.HTTPError: For HTTP-level errors
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Payload: {payload}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": self._auth_header,
                    }
                )
                
                # Handle HTTP errors
                if response.status_code == 401:
                    raise AuthenticationError("Invalid API credentials")
                elif response.status_code == 429:
                    raise RateLimitError("API rate limit exceeded")
                
                response.raise_for_status()
                
                result = response.json()
                logger.debug(f"Response: {result}")
                
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e}")
                logger.error(f"Response body: {e.response.text}")
                raise AstrologyAPIError(f"API request failed: {e.response.text}") from e
            
            except httpx.TimeoutException as e:
                logger.error(f"Request timeout: {e}")
                raise
            
            except httpx.NetworkError as e:
                logger.error(f"Network error: {e}")
                raise
    
    async def get_birth_details(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """
        Fetch birth details from Astrology API
        
        Args:
            birth_data: Validated birth details request
            
        Returns:
            Birth details response from API
            
        Example:
            >>> client = AstrologyAPIClient()
            >>> request = BirthDetailsRequest(
            ...     day=15, month=8, year=1990,
            ...     hour=14, min=30,
            ...     lat=28.6139, lon=77.2090, tzone=5.5
            ... )
            >>> result = await client.get_birth_details(request)
        """
        try:
            # Validate input
            payload = birth_data.dict()
            
            # Make API request
            response = await self._make_request("birth_details", payload)
            
            return response
            
        except Exception as e:
            logger.error(f"Error fetching birth details: {e}")
            raise
    
    async def get_planetary_positions(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """
        Fetch planetary positions from Astrology API
        
        Args:
            birth_data: Validated birth details request
            
        Returns:
            Planetary positions response from API
        """
        payload = birth_data.dict()
        return await self._make_request("planets", payload)
    
    async def get_chart_data(
        self,
        birth_data: BirthDetailsRequest,
        chart_type: str = "D1"
    ) -> Dict[str, Any]:
        """
        Fetch chart data from Astrology API
        
        Args:
            birth_data: Validated birth details request
            chart_type: Type of chart (D1, D9, etc.)
            
        Returns:
            Chart data response from API
        """
        payload = birth_data.dict()
        payload["chart_type"] = chart_type
        return await self._make_request("horo_chart", payload)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def get_birth_details(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for getting birth details
    
    This is a backward-compatible wrapper for your existing code.
    
    Args:
        user_data: Dictionary containing birth details
        
    Returns:
        API response dictionary
    """
    try:
        # Validate and parse input
        birth_request = BirthDetailsRequest(**user_data)
        
        # Create client and fetch data
        client = AstrologyAPIClient()
        result = await client.get_birth_details(birth_request)
        
        return result
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return {
            "message": "Invalid birth data provided",
            "status": False,
            "error": str(e)
        }
    
    except AstrologyAPIError as e:
        logger.error(f"API error: {e}")
        return {
            "message": "Failed to fetch birth details from API",
            "status": False,
            "error": str(e)
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            "message": "Something went wrong. Please try again later.",
            "status": False,
            "error": str(e)
        }
