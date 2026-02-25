# src/services/astrology_service.py
# src\services\astrology_service.py
"""
Astrology Data Service

Main orchestrator for fetching, caching, and formatting astrology data
from 3rd-party APIs for RAG consumption.
"""

import logging
from typing import Dict, Any, Optional
from datetime import date

from ..integrations.astrology_api.extended_client import (
    ExtendedAstrologyAPIClient,
    BirthDetailsRequest
)
from .cache_manager import CacheManager, CacheConfig
from .rag_context_formatter import RAGContextFormatter


logger = logging.getLogger(__name__)


# ============================================================================
# ASTROLOGY DATA SERVICE
# ============================================================================

class AstrologyDataService:
    """
    Production service for astrology data management
    
    Features:
    - Unified interface for all astrology data types
    - Automatic Redis caching with configurable TTL
    - RAG-ready context formatting
    - Graceful fallback on failures
    - Comprehensive logging
    
    Architecture:
        User Request -> Service -> Cache Check -> API Call -> Format -> RAG
    """
    
    def __init__(
        self,
        api_client: Optional[ExtendedAstrologyAPIClient] = None,
        cache_manager: Optional[CacheManager] = None,
        cache_config: Optional[CacheConfig] = None
    ):
        """
        Initialize astrology data service
        
        Args:
            api_client: Astrology API client (creates new if None)
            cache_manager: Cache manager (creates new if None)
            cache_config: Cache configuration (uses defaults if None)
        """
        self.api_client = api_client or ExtendedAstrologyAPIClient()
        self.cache_manager = cache_manager or CacheManager(cache_config)
        self.formatter = RAGContextFormatter()
        
        logger.info("AstrologyDataService initialized")
    
    async def initialize(self):
        """Initialize connections (call this before using the service)"""
        await self.cache_manager.connect()
        logger.info("AstrologyDataService connections established")
    
    async def shutdown(self):
        """Cleanup connections"""
        await self.cache_manager.disconnect()
        logger.info("AstrologyDataService connections closed")
    
    # ========================================================================
    # BIRTH CHART
    # ========================================================================
    
    async def get_birth_chart(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        system: str = "vedic",
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get birth chart with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            system: 'vedic' or 'western'
            format_for_rag: Whether to format for RAG (default: True)
            
        Returns:
            Birth chart data (formatted or raw)
        """
        async def fetch_birth_chart(**kwargs):
            if system == "vedic":
                return await self.api_client.get_vedic_birth_chart(birth_data)
            else:
                return await self.api_client.get_tropical_birth_chart(birth_data)
        
        # Use cache-aside pattern
        data = await self.cache_manager.get_or_fetch(
            user_id=user_id,
            data_type=f"birth_chart_{system}",
            fetch_fn=fetch_birth_chart,
            system=system
        )
        
        if format_for_rag:
            return self.formatter.format_birth_chart(data)
        return data
    
    # ========================================================================
    # DASHAS
    # ========================================================================
    
    async def get_dashas(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        dasha_type: str = "vimshottari",
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get dasha periods with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            dasha_type: 'vimshottari', 'yogini', or 'char'
            format_for_rag: Whether to format for RAG
            
        Returns:
            Dasha data (formatted or raw)
        """
        async def fetch_dashas(**kwargs):
            if dasha_type == "vimshottari":
                return await self.api_client.get_vimshottari_dasha(birth_data)
            elif dasha_type == "yogini":
                return await self.api_client.get_yogini_dasha(birth_data)
            elif dasha_type == "char":
                return await self.api_client.get_char_dasha(birth_data)
            else:
                raise ValueError(f"Unknown dasha type: {dasha_type}")
        
        data = await self.cache_manager.get_or_fetch(
            user_id=user_id,
            data_type=f"dashas_{dasha_type}",
            fetch_fn=fetch_dashas,
            dasha_type=dasha_type
        )
        
        if format_for_rag:
            return self.formatter.format_dashas(data)
        return data
    
    # ========================================================================
    # AYANAMSA
    # ========================================================================
    
    async def get_ayanamsa(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        ayanamsa_type: str = "lahiri",
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get ayanamsa calculation with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            ayanamsa_type: Type of ayanamsa
            format_for_rag: Whether to format for RAG
            
        Returns:
            Ayanamsa data
        """
        async def fetch_ayanamsa(**kwargs):
            return await self.api_client.get_ayanamsa(birth_data, ayanamsa_type)
        
        data = await self.cache_manager.get_or_fetch(
            user_id=user_id,
            data_type=f"ayanamsa_{ayanamsa_type}",
            fetch_fn=fetch_ayanamsa,
            ayanamsa_type=ayanamsa_type
        )
        
        return data  # Ayanamsa is simple, no special formatting needed
    
    # ========================================================================
    # HOROSCOPES
    # ========================================================================
    
    async def get_horoscope(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        period: str = "daily",
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get horoscope predictions with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            period: 'daily', 'weekly', 'monthly', or 'yearly'
            format_for_rag: Whether to format for RAG
            
        Returns:
            Horoscope data (formatted or raw)
        """
        async def fetch_horoscope(**kwargs):
            if period == "daily":
                return await self.api_client.get_daily_horoscope(birth_data)
            elif period == "weekly":
                return await self.api_client.get_weekly_horoscope(birth_data)
            elif period == "monthly":
                return await self.api_client.get_monthly_horoscope(birth_data)
            elif period == "yearly":
                return await self.api_client.get_yearly_horoscope(birth_data)
            else:
                raise ValueError(f"Unknown period: {period}")
        
        data = await self.cache_manager.get_or_fetch(
            user_id=user_id,
            data_type=f"horoscope_{period}",
            fetch_fn=fetch_horoscope,
            period=period
        )
        
        if format_for_rag:
            return self.formatter.format_horoscope(data, period)
        return data
    
    # ========================================================================
    # TRANSITS
    # ========================================================================
    
    async def get_transits(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get current transits with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            format_for_rag: Whether to format for RAG
            
        Returns:
            Transit data (formatted or raw)
        """
        async def fetch_transits(**kwargs):
            return await self.api_client.get_current_transits(birth_data)
        
        data = await self.cache_manager.get_or_fetch(
            user_id=user_id,
            data_type="transits",
            fetch_fn=fetch_transits
        )
        
        if format_for_rag:
            return self.formatter.format_transits(data)
        return data
    
    # ========================================================================
    # COMPREHENSIVE DATA
    # ========================================================================
    
    async def get_all_astro_data(
        self,
        user_id: str,
        birth_data: BirthDetailsRequest,
        include_horoscope: bool = True,
        include_transits: bool = True,
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete astrological profile with caching
        
        Args:
            user_id: User identifier
            birth_data: Birth details
            include_horoscope: Include daily horoscope
            include_transits: Include current transits
            format_for_rag: Whether to format for RAG
            
        Returns:
            Complete astrology data
        """
        logger.info(f"Fetching complete astro data for user {user_id}")
        
        # Fetch all data types in parallel
        import asyncio
        
        tasks = {
            "birth_chart": self.get_birth_chart(user_id, birth_data, format_for_rag=False),
            "dashas": self.get_dashas(user_id, birth_data, format_for_rag=False),
            "ayanamsa": self.get_ayanamsa(user_id, birth_data, format_for_rag=False),
        }
        
        if include_horoscope:
            tasks["horoscope"] = self.get_horoscope(user_id, birth_data, format_for_rag=False)
        
        if include_transits:
            tasks["transits"] = self.get_transits(user_id, birth_data, format_for_rag=False)
        
        # Execute all fetches concurrently
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Combine results
        complete_data = {}
        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {key}: {result}")
                complete_data[key] = {"error": str(result)}
            else:
                complete_data[key] = result
        
        # Format for RAG if requested
        if format_for_rag:
            formatted_contexts = []
            
            if "birth_chart" in complete_data:
                formatted_contexts.append(
                    self.formatter.format_birth_chart(complete_data["birth_chart"])
                )
            
            if "dashas" in complete_data:
                formatted_contexts.append(
                    self.formatter.format_dashas(complete_data["dashas"])
                )
            
            if "horoscope" in complete_data:
                formatted_contexts.append(
                    self.formatter.format_horoscope(complete_data["horoscope"], "daily")
                )
            
            if "transits" in complete_data:
                formatted_contexts.append(
                    self.formatter.format_transits(complete_data["transits"])
                )
            
            return self.formatter.combine_contexts(formatted_contexts)
        
        return complete_data
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached data for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of cache entries deleted
        """
        return await self.cache_manager.invalidate_user_cache(user_id)
