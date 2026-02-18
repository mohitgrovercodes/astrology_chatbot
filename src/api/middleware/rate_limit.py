# src/api/middleware/rate_limit.py
# src\api\middleware\rate_limit.py
"""
Rate Limiting Middleware
==========================

Rate limiting for API endpoints to prevent abuse.
"""

from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import time

from src.api.config import settings


class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    Tracks requests per API key and IP address.
    """
    
    def __init__(self):
        # Store: {key: [(timestamp, count)]}
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup(self):
        """Remove old entries."""
        if time.time() - self.last_cleanup > self.cleanup_interval:
            cutoff = datetime.now() - timedelta(hours=1)
            for key in list(self.requests.keys()):
                self.requests[key] = [
                    (ts, count) for ts, count in self.requests[key]
                    if ts > cutoff
                ]
                if not self.requests[key]:
                    del self.requests[key]
            self.last_cleanup = time.time()
    
    def _get_key(self, request: Request, api_key: str = None) -> str:
        """Get rate limit key (API key or IP)."""
        if api_key:
            return f"key:{api_key}"
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def check_rate_limit(
        self,
        request: Request,
        api_key: str = None,
        limit_per_minute: int = None
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit.
        
        Args:
            request: FastAPI request
            api_key: Optional API key
            limit_per_minute: Requests per minute limit
            
        Returns:
            Tuple of (is_allowed, current_count, limit)
        """
        self._cleanup()
        
        limit = limit_per_minute or settings.RATE_LIMIT_PER_MINUTE
        key = self._get_key(request, api_key)
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        
        # Get requests in last minute
        recent_requests = [
            (ts, count) for ts, count in self.requests[key]
            if ts > cutoff
        ]
        
        # Count total requests
        current_count = sum(count for _, count in recent_requests)
        
        if current_count >= limit:
            return False, current_count, limit
        
        # Add new request
        recent_requests.append((now, 1))
        self.requests[key] = recent_requests
        
        return True, current_count + 1, limit


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(
    request: Request,
    api_key: str = None,
    limit_per_minute: int = None
):
    """
    Rate limit dependency for routes.
    
    Raises HTTPException if rate limit exceeded.
    """
    allowed, current, limit = rate_limiter.check_rate_limit(
        request,
        api_key,
        limit_per_minute
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. {current}/{limit} requests per minute.",
            headers={"Retry-After": "60"}
        )
    
    # Add rate limit info to response headers (will be added by endpoint)
    request.state.rate_limit_info = {
        "current": current,
        "limit": limit,
        "remaining": limit - current
    }
