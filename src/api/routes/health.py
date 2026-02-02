"""
Health Check Routes
====================

Health check and monitoring endpoints.
"""

from fastapi import APIRouter, Response
from src.api.schemas.common import HealthResponse
from src.api.dependencies import get_orchestrator, get_user_manager
import time

router = APIRouter()

# Track startup time for uptime calculation
_startup_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns system health status and component checks.
    """
    uptime = time.time() - _startup_time
    
    # Check components
    components = {
        "api": "ok"
    }
    
    # Try to check orchestrator
    try:
        orchestrator = get_orchestrator()
        components["orchestrator"] = "ok" if orchestrator else "error"
    except Exception as e:
        components["orchestrator"] = f"error: {str(e)}"
    
    # Try to check user manager
    try:
        user_manager = get_user_manager()
        components["user_manager"] = "ok" if user_manager else "error"
    except Exception as e:
        components["user_manager"] = f"error: {str(e)}"
    
    # Determine overall status
    status = "healthy" if all(
        v == "ok" for v in components.values()
    ) else "degraded"
    
    return HealthResponse(
        status=status,
        version="1.0.0",
        uptime=uptime,
        components=components
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint for basic connectivity check."""
    return {"status": "pong", "timestamp": time.time()}
