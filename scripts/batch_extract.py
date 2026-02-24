# scripts/batch_extract.py
# scripts\batch_extract.py
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
project_root = Path(__file__).parent.parent  # Go up from scripts/ to project root
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
    # Make arguments optional for interactive mode
    parser.add_argument("pdf_path", nargs="?", help="Path to PDF file")
    parser.add_argument("--start", type=int, default=None, help="Start page")
    parser.add_argument("--end", type=int, default=None, help="End page")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--output", default="./extraction_output", help="Output directory")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("📑 Batch PDF Extraction Tool")
    print("=" * 60)
    
    # 1. Input File
    if not args.pdf_path:
        # Check defaults
        default_dir = Path("data/raw")
        default_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_files = list(default_dir.glob("*.pdf"))
        
        if pdf_files:
            print(f"\nFound PDFs in {default_dir}:")
            for i, f in enumerate(pdf_files, 1):
                print(f"  {i}. {f.name}")
        
        while not args.pdf_path:
            prompt = "\n[1/4] Enter input PDF path"
            if pdf_files:
                prompt += f" (or enter number 1-{len(pdf_files)}): "
            else:
                prompt += ": "
                
            val = input(prompt).strip().strip('"')
            
            # Check if user entered a number
            if val.isdigit() and pdf_files:
                idx = int(val) - 1
                if 0 <= idx < len(pdf_files):
                    args.pdf_path = str(pdf_files[idx])
                    print(f"     Selected: {args.pdf_path}")
                    break
            
            # Check if user entered a path
            if os.path.exists(val):
                args.pdf_path = val
            elif os.path.exists(default_dir / val):
                 args.pdf_path = str(default_dir / val)
            else:
                print(f"[FAIL] File not found: {val}")
    
    # 2. Start Page
    if args.start is None:
        while True:
            try:
                val = input("\n[2/4] Enter Start Page (Default: 1): ").strip()
                args.start = int(val) if val else 1
                if args.start < 1: raise ValueError
                break
            except ValueError:
                print("[FAIL] Invalid input. Please enter a positive integer.")
                
    # 3. End Page
    if args.end is None:
        while True:
            try:
                val = input("\n[3/4] Enter End Page (e.g., 50): ").strip()
                if not val:
                    print("[FAIL] End page is required for batch processing.")
                    continue
                args.end = int(val)
                if args.end < args.start:
                    print(f"[FAIL] End page must be at least {args.start}.")
                    continue
                break
            except ValueError:
                print("[FAIL] Invalid input. Please enter a positive integer.")

    # 4. Workers
    if args.workers is None:
        default_workers = 4
        try:
            val = input(f"\n[4/4] Number of parallel workers (Default: {default_workers}): ").strip()
            args.workers = int(val) if val else default_workers
        except ValueError:
            args.workers = default_workers

    
    # 1. AUTH SETUP: Use GCP Credentials for Vertex AI
    # Ensure credentials file is set
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Check potential default path
        default_creds = project_root / "google_credentials.json"
        if default_creds.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(default_creds)
            print(f"🔑 Using Credentials: {default_creds}")
        else:
            print("[FAIL] Error: GOOGLE_APPLICATION_CREDENTIALS not set and not found in root.")
            return

    print("[VERTEX AI] Configuring for Google Cloud Vertex AI...")
    
    # 2. Setup Configuration
    config = ExtractionConfig(
        # Model Strategy
        primary_model="gemini-2.5-flash-lite",  # Fast for text-heavy pages
        hybrid_table_model="gemini-2.5-flash",  # Better for table-heavy pages
        upgrade_model="gemini-2.5-pro",         # Fallback for low confidence
        enable_hybrid_strategy=True,            # [OK] Use Flash for tables, Lite for text
        
        # Quality Settings
        confidence_threshold=0.9,               # Strict 90% threshold for Pro fallback
        enable_auto_upgrade=True,
        enable_content_validation=True,         # [OK] Validate and adjust confidence
        
        # Performance
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
    
    print("\n[START] Starting Extraction Run")
    print(f"PDF: {args.pdf_path}")
    print(f"Pages: {args.start} to {args.end}")
    print(f"Workers: {args.workers}")
    print(f"Strategy: Two-Tier (Flash-Lite -> Pro)")
    print("-" * 50)
    
    # 3. Convert PDF to Images
    from pdf2image import convert_from_path
    
    print("[CONVERT] Converting PDF to images (this may take a moment)...")
    try:
        images = convert_from_path(
            args.pdf_path,
            first_page=args.start,
            last_page=args.end,
            dpi=250
        )
    except Exception as e:
        print(f"[ERROR] PDF Conversion Failed: {e}")
        print("Tip: Install poppler-utils if not installed.")
        return

    print(f"[OK] Converted {len(images)} pages.")

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
    
    # 5. Save Consolidated Batch Result (for preprocessing pipeline)
    output_dir = Path(args.output)
    batch_result_path = output_dir / f"batch_result_pages_{args.start}-{args.end}.json"
    
    # Convert pages to preprocessing pipeline format
    # Mapping extraction schema (PageMetadata, ContentBlock) to preprocessing schema (ExtractedPage)
    pages_data = []
    for page in result.pages:
        # Combine all content blocks into a single content string
        content_text = page.raw_text or ""
        if not content_text and page.content_blocks:
            # Fallback: combine content blocks if raw_text is empty
            content_text = "\n\n".join(block.text for block in page.content_blocks if block.text)
        
        # Extract verses and verse numbers from content blocks
        verses = []
        verse_numbers = []
        tables = []
        
        for block in page.content_blocks:
            # Safely get content_type value
            try:
                content_type_value = block.content_type.value if hasattr(block.content_type, 'value') else str(block.content_type)
            except Exception:
                content_type_value = "prose"  # Default fallback
            
            if content_type_value.lower() in ["shloka", "translation"] and block.text:
                verses.append(block.text)
                if block.verse_data and hasattr(block.verse_data, 'verse_number') and block.verse_data.verse_number:
                    verse_numbers.append(str(block.verse_data.verse_number))
            elif content_type_value.lower() == "table" and block.table_data:
                # Convert table_data to dict if it's a Pydantic model
                try:
                    if hasattr(block.table_data, 'model_dump'):
                        tables.append(block.table_data.model_dump())
                    else:
                        tables.append(block.table_data)
                except Exception:
                    pass  # Skip tables that fail to convert
        
        # Map page_type from extraction to preprocessing enum
        # Extraction uses: text_heavy, table_heavy, mixed, chart, title, index
        # Preprocessing uses: text, table, mixed, title_page
        try:
            page_type_raw = page.metadata.page_type.value if hasattr(page.metadata.page_type, 'value') else str(page.metadata.page_type)
        except Exception:
            page_type_raw = "mixed"
            
        page_type_map = {
            "text_heavy": "text",
            "table_heavy": "table",
            "mixed": "mixed",
            "chart": "mixed",
            "title": "title_page",
            "index": "text"
        }
        page_type = page_type_map.get(page_type_raw, "mixed")
        
        # Determine has_sanskrit from languages_present
        # PageMetadata.languages_present: List[str] - check if "sanskrit" or "hindi" present
        has_sanskrit = False
        try:
            if hasattr(page.metadata, 'languages_present') and page.metadata.languages_present:
                langs_lower = [lang.lower() for lang in page.metadata.languages_present]
                has_sanskrit = any(lang in langs_lower for lang in ["sanskrit", "hindi", "devanagari"])
        except Exception:
            has_sanskrit = False
        
        # Get chapter/section title safely
        title = None
        try:
            title = page.metadata.chapter_title or page.metadata.section_title
        except Exception:
            pass
        
        # Create preprocessing-compatible page dict
        page_dict = {
            "page_number": page.metadata.page_number,
            "page_type": page_type,
            "title": title,
            "content": content_text,
            "has_sanskrit": has_sanskrit,
            "verses": verses,
            "verse_numbers": verse_numbers,
            "tables": tables,
        }
        
        # Add optional fields safely
        try:
            if page.confidence:
                page_dict["confidence"] = page.confidence.model_dump()
        except Exception:
            pass
            
        try:
            if page.retry_metadata:
                page_dict["retry_metadata"] = page.retry_metadata.model_dump()
        except Exception:
            pass
        
        pages_data.append(page_dict)
    
    # Save consolidated batch result
    import json
    with open(batch_result_path, 'w', encoding='utf-8') as f:
        json.dump(pages_data, f, ensure_ascii=False, indent=2)
        
    # Also save as text file for easy reading/debugging
    txt_result_path = str(batch_result_path).replace('.json', '.txt')
    with open(txt_result_path, 'w', encoding='utf-8') as f:
        f.write(f"EXTRACTION BATCH: Pages {args.start} to {args.end}\n")
        f.write(f"Source: {args.pdf_path}\n")
        f.write("="*60 + "\n\n")
        
        for page_data in pages_data:
            p_num = page_data.get('page_number', '?')
            p_conf = page_data.get('confidence', {}).get('overall_score', 0.0)
            
            # Determine model used
            retry_meta = page_data.get('retry_metadata')
            if retry_meta and retry_meta.get('retry_count', 0) > 0:
                model_label = "GEMINI-2.5-PRO (Expensive)"
                icon = "💰"
            else:
                # Default is usually Flash-Lite or Flash based on page type
                # We can infer from page type if needed, but "Standard" is safe
                p_type = page_data.get('metadata', {}).get('page_type', 'unknown')
                model_name = "GEMINI-2.5-FLASH-LITE" if p_type == 'text_heavy' else "GEMINI-2.5-FLASH"
                model_label = f"{model_name} (Cheap)"
                icon = "⚡"
            
            f.write(f"PAGE {p_num} {icon} [{model_label}] (Conf: {p_conf:.2f})\n")
            f.write("-" * 50 + "\n")
            f.write(page_data.get('content', '') + "\n")
            f.write("="*60 + "\n\n")
            
    print(f"[BATCH] Consolidated text saved: {txt_result_path}")
    
    print("\n" + "="*50)
    print("[COMPLETE] Run Complete!")
    print(f"See results in: {args.output}")
    print(f"[BATCH] Consolidated result: {batch_result_path.name}")

if __name__ == "__main__":
    main()
