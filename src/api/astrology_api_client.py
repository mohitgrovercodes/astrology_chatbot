# src\api\astrology_api_client.py
"""
Third-Party Astrology API Client
==================================

Generic HTTP client for integrating with external astrology calculation APIs.
Supports multiple API providers with configurable endpoints and authentication.

Configuration via .env:
- ASTRO_API_BASE_URL: Base URL for the API
- ASTRO_API_KEY: API key for authentication
- ASTRO_API_TIMEOUT: Request timeout in seconds (default: 30)
- ASTRO_API_CACHE_TTL: Cache TTL in seconds (default: 3600)
"""

import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib


class AstrologyAPIClient:
    """Client for third-party astrology calculation APIs."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        cache_ttl: int = 3600
    ):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL for the API (e.g., "https://api.astrology.com/v1")
            api_key: API key for authentication
            timeout: Request timeout in seconds
            cache_ttl: Cache time-to-live in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        
        # HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=timeout,
            headers=self._get_default_headers()
        )
        
        print(f"[ASTRO-API] Initialized client: {base_url}")
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NakshatraAI/1.0"
        }
        
        if self.api_key:
            # Common authentication patterns
            headers["Authorization"] = f"Bearer {self.api_key}"
            # Alternative: headers["X-API-Key"] = self.api_key
        
        return headers
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key from endpoint and parameters."""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                print(f"[ASTRO-API] Cache hit: {cache_key[:8]}...")
                return data
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, data: Any):
        """Store data in cache."""
        self._cache[cache_key] = (data, datetime.now())
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/birth-chart")
            params: Query parameters
            data: Request body data
            use_cache: Whether to use caching
            
        Returns:
            Response data as dictionary
            
        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}{endpoint}"
        
        # Check cache for GET requests
        if method.upper() == "GET" and use_cache:
            cache_key = self._get_cache_key(endpoint, params or {})
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Make request
        try:
            print(f"[ASTRO-API] {method} {endpoint}")
            
            response = self.client.request(
                method=method,
                url=url,
                params=params,
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Cache GET requests
            if method.upper() == "GET" and use_cache:
                cache_key = self._get_cache_key(endpoint, params or {})
                self._set_cache(cache_key, result)
            
            return result
            
        except httpx.HTTPStatusError as e:
            print(f"[ASTRO-API] HTTP Error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"[ASTRO-API] Request Error: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"[ASTRO-API] JSON Decode Error: {e}")
            raise
    
    # =========================================================================
    # BIRTH CHART CALCULATIONS
    # =========================================================================
    
    def get_birth_chart(
        self,
        date: str,
        time: str,
        latitude: float,
        longitude: float,
        timezone: str = "UTC",
        system: str = "vedic"
    ) -> Dict[str, Any]:
        """
        Get birth chart from API.
        
        Args:
            date: Birth date (YYYY-MM-DD)
            time: Birth time (HH:MM:SS)
            latitude: Birth latitude
            longitude: Birth longitude
            timezone: Timezone (e.g., "Asia/Kolkata")
            system: Astrology system ("vedic" or "western")
            
        Returns:
            Birth chart data
        """
        data = {
            "date": date,
            "time": time,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "system": system
        }
        
        return self._make_request("POST", "/birth-chart", data=data)
    
    def get_planetary_positions(
        self,
        date: str,
        time: str,
        latitude: float,
        longitude: float,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Get planetary positions for a given date/time/location.
        
        Returns:
            Planetary positions data
        """
        params = {
            "date": date,
            "time": time,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone
        }
        
        return self._make_request("GET", "/planets", params=params)
    
    def get_houses(
        self,
        date: str,
        time: str,
        latitude: float,
        longitude: float,
        timezone: str = "UTC",
        house_system: str = "placidus"
    ) -> Dict[str, Any]:
        """
        Get house cusps.
        
        Args:
            house_system: House system (placidus, koch, equal, whole-sign, etc.)
            
        Returns:
            House data
        """
        params = {
            "date": date,
            "time": time,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "house_system": house_system
        }
        
        return self._make_request("GET", "/houses", params=params)
    
    # =========================================================================
    # DASHA & TRANSITS
    # =========================================================================
    
    def get_vimshottari_dasha(
        self,
        date: str,
        time: str,
        latitude: float,
        longitude: float,
        timezone: str = "UTC",
        current_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get Vimshottari Dasha periods.
        
        Args:
            current_date: Date for which to calculate current dasha (defaults to today)
            
        Returns:
            Dasha data
        """
        data = {
            "birth_date": date,
            "birth_time": time,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "current_date": current_date or datetime.now().strftime("%Y-%m-%d")
        }
        
        return self._make_request("POST", "/dasha/vimshottari", data=data)
    
    def get_transits(
        self,
        date: Optional[str] = None,
        latitude: float = 0.0,
        longitude: float = 0.0
    ) -> Dict[str, Any]:
        """
        Get current planetary transits.
        
        Args:
            date: Date for transits (defaults to today)
            latitude: Location latitude
            longitude: Location longitude
            
        Returns:
            Transit data
        """
        params = {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "latitude": latitude,
            "longitude": longitude
        }
        
        return self._make_request("GET", "/transits", params=params)
    
    # =========================================================================
    # COMPATIBILITY & PREDICTIONS
    # =========================================================================
    
    def get_compatibility(
        self,
        person1: Dict[str, Any],
        person2: Dict[str, Any],
        system: str = "vedic"
    ) -> Dict[str, Any]:
        """
        Get compatibility analysis between two people.
        
        Args:
            person1: First person's birth data (date, time, lat, lon, tz)
            person2: Second person's birth data
            system: Astrology system
            
        Returns:
            Compatibility analysis
        """
        data = {
            "person1": person1,
            "person2": person2,
            "system": system
        }
        
        return self._make_request("POST", "/compatibility", data=data)
    
    def get_predictions(
        self,
        birth_data: Dict[str, Any],
        prediction_type: str = "general",
        period: str = "month"
    ) -> Dict[str, Any]:
        """
        Get astrological predictions.
        
        Args:
            birth_data: Birth data (date, time, lat, lon, tz)
            prediction_type: Type of prediction (general, career, love, health, etc.)
            period: Prediction period (day, week, month, year)
            
        Returns:
            Predictions
        """
        data = {
            **birth_data,
            "type": prediction_type,
            "period": period
        }
        
        return self._make_request("POST", "/predictions", data=data)
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        print("[ASTRO-API] Cache cleared")
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
        print("[ASTRO-API] Client closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# =========================================================================
# FACTORY FUNCTION
# =========================================================================

def get_astrology_api_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[AstrologyAPIClient]:
    """
    Factory function to create API client from environment variables.
    
    Returns:
        AstrologyAPIClient instance or None if not configured
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    base_url = base_url or os.getenv("ASTRO_API_BASE_URL")
    api_key = api_key or os.getenv("ASTRO_API_KEY")
    
    if not base_url:
        print("[ASTRO-API] No API URL configured, skipping external API")
        return None
    
    timeout = int(os.getenv("ASTRO_API_TIMEOUT", "30"))
    cache_ttl = int(os.getenv("ASTRO_API_CACHE_TTL", "3600"))
    
    return AstrologyAPIClient(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        cache_ttl=cache_ttl
    )


# =========================================================================
# EXAMPLE USAGE
# =========================================================================

if __name__ == "__main__":
    # Example: Using the API client
    
    # Option 1: Direct initialization
    client = AstrologyAPIClient(
        base_url="https://api.example.com/v1",
        api_key="your-api-key-here"
    )
    
    # Option 2: From environment variables
    # client = get_astrology_api_client()
    
    if client:
        try:
            # Get birth chart
            chart = client.get_birth_chart(
                date="1990-05-15",
                time="14:30:00",
                latitude=28.6139,
                longitude=77.2090,
                timezone="Asia/Kolkata",
                system="vedic"
            )
            print("Birth Chart:", json.dumps(chart, indent=2))
            
            # Get current transits
            transits = client.get_transits(
                latitude=28.6139,
                longitude=77.2090
            )
            print("Transits:", json.dumps(transits, indent=2))
            
        finally:
            client.close()
