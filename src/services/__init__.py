# src/services/__init__.py
"""
Services Module

Adapter for receiving pre-fetched astrology data from the backend
and preparing it for RAG consumption.
"""

from .backend_data_adapter import (
    BackendDataAdapter,
    BackendAstroData,
    RAGContextFormatter,
    process_backend_data_for_rag
)

__all__ = [
    "BackendDataAdapter",
    "BackendAstroData",
    "RAGContextFormatter",
    "process_backend_data_for_rag",
]
