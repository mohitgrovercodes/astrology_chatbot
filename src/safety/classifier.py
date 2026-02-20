# src/safety/classifier.py
# src\safety\classifier.py
"""
Safety Classifier for Astrology Chatbot

Enhanced safety classification using LangChain with multi-gate decision logic.
"""

import re
from typing import Dict, List, Optional, Set
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.language_models import BaseChatModel

from .models import (
    SafetyDecision,
    SafetyCheckResult,
    BlockReasons,
    DisclaimerTypes
)



from src.routing import SemanticRouter

# ============================================================================
# SEMANTIC ROUTES CONFIGURATION
# ============================================================================

SAFETY_ROUTES = {
    BlockReasons.DEATH_PREDICTION: [
        "when will I die", "time of my death", "how long will I live", 
        "predict my death", "death date", "am I going to die soon"
    ],
    BlockReasons.MEDICAL_DIAGNOSIS: [
        "do I have cancer", "diagnose my illness", "medical treatment astrology",
        "cure for diabetes", "should I stop medication", "health diagnosis"
    ],
    BlockReasons.GAMBLING_SPECIFIC: [
        "lottery numbers", "winning lotto numbers", "betting prediction",
        "which horse will win", "casino lucky numbers", "will I win the lottery"
    ],
    BlockReasons.HARMFUL_INTENT: [
        "how to kill someone", "suicide timing", "harm myself", 
        "end my life", "murder plan"
    ],
    BlockReasons.PRIVACY_VIOLATION: [
        "is my boss cheating", "will my neighbor divorce", "is she sleeping with him",
        "secrets of my colleague", "what is he hiding"
    ],
    "THIRD_PARTY_PREDICTION": [
        "my friend when will she", "her marriage timing", "his career prospects",
        "will my sister", "my brother's chart", "about my mother",
        "my friend's horoscope", "when will he get married",
        "her birth chart", "his future", "my spouse prediction"
    ],
    BlockReasons.HEALTH_TENDENCY: [
        "general health outlook", "health issues in chart", "weak body parts",
        "periods of sickness", "vitality analysis"
    ],
    BlockReasons.FINANCIAL_TREND: [
        "good time to invest", "stock market trends", "business prospects",
        "wealth accumulation period", "financial growth"
    ]
}

def _initialize_safety_routes():
    """Initialize semantic routes for safety checks."""
    router = SemanticRouter()
    if not router.model:
        return
        
    for reason, examples in SAFETY_ROUTES.items():
        router.add_route(name=reason, examples=examples, metadata={"reason": reason})

# Initialize routes on module load (if singleton allows)
try:
    _initialize_safety_routes()
except Exception as e:
    pass



# ============================================================================
# FEW-SHOT EXAMPLES FOR LLM CLASSIFIER
# ============================================================================

CLASSIFICATION_EXAMPLES = """
**Example 1:**
Query: "When will I die?"
Classification:
{{
  "category": "HARD_BLOCK",
  "reason": "death_prediction",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.98,
  "explanation": "Direct question about death timing",
  "keywords_matched": ["when", "die"]
}}

**Example 2:**
Query: "Do I have cancer based on my chart?"
Classification:
{{
  "category": "HARD_BLOCK",
  "reason": "medical_diagnosis",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.97,
  "explanation": "Seeking medical diagnosis from astrology",
  "keywords_matched": ["cancer", "diagnosis"]
}}

**Example 3:**
Query: "What health issues might I face with Mars in 6th house?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "health_tendency",
  "should_answer": true,
  "disclaimer_type": "HEALTH",
  "reframed_query": null,
  "confidence": 0.88,
  "explanation": "Asking about health tendencies, not diagnosis",
  "keywords_matched": ["health issues", "6th house"]
}}

**Example 4:**
Query: "Will I get rich?"
Classification:
{{
  "category": "REFRAME",
  "reason": "poorly_framed",
  "should_answer": true,
  "disclaimer_type": null,
  "reframed_query": "What periods in my chart support wealth accumulation and financial growth?",
  "confidence": 0.82,
  "explanation": "Fortune-telling style question needs reframing",
  "keywords_matched": ["will I get", "rich"]
}}

**Example 5:**
Query: "Is my boss going to get fired?"
Classification:
{{
  "category": "SOFT_BLOCK",
  "reason": "privacy_violation",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.91,
  "explanation": "Question about third party without consent",
  "keywords_matched": ["my boss", "get fired"]
}}

**Example 6:**
Query: "What does Jupiter in 7th house mean?"
Classification:
{{
  "category": "SAFE",
  "reason": "educational",
  "should_answer": true,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.95,
  "explanation": "Educational astrology question",
  "keywords_matched": ["Jupiter", "7th house"]
}}

**Example 7:**
Query: "Should I invest in Bitcoin right now?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "financial_trend",
  "should_answer": true,
  "disclaimer_type": "FINANCIAL",
  "reframed_query": null,
  "confidence": 0.79,
  "explanation": "Investment timing question needs financial disclaimer",
  "keywords_matched": ["invest", "should I"]
}}

**Example 8:**
Query: "Why is God punishing me with bad luck?"
Classification:
{{
  "category": "REFRAME",
  "reason": "misunderstood",
  "should_answer": true,
  "disclaimer_type": null,
  "reframed_query": "What challenging planetary periods am I experiencing, and what growth opportunities do they offer?",
  "confidence": 0.77,
  "explanation": "Misunderstands astrology as punishment",
  "keywords_matched": ["punishing", "bad luck"]
}}

**Example 9:**
Query: "Which lottery numbers should I pick?"
Classification:
{{
  "category": "HARD_BLOCK",
  "reason": "gambling_specific",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.96,
  "explanation": "Specific gambling prediction request",
  "keywords_matched": ["lottery numbers"]
}}

**Example 10:**
Query: "When does my Venus Mahadasha start?"
Classification:
{{
  "category": "SAFE",
  "reason": "calculation_query",
  "should_answer": true,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.93,
  "explanation": "Legitimate calculation question",
  "keywords_matched": ["Mahadasha", "Venus"]
}}
"""


