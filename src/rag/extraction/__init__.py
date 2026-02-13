# src\rag\extraction\__init__.py
"""
Vision LLM Extraction Pipeline for Astrology Texts
===================================================

This package provides high-quality text and table extraction from 
scanned astrology books using Google Gemini Vision.

Key Components:
- VisionPipeline: Complete extraction pipeline for PDFs
- VisionExtractor: Core Vision LLM extraction logic
- extraction_schemas: Pydantic models for structured output
- extraction_prompts: Specialized prompts for astrology texts

Usage:
    from vision_pipeline import VisionPipeline, PipelineConfig
    
    config = PipelineConfig(
        book_title="Brihat Parasara Hora Shastra",
        output_dir="./output",
    )
    
    pipeline = VisionPipeline(config)
    result = pipeline.process_pdf("book.pdf")

For more details, see demo_extraction.py
"""

from .vision_pipeline import VisionPipeline, PipelineConfig
from .vision_extractor import VisionExtractor, ExtractionConfig, BatchExtractor
from .extraction_schemas import (
    PageType,
    ContentType,
    ExtractedPage,
    PageMetadata,
    ContentBlock,
    ExtractedTable,
    VerseBlock,
    RAGChunk,
    ExtractionResult,
)

__version__ = "0.1.0"
__author__ = "Astrology AI Chatbot Project"

__all__ = [
    # Pipeline
    "VisionPipeline",
    "PipelineConfig",
    
    # Extractor
    "VisionExtractor",
    "ExtractionConfig",
    "BatchExtractor",
    
    # Schemas
    "PageType",
    "ContentType",
    "ExtractedPage",
    "PageMetadata",
    "ContentBlock",
    "ExtractedTable",
    "VerseBlock",
    "RAGChunk",
    "ExtractionResult",
]
