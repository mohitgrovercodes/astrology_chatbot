# src/prediction/chart_synthesis_engine.py
"""
Chart Synthesis Engine - Uses validation rules for ANALYSIS

Takes:
1. Raw chart data (from VedicEngine)
2. Enhanced analysis (from ChartAnalyzer — dignities, lords, aspects)
3. Validation rules (from indexed_rules.json)

Produces:
Structured astrological analysis with:
- Yogas present/absent
- House-by-house analysis
- Key strengths and challenges
- Dasha-period synthesis
- Targeted classical references

This is the "brain" that decides what matters for this specific chart + query.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import json


class ChartSynthesisEngine:
    """
    Synthesizes classical analysis using validation rules.
    
    Transforms validation rules from "pass/fail checks" into "analytical insights".
    """
    
    def __init__(
        self,
        indexed_rules_path: str = "optimized/indexed_rules.json",
        tiered_rules_path: str = "optimized/tiered_rules.json"
    ):
        self.indexed_path = Path(indexed_rules_path)
        self.tiered_path = Path(tiered_rules_path)
        
        self._indexed_data = None
        self._tiered_data = None
    
    def _load_indexed(self) -> Dict:
        """Lazy-load indexed rules."""
        if self._indexed_data is None and self.indexed_path.exists():
            with open(self.indexed_path, encoding='utf-8') as f:
                self._indexed_data = json.load(f)
        return self._indexed_data or {}
    
    def _load_tiered(self) -> Dict:
        """Lazy-load tiered rules."""
        if self._tiered_data is None and self.tiered_path.exists():
            with open(self.tiered_path, encoding='utf-8') as f:
                self._tiered_data = json.load(f)
        return self._tiered_data or {}
    
    # ──────────────────────────────────────────────────────────────────────
    # RULE FILTERING
    # ──────────────────────────────────────────────────────────────────────
    
    def _get_applicable_rules(
        self,
        query_type: str,
        stage: str = "promise",
        max_rules: int = 100
    ) -> List[Dict]:
        """
        Get rules relevant to this query using the index.
        
        Returns top N most applicable rules ordered by relevance.
        """
        indexed = self._load_indexed()
        composite_index = indexed.get('indices', {}).get('composite', {})
        rule_map = indexed.get('rule_map', {})
        
        if not composite_index or not rule_map:
            return []
        
        # Try composite keys: query_stage, query_*, all_stage
        keys_to_try = [
            f"{query_type}_{stage}",
            f"{query_type}_promise",
            f"{query_type}_timing",
            query_type,
            f"all_{stage}",
        ]
        
        matched_ids = set()
        for key in keys_to_try:
            matched_ids.update(composite_index.get(key, []))
            if len(matched_ids) >= max_rules:
                break
        
        # Get full rules
        rules = [
            rule_map[rid]
            for rid in list(matched_ids)[:max_rules]
            if rid in rule_map
        ]
        
        # Sort by check_order
        rules.sort(key=lambda r: r.get('check_order', 999))
        
        return rules
    
    # ──────────────────────────────────────────────────────────────────────
    # RULE EVALUATION (simplified from validation engine)
    # ──────────────────────────────────────────────────────────────────────
    
    def _evaluate_rule_simple(self, rule: Dict, chart_enhanced: Dict) -> Dict:
        """
        Simplified rule evaluation — returns structured result.
        
        Unlike validation engine (which uses LLM), this does pattern matching
        on rule descriptions to extract meaning.
        
        Returns:
        {
            "rule_id": "...",
            "rule_name": "...",
            "category": "yoga | house_analysis | dignity | aspect | ...",
            "applies": True/False,
            "significance": "strength | challenge | neutral",
            "description": "Human-readable interpretation"
        }
        """
        rule_name = rule.get('rule_name', '').lower()
        category = rule.get('category', '').lower()
        
        # Weighted deterministic inference over chart features.
        strengths = chart_enhanced.get('strengths', {}) or {}
        aspects = chart_enhanced.get('aspects', []) or []
        avg_strength = (
            sum(v for v in strengths.values() if isinstance(v, (int, float))) / max(len(strengths), 1)
            if strengths else 5.0
        )
        hard_aspect_count = sum(
            1 for a in aspects
            if str(a.get('aspect', '')).lower() in {'square', 'opposition', 'conjunction_malefic'}
        )
        soft_aspect_count = sum(
            1 for a in aspects
            if str(a.get('aspect', '')).lower() in {'trine', 'sextile', 'conjunction_benefic'}
        )

        weighted_score = 0.0
        weighted_score += (avg_strength - 5.0) * 0.4
        weighted_score += (soft_aspect_count * 0.25)
        weighted_score -= (hard_aspect_count * 0.3)

        # Rule-specific keyword signal weighting
        if any(k in rule_name for k in ['exalted', 'own', 'mooltrikona']):
            weighted_score += 1.25
        if any(k in rule_name for k in ['debilitated', 'combust', 'afflicted']):
            weighted_score -= 1.25
        if 'raja yoga' in rule_name or 'dhana yoga' in rule_name:
            weighted_score += 0.9

        # Pattern matching on rule names to produce interpretable labels
        result = {
            "rule_id": rule['rule_id'],
            "rule_name": rule.get('rule_name', ''),
            "category": category,
            "applies": weighted_score >= 0.25,
            "significance": "neutral",
            "description": "",
            "classical_ref": rule.get('classical_reference', ''),
            "weighted_score": round(weighted_score, 3),
        }
        
        # Yoga detection patterns
        if 'yoga' in category or 'yoga' in rule_name:
            result['category'] = 'yoga'
            # Extract yoga type from name
            if 'raja' in rule_name:
                result['description'] = "Raja Yoga indicates power and authority"
                result['significance'] = "strength" if weighted_score >= 0 else "neutral"
            elif 'dhana' in rule_name:
                result['description'] = "Dhana Yoga indicates wealth accumulation"
                result['significance'] = "strength" if weighted_score >= 0 else "neutral"
            elif 'gaja' in rule_name and 'kesari' in rule_name:
                result['description'] = "Gaja Kesari Yoga brings wisdom and prosperity"
                result['significance'] = "strength" if weighted_score >= 0 else "neutral"
            else:
                result['description'] = f"{rule.get('rule_name', 'Yoga')} detected"
                result['significance'] = "strength" if weighted_score >= 0 else "neutral"
        
        # House lord analysis patterns
        elif 'lord' in rule_name and 'house' in rule_name:
            result['category'] = 'house_lord'
            result['description'] = rule.get('rule_name', '')
        
        # Dignity patterns
        elif any(word in rule_name for word in ['exalted', 'debilitated', 'own', 'dignity']):
            result['category'] = 'dignity'
            if 'exalted' in rule_name:
                result['significance'] = "strength" if weighted_score >= 0 else "neutral"
                result['description'] = f"{rule.get('rule_name', '')} enhances planetary strength"
            elif 'debilitated' in rule_name:
                result['significance'] = "challenge"
                result['description'] = f"{rule.get('rule_name', '')} weakens planetary effects"
        
        # Aspect patterns
        elif 'aspect' in rule_name:
            result['category'] = 'aspect'
            result['description'] = rule.get('rule_name', '')
        
        # Combustion
        elif 'combust' in rule_name:
            result['category'] = 'combustion'
            result['significance'] = "challenge"
            result['description'] = rule.get('rule_name', '')

        if result['significance'] == 'neutral':
            if weighted_score > 0.75:
                result['significance'] = 'strength'
            elif weighted_score < -0.75:
                result['significance'] = 'challenge'
        
        return result
    
    # ──────────────────────────────────────────────────────────────────────
    # HOUSE-BY-HOUSE SYNTHESIS
    # ──────────────────────────────────────────────────────────────────────
    
    def _synthesize_house_analysis(
        self,
        house_num: int,
        chart_enhanced: Dict,
        query_type: str
    ) -> Dict:
        """
        Analyze a specific house using enhanced chart data.
        
        Returns structured analysis of:
        - House lord status
        - Planets in house
        - Aspects on house
        - Dignity of lord
        - Relevance to query
        """
        house_lords = chart_enhanced.get('house_lords', [])
        aspects = chart_enhanced.get('aspects', [])
        strengths = chart_enhanced.get('strengths', {})
        
        # Find this house's lord info
        lord_info = next((hl for hl in house_lords if hl['house'] == house_num), None)
        
        if not lord_info:
            return {"house": house_num, "analysis": "Data unavailable"}
        
        # Get planets aspecting this house
        aspecting_planets = [
            asp['planet']
            for asp in aspects
            if house_num in asp['aspects_houses']
        ]
        
        # Build analysis
        lord_strength = strengths.get(lord_info['lord'], 5.0)
        
        analysis = {
            "house": house_num,
            "sign": lord_info['sign'],
            "lord": lord_info['lord'],
            "lord_placement": {
                "house": lord_info['lord_in_house'],
                "sign": lord_info['lord_in_sign'],
                "dignity": lord_info['lord_dignity']
            },
            "lord_strength": lord_strength,
            "aspecting_planets": aspecting_planets,
            "assessment": self._assess_house_strength(lord_strength, lord_info['lord_dignity'])
        }
        
        return analysis
    
    def _assess_house_strength(self, strength: float, dignity: str) -> str:
        """Convert numerical strength to qualitative assessment."""
        if strength >= 8.0:
            return "Very Strong"
        elif strength >= 6.0:
            return "Strong"
        elif strength >= 4.0:
            return "Moderate"
        elif strength >= 2.0:
            return "Weak"
        else:
            return "Very Weak"
    
    # ──────────────────────────────────────────────────────────────────────
    # KEY HOUSES BY QUERY TYPE
    # ──────────────────────────────────────────────────────────────────────
    
    def _get_key_houses_for_query(self, query_type: str) -> List[int]:
        """Return houses most relevant to this query type."""
        house_map = {
            'marriage': [1, 7, 2, 5, 8, 12],  # Self, spouse, family, romance, intimacy, bed pleasures
            'career': [1, 10, 2, 6, 11],       # Self, profession, wealth, service, gains
            'finance': [1, 2, 5, 9, 11],       # Self, wealth, speculation, fortune, gains
            'health': [1, 6, 8, 12],           # Self, disease, chronic issues, hospitalization
            'children': [1, 5, 9],             # Self, progeny, fortune
            'education': [1, 2, 4, 5, 9],      # Self, speech, learning, intelligence, higher knowledge
            'spiritual': [1, 5, 9, 12],        # Self, purva punya, dharma, moksha
        }
        return house_map.get(query_type.lower(), [1, 7, 10])  # Default to key life houses
    
    # ──────────────────────────────────────────────────────────────────────
    # MAIN SYNTHESIS
    # ──────────────────────────────────────────────────────────────────────
    
    def synthesize(
        self,
        chart_data: Dict,
        chart_enhanced: Dict,
        query_type: str,
        validation_result: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main synthesis — combines chart analysis + rules + validation.
        
        Returns structured analysis ready for LLM consumption.
        """
        # Get applicable rules
        rules = self._get_applicable_rules(query_type, stage="promise", max_rules=200)

        # Always include yoga rules — pull them out first, then fill remaining slots
        yoga_rules = [r for r in rules if 'yoga' in r.get('rule_name', '').lower() or 'yoga' in r.get('category', '').lower()]
        non_yoga_rules = [r for r in rules if r not in yoga_rules]
        # Take up to 10 yoga rules + up to 40 non-yoga rules = 50 total cap
        selected_rules = yoga_rules[:10] + non_yoga_rules[:40]

        # Evaluate rules (simplified pattern matching)
        evaluated_rules = [
            self._evaluate_rule_simple(rule, chart_enhanced)
            for rule in selected_rules
        ]
        
        # Categorize insights
        yogas = [r for r in evaluated_rules if r['category'] == 'yoga']
        house_factors = [r for r in evaluated_rules if r['category'] == 'house_lord']
        dignity_factors = [r for r in evaluated_rules if r['category'] == 'dignity']
        
        # Analyze key houses for this query
        key_houses = self._get_key_houses_for_query(query_type)
        house_analyses = [
            self._synthesize_house_analysis(h, chart_enhanced, query_type)
            for h in key_houses
        ]
        
        # Build strengths and challenges
        strengths_list = []
        challenges_list = []
        
        # From dignities
        for d in chart_enhanced.get('dignities', []):
            if d['dignity'] == 'exalted':
                strengths_list.append(f"{d['planet']} exalted in {d['sign']} — maximum strength")
            elif d['dignity'] == 'debilitated':
                challenges_list.append(f"{d['planet']} debilitated in {d['sign']} — weakened effects")
            elif d['dignity'] == 'own':
                strengths_list.append(f"{d['planet']} in own sign {d['sign']} — comfortable expression")
        
        # From combustion
        for planet, is_combust in chart_enhanced.get('combustion', {}).items():
            if is_combust:
                challenges_list.append(f"{planet} combust — obscured by Sun's rays")
        
        # From yogas
        for yoga in yogas:
            if yoga['significance'] == 'strength':
                strengths_list.append(yoga['description'])
        
        # From validation result if available
        if validation_result:
            strength_score = validation_result.get('overall_strength', 5.0)
            for failure in validation_result.get('critical_failures', [])[:3]:
                challenges_list.append(f"{failure['rule_name']}: {failure['reason']}")
        
        # Synthesize final structure
        synthesis = {
            "query_type": query_type,
            "overall_assessment": {
                "strength_score": validation_result.get('overall_strength', 5.0) if validation_result else 5.0,
                "can_proceed": validation_result.get('can_proceed', True) if validation_result else True,
            },
            "key_houses": house_analyses,
            "yogas_detected": [
                {
                    "name": y['rule_name'],
                    "description": y['description'],
                    "significance": y['significance'],
                    "source": y['classical_ref']
                }
                for y in yogas[:5]
            ],
            "planetary_strengths": chart_enhanced.get('strengths', {}),
            "chart_strengths": strengths_list[:8],  # Top 8
            "chart_challenges": challenges_list[:8],  # Top 8
            "house_lord_summary": {
                f"H{ha['house']}": {
                    "lord": ha['lord'],
                    "strength": ha['lord_strength'],
                    "assessment": ha['assessment'],
                    "placement": f"H{ha['lord_placement']['house']} in {ha['lord_placement']['sign']}"
                }
                for ha in house_analyses
            },
            "aspect_highlights": [
                f"{asp['planet']} (H{asp['from_house']}) aspects houses {asp['aspects_houses']}"
                for asp in chart_enhanced.get('aspects', [])[:5]
            ],
        }
        
        return synthesis


