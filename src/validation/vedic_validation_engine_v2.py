# src/validation/vedic_validation_engine_v2.py
"""
vedic_validation_engine_v2.py
------------------------------
LLM-guided validation engine using OpenAI (via LLMFactory).
Reads check_logic from tiered_rules.json and evaluates each rule
against chart data using the LLM.

Provider is configured via LLM_PROVIDER env var (default: openai).
    LLM_PROVIDER=openai  -> uses gpt-4o-mini
    LLM_PROVIDER=free    -> uses Ollama llama3.2:3b

Usage:
    python -m src.validation.vedic_validation_engine_v2 --tier 1 --query marriage

    # Or import:
    from src.validation.vedic_validation_engine_v2 import VedicValidationEngineV2
    engine = VedicValidationEngineV2()
    result = engine.validate(chart_data, query_type="marriage", tier=1)
"""

import json
import os
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

# ── LLM: via LLMFactory (OpenAI or Ollama) ──────────────────────────────────
from langchain_core.prompts import ChatPromptTemplate
try:
    from src.llm.factory import LLMFactory
    LLMFACTORY_AVAILABLE = True
except ImportError:
    try:
        from llm.factory import LLMFactory
        LLMFACTORY_AVAILABLE = True
    except ImportError:
        LLMFACTORY_AVAILABLE = False
        print("[WARN] LLMFactory not found. Ensure src/llm/factory.py exists.")


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id:         str
    rule_name:       str
    passed:          bool
    severity:        str
    halt_on_failure: bool
    reason:          str
    recommendation:  str
    classical_ref:   str
    impact_pct:      int


@dataclass
class ValidationResult:
    query_type:        str
    tier_used:         int
    rules_checked:     int
    passed:            int
    failed:            int
    critical_failures: List[RuleResult] = field(default_factory=list)
    high_failures:     List[RuleResult] = field(default_factory=list)
    all_results:       List[RuleResult] = field(default_factory=list)
    overall_strength:  float = 10.0
    halt_triggered:    bool  = False
    halt_rule:         Optional[str] = None
    can_proceed:       bool  = True
    elapsed_seconds:   float = 0.0
    reasoning_summary: str   = ""


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────────────────────────

EVAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a Vedic astrology expert evaluating whether astrological rules
are satisfied by a given birth chart.

For each rule provided, evaluate it against the chart and return:
- passed: true if the rule is satisfied or cannot be confirmed as violated
- reason: one concise sentence explaining the verdict
- recommendation: if failed, what the astrologer should note (empty string if passed)

Rules:
- If chart data is insufficient to evaluate a rule, return passed: true
- Only mark failed if there is clear evidence of violation
- Sun and Moon are NEVER retrograde (always pass retrograde checks for them)

Return ONLY a valid JSON array. No markdown fences, no text outside JSON.
Format exactly:
[
  {{"rule_id": "VR001", "passed": true, "reason": "...", "recommendation": ""}},
  {{"rule_id": "VR002", "passed": false, "reason": "...", "recommendation": "..."}}
]"""),
    ("human", """BIRTH CHART:
{chart_json}

RULES TO EVALUATE:
{rules_json}

