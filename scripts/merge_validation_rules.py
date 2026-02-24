#!/usr/bin/env python3
# merge_validation_rules.py
"""
Merge Validation Rules - Enhanced with Deduplication

Combines multiple JSON rule files with smart deduplication.

Usage:
    # Merge multiple files into one
    python merge_validation_rules.py file1.json file2.json file3.json --output merged.json
    
    # Append to existing file
    python merge_validation_rules.py new_file.json --append-to existing.json
    
    # Merge without deduplication
    python merge_validation_rules.py file1.json file2.json --output merged.json --no-deduplicate
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter


def convert_to_hashable(value):
    """
    Convert unhashable types (list, dict) to hashable equivalents.
    
    Args:
        value: Any value (string, list, dict, etc.)
        
    Returns:
        Hashable version of the value
    """
    if isinstance(value, list):
        # Convert list to tuple of sorted strings
        return tuple(sorted(str(v) for v in value))
    elif isinstance(value, dict):
        # Convert dict to sorted tuple of items
        return tuple(sorted((k, str(v)) for k, v in value.items()))
    else:
        return value


def deduplicate_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate rules based on rule_name + category
    
    For duplicates, keeps the rule with higher extraction_confidence
    
    Handles list/dict fields by converting to hashable types
    """
    
    print(f"\n🔍 Deduplicating {len(rules)} rules...")
    
    # Track unique rules by (rule_name, category)
    unique_map = {}
    
    for rule in rules:
        rule_name = rule.get('rule_name', 'Unknown')
        category = rule.get('category', 'general')
        
        # Convert category to hashable (handles list, dict, string)
        category_hashable = convert_to_hashable(category)
        
        # Create key for deduplication
        key = (rule_name, category_hashable)
        
        # If not seen before, add it
        if key not in unique_map:
            unique_map[key] = rule
        else:
            # If seen before, keep the one with higher confidence
            existing_conf = unique_map[key].get('extraction_confidence', 0.0)
            new_conf = rule.get('extraction_confidence', 0.0)
            
            if new_conf > existing_conf:
                unique_map[key] = rule
    
    unique_rules = list(unique_map.values())
    duplicates_removed = len(rules) - len(unique_rules)
    
    print(f"  ✅ Removed {duplicates_removed} duplicates")
    print(f"  ✅ Unique rules: {len(unique_rules)}")
    
    return unique_rules


def load_rules(filepath: Path) -> List[Dict[str, Any]]:
    """Load validation rules from JSON file"""
    print(f"📖 Loading: {filepath}")
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both formats: list of rules or dict with 'rules' key
    if isinstance(data, list):
        rules = data
    elif isinstance(data, dict) and 'rules' in data:
        rules = data['rules']
    else:
        raise ValueError(f"Invalid format in {filepath}. Expected list or dict with 'rules' key.")
    
    print(f"  ✅ Loaded {len(rules)} rules")
    return rules


def save_rules(rules: List[Dict[str, Any]], output_path: Path, metadata: Dict[str, Any] = None):
    """
    Save rules to JSON file with metadata
    
    Args:
        rules: List of validation rules
        output_path: Output file path
        metadata: Optional metadata dict
    """
    print(f"\n💾 Saving to: {output_path}")
    
    # Default metadata
    if metadata is None:
        metadata = {
            "total_rules": len(rules),
            "description": "Merged validation rules"
        }
    
    # Update rule count
    metadata["total_rules"] = len(rules)
    
    # Create output structure
    output_data = {
        "metadata": metadata,
        "rules": rules
    }
    
    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save with pretty formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ Saved {len(rules)} rules")
    print(f"  📊 File size: {output_path.stat().st_size / 1024:.2f} KB")


def analyze_rules(rules: List[Dict[str, Any]]):
    """Print analysis of rule set"""
    print(f"\n📊 Analysis:")
    print(f"  Total rules: {len(rules)}")
    
    # Count by category
    categories = [r.get('category', 'unknown') for r in rules]
    # Handle list categories
    flat_categories = []
    for cat in categories:
        if isinstance(cat, list):
            flat_categories.extend(cat)
        else:
            flat_categories.append(cat)
    
    category_counts = Counter(flat_categories)
    print(f"  Categories: {len(category_counts)}")
    for cat, count in category_counts.most_common(10):
        print(f"    {cat}: {count}")
    
    # Count by severity
    severities = [r.get('severity', 'unknown') for r in rules]
    severity_counts = Counter(severities)
    print(f"  Severities:")
    for sev, count in severity_counts.most_common():
        print(f"    {sev}: {count}")
    
    # Average confidence
    confidences = [r.get('extraction_confidence', 0.0) for r in rules]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        print(f"  Avg confidence: {avg_conf:.3f}")


