"""
Agentic retrieval loop for NakshatraAI (#12 roadmap item).

Replaces the fixed single-retrieval pipeline with an LLM-guided loop where
the model decides which tools to call and crafts targeted queries informed by
the deterministic FactorPlan.

Integration point: called from _handle_rag_with_calculation_node between
Step 1 (SemanticFrame/FactorPlan pre-build) and the existing prompt builder.
All downstream steps — prompt construction, quality gate, memory write — are
unchanged.

Tools available to the agent:
  retrieve_knowledge  — RAG retrieval (max_retrievals cap enforced, multi-hop)
  get_chart_snapshot  — structured natal chart view from already-loaded state (zero API cost)
  get_dasha_snapshot  — dasha timing windows from already-loaded state (zero API cost)

Loop control:
  max_iters=3 iterations, max_retrievals=2, hard timeout via max_iters.
  Termination: agent emits no tool calls → proceed to generation.

Failure contract:
  Any exception inside run_agent_loop returns an empty AgentLoopResult.
  Callers must handle an empty retrieval_chunks list (existing no-retriever
  code path is the natural fallback).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class AgentLoopResult:
    retrieval_chunks: list = field(default_factory=list)
    chart_context: str = ""
    dasha_context: str = ""
    tool_calls_made: list = field(default_factory=list)  # [{"name": ..., "args": {...}}]


# ── Tool schemas (OpenAI-compatible format accepted by ChatVertexAI) ──────────


_RETRIEVE_SCHEMA = {
    "name": "retrieve_knowledge",
    "description": (
        "Fetch relevant Vedic astrology texts from the knowledge base. "
        "Craft a targeted query using the top-ranked factors, planets, and houses "
        "most relevant to the user's question. Can be called up to twice."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Specific retrieval query. Include planet names, house numbers, "
                    "domain keywords, and dasha lords relevant to the question."
                ),
            },
            "sub_focus": {
                "type": "string",
                "description": (
                    "Optional secondary focus to append to the query "
                    "(e.g. 'Saturn transit 7th house delay', 'Navamsa Venus placement')."
                ),
            },
        },
        "required": ["query"],
    },
}

_CHART_SCHEMA = {
    "name": "get_chart_snapshot",
    "description": (
        "Get a structured snapshot of the user's natal chart from pre-computed state. "
        "Use when you need specific house lords, planetary placements, yogas, "
        "divisional chart details, or planetary conditions (retrograde, combust, etc.)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "focus": {
                "type": "string",
                "description": "Which aspect to return: 'placements', 'yogas', 'houses', 'divisional', 'conditions', or 'all'.",
                "enum": ["placements", "yogas", "houses", "divisional", "conditions", "all"],
            },
        },
        "required": ["focus"],
    },
}

_DASHA_SCHEMA = {
    "name": "get_dasha_snapshot",
    "description": (
        "Get dasha timing windows from pre-computed state. "
        "Use when you need active dasha/antardasha lords, upcoming pratyantardasha windows, "
        "or antardasha transitions for timing questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "horizon": {
                "type": "string",
                "description": (
                    "'near' = pratyantardasha windows (0-12 months), "
                    "'mid' = antardashas (1-5 years), "
                    "'far' = mahadasha overview."
                ),
                "enum": ["near", "mid", "far"],
            },
        },
        "required": ["horizon"],
    },
}


def _build_tool_schemas(retrieval_count: int, max_retrievals: int) -> list:
    schemas = [_CHART_SCHEMA, _DASHA_SCHEMA]
    if retrieval_count < max_retrievals:
        schemas.insert(0, _RETRIEVE_SCHEMA)
    return schemas


# ── Tool executors ────────────────────────────────────────────────────────────


def _exec_retrieve(
    args: dict,
    state: dict,
    retriever,
    frame: dict,
    retrieval_count: int,
    max_retrievals: int,
) -> list:
    if retrieval_count >= max_retrievals:
        return []

    query = args.get("query", "")
    sub_focus = args.get("sub_focus", "")
    if sub_focus:
        query = f"{query} {sub_focus}"

    domain = frame.get("domain", "general")
    question_mode = frame.get("question_mode", "summary")
    language = state.get("detected_language", "en")

    # Build HyDE context from already-loaded chart/dasha state
    hyde_ctx = None
    chart = state.get("chart_data") or {}
    dasha = state.get("dasha_data") or {}
    lagna = (
        (chart.get("lagna") or {}).get("sign")
        or (chart.get("ascendant") or {}).get("sign", "")
    )
    _md = dasha.get("mahadasha") or {}
    _ad = dasha.get("antardasha") or {}
    md_planet = (_md.get("planet") or _md.get("lord", "")) if isinstance(_md, dict) else ""
    ad_planet = (_ad.get("planet") or _ad.get("lord", "")) if isinstance(_ad, dict) else ""
    if lagna:
        parts = [f"{lagna} ascendant"]
        if md_planet:
            ds = f"{md_planet} MD"
            if ad_planet and ad_planet != md_planet:
                ds += f" / {ad_planet} AD"
            parts.append(ds)
        parts.append(f"{domain} domain")
        hyde_ctx = ", ".join(parts)

    try:
        from config.rag_config import RAGConfig
        top_k = RAGConfig.get_top_k(content_type="interpretation")
    except Exception:
        top_k = 8

    try:
        chunks = retriever.retrieve(
            query=query,
            intent="RAG_WITH_CALCULATION",
            top_k=top_k,
            language=language,
            content_type="interpretation",
            user_id=state.get("user_id"),
            hyde_context=hyde_ctx,
            question_mode=question_mode,
        )
        logger.info("[AGENT_LOOP] retrieve_knowledge → %d chunks (query: %s…)", len(chunks), query[:60])
        return chunks
    except Exception as e:
        logger.warning("[AGENT_LOOP] retrieve_knowledge failed: %s", e)
        return []


def _exec_chart_snapshot(args: dict, state: dict) -> str:
    focus = args.get("focus", "all")
    chart = state.get("chart_data") or {}
    synthesis = state.get("synthesis") or {}
    lines: List[str] = [f"=== CHART SNAPSHOT (focus={focus}) ==="]

    if focus in ("placements", "all"):
        planets = chart.get("planets") or {}
        if planets:
            lines.append("Planetary Placements:")
            for planet, info in list(planets.items())[:12]:
                if isinstance(info, dict):
                    sign = info.get("sign", "")
                    house = info.get("house", "")
                    retro = " [R]" if info.get("retrograde") else ""
                    combust = " [combust]" if info.get("combust") else ""
                    lines.append(f"  {planet}: {sign} H{house}{retro}{combust}")

    if focus in ("houses", "all"):
        key_houses = synthesis.get("key_houses") or {}
        if key_houses:
            lines.append("Key Houses (from synthesis):")
            for h, data in list(key_houses.items())[:6]:
                if isinstance(data, dict):
                    lord = data.get("lord", "")
                    status = data.get("status", "")
                    lines.append(f"  {h}: lord={lord} status={status}")

    if focus in ("yogas", "all"):
        yogas = synthesis.get("yogas") or chart.get("yogas") or []
        if yogas:
            lines.append("Yogas Detected:")
            for y in yogas[:8]:
                name = (y.get("name", y) if isinstance(y, dict) else str(y))
                lines.append(f"  {name}")

    if focus in ("divisional", "all"):
        div = chart.get("divisional_charts") or synthesis.get("divisional_charts") or {}
        if div:
            lines.append("Divisional Charts:")
            for dc, ddata in list(div.items())[:4]:
                summary = (
                    ddata.get("summary", str(ddata))[:80]
                    if isinstance(ddata, dict)
                    else str(ddata)[:80]
                )
                lines.append(f"  {dc}: {summary}")

    if focus in ("conditions", "all"):
        conds = synthesis.get("planetary_conditions") or {}
        if conds:
            lines.append("Planetary Conditions:")
            for planet, cond in list(conds.items())[:8]:
                lines.append(f"  {planet}: {cond}")

    result = "\n".join(lines)
    logger.info("[AGENT_LOOP] get_chart_snapshot(focus=%s) → %d chars", focus, len(result))
    return result


def _exec_dasha_snapshot(args: dict, state: dict) -> str:
    horizon = args.get("horizon", "near")
    dasha = state.get("dasha_data") or {}
    lines: List[str] = [f"=== DASHA SNAPSHOT (horizon={horizon}) ==="]

    _md = dasha.get("mahadasha") or {}
    _ad = dasha.get("antardasha") or {}

    if isinstance(_md, dict) and _md:
        md_lord = _md.get("planet") or _md.get("lord", "")
        md_end = _md.get("end", "")
        lines.append(f"Active Mahadasha: {md_lord} (ends {md_end})")

    if isinstance(_ad, dict) and _ad:
        ad_lord = _ad.get("planet") or _ad.get("lord", "")
        ad_end = _ad.get("end", "")
        lines.append(f"Active Antardasha: {ad_lord} (ends {ad_end})")

    if horizon in ("near", "all"):
        pratyantar = dasha.get("upcoming_pratyantardashas") or []
        if isinstance(pratyantar, dict):
            pratyantar = [pratyantar]
        if pratyantar:
            lines.append("Upcoming Pratyantardasha windows:")
            for p in pratyantar[:6]:
                if isinstance(p, dict):
                    lord = p.get("lord") or p.get("planet", "")
                    start = p.get("start", "")
                    end = p.get("end", "")
                    lines.append(f"  {lord}: {start} → {end}")

    if horizon in ("mid", "all"):
        antardashas = dasha.get("upcoming_antardashas") or []
        if antardashas:
            lines.append("Upcoming Antardashas:")
            for a in antardashas[:5]:
                if isinstance(a, dict):
                    lord = a.get("lord") or a.get("planet", "")
                    start = a.get("start", "")
                    end = a.get("end", "")
                    lines.append(f"  {lord}: {start} → {end}")

    if horizon in ("far", "all"):
        if isinstance(_md, dict) and _md:
            lines.append(
                f"Mahadasha overview: {_md.get('planet') or _md.get('lord','')} "
                f"{_md.get('start','')} → {_md.get('end','')}"
            )

    result = "\n".join(lines)
    logger.info("[AGENT_LOOP] get_dasha_snapshot(horizon=%s) → %d chars", horizon, len(result))
    return result


# ── Agent prompts ─────────────────────────────────────────────────────────────


def _format_factor_plan(factor_plan) -> str:
    if factor_plan is None:
        return ""
    try:
        top = getattr(factor_plan, "top_factors", []) or []
        if not top:
            return ""
        lines = ["Top-ranked factors (domain × dasha × validation):"]
        for i, f in enumerate(top[:3], 1):
            text = getattr(f, "text", str(f))
            score = getattr(f, "combined_score", "")
            why = getattr(f, "why", "")
            score_str = f" (score={score:.2f})" if isinstance(score, float) else ""
            why_str = f" — {why}" if why else ""
            lines.append(f"  {i}. {text}{score_str}{why_str}")
        return "\n".join(lines)
    except Exception:
        return ""


def _build_system_prompt(frame: dict, factor_plan) -> str:
    domain = frame.get("domain", "general")
    question_mode = frame.get("question_mode", "summary")
    detail_level = frame.get("detail_level", "standard")
    factor_block = _format_factor_plan(factor_plan)

    return f"""You are a retrieval planner for a Vedic astrology AI system.

