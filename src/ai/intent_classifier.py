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
        "meri rashi kya hai": "CALCULATION_ONLY",
        "mera lagna kya hai": "CALCULATION_ONLY",
        "what is my rashi": "CALCULATION_ONLY",
        "meri kundali dikhao": "CALCULATION_ONLY",
        
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
        
        # Foreign Travel / Videsh Yatra (High confidence mappings)
        "main foreign jaunga": "RAG_WITH_CALCULATION",
        "videsh yatra": "RAG_WITH_CALCULATION",
        "kab jaunga videsh": "RAG_WITH_CALCULATION",
        "foreign yatra": "RAG_WITH_CALCULATION",
        "abroad travel": "RAG_WITH_CALCULATION",
        "when will i go abroad": "RAG_WITH_CALCULATION",
    }

    
    CLASSIFICATION_PROMPT = """You are an intent classifier for a Vedic astrology chatbot. Classify the query into EXACTLY ONE of four categories.

The user ALWAYS has birth details on file. The query may be in English, Hindi, Hinglish, or any mix.

---

## CATEGORY DEFINITIONS

**CALCULATION_ONLY**
The user wants a raw astrological fact directly derivable from their birth chart — no interpretation, no prediction, no advice.
Key signal: Asks "what is my X" or "show me my X" where X is a chart element (sign, ascendant, lagna, dasha, rashi, nakshatra, planetary position, kundali).
Also: "when is my [planet] dasha/mahadasha/antardasha?" → this is a date lookup from the dasha timeline, NOT a prediction.
Examples: "what is my sun sign", "what is my lagna", "what is my ascendant", "when is my jupiter dasha", "show my kundali", "what are my current dashas", "meri rashi kya hai", "mera lagna kya hai"
NOTE: If the user is asking for a date or period (like "when is my X dasha"), that is CALCULATION_ONLY — not RAG_WITH_CALCULATION.

**RAG_WITH_CALCULATION**
The user wants a PREDICTION, INTERPRETATION, or ADVICE about their life situation based on their chart.
Key signal: Asks about future events, outcomes, life areas (marriage, career, health, children, travel), OR asks what a placement MEANS/EFFECTS for them.
Examples: "when will I get married", "how is my career", "will I get a promotion", "what does my Jupiter placement mean for me", "impact of Saturn on my 10th house", "will I go abroad"

**RAG_ONLY**
The user wants a general explanation of an astrological concept — NOT about their own chart.
Key signal: No personal pronouns like "my", "me", "I" — asks to "explain", "define", or "what does X mean in general".
Examples: "what is a raj yoga", "explain the 10th house", "what does mars in 7th house mean", "define mahadasha"

**CHITCHAT**
Greetings, thanks, conversational filler, or identity questions.
Examples: "hi", "hello", "thanks", "who are you", "good morning"

**AMBIGUOUS**
Only use when the query is a BARE term (single planet or house number) with NO indication of whether the user wants theory or their personal chart.
Examples: "Jupiter", "7th house" (alone, no context)

---

USER QUERY: "{query}"

CONVERSATION CONTEXT (last few messages):
{context}

## DECISION RULES
1. If the query asks "what is my [sign/lagna/rashi/ascendant/nakshatra]" → CALCULATION_ONLY (it is a fact lookup, not a prediction).
2. If the query asks "when is/will my [planet] dasha/mahadasha" → CALCULATION_ONLY (dasha dates are computed, not interpreted).
3. If the query asks about future life events or what something MEANS FOR the user → RAG_WITH_CALCULATION.
4. If there is no "my" / "me" / "I" and the user is asking for explanation → RAG_ONLY.
5. AMBIGUOUS only for bare single-word astrological terms with no context.

Respond with ONLY a valid JSON object — no extra text:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "reasoning": "One sentence explanation of why."}}

"""

    def __init__(self, llm=None, use_cache: bool = True, embeddings=None):
        """
        Initialize LLM-based classifier.
        
        Args:
            llm: LangChain LLM instance (will be set by orchestrator if None)
            use_cache: Whether to cache classification results
            embeddings: LangChain Embeddings instance for Semantic Routing
        """
        self.llm = llm
        self.use_cache = use_cache
        self.cache = {}
        self.embeddings = embeddings
        
        # Level 2: Semantic Reference Dataset
        self.SEMANTIC_REFERENCE = {
            "CALCULATION_ONLY": [
                "show me my birth chart",
                "what is my lagna",
                "mera lagna kya hai",
                "meri rashi kya hai",
                "what is my moon sign",
                "display my d9 chart",
                "what are my current dashas",
                "give me my planetary positions",
                "show my kundali",
                "what is my ascendant",
                "current dasha period",
                "show my navamsha chart",
                "what is my sun sign",
                "mera janam kundli dikhao"
            ],
            "RAG_WITH_CALCULATION": [
                "when will i get married",
                "how is my career looking in 2025",
                "will i get a job soon",
                "mere liye kaisi job sahi rahegi",
                "when will i buy a house",
                "is this a good time for me",
                "what does my jupiter placement mean for me",
                "how is my health",
                "meri kismat kaisi hai",
                "predict my future",
                "when will i travel abroad",
                "how will my marriage be",
                "what is the impact of saturn in my chart",
                "mere career ka kya hoga",
                "foreign travel in my chart",
                "overseas opportunities",
                "main foreign jaunga",
                "videsh yatra kab hogi",
                "foreign settle kab hounga"

            ],
            "RAG_ONLY": [
                "what is a raj yoga",
                "explain the 10th house in general",
                "what does saturn return mean",
                "what are the qualities of a scorpio moon",
                "what is vimshottari dasha",
                "define mahadasha",
                "what are kendra houses",
                "what does mars in 7th house mean",
                "explain mangalik dosha",
                "what is the significance of rahu",
                "what are panapara houses",
                "how are divisional charts used"
            ],
            "CHITCHAT": [
                "hi",
                "hello",
                "good morning",
                "thanks",
                "thank you",
                "bye",
                "namaste",
                "who are you",
                "good evening",
                "who are you?",
                "mera naam kya hai?",
            ]
        }
        
        # Pre-computed vectors built lazily
        self._reference_vectors = None
        self._reference_labels = None
        
        print("[INTENT] 3-Level Intent Classifier initialized")
        print(f"[INTENT] Categories: {', '.join(self.CATEGORIES)}")
        
        if self.embeddings:
            self._initialize_embeddings()

    def _initialize_embeddings(self):
        """Pre-compute embeddings for semantic reference dataset."""
        import numpy as np
        
        print("[INTENT] Pre-computing semantic intent vectors...")
        try:
            all_queries = []
            labels = []
            
            for intent, queries in self.SEMANTIC_REFERENCE.items():
                for q in queries:
                    all_queries.append(q)
                    labels.append(intent)
                    
            vectors = self.embeddings.embed_documents(all_queries)
            
            # Convert to numpy arrays and normalize for fast cosine similarity via dot product
            self._reference_vectors = np.array(vectors)
            norms = np.linalg.norm(self._reference_vectors, axis=1, keepdims=True)
            self._reference_vectors = self._reference_vectors / norms
            self._reference_labels = labels
            
            print(f"[INTENT] Built semantic vector space with {len(all_queries)} reference points.")
        except Exception as e:
            print(f"[INTENT] [ERROR] Failed to initialize semantic vectors: {e}")
    
    def set_llm(self, llm):
        """Set the LLM instance (called by orchestrator during initialization)."""
        self.llm = llm
        print("[INTENT] LLM connected to classifier")
    
    def _is_nonsensical(self, query: str) -> bool:
        """
        Check if a query is nonsensical or random noise.
        
        Returns:
            True if input appears to be random characters or too short.
        """
        q = query.strip()
        if not q or len(q) < 2:
            return True
        
        # Check for strings with no vowels (often random typing)
        # Excludes very short common words if any
        if len(q) > 4 and not any(v in q.lower() for v in 'aeiouy'):
            # Allow some common Hindi/Sanskrit transliterations like 'krish'
            common_vowelless = ['krish', 'hmm', 'hmmm', 'kk']
            if not any(cv in q.lower() for cv in common_vowelless):
                return True
                
        return False

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
                    'according to', 'classical', 'traditional', 'meaning'
                ]
                if any(marker in query_lower for marker in theory_markers):
                    return False  # Not ambiguous, user wants theory
                
                # Personalization markers (user wants their chart)
                personal_markers = [
                    'for me', 'my', 'mine', 'in my chart', 'in my life',
                    'will i', 'am i', 'do i', 'should i', 'when will i',
                    'main', 'mera', 'meri', 'mere', 'mujhe', 'jaunga', 'kab'
                ]

                if any(marker in query_lower for marker in personal_markers):
                    return False  # Not ambiguous, user wants personalization
                
                # No clear markers -> AMBIGUOUS!
                return True
        
        return False
    
    # -----------------------------------------------------------------------
    # Level 1.5: Keyword Pre-Router (fires BEFORE semantic & LLM)
    # Handles chart-lookup patterns deterministically — no probability needed.
    # -----------------------------------------------------------------------
    _CALC_ONLY_TRIGGERS = [
        # English: "what is my <X>" where X is a chart element
        r'\bwhat is my (sun sign|moon sign|lagna|ascendant|rashi|nakshatra|rising sign|birth chart|kundali|kundli|d1|d9|navamsha|atma karaka|amatyakaraka|darakaraka|arudha|chart|planetary position|planets)\b',
        r'\bwhat\'s my (sun sign|moon sign|lagna|ascendant|rashi|nakshatra|rising sign|birth chart|kundali|kundli|d1|d9|navamsha|chart|planetary position|planets)\b',
        # "when is/will my <planet> (maha)?dasha / antardasha"
        r'\bwhen (is|will be) my .*(dasha|mahadasha|antardasha|bhukti)\b',
        # "show/display/give me my chart/kundali/dashas"
        r'\b(show|display|give me|dikhao|batao) my (chart|kundali|kundli|dashas|birth chart|navamsha|d9)\b',
        # Hindi transliteration
        r'\b(mera|meri|mere) (lagna|rashi|nakshatra|kundali|kundli|janam kundali|sun sign|moon sign|ascendant) (kya hai|dikhao|batao|hai)\b',
        r'\b(mera|meri) lagna kya hai\b',
        r'\b(mera|meri) rashi kya hai\b',
        r'\bmeri? kundali? (dikhao|batao)\b',
        r'\bcurrent dasha\b',
        r'\bwhat are my (current )?dashas\b',
        r'\bmy dasha (period|timeline|sequence)\b',
    ]

    def _keyword_pre_route(self, query: str) -> Optional[Dict]:
        """
        Level 1.5: Deterministic keyword pre-router for CALCULATION_ONLY.
        Catches clear chart-lookup queries before spending an LLM call.
        Returns a result dict if matched, None otherwise.
        """
        q_lower = query.lower()
        for pattern in self._CALC_ONLY_TRIGGERS:
            if re.search(pattern, q_lower):
                print(f"[INTENT] [KEYWORD_PRE_ROUTER] -> CALCULATION_ONLY (pattern match)")
                return {
                    'intent': 'CALCULATION_ONLY',
                    'confidence': 0.97,
                    'reasoning': 'Keyword pre-router: deterministic chart-lookup pattern',
                    'cached': False,
                    'cache_type': 'keyword'
                }
        return None

    def _semantic_route(self, query: str, threshold: float = 0.85) -> Optional[Dict]:
        """
        Level 2 Semantic Routing.
        Compares query embedding to reference vectors using cosine similarity.
        """
        if not self.embeddings or self._reference_vectors is None or self._reference_labels is None:
            return None
            
        import numpy as np
        
        try:
            # Embed the user query
            query_vector = self.embeddings.embed_query(query)
            query_array = np.array(query_vector).reshape(1, -1)
            
            # Normalize
            q_norm = np.linalg.norm(query_array)
            if q_norm == 0:
                return None
            query_array = query_array / q_norm
            
            # Calculate cosine similarity (dot product of normalized vectors)
            similarities = np.dot(self._reference_vectors, query_array.T).flatten()
            
            # Find the best match
            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]
            best_label = self._reference_labels[best_idx]
            
            # print(f"[INTENT] [DEBUG] Semantic best match: '{self.SEMANTIC_REFERENCE[best_label][best_idx]}' score={best_score:.3f}")
            
            # Return result if above confidence threshold
            if best_score >= threshold:
                result = {
                    'intent': best_label,
                    'confidence': float(best_score),
                    'reasoning': f'Semantic match (score {best_score:.2f})',
                    'cached': False,
                    'cache_type': 'semantic'
                }
                print(f"[INTENT] [SEMANTIC_ROUTER] -> {best_label} (score: {best_score:.3f})")
                return result
                
        except Exception as e:
            print(f"[INTENT] [ERROR] Semantic routing failed: {e}")
            
        return None

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
        
        q = query.lower().strip().rstrip('?!.')
        
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
        
        # Step 1.5: Keyword Pre-Router (CALCULATION_ONLY fast-path)
        keyword_result = self._keyword_pre_route(query)
        if keyword_result:
            return keyword_result

        # Step 2: Semantic Routing (Level 2)
        semantic_result = self._semantic_route(query)
        if semantic_result:
            return semantic_result
            
        # Step 3: Check LLM result cache
        cache_key = q
        if self.use_cache and cache_key in self.cache:
            result = self.cache[cache_key].copy()
            result['cached'] = True
            result['cache_type'] = 'llm_result'
            print(f"[INTENT] [LLM_CACHE] -> {result['intent']}")
            return result
        
        print(f"[INTENT] [LLM_CLASSIFIER] Classifying: '{query[:50]}...'")
        
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
        calc_triggers = ['show', 'display', 'give me', 'what is my', 'what are my', 'kya hai', 'batao', 'dikhao', 'mera', 'meri']
        calc_targets = ['chart', 'kundali', 'lagna', 'rashi', 'nakshatra', 'dasha', 'transit', 'position', 'janm kundali']
        has_trigger = any(trigger in q for trigger in calc_triggers)
        has_target = any(target in q for target in calc_targets)
        no_interpretation = not any(word in q for word in ['mean', 'effect', 'impact', 'when will', 'future', 'predict', 'kaisi', 'kaisa', 'kab'])
        
        # Specific exact matches
        is_exact_match = q in ['meri rashi kya hai', 'mera lagna kya hai', 'meri kundali dikhao', 'what is my rashi']

        if (has_trigger and has_target and no_interpretation) or is_exact_match:
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