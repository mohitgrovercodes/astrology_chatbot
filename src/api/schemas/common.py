# src\api\schemas\common.py
"""
Common Schemas - Pydantic Models
==================================

Common request and response models used across endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Detailed error information")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Error timestamp"
    )
    path: Optional[str] = Field(None, description="Request path")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid request",
                "details": "Missing required field: user_id",
                "timestamp": "2026-02-02T14:00:00Z",
                "path": "/api/v1/chat"
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response."""
    message: str = Field(..., description="Success message")
    data: Optional[dict] = Field(None, description="Response data")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    uptime: float = Field(..., description="Uptime in seconds")
    components: dict = Field(..., description="Component health status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime": 3600.5,
                "components": {
                    "orchestrator": "ok",
                    "database": "ok",
                    "llm": "ok"
                }
            }
        }
