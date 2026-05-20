# NakshatraAI Eval Harness

Automated quality evaluation for the chatbot. Runs golden scenarios against the live API, scores each response on deterministic rules + an LLM tone judge, and writes a JSON scorecard plus a Markdown digest you can diff across runs.

## Quick start

```bash
# 1. Start the server with telemetry enabled
EVAL_TELEMETRY=1 uvicorn src.api.main:app --port 6262

# 2. In another shell, run the eval
python scripts/run_eval.py

# 3. See the latest scorecard
cat data/eval_results/latest.md
```

Outputs land in `data/eval_results/`:

- `<timestamp>[_label].json` — full structured scorecard for diffing
- `latest.json` — copy of the most recent run
- `latest.md` — human-readable digest with regression section vs the previous run

## What gets scored

**Deterministic checks (per turn):**

| Check | What it verifies |
|---|---|
| `response_nonempty` | Response has >20 characters |
| `length_in_range` | Word count fits phase-appropriate window (INITIAL 80–200, DETAILED 200–560) |
| `language_match` | Response language matches the scenario's language tag |
| `has_month_year` | Predictions cite at least one explicit month-year window |
| `no_past_dates` | No cited year is strictly before today |
| `domain_match` | SemanticFrame domain matches the scenario's domain tag |
| `accuracy_gate_clean` | `accuracy_gate` didn't flag mismatched factor claims |
| `phase_transition` | Conversation phase advanced in an allowed direction |
| `factor_coverage` | At least one of the top FOCUS FACTORS is referenced |
| `no_meta_reviewer_leak` | Response doesn't contain reviewer/meta language |
| `processing_time_budget` | Turn completed within latency budget (45s prediction / 10s chitchat) |

**LLM judge (one Gemini Flash call per turn):**

Scored 0–3 on each:

- `warmth` — empathetic acknowledgment of user's emotional state
- `voice_match` — sounds like a real astrologer vs robotic
- `jargon_handled` — technical terms explained in plain language
- `closing_appropriate` — phase-correct closing (offer/pivot/farewell)

**Aggregate scoring:**

- Per-turn `final_score = 0.6 × deterministic + 0.4 × judge` (judge weight zero if disabled)
- Per-scenario `aggregate_score = mean(turn.final_score)`
- Scenario `passed = aggregate_score >= pass_threshold` (default 0.70)
- Overall score = mean of scenario aggregate_scores

## CLI

```bash
# Run everything
python scripts/run_eval.py

# Smoke run on 2 scenarios, no LLM judge (~1 min)
python scripts/run_eval.py --ids career_hinglish_anxious_01 finance_english_worried_01 --no-judge

# Only marriage scenarios
python scripts/run_eval.py --tags marriage

# Label this run (suffix the filename)
python scripts/run_eval.py --label "post-factor-scorer-fix"

# Stricter pass threshold
python scripts/run_eval.py --pass-threshold 0.85

# Compare two saved runs
python scripts/run_eval.py --compare data/eval_results/<run_a>.json data/eval_results/<run_b>.json
```

Exit codes: `0` = all pass, `1` = some failed/errored, `2` = server unreachable, `3` = internal error.

## Cost

LLM judge: ~$0.0001–0.0003 per scenario (Gemini Flash). Full 27-scenario run with judge enabled: **~$0.005–0.01** in LLM fees. Plus the actual `/message` LLM costs (already accounted for in production).

Turn off the judge with `--no-judge` for pure-rule runs (no extra cost, but tone regressions become invisible).

## Adding scenarios

Edit `data/golden_scenarios.yaml`. Required fields per scenario:

```yaml
- id: unique_stable_id
  tags: [domain, language, tone, phase, ...]   # see _DOMAIN_TAGS, _LANG_TAGS in deterministic.py
  user_profile:
    name: "..."
    date_of_birth: "YYYY-MM-DD"
    time_of_birth: "HH:MM:SS"
    place_of_birth: "..."
    latitude: <float>
    longitude: <float>
    timezone: "Asia/Kolkata"
  conversation:
    - {role: user,      text: "..."}
    - {role: assistant, text: "..."}   # golden reference for tone
    - {role: user,      text: "..."}   # multi-turn supported
    - {role: assistant, text: "..."}
```

**Tag conventions:**
- Domain (required): `marriage | career | finance | health | children | foreign | divorce | education | home | spirituality`
- Language: `english | hindi | hinglish | tamil | telugu | malayalam | marathi | punjabi`
- Tone: `anxious | frustrated | worried | hopeful | excited | neutral | casual`
- Phase context: `initial | detailed | followup` (informational only)

## Architecture

```
src/eval/
├── __init__.py          # public API
├── runner.py            # multi-turn execution + scoring
├── scorecard.py         # JSON + Markdown writers + diff
├── README.md            # this file
└── metrics/
    ├── __init__.py
    ├── deterministic.py # rule-based checks
    └── llm_judge.py     # Gemini Flash tone judge

scripts/run_eval.py      # CLI entry
data/golden_scenarios.yaml
data/eval_results/       # output (gitignored)
```

The runner talks to the live FastAPI server over HTTP. Set `EVAL_TELEMETRY=1` in the server's environment so `metadata["eval"]` is populated; without it, deterministic checks that depend on the SemanticFrame, accuracy_gate, focus_factors, or conversation_phase will silently report "skipped".

## Recommended workflow

1. Make a code change.
2. Run `python scripts/run_eval.py --label "before-change"` — baseline.
3. Make the change.
4. Run `python scripts/run_eval.py --label "after-change"`.
5. Read `data/eval_results/latest.md` — the regression section pairs scenarios and shows Δ per scenario, per tag, and per check.
6. If a scenario regressed, drill into its turn-level results in the JSON.

## Known limitations

- **Single-judge bias**: the LLM judge is itself Gemini Flash. Judging your own output has known issues. Future enhancement: rotate models or use a separate provider for the judge.
- **No semantic equivalence check**: we don't compare the response to the golden reference for content — only tone. The golden is informational. This is intentional (charts differ across users, so content can't be matched).
- **Latency budget is generous**: 45s reflects current cold-start orchestrator times. Tighten as the orchestrator gets faster.
- **No streaming evaluation**: the harness hits `/message` (synchronous). Streaming responses would need a separate runner.
