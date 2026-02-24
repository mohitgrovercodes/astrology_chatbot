# src/ai/intent_classifier.py
# src\ai\intent_classifier.py
"""
LLM-Based Intent Classifier for NakshatraAI.

Uses an LLM (via LLMFactory) to accurately classify user queries into four categories:
- CHITCHAT: Greetings and conversational queries
- CALCULATION_ONLY: Raw chart data requests (no interpretation)
- RAG_WITH_CALCULATION: Personal predictions (chart + knowledge + interpretation)
- RAG_ONLY: General astrology theory (no user chart needed)
"""

from typing import Dict, List, Optional, Any
import json
import os
import re


class LLMIntentClassifier:
    """
    LLM-powered intent classifier for accurate query routing.
    
    Uses structured prompting to classify user queries into one of four categories.
    Falls back to pattern matching if LLM fails.
    """
    
    CATEGORIES = [
        "CHITCHAT",
        "CALCULATION_ONLY", 
        "RAG_WITH_CALCULATION",
        "RAG_ONLY",
        "AMBIGUOUS"  # NEW: Queries that need clarification
    ]
    
    # High-confidence pattern cache (exact matches only, 95%+ confidence)
    # Checked BEFORE calling LLM for instant classification
    SAFE_PATTERN_CACHE = {
        # CHITCHAT (100% confidence - greetings and thanks)
        "hi": "CHITCHAT",
        "hello": "CHITCHAT",
        "hey": "CHITCHAT",
        "namaste": "CHITCHAT",
        "good morning": "CHITCHAT",
        "good evening": "CHITCHAT",
        "thanks": "CHITCHAT",
        "thank you": "CHITCHAT",
        "bye": "CHITCHAT",
        "goodbye": "CHITCHAT",
        
        # CALCULATION_ONLY (95%+ confidence - raw data requests)
        "show my birth chart": "CALCULATION_ONLY",
        "show my kundali": "CALCULATION_ONLY",
        "show my chart": "CALCULATION_ONLY",
        "what is my lagna": "CALCULATION_ONLY",
        "what is my ascendant": "CALCULATION_ONLY",
        "what is my moon sign": "CALCULATION_ONLY",
        "what is my sun sign": "CALCULATION_ONLY",
        "what are my current dashas": "CALCULATION_ONLY",
        "show my dashas": "CALCULATION_ONLY",
        "display my chart": "CALCULATION_ONLY",
        "give me my chart": "CALCULATION_ONLY",
        
        # RAG_ONLY (95%+ confidence - general theory, no personal words)
        "what are panapara houses": "RAG_ONLY",
        "what are kendra houses": "RAG_ONLY",
        "what is a raj yoga": "RAG_ONLY",
        "what is raj yoga": "RAG_ONLY",
        "explain the 10th house": "RAG_ONLY",
        "explain the 7th house": "RAG_ONLY",
        "what does mars in 7th house mean": "RAG_ONLY",
        "what does jupiter in 10th house mean": "RAG_ONLY",
        "define mahadasha": "RAG_ONLY",
        "what is antardasha": "RAG_ONLY",
        "what is vimshottari dasha": "RAG_ONLY",
        "explain saturn return": "RAG_ONLY",
        
        # RAG_WITH_CALCULATION (95%+ confidence - "when will I" pattern)
        "when will i get married": "RAG_WITH_CALCULATION",
        "when will i get a job": "RAG_WITH_CALCULATION",
        "when will i have children": "RAG_WITH_CALCULATION",
        "when will i buy a house": "RAG_WITH_CALCULATION",
        "how is my career": "RAG_WITH_CALCULATION",
        "how is my health": "RAG_WITH_CALCULATION",
        "how is my marriage": "RAG_WITH_CALCULATION",
        "predict my future": "RAG_WITH_CALCULATION",
    }
    
    CLASSIFICATION_PROMPT = """You are an intelligent intent classifier for a Vedic astrology chatbot.

The user ALWAYS has birth details on file, so personalized predictions are always possible.
The query may be in ANY language — English, Hindi, Tamil, Hinglish, or mixed. Understand the semantic meaning regardless of language.

Classify the query into exactly ONE of these four categories based on what the user is fundamentally trying to achieve:

---

**CHITCHAT**
The user is having casual conversation — greeting, thanking, asking about the bot, or saying goodbye.
Core signal: No astrological intent. The user just wants to connect or wrap up.
Examples: "Hi", "Thanks", "Who are you?", "Namaste", "Bye", "Shukriya"

**CALCULATION_ONLY**
The user wants to *see* raw astrological data from their birth chart — positions, placements, dashas, divisional charts.
Core signal: They want data *displayed*, not interpreted. No prediction or meaning is being asked for.
Examples: "Show my birth chart", "What is my lagna?", "My planetary positions", "Current dasha period", "Display D9 chart"

**RAG_WITH_CALCULATION**
The user wants a *personalized* prediction, guidance, or interpretation specific to their own life situation.
Core signal: The answer must be tailored to THIS person's chart. It could be about future events, life areas (career, marriage, health, finance, relationships), or timing — and it requires understanding who they are astrologically.
This includes ANY language variant: "mere liye", "mujhe batao", "kab hoga", "meri kismat", "mera career", "for me", "in my chart", etc.
Also includes follow-up questions in an ongoing personal reading: "Why that time?", "What about my health?", "Is this good or bad?"
When the intent feels personal — even slightly — prefer this category over RAG_ONLY.
Examples: "When will I get married?", "Is 2025 good for my career?", "Mere liye kaisi job sahi rahegi?", "What does my Jupiter placement mean for me?", "Will I travel abroad?"

**RAG_ONLY**
The user is asking about astrology as a *subject* — concepts, theories, general interpretations.
Core signal: The answer would be the same for ANY person. No personalization needed.
This should only be chosen if the query is clearly educational or conceptual with no personal framing.
Examples: "What is a Raj Yoga?", "Explain the 10th house in general", "What does Saturn return mean?", "What are the qualities of a Scorpio moon in Vedic astrology?"

---

USER QUERY: "{query}"

CONVERSATION CONTEXT (last few messages):
{context}

Think step by step:
1. What does the user fundamentally want — data, a personal answer, education, or just conversation?
2. Is the query personal to their life situation (even implicitly)?
3. If the query is ambiguous between RAG_ONLY and RAG_WITH_CALCULATION, always prefer RAG_WITH_CALCULATION.

Respond with ONLY a valid JSON object — no extra text:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "reasoning": "One sentence explanation of why."}}
"""

    def __init__(self, llm=None, use_cache: bool = True):
        """
        Initialize LLM-based classifier.
        
        Args:
            llm: LangChain LLM instance (will be set by orchestrator if None)
            use_cache: Whether to cache classification results
        """
        self.llm = llm
        self.use_cache = use_cache
        self.cache = {}
        
        print("[INTENT] LLM-based classifier initialized")
        print(f"[INTENT] Categories: {', '.join(self.CATEGORIES)}")
    
    def set_llm(self, llm):
        """Set the LLM instance (called by orchestrator during initialization)."""
        self.llm = llm
        print("[INTENT] LLM connected to classifier")
    
    def _is_ambiguous(self, query: str, user_profile: Optional[Dict] = None) -> bool:
        """
        Detect if a query is ambiguous (could be theory OR personalized).
        
        Triggers:
        - Query mentions a planet/house WITHOUT context
        - User has birth data (so personalization is possible)
        - No explicit intent markers (e.g., "in general", "for me")
        
        Returns:
            True if query is ambiguous and needs clarification
        """
        # Only ambiguous if user HAS birth data (personalization is possible)
        if not user_profile or not user_profile.get('date_of_birth'):
            return False
        
        query_lower = query.lower().strip()
        
        # Ambiguous patterns: Mentions planet/house without clear intent
        ambiguous_patterns = [
            r'\btell me about (jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu)\b',
            r'\bwhat (is|are) (the )?(1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th) house\b',
            r'\bexplain (jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu)\b',
            r'\b(jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu) in astrology\b',
            r'\btell me about (the )?(1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th) house\b',
        ]
        
        # Check if query matches ambiguous patterns
        for pattern in ambiguous_patterns:
            if re.search(pattern, query_lower):
                # Check for explicit intent markers that REMOVE ambiguity
                
                # Theory markers (user wants general explanation)
                theory_markers = [
                    'in general', 'generally', 'what is', 'what are', 'define',
                    'meaning of', 'significance of', 'in vedic astrology',
                    'according to', 'classical', 'traditional'
                ]
                if any(marker in query_lower for marker in theory_markers):
                    return False  # Not ambiguous, user wants theory
                
                # Personalization markers (user wants their chart)
                personal_markers = [
                    'for me', 'my', 'mine', 'in my chart', 'in my life',
                    'will i', 'am i', 'do i', 'should i', 'when will i'
                ]
                if any(marker in query_lower for marker in personal_markers):
                    return False  # Not ambiguous, user wants personalization
                
                # No clear markers → AMBIGUOUS!
                return True
        
        return False
    
    def _is_nonsensical(self, query: str) -> bool:
        """
        Check if query is nonsensical (random numbers, gibberish, etc.).
        
        Returns:
            True if query appears to be nonsensical
        """
        q = query.strip()
        
        # Check if query is just numbers
        if q.isdigit() and len(q) > 4:
            return True
        
        # Check if query is too short to be meaningful
        if len(q) < 2:
            return True
        
        # Check if query has no letters (only numbers/symbols)
        if not any(c.isalpha() for c in q):
            return True
        
        return False
    
    def classify(
        self,
        query: str,
        user_profile: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Classify query using LLM.
        
        Args:
            query: User's input query
            user_profile: User profile data (to check if birth data exists)
            conversation_history: Previous messages (for context)
            
        Returns:
            Dict with intent, confidence, reasoning, and cached flag
        """
        # Pre-validation: Check for nonsensical input
        if self._is_nonsensical(query):
            result = {
                'intent': 'CHITCHAT',
                'confidence': 0.95,
                'reasoning': 'Input appears to be nonsensical or random',
                'cached': False
            }
            print(f"[INTENT] [VALIDATION] -> CHITCHAT (nonsensical input)")
            return result
        
        # NEW: Check for ambiguous queries BEFORE LLM classification
        if self._is_ambiguous(query, user_profile):
            result = {
                'intent': 'AMBIGUOUS',
                'confidence': 0.90,
                'reasoning': 'Query could be theory or personalized, needs clarification',
                'cached': False
            }
            print(f"[INTENT] [AMBIGUITY] -> AMBIGUOUS (needs clarification)")
            return result
        
        q = query.lower().strip()
        
        # Step 1: Check SAFE_PATTERN_CACHE first (instant, no LLM call!)
        if q in self.SAFE_PATTERN_CACHE:
            intent = self.SAFE_PATTERN_CACHE[q]
            result = {
                'intent': intent,
                'confidence': 0.98,  # High confidence for exact matches
                'reasoning': f'Pattern cache: exact match for {intent}',
                'cached': True,
                'cache_type': 'pattern'  # Track cache type
            }
            print(f"[INTENT] [PATTERN_CACHE] -> {intent} (instant)")
            return result
        
        # Step 2: Check LLM result cache
        cache_key = q
        if self.use_cache and cache_key in self.cache:
            result = self.cache[cache_key].copy()
            result['cached'] = True
            result['cache_type'] = 'llm_result'
            print(f"[INTENT] [LLM_CACHE] -> {result['intent']}")
            return result
        
        print(f"[INTENT] Classifying: '{query[:50]}...'")
        
        # Check if LLM is available
        if self.llm is None:
            print("[INTENT] [WARN] No LLM available, using fallback")
            return self._fallback_classify(query, user_profile)
        
        # Format conversation history
        context_str = "None"
        if conversation_history and len(conversation_history) > 0:
            # Database returns: [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
            # Format into readable context
            recent_messages = conversation_history[-4:]  # Last 4 messages (2 turns)
            context_lines = []
            for msg in recent_messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:150]  # Truncate long messages
                if role == 'user':
                    context_lines.append(f"User: {content}")
                elif role == 'assistant':
                    context_lines.append(f"Bot: {content}")
            
            if context_lines:
                context_str = "\n".join(context_lines)
        
        # Build prompt (birth data always available per user requirement)
        prompt = self.CLASSIFICATION_PROMPT.format(query=query, context=context_str)
        
        try:
            # Call LLM
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            result = self._parse_llm_response(response_text)
            
            # Validate intent
            if result['intent'] not in self.CATEGORIES:
                print(f"[INTENT] [WARN] Invalid category '{result['intent']}', defaulting to RAG_WITH_CALCULATION")
                result['intent'] = 'RAG_WITH_CALCULATION'
            
            result['cached'] = False
            
            # Cache result
            if self.use_cache:
                self.cache[cache_key] = {k: v for k, v in result.items() if k != 'cached'}
            
            print(f"[INTENT] [LLM] -> {result['intent']} (confidence: {result['confidence']:.2f})")
            return result
            
        except Exception as e:
            print(f"[INTENT] [ERROR] LLM classification failed: {e}")
            return self._fallback_classify(query, user_profile)
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured result."""
        try:
            # Try to extract JSON from response
            # Handle cases where LLM adds extra text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                
                return {
                    'intent': result.get('intent', 'RAG_WITH_CALCULATION').upper(),
                    'confidence': float(result.get('confidence', 0.8)),
                    'reasoning': result.get('reasoning', 'LLM classification')
                }
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[INTENT] [WARN] Failed to parse JSON: {e}")
        
        # If JSON parsing fails, try to extract intent from text
        response_upper = response_text.upper()
        for category in self.CATEGORIES:
            if category in response_upper:
                return {
                    'intent': category,
                    'confidence': 0.7,
                    'reasoning': 'Extracted from LLM text response'
                }
        
        # Default fallback
        return {
            'intent': 'RAG_WITH_CALCULATION',
            'confidence': 0.5,
            'reasoning': 'Could not parse LLM response'
        }
    
    def _fallback_classify(self, query: str, user_profile: Optional[Dict] = None) -> Dict:
        """
        Pattern-based fallback classification.
        Used when LLM is unavailable or fails.
        """
        q = query.lower().strip()
        
        # CHITCHAT patterns
        chitchat_patterns = [
            'hi', 'hello', 'hey', 'namaste', 'good morning', 'good evening',
            'who are you', 'what are you', 'your name',
            'thanks', 'thank you', 'bye', 'goodbye'
        ]
        if any(pattern in q for pattern in chitchat_patterns):
            return {
                'intent': 'CHITCHAT',
                'confidence': 0.85,
                'reasoning': 'Fallback: conversational pattern detected',
                'cached': False
            }
        
        # CALCULATION_ONLY patterns
        calc_triggers = ['show', 'display', 'give me', 'what is my', 'what are my']
        calc_targets = ['chart', 'kundali', 'lagna', 'rashi', 'nakshatra', 'dasha', 'transit', 'position']
        has_trigger = any(trigger in q for trigger in calc_triggers)
        has_target = any(target in q for target in calc_targets)
        no_interpretation = not any(word in q for word in ['mean', 'effect', 'impact', 'when will', 'future', 'predict'])
        
        if has_trigger and has_target and no_interpretation:
            return {
                'intent': 'CALCULATION_ONLY',
                'confidence': 0.80,
                'reasoning': 'Fallback: raw data request pattern',
                'cached': False
            }
        
        # RAG_ONLY patterns (general theory, no "my")
        theory_patterns = ['what does', 'what is the meaning', 'explain', 'define', 'tell me about']
        general_targets = ['house', 'planet in', 'aspect', 'yoga', 'nakshatra', 'sign']
        is_theory = any(pattern in q for pattern in theory_patterns)
        is_general = any(target in q for target in general_targets)
        is_not_personal = 'my' not in q and 'i ' not in q and 'me' not in q
        
        if is_theory and is_general and is_not_personal:
            return {
                'intent': 'RAG_ONLY',
                'confidence': 0.75,
                'reasoning': 'Fallback: general theory pattern',
                'cached': False
            }
        
        # Default: RAG_WITH_CALCULATION (most common for personal questions)
        return {
            'intent': 'RAG_WITH_CALCULATION',
            'confidence': 0.70,
            'reasoning': 'Fallback: default to personalized prediction',
            'cached': False
        }
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self.cache),
            "cache_enabled": self.use_cache,
            "categories": self.CATEGORIES,
            "llm_connected": self.llm is not None
        }


