"""
Production Integration Example

Demonstrates how to use the Astrology Data Service with Redis caching
and RAG context formatting.
"""

import asyncio
import logging
from datetime import date

from src.integrations.astrology_api import BirthDetailsRequest
from src.services import AstrologyDataService, CacheConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Example 1: Basic usage with automatic caching"""
    
    # Initialize service (uses environment variables for config)
    service = AstrologyDataService()
    await service.initialize()
    
    try:
        # User's birth details
        birth_data = BirthDetailsRequest(
            day=15,
            month=8,
            year=1990,
            hour=14,
            min=30,
            lat=28.6139,  # Delhi
            lon=77.2090,
            tzone=5.5     # IST
        )
        
        user_id = "user_123"
        
        # Fetch birth chart (will cache automatically)
        logger.info("Fetching birth chart...")
        birth_chart = await service.get_birth_chart(
            user_id=user_id,
            birth_data=birth_data,
            system="vedic",
            format_for_rag=True  # Get RAG-formatted output
        )
        
        logger.info("Birth Chart (RAG Format):")
        logger.info(birth_chart["text"])
        
        # Second call will hit cache (much faster)
        logger.info("\nFetching birth chart again (should hit cache)...")
        birth_chart_cached = await service.get_birth_chart(
            user_id=user_id,
            birth_data=birth_data,
            system="vedic"
        )
        
    finally:
        await service.shutdown()


async def example_complete_profile():
    """Example 2: Fetch complete astrological profile"""
    
    service = AstrologyDataService()
    await service.initialize()
    
    try:
        birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=14, min=30,
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        # Fetch all astrology data in parallel
        logger.info("Fetching complete astrological profile...")
        complete_data = await service.get_all_astro_data(
            user_id="user_123",
            birth_data=birth_data,
            include_horoscope=True,
            include_transits=True,
            format_for_rag=True
        )
        
        logger.info("\nComplete Profile (RAG Format):")
        logger.info(complete_data["text"])
        
        logger.info("\nMetadata:")
        logger.info(complete_data["metadata"])
        
    finally:
        await service.shutdown()


async def example_custom_cache_config():
    """Example 3: Custom cache configuration"""
    
    # Custom cache settings
    cache_config = CacheConfig(
        host="localhost",
        port=6379,
        db=0,
        ttl_birth_chart=7200,     # 2 hours instead of 24
        ttl_horoscope=1800,       # 30 minutes instead of 1 hour
        key_prefix="my_astro_app"
    )
    
    service = AstrologyDataService(cache_config=cache_config)
    await service.initialize()
    
    try:
        birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=14, min=30,
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        # Fetch with custom cache settings
        birth_chart = await service.get_birth_chart(
            user_id="user_456",
            birth_data=birth_data
        )
        
        logger.info("Data fetched with custom cache config")
        
    finally:
        await service.shutdown()


async def example_rag_integration():
    """Example 4: Integration with RAG system"""
    
    service = AstrologyDataService()
    await service.initialize()
    
    try:
        birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=14, min=30,
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        user_query = "What career opportunities will I have this year?"
        user_id = "user_789"
        
        # Step 1: Get astrological context
        logger.info("Step 1: Fetching astrological context...")
        astro_context = await service.get_all_astro_data(
            user_id=user_id,
            birth_data=birth_data,
            format_for_rag=True
        )
        
        # Step 2: Pass to RAG engine (pseudo-code)
        logger.info("\nStep 2: Querying RAG engine...")
        # rag_response = await rag_engine.query(
        #     query=user_query,
        #     context=astro_context["text"],
        #     metadata=astro_context["metadata"]
        # )
        
        # Step 3: Generate LLM response (pseudo-code)
        logger.info("\nStep 3: Generating LLM response...")
        # final_response = await llm.generate(
        #     prompt=rag_response["prompt"],
        #     context=rag_response["retrieved_chunks"]
        # )
        
        logger.info("\nAstrological Context for RAG:")
        logger.info(astro_context["text"][:500] + "...")
        
    finally:
        await service.shutdown()


async def example_cache_invalidation():
    """Example 5: Cache invalidation when user updates profile"""
    
    service = AstrologyDataService()
    await service.initialize()
    
    try:
        user_id = "user_999"
        
        # Original birth data
        old_birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=14, min=30,
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        # Fetch and cache
        logger.info("Fetching with original birth data...")
        await service.get_birth_chart(user_id, old_birth_data)
        
        # User updates their birth time
        logger.info("\nUser updated birth time...")
        new_birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=15, min=0,  # Changed time
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        # Invalidate old cache
        logger.info("Invalidating user cache...")
        deleted_count = await service.invalidate_user_cache(user_id)
        logger.info(f"Deleted {deleted_count} cache entries")
        
        # Fetch with new data (will call API, not cache)
        logger.info("\nFetching with new birth data...")
        await service.get_birth_chart(user_id, new_birth_data)
        
    finally:
        await service.shutdown()


async def example_individual_endpoints():
    """Example 6: Using individual endpoints"""
    
    service = AstrologyDataService()
    await service.initialize()
    
    try:
        birth_data = BirthDetailsRequest(
            day=15, month=8, year=1990,
            hour=14, min=30,
            lat=28.6139, lon=77.2090, tzone=5.5
        )
        
        user_id = "user_111"
        
        # Fetch different data types
        logger.info("Fetching Vimshottari Dashas...")
        dashas = await service.get_dashas(
            user_id, birth_data,
            dasha_type="vimshottari",
            format_for_rag=True
        )
        logger.info(dashas["text"])
        
        logger.info("\nFetching daily horoscope...")
        horoscope = await service.get_horoscope(
            user_id, birth_data,
            period="daily",
            format_for_rag=True
        )
        logger.info(horoscope["text"])
        
        logger.info("\nFetching current transits...")
        transits = await service.get_transits(
            user_id, birth_data,
            format_for_rag=True
        )
        logger.info(transits["text"])
        
    finally:
        await service.shutdown()


if __name__ == "__main__":
    # Run examples
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    asyncio.run(example_basic_usage())
    
    print("\n" + "=" * 60)
    print("Example 2: Complete Profile")
    print("=" * 60)
    asyncio.run(example_complete_profile())
    
    print("\n" + "=" * 60)
    print("Example 4: RAG Integration")
    print("=" * 60)
    asyncio.run(example_rag_integration())
    
    print("\n" + "=" * 60)
    print("Example 5: Cache Invalidation")
    print("=" * 60)
    asyncio.run(example_cache_invalidation())
    
    print("\n" + "=" * 60)
    print("Example 6: Individual Endpoints")
    print("=" * 60)
    asyncio.run(example_individual_endpoints())
