# build_rule_indices.py
"""
Rule Indexing System - Fast Multi-Dimensional Lookup

Builds composite indices for ultra-fast rule lookup.
Reduces lookup time from O(n) to O(1).

Features:
- Multi-dimensional indexing
- Composite index generation
- Query optimization
- Index statistics
- Serialization support

Usage:
    python build_rule_indices.py \
        --input consolidated_rules.json \
        --output indexed_rules.json \
        --index-by query_type,stage,category,severity
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import defaultdict
from tqdm import tqdm
import itertools


class RuleIndexBuilder:
    """Build multi-dimensional indices for fast rule lookup"""
    
    def __init__(self):
        self.indices = {
            'by_query_type': defaultdict(list),
            'by_stage': defaultdict(list),
            'by_category': defaultdict(list),
            'by_severity': defaultdict(list),
            'composite': defaultdict(list),
            'by_parameter_type': defaultdict(list)
        }
        
        self.stats = {
            'total_rules': 0,
            'indexed_dimensions': 0,
            'composite_indices': 0,
            'index_coverage': {}
        }
    
    def build_indices(
        self,
        rules: List[Dict[str, Any]],
        dimensions: List[str]
    ) -> Dict[str, Any]:
        """
        Build all indices
        
        Args:
            rules: List of rules to index
            dimensions: Dimensions to index by
            
        Returns:
            Complete index structure
        """
        
        print("\n🔨 BUILDING RULE INDICES")
        print("=" * 60)
        
        self.stats['total_rules'] = len(rules)
        print(f"[STATS] Indexing {len(rules)} rules")
        print(f"📐 Dimensions: {', '.join(dimensions)}")
        
        # Build single-dimension indices
        print("\n[SEARCH] Building single-dimension indices...")
        if 'query_type' in dimensions:
            self._build_query_type_index(rules)
        if 'stage' in dimensions:
            self._build_stage_index(rules)
        if 'category' in dimensions:
            self._build_category_index(rules)
        if 'severity' in dimensions:
            self._build_severity_index(rules)
        
        # Build parameter type index
        print("\n[SEARCH] Building parameter type index...")
        self._build_parameter_type_index(rules)
        
        # Build composite indices
        print("\n[SEARCH] Building composite indices...")
        self._build_composite_indices(rules, dimensions)
        
        # Calculate statistics
        self._calculate_stats()
        
        print("\n" + "=" * 60)
        print("[OK] INDEX BUILDING COMPLETE")
        print(f"[STATS] Total indices created: {sum(len(idx) for idx in self.indices.values())}")
        print("=" * 60)
        
        return self.indices
    
    def _build_query_type_index(self, rules: List[Dict[str, Any]]):
        """Index by query type (marriage, career, etc.)"""
        
        for rule in tqdm(rules, desc="  Query type", leave=False):
            query_types = rule.get('applies_to_queries', [])
            
            # Handle string or list
            if isinstance(query_types, str):
                query_types = [query_types]
            
            for qt in query_types:
                # Extract value if it's a dict
                if isinstance(qt, dict):
                    qt = qt.get('value', qt)
                
                self.indices['by_query_type'][qt].append(rule['rule_id'])
                
                # Also index under 'all' if applicable
                if qt == 'all':
                    for common_qt in ['marriage', 'career', 'finance', 'health']:
                        self.indices['by_query_type'][common_qt].append(rule['rule_id'])
    
    def _build_stage_index(self, rules: List[Dict[str, Any]]):
        """Index by prediction stage"""
        
        for rule in tqdm(rules, desc="  Stage", leave=False):
            stage = rule.get('prediction_stage', 'promise')
            
            # Extract value if it's a dict
            if isinstance(stage, dict):
                stage = stage.get('value', stage)
            
            # Handle list
            if isinstance(stage, list):
                stages = stage
            # Handle pipe-separated stages
            elif isinstance(stage, str) and '|' in stage:
                stages = stage.split('|')
            else:
                stages = [stage]
            
            for s in stages:
                self.indices['by_stage'][str(s).strip()].append(rule['rule_id'])
    
    def _build_category_index(self, rules: List[Dict[str, Any]]):
        """Index by validation category"""
        
        for rule in tqdm(rules, desc="  Category", leave=False):
            category = rule.get('category', 'general')
            
            # Extract value if it's a dict
            if isinstance(category, dict):
                category = category.get('value', category)
            
            # Handle list
            if isinstance(category, list):
                categories = category
            # Handle pipe-separated categories
            elif isinstance(category, str) and '|' in category:
                categories = category.split('|')
            else:
                categories = [category]
            
            for c in categories:
                self.indices['by_category'][str(c).strip()].append(rule['rule_id'])
    
    def _build_severity_index(self, rules: List[Dict[str, Any]]):
        """Index by severity level"""
        
        for rule in tqdm(rules, desc="  Severity", leave=False):
            severity = rule.get('severity', 'medium')
            
            # Extract value if it's a dict
            if isinstance(severity, dict):
                severity = severity.get('value', severity)
            
            # Handle list (take first)
            if isinstance(severity, list):
                severity = severity[0] if severity else 'medium'
            
            self.indices['by_severity'][str(severity)].append(rule['rule_id'])
    
    def _build_parameter_type_index(self, rules: List[Dict[str, Any]]):
        """Index parameterized rules by parameter type"""
        
        for rule in tqdm(rules, desc="  Parameter type", leave=False):
            if rule.get('is_parameterized'):
                param_type = rule.get('parameter_type', 'unknown')
                self.indices['by_parameter_type'][param_type].append(rule['rule_id'])
    
    def _build_composite_indices(self, rules: List[Dict[str, Any]], dimensions: List[str]):
        """Build composite indices for common query patterns"""
        
        # Define common composite patterns
        composite_patterns = [
            ['query_type', 'stage'],
            ['query_type', 'category'],
            ['stage', 'category'],
            ['query_type', 'stage', 'category'],
            ['query_type', 'stage', 'severity']
        ]
        
        # Filter patterns by available dimensions
        valid_patterns = [
            p for p in composite_patterns
            if all(d in dimensions for d in p)
        ]
        
        print(f"   Building {len(valid_patterns)} composite index patterns...")
        
        for rule in tqdm(rules, desc="  Composite", leave=False):
            rule_id = rule['rule_id']
            
            # Extract values
            values = {}
            
            # Query type
            query_types = rule.get('applies_to_queries', [])
            if isinstance(query_types, str):
                query_types = [query_types]
            values['query_type'] = [
                qt.get('value', qt) if isinstance(qt, dict) else qt
                for qt in query_types
            ]
            
            # Stage
            stage = rule.get('prediction_stage', 'promise')
            if isinstance(stage, dict):
                stage = stage.get('value', stage)
            if isinstance(stage, list):
                values['stage'] = [str(s).strip() for s in stage]
            elif '|' in str(stage):
                values['stage'] = [s.strip() for s in str(stage).split('|')]
            else:
                values['stage'] = [str(stage)]
            
            # Category
            category = rule.get('category', 'general')
            if isinstance(category, dict):
                category = category.get('value', category)
            if isinstance(category, list):
                values['category'] = [str(c).strip() for c in category]
            elif '|' in str(category):
                values['category'] = [c.strip() for c in str(category).split('|')]
            else:
                values['category'] = [str(category)]
            
            # Severity
            severity = rule.get('severity', 'medium')
            if isinstance(severity, dict):
                severity = severity.get('value', severity)
            if isinstance(severity, list):
                values['severity'] = [str(severity[0]) if severity else 'medium']
            else:
                values['severity'] = [str(severity)]
            
            # Build composite keys
            for pattern in valid_patterns:
                # Get all combinations for this pattern
                value_lists = [values[dim] for dim in pattern]
                
                for combo in itertools.product(*value_lists):
                    key = '_'.join(combo)
                    self.indices['composite'][key].append(rule_id)
        
        self.stats['composite_indices'] = len(self.indices['composite'])
    
    def _calculate_stats(self):
        """Calculate index statistics"""
        
        self.stats['indexed_dimensions'] = sum(1 for idx in self.indices.values() if idx)
        
        # Coverage statistics
        for idx_name, idx_data in self.indices.items():
            if idx_data:
                self.stats['index_coverage'][idx_name] = {
                    'unique_keys': len(idx_data),
                    'total_entries': sum(len(rules) for rules in idx_data.values()),
                    'avg_rules_per_key': sum(len(rules) for rules in idx_data.values()) / len(idx_data) if idx_data else 0
                }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics"""
        return self.stats
    
    def create_lookup_guide(self) -> Dict[str, Any]:
        """Create a guide for using the indices"""
        
        return {
            'usage_examples': {
                'marriage_promise': {
                    'description': 'Get all rules for marriage at promise stage',
                    'index': 'composite',
                    'key': 'marriage_promise'
                },
                'career_timing_critical': {
                    'description': 'Get critical career rules at timing stage',
                    'index': 'composite',
                    'key': 'career_timing_critical'
                },
                'all_critical': {
                    'description': 'Get all critical rules',
                    'index': 'by_severity',
                    'key': 'critical'
                },
                'parameterized_sign_rules': {
                    'description': 'Get all sign-parameterized rules',
                    'index': 'by_parameter_type',
                    'key': 'sign'
                }
            },
            'available_indices': list(self.indices.keys()),
            'composite_patterns': list(self.indices['composite'].keys())[:20]  # Sample
        }


