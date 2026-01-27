#!/usr/bin/env python3
"""
Batch Extraction Runner
Uses the optimized VisionExtractor with parallel processing and checkpoints.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path to allow imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from {env_path}")
except ImportError:
    print("Warning: python-dotenv not installed")

# Filter warnings from deprecated google.generativeai
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai

# Configure Logging
log_file = "extraction_run.log"
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Import optimized modules
# We import directly from the file to avoid triggering package-level imports
sys.path.append(str(project_root / "src/rag/extraction"))
try:
    from src.rag.extraction.vision_extractor import VisionExtractor, BatchExtractor, ExtractionConfig
except ImportError:
    # Fallback if src package logic fails
    sys.path.append(str(project_root / "src" / "rag" / "extraction"))
    from vision_extractor import VisionExtractor, BatchExtractor, ExtractionConfig

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch PDF Extraction with Optimizations")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--start", type=int, default=1, help="Start page")
    parser.add_argument("--end", type=int, default=10, help="End page")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers")
    parser.add_argument("--output", default="./extraction_output", help="Output directory")
    
    args = parser.parse_args()
    
    # 1. AUTH SETUP: Use GCP Credentials for Vertex AI
    # Ensure credentials file is set
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Check potential default path
        default_creds = project_root / "google_credentials.json"
        if default_creds.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(default_creds)
            print(f"🔑 Using Credentials: {default_creds}")
        else:
            print("❌ Error: GOOGLE_APPLICATION_CREDENTIALS not set and not found in root.")
            return

    print("☁️  Configuring for Google Cloud Vertex AI...")
    
    # 2. Setup Configuration
    config = ExtractionConfig(
        primary_model="gemini-2.5-flash-lite",  # Use Lite for speed/cost
        upgrade_model="gemini-2.5-pro",
        confidence_threshold=0.9,           # Strict 90% threshold for Pro fallback
        enable_auto_upgrade=True,
        enable_parallel=True,
        max_workers=args.workers,
        enable_checkpoints=True,
        checkpoint_interval=10,
        output_dir=args.output,
        # Vertex AI settings
        use_vertex_ai=True,
        project_id=None,  # Will auto-detect from JSON
        location="us-central1"
    )
    
    print("\n🚀 Starting Extraction Run")
    print(f"PDF: {args.pdf_path}")
    print(f"Pages: {args.start} to {args.end}")
    print(f"Workers: {args.workers}")
    print(f"Strategy: Two-Tier (Flash-Lite -> Pro)")
    print("-" * 50)
    
    # 3. Convert PDF to Images
    from pdf2image import convert_from_path
    
    print("📸 Converting PDF to images (this may take a moment)...")
    try:
        images = convert_from_path(
            args.pdf_path,
            first_page=args.start,
            last_page=args.end,
            dpi=250
        )
    except Exception as e:
        print(f"❌ PDF Conversion Failed: {e}")
        print("Tip: Install poppler-utils if not installed.")
        return

    print(f"✅ Converted {len(images)} pages.")

    # 4. Run Extraction
    extractor = VisionExtractor(config)
    batch = BatchExtractor(extractor)
    
    # We pass the images list directly
    # Note: start_page argument is for labeling, it doesn't skip images
    result = batch.extract_pages(
        images=images,
        book_title=Path(args.pdf_path).stem,
        start_page=args.start
    )
    
    print("\n" + "="*50)
    print("🎉 Run Complete!")
    print(f"See results in: {args.output}")

if __name__ == "__main__":
    main()
