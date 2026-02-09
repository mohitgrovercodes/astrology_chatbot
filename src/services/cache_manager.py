"""
Redis Cache Manager for Astrology Data

Handles all caching operations with type-safe keys, configurable TTL,
and graceful fallback strategies.
"""

import json
import hashlib
import logging
from typing import Any, Optional, Callable, Dict
from datetime import timedelta
from functools import wraps

try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis
except ImportError:
    raise ImportError(
        "redis package not found. Install with: pip install redis[hiredis]"
    )

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class CacheConfig(BaseModel):
    """Configuration for Redis cache"""
    
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")
    
    # TTL configurations (in seconds)
    ttl_birth_chart: int = Field(default=86400, description="24 hours")
    ttl_dashas: int = Field(default=604800, description="7 days")
    ttl_horoscope: int = Field(default=3600, description="1 hour")
    ttl_transits: int = Field(default=1800, description="30 minutes")
    ttl_ayanamsa: int = Field(default=604800, description="7 days")
    ttl_default: int = Field(default=3600, description="1 hour default")
    
    # Cache key prefix
    key_prefix: str = Field(default="astro", description="Cache key namespace")
    
    # Connection settings
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, description="Connection timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    max_connections: int = Field(default=50, description="Max connection pool size")
    
    class Config:
        env_prefix = "REDIS_"


# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    """
    Production-grade Redis cache manager for astrology data
    
    Features:
    - Namespaced cache keys
    - Automatic serialization/deserialization
    - Configurable TTL per data type
    - Cache-aside pattern support
    - Graceful degradation on Redis failures
    - Connection pooling
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize cache manager
        
        Args:
            config: Cache configuration (defaults to env vars)
        """
        self.config = config or CacheConfig()
        self._client: Optional[Redis] = None
        self._is_available = True
        
        logger.info(f"CacheManager initialized with config: {self.config.host}:{self.config.port}")
    
    async def connect(self):
        """Establish Redis connection"""
        try:
            self._client = await aioredis.from_url(
                f"redis://{self.config.host}:{self.config.port}/{self.config.db}",
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                max_connections=self.config.max_connections,
                decode_responses=True  # Auto-decode bytes to strings
            )
            
            # Test connection
            await self._client.ping()
            self._is_available = True
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._is_available = False
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")
    
    def _build_key(self, user_id: str, data_type: str, **kwargs) -> str:
        """
        Build namespaced cache key
        
        Args:
            user_id: User identifier
            data_type: Type of astrology data (birth_chart, dashas, etc.)
            **kwargs: Additional parameters to include in key hash
            
        Returns:
            Formatted cache key
            
        Example:
            >>> _build_key("user_123", "birth_chart")
            "astro:user_123:birth_chart:abc123"
        """
        # Create deterministic hash from kwargs
        if kwargs:
            hash_input = json.dumps(kwargs, sort_keys=True)
            param_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
            return f"{self.config.key_prefix}:{user_id}:{data_type}:{param_hash}"
        else:
            return f"{self.config.key_prefix}:{user_id}:{data_type}"
    
    def _get_ttl(self, data_type: str) -> int:
        """
        Get TTL for specific data type
        
        Args:
            data_type: Type of astrology data
            
        Returns:
            TTL in seconds
        """
        ttl_map = {
            "birth_chart": self.config.ttl_birth_chart,
            "dashas": self.config.ttl_dashas,
            "horoscope": self.config.ttl_horoscope,
            "transits": self.config.ttl_transits,
            "ayanamsa": self.config.ttl_ayanamsa,
        }
        return ttl_map.get(data_type, self.config.ttl_default)
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found
        """
        if not self._is_available or not self._client:
            logger.warning("Redis not available, skipping cache read")
            return None
        
        try:
            data = await self._client.get(key)
            if data:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(data)
            else:
                logger.debug(f"Cache MISS: {key}")
                return None
                
        except Exception as e:
            logger.error(f"Cache read error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store data in cache
        
        Args:
            key: Cache key
            value: Data to cache
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._is_available or not self._client:
            logger.warning("Redis not available, skipping cache write")
            return False
        
        try:
            serialized = json.dumps(value)
            
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Cache write error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete cached data
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        if not self._is_available or not self._client:
            return False
        
        try:
            deleted = await self._client.delete(key)
            logger.debug(f"Cache DELETE: {key} (deleted: {deleted})")
            return bool(deleted)
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if exists, False otherwise
        """
        if not self._is_available or not self._client:
            return False
        
        try:
            return bool(await self._client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists check error for key {key}: {e}")
            return False
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached data for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of keys deleted
        """
        if not self._is_available or not self._client:
            return 0
        
        try:
            pattern = f"{self.config.key_prefix}:{user_id}:*"
            keys = []
            
            # Scan for matching keys
            async for key in self._client.scan_iter(match=pattern, count=100):
                keys.append(key)
            
            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Cache invalidation error for user {user_id}: {e}")
            return 0
    
    async def get_or_fetch(
        self,
        user_id: str,
        data_type: str,
        fetch_fn: Callable,
        ttl: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Cache-aside pattern: Get from cache or fetch and store
        
        Args:
            user_id: User identifier
            data_type: Type of astrology data
            fetch_fn: Async function to fetch data if cache miss
            ttl: Custom TTL (defaults to data type TTL)
            **kwargs: Additional parameters for cache key and fetch function
            
        Returns:
            Cached or freshly fetched data
            
        Example:
            >>> async def fetch_birth_chart(birth_data):
            ...     return await api.get_birth_chart(birth_data)
            >>> 
            >>> data = await cache.get_or_fetch(
            ...     user_id="user_123",
            ...     data_type="birth_chart",
            ...     fetch_fn=fetch_birth_chart,
            ...     birth_data=user_birth_details
            ... )
        """
        # Build cache key
        key = self._build_key(user_id, data_type, **kwargs)
        
        # Try cache first
        cached_data = await self.get(key)
        if cached_data is not None:
            return cached_data
        
        # Cache miss - fetch fresh data
        logger.info(f"Fetching fresh data for {data_type} (user: {user_id})")
        
        try:
            fresh_data = await fetch_fn(**kwargs)
            
            # Store in cache
            cache_ttl = ttl or self._get_ttl(data_type)
            await self.set(key, fresh_data, ttl=cache_ttl)
            
            return fresh_data
            
        except Exception as e:
            logger.error(f"Error fetching data for {data_type}: {e}")
            raise


# ============================================================================
# DECORATOR FOR AUTOMATIC CACHING
# ============================================================================

def cached(data_type: str, ttl: Optional[int] = None):
    """
    Decorator for automatic caching of async functions
    
    Args:
        data_type: Type of astrology data
        ttl: Custom TTL (optional)
        
    Example:
        >>> @cached("birth_chart", ttl=86400)
        >>> async def get_birth_chart(cache_manager, user_id, birth_data):
        ...     return await api.fetch_birth_chart(birth_data)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(cache_manager: CacheManager, user_id: str, *args, **kwargs):
            # Build cache key
            key = cache_manager._build_key(user_id, data_type, **kwargs)
            
            # Try cache
            cached_data = await cache_manager.get(key)
            if cached_data is not None:
                return cached_data
            
            # Fetch fresh
            fresh_data = await func(cache_manager, user_id, *args, **kwargs)
            
            # Cache it
            cache_ttl = ttl or cache_manager._get_ttl(data_type)
            await cache_manager.set(key, fresh_data, ttl=cache_ttl)
            
            return fresh_data
        
        return wrapper
    return decorator
