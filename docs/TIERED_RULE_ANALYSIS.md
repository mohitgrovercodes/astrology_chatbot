# Tiered Rule Analysis: How It Works and How to Customise It

## 1. How tiered rule analysis is done

Tiered rule analysis runs when the user asks for **interpretation or prediction** (RAG_WITH_CALCULATION) and the orchestrator has chart data. It has two main parts: **validation** (pass/fail rules) and **synthesis** (structured analysis for the prompt).

### 1.1 Flow overview

```
User query (e.g. "when will I get married?")
    → Query type detection (marriage | career | finance | health | children | general)
    → Tier selection: determine_validation_tier(query)  →  1 | 2 | 3
    → Load rules: tiered_rules.json (tiers 1–3) + optional indexed_rules.json
    → Filter by query_type and (if index exists) composite index
    → Live-chat filter: severity + cap at 80 rules, skip yoga/combination rules
    → Batch LLM evaluation (VedicValidationEngineV2): each rule’s check_logic vs chart
    → Aggregate: overall_strength, can_proceed, critical_failures
    → Optional: ChartSynthesisEngine.synthesize() for strengths/challenges/yogas/key houses
    → All of this is injected into the final LLM prompt (validation + synthesis blocks)
```

### 1.2 Tier selection (`determine_validation_tier`)

**Location:** `src/orchestration/orchestrator_validation_helpers.py`

- **Tier 3** (most rules): query contains words like `detailed`, `comprehensive`, `thorough`, `complete analysis`, `in-depth`, `everything`.
- **Tier 2**: query contains `explain`, `analyze`, `what does`, `how does`, or has ≥2 `?` and at least one ` and `.
- **Tier 1** (default): everything else. Optimised for fast live chat.

So for a typical short question like “when will I get married?”, the tier is **1** unless the user explicitly asks for a detailed/comprehensive analysis.

### 1.3 Rule loading (how many rules are in each tier)

Rules live in **`optimized/tiered_rules.json`** under `tiers.tier1`, `tiers.tier2`, `tiers.tier3` (and optionally `tier4`). Counts from **`optimized/stats/tier_analysis.json`**:

| Tier | Approx. rules in tier | Typical use |
|------|------------------------|-------------|
| 1    | ~750                  | Fast path; critical only |
| 2    | ~1,750                 | Standard; more coverage |
| 3    | ~8,000                 | Detailed / comprehensive |
| 4    | ~6,000                 | Not used by validation engine (only in stats) |

For a given request the engine does **not** evaluate all rules in the tier. It first narrows by **query type** and optionally **stage**:

1. **With index** (`optimized/indexed_rules.json`):  
   Uses composite keys like `{query_type}_promise`, `{query_type}_timing`, `all_promise`, etc. Only rules that (a) match the index for this query_type/stage and (b) belong to the selected tier(s) 1..tier are loaded. So the **number of rules actually checked** is usually much smaller than the full tier count (e.g. tens to a few hundred, depending on index and query type).

2. **Without index** (fallback):  
   All rules in tiers 1..tier are loaded, then filtered by `applies_to_queries` and optionally `prediction_stage`. That can be up to 750 (tier 1), 2,500 (tier 2), or 8,000+ (tier 3).

### 1.4 Live-chat cap (how many rules are actually evaluated)

**Location:** `src/validation/vedic_validation_engine_v2.py` (inside `validate(..., live_chat=True)`)

When the orchestrator calls the validation engine it uses **`live_chat=True`**. Then:

- Only **critical** and **high** severity rules are kept.
- **Yoga/combination rules are always included** (`include_yoga_live = True`). They are evaluated but their failures are severity-demoted (`critical` → `high`) so “yoga absent” never blocks a prediction.
- The list is **capped at 80 rules** (after sorting by `check_order`).

So **per query, at most 80 rules are evaluated** in the current live-chat path, even if the tier + index would return more.

#### Severity override safeguards (post-evaluation)

The engine applies three layered overrides **after** the LLM returns verdicts, before computing `can_proceed`:

| Category / Pattern | Override applied |
|---|---|
| `yoga`, `combination`, `raja yoga`, `dhana yoga`, … (rule name keywords) | `critical` → `high`; never blocks |
| `category == “table_based_rules”` (house lord lookups, sign lordship tables, Sarvashtakavarga) | `critical` → `high`, `halt_on_failure` cleared |
| “generate navamsa”, “chart not provided”, … (infra/tooling keywords) | `critical` → `high`, `halt_on_failure` cleared |
| `category == “data_integrity”` / `”astronomical_constraint”` | Hard-halt preserved (these are genuine impossibilities) |

This ensures that lookup/reference table rules (4,958 rules, 1,721 of which were tagged `critical+halt`) never cause a false BLOCKED result when the LLM misinterprets a conditional fact as a chart flaw.

### 1.5 Rule evaluation (what “checked” means)

Each selected rule has a **`check_logic`** (condition + optional calculation). The engine:

