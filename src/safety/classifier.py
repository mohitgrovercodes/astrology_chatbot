# src/safety/classifier.py
# src\safety\classifier.py
"""
Safety Classifier for Astrology Chatbot

Enhanced safety classification using LangChain with multi-gate decision logic.
"""

import re
from typing import Dict, List, Optional, Set
from langchain_core.prompts import ChatPromptTemplate
from config.logger import get_logger

logger = get_logger("safety")
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.language_models import BaseChatModel

from .models import (
    SafetyDecision,
    SafetyCheckResult,
    BlockReasons,
    DisclaimerTypes
)



from src.routing import SemanticRouter
from .vulgarity import (
    contains_vulgar_keyword,
    is_clearly_astrological_query,
    llm_vulgarity_check,
)

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
    BlockReasons.VULGAR_CONTENT: [
        "sex position astrology", "which sign is best in bed", "sexual compatibility",
        "how to seduce", "nude", "porn", "masturbation", "bitch", "fuck you",
        "chutiya", "madarchod", "bhosdike", "randi", "harami",
        "gaandu", "lund", "chut", "bhenchod"
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
    BlockReasons.SABOTAGE_CRITICISM: [
        "your prediction is wrong", "you are fake", "this makes no sense",
        "astrology is a scam", "you don't know anything", "why did you lie",
        "this prediction failed", "you are useless", "shut up bot",
        "you are wrong"
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
    """
    Initialize semantic routes for safety checks.
    PERF: Uses add_routes_batch() — single OpenAI API call for ALL routes.
          Results are disk-cached; subsequent calls load in milliseconds.
    """
    router = SemanticRouter()
    if not router.model:
        return

    router.add_routes_batch([
        {"name": reason, "examples": examples, "metadata": {"reason": reason}}
        for reason, examples in SAFETY_ROUTES.items()
    ])

# NOTE: Routes are intentionally NOT initialized at module load time.
# They are initialized lazily on the first classify() call.
# This avoids 9 OpenAI API calls at import time, which was the main startup bottleneck.
# See SafetyClassifier._ensure_routes_initialized() below.



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
  "explanation": "Direct question about death timing"
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
  "explanation": "Seeking medical diagnosis from astrology"
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
  "explanation": "Asking about health tendencies for self, not diagnosis"
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
  "explanation": "Fortune-telling style question needs reframing"
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
  "explanation": "Question about a third party without their consent"
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
  "explanation": "Educational astrology question"
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
  "explanation": "Investment timing question needs financial disclaimer"
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
  "explanation": "Misunderstands astrology as punishment"
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
  "explanation": "Specific gambling prediction request"
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
  "explanation": "Legitimate calculation question about own chart"
}}

**Example 11:**
Query: "Mera bachha kab paida hoga?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "children_timing",
  "should_answer": true,
  "disclaimer_type": "CHILDREN",
  "reframed_query": null,
  "confidence": 0.92,
  "explanation": "User asking about their own future child (5th house question) — 'Mera' means MY, this is a personal fertility/timing query"
}}

**Example 12:**
Query: "Mere dost ki shaadi kab hogi?"
Classification:
{{
  "category": "SOFT_BLOCK",
  "reason": "third_party_prediction",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.93,
  "explanation": "Asking about a friend's marriage — third party without their consent. 'Dost' (friend) makes this about someone else."
}}

**Example 13:**
Query: "Meri shaadi kab hogi?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "relationship_compatibility",
  "should_answer": true,
  "disclaimer_type": "RELATIONSHIP",
  "reframed_query": null,
  "confidence": 0.94,
  "explanation": "User asking about own marriage timing — 'Meri' (my) confirms this is personal"
}}

**Example 14:**
Query: "What did I ask you last time?"
Classification:
{{
  "category": "SAFE",
  "reason": "meta_question",
  "should_answer": true,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.96,
  "explanation": "Question about the conversation history, not an astrological prediction"
}}

