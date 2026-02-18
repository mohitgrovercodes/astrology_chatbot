# tests/test_preprocessing.py
# tests\test_preprocessing.py
#!/usr/bin/env python3
"""
Test script for the preprocessing pipeline.
Run from project root: python tests/test_preprocessing.py
"""

import sys
import os
from pathlib import Path

# Add project root to path - but avoid importing full src package
project_root = Path(__file__).parent.parent
# Add the rag/preprocessing path directly to avoid src/__init__.py imports
preprocessing_path = project_root / "src" / "rag" / "preprocessing"
sys.path.insert(0, str(preprocessing_path))
sys.path.insert(0, str(project_root / "src" / "rag"))
sys.path.insert(0, str(project_root))

import json


def test_structural_cleaner():
    """Test the structural cleaner with sample data."""
    print("=" * 70)
    print("TESTING STRUCTURAL CLEANER (Phase 2)")
    print("=" * 70)
    
    # Import schemas directly (preprocessing is in path)
    from schemas import (
        ExtractedPage, 
        CleanedPage, 
        CleanedDocument,
        PageType
    )
    
    # Now we can test the cleaner logic
    # First, let's test the schemas work
    sample_file = project_root / "extracted" / "sample_bphs_pages.json"
    
    if not sample_file.exists():
        print(f"[SKIP] Sample file not found: {sample_file}")
        return False
    
    print(f"\n[1/4] Loading sample file: {sample_file.name}")
    with open(sample_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[OK] Loaded {len(data)} pages")
    
    # Test schema parsing
    print(f"\n[2/4] Validating schemas...")
    try:
        pages = [ExtractedPage(**page) for page in data]
        print(f"[OK] All {len(pages)} pages validated with Pydantic schema")
    except Exception as e:
        print(f"[FAIL] Schema validation error: {e}")
        return False
    
    # Test the cleaner
    print(f"\n[3/4] Testing StructuralCleaner...")
    try:
        # Import cleaner classes (preprocessing is in path)
        from structural_cleaner import StructuralCleaner
        
        cleaner = StructuralCleaner()
        
        # Detect global headers
        headers = cleaner.detect_global_headers(pages)
        print(f"[OK] Detected {len(headers)} global headers: {headers[:3]}...")
        
        # Clean all pages
        cleaned_doc = cleaner.clean_document(pages, source_file=str(sample_file))
        print(f"[OK] Cleaned {len(cleaned_doc.pages)} pages")
        
    except Exception as e:
        import traceback
        print(f"[FAIL] Cleaner error: {e}")
        traceback.print_exc()
        return False
    
    # Show results
    print(f"\n[4/4] Results:")
    print("-" * 70)
    
    for page in cleaned_doc.pages:
        print(f"\nPage {page.page_number}:")
        print(f"  Original title: {data[page.page_number-1].get('title', 'N/A')}")
        print(f"  Validated title: {page.title}")
        print(f"  Title was header: {page.title_was_header}")
        print(f"  Cleaning applied: {', '.join(page.cleaning_applied)}")
        print(f"  Verse numbers: {page.verse_numbers}")
        content_preview = page.content[:150].encode('ascii', 'replace').decode('ascii')
        print(f"  Content (first 150 chars): {content_preview}...")
    
    # Save output
    output_file = project_root / "extracted" / "cleaned_1-3.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_doc.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Saved cleaned output to: {output_file}")
    
    print("\n" + "=" * 70)
    print("STRUCTURAL CLEANER TEST PASSED")
    print("=" * 70)
    return True


def test_schemas():
    """Test that all schemas are importable and valid."""
    print("=" * 70)
    print("TESTING SCHEMAS")
    print("=" * 70)
    
    try:
        from schemas import (
            ExtractedPage,
            CleanedPage,
            LinkedPage,
            SemanticUnit,
            EnrichedChunk,
            PageType,
            UnitType,
        )
        print("[OK] All schemas imported successfully")
        
        # Test PageType enum
        assert PageType.MIXED == "mixed"
        print("[OK] PageType enum works")
        
        # Test UnitType enum
        assert UnitType.VERSE_COMMENTARY == "verse_commentary"
        print("[OK] UnitType enum works")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Schema import error: {e}")
        return False


if __name__ == "__main__":
    print("\nPreprocessing Pipeline Tests\n")
    
    results = []
    
    # Test 1: Schemas
    results.append(("Schemas", test_schemas()))
    
    # Test 2: Structural Cleaner
    results.append(("Structural Cleaner", test_structural_cleaner()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
