# vedic_validation_engine.py
"""
Vedic Validation Engine

Deterministic validation engine that applies rules from vedic_validation_rules.json
Integrates with existing calculation engines.

Usage:
    from vedic_validation_engine import VedicValidationEngine
    
    validator = VedicValidationEngine("vedic_validation_rules.json")
    result = validator.validate_promise(query_type="marriage", chart_data=chart)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Import from existing project structure
try:
    from vedic_validation_schema import (
        VedicValidationRule,
        VedicValidationRuleSet,
        ValidationSeverity,
        QueryType,
        PredictionStage
    )
except ImportError:
    print("⚠️  vedic_validation_schema not found. Ensure it's in the same directory.")


@dataclass
class ValidationResult:
    """Result of a single validation check"""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str
    impact_if_failed: str
    impact_percentage: int
    details: Dict[str, Any]
    recommendation: Optional[str] = None


@dataclass
class StageValidationResult:
    """Result of validating an entire stage (Promise/Timing/Trigger)"""
    stage: str
    passed: bool
    overall_strength: float  # 0-10 scale
    critical_issues: List[ValidationResult]
    high_issues: List[ValidationResult]
    medium_issues: List[ValidationResult]
    low_issues: List[ValidationResult]
    all_checks: List[ValidationResult]
    proceed_to_next_stage: bool
    reasoning: str


class VedicValidationEngine:
    """
    Deterministic validation engine for Vedic astrology predictions
    
    Enforces Promise → Timing → Trigger hierarchy
    Applies rules from vedic_validation_rules.json
    """
    
    def __init__(self, rules_file: str = "vedic_validation_rules.json"):
        """
        Initialize validation engine
        
        Args:
            rules_file: Path to JSON file with extracted rules
        """
        self.rules_file = Path(rules_file)
        self.rules: Dict[str, VedicValidationRule] = {}
        self.rules_by_stage: Dict[str, List[VedicValidationRule]] = {
            "promise": [],
            "timing": [],
            "trigger": []
        }
        self.rules_by_query_type: Dict[str, List[VedicValidationRule]] = {}
        
        self.load_rules()
    
    def load_rules(self):
        """Load rules from JSON file"""
        if not self.rules_file.exists():
            print(f"⚠️  Rules file not found: {self.rules_file}")
            print("   Run extract_validation_rules.py first")
            return
        
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            ruleset = VedicValidationRuleSet(**data)
            
            # Index rules
            for rule in ruleset.rules:
                self.rules[rule.rule_id] = rule
                
                # By stage
                stage = rule.prediction_stage.value
                self.rules_by_stage[stage].append(rule)
                
                # By query type
                for qt in rule.applies_to_queries:
                    qt_val = qt.value
                    if qt_val not in self.rules_by_query_type:
                        self.rules_by_query_type[qt_val] = []
                    self.rules_by_query_type[qt_val].append(rule)
            
            print(f"✅ Loaded {len(self.rules)} validation rules")
            print(f"   Promise: {len(self.rules_by_stage['promise'])}")
            print(f"   Timing: {len(self.rules_by_stage['timing'])}")
            print(f"   Trigger: {len(self.rules_by_stage['trigger'])}")
            
        except Exception as e:
            print(f"❌ Error loading rules: {e}")
    
    def get_applicable_rules(
        self,
        stage: str,
        query_type: str
    ) -> List[VedicValidationRule]:
        """
        Get rules applicable for a stage and query type
        
        Args:
            stage: 'promise', 'timing', or 'trigger'
            query_type: 'marriage', 'career', etc.
            
        Returns:
            List of applicable rules, sorted by check_order
        """
        # Get rules for stage
        stage_rules = self.rules_by_stage.get(stage, [])
        
        # Filter by query type
        applicable = []
        for rule in stage_rules:
            query_types = [qt.value for qt in rule.applies_to_queries]
            if "all" in query_types or query_type in query_types:
                applicable.append(rule)
        
        # Sort by check_order
        applicable.sort(key=lambda r: r.check_order)
        
        return applicable
    
    # ============================================================================
    # STAGE 1: PROMISE VALIDATION
    # ============================================================================
    
    def validate_promise(
        self,
        query_type: str,
        chart_data: Dict[str, Any]
    ) -> StageValidationResult:
        """
        Validate Promise stage (D1 + Divisional + Non-negotiables)
        
        Args:
            query_type: 'marriage', 'career', 'finance', etc.
            chart_data: Dictionary with:
                - 'D1': Birth chart data
                - 'D9', 'D10', etc.: Divisional charts
                - 'planets': Planetary positions
                - 'lagna': Ascendant
                
        Returns:
            StageValidationResult with pass/fail and details
        """
        
        print(f"\n🔍 PROMISE VALIDATION ({query_type})")
        print("=" * 60)
        
        # Get applicable rules
        rules = self.get_applicable_rules("promise", query_type)
        
        print(f"Checking {len(rules)} rules...")
        
        validation_results = []
        critical_issues = []
        high_issues = []
        medium_issues = []
        low_issues = []
        
        # Apply each rule
        for rule in rules:
            print(f"  [{rule.check_order}] {rule.rule_name}...", end=" ")
            
            result = self._apply_rule(rule, chart_data, query_type)
            validation_results.append(result)
            
            if not result.passed:
                if result.severity == "critical":
                    critical_issues.append(result)
                elif result.severity == "high":
                    high_issues.append(result)
                elif result.severity == "medium":
                    medium_issues.append(result)
                else:
                    low_issues.append(result)
                print(f"❌ {result.severity.upper()}")
            else:
                print("✅")
        
        # Calculate overall strength
        strength = self._calculate_strength(validation_results)
        
        # Determine if can proceed
        passed = len(critical_issues) == 0
        proceed = passed and strength >= 5.0
        
        # Build reasoning
        reasoning = self._build_reasoning(
            stage="promise",
            passed=passed,
            strength=strength,
            critical_issues=critical_issues,
            high_issues=high_issues
        )
        
        result = StageValidationResult(
            stage="promise",
            passed=passed,
            overall_strength=strength,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            all_checks=validation_results,
            proceed_to_next_stage=proceed,
            reasoning=reasoning
        )
        
        # Print summary
        self._print_stage_summary(result)
        
        return result
    
    # ============================================================================
    # STAGE 2: TIMING VALIDATION
    # ============================================================================
    
    def validate_timing(
        self,
        query_type: str,
        dasha_data: Dict[str, Any],
        promise_result: StageValidationResult
    ) -> StageValidationResult:
        """
        Validate Timing stage (Dasha analysis)
        
        Only called if promise validation passed.
        
        Args:
            query_type: Query type
            dasha_data: Current dasha periods
            promise_result: Result from promise validation
            
        Returns:
            StageValidationResult
        """
        
        if not promise_result.proceed_to_next_stage:
            return StageValidationResult(
                stage="timing",
                passed=False,
                overall_strength=0.0,
                critical_issues=[],
                high_issues=[],
                medium_issues=[],
                low_issues=[],
                all_checks=[],
                proceed_to_next_stage=False,
                reasoning="Timing check skipped - promise validation failed"
            )
        
        print(f"\n🔍 TIMING VALIDATION ({query_type})")
        print("=" * 60)
        
        rules = self.get_applicable_rules("timing", query_type)
        print(f"Checking {len(rules)} rules...")
        
        # Similar structure to validate_promise
        # TODO: Implement dasha-specific checks
        
        # Placeholder
        return StageValidationResult(
            stage="timing",
            passed=True,
            overall_strength=7.0,
            critical_issues=[],
            high_issues=[],
            medium_issues=[],
            low_issues=[],
            all_checks=[],
            proceed_to_next_stage=True,
            reasoning="Timing validation passed (placeholder)"
        )
    
    # ============================================================================
    # STAGE 3: TRIGGER VALIDATION
    # ============================================================================
    
    def validate_trigger(
        self,
        query_type: str,
        transit_data: Dict[str, Any],
        timing_result: StageValidationResult
    ) -> StageValidationResult:
        """
        Validate Trigger stage (Transit analysis)
        
        Only called if timing validation passed.
        """
        
        if not timing_result.proceed_to_next_stage:
            return StageValidationResult(
                stage="trigger",
                passed=False,
                overall_strength=0.0,
                critical_issues=[],
                high_issues=[],
                medium_issues=[],
                low_issues=[],
                all_checks=[],
                proceed_to_next_stage=False,
                reasoning="Trigger check skipped - timing validation failed"
            )
        
        print(f"\n🔍 TRIGGER VALIDATION ({query_type})")
        print("=" * 60)
        
        rules = self.get_applicable_rules("trigger", query_type)
        print(f"Checking {len(rules)} rules...")
        
        # TODO: Implement transit checks
        
        # Placeholder
        return StageValidationResult(
            stage="trigger",
            passed=True,
            overall_strength=8.0,
            critical_issues=[],
            high_issues=[],
            medium_issues=[],
            low_issues=[],
            all_checks=[],
            proceed_to_next_stage=True,
            reasoning="Trigger validation passed (placeholder)"
        )
    
    # ============================================================================
    # RULE APPLICATION
    # ============================================================================
    
    def _apply_rule(
        self,
        rule: VedicValidationRule,
        data: Dict[str, Any],
        query_type: str
    ) -> ValidationResult:
        """
        Apply a single validation rule
        
        This is where specific checks are implemented:
        - Combustion check
        - Functional nature
        - Navamsha confirmation
        - etc.
        """
        
        # Dispatch to specific check based on rule_id or category
        if rule.rule_id == "VR001" or "combustion" in rule.rule_name.lower():
            return self._check_combustion(rule, data)
        
        elif rule.rule_id == "VR002" or "navamsha" in rule.rule_name.lower():
            return self._check_navamsha_confirmation(rule, data)
        
        elif rule.rule_id == "VR003" or "functional" in rule.rule_name.lower():
            return self._check_functional_nature(rule, data, query_type)
        
        else:
            # Generic check (placeholder)
            return ValidationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                passed=True,  # Default to pass for now
                severity=rule.severity.value,
                impact_if_failed=rule.impact_if_violated,
                impact_percentage=rule.impact_percentage or 0,
                details={"status": "not_implemented"},
                recommendation=f"Rule {rule.rule_id} check not yet implemented"
            )
    
    # ============================================================================
    # SPECIFIC CHECKS (to be implemented based on calculation engine)
    # ============================================================================
    
    def _check_combustion(
        self,
        rule: VedicValidationRule,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Check if planet is combust (within 8° of Sun)"""
        
        # TODO: Implement using calculation engine data
        # For now, placeholder
        
        return ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            passed=True,
            severity=rule.severity.value,
            impact_if_failed=rule.impact_if_violated,
            impact_percentage=rule.impact_percentage or 0,
            details={"checked": "combustion", "status": "placeholder"},
            recommendation=None
        )
    
    def _check_navamsha_confirmation(
        self,
        rule: VedicValidationRule,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Check if D9 confirms D1 promise"""
        
        # TODO: Implement
        
        return ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            passed=True,
            severity=rule.severity.value,
            impact_if_failed=rule.impact_if_violated,
            impact_percentage=rule.impact_percentage or 0,
            details={"checked": "navamsha", "status": "placeholder"}
        )
    
    def _check_functional_nature(
        self,
        rule: VedicValidationRule,
        data: Dict[str, Any],
        query_type: str
    ) -> ValidationResult:
        """Check functional benefic/malefic by lagna"""
        
        # TODO: Implement using lagna_specific_rules from rule
        
        return ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            passed=True,
            severity=rule.severity.value,
            impact_if_failed=rule.impact_if_violated,
            impact_percentage=rule.impact_percentage or 0,
            details={"checked": "functional_nature", "status": "placeholder"}
        )
    
    # ============================================================================
    # UTILITIES
    # ============================================================================
    
    def _calculate_strength(self, results: List[ValidationResult]) -> float:
        """Calculate overall strength score (0-10) based on validation results"""
        
        if not results:
            return 5.0  # Neutral
        
        total_impact = 0
        max_possible = 0
        
        for result in results:
            max_possible += 100
            if result.passed:
                total_impact += 100
            else:
                total_impact += (100 - result.impact_percentage)
        
        if max_possible == 0:
            return 5.0
        
        # Convert to 0-10 scale
        percentage = (total_impact / max_possible)
        return round(percentage * 10, 1)
    
    def _build_reasoning(
        self,
        stage: str,
        passed: bool,
        strength: float,
        critical_issues: List[ValidationResult],
        high_issues: List[ValidationResult]
    ) -> str:
        """Build human-readable reasoning"""
        
        if passed and strength >= 8.0:
            return f"{stage.title()} validation passed strongly (strength: {strength}/10)"
        elif passed and strength >= 5.0:
            return f"{stage.title()} validation passed moderately (strength: {strength}/10)"
        elif passed:
            return f"{stage.title()} validation passed weakly (strength: {strength}/10)"
        else:
            issues_str = ", ".join([issue.rule_name for issue in critical_issues[:3]])
            return f"{stage.title()} validation failed due to: {issues_str}"
    
    def _print_stage_summary(self, result: StageValidationResult):
        """Print summary of stage validation"""
        
        print("\n" + "-" * 60)
        print(f"STAGE: {result.stage.upper()}")
        print(f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        print(f"Strength: {result.overall_strength}/10")
        
        if result.critical_issues:
            print(f"\n🚫 Critical Issues: {len(result.critical_issues)}")
            for issue in result.critical_issues:
                print(f"   - {issue.rule_name}")
        
        if result.high_issues:
            print(f"\n⚠️  High Issues: {len(result.high_issues)}")
            for issue in result.high_issues[:3]:
                print(f"   - {issue.rule_name}")
        
        print(f"\n{'✅ Proceed to next stage' if result.proceed_to_next_stage else '❌ Do not proceed'}")
        print("-" * 60)


# Example usage
if __name__ == "__main__":
    # Initialize engine
    validator = VedicValidationEngine("vedic_validation_rules.json")
    
    # Example chart data (placeholder structure)
    chart_data = {
        "D1": {
            "lagna": "Aries",
            "planets": {
                "Sun": {"longitude": 45.5, "sign": "Taurus"},
                "Moon": {"longitude": 120.3, "sign": "Cancer"}
            }
        },
        "D9": {
            "planets": {}
        }
    }
    
    # Validate promise
    promise_result = validator.validate_promise(
        query_type="marriage",
        chart_data=chart_data
    )
    
    print(f"\n✅ Promise Validation Complete")
    print(f"Result: {promise_result.reasoning}")
