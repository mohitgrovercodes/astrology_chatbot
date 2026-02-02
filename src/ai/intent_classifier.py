"""
LLM-Based Intent Classifier for NakshatraAI.

Uses Gemini/GPT to accurately classify user queries into four categories:
- CHITCHAT: Greetings and conversational queries
- CALCULATION_ONLY: Raw chart data requests (no interpretation)
- RAG_WITH_CALCULATION: Personal predictions (chart + knowledge + interpretation)
- RAG_ONLY: General astrology theory (no user chart needed)
"""

from typing import Dict, List, Optional, Any
import json
import os


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
        "RAG_ONLY"
    ]
    
    CLASSIFICATION_PROMPT = """You are an intent classifier for a Vedic astrology chatbot. The user ALWAYS has birth details available.

Classify the user's query into exactly ONE of these categories:

**CHITCHAT**: Greetings, casual conversation, or questions about the bot itself.
Examples: "Hi", "Hello", "Who are you?", "Thanks", "Bye"

**CALCULATION_ONLY**: User wants to SEE their raw birth chart data WITHOUT interpretation.
- They want numbers, positions, or chart details displayed
- NO prediction, NO explanation of meaning
Examples: "Show my birth chart", "What's my moon sign?", "Display my D1 chart", "What are my current dashas?", "Show my planetary positions"

**RAG_WITH_CALCULATION**: User wants a PERSONALIZED prediction or interpretation about THEIR life.
- Uses their birth chart for PERSONALIZED answers
- Requires calculation + knowledge + interpretation
Examples: "When will I get married?", "How is my career this year?", "What does Jupiter mean for ME?", "Is this a good time to start a business?", "Predict my health"

**RAG_ONLY**: User asks about GENERAL astrology theory, NOT specific to their chart.
- Educational/theoretical questions
- NO personalization needed
Examples: "What does Mars in 7th house generally mean?", "Explain the 10th house", "What is a Raj Yoga?", "Define Ketu", "What are the effects of Saturn return?"

---
IMPORTANT RULES:
1. If query contains "my" or "me" or "I" with a prediction -> RAG_WITH_CALCULATION
2. If query asks for chart/positions/dashas without interpretation -> CALCULATION_ONLY  
3. If query is theoretical/educational with no personal reference -> RAG_ONLY

USER QUERY: "{query}"

Respond with ONLY a JSON object:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "reasoning": "Brief explanation"}}
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
        q = query.lower().strip()
        
        # Check cache first (simplified - birth data always available)
        cache_key = q
        if self.use_cache and cache_key in self.cache:
            result = self.cache[cache_key].copy()
            result['cached'] = True
            print(f"[INTENT] [CACHED] -> {result['intent']}")
            return result
        
        print(f"[INTENT] Classifying: '{query[:50]}...'")
        
        # Check if LLM is available
        if self.llm is None:
            print("[INTENT] [WARN] No LLM available, using fallback")
            return self._fallback_classify(query, user_profile)
        
        # Build prompt (birth data always available per user requirement)
        prompt = self.CLASSIFICATION_PROMPT.format(query=query)
        
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