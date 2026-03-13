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
import redis
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


def validate_and_sanitize_response(
    question: str,
    answer: str,
    intent_analysis: Dict[str, Any],
    recent_history: List[Dict[str, Any]],
    context_window: int = 20,
    min_numbered_points: int = 0,
) -> str:
    """
    Use a small LLM to semantically validate and, if needed, rewrite the draft
    answer so that it stays consistent with the user's intent and recent context.

    This replaces brittle word-level pattern matching with holistic,
    sentence-level understanding.
    """
    draft_answer = answer or ""
    q_lower = (question or "").lower()
    a_lower = draft_answer.lower()

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
    needs_numbering_enforcement = bool(min_numbered_points and min_numbered_points > 0)
    should_validate = (
        likely_sensitive
        or likely_overconfident
        or likely_short_or_generic
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

STRUCTURE ENFORCEMENT (if requested):
- When 'min_numbered_points' is > 0, you MUST ensure that the final answer contains AT LEAST
  that many clearly numbered points (for example: "1)", "2)", "3)", etc.).
- Each numbered point should describe a distinct astrological factor AND what it means for
  the user. These points can appear after a short narrative introduction, but they must be
  present and easy for the user to see and count.

Respond in STRICT JSON ONLY, no extra text, like this:
{{
  "is_coherent": true/false,
  "needs_revision": true/false,
  "reason": "short explanation of any problem you see",
  "revised_answer": "a fully corrected answer in the SAME LANGUAGE as the draft, or empty string if no change is needed",
  "min_numbered_points": """ + str(int(min_numbered_points or 0)) + """
}}"""

        llm = _get_response_validator_llm()
        resp = llm.invoke(validator_prompt)
        raw = getattr(resp, "content", str(resp))
        data = _json.loads(raw)

        final_answer = draft_answer
        if isinstance(data, dict) and data.get("needs_revision") and data.get("revised_answer"):
            logger.info(f"[VALIDATOR] LLM revised answer: {data.get('reason', '')}")
            final_answer = data["revised_answer"]

        # Deterministic post-check: if we explicitly require numbered points
        # and the current answer still does not meet the minimum, trigger a
        # second, focused rewrite pass that ONLY enforces numbered structure.
        if needs_numbering_enforcement:
            current_points = _count_numbered_points(final_answer)
            if current_points < int(min_numbered_points or 0):
                logger.info(
                    f"[VALIDATOR] Numbering enforcement: found {current_points} "
                    f"points, required {int(min_numbered_points or 0)}. Forcing rewrite."
                )
                rewrite_prompt = f"""You are an astrology editor.

Rewrite the assistant's answer so that it:
- keeps the SAME timing windows, planets, houses and factual content
- stays in the SAME LANGUAGE and script as the original answer
- sounds like a warm, professional astrologer
- and MOST IMPORTANTLY, presents AT LEAST {int(min_numbered_points or 0)} clearly numbered
  astrological reasoning points (for example: "1) ...", "2) ...", "3) ...").

Guidelines:
- You may add short connector sentences, but do NOT invent new dates or change years.
- Group related ideas into numbered points so that each point describes ONE key factor
  (house lord, dasha/pratyantar, yoga, planetary condition, divisional chart insight, etc.)
  and directly states what it means for this person's life.
- You may keep a short 1–2 sentence introduction BEFORE the numbered list.

Return ONLY the rewritten answer text, no JSON, no explanation.

ORIGINAL ANSWER:
\"\"\"{final_answer}\"\"\""""
                resp2 = llm.invoke(rewrite_prompt)
                rewritten = getattr(resp2, "content", str(resp2)).strip()
                if rewritten:
                    # Even if the model still under-shoots, prefer the rewritten
                    # version because it will usually be closer to the desired
                    # structure.
                    logger.info("[VALIDATOR] Applied forced numbered-structure rewrite")
                    return rewritten

        return final_answer
    except Exception as e:
        logger.info(f"[VALIDATOR] Error in LLM response validator: {e}")
        return draft_answer


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
            logger.info(f"[SESSION] [OK] Redis connected on {redis_host}:{redis_port}")
        except Exception as e:
            logger.info(f"[SESSION] [FAIL] Redis connection failed: {e}")
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
            logger.info(f"[SUMMARY] Stored conversation summary permanently at key: {key}")
        except Exception as e:
            logger.info(f"[SUMMARY] Error storing summary: {e}")
    
    def get_chart_data(self, user_id: str):
        if not self.redis:
            return None
        try:
            key = f"session:{user_id}:chart"
            logger.info(f"[REDIS] GET key={key}")
            data = self.redis.get(key)
            if data:
                chart = json.loads(data)
                # Schema version check: evict charts missing vargottama/divisional_charts_simple
                # (computed in serializer v2) so they get recalculated with enriched data.
                if 'divisional_charts_simple' not in chart or 'vargottama' not in chart:
                    logger.info(f"[CHART] Schema v1 detected for {user_id} (missing divisional/vargottama) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                logger.info(f"[REDIS] Found chart in Redis")
                return chart
            else:
                logger.info(f"[REDIS] No chart found at key: {key}")
                return None
        except Exception as e:
            logger.info(f"[SESSION] ERROR: Failed to get chart data for {user_id}: {e}")
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
            logger.info(f"[REDIS] GET key={key}")
            raw = self.redis.get(key)
            if not raw:
                logger.info(f"[REDIS] No dasha found at key: {key}")
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
                    logger.info(f"[DASHA] STALE — cached {age_days:.1f} days ago (threshold: {refresh_threshold} days). Evicting and forcing recompute.")
                    self.redis.delete(key)
                    return None

                data = envelope.get("data", {})
                # Schema version check: evict old formats missing enriched fields.
                # v1: missing upcoming_pratyantardashas entirely
                # v2: has upcoming_pratyantardashas but entries lack "status" field
                if data and "upcoming_pratyantardashas" not in data:
                    logger.info(f"[DASHA] Schema v1 detected for {user_id} (missing pratyantar detail) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                pds = data.get("upcoming_pratyantardashas", [])
                if pds and "status" not in pds[0]:
                    logger.info(f"[DASHA] Schema v2 detected for {user_id} (missing status field) — evicting to upgrade.")
                    self.redis.delete(key)
                    return None
                logger.info(f"[REDIS] Found dasha in Redis (age: {age_days:.1f} days, threshold: {refresh_threshold} days) — FRESH")
                return data
            else:
                # Legacy flat format — evict to migrate to new envelope
                logger.info(f"[DASHA] Legacy format detected for {user_id} — evicting and forcing recompute.")
                self.redis.delete(key)
                return None

        except Exception as e:
            logger.info(f"[SESSION] ERROR: Failed to get dasha data for {user_id}: {e}")
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
            logger.info(f"[REDIS] GET key={key}")
            raw = self.redis.get(key)
            if not raw:
                logger.info(f"[REDIS] No transit found at key: {key}")
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
                    logger.info(f"[TRANSIT] STALE — cached {age_hours:.1f}h ago (threshold: {refresh_threshold}h). Evicting key and forcing recompute.")
                    self.redis.delete(key)
                    return None

                logger.info(f"[REDIS] Found transit in Redis (age: {age_hours:.1f}h, threshold: {refresh_threshold}h) — FRESH")
                return envelope.get("data")
            else:
                # Legacy flat format — treat as stale to migrate to new envelope
                logger.info(f"[TRANSIT] Legacy format detected for {user_id} — evicting and forcing recompute.")
                self.redis.delete(key)
                return None

        except Exception as e:
            logger.info(f"[SESSION] ERROR: Failed to get transit data for {user_id}: {e}")
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

                logger.info(f"[DOB_VALIDATION] Checking DOB: {dob}")
                if not validation['valid']:
                    logger.info(f"[DOB_VALIDATION] ⚠️  Invalid: {validation['issue']}")
                    logger.debug(f"- Message: {validation['message']}")
                else:
                    logger.info(f"[DOB_VALIDATION] [OK] Valid - Age: {validation['age_years']} years, {validation['age_months']} months")

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
                        logger.info(f"[CONVERSION] Message {idx+1}: Added USER message - '{question[:50]}...'")
                    
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
                        logger.info(f"[CONVERSION] Message {idx+1}: Added ASSISTANT message - '{answer[:50]}...' (source: {msg.get('source', 'external')})")
            
            # Store conversation
            _set_data(f"session:{user_id}:history", internal_conversation)
            
            # Verification logging
            logger.debug(f"{'='*80}")
            logger.info(f"[REDIS STORAGE] Session initialized for user: {user_id}")
            logger.debug(f"{'='*80}")
            logger.info(f"[REDIS] [OK] User profile stored:")
            logger.debug(f"- Name: {user_profile.get('name', 'Unknown')}")
            logger.debug(f"- DOB: {user_profile.get('date_of_birth', 'Unknown')}")
            logger.info(f"[REDIS] [OK] Conversation history stored:")
            logger.debug(f"- Total messages in Redis: {len(internal_conversation)}")
            
            if internal_conversation:
                logger.info(f"[REDIS] First few messages in Redis:")
                for i, msg in enumerate(internal_conversation[:4]):
                    role = msg.get('role', 'unknown')
                    content_preview = msg.get('content', '')[:60]
                    source = msg.get('metadata', {}).get('source', 'N/A')
                    logger.debug(f"{i+1}. [{role.upper()}] {content_preview}... (source: {source})")
            logger.debug(f"{'='*80}")
            
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
            logger.info(f"[SESSION] Error initializing: {e}")
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
            logger.info(f"[REDIS] STORE key={key}")
            self.redis.set(key, json.dumps(chart_data))
            logger.info(f"[CACHE] [OK] Chart stored permanently (no TTL)")
        except Exception as e:
            logger.info(f"[CACHE] Error storing chart: {e}")
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
            logger.info(f"[REDIS] STORE key={key}")
            envelope = {
                "data": dasha_data,
                "stored_at": datetime.utcnow().isoformat()  # For staleness check on read
            }
            self.redis.set(key, json.dumps(envelope))
            logger.info(f"[CACHE] [OK] Dasha stored permanently with timestamp (refresh threshold: {settings.DASHA_REFRESH_DAYS} days)")
        except Exception as e:
            logger.info(f"[CACHE] Error storing dasha: {e}")
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
            logger.info(f"[REDIS] STORE key={key}")
            envelope = {
                "data": transit_data,
                "stored_at": datetime.utcnow().isoformat()  # For staleness check on read
            }
            self.redis.set(key, json.dumps(envelope))
            logger.info(f"[CACHE] [OK] Transit stored permanently with timestamp (refresh threshold: {settings.TRANSIT_REFRESH_HOURS}h)")
        except Exception as e:
            logger.info(f"[CACHE] Error storing transit: {e}")
            pass
    
    def update_user_profile(self, user_id: str, user_profile: dict):
        """Overwrite the user profile in Redis for an existing session (permanent, no TTL)."""
        if not self.redis:
            return
        try:
            key = f"session:{user_id}:user_profile"
            self.redis.set(key, json.dumps(user_profile))
            logger.info(f"[REDIS] Profile updated permanently for {user_id}: DOB={user_profile.get('date_of_birth', 'N/A')}")
        except Exception as e:
            logger.info(f"[SESSION] Error updating profile for {user_id}: {e}")

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
            logger.info(f"[REDIS] History overwritten permanently for {user_id}: {len(internal_conversation)} messages")
        except Exception as e:
            logger.info(f"[SESSION] Error overwriting history for {user_id}: {e}")

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
            logger.info(f"[PHASE] Error storing phase: {e}")

    def extend_session(self, user_id: str):
        """No-op: all session data is stored permanently in Redis (no TTL to extend)."""
        pass

    def store_detected_language(self, user_id: str, lang_code: str) -> None:
        """Persist the detected language for this session turn."""
        if not self.redis or not lang_code:
            return
        try:
            self.redis.set(f"session:{user_id}:lang", lang_code)
        except Exception as e:
            logger.info(f"[LANG] Error storing detected language: {e}")

    def get_detected_language(self, user_id: str) -> str:
        """Retrieve the previously detected language for this session (default 'en')."""
        if not self.redis:
            return "en"
        try:
            val = self.redis.get(f"session:{user_id}:lang")
            return val.decode() if isinstance(val, bytes) else (val or "en")
        except Exception:
            return "en"
    
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
        try:
            _session_manager = get_shared_session_manager()
        except Exception:
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
    evidence: Optional[Dict[str, Any]] = None


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
            for stale_key in [
                f"session:{user_id}:chart",
                f"session:{user_id}:dasha",
                f"session:{user_id}:transit",
            ]:
                if session_manager.redis:
                    session_manager.redis.delete(stale_key)
            logger.info(f"[REDIS] Stale chart/dasha/transit cache evicted for {user_id}.")

            return InitializeSessionResponse(
                user_id=user_id,
                status="refreshed"
            )

        result = session_manager.initialize_session(
            user_id=user_id,
            user_profile=request.user_profile.model_dump() if hasattr(request.user_profile, 'model_dump') else request.user_profile.dict(),
            conversation_history=conversation
        )

        logger.info(f"[REDIS] Initialized NEW session for {user_id} - Status: {result['status']}")

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
                source="openai"
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
            "detected_language": session_manager.get_detected_language(user_id)
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
                r"[^.!?\n]*(agar aap chah|agar chahein).{0,80}(detail|vistar|samjha|elaborate)[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*(aur (bhi )?detail mein samjha|aur jaanna hai|aur detail chahiye|aur bhi (batana|samjhana))[^.!?\n]*[.!?]?\s*",
                r"[^.!?\n]*\b(main aapko|I can).{0,50}(aur (bata|samjha|detail)|more detail|elaborate|explain further)[^.!?\n]*[.!?]?\s*",
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
            # User agreed to detailed reasoning → allow richer explanation (~600 words)
            MAX_MOBILE_WORDS = 600
        elif result_phase == 'FOLLOWUP_LOOP':
            # Follow-up loop responses (further questions) capped slightly lower
            MAX_MOBILE_WORDS = 500
        elif result_phase == 'AWAITING_DETAIL':
            # Initial short response → hard cap at 200 words
            MAX_MOBILE_WORDS = 200
        else:
            MAX_MOBILE_WORDS = 200  # Default fallback (also initial)
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

        # ── FINAL ENFORCEMENT: ensure initial short response ends with offer-for-detail question ──
        # This runs *after* any truncation so the closing question cannot be accidentally cut off.
        # The orchestrator injects a closing via pick_initial_closing(); only append if it got
        # truncated away — detected by absence of any question mark near the end of the answer.
        if result_phase == 'AWAITING_DETAIL':
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
        # initial timing answer), require AT LEAST 5 numbered astrological reasoning
        # points. We key this off the high-level intent returned by the orchestrator
        # plus the intent_type from the LLM intent analysis.
        min_points = 0
        _ia = intent_analysis or {}
        _ia_type = _ia.get("intent_type")
        # Only enforce numbered astro reasoning when we're in the astro prediction
        # flow and the message is a continuation/clarification (second step).
        if intent == "RAG_WITH_CALCULATION" and _ia_type in ("CONTINUATION", "CLARIFICATION"):
            min_points = 5

        answer = validate_and_sanitize_response(
            question=question,
            answer=answer,
            intent_analysis=intent_analysis,
            recent_history=recent_history,
            min_numbered_points=min_points,
        )

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
            logger.info(f"[PHASE] Updated to: {new_phase.get('phase')} | topic: {new_phase.get('topic')}")

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
        
        # Return response
        return SendMessageResponse(
            user_id=user_id,
            question=question,
            answer=answer,
            source="openai",
            evidence=result.get("astro_evidence") if isinstance(result, dict) else None,
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