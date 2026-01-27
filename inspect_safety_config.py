#!/usr/bin/env python3
"""
Inspect SafetyConfig Schema

This script shows the exact structure expected by your SafetyConfig Pydantic model.
"""

import sys
from pathlib import Path
import json

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("SafetyConfig Schema Inspector")
print("=" * 70)
print()

try:
    from src.utils.config import SafetyConfig
    from pydantic import BaseModel
    
    print("✅ Successfully imported SafetyConfig")
    print()
    
    # Get the JSON schema
    schema = SafetyConfig.model_json_schema()
    
    print("Full JSON Schema:")
    print("-" * 70)
    print(json.dumps(schema, indent=2))
    print()
    
    # Show field details
    print("=" * 70)
    print("Field Details:")
    print("=" * 70)
    
    for field_name, field_info in SafetyConfig.model_fields.items():
        print(f"\n📋 {field_name}")
        print(f"   Type: {field_info.annotation}")
        print(f"   Required: {field_info.is_required()}")
        
        if not field_info.is_required():
            print(f"   Default: {field_info.default}")
        
        if field_info.description:
            print(f"   Description: {field_info.description}")
    
    print()
    print("=" * 70)
    print("Example YAML Configuration:")
    print("=" * 70)
    
    # Try to create an example
    try:
        # Try with minimal fields
        example = SafetyConfig(
            blocked_topics=[],
            disclaimer_topics={},
            disclaimer_template="Example template"
        )
        print("✅ Minimal config works:")
        print()
        print("safety:")
        print("  blocked_topics: []")
        print("  disclaimer_topics: {}")
        print("  disclaimer_template: 'Text here'")
        
    except Exception as e:
        print(f"❌ Minimal config failed: {e}")
        print()
        print("The schema above shows what's actually required.")
    
    print()
    print("=" * 70)
    
except ImportError as e:
    print(f"❌ Failed to import SafetyConfig: {e}")
    print()
    print("Make sure you're running from project root:")
    print("  cd /path/to/astro_chatbot")
    print("  python inspect_safety_config.py")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