**Example 15:**
Query: "Main foreign kab jaunga?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "foreign_travel",
  "should_answer": true,
  "disclaimer_type": "GENERAL",
  "reframed_query": null,
  "confidence": 0.91,
  "explanation": "Personal foreign travel query — 'Main' (I) and 'jaunga' (I will go) are first-person, this is about the user themselves"
}}

**Example 16:**
Query: "Mere beta ki naukri kab lagegi?"
Classification:
{{
  "category": "SOFT_BLOCK",
  "reason": "third_party_prediction",
  "should_answer": false,
  "disclaimer_type": null,
  "reframed_query": null,
  "confidence": 0.90,
  "explanation": "Asking about son's job prospects — 'Mere beta' (my son) is a third party, not the user themselves"
}}

**Example 17:**
Query: "Mera beta kab paida hoga?"
Classification:
{{
  "category": "CONDITIONAL",
  "reason": "children_timing",
  "should_answer": true,
  "disclaimer_type": "CHILDREN",
  "reframed_query": null,
  "confidence": 0.91,
  "explanation": "User asking when they will have a son — 'paida hoga' (will be born) makes this about having a child, not predicting for an existing child"
}}
"""


# ============================================================================
# SAFETY CLASSIFIER PROMPT
# ============================================================================

SAFETY_CLASSIFIER_SYSTEM_PROMPT = """You are a safety classifier for a professional Vedic astrology AI chatbot serving real users across multiple languages (English, Hindi, Tamil, Hinglish, mixed). Your role is to protect users from harmful astrological practices while allowing legitimate, empowering consultations.

Your classification must be based on the user's UNDERLYING INTENT and potential REAL-WORLD HARM, not specific words or phrases. A user asking in Hindi, Tamil, or Hinglish deserves the same nuanced evaluation as one asking in English.

**CLASSIFICATION CATEGORIES:**

**HARD_BLOCK** — The answer would cause genuine harm or is deeply unethical. Block regardless of phrasing language:
- `death_prediction`: Any request for timing, prediction, or probability of death for self or others. This includes indirect phrasings like "how long will I live", "when is my time up", "meri maut kab hogi" (Hindi), "en maranam eppodhu" (Tamil).
- `medical_diagnosis`: Requests that treat astrology as medical diagnosis or that ask whether a person has a disease, or whether they should change/stop medication.
- `gambling_specific`: Requests for specific winning numbers, which bet to place, or outcomes in games of chance.
- `harmful_intent`: Any query where the user intends harm to self or others, even if framed astrologically ("which day is auspicious to hurt someone").
- `vulgar_content`: Messages containing profanity, sexual explicitness, vulgar abuse, or sexually inappropriate requests — in any language including Hindi/Hinglish. Examples: sexually explicit questions, abusive slurs, profane insults directed at the bot.

**SOFT_BLOCK** — The request is outside the ethical scope of astrology for this bot. Decline warmly:
- `privacy_violation`: Questions asked about a third party (boss, neighbor, spouse, friend) without their consent — predictions, secrets, behavior analysis.
- `out_of_scope`: Conspiracy theories, political predictions, stock tips, sports match outcomes.
- `sabotage_criticism`: User claims the prediction is wrong, insults the bot, calls astrology fake, or is expressing deep frustration. Respond gracefully.

**CONDITIONAL** — Answerable, but requires a protective disclaimer to prevent misuse:
- `health_tendency`: General health tendencies from chart (not diagnosis). Add HEALTH disclaimer.
- `financial_trend`: Investment timing, wealth periods from chart. Add FINANCIAL disclaimer.
- `relationship_compatibility`: Marriage, partnership questions. Add RELATIONSHIP disclaimer.
- `children_timing`: Fertility, children timing. Add CHILDREN disclaimer.
- `career_change`: Career timing, job decisions. Add CAREER disclaimer.
- `foreign_travel`: Queries about going abroad, videsh yatra, or immigration. Add GENERAL disclaimer.

**REFRAME** — The question is answerable but framed as hard fortune-telling. Reframe it to empower the user with probabilistic guidance:
- `poorly_framed`: "Will I get rich?" -> "What periods support wealth accumulation for me?"
- `misunderstood`: "Why is God punishing me?" -> "What challenging planetary periods am I in, and how do I grow through them?"

