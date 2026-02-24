# optimize_rules.py
"""
Master Rule Optimization Script

Runs all three optimization steps in sequence:
1. Consolidation (10K -> 3K rules)
2. Indexing (fast lookup tables)
3. Tier Classification (progressive validation)

Usage:
    python optimize_rules.py \
        --input vedic_validation_rules.json \
        --output-dir ./optimized \
        --tier1-size 50 \
        --tier2-size 200

    # With custom settings
    python optimize_rules.py \
        --input vedic_validation_rules.json \
        --output-dir ./optimized \
        --min-confidence 0.80 \
        --tier1-size 75 \
        --tier2-size 250 \
        --tier3-size 1200
"""

import json
import argparse
from pathlib import Path
import sys
import subprocess
from datetime import datetime


def run_step(step_name: str, command: list) -> bool:
    """Run a single optimization step"""
    
    print("\n" + "=" * 70)
    print(f"[LAUNCH] STEP: {step_name}")
    print("=" * 70)
    print(f"Command: {' '.join(command)}\n")
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=False,
            text=True
        )
        
        print(f"\n[OK] {step_name} completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n[FAIL] {step_name} failed!")
        print(f"Error: {e}")
        return False
    except FileNotFoundError:
        print(f"\n[FAIL] Script not found!")
        print(f"Make sure all scripts are in the same directory.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Master script for rule optimization pipeline"
    )
    
    # Input/Output
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input validation rules JSON file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./optimized',
        help='Output directory for optimized files'
    )
    
    # Consolidation options
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.75,
        help='Minimum extraction confidence (default: 0.75)'
    )
    
    # Tier options
    parser.add_argument(
        '--tier1-size',
        type=int,
        default=300,  # Increased for 15+ books
        help='Target size for Tier 1 (Essential)'
    )
    parser.add_argument(
        '--tier2-size',
        type=int,
        default=800,  # Increased for 15+ books
        help='Target size for Tier 2 (Important)'
    )
    parser.add_argument(
        '--tier3-size',
        type=int,
        default=3000,  # Increased for 15+ books
        help='Target size for Tier 3 (Detailed)'
    )
    
    # Advanced options
    parser.add_argument(
        '--skip-consolidation',
        action='store_true',
        help='Skip consolidation step (use if already consolidated)'
    )
    parser.add_argument(
        '--skip-indexing',
        action='store_true',
        help='Skip indexing step'
    )
    parser.add_argument(
        '--skip-tiering',
        action='store_true',
        help='Skip tier classification step'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define file paths
    consolidated_file = output_dir / 'consolidated_rules.json'
    indexed_file = output_dir / 'indexed_rules.json'
    tiered_file = output_dir / 'tiered_rules.json'
    
    stats_dir = output_dir / 'stats'
    stats_dir.mkdir(exist_ok=True)
    
    consolidation_stats = stats_dir / 'consolidation_stats.json'
    indexing_stats = stats_dir / 'indexing_stats.json'
    tier_analysis = stats_dir / 'tier_analysis.json'
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Print header
    print("\n" + "=" * 70)
    print("🎯 RULE OPTIMIZATION MASTER PIPELINE")
    print("=" * 70)
    print(f"📥 Input:           {args.input}")
    print(f"📤 Output dir:      {output_dir}")
    print(f"[STATS] Min confidence:  {args.min_confidence}")
    print(f"🎯 Tier 1 target:   {args.tier1_size} rules (default: 300 for 15+ books)")
    print(f"🎯 Tier 2 target:   {args.tier2_size} rules (default: 800 for 15+ books)")
    print(f"🎯 Tier 3 target:   {args.tier3_size} rules (default: 3000 for 15+ books)")
    print("=" * 70)
    
    # Track results
    results = {}
    start_time = datetime.now()
    
    # Step 1: Consolidation
    if not args.skip_consolidation:
        step1_cmd = [
            sys.executable,
            str(script_dir / 'consolidate_validation_rules.py'),
            '--input', args.input,
            '--output', str(consolidated_file),
            '--min-confidence', str(args.min_confidence),
            '--stats-file', str(consolidation_stats)
        ]
        
        results['consolidation'] = run_step("CONSOLIDATION", step1_cmd)
        
        if not results['consolidation']:
            print("\n[FAIL] Pipeline failed at consolidation step!")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping consolidation (using existing file)")
        results['consolidation'] = 'skipped'
    
    # Step 2: Indexing
    if not args.skip_indexing:
        step2_cmd = [
            sys.executable,
            str(script_dir / 'build_rule_indices.py'),
            '--input', str(consolidated_file),
            '--output', str(indexed_file),
            '--index-by', 'query_type,stage,category,severity',
            '--stats-file', str(indexing_stats)
        ]
        
        results['indexing'] = run_step("INDEXING", step2_cmd)
        
        if not results['indexing']:
            print("\n[FAIL] Pipeline failed at indexing step!")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping indexing")
        results['indexing'] = 'skipped'
    
    # Step 3: Tier Classification
    if not args.skip_tiering:
        step3_cmd = [
            sys.executable,
            str(script_dir / 'classify_rule_tiers.py'),
            '--input', str(consolidated_file),
            '--output', str(tiered_file),
            '--tier1-size', str(args.tier1_size),
            '--tier2-size', str(args.tier2_size),
            '--tier3-size', str(args.tier3_size),
            '--analysis-file', str(tier_analysis)
        ]
        
        results['tiering'] = run_step("TIER CLASSIFICATION", step3_cmd)
        
        if not results['tiering']:
            print("\n[FAIL] Pipeline failed at tier classification step!")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping tier classification")
        results['tiering'] = 'skipped'
    
    # Calculate total time
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Print final summary
    print("\n" + "=" * 70)
    print("[OK] OPTIMIZATION PIPELINE COMPLETE!")
    print("=" * 70)
    print(f"⏱️  Total time: {duration}")
    print(f"\n📁 Output files:")
    print(f"   • {consolidated_file}")
    print(f"   • {indexed_file}")
    print(f"   • {tiered_file}")
    print(f"\n[STATS] Statistics:")
    print(f"   • {consolidation_stats}")
    print(f"   • {indexing_stats}")
    print(f"   • {tier_analysis}")
    
    # Load and print quick stats
    if consolidated_file.exists():
        with open(consolidated_file, 'r', encoding='utf-8') as f:
            cons_data = json.load(f)
        
        original = cons_data['metadata'].get('original_count', 0)
        consolidated = cons_data['metadata'].get('consolidated_count', 0)
        reduction = cons_data['metadata'].get('reduction_percentage', 0)
        
        print(f"\n📉 Consolidation:")
        print(f"   Original:      {original:,} rules")
        print(f"   Consolidated:  {consolidated:,} rules")
        print(f"   Reduction:     {reduction:.1f}%")
    
    if tiered_file.exists():
        with open(tiered_file, 'r', encoding='utf-8') as f:
            tier_data = json.load(f)
        
        tier_sizes = tier_data['metadata'].get('tier_sizes', {})
        
        print(f"\n🎯 Tier Distribution:")
        print(f"   Tier 1 (Essential):     {tier_sizes.get('tier1_actual', 0)} rules")
        print(f"   Tier 2 (Important):     {tier_sizes.get('tier2_actual', 0)} rules")
        print(f"   Tier 3 (Detailed):      {tier_sizes.get('tier3_actual', 0)} rules")
        print(f"   Tier 4 (Comprehensive): {tier_sizes.get('tier4_actual', 0)} rules")
    
    print("\n[IDEA] Next steps:")
    print("   1. Review statistics in stats/ directory")
    print("   2. Test performance with sample chart")
    print("   3. Integrate indexed_rules.json into your validation engine")
    print("   4. Use tiered validation for different use cases")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()