# Aliases for backward compatibility
IntentClassifier = LLMIntentClassifier
SimplifiedIntentClassifier = LLMIntentClassifier
EnhancedIntentClassifier = LLMIntentClassifier


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Intent Classifier - Test (Fallback Mode)")
    print("=" * 60)
    print()
    
    classifier = LLMIntentClassifier()
    
    test_cases = [
        ("hi", "CHITCHAT"),
        ("show my birth chart", "CALCULATION_ONLY"),
        ("what are my current dashas", "CALCULATION_ONLY"),
        ("when will I get married", "RAG_WITH_CALCULATION"),
        ("how is my career going", "RAG_WITH_CALCULATION"),
        ("what does Mars in 7th house mean", "RAG_ONLY"),
        ("explain the 10th house", "RAG_ONLY"),
    ]
    
    print("Testing fallback classification:")
    print("-" * 40)
    
    for query, expected in test_cases:
        result = classifier.classify(query, {})
        actual = result['intent']
        status = "[OK]" if actual == expected else "[FAIL]"
        print(f"{status} '{query}'")
        print(f"   Expected: {expected}, Got: {actual}")
        print()
    
    print("=" * 60)
    print("[DONE] Fallback tests complete!")
    print("Note: Full LLM classification requires LLM instance.")
    print("=" * 60)