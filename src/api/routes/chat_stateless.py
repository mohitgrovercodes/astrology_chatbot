# src/api/routes/chat_stateless.py
"""
Stateless Chat Routes with Professional Context Management.

Features:
- LLM-based context analysis (no pattern matching)
- Conversation summarization every 6 messages
- Intent detection: Continuation/New Topic/Clarification
- Comprehensive logging
"""

import os
import re
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import time
import json
from datetime import datetime
from src.llm.factory import LLMFactory
from config.logger import get_logger

logger = get_logger("chat_stateless")

from src.api.orchestrator_helper import get_orchestrator
from src.api.config import settings
from src.api.dependencies import (
    get_context_manager as get_shared_context_manager,
    get_session_manager as get_shared_session_manager,
)


router = APIRouter()


# ============================================================================
# CONTEXT MANAGER - LLM-Based Context Analysis
# ============================================================================

class ContextManager:
    """
    Professional-grade context manager using LLM for intelligent analysis.
    No pattern matching - purely LLM-driven decisions.
    """
    
    def __init__(self):
        """Initialize fast LLM for context analysis via centralized factory."""
        self.fast_llm = LLMFactory.create(
            purpose="classification",
            temperature=0.1  # Low temperature for consistent analysis
        )
    
    def analyze_message_intent(
        self,
        current_query: str,
        conversation_history: List[Dict],
        conversation_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze if the current message is:
        A) Continuation of current topic
        B) New topic
        C) Clarification request
        
        Uses LLM - No pattern matching!
        
        Returns:
            {
                "intent_type": "CONTINUATION" | "NEW_TOPIC" | "CLARIFICATION",
                "confidence": float,
                "reasoning": str,
                "referenced_topic": str (if continuation/clarification),
                "requires_context": bool
            }
        """
        # Format conversation for analysis
        conv_text = self._format_conversation(conversation_history)
        
        analysis_prompt = f"""You are a conversation analyzer for an astrology chatbot.

Analyze the user's current message and determine its intent.

CONVERSATION SUMMARY (if available):
{conversation_summary or "No summary yet - this is an early conversation"}

RECENT CONVERSATION:
{conv_text or "No previous messages"}

CURRENT USER MESSAGE:
"{current_query}"

Your task:
Classify this message as ONE of the following:

A) CONTINUATION - User is continuing/following up on the previous topic
   Examples: "Tell me more", "What else?", "How does this affect my career?"
   
B) NEW_TOPIC - User is starting a completely new topic
   Examples: "What about my health?", "Tell me about my marriage prospects"
   
C) CLARIFICATION - User is asking for clarification on something unclear
   Examples: "What do you mean?", "Can you explain that?", "I don't understand"

Respond in JSON format:
{{
    "intent_type": "CONTINUATION" | "NEW_TOPIC" | "CLARIFICATION",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why",
    "referenced_topic": "What SPECIFIC topic they're referring to (e.g., 'Pisces moon sign' instead of just 'moon sign')",
    "requires_context": true/false
}}

Be accurate - analyze the semantic meaning, not just keywords. If a user asks about their placement (like moon sign), and it was just discussed, include the specific placement in the referenced_topic.
"""
        
        try:
            response = self.fast_llm.invoke(analysis_prompt)
            content = response.content.strip()
            
            # ════════════════════════════════════════════════════════════════
            # ROBUST JSON PARSING - Handle LLM format variations
            # ════════════════════════════════════════════════════════════════
            if not content:
                raise ValueError("Empty response from LLM")
            
            # Try to extract JSON if wrapped in markdown code blocks
            if "```json" in content:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            elif "```" in content:
                # Handle plain markdown code blocks
                import re
                json_match = re.search(r'```\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            
            # Remove any leading/trailing markdown artifacts
            content = content.strip('`').strip()
            
            # Parse JSON
            result = json.loads(content)
            
            # Validate required fields
            if 'intent_type' not in result:
                result['intent_type'] = 'NEW_TOPIC'
            if 'confidence' not in result:
                result['confidence'] = 0.5
            
            logger.info(f"[CONTEXT ANALYSIS]")
            logger.debug(f"Query: {current_query[:60]}...")
            logger.debug(f"Intent: {result['intent_type']}")
            logger.debug(f"Confidence: {result.get('confidence', 0.5):.2f}")
            logger.debug(f"Reasoning: {result.get('reasoning', 'N/A')}")
            if result.get('referenced_topic'):
                logger.debug(f"Referenced Topic: {result['referenced_topic']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.info(f"[CONTEXT] JSON Parse Error: {e}")
            logger.info(f"[CONTEXT] LLM Response (first 200 chars): {response.content[:200]}...")
            # Fallback to safe default
            return {
                "intent_type": "NEW_TOPIC",
                "confidence": 0.5,
                "reasoning": "JSON parse error - defaulting to NEW_TOPIC",
                "referenced_topic": None,
                "requires_context": False
            }
            
        except Exception as e:
            logger.error(f"[CONTEXT] Error analyzing intent: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to safe default
            return {
                "intent_type": "NEW_TOPIC",
                "confidence": 0.5,
                "reasoning": "Error in analysis",
                "referenced_topic": None,
                "requires_context": False
            }
    
    def resolve_contextual_query(
        self,
        current_query: str,
        conversation_history: List[Dict],
        intent_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Lightweight Semantic Interpreter with Confidence-Based Reframing.
        
        CRITICAL: Only resolve ambiguity and inject topic clarity.
        DO NOT change the meaning or intent of the original query.
        
        Returns:
            {
                "action": "EXPAND" | "HINT" | "ASK_CLARIFICATION",
                "processed_query": str,
                "ambiguity_score": float,
                "clarification_needed": bool,
                "explanation": str,
                ["clarification_question": str]  # only if ASK_CLARIFICATION
            }
        """
        if not intent_analysis.get('requires_context'):
            return {
                "action": "NONE",
                "processed_query": current_query,
                "ambiguity_score": 0.0,
                "clarification_needed": False,
                "explanation": "Query is clear and self-contained"
            }
        
        conv_text = self._format_conversation(conversation_history[-3:])

        # ── DETERMINISTIC PRE-CHECK ───────────────────────────────────────────
        # If conversation has a clear single-topic context (≤4 messages) AND
        # the query has an obvious pronoun/follow-up phrase, skip LLM scoring
        # entirely and EXPAND immediately. This prevents the LLM from
        # under-scoring crystal-clear follow-ups like "Tell me more about it".
        CLEAR_FOLLOWUP_PHRASES = [
            'tell me more about it', 'more about it', 'what else about it',
            'tell me more', 'what else', 'say more', 'expand on that',
            'elaborate', 'go on', 'continue',
        ]
        PRONOUN_WORDS = ['it', 'this', 'that', 'these', 'those']
        query_lower = current_query.lower().strip()
        referenced_topic = intent_analysis.get('referenced_topic', 'the previous topic')

        is_clear_followup = any(phrase in query_lower for phrase in CLEAR_FOLLOWUP_PHRASES)
        has_pronoun = any(word in query_lower.split() for word in PRONOUN_WORDS)
        is_short_followup = len(current_query.split()) <= 6 and (
            query_lower.startswith('why') or query_lower.startswith('how') or
            query_lower.startswith('when') or query_lower.startswith('what')
        )
        single_topic_context = len(conversation_history) <= 4  # ≤2 exchanges

        if (is_clear_followup or (has_pronoun and single_topic_context) or
                (is_short_followup and single_topic_context)):
            # Build an inline expansion without a second LLM call
            expanded = current_query
            for pron in PRONOUN_WORDS:
                if f' {pron} ' in f' {query_lower} ':
                    expanded = current_query.replace(pron, referenced_topic)
                    expanded = expanded.replace(pron.capitalize(), referenced_topic.capitalize())
                    break
            logger.info(f"[SEMANTIC INTERPRETER] [EXPAND] Deterministic EXPAND (skipping LLM)")
            logger.debug(f"Pattern matched: clear_followup={is_clear_followup}, pronoun={has_pronoun}, short={is_short_followup}")
            logger.debug(f"Expanded: '{expanded}'")
            return {
                "action": "EXPAND",
                "processed_query": expanded,
                "ambiguity_score": 0.95,
                "clarification_needed": False,
                "explanation": "Single-topic follow-up: deterministically expanded"
            }
        # ─────────────────────────────────────────────────────────────────────
        referenced_topic = intent_analysis.get('referenced_topic', 'Previous topic')
        
        # Build ambiguity analysis prompt (your existing improved prompt here)
        ambiguity_prompt = f"""You are a semantic analyzer for an astrology chatbot.

Analyze the user's query to determine:
1. How clear and resolvable is it? (1.0 = perfectly clear with context, 0.0 = completely vague/ambiguous)
2. Can we confidently resolve references without changing meaning?

[WARN] CRITICAL: Be LIBERAL with confidence scores! Most follow-up questions have clear context.

[STATS] SCORING GUIDELINES (determines bot behavior):
• Score > 0.6 -> AUTO-EXPAND (bot immediately expands references and answers)
• Score 0.3-0.6 -> ADD HINT (bot adds minimal context hint)
• Score < 0.3 -> ASK CLARIFICATION (bot asks user what they mean)

[OK] EXAMPLES - SCORE HIGH (0.7-1.0) - AUTO-EXPAND:

Query: "Tell me more about it"
Context: "Your moon sign is Gemini"
-> Score: 0.9
-> Reasoning: "it" clearly = Gemini moon (single recent topic)

Query: "Why that time?"
Context: "You will get married in March 2026"
-> Score: 0.95
-> Reasoning: "that time" clearly = March 2026

[WARN] EXAMPLES - SCORE MEDIUM (0.3-0.6) - ADD HINT:

Query: "What else should I know?"
Context: "Moon in Gemini. Career prospects are good."
-> Score: 0.5
-> Reasoning: Two topics (moon, career), unclear which one

[FAIL] EXAMPLES - SCORE LOW (0.0-0.3) - ASK CLARIFICATION:

Query: "Is this good?"
Context: [4+ topics: moon sign, career, marriage, health]
-> Score: 0.2
-> Reasoning: Multiple topics, "this" is too vague

PREVIOUS CONVERSATION:
{conv_text}

REFERENCED TOPIC (from intent analysis):
{referenced_topic}

USER'S QUERY:
"{current_query}"

Respond in JSON:
{{
    "ambiguity_score": 0.0-1.0,
    "can_resolve_safely": true/false,
    "main_ambiguous_terms": ["it", "this", etc.],
    "reasoning": "Brief explanation of score"
}}

Remember: Higher score = More confident = Bot answers immediately!
"""
        
        # STEP 1: Try to get LLM analysis
        ambiguity_analysis = None
        ambiguity_score = 0.5
        can_resolve = False
        reasoning = "Unknown"
        
        try:
            import re
            ambiguity_response = self.fast_llm.invoke(ambiguity_prompt)
            response_content = ambiguity_response.content
            
            # Try multiple JSON extraction methods
            if '```json' in response_content:
                json_str = response_content.split('```json')[1].split('```')[0].strip()
                ambiguity_analysis = json.loads(json_str)
            elif '```' in response_content:
                json_str = response_content.split('```')[1].split('```')[0].strip()
                ambiguity_analysis = json.loads(json_str)
            else:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
                if json_match:
                    ambiguity_analysis = json.loads(json_match.group())
                else:
                    ambiguity_analysis = json.loads(response_content.strip())
            
            if ambiguity_analysis:
                ambiguity_score = float(ambiguity_analysis.get('ambiguity_score', 0.5))
                can_resolve = ambiguity_analysis.get('can_resolve_safely', False)
                reasoning = ambiguity_analysis.get('reasoning', 'No reasoning')
                logger.info(f"[SEMANTIC INTERPRETER]")
                logger.debug(f"Query: {current_query}")
                logger.debug(f"Ambiguity Score: {ambiguity_score:.2f}")
                logger.debug(f"Reasoning: {reasoning}")
            
        except Exception as e:
            # Fallback to heuristics
            logger.info(f"[CONTEXT] JSON failed, using heuristics: {e}")
            query_lower = current_query.lower()
            
            if any(phrase in query_lower for phrase in ['tell me more about it', 'more about it']):
                ambiguity_score, can_resolve, reasoning = 0.9, True, "Clear follow-up (heuristic)"
            elif any(phrase in query_lower for phrase in ['tell me more', 'what else']):
                ambiguity_score, can_resolve, reasoning = 0.75, True, "Follow-up (heuristic)"
            elif any(word in query_lower for word in ['why', 'how']) and len(current_query.split()) <= 4:
                ambiguity_score, can_resolve, reasoning = 0.85, True, "Short question (heuristic)"
            elif any(ref in query_lower for ref in ['it', 'this', 'that']) and len(conversation_history) > 0:
                ambiguity_score, can_resolve, reasoning = 0.7, True, "Reference with history (heuristic)"
            else:
                ambiguity_score, can_resolve, reasoning = 0.3, False, "Unclear (heuristic)"
        
        # STEP 2: Apply strategy based on score
        # HIGH CONFIDENCE (> 0.6): Auto-expand
        if ambiguity_score > 0.6 and can_resolve:
            logger.debug(f"-> Strategy: AUTO-EXPAND")
            
            expansion_prompt = f"""You are a query pre-processor for an astrology chatbot. Your only job is pronoun resolution.

Rules:
- ONLY replace vague pronouns (it/this/that/these/those) with the specific noun from context
- Keep the original phrasing exactly as-is otherwise
- Do NOT add new topics, change the question's intent, or introduce any content not already in the query
- Do NOT answer the question — only rewrite it

Expand vague references in: "{current_query}"
Context topic: {referenced_topic}
Recent conversation: {conv_text}

Respond with ONLY the rewritten query. If nothing needs changing, return the original query unchanged.
"""
            try:
                response = self.fast_llm.invoke(expansion_prompt)
                expanded = response.content.strip()
            except:
                expanded = current_query
            
            return {
                "action": "EXPAND",
                "processed_query": expanded,
                "ambiguity_score": ambiguity_score,
                "clarification_needed": False,
                "explanation": reasoning
            }
        
        # MEDIUM CONFIDENCE (0.3-0.6): Add hint
        elif 0.3 <= ambiguity_score <= 0.6:
            logger.debug(f"-> Strategy: HINT")
            hinted = f"Regarding {referenced_topic}: {current_query}"
            
            return {
                "action": "HINT",
                "processed_query": hinted,
                "ambiguity_score": ambiguity_score,
                "clarification_needed": False,
                "explanation": reasoning
            }
        
        # LOW CONFIDENCE (< 0.3): Ask for clarification
        else:
            logger.debug(f"-> Strategy: ASK_CLARIFICATION")
            clarification_q = f"Could you clarify what you're referring to regarding {referenced_topic}?"
            
            return {
                "action": "ASK_CLARIFICATION",
                "processed_query": current_query,
                "ambiguity_score": ambiguity_score,
                "clarification_needed": True,
                "clarification_question": clarification_q,
                "explanation": reasoning
            }
    
    def generate_conversation_summary(
        self,
        conversation_history: List[Dict],
        current_summary: Optional[str] = None
    ) -> str:
        """
        Generate conversation summary, building on previous summary if exists.
        
        CRITICAL: Must integrate previous summary with new messages!
        """
        # Get recent messages (based on threshold)
        threshold = settings.CONVERSATION_SUMMARY_THRESHOLD
        recent_messages = conversation_history[-threshold:] if len(conversation_history) > threshold else conversation_history
        conv_text = self._format_conversation(recent_messages)
        
        # Build on previous summary if it exists
        if current_summary:
            summary_prompt = f"""You are updating a summary for an astrology chatbot conversation.

SCOPE RULE: Only include astrological topics (charts, planets, dashas, transits, yogas, predictions). Omit anything outside this scope.

PREVIOUS SUMMARY:
{current_summary}

NEW MESSAGES SINCE LAST SUMMARY:
{conv_text}

Task: Create an updated summary that:
1. Preserves key astrological information from previous summary
2. Adds new astrological topics/insights from new messages
3. Stays concise (2-3 sentences)
4. Maintains continuity

Respond with ONLY the updated summary.
"""
        else:
            # First summary
            summary_prompt = f"""Summarize this astrology chatbot conversation in 2-3 sentences.

SCOPE RULE: Only include astrological topics (charts, planets, dashas, transits, yogas, predictions). Omit anything outside this scope.

{conv_text}

Focus on:
- Main astrological topics discussed
- Key questions asked
- Important insights provided

Respond with ONLY the summary.
"""
        
        try:
            response = self.fast_llm.invoke(summary_prompt)
            summary = response.content.strip()
            logger.info(f"[SUMMARY] Generated: {summary[:100]}...")
            return summary
        except Exception as e:
            logger.info(f"[SUMMARY] Error: {e}")
            return current_summary or "Conversation about astrological insights."
    
    def _format_conversation(self, conversation: List[Dict]) -> str:
        """Format conversation history for LLM analysis."""
        if not conversation:
            return "No previous messages"
        
        formatted = []
        for msg in conversation:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)


