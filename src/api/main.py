# src/api/main.py
"""
FastAPI Main Application for NakshatraAI Chatbot.

Includes stateless chat routes with Redis session management.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import routers
from src.api.routes import chat_stateless

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
            "chat_initialize": "/api/v1/chat/initialize",
            "chat_message": "/api/v1/chat/message",
            "stats": "/api/v1/chat/stats"
        }
    }

# Health check
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=6262,
        reload=True
    )