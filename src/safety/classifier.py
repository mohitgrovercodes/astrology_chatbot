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

1. What is the user actually trying to achieve with this query?
2. If I answer this question, what is the realistic worst-case outcome for the user?
3. Is the intent medical, predictive of death, gambling-related, or about a third party?
4. Is the phrasing fatalistic ("will X happen") or empowering ("what energy supports X")?
5. Choose the category that best protects the user while causing the least unnecessary restriction.

**HINGLISH/HINDI BIAS:** Realize that "Main" (I), "Mera/Meri" (My), and "Mujhe" (Me/To me) are FIRST-PERSON pronouns. If a user says "Main foreign kab jaunga?", they are asking about THEMSELVES. This is ALWAYS SAFE and NEVER a privacy violation.

**CONSERVATIVE BIAS:** When genuinely uncertain between SAFE and CONDITIONAL, choose CONDITIONAL. When uncertain between CONDITIONAL and SOFT_BLOCK, choose CONDITIONAL with a strong disclaimer. Only use HARD_BLOCK when the potential harm is concrete and serious.

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
    
    # ── Astrological safe-words: queries containing these skip the LLM vulgarity gate ──
    _ASTRO_SAFE_WORDS = frozenset([
        'kundli', 'kundali', 'horoscope', 'rashi', 'lagna', 'nakshatra', 'dasha',
        'antardasha', 'mahadasha', 'graha', 'planet', 'saturn', 'jupiter', 'venus',
        'mars', 'mercury', 'moon', 'sun', 'rahu', 'ketu', 'shani', 'mangal',
        'budh', 'brihaspati', 'shukra', 'surya', 'chandra', 'transit', 'gochar',
        'chart', 'birth chart', 'vedic', 'jyotish', 'yoga', 'bhava', 'house',
        'marriage', 'shaadi', 'career', 'naukri', 'health', 'money', 'dhan',
        'foreign', 'videsh', 'child', 'bachha', 'santan', 'property', 'ghar',
    ])

    def _llm_vulgarity_check(self, query: str) -> bool:
        """
        Lightweight LLM gate for vulgarity/explicit content not caught by keywords.
        Returns True if the query is vulgar/abusive/explicit, False otherwise.
        Fails OPEN (returns False) on any error so legitimate queries are never blocked.
        Only called for queries that are not clearly astrological or chitchat.
        """
        try:
            prompt = (
                "You are a content moderator for a professional astrology chatbot. "
                "Decide ONLY whether the user message below contains: profanity, sexual explicitness, "
                "verbal abuse, sexual harassment, or vulgar insults — in ANY language "
                "(English, Hindi, Tamil, Telugu, Marathi, Punjabi, Malayalam, Urdu, Hinglish, or any mix).\n\n"
                f'User message: "{query}"\n\n'
                "Reply with exactly one word: YES (if vulgar/abusive/explicit) or NO (if not)."
            )
            response = self.llm.invoke(prompt)
            answer = response.content.strip().upper()
            is_vulgar = answer.startswith("YES")
            if is_vulgar:
                logger.info(f"[SAFETY] LLM vulgarity check: VULGAR — '{query[:60]}'")
            return is_vulgar
        except Exception as e:
            logger.error(f"[SAFETY] LLM vulgarity check error (fail-open): {e}")
            return False  # fail open — do not block on errors

    def classify(self, query: str, conversation_history: list = None) -> SafetyCheckResult:
        """
        Classify query safety using multi-gate approach.
        """
        # Gate -2: Keyword hard-block — covers all major Indian + English profanity.
        # No LLM call. Runs first for zero latency on obvious cases.
        _VULGAR_KEYWORDS = {
            # ── English ──────────────────────────────────────────────────────
            'fuck', 'shit', 'bitch', 'asshole', 'bastard', 'motherfucker',
            'dick', 'pussy', 'cock', 'cunt', 'whore', 'slut', 'nude', 'porn',
            'pornography', 'masturbat', 'sex position', 'sexual position',
            # ── Hindi / Hinglish (transliterated) ────────────────────────────
            'chutiya', 'madarchod', 'bhosdike', 'bhosdika', 'randi', 'harami',
            'gaandu', 'gandu', 'lund', 'chut', 'bhenchod', 'behenchod',
            'maderchod', 'saala', 'kamina', 'kutte', 'kamine', 'haramzada',
            'haramkhor', 'madarjaat', 'lavde', 'lavda',
            # ── Tamil (transliterated) ────────────────────────────────────────
            'punda', 'pundai', 'sunni', 'thevidiya', 'ootha', 'koothi',
            'baadu', 'paiyan', 'oombu',
            # ── Telugu (transliterated) ───────────────────────────────────────
            'dengey', 'dengudi', 'pukku', 'modda', 'lanja', 'lanjakodaka',
            'pooku', 'gudda',
            # ── Marathi (transliterated) ──────────────────────────────────────
            'zavnya', 'zavad', 'bhadva', 'aai zavadya', 'ghanta', 'zadya',
            # ── Punjabi (transliterated) ──────────────────────────────────────
            'bhen di', 'teri maa', 'phudu', 'phuddu', 'maa di',
            # ── Malayalam (transliterated) ────────────────────────────────────
            'theetta', 'myre', 'kunna', 'pooru', 'poori', 'ammaye',
            # ── Urdu (transliterated) ─────────────────────────────────────────
            'haraamzada', 'gaand', 'khanki', 'madar', 'sala kutta',
            # ── Native Unicode script (common high-frequency slurs) ───────────
            'चुतिया', 'मादरचोद', 'भड़वा', 'रंडी', 'हरामी', 'लंड', 'भोसड़ी',
            'புண்டை', 'சுன்னி', 'தேவிடியா',
            'పుక్కు', 'మొద్ద', 'లంజ',
            'झवाड', 'भडवा', 'लवडा',
            'ਭੈਣ ਦੀ', 'ਫੁੱਡੂ',
            'കുണ്ണ', 'പൂറ്',
        }
        query_lower_vg = query.lower()
        if any(kw in query_lower_vg for kw in _VULGAR_KEYWORDS):
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

        # Gate -1.5: LLM vulgarity fallback — catches multilingual profanity,
        # euphemisms, and mixed-language abuse missed by keywords.
        # Skipped for clearly astrological queries (no latency overhead on the
        # majority of real traffic).
        query_words = set(query_lower_vg.split())
        is_clearly_astro = bool(query_words & self._ASTRO_SAFE_WORDS)
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

        # Gate -1: User's Own Data Queries (PRIORITY - check first!)
        # These should NEVER be blocked - user asking about their own profile
        query_lower = query.lower().strip()
        
        # Multi-word English phrases — safe to use substring match
        own_data_phrases = [
            'my dob', 'my date of birth', 'my birth date', 'my birthday',
            'my birth time', 'my time of birth', 'my birth place',
            'my place of birth', 'when was i born', 'where was i born',
            'what time was i born', 'my chart', 'my kundli', 'my horoscope',
            'show me my', 'tell me my', 'what is my',
        ]
        # Short Hindi/Hinglish first-person markers — word-boundary matched to avoid
        # 'meri behen ki shaadi' triggering 'meri' and short-circuiting Gate 0.
        hindi_markers = ['main', 'mera', 'meri', 'mujhe', 'hum']

        # Third-party relationship words: if ANY of these appear alongside a Hindi
        # first-person marker, the query is about someone ELSE — do NOT bypass safety.
        _THIRD_PARTY_HINDI_WORDS = {
            'behen', 'behan', 'behna', 'bhai', 'bhaiya', 'didi',
            'maa', 'mata', 'papa', 'pita', 'pitaji', 'baap',
            'dost', 'yaar', 'saheli', 'frnd',
            'boss', 'manager', 'colleague', 'sahab',
            'pati', 'patni', 'husband', 'wife', 'biwi',
            'beta', 'beti', 'bachha', 'ladka', 'ladki',
            'chacha', 'chachi', 'mama', 'mami', 'nana', 'nani',
            'dada', 'dadi', 'naana', 'naani', 'fufa', 'bua',
        }

        import re as _re
        phrase_match = any(phrase in query_lower for phrase in own_data_phrases)
        hindi_match = any(_re.search(r'\b' + marker + r'\b', query_lower) for marker in hindi_markers)

        # Cancel the hindi bypass if the query also contains a third-party relationship word
        if hindi_match:
            query_words_set = set(query_lower.split())
            if query_words_set & _THIRD_PARTY_HINDI_WORDS:
                hindi_match = False  # This is about someone else — don't bypass Gate 0

        if phrase_match or hindi_match:
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
        
        # ════════════════════════════════════════════════════════════════
        # Gate -0.5: Meta-Question Detection (Conversation History Queries)
        # ════════════════════════════════════════════════════════════════
        # Questions ABOUT the conversation itself should NOT be blocked
        meta_question_patterns = [
            r'what (was|were|is) (my|i|our) (last|previous|earlier|first) (question|query|message|thing)',
            r'what did i (ask|say|tell|mention)',
            r'what (have we|did we) (discuss|talk|chat) about',
            r'can you (repeat|tell me|remind me|recall)',
            r'what (was|is) (our|my|the) (conversation|discussion|chat) about',
            r'what (topic|subject) (did we|were we)',
            r'remind me (what|of)',
            r'go back to',
            r'earlier you (said|mentioned|told)',
        ]
        
        import re
        is_meta_question = any(re.search(pattern, query_lower) for pattern in meta_question_patterns)
        
        if is_meta_question:
            logger.info(f"[SAFETY] Meta-question detected - allowing conversation history query")
            decision = SafetyDecision(
                category="SAFE",
                reason="meta_question",
                should_answer=True,
                disclaimer_type=None,
                confidence=0.90,
                explanation="Query is about conversation history, not astrology content"
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
        
        # Gate 1: Fast Semantic Routing (lazy-initialize routes on first call)
        if self.use_pattern_matching and self.semantic_router.model:
            self._ensure_routes_initialized()
            route_result = self.semantic_router.route(query, threshold=0.75)  # Tuned threshold for safety
            
            if route_result:
                # Semantic match found
                decision = self._create_semantic_decision(query, route_result.name, route_result.confidence)
                return self._build_result(query, decision)
        
        # Gate 2: LLM Classification
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
    
    def _llm_third_party_check(self, query: str) -> Optional[tuple[bool, str]]:
        """
        LLM fallback for third-party detection — catches multilingual and
        creatively phrased requests that keyword patterns miss.
        Returns (True, 'someone else') if the query asks for another person's
        chart/prediction, None otherwise. Fails open on errors.
        """
        try:
            prompt = (
                "You are a safety classifier for an astrology chatbot. "
                "Determine whether the following message is asking for astrological "
                "predictions or chart analysis for someone OTHER than the person writing "
                "the message — in any language (English, Hindi, Hinglish, Tamil, Telugu, "
                "Marathi, Punjabi, Malayalam, Urdu, or any mix).\n\n"
                f'Message: "{query}"\n\n'
                "Reply with exactly one word: YES (asking about someone else) or NO (asking about themselves)."
            )
            response = self.llm.invoke(prompt)
            answer = response.content.strip().upper()
            if answer.startswith("YES"):
                logger.info(f"[SAFETY] LLM third-party check: third-party query detected — '{query[:60]}'")
                return True, "someone else"
            return None
        except Exception as e:
            logger.error(f"[SAFETY] LLM third-party check error (fail-open): {e}")
            return None  # fail open

    def _detect_third_party(self, query: str) -> Optional[tuple[bool, str]]:
        """
        Detect if query is about someone else's prediction.
        Layer 1: English keyword patterns.
        Layer 2: Hindi/multilingual keyword patterns.
        Layer 3: LLM fallback for everything else (skipped for clearly self-referential queries).

        Returns:
            (is_third_party, person_name) or None
        """
        query_lower = query.lower()

        # Exclusions: Valid questions about the user's *own* life events involving others.
        exclusions = [
            'my child be born', 'have a child', 'get a job',
            'kab jaunga', 'kab jayengi', 'videsh kab', 'foreign kab',
        ]
        for exc in exclusions:
            if exc in query_lower:
                return None

        # ── Layer 1: English keyword patterns ────────────────────────────────
        en_patterns = [
            'my friend', 'my sister', 'my brother', 'my mother', 'my father',
            'my husband', 'my wife', 'my son', 'my daughter',
            'my boss', 'my colleague', 'my neighbor',
            'her chart', 'his chart', 'their chart',
            'her horoscope', 'his horoscope',
            'when will he', 'when will she', 'when will they',
            'will he', 'will she', 'will they',
            'does he', 'does she', 'do they',
        ]

        # Child-chart exception: "my child's chart" is third-party, but
        # "when will I have a child" is the user's own query.
        if 'my child' in query_lower and not any(exc in query_lower for exc in exclusions):
            if 'chart' in query_lower or 'horoscope' in query_lower or 'kundli' in query_lower:
                return True, "your child"

        for pattern in en_patterns:
            if pattern in query_lower:
                words_after = query.split(pattern)[-1] if pattern in query.lower() else ""
                names = re.findall(r'\b[A-Z][a-z]+\b', words_after[:50])
                person = names[0] if names else "someone else"
                if 'name is' in query_lower:
                    name_match = re.search(r'name is ([A-Z][a-z]+)', query, re.IGNORECASE)
                    if name_match:
                        person = name_match.group(1)
                return True, person

        # ── Layer 2: Hindi / multilingual keyword patterns ────────────────────
        hi_patterns = [
            # Hindi/Hinglish relationship + possessive combos
            'mere dost', 'meri dost', 'mera dost',
            'meri behen', 'meri behan', 'meri didi',
            'mere bhai', 'mera bhai', 'mere bhaiya',
            'meri maa', 'mere papa', 'mere pitaji', 'mere pita',
            'meri wife', 'mere pati', 'meri patni',
            'mera beta', 'meri beti',
            'mere boss', 'mere sahab', 'mere colleague',
            'meri saheli', 'mere yaar',
            # Third-person future/prediction markers
            'uski shaadi', 'uska career', 'unki kundali', 'unka chart',
            'iski kundali', 'iska chart', 'uski kundali', 'uska bhavishya',
            # Tamil (transliterated)
            'en nanban', 'en akka', 'en thambi', 'en amma', 'en appa',
            'en husband', 'en wife', 'en boss',
            # Telugu (transliterated)
            'na friend', 'na sister', 'na brother', 'na husband', 'na wife',
        ]

        for pattern in hi_patterns:
            if pattern in query_lower:
                return True, "someone else"

        # ── Layer 3: LLM fallback ─────────────────────────────────────────────
        # Only call LLM if the query doesn't look entirely self-referential.
        # Skip if clearly first-person astrological (avoids latency on ~90% of traffic).
        _SELF_REFERENTIAL = {
            'mera', 'meri', 'mujhe', 'main', 'hum', 'my', 'i ', "i'm",
            'mere liye', 'apna', 'apni',
        }
        _ASTRO_TERMS = {
            'kundli', 'kundali', 'chart', 'rashi', 'lagna', 'dasha',
            'nakshatra', 'horoscope', 'jyotish',
        }
        has_self_ref = any(w in query_lower for w in _SELF_REFERENTIAL)
        has_astro = any(w in query_lower for w in _ASTRO_TERMS)

        # Only skip LLM if both clearly self-referential AND astrological
        if not (has_self_ref and has_astro):
            return self._llm_third_party_check(query)

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