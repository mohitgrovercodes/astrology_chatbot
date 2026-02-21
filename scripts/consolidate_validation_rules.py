# consolidate_validation_rules.py
"""
Rule Consolidation Script - Advanced Version

Consolidates repetitive validation rules into parameterized versions.
Reduces 10,000+ rules to ~3,000 high-quality rules.

Features:
- Pattern detection (sign-specific, planet-specific, house-specific)
- Automatic parameterization
- Quality filtering
- Deduplication
- Statistical analysis

Usage:
    python consolidate_validation_rules.py \
        --input vedic_validation_rules.json \
        --output consolidated_rules.json \
        --min-confidence 0.75 \
        --strategy aggressive
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict, Counter
import re
from difflib import SequenceMatcher
from tqdm import tqdm


class RuleConsolidator:
    """Advanced rule consolidation with pattern detection"""
    
    def __init__(self, min_confidence: float = 0.75):
        self.min_confidence = min_confidence
        
        # Pattern definitions
        self.signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        self.planets = [
            "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
            "Rahu", "Ketu", "Uranus", "Neptune", "Pluto"
        ]
        self.houses = [
            "1st", "2nd", "3rd", "4th", "5th", "6th",
            "7th", "8th", "9th", "10th", "11th", "12th"
        ]
        
        # Consolidation patterns
        self.patterns = {
            'sign_specific': [],
            'planet_specific': [],
            'house_specific': [],
            'planet_sign': [],
            'planet_house': [],
            'nakshatra_specific': [],
            'dasha_specific': []
        }
        
        self.stats = {
            'original_count': 0,
            'after_quality_filter': 0,
            'after_dedup': 0,
            'after_consolidation': 0,
            'consolidation_groups': 0
        }
    
    def consolidate(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Main consolidation pipeline
        
        Args:
            rules: List of raw rules
            
        Returns:
            Consolidated rules list
        """
        
        print("\n🔄 RULE CONSOLIDATION PIPELINE")
        print("=" * 60)
        
        self.stats['original_count'] = len(rules)
        print(f"📊 Input: {len(rules)} rules")
        
        # Step 1: Quality filtering
        print("\n🔍 Step 1: Quality Filtering...")
        rules = self._filter_by_quality(rules)
        self.stats['after_quality_filter'] = len(rules)
        print(f"   ✅ Kept {len(rules)} high-quality rules")
        
        # Step 2: Exact deduplication
        print("\n🔍 Step 2: Exact Deduplication...")
        rules = self._deduplicate_exact(rules)
        self.stats['after_dedup'] = len(rules)
        print(f"   ✅ Removed duplicates, {len(rules)} unique rules")
        
        # Step 3: Pattern detection
        print("\n🔍 Step 3: Pattern Detection...")
        pattern_groups = self._detect_patterns(rules)
        print(f"   ✅ Found {len(pattern_groups)} consolidation groups")
        
        # Step 4: Consolidate patterns
        print("\n🔍 Step 4: Consolidating Patterns...")
        consolidated = self._consolidate_patterns(pattern_groups)
        
        # Step 5: Add remaining non-pattern rules
        print("\n🔍 Step 5: Adding Non-Pattern Rules...")
        final_rules = self._merge_with_remaining(consolidated, rules, pattern_groups)
        
        self.stats['after_consolidation'] = len(final_rules)
        self.stats['consolidation_groups'] = len(pattern_groups)
        
        print("\n" + "=" * 60)
        print("✅ CONSOLIDATION COMPLETE")
        print(f"📊 Final count: {len(final_rules)} rules")
        print(f"📉 Reduction: {self.stats['original_count'] - len(final_rules)} rules ({(1 - len(final_rules)/self.stats['original_count'])*100:.1f}%)")
        print("=" * 60)
        
        return final_rules
    
    def _filter_by_quality(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter rules by quality criteria"""
        
        filtered = []
        
        for rule in tqdm(rules, desc="  Filtering", leave=False):
            # Check confidence
            confidence = rule.get('extraction_confidence', 1.0)
            if confidence < self.min_confidence:
                continue
            
            # Check if rule has substance
            impact = rule.get('impact_if_violated', '')
            if not impact or impact in ['Unknown impact', 'Impact not specified']:
                continue
            
            # Check if rule has logic
            check_logic = rule.get('check_logic', {})
            if not check_logic or not check_logic.get('condition'):
                continue
            
            filtered.append(rule)
        
        return filtered
    
    def _deduplicate_exact(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove exact duplicates"""
        
        seen = {}
        unique = []
        
        for rule in tqdm(rules, desc="  Deduplicating", leave=False):
            # Create key from rule_name + category
            # Handle category as string or list
            category = rule.get('category', 'general')
            if isinstance(category, list):
                category = '|'.join(sorted(category))  # Make it hashable
            elif isinstance(category, dict):
                category = category.get('value', 'general')
            
            key = (
                rule.get('rule_name', '').lower().strip(),
                str(category)  # Ensure it's a string
            )
            
            if key not in seen:
                seen[key] = rule
                unique.append(rule)
            else:
                # Keep the one with higher confidence
                existing_conf = seen[key].get('extraction_confidence', 0.0)
                new_conf = rule.get('extraction_confidence', 0.0)
                if new_conf > existing_conf:
                    # Replace with higher confidence version
                    idx = unique.index(seen[key])
                    unique[idx] = rule
                    seen[key] = rule
        
        return unique
    
    def _detect_patterns(self, rules: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Detect consolidation patterns"""
        
        groups = defaultdict(list)
        
        for rule in tqdm(rules, desc="  Detecting patterns", leave=False):
            rule_name = rule.get('rule_name', '')
            
            # Detect sign-specific patterns
            if self._is_sign_specific(rule_name):
                base_name = self._extract_base_name(rule_name, self.signs)
                groups[f"sign:{base_name}"].append(rule)
            
            # Detect planet-specific patterns
            elif self._is_planet_specific(rule_name):
                base_name = self._extract_base_name(rule_name, self.planets)
                groups[f"planet:{base_name}"].append(rule)
            
            # Detect house-specific patterns
            elif self._is_house_specific(rule_name):
                base_name = self._extract_base_name(rule_name, self.houses)
                groups[f"house:{base_name}"].append(rule)
            
            # Detect planet-in-sign patterns
            elif self._is_planet_in_sign(rule_name):
                planet, sign = self._extract_planet_sign(rule_name)
                if planet and sign:
                    groups[f"planet_sign:{planet}"].append(rule)
            
            # Detect planet-in-house patterns
            elif self._is_planet_in_house(rule_name):
                planet, house = self._extract_planet_house(rule_name)
                if planet and house:
                    groups[f"planet_house:{planet}"].append(rule)
        
        # Filter groups (only keep groups with 3+ rules)
        filtered_groups = {
            k: v for k, v in groups.items() if len(v) >= 3
        }
        
        return filtered_groups
    
    def _is_sign_specific(self, rule_name: str) -> bool:
        """Check if rule is sign-specific"""
        # Pattern: "Something in Aries", "Aries Something"
        for sign in self.signs:
            if sign.lower() in rule_name.lower():
                # Check if other signs are NOT present
                other_signs = [s for s in self.signs if s != sign]
                if not any(s.lower() in rule_name.lower() for s in other_signs):
                    return True
        return False
    
    def _is_planet_specific(self, rule_name: str) -> bool:
        """Check if rule is planet-specific"""
        for planet in self.planets:
            if planet.lower() in rule_name.lower():
                other_planets = [p for p in self.planets if p != planet]
                if not any(p.lower() in rule_name.lower() for p in other_planets):
                    return True
        return False
    
    def _is_house_specific(self, rule_name: str) -> bool:
        """Check if rule is house-specific"""
        for house in self.houses:
            if house in rule_name:
                other_houses = [h for h in self.houses if h != house]
                if not any(h in rule_name for h in other_houses):
                    return True
        return False
    
    def _is_planet_in_sign(self, rule_name: str) -> bool:
        """Check if pattern is planet-in-sign"""
        has_planet = any(p.lower() in rule_name.lower() for p in self.planets)
        has_sign = any(s.lower() in rule_name.lower() for s in self.signs)
        return has_planet and has_sign and " in " in rule_name.lower()
    
    def _is_planet_in_house(self, rule_name: str) -> bool:
        """Check if pattern is planet-in-house"""
        has_planet = any(p.lower() in rule_name.lower() for p in self.planets)
        has_house = any(h in rule_name for h in self.houses)
        return has_planet and has_house and " in " in rule_name.lower()
    
    def _extract_base_name(self, rule_name: str, variants: List[str]) -> str:
        """Extract base name by removing variant"""
        for variant in variants:
            rule_name = re.sub(rf'\b{variant}\b', '', rule_name, flags=re.IGNORECASE)
        return rule_name.strip()
    
    def _extract_planet_sign(self, rule_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract planet and sign from rule name"""
        planet = None
        sign = None
        
        for p in self.planets:
            if p.lower() in rule_name.lower():
                planet = p
                break
        
        for s in self.signs:
            if s.lower() in rule_name.lower():
                sign = s
                break
        
        return planet, sign
    
    def _extract_planet_house(self, rule_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract planet and house from rule name"""
        planet = None
        house = None
        
        for p in self.planets:
            if p.lower() in rule_name.lower():
                planet = p
                break
        
        for h in self.houses:
            if h in rule_name:
                house = h
                break
        
        return planet, house
    
    def _consolidate_patterns(self, pattern_groups: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Consolidate pattern groups into parameterized rules"""
        
        consolidated = []
        
        for group_key, group_rules in tqdm(pattern_groups.items(), desc="  Consolidating"):
            if not group_rules:
                continue
            
            # Determine pattern type
            pattern_type = group_key.split(':')[0]
            
            if pattern_type == 'sign':
                consolidated_rule = self._consolidate_sign_specific(group_rules)
            elif pattern_type == 'planet':
                consolidated_rule = self._consolidate_planet_specific(group_rules)
            elif pattern_type == 'house':
                consolidated_rule = self._consolidate_house_specific(group_rules)
            elif pattern_type == 'planet_sign':
                consolidated_rule = self._consolidate_planet_in_sign(group_rules)
            elif pattern_type == 'planet_house':
                consolidated_rule = self._consolidate_planet_in_house(group_rules)
            else:
                continue
            
            if consolidated_rule:
                consolidated.append(consolidated_rule)
        
        return consolidated
    
    def _consolidate_sign_specific(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate sign-specific rules"""
        
        # Use first rule as template
        template = rules[0].copy()
        
        # Extract sign-specific data
        sign_data = {}
        for rule in rules:
            rule_name = rule.get('rule_name', '')
            for sign in self.signs:
                if sign.lower() in rule_name.lower():
                    sign_data[sign] = {
                        'impact': rule.get('impact_if_violated', ''),
                        'threshold': rule.get('check_logic', {}).get('threshold'),
                        'comparison': rule.get('check_logic', {}).get('comparison'),
                        'calculation': rule.get('check_logic', {}).get('calculation', '')
                    }
                    break
        
        # Create consolidated rule
        base_name = self._extract_base_name(template['rule_name'], self.signs)
        
        template['rule_name'] = f"{base_name} (Parameterized by Sign)"
        template['is_parameterized'] = True
        template['parameter_type'] = 'sign'
        template['sign_parameters'] = sign_data
        template['original_rule_count'] = len(rules)
        
        return template
    
    def _consolidate_planet_specific(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate planet-specific rules"""
        
        template = rules[0].copy()
        
        planet_data = {}
        for rule in rules:
            rule_name = rule.get('rule_name', '')
            for planet in self.planets:
                if planet.lower() in rule_name.lower():
                    planet_data[planet] = {
                        'impact': rule.get('impact_if_violated', ''),
                        'threshold': rule.get('check_logic', {}).get('threshold'),
                        'comparison': rule.get('check_logic', {}).get('comparison'),
                        'calculation': rule.get('check_logic', {}).get('calculation', '')
                    }
                    break
        
        base_name = self._extract_base_name(template['rule_name'], self.planets)
        
        template['rule_name'] = f"{base_name} (Parameterized by Planet)"
        template['is_parameterized'] = True
        template['parameter_type'] = 'planet'
        template['planet_parameters'] = planet_data
        template['original_rule_count'] = len(rules)
        
        return template
    
    def _consolidate_house_specific(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate house-specific rules"""
        
        template = rules[0].copy()
        
        house_data = {}
        for rule in rules:
            rule_name = rule.get('rule_name', '')
            for house in self.houses:
                if house in rule_name:
                    house_data[house] = {
                        'impact': rule.get('impact_if_violated', ''),
                        'threshold': rule.get('check_logic', {}).get('threshold'),
                        'comparison': rule.get('check_logic', {}).get('comparison'),
                        'calculation': rule.get('check_logic', {}).get('calculation', '')
                    }
                    break
        
        base_name = self._extract_base_name(template['rule_name'], self.houses)
        
        template['rule_name'] = f"{base_name} (Parameterized by House)"
        template['is_parameterized'] = True
        template['parameter_type'] = 'house'
        template['house_parameters'] = house_data
        template['original_rule_count'] = len(rules)
        
        return template
    
    def _consolidate_planet_in_sign(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate planet-in-sign rules"""
        
        template = rules[0].copy()
        
        # Group by sign
        sign_data = defaultdict(dict)
        planet_name = None
        
        for rule in rules:
            planet, sign = self._extract_planet_sign(rule['rule_name'])
            if planet and sign:
                planet_name = planet
                sign_data[sign] = {
                    'impact': rule.get('impact_if_violated', ''),
                    'threshold': rule.get('check_logic', {}).get('threshold'),
                    'severity': rule.get('severity', 'medium')
                }
        
        if planet_name:
            template['rule_name'] = f"{planet_name} Sign Placement (All Signs)"
            template['is_parameterized'] = True
            template['parameter_type'] = 'planet_sign'
            template['sign_effects'] = dict(sign_data)
            template['original_rule_count'] = len(rules)
        
        return template
    
    def _consolidate_planet_in_house(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate planet-in-house rules"""
        
        template = rules[0].copy()
        
        # Group by house
        house_data = defaultdict(dict)
        planet_name = None
        
        for rule in rules:
            planet, house = self._extract_planet_house(rule['rule_name'])
            if planet and house:
                planet_name = planet
                house_data[house] = {
                    'impact': rule.get('impact_if_violated', ''),
                    'threshold': rule.get('check_logic', {}).get('threshold'),
                    'severity': rule.get('severity', 'medium')
                }
        
        if planet_name:
            template['rule_name'] = f"{planet_name} House Placement (All Houses)"
            template['is_parameterized'] = True
            template['parameter_type'] = 'planet_house'
            template['house_effects'] = dict(house_data)
            template['original_rule_count'] = len(rules)
        
        return template
    
    def _merge_with_remaining(
        self,
        consolidated: List[Dict[str, Any]],
        all_rules: List[Dict[str, Any]],
        pattern_groups: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Add rules that weren't part of any pattern"""
        
        # Get IDs of rules that were consolidated
        consolidated_rule_ids = set()
        for group_rules in pattern_groups.values():
            for rule in group_rules:
                consolidated_rule_ids.add(rule.get('rule_id'))
        
        # Add remaining rules
        remaining = [
            r for r in all_rules
            if r.get('rule_id') not in consolidated_rule_ids
        ]
        
        print(f"   ✅ Added {len(remaining)} non-pattern rules")
        
        return consolidated + remaining
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get consolidation statistics"""
        return self.stats


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate validation rules for better performance"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input rules JSON file'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output consolidated rules file'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.75,
        help='Minimum extraction confidence (default: 0.75)'
    )
    parser.add_argument(
        '--stats-file',
        type=str,
        help='Output file for statistics (JSON)'
    )
    
    args = parser.parse_args()
    
    # Load rules
    print(f"\n📖 Loading rules from {args.input}...")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rules = data.get('rules', data if isinstance(data, list) else [])
    
    print(f"   ✅ Loaded {len(rules)} rules")
    
    # Consolidate
    consolidator = RuleConsolidator(min_confidence=args.min_confidence)
    consolidated_rules = consolidator.consolidate(rules)
    
    # Prepare output
    output_data = {
        'metadata': {
            'original_count': consolidator.stats['original_count'],
            'consolidated_count': len(consolidated_rules),
            'reduction_percentage': (1 - len(consolidated_rules)/consolidator.stats['original_count']) * 100,
            'min_confidence': args.min_confidence,
            'consolidation_groups': consolidator.stats['consolidation_groups']
        },
        'rules': consolidated_rules
    }
    
    # Save consolidated rules
    print(f"\n💾 Saving consolidated rules to {args.output}...")
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Saved {len(consolidated_rules)} rules")
    
    # Save statistics if requested
    if args.stats_file:
        stats = consolidator.get_statistics()
        with open(args.stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        print(f"   ✅ Statistics saved to {args.stats_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 CONSOLIDATION SUMMARY")
    print("=" * 60)
    print(f"Original rules:        {consolidator.stats['original_count']:,}")
    print(f"After quality filter:  {consolidator.stats['after_quality_filter']:,}")
    print(f"After deduplication:   {consolidator.stats['after_dedup']:,}")
    print(f"After consolidation:   {len(consolidated_rules):,}")
    print(f"\nReduction:             {consolidator.stats['original_count'] - len(consolidated_rules):,} rules")
    print(f"Percentage:            {(1 - len(consolidated_rules)/consolidator.stats['original_count'])*100:.1f}%")
    print(f"Consolidation groups:  {consolidator.stats['consolidation_groups']}")
    print("=" * 60)


if __name__ == "__main__":
    main()