Your only task is to gather the right context to support a high-quality answer.
Do NOT answer the user's question — that is handled in a separate generation step.

Pre-computed deterministic analysis:
  Domain: {domain}
  Question mode: {question_mode}  (timing=event windows | qualities=traits | advice=recommendations)
  Detail level: {detail_level}
{factor_block}

Available tools:
  retrieve_knowledge   — fetch Vedic astrology texts (max 2 calls; use factor-grounded queries)
  get_chart_snapshot   — natal chart details from pre-loaded state (free, no API call)
  get_dasha_snapshot   — dasha timing windows from pre-loaded state (free, no API call)

Retrieval strategy:
  1. Call retrieve_knowledge with a query grounded in the top-ranked factors and domain.
  2. If the first result lacks context on a specific yoga, transit, or divisional placement,
     use the second retrieval call to fill that gap.
  3. Use get_chart_snapshot / get_dasha_snapshot when you need specific chart data to
     cross-reference — these are free calls that read pre-computed state.
  4. Stop calling tools when you have enough context for a complete, well-grounded answer.

When you are done gathering context, output nothing and make no further tool calls."""


def _build_user_message(query: str, frame: dict) -> str:
    domain = frame.get("domain", "general")
    question_mode = frame.get("question_mode", "summary")
    return (
        f"User question: {query}\n"
        f"Domain: {domain} | Mode: {question_mode}\n\n"
        "Gather the context needed to answer this well."
    )


# ── Main loop ─────────────────────────────────────────────────────────────────


def run_agent_loop(
    query: str,
    frame: dict,
    factor_plan,
    state: dict,
    retriever,
    llm,
    max_retrievals: int = 2,
    max_iters: int = 3,
    log: Optional[logging.Logger] = None,
) -> AgentLoopResult:
    """
    Run the agentic retrieval loop.

    Uses fast_llm (passed as `llm`) for tool selection — cheap per-token cost.
    Returns AgentLoopResult with all retrieval chunks plus any chart/dasha context
    the agent chose to surface.

    Falls back gracefully to empty AgentLoopResult on any error; the caller's
    existing no-retriever path handles empty retrieval_chunks.
    """
    _log = log or logger
    result = AgentLoopResult()

    if retriever is None:
        _log.info("[AGENT_LOOP] No retriever — skipping loop")
        return result

    try:
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    except ImportError as e:
        _log.warning("[AGENT_LOOP] langchain_core not available: %s", e)
        return result

    # Unwrap RateLimitedLLM to get the underlying ChatVertexAI that supports bind_tools
    _base_llm = llm.llm if hasattr(llm, "llm") else llm

    system_prompt = _build_system_prompt(frame, factor_plan)
    user_msg = _build_user_message(query, frame)

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]

    retrieval_count = 0

    for iteration in range(max_iters):
        tool_schemas = _build_tool_schemas(retrieval_count, max_retrievals)
        try:
            llm_with_tools = _base_llm.bind_tools(tool_schemas)
            response = llm_with_tools.invoke(messages)
        except Exception as e:
            _log.warning("[AGENT_LOOP] LLM call failed at iter %d: %s", iteration + 1, e)
            break

        tool_calls = getattr(response, "tool_calls", []) or []
        if not tool_calls:
            _log.info("[AGENT_LOOP] Agent finished after %d iteration(s)", iteration + 1)
            break

        messages.append(response)

        tool_messages: list = []
        for tc in tool_calls:
            # LangChain tool_calls are dicts: {"name": ..., "args": {...}, "id": ...}
            name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            tc_id = tc.get("id", name) if isinstance(tc, dict) else getattr(tc, "id", name)

            result.tool_calls_made.append({"name": name, "args": args})

            if name == "retrieve_knowledge":
                chunks = _exec_retrieve(args, state, retriever, frame, retrieval_count, max_retrievals)
                result.retrieval_chunks.extend(chunks)
                retrieval_count += 1
                tool_output = f"Retrieved {len(chunks)} knowledge chunks."

            elif name == "get_chart_snapshot":
                snapshot = _exec_chart_snapshot(args, state)
                result.chart_context = (
                    result.chart_context + "\n" + snapshot if result.chart_context else snapshot
                )
                tool_output = snapshot

            elif name == "get_dasha_snapshot":
                snapshot = _exec_dasha_snapshot(args, state)
                result.dasha_context = (
                    result.dasha_context + "\n" + snapshot if result.dasha_context else snapshot
                )
                tool_output = snapshot

            else:
                _log.warning("[AGENT_LOOP] Unknown tool requested: %s", name)
                tool_output = f"Tool '{name}' is not available."

            tool_messages.append(ToolMessage(content=tool_output, tool_call_id=tc_id))

        messages.extend(tool_messages)

        if retrieval_count >= max_retrievals:
            _log.info("[AGENT_LOOP] Retrieval cap reached (%d/%d)", retrieval_count, max_retrievals)
            # Allow one final iteration so agent can call chart/dasha tools if needed
            if iteration == max_iters - 2:
                continue
            break

    _log.info(
        "[AGENT_LOOP] Complete: %d chunks, %d retrieval(s), %d tool call(s)",
        len(result.retrieval_chunks),
        retrieval_count,
        len(result.tool_calls_made),
    )
    return result
