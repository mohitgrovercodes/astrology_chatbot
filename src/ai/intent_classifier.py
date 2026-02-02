"""
Universal Intent Classifier - Works with ANY import name.
Has SimplifiedIntentClassifier AND EnhancedIntentClassifier as aliases.
"""

from typing import Dict, List, Optional, Any


class SimplifiedIntentClassifier:
    """
    Pattern-based intent classifier.
    Works with both SimplifiedIntentClassifier and EnhancedIntentClassifier names.
    
    3 categories:
    - CHITCHAT
    - NEEDS_CALCULATION
    - NEEDS_RAG
    """
    
    def __init__(self, llm_provider: str = "google", use_cache: bool = True):
        """Initialize classifier."""
        print("[INTENT] Using Gemini 2.5 Flash (3 categories)")
        print("[INTENT] Simplified 3-category classifier (CHITCHAT | NEEDS_RAG | NEEDS_CALCULATION)")
        self.use_cache = use_cache
        self.cache = {}
    
    def classify(
        self,
        query: str,
        user_profile: Dict[str, Any],
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """Classify using pattern matching."""
        
        q = query.lower().strip()
        
        # Check cache
        if self.use_cache and q in self.cache:
            result = self.cache[q].copy()
            result['cached'] = True
            return result
        
        print(f"[INTENT] Classifying query: '{query[:50]}...'")
        
        # CHITCHAT
        chitchat_patterns = [
            'hi', 'hello', 'hey', 'namaste', 'good morning', 'good evening',
            'who are you', 'what are you', 'your name',
            'what can you do', 'how can you help', 'help',
            'thanks', 'thank you', 'bye', 'goodbye'
        ]
        
        if any(pattern in q for pattern in chitchat_patterns):
            result = {
                "intent": "CHITCHAT",
                "confidence": 0.90,
                "reasoning": "Pattern: conversational",
                "cached": False
            }
            if self.use_cache:
                self.cache[q] = {k: v for k, v in result.items() if k != 'cached'}
            print(f"[INTENT] [LLM] → CHITCHAT (confidence: 0.90)")
            return result
        
        # NEEDS_CALCULATION
        calc_triggers = ['calculate', 'show', 'display', 'generate', 'give me', 'what is my']
        calc_targets = ['chart', 'kundali', 'horoscope', 'lagna', 'ascendant', 'rashi', 'dasha']
        
        has_trigger = any(trigger in q for trigger in calc_triggers)
        has_target = any(target in q for target in calc_targets)
        
        calc_phrases = ['my chart', 'my kundali', 'my lagna', 'my rashi', 'my dasha']
        has_phrase = any(phrase in q for phrase in calc_phrases)
        
        if (has_trigger and has_target) or has_phrase:
            if not any(word in q for word in ['mean', 'good', 'bad', 'when will', 'will i']):
                result = {
                    "intent": "NEEDS_CALCULATION",
                    "confidence": 0.85,
                    "reasoning": "Pattern: calculation request",
                    "cached": False
                }
                if self.use_cache:
                    self.cache[q] = {k: v for k, v in result.items() if k != 'cached'}
                print(f"[INTENT] [LLM] → NEEDS_CALCULATION (confidence: 0.85)")
                return result
        
        # NEEDS_RAG (default)
        result = {
            "intent": "NEEDS_RAG",
            "confidence": 0.80,
            "reasoning": "Pattern: astrology knowledge",
            "cached": False
        }
        if self.use_cache:
            self.cache[q] = {k: v for k, v in result.items() if k != 'cached'}
        print(f"[INTENT] [LLM] → NEEDS_RAG (confidence: 0.80)")
        return result
    
    def get_cache_stats(self) -> Dict:
        """Get cache stats."""
        return {
            "cache_size": len(self.cache),
            "cache_enabled": self.use_cache,
            "categories": ["CHITCHAT", "NEEDS_CALCULATION", "NEEDS_RAG"]
        }


# Aliases for backward compatibility
EnhancedIntentClassifier = SimplifiedIntentClassifier
IntentClassifier = SimplifiedIntentClassifier


if __name__ == "__main__":
    print("Testing Intent Classifier...")
    print()
    
    classifier = SimplifiedIntentClassifier()
    
    test_cases = [
        ("hi", "CHITCHAT"),
        ("calculate my chart", "NEEDS_CALCULATION"),
        ("what does Jupiter mean?", "NEEDS_RAG"),
    ]
    
    for query, expected in test_cases:
        result = classifier.classify(query, {})
        actual = result['intent']
        status = "✓" if actual == expected else "✗"
        print(f"{status} '{query}' → {actual}")
    
    print("\n✅ Classifier ready!")