**SAFE** — Legitimate astrological question with no special risk:
- `educational`: Learning about concepts, planets, houses, yogas, dashas.
- `calculation_query`: Birth chart, dasha, transit calculations.
- `chart_interpretation`: Interpreting a placement or pattern for personal understanding.

---

**HOW TO REASON (step by step before classifying):**

1. Who is the subject of the query — the user themselves, or someone else?
2. What is the user actually trying to achieve?
3. If I answer this, what is the realistic worst-case outcome for the user?
4. Is the intent medical, death-prediction, gambling, or truly about a third party?
5. Choose the category that best protects the user while causing the least unnecessary restriction.

**FIRST-PERSON IDENTIFICATION (critical for Hindi/Hinglish):**
These words confirm the query is about the USER THEMSELVES — never treat these as third-party:
- "Main" = I, "Mera/Mere/Meri" = My, "Mujhe/Mujhko" = To me, "Apna/Apni" = My own, "Hum" = We/I
- "En" (Tamil I/my), "Na" (Telugu my), "Naan" (Tamil I)
If the query uses these AND asks about marriage/career/health/children/travel — it is a PERSONAL question. Classify as CONDITIONAL or SAFE, never SOFT_BLOCK.

**SELF vs THIRD-PARTY — the critical distinction:**
- "Meri shaadi kab hogi?" → user's OWN marriage → CONDITIONAL (relationship_compatibility)
- "Mere dost ki shaadi kab hogi?" → friend's marriage → SOFT_BLOCK (third_party_prediction)
- "Mera bachha kab paida hoga?" / "Mera beta kab paida hoga?" → user asking about HAVING a child → CONDITIONAL (children_timing). "Paida hoga" (will be born) signals this is about the user's own future parenthood, not predicting for an existing child.
- "Mere beta ki naukri kab lagegi?" → asking about an existing son's job → SOFT_BLOCK (third_party_prediction)
The key test: does the query ask about the USER'S OWN life event, or about someone else's?

**META-QUESTIONS:**
Questions about the conversation itself ("What did I ask?", "What were we discussing?", "Can you repeat that?") are SAFE. They are not astrological predictions and should never be blocked.

**CONSERVATIVE BIAS:** When uncertain between SAFE and CONDITIONAL, choose CONDITIONAL. When uncertain between CONDITIONAL and SOFT_BLOCK, choose CONDITIONAL with a strong disclaimer. Only use HARD_BLOCK when potential harm is concrete and serious.

{examples}