# ============================================================================
# SAFETY CLASSIFIER PROMPT
# ============================================================================

SAFETY_CLASSIFIER_SYSTEM_PROMPT = """You are a safety classifier for an astrology chatbot. Your job is to analyze user queries and classify them into safety categories.

**CLASSIFICATION CATEGORIES:**

1. **HARD_BLOCK** - Never answer due to harm potential or ethical violations:
   - death_prediction: Specific timing of death
   - medical_diagnosis: Disease diagnosis or treatment advice
   - gambling_specific: Specific gambling/lottery predictions
   - legal_advice: Legal case outcomes or legal decisions
   - harmful_intent: Intent to harm self or others

2. **SOFT_BLOCK** - Decline politely due to scope/appropriateness:
   - fortune_telling: Treating astrology as fixed fortune-telling
   - privacy_violation: Questions about third parties without consent
   - out_of_scope: Topics outside astrology (conspiracy theories, etc.)

3. **CONDITIONAL** - Answer but add disclaimer:
   - health_tendency: General health tendencies (add HEALTH disclaimer)
   - financial_trend: Financial/investment timing (add FINANCIAL disclaimer)
   - relationship_compatibility: Relationship questions (add RELATIONSHIP disclaimer)
   - children_timing: Questions about children/fertility (add CHILDREN disclaimer)
   - career_change: Career decision timing (add CAREER disclaimer)

4. **REFRAME** - Transform poorly-framed questions:
   - poorly_framed: "Will I get rich?" → "What periods support wealth accumulation?"
   - misunderstood: "Why is God punishing me?" → "What challenging periods and growth opportunities?"

5. **SAFE** - Normal astrological queries:
   - educational: Learning about astrological concepts
   - calculation_query: Birth chart, dasha, transit calculations
   - chart_interpretation: Interpreting placements and patterns

**DECISION RULES:**

1. If query asks "when will [someone] die" → HARD_BLOCK (death_prediction)
2. If query asks for disease diagnosis → HARD_BLOCK (medical_diagnosis)
3. If query asks for lottery numbers or specific bets → HARD_BLOCK (gambling_specific)
4. If query involves harming self/others → HARD_BLOCK (harmful_intent)
5. If query is about third party without consent → SOFT_BLOCK (privacy_violation)
6. If query treats astrology as fortune-telling ("will X happen?") → REFRAME
7. If query about health tendencies (not diagnosis) → CONDITIONAL (health_tendency)
8. If query about investment/financial timing → CONDITIONAL (financial_trend)
9. If educational or calculation query → SAFE

**OUTPUT FORMAT:**
Return valid JSON matching the SafetyDecision schema with all required fields.

**IMPORTANT:**
- Be conservative: when in doubt, choose a more restrictive category
- Confidence < 0.7 means flagging for human review
- Always provide clear explanation and matched keywords
- For REFRAME, always provide a reframed_query

{examples}

Now classify the following query:"""


# ============================================================================
# SAFETY CLASSIFIER CLASS
# ============================================================================