- Formats chart + rules for the **validation LLM** (from `LLMFactory`, purpose `"validation"`).
- Sends **batches** of rules (batch size 15 in live_chat) to the LLM.
- LLM returns for each rule: **passed** (true/false), **reason**, **recommendation**.
- Results are aggregated into:
  - **overall_strength** (0–10): starts at 10, minus penalties for critical/high/medium failures.
  - **can_proceed**: false if any critical failure remains after severity overrides, or if a “halt” rule fired.
  - **critical_failures** (and high_failures): used for disclaimers and for synthesis.

So “how many rules get checked” = number of rules that pass the tier + index + live_chat filter and are sent to the LLM (currently **at most 80** in live chat).

### 1.6 Synthesis (ChartSynthesisEngine)

After validation, **ChartSynthesisEngine** (if enabled) builds a structured analysis:

- Loads rules from **indexed_rules** (composite index), up to **200** applicable rules, then keeps 10 yoga + 40 non-yoga (50 total) and evaluates them with **pattern-based** logic (no LLM).
- Produces **chart_strengths**, **chart_challenges**, **yogas_detected**, **key_houses**, etc.
- Injects **validation_result** (e.g. strength score, critical_failures) into challenges.

This synthesis is what gets formatted in **`_format_enhanced_analysis`** in the orchestrator and added to the prompt as “ENHANCED CHART ANALYSIS”, “CHART STRENGTHS”, “CHART CHALLENGES”, “KEY HOUSES”, etc., so the answer LLM has a clear picture when “analysis is required”.

---

## 2. How many rules get checked currently (summary)

| Stage | What happens | Approx. count |
|-------|-------------------------------|----------------|
| Tier selection | Query → tier 1 / 2 / 3 | 1 tier per request |
| Rule pool (tier) | tier1 ≈ 750, tier2 ≈ 2500, tier3 ≈ 8000 | Depends on tier |
| After index + query_type | Only rules for that query_type (and stage) in that tier | Often 50–300+ |
| After live_chat filter | Severity critical+high, **yoga rules included**, cap 80 | **At most 80** |
| Batches to LLM | 15 rules per batch | 80 ÷ 15 ≈ 6 batches |
| Severity overrides (post-eval) | yoga/table_based/infra rules demoted; data_integrity rules halt | Applied per rule |
| Synthesis (separate) | Indexed rules, then 50 rules pattern-evaluated | 50 rules (no LLM) |

So in the **current live-chat path**, the number of rules **evaluated by the LLM** is **at most 80** per request. Yoga rules are now always evaluated (improving prediction richness). Table-based lookup rules are evaluated but can never block predictions even if the LLM marks them as failed.

---

## 3. How to customise

### 3.1 Tier selection (when to use tier 2 or 3)

**File:** `src/orchestration/orchestrator_validation_helpers.py`  
**Function:** `determine_validation_tier(query, user_preferences=None)`

- Add/remove keywords for tier 2 or 3.
- Use **user_preferences** (e.g. “always detailed”) to force a higher tier.
- Example: treat “explain in detail” or “full analysis” as tier 2 even without the exact word “detailed”.

### 3.2 Which rules belong to which tier

**File:** `optimized/tiered_rules.json` (generated/curated; see e.g. `scripts/classify_rule_tiers.py` and stats in `optimized/stats/tier_analysis.json`)

- Move rules between `tier1`, `tier2`, `tier3` to change speed vs coverage.
- Tier 1: keep only rules that are essential for safety and “can_proceed”.
- Tier 2/3: add rules that improve explanation quality for “detailed” or “comprehensive” requests.

### 3.3 Index (which rules run for which query type)

**File:** `optimized/indexed_rules.json` (composite index: `query_type_stage` → rule_ids)

- Ensures that for “marriage” only marriage-related rules (and optional “all”) are loaded.
- Rebuild or extend the index when you add new query types or rules so that “how many rules get checked” stays relevant to the question.

### 3.4 Live-chat cap and filters

**File:** `src/validation/vedic_validation_engine_v2.py`  
**In `validate()`:** block starting with `if live_chat:`

- **Cap:** change `applicable = applicable[:80]` to another limit (e.g. 120) for more checks at the cost of latency and API cost.
- **Severity:** change `LIVE_SEVERITIES = {"critical", "high"}` to include `"medium"` if you want more rules evaluated.
- **Yoga inclusion:** `include_yoga_live = True` in the orchestrator — yoga rules are now always included. To revert to the old behaviour (skip yoga rules), change this to `tier > 1` in `orchestrator.py`.
- **table_based_rules protection:** these rules are evaluated but their failures are demoted before `can_proceed` is calculated. Do not add `"table_based_rules"` to `SKIP_IN_LIVE` as they provide useful scoring signal.

### 3.5 Batch size and timeout

**File:** `src/validation/vedic_validation_engine_v2.py`  
**In `validate()`:** `eff_batch = 15 if live_chat else self.batch_size`

