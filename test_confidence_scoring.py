#!/usr/bin/env python3
"""
Test script for confidence scoring and two-tier extraction.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    # Load .env from the same directory as this script
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded .env from: {env_path}")
except ImportError:
    print("WARNING: dotenv not found, skipping .env loading")
    # Make sure API key is in environment
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY must be set in environment")
        sys.exit(1)

from src.rag.extraction.vision_extractor import VisionExtractor, ExtractionConfig
from pdf2image import convert_from_path
import json

def test_confidence_scoring(pdf_path: str, page_num: int = 1):
    """Test confidence scoring on a single page."""
    
    print("\n" + "="*70)
    print("CONFIDENCE SCORING TEST")
    print("="*70)
    
    # Configure with two-tier strategy
    config = ExtractionConfig(
        primary_model="models/gemini-flash-lite-latest",
        upgrade_model="models/gemini-2.5-pro",
        confidence_threshold=0.8,
        enable_auto_upgrade=True,
        save_raw_responses=True,
        output_dir="./test_confidence_output"
    )
    
    print(f"\nConfiguration:")
    print(f"  Primary Model: {config.primary_model}")
    print(f"  Upgrade Model: {config.upgrade_model}")
    print(f"  Confidence Threshold: {config.confidence_threshold}")
    print(f"  Auto-Upgrade: {config.enable_auto_upgrade}")
    
    # Initialize extractor
    print(f"\nInitializing VisionExtractor...")
    extractor = VisionExtractor(config)
    
    # Convert PDF page to image
    print(f"\nConverting page {page_num} to image...")
    images = convert_from_path(pdf_path, dpi=250, first_page=page_num, last_page=page_num)
    if not images:
        print("❌ Failed to convert PDF page")
        return
    
    image = images[0]
    print(f"✓ Image size: {image.size}")
    
    # Extract with confidence scoring
    print(f"\n{'='*70}")
    print(f"EXTRACTING PAGE {page_num}")
    print(f"{'='*70}\n")
    
    result = extractor.extract_page(
        image=image,
        page_num=page_num,
        book_title="Test Book"
    )
    
    # Display results
    print(f"\n{'='*70}")
    print("EXTRACTION RESULTS")
    print(f"{'='*70}")
    
    print(f"\n[Page Info]:")
    print(f"  Page Number: {result.metadata.page_number}")
    print(f"  Page Type: {result.metadata.page_type}")
    print(f"  Content Blocks: {len(result.content_blocks)}")
    
    print(f"\n[Confidence Scoring]:")
    if result.confidence:
        print(f"  Overall Score: {result.confidence.overall_score:.2f}")
        print(f"  Criteria:")
        for criterion, score in result.confidence.criteria.items():
            print(f"    - {criterion}: {score:.2f}")
        if result.confidence.reasoning:
            print(f"  Reasoning: {result.confidence.reasoning}")
        if result.confidence.flags:
            print(f"  Flags: {', '.join(result.confidence.flags)}")
    else:
        print(f"  Overall Score: {result.extraction_confidence:.2f} (legacy)")
    
    print(f"\n[Retry Metadata]:")
    if result.retry_metadata:
        print(f"  Initial Model: {result.retry_metadata.initial_model}")
        print(f"  Retry Count: {result.retry_metadata.retry_count}")
        if result.retry_metadata.retry_count > 0:
            print(f"  Retry Model: {result.retry_metadata.retry_model}")
            print(f"  Initial Confidence: {result.retry_metadata.initial_confidence:.2f}")
            print(f"  Retry Reason: {result.retry_metadata.retry_reason}")
            print(f"\n  >>> PAGE UPGRADED - Confidence improved!")
        else:
            print(f"  >>> No retry needed - Good quality")
    
    # Save results for inspection
    output_file = Path(config.output_dir) / f"test_page_{page_num}_result.json"
    output_file.parent.mkdir(exist_ok=True, parents=True)
    
    result_dict = {
        "page_number": result.metadata.page_number,
        "page_type": result.metadata.page_type,
        "content_blocks_count": len(result.content_blocks),
        "extraction_confidence": result.extraction_confidence,
        "confidence": result.confidence.dict() if result.confidence else None,
        "retry_metadata": result.retry_metadata.dict() if result.retry_metadata else None,
        "sample_content": result.raw_text[:500] if result.raw_text else ""
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SAVED] Results saved to: {output_file}")
    print(f"\n{'='*70}")
    print("[SUCCESS] TEST COMPLETE")
    print(f"{'='*70}\n")
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\nUsage: python test_confidence_scoring.py <pdf_path> [page_num]")
        print("\nExample:")
        print("  python test_confidence_scoring.py sample.pdf 1")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    if not Path(pdf_path).exists():
        print(f"\n❌ PDF not found: {pdf_path}")
        sys.exit(1)
    
    try:
        test_confidence_scoring(pdf_path, page_num)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
