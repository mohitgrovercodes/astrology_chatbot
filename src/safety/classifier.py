"""
Safety Classifier for Astrology Chatbot

Enhanced safety classification using LangChain with multi-gate decision logic.
"""

import re
from typing import Dict, List, Optional, Set
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from .models import (
    SafetyDecision,
    SafetyCheckResult,
    BlockReasons,
    DisclaimerTypes
)


# ============================================================================
# KEYWORD PATTERNS (Fast Pre-filtering)
# ============================================================================

# Pattern matching for quick detection before LLM call
KEYWORD_PATTERNS = {
    # Hard Blocks
    BlockReasons.DEATH_PREDICTION: {
        "patterns": [
            r"\b(when|will|am I going to|time of)\s+(I|we|he|she|they|my|his|her)\s+(die|death|pass away|dying)",
            r"\bhow long\s+(will|to)\s+(I|we|he|she|they)\s+live",
            r"\b(predict|tell me|know)\s+(when|time of)\s+(death|die|dying)",
            r"\b(my|his|her|their)\s+(death|dying)\s+(date|time|when)",
        ],
        "keywords": ["die", "death", "pass away", "when will I die", "time of death"]
    },
    
    BlockReasons.MEDICAL_DIAGNOSIS: {
        "patterns": [
            r"\bdo I have\s+(cancer|diabetes|disease|illness|tumor)",
            r"\b(diagnose|diagnosis|medical condition)\s+(based on|from|using)\s+(chart|astrology)",
            r"\b(should I|can I)\s+(stop|start|take)\s+(medication|medicine|treatment)",
            r"\b(cure|treat|fix)\s+(my|this)\s+(disease|illness|condition)\s+(with|using)\s+astrology",
        ],
        "keywords": ["diagnose", "cure disease", "stop medication", "do I have cancer"]
    },
    
    BlockReasons.GAMBLING_SPECIFIC: {
        "patterns": [
            r"\b(lottery|lotto)\s+(numbers|winning|win)",
            r"\b(which|what)\s+(horse|team|number)\s+(to|should I)\s+bet",
            r"\b(will I win|winning)\s+(the lottery|gambling|casino|bet)",
            r"\b(lucky numbers|lucky day)\s+(for|to)\s+(lottery|gambling|betting)",
        ],
        "keywords": ["lottery numbers", "which horse to bet", "will I win the lottery"]
    },
    
    BlockReasons.HARMFUL_INTENT: {
        "patterns": [
            r"\b(kill|murder|harm|hurt|suicide)\b",
            r"\b(end|take)\s+(my|his|her)\s+life",
            r"\b(good time|auspicious)\s+to\s+(harm|hurt|kill)",
        ],
        "keywords": ["kill", "suicide", "harm someone", "end my life"]
    },
    
    # Soft Blocks
    BlockReasons.PRIVACY_VIOLATION: {
        "patterns": [
            r"\b(my|his|her)\s+(boss|neighbor|colleague|coworker|ex)\s+(will|going to|cheating)",
            r"\b(is|will)\s+(he|she|they)\s+(cheat|cheating|divorce|get fired|die)",
            r"\bwhat (will happen|is happening)\s+to\s+(him|her|them|my boss|my neighbor)",
        ],
        "keywords": ["my boss", "my neighbor", "is he cheating", "will she get fired"]
    },
    
    # Conditional (need disclaimers)
    BlockReasons.HEALTH_TENDENCY: {
        "patterns": [
            r"\b(health|medical)\s+(issues|problems|concerns|tendencies)",
            r"\b(6th house|Saturn in 6th|Mars in 6th)\s+(health|disease)",
            r"\bwhat\s+(diseases|health problems|illnesses)\s+(might|could|may)",
        ],
        "keywords": ["health issues", "6th house health", "what diseases might"]
    },
    
    BlockReasons.FINANCIAL_TREND: {
        "patterns": [
            r"\b(should I|is it good)\s+(invest|buy|sell|start business)",
            r"\b(stock market|investment|business)\s+(good time|timing|period)",
            r"\b(financial|money|wealth)\s+(period|timing|phase)",
        ],
        "keywords": ["should I invest", "good time for business", "financial period"]
    },
}


