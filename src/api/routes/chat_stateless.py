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
from src.ai.voice_charter import pick_initial_closing
from src.api.response_postprocessor import validate_and_sanitize_response
from config.logger import get_logger

logger = get_logger("chat_stateless")

from src.api.orchestrator_helper import get_orchestrator
from src.api.config import settings
from src.safety.vulgarity import (
    contains_vulgar_keyword,
    is_clearly_astrological_query,
    llm_vulgarity_check,
)
from src.api.dependencies import (
    get_context_manager as get_shared_context_manager,
    get_session_manager as get_shared_session_manager,
)
from src.ai.context_manager import ContextManager as SharedContextManager


router = APIRouter()


# ============================================================================
# CONTEXT MANAGER (deprecated in this route)
# Single source of truth lives in `src/ai/context_manager.py`.
# ============================================================================

class ContextManager:
    """
    Professional-grade context manager using LLM for intelligent analysis.
    No pattern matching - purely LLM-driven decisions.
    """

    def __new__(cls, *args, **kwargs):
        # Route-local ContextManager is deprecated. Always return shared implementation.
        return SharedContextManager()
    
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

def get_context_manager() -> SharedContextManager:
    """Get canonical context manager instance from dependency container."""
    global _context_manager
    if _context_manager is None:
        try:
            _context_manager = get_shared_context_manager()
        except Exception:
            # Fallback should still use the shared/canonical implementation.
            _context_manager = SharedContextManager()
    return _context_manager


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
            from src.api.config import settings
            _session_manager = SessionManager(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
            )
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

        if result['status'] == 'error':
            raise HTTPException(
                status_code=503,
                detail=result.get('message', 'Session initialization failed')
            )

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

        # return InitializeSessionResponse(
        #     user_id=result['user_id'],
        #     status=result['status']
        # )
        return InitializeSessionResponse(
            user_id=user_id,
            status=result.get('status', 'initialized')
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
        def _is_vulgar(text: str) -> bool:
            """Keyword check + LLM fallback for vulgarity not in the keyword list."""
            # 1. Fast keyword check
            if contains_vulgar_keyword(text):
                return True
            # 2. Skip LLM check if the query is clearly astrological (saves latency)
            if is_clearly_astrological_query(text):
                return False
            # 3. LLM fallback — catches abbreviations, creative spellings, euphemisms,
            #    code-switching, and languages not covered by the keyword list.
            try:
                if llm_vulgarity_check(query=text, llm=context_manager.fast_llm, strict_prompt=True):
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

        # ── STRIP HOUSE PARENTHETICAL LABELS ──────────────────────────────────
        # LLM adds educational glosses like "7th house (Marriage & Partnership)"
        # or "2nd house (Wealth & Family)". These sound robotic. Strip them.
        _before_labels = answer
        answer = re.sub(
            r'\b(house|lord|bhava)\s*\((?!D\d)[^)]{3,50}\)',
            lambda m: m.group(0).split('(')[0].rstrip(),
            answer,
            flags=re.IGNORECASE,
        )
        if answer != _before_labels:
            logger.info("[POST_PROCESS] Stripped house parenthetical label(s)")

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

        # ── CLOSING CHECK: trust the LLM's own follow-up offer ──
        # The new prose instruction tells the LLM to write a natural follow-up offer itself.
        # Only append a fallback closing if the answer has NO sentence-ending punctuation at all
        # (edge case: very truncated answer with no period, question mark, or exclamation).
        if result_phase == 'AWAITING_DETAIL':
            _input_phase = conv_phase_data.get('phase', 'INITIAL')
            _is_new_topic_cycle = _input_phase in ('INITIAL', 'FOLLOWUP_LOOP')
            if _is_new_topic_cycle:
                # Check last 300 chars for any sentence-ending punctuation — LLM always writes one
                last_300 = answer[-300:] if len(answer) > 300 else answer
                already_has_closing = any(c in last_300 for c in ('?', '!', '।'))
                if not already_has_closing:
                    _detected_lang = result.get('detected_language') or session_manager.get_detected_language(user_id) or 'en'
                    _closing_q_map = {
                        'en': 'Would you like me to go deeper into the astrological reasoning?',
                        'hi': 'Kya aap aur detail mein jaanna chahenge?',
                        'hi-lat': 'Kya aap aur detail mein jaanna chahenge?',
                        'ta': 'Itharku pin ullana jothida karanam theriya virumbukireerga?',
                        'ta-lat': 'Itharku pin ullana jothida karanam theriya virumbukireerga?',
                        'pa': 'Ki tusi is de pichhe di jyotish wajah jaanna chahunde ho?',
                        'pa-lat': 'Ki tusi is de pichhe di jyotish wajah jaanna chahunde ho?',
                    }
                    _closing_q = _closing_q_map.get(_detected_lang, _closing_q_map['en'])
                    answer = (answer.rstrip() + "\n\n" + _closing_q).strip()
                    logger.info(f"[POST_PROCESS] Appended fallback closing (answer had no sentence-ending punctuation)")

        # ── DUPLICATE CLOSING CLEANUP ──
        # The LLM sometimes writes a non-question "offer" sentence immediately before the
        # closing question, creating a redundant double ending:
        #   "Agar aap chahein, toh main aur bata sakta hoon.\n\nKya aap jaanna chahenge?"
        # If the answer ends with "?" we check if the sentence just before the final question
        # is itself a generic "offer more detail" statement, and if so remove it.
        if answer.rstrip().endswith('?'):
            _sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
            if len(_sentences) >= 2:
                _penultimate = _sentences[-2]
                _offer_markers = [
                    r'agar aap chah', r'agar chahein',
                    r'if you.{0,10}like', r'would you like me to',
                    r'main aapko.*bata sakta', r'aur detail (mein|chahiye)',
                    r'astrological reasoning.*detail', r'gehri jyotish',
                ]
                if any(re.search(p, _penultimate, re.IGNORECASE) for p in _offer_markers):
                    answer = (' '.join(_sentences[:-2]) + '\n\n' + _sentences[-1]).strip()
                    logger.info("[POST_PROCESS] Stripped redundant non-question offer sentence before closing question")

        # ── NON-ASTROLOGICAL CLOSING QUESTION GUARD ──
        # Replace closing questions that ask about user preferences/goals (not astrological)
        # with a proper canned astrological closing from pick_initial_closing().
        # Detects patterns like "kis tarah ki X chahiye?", "what kind of X are you looking for?"
        if result_phase == 'AWAITING_DETAIL' and answer.rstrip().endswith('?'):
            _last_q_match = re.search(r'[^.!?\n]*\?+\s*$', answer)
            if _last_q_match:
                _last_q = _last_q_match.group(0)
                _non_astro_patterns = [
                    r'kis tarah ki.{0,60}\?',
                    r'kya type.{0,60}\?',
                    r'what (kind|type) of.{0,60}(looking|want|seeking|interest)',
                    r'(talash|dhundh|chahte|chahiye).{0,40}\?$',
                    r'kahan.{0,40}(jaana|settle|rehna).{0,30}\?',
                    r'aapke (liye|goals|plans|expectations).{0,40}\?',
                ]
                if any(re.search(p, _last_q, re.IGNORECASE) for p in _non_astro_patterns):
                    _detected_lang = result.get('detected_language') or session_manager.get_detected_language(user_id) or 'en'
                    _ia_domain = (intent_analysis or {}).get('domain') or conv_phase_data.get('topic') or 'general'
                    _replacement_q = pick_initial_closing(
                        rng=__import__('random').Random(answer[:40]),
                        language=_detected_lang,
                        domain=_ia_domain,
                    )
                    answer = answer[:_last_q_match.start()].rstrip() + '\n\n' + _replacement_q
                    logger.info(f"[POST_PROCESS] Replaced non-astrological closing question with: {_replacement_q}")

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
        # Numbered points enforcement disabled — few-shot examples teach structure
        # through prose style, not numbered lists.
        # min_points = 7 was forcing the validator to rewrite prose into numbered structure.

        answer = validate_and_sanitize_response(
            question=question,
            answer=answer,
            intent_analysis=intent_analysis,
            recent_history=recent_history,
            min_numbered_points=min_points,
            detected_language=result.get('detected_language') or session_manager.get_detected_language(user_id),
        )

        # ── POST-VALIDATOR: enforce cross-domain follow-up question on AWAITING_DETAIL→FOLLOWUP_LOOP ──
        # The detailed instruction now tells the LLM to end with _suggested_followup directly.
        # We only strip truly generic "offer more details on same topic" endings that would
        # conflict with the cross-domain pivot question. Natural prose closings are preserved.
        if conv_phase_data.get('phase') == 'AWAITING_DETAIL' and result_phase == 'FOLLOWUP_LOOP':
            _offer_more_patterns_post = [
                # Only strip explicit same-topic "do you want more detail" (not natural closings)
                r"[^.!?\n]*(agar aap chah|agar chahein).{0,80}(detail|vistar|samjha|elaborate|vyakhya|bata)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*(aur (bhi )?detail mein samjha|aur detail chahiye)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(would you like me to).{0,60}(more detail|elaborate|explain (further|more)|go deeper)[^.!?\n]*[.!?]?\s*",
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
            # lost it. Search the FULL answer so we don't double-append if the LLM already
            # included the question anywhere (not just in the last 150 chars).
            _fup = result.get('_detailed_followup', '') or ''
            if _fup:
                _fup_start = _fup[:40].lower()  # First 40 chars as fingerprint
                if _fup_start not in answer.lower():
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
                "processed_query": processed_query if processed_query != question else None,
                # Structured timing metadata — avoids regex-parsing response text later
                "timing_windows": result.get('response_timing_windows') or [],
                "topic": result.get('response_topic') or "",
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