import json as _json

# Global context manager instance
_context_manager = None

def get_context_manager() -> ContextManager:
    """Get canonical context manager instance from dependency container."""
    global _context_manager
    if _context_manager is None:
        try:
            _context_manager = get_shared_context_manager()
        except Exception:
            _context_manager = ContextManager()
    return _context_manager


_response_validator_llm = None


def _get_response_validator_llm():
    """Lazily create a low-temperature LLM for semantic response validation."""
    global _response_validator_llm
    if _response_validator_llm is None:
        _response_validator_llm = LLMFactory.create(
            purpose="classification",
            temperature=0.1,
        )
    return _response_validator_llm


def _normalized_word_tokens(text: str) -> List[str]:
    """Normalize free text to alphanumeric tokens for stable style matching."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [tok for tok in cleaned.split() if tok]


def _edge_signature(text: str, take_words: int = 9) -> Dict[str, str]:
    """
    Build compact opening/closing signatures for repetition checks.
    Uses normalized tokens so small punctuation differences do not evade matching.
    """
    toks = _normalized_word_tokens(text)
    if not toks:
        return {"opening": "", "closing": ""}
    opening = " ".join(toks[:take_words])
    closing = " ".join(toks[-take_words:])
    return {"opening": opening, "closing": closing}


def _recent_assistant_messages(
    recent_history: List[Dict[str, Any]],
    max_messages: int = 4,
) -> List[str]:
    """Return latest assistant messages from history for session-style memory."""
    msgs: List[str] = []
    for msg in reversed(recent_history or []):
        if msg.get("role") == "assistant" and msg.get("content"):
            msgs.append(str(msg.get("content")))
        if len(msgs) >= max_messages:
            break
    return list(reversed(msgs))


def _build_repetition_guard_context(
    candidate_answer: str,
    recent_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build session-level repetition guard context used by the validator.
    Tracks opening/closing signatures from recent assistant turns.
    """
    recent_answers = _recent_assistant_messages(recent_history, max_messages=4)
    recent_edges = [_edge_signature(a) for a in recent_answers]
    candidate_edge = _edge_signature(candidate_answer)

    opening_repeated = bool(
        candidate_edge["opening"]
        and any(candidate_edge["opening"] == e["opening"] for e in recent_edges if e["opening"])
    )
    closing_repeated = bool(
        candidate_edge["closing"]
        and any(candidate_edge["closing"] == e["closing"] for e in recent_edges if e["closing"])
    )

    return {
        "recent_openings": [e["opening"] for e in recent_edges if e["opening"]],
        "recent_closings": [e["closing"] for e in recent_edges if e["closing"]],
        "opening_repeated": opening_repeated,
        "closing_repeated": closing_repeated,
        "likely_repetition": opening_repeated or closing_repeated,
    }


