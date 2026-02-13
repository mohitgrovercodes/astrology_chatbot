# src\api\main.py
"""
FastAPI Application - Main Entry Point
=======================================

Production-ready REST API for NakshatraAI Astrology Chatbot.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import time

from src.api.config import settings
from src.api.routes import chat, user, calculation, health

# Create FastAPI app
app = FastAPI(
    title="NakshatraAI API",
    description="Expert Astrology AI Chatbot - Vedic & Western Astrology",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(user.router, prefix="/api/v1", tags=["User"])
app.include_router(calculation.router, prefix="/api/v1", tags=["Calculation"])


# Startup event
@app.on_event("startup")
async def startup_event():
    print("=" * 70)
    print("NakshatraAI API Starting...")
    print(f"Version: 1.0.0")
    print(f"Docs: http://localhost:{settings.PORT}/api/docs")
    print("=" * 70)

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    print("NakshatraAI API Shutting down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
