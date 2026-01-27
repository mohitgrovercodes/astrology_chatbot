# Astrology AI ChatBot - RAG Pipeline

A production-grade extraction and text pre-processing pipeline for building an expert Astrology AI system.

## 🌟 Project Overview

This system processes classical astrology texts (Vedic & Western) from raw PDF images into enriched, Rerank-ready semantic chunks for a RAG (Retrieval-Augmented Generation) system.

### Key Capabilities
- **Hierarchical Extraction**: Uses Gemini Vision (Flash-Lite/Flash/Pro) for precise layout-aware extraction of shlokas, translations, and complex astrological tables.
- **Strict Two-Tier Logic**: Uses Flash-Lite for text, Flash for tables, and auto-upgrades to Pro for validation failures.
- **Multi-Phase Preprocessing**: Structural cleaning (whitespace, Sanskrit normalization), cross-page linking, and semantic segmentation.
- **Metadata Enrichment**: Automatically generates astrological entities (planets, houses, signs) and hypothetical questions for each chunk.

## 📂 Project Structure

```text
├── batch_extract.py           # Production entry point for PDF extraction
├── extract_pdf.py             # Interactive wrapper for single-page testing
├── run_preprocessing_phases.py # Entry point for cleaning & enrichment (Phases 2-5)
├── src/
│   ├── rag/
│   │   ├── extraction/        # Vision extraction core (prompts, schemas, logic)
│   │   └── preprocessing/     # Cleaning, analysis, and segmentation modules
│   ├── llm/                   # Centralized LLM Factory (Gemini/OpenAI/xAI)
│   └── utils/                 # Config, Logging, and Cost Tracking
└── config/                    # YAML configuration for models and thresholds
```

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install pydantic google-generativeai openai pillow numpy pdf2image
```

### 2. Extraction (Phase 1)
Extract raw text and structures from PDF:

```bash
# Batch extraction
python batch_extract.py data/raw/book.pdf --start 100 --end 110 --workers 5

# Interactive/Single-page testing
python extract_pdf.py
```

### 3. Preprocessing (Phases 2-5)
Clean, link, and enrich the extracted data:

```bash
# Process a single batch or page
python run_preprocessing_phases.py --input extraction_output/raw_response_page_110.json
```

## 🛠️ Developer Tools

- **Cost Tracking**: Automatic SQLite-based tracking of token usage and API costs in `logs/cost_tracker.db`.
- **Hybrid Routing**: The system automatically selects the cheapest capable model and upgrades to Pro only when extraction quality is low.
- **Schema Compatibility**: Preprocessing automatically handles the "Rich" nested JSON output from the Vision system.

## 📄 License
Internal project for expert Astrology AI system development.