# ──────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ──────────────────────────────────────────────────────────────────────────

def synthesize_chart_analysis(
    chart_data: Dict,
    chart_enhanced: Dict,
    query_type: str,
    validation_result: Optional[Dict] = None
) -> Dict:
    """Convenience function — synthesizes complete analysis."""
    engine = ChartSynthesisEngine()
    return engine.synthesize(chart_data, chart_enhanced, query_type, validation_result)


if __name__ == "__main__":
    # Test synthesis
    sample_chart = {
        "lagna": {"sign": "Aries", "degree": 15.23},
        "planets": {
            "JUPITER": {"sign": "Cancer", "house": 4, "degree": 5.30, "is_retrograde": False},
            "VENUS": {"sign": "Aries", "house": 1, "degree": 28.50, "is_retrograde": False},
        }
    }
    
    sample_enhanced = {
        "dignities": [
            {"planet": "JUPITER", "sign": "Cancer", "dignity": "exalted", "is_deep": True, "degrees": 5.30},
            {"planet": "VENUS", "sign": "Aries", "dignity": "debilitated", "is_deep": False, "degrees": 28.50}
        ],
        "strengths": {"JUPITER": 10.0, "VENUS": 2.0},
        "house_lords": [
            {"house": 7, "sign": "Libra", "lord": "VENUS", "lord_in_house": 1, 
             "lord_in_sign": "Aries", "lord_dignity": "debilitated"}
        ],
        "aspects": [],
        "combustion": {},
        "retrograde": []
    }
    
    synthesis = synthesize_chart_analysis(
        chart_data=sample_chart,
        chart_enhanced=sample_enhanced,
        query_type="marriage"
    )
    
    print("=== CHART SYNTHESIS ===\n")
    print(f"Query: {synthesis['query_type']}")
    print(f"Overall Strength: {synthesis['overall_assessment']['strength_score']}/10\n")
    
    print("Strengths:")
    for s in synthesis['chart_strengths']:
        print(f"  • {s}")
    
    print("\nChallenges:")
    for c in synthesis['chart_challenges']:
        print(f"  • {c}")
    
    print("\nKey Houses:")
    for house_num, info in synthesis['house_lord_summary'].items():
        print(f"  {house_num}: {info['lord']} - {info['assessment']} ({info['strength']:.1f}/10)")