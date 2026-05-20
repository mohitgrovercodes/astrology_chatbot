# src/eval/runner.py
"""
Multi-turn eval runner.

For each scenario in golden_scenarios.yaml:
  1. POST /api/v1/chat/initialize with the scenario's user_profile
  2. Walk the conversation turn-by-turn against /api/v1/chat/message
  3. After each user turn, capture the assistant response + metadata.eval
     telemetry, then build a CheckContext and run all deterministic checks
     plus the LLM judge
  4. Compute a per-scenario aggregate score

Requirements:
  - Live server running at BASE_URL (default http://localhost:6262)
  - Server started with EVAL_TELEMETRY=1 so metadata["eval"] is populated
  - Valid X-API-Key
  - GCP creds for LLM judge calls (uses LLMFactory)

Scenario YAML schema this expects:
  scenarios:
    - id: <stable id>
      tags: [domain, language, tone, phase, ...]
      user_profile: {name, date_of_birth, time_of_birth, place_of_birth, ...}
      chart_context: |  (optional; informational only)
      conversation:
        - {role: user,      text: "..."}
        - {role: assistant, text: "..."}        # golden reference for tone
        ...

Multi-turn behavior: every user turn in the conversation is sent. Each turn's
assistant response is scored INDEPENDENTLY (so a single scenario produces N
turn-level scores plus a scenario-level aggregate).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import yaml

from src.eval.metrics import (
    CheckResult,
    judge_response_tone,
    run_deterministic_checks,
)
from src.eval.metrics.deterministic import (
    CheckContext,
    infer_expected_domain,
    infer_expected_language,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EvalConfig:
    base_url: str = "http://localhost:6262"
    api_key: str = "test_api_key"
    scenarios_path: str = "data/golden_scenarios.yaml"
    init_timeout_s: int = 30
    message_timeout_s: int = 180
    ids: Optional[List[str]] = None     # if set, only run these scenarios
    tags: Optional[List[str]] = None    # if set, only scenarios with ANY of these tags
    enable_llm_judge: bool = True
    pass_threshold: float = 0.70        # scenario passes if final_score >= this
    verbose: bool = True

    @property
    def headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────────────────────
# Scenario loading + filtering
# ──────────────────────────────────────────────────────────────────────────────

def load_scenarios(path: str = "data/golden_scenarios.yaml") -> List[Dict[str, Any]]:
    """Read scenarios from YAML and return the list (or raise if file missing)."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    scenarios = data.get("scenarios", []) if isinstance(data, dict) else []
    if not scenarios:
        raise ValueError(f"No scenarios found in {path}")
    return scenarios


