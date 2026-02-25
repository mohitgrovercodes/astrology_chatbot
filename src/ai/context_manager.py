# src/ai/context_manager.py
"""
AI Context Manager for NakshatraAI.

Handles intelligent conversation analysis, semantic query resolution,
and summarization using LLMs.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from src.llm.factory import LLMFactory

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Professional-grade context manager using LLM for intelligent analysis.
    """
    
    def __init__(self):
        """Initialize fast LLM for context analysis."""
        self.fast_llm = LLMFactory.create(
            purpose="classification",
            temperature=0.1
        )
    
    def analyze_message_intent(
        self,
        current_query: str,
        conversation_history: List[Dict],
        conversation_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """Classify message as CONTINUATION, NEW_TOPIC, or CLARIFICATION."""
        conv_text = self._format_conversation(conversation_history)
        
        analysis_prompt = f"""You are a conversation analyzer for an astrology chatbot.

Analyze the user's current message and determine its intent.

CONVERSATION SUMMARY (if available):
{conversation_summary or "No summary yet - this is an early conversation"}

RECENT CONVERSATION:
{conv_text or "No previous messages"}

CURRENT USER MESSAGE:
"{current_query}"

Respond in JSON format:
{{
    "intent_type": "CONTINUATION" | "NEW_TOPIC" | "CLARIFICATION",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "referenced_topic": "Specific topic (e.g., 'career' or 'Saturn transit')",
    "requires_context": true/false
}}
"""
        try:
            response = self.fast_llm.invoke(analysis_prompt)
            result = json.loads(response.content)
            return result
        except Exception as e:
            logger.error(f"[CONTEXT] Intent analysis error: {e}")
            return {
                "intent_type": "NEW_TOPIC",
                "confidence": 0.5,
                "reasoning": "Fallback due to error",
                "referenced_topic": None,
                "requires_context": False
            }

    def resolve_contextual_query(
        self,
        current_query: str,
        conversation_history: List[Dict],
        intent_analysis: Dict
    ) -> Dict[str, Any]:
        """Resolve ambiguity and inject context into follow-up queries."""
        if not intent_analysis.get('requires_context'):
            return {
                "action": "NONE",
                "processed_query": current_query,
                "ambiguity_score": 0.0,
                "clarification_needed": False,
                "explanation": "Clear query"
            }

        # Heuristic pre-check for common follow-up patterns
        FOLLOWUP_PHRASES = ['tell me more', 'what else', 'go on', 'expand', 'explain']
        query_lower = current_query.lower()
        referenced_topic = intent_analysis.get('referenced_topic', 'the previous topic')
        
        if any(phrase in query_lower for phrase in FOLLOWUP_PHRASES) and len(query_lower.split()) < 5:
            return {
                "action": "EXPAND",
                "processed_query": f"{current_query} about {referenced_topic}",
                "ambiguity_score": 0.9,
                "clarification_needed": False,
                "explanation": "Pattern-based expansion"
            }

        # LLM-based semantic interpretation
        conv_text = self._format_conversation(conversation_history[-3:])
        resolution_prompt = f"""You are a semantic analyzer for an astrology chatbot.

Analyze the user's query relative to the conversation context.

CONTEXT: {referenced_topic}
HISTORY: {conv_text}
QUERY: "{current_query}"

Respond in JSON:
{{
    "ambiguity_score": 0.0-1.0,
    "can_resolve_safely": true/false,
    "processed_query": "The resolved query (e.g., 'Tell me more about career' instead of 'Tell me more')",
    "reasoning": "Explanation"
}}
"""
        try:
            response = self.fast_llm.invoke(resolution_prompt)
            result = json.loads(response.content)
            
            score = result.get('ambiguity_score', 0.5)
            if score > 0.6 and result.get('can_resolve_safely'):
                return {
                    "action": "EXPAND",
                    "processed_query": result.get('processed_query', current_query),
                    "ambiguity_score": score,
                    "clarification_needed": False,
                    "explanation": result.get('reasoning')
                }
            elif score > 0.3:
                return {
                    "action": "HINT",
                    "processed_query": f"Regarding {referenced_topic}: {current_query}",
                    "ambiguity_score": score,
                    "clarification_needed": False,
                    "explanation": "Medium confidence hint"
                }
            else:
                return {
                    "action": "ASK_CLARIFICATION",
                    "processed_query": current_query,
                    "ambiguity_score": score,
                    "clarification_needed": True,
                    "clarification_question": f"Could you clarify what you mean regarding {referenced_topic}?",
                    "explanation": "Low confidence"
                }
        except Exception as e:
            logger.error(f"[CONTEXT] Resolution error: {e}")
            return {"action": "NONE", "processed_query": current_query, "ambiguity_score": 0.0, "clarification_needed": False, "explanation": "Fallback"}

    def generate_conversation_summary(
        self,
        conversation_history: List[Dict],
        current_summary: Optional[str] = None
    ) -> str:
        """Create or update a concise conversation summary."""
        recent_messages = conversation_history[-6:]
        conv_text = self._format_conversation(recent_messages)
        
        prompt = f"""Summarize this astrology conversation concisely (2-3 sentences).
{f'PREVIOUS SUMMARY: {current_summary}' if current_summary else ''}
NEW MESSAGES:
{conv_text}
ONLY respond with the summary text."""
        
        try:
            response = self.fast_llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"[CONTEXT] Summary error: {e}")
            return current_summary or "Astrological discussion."

    def _format_conversation(self, conversation: List[Dict]) -> str:
        return "\n".join([f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in conversation])

# Global instance
_context_manager = None
def get_context_manager():
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
