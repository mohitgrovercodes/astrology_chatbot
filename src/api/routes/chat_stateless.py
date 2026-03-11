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
import os
import redis
import json
from datetime import datetime
from src.llm.factory import LLMFactory

from src.api.orchestrator_helper import get_orchestrator
from src.api.config import settings


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
            
            print(f"\n[CONTEXT ANALYSIS]")
            print(f"  Query: {current_query[:60]}...")
            print(f"  Intent: {result['intent_type']}")
            print(f"  Confidence: {result.get('confidence', 0.5):.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
            if result.get('referenced_topic'):
                print(f"  Referenced Topic: {result['referenced_topic']}")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"[CONTEXT] JSON Parse Error: {e}")
            print(f"[CONTEXT] LLM Response (first 200 chars): {response.content[:200]}...")
            # Fallback to safe default
            return {
                "intent_type": "NEW_TOPIC",
                "confidence": 0.5,
                "reasoning": "JSON parse error - defaulting to NEW_TOPIC",
                "referenced_topic": None,
                "requires_context": False
            }
            
        except Exception as e:
            print(f"[CONTEXT] Error analyzing intent: {e}")
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
            print(f"\n[SEMANTIC INTERPRETER] [EXPAND] Deterministic EXPAND (skipping LLM)")
            print(f"  Pattern matched: clear_followup={is_clear_followup}, pronoun={has_pronoun}, short={is_short_followup}")
            print(f"  Expanded: '{expanded}'")
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
                print(f"\n[SEMANTIC INTERPRETER]")
                print(f"  Query: {current_query}")
                print(f"  Ambiguity Score: {ambiguity_score:.2f}")
                print(f"  Reasoning: {reasoning}")
            
        except Exception as e:
            # Fallback to heuristics
            print(f"[CONTEXT] JSON failed, using heuristics: {e}")
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
            print(f"  -> Strategy: AUTO-EXPAND")
            
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
            print(f"  -> Strategy: HINT")
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
            print(f"  -> Strategy: ASK_CLARIFICATION")
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
            print(f"[SUMMARY] Generated: {summary[:100]}...")
            return summary
        except Exception as e:
            print(f"[SUMMARY] Error: {e}")
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


# Global context manager instance
_context_manager = None

