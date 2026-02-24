# classify_rule_tiers.py
"""
Rule Tier Classification - Progressive Refinement System

Classifies rules into tiers based on importance for progressive validation.
Enables fast validation (Tier 1) or comprehensive analysis (Tier 4).

Tiers:
- Tier 1 (Essential): ~50 critical rules, <100ms
- Tier 2 (Important): ~200 high-priority rules, <500ms
- Tier 3 (Detailed): ~1000 refinement rules, ~2s
- Tier 4 (Comprehensive): All rules, ~5s+

Usage:
    python classify_rule_tiers.py \
        --input consolidated_rules.json \
        --output tiered_rules.json \
        --tier1-size 50 \
        --tier2-size 200 \
        --tier3-size 1000
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import Counter
from tqdm import tqdm


class TierClassifier:
    """Classify rules into importance tiers"""
    
    def __init__(
        self,
        tier1_size: int = 50,
        tier2_size: int = 200,
        tier3_size: int = 1000
    ):
        self.tier1_size = tier1_size
        self.tier2_size = tier2_size
        self.tier3_size = tier3_size
        
        # Scoring weights
        self.weights = {
            'severity': {
                'critical': 100,
                'high': 50,
                'medium': 20,
                'low': 5
            },
            'stage': {
                'promise': 50,  # Promise checks are most important
                'timing': 30,
                'trigger': 20
            },
            'halt_on_failure': 75,  # Rules that halt are very important
            'impact_percentage': 1.0,  # Direct multiplier
            'check_order': -0.5,  # Lower check_order = higher priority
            'category': {
                'planetary_state': 40,
                'divisional_confirmation': 35,
                'strength_assessment': 30,
                'hierarchical_logic': 25,
                'lagna_specific': 20,
                'lunar_consideration': 15,
                'karmic_axis': 10,
                'general': 5
            }
        }
        
        self.stats = {
            'tier1': 0,
            'tier2': 0,
            'tier3': 0,
            'tier4': 0,
            'total': 0
        }
    
    def classify(self, rules: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Classify rules into tiers
        
        Args:
            rules: List of rules to classify
            
        Returns:
            Dictionary with tier assignments
        """
        
        print("\n🎯 RULE TIER CLASSIFICATION")
        print("=" * 60)
        
        self.stats['total'] = len(rules)
        print(f"📊 Classifying {len(rules)} rules into tiers")
        print(f"🎯 Tier 1 target: {self.tier1_size} rules")
        print(f"🎯 Tier 2 target: {self.tier2_size} rules")
        print(f"🎯 Tier 3 target: {self.tier3_size} rules")
        
        # Step 1: Calculate importance scores
        print("\n🔍 Step 1: Calculating importance scores...")
        scored_rules = self._score_rules(rules)
        
        # Step 2: Assign tiers
        print("\n🔍 Step 2: Assigning tiers...")
        tiered_rules = self._assign_tiers(scored_rules)
        
        # Step 3: Validate tier assignments
        print("\n🔍 Step 3: Validating tier assignments...")
        tiered_rules = self._validate_tiers(tiered_rules)
        
        # Calculate statistics
        self._calculate_stats(tiered_rules)
        
        print("\n" + "=" * 60)
        print("✅ TIER CLASSIFICATION COMPLETE")
        print(f"📊 Tier 1 (Essential):     {self.stats['tier1']} rules")
        print(f"📊 Tier 2 (Important):     {self.stats['tier2']} rules")
        print(f"📊 Tier 3 (Detailed):      {self.stats['tier3']} rules")
        print(f"📊 Tier 4 (Comprehensive): {self.stats['tier4']} rules")
        print("=" * 60)
        
        return tiered_rules
    
    def _score_rules(self, rules: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        """Calculate importance score for each rule"""
        
        scored = []
        
        for rule in tqdm(rules, desc="  Scoring", leave=False):
            score = 0.0
            
            # 1. Severity score
            severity = rule.get('severity', 'medium')
            if isinstance(severity, dict):
                severity = severity.get('value', 'medium')
            # Handle list - take first
            if isinstance(severity, list):
                severity = severity[0] if severity else 'medium'
            score += self.weights['severity'].get(str(severity), 20)
            
            # 2. Stage score
            stage = rule.get('prediction_stage', 'promise')
            if isinstance(stage, dict):
                stage = stage.get('value', 'promise')
            # Handle list - take first
            if isinstance(stage, list):
                stage = stage[0] if stage else 'promise'
            # Handle pipe-separated stages - use first/primary
            if '|' in str(stage):
                stage = str(stage).split('|')[0].strip()
            score += self.weights['stage'].get(str(stage), 20)
            
            # 3. Halt on failure bonus
            if rule.get('halt_on_failure'):
                score += self.weights['halt_on_failure']
            
            # 4. Impact percentage
            impact_pct = rule.get('impact_percentage', 50)
            if impact_pct:
                score += impact_pct * self.weights['impact_percentage']
            
            # 5. Check order (lower is better)
            check_order = rule.get('check_order', 100)
            if check_order:
                score += check_order * self.weights['check_order']
            
            # 6. Category score
            category = rule.get('category', 'general')
            if isinstance(category, dict):
                category = category.get('value', 'general')
            # Handle list - take first
            if isinstance(category, list):
                category = category[0] if category else 'general'
            # Handle pipe-separated categories - use first/primary
            if '|' in str(category):
                category = str(category).split('|')[0].strip()
            score += self.weights['category'].get(str(category), 10)
            
            # 7. Boost for parameterized rules (they represent many rules)
            if rule.get('is_parameterized'):
                original_count = rule.get('original_rule_count', 1)
                score += original_count * 2  # Boost by number of rules consolidated
            
            # 8. Confidence multiplier
            confidence = rule.get('extraction_confidence', 0.8)
            score *= confidence
            
            scored.append((rule, score))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored
    
    def _assign_tiers(self, scored_rules: List[Tuple[Dict[str, Any], float]]) -> Dict[str, List[Dict[str, Any]]]:
        """Assign rules to tiers based on scores"""
        
        tiers = {
            'tier1': [],
            'tier2': [],
            'tier3': [],
            'tier4': []
        }
        
        for idx, (rule, score) in enumerate(tqdm(scored_rules, desc="  Assigning", leave=False)):
            # Add tier metadata to rule
            rule_with_tier = rule.copy()
            rule_with_tier['importance_score'] = round(score, 2)
            
            if idx < self.tier1_size:
                rule_with_tier['tier'] = 1
                rule_with_tier['tier_name'] = 'Essential'
                tiers['tier1'].append(rule_with_tier)
            elif idx < self.tier1_size + self.tier2_size:
                rule_with_tier['tier'] = 2
                rule_with_tier['tier_name'] = 'Important'
                tiers['tier2'].append(rule_with_tier)
            elif idx < self.tier1_size + self.tier2_size + self.tier3_size:
                rule_with_tier['tier'] = 3
                rule_with_tier['tier_name'] = 'Detailed'
                tiers['tier3'].append(rule_with_tier)
            else:
                rule_with_tier['tier'] = 4
                rule_with_tier['tier_name'] = 'Comprehensive'
                tiers['tier4'].append(rule_with_tier)
        
        return tiers
    
    def _validate_tiers(self, tiered_rules: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Validate and adjust tier assignments.
        
        Only promotes rules that are BOTH critical severity AND halt_on_failure=True.
        Caps promotion so Tier 1 never exceeds tier1_size * 1.5 (prevents bloat
        when LLM over-marks rules as critical during extraction).
        """
        
        # How many slots remain in Tier 1 before hitting the cap
        max_tier1 = int(self.tier1_size * 1.5)
        slots_available = max(0, max_tier1 - len(tiered_rules['tier1']))
        
        candidates = []
        for source_tier in ('tier2', 'tier3', 'tier4'):
            for rule in tiered_rules[source_tier]:
                severity = rule.get('severity', '')
                if isinstance(severity, list):
                    severity = severity[0] if severity else ''
                if isinstance(severity, dict):
                    severity = severity.get('value', '')
                halt = rule.get('halt_on_failure', False)
                if str(severity).lower() == 'critical' and halt:
                    candidates.append((source_tier, rule))
        
        # Only promote up to available slots
        to_promote = candidates[:slots_available]
        skipped   = len(candidates) - len(to_promote)
        
        if to_promote:
            print(f"   ⬆️  Promoting {len(to_promote)} critical+halt rules to Tier 1")
            if skipped:
                print(f"   ⏭️  Skipped {skipped} additional critical rules (Tier 1 cap {max_tier1} reached)")
            
            promoted_rules = {id(r) for _, r in to_promote}
            for source_tier in ('tier2', 'tier3', 'tier4'):
                tiered_rules[source_tier] = [
                    r for r in tiered_rules[source_tier]
                    if id(r) not in promoted_rules
                ]
            for _, rule in to_promote:
                rule['tier'] = 1
                rule['tier_name'] = 'Essential'
                tiered_rules['tier1'].append(rule)
        else:
            print(f"   ✅ No critical+halt_on_failure rules need promotion")
        
        return tiered_rules
    
    def _calculate_stats(self, tiered_rules: Dict[str, List[Dict[str, Any]]]):
        """Calculate tier statistics"""
        
        self.stats['tier1'] = len(tiered_rules['tier1'])
        self.stats['tier2'] = len(tiered_rules['tier2'])
        self.stats['tier3'] = len(tiered_rules['tier3'])
        self.stats['tier4'] = len(tiered_rules['tier4'])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tier statistics"""
        return self.stats
    
    def analyze_tiers(self, tiered_rules: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Analyze composition of each tier"""
        
        analysis = {}
        
        for tier_name, tier_rules in tiered_rules.items():
            if not tier_rules:
                continue
            
            # Helper function to extract value from field
            def extract_value(field, default='unknown'):
                if isinstance(field, dict):
                    return field.get('value', default)
                elif isinstance(field, list):
                    return field[0] if field else default
                else:
                    return str(field) if field else default
            
            # Count by severity
            severities = Counter(
                extract_value(r.get('severity'), 'medium')
                for r in tier_rules
            )
            
            # Count by category
            categories = Counter()
            for r in tier_rules:
                cat = extract_value(r.get('category'), 'general')
                # Take first if pipe-separated
                cat = str(cat).split('|')[0].strip()
                categories[cat] += 1
            
            # Count by stage
            stages = Counter()
            for r in tier_rules:
                stage = extract_value(r.get('prediction_stage'), 'promise')
                # Take first if pipe-separated
                stage = str(stage).split('|')[0].strip()
                stages[stage] += 1
            
            # Count parameterized
            parameterized = sum(1 for r in tier_rules if r.get('is_parameterized'))
            
            # Average importance score
            avg_score = sum(r.get('importance_score', 0) for r in tier_rules) / len(tier_rules)
            
            analysis[tier_name] = {
                'count': len(tier_rules),
                'avg_importance_score': round(avg_score, 2),
                'by_severity': dict(severities),
                'by_category': dict(categories.most_common(5)),
                'by_stage': dict(stages),
                'parameterized_count': parameterized
            }
        
        return analysis


def main():
    parser = argparse.ArgumentParser(
        description="Classify rules into importance tiers"
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
        help='Output tiered rules file'
    )
    parser.add_argument(
        '--tier1-size',
        type=int,
        default=50,
        help='Target size for Tier 1 (Essential)'
    )
    parser.add_argument(
        '--tier2-size',
        type=int,
        default=200,
        help='Target size for Tier 2 (Important)'
    )
    parser.add_argument(
        '--tier3-size',
        type=int,
        default=1000,
        help='Target size for Tier 3 (Detailed)'
    )
    parser.add_argument(
        '--analysis-file',
        type=str,
        help='Output file for tier analysis'
    )
    
    args = parser.parse_args()
    
    # Load rules
    print(f"\n📖 Loading rules from {args.input}...")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rules = data.get('rules', data if isinstance(data, list) else [])
    metadata = data.get('metadata', {})
    
    print(f"   ✅ Loaded {len(rules)} rules")
    
    # Classify
    classifier = TierClassifier(
        tier1_size=args.tier1_size,
        tier2_size=args.tier2_size,
        tier3_size=args.tier3_size
    )
    
    tiered_rules = classifier.classify(rules)
    
    # Analyze tiers
    print("\n📊 Analyzing tier composition...")
    analysis = classifier.analyze_tiers(tiered_rules)
    
    # Prepare output
    output_data = {
        'metadata': {
            **metadata,
            'tiered': True,
            'tier_sizes': {
                'tier1_target': args.tier1_size,
                'tier2_target': args.tier2_size,
                'tier3_target': args.tier3_size,
                'tier1_actual': classifier.stats['tier1'],
                'tier2_actual': classifier.stats['tier2'],
                'tier3_actual': classifier.stats['tier3'],
                'tier4_actual': classifier.stats['tier4']
            }
        },
        'tiers': tiered_rules,
        'all_rules': (
            tiered_rules['tier1'] +
            tiered_rules['tier2'] +
            tiered_rules['tier3'] +
            tiered_rules['tier4']
        ),
        'analysis': analysis,
        'statistics': classifier.get_statistics()
    }
    
    # Save tiered rules
    print(f"\n💾 Saving tiered rules to {args.output}...")
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Saved tiered structure")
    
    # Save analysis if requested
    if args.analysis_file:
        with open(args.analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        print(f"   ✅ Analysis saved to {args.analysis_file}")
    
    # Print detailed summary
    print("\n" + "=" * 60)
    print("📊 TIER ANALYSIS")
    print("=" * 60)
    
    for tier_name in ['tier1', 'tier2', 'tier3', 'tier4']:
        if tier_name in analysis:
            tier_data = analysis[tier_name]
            tier_display = {
                'tier1': 'Tier 1 (Essential)',
                'tier2': 'Tier 2 (Important)',
                'tier3': 'Tier 3 (Detailed)',
                'tier4': 'Tier 4 (Comprehensive)'
            }
            
            print(f"\n{tier_display[tier_name]}:")
            print(f"  Count:              {tier_data['count']}")
            print(f"  Avg Score:          {tier_data['avg_importance_score']}")
            print(f"  Parameterized:      {tier_data['parameterized_count']}")
            print(f"  By Severity:        {tier_data['by_severity']}")
            print(f"  Top Categories:     {tier_data['by_category']}")
            print(f"  By Stage:           {tier_data['by_stage']}")
    
    print("\n" + "=" * 60)
    print("💡 USAGE RECOMMENDATIONS:")
    print("=" * 60)
    print(f"Tier 1: Quick validation (~{classifier.stats['tier1']} rules, <100ms)")
    print(f"Tier 2: Standard validation (~{classifier.stats['tier2']} rules, <500ms)")
    print(f"Tier 3: Detailed analysis (~{classifier.stats['tier3']} rules, ~2s)")
    print(f"Tier 4: Comprehensive report (~{classifier.stats['tier4']} rules, ~5s+)")
    print("=" * 60)


if __name__ == "__main__":
    main()