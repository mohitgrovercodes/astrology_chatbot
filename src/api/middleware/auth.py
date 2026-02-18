# src/api/middleware/auth.py
# src\api\middleware\auth.py
"""
API Key Authentication Middleware
===================================

API key-based authentication for all protected endpoints.

NOTE: "X-API-Key" is just the HTTP header name (standard convention).
It is NOT related to Twitter/X API. You create your own API keys
and configure them in the VALID_API_KEYS environment variable.
"""

from fastapi import Header, HTTPException, Depends
from typing import Optional
from src.api.config import settings


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Verify API key from request header.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        Verified API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Include 'X-API-Key' header."
        )
    
    # Check if API key is valid
    valid_keys = settings.get_api_keys()
    if valid_keys and x_api_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    # In development/testing, allow any key if no keys configured
    if not valid_keys and settings.DEBUG:
        return x_api_key
    
    return x_api_key


async def verify_internal_service(x_internal_service: Optional[str] = Header(None)) -> bool:
    """
    Verify the Internal Service shared secret.
    """
    if not x_internal_service:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Internal Service Authentication Required"
        )
        
    if x_internal_service != settings.INTERNAL_SERVICE_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid Internal Service Secret"
        )
        
    return True


# Dependency for protected routes
APIKeyDep = Depends(verify_api_key)
InternalServiceDep = Depends(verify_internal_service)