- Increase `eff_batch` to reduce number of LLM calls (and latency) at the cost of longer single calls and token usage.
- `timeout_sec` in the orchestrator (currently `None` when calling `validate`) can be set to stop after N seconds and return partial results.

### 3.6 RAG / retrieval vs tier

**File:** `config/rag_config.py`  
**Constants:** `TIER_1_TOP_K`, `TIER_2_TOP_K`, `TIER_3_TOP_K`, `TIER_4_TOP_K`

- These control **retrieval** top_k when a validation tier is passed to `get_top_k(validation_tier=N)`. They do **not** change how many validation rules are evaluated; they change how many RAG chunks are fetched when using tier-aware retrieval.

### 3.7 Synthesis rule count

**File:** `src/validation/chart_synthesis_engine.py`  
**In `synthesize()`:** `max_rules=200`, then `yoga_rules[:10] + non_yoga_rules[:40]`

- Increase 200 to consider more rules from the index; increase 10/40 to allow more yogas and non-yoga factors in the synthesis block (and thus in the prompt).

---

## 4. Suggestions for how the chatbot answers when analysis is required

### 4.1 Keep validation and synthesis in the driver’s seat

- **Validation** (overall_strength, can_proceed, critical_failures) should drive:
  - Whether to answer at all (hard halt) or add a disclaimer (soft).
  - Wording like “your chart shows moderate strength for this area” vs “several challenging factors”.
- **Synthesis** (chart_strengths, chart_challenges, yogas_detected, key_houses) should drive:
  - Which factors the model is **instructed** to prioritise (already in `_format_enhanced_analysis` and ENGINE USAGE GUIDELINES).
- Ensure the final prompt **always** includes the validation block (e.g. strength, can_proceed, critical_failures) and the synthesis block when available, so the model does not “guess” from raw positions.

### 4.2 Make “analysis required” explicit in the prompt

- When the user asks for “detailed” or “full” analysis, the prompt should state that they requested a **detailed** response and that the model must use **all** provided analysis sections (key houses, yogas, strengths, challenges, validation summary).
- The existing **response_mode** (initial / detailed / followup) and length instructions already help; tying “detailed” to **tier 2 or 3** ensures more rules (and, if you raise the live-chat cap for tier 2/3, more evaluated rules) so the analysis is richer.

### 4.3 Prefer synthesis over raw chart dumps

- The answer should be grounded in **ENHANCED CHART ANALYSIS** (synthesis + validation) first, and only then in raw chart/dasha/transit data. That reduces hallucination and keeps answers consistent with the rule engine.
- In ENGINE USAGE GUIDELINES, you already tell the model to use house lords, yogas, divisional charts, dasha, etc.; reinforcing “use the CHART STRENGTHS and CHART CHALLENGES sections as the main summary” keeps analysis coherent.

### 4.4 Use tier to match depth to request

- **Tier 1:** Short, headline answer; 80 rules is enough for safety and a reasonable headline.
- **Tier 2 / 3:** When the user asks for “explain”, “analyze”, “detailed”, “comprehensive”, use tier 2 or 3 so more rules are in the pool; consider **raising the live-chat cap** (e.g. 120 or 150) for tier 2/3 so the model has more passed/failed signals to summarise. That way “analysis required” gets more substance without changing the pipeline.

### 4.5 Disclaimers and critical failures

- When **overall_strength** is low or there are **critical_failures**, the prompt already gets a disclaimer and the model is instructed to acknowledge limitations. Keep that behaviour so that when analysis is required but the chart is weak, the bot is honest and still uses the structured analysis (challenges, key houses) rather than sounding generic.

### 4.6 Optional: separate “analysis-only” path

- For queries like “analyse my chart for marriage” (no “when”), you could run **synthesis + validation** as now but emphasise in the prompt that the reply should be **analytical** (strengths, challenges, key houses, yogas) and only briefly mention timing. That keeps “analysis” distinct from “prediction” and avoids the model over-promising dates when the user only asked for analysis.

---

## 5. Quick reference

| What you want to change | Where to look |
|-------------------------|----------------|
| When tier 2/3 is used | `orchestrator_validation_helpers.determine_validation_tier` |
| Which rules exist per tier | `optimized/tiered_rules.json`, `optimized/stats/tier_analysis.json` |
| Which rules run per query type | `optimized/indexed_rules.json` (composite index) |
| Max rules evaluated (live chat) | `vedic_validation_engine_v2.validate` → `live_chat` block → cap 80, severity, SKIP_IN_LIVE |
| Batch size / timeout | `vedic_validation_engine_v2.validate` (eff_batch, timeout_sec) |
| What goes into the answer as “analysis” | `_format_enhanced_analysis` (orchestrator) + synthesis + validation_context |
| Synthesis rule count | `chart_synthesis_engine.synthesize` (max_rules, yoga/non-yoga caps) |
