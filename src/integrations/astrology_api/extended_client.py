# src\integrations\astrology_api\extended_client.py
"""
Extended Astrology API Client

Extends the base client with all production API endpoints for:
- Birth charts (multiple systems)
- Dashas (Vimshottari, Yogini, etc.)
- Ayanamsa calculations
- Horoscopes (daily, weekly, monthly, yearly)
- Transits
- Divisional charts (D1-D60)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import date

from .client import (
    AstrologyAPIClient,
    BirthDetailsRequest,
    AstrologyAPIError
)


logger = logging.getLogger(__name__)


# ============================================================================
# EXTENDED API CLIENT
# ============================================================================

class ExtendedAstrologyAPIClient(AstrologyAPIClient):
    """
    Extended client with all production astrology API endpoints
    
    Inherits authentication, retry logic, and error handling from base client.
    Adds methods for all astrology calculation types.
    """
    
    # ========================================================================
    # BIRTH CHART METHODS
    # ========================================================================
    
    async def get_tropical_birth_chart(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get tropical (Western) birth chart"""
        payload = birth_data.dict()
        payload["ayanamsa"] = "true_lahiri"  # Can be configured
        return await self._make_request("western_horoscope", payload)
    
    async def get_vedic_birth_chart(
        self,
        birth_data: BirthDetailsRequest,
        ayanamsa: str = "lahiri"
    ) -> Dict[str, Any]:
        """
        Get Vedic birth chart
        
        Args:
            birth_data: Birth details
            ayanamsa: Ayanamsa system (lahiri, raman, krishnamurti, etc.)
        """
        payload = birth_data.dict()
        payload["ayanamsa"] = ayanamsa
        return await self._make_request("birth_details", payload)
    
    # ========================================================================
    # PLANETARY POSITIONS
    # ========================================================================
    
    async def get_planetary_positions(
        self,
        birth_data: BirthDetailsRequest,
        system: str = "vedic"
    ) -> Dict[str, Any]:
        """
        Get planetary positions
        
        Args:
            birth_data: Birth details
            system: 'vedic' or 'western'
        """
        payload = birth_data.dict()
        endpoint = "planets" if system == "vedic" else "planets/tropical"
        return await self._make_request(endpoint, payload)
    
    async def get_planet_details(
        self,
        birth_data: BirthDetailsRequest,
        planet: str
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific planet
        
        Args:
            birth_data: Birth details
            planet: Planet name (sun, moon, mars, etc.)
        """
        payload = birth_data.dict()
        return await self._make_request(f"planet_details/{planet}", payload)
    
    # ========================================================================
    # DASHA SYSTEMS
    # ========================================================================
    
    async def get_vimshottari_dasha(
        self,
        birth_data: BirthDetailsRequest,
        years: int = 120
    ) -> Dict[str, Any]:
        """
        Get Vimshottari Dasha periods
        
        Args:
            birth_data: Birth details
            years: Number of years to calculate (default: 120)
        """
        payload = birth_data.dict()
        payload["years"] = years
        return await self._make_request("major_vdasha", payload)
    
    async def get_yogini_dasha(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get Yogini Dasha periods"""
        payload = birth_data.dict()
        return await self._make_request("major_yogini_dasha", payload)
    
    async def get_char_dasha(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get Char Dasha periods"""
        payload = birth_data.dict()
        return await self._make_request("major_chara_dasha", payload)
    
    async def get_current_dasha(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get current running Dasha period"""
        payload = birth_data.dict()
        return await self._make_request("current_vdasha", payload)
    
    # ========================================================================
    # AYANAMSA
    # ========================================================================
    
    async def get_ayanamsa(
        self,
        birth_data: BirthDetailsRequest,
        ayanamsa_type: str = "lahiri"
    ) -> Dict[str, Any]:
        """
        Get Ayanamsa calculation
        
        Args:
            birth_data: Birth details
            ayanamsa_type: Type of ayanamsa (lahiri, raman, krishnamurti, etc.)
        """
        payload = birth_data.dict()
        payload["ayanamsa"] = ayanamsa_type
        return await self._make_request("ayanamsa", payload)
    
    # ========================================================================
    # DIVISIONAL CHARTS
    # ========================================================================
    
    async def get_divisional_chart(
        self,
        birth_data: BirthDetailsRequest,
        division: str = "D1"
    ) -> Dict[str, Any]:
        """
        Get divisional chart (Varga charts)
        
        Args:
            birth_data: Birth details
            division: Chart division (D1, D2, D3, ..., D60)
        """
        payload = birth_data.dict()
        payload["division"] = division
        return await self._make_request("horo_chart", payload)
    
    async def get_all_divisional_charts(
        self,
        birth_data: BirthDetailsRequest,
        divisions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get multiple divisional charts
        
        Args:
            birth_data: Birth details
            divisions: List of divisions (defaults to common ones)
        """
        if divisions is None:
            divisions = ["D1", "D2", "D3", "D9", "D10", "D12", "D30", "D60"]
        
        results = {}
        for division in divisions:
            try:
                results[division] = await self.get_divisional_chart(birth_data, division)
            except Exception as e:
                logger.error(f"Error fetching {division} chart: {e}")
                results[division] = {"error": str(e)}
        
        return results
    
    # ========================================================================
    # HOROSCOPES
    # ========================================================================
    
    async def get_daily_horoscope(
        self,
        birth_data: BirthDetailsRequest,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get daily horoscope
        
        Args:
            birth_data: Birth details
            target_date: Date for horoscope (defaults to today)
        """
        payload = birth_data.dict()
        if target_date:
            payload["date"] = target_date.isoformat()
        return await self._make_request("sun_sign_prediction/daily", payload)
    
    async def get_weekly_horoscope(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get weekly horoscope"""
        payload = birth_data.dict()
        return await self._make_request("sun_sign_prediction/weekly", payload)
    
    async def get_monthly_horoscope(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get monthly horoscope"""
        payload = birth_data.dict()
        return await self._make_request("sun_sign_prediction/monthly", payload)
    
    async def get_yearly_horoscope(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get yearly horoscope"""
        payload = birth_data.dict()
        return await self._make_request("sun_sign_prediction/yearly", payload)
    
    # ========================================================================
    # TRANSITS
    # ========================================================================
    
    async def get_current_transits(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get current planetary transits"""
        payload = birth_data.dict()
        return await self._make_request("planet_transit", payload)
    
    async def get_transit_predictions(
        self,
        birth_data: BirthDetailsRequest,
        planet: str
    ) -> Dict[str, Any]:
        """
        Get transit predictions for a specific planet
        
        Args:
            birth_data: Birth details
            planet: Planet name (jupiter, saturn, etc.)
        """
        payload = birth_data.dict()
        return await self._make_request(f"transit_prediction/{planet}", payload)
    
    # ========================================================================
    # COMPATIBILITY
    # ========================================================================
    
    async def get_compatibility_score(
        self,
        person1_data: BirthDetailsRequest,
        person2_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """
        Get compatibility score between two people
        
        Args:
            person1_data: First person's birth details
            person2_data: Second person's birth details
        """
        payload = {
            "male": person1_data.dict(),
            "female": person2_data.dict()
        }
        return await self._make_request("match_ashtakoot_points", payload)
    
    # ========================================================================
    # YOGAS & DOSHAS
    # ========================================================================
    
    async def get_yogas(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get all yogas in birth chart"""
        payload = birth_data.dict()
        return await self._make_request("basic_gem_suggestion", payload)
    
    async def get_mangal_dosha(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Check for Mangal Dosha (Mars affliction)"""
        payload = birth_data.dict()
        return await self._make_request("manglik", payload)
    
    async def get_kalsarpa_dosha(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Check for Kalsarpa Dosha"""
        payload = birth_data.dict()
        return await self._make_request("kalsarpa_details", payload)
    
    # ========================================================================
    # PANCHANG
    # ========================================================================
    
    async def get_panchang(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get Panchang (Hindu calendar) details"""
        payload = birth_data.dict()
        return await self._make_request("basic_panchang", payload)
    
    async def get_choghadiya(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get Choghadiya (auspicious timings)"""
        payload = birth_data.dict()
        return await self._make_request("basic_choghadiya", payload)
    
    # ========================================================================
    # REMEDIES
    # ========================================================================
    
    async def get_gemstone_suggestions(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get gemstone recommendations"""
        payload = birth_data.dict()
        return await self._make_request("basic_gem_suggestion", payload)
    
    async def get_rudraksha_suggestions(
        self,
        birth_data: BirthDetailsRequest
    ) -> Dict[str, Any]:
        """Get Rudraksha recommendations"""
        payload = birth_data.dict()
        return await self._make_request("rudraksha_suggestion", payload)