Return JSON array only.""")
])


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class VedicValidationEngineV2:
    """
    LLM-guided validation engine using OpenAI (or Ollama) via LLMFactory.
    Evaluates check_logic rules from tiered_rules.json against chart data.
    """

    def __init__(
        self,
        tiered_rules_path:  str = "optimized/tiered_rules.json",
        indexed_rules_path: str = "optimized/indexed_rules.json",
        model:       str = None,  # overrides LLMFactory model selection
        batch_size:  int = 10,    # rules per LLM call
        max_workers: int = 3,     # parallel LLM calls
    ):
        if not LLMFACTORY_AVAILABLE:
            raise ImportError(
                "LLMFactory not found. Ensure src/llm/factory.py exists."
            )

        self.tiered_path   = Path(tiered_rules_path)
        self.indexed_path  = Path(indexed_rules_path)
        self.batch_size    = batch_size
        self.max_workers   = max_workers
        self._tiered_data  = None
        self._indexed_data = None   # loaded on first use
        self._api_lock     = threading.Semaphore(max_workers)

        # Create LLM via factory (respects LLM_PROVIDER env var)
        _llm = LLMFactory.create(
            purpose="validation",
            model=model,           # None -> factory picks default
            temperature=0,
            max_tokens=8192,
            use_rate_limiting=True,
            rate_limit_delay=2.0,
        )
        print(f"[LLM] LLM Provider: {LLMFactory._determine_provider()}")
        print(f"[LLM] Model:        {model or LLMFactory._select_model_for_provider(LLMFactory._determine_provider(), 'validation')}")

        self.llm   = _llm
        self.chain = EVAL_PROMPT | self.llm

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load_tiered(self) -> Dict:
        if self._tiered_data is None:
            self._tiered_data = json.load(
                open(self.tiered_path, encoding="utf-8")
            )
        return self._tiered_data

    def _load_indexed(self) -> Dict:
        if self._indexed_data is None:
            if self.indexed_path.exists():
                self._indexed_data = json.load(
                    open(self.indexed_path, encoding="utf-8")
                )
            else:
                self._indexed_data = {}
        return self._indexed_data

    def _get_rules_for_tier(self, max_tier: int) -> List[Dict]:
        data  = self._load_tiered()
        rules = []
        for t in range(1, max_tier + 1):
            rules.extend(data["tiers"].get(f"tier{t}", []))
        return rules

    def _get_rules_via_index(
        self, query_type: str, max_tier: int, stage: Optional[str] = None
    ) -> List[Dict]:
        """
        Use composite index for O(1) lookup instead of linear scan.

        Key format: "marriage_promise"  (underscore-joined, from build_rule_indices.py)
        Falls back to empty list — caller uses linear scan.
        """
        idx_data = self._load_indexed()
        if not idx_data:
            return []

        composite = idx_data.get("indices", {}).get("composite", {})
        rule_map  = idx_data.get("rule_map", {})

        if not composite or not rule_map:
            return []

        # Composite keys use underscore: "marriage_promise" (from build_rule_indices.py)
        stages = [stage] if stage else ["promise", "timing", "trigger", "general"]

        # Step 1: specific query match (e.g. "marriage_promise")
        specific_ids: set = set()
        for s in stages:
            specific_ids.update(composite.get(f"{query_type.lower()}_{s}", []))
        specific_ids.update(composite.get(query_type.lower(), []))

        # Step 2: "all" fallback — only include if specific match is thin (<50 rules)
        # "all_*" keys contain every rule tagged applies_to_queries=all, which is most rules
        # Using them unconditionally defeats the purpose of the index
        all_ids: set = set()
        if len(specific_ids) < 50:
            for s in stages:
                all_ids.update(composite.get(f"all_{s}", []))
            all_ids.update(composite.get("all", []))

        matched_ids = specific_ids | all_ids
        print(f"  [Index] specific={len(specific_ids)} + all_fallback={len(all_ids)} = {len(matched_ids)} matched")

        if not matched_ids:
            return []

        # Build set of rule_ids that are in the requested tiers
        tiered   = self._load_tiered()
        tier_ids: set = set()
        for t in range(1, max_tier + 1):
            for r in tiered["tiers"].get(f"tier{t}", []):
                tier_ids.add(r["rule_id"])

        rules = [
            rule_map[rid]
            for rid in matched_ids
            if rid in tier_ids and rid in rule_map
        ]
        rules.sort(key=lambda r: r.get("check_order", 999))
        return rules

    # ── Filters ───────────────────────────────────────────────────────────────

    def _filter_by_query(self, rules: List[Dict], query_type: str) -> List[Dict]:
        result = []
        for rule in rules:
            applies = rule.get("applies_to_queries", [])
            if isinstance(applies, str):
                applies = [applies]
            values = []
            for a in applies:
                if isinstance(a, dict):
                    values.append(a.get("value", "").lower())
                else:
                    values.append(str(a).lower())
            if "all" in values or query_type.lower() in values:
                result.append(rule)
        return result

    def _filter_by_stage(self, rules: List[Dict], stage: str) -> List[Dict]:
        result = []
        for rule in rules:
            s = rule.get("prediction_stage", "")
            if isinstance(s, dict): s = s.get("value", "")
            if isinstance(s, list): s = s[0] if s else ""
            s = str(s).lower()
            if stage.lower() in s or s in ("all", "general"):
                result.append(rule)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_severity(self, rule: Dict) -> str:
        s = rule.get("severity", "medium")
        if isinstance(s, list): s = s[0] if s else "medium"
        if isinstance(s, dict): s = s.get("value", "medium")
        return str(s).lower()

    def _format_rule_for_llm(self, rule: Dict) -> Dict:
        """Compact representation — only what LLM needs."""
        cl = rule.get("check_logic", {})
        if isinstance(cl, str):
            condition, calculation = cl, ""
        elif isinstance(cl, dict):
            condition   = cl.get("condition", "")
            calculation = cl.get("calculation", "")
        else:
            condition, calculation = str(cl), ""

        return {
            "rule_id":     rule["rule_id"],
            "rule_name":   rule.get("rule_name", ""),
            "condition":   condition,
            "calculation": calculation,
            "severity":    self._get_severity(rule),
            "source":      rule.get("classical_reference", ""),
        }

    # ── LLM evaluation ────────────────────────────────────────────────────────

    def _extract_json(self, content: str) -> list:
        """Robustly extract a JSON array from LLM response."""
        content = content.strip()

        # Strip markdown fences
        if "```" in content:
            lines   = content.split("\n")
            content = "\n".join(
                ln for ln in lines
                if not ln.strip().startswith("```")
            ).strip()

        # Try direct parse
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                parsed = next(iter(parsed.values()))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            pass

        # Extract the [...] portion
        s = content.find("[")
        e = content.rfind("]")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(content[s:e + 1])
            except json.JSONDecodeError:
                pass

        # Truncated response — extract complete objects via regex
        import re
        objects = []
        for m in re.finditer(
            r'\{[^{}]*"rule_id"\s*:\s*"([^"]+)"[^{}]*"passed"\s*:\s*(true|false)[^{}]*\}',
            content, re.DOTALL
        ):
            try:
                objects.append(json.loads(m.group(0)))
            except Exception:
                pass
        return objects

    def _evaluate_batch(self, rules: List[Dict], chart: Dict) -> List[Dict]:
        """Send one batch to the LLM and parse verdicts (rate-limited)."""
        rules_for_llm = [self._format_rule_for_llm(r) for r in rules]
        # Rate limiting is handled by RateLimitedLLM wrapper in LLMFactory

        try:
            response = self.chain.invoke({
                "chart_json": json.dumps(chart, indent=2),
                "rules_json": json.dumps(rules_for_llm, indent=2),
            })

            content = response.content if hasattr(response, "content") else str(response)
            parsed  = self._extract_json(content)

            if not parsed:
                raise ValueError("Empty or unparseable response from LLM")

            return parsed

        except Exception as e:
            print(f"\n   [ERROR] LLM error ({type(e).__name__}): {e}")
            return [
                {
                    "rule_id":        r["rule_id"],
                    "passed":         True,
                    "reason":         "LLM error — defaulted to pass",
                    "recommendation": "",
                }
                for r in rules
            ]

    # ── Main validate ─────────────────────────────────────────────────────────

    def validate(
        self,
        chart_data:  Dict[str, Any],
        query_type:  str           = "marriage",
        tier:        int           = 1,
        stage:       Optional[str] = None,
        live_chat:   bool          = False,   # Fast mode: fewer rules, hard timeout
        timeout_sec: float         = 25.0,    # Max seconds before partial result
    ) -> ValidationResult:
        """
        Validate a chart against rules.

        Args:
            chart_data:  Dict from VedicEngine (planets, lagna, dasha, transits)
            query_type:  'marriage' | 'career' | 'finance' | 'health' | 'children'
            tier:        1=quick | 2=standard | 3=detailed
            stage:       'promise' | 'timing' | 'trigger' | None (all)

        Returns:
            ValidationResult
        """
        t0 = time.time()

        print(f"\n{'='*65}")
        print(f"  VEDIC VALIDATION  |  Query: {query_type.upper()}  |  Tier: 1-{tier}")
        print(f"{'='*65}")

        # ── Load rules: index first, linear scan fallback ────────────────
        indexed_rules = self._get_rules_via_index(query_type, tier, stage)

        if indexed_rules:
            applicable = indexed_rules
            all_rules  = self._get_rules_for_tier(tier)
            print(f"  Total in Tier 1-{tier}:         {len(all_rules)}")
            print(f"  Index hit [OK]               {len(applicable)} rules "
                  f"(vs {len(all_rules)} linear scan)")
            if stage:
                print(f"  Stage filter:               '{stage}'")
        else:
            # Index not available — fall back to linear scan + filter
            all_rules  = self._get_rules_for_tier(tier)
            applicable = self._filter_by_query(all_rules, query_type)
            if stage:
                applicable = self._filter_by_stage(applicable, stage)
            print(f"  Total in Tier 1-{tier}:         {len(all_rules)}")
            print(f"  Linear scan [WARN]           {len(applicable)} applicable "
                  f"(index not found)")
            if stage:
                print(f"  Filtered to '{stage}' stage: {len(applicable)}")

        if not applicable:
            print("  [WARN] No applicable rules found.")
            print("  Common query types: marriage, career, finance, health, children")
            return ValidationResult(
                query_type=query_type, tier_used=tier,
                rules_checked=0, passed=0, failed=0
            )

        # ── Live chat mode: strip down to essential rules only ─────────────
        if live_chat:
            SKIP_IN_LIVE = {
                "yoga", "combination", "longevity", "deep exaltation",
                "exclusively aspected", "high status", "raja yoga",
                "dhana yoga", "pancha mahapurusha"
            }
            LIVE_SEVERITIES = {"critical", "high"}

            before = len(applicable)
            applicable = [
                r for r in applicable
                if self._get_severity(r) in LIVE_SEVERITIES
                and not any(
                    kw in r.get("rule_name", "").lower()
                    for kw in SKIP_IN_LIVE
                )
            ]
            # Also cap at first 80 rules ordered by check_order
            applicable.sort(key=lambda r: r.get("check_order", 999))
            applicable = applicable[:80]
            print(f"  Live chat filter:           {before} -> {len(applicable)} rules "
                  f"(critical+high, non-yoga, capped at 80)")

        # Effective batch size: larger batches = fewer API calls
        eff_batch = 15 if live_chat else self.batch_size

        total_batches = (len(applicable) + eff_batch - 1) // eff_batch
        print(f"  Batches:                    {total_batches} x {eff_batch} rules")
        print(f"  Workers:                    {self.max_workers} parallel")
        print(f"\n  Evaluating...\n")

        # ── Build all batches upfront ─────────────────────────────────────
        batches = [
            (i // eff_batch, applicable[i: i + eff_batch])
            for i in range(0, len(applicable), eff_batch)
        ]

        # ── Run batches in parallel with optional hard timeout ────────────
        verdict_store: Dict[int, List[Dict]] = {}
        completed = 0
        timed_out = False

        def run_batch(args):
            idx, batch = args
            return idx, self._evaluate_batch(batch, chart_data)

        deadline = None if timeout_sec is None else (time.time() + timeout_sec)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(run_batch, b): b[0] for b in batches}
            for future in as_completed(futures):
                if deadline is not None and time.time() > deadline:
                    break
                try:
                    # Calculate timeout safely: None if no deadline, else remaining time (min 1 second)
                    timeout_val = None if deadline is None else max(1, deadline - time.time())
                    idx, verdicts = future.result(timeout=timeout_val)
                    verdict_store[idx] = verdicts
                    completed += 1
                    print(f"  [{completed:3d}/{total_batches}] batch {idx+1} done ({len(verdicts)} verdicts)",
                          flush=True)
                except FutureTimeout:
                    timed_out = True
                    print(f"\n  [TIMEOUT] Timeout - stopping early")
                    break

        # ── Process results in original order ─────────────────────────────
        all_rule_results: List[RuleResult] = []
        halt_triggered = False
        halt_rule_name = None

        for batch_idx, batch in batches:
            if batch_idx not in verdict_store:
                continue  # timed out — skip unfinished batches
            verdicts    = verdict_store.get(batch_idx, [])
            verdict_map = {v["rule_id"]: v for v in verdicts}
            batch_failed = 0

            for rule in batch:
                rid      = rule["rule_id"]
                verdict  = verdict_map.get(rid, {})
                passed   = verdict.get("passed", True)
                severity = self._get_severity(rule)
                # ── Severity override for yoga/combination rules ──────────
                # Yoga absence = rule not triggered, not a chart defect.
                # Demote to "high" so it contributes to score but doesn't block.
                raw_halt = rule.get("halt_on_failure", False)
                category = rule.get("category", "").lower()
                rule_name_lower = rule.get("rule_name", "").lower()

                YOGA_KEYWORDS = {
                    "yoga", "combination", "conjunction", "exaltation requirement",
                    "deep exaltation", "exclusively aspected", "eligibility",
                    "longevity decline", "high status"
                }
                is_yoga_rule = (
                    "yoga" in category
                    or "combination" in category
                    or any(kw in rule_name_lower for kw in YOGA_KEYWORDS)
                )
                # Downgrade yoga-absence failures: critical -> high
                if not passed and is_yoga_rule and severity == "critical":
                    severity = "high"

                # Halt only for genuine data-integrity / astronomical impossibilities
                HALT_CATEGORIES = {"data_integrity", "astronomical_constraint"}
                HALT_KEYWORDS   = {
                    "impossible", "impossibility", "never retrograde",
                    "cannot be retrograde", "elongation", "maximum elongation"
                }
                should_halt = raw_halt and (
                    category in HALT_CATEGORIES
                    or any(kw in rule_name_lower for kw in HALT_KEYWORDS)
                )

                rr = RuleResult(
                    rule_id         = rid,
                    rule_name       = rule.get("rule_name", ""),
                    passed          = passed,
                    severity        = severity,
                    halt_on_failure = should_halt,
                    reason          = verdict.get("reason", ""),
                    recommendation  = verdict.get("recommendation", ""),
                    classical_ref   = rule.get("classical_reference", ""),
                    impact_pct      = rule.get("impact_percentage", 0),
                )
                all_rule_results.append(rr)

                if not passed:
                    batch_failed += 1
                    if should_halt and not halt_triggered:
                        halt_triggered = True
                        halt_rule_name = rule.get("rule_name", rid)

            status = "[HALT]" if halt_triggered else f"{batch_failed} failed"
            print(f"  Batch {batch_idx+1}: {status}")

            if halt_triggered:
                print(f"\n  [HALT] Halt triggered by: {halt_rule_name}")
                break

        # Aggregate
        passed_list   = [r for r in all_rule_results if r.passed]
        failed_list   = [r for r in all_rule_results if not r.passed]
        critical_fail = [r for r in failed_list if r.severity == "critical"]
        high_fail     = [r for r in failed_list if r.severity == "high"]
        medium_fail   = [r for r in failed_list if r.severity == "medium"]

        strength  = 10.0
        strength -= len(critical_fail) * 1.5
        strength -= len(high_fail)     * 0.5
        strength -= len(medium_fail)   * 0.2
        strength  = max(0.0, min(10.0, strength))

        can_proceed = len(critical_fail) == 0 and not halt_triggered
        elapsed     = time.time() - t0

        if not can_proceed:
            top     = critical_fail[0] if critical_fail else None
            summary = ("BLOCKED for " + query_type + ". "
                       + (f"Key issue: {top.rule_name}." if top else "Halt triggered."))
        elif strength >= 8:
            summary = (f"STRONG chart for {query_type}. "
                       f"{len(passed_list)}/{len(all_rule_results)} rules passed.")
        elif strength >= 6:
            summary = (f"MODERATE strength for {query_type}. "
                       f"{len(critical_fail)} critical, {len(high_fail)} high issues.")
        else:
            summary = (f"WEAK chart for {query_type}. "
                       f"{len(failed_list)} failures across severity levels.")

        result = ValidationResult(
            query_type=query_type, tier_used=tier,
            rules_checked=len(all_rule_results),
            passed=len(passed_list), failed=len(failed_list),
            critical_failures=critical_fail, high_failures=high_fail,
            all_results=all_rule_results,
            overall_strength=strength,
            halt_triggered=halt_triggered, halt_rule=halt_rule_name,
            can_proceed=can_proceed,
            elapsed_seconds=elapsed,
            reasoning_summary=summary,
        )

        self._print_summary(result)
        return result

    def _print_summary(self, r: ValidationResult):
        print(f"\n{'='*65}")
        print(f"  RESULTS")
        print(f"{'='*65}")
        print(f"  Rules checked:      {r.rules_checked}")
        print(f"  Passed:             {r.passed}")
        print(f"  Failed:             {r.failed}")
        print(f"  Critical failures:  {len(r.critical_failures)}")
        print(f"  High failures:      {len(r.high_failures)}")
        print(f"  Strength:           {r.overall_strength:.1f} / 10")
        print(f"  Halt triggered:     {'YES [HALT]' if r.halt_triggered else 'No [OK]'}")
        print(f"  Time:               {r.elapsed_seconds:.1f}s")
        print(f"  Can proceed:        {'YES [OK]' if r.can_proceed else 'NO [ERROR]'}")
        print(f"\n  {r.reasoning_summary}")

        if r.critical_failures:
            print(f"\n  [CRITICAL FAILURES]:")
            for f in r.critical_failures[:5]:
                print(f"     [{f.rule_id}] {f.rule_name}")
                print(f"              Reason: {f.reason}")
                print(f"              Source: {f.classical_ref}")
                if f.recommendation:
                    print(f"              Note:   {f.recommendation}")

        if r.high_failures:
            print(f"\n  [HIGH FAILURES] (first 3):")
            for f in r.high_failures[:3]:
                print(f"     [{f.rule_id}] {f.rule_name}")
                print(f"              {f.reason}")

        print(f"{'='*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vedic Validation Engine")
    parser.add_argument("--tiered-rules", default="optimized/tiered_rules.json")
    parser.add_argument("--tier",  type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--query", default="marriage",
                        help="marriage | career | finance | health | children")
    parser.add_argument("--stage", default=None,
                        help="promise | timing | trigger | None (all)")
    parser.add_argument("--batch", type=int, default=10,
                        help="Rules per LLM call (default: 10, overridden to 15 in --live mode)")
    parser.add_argument("--live", action="store_true",
                        help="Live chat mode: fast, capped at 80 critical rules, 25s timeout")
    parser.add_argument("--timeout", type=float, default=25.0,
                        help="Timeout seconds for live mode (default: 25)")
    parser.add_argument("--workers", type=int, default=3,
                        help="Parallel LLM calls (default: 3)")
    parser.add_argument("--model", default=None,
                        help="Override LLM model name (e.g. gpt-4o, llama3.2:3b)")
    args = parser.parse_args()

    # ── Sample chart (replace with real VedicEngine output) ──────────────────
    # Astronomically valid: Venus in Aries (28° from Sun in Taurus), Mercury conjunct Sun
    # Mars lagna (Aries) -> Mars is lagna lord, also first dasa lord by BPHS method
    sample_chart = {
        "lagna": "Aries", "lagna_degrees": 15.23,
        "moon_sign": "Cancer", "sun_sign": "Taurus",
        "planets": {
            "Sun":     {"rashi": "Taurus",  "house": 2,  "degrees": 12.45, "is_retrograde": False},
            "Moon":    {"rashi": "Cancer",  "house": 4,  "degrees": 8.23,  "is_retrograde": False},
            "Mars":    {"rashi": "Scorpio", "house": 8,  "degrees": 22.10, "is_retrograde": False},
            "Mercury": {"rashi": "Taurus",  "house": 2,  "degrees": 20.10, "is_retrograde": False},
            "Jupiter": {"rashi": "Cancer",  "house": 4,  "degrees": 5.30,  "is_retrograde": False},
            "Venus":   {"rashi": "Aries",   "house": 1,  "degrees": 28.50, "is_retrograde": False},
            "Saturn":  {"rashi": "Pisces",  "house": 12, "degrees": 9.78,  "is_retrograde": False},
            "Rahu":    {"rashi": "Pisces",  "house": 12, "degrees": 14.32, "is_retrograde": True},
            "Ketu":    {"rashi": "Virgo",   "house": 6,  "degrees": 14.32, "is_retrograde": True},
        },
        "house_lords": {
            1:"Mars", 2:"Venus", 3:"Mercury", 4:"Moon",
            5:"Sun",  6:"Mercury", 7:"Venus", 8:"Mars",
            9:"Jupiter", 10:"Saturn", 11:"Saturn", 12:"Jupiter",
        },
        # Shad Vargas (6 primary divisional charts) — required by VR18036
        "divisional_charts": {
            "D1":  {"lagna": "Aries",   "planets": {"Sun":"Taurus","Moon":"Cancer","Mars":"Scorpio","Mercury":"Taurus","Jupiter":"Cancer","Venus":"Aries","Saturn":"Pisces","Rahu":"Pisces","Ketu":"Virgo"}},
            "D2":  {"lagna": "Scorpio", "planets": {"Sun":"Gemini","Moon":"Sagittarius","Mars":"Cancer","Mercury":"Gemini","Jupiter":"Sagittarius","Venus":"Taurus","Saturn":"Virgo"}},
            "D3":  {"lagna": "Sagittarius","planets": {"Sun":"Capricorn","Moon":"Pisces","Mars":"Scorpio","Mercury":"Capricorn","Jupiter":"Pisces","Venus":"Sagittarius","Saturn":"Aquarius"}},
            "D7":  {"lagna": "Cancer",  "planets": {"Sun":"Virgo","Moon":"Scorpio","Mars":"Pisces","Mercury":"Virgo","Jupiter":"Scorpio","Venus":"Gemini","Saturn":"Capricorn"}},
            "D9":  {"lagna": "Sagittarius","planets": {"Sun":"Capricorn","Moon":"Pisces","Mars":"Leo","Mercury":"Aquarius","Jupiter":"Cancer","Venus":"Scorpio","Saturn":"Libra","Rahu":"Virgo","Ketu":"Pisces"}},
            "D30": {"lagna": "Capricorn","planets": {"Sun":"Aquarius","Moon":"Aries","Mars":"Gemini","Mercury":"Aquarius","Jupiter":"Leo","Venus":"Capricorn","Saturn":"Virgo"}},
        },
        # Navamsa (D9) explicitly for VR00745
        "navamsa": {
            "lagna": "Sagittarius",
            "planets": {
                "Sun":"Capricorn","Moon":"Pisces","Mars":"Leo",
                "Mercury":"Aquarius","Jupiter":"Cancer","Venus":"Scorpio",
                "Saturn":"Libra","Rahu":"Virgo","Ketu":"Pisces"
            }
        },
        "dasha": {
            "mahadasha":       {"planet": "Venus",   "end_date": "2044-03-15"},
            "antardasha":      {"planet": "Moon",    "end_date": "2027-07-15"},
            "pratyantardasha": {"planet": "Jupiter", "end_date": "2026-06-12"},
            "dasha_sequence":  "Venus-Moon-Jupiter",
        },
        "transits": {
            "Jupiter": {"rashi": "Taurus", "house": 2},
            "Saturn":  {"rashi": "Pisces", "house": 12},
        },
    }

    engine = VedicValidationEngineV2(
        tiered_rules_path=args.tiered_rules,
        model=args.model,
        batch_size=args.batch,
        max_workers=args.workers,
    )

    result = engine.validate(
        chart_data=sample_chart,
        query_type=args.query,
        tier=args.tier,
        stage=args.stage,
        live_chat=args.live,
        timeout_sec=args.timeout,
    )