#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Only Phase 5: Chunk Enrichment

Takes Phase 4 output (SemanticDocument) and runs Phase 5 enrichment.
"""

import os
import sys
import json
from pathlib import Path

# Setup UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup paths
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
    print("PHASE 5 ONLY: CHUNK ENRICHMENT")
    print("="*70)
    print()
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Only Phase 5: Chunk Enrichment")
    parser.add_argument("input", help="Input Phase 4 JSON file (SemanticDocument)")
    parser.add_argument("--output", "-o", type=str, help="Output directory", default="./preprocessing_output")
    parser.add_argument("--source-book", "-s", type=str, help="Source book name", default=None)
    parser.add_argument("--tradition", "-t", type=str, choices=["vedic", "western"], default="vedic")
    args = parser.parse_args()
    
    input_file = args.input
    output_dir = args.output
    
    # Check input exists
    if not Path(input_file).exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return 1
    
    print(f"[INPUT] {input_file}")
    print(f"[OUTPUT] {output_dir}")
    print()
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Import required modules
    try:
        from src.rag.preprocessing.schemas import SemanticDocument, EnrichedDocument
        from src.rag.preprocessing.pipeline import PreprocessingPipeline
    except ImportError as e:
        print(f"[ERROR] Failed to import modules: {e}")
        return 1
    
    # Load Phase 4 output
    print("[LOAD] Loading Phase 4 output...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify it's a SemanticDocument
        if "units" not in data:
            print(f"[ERROR] Input file doesn't appear to be a Phase 4 output (no 'units' field)")
            return 1
        
        semantic_doc = SemanticDocument(**data)
        print(f"[OK] Loaded {len(semantic_doc.units)} semantic units")
    except Exception as e:
        print(f"[ERROR] Failed to load input: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Determine source book
    source_book = args.source_book
    if not source_book and semantic_doc.source_file:
        # Try to extract from filename
        source_book = Path(semantic_doc.source_file).stem.replace("_", " ").title()
    if not source_book:
        source_book = "Unknown Book"
    
    print(f"[INFO] Source Book: {source_book}")
    print(f"[INFO] Tradition: {args.tradition}")
    print()
    
    # Initialize pipeline (only needs enricher)
    print("[INIT] Initializing enricher...")
    pipeline = PreprocessingPipeline(
        source_book=source_book,
        tradition=args.tradition,
        use_llm=True,  # Phase 5 requires LLM
        output_dir=output_dir
    )
    print("[OK] Enricher initialized")
    print()
    
    # Run Phase 5
    try:
        enriched_doc = pipeline.run_phase5(semantic_doc)
        
        print()
        print("="*70)
        print("[SUCCESS] PHASE 5 COMPLETE!")
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
        for phase_file in sorted(Path(output_dir).glob("*phase5*.json")):
            print(f"  - {phase_file.name}")
        
        print()
        print("[NEXT STEP] Phase 6: Vector Ingestion (Embedding)")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"[ERROR] Phase 5 failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
