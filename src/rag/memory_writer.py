# src/rag/memory_writer.py
"""
User Memory Writer for NakshatraAI (Improvement #7).

Problem solved:
  MemoryRetriever can retrieve user-specific facts during RAG, but nothing
  ever writes to it. Follow-up questions are generic because the system has
  no memory of "user works in finance", "has 2 kids", "wife named Priya".

What this module does:
  After each RAG_WITH_CALCULATION response, scan the user's message for
  explicit personal facts using two-stage extraction:

    Stage 1 — Regex (zero latency, no LLM):
      Catches the most common explicit fact patterns:
        "I work as/in X", "I am a X", "I'm a X"
        "my wife/husband is named X"
        "I have N children/kids"
        "I live in X / I'm from X"
        "I'm N years old"
        "my name is X"

    Stage 2 — Fast LLM fallback (≤2s hard timeout):
      If the message is substantive (≥20 words, contains "I"/"my"/"me")
      but regex found nothing, call the fast LLM to extract facts as JSON.
      Falls back silently on timeout or error.

  Each extracted fact is stored via MemoryRetriever.add_memory() as:
    content:  "User fact [{type}]: {fact_text}"
    metadata: {user_id, fact_type, domain, source, timestamp}

Design principles:
  - Non-blocking: called as a daemon thread, never delays the response.
  - Idempotent-ish: simple duplicate guard (same fact_type + normalised text
    already in recent memories → skip). Not perfect, good enough.
  - No hallucination: regex extracts only what is explicitly present; the LLM
    prompt instructs "do NOT infer or guess — only explicit statements".

What is NOT stored:
  - Questions ("when will I get married?") — no personal fact content.
  - Astrological interpretations from the bot — only user-stated facts.
  - Generic desires ("I want to succeed") — no concrete personal fact.
  - Chart data — already structured in state; stored separately.

Usage (fire-and-forget):
    import threading
    from src.rag.memory_writer import extract_and_store_user_facts

    t = threading.Thread(
        target=extract_and_store_user_facts,
        kwargs=dict(
            user_message=state['query'],
            user_id=state['user_id'],
            memory_retriever=self.hybrid_retriever.memory_retriever,
            fast_llm=self.fast_llm,
            domain=frame_domain,
        ),
        daemon=True,
    )
    t.start()
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Regex extraction patterns
# Each tuple: (compiled pattern, fact_type, extractor_fn or None)
# extractor_fn(match) → fact_text string, or None to use group(1) default.
# ──────────────────────────────────────────────────────────────────────────────

def _join_groups(m: re.Match, sep: str = " ") -> str:
    """Concatenate all non-None groups, stripped."""
    return sep.join(g.strip() for g in m.groups() if g).strip()


_FACT_PATTERNS: List[Tuple[re.Pattern, str, Any]] = [
    # Profession / role
    (
        re.compile(
            r"\bi\s+(?:am|'m)\s+(?:a|an)\s+([\w][\w\s]{1,30}?)(?:\s*[.,]|\s+by profession|\s+by trade|$)",
            re.IGNORECASE,
        ),
        "profession",
        lambda m: f"user is a {m.group(1).strip()}",
    ),
    (
        re.compile(
            r"\bi\s+work\s+(?:as|in|at|for)\s+([\w][\w\s]{1,30}?)(?:\s*[.,]|$)",
            re.IGNORECASE,
        ),
        "profession",
        lambda m: f"user works {m.group(0).split('work')[1].strip()}",
    ),
    # Spouse / partner name
    (
        re.compile(
            r"my\s+(?:wife|husband|spouse|partner|girlfriend|boyfriend)\s+(?:is\s+)?(?:named?|'s\s+name\s+is)\s+([\w]+)",
            re.IGNORECASE,
        ),
        "family",
        lambda m: f"user's {m.group(0).split('my ')[1].split(' is')[0].split(' named')[0].strip()} is named {m.group(1)}",
    ),
    # Number of children
    (
        re.compile(
            r"\bi\s+have\s+(\d+|one|two|three|four|five|no)\s+(?:child(?:ren)?|kid(?:s)?|son(?:s)?|daughter(?:s)?)",
            re.IGNORECASE,
        ),
        "family",
        lambda m: f"user has {m.group(1)} children",
    ),
    # Location
    (
        re.compile(
            r"\bi\s+(?:live\s+in|am\s+from|'m\s+from|stay\s+in|reside\s+in|moved\s+to)\s+([\w][\w\s]{1,25}?)(?:\s*[.,]|$)",
            re.IGNORECASE,
        ),
        "location",
        lambda m: f"user lives in / is from {m.group(1).strip()}",
    ),
    # Age
    (
        re.compile(
            r"\bi\s+(?:am|'m)\s+(\d{2})\s+years?\s+old",
            re.IGNORECASE,
        ),
        "age",
        lambda m: f"user is {m.group(1)} years old",
    ),
    # Name
    (
        re.compile(
            r"(?:my\s+name\s+is|i\s+am\s+called)\s+([\w]+)",
            re.IGNORECASE,
        ),
        "name",
        lambda m: f"user's name is {m.group(1)}",
    ),
    # Marital status (explicit)
    (
        re.compile(
            r"\bi\s+(?:am|'m)\s+(married|divorced|single|widowed|separated)",
            re.IGNORECASE,
        ),
        "relationship_status",
        lambda m: f"user is {m.group(1).lower()}",
    ),
    # Recent life event
    (
        re.compile(
            r"\bi\s+(?:just|recently|got|have\s+just)\s+(got\s+(?:a\s+)?(?:job|promotion|married|divorced)|started\s+a\s+new\s+job|moved|had\s+a\s+baby)",
            re.IGNORECASE,
        ),
        "life_event",
        lambda m: f"user recently: {m.group(1).strip()}",
    ),
]

# Only run LLM fallback if the message is substantive and personal
_PERSONAL_SIGNAL_RE = re.compile(r"\b(?:i|my|me|mine|myself|i'm|i've|i've)\b", re.IGNORECASE)
_LLM_FALLBACK_MIN_WORDS = 20


# ──────────────────────────────────────────────────────────────────────────────
# Regex extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_via_regex(text: str) -> List[Dict[str, str]]:
    """Return list of {fact_text, fact_type} dicts from regex scan."""
    facts: List[Dict[str, str]] = []
    seen_facts: set = set()

    for pattern, fact_type, extractor in _FACT_PATTERNS:
        for m in pattern.finditer(text):
            try:
                fact_text = extractor(m).strip() if extractor else m.group(1).strip()
            except Exception:
                continue
            # Normalise and deduplicate within this call
            key = (fact_type, fact_text.lower()[:60])
            if key in seen_facts:
                continue
            seen_facts.add(key)
            facts.append({"fact_text": fact_text, "fact_type": fact_type})

    return facts


# ──────────────────────────────────────────────────────────────────────────────
# LLM fallback extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_via_llm(text: str, fast_llm, timeout: float = 2.0) -> List[Dict[str, str]]:
    """
    Call fast LLM to extract personal facts as JSON.
    Returns [] on timeout, error, or no facts found.
    """
    import concurrent.futures

    prompt = (
        "You are extracting explicit personal facts from a user message sent to an astrology chatbot.\n"
        "Return ONLY a JSON array of objects with keys 'fact' (string) and 'type' (one of: "
        "profession, family, location, age, name, relationship_status, life_event, preference).\n"
        "Rules:\n"
        "  - Extract ONLY what the user explicitly stated — do NOT infer or guess.\n"
        "  - Ignore questions, chart requests, and astrological topics.\n"
        "  - If no explicit personal facts are present, return [].\n"
        "  - Keep fact strings concise (max 20 words each).\n\n"
        f'User message: "{text[:400]}"\n\n'
        "JSON array:"
    )

    def _call() -> List[Dict[str, str]]:
        response = fast_llm.invoke(prompt)
        raw = (response.content if hasattr(response, "content") else str(response)).strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [
            {"fact_text": str(item.get("fact", "")).strip(), "fact_type": str(item.get("type", "general")).strip()}
            for item in data
            if isinstance(item, dict) and item.get("fact")
        ]

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.debug("[MEMORY_WRITER] LLM fallback timed out after %.1fs", timeout)
    except Exception as exc:
        logger.debug("[MEMORY_WRITER] LLM fallback failed: %s", exc)
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate guard
# ──────────────────────────────────────────────────────────────────────────────

def _is_duplicate(fact_text: str, fact_type: str, existing_memories: List[Dict]) -> bool:
    """
    Rough duplicate check: if existing memories already contain a very similar
    fact of the same type, skip. Comparison is lowercase substring match.
    """
    normalised = fact_text.lower()[:50]
    for mem in existing_memories:
        content = (mem.get("content") or "").lower()
        m_type = (mem.get("metadata") or {}).get("fact_type", "")
        if m_type == fact_type and normalised in content:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def extract_and_store_user_facts(
    user_message: str,
    user_id: str,
    memory_retriever,               # MemoryRetriever instance
    fast_llm=None,
    domain: str = "general",
    llm_timeout: float = 2.0,
) -> int:
    """
    Extract personal facts from `user_message` and store them via `memory_retriever`.

    Designed to be called in a daemon thread — never raises, swallows all errors.

    Args:
        user_message:      The raw user query text.
        user_id:           User identifier for memory namespacing.
        memory_retriever:  MemoryRetriever instance (must have add_memory()).
        fast_llm:          Fast LLM for fallback extraction (optional).
        domain:            Current astrological domain from SemanticFrame.
        llm_timeout:       Hard timeout for the LLM fallback call (seconds).

    Returns:
        Number of facts stored (0 on any error or no facts found).
    """
    if not user_message or not user_id or not memory_retriever:
        return 0

    try:
        text = user_message.strip()

        # ── Stage 1: Regex extraction ────────────────────────────────────────
        facts = _extract_via_regex(text)

        # ── Stage 2: LLM fallback (only if message is substantive + personal) ─
        if not facts and fast_llm:
            word_count = len(text.split())
            personal_signals = len(_PERSONAL_SIGNAL_RE.findall(text))
            if word_count >= _LLM_FALLBACK_MIN_WORDS and personal_signals >= 1:
                facts = _extract_via_llm(text, fast_llm, timeout=llm_timeout)

        if not facts:
            return 0

        # ── Duplicate guard: fetch recent memories for this user ─────────────
        try:
            existing = memory_retriever.retrieve_memories(
                user_id=user_id,
                query=text[:100],
                k=5,
            )
        except Exception:
            existing = []

        # ── Store each new fact ──────────────────────────────────────────────
        ts = datetime.now(timezone.utc).isoformat()
        stored = 0

        for item in facts:
            fact_text = (item.get("fact_text") or "").strip()
            fact_type = (item.get("fact_type") or "general").strip()

            if not fact_text or len(fact_text) < 4:
                continue

            if _is_duplicate(fact_text, fact_type, existing):
                logger.debug("[MEMORY_WRITER] Skipping duplicate: %s", fact_text[:50])
                continue

            content = f"User fact [{fact_type}]: {fact_text}"
            metadata = {
                "fact_type": fact_type,
                "domain": domain,
                "source": "regex" if not fast_llm else "extracted",
                "timestamp": ts,
            }

            memory_retriever.add_memory(
                user_id=user_id,
                content=content,
                role="user",
                metadata=metadata,
            )
            stored += 1
            logger.info("[MEMORY_WRITER] Stored [%s]: %s", fact_type, fact_text[:60])

        return stored

    except Exception as exc:
        logger.debug("[MEMORY_WRITER] Unexpected error: %s", exc)
        return 0


def maybe_store_user_facts_async(
    user_message: str,
    user_id: str,
    memory_retriever,
    fast_llm=None,
    domain: str = "general",
) -> None:
    """
    Fire-and-forget wrapper: spawns a daemon thread to run extract_and_store_user_facts.
    Returns immediately — never blocks the response pipeline.
    """
    if not user_message or not user_id or not memory_retriever:
        return

    t = threading.Thread(
        target=extract_and_store_user_facts,
        kwargs=dict(
            user_message=user_message,
            user_id=user_id,
            memory_retriever=memory_retriever,
            fast_llm=fast_llm,
            domain=domain,
        ),
        daemon=True,
        name=f"memory-writer-{user_id[:8]}",
    )
    t.start()
    logger.debug("[MEMORY_WRITER] Async write started for user %s", user_id[:8])