def filter_scenarios(
    scenarios: List[Dict[str, Any]],
    ids: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    out = scenarios
    if ids:
        ids_set = set(ids)
        out = [s for s in out if s.get("id") in ids_set]
    if tags:
        tags_set = set(tags)
        out = [s for s in out if tags_set.intersection(s.get("tags", []))]
    return out


# ──────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────────────────────

def _initialize_session(cfg: EvalConfig, user_id: str, profile: Dict[str, Any]) -> Tuple[bool, str]:
    payload = {
        "user_id": user_id,
        "user_profile": {**profile, "user_id": user_id},
        "conversation_history": [],
    }
    try:
        r = requests.post(
            f"{cfg.base_url}/api/v1/chat/initialize",
            json=payload, headers=cfg.headers, timeout=cfg.init_timeout_s,
        )
        if r.status_code in (200, 201):
            return True, ""
        body = r.text[:300]
        return False, f"HTTP {r.status_code}: {body}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _send_message(cfg: EvalConfig, user_id: str, question: str) -> Dict[str, Any]:
    payload = {"user_id": user_id, "question": question}
    try:
        r = requests.post(
            f"{cfg.base_url}/api/v1/chat/message",
            json=payload, headers=cfg.headers, timeout=cfg.message_timeout_s,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": f"timeout after {cfg.message_timeout_s}s"}
    except requests.exceptions.HTTPError as exc:
        return {"error": f"http_error: {exc.response.status_code}", "body": exc.response.text[:300]}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _health_check(cfg: EvalConfig) -> bool:
    try:
        r = requests.get(f"{cfg.base_url}/api/v1/health", headers=cfg.headers, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Per-turn scoring
# ──────────────────────────────────────────────────────────────────────────────

def _user_tone_from_tags(tags: List[str]) -> str:
    for t in ("anxious", "frustrated", "worried", "hopeful", "excited",
              "neutral", "casual", "concerned"):
        if t in tags:
            return t
    return "neutral"


def _phase_for_turn(turn_index: int, total_user_turns: int) -> str:
    """
    Crude phase prediction for golden scenarios that don't annotate it.
    First turn: INITIAL. Subsequent turns (which are usually follow-ups):
      - if total is 2, the second is AWAITING_DETAIL
      - if total > 2, alternate FOLLOWUP_LOOP / AWAITING_DETAIL
    """
    if turn_index == 0:
        return "INITIAL"
    if turn_index == 1:
        return "AWAITING_DETAIL"
    # Beyond the first follow-up we just lean on telemetry; scorer reads the
    # actual phase from conversation_phase in metadata
    return "FOLLOWUP_LOOP"


def _build_check_context(
    scenario: Dict[str, Any],
    user_message: str,
    assistant_response: str,
    metadata: Dict[str, Any],
    turn_index: int,
    prior_phase: Optional[str],
    total_user_turns: int,
) -> CheckContext:
    tags = scenario.get("tags", [])
    eval_meta = (metadata or {}).get("eval") or {}
    validation_diag = (metadata or {}).get("validation_diagnostics") or {}
    accuracy_gate = (metadata or {}).get("accuracy_gate") or {}

    return CheckContext(
        scenario_id=scenario.get("id", "unknown"),
        scenario_tags=tags,
        expected_domain=infer_expected_domain(tags),
        expected_language=infer_expected_language(tags),
        expected_phase=_phase_for_turn(turn_index, total_user_turns),
        user_message=user_message,
        assistant_response=assistant_response,
        semantic_frame=eval_meta.get("semantic_frame", {}),
        accuracy_gate=accuracy_gate,
        accuracy_gate_fired=bool(eval_meta.get("accuracy_gate_fired")),
        focus_factors=eval_meta.get("focus_factors", []) or [],
        conversation_phase=eval_meta.get("conversation_phase", {}) or {},
        response_timing_windows=eval_meta.get("response_timing_windows", []) or [],
        response_topic=eval_meta.get("response_topic"),
        validation_diagnostics=validation_diag,
        processing_time_s=float(eval_meta.get("processing_time_s") or 0.0),
        turn_index=turn_index,
        prior_phase=prior_phase,
    )


@dataclass
class TurnScore:
    turn_index: int
    user_message: str
    assistant_response: str
    deterministic: List[Dict[str, Any]] = field(default_factory=list)
    judge: Optional[Dict[str, Any]] = None
    deterministic_score: float = 0.0
    judge_score: float = 0.0
    final_score: float = 0.0
    elapsed_s: float = 0.0
    error: Optional[str] = None
    eval_metadata: Dict[str, Any] = field(default_factory=dict)


def _score_turn(
    cfg: EvalConfig,
    scenario: Dict[str, Any],
    turn_index: int,
    user_message: str,
    response_payload: Dict[str, Any],
    prior_phase: Optional[str],
    total_user_turns: int,
    golden_assistant: str,
    fast_llm,
) -> TurnScore:
    if "error" in response_payload and "answer" not in response_payload:
        return TurnScore(
            turn_index=turn_index,
            user_message=user_message,
            assistant_response="",
            error=str(response_payload.get("error")),
        )

    assistant_response = response_payload.get("answer", "") or ""
    metadata = response_payload.get("metadata") or {}
    eval_meta = metadata.get("eval") or {}

    ctx = _build_check_context(
        scenario=scenario,
        user_message=user_message,
        assistant_response=assistant_response,
        metadata=metadata,
        turn_index=turn_index,
        prior_phase=prior_phase,
        total_user_turns=total_user_turns,
    )

    det_results = run_deterministic_checks(ctx)
    det_score = (
        sum(r.score for r in det_results) / len(det_results)
        if det_results else 0.0
    )

    judge_dict: Optional[Dict[str, Any]] = None
    judge_score = 0.0
    if cfg.enable_llm_judge and fast_llm is not None:
        jres = judge_response_tone(
            question=user_message,
            response=assistant_response,
            golden=golden_assistant,
            phase=ctx.expected_phase or "INITIAL",
            domain=ctx.expected_domain or "general",
            language=ctx.expected_language or "en",
            user_tone=_user_tone_from_tags(scenario.get("tags", [])),
            fast_llm=fast_llm,
        )
        judge_dict = jres.to_dict()
        judge_score = jres.normalised

    # Final score: deterministic carries 60%, judge 40%.
    # If judge unavailable, deterministic alone (full weight).
    if judge_dict is None or judge_dict.get("error"):
        final = det_score
    else:
        final = 0.60 * det_score + 0.40 * judge_score

    return TurnScore(
        turn_index=turn_index,
        user_message=user_message,
        assistant_response=assistant_response,
        deterministic=[r.to_dict() for r in det_results],
        judge=judge_dict,
        deterministic_score=round(det_score, 3),
        judge_score=round(judge_score, 3),
        final_score=round(final, 3),
        elapsed_s=float(eval_meta.get("processing_time_s") or 0.0),
        eval_metadata=eval_meta,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Per-scenario runner
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    id: str
    tags: List[str] = field(default_factory=list)
    turns: List[Dict[str, Any]] = field(default_factory=list)
    aggregate_score: float = 0.0
    passed: bool = False
    error: Optional[str] = None
    elapsed_s: float = 0.0


def _run_one_scenario(
    cfg: EvalConfig,
    scenario: Dict[str, Any],
    fast_llm,
) -> ScenarioResult:
    sid = scenario.get("id", "unknown")
    user_id = f"eval_{sid}_{uuid.uuid4().hex[:8]}"
    profile = scenario.get("user_profile", {})
    turns = scenario.get("conversation", [])
    user_turns = [t for t in turns if t.get("role") == "user"]
    golden_turns = [t for t in turns if t.get("role") == "assistant"]
    total_user = len(user_turns)

    result = ScenarioResult(id=sid, tags=scenario.get("tags", []))
    t_start = time.time()

    if not user_turns:
        result.error = "no user turns in scenario"
        return result

    # Initialize session
    ok, err = _initialize_session(cfg, user_id, profile)
    if not ok:
        result.error = f"initialize failed: {err}"
        return result

    prior_phase: Optional[str] = None

    for ti, user_turn in enumerate(user_turns):
        question = user_turn.get("text", "")
        golden = golden_turns[ti].get("text", "") if ti < len(golden_turns) else ""

        if cfg.verbose:
            print(f"  [{sid}] turn {ti+1}/{total_user}: {question[:60]}...")

        t0 = time.time()
        payload = _send_message(cfg, user_id, question)
        elapsed = time.time() - t0

        score = _score_turn(
            cfg=cfg,
            scenario=scenario,
            turn_index=ti,
            user_message=question,
            response_payload=payload,
            prior_phase=prior_phase,
            total_user_turns=total_user,
            golden_assistant=golden,
            fast_llm=fast_llm,
        )
        score.elapsed_s = score.elapsed_s or round(elapsed, 2)

        result.turns.append(asdict(score))
        # Update prior_phase from telemetry for next turn
        new_phase = (score.eval_metadata.get("conversation_phase") or {}).get("phase")
        prior_phase = new_phase or prior_phase

        if score.error:
            # Skip remaining turns once we hit an error
            result.error = score.error
            break

    # Aggregate: mean of turn final_scores
    scored_turns = [t for t in result.turns if t.get("error") is None]
    if scored_turns:
        result.aggregate_score = round(
            sum(t.get("final_score", 0.0) for t in scored_turns) / len(scored_turns), 3
        )
    result.passed = result.aggregate_score >= cfg.pass_threshold and result.error is None
    result.elapsed_s = round(time.time() - t_start, 2)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public entry
# ──────────────────────────────────────────────────────────────────────────────

def _load_judge_llm():
    """Lazily build the Gemini Flash judge LLM via the project's factory."""
    try:
        from src.llm.factory import LLMFactory
        return LLMFactory.create(purpose="classification", temperature=0.1)
    except Exception as exc:
        logger.warning("[EVAL] Could not load LLM judge (%s) — soft scoring disabled.", exc)
        return None


def run_evaluation(cfg: EvalConfig) -> Dict[str, Any]:
    """
    Run the full eval suite. Returns the scorecard dict (which can be passed
    to write_scorecard for persistence).
    """
    if not _health_check(cfg):
        raise RuntimeError(f"Server health check failed at {cfg.base_url}. "
                           "Start the server with EVAL_TELEMETRY=1 and try again.")

    scenarios = load_scenarios(cfg.scenarios_path)
    scenarios = filter_scenarios(scenarios, ids=cfg.ids, tags=cfg.tags)
    if not scenarios:
        raise RuntimeError("No scenarios matched the filter.")

    fast_llm = _load_judge_llm() if cfg.enable_llm_judge else None

    run_started = time.time()
    results: List[ScenarioResult] = []
    for i, scn in enumerate(scenarios, 1):
        if cfg.verbose:
            print(f"\n[{i}/{len(scenarios)}] {scn.get('id', 'unknown')} ({','.join(scn.get('tags', []))})")
        try:
            res = _run_one_scenario(cfg, scn, fast_llm=fast_llm)
        except Exception as exc:
            res = ScenarioResult(
                id=scn.get("id", "unknown"),
                tags=scn.get("tags", []),
                error=f"runner_exception: {type(exc).__name__}: {exc}",
            )
        results.append(res)
        if cfg.verbose:
            mark = "PASS" if res.passed else ("FAIL" if not res.error else "ERROR")
            print(f"  → {mark}  score={res.aggregate_score:.3f}  ({res.elapsed_s:.1f}s)")

    return _build_scorecard(cfg, scenarios, results, run_started, fast_llm is not None)


def _build_scorecard(
    cfg: EvalConfig,
    scenarios: List[Dict[str, Any]],
    results: List[ScenarioResult],
    run_started: float,
    judge_enabled: bool,
) -> Dict[str, Any]:
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed and not r.error]
    errored = [r for r in results if r.error]

    # Aggregate scores
    scored = [r.aggregate_score for r in results if not r.error]
    overall = round(sum(scored) / len(scored), 3) if scored else 0.0

    # By tag breakdown
    tag_scores: Dict[str, List[float]] = {}
    for r in results:
        if r.error:
            continue
        for tag in r.tags:
            tag_scores.setdefault(tag, []).append(r.aggregate_score)
    by_tag = {
        t: {"count": len(s), "mean_score": round(sum(s) / len(s), 3)}
        for t, s in sorted(tag_scores.items())
    }

    return {
        "schema_version": 1,
        "started_at": run_started,
        "finished_at": time.time(),
        "config": {
            "base_url": cfg.base_url,
            "scenarios_path": cfg.scenarios_path,
            "filter_ids": cfg.ids,
            "filter_tags": cfg.tags,
            "pass_threshold": cfg.pass_threshold,
            "llm_judge_enabled": judge_enabled and cfg.enable_llm_judge,
        },
        "totals": {
            "scenarios": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "errored": len(errored),
            "overall_score": overall,
        },
        "by_tag": by_tag,
        "scenarios": [asdict(r) for r in results],
    }