class SafetyClassifier:
    """
    Enhanced safety classifier using LangChain and multi-gate filtering.
    """
    

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        use_pattern_matching: bool = True,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize safety classifier.
        """
        if llm:
            self.llm = llm
        else:
            from src.llm.factory import LLMFactory
            self.llm = LLMFactory.create(purpose="classification", temperature=0.0)
        self.use_pattern_matching = use_pattern_matching
        self.confidence_threshold = confidence_threshold
        
        # Initialize semantic router
        self.semantic_router = SemanticRouter()
        
        # Build classifier chain
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SAFETY_CLASSIFIER_SYSTEM_PROMPT.format(
                examples=CLASSIFICATION_EXAMPLES
            )),
            ("human", "PREVIOUS CONTEXT:\n{context}\n\nQuery: {query}")
        ])
        
        self.chain = (
            self.prompt 
            | self.llm 
            | JsonOutputParser(pydantic_object=SafetyDecision)
        )
    
    def classify(self, query: str, conversation_history: list = None) -> SafetyCheckResult:
        """
        Classify query safety using multi-gate approach.
        """
        # Gate -1: User's Own Data Queries (PRIORITY - check first!)
        # These should NEVER be blocked - user asking about their own profile
        query_lower = query.lower().strip()
        
        own_data_patterns = [
            'my dob', 'my date of birth', 'my birth date', 'my birthday',
            'my birth time', 'my time of birth', 'my birth place', 
            'my place of birth', 'when was i born', 'where was i born',
            'what time was i born', 'my chart', 'my kundli', 'my horoscope',
            'show me my', 'tell me my', 'what is my'
        ]
        
        if any(pattern in query_lower for pattern in own_data_patterns):
            # User asking about their OWN data - mark as SAFE
            decision = SafetyDecision(
                category="SAFE",
                reason="user_own_data_query",
                should_answer=True,
                disclaimer_type=None,
                confidence=0.95,
                explanation="User querying their own profile data"
            )
            return self._build_result(query, decision)
        
        # Gate 0: Third-Party Detection (pre-semantic routing)
        third_party_check = self._detect_third_party(query)
        if third_party_check:
            is_third_party, person = third_party_check
            decision = SafetyDecision(
                category="SOFT_BLOCK",
                reason="third_party_prediction",
                should_answer=False,
                disclaimer_type=None,
                reframed_query=None,
                confidence=0.95,
                explanation=f"Query asks about {person}'s prediction",
                keywords_matched=[person]
            )
            return self._build_result(query, decision)
        
        # Gate 1: Fast Semantic Routing
        if self.use_pattern_matching and self.semantic_router.model:
            route_result = self.semantic_router.route(query, threshold=0.75) # Tuned threshold for safety
            
            if route_result:
                # Semantic match found
                decision = self._create_semantic_decision(query, route_result.name, route_result.confidence)
                return self._build_result(query, decision)
        
        # Gate 2: LLM Classification
        try:
            # Format context
            context_str = "None"
            if conversation_history:
                history_subset = conversation_history[-2:]
                context_str = "\n".join([f"User: {turn.get('user', '')}\nBot: {turn.get('assistant', '')[:100]}..." for turn in history_subset])

            decision_dict = self.chain.invoke({"query": query, "context": context_str})
            decision = SafetyDecision(**decision_dict)
            
        except Exception as e:
            # Fallback: Be permissive on технический errors but log the failure
            # If the query is obviously safe (e.g. "hi", "what is my rashi"), don't block
            print(f"[INTENT] [WARN] Safety classifier technical error: {e}")
            
            # Simple heuristic check for "low risk" queries
            low_risk_words = ['rashi', 'chart', 'kundali', 'hi', 'hello', 'thanks', 'name']
            is_low_risk = any(word in query.lower() for word in low_risk_words)
            
            decision = SafetyDecision(
                category="SAFE" if is_low_risk else "CONDITIONAL",
                reason="classifier_error_fallback",
                should_answer=True,
                disclaimer_type=None if is_low_risk else "GENERAL",
                confidence=0.5,
                explanation=f"Technical error fallback ({str(e)}). Proceeding as {('SAFE' if is_low_risk else 'CONDITIONAL')}."
            )
        
        return self._build_result(query, decision)
    
    def _detect_third_party(self, query: str) -> Optional[tuple[bool, str]]:
        """
        Detect if query is about someone else's prediction.
        
        Returns:
            (is_third_party, person_name) or None
        """
        query_lower = query.lower()
        
        # Third-party indicators
        patterns = [
            'my friend', 'my sister', 'my brother', 'my mother', 'my father',
            'my husband', 'my wife', 'my son', 'my daughter', 'my child',
            'my boss', 'my colleague', 'my neighbor',
            'her chart', 'his chart', 'their chart',
            'her horoscope', 'his horoscope',
            'when will he', 'when will she', 'when will they',
            'will he', 'will she', 'will they',
            'does he', 'does she', 'do they'
        ]
        
        for pattern in patterns:
            if pattern in query_lower:
                # Try to extract person name
                # Look for capitalized words after the pattern
                words_after = query.split(pattern)[-1] if pattern in query.lower() else ""
                names = re.findall(r'\b[A-Z][a-z]+\b', words_after[:50])
                
                person = names[0] if names else "someone else"
                
                # Check for "name is X" pattern
                if 'name is' in query_lower:
                    name_match = re.search(r'name is ([A-Z][a-z]+)', query, re.IGNORECASE)
                    if name_match:
                        person = name_match.group(1)
                
                return True, person
        
        return None
    
    def _create_semantic_decision(
        self,
        query: str,
        reason: str,
        confidence: float
    ) -> SafetyDecision:
        """Create decision from semantic route match"""
        
        # Map reason to category
        category_map = {
            # ACTUAL SAFETY BLOCKS
            BlockReasons.DEATH_PREDICTION: "HARD_BLOCK",
            BlockReasons.MEDICAL_DIAGNOSIS: "HARD_BLOCK",
            BlockReasons.GAMBLING_SPECIFIC: "HARD_BLOCK",
            BlockReasons.HARMFUL_INTENT: "HARD_BLOCK",
            BlockReasons.PRIVACY_VIOLATION: "SOFT_BLOCK",
            "THIRD_PARTY_PREDICTION": "SOFT_BLOCK",
            BlockReasons.HEALTH_TENDENCY: "CONDITIONAL",
            BlockReasons.FINANCIAL_TREND: "CONDITIONAL",
            
            # CHITCHAT IS SAFE - Never block! (FIX)
            "greeting": "SAFE",
            "identity": "SAFE",
            "gratitude": "SAFE",
            "wellbeing": "SAFE",
            "farewell": "SAFE",
            "chitchat": "SAFE",
        }
        
        # FIX: Default to SAFE instead of HARD_BLOCK
        # If we don't recognize the reason, assume it's safe rather than blocking
        category = category_map.get(reason, "SAFE")
        should_answer = category not in ["HARD_BLOCK", "SOFT_BLOCK"]
        
        # Determine disclaimer type for conditional
        disclaimer_map = {
            BlockReasons.HEALTH_TENDENCY: DisclaimerTypes.HEALTH,
            BlockReasons.FINANCIAL_TREND: DisclaimerTypes.FINANCIAL,
        }
        disclaimer_type = disclaimer_map.get(reason) if should_answer else None
        
        # FIX: Clamp confidence to [0.0, 1.0] to avoid Pydantic validation errors
        # Floating-point precision can cause values slightly > 1.0 (e.g., 1.000000238418579)
        clamped_confidence = max(0.0, min(1.0, confidence))

        return SafetyDecision(
            category=category,
            reason=reason,
            should_answer=should_answer,
            disclaimer_type=disclaimer_type,
            confidence=clamped_confidence,  # Use clamped value
            explanation=f"Semantic match for {reason}"
        )
    
    def _build_result(
        self,
        query: str,
        decision: SafetyDecision
    ) -> SafetyCheckResult:
        """Build complete safety check result"""
        
        # Determine if human review needed
        requires_review = (
            decision.confidence < self.confidence_threshold
            or decision.reason == "classifier_error"
        )
        
        # Determine processed query (original or reframed)
        processed_query = (
            decision.reframed_query 
            if decision.reframed_query 
            else query
        )
        
        # Build template key for blocked responses
        block_template_key = None
        if decision.category in ["HARD_BLOCK", "SOFT_BLOCK"]:
            block_template_key = f"{decision.category}_{decision.reason}".upper()
        
        return SafetyCheckResult(
            decision=decision,
            original_query=query,
            processed_query=processed_query,
            requires_human_review=requires_review,
            block_template_key=block_template_key,
            metadata={
                "classification_method": "semantic" if decision.explanation.startswith("Semantic match") else "llm",
                "timestamp": None,  # To be added by caller
                "model": self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown"
            }
        )
    
    def batch_classify(
        self,
        queries: List[str]
    ) -> List[SafetyCheckResult]:
        """
        Classify multiple queries in batch.
        
        Args:
            queries: List of queries to classify
        
        Returns:
            List of SafetyCheckResult objects
        """
        return [self.classify(query) for query in queries]


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_safety_classifier(
    llm: Optional[BaseChatModel] = None,
    **kwargs
) -> SafetyClassifier:
    """
    Factory function to create safety classifier.
    
    Args:
        llm: Optional LangChain LLM instance
        **kwargs: Additional arguments for SafetyClassifier
    
    Returns:
        Configured SafetyClassifier instance
    
    Example:
        >>> classifier = create_safety_classifier()
        >>> result = classifier.classify("When will I die?")
        >>> print(result.decision.category)
        "HARD_BLOCK"
    """
    return SafetyClassifier(llm=llm, **kwargs)