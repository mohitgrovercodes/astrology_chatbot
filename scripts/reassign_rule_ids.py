# reassign_rule_ids.py
"""
reassign_rule_ids.py
--------------------
Reassigns unique sequential rule IDs to all rules after merging
multiple book files. Run this AFTER merging, BEFORE optimizing.

Usage:
    python reassign_rule_ids.py --input merged_rules.json --output reindexed_rules.json

The old rule_id is preserved in 'original_rule_id' field.
"""

import json
import argparse
from pathlib import Path
from collections import Counter


def main():
    parser = argparse.ArgumentParser(description="Reassign unique rule IDs after merging")
    parser.add_argument("--input",  required=True, help="Input merged rules JSON")
    parser.add_argument("--output", required=True, help="Output file with unique IDs")
    parser.add_argument("--prefix", default="VR", help="ID prefix (default: VR)")
    args = parser.parse_args()

    # ── Load
    print(f"\n📖 Loading rules from {args.input}...")
    data = json.load(open(args.input, "r", encoding="utf-8"))
    rules = data.get("rules", data) if isinstance(data, dict) else data
    print(f"   [OK] Loaded {len(rules)} rules")

    # ── Check for duplicates before fixing
    existing_ids = [r.get("rule_id", "") for r in rules]
    id_counts = Counter(existing_ids)
    duplicates = {k: v for k, v in id_counts.items() if v > 1}
    print(f"   [WARN]  Duplicate IDs found: {len(duplicates)} IDs repeated")
    print(f"   [STATS] Total unique IDs before fix: {len(set(existing_ids))}")

    # ── Reassign sequentially
    print(f"\n🔄 Reassigning IDs with prefix '{args.prefix}'...")
    for idx, rule in enumerate(rules, start=1):
        new_id = f"{args.prefix}{idx:05d}"   # e.g. VR00001, VR00002...

        # Preserve original ID
        old_id = rule.get("rule_id", "")
        if old_id and old_id != new_id:
            rule["original_rule_id"] = old_id

        rule["rule_id"] = new_id

    # ── Verify no duplicates remain
    new_ids = [r["rule_id"] for r in rules]
    assert len(new_ids) == len(set(new_ids)), "[FAIL] Still have duplicates — bug!"
    print(f"   [OK] All {len(rules)} rules now have unique IDs")
    print(f"   [STATS] Range: {new_ids[0]} -> {new_ids[-1]}")

    # ── Save
    if isinstance(data, dict):
        data["rules"] = rules
        output_data = data
    else:
        output_data = rules

    json.dump(output_data, open(args.output, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved to {args.output}")


if __name__ == "__main__":
    main()
