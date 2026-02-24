# test_validation_engine.py
"""
test_validation_engine.py
--------------------------
Tests the VedicValidationEngine with the optimized tiered rules.

The existing engine expects the OLD flat schema (VedicValidationRuleSet).
This test loads the TIERED rules directly as plain dicts and runs
validation manually — no schema dependency needed.

Usage:
    python test_validation_engine.py
    python test_validation_engine.py --tier 1          # quick (750 rules)
    python test_validation_engine.py --tier 2          # standard (2500 rules)
    python test_validation_engine.py --query career    # different query type
"""

import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE CHART DATA
# Replace with output from your VedicEngine for a real test.
# This is a synthetic chart for a marriage prediction query.
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_CHART = {
    "lagna": "Aries",
    "lagna_degrees": 15.23,
    "moon_sign": "Cancer",
    "moon_nakshatra": "Pushya",
    "sun_sign": "Taurus",

    "planets": {
        "Sun":     {"rashi": "Taurus",   "house": 2,  "degrees": 12.45, "is_retrograde": False, "nakshatra": "Rohini"},
        "Moon":    {"rashi": "Cancer",   "house": 4,  "degrees": 8.23,  "is_retrograde": False, "nakshatra": "Pushya"},
        "Mars":    {"rashi": "Scorpio",  "house": 8,  "degrees": 22.10, "is_retrograde": False, "nakshatra": "Jyeshtha"},
        "Mercury": {"rashi": "Taurus",   "house": 2,  "degrees": 5.67,  "is_retrograde": False, "nakshatra": "Krittika"},
        "Jupiter": {"rashi": "Taurus",   "house": 2,  "degrees": 18.90, "is_retrograde": False, "nakshatra": "Rohini"},
        "Venus":   {"rashi": "Capricorn","house": 10, "degrees": 3.45,  "is_retrograde": False, "nakshatra": "Uttara Ashadha"},
        "Saturn":  {"rashi": "Pisces",   "house": 12, "degrees": 9.78,  "is_retrograde": False, "nakshatra": "Uttara Bhadrapada"},
        "Rahu":    {"rashi": "Pisces",   "house": 12, "degrees": 14.32, "is_retrograde": True,  "nakshatra": "Uttara Bhadrapada"},
        "Ketu":    {"rashi": "Virgo",    "house": 6,  "degrees": 14.32, "is_retrograde": True,  "nakshatra": "Hasta"},
    },

    # House lords (which planet rules each house, based on Aries lagna)
    "house_lords": {
        1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon",
        5: "Sun",  6: "Mercury", 7: "Venus", 8: "Mars",
        9: "Jupiter", 10: "Saturn", 11: "Saturn", 12: "Jupiter"
    },

    # Current dasha
    "dasha": {
        "mahadasha":       {"planet": "Venus",   "end_date": "2044-03-15"},
        "antardasha":      {"planet": "Moon",    "end_date": "2027-07-15"},
        "pratyantardasha": {"planet": "Jupiter", "end_date": "2026-06-12"},
        "dasha_sequence":  "Venus-Moon-Jupiter"
    },

    # Current transits
    "transits": {
        "Jupiter": {"rashi": "Taurus",  "house": 2},
        "Saturn":  {"rashi": "Pisces",  "house": 12},
        "Rahu":    {"rashi": "Pisces",  "house": 12},
    },

    # Divisional charts (minimal)
    "D9": {
        "lagna": "Libra",
        "planets": {
            "Venus": {"rashi": "Pisces", "house": 6},
        }
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# LIGHTWEIGHT RULE CHECKER
# Applies rules from tiered_rules.json without needing the Pydantic schema.
# Each rule's check_conditions list is matched against the chart dict.
# ─────────────────────────────────────────────────────────────────────────────

def load_rules_for_tier(tiered_path: str, max_tier: int) -> List[Dict]:
    """Load all rules up to and including max_tier."""
    data = json.load(open(tiered_path, encoding="utf-8"))
    tiers = data.get("tiers", {})

    rules = []
    for t in range(1, max_tier + 1):
        tier_key = f"tier{t}"
        rules.extend(tiers.get(tier_key, []))
    return rules


def filter_by_query(rules: List[Dict], query_type: str) -> List[Dict]:
    """Keep rules that apply to this query type or 'all'."""
    result = []
    for rule in rules:
        applies = rule.get("applies_to_queries", [])
        if isinstance(applies, str):
            applies = [applies]
        # Normalise: each item may be a string or dict
        values = []
        for a in applies:
            if isinstance(a, dict):
                values.append(a.get("value", "").lower())
            else:
                values.append(str(a).lower())
        if "all" in values or query_type.lower() in values:
            result.append(rule)
    return result


def check_rule(rule: Dict, chart: Dict) -> Dict[str, Any]:
    """
    Very lightweight rule checker.
    Returns {passed, reason} for each rule.

    Since rules are textual (not code), we do keyword-based matching
    against the chart dict. A full implementation would parse
    check_conditions properly — this gives you a working test harness.
    """
    conditions = rule.get("check_conditions", [])
    rule_name  = rule.get("rule_name", "Unknown")
    passed     = True
    reason     = "No conditions defined — assumed pass"

    if not conditions:
        return {"passed": True, "reason": reason}

    failed_conditions = []

    for condition in conditions:
        # Each condition is a dict with keys like:
        # factor, operator, value, description
        factor   = condition.get("factor", "")
        operator = condition.get("operator", "")
        value    = condition.get("value", "")
        desc     = condition.get("description", condition.get("factor", ""))

        # ── Simple keyword checks against chart ──────────────────────────
        matched = _evaluate_condition(factor, operator, value, chart)
        if not matched:
            failed_conditions.append(desc or factor)

    if failed_conditions:
        passed = False
        reason = f"Failed: {'; '.join(failed_conditions[:3])}"
    else:
        reason = "All conditions satisfied"

    return {"passed": passed, "reason": reason}


def _evaluate_condition(factor: str, operator: str, value: Any, chart: Dict) -> bool:
    """
    Evaluate a single condition against the chart.
    Returns True (pass) or False (fail).

    This is a simplified evaluator. A production engine would
    have explicit handlers per factor type.
    """
    factor_lower = str(factor).lower()
    value_str    = str(value).lower()

    # ── 7th house / 7th lord checks ──────────────────────────────────────
    if "7th_lord" in factor_lower or "seventh_lord" in factor_lower:
        house_lords = chart.get("house_lords", {})
        lord = str(house_lords.get(7, "")).lower()
        if "combust" in value_str:
            # Check if 7th lord is within 6° of Sun
            planet_data = chart["planets"].get(lord.capitalize(), {})
            sun_data    = chart["planets"].get("Sun", {})
            if planet_data.get("rashi") == sun_data.get("rashi"):
                deg_diff = abs(planet_data.get("degrees", 0) - sun_data.get("degrees", 0))
                return not (deg_diff < 6)   # fail if combust
        return True  # condition not evaluable, assume pass

    # ── Retrograde checks ─────────────────────────────────────────────────
    if "retrograde" in factor_lower:
        for planet, pdata in chart["planets"].items():
            if planet.lower() in factor_lower and pdata.get("is_retrograde"):
                if operator in ("==", "is", "equals"):
                    return value_str in ("true", "yes", "1")
        return True

    # ── Combustion checks ─────────────────────────────────────────────────
    if "combust" in factor_lower or "combustion" in factor_lower:
        sun = chart["planets"].get("Sun", {})
        for planet, pdata in chart["planets"].items():
            if planet == "Sun":
                continue
            if planet.lower() in factor_lower:
                if pdata.get("rashi") == sun.get("rashi"):
                    diff = abs(pdata.get("degrees", 0) - sun.get("degrees", 0))
                    combust_orbs = {
                        "Moon": 12, "Mars": 17, "Mercury": 14,
                        "Jupiter": 11, "Venus": 10, "Saturn": 15
                    }
                    orb = combust_orbs.get(planet, 10)
                    if diff < orb:
                        return False   # is combust -> fail
        return True

    # ── House occupancy checks ────────────────────────────────────────────
    if "house" in factor_lower and any(str(h) in factor_lower for h in range(1, 13)):
        # e.g. factor = "7th_house_occupant" value = "benefic"
        try:
            house_num = next(
                int(tok) for tok in factor_lower.replace("_", " ").split()
                if tok.isdigit() and 1 <= int(tok) <= 12
            )
            occupants = [
                p for p, d in chart["planets"].items()
                if d.get("house") == house_num
            ]
            benefics  = {"Jupiter", "Venus", "Moon", "Mercury"}
            malefics  = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}

            if "benefic" in value_str:
                return any(p in benefics for p in occupants)
            if "malefic" in value_str:
                return any(p in malefics for p in occupants)
            if "empty" in value_str:
                return len(occupants) == 0
        except StopIteration:
            pass
        return True  # can't evaluate -> pass

    # Default: condition not evaluable with simple checker -> pass
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_test(tiered_path: str, query_type: str, max_tier: int):

    print("\n" + "=" * 70)
    print(f"  VALIDATION ENGINE TEST")
    print(f"  Query: {query_type.upper()}  |  Tier: 1-{max_tier}")
    print("=" * 70)

    # ── Load rules ───────────────────────────────────────────────────────
    print(f"\n📖 Loading rules from {tiered_path}...")
    t0 = time.time()
    all_rules = load_rules_for_tier(tiered_path, max_tier)
    print(f"   [OK] Loaded {len(all_rules)} rules (Tier 1-{max_tier})")

    # ── Filter by query type ─────────────────────────────────────────────
    applicable = filter_by_query(all_rules, query_type)
    print(f"   [OK] {len(applicable)} rules apply to '{query_type}'")

    if not applicable:
        print("\n[WARN]  No applicable rules found. Check query_type spelling.")
        print("   Common values: marriage, career, finance, health, children")
        return

    # ── Run checks ───────────────────────────────────────────────────────
    print(f"\n[SEARCH] Running {len(applicable)} rule checks...\n")

    passed_count  = 0
    failed_count  = 0
    skipped_count = 0
    critical_failures = []
    high_failures     = []
    halt_triggered    = False

    for rule in applicable:
        result = check_rule(rule, SAMPLE_CHART)

        severity     = rule.get("severity", "medium")
        if isinstance(severity, list): severity = severity[0]
        if isinstance(severity, dict): severity = severity.get("value", "medium")
        severity = str(severity).lower()

        halt = rule.get("halt_on_failure", False)

        if result["passed"]:
            passed_count += 1
        else:
            failed_count += 1
            entry = {
                "rule_id":   rule.get("rule_id"),
                "rule_name": rule.get("rule_name"),
                "severity":  severity,
                "reason":    result["reason"],
                "halt":      halt,
                "source":    rule.get("classical_reference", rule.get("source_book", ""))
            }
            if severity == "critical":
                critical_failures.append(entry)
            elif severity == "high":
                high_failures.append(entry)

            if halt:
                halt_triggered = True
                print(f"   [STOP] HALT triggered by: {rule.get('rule_name')}")
                break

    elapsed = time.time() - t0

    # ── Summary ──────────────────────────────────────────────────────────
    total_checked = passed_count + failed_count
    strength = max(0.0, 10.0 - (len(critical_failures) * 2.0) - (len(high_failures) * 0.5))

    print("\n" + "=" * 70)
    print("  VALIDATION RESULTS")
    print("=" * 70)
    print(f"  Rules checked:       {total_checked}")
    print(f"  Passed:              {passed_count}")
    print(f"  Failed:              {failed_count}")
    print(f"  Critical failures:   {len(critical_failures)}")
    print(f"  High failures:       {len(high_failures)}")
    print(f"  Overall strength:    {strength:.1f} / 10")
    print(f"  Halt triggered:      {'YES ⛔' if halt_triggered else 'No [OK]'}")
    print(f"  Time elapsed:        {elapsed:.2f}s")
    print(f"  Can proceed:         {'NO' if critical_failures or halt_triggered else 'YES [OK]'}")

    if critical_failures:
        print(f"\n[ALERT] CRITICAL FAILURES ({len(critical_failures)}):")
        for f in critical_failures[:5]:
            print(f"   [{f['rule_id']}] {f['rule_name']}")
            print(f"        Source: {f['source']}")
            print(f"        Reason: {f['reason']}")

    if high_failures:
        print(f"\n[WARN]  HIGH SEVERITY FAILURES ({len(high_failures)}) — first 5:")
        for f in high_failures[:5]:
            print(f"   [{f['rule_id']}] {f['rule_name']}")

    print("\n" + "=" * 70)
    print("  INTERPRETATION")
    print("=" * 70)
    if strength >= 8:
        verdict = "STRONG — High confidence prediction possible"
    elif strength >= 6:
        verdict = "MODERATE — Prediction possible with caveats"
    elif strength >= 4:
        verdict = "WEAK — Significant challenges present"
    else:
        verdict = "VERY WEAK — Prediction not advised"
    print(f"  {verdict}")
    print("=" * 70 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Vedic Validation Engine")
    parser.add_argument(
        "--tiered-rules",
        default="optimized/tiered_rules.json",
        help="Path to tiered_rules.json (default: optimized/tiered_rules.json)"
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Max tier to use: 1=quick, 2=standard, 3=detailed (default: 1)"
    )
    parser.add_argument(
        "--query",
        default="marriage",
        help="Query type: marriage, career, finance, health, children (default: marriage)"
    )
    args = parser.parse_args()

    if not Path(args.tiered_rules).exists():
        print(f"[FAIL] File not found: {args.tiered_rules}")
        print("   Run optimize_rules.py first to generate tiered_rules.json")
    else:
        run_test(args.tiered_rules, args.query, args.tier)
