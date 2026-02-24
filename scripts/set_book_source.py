# set_book_source.py
"""
set_book_source.py
------------------
Replaces ALL source fields in a rules JSON file with a single canonical book name.
Use this on individual per-book extraction files BEFORE merging.

Usage:
    python set_book_source.py --input bphs_rules.json --book "BPHS"
    python set_book_source.py --input saravali_rules.json --book "Saravali"
    python set_book_source.py --input jataka_parijata_rules.json --book "Jataka Parijata"

Overwrites the input file in place (original backed up as .bak).
"""

import json
import shutil
import argparse
from pathlib import Path

# Fields to normalize (checks all of these)
SOURCE_FIELDS = ["classical_reference", "source_book", "source", "book"]


def main():
    parser = argparse.ArgumentParser(description="Set canonical book name in a rules file")
    parser.add_argument("--input", required=True, help="Input rules JSON file")
    parser.add_argument("--book",  required=True, help='Canonical book name e.g. "BPHS"')
    parser.add_argument("--no-backup", action="store_true", help="Skip creating .bak backup")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {args.input}")
        return

    # ── Backup
    if not args.no_backup:
        backup_path = input_path.with_suffix(".bak")
        shutil.copy2(input_path, backup_path)
        print(f"💾 Backup saved: {backup_path}")

    # ── Load
    data = json.load(open(input_path, "r", encoding="utf-8"))
    rules = data.get("rules", data) if isinstance(data, dict) else data
    print(f"📖 Loaded {len(rules)} rules from {args.input}")

    # ── Replace
    updated = 0
    for rule in rules:
        # Save original source before overwriting
        for field in SOURCE_FIELDS:
            if field in rule and rule[field]:
                original = rule[field]
                if original != args.book:
                    rule["original_reference"] = original  # preserve it
                rule[field] = args.book
                updated += 1
                break  # only update the first matching field

    print(f"✅ Set source to '{args.book}' for {updated} rules")

    # ── Save
    if isinstance(data, dict):
        data["rules"] = rules
        output_data = data
    else:
        output_data = rules

    json.dump(output_data, open(input_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"💾 Saved: {input_path}")

    # ── Quick verify
    sample_sources = set()
    for r in rules[:20]:
        for field in SOURCE_FIELDS:
            if field in r:
                sample_sources.add(r[field])
                break
    print(f"🔍 Sample check (first 20 rules): {sample_sources}")


if __name__ == "__main__":
    main()