def main():
    parser = argparse.ArgumentParser(
        description="Build fast indices for validation rules"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input consolidated rules file'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output indexed rules file'
    )
    parser.add_argument(
        '--index-by',
        type=str,
        default='query_type,stage,category,severity',
        help='Comma-separated dimensions to index by'
    )
    parser.add_argument(
        '--stats-file',
        type=str,
        help='Output file for statistics'
    )
    
    args = parser.parse_args()
    
    # Parse dimensions
    dimensions = [d.strip() for d in args.index_by.split(',')]
    
    # Load rules
    print(f"\n📖 Loading rules from {args.input}...")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract rules and metadata
    rules = data.get('rules', data if isinstance(data, list) else [])
    metadata = data.get('metadata', {})
    
    print(f"   [OK] Loaded {len(rules)} rules")
    
    # Create lookup map (rule_id -> full rule)
    rule_map = {rule['rule_id']: rule for rule in rules}
    
    # Build indices
    builder = RuleIndexBuilder()
    indices = builder.build_indices(rules, dimensions)
    
    # Create lookup guide
    lookup_guide = builder.create_lookup_guide()
    
    # Prepare output
    output_data = {
        'metadata': {
            **metadata,
            'indexed': True,
            'index_dimensions': dimensions,
            'total_indices': builder.stats['indexed_dimensions'],
            'composite_indices': builder.stats['composite_indices']
        },
        'indices': {
            key: {k: list(v) for k, v in value.items()}  # Convert defaultdict to regular dict
            for key, value in indices.items()
        },
        'rule_map': rule_map,
        'lookup_guide': lookup_guide,
        'statistics': builder.get_statistics()
    }
    
    # Save indexed rules
    print(f"\n[SAVE] Saving indexed rules to {args.output}...")
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"   [OK] Saved indexed structure")
    
    # Save statistics if requested
    if args.stats_file:
        with open(args.stats_file, 'w', encoding='utf-8') as f:
            json.dump(builder.get_statistics(), f, indent=2)
        print(f"   [OK] Statistics saved to {args.stats_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("[STATS] INDEX SUMMARY")
    print("=" * 60)
    print(f"Total rules:           {len(rules):,}")
    print(f"Index dimensions:      {len(dimensions)}")
    print(f"Composite indices:     {builder.stats['composite_indices']:,}")
    print(f"\nIndex Coverage:")
    for idx_name, coverage in builder.stats['index_coverage'].items():
        print(f"  {idx_name}:")
        print(f"    Unique keys:       {coverage['unique_keys']}")
        print(f"    Avg rules/key:     {coverage['avg_rules_per_key']:.1f}")
    print("=" * 60)
    
    # Print usage examples
    print("\n[IDEA] USAGE EXAMPLES:")
    print("-" * 60)
    for example_name, example_data in lookup_guide['usage_examples'].items():
        print(f"\n{example_name}:")
        print(f"  {example_data['description']}")
        print(f"  Index: indices['{example_data['index']}']['{example_data['key']}']")


if __name__ == "__main__":
    main()