def get_context_manager() -> ContextManager:
    """Get global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


# ============================================================================
# ENHANCED SESSION MANAGER with Conversation Summary
# ============================================================================

class EnhancedSessionManager:
    def __init__(self):
        self.redis = None

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_password = os.getenv("REDIS_PASSWORD", None)

        try:
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password if redis_password else None,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self.redis.ping()
            print(f"[SESSION] ✅ Redis connected on {redis_host}:{redis_port}")
        except Exception as e:
            print(f"[SESSION] ❌ Redis connection failed: {e}")
            self.redis = None
    
    def require_redis(self):
        if not self.redis:
            raise Exception("Redis connection is unavailable. Cannot process session data.")

    def get_user_profile(self, user_id: str):
        self.require_redis()
        try:

            data = self.redis.get(f"session:{user_id}:user_profile")
            return json.loads(data) if data else None
        except:
            return None
    
    def get_conversation_history(self, user_id: str):
        if not self.redis:
            return []
        try:
            key = f"session:{user_id}:history"
            data = self.redis.get(key)
            return json.loads(data) if data else []
        except:
            return []
    
    def get_conversation_summary(self, user_id: str) -> Optional[str]:
        """Get conversation summary from Redis."""
        if not self.redis:
            return None
        try:
            key = f"session:{user_id}:summary"
            data = self.redis.get(key)
            if data:
                summary_data = json.loads(data)
                return summary_data.get('summary')
            return None
        except:
            return None
    
    def store_conversation_summary(self, user_id: str, summary: str):
        """Store conversation summary in Redis permanently (no TTL)."""
        if not self.redis:
            return
        try:
            summary_data = {
                "summary": summary,
                "updated_at": datetime.utcnow().isoformat(),
                "message_count": len(self.get_conversation_history(user_id))
            }
            key = f"session:{user_id}:summary"
            self.redis.set(key, json.dumps(summary_data))
            print(f"[SUMMARY] Stored conversation summary permanently at key: {key}")
        except Exception as e:
            print(f"[SUMMARY] Error storing summary: {e}")
    
    def get_chart_data(self, user_id: str):
        if not self.redis:
            return None
        try:
            key = f"session:{user_id}:chart"
            print(f"[REDIS] GET key={key}")
            data = self.redis.get(key)
            if data:
                chart = json.loads(data)
                # Schema version check: evict charts missing vargottama/divisional_charts_simple
                # (computed in serializer v2) so they get recalculated with enriched data.
                if 'divisional_charts_simple' not in chart or 'vargottama' not in chart:
                    print(f"[CHART] Schema v1 detected for {user_id} (missing divisional/vargottama) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                print(f"[REDIS] Found chart in Redis")
                return chart
            else:
                print(f"[REDIS] No chart found at key: {key}")
                return None
        except Exception as e:
            print(f"[SESSION] ERROR: Failed to get chart data for {user_id}: {e}")
            return None
    
    def get_dasha_data(self, user_id: str):
        """
        Fetch Dasha data from Redis.
        The active Mahadasha/Antardasha period shifts over months, so we perform
        an application-level staleness check: if cached data is older than
        DASHA_REFRESH_DAYS (default 30 days), we evict it and return None so
        the orchestrator recomputes the current Dasha state.
        """
        if not self.redis:
            return None
        try:
            key = f"session:{user_id}:dasha"
            print(f"[REDIS] GET key={key}")
            raw = self.redis.get(key)
            if not raw:
                print(f"[REDIS] No dasha found at key: {key}")
                return None

            envelope = json.loads(raw)

            # ── Staleness check ───────────────────────────────────────────────
            # Support both new envelope format and legacy flat format.
            stored_at_str = envelope.get("stored_at") if isinstance(envelope, dict) else None

            if stored_at_str:
                stored_at = datetime.fromisoformat(stored_at_str)
                age_days = (datetime.utcnow() - stored_at).total_seconds() / 86400
                refresh_threshold = settings.DASHA_REFRESH_DAYS

                if age_days >= refresh_threshold:
                    print(f"[DASHA] STALE — cached {age_days:.1f} days ago (threshold: {refresh_threshold} days). Evicting and forcing recompute.")
                    self.redis.delete(key)
                    return None

                data = envelope.get("data", {})
                # Schema version check: evict old formats missing enriched fields.
                # v1: missing upcoming_pratyantardashas entirely
                # v2: has upcoming_pratyantardashas but entries lack "status" field
                if data and "upcoming_pratyantardashas" not in data:
                    print(f"[DASHA] Schema v1 detected for {user_id} (missing pratyantar detail) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                pds = data.get("upcoming_pratyantardashas", [])
                if pds and "status" not in pds[0]:
                    print(f"[DASHA] Schema v2 detected for {user_id} (missing status field) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                print(f"[REDIS] Found dasha in Redis (age: {age_days:.1f} days, threshold: {refresh_threshold} days) — FRESH")
                return data
            else:
                # Legacy flat format — evict to migrate to new envelope
                print(f"[DASHA] Legacy format detected for {user_id} — evicting and forcing recompute.")
                self.redis.delete(key)
                return None

        except Exception as e:
            print(f"[SESSION] ERROR: Failed to get dasha data for {user_id}: {e}")
            return None
    
    def get_transit_data(self, user_id: str):
        """
        Fetch transit data from Redis.
        Transit positions change daily, so we perform an application-level
        staleness check: if the cached data is older than TRANSIT_REFRESH_HOURS
        (default 24h), we evict it and return None so the orchestrator recomputes
        fresh planetary positions for this request.
        """
        if not self.redis:
            return None
        try:
            key = f"session:{user_id}:transit"
            print(f"[REDIS] GET key={key}")
            raw = self.redis.get(key)
            if not raw:
                print(f"[REDIS] No transit found at key: {key}")
                return None

            envelope = json.loads(raw)

            # ── Staleness check ───────────────────────────────────────────────
            # We support both the new envelope format {"data": ..., "stored_at": ...}
            # and the legacy flat format (no stored_at key) for backward compat.
            stored_at_str = envelope.get("stored_at") if isinstance(envelope, dict) else None

            if stored_at_str:
                stored_at = datetime.fromisoformat(stored_at_str)
                age_hours = (datetime.utcnow() - stored_at).total_seconds() / 3600
                refresh_threshold = settings.TRANSIT_REFRESH_HOURS

                if age_hours >= refresh_threshold:
                    print(f"[TRANSIT] STALE — cached {age_hours:.1f}h ago (threshold: {refresh_threshold}h). Evicting key and forcing recompute.")
                    self.redis.delete(key)
                    return None

                print(f"[REDIS] Found transit in Redis (age: {age_hours:.1f}h, threshold: {refresh_threshold}h) — FRESH")
                return envelope.get("data")
            else:
                # Legacy flat format — treat as stale to migrate to new envelope
                print(f"[TRANSIT] Legacy format detected for {user_id} — evicting and forcing recompute.")
                self.redis.delete(key)
                return None

        except Exception as e:
            print(f"[SESSION] ERROR: Failed to get transit data for {user_id}: {e}")
            return None
    
    def session_exists(self, user_id: str):
        if not self.redis:
            return False
        return self.redis.exists(f"session:{user_id}:metadata") > 0
    
    def initialize_session(self, user_id: str, user_profile: dict, conversation_history: list = None):
        self.require_redis()
        
        try:
            # Helper for session persistence — always permanent (no TTL)
            def _set_data(key, val):
                self.redis.set(key, json.dumps(val))

            # ════════════════════════════════════════════════════════════════
            # VALIDATE DOB — must happen BEFORE the first Redis store so the
            # profile is always written with _dob_validation in a single atomic
            # operation.  Writing twice (once without, once with) left a window
            # where a concurrent read returned a profile missing _dob_validation,
            # causing age_years to default to 0 in the orchestrator.
            # ════════════════════════════════════════════════════════════════
            from src.validation.age_validator import AgeValidator

            dob = user_profile.get('date_of_birth')
            if dob:
                validation = AgeValidator.validate_dob(dob)

                print(f"[DOB_VALIDATION] Checking DOB: {dob}")
                if not validation['valid']:
                    print(f"[DOB_VALIDATION] ⚠️  Invalid: {validation['issue']}")
                    print(f"  - Message: {validation['message']}")
                else:
                    print(f"[DOB_VALIDATION] ✅ Valid - Age: {validation['age_years']} years, {validation['age_months']} months")

                user_profile['_dob_validation'] = validation

            # Store user profile (single write, always includes _dob_validation)
            _set_data(f"session:{user_id}:user_profile", user_profile)

            # Convert conversation history from external format to internal format
            internal_conversation = []
            if conversation_history:
                for idx, msg in enumerate(conversation_history):
                    # Extract timestamp (handle both MongoDB and ISO formats)
                    timestamp = msg.get('timestamp')
                    if isinstance(timestamp, dict) and '$date' in timestamp:
                        timestamp = timestamp['$date']
                    elif timestamp is None:
                        timestamp = datetime.utcnow().isoformat()
                    
                    # Get question and answer
                    question = msg.get('question', '').strip()
                    answer = msg.get('answer', '').strip()
                    
                    # Add user message ONLY if question is non-empty
                    if question:
                        internal_conversation.append({
                            "role": "user",
                            "content": question,
                            "timestamp": timestamp
                        })
                        print(f"[CONVERSION] Message {idx+1}: Added USER message - '{question[:50]}...'")
                    
                    # Always add assistant message if answer exists
                    if answer:
                        internal_conversation.append({
                            "role": "assistant",
                            "content": answer,
                            "timestamp": timestamp,
                            "metadata": {
                                "source": msg.get('source', 'external')
                            }
                        })
                        print(f"[CONVERSION] Message {idx+1}: Added ASSISTANT message - '{answer[:50]}...' (source: {msg.get('source', 'external')})")
            
            # Store conversation
            _set_data(f"session:{user_id}:history", internal_conversation)
            
            # Verification logging
            print(f"\n{'='*80}")
            print(f"[REDIS STORAGE] Session initialized for user: {user_id}")
            print(f"{'='*80}")
            print(f"[REDIS] ✅ User profile stored:")
            print(f"  - Name: {user_profile.get('name', 'Unknown')}")
            print(f"  - DOB: {user_profile.get('date_of_birth', 'Unknown')}")
            print(f"\n[REDIS] ✅ Conversation history stored:")
            print(f"  - Total messages in Redis: {len(internal_conversation)}")
            
            if internal_conversation:
                print(f"\n[REDIS] First few messages in Redis:")
                for i, msg in enumerate(internal_conversation[:4]):
                    role = msg.get('role', 'unknown')
                    content_preview = msg.get('content', '')[:60]
                    source = msg.get('metadata', {}).get('source', 'N/A')
                    print(f"  {i+1}. [{role.upper()}] {content_preview}... (source: {source})")
            print(f"{'='*80}\n")
            
            # Initialize empty summary
            self.store_conversation_summary(user_id, "New conversation started.")
            
            # Store metadata
            metadata = {
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "messages_imported": len(internal_conversation),
                "last_summary_at": datetime.utcnow().isoformat()
            }
            _set_data(f"session:{user_id}:metadata", metadata)
            
            return {
                "status": "success",
                "user_id": user_id
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[SESSION] Error initializing: {e}")
            return {
                "status": "error",
                "user_id": user_id,
                "message": str(e)
            }
    
    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        if not self.redis:
            return False
        
        try:
            conversation = self.get_conversation_history(session_id)
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            if metadata:
                message["metadata"] = metadata
            
            conversation.append(message)
            
            # Keep last N messages (sliding window)
            context_window = settings.CONVERSATION_CONTEXT_WINDOW
            if len(conversation) > context_window:
                conversation = conversation[-context_window:]
            
            key = f"session:{session_id}:history"
            # Store permanently — no TTL
            self.redis.set(key, json.dumps(conversation))
            return True
        except:
            return False
    
    def should_update_summary(self, user_id: str) -> bool:
        """Check if we should update the conversation summary (every 6 messages)."""
        conversation = self.get_conversation_history(user_id)
        
        # Get last summary metadata
        try:
            summary_data_str = self.redis.get(f"session:{user_id}:summary")
            if summary_data_str:
                summary_data = json.loads(summary_data_str)
                last_summary_count = summary_data.get('message_count', 0)
            else:
                last_summary_count = 0
        except:
            last_summary_count = 0
        
        # Update based on configured threshold
        messages_since_summary = len(conversation) - last_summary_count
        
        return messages_since_summary >= settings.CONVERSATION_SUMMARY_THRESHOLD
    
    def store_chart_data(self, user_id: str, chart_data: dict):
        if not self.redis:
            return
        try:
            key = f"session:{user_id}:chart"
            print(f"[REDIS] STORE key={key}")
            self.redis.set(key, json.dumps(chart_data))
            print(f"[CACHE] [OK] Chart stored permanently (no TTL)")
        except Exception as e:
            print(f"[CACHE] Error storing chart: {e}")
            pass
    
    def store_dasha_data(self, user_id: str, dasha_data: dict):
        """
        Store Dasha data with a timestamp envelope for staleness detection.
        Data is stored permanently in Redis (no TTL); freshness is controlled
        in get_dasha_data() via DASHA_REFRESH_DAYS.
        """
        if not self.redis:
            return
        try:
            key = f"session:{user_id}:dasha"
            print(f"[REDIS] STORE key={key}")
            envelope = {
                "data": dasha_data,
                "stored_at": datetime.utcnow().isoformat()  # For staleness check on read
            }
            self.redis.set(key, json.dumps(envelope))
            print(f"[CACHE] [OK] Dasha stored permanently with timestamp (refresh threshold: {settings.DASHA_REFRESH_DAYS} days)")
        except Exception as e:
            print(f"[CACHE] Error storing dasha: {e}")
            pass
    
    def store_transit_data(self, user_id: str, transit_data: dict):
        """
        Store transit data with a timestamp envelope for staleness detection.
        Data is stored permanently in Redis (no TTL); freshness is controlled
        in get_transit_data() via TRANSIT_REFRESH_HOURS.
        """
        if not self.redis:
            return
        try:
            key = f"session:{user_id}:transit"
            print(f"[REDIS] STORE key={key}")
            envelope = {
                "data": transit_data,
                "stored_at": datetime.utcnow().isoformat()  # For staleness check on read
            }
            self.redis.set(key, json.dumps(envelope))
            print(f"[CACHE] [OK] Transit stored permanently with timestamp (refresh threshold: {settings.TRANSIT_REFRESH_HOURS}h)")
        except Exception as e:
            print(f"[CACHE] Error storing transit: {e}")
            pass
    
    def update_user_profile(self, user_id: str, user_profile: dict):
        """Overwrite the user profile in Redis for an existing session (permanent, no TTL)."""
        if not self.redis:
            return
        try:
            key = f"session:{user_id}:user_profile"
            self.redis.set(key, json.dumps(user_profile))
            print(f"[REDIS] Profile updated permanently for {user_id}: DOB={user_profile.get('date_of_birth', 'N/A')}")
        except Exception as e:
            print(f"[SESSION] Error updating profile for {user_id}: {e}")

    def overwrite_conversation_history(self, user_id: str, conversation_history: list):
        """Convert external conversation history and overwrite existing Redis history (permanent, no TTL)."""
        if not self.redis:
            return
        try:
            internal_conversation = []
            for idx, msg in enumerate(conversation_history):
                timestamp = msg.get('timestamp')
                if isinstance(timestamp, dict) and '$date' in timestamp:
                    timestamp = timestamp['$date']
                elif timestamp is None:
                    timestamp = datetime.utcnow().isoformat()

                question = msg.get('question', '').strip()
                answer = msg.get('answer', '').strip()

                if question:
                    internal_conversation.append({
                        "role": "user",
                        "content": question,
                        "timestamp": timestamp
                    })
                if answer:
                    internal_conversation.append({
                        "role": "assistant",
                        "content": answer,
                        "timestamp": timestamp,
                        "metadata": {"source": msg.get('source', 'external')}
                    })

            key = f"session:{user_id}:history"
            # Store permanently — no TTL
            self.redis.set(key, json.dumps(internal_conversation))
            print(f"[REDIS] History overwritten permanently for {user_id}: {len(internal_conversation)} messages")
        except Exception as e:
            print(f"[SESSION] Error overwriting history for {user_id}: {e}")

    def get_conversation_phase(self, user_id: str) -> dict:
        """Get conversation phase for progressive disclosure."""
        if not self.redis:
            return {"phase": "INITIAL", "topic": None, "last_query": None, "followup_count": 0}
        try:
            data = self.redis.get(f"session:{user_id}:conv_phase")
            if data:
                return json.loads(data)
        except:
            pass
        return {"phase": "INITIAL", "topic": None, "last_query": None, "followup_count": 0}

    def set_conversation_phase(self, user_id: str, phase: str, topic: str = None,
                                last_query: str = None, followup_count: int = 0):
        """Store conversation phase for progressive disclosure."""
        if not self.redis:
            return
        try:
            data = {
                "phase": phase,
                "topic": topic,
                "last_query": last_query,
                "followup_count": followup_count,
                "updated_at": datetime.utcnow().isoformat()
            }
            self.redis.set(f"session:{user_id}:conv_phase", json.dumps(data))
        except Exception as e:
            print(f"[PHASE] Error storing phase: {e}")

    def extend_session(self, user_id: str):
        """No-op: all session data is stored permanently in Redis (no TTL to extend)."""
        pass
    
    def clear_session(self, session_id: str):
        if not self.redis:
            return False
        try:
            keys = [
                f"session:{session_id}:user_profile",
                f"session:{session_id}:history",
                f"session:{session_id}:summary",
                f"session:{session_id}:metadata",
                f"session:{session_id}:chart",
                f"session:{session_id}:dasha",
                f"session:{session_id}:transit",
                f"session:{session_id}:conv_phase"
            ]
            self.redis.delete(*keys)
            return True
        except:
            return False
    
    def get_active_sessions_count(self):
        if not self.redis:
            return 0
        try:
            keys = self.redis.keys("session:*:metadata")
            return len(keys)
        except:
            return 0


# Global session manager
_session_manager = None

def get_session_manager():
    global _session_manager
    if _session_manager is None:
        _session_manager = EnhancedSessionManager()
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
            print(f"\n[REDIS] Session already exists for {user_id} — performing selective refresh.")

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
                print(f"[REDIS] History refreshed: {len(conversation)} external messages imported.")

            # Evict stale calculated data — forces recompute on next /message
            for stale_key in [
                f"session:{user_id}:chart",
                f"session:{user_id}:dasha",
                f"session:{user_id}:transit",
            ]:
                if session_manager.redis:
                    session_manager.redis.delete(stale_key)
            print(f"[REDIS] Stale chart/dasha/transit cache evicted for {user_id}.")

            return InitializeSessionResponse(
                user_id=user_id,
                status="refreshed"
            )

        result = session_manager.initialize_session(
            user_id=user_id,
            user_profile=request.user_profile.model_dump() if hasattr(request.user_profile, 'model_dump') else request.user_profile.dict(),
            conversation_history=conversation
        )

        print(f"\n[REDIS] Initialized NEW session for {user_id} - Status: {result['status']}")

        return InitializeSessionResponse(
            user_id=result['user_id'],
            status=result['status']
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[SESSION_ERROR] Error initializing session: {e}")
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
        print("Testing XYZ")
        if not user_profile:
            print(f"[WARNING] /message blocked: Session not found in Redis for user: {user_id}")
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
                    print(f"[PRE-SAFETY] LLM vulgarity fallback triggered — blocking")
                    return True
            except Exception as _e:
                print(f"[PRE-SAFETY] LLM vulgarity check error (fail-open): {_e}")
            return False

        if _is_vulgar(question):
            print(f"[PRE-SAFETY] Vulgar content detected — returning hard block")
            from src.safety.templates import HARD_BLOCK_VULGAR
            session_manager.add_message(user_id, "user", question)
            session_manager.add_message(user_id, "assistant", HARD_BLOCK_VULGAR,
                                        metadata={"intent": "HARD_BLOCK", "source": "safety"})
            return SendMessageResponse(
                user_id=user_id,
                question=question,
                answer=HARD_BLOCK_VULGAR,
                source="openai"
            )

        # ====================================================================
        # STEP 1: GET CONVERSATION CONTEXT
        # ====================================================================
        full_history = session_manager.get_conversation_history(user_id) or []
        conversation_summary = session_manager.get_conversation_summary(user_id)
        
        print(f"\n{'='*80}")
        print(f"[REDIS CONVERSATION CONTEXT] Fetched from Redis for User: {user_id}")
        print(f"{'='*80}")
        print(f"Total messages in history: {len(full_history)}")
        print(f"Conversation summary available: {'Yes' if conversation_summary else 'No'}")
        if conversation_summary:
            print(f"Summary: {conversation_summary[:100]}...")
        
        # Verification: Show what's in Redis
        if full_history:
            print(f"\n[REDIS VERIFICATION] Conversation history details:")
            for i, msg in enumerate(full_history[:6]):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:60]
                source = msg.get('metadata', {}).get('source', 'N/A')
                print(f"  {i+1}. [{role.upper():9}] {content}... (source: {source})")
            
            if len(full_history) > 6:
                print(f"  ... and {len(full_history) - 6} more messages")
        else:
            print(f"[REDIS VERIFICATION] No conversation history (first message)")
            print(f"{'='*80}\n")
            print(f"[REDIS CONVERSATION CONTEXT] Fetched from Redis for User: {user_id}")
            print(f"{'='*80}")
            print(f"Total messages in history: {len(full_history)}")
            print(f"Conversation summary available: {'Yes' if conversation_summary else 'No'}")
            if conversation_summary:
                print(f"Summary: {conversation_summary[:100]}...")
            
            # Verification: Show what's in Redis
            if full_history:
                print(f"\n[REDIS VERIFICATION] Conversation history details:")
                for i, msg in enumerate(full_history[:6]):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:60]
                    source = msg.get('metadata', {}).get('source', 'N/A')
                    print(f"  {i+1}. [{role.upper():9}] {content}... (source: {source})")
                
                if len(full_history) > 6:
                    print(f"  ... and {len(full_history) - 6} more messages")
            else:
                print(f"[REDIS VERIFICATION] No conversation history (first message)")
            print(f"{'='*80}\n")
        
        # ====================================================================
        # STEP 2: ANALYZE MESSAGE INTENT (LLM-Based)
        # ====================================================================
        print(f"\n[STEP 1: INTENT ANALYSIS]")
        print(f"Analyzing: '{question}'")
        
        intent_analysis = context_manager.analyze_message_intent(
            current_query=question,
            conversation_history=full_history[-10:],  # Last 10 messages for context
            conversation_summary=conversation_summary
        )

        # ── Reset conversation phase on NEW_TOPIC ────────────────────────
        if intent_analysis.get('intent_type') == 'NEW_TOPIC':
            conv_phase_check = session_manager.get_conversation_phase(user_id)
            if conv_phase_check.get('phase') != 'INITIAL':
                print(f"[PHASE] NEW_TOPIC detected → resetting phase from {conv_phase_check.get('phase')} to INITIAL")
                session_manager.set_conversation_phase(user_id, phase="INITIAL")

        # ====================================================================
        # STEP 3: RESOLVE CONTEXTUAL QUERY (Confidence-Based)
        # ====================================================================
        print(f"\n[STEP 2: SEMANTIC INTERPRETATION]")

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
            print(f"[PHASE] Skipping semantic expansion — phase={_phase_now}, response={_response_type_now}")
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
                
                print(f"\n[CLARIFICATION REQUESTED]")
                print(f"  Ambiguity Score: {resolution_result['ambiguity_score']:.2f}")
                print(f"  Returning clarification question instead of processing query")
                
                # Store the clarification exchange
                session_manager.add_message(user_id, "user", question)
                session_manager.add_message(
                    user_id,
                    "assistant",
                    clarification_answer,
                    metadata={
                        "intent": "CLARIFICATION_REQUEST",
                        "source": "openai",
                        "ambiguity_score": resolution_result['ambiguity_score']
                    }
                )
                
                processing_time = time.time() - start_time
                
                return SendMessageResponse(
                    user_id=user_id,
                    question=question,
                    answer=clarification_answer,
                    source="openai"
                )
        
        # Get the processed query (original, expanded, or hinted)
        processed_query = resolution_result['processed_query']
        
        print(f"\n[RESOLUTION RESULT]")
        print(f"  Action: {resolution_result['action']}")
        print(f"  Ambiguity Score: {resolution_result['ambiguity_score']:.2f}")
        print(f"  Original Query: {question}")
        print(f"  Processed Query: {processed_query}")
        if processed_query != question:
            print(f"  [OK] Query enhanced for clarity")
        else:
            print(f"  [INFO]  No modification needed")
        
        # ====================================================================
        # STEP 4: PREPARE CONTEXT FOR ORCHESTRATOR
        # ====================================================================
        print(f"\n[STEP 3: PREPARING ORCHESTRATOR CONTEXT]")
        
        # Get recent history (context window)
        if len(full_history) > settings.CONVERSATION_CONTEXT_WINDOW:
            recent_history = full_history[-settings.CONVERSATION_CONTEXT_WINDOW:]
            print(f"Sending last {settings.CONVERSATION_CONTEXT_WINDOW} of {len(full_history)} messages")
        else:
            recent_history = full_history
            print(f"Sending all {len(full_history)} messages")
        
        # Log what's being sent to orchestrator
        print(f"\n{'-'*80}")
        print(f"[MESSAGES SENT TO ORCHESTRATOR]")
        print(f"{'-'*80}")
        for i, msg in enumerate(recent_history, 1):
            role_label = "[USER]" if msg['role'] == 'user' else "[BOT]"
            content_preview = msg['content'][:70] + "..." if len(msg['content']) > 70 else msg['content']
            print(f"{i}. {role_label}: {content_preview}")
        
        print(f"\n[CURRENT QUERY TO ORCHESTRATOR]")
        print(f"  Original User Query: {question}")
        print(f"  Processed Query: {processed_query}")
        print(f"  Intent Type: {intent_analysis['intent_type']}")
        print(f"  Resolution Action: {resolution_result['action']}")
        if resolution_result['action'] == 'EXPAND':
            print(f"  [OK] Query expanded for clarity (confidence: {resolution_result['ambiguity_score']:.2f})")
        elif resolution_result['action'] == 'HINT':
            print(f"  [INFO]  Hint added for context (confidence: {resolution_result['ambiguity_score']:.2f})")
        print(f"{'-'*80}\n")
        
        # ====================================================================
        # STEP 5: GET CACHED CALCULATIONS
        # ====================================================================
        cached_chart = session_manager.get_chart_data(user_id)
        cached_dasha = session_manager.get_dasha_data(user_id)
        cached_transit = session_manager.get_transit_data(user_id)
        
        print(f"[REDIS CACHED DATA FETCH]")
        print(f"  Chart: {'[OK] Fetched from Redis' if cached_chart else '[MISSING] Not in Redis'}")
        print(f"  Dasha: {'[OK] Fetched from Redis' if cached_dasha else '[MISSING] Not in Redis'}")
        print(f"  Transit: {'[OK] Fetched from Redis' if cached_transit else '[MISSING] Not in Redis'}")

        
        # ── Load conversation phase for progressive disclosure ────────────
        conv_phase_data = session_manager.get_conversation_phase(user_id)
        print(f"[PHASE] Current phase: {conv_phase_data.get('phase')} | topic: {conv_phase_data.get('topic')}")

        orchestrator_session_data = {
            "chart_data": cached_chart,
            "dasha_data": cached_dasha,
            "transit_data": cached_transit,
            "summary": conversation_summary,
            "intent_analysis": intent_analysis,
            "conversation_phase": conv_phase_data,
            "original_user_question": question  # True original before semantic expansion
        }
        
        # Log what cached data is being passed to orchestrator
        if cached_chart:
            print(f"[CACHE] [OK] Passing cached chart to orchestrator")
        if cached_dasha:
            print(f"[CACHE] [OK] Passing cached dasha to orchestrator")
        if cached_transit:
            print(f"[CACHE] [OK] Passing cached transit to orchestrator")
        
        # ====================================================================
        # STEP 6: PROCESS QUERY WITH ORCHESTRATOR
        # ====================================================================
        print(f"\n[STEP 4: CALLING ORCHESTRATOR]")
        
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
            print(f"[POST_PROCESS] Removed 'thank you' pattern")
        
        # Enforce word maximum for mobile (phase-aware)
        # Use the RESULT phase (what the orchestrator decided) not the INPUT phase
        result_phase = (result.get('conversation_phase') or {}).get('phase', conv_phase_data.get('phase', 'INITIAL'))
        if result_phase == 'FOLLOWUP_LOOP' and conv_phase_data.get('phase') == 'AWAITING_DETAIL':
            # User agreed to details → detailed response capped at 300 words
            MAX_MOBILE_WORDS = 300
        elif result_phase == 'FOLLOWUP_LOOP':
            # Follow-up loop responses capped at 200 words
            MAX_MOBILE_WORDS = 200
        elif result_phase == 'AWAITING_DETAIL':
            # Initial short response → hard cap at 100 words
            MAX_MOBILE_WORDS = 100
        else:
            MAX_MOBILE_WORDS = 100  # Default fallback (also initial)
        word_count = len(answer.split())

        if word_count > MAX_MOBILE_WORDS:
            print(f"[MOBILE] Response too long ({word_count} words), truncating to {MAX_MOBILE_WORDS}...")
            
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
                detected_lang = result.get('detected_language', 'en')
                if detected_lang in ['hi', 'hi-lat']:
                    answer += " Aur gehrai mein jaanna chahein toh poochh sakte hain."
                else:
                    answer += " Feel free to ask if you'd like to explore this further."
            
            print(f"[MOBILE] Truncated: {word_count} → {len(answer.split())} words")
        
        print(f"\n[ORCHESTRATOR RESULT]")
        print(f"  Intent: {intent}")
        print(f"  Confidence: {confidence:.2f}")
        print(f"  Answer length: {len(answer)} characters ({len(answer.split())} words)")
        
        # ====================================================================
        # STEP 7: STORE NEW CALCULATIONS IN CACHE
        # ====================================================================
        # Only store if not already cached
        if result.get('chart_data') and not cached_chart:
            print(f"[REDIS CACHE] Storing NEW chart data to Redis...")
            session_manager.store_chart_data(user_id, result['chart_data'])
            print(f"[REDIS CACHE] [OK] Chart stored in Redis")
        
        if result.get('dasha_data') and not cached_dasha:
            print(f"[REDIS CACHE] Storing NEW dasha data to Redis...")
            session_manager.store_dasha_data(user_id, result['dasha_data'])
            print(f"[REDIS CACHE] [OK] Dasha stored in Redis")
        
        if result.get('transit_data') and not cached_transit:
            print(f"[REDIS CACHE] Storing NEW transit data to Redis...")
            session_manager.store_transit_data(user_id, result['transit_data'])
            print(f"[REDIS CACHE] [OK] Transit stored in Redis")
        
        # ====================================================================
        # STEP 8: UPDATE CONVERSATION HISTORY
        # ====================================================================
        print(f"\n[REDIS] Saving latest user & assistant messages to Redis history...")

        session_manager.add_message(user_id, "user", question)  # Store original question
        session_manager.add_message(
            user_id,
            "assistant",
            answer,
            metadata={
                "intent": intent,
                "confidence": confidence,
                "source": "openai",
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
                followup_count=new_phase.get('followup_count', 0)
            )
            print(f"[PHASE] Updated to: {new_phase.get('phase')} | topic: {new_phase.get('topic')}")

        # ====================================================================
        # STEP 9: UPDATE CONVERSATION SUMMARY (Every 10 messages)
        # ====================================================================
        if session_manager.should_update_summary(user_id):
            print(f"\n[STEP 5: UPDATING CONVERSATION SUMMARY]")
            print(f"  Threshold reached: Generating new summary...")
            
            updated_history = session_manager.get_conversation_history(user_id)
            new_summary = context_manager.generate_conversation_summary(
                conversation_history=updated_history,
                current_summary=conversation_summary
            )
            
            session_manager.store_conversation_summary(user_id, new_summary)
        
        # Extend session
        session_manager.extend_session(user_id)
        
        processing_time = time.time() - start_time
        
        print(f"\n[RESPONSE SUMMARY]")
        print(f"  Processing time: {processing_time:.2f}s")
        print(f"  Context intent: {intent_analysis['intent_type']}")
        print(f"  Resolution action: {resolution_result['action']}")
        print(f"  Ambiguity score: {resolution_result['ambiguity_score']:.2f}")
        print(f"  Orchestrator intent: {intent}")
        print(f"  Response length: {len(answer)} characters")
        print(f"{'='*80}\n")
        
        # Return response
        return SendMessageResponse(
            user_id=user_id,
            question=question,
            answer=answer,
            source="openai"
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