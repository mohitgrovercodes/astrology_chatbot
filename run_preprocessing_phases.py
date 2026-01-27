#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Preprocessing Phases 2-5 on Extracted Data
Uses existing extraction output from Phase 1
"""

import os
import sys
from pathlib import Path

# Setup UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup paths - add preprocessing directory to path
project_root = Path(__file__).parent
preprocessing_dir = project_root / "src" / "rag" / "preprocessing"
sys.path.insert(0, str(preprocessing_dir))
sys.path.insert(0, str(project_root))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=project_root / ".env")
    print(f"[OK] Loaded environment")
except ImportError:
    print("[WARN] python-dotenv not installed")

def main():
    print("="*70)
    print("TEXT PREPROCESSING PIPELINE (Phases 2-5)")
    print("="*70)
    print()
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Preprocessing Phases 2-5")
    parser.add_argument("--input", "-i", type=str, help="Input JSON file path", default=None)
    parser.add_argument("--output", "-o", type=str, help="Output directory", default="./preprocessing_output")
    args = parser.parse_args()
    
    # Configuration
    default_input = "extraction_output/batch_result_pages_108-116.json"
    
    if args.input:
        input_json = args.input
    else:
        # Auto-detect most recent batch file if no input provided
        if Path(default_input).exists():
           input_json = default_input
        else:
           # Try to find any batch result
           batches = list(Path("extraction_output").glob("batch_result_*.json"))
           if batches:
               input_json = str(batches[-1])
           else:
               input_json = default_input # Fallback
    
    output_dir = args.output
    
    # Check input exists
    if not Path(input_json).exists():
        print(f"[ERROR] Input file not found: {input_json}")
        print(f"Please specify a file with --input")
        return 1
    
    print(f"[INPUT] {input_json}")
    print(f"[OUTPUT] {output_dir}")
    print()
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Import preprocessing pipeline
    try:
        from pipeline import PreprocessingPipeline
    except ImportError as e:
        print(f"[ERROR] Failed to import PreprocessingPipeline: {e}")
        print("[INFO] Trying alternative import...")
        try:
            from src.rag.preprocessing.pipeline import PreprocessingPipeline
        except ImportError as e2:
            print(f"[ERROR] Alternative import also failed: {e2}")
            return 1
    
    # Initialize pipeline
    print("[INIT] Initializing preprocessing pipeline...")
    pipeline = PreprocessingPipeline(
        source_book="Brihat Parasara Hora Sastra",
        tradition="vedic",
        use_llm=True,  # Enable LLM for enrichment
        use_llm_cleaning=True, # Enable LLM for structural cleaning (Phase 2)
        output_dir=output_dir
    )
    print("[OK] Pipeline initialized")
    print()
    
    # Run phases 2-5
    print("[RUN] Running preprocessing phases 2-5...")
    print()
    
    try:
        enriched_doc = pipeline.run_full_pipeline(
            input_file=input_json,
            skip_embedding=True  # Skip Phase 6 (embedding)
        )
        
        print()
        print("="*70)
        print("[SUCCESS] PREPROCESSING COMPLETE!")
        print("="*70)
        print()
        
        # Display summary
        print("[SUMMARY]")
        print(f"  Source File: {enriched_doc.source_file}")
        print(f"  Total Chunks: {len(enriched_doc.chunks)}")
        
        if enriched_doc.chunks:
            avg_tokens = sum(c.token_count for c in enriched_doc.chunks) / len(enriched_doc.chunks)
            total_tokens = sum(c.token_count for c in enriched_doc.chunks)
            print(f"  Avg Tokens/Chunk: {avg_tokens:.0f}")
            print(f"  Total Tokens: {total_tokens}")
        
        print()
        print("[OUTPUT FILES]")
        for phase_file in sorted(Path(output_dir).glob("*.json")):
            print(f"  - {phase_file.name}")
        
        print()
        print("[NEXT STEP] Phase 6: Vector Ingestion (Embedding)")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
