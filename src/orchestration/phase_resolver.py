"""
Phase Resolver — canonical conversation-phase helpers for NakshatraAI.

Problem: The conversation phase state-read pattern and the user response-type
classifier (pattern → short-continuation override → LLM fallback) were copy-pasted
across three nodes in orchestrator.py (safety check, intent classification, main
routing) and the validation pre-check, causing subtle divergence and making the
phase FSM hard to follow or test.

What this module does:
- get_phase(state) / get_phase_data(state): eliminate the repeated inline
  dict-chain `(state.get('session_data') or {}).get('conversation_phase', {})...`
- resolve_response_type(...): single canonical classifier — pattern match →
  short-continuation override → LLM fallback — called by all three nodes.
- resolve_phase_transition(...): the FSM transition table in one testable place.
- make_phase_data(...): canonical dict constructor for conversation_phase writes.

What is NOT handled:
- Phase instruction strings (prompt content) — those stay in the orchestrator.
- Topic/domain detection logic — stays in the routing branches.
- State persistence — callers still write state['conversation_phase'] = make_phase_data(...).

Usage:
    from src.orchestration.phase_resolver import (
        get_phase, get_phase_data,
        resolve_response_type, resolve_phase_transition, make_phase_data,
    )
    current_phase = get_phase(state)
    resp_type = resolve_response_type(orig_q, current_phase, intent_info, last_bot, fast_llm, logger)
    new_phase  = resolve_phase_transition(current_phase, resp_type, intent_type,
                                          is_affirmative_to_pivot, is_fresh_q_in_awaiting)
    state['conversation_phase'] = make_phase_data(new_phase, topic, last_query, followup_count)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Re-import lazily inside functions to avoid circular imports at module load time.
# All callers already import these constants directly from context_manager when
# they need to branch on them — this module just avoids duplicating the reads.

_FRESH_QUESTION_TOKENS = frozenset(
    ("kab", "kya", "kaise", "kyun", "where", "when", "what", "how", "who")
)


# ── State accessors ─────────────────────────────────────────────────────────


def get_phase_data(state: dict) -> dict:
    """Return the raw conversation_phase dict from state (never raises)."""
    return (state.get("session_data") or {}).get("conversation_phase", {})


def get_phase(state: dict) -> str:
    """Return the current phase string, defaulting to PHASE_INITIAL."""
    from src.ai.context_manager import PHASE_INITIAL  # lazy to avoid circular import
    return get_phase_data(state).get("phase", PHASE_INITIAL)


# ── Response-type classifier ─────────────────────────────────────────────────


def resolve_response_type(
    orig_q: str,
    current_phase: str,
    intent_info: Optional[dict] = None,
    last_bot_msg: str = "",
    fast_llm=None,
    log: Optional[logging.Logger] = None,
) -> str:
    """
    Classify the user's message as AFFIRMATIVE | NEGATIVE | OTHER.

    Stages (in order):
    1. Pattern match via detect_user_response_type.
    2. Short-continuation override: ≤6-word CONTINUATION/CLARIFICATION in
       FOLLOWUP_LOOP → AFFIRMATIVE (user typing "haan" in different words).
    3. LLM fallback: if still OTHER, active phase, and not a fresh question,
       call detect_response_type_with_llm_fallback (fast, hard-timeout inside).
    """
    from src.ai.context_manager import (
        detect_user_response_type,
        detect_response_type_with_llm_fallback,
        PHASE_AWAITING_DETAIL,
        PHASE_FOLLOWUP_LOOP,
    )

    _log = log or logger
    intent_info = intent_info or {}

    resp_type = detect_user_response_type(orig_q)
    words = orig_q.strip().split()

    # Stage 2 — short continuation in FOLLOWUP_LOOP counts as affirmative.
    if (
        resp_type == "OTHER"
        and current_phase == PHASE_FOLLOWUP_LOOP
        and len(words) <= 6
        and intent_info.get("intent_type") in ("CONTINUATION", "CLARIFICATION")
    ):
        _log.info("[PHASE] Short CONTINUATION in FOLLOWUP_LOOP → AFFIRMATIVE")
        return "AFFIRMATIVE"

    # Stage 3 — LLM fallback for remaining OTHER in active phases.
    if resp_type == "OTHER" and current_phase in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP):
        oq_lower = orig_q.lower()
        _is_likely_fresh = len(words) >= 4 and (
            "?" in orig_q or any(t in oq_lower.split() for t in _FRESH_QUESTION_TOKENS)
        )
        if not _is_likely_fresh and last_bot_msg:
            resp_type = detect_response_type_with_llm_fallback(
                orig_q, last_bot_msg, fast_llm, current_phase
            )
            if resp_type != "OTHER":
                _log.info("[PHASE] LLM fallback classified: %s", resp_type)

    return resp_type


# ── Phase FSM ────────────────────────────────────────────────────────────────


def resolve_phase_transition(
    current_phase: str,
    user_response_type: str,
    intent_type: str = "",
    is_affirmative_to_pivot: bool = False,
    is_fresh_q_in_awaiting: bool = False,
) -> str:
    """
    Return the phase to store after this turn completes.

    FSM table:
        NEW_TOPIC intent          → INITIAL  (always)
        affirmative to pivot Q    → FOLLOWUP_LOOP
        fresh Q while AWAITING    → INITIAL
        AWAITING + AFFIRMATIVE    → FOLLOWUP_LOOP
        AWAITING + NEGATIVE       → FOLLOWUP_LOOP
        AWAITING + OTHER          → INITIAL
        FOLLOWUP  + AFFIRMATIVE   → AWAITING_DETAIL  (new topic cycle)
        FOLLOWUP  + NEGATIVE      → FOLLOWUP_LOOP
        INITIAL   (any)           → AWAITING_DETAIL
    """
    from src.ai.context_manager import (
        PHASE_INITIAL,
        PHASE_AWAITING_DETAIL,
        PHASE_FOLLOWUP_LOOP,
    )

    if intent_type == "NEW_TOPIC":
        return PHASE_INITIAL
    if is_affirmative_to_pivot:
        return PHASE_FOLLOWUP_LOOP
    if is_fresh_q_in_awaiting:
        return PHASE_INITIAL

    if current_phase == PHASE_AWAITING_DETAIL:
        if user_response_type in ("AFFIRMATIVE", "NEGATIVE"):
            return PHASE_FOLLOWUP_LOOP
        return PHASE_INITIAL  # OTHER → treat as fresh question

    if current_phase == PHASE_FOLLOWUP_LOOP:
        if user_response_type == "AFFIRMATIVE":
            return PHASE_AWAITING_DETAIL
        return PHASE_FOLLOWUP_LOOP  # NEGATIVE → offer alternative

    # INITIAL or unknown — short answer, then await detail request.
    return PHASE_AWAITING_DETAIL


# ── Phase-data constructor ───────────────────────────────────────────────────


def make_phase_data(
    phase: str,
    topic: Optional[str],
    last_query: str,
    followup_count: int,
) -> dict:
    """Canonical constructor for the conversation_phase state dict."""
    return {
        "phase": phase,
        "topic": topic,
        "last_query": last_query,
        "followup_count": followup_count,
    }