def quick_pattern_check(query: str) -> Optional[str]:
    """
    Fast keyword/pattern matching before LLM call.
    
    Returns reason code if pattern matches, None otherwise.
    """
    query_lower = query.lower()
    
    for reason, data in KEYWORD_PATTERNS.items():
        # Check regex patterns
        for pattern in data.get("patterns", []):
            if re.search(pattern, query_lower):
                return reason
        
        # Check simple keywords
        for keyword in data.get("keywords", []):
            if keyword.lower() in query_lower:
                return reason
    
    return None


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
        llm: Optional[ChatOpenAI] = None,
        use_pattern_matching: bool = True,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize safety classifier.
        
        Args:
            llm: LangChain LLM instance (defaults to gpt-4o-mini)
            use_pattern_matching: Whether to use fast pattern matching first
            confidence_threshold: Threshold below which to flag for human review
        """
        self.llm = llm or ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,  # Deterministic for safety decisions
        )
        self.use_pattern_matching = use_pattern_matching
        self.confidence_threshold = confidence_threshold
        
        # Build classifier chain
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SAFETY_CLASSIFIER_SYSTEM_PROMPT.format(
                examples=CLASSIFICATION_EXAMPLES
            )),
            ("human", "Query: {query}")
        ])
        
        self.chain = (
            self.prompt 
            | self.llm 
            | JsonOutputParser(pydantic_object=SafetyDecision)
        )
    
    def classify(self, query: str) -> SafetyCheckResult:
        """
        Classify query safety using multi-gate approach.
        
        Args:
            query: User query to classify
        
        Returns:
            SafetyCheckResult with decision and metadata
        """
        # Gate 1: Fast pattern matching
        if self.use_pattern_matching:
            pattern_reason = quick_pattern_check(query)
            
            if pattern_reason:
                # Pattern matched - create high-confidence decision
                decision = self._create_pattern_decision(query, pattern_reason)
                return self._build_result(query, decision)
        
        # Gate 2: LLM Classification
        try:
            decision_dict = self.chain.invoke({"query": query})
            decision = SafetyDecision(**decision_dict)
            
        except Exception as e:
            # Fallback: Conservative block on error
            decision = SafetyDecision(
                category="HARD_BLOCK",
                reason="classifier_error",
                should_answer=False,
                confidence=0.0,
                explanation=f"Classifier error: {str(e)}"
            )
        
        return self._build_result(query, decision)
    
    def _create_pattern_decision(
        self,
        query: str,
        reason: str
    ) -> SafetyDecision:
        """Create decision from pattern match"""
        
        # Map reason to category
        category_map = {
            BlockReasons.DEATH_PREDICTION: "HARD_BLOCK",
            BlockReasons.MEDICAL_DIAGNOSIS: "HARD_BLOCK",
            BlockReasons.GAMBLING_SPECIFIC: "HARD_BLOCK",
            BlockReasons.HARMFUL_INTENT: "HARD_BLOCK",
            BlockReasons.PRIVACY_VIOLATION: "SOFT_BLOCK",
            BlockReasons.HEALTH_TENDENCY: "CONDITIONAL",
            BlockReasons.FINANCIAL_TREND: "CONDITIONAL",
        }
        
        category = category_map.get(reason, "HARD_BLOCK")
        should_answer = category not in ["HARD_BLOCK", "SOFT_BLOCK"]
        
        # Determine disclaimer type for conditional
        disclaimer_map = {
            BlockReasons.HEALTH_TENDENCY: DisclaimerTypes.HEALTH,
            BlockReasons.FINANCIAL_TREND: DisclaimerTypes.FINANCIAL,
        }
        disclaimer_type = disclaimer_map.get(reason) if should_answer else None
        
        return SafetyDecision(
            category=category,
            reason=reason,
            should_answer=should_answer,
            disclaimer_type=disclaimer_type,
            confidence=0.95,  # High confidence from pattern match
            explanation=f"Matched pattern for {reason}"
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
                "classification_method": "pattern" if quick_pattern_check(query) else "llm",
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
    llm: Optional[ChatOpenAI] = None,
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