def validate_and_sanitize_response(
    question: str,
    answer: str,
    intent_analysis: Dict[str, Any],
    recent_history: List[Dict[str, Any]],
    context_window: int = 20,
    min_numbered_points: int = 0,
    detected_language: Optional[str] = None,
) -> str:
    """
    Use a small LLM to semantically validate and, if needed, rewrite the draft
    answer so that it stays consistent with the user's intent and recent context.

    This replaces brittle word-level pattern matching with holistic,
    sentence-level understanding.
    """
    draft_answer = answer or ""
    today_iso = datetime.utcnow().date().isoformat()
    q_lower = (question or "").lower()
    a_lower = draft_answer.lower()
    repetition_ctx = _build_repetition_guard_context(draft_answer, recent_history)

    # Conditional validator: only rewrite when contradiction-risk or tone-risk is
    # likely, OR when we explicitly require numbered reasoning points (detailed mode).
    # This avoids flattening naturally good responses while still enforcing structure
    # when requested.
    risk_keywords = (
        "divorce", "separation", "talaq", "breakup", "remarriage",
        "children", "pregnancy", "job", "career", "marriage", "shaadi"
    )
    contradiction_markers = (
        "definitely", "guaranteed", "100%", "certainly happen"
    )
    likely_sensitive = any(k in q_lower for k in risk_keywords)
    likely_overconfident = any(m in a_lower for m in contradiction_markers)
    likely_short_or_generic = len(draft_answer.split()) < 25
    likely_repetition = bool(repetition_ctx.get("likely_repetition"))
    needs_numbering_enforcement = bool(min_numbered_points and min_numbered_points > 0)
    should_validate = (
        likely_sensitive
        or likely_overconfident
        or likely_short_or_generic
        or likely_repetition
        or needs_numbering_enforcement
    )

    if not should_validate:
        return draft_answer

    def _count_numbered_points(text: str) -> int:
        """
        Best-effort counter for clearly numbered lines like:
        '1) ...', '2. ...', '1 - ...'. Used to enforce minimum structured
        astrological reasoning points in detailed responses.
        """
        if not text:
            return 0
        count = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Arabic digits: 1) 2. 3-
            if re.match(r"^[0-9]+[\)\.\-\:]\s+", stripped):
                count += 1
                continue
            # Basic Devanagari digits: १) २. ३-
            if re.match(r"^[\u0966-\u096f]+[\)\.\-\:]\s+", stripped):
                count += 1
                continue
        return count

    def _safe_score(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _looks_like_meta_review(text: str) -> bool:
        """
        Guardrail: sometimes validator LLM returns critique text ("The draft answer...")
        instead of a user-facing rewrite. Never surface that to end users.
        """
        t = (text or "").strip().lower()
        if not t:
            return False
        meta_markers = (
            "the draft answer",
            "does not adequately",
            "lacks",
            "the user's inquiry",
            "the response should",
            "this draft",
        )
        return any(m in t for m in meta_markers)

    def _add_months(base_date, months: int):
        m = max(0, int(months))
        y = base_date.year + (base_date.month - 1 + m) // 12
        mm = (base_date.month - 1 + m) % 12 + 1
        return base_date.replace(year=y, month=mm, day=1)

    def _normalize_timeline_text(text: str) -> str:
        """
        Deterministic timeline hygiene:
        1) Convert duration-only ranges (e.g., 6-18 months / 6-18 mahine) to month-year windows.
        2) Fix past-year + future-verb mismatch (e.g., "2025 se shuru hoga").
        3) Remove ended past month/year prediction ranges and replace with future-facing fallback.
        """
        if not text:
            return text

        now = datetime.utcnow().date().replace(day=1)
        current_year = now.year

        def _duration_repl(match):
            a = int(match.group(1))
            b = int(match.group(2))
            unit = (match.group(3) or "").lower()
            if b < a:
                a, b = b, a
            if b > 48:
                return match.group(0)
            s = _add_months(now, a)
            e = _add_months(now, b)
            if any(k in unit for k in ("mahine", "saal")):
                return f"{s.strftime('%B %Y')} se {e.strftime('%B %Y')} tak"
            return f"from {s.strftime('%B %Y')} to {e.strftime('%B %Y')}"

        text = re.sub(
            r"(?i)\b(\d{1,2})\s*-\s*(\d{1,2})\s*(months?|mahine|years?|saal)\b",
            _duration_repl,
            text,
        )

        def _past_future_repl(match):
            year = int(match.group(1))
            middle = match.group(2) or ""
            verb = (match.group(3) or "").lower()
            if year >= current_year:
                return match.group(0)
            if "will" in verb:
                fixed_verb = "started and is currently active"
            else:
                fixed_verb = "shuru ho chuka hai aur abhi active hai"
            return f"{year}{middle}{fixed_verb}"

        text = re.sub(
            r"(?i)\b((?:19|20)\d{2})([^.\n]{0,40}?)(shuru\s+hoga|shuru\s+hogi|shuru\s+honge|will\s+start|will\s+begin)\b",
            _past_future_repl,
            text,
        )

        month_re = (
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        )
        range_re = re.compile(
            rf"(?i)\b({month_re}\s+(?:19|20)\d{{2}})\s*(?:to|until|till|se|tak|→|-|–|—)\s*({month_re}\s+(?:19|20)\d{{2}})\b"
        )
        year_range_re = re.compile(
            r"(?i)\b((?:19|20)\d{2})\s*(?:to|until|till|se|tak|-|–|—)\s*((?:19|20)\d{2})\b"
        )

        def _parse_my(val: str):
            v = (val or "").strip()
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return datetime.strptime(v, fmt).date().replace(day=1)
                except Exception:
                    continue
            return None

        predictive_markers = (
            "favorable", "supportive", "opportunity", "chance", "hoga", "hogi", "milega",
            "milegi", "shubh", "anukul", "sambhavna", "trip", "travel", "marriage", "shadi",
            "career", "job", "finance",
        )

        sentences = re.split(r"(?<=[.!?।])\s+", text)
        kept = []
        removed = 0
        for s in sentences:
            st = s.strip()
            if not st:
                continue
            lower = st.lower()
            has_predictive = any(m in lower for m in predictive_markers)
            drop = False

            m = range_re.search(st)
            if m and has_predictive:
                end_d = _parse_my(m.group(2))
                if end_d and end_d < now:
                    drop = True

            if not drop:
                y = year_range_re.search(st)
                if y and has_predictive:
                    if int(y.group(2)) < now.year:
                        drop = True

            if drop:
                removed += 1
                continue
            kept.append(st)

        if removed > 0:
            start = _add_months(now, 2)
            end = _add_months(now, 8)
            has_dev = any('\u0900' <= ch <= '\u097F' for ch in text)
            is_hinglish = (not has_dev) and any(tok in text.lower() for tok in ["aap", "hai", "ke", "mein", "shadi", "samay"])
            if has_dev:
                fallback = (
                    f"आगे के लिए अधिक व्यावहारिक और सहायक समय {start.strftime('%B %Y')} से {end.strftime('%B %Y')} के बीच दिखता है।"
                )
            elif is_hinglish:
                fallback = (
                    f"Aage ke liye practical supportive period {start.strftime('%B %Y')} se {end.strftime('%B %Y')} tak dikh raha hai."
                )
            else:
                fallback = (
                    f"A practical supportive future period appears between {start.strftime('%B %Y')} and {end.strftime('%B %Y')}."
                )
            kept.append(fallback)

        text = " ".join(kept).strip()
        return text

    def _has_ended_past_timeline_reference(text: str) -> bool:
        if not text:
            return False
        now = datetime.utcnow().date().replace(day=1)
        month_re = (
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        )
        range_re = re.compile(
            rf"(?i)\b({month_re}\s+(?:19|20)\d{{2}})\s*(?:to|until|till|se|tak|→|-|–|—)\s*({month_re}\s+(?:19|20)\d{{2}})\b"
        )
        year_range_re = re.compile(
            r"(?i)\b((?:19|20)\d{2})\s*(?:to|until|till|se|tak|-|–|—)\s*((?:19|20)\d{2})\b"
        )

        def _parse_my(val: str):
            v = (val or "").strip()
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return datetime.strptime(v, fmt).date().replace(day=1)
                except Exception:
                    continue
            return None

        for m in range_re.finditer(text):
            end_d = _parse_my(m.group(2))
            if end_d and end_d < now:
                return True
        for y in year_range_re.finditer(text):
            if int(y.group(2)) < now.year:
                return True
        return False

    def _is_mostly_english(text: str) -> bool:
        if not text:
            return False
        words = re.findall(r"[A-Za-z]+", text.lower())
        if not words:
            return False
        common = {
            "the", "and", "for", "with", "your", "you", "this", "that", "will", "from",
            "period", "future", "relationship", "marriage", "insight", "summary", "context",
        }
        hit = sum(1 for w in words if w in common)
        return (hit / max(1, len(words))) > 0.08

    def _has_hinglish_markers(text: str) -> bool:
        t = (text or "").lower()
        markers = ["aap", "hai", "hain", "ki", "ka", "ke", "mein", "se", "tak", "samay", "shadi", "kya"]
        return sum(1 for m in markers if m in t) >= 3

    def _language_or_script_violation(text: str, expected: Optional[str]) -> bool:
        exp = (expected or "").strip().lower()
        if not exp:
            return False
        dev_count = sum(1 for ch in (text or "") if '\u0900' <= ch <= '\u097F')

        if exp == "hi":
            return dev_count < 8
        if exp == "hi-lat":
            # Hinglish should be in Latin script and not plain generic English.
            if dev_count > 0:
                return True
            return _is_mostly_english(text) and not _has_hinglish_markers(text)
        if exp == "en":
            return dev_count > 0
        return False

    def _has_robotic_heading_leak(text: str) -> bool:
        if not text:
            return False
        heading_patterns = [
            r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(current dasha context|upcoming pratyantar period|future activation period|broader future period|long-term perspective)\*?\*?\s*:",
            r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(chart strengths and positive aspects|gochara insights|yogas and potential challenges)\*?\*?\s*:",
            r"(?i)\blet'?s delve deeper\b",
        ]
        return any(re.search(p, text) for p in heading_patterns)

    try:
        conv_snippet: List[str] = []
        for msg in (recent_history or [])[-context_window:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conv_snippet.append(f"{role.upper()}: {content}")
        conv_text = "\n".join(conv_snippet) or "No previous messages"

        analysis = intent_analysis or {}

        validator_prompt = f"""You are a semantic validator AND style judge for an astrology chatbot.

Your job is to check whether the assistant's draft answer is:
- logically correct and non-contradictory
- emotionally appropriate to what the user asked
- consistent with the recent conversation history
- written in the natural voice of a warm, expert astrologer (NOT a generic AI assistant)

You MUST rely on MEANING, not keyword matching. Think about what the user is
really asking and whether the answer respects that.

You must pay special attention to these cases:

1) DIVORCE / SEPARATION QUERIES
   - When the user asks about divorce or separation, the answer MUST:
     • Acknowledge that the user is asking about possible strain, distance, or separation.
     • Focus on relationship pressure/tension phases, and talk gently about communication,
       boundaries, or counseling.
   - The answer MUST NOT:
     • Re-start the discussion as if it is a "happy marriage timing" or "favourable time for marriage".
     • Celebrate getting a new partner, strong romantic progress, or "bahut hi accha/sukhad samay"
       for marriage immediately after a divorce question.
   - Only talk about favourable marriage / remarriage timing if the user explicitly asks
     about remarriage in a later question.

2) TIMELINE COHERENCE
   - If the chat already stated a clear FUTURE window for a life event (marriage, job, career,
     foreign travel, children, etc.), do NOT allow a later answer to confidently state a
     completely different, non-overlapping window for the SAME topic unless you clearly frame
     it as a refinement or secondary/supporting period.
   - For example, if the initial answer said "2027 ke beech se 2028 ke aas-paas shadi ke strong
     yog dikh rahe hain", the detailed follow-up should EITHER reuse that 2027–2028 window,
     OR explain it as "core" and then optionally add a nearby supporting sub‑window, not jump
     to something like "2024 ke end tak" as the main window.
   - When the chat already gave a specific timing, prefer to KEEP that timing and add depth
     (houses, dashas, yogas, divisional charts) rather than inventing a new, contradictory one.
   - For divorce/separation specifically, do NOT push it clearly BEFORE a strong future marriage
     window that you already stated. In such cases, soften the timing for divorce (e.g.,
     "aane wale kuch saalon mein") and emphasize emotional themes rather than hard earlier dates.

3) GENERAL COHERENCE
   - Avoid sentences that directly contradict what was said just before
     (e.g., "no children possible" right after "strong chance for children in 2028").
   - Avoid robotic repetition of the same phrasing; keep the tone natural and human.
   - If the DRAFT answer already ends with a clear, user-facing follow-up question
     (for example, inviting them to ask more about a specific topic), your revised
     answer MUST also end with a natural follow-up question in the SAME spirit and
     on the SAME topic, unless the conversation has clearly moved on. Do NOT strip
     away the closing question and leave the user hanging.
   - When the user's question is a simple, everyday request (e.g. "meri shadi kab hogi",
     "job kab milegi", "ghar kab kharid paunga") and does NOT contain astrological
     jargon, the SHORT initial answer must also avoid explicit house/planet/dasha
     terminology (no "7th house", "lord", "Venus", "Mars", "dasha", etc.). In such
     cases, if the draft uses these technical terms in a brief timing answer, rewrite
     them into plain-life language (supportive phase, opportunity, pressure, etc.)
     while keeping the timing window and meaning intact.

   - FUTURE-ONLY TIMING (NON-NEGOTIABLE):
     • TODAY is {today_iso}.
     • Do NOT output past timing windows as prediction windows.
     • Any explicit month/year/date ranges in the revised answer must be active-now or future-facing.
     • If a range has already passed, reframe it into future/supportive windows from TODAY onward.
     • For user-facing timelines, prefer explicit month-year ranges ("Aug 2026 to Nov 2026")
       and avoid duration-only phrases like "6-18 months" / "6-18 mahine" as final timing.

4) LIFE-EVENT ORDERING (CRITICAL)
   - NEVER make the timeline of major life events obviously backwards relative to what
     the conversation already established. Examples of IMPOSSIBLE orderings:
       • Predicting divorce clearly BEFORE a strong future marriage window that you
         already stated in this conversation.
       • Saying the user will have children clearly BEFORE marriage, when earlier
         messages framed marriage as a necessary prior step.
       • Saying a second marriage window that begins clearly BEFORE the first marriage
         window you already gave.
   - When you detect such a conflict, you MUST:
       • Keep the emotional truth (e.g., "tension", "distance", "responsibility for family"),
         but soften or widen the timing ("aane wale kuch saalon mein", "2026 ke baad ke kuch
         saal") instead of giving a hard, earlier year or narrow window that breaks the
         logical order.
       • If needed, explicitly say that astrology shows phases of pressure or change rather
         than a precise date, so you do not contradict the already stated sequence of events.

5) TONE & VOICE QUALITY (LLM-AS-A-JUDGE)
   - The final answer must sound like a professional, warm astrologer speaking directly
     to the user, not like a generic AI model or technical report.
   - Strongly avoid generic "AI-speak" phrases such as: "let's delve into", "as an AI",
     "cutting-edge", "state-of-the-art model", "this is a testament to", or anything that
     breaks the illusion of a human astrologer.
   - Prefer astro-appropriate, probabilistic wording:
       • Instead of "guaranteed", "definitely", "certain", prefer "strong support", "zyada sambhavna",
         "indicates", "tends to manifest", "suggests a phase where...".
       • Emphasize free will, effort and practical choices over fate or fixed destiny.
   - Preserve the user's language and script from the draft answer. If the draft is in Hindi
     or Hinglish, your revision must also be in the same language/script (do NOT switch to English).
   - You may gently improve phrasing, flow and warmth as long as you do not change factual content,
     dates, or key timing windows already stated in the draft.

6) EMOTIONAL MIRROR + SESSION REPETITION GUARD
   - The opening line should briefly mirror the user's emotional intent when appropriate
     (e.g., concern, confusion, urgency, hope) before analysis.
   - Avoid repeating the same opening/closing style used in recent assistant replies.
   - If this draft repeats recent opening/closing signatures, rewrite with fresh phrasing
     while preserving facts and timing.

RECENT STYLE MEMORY (normalized phrase signatures from latest assistant turns):
- Recent openings: {_json.dumps(repetition_ctx.get("recent_openings", []), ensure_ascii=False)}
- Recent closings: {_json.dumps(repetition_ctx.get("recent_closings", []), ensure_ascii=False)}
- Candidate flags: opening_repeated={repetition_ctx.get("opening_repeated")}, closing_repeated={repetition_ctx.get("closing_repeated")}

EXAMPLE CORRECTIONS (FEW-SHOT GUIDANCE)

Example 1 – BAD marriage tone after divorce question:
- CONTEXT:
  - Earlier answer: "2027 ke shuruat se 2028 ke beech shaadi ke sabse strong yog dikh rahe hain..."
  - USER now: "Meri divorce kab hoga?"
- DRAFT: "Aapke liye shadi ka samay abhi bahut hi favourable dikh raha hai..."
- YOU SHOULD REWRITE AS (Hindi tone preserved, but meaning fixed):
  "Aapke sawal se yeh samajh aata hai ki aap apne rishte mein alag hone ya bade badlav ki sambhavana ke baare mein soch rahe hain. Chart ke hisaab se aane wale kuch saalon mein aise phases aa sakte hain jahan tanav, doori ya uljhan zyada mehsoos ho, khaas taur par 2026 ke doosre aadhe se 2027 ke dauran. Is daur ko jaldi decision ke bajay khuli baat-cheet, boundaries clear karne aur zarurat pade to counseling ke zariye handle karna zyada sehatmand rahega. Astrology yeh batati hai ki yeh ek pressure phase hai jahan aapko apni emotional safety, respect aur bhavishya ke baare mein soch-samajh kar kadam rakhna chahiye. Kya aap chahenge ki main aapko is phase ke exact months aur chart ke un factors ke baare mein bataun jo yeh tanav dikhate hain?"

Example 2 – BAD divorce before earlier marriage window:
- CONTEXT:
  - Earlier: "Shaadi ke liye sabse strong window 2027–2028 ke beech dikh rahi hai."
  - USER now: "Mera divorce kab hoga?"
- DRAFT: "2026 ke beech tak divorce hone ke chances strong hain."
- YOU SHOULD REWRITE AS:
  "Pehle humne dekha tha ki 2027–2028 ke aas-paas shaadi ke liye strong support dikh raha hai, isliye usse pehle hi exact divorce saal batana theek nahi hoga. Chart yeh dikhata hai ki shaadi ke baad kuch saalon mein zimmedariyon aur expectations ke chalte rishte par pressure aa sakta hai, jahan tanav ya doori mehsoos ho. Is tarah ke daur ko samvaad, practical support aur zarurat pade to counseling se kaafi had tak sambhala ja sakta hai. Agar aap separation ke baare mein soch rahe hain, to pehle apni emotional aur financial safety par dhyan dena zaruri hai, na ki sirf tareekh par."

Example 3 – GOOD draft you should keep:
- CONTEXT:
  - USER: "Mujhe government job kab milegi?"
- DRAFT:
  "Aapke liye sarkari naukri ke liye sabse zyada support 2026 ke doosre aadhe se lekar 2027 ke pehle hisson tak dikhai deta hai. Is dauran exams, interviews aur selection ke liye active rehna aapke liye zyada fruitful ho sakta hai. Agar aap is period mein focused preparation karein, to ek stable government job milne ke chances mazboot dikhai dete hain."
- In this case, "is_coherent": true, "needs_revision": false, "revised_answer": "".

CONVERSATION (last {context_window} messages):
{conv_text}

LATEST USER QUESTION:
USER: "{question}"

INTENT ANALYSIS (for your reference):
{_json.dumps(analysis, ensure_ascii=False)}

DRAFT ASSISTANT ANSWER (in user's language):
ASSISTANT_DRAFT:
\"\"\"{draft_answer}\"\"\"

IMPORTANT DECISION RULE:
- If draft is already coherent, context-appropriate and naturally phrased, preserve it — UNLESS
  a specific numbered structure has been requested.
- Rewrite when there is a real contradiction, tone/voice mismatch, obvious generic AI phrasing,
  major coherence break, OR when the answer fails to provide the minimum number of numbered
  astrological reasoning points requested.
- Your revised answer must be direct user-facing astrology guidance, NEVER a reviewer note,
  audit explanation, or critique of the draft.

STRUCTURE ENFORCEMENT (if requested):
- When 'min_numbered_points' is > 0, you MUST ensure that the final answer contains AT LEAST
  that many clearly numbered points (for example: "1)", "2)", "3)", etc.), and you should
  NOT artificially stop at that number if more distinct, meaningful factors are available.
- Each numbered point should describe a distinct astrological factor AND what it means for
  the user. These points can appear after a short narrative introduction, but they must be
  present and easy for the user to see and count.

Respond in STRICT JSON ONLY, no extra text, like this:
{{
  "is_coherent": true/false,
  "needs_revision": true/false,
  "reason": "short explanation of any problem you see",
  "revised_answer": "a fully corrected answer in the SAME LANGUAGE as the draft, or empty string if no change is needed",
  "human_warmth_score": 1-10,
  "authentic_astrologer_voice_score": 1-10,
  "repetition_risk_score": 1-10,
  "min_numbered_points": """ + str(int(min_numbered_points or 0)) + """
}}"""

        llm = _get_response_validator_llm()
        resp = llm.invoke(validator_prompt)
        raw = getattr(resp, "content", str(resp))
        data = _json.loads(raw)

        final_answer = draft_answer
        if isinstance(data, dict) and data.get("needs_revision") and data.get("revised_answer"):
            candidate = str(data.get("revised_answer", "")).strip()
            if _looks_like_meta_review(candidate):
                logger.warning("[VALIDATOR] Ignoring meta-review text returned as revised_answer; keeping draft.")
            else:
                logger.info(f"[VALIDATOR] LLM revised answer: {data.get('reason', '')}")
                final_answer = candidate

        # Secondary style gate: enforce warmth/authenticity/repetition quality
        # even when the model marks the draft as coherent.
        if isinstance(data, dict):
            warmth = _safe_score(data.get("human_warmth_score", 10), 10)
            authenticity = _safe_score(data.get("authentic_astrologer_voice_score", 10), 10)
            repetition_risk = _safe_score(data.get("repetition_risk_score", 1), 1)
            min_warmth = max(1, min(10, int(getattr(settings, "STYLE_MIN_HUMAN_WARMTH_SCORE", 7))))
            min_auth = max(1, min(10, int(getattr(settings, "STYLE_MIN_AUTHENTIC_ASTROLOGER_VOICE_SCORE", 7))))
            max_repeat = max(1, min(10, int(getattr(settings, "STYLE_MAX_REPETITION_RISK_SCORE", 4))))
            needs_style_rewrite = (
                (warmth < min_warmth)
                or (authenticity < min_auth)
                or (repetition_risk > max_repeat)
            )

            if needs_style_rewrite and not (data.get("needs_revision") and data.get("revised_answer")):
                logger.info(
                    "[VALIDATOR] Style rewrite triggered "
                    f"(warmth={warmth}<{min_warmth}, "
                    f"authenticity={authenticity}<{min_auth}, "
                    f"repetition_risk={repetition_risk}>{max_repeat})"
                )
                style_rewrite_prompt = f"""You are a response polishing editor for an astrology assistant.

Rewrite the answer so that it:
- keeps the SAME factual content, timing windows, and astrological meaning
- stays in the SAME language/script
- sounds warm, natural, and like a real expert astrologer
- starts with a brief emotional mirror of the user's concern (1 line max)
- avoids repeating recent opening/closing phrasing
- remains concise and user-facing (not a report)

Do NOT invent new dates, planets, houses, or claims.

RECENT STYLE MEMORY:
- Openings: {_json.dumps(repetition_ctx.get("recent_openings", []), ensure_ascii=False)}
- Closings: {_json.dumps(repetition_ctx.get("recent_closings", []), ensure_ascii=False)}

USER QUESTION:
\"\"\"{question}\"\"\"

ANSWER TO REWRITE:
\"\"\"{final_answer}\"\"\"

Return ONLY the rewritten answer text."""
                style_resp = llm.invoke(style_rewrite_prompt)
                polished = getattr(style_resp, "content", str(style_resp)).strip()
                if polished:
                    final_answer = polished

        # Deterministic post-check: if we explicitly require numbered points
        # and the current answer still does not meet the minimum, trigger a
        # second, focused rewrite pass that ONLY enforces numbered structure.
        if needs_numbering_enforcement:
            required_points = int(min_numbered_points or 0)
            current_points = _count_numbered_points(final_answer)
            if current_points < required_points:
                logger.info(
                    f"[VALIDATOR] Numbering enforcement: found {current_points} "
                    f"points, required {required_points}. Forcing rewrite."
                )
                rewrite_prompt = f"""You are an astrology editor.

Rewrite the assistant's answer so that it:
- keeps the SAME timing windows, planets, houses and factual content
- stays in the SAME LANGUAGE and script as the original answer
- sounds like a warm, professional astrologer
- and MOST IMPORTANTLY, presents AT LEAST {required_points} clearly numbered
  astrological reasoning points (for example: "1) ...", "2) ...", "3) ...").

Guidelines:
- You may add short connector sentences, but do NOT invent new dates or change years.
- Group related ideas into numbered points so that each point describes ONE key factor
  (house lord, dasha/pratyantar, yoga, planetary condition, divisional chart insight, etc.)
  and directly states what it means for this person's life.
- You may keep a short 1–2 sentence introduction BEFORE the numbered list.
- CRITICAL: If the original answer ends with a question about a DIFFERENT life area (e.g. career, health, marriage, children, finances), you MUST preserve that exact question at the very end of your rewrite. Do NOT replace it with an offer for more detail or further explanation.

Return ONLY the rewritten answer text, no JSON, no explanation.

ORIGINAL ANSWER:
\"\"\"{final_answer}\"\"\""""
                resp2 = llm.invoke(rewrite_prompt)
                rewritten = getattr(resp2, "content", str(resp2)).strip()
                if rewritten and not _looks_like_meta_review(rewritten):
                    logger.info("[VALIDATOR] Applied forced numbered-structure rewrite")
                    final_answer = rewritten

                # After the LLM rewrite, run a deterministic fallback to guarantee
                # visible numbering if the model still did not meet the requirement.
                post_points = _count_numbered_points(final_answer)
                if post_points < required_points:
                    logger.info(
                        f"[VALIDATOR] Deterministic numbering fallback: found {post_points}, "
                        f"required {required_points}. Prefixing numbered points."
                    )
                    lines = final_answer.splitlines()
                    numbered_lines: List[str] = []
                    point_idx = 1
                    for line in lines:
                        stripped = line.strip()
                        if (
                            stripped
                            and point_idx <= required_points
                            and not re.match(r"^[0-9\u0966-\u096f]+[\)\.\-\:]\s+", stripped)
                        ):
                            numbered_lines.append(f"{point_idx}) {line.lstrip()}")
                            point_idx += 1
                        else:
                            numbered_lines.append(line)
                    final_answer = "\n".join(numbered_lines)

        final_answer = _normalize_timeline_text(final_answer)

        # HARD FAIL-SAFE: never return ended past prediction ranges.
        # 1) One forced rewrite pass.
        # 2) If still present, deterministic cleanup via timeline normalizer.
        if _has_ended_past_timeline_reference(final_answer):
            logger.warning("[VALIDATOR] Ended past timeline detected post-normalization. Forcing one additional rewrite.")
            hard_fix_prompt = f"""You are fixing timeline safety in an astrology answer.

TODAY is {today_iso}.

Rewrite the answer so that:
- it keeps the SAME main astrological meaning and language/script
- it removes any ended past prediction ranges
- all prediction windows are ongoing/future-facing month-year ranges
- no exact day-level dates

Return ONLY the corrected answer text.

ANSWER:
\"\"\"{final_answer}\"\"\""""
            hard_resp = llm.invoke(hard_fix_prompt)
            hard_text = getattr(hard_resp, "content", str(hard_resp)).strip()
            if hard_text and not _looks_like_meta_review(hard_text):
                final_answer = _normalize_timeline_text(hard_text)

        if _has_ended_past_timeline_reference(final_answer):
            logger.warning("[VALIDATOR] Ended past timeline still present after forced rewrite. Applying deterministic final cleanup.")
            final_answer = _normalize_timeline_text(final_answer)

        # HARD FAIL-SAFE: keep language/script consistent and avoid robotic report headings.
        if _language_or_script_violation(final_answer, detected_language) or _has_robotic_heading_leak(final_answer):
            logger.warning(
                "[VALIDATOR] Language/script or heading-style violation detected. Forcing one natural-voice rewrite."
            )
            _lang = (detected_language or "same as draft").strip()
            style_fix_prompt = f"""You are fixing final response style for an astrology chatbot.

Rewrite the answer so that:
- it stays in { _lang } language/script (or same as draft if unknown),
- it sounds like natural conversational astrologer guidance,
- it does NOT use report-like headings such as:
  "Current Dasha Context", "Upcoming Pratyantar Period", "Broader Future Period", "Long-term Perspective",
- it does NOT use phrases like "Let's delve deeper",
- it preserves the same factual meaning and timing windows.

Return ONLY the corrected answer text.

ANSWER:
\"\"\"{final_answer}\"\"\""""
            style_fix_resp = llm.invoke(style_fix_prompt)
            style_fixed = getattr(style_fix_resp, "content", str(style_fix_resp)).strip()
            if style_fixed and not _looks_like_meta_review(style_fixed):
                final_answer = _normalize_timeline_text(style_fixed)
                # deterministic phrase cleanup if model still leaked headings
                final_answer = re.sub(
                    r"(?im)^\s*(?:\d+\.\s*)?\*?\*?(current dasha context|upcoming pratyantar period|future activation period|broader future period|long-term perspective|chart strengths and positive aspects|gochara insights|yogas and potential challenges)\*?\*?\s*:\s*",
                    "",
                    final_answer,
                )
                final_answer = re.sub(r"(?i)\blet'?s delve deeper\b", "Chaliye detail mein samajhte hain", final_answer)

        return final_answer
    except Exception as e:
        logger.info(f"[VALIDATOR] Error in LLM response validator: {e}")
        return draft_answer


# ============================================================================
# SESSION MANAGER — single source of truth is src/session/manager.py (SessionManager).
# EnhancedSessionManager has been removed; the fallback below also uses SessionManager
# so there is only ever one class in play, eliminating key-name and signature divergence.
# ============================================================================


def _infer_voice_preferences_from_message(question: str) -> Optional[Dict[str, str]]:
    """
    Infer consultation preferences from the user's message (e.g. "keep it short", "no remedies").
    Returns a dict of keys to merge into stored voice_preferences, or None if nothing inferred.
    """
    if not question or len(question.strip()) < 3:
        return None
    q = question.lower().strip()
    out: Dict[str, str] = {}
    # Detail level
    if any(phrase in q for phrase in ("keep it short", "short answer", "brief only", "brief answer", "short reply", "in short", "bas batao", "sirf short", "zyada mat likho")):
        out["detail_level"] = "brief"
    elif any(phrase in q for phrase in ("full detail", "detailed answer", "explain in detail", "puri detail", "sab batao", "vistar se")):
        out["detail_level"] = "detailed"
    # Remedy preference
    if any(phrase in q for phrase in ("no remedies", "no upayas", "without remedies", "remedy mat batao", "upaya mat do")):
        out["remedy_preference"] = "avoid"
    elif any(phrase in q for phrase in ("remedies batao", "upaya batao", "suggest remedies", "include remedies")):
        out["remedy_preference"] = "include"
    # Tone
    if any(phrase in q for phrase in ("cautious", "conservative", "sambhal ke", "careful")):
        out["tone"] = "cautious"
    elif any(phrase in q for phrase in ("encouraging", "positive", "hopeful", "positive raho")):
        out["tone"] = "encouraging"
    return out if out else None


# Global session manager — always SessionManager from src/session/manager.py
_session_manager = None

def get_session_manager():
    global _session_manager
    if _session_manager is None:
        try:
            _session_manager = get_shared_session_manager()
        except Exception:
            # Fallback: create a fresh SessionManager directly (same class, same keys)
            from src.session.manager import SessionManager
            _session_manager = SessionManager()
    return _session_manager


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class UserProfile(BaseModel):
    """User profile data."""
    user_id: str
    name: str
    date_of_birth: str = Field(..., description="YYYY-MM-DD format")
    time_of_birth: str = Field(..., description="HH:MM:SS format")
    place_of_birth: str
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"
    preferred_system: str = "vedic"


class VoicePreferences(BaseModel):
    """Optional consultation-style preferences (honored when building responses)."""
    detail_level: Optional[str] = Field(None, description="brief | balanced | detailed")
    remedy_preference: Optional[str] = Field(None, description="include | avoid | neutral")
    tone: Optional[str] = Field(None, description="cautious | balanced | encouraging")


class ConversationHistoryItem(BaseModel):
    """Single conversation item from external system."""
    question: str
    answer: str
    source: str = "external"
    timestamp: Any


class InitializeSessionRequest(BaseModel):
    """Request to initialize a new session."""
    user_id: str = Field(..., description="User identifier (also used as session_id)")
    user_profile: UserProfile
    conversation_history: Optional[List[ConversationHistoryItem]] = []
    voice_preferences: Optional[VoicePreferences] = Field(None, description="Optional consultation style preferences")


class InitializeSessionResponse(BaseModel):
    """Response from session initialization."""
    user_id: str
    status: str


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    user_id: str = Field(..., description="User identifier (same as session_id)")
    question: str


class SendMessageResponse(BaseModel):
    """Response from message."""
    user_id: str
    question: str
    answer: str
    source: str = "openai"
    evidence: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# ENDPOINT 1: INITIALIZE SESSION
# ============================================================================

@router.post("/initialize", response_model=InitializeSessionResponse)
def initialize_session(request: InitializeSessionRequest):
    """Initialize a new chatbot session."""
    try:
        session_manager = get_session_manager()
        user_id = request.user_id

        conversation = []
        if request.conversation_history:
            conversation = [item.dict() for item in request.conversation_history]

        if session_manager.session_exists(user_id):
            # ── SELECTIVE REFRESH ─────────────────────────────────────────────
            # Session exists.  We must NOT blindly skip re-initialization —
            # the caller may be sending updated conversation_history (new Q&As
            # from the old system) or the chart/dasha cache may be stale.
            #
            # Strategy:
            #   1. Always overwrite conversation_history so new external messages
            #      are imported (they will be filtered at LLM call time if "external").
            #   2. Always overwrite user_profile so DOB / timezone changes take effect.
            #   3. Evict chart + dasha + transit cache so they are recomputed with
            #      the fixed engine on the next /message call.
            #   4. Do NOT recreate metadata or summary (preserve session continuity).
            logger.info(f"[REDIS] Session already exists for {user_id} — performing selective refresh.")

            # Refresh profile (DOB / timezone may have changed)
            profile_dict = (
                request.user_profile.model_dump()
                if hasattr(request.user_profile, 'model_dump')
                else request.user_profile.dict()
            )
            session_manager.update_user_profile(user_id, profile_dict)

            # Overwrite history so freshly-imported external Q&As are stored
            if request.conversation_history:
                conversation = [item.dict() for item in request.conversation_history]
                session_manager.overwrite_conversation_history(user_id, conversation)
                logger.info(f"[REDIS] History refreshed: {len(conversation)} external messages imported.")

            # Evict stale calculated data — forces recompute on next /message
            session_manager.evict_calculated_data(user_id)
            logger.info(f"[REDIS] Stale chart/dasha/transit cache evicted for {user_id}.")

            if request.voice_preferences is not None:
                prefs = request.voice_preferences.model_dump() if hasattr(request.voice_preferences, "model_dump") else request.voice_preferences.dict()
                prefs_clean = {k: v for k, v in prefs.items() if v is not None}
                if prefs_clean:
                    session_manager.store_voice_preferences(user_id, prefs_clean)

            try:
                _post_refresh_hist = session_manager.get_conversation_history(user_id) or []
                logger.info(
                    f"[REDIS][INIT_SANITY] post-refresh history count for {user_id}: {len(_post_refresh_hist)} "
                    f"(input_history_count={len(conversation)})"
                )
            except Exception as _hist_e:
                logger.info(f"[REDIS][INIT_SANITY] history check skipped for {user_id}: {_hist_e}")

            return InitializeSessionResponse(
                user_id=user_id,
                status="refreshed"
            )

        result = session_manager.initialize_session(
            user_id=user_id,
            user_profile=request.user_profile.model_dump() if hasattr(request.user_profile, 'model_dump') else request.user_profile.dict(),
            conversation_history=conversation
        )

        if request.voice_preferences is not None:
            prefs = request.voice_preferences.model_dump() if hasattr(request.voice_preferences, "model_dump") else request.voice_preferences.dict()
            prefs_clean = {k: v for k, v in prefs.items() if v is not None}
            if prefs_clean:
                session_manager.store_voice_preferences(user_id, prefs_clean)

        logger.info(f"[REDIS] Initialized NEW session for {user_id} - Status: {result['status']}")

        try:
            _post_init_hist = session_manager.get_conversation_history(user_id) or []
            _input_hist_count = len(conversation)
            logger.info(
                f"[REDIS][INIT_SANITY] post-init history count for {user_id}: {len(_post_init_hist)} "
                f"(input_history_count={_input_hist_count})"
            )
            # If caller started a clean session but history is unexpectedly long,
            # surface a warning for reset semantics debugging.
            if _input_hist_count == 0 and len(_post_init_hist) > 1:
                logger.warning(
                    f"[REDIS][INIT_SANITY] Unexpected non-empty history after clean initialize for {user_id} "
                    f"(count={len(_post_init_hist)})."
                )
        except Exception as _hist_e:
            logger.info(f"[REDIS][INIT_SANITY] history check skipped for {user_id}: {_hist_e}")

        return InitializeSessionResponse(
            user_id=result['user_id'],
            status=result['status']
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.info(f"[SESSION_ERROR] Error initializing session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize session: {str(e)}"
        )




# ============================================================================
# ENDPOINT 2: SEND MESSAGE with Context Management
# ============================================================================

@router.post("/message", response_model=SendMessageResponse)
def send_message(request: SendMessageRequest):
    """
    Send a message with professional context management.
    
    Features:
    - LLM-based intent analysis (Continuation/New Topic/Clarification)
    - Contextual query resolution
    - Conversation summarization every 10 messages
    - Comprehensive logging
    """
    start_time = time.time()
    
    try:
        session_manager = get_session_manager()
        context_manager = get_context_manager()
        user_id = request.user_id
        question = request.question
        
        # Get user profile
        try:
            user_profile = session_manager.get_user_profile(user_id)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Backend session database (Redis) is unavailable: {str(e)}"
            )
        if not user_profile:
            logger.info(f"[WARNING] /message blocked: Session not found in Redis for user: {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Session not found for user: {user_id}. Please call /initialize first."
            )

        # ====================================================================
        # PRE-STEP: VULGARITY GATE — runs before ANY LLM call or context analysis.
        # This must be here because chat_stateless.py can return early (clarification
        # path) before the orchestrator's safety_check node ever runs, so classifier.py
        # Gate -2 would never execute for those messages.
        # ====================================================================
        _VULGAR_KW = {
            'fuck', 'shit', 'bitch', 'asshole', 'bastard', 'motherfucker',
            'dick', 'pussy', 'cock', 'cunt', 'whore', 'slut', 'nude', 'porn',
            'pornography', 'masturbat', 'sex position', 'sexual position',
            'chutiya', 'madarchod', 'bhosdike', 'bhosdika', 'randi', 'harami',
            'gaandu', 'gandu', 'lund', 'chut', 'bhenchod', 'behenchod',
            'maderchod', 'haramzada', 'haramkhor', 'madarjaat', 'lavde', 'lavda',
            'punda', 'pundai', 'sunni', 'thevidiya', 'ootha', 'koothi', 'oombu',
            'dengey', 'dengudi', 'pukku', 'modda', 'lanja', 'pooku',
            'zavnya', 'zavad', 'bhadva', 'zadya',
            'bhen di', 'teri maa', 'phudu', 'phuddu', 'maa di',
            'theetta', 'myre', 'kunna', 'pooru', 'poori', 'ammaye',
            'haraamzada', 'gaand', 'khanki', 'madar', 'sala kutta',
            'चुतिया', 'मादरचोद', 'भड़वा', 'रंडी', 'हरामी', 'लंड', 'भोसड़ी',
            'புண்டை', 'சுன்னி', 'తేవిడియా',
            'పుక్కు', 'మొద్ద', 'లంజ',
            'झवाड', 'भडवा', 'लवडा',
            'ਭੈਣ ਦੀ', 'ਫੁੱਡੂ',
            'കുണ്ണ', 'പൂറ്',
        }
        _ASTRO_SAFE = frozenset([
            'kundli', 'kundali', 'horoscope', 'rashi', 'lagna', 'nakshatra', 'dasha',
            'antardasha', 'mahadasha', 'graha', 'planet', 'saturn', 'jupiter', 'venus',
            'mars', 'mercury', 'moon', 'sun', 'rahu', 'ketu', 'shani', 'mangal',
            'budh', 'brihaspati', 'shukra', 'surya', 'chandra', 'transit', 'gochar',
            'chart', 'vedic', 'jyotish', 'yoga', 'bhava', 'house',
            'marriage', 'shaadi', 'career', 'naukri', 'health', 'money', 'dhan',
            'foreign', 'videsh', 'child', 'bachha', 'santan', 'property', 'ghar',
        ])

        def _is_vulgar(text: str) -> bool:
            """Keyword check + LLM fallback for vulgarity not in the keyword list."""
            t = text.lower()
            # 1. Fast keyword check
            if any(kw in t for kw in _VULGAR_KW):
                return True
            # 2. Skip LLM check if the query is clearly astrological (saves latency)
            if set(t.split()) & _ASTRO_SAFE:
                return False
            # 3. LLM fallback — catches abbreviations, creative spellings, euphemisms,
            #    code-switching, and languages not covered by the keyword list.
            try:
                llm_prompt = (
                    "You are a content moderator for a professional astrology chatbot. "
                    "Does the following message contain profanity, sexual explicitness, "
                    "verbal abuse, sexual harassment, or vulgar insults in ANY language "
                    "(including abbreviations like 'bc', 'mc', 'lc', creative spellings, "
                    "or mixed-language abuse)?\n\n"
                    f'Message: "{text}"\n\n'
                    "Reply with exactly one word: YES or NO."
                )
                resp = context_manager.fast_llm.invoke(llm_prompt)
                result_text = resp.content.strip().upper()
                if result_text.startswith("YES"):
                    logger.info(f"[PRE-SAFETY] LLM vulgarity fallback triggered — blocking")
                    return True
            except Exception as _e:
                logger.info(f"[PRE-SAFETY] LLM vulgarity check error (fail-open): {_e}")
            return False

        if _is_vulgar(question):
            logger.info(f"[PRE-SAFETY] Vulgar content detected — returning hard block")
            from src.safety.templates import HARD_BLOCK_VULGAR
            session_manager.add_message(user_id, "user", question)
            session_manager.add_message(user_id, "assistant", HARD_BLOCK_VULGAR,
                                        metadata={"intent": "HARD_BLOCK", "source": "safety"})
            return SendMessageResponse(
                user_id=user_id,
                question=question,
                answer=HARD_BLOCK_VULGAR,
                source="Nakshatra-ai"
            )

        # ====================================================================
        # STEP 1: GET CONVERSATION CONTEXT
        # ====================================================================
        full_history = session_manager.get_conversation_history(user_id) or []
        conversation_summary = session_manager.get_conversation_summary(user_id)
        
        logger.debug(f"{'='*80}")
        logger.info(f"[REDIS CONVERSATION CONTEXT] Fetched from Redis for User: {user_id}")
        logger.debug(f"{'='*80}")
        logger.debug(f"Total messages in history: {len(full_history)}")
        logger.debug(f"Conversation summary available: {'Yes' if conversation_summary else 'No'}")
        if conversation_summary:
            logger.debug(f"Summary: {conversation_summary[:100]}...")
        
        # Verification: Show what's in Redis
        if full_history:
            logger.info(f"[REDIS VERIFICATION] Conversation history details:")
            for i, msg in enumerate(full_history[:6]):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:60]
                source = msg.get('metadata', {}).get('source', 'N/A')
                logger.debug(f"{i+1}. [{role.upper():9}] {content}... (source: {source})")
            
            if len(full_history) > 6:
                logger.debug(f"... and {len(full_history) - 6} more messages")
        else:
            logger.info(f"[REDIS VERIFICATION] No conversation history (first message)")
            logger.debug(f"{'='*80}")
            logger.info(f"[REDIS CONVERSATION CONTEXT] Fetched from Redis for User: {user_id}")
            logger.debug(f"{'='*80}")
            logger.debug(f"Total messages in history: {len(full_history)}")
            logger.debug(f"Conversation summary available: {'Yes' if conversation_summary else 'No'}")
            if conversation_summary:
                logger.debug(f"Summary: {conversation_summary[:100]}...")
            
            # Verification: Show what's in Redis
            if full_history:
                logger.info(f"[REDIS VERIFICATION] Conversation history details:")
                for i, msg in enumerate(full_history[:6]):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:60]
                    source = msg.get('metadata', {}).get('source', 'N/A')
                    logger.debug(f"{i+1}. [{role.upper():9}] {content}... (source: {source})")
                
                if len(full_history) > 6:
                    logger.debug(f"... and {len(full_history) - 6} more messages")
            else:
                logger.info(f"[REDIS VERIFICATION] No conversation history (first message)")
            logger.debug(f"{'='*80}")
        
        # ====================================================================
        # STEP 2: ANALYZE MESSAGE INTENT (LLM-Based)
        # ====================================================================
        logger.info(f"[STEP 1: INTENT ANALYSIS]")
        logger.debug(f"Analyzing: '{question}'")
        
        intent_analysis = context_manager.analyze_message_intent(
            current_query=question,
            conversation_history=full_history[-10:],  # Last 10 messages for context
            conversation_summary=conversation_summary
        )

        # ── Reset conversation phase on NEW_TOPIC ────────────────────────
        if intent_analysis.get('intent_type') == 'NEW_TOPIC':
            conv_phase_check = session_manager.get_conversation_phase(user_id)
            if conv_phase_check.get('phase') != 'INITIAL':
                logger.info(f"[PHASE] NEW_TOPIC detected → resetting phase from {conv_phase_check.get('phase')} to INITIAL")
                session_manager.set_conversation_phase(user_id, phase="INITIAL")

        # ====================================================================
        # STEP 3: RESOLVE CONTEXTUAL QUERY (Confidence-Based)
        # ====================================================================
        logger.info(f"[STEP 2: SEMANTIC INTERPRETATION]")

        # Only resolve contextual references when there is at least one real prior
        # user message in history.  If the history contains only app-generated
        # assistant messages (e.g. mobile-app welcome/disclaimer messages seeded
        # at /initialize with empty question fields), treating the query as a
        # CONTINUATION would incorrectly expand it against those bot messages.
        real_user_messages_in_history = [m for m in full_history if m.get('role') == 'user']

        resolution_result = {
            "action": "NONE",
            "processed_query": question,
            "ambiguity_score": 0.0,
            "clarification_needed": False,
            "explanation": "New topic - no resolution needed"
        }

        # ── Progressive Disclosure: skip expansion for affirmative/negative responses ──
        # When the bot asked "want more details?" or a follow-up question, the user's
        # "yes"/"no"/"haan" must reach the orchestrator intact.  The semantic expander
        # would otherwise rewrite it into the bot's own question, causing CHITCHAT misrouting.
        from src.ai.context_manager import detect_user_response_type
        _phase_now = session_manager.get_conversation_phase(user_id).get('phase', 'INITIAL')
        _response_type_now = detect_user_response_type(question)
        # Skip expansion when in an active progressive disclosure phase AND the
        # user's message is short (≤5 words). Short messages in these phases are
        # continuations/affirmations, NOT new questions that need context injection.
        # This prevents "Hmm samjhao" → "Hmm samjhao iske peeche ki vyakhya...?" rewrites
        # that confuse the safety classifier and misroute to BLOCKED.
        _is_short_phrase = len(question.strip().split()) <= 5
        _skip_expansion = (
            _phase_now in ('AWAITING_DETAIL', 'FOLLOWUP_LOOP')
            and (_response_type_now in ('AFFIRMATIVE', 'NEGATIVE') or _is_short_phrase)
        )

        if not _skip_expansion and intent_analysis['intent_type'] in ['CONTINUATION', 'CLARIFICATION'] and real_user_messages_in_history:
            resolution_result = context_manager.resolve_contextual_query(
                current_query=question,
                conversation_history=full_history,
                intent_analysis=intent_analysis
            )
        elif _skip_expansion:
            logger.info(f"[PHASE] Skipping semantic expansion — phase={_phase_now}, response={_response_type_now}")
            resolution_result = {
                "action": "NONE",
                "processed_query": question,
                "ambiguity_score": 0.0,
                "clarification_needed": False,
                "explanation": "Progressive disclosure phase — expansion skipped"
            }
            
            # If clarification needed, return early
            if resolution_result.get('clarification_needed'):
                clarification_answer = resolution_result.get('clarification_question', 
                    "Could you please clarify what you're referring to?")
                
                logger.info(f"[CLARIFICATION REQUESTED]")
                logger.debug(f"Ambiguity Score: {resolution_result['ambiguity_score']:.2f}")
                logger.debug(f"Returning clarification question instead of processing query")
                
                # Store the clarification exchange
                session_manager.add_message(user_id, "user", question)
                session_manager.add_message(
                    user_id,
                    "assistant",
                    clarification_answer,
                    metadata={
                        "intent": "CLARIFICATION_REQUEST",
                        "source": "chatbot",
                        "ambiguity_score": resolution_result['ambiguity_score']
                    }
                )
                
                processing_time = time.time() - start_time
                
                return SendMessageResponse(
                    user_id=user_id,
                    question=question,
                    answer=clarification_answer,
                    source="Nakshatra-ai"
                )
        
        # Get the processed query (original, expanded, or hinted)
        processed_query = resolution_result['processed_query']
        
        logger.info(f"[RESOLUTION RESULT]")
        logger.debug(f"Action: {resolution_result['action']}")
        logger.debug(f"Ambiguity Score: {resolution_result['ambiguity_score']:.2f}")
        logger.debug(f"Original Query: {question}")
        logger.debug(f"Processed Query: {processed_query}")
        if processed_query != question:
            logger.debug(f"[OK] Query enhanced for clarity")
        else:
            logger.debug(f"[INFO]  No modification needed")
        
        # ====================================================================
        # STEP 4: PREPARE CONTEXT FOR ORCHESTRATOR
        # ====================================================================
        logger.info(f"[STEP 3: PREPARING ORCHESTRATOR CONTEXT]")
        
        # Get recent history (context window)
        if len(full_history) > settings.CONVERSATION_CONTEXT_WINDOW:
            recent_history = full_history[-settings.CONVERSATION_CONTEXT_WINDOW:]
            logger.debug(f"Sending last {settings.CONVERSATION_CONTEXT_WINDOW} of {len(full_history)} messages")
        else:
            recent_history = full_history
            logger.debug(f"Sending all {len(full_history)} messages")
        
        # Log what's being sent to orchestrator
        logger.debug(f"{'-'*80}")
        logger.info(f"[MESSAGES SENT TO ORCHESTRATOR]")
        logger.debug(f"{'-'*80}")
        for i, msg in enumerate(recent_history, 1):
            role_label = "[USER]" if msg['role'] == 'user' else "[BOT]"
            content_preview = msg['content'][:70] + "..." if len(msg['content']) > 70 else msg['content']
            logger.debug(f"{i}. {role_label}: {content_preview}")

        logger.info(f"[CURRENT QUERY TO ORCHESTRATOR]")
        logger.debug(f"Original User Query: {question}")
        logger.debug(f"Processed Query: {processed_query}")
        logger.debug(f"Intent Type: {intent_analysis['intent_type']}")
        logger.debug(f"Resolution Action: {resolution_result['action']}")
        if resolution_result['action'] == 'EXPAND':
            logger.debug(f"[OK] Query expanded for clarity (confidence: {resolution_result['ambiguity_score']:.2f})")
        elif resolution_result['action'] == 'HINT':
            logger.debug(f"[INFO]  Hint added for context (confidence: {resolution_result['ambiguity_score']:.2f})")
        logger.debug(f"{'-'*80}")
        
        # ====================================================================
        # STEP 5: GET CACHED CALCULATIONS
        # ====================================================================
        cached_chart = session_manager.get_chart_data(user_id)
        cached_dasha = session_manager.get_dasha_data(user_id)
        cached_transit = session_manager.get_transit_data(user_id)
        
        logger.info(f"[REDIS CACHED DATA FETCH]")
        logger.debug(f"Chart: {'[OK] Fetched from Redis' if cached_chart else '[MISSING] Not in Redis'}")
        logger.debug(f"Dasha: {'[OK] Fetched from Redis' if cached_dasha else '[MISSING] Not in Redis'}")
        logger.debug(f"Transit: {'[OK] Fetched from Redis' if cached_transit else '[MISSING] Not in Redis'}")

        
        # ── Load conversation phase for progressive disclosure ────────────
        conv_phase_data = session_manager.get_conversation_phase(user_id)
        logger.info(f"[PHASE] Current phase: {conv_phase_data.get('phase')} | topic: {conv_phase_data.get('topic')}")

        # ── Voice preferences: merge any inferred from this message into stored ────────────
        prefs = session_manager.get_voice_preferences(user_id) or {}
        inferred = _infer_voice_preferences_from_message(question)
        if inferred:
            session_manager.store_voice_preferences(user_id, {**prefs, **inferred})
            prefs = session_manager.get_voice_preferences(user_id) or {}

        # Pre-fetch cached validation result so the orchestrator can skip re-running
        # the expensive LLM-based validation (saves ~34s per request for same query_type).
        # The query_type is derived from intent_analysis domain when available.
        _ia_domain = (intent_analysis.get('domain') or '').strip().lower() or None
        if _ia_domain == 'foreign_travel':
            _ia_domain = 'foreign'
        _cached_validation = session_manager.get_validation_result(user_id, _ia_domain) if _ia_domain else None

        orchestrator_session_data = {
            "chart_data": cached_chart,
            "dasha_data": cached_dasha,
            "transit_data": cached_transit,
            "summary": conversation_summary,
            "intent_analysis": intent_analysis,
            "conversation_phase": conv_phase_data,
            "original_user_question": question,  # True original before semantic expansion
            # Pass the previously detected language so _detect_language_node can
            # use it as a fallback for short ambiguous queries (e.g. "Haan batao")
            "detected_language": session_manager.get_detected_language(user_id),
            "voice_preferences": prefs,
            "cached_validation_result": _cached_validation,  # None if not cached yet
        }
        
        # Log what cached data is being passed to orchestrator
        if cached_chart:
            logger.info(f"[CACHE] [OK] Passing cached chart to orchestrator")
        if cached_dasha:
            logger.info(f"[CACHE] [OK] Passing cached dasha to orchestrator")
        if cached_transit:
            logger.info(f"[CACHE] [OK] Passing cached transit to orchestrator")
        
        # ====================================================================
        # STEP 6: PROCESS QUERY WITH ORCHESTRATOR
        # ====================================================================
        logger.info(f"[STEP 4: CALLING ORCHESTRATOR]")
        
        orchestrator = get_orchestrator()
        
        result = orchestrator.process_query(
            query=processed_query,  # Use processed query from semantic interpreter!
            user_id=user_id,
            conversation_history=recent_history,
            user_profile_override=user_profile,
            session_data=orchestrator_session_data
        )

        # Extract response details
        answer = result.get('answer', '')
        intent = result.get('intent', 'UNKNOWN')
        confidence = result.get('confidence', 0.0)
        
        # ════════════════════════════════════════════════════════════════════════
        # POST-PROCESSING: Remove "Thank You" Patterns & Enforce Length
        # ════════════════════════════════════════════════════════════════════════
        import re
        
        # Remove "thank you for providing details" patterns
        thank_you_patterns = [
            r"thank you for (providing|sharing) your (birth )?details[,.]?\s*",
            r"thanks for (providing|sharing) your (birth )?details[,.]?\s*",
            r"dhanyavaad aapke (janam )?details dene ke liye[,.]?\s*",
            r"shukriya aapke details[,.]?\s*",
            r"based on (the )?information (you )?provided[,.]?\s*",
            r"aapke diye gaye details[,.]?\s*",
        ]
        
        original_answer = answer
        for pattern in thank_you_patterns:
            answer = re.sub(pattern, "", answer, flags=re.IGNORECASE)
        
        # Remove orphaned sentence starters after removal
        answer = re.sub(r"^\s*(Now|Ab|So|Toh)[,.]?\s*", "", answer, flags=re.IGNORECASE)
        
        if answer != original_answer:
            logger.info(f"[POST_PROCESS] Removed 'thank you' pattern")

        # Use the RESULT phase (what the orchestrator decided) not the INPUT phase
        result_phase = (result.get('conversation_phase') or {}).get('phase', conv_phase_data.get('phase', 'INITIAL'))

        # ── DETAILED RESPONSE: strip any "offer more details on same topic" sentences ──
        # The LLM sometimes adds these even when instructed not to. Remove them by pattern.
        if result_phase == 'FOLLOWUP_LOOP':
            # Remove explicit "Next Favorable Window" sections in detailed responses.
            # Secondary windows should be woven naturally into the factor explanation,
            # not emitted as a separate heading block.
            _next_window_original = answer
            _next_window_patterns = [
                r"(?is)\n*\s*next\s+favo(?:u)?rable\s+window\s*:[^\n]*(?:\n[^\n]*)?",
                r"(?is)\n*\s*agla\s+favo(?:u)?rable\s+window\s*:[^\n]*(?:\n[^\n]*)?",
            ]
            for _pat in _next_window_patterns:
                answer = re.sub(_pat, "\n", answer, flags=re.IGNORECASE)
            if answer != _next_window_original:
                logger.info("[POST_PROCESS] Removed standalone 'Next Favorable Window' section from detailed response")

            _offer_more_patterns = [
                r"[^.!?\n]*(agar aap chah|agar chahein).{0,80}(detail|vistar|samjha|elaborate|vyakhya|bata)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*(aur (bhi )?detail mein samjha|aur jaanna hai|aur detail chahiye|aur bhi (batana|samjhana))[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(main aapko|main aap).{0,50}(aur (bata|samjha|detail|vyakhya)|more detail|elaborate|explain further)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(iske peeche|iske piche).{0,60}(vyakhya|samjha|bata|detail|karanon)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(if you.{0,20}(would like|want|wish)|would you like me to).{0,60}(more detail|elaborate|explain (further|more)|go deeper)[^.!?\n]*[.!?]?\s*",
            ]
            _detail_original = answer
            for _pat in _offer_more_patterns:
                answer = re.sub(_pat, " ", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\n{3,}", "\n\n", answer)
            answer = re.sub(r"  +", " ", answer).strip()
            if answer != _detail_original:
                logger.info(f"[POST_PROCESS] Removed 'offer more details on same topic' sentence from detailed response")

        # Enforce word maximum for mobile (phase-aware)
        if result_phase == 'FOLLOWUP_LOOP' and conv_phase_data.get('phase') == 'AWAITING_DETAIL':
            # User agreed to detailed reasoning → keep depth but avoid overly long blocks
            MAX_MOBILE_WORDS = 560
        elif result_phase == 'FOLLOWUP_LOOP':
            # Follow-up loop responses (further questions) capped slightly lower
            MAX_MOBILE_WORDS = 500
        elif result_phase == 'AWAITING_DETAIL':
            # Initial short response → hard cap at 250 words
            MAX_MOBILE_WORDS = 250
        else:
            MAX_MOBILE_WORDS = 250  # Default fallback (also initial)
        word_count = len(answer.split())

        if word_count > MAX_MOBILE_WORDS:
            logger.info(f"[MOBILE] Response too long ({word_count} words), truncating to {MAX_MOBILE_WORDS}...")
            
            # Split into sentences
            sentences = re.split(r'(?<=[.!?])\s+', answer)
            
            # Keep sentences until we hit word limit
            truncated_sentences = []
            current_words = 0
            
            for sentence in sentences:
                sentence_words = len(sentence.split())
                if current_words + sentence_words <= MAX_MOBILE_WORDS:
                    truncated_sentences.append(sentence)
                    current_words += sentence_words
                else:
                    break
            
            answer = ' '.join(truncated_sentences)
            
            # Add continuation hint only if truncated AND not in progressive disclosure flow
            if len(truncated_sentences) < len(sentences) and result_phase not in ('AWAITING_DETAIL', 'FOLLOWUP_LOOP'):
                # Use detected language (with Redis fallback) to keep the continuation
                # hint in the same language/script as the user.
                _detected_lang = result.get('detected_language') or session_manager.get_detected_language(user_id) or 'en'
                _trunc_hint_map = {
                    'en': " Feel free to ask if you'd like to explore this further.",
                    'hi': " Agar aap chahen to is baat ko aur gehraai se samjha sakta hoon.",
                    'hi-lat': " Agar aap chahein to main is baat ko aur gehraai se samjha sakta hoon.",
                    'ta': " Neengal virumbinaal idhai naan innum vivaramaaga vilakkalaam.",
                    'ta-lat': " Neengal virumbinaal idhai naan innum vivaramaa vilakkalaam.",
                    'pa': " Je tusi chaunde ho tan main eh gall hor vadh toon vadh spasht kar sakda haan.",
                    'pa-lat': " Je tusi chaunde ho tan main eh gall hor vadh toon vadh spasht kar sakda haan.",
                }
                answer += _trunc_hint_map.get(_detected_lang, _trunc_hint_map['en'])
            
            logger.info(f"[MOBILE] Truncated: {word_count} → {len(answer.split())} words")

        # ── FINAL ENFORCEMENT: ensure INITIAL/new-topic short responses end with offer-for-detail question ──
        # Covers two cases:
        #   1. INITIAL → AWAITING_DETAIL  (fresh user question)
        #   2. FOLLOWUP_LOOP → AWAITING_DETAIL  (user said yes to cross-domain follow-up → new topic cycle)
        # Runs *after* any truncation so the closing question cannot be accidentally cut off.
        if result_phase == 'AWAITING_DETAIL':
            _input_phase = conv_phase_data.get('phase', 'INITIAL')
            _is_new_topic_cycle = _input_phase in ('INITIAL', 'FOLLOWUP_LOOP')
            if _is_new_topic_cycle:
                last_200 = answer[-200:] if len(answer) > 200 else answer
                already_has_closing = '?' in last_200
                if not already_has_closing:
                    _detected_lang = result.get('detected_language') or session_manager.get_detected_language(user_id) or 'en'
                    _closing_q_map = {
                        'en': 'Would you like me to explain the detailed astrological reasoning behind this?',
                        'hi': 'Kya aap iske peeche ki vistarit jyotishiya wajah jaanna chahenge?',
                        'hi-lat': 'Kya aap iske peeche ki vistarit jyotishiya wajah jaanna chahenge?',
                        'ta': 'Itharku pinnaal ullaa jothida karanam theriya virumbukireerga?',
                        'ta-lat': 'Itharku pin ullana jothida karanam theriya virumbukireerga?',
                        'pa': 'Ki tusi is de pichhe di jyotish wajah jaanna chahunde ho?',
                        'pa-lat': 'Ki tusi is de pichhe di jyotish wajah jaanna chahunde ho?',
                    }
                    _closing_q = _closing_q_map.get(_detected_lang, _closing_q_map['en'])
                    answer = (answer.rstrip() + "\n\n" + _closing_q).strip()
                    logger.info(f"[POST_PROCESS] Appended offer-for-detail question (closing was truncated)")
        
        # Run final semantic validator using a small conversation context window.
        # For detailed responses (second-step CONTINUATION/CLARIFICATION after an
        # initial timing answer), require AT LEAST 7 numbered astrological reasoning
        # points. We key this off the high-level intent returned by the orchestrator
        # plus the intent_type from the LLM intent analysis.
        min_points = 0
        _ia = intent_analysis or {}
        _ia_type = _ia.get("intent_type")
        # Only enforce numbered astro reasoning for the specific detailed-answer step:
        # input phase AWAITING_DETAIL -> result phase FOLLOWUP_LOOP.
        # Do NOT enforce it for FOLLOWUP_LOOP -> AWAITING_DETAIL (new pivot topic short
        # answer), otherwise validator rewrites can drag the answer back to old topic.
        _input_phase = conv_phase_data.get('phase', 'INITIAL')
        _is_detailed_step = (_input_phase == 'AWAITING_DETAIL' and result_phase == 'FOLLOWUP_LOOP')
        if (
            intent == "RAG_WITH_CALCULATION"
            and _ia_type in ("CONTINUATION", "CLARIFICATION")
            and _is_detailed_step
        ):
            min_points = 7

        answer = validate_and_sanitize_response(
            question=question,
            answer=answer,
            intent_analysis=intent_analysis,
            recent_history=recent_history,
            min_numbered_points=min_points,
            detected_language=result.get('detected_language') or session_manager.get_detected_language(user_id),
        )

        # ── POST-VALIDATOR: enforce cross-domain follow-up question on AWAITING_DETAIL→FOLLOWUP_LOOP ──
        # The numbered-points rewrite can lose the follow-up question injected by the orchestrator.
        # Re-strip any "offer more details" sentences the rewriter may have added, then
        # append the pre-generated cross-domain follow-up question if it is missing.
        if conv_phase_data.get('phase') == 'AWAITING_DETAIL' and result_phase == 'FOLLOWUP_LOOP':
            _offer_more_patterns_post = [
                # Generic Hindi "if you want more details" patterns
                r"[^.!?\n]*(agar aap chah|agar chahein).{0,80}(detail|vistar|samjha|elaborate|vyakhya|bata)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*(aur (bhi )?detail mein samjha|aur jaanna hai|aur detail chahiye|aur bhi (batana|samjhana))[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(main aapko|main aap).{0,50}(aur (bata|samjha|detail|vyakhya)|more detail|elaborate|explain further)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(iske peeche|iske piche).{0,60}(vyakhya|samjha|bata|detail|karanon)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(if you.{0,20}(would like|want|wish)|would you like me to).{0,60}(more detail|elaborate|explain (further|more)|go deeper)[^.!?\n]*[.!?]?\s*",
                # Remove awkward same-topic "opportunity" questions (e.g., marriage)
                r"[^.!?\n]*(aapko|tumhe).{0,40}(shadi|shaadi|marriage).{0,40}(kaise).{0,40}(avsar|mauke?|opportunit(?:y|ies))[^.!?\n]*\?\s*",
            ]
            for _pat in _offer_more_patterns_post:
                answer = re.sub(_pat, " ", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\n{3,}", "\n\n", answer)
            answer = re.sub(r"  +", " ", answer).strip()
            # If the detailed answer still ends with a question about the same topic we just
            # covered, remove that trailing same-domain question and keep only the pivot.
            _topic_now = (conv_phase_data.get('topic') or '').lower()
            _same_topic_keywords = {
                'marriage': ['shadi', 'shaadi', 'marriage', 'vivah', 'rishta', 'partner', 'spouse'],
                'career': ['career', 'job', 'naukri', 'kaam', 'profession', 'business', 'rojgar'],
                'finance': ['finance', 'money', 'paisa', 'dhan', 'wealth', 'arthik'],
                'health': ['health', 'sehat', 'swasthya', 'bimari', 'illness'],
                'children': ['child', 'children', 'bacche', 'santaan', 'aulad'],
                'foreign': ['foreign', 'videsh', 'abroad', 'overseas', 'travel', 'settlement'],
            }.get(_topic_now, [])
            if _same_topic_keywords:
                _question_sentences = re.findall(r'[^.!?\n]*\?+', answer)
                _same_topic_q = [
                    _q for _q in _question_sentences
                    if any(_kw in _q.lower() for _kw in _same_topic_keywords)
                ]
                for _q in _same_topic_q:
                    answer = answer.replace(_q, " ")
                answer = re.sub(r"\n{3,}", "\n\n", answer)
                answer = re.sub(r"  +", " ", answer).strip()
            # Always append the cross-domain follow-up question if the validated response
            # lost it. Check the last 150 chars for the start of the follow-up text so we
            # don't double-append if the LLM already included it correctly.
            _fup = result.get('_detailed_followup', '') or ''
            if _fup:
                _last_150 = answer[-150:] if len(answer) > 150 else answer
                _fup_start = _fup[:30].lower()  # First 30 chars as fingerprint
                if _fup_start not in _last_150.lower():
                    answer = answer.rstrip() + "\n\n" + _fup
                    logger.info(f"[POST_PROCESS] Appended cross-domain follow-up question after validator rewrite")

        logger.info(f"[ORCHESTRATOR RESULT]")
        logger.debug(f"Intent: {intent}")
        logger.debug(f"Confidence: {confidence:.2f}")
        logger.debug(f"Answer length: {len(answer)} characters ({len(answer.split())} words)")
        
        # ====================================================================
        # STEP 7: STORE NEW CALCULATIONS IN CACHE
        # ====================================================================
        # Only store if not already cached
        if result.get('chart_data') and not cached_chart:
            logger.info(f"[REDIS CACHE] Storing NEW chart data to Redis...")
            session_manager.store_chart_data(user_id, result['chart_data'])
            logger.info(f"[REDIS CACHE] [OK] Chart stored in Redis")
        
        if result.get('dasha_data') and not cached_dasha:
            logger.info(f"[REDIS CACHE] Storing NEW dasha data to Redis...")
            session_manager.store_dasha_data(user_id, result['dasha_data'])
            logger.info(f"[REDIS CACHE] [OK] Dasha stored in Redis")
        
        if result.get('transit_data') and not cached_transit:
            logger.info(f"[REDIS CACHE] Storing NEW transit data to Redis...")
            session_manager.store_transit_data(user_id, result['transit_data'])
            logger.info(f"[REDIS CACHE] [OK] Transit stored in Redis")

        # Cache validation result so the next request in this session skips re-validation
        _result_val = result.get('validation_result')
        _result_qt = result.get('validation_query_type') or ((_result_val or {}).get('query_type'))
        if _result_val and _result_qt and _result_qt != 'general':
            session_manager.store_validation_result(user_id, _result_qt, _result_val)
            logger.info(f"[REDIS CACHE] [OK] Validation result cached for query_type={_result_qt}")
        
        # ====================================================================
        # STEP 8: UPDATE CONVERSATION HISTORY
        # ====================================================================
        logger.info(f"[REDIS] Saving latest user & assistant messages to Redis history...")

        session_manager.add_message(user_id, "user", question)  # Store original question
        session_manager.add_message(
            user_id,
            "assistant",
            answer,
            metadata={
                "intent": intent,
                "confidence": confidence,
                "source": "chatbot",   # "chatbot" = generated this session; "external"/"openai" = old imported history
                "context_intent": intent_analysis['intent_type'],
                "resolution_action": resolution_result['action'],
                "ambiguity_score": resolution_result['ambiguity_score'],
                "processed_query": processed_query if processed_query != question else None
            }
        )
        
        # ====================================================================
        # STEP 8.5: UPDATE CONVERSATION PHASE (Progressive Disclosure)
        # ====================================================================
        new_phase = result.get('conversation_phase')
        if new_phase:
            session_manager.set_conversation_phase(
                user_id,
                phase=new_phase.get('phase', 'INITIAL'),
                topic=new_phase.get('topic'),
                last_query=new_phase.get('last_query'),
                followup_count=new_phase.get('followup_count', 0),
                visited_domains=new_phase.get('visited_domains'),
            )
            logger.info(
                f"[PHASE] Updated to: {new_phase.get('phase')} | "
                f"topic: {new_phase.get('topic')} | "
                f"visited: {new_phase.get('visited_domains')}"
            )

        # Persist the detected language for the next turn's session-prior fallback
        _new_detected_lang = result.get('detected_language', 'en')
        if _new_detected_lang and _new_detected_lang != 'en':
            session_manager.store_detected_language(user_id, _new_detected_lang)
            logger.info(f"[LANG] Session language persisted: {_new_detected_lang}")

        # ====================================================================
        # STEP 9: UPDATE CONVERSATION SUMMARY (Every 10 messages)
        # ====================================================================
        if session_manager.should_update_summary(user_id):
            logger.info(f"[STEP 5: UPDATING CONVERSATION SUMMARY]")
            logger.debug(f"Threshold reached: Generating new summary...")
            
            updated_history = session_manager.get_conversation_history(user_id)
            new_summary = context_manager.generate_conversation_summary(
                conversation_history=updated_history,
                current_summary=conversation_summary
            )
            
            session_manager.store_conversation_summary(user_id, new_summary)
        
        # Extend session
        session_manager.extend_session(user_id)
        
        processing_time = time.time() - start_time
        
        logger.info(f"[RESPONSE SUMMARY]")
        logger.debug(f"Processing time: {processing_time:.2f}s")
        logger.debug(f"Context intent: {intent_analysis['intent_type']}")
        logger.debug(f"Resolution action: {resolution_result['action']}")
        logger.debug(f"Ambiguity score: {resolution_result['ambiguity_score']:.2f}")
        logger.debug(f"Orchestrator intent: {intent}")
        logger.debug(f"Response length: {len(answer)} characters")
        logger.debug(f"{'='*80}")

        # API metadata payload for frontend diagnostics panels
        response_metadata: Dict[str, Any] = {}
        if isinstance(result, dict):
            vr = result.get("validation_result") or {}
            vdbg = result.get("validation_debug") or vr.get("debug_stats") or {}
            if vr or vdbg:
                response_metadata["validation_diagnostics"] = {
                    "query_type": vr.get("query_type"),
                    "overall_strength": vr.get("overall_strength"),
                    "can_proceed": vr.get("can_proceed"),
                    "rules_checked": vr.get("rules_checked"),
                    "rules_passed": vr.get("rules_passed"),
                    "rules_failed": vr.get("rules_failed"),
                    "critical_failures_count": len(vr.get("critical_failures") or []),
                    "debug_stats": vdbg,
                }
        
        # Return response
        return SendMessageResponse(
            user_id=user_id,
            question=question,
            answer=answer,
            source="openai",
            evidence=result.get("astro_evidence") if isinstance(result, dict) else None,
            metadata=response_metadata or None,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Message processing error: {str(e)}")


# ============================================================================
# OPTIONAL ENDPOINTS
# ============================================================================

@router.get("/session/{session_id}/status")
def get_session_status(session_id: str):
    """Get session status with summary information."""
    try:
        session_manager = get_session_manager()
        
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        user_profile = session_manager.get_user_profile(session_id)
        conversation = session_manager.get_conversation_history(session_id)
        summary = session_manager.get_conversation_summary(session_id)
        
        return {
            "session_id": session_id,
            "exists": True,
            "user_id": user_profile.get('user_id') if user_profile else None,
            "cached_data": {
                "user_profile": user_profile is not None,
                "chart_data": session_manager.get_chart_data(session_id) is not None,
                "dasha_data": session_manager.get_dasha_data(session_id) is not None,
                "transit_data": session_manager.get_transit_data(session_id) is not None,
                "conversation_messages": len(conversation),
                "conversation_summary": summary
            },
            "context_window_size": settings.CONVERSATION_CONTEXT_WINDOW,
            "messages_sent_to_llm": min(len(conversation), settings.CONVERSATION_CONTEXT_WINDOW)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
def clear_session(session_id: str):
    """Clear a session."""
    try:
        session_manager = get_session_manager()
        success = session_manager.clear_session(session_id)
        
        if success:
            return {"status": "success", "message": f"Session {session_id} cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/stats")
def get_stats():
    """Get chatbot statistics."""
    try:
        session_manager = get_session_manager()
        
        return {
            "active_sessions": session_manager.get_active_sessions_count(),
            "redis_connected": session_manager.redis is not None,
            "context_window_size": settings.CONVERSATION_CONTEXT_WINDOW,
            "context_window_env_var": "CONVERSATION_CONTEXT_WINDOW",
            "context_window_source": "centralized_config",
            "features": {
                "llm_context_analysis": True,
                "conversation_summarization": True,
                "intent_detection": ["CONTINUATION", "NEW_TOPIC", "CLARIFICATION"],
                "query_resolution": True
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))