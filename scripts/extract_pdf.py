# scripts/extract_pdf.py
# scripts\extract_pdf.py
#!/usr/bin/env python3
"""
Interactive PDF Extraction Tool
Wrapper around the production VisionExtractor logic.
"""

import os
import sys
import json
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent  # Go up from scripts/ to project root
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import our production modules
try:
    from src.rag.extraction.vision_extractor import VisionExtractor, ExtractionConfig
    from src.rag.extraction.pdf_processor import PDFProcessor
except ImportError:
    print("[FAIL] Error: Could not import production modules.")
    print("Make sure you are running from the project root.")
    sys.exit(1)

# Configure logging to show our custom logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Interactive extraction interface"""
    print("\n")
    print("="*70)
    print("  ASTRO CHATBOT - INTERACTIVE EXTRACTION")
    print("  Uses Strict Hybrid Strategy (Flash-Lite / Flash / Pro)")
    print("="*70)
    print()
    
    # Get PDF path
    default_pdf = "data/raw/BrihatParasaraHoraSastra.pdf"
    pdf_input = input(f"Enter PDF file path [{default_pdf}]: ").strip().strip('"')
    pdf_path = pdf_input or default_pdf
    
    if not os.path.exists(pdf_path):
        print(f"\n[FAIL] File not found: {pdf_path}")
        return
    
    print(f"✓ PDF found: {pdf_path}\n")
    
    # Initialize Processor and Extractor
    print("Initializing engines...")
    try:
        pdf_processor = PDFProcessor(pdf_path)
        
        # Use our production config
        config = ExtractionConfig(
            output_dir="./extraction_output_interactive",
            save_raw_responses=True,
            enable_hybrid_strategy=True  # Ensure hybrid is on
        )
        extractor = VisionExtractor(config)
        print("✓ Engines ready\n")
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return

    while True:
        print("-" * 50)
        print("MODES:")
        print("  1. Extract Single Page")
        print("  2. Extract Range")
        print("  q. Quit")
        
        choice = input("\nSelect mode: ").strip().lower()
        
        if choice == 'q':
            break
            
        if choice == '1':
            try:
                page_num_str = input("Page number: ").strip()
                if not page_num_str: continue
                page_num = int(page_num_str)
                
                print(f"\nProcessing Page {page_num}...")
                
                # 1. Convert to image
                images = pdf_processor.convert_to_images(page_num, page_num)
                if not images:
                    print("[FAIL] Failed to convert PDF page")
                    continue
                image = images[0]
                
                # 2. Extract using production logic
                result = extractor.extract_page(image, page_num)
                
                # 3. Show Result
                print("\n" + "="*30)
                print(f"RESULT (Confidence: {result.extraction_confidence:.2f})")
                print("="*30)
                print(f"Model Used: {result.confidence.reasoning if result.confidence else 'Unknown'}")
                if result.retry_metadata:
                    print(f"RETRY TRIGGERED: Yes (Count: {result.retry_metadata.retry_count})")
                    print(f"Retry Reason: {result.retry_metadata.retry_reason}")
                
                print("\nCONTENT PREVIEW:")
                print("-" * 20)
                content_preview = result.raw_text[:500] + "..." if len(result.raw_text) > 500 else result.raw_text
                print(content_preview)
                print("\n" + "="*70)
                
                # Save schema-compliant final JSON (for Preprocessing)
                final_json_path = Path(extractor.output_dir) / f"page_{page_num}_final.json"
                with open(final_json_path, 'w', encoding='utf-8') as f:
                    # Use model_dump() if Pydantic v2, else dict()
                    data = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"✓ Saved Final JSON: {final_json_path}")
                print(f"  (Use this file for run_preprocessing_phases.py)")
                print(f"Saved artifacts to: {extractor.output_dir}")
                
            except ValueError:
                print("[FAIL] Invalid number")
            except Exception as e:
                print(f"[FAIL] Error: {e}")
                import traceback
                traceback.print_exc()

        elif choice == '2':
            print("\n[WARN]  For robust batch processing, use 'batch_extract.py' instead.")
            print("   This tool is optimized for single-page debugging.")
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
