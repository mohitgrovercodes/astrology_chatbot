# check_merged.py
import json, sys
f = sys.argv[1] if len(sys.argv) > 1 else 'merged.json'
data = json.load(open(f, 'r', encoding='utf-8'))
rules = data.get('rules', data) if isinstance(data, dict) else data
print(f'Total rules: {len(rules)}')
sources = sorted(set(str(r.get('source_book') or r.get('classical_reference') or r.get('source', 'unknown'))[:60] for r in rules))
print(f'Sources ({len(sources)}):')
[print(f'  - {s}') for s in sources]