Now classify the following query, applying semantic reasoning — do not rely on keyword matching alone:"""


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
        PERF: SemanticRouter routes are NOT loaded here — they are initialized
              lazily on the first classify() call to avoid API calls at startup.
        """
        if llm:
            self.llm = llm
        else:
            from src.llm.factory import LLMFactory
            self.llm = LLMFactory.create(purpose="classification", temperature=0.0)
        self.use_pattern_matching = use_pattern_matching
        self.confidence_threshold = confidence_threshold

        # Semantic router: singleton, routes loaded lazily on first classify()
        self.semantic_router = SemanticRouter()
        self._safety_routes_initialized = False

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

    def _ensure_routes_initialized(self):
        """Lazy-init safety routes on first classify() call (disk-cached)."""
        if self._safety_routes_initialized:
            return
        try:
            _initialize_safety_routes()
        except Exception as e:
            logger.warning(f"[SAFETY] could not initialize semantic routes: {e}")
        self._safety_routes_initialized = True
    
    def _llm_vulgarity_check(self, query: str) -> bool:
        """
        Lightweight LLM gate for vulgarity/explicit content not caught by keywords.
        Returns True if the query is vulgar/abusive/explicit, False otherwise.
        Fails OPEN (returns False) on any error so legitimate queries are never blocked.
        Only called for queries that are not clearly astrological or chitchat.
        """
        try:
            is_vulgar = llm_vulgarity_check(query=query, llm=self.llm, strict_prompt=False)
            if is_vulgar:
                logger.info(f"[SAFETY] LLM vulgarity check: VULGAR — '{query[:60]}'")
            return is_vulgar
        except Exception as e:
            logger.error(f"[SAFETY] LLM vulgarity check error (fail-open): {e}")
            return False  # fail open — do not block on errors

    def classify(self, query: str, conversation_history: list = None) -> SafetyCheckResult:
        """
        Classify query safety.

        Gate 1 — Keyword hard-block: zero-latency check for obvious profanity/vulgarity.
        Gate 2 — LLM vulgarity fallback: catches multilingual abuse missed by keywords
                  (skipped for clearly astrological queries).
        Gate 3 — Unified LLM classification: single smart call that handles all query
                  types including first-person Hinglish, third-party detection, meta-
                  questions, and all safety categories.  No pattern matching.
        """
        # Gate 1: Keyword hard-block — covers all major Indian + English profanity.
        # No LLM call. Runs first for zero latency on obvious cases.
        if contains_vulgar_keyword(query):
            logger.info(f"[SAFETY] Vulgar keyword detected — hard blocking")
            decision = SafetyDecision(
                category="HARD_BLOCK",
                reason=BlockReasons.VULGAR_CONTENT,
                should_answer=False,
                disclaimer_type=None,
                confidence=0.99,
                explanation="Vulgar or explicit content detected via keyword pre-check"
            )
            return self._build_result(query, decision)

        # Gate 2: LLM vulgarity fallback — catches multilingual profanity,
        # euphemisms, and mixed-language abuse missed by keywords.
        # Skipped for clearly astrological queries (no latency overhead on the
        # majority of real traffic).
        is_clearly_astro = is_clearly_astrological_query(query)
        if not is_clearly_astro and self._llm_vulgarity_check(query):
            decision = SafetyDecision(
                category="HARD_BLOCK",
                reason=BlockReasons.VULGAR_CONTENT,
                should_answer=False,
                disclaimer_type=None,
                confidence=0.95,
                explanation="Vulgar or explicit content detected via LLM vulgarity check"
            )
            return self._build_result(query, decision)

        # Gate 3: Unified LLM classification — handles everything:
        # first-person vs third-party, meta-questions, safety categories,
        # disclaimers, and reframing. No pattern matching.
        query_lower = query.lower().strip()
        try:
            # Format context — history uses {'role': ..., 'content': ...} format
            context_str = "None"
            if conversation_history:
                history_subset = conversation_history[-2:]
                context_lines = []
                for turn in history_subset:
                    role = turn.get('role', '')
                    content = turn.get('content', '')[:100]
                    if role == 'user':
                        context_lines.append(f"User: {content}")
                    elif role == 'assistant':
                        context_lines.append(f"Bot: {content}...")
                if context_lines:
                    context_str = "\n".join(context_lines)

            decision_dict = self.chain.invoke({"query": query, "context": context_str})
            decision = SafetyDecision(**decision_dict)
            
        except Exception as e:
            # Fallback: Be permissive on technical errors but log the failure
            # If the query is obviously safe (e.g. "hi", "what is my rashi"), don't block
            logger.warning(f"[INTENT] Safety classifier technical error: {e}")
            
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
            BlockReasons.VULGAR_CONTENT: "HARD_BLOCK",
            BlockReasons.PRIVACY_VIOLATION: "SOFT_BLOCK",
            "THIRD_PARTY_PREDICTION": "SOFT_BLOCK",
            BlockReasons.SABOTAGE_CRITICISM: "SOFT_BLOCK",
            BlockReasons.HEALTH_TENDENCY: "CONDITIONAL",
            BlockReasons.FINANCIAL_TREND: "CONDITIONAL",
            
            # CHITCHAT IS SAFE - Never block! (FIX)
            "greeting": "SAFE",
            "identity": "SAFE",
            "gratitude": "SAFE",
            "wellbeing": "SAFE",
            "farewell": "SAFE",
            "closure": "SAFE",
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