# src/api/main.py
"""
FastAPI Main Application for NakshatraAI Chatbot.

Includes stateless chat routes with Redis session management.
"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio
import os

from config.logger import get_logger

logger = get_logger("api")

# Import routers
from src.api.routes import chat_stateless, calculation, health


# ── Request / Response logging middleware ─────────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request and response with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"
        query = f"?{request.url.query}" if request.url.query else ""

        logger.info(f"[REQUEST] {method} {path}{query} ← {client}")
        try:
            response = await call_next(request)
            ms = round((time.time() - start) * 1000)
            level = "warning" if response.status_code >= 400 else "info"
            getattr(logger, level)(
                f"[RESPONSE] {method} {path} → {response.status_code} ({ms}ms)"
            )
            return response
        except Exception as exc:
            ms = round((time.time() - start) * 1000)
            logger.error(
                f"[ERROR] {method} {path} → UNHANDLED EXCEPTION ({ms}ms): {exc}",
                exc_info=True,
            )
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Kick off orchestrator pre-warming in the background so uvicorn starts instantly."""
    async def _prewarm():
        from src.api.orchestrator_helper import get_orchestrator
        logger.info("[STARTUP] Pre-warming orchestrator in background...")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, get_orchestrator)
            logger.info("[STARTUP] Orchestrator ready.")
        except Exception as exc:
            logger.error(f"[STARTUP] Pre-warm failed (will retry on first request): {exc}", exc_info=True)

    asyncio.create_task(_prewarm())
    yield


# Create FastAPI app
app = FastAPI(
    title="NakshatraAI Chatbot API",
    description="Vedic Astrology Chatbot with Redis Session Management",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(RequestLoggingMiddleware)

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