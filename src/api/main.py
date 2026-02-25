# src/api/main.py
"""
FastAPI Main Application for NakshatraAI Chatbot.

Includes stateless chat routes with Redis session management.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import routers
from src.api.routes import chat_stateless, calculation, health

# Create FastAPI app
app = FastAPI(
    title="NakshatraAI Chatbot API",
    description="Vedic Astrology Chatbot with Redis Session Management",
    version="2.0.0"
)

# CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    chat_stateless.router,
    prefix="/api/v1/chat",
    tags=["chat"]
)

app.include_router(
    calculation.router,
    prefix="/api/v1",
    tags=["calculation"]
)

# Health router (available at root for monitoring /health and versioned for API consistency)
app.include_router(health.router, tags=["monitoring"])
app.include_router(health.router, prefix="/api/v1", tags=["monitoring"])

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "NakshatraAI Chatbot API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "chat": "/api/v1/chat",
            "calculation": "/api/v1/calculate",
            "health": "/health",
            "health_v1": "/api/v1/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=6262,
        reload=True
    )