def merge_files(
    input_files: List[Path],
    output_file: Path,
    deduplicate: bool = True
):
    """
    Merge multiple validation rule files
    
    Args:
        input_files: List of input JSON files
        output_file: Output JSON file
        deduplicate: Whether to remove duplicates
    """
    print("=" * 60)
    print("🔀 MERGING VALIDATION RULES")
    print("=" * 60)
    
    print(f"📁 Input files: {len(input_files)}")
    for f in input_files:
        print(f"  - {f}")
    print(f"📁 Output: {output_file}")
    print(f"🔍 Deduplicate: {deduplicate}")
    
    # Load all rules
    all_rules = []
    for filepath in input_files:
        rules = load_rules(filepath)
        all_rules.extend(rules)
    
    print(f"\n📊 Combined: {len(all_rules)} rules")
    
    # Deduplicate if requested
    if deduplicate:
        all_rules = deduplicate_rules(all_rules)
    
    # Analyze
    analyze_rules(all_rules)
    
    # Save
    metadata = {
        "total_rules": len(all_rules),
        "description": f"Merged from {len(input_files)} files",
        "source_files": [str(f) for f in input_files],
        "deduplicated": deduplicate
    }
    
    save_rules(all_rules, output_file, metadata)
    
    print("\n" + "=" * 60)
    print("✅ MERGE COMPLETE")
    print("=" * 60)


def append_to_existing(
    new_file: Path,
    existing_file: Path,
    deduplicate: bool = True
):
    """
    Append rules from new file to existing file
    
    Args:
        new_file: New rules file
        existing_file: Existing rules file (will be updated)
        deduplicate: Whether to remove duplicates
    """
    print("=" * 60)
    print("➕ APPENDING RULES TO EXISTING FILE")
    print("=" * 60)
    
    print(f"📁 New file: {new_file}")
    print(f"📁 Existing file: {existing_file}")
    print(f"🔍 Deduplicate: {deduplicate}")
    
    # Load existing rules
    print(f"\n📖 Loading existing rules from {existing_file}...")
    existing_rules = load_rules(existing_file)
    
    # Load new rules
    print(f"📖 Loading new rules from {new_file}...")
    new_rules = load_rules(new_file)
    
    # Combine
    print(f"\n🔀 Combining rules...")
    print(f"  Existing: {len(existing_rules)}")
    print(f"  New: {len(new_rules)}")
    
    all_rules = existing_rules + new_rules
    print(f"  Combined: {len(all_rules)}")
    
    # Deduplicate if requested
    if deduplicate:
        all_rules = deduplicate_rules(all_rules)
    
    # Analyze
    analyze_rules(all_rules)
    
    # Save back to existing file
    metadata = {
        "total_rules": len(all_rules),
        "description": f"Appended rules from {new_file.name}",
        "deduplicated": deduplicate
    }
    
    save_rules(all_rules, existing_file, metadata)
    
    print("\n" + "=" * 60)
    print("✅ APPEND COMPLETE")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Merge validation rule JSON files with deduplication"
    )
    
    parser.add_argument(
        'input_files',
        nargs='+',
        type=Path,
        help='Input JSON files to merge'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        help='Output JSON file (required unless using --append-to)'
    )
    
    parser.add_argument(
        '--append-to',
        type=Path,
        help='Append to existing file instead of creating new one'
    )
    
    parser.add_argument(
        '--no-deduplicate',
        action='store_true',
        help='Skip deduplication step'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.output and not args.append_to:
        parser.error("Either --output or --append-to must be specified")
    
    if args.output and args.append_to:
        parser.error("Cannot specify both --output and --append-to")
    
    deduplicate = not args.no_deduplicate
    
    try:
        if args.append_to:
            # Append mode
            if len(args.input_files) != 1:
                parser.error("--append-to requires exactly one input file")
            append_to_existing(args.input_files[0], args.append_to, deduplicate)
        else:
            # Merge mode
            merge_files(args.input_files, args.output, deduplicate)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()