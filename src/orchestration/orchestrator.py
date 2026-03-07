# src\orchestration\orchestrator.py
"""
Enhanced LangGraph Orchestrator with REAL Calculation Integration.

UPDATED: Now uses actual VedicEngine calculations (no placeholders!)

3-way routing:
1. CHITCHAT -> Quick response
2. NEEDS_CALCULATION -> Real birth chart calculation
3. NEEDS_RAG -> Knowledge + Real chart data + Interpretation/Prediction
4. RAG_ONLY -> Knowledge only
"""

from datetime import datetime
from src.utils.localization import get_localization_manager
from src.safety.constitution import get_constitution_injection
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Tuple

# Types for state management
import json

from langgraph.graph import StateGraph, END  # ← ADD CompiledStateGraph
from langchain_core.messages import HumanMessage, AIMessage

# NEW: Import calculation tools
from src.tools.tools import get_calculation_tools
from src.utils.serializers import serialize_vedic_chart

# PHASE 10.5: Import new safety framework
from src.safety import create_safety_classifier, get_template, get_disclaimer
from src.safety.input_validator import InputValidator

# PHASE 11: Semantic Routing
from src.routing import SemanticRouter
from src.orchestration.divisional_chart_helper import get_divisional_chart_context

# PERSISTENCE & CACHING
from src.engines.vedic.vedic_engine import VedicEngine, VedicChart
from config.rag_config import RAGConfig

try:
    from src.validation.vedic_validation_engine_v2 import VedicValidationEngineV2
    VALIDATION_AVAILABLE = True
except ImportError:
    print("[VALIDATION] vedic_validation_engine_v2 not found - validation disabled")
    VALIDATION_AVAILABLE = False
    
try:
    from src.engines.vedic.chart_analyzer import ChartAnalyzer, analyze_chart
    from src.validation.chart_synthesis_engine import ChartSynthesisEngine, synthesize_chart_analysis
    ENHANCED_ANALYSIS_AVAILABLE = True
except ImportError:
    print("[ENHANCED_ANALYSIS] chart_analyzer/synthesis_engine not found - using basic analysis")
    ENHANCED_ANALYSIS_AVAILABLE = False

from src.orchestration.orchestrator_validation_helpers import (
    detect_query_type,
    determine_validation_tier,
    prepare_chart_for_validation,
    should_hard_halt,
    build_halt_response,
    build_validation_disclaimer,
    format_validation_for_prompt
)

class NakshatraState(TypedDict):
    """Enhanced state with calculation results."""
    
    # Input
    query: str
    user_id: str
    conversation_history: List[Dict]
    session_data: Optional[Dict]     # NEW: Transient session data (e.g., from Redis)
    
    # User context
    user_profile: Optional[Dict]
    authenticated: bool
    
    # Intent classification
    intent: Optional[str]  # CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY
    confidence: float
    intent_reasoning: str
    cached: bool
    detected_language: str  # 'en', 'hi', 'ta', etc.
    original_query: str     # Keep original for final response
    persona_type: str       # 'vedic' | 'western' (Phase 9)
    
    # Calculation results (for PREDICTION flow)
    chart_data: Optional[Dict]  # Birth chart
    dasha_data: Optional[Dict]  # Current dashas
    transit_data: Optional[Dict]  # Current transits
    
    # RAG results
    knowledge_chunks: Optional[List]
    
    # PHASE 10.5: Advanced Safety Metadata
    safety_result: Optional[Dict]     # Full SafetyCheckResult
    disclaimer_type: Optional[str]    # For CONDITIONAL responses
    is_reframed: bool                 # Track if query was transformed
    
    # Response
    answer: str
    error: Optional[str]
    processing_time: float
    
    # PHASE 10: Verification Loop
    validation_attempts: int
    validation_feedback: Optional[str]
    is_safe: bool
    
    # messages: Annotated[List, operator.add]

    # PHASE 12: Validation Results
    validation_result: Optional[Dict]
    validation_strength: Optional[float]
    validation_can_proceed: bool
    validation_query_type: Optional[str]
    validation_disclaimer: Optional[str]

    # NEW: Context Management Fields
    conversation_summary: Optional[str]      # LLM-generated summary
    intent_analysis: Optional[Dict]          # From context manager
    resolution_result: Optional[Dict]        # From semantic interpreter

class EnhancedLangGraphOrchestrator:
    """
    Enhanced orchestrator with 3-way routing and REAL calculations.
    """
    
    def __init__(
        self,
        intent_classifier,
        hybrid_retriever,
        prompt_builder,
        calculation_tools: Optional[Dict] = None,  # [DONE] CHANGED: Now optional
        llm=None,
        fast_llm=None  # NEW: Fast LLM for classification
    ):
        """Initialize enhanced orchestrator with dual LLM support."""
        self.intent_classifier = intent_classifier
        self.user_manager = None  # Removed: system is fully stateless via Redis
        self.hybrid_retriever = hybrid_retriever
        self.prompt_builder = prompt_builder
        
        # NEW: Auto-load calculation tools if not provided
        if calculation_tools is None:
            print("[LANGGRAPH] Loading calculation tools...")
            calculation_tools = get_calculation_tools()
            print(f"[LANGGRAPH] Loaded {len(calculation_tools)} calculation tools")
        
        self.calculation_tools = calculation_tools

        # [NEW] Auto-load prompt builder if not provided
        if prompt_builder is None:
            try:
                from src.ai.prompt_builder import PromptBuilder
                print("[LANGGRAPH] Auto-loading PromptBuilder...")
                prompt_builder = PromptBuilder()
            except ImportError as e:
                print(f"[LANGGRAPH] [ERROR] Failed to auto-load PromptBuilder: {e}")
        
        self.prompt_builder = prompt_builder

        # [NEW] Auto-load intent classifier if not provided
        if intent_classifier is None:
            try:
                from src.ai.intent_classifier import LLMIntentClassifier
                print("[LANGGRAPH] Auto-loading LLMIntentClassifier...")
                intent_classifier = LLMIntentClassifier(llm=fast_llm or llm)
            except ImportError as e:
                print(f"[LANGGRAPH] [ERROR] Failed to auto-load LLMIntentClassifier: {e}")
        
        self.intent_classifier = intent_classifier
        
        # [PHASE 6] Auto-load LLM if not provided
        if llm is None:
            from src.llm.factory import LLMFactory
            print("[LANGGRAPH] Auto-loading default LLM...")
            llm = LLMFactory.create()
            
        self.llm = llm  # Quality LLM for responses
        self.fast_llm = fast_llm or llm  # Fast LLM for classification (fallback to quality LLM)
        
        # [DONE] Connect fast LLM to intent classifier
        if hasattr(self.intent_classifier, 'set_llm') and self.fast_llm is not None:
            self.intent_classifier.set_llm(self.fast_llm)
            print("[LANGGRAPH] Fast LLM connected to intent classifier")
        
        # PHASE 10.5: Initialize new safety components
        self.safety_classifier = create_safety_classifier(llm=self.fast_llm)
        self.input_validator = InputValidator()
        
        # PHASE 11: Initialize Semantic Router for Chitchat
        self.semantic_router = SemanticRouter()
        if self.semantic_router.model:
            # Route 1: Greetings
            self.semantic_router.add_route(
                name="greeting",
                examples=[
                    "hi", "hello", "hey", "namaste", "namaskaram", "vanakkam", "hola",
                    "good morning", "good evening", "good afternoon", "howdy",
                    "wassup", "sup", "yo", "greetings", "salaam", "bonjour"
                ],
                metadata={"type": "greeting", "subtype": "simple_greeting"}
            )
            
            # Route 2: Identity questions
            self.semantic_router.add_route(
                name="identity",
                examples=[
                    "who are you", "what are you", "tell me about yourself",
                    "what can you do", "introduce yourself",
                    # Bot name questions ONLY ("your" / "aap" / "tum")
                    "what is your name", "what's your name",
                    "kaun ho tum", "kya ho tum", "aap kaun hain",
                    "aapka naam kya hai", "tumhara naam kya hai",
                ],
                metadata={"type": "chitchat", "subtype": "identity"}
            )

            # Route 2b: Personal profile questions (what is MY name/DOB/chart)
            # MUST be added BEFORE identity so the router resolves correctly
            self.semantic_router.add_route(
                name="personal_profile_query",
                examples=[
                    # English
                    "what is my name", "what's my name", "do you know my name",
                    "what is my date of birth", "what is my birth date",
                    "what is my sun sign", "what is my moon sign", "what is my ascendant",
                    "tell me my details", "what do you know about me",
                    "what city am I from", "where was I born",
                    # Hindi (Hinglish)
                    "mera naam kya hai", "mera name kya hai", "mera naam batao",
                    "meri date of birth kya hai", "meri DOB kya hai",
                    "mera janam kab hua", "main kahan paida hua", "meri birthplace kya hai",
                    "mera sign kya hai", "meri rashi kya hai", "mera lagna kya hai",
                    "tum mujhe jaante ho", "aap mujhe jaante hain",
                    "mere baare mein kya jaante ho",
                    # Hindi (native script)
                    "मेरा नाम क्या है", "मेरी जन्म तिथि क्या है",
                    "आप मुझे जानते हैं",
                ],
                metadata={"type": "chitchat", "subtype": "personal_profile_query"}
            )
            
            # Route 3: Gratitude
            self.semantic_router.add_route(
                name="gratitude",
                examples=[
                    "thanks", "thank you", "appreciate it", "grateful", "thankyou",
                    "dhanyavad", "shukriya", "dhanyawad", "shukriya-ji"
                ],
                metadata={"type": "chitchat", "subtype": "gratitude"}
            )
            
            # Route 4: How are you / Well-being checks
            self.semantic_router.add_route(
                name="wellbeing",
                examples=[
                    "how are you", "how's it going", "what's up", "how do you do",
                    "kaise ho", "kya haal hai", "all good"
                ],
                metadata={"type": "chitchat", "subtype": "wellbeing"}
            )
            
            # Route 4.5: Closure
            self.semantic_router.add_route(
                name="closure",
                examples=[
                    "ok", "okay", "got it", "understood", "alright", "sure",
                    "theek hai", "samajh gaya", "thik hai", "achha",
                    "fine", "makes sense"
                ],
                metadata={"type": "chitchat", "subtype": "closure"}
            )
            
            # Route 5: Farewell
            self.semantic_router.add_route(
                name="farewell",
                examples=[
                    "bye", "goodbye", "see you", "talk later", "take care",
                    "alvida", "khuda hafiz", "catch you later"
                ],
                metadata={"type": "chitchat", "subtype": "farewell"}
            )
        
        # PHASE 12: Initialize Validation Engine
        self.validation_engine = None
        self.validation_enabled = VALIDATION_AVAILABLE
        
        if self.validation_enabled:
            print("[VALIDATION] Validation engine enabled")

        self.graph = self._build_graph()
        
        print("[LANGGRAPH] [SUCCESS] Enhanced orchestrator initialized")
        print("[LANGGRAPH] Routes: CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY")
        print("[LANGGRAPH] Safety guardrails enabled (Phase 6)")

        self.chart_analyzer = None
        self.synthesis_engine = None
        
        if ENHANCED_ANALYSIS_AVAILABLE:
            try:
                self.chart_analyzer = ChartAnalyzer()
                self.synthesis_engine = ChartSynthesisEngine(
                    indexed_rules_path="optimized/indexed_rules.json",
                    tiered_rules_path="optimized/tiered_rules.json"
                )
                print("[ENHANCED_ANALYSIS] Engines initialized")
            except Exception as e:
                print(f"[ENHANCED_ANALYSIS] Init failed: {e}")
    
    def _build_graph(self):
        """Build LangGraph workflow."""
        print("[LANGGRAPH] Building enhanced workflow graph...")
        
        workflow = StateGraph(NakshatraState)
        
        # Add nodes
        workflow.add_node("authenticate", self._authenticate_node)
        workflow.add_node("detect_language", self._detect_language_node)
        workflow.add_node("safety_check", self._handle_safety_check_node)
        workflow.add_node("intent_classification", self._classify_intent_node)
        workflow.add_node("chitchat", self._handle_chitchat_node)
        workflow.add_node("calculation_only", self._handle_calculation_only_node)
        workflow.add_node("rag_with_calculation", self._handle_rag_with_calculation_node)
        workflow.add_node("rag_only", self._handle_rag_only_node)
        workflow.add_node("clarification", self._handle_clarification_node)
        workflow.add_node("format_response", self._format_response_node)
        
        # Set entry point
        workflow.set_entry_point("authenticate")
        
        # Connect nodes
        workflow.add_edge("authenticate", "detect_language")
        workflow.add_edge("detect_language", "safety_check")
        
        # Conditional edge from safety_check
        def route_after_safety(state: NakshatraState) -> str:
            intent = state.get('intent', '')
            if intent in ('BLOCKED', 'DATA_VALIDATION_ERROR', 'AGE_INAPPROPRIATE'):
                return "blocked"
            return "safe"

        workflow.add_conditional_edges(
            "safety_check",
            route_after_safety,
            {
                "blocked": "format_response",
                "safe": "intent_classification"
            }
        )
        
        # Route from intent classification based on intent
        def route_by_intent(state: NakshatraState) -> str:
            """Route based on classified intent."""
            intent = state.get('intent', 'CHITCHAT')
            
            if intent == 'CHITCHAT':
                return "chitchat"
            elif intent == 'CALCULATION_ONLY':
                return "calculation_only"
            elif intent == 'RAG_WITH_CALCULATION':
                return "rag_with_calculation"
            elif intent == 'RAG_ONLY':
                return "rag_only"
            elif intent == 'AMBIGUOUS':
                return "clarification"
            else:
                return "chitchat"  # Default fallback
        
        workflow.add_conditional_edges(
            "intent_classification",
            route_by_intent,
            {
                "chitchat": "chitchat",
                "calculation_only": "calculation_only",
                "rag_with_calculation": "rag_with_calculation",
                "rag_only": "rag_only",
                "clarification": "clarification"
            }
        )
        
        # All intent handlers go to format_response
        workflow.add_edge("chitchat", "format_response")
        workflow.add_edge("calculation_only", "format_response")
        workflow.add_edge("rag_with_calculation", "format_response")
        workflow.add_edge("rag_only", "format_response")
        workflow.add_edge("clarification", "format_response")
        
        # End node
        workflow.add_edge("format_response", END)
        
        # Compile
        print("[LANGGRAPH] Compiling workflow...")
        return workflow.compile()
        
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def _authenticate_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1: Authenticate user and merge session data."""
        # Check if profile is already provided (e.g., from external context)
        if state.get('user_profile'):
            print(f"[AUTH] Using provided user profile for: {state['user_id']}")
            state['authenticated'] = True
        else:
            print(f"[AUTH] Authenticating user: {state['user_id']}")
            
            # Use UserManager ONLY if it exists (Bypassed in stateless production)
            if self.user_manager and self.user_manager.user_exists(state['user_id']):
                # Load profile from DB
                user_profile = self.user_manager.get_user_profile(state['user_id'])
                if user_profile:
                    state['user_profile'] = user_profile.to_dict()
                    state['authenticated'] = True
                    print(f"[AUTH] [FALLBACK] Loaded profile from database for {state['user_id']}")
                    # Update last active
                    self.user_manager.update_last_active(state['user_id'])
            else:
                if not self.user_manager:
                    print(f"[AUTH] [INFO] Stateless mode: No UserManager provided")
                else:
                    print(f"[AUTH] [INFO] User not in DB: {state['user_id']}")
                state['user_profile'] = {}
                state['authenticated'] = False

        # SESSION DATA OVERWRITES DB DATA (Priority Tier)
        session_data = state.get('session_data')
        if session_data:
            print(f"[AUTH] [PRIORITY] Merging session mapping for {state['user_id']}")
            if not state['user_profile']:
                state['user_profile'] = {}

            # Promoting internal state keys (Priority injection)
            # NOTE: Do NOT do user_profile.update(session_data) — it pollutes user_profile
            # with chart_data, dasha_data, transit_data, summary, intent_analysis etc.
            internal_keys = ['chart_data', 'dasha_data', 'transit_data', 'detected_language', 'persona_type']
            for key in internal_keys:
                if key in session_data:
                    print(f"[AUTH] [PRIORITY] Using injected context: {key}")
                    state[key] = session_data[key]

            # Put chart_data into user_profile so _build_theory_prompt can access it
            # (RAG_ONLY path uses user_profile.get('chart_data') for Moon Sign / Lagna context)
            if state.get('chart_data') is not None:
                state['user_profile']['chart_data'] = state['chart_data']

        # TIERED HISTORY MANAGEMENT
        # Tier 1 (Priority): Use injected history
        # Tier 2 (Fallback): Load from database
        if state.get('conversation_history') is None:
            if self.user_manager:
                print(f"[AUTH] [FALLBACK] Loading conversation history from database for {state['user_id']}")
                state['conversation_history'] = self.user_manager.get_history(state['user_id'], limit=5)
            else:
                state['conversation_history'] = []
        else:
            print(f"[AUTH] [PRIORITY] Using injected conversation history ({len(state['conversation_history'])} messages)")

        return state

    def _detect_language_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1.5: Detect query language using library-based detection with LLM fallback."""
        from src.locales.language_detector import get_language_detector
        
        query = state['query']
        print(f"[LANG] Detecting language for: '{query[:30]}...'")
        
        # Use new LanguageDetector with LLM fallback
        detector = get_language_detector(llm=self.fast_llm)
        
        try:
            # Get language with confidence
            detected_lang, confidence = detector.detect_with_confidence(query)
            
            state['detected_language'] = detected_lang
            state['original_query'] = query
            
            # Log detection method
            method = "library" if confidence > 0.7 else "LLM fallback"
            print(f"[LANG] Detected: {detected_lang} ({method}, confidence: {confidence:.2f})")
            
        except Exception as e:
            print(f"[LANG] Detection error: {e}, defaulting to 'en'")
            state['detected_language'] = 'en'
            state['original_query'] = query
            
        return state
    
    def _handle_safety_check_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 2.5: Safety check BEFORE intent classification.
        Blocks harmful queries and third-party predictions.
        """
        query = state['query']
        user_profile = state.get('user_profile', {})
        conversation_history = state.get('conversation_history', [])
        
        print(f"[SAFETY] Checking query safety...")
        
        # Import safety classifier
        from src.safety import create_safety_classifier
        
        try:
            # Initialize safety classifier if not already done
            if not hasattr(self, 'safety_classifier'):
                self.safety_classifier = create_safety_classifier()
            
            # Run safety check
            safety_result = self.safety_classifier.classify(
                query=query,
                conversation_history=conversation_history
            )
            
            
            # If blocked, return template response immediately
            if safety_result.is_blocked:
                print(f"[SAFETY] BLOCKED: {safety_result.decision.reason}")
                
                # WORKAROUND: Don't block chitchat queries
                CHITCHAT_REASONS = ['greeting', 'identity', 'gratitude', 'wellbeing', 'farewell', 'closure']
                if safety_result.decision.reason in CHITCHAT_REASONS:
                    print(f"[SAFETY] Chitchat query - allowing through")
                    state['is_safe'] = True
                    return state
                
                # Continue with real blocking...
                from src.safety.templates import get_template, build_third_party_refusal
                
                # Special handling for third-party predictions
                if safety_result.decision.reason == "third_party_prediction":
                    person = safety_result.decision.keywords_matched[0] if safety_result.decision.keywords_matched else "someone else"
                    response = build_third_party_refusal(
                        person=person,
                        user_name=user_profile.get('name', 'friend')
                    )
                else:
                    # Use standard template
                    template_key = safety_result.get_template_key()
                    response = get_template(template_key) if template_key else "I cannot provide guidance on this query due to safety concerns."
                
                state['answer'] = response
                state['intent'] = 'BLOCKED'
                state['is_safe'] = False
                return state
            
            # Store safety metadata so _classify_intent_node doesn't need to re-run the classifier
            state['safety_result'] = safety_result.decision.model_dump()
            state['disclaimer_type'] = safety_result.decision.disclaimer_type
            state['is_reframed'] = False

            # Handle REFRAME: transform query here so intent classifier sees the reframed version
            if safety_result.decision.category == "REFRAME":
                print(f"[SAFETY] [REFRAME] Reframing query: {state['query']} -> {safety_result.processed_query}")
                state['original_query'] = state['query']
                state['query'] = safety_result.processed_query
                state['is_reframed'] = True

            # If conditional, flag for disclaimer
            if safety_result.needs_disclaimer:
                state['needs_disclaimer'] = safety_result.decision.disclaimer_type

            # Safe to proceed
            state['is_safe'] = True
            print(f"[SAFETY] [OK] Safe to proceed")
            
            # ════════════════════════════════════════════════════════════════
            # AGE-APPROPRIATENESS CHECK
            # ════════════════════════════════════════════════════════════════
            from src.validation.age_validator import AgeValidator

            user_profile = state.get('user_profile', {})

            # Always recompute from DOB so stale cached values (from old buggy code)
            # never produce misleading messages.  The validator is cheap (no I/O).
            dob = user_profile.get('date_of_birth')
            if dob:
                dob_validation = AgeValidator.validate_dob(dob)
                print(f"[AGE_CHECK] Validated DOB live: {dob} → {dob_validation.get('issue') or 'ok'} (age {dob_validation.get('age_years')}y)")
            else:
                dob_validation = {}

            # Check if DOB is invalid — use `is False` not `== False` so that a
            # missing/None 'valid' key (empty dict case) does not silently pass through.
            if dob_validation.get('valid') is False:
                print(f"[AGE_CHECK] Invalid DOB: {dob_validation.get('issue')}")
                state['intent'] = "DATA_VALIDATION_ERROR"
                state['answer'] = dob_validation.get('message')
                return state

            # Check age-appropriateness for query
            age_years = dob_validation.get('age_years', 0)
            query_type = AgeValidator.detect_query_type(state.get('query', ''))

            if query_type:
                print(f"[AGE_CHECK] Query type: {query_type}, User age: {age_years}")
                
                language = state.get('detected_language', 'en')
                appropriateness = AgeValidator.is_query_appropriate(
                    query_type=query_type,
                    age_years=age_years,
                    language=language
                )
                
                if not appropriateness['appropriate']:
                    print(f"[AGE_CHECK] ⚠️  Not appropriate: {appropriateness['reason']}")
                    state['intent'] = "AGE_INAPPROPRIATE"
                    state['answer'] = appropriateness['message']
                    return state  # Or your return format

                print(f"[AGE_CHECK] ✅ Age-appropriate query")

                

        except Exception as e:
            print(f"[SAFETY] [ERROR] Error in safety check: {e}")
            import traceback
            traceback.print_exc()
            # On error, allow to proceed (fail open for availability)
            state['is_safe'] = True
        
        return state

    def _classify_intent_node(self, state: NakshatraState) -> NakshatraState:
        """Node 2: Classify intent."""
        print(f"[INTENT] Classifying query: '{state['query'][:50]}...'")

        # == CONTINUATION GUARD ================================================
        # Bare follow-up phrases must reach the RAG node — not CHITCHAT/BLOCKED.
        # "Tell me more", "Why that time?", "What else?" are valid astrological
        # queries when conversation history exists.  Without this guard they
        # fall through to the semantic router (chitchat) or safety classifier
        # (SOFT_BLOCK_OUT_OF_SCOPE), producing "beyond scope" responses.
        _CONTINUATION_PHRASES = {
            'tell me more', 'what else', 'say more', 'elaborate', 'continue',
            'go on', 'and then', 'expand', 'explain more', 'more details',
            'more information', 'tell me',
        }
        _SHORT_QUESTION_STARTERS = ('why', 'how', 'when', 'what', 'where', 'who')
        q = state['query'].lower().strip().rstrip('?.')
        history = state.get('conversation_history', [])
        is_continuation = (
            any(phrase == q or q.startswith(phrase) for phrase in _CONTINUATION_PHRASES)
            or (len(q.split()) <= 2 and q.split()[0] in _SHORT_QUESTION_STARTERS) # Refined to avoid intercepting full questions
        )
        if is_continuation and len(history) > 0:
            print(f"[INTENT] [CONTINUATION] CONTINUATION GUARD: routed to RAG_ONLY (history={len(history)} msgs)")

            state['intent'] = 'RAG_ONLY'
            state['confidence'] = 0.85
            state['intent_reasoning'] = 'Bare continuation query with active conversation'
            state['is_safe'] = True
            return state
        # ─────────────────────────────────────────────────────────────────────

        # Keyword pre-check for all chitchat routes.
        # Short single-word / common phrases (especially multilingual ones) often fall
        # below the 0.7 embedding threshold because the mean route vector is diluted
        # across many diverse examples. Exact keyword matching bypasses this reliably.
        _CHITCHAT_KEYWORD_ROUTES = {
            # greeting
            'hi': 'greeting', 'hello': 'greeting', 'hey': 'greeting',
            'namaste': 'greeting', 'namaskaram': 'greeting', 'vanakkam': 'greeting',
            'hola': 'greeting', 'howdy': 'greeting', 'wassup': 'greeting',
            'sup': 'greeting', 'yo': 'greeting', 'greetings': 'greeting',
            'salaam': 'greeting', 'bonjour': 'greeting',
            'good morning': 'greeting', 'good evening': 'greeting', 'good afternoon': 'greeting',
            # gratitude
            'thanks': 'gratitude', 'thank you': 'gratitude', 'thankyou': 'gratitude',
            'appreciate it': 'gratitude', 'grateful': 'gratitude',
            'dhanyavad': 'gratitude', 'shukriya': 'gratitude',
            'dhanyawad': 'gratitude', 'shukriya-ji': 'gratitude',
            # wellbeing
            'how are you': 'wellbeing', "how's it going": 'wellbeing',
            "what's up": 'wellbeing', 'how do you do': 'wellbeing',
            'kaise ho': 'wellbeing', 'kya haal hai': 'wellbeing', 'all good': 'wellbeing',
            # farewell
            'bye': 'farewell', 'goodbye': 'farewell', 'see you': 'farewell',
            'talk later': 'farewell', 'take care': 'farewell',
            'alvida': 'farewell', 'khuda hafiz': 'farewell', 'catch you later': 'farewell',
            # closure
            'ok': 'closure', 'okay': 'closure', 'got it': 'closure',
            'understood': 'closure', 'alright': 'closure', 'sure': 'closure',
            'theek hai': 'closure', 'samajh gaya': 'closure', 'thik hai': 'closure',
            'achha': 'closure', 'fine': 'closure', 'makes sense': 'closure',
        }
        q_normalized = state['query'].lower().strip().rstrip('!.')
        _kw_route = _CHITCHAT_KEYWORD_ROUTES.get(q_normalized)
        if _kw_route:
            print(f"[INTENT] Keyword chitchat match: '{state['query']}' -> {_kw_route}")
            state['intent'] = 'CHITCHAT'
            state['confidence'] = 1.0
            state['intent_reasoning'] = f'Keyword chitchat match: {_kw_route}'
            state['chitchat_subtype'] = _kw_route
            return state

        # PHASE 11: Semantic Chitchat Router
        # Check for simple greetings semantically
        chitchat_match = None
        if self.semantic_router.model:
            chitchat_match = self.semantic_router.route(state['query'], threshold=0.7)
            
        # List of routes that should be treated as chitchat
        CHITCHAT_ROUTES = ['chitchat', 'greeting', 'identity', 'personal_profile_query', 'gratitude', 'wellbeing', 'farewell', 'closure']
        
        if chitchat_match and chitchat_match.name in CHITCHAT_ROUTES:
            print(f"[INTENT] Semantic Chitchat Match: '{state['query']}' -> {chitchat_match.name} ({chitchat_match.confidence:.2f})")
            state['intent'] = 'CHITCHAT'
            state['confidence'] = chitchat_match.confidence
            state['intent_reasoning'] = f"Semantic Chitchat Match: {chitchat_match.name}"
            # is_safe was already set by the dedicated safety_check node; don't override it
            return state

        # Safety metadata (category, disclaimer, reframe flag) was already populated
        # by the dedicated safety_check node that runs before this node.
        # Log the stored result for traceability; do NOT re-run the classifier.
        stored_safety = state.get('safety_result', {})
        if stored_safety:
            category = stored_safety.get('category', 'SAFE')
            disclaimer = stored_safety.get('disclaimer_type')
            print(f"[INTENT] Using safety result from safety_check node: {category}")
            if disclaimer:
                print(f"[INTENT] Disclaimer carried forward: {disclaimer}")
        
        result = self.intent_classifier.classify(
            query=state['query'],
            user_profile=state['user_profile'],
            conversation_history=state.get('conversation_history', [])
        )
        
        state['intent'] = result['intent']
        state['confidence'] = result['confidence']
        state['intent_reasoning'] = result.get('reasoning', '')
        state['cached'] = result.get('cached', False)
        
        cache_status = "CACHED" if state['cached'] else "LLM"
        print(f"[INTENT] [LLM] -> {state['intent']} (confidence: {state['confidence']:.2f})")
        
        return state
    
    def _handle_chitchat_node(self, state: NakshatraState) -> NakshatraState:
        """Node 3a: Handle conversational queries with semantic understanding."""
        print(f"[CHITCHAT] Response for language: {state.get('detected_language', 'en')}")
        
        user_name = state['user_profile'].get('name', 'User')
        query = state['query']
        lang = state.get('detected_language', 'en')
        conversation_history = state.get('conversation_history', [])
        
        # Import greeting functions
        from src.ai.personas import get_contextual_greeting, get_greeting
        
        # SEMANTIC ROUTING: Detect chitchat type using semantic similarity
        # First, check if the intent node already determined the subtype via keyword match.
        chitchat_match = None
        _predetected_subtype = state.get('chitchat_subtype')
        if _predetected_subtype:
            chitchat_match = type('_FakeMatch', (), {'name': _predetected_subtype, 'confidence': 1.0})()
        elif self.semantic_router.model:
            chitchat_match = self.semantic_router.route(query, threshold=0.70)

        # Handle based on semantic match
        if chitchat_match:
            match_type = chitchat_match.name
            confidence = chitchat_match.confidence
            print(f"[CHITCHAT] Semantic match: {match_type} (confidence: {confidence:.2f})")
            
            # 0. PERSONAL PROFILE QUERIES — "Mera naam kya hai?", "What is my name?"
            #    Must be checked BEFORE identity to avoid misrouting.
            if match_type == "personal_profile_query":
                print(f"[CHITCHAT] [PROFILE] Match found. Calling profile helper...")
                state['answer'] = self._answer_personal_profile_query(
                    query=query, 
                    user_profile=state['user_profile'], 
                    language=lang,
                    chart_data=state.get('chart_data')
                )
                print(f"[CHITCHAT] [PROFILE] Result length: {len(state['answer'])} characters")
                return state



            # 1. GREETING
            if match_type == "greeting":
                if len(conversation_history) > 0:
                    # Ongoing conversation: skip repetitive intro, give brief "How can I help you?"
                    loc_manager = get_localization_manager()
                    if lang == 'en':
                        state['answer'] = "Yes, I'm here. How can I assist you further?"
                    elif lang == 'hi-lat':
                        state['answer'] = "Haan, main yahaan hoon. Aur kya jaanana chahenge?"
                    else:
                        state['answer'] = get_contextual_greeting(
                            user_name=user_name,
                            conversation_length=len(conversation_history),
                            language=lang
                        )
                else:
                    # First greeting
                    greeting = get_contextual_greeting(
                        user_name=user_name,
                        conversation_length=len(conversation_history),
                        language=lang
                    )
                    state['answer'] = greeting
                return state
            
            # 2. IDENTITY QUESTIONS
            elif match_type == "identity":
                if lang == 'en':
                    state['answer'] = f"I'm NakshatraAI, a professional Vedic astrology consultant. I can analyze your birth chart, predict timing for life events, and provide guidance based on classical astrological principles."
                elif lang == 'hi-lat':
                    state['answer'] = f"Main NakshatraAI hoon, ek professional Vedic jyotish paramarshdata. Main aapki kundli ka vishleshan kar sakta hoon, jeevan ghatnaon ka samay bata sakta hoon, aur shastriya jyotish siddhanton par aadharit margdarshan de sakta hoon."
                elif lang == 'hi':
                    state['answer'] = f"मैं नक्षत्रएआई हूं, एक व्यावसायिक वैदिक ज्योतिष परामर्शदाता। मैं आपकी कुंडली का विश्लेषण कर सकता हूं और जीवन की घटनाओं का समय बता सकता हूं।"
                else:
                    # Fallback to English
                    state['answer'] = f"I'm NakshatraAI, a professional Vedic astrology consultant."
                return state
            
            # 3. GRATITUDE
            elif match_type == "gratitude":
                if lang == 'en':
                    state['answer'] = f"You're welcome, {user_name}! Feel free to ask anything about your chart or astrological concepts."
                elif lang == 'hi-lat':
                    state['answer'] = f"Aapka swagat hai, {user_name}! Apne chart ya jyotish avdharanao ke bare mein kuch bhi poochh sakte hain."
                elif lang == 'hi':
                    state['answer'] = f"आपका स्वागत है, {user_name}! अपने चार्ट या ज्योतिष अवधारणाओं के बारे में कुछ भी पूछ सकते हैं।"
                else:
                    state['answer'] = f"You're welcome, {user_name}!"
                return state
            
            # 4. WELLBEING CHECK
            elif match_type == "wellbeing":
                if lang == 'en':
                    state['answer'] = f"I'm doing well, thank you for asking, {user_name}! As an AI, I'm always ready to help you explore your birth chart and astrological insights. How can I assist you today?"
                elif lang == 'hi-lat':
                    state['answer'] = f"Main theek hoon, poochne ke liye dhanyavad, {user_name}! Aaj main aapki kaise madad kar sakta hoon?"
                else:
                    state['answer'] = f"I'm doing well, {user_name}! How can I help you today?"
                return state
            
            # 5. FAREWELL
            elif match_type == "farewell":
                if lang == 'en':
                    state['answer'] = f"Goodbye, {user_name}! Feel free to return anytime you have questions about your chart or astrology. May the stars guide you well!"
                elif lang == 'hi-lat':
                    state['answer'] = f"Alvida, {user_name}! Jab bhi aapke chart ya jyotish ke baare mein sawal ho, wapas aa sakte hain. Tare aapka margdarshan karen!"
                else:
                    state['answer'] = f"Goodbye, {user_name}! Take care!"
                return state
                
            # 6. CLOSURE
            elif match_type == "closure":
                if lang == 'en':
                    state['answer'] = f"Happy to help, {user_name}!"
                elif lang == 'hi-lat':
                    state['answer'] = f"Bahut badiya, {user_name}!"
                else:
                    state['answer'] = f"Happy to help, {user_name}!"
                return state

        # Multilingual/Complex path: Use fast LLM with persona (Fallback for no match or unhandled type)
        print(f"[CHITCHAT] No specific semantic match or unhandled type. Using LLM fallback.")
        try:
            from src.ai.personas import get_persona
            persona_type = state['user_profile'].get('preferred_system', 'vedic')
            persona = get_persona(persona_type)
            
            system_prompt = persona.get_system_prompt(
                user_name=user_name,
                language=lang,
                llm=self.fast_llm
            )

            # Add conversational tone guidelines
            from src.safety.templates import CONVERSATIONAL_TONE_SYSTEM_PROMPT
            system_prompt += f"\n\n{CONVERSATIONAL_TONE_SYSTEM_PROMPT}"

            # Inject constitution — same rules apply in chitchat as in all other paths
            constitution = get_constitution_injection()
            system_prompt = f"{system_prompt}\n\n{constitution}"
            
            # Map language code to descriptive name
            loc_manager = get_localization_manager()
            lang_name = loc_manager.get_language_name(lang)
            
            if '-lat' in lang:
                script_instruction = f"CRITICAL: You MUST respond in {lang_name} using ROMAN SCRIPT (English alphabet) only. Do NOT use any {lang_name.split(' (')[0]} characters or Devanagari script. Example: 'Main theek hoon' instead of 'मैं ठीक हूं'."
            else:
                script_instruction = f"Respond entirely in {lang_name} (NATIVE SCRIPT ONLY)."
            
            # PHASE 6: Tiered History Support
            history_context = ""
            if state.get('conversation_history'):
                history_turns = state['conversation_history'][-3:]
                from src.ai.prompt_builder import PromptBuilder
                builder = PromptBuilder()
                formatted_history = builder._format_conversation(history_turns)
                history_context = f"\nCONVERSATION CONTEXT:\n{formatted_history}\n"

            # Build user profile context for LLM (safety net for novel personal queries)
            _up = state.get('user_profile', {})
            _bd = _up.get('birth_details', {})
            _loc = _bd.get('location', {})
            
            # Support both nested and flat structures
            uname = _up.get('name', '')
            udob = _up.get('date_of_birth') or _bd.get('date', '')
            utob = _up.get('time_of_birth') or _bd.get('time', '')
            uloc = _up.get('place_of_birth') or _loc.get('city') or _loc.get('address', '')
            
            _profile_lines = []
            if uname: _profile_lines.append(f"User name: {uname}")
            if udob: _profile_lines.append(f"Date of birth: {udob}")
            if utob: _profile_lines.append(f"Time of birth: {utob}")
            if uloc: _profile_lines.append(f"Birth place: {uloc}")
            
            # Add signs if available (from profile or state)
            us_sign = _up.get('sun_sign') or (state.get('chart_data', {}).get('planets', {}).get('SUN', {}).get('sign', '') if state.get('chart_data') else '')
            um_sign = _up.get('moon_sign') or (state.get('chart_data', {}).get('planets', {}).get('MOON', {}).get('sign', '') if state.get('chart_data') else '')
            uasc = _up.get('ascendant') or (state.get('chart_data', {}).get('lagna') if state.get('chart_data') else '')
            
            if us_sign: _profile_lines.append(f"Sun sign: {us_sign}")
            if um_sign: _profile_lines.append(f"Moon sign: {um_sign}")
            if uasc: _profile_lines.append(f"Ascendant (Lagna): {uasc}")
            
            user_profile_context = (
                "USER PROFILE (use this if the user asks about their own details):\n"
                + "\n".join(_profile_lines)
            ) if _profile_lines else "User profile details are not available yet."

            prompt = f"""{system_prompt}
            
    {history_context}
    User: "{state['query']}"

    INSTRUCTIONS:
    1. Provide a warm, empathetic, professional response.
    2. If the user greets and it's the start of the conversation, greet back. If it's an ongoing conversation, SKIP greetings and get straight to the point.
    3. If the user asks about previous messages or personal context, ANSWER DIRECTLY based on CONVERSATION CONTEXT.
    4. If the question is entirely outside astrology and NOT in history, politely explain your scope.
    5. {script_instruction}
    6. Keep it brief (under 60 words).

    {user_profile_context}

    Response:"""
            
            llm_response = self.fast_llm.invoke(prompt)
            state['answer'] = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            print(f"[CHITCHAT] [LLM] Result: {len(state['answer'])} chars")
            
        except Exception as e:
            print(f"[CHITCHAT] Error generating response: {e}")
            state['answer'] = get_greeting(lang)

        return state


    # ------------------------------------------------------------------
    # PERSONAL PROFILE QUERY HELPER
    # ------------------------------------------------------------------
    def _answer_personal_profile_query(
        self, query: str, user_profile: dict, language: str, chart_data: Optional[Dict] = None
    ) -> str:
        """
        Answer questions about the USER's own details (name, DOB, location, sign)
        using the structured user_profile dict — no LLM guesswork.
        """
        print(f"[PROFILE_DEBUG] Answering profile query: {query}")
        name = user_profile.get('name', '')


        
        # Support both nested 'birth_details' and flat structure from Redis
        bd = user_profile.get('birth_details', {})
        dob = bd.get('date', '') or user_profile.get('date_of_birth', '')
        tob = bd.get('time', '') or user_profile.get('time_of_birth', '')
        
        location = bd.get('location', {})
        city = location.get('city', '') or location.get('address', '') or user_profile.get('place_of_birth', '')
        
        # Signs from profile or chart_data fallback
        sun_sign = user_profile.get('sun_sign', '')
        moon_sign = user_profile.get('moon_sign', '')
        ascendant = user_profile.get('ascendant', '')
        
        if chart_data:
            if not sun_sign:
                sun_sign = chart_data.get('planets', {}).get('SUN', {}).get('sign', '')
            if not moon_sign:
                moon_sign = chart_data.get('planets', {}).get('MOON', {}).get('sign', '')
            if not ascendant:
                # Support both 'lagna' top level and 'ascendant' dict
                ascendant = chart_data.get('lagna') or chart_data.get('ascendant', {}).get('sign', '')


        q = query.lower()

        # --- Name questions ---
        naam_triggers = [
            'naam kya', 'name kya', 'naam batao', 'what is my name',
            "what's my name", 'do you know my name', 'मेरा नाम',
        ]
        if any(t in q for t in naam_triggers):
            if name:
                if language in ('hi', 'hi-lat'):
                    return f"Aapka naam **{name}** hai! 😊"
                return f"Your name is **{name}**! 😊"
            else:
                if language in ('hi', 'hi-lat'):
                    return "Mujhe aapka naam nahi pata. Kya aap bata sakte hain?"
                return "I don't have your name on file yet. Could you tell me?"

        # --- DOB / Birth date questions ---
        dob_triggers = [
            'date of birth', 'dob', 'birth date', 'janam kab', 'date of birth kya',
            'meri dob', 'मेरी जन्म तिथि',
        ]
        if any(t in q for t in dob_triggers):
            if dob:
                if language in ('hi', 'hi-lat'):
                    return f"Aapki date of birth **{dob}** hai."
                return f"Your date of birth on file is **{dob}**."
            else:
                if language in ('hi', 'hi-lat'):
                    return "Mujhe aapki DOB nahi pata abhi. Kya aap bata sakte hain?"
                return "I don't have your date of birth on file. Could you share it?"

        # --- Location questions ---
        loc_triggers = [
            'kahan paida', 'birthplace', 'birth place', 'city am i from',
            'where was i born', 'birth city', 'main kahan se', 'janmsthan',
            'place of birth', 'location of birth',
        ]

        if any(t in q for t in loc_triggers):
            if city:
                if language in ('hi', 'hi-lat'):
                    return f"Aapka janam sthan **{city}** hai."
                return f"Your birth place on file is **{city}**."
            else:
                if language in ('hi', 'hi-lat'):
                    return "Mujhe aapki birthplace nahi pata. Kya aap bata sakte hain?"
                return "I don't have your birth location. Could you share it?"

        # --- Sign questions ---
        sign_triggers = [
            'sun sign', 'moon sign', 'ascendant', 'lagna', 'rashi', 'sign kya', 'meri rashi',
        ]
        if any(t in q for t in sign_triggers):
            parts = []
            if sun_sign:
                parts.append(f"Sun sign: **{sun_sign}**")
            if moon_sign:
                parts.append(f"Moon sign: **{moon_sign}**")
            if ascendant:
                parts.append(f"Ascendant: **{ascendant}**")
            if parts:
                return "Your signs — " + ", ".join(parts) + "."

        # --- Generic fallback: summarise everything we know ---
        summary_parts = []
        if name:
            summary_parts.append(f"Name: **{name}**")
        if dob:
            summary_parts.append(f"DOB: **{dob}**")
        if tob:
            summary_parts.append(f"Time of birth: **{tob}**")
        if city:
            summary_parts.append(f"Birth place: **{city}**")
        if sun_sign:
            summary_parts.append(f"Sun sign: **{sun_sign}**")
        if moon_sign:
            summary_parts.append(f"Moon sign: **{moon_sign}**")

        if summary_parts:
            intro = "Yeh hai aapki profile:" if language in ('hi', 'hi-lat') else "Here's what I have on file for you:"
            return intro + "\n" + " | ".join(summary_parts)

        # Nothing known
        if language in ('hi', 'hi-lat'):
            return (
                "Abhi mere paas aapki details nahi hain. "
                "Kya aap apni janam tithi, samay aur jagah bata sakte hain?"
            )
        return (
            "I don't have your details on file yet. "
            "Could you share your date of birth, time, and place?"
        )
        
    def _extract_topic(self, query: str) -> str:
        """Extract the main topic from an ambiguous query."""
        import re
        
        # Planets
        planets = ['jupiter', 'venus', 'mars', 'saturn', 'mercury', 'sun', 'moon', 'rahu', 'ketu']
        # Houses
        houses = ['1st house', '2nd house', '3rd house', '4th house', '5th house', 
                  '6th house', '7th house', '8th house', '9th house', '10th house', 
                  '11th house', '12th house']
        
        query_lower = query.lower()
        
        for planet in planets:
            if planet in query_lower:
                return planet.capitalize()
        
        for house in houses:
            if house in query_lower:
                return f"the {house}"
        
        return "this topic"
    
    def _handle_clarification_node(self, state: NakshatraState) -> NakshatraState:
        """Node 3b: Handle ambiguous queries by asking for clarification."""
        print(f"[CLARIFICATION] Asking user to specify intent")
        
        user_name = state['user_profile'].get('name', 'User')
        query = state['query']
        lang = state.get('detected_language', 'en')
        
        # Extract the topic (e.g., "Jupiter", "7th house")
        topic = self._extract_topic(query)
        
        # Build clarification prompt (English for now, multilingual in Phase 3)
        if lang == 'en':
            state['answer'] = f"""Namaste, {user_name}! 🙏

I can help you with **{topic}** in two ways:

1️⃣ **General Explanation** (Theory)
   -> Learn about {topic} in Vedic astrology (classical principles)

2️⃣ **Personalized Analysis** (Your Chart)
   -> Understand {topic} specifically in YOUR birth chart

**Which would you prefer?**
- Reply with "1" or "general" for theory
- Reply with "2" or "personalized" for your chart analysis

Or, you can rephrase your question to be more specific! 😊"""
        else:
            # Fallback to English for non-English languages (Phase 3 will add multilingual templates)
            state['answer'] = f"""Namaste, {user_name}! 🙏

I can help you with **{topic}** in two ways:

1️⃣ **General Explanation** (Theory)
2️⃣ **Personalized Analysis** (Your Chart)

**Which would you prefer?**
Reply with "1" for theory or "2" for personalized analysis."""
        
        print(f"[CLARIFICATION] Topic: {topic}, Language: {lang}")
        return state
    
    def _get_or_calculate_chart(self, user_id: str, user_profile: Dict, state: Optional[NakshatraState] = None) -> Tuple[Optional[Dict], Optional[VedicChart]]:
        """
        Helper to get chart data, prioritizing:
        1. Injected state data (Stateless Production Mode)
        2. Cached data in user_profile
        3. Fresh calculation (Development/Fallback)
        """
        # TIER 1: Priority Injection (Redis/API)
        if state and state.get('chart_data'):
            print(f"[CALC] [PRIORITY] Using injected chart data for {user_id}")
            return state['chart_data'], None

        # TIER 2: Database Cache (Fallback)
        cached_json = user_profile.get('birth_chart_cache')
        if cached_json:
            try:
                print(f"[CALC] [FALLBACK] Using cached chart for {user_id}. Deserializing...")
                chart_data_dict = json.loads(cached_json)
                # Reconstruct the full VedicChart object for deeper calculations if needed
                full_chart = VedicChart.from_dict(chart_data_dict)
                
                # We also need the tool-compatible dict formatting for the LLM
                # (The tool 'calculate_vedic_birth_chart' provides this formatting)
                # For now, we'll re-calculate the tool-dict from the full_chart to ensure consistency
                from src.tools.tools import calculate_vedic_chart
                # Mock the tool logic to get the formatted dict from existing chart
                # Actually, simpler: have a helper in tools.py to format a chart
                return None, full_chart # We'll let the node handle the dict conversion
            except Exception as e:
                print(f"[CACHE] [WARN] Failed to load cached chart: {e}")
        
        # No cache or error: Calculate fresh
        print(f"[CACHE] No cache found. Calculating fresh chart for {user_id}...")
        try:
            # Standardize field names (UserProfile uses date_of_birth)
            dob = user_profile.get('date_of_birth')
            tob = user_profile.get('time_of_birth', '12:00:00')
            lat = user_profile.get('latitude')
            lon = user_profile.get('longitude')
            tz = user_profile.get('timezone', 'Asia/Kolkata')
            
            if not dob or lat is None or lon is None:
                print(f"[CACHE] [WARN] Missing birth data for {user_id}: dob={dob}, lat={lat}, lon={lon}")
                return None, None
                
            # Combine date and time
            try:
                dt_str = f"{dob} {tob}"
                birth_datetime = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Fallback if only date is provided or format is slightly different
                birth_datetime = datetime.fromisoformat(dob) if isinstance(dob, str) else dob
            
            # We use the VedicEngine directly to get the full object
            engine = VedicEngine()
            full_chart = engine.generate_chart(
                birth_date=birth_datetime,
                latitude=lat,
                longitude=lon,
                timezone_str=tz
            )
            
            # Chart caching in DB removed (stateless Redis architecture)
            # Chart data is available in Redis session for the duration of the session
            
            return None, full_chart
        except Exception as e:
            print(f"[CACHE] [ERROR] Fresh calculation failed: {e}")
            return None, None

    def _handle_calculation_only_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3b: CALCULATION_ONLY - Return raw chart data without interpretation.
        Uses VedicEngine, NO RAG, NO LLM interpretation.
        """
        print("[CALCULATION_ONLY] Generating raw chart data")
        
        user_profile = state['user_profile']
        query = state['query'].lower()
        
        # Check if user has birth data
        if not user_profile.get('date_of_birth'):
            state['answer'] = "I don't have your birth details. Please update your profile with date, time, and place of birth."
            return state
        
        # FIX #4: Check if user is asking about their profile/birth data
        profile_keywords = ['dob', 'date of birth', 'birth date', 'birthday', 
                           'birth time', 'time of birth', 'birth place', 
                           'place of birth', 'born', 'when was i born', 
                           'where was i born', 'what time was i born']
        
        if any(keyword in query for keyword in profile_keywords):
            # User asking about their own birth details - provide direct answer
            print("[CALCULATION_ONLY] User asking about profile data")
            
            response = f"""**Your Birth Details:**

📅 **Date of Birth:** {user_profile.get('date_of_birth', 'Not available')}
⏰ **Time of Birth:** {user_profile.get('time_of_birth', 'Not available')}
📍 **Place of Birth:** {user_profile.get('place_of_birth', 'Not available')}

These details are used to calculate your Vedic birth chart with precise planetary positions.

**What would you like to explore?**
• View your complete birth chart
• Understand your planetary placements
• Check current dashas (planetary periods)
• See upcoming transits"""
            
            state['answer'] = response
            return state
        
        try:
            # Calculate or load from cache (Bypass if state['chart_data'] exists)
            chart_data_from_helper, full_chart = self._get_or_calculate_chart(state['user_id'], user_profile, state)
            
            # If we got a dict back directly (bypass mode), use it
            if isinstance(chart_data_from_helper, dict) and not full_chart:
                chart_data = chart_data_from_helper
            elif full_chart:
                # Standard conversion from object
                chart_data = serialize_vedic_chart(full_chart)
            else:
                state['answer'] = "Could not generate or load your birth chart. Please check your birth details."
                return state
            
            print(f"[CALCULATION_ONLY] Chart: Lagna={chart_data.get('lagna', {}).get('sign', 'Unknown')}, Rashi={chart_data.get('planets', {}).get('MOON', {}).get('sign', 'Unknown')}")
            
            # Use LLM to extract only what was asked for
            extraction_prompt = f"""You are a data extraction assistant. The user asked: "{state['query']}"
 
USER'S BIRTH DETAILS:
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}
 
COMPLETE BIRTH CHART DATA:
• Lagna (Ascendant): {chart_data.get('lagna', {}).get('sign', 'Unknown')}
• Moon Sign (Rashi): {chart_data.get('planets', {}).get('MOON', {}).get('sign', 'Unknown')}
• Sun Sign: {chart_data.get('planets', {}).get('SUN', {}).get('sign', 'Unknown')}
• Moon Nakshatra: {chart_data.get('planets', {}).get('MOON', {}).get('nakshatra', 'Unknown')}
 
Planetary Positions:
• Sun: {chart_data.get('planets', {}).get('SUN', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('SUN', {}).get('house', '?')})
• Moon: {chart_data.get('planets', {}).get('MOON', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('MOON', {}).get('house', '?')})
• Mars: {chart_data.get('planets', {}).get('MARS', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('MARS', {}).get('house', '?')})
• Mercury: {chart_data.get('planets', {}).get('MERCURY', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('MERCURY', {}).get('house', '?')})
• Jupiter: {chart_data.get('planets', {}).get('JUPITER', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('JUPITER', {}).get('house', '?')})
• Venus: {chart_data.get('planets', {}).get('VENUS', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('VENUS', {}).get('house', '?')})
• Saturn: {chart_data.get('planets', {}).get('SATURN', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('SATURN', {}).get('house', '?')})
• Rahu: {chart_data.get('planets', {}).get('RAHU', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('RAHU', {}).get('house', '?')})
• Ketu: {chart_data.get('planets', {}).get('KETU', {}).get('sign', 'Unknown')} (House {chart_data.get('planets', {}).get('KETU', {}).get('house', '?')})
 
INSTRUCTIONS:
1. Extract ONLY the specific information the user asked for
2. If they asked for birth details (date/time/place), provide those
3. If they asked for "sun sign", return ONLY the sun sign
4. If they asked for "moon sign", return ONLY the moon sign
5. If they asked for "my chart" or "birth chart", return the complete formatted chart
6. Keep the response concise and direct
7. DO NOT add interpretation or predictions

Provide a concise answer:"""

            response = self.llm.invoke(extraction_prompt)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
            # Store chart data for potential follow-up questions
            state['chart_data'] = chart_data

            # Calculate current dasha if missing
            if not state.get('dasha_data'):
                try:
                    print("[CALCULATION_ONLY] Calculating dasha...")
                    dasha_tool = self.calculation_tools.get('calculate_current_dasha')
                    if dasha_tool:
                        dasha_data = dasha_tool.invoke({
                            "date_of_birth": user_profile.get('date_of_birth'),
                            "time_of_birth": user_profile.get('time_of_birth'),
                            "latitude": user_profile.get('latitude'),
                            "longitude": user_profile.get('longitude')
                        })
                        if "error" not in dasha_data:
                            state['dasha_data'] = dasha_data
                except Exception as e:
                    print(f"[CALCULATION_ONLY] Dasha calculation error: {e}")

            # Calculate current transits if missing
            if not state.get('transit_data'):
                try:
                    print("[CALCULATION_ONLY] Calculating transits...")
                    transit_tool = self.calculation_tools.get('calculate_current_transits')
                    if transit_tool:
                        transit_data = transit_tool.invoke({})
                        if "error" not in transit_data:
                            state['transit_data'] = transit_data
                except Exception as e:
                    print(f"[CALCULATION_ONLY] Transit calculation error: {e}")

        except Exception as e:
            print(f"[ERROR] Calculation failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error generating chart: {e}"
        
        return state
    
    def _handle_rag_with_calculation_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3c: RAG_WITH_CALCULATION - Personalized predictions with validation.
        
        PHASE 12: Now includes classical validation engine integration
        
        Flow:
        1. Calculate birth chart, dashas, and transits
        1.5. VALIDATE chart against classical rules (NEW)
        2. Retrieve relevant knowledge from vector DB
        3. Build prompt with validation constraints
        4. Generate LLM response
        """
        print("[RAG_WITH_CALCULATION] Personalized prediction flow with validation")
        
        user_profile = state['user_profile']
        
        try:
            # ================================================================
            # STEP 1: Calculate user's chart
            # ================================================================
            if user_profile.get('date_of_birth'):
                print("[RAG_WITH_CALCULATION] Step 1: Calculating user's chart...")
                
                if not state.get('chart_data'):
                    try:
                        # Calculate or load from cache
                        chart_data_from_helper, full_chart = self._get_or_calculate_chart(
                            state['user_id'], user_profile, state
                        )
                        
                        if isinstance(chart_data_from_helper, dict):
                            state['chart_data'] = chart_data_from_helper
                        elif full_chart:
                            state['chart_data'] = serialize_vedic_chart(full_chart)
                            
                        if state.get('chart_data'):
                            print(f"[RAG_WITH_CALCULATION] Chart ready: Lagna={state['chart_data'].get('lagna') or state['chart_data'].get('ascendant', {}).get('rashi', 'Unknown')}")
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Chart calculation error: {e}")

                # Calculate current dasha (UN-NESTED from chart check)
                if not state.get('dasha_data'):
                    try:
                        print("[RAG_WITH_CALCULATION] Calculating dasha...")
                        dasha_tool = self.calculation_tools.get('calculate_current_dasha')
                        if dasha_tool:
                            dasha_data = dasha_tool.invoke({
                                "date_of_birth": user_profile.get('date_of_birth'),
                                "time_of_birth": user_profile.get('time_of_birth'),
                                "latitude": user_profile.get('latitude'),
                                "longitude": user_profile.get('longitude')
                            })
                            if "error" not in dasha_data:
                                state['dasha_data'] = dasha_data
                                print(f"[RAG_WITH_CALCULATION] Dasha: {dasha_data.get('dasha_sequence', 'Unknown')}")
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Dasha calculation error: {e}")
                
                # Calculate current transits (UN-NESTED from chart check)
                if not state.get('transit_data'):
                    try:
                        print("[RAG_WITH_CALCULATION] Calculating transits...")
                        transit_tool = self.calculation_tools.get('calculate_current_transits')
                        if transit_tool:
                            transit_data = transit_tool.invoke({})
                            if "error" not in transit_data:
                                state['transit_data'] = transit_data
                                print(f"[RAG_WITH_CALCULATION] Transits for {transit_data.get('date', 'current')}")
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Transit calculation error: {e}")

            else:
                print("[RAG_WITH_CALCULATION] No birth data - proceeding without chart")

            # ================================================================
            # STEP 1.25: ENHANCED CHART ANALYSIS (PHASE 13 - NEW)
            # ================================================================
            enhanced_analysis = None
            synthesis = None
            
            if state.get('chart_data') and ENHANCED_ANALYSIS_AVAILABLE and self.chart_analyzer:
                try:
                    print("[ENHANCED_ANALYSIS] Calculating dignities, lords, aspects...")
                    enhanced_analysis = self.chart_analyzer.analyze_chart(state['chart_data'])
                    
                    # Log key findings
                    print(f"[ENHANCED_ANALYSIS] Found {len(enhanced_analysis['dignities'])} planetary dignities")
                    print(f"[ENHANCED_ANALYSIS] Calculated {len(enhanced_analysis['house_lords'])} house lordships")
                    print(f"[ENHANCED_ANALYSIS] Mapped {len(enhanced_analysis['aspects'])} aspect patterns")
                    
                    # Store in state for later use
                    state['enhanced_analysis'] = enhanced_analysis
                    
                except Exception as e:
                    print(f"[ENHANCED_ANALYSIS] Error: {e}")

            # ================================================================
            # STEP 1.5: VALIDATE CHART (PHASE 12 - NEW)
            # ================================================================
            if state.get('chart_data') and VALIDATION_AVAILABLE:
                try:
                    print("[VALIDATION] Running validation...")
                    
                    # Detect query type with LLM confirmation
                    query_type = detect_query_type(
                        state['query'], 
                        llm=self.fast_llm if hasattr(self, 'fast_llm') else None,
                        use_llm_confirmation=True
                    )
                    state['validation_query_type'] = query_type
                    
                    # Skip validation for general questions
                    if query_type == 'general':
                        print(f"[VALIDATION] Skipping validation for general question")
                    else:
                        # Determine tier (optimized for live chat)
                        tier = determine_validation_tier(state['query'])
                        print(f"[VALIDATION] Query: {query_type}, Tier: {tier}")
                        
                        # Get or create validation engine
                        if not hasattr(self, 'validation_engine'):
                            self.validation_engine = None
                        
                        if self.validation_engine is None:
                            try:
                                from pathlib import Path
                                rules_path = Path("optimized/tiered_rules.json")
                                
                                if rules_path.exists():
                                    print("[VALIDATION] Initializing engine...")
                                    self.validation_engine = VedicValidationEngineV2(
                                        tiered_rules_path=str(rules_path),
                                        indexed_rules_path="optimized/indexed_rules.json"
                                    )
                                    print("[VALIDATION] [OK] Engine ready")
                                else:
                                    print("[VALIDATION] Rules file not found")
                            except Exception as e:
                                print(f"[VALIDATION] Init failed: {e}")
                        
                        if self.validation_engine:
                            # Prepare chart for validation
                            val_chart = prepare_chart_for_validation(
                                chart_data=state['chart_data'],
                                dasha_data=state.get('dasha_data', {}),
                                transit_data=state.get('transit_data', {})
                            )
                            
                            # Run validation with timeout for live chat
                            val_result = self.validation_engine.validate(
                                chart_data=val_chart,
                                query_type=query_type,
                                tier=tier,
                                stage=None,
                                live_chat=True,
                                timeout_sec=None
                            )
                            
                            # Store results
                            state['validation_result'] = {
                                'query_type': val_result.query_type,
                                'overall_strength': val_result.overall_strength,
                                'can_proceed': val_result.can_proceed,
                                'critical_failures': [
                                    {
                                        'rule_id': f.rule_id,
                                        'rule_name': f.rule_name,
                                        'reason': f.reason,
                                        'recommendation': f.recommendation,
                                        'classical_ref': f.classical_ref
                                    }
                                    for f in val_result.critical_failures
                                ]
                            }
                            
                            state['validation_strength'] = val_result.overall_strength
                            state['validation_can_proceed'] = val_result.can_proceed
                            
                            print(f"[VALIDATION] [OK] Strength: {val_result.overall_strength:.1f}/10")
                            print(f"[VALIDATION] Critical failures: {len(val_result.critical_failures)}")
                            
                            # HARD HALT CHECK (only for extreme cases)
                            if should_hard_halt(val_result.overall_strength, val_result.critical_failures):
                                print(f"[VALIDATION] [STOP] HARD HALT - Refusing prediction")
                                state['answer'] = build_halt_response(
                                    state['validation_result'],
                                    state['user_profile'],
                                    state.get('detected_language', 'en')
                                )
                                return state  # Exit early without generating prediction
                            
                            # Build disclaimer for weak charts (soft warnings)
                            if val_result.overall_strength < 6.0:
                                state['validation_disclaimer'] = build_validation_disclaimer(
                                    val_result.overall_strength,
                                    query_type,
                                    val_result.critical_failures
                                )
                                print(f"[VALIDATION] Added disclaimer for weak chart")
                
                except Exception as e:
                    print(f"[VALIDATION] Error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Don't block on validation errors - proceed without validation
            
            # ================================================================
            # STEP 1.75: RULE-BASED SYNTHESIS (PHASE 13 - NEW)
            # ================================================================
            if ENHANCED_ANALYSIS_AVAILABLE and enhanced_analysis:
                try:
                    # Get query_type from validation or detect it
                    query_type_for_synthesis = state.get('validation_query_type')
                    if not query_type_for_synthesis and state.get('chart_data'):
                        try:
                            query_type_for_synthesis = detect_query_type(
                                state['query'],
                                llm=self.fast_llm if hasattr(self, 'fast_llm') else None,
                                use_llm_confirmation=True
                            )
                        except:
                            query_type_for_synthesis = 'general'
                    
                    if query_type_for_synthesis and query_type_for_synthesis != 'general' and self.synthesis_engine:
                        print(f"[SYNTHESIS] Building rule-based analysis for {query_type_for_synthesis}...")
                        
                        synthesis = self.synthesis_engine.synthesize(
                            chart_data=state['chart_data'],
                            chart_enhanced=enhanced_analysis,
                            query_type=query_type_for_synthesis,
                            validation_result=state.get('validation_result')
                        )
                        
                        state['synthesis'] = synthesis
                        
                        print(f"[SYNTHESIS] ✓ Identified {len(synthesis.get('chart_strengths', []))} strengths")
                        print(f"[SYNTHESIS] ✓ Identified {len(synthesis.get('chart_challenges', []))} challenges")
                        print(f"[SYNTHESIS] ✓ Detected {len(synthesis.get('yogas_detected', []))} yogas")
                        print(f"[SYNTHESIS] ✓ Analyzed {len(synthesis.get('key_houses', []))} key houses")
                    else:
                        print(f"[SYNTHESIS] Skipped - query_type is '{query_type_for_synthesis}'")
                        
                except Exception as e:
                    print(f"[SYNTHESIS] Error: {e}")
                    import traceback
                    traceback.print_exc()

            # ================================================================
            # STEP 2: Retrieve Relevant Knowledge
            # ================================================================
            print("[RAG_WITH_CALCULATION] Step 2: Retrieving knowledge...")
            
            knowledge_chunks = state.get('knowledge_chunks') or []

            if not knowledge_chunks and self.hybrid_retriever:
                # Enhance query for better retrieval if we have chart data
                retrieval_query = state['query']
                if state.get('chart_data'):
                    c = state['chart_data']
                    lagna = c.get('lagna', {}).get('sign') or c.get('ascendant', {}).get('sign', 'Unknown')
                    moon_sign = c.get('moon_sign') or c.get('planets', {}).get('MOON', {}).get('sign', 'Unknown')
                    retrieval_query += f" (Lagna: {lagna}, Rashi: {moon_sign})"

                knowledge_chunks = self.hybrid_retriever.retrieve(
                    query=retrieval_query,
                    intent="RAG_WITH_CALCULATION",
                    top_k=RAGConfig.get_top_k(content_type='interpretation'),
                    language=state.get('detected_language', 'en')
                )
            elif not knowledge_chunks:
                print("[RAG_WITH_CALCULATION] No retriever - proceeding with zero knowledge")
            
            state['knowledge_chunks'] = knowledge_chunks
            print(f"[RAG_WITH_CALCULATION] Retrieved {len(knowledge_chunks)} chunks")
            
            # ================================================================
            # STEP 3: Build Prompt (with validation constraints)
            # ================================================================
            if state.get('chart_data'):
                prompt = self._build_prediction_prompt(
                    query=state['query'],
                    chart_data=state['chart_data'],
                    dasha_data=state.get('dasha_data', {}),
                    transit_data=state.get('transit_data', {}),
                    knowledge_chunks=knowledge_chunks,
                    user_profile=user_profile,
                    conversation_history=state.get('conversation_history', []),
                    language=state.get('detected_language', 'en'),
                    validation_result=state.get('validation_result'),
                    enhanced_analysis=state.get('enhanced_analysis'),  # NEW
                    synthesis=state.get('synthesis')  # NEW
                )
            else:
                # Chart calculation failed — do NOT hallucinate chart-specific details.
                # Fall back to RAG_ONLY mode and tell the LLM explicitly that birth chart
                # data is unavailable so it provides general guidance only.
                print("[RAG_WITH_CALCULATION] [WARN] No chart data — falling back to RAG_ONLY prompt")
                no_chart_notice = (
                    "\n\nIMPORTANT: Birth chart data could not be calculated for this user (likely due to an "
                    "invalid date of birth format). Do NOT invent, assume, or state any planetary positions, "
                    "house lords, lagna, rashi, dashas, or nakshatra placements. "
                    "Provide ONLY general Vedic astrology guidance based on the classical texts provided. "
                    "If the user asks about their personal chart, politely inform them that their birth data "
                    "needs to be corrected first."
                    "\n\nMOBILE RESPONSE FORMAT: Maximum 3-4 sentences (100-150 words). "
                    "Be direct and concise. No meta-commentary."
                )
                if self.prompt_builder:
                    prompt = self.prompt_builder.build_prompt(
                        query=state['query'],
                        intent="RAG_ONLY",
                        user_profile=state['user_profile'],
                        knowledge_chunks=knowledge_chunks,
                        conversation_history=state.get('conversation_history', []),
                        language=state.get('detected_language', 'en')
                    )
                    # Inject the no-chart notice into the system part (before the query marker)
                    if "====USER_QUERY_MARKER====" in prompt:
                        parts = prompt.split("====USER_QUERY_MARKER====")
                        prompt = parts[0] + no_chart_notice + "\n\n====USER_QUERY_MARKER====" + parts[1]
                    else:
                        prompt = prompt + no_chart_notice
                else:
                    print("[RAG_WITH_CALCULATION] [ERROR] No prompt_builder - using fallback template")
                    prompt = (
                        f"You are a Vedic astrology assistant.{no_chart_notice}\n\n"
                        f"====USER_QUERY_MARKER====\n\"{state['query']}\""
                    )
            
            # ================================================================
            # STEP 4: Build Messages Array with Conversation History
            # ================================================================
            messages = []

            # Add system prompt
            messages.append({
                "role": "system",
                "content": prompt.split("====USER_QUERY_MARKER====")[0].strip()  # System part
            })

            # Add conversation history (CRITICAL for context!)
            conversation_history = state.get('conversation_history', [])
            if conversation_history:
                formatted_history = self._format_conversation_for_llm(conversation_history)
                messages.extend(formatted_history)
                print(f"[RAG_WITH_CALCULATION] Including {len(formatted_history)} previous messages")

            # Add current query with chart context
            user_prompt = "USER_QUERY:" + prompt.split("====USER_QUERY_MARKER====")[1]
            messages.append({
                "role": "user",
                "content": user_prompt
            })

            # ================================================================
            # STEP 5: Generate LLM Response with Full Context
            # ================================================================
            print(f"[LLM] Sending {len(messages)} messages to LLM")
            response = self.llm.invoke(messages)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            print(f"[ERROR] RAG_WITH_CALCULATION failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error during astrological analysis: {e}"
        
        return state
    
    def _handle_rag_only_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3d: RAG_ONLY - General astrology theory questions.
        Uses RAG + LLM interpretation ONLY. NO chart calculations.
        
        For questions like: "What does Mars in 7th house mean?", "Explain the 10th house"
        """
        print("[RAG_ONLY] General theory question - no chart calculation needed")
        
        try:
            knowledge_chunks = state.get('knowledge_chunks') or []

            if not knowledge_chunks and self.hybrid_retriever:
                knowledge_chunks = self.hybrid_retriever.retrieve(
                    query=state['query'],
                    intent="RAG_ONLY",
                    top_k=RAGConfig.get_top_k(content_type='general'),  # Auto: 8 chunks
                    language=state.get('detected_language', 'en')
                )
            elif not knowledge_chunks:
                 print("[RAG_ONLY] [WARN] No retriever provided and no chunks injected.")
            
            state['knowledge_chunks'] = knowledge_chunks
            print(f"[RAG_ONLY] Retrieved {len(knowledge_chunks)} knowledge chunks")
            
            # Step 2: Build prompt for general theory
            prompt = self._build_theory_prompt(
                query=state['query'],
                knowledge_chunks=knowledge_chunks,
                user_profile=state['user_profile'],
                language=state.get('detected_language', 'en')
            )
            
            if not knowledge_chunks or len(knowledge_chunks) == 0:
                print("[RAG_ONLY] [WARN] No chunks - using fallback")
                
                # Quick fallback for common queries
                query_lower = state['query'].lower()
                
                if 'jupiter' in query_lower and '7th' in query_lower:
                    state['answer'] = """Jupiter in the 7th house is highly auspicious for marriage and partnerships. This placement indicates:

            - A wise and supportive spouse
            - Harmonious relationships
            - Prosperity through partnerships
            - Beneficial business collaborations

            This is general astrological knowledge. For personalized insights based on your specific chart, let me analyze your birth details."""
                    return state
                
                elif 'moon' in query_lower and ('10th' in query_lower or 'career' in query_lower):
                    state['answer'] = """Moon's placement relates to career through emotional connection to work and public image. The 10th house specifically governs career, reputation, and professional achievements.

            For detailed insights about your career prospects, I can analyze your complete birth chart with current planetary periods."""
                    return state
                
                # If no fallback, continue to original "no sources" message

            # GROUNDING SAFEGUARD: If no sources, refuse to answer
            if prompt is None:
                user_name = state['user_profile'].get('name', 'User')
                prefix = f"Namaste, {user_name}." if not conversation_history else "I apologize,"
                state['answer'] = f"""{prefix}

I apologize, but I could not find relevant information in the classical astrology texts to answer your question about "{state['query']}".

**Why this happened:**
• The knowledge base may not contain information on this specific topic
• The query might need to be rephrased for better results
• The vectorDB may not have been loaded correctly

**What you can do:**
1. Try rephrasing your question with more specific terms
2. Check if the knowledge base has been properly ingested
3. Ask about a related topic that may be covered in the texts

I prefer to say "I don't know" rather than provide information not grounded in classical sources.

🙏 Thank you for understanding."""
                print("[RAG_ONLY] [GROUNDED] Refused to answer without sources")
                return state
            
            # Step 3: Generate response with LLM (only if we have sources!)
            # Build messages with conversation history
            messages = []

            # System prompt
            messages.append({
                "role": "system", 
                "content": prompt.split("====USER_QUERY_MARKER====")[0].strip()
            })

            # Add conversation history
            conversation_history = state.get('conversation_history', [])
            if conversation_history:
                formatted_history = self._format_conversation_for_llm(conversation_history)
                messages.extend(formatted_history)
                print(f"[RAG_ONLY] Including {len(formatted_history)} previous messages")

            # Current query
            user_prompt = "USER_QUERY:" + prompt.split("====USER_QUERY_MARKER====")[1]
            messages.append({
                "role": "user",
                "content": user_prompt
            })

            # Invoke with full context
            print(f"[LLM] Sending {len(messages)} messages to LLM")
            response = self.llm.invoke(messages)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            print(f"[ERROR] RAG_ONLY path failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error during theory explanation: {e}"
        
        return state
    
    def _build_chart_anchor_block(self, chart_data: Dict) -> str:
        """
        Build a hard-constraint anchor block injected at the TOP of every system
        prompt that has chart data.

        Purpose: prevent the LLM from substituting its training-knowledge Lagna
        (e.g. treating the Sun sign as the Lagna) for the calculated one.
        """
        if not chart_data:
            return ""

        house_lords_block = self._compute_house_lords_block(chart_data)
        if not house_lords_block:
            return ""

        lagna_data = chart_data.get("lagna") or chart_data.get("ascendant", {})
        lagna_sign = lagna_data.get("sign") or lagna_data.get("rashi", "Unknown")
        lagna_deg  = lagna_data.get("degree", 0.0)

        sun_data  = chart_data.get("planets", {}).get("SUN", {})
        sun_sign  = sun_data.get("sign", "Unknown")
        moon_data = chart_data.get("planets", {}).get("MOON", {})
        moon_sign = moon_data.get("sign", "Unknown")

        _SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        _LORDS = {"Aries":"MARS","Taurus":"VENUS","Gemini":"MERCURY","Cancer":"MOON",
                  "Leo":"SUN","Virgo":"MERCURY","Libra":"VENUS","Scorpio":"MARS",
                  "Sagittarius":"JUPITER","Capricorn":"SATURN","Aquarius":"SATURN",
                  "Pisces":"JUPITER"}
        _SANSKRIT = {"Mesha":"Aries","Vrishabha":"Taurus","Mithuna":"Gemini",
                     "Karka":"Cancer","Simha":"Leo","Kanya":"Virgo","Tula":"Libra",
                     "Vrischika":"Scorpio","Dhanu":"Sagittarius","Makara":"Capricorn",
                     "Kumbha":"Aquarius","Meena":"Pisces"}

        lagna_norm = _SANSKRIT.get(lagna_sign, lagna_sign)
        if lagna_norm not in _SIGNS:
            return f"VERIFIED LAGNA: {lagna_sign}\n{house_lords_block}"

        lagna_idx = _SIGNS.index(lagna_norm)

        def house_lord(h):
            sign = _SIGNS[(lagna_idx + h - 1) % 12]
            return _LORDS.get(sign, "?"), sign

        all_lords = ["SUN","MOON","MARS","MERCURY","JUPITER","VENUS","SATURN"]

        # Compact all-12-house quick-reference table
        quick_ref_lines = []
        for h in range(1, 13):
            hl, hs = house_lord(h)
            quick_ref_lines.append(f"  H{h:2d} ({hs:13}): {hl}")
        quick_ref_text = "\n".join(quick_ref_lines)

        # Focused forbidden claims for the 6 most commonly discussed houses
        # (1=self, 5=children/intellect, 7=marriage, 9=fortune, 10=career, 11=gains)
        _ORDINALS = {1:"1st",2:"2nd",3:"3rd",5:"5th",7:"7th",9:"9th",10:"10th",11:"11th"}
        _DOMAINS  = {1:"self/lagna",5:"children",7:"marriage",9:"fortune",10:"career",11:"gains"}
        focus_houses = [1, 5, 7, 9, 10, 11]
        forbidden_lines = []
        for h_num in focus_houses:
            hl, hs = house_lord(h_num)
            ord_str = _ORDINALS.get(h_num, f"{h_num}th")
            dom_str = _DOMAINS.get(h_num, "")
            for p in all_lords:
                if p != hl:
                    forbidden_lines.append(
                        f"  X NEVER say {p:8} is the {ord_str} lord ({dom_str}) — correct: {hl} ({hs})"
                    )
        forbidden_text = "\n".join(forbidden_lines)

        return f"""
=======================================================================
VERIFIED BIRTH CHART — OVERRIDE YOUR TRAINING KNOWLEDGE
These values are from Swiss Ephemeris. They SUPERSEDE anything you
believe about this birth date from your training data.
=======================================================================

LAGNA (ASCENDANT): {lagna_sign} {lagna_deg:.1f} degrees
WARNING: Sun is in {sun_sign} — SUN SIGN ≠ LAGNA. Do NOT use Sun sign as Lagna.
Three distinct values — Moon sign: {moon_sign} | Lagna: {lagna_sign} | Sun: {sun_sign}

{house_lords_block}

QUICK-REFERENCE ALL-12 HOUSE LORDS (from Lagna — single source of truth):
{quick_ref_text}

CROSS-REFERENCE MANDATE:
Before stating ANY house-lord, dignity, or timing claim, verify it against
the tables above. Format every lord reference as:
  "Nth house (domain) lord [PLANET]"
  e.g. "7th house (Marriage & Partnership) lord VENUS"
If the computed data does not contain evidence for a claim, write
"data not available" — never substitute training-knowledge defaults.

FORBIDDEN CLAIMS — NEVER state any of the following:
{forbidden_text}

LAGNA ANCHOR RULE: Every house-lord claim must match the HOUSE LORDS table.
If you are about to say a planet is the Nth lord and it does not match
this table, STOP and use the correct lord from the table above.
=======================================================================
"""

    def _build_theory_prompt(self, query: str, knowledge_chunks: list, user_profile: dict, language: str = "en") -> str:
        """Build prompt for general astrology theory explanations."""
        
        # GROUNDING SAFEGUARD: Refuse to answer without sources
        if not knowledge_chunks or len(knowledge_chunks) == 0:
            return None  # Signal to caller: no sources, don't answer
        
        # Get persona based on language
        try:
            from src.ai.personas import get_persona
            persona = get_persona(user_profile.get('preferred_system', 'vedic'))
            system_prompt = persona.get_system_prompt(
                user_name=user_profile.get('name', 'User'),
                language=language,
                llm=self.fast_llm
            )
        except:
            system_prompt = "You are an expert Vedic astrologer explaining astrological concepts."
        
        # PHASE 10: Inject Constitution
        constitution = get_constitution_injection()
        system_prompt = f"{system_prompt}\n\n{constitution}"

        # ── CHART ANCHOR: inject at top so house lords are grounded ───────────
        _up_cd = user_profile.get("chart_data") or {}
        chart_anchor_theory = self._build_chart_anchor_block(_up_cd)
        if chart_anchor_theory:
            system_prompt = chart_anchor_theory + "\n\n" + system_prompt

        # Format knowledge context WITH SOURCE ATTRIBUTION
        context_parts = []
        for i, chunk in enumerate(knowledge_chunks[:4], 1):
            source = chunk.metadata.get('source_book', 'Unknown') if hasattr(chunk, 'metadata') else 'Unknown'
            chapter = chunk.metadata.get('chapter', '') if hasattr(chunk, 'metadata') else ''
            verse = chunk.metadata.get('verse_number', '') if hasattr(chunk, 'metadata') else ''
            
            # Format with book name prominently
            source_citation = f"[{source}"
            if chapter:
                source_citation += f" - Chapter {chapter}"
            if verse:
                source_citation += f", Verse {verse}"
            source_citation += "]"
            
            content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
            context_parts.append(f"{source_citation}\n{content}")
        
        context = "\n\n".join(context_parts)
        
        # Map language code to descriptive name for LLM
        loc_manager = get_localization_manager()
        lang_name = loc_manager.get_language_name(language)

        # Build script instruction for language enforcement
        if '-lat' in language:
            script_instruction = f"Respond in {lang_name} using ROMAN ALPHABET only (no native script)."
        elif language != 'en':
            script_instruction = f"Respond entirely in {lang_name} (native script)."
        else:
            script_instruction = "Respond in clear, professional English."

        # Use dynamic instruction builder (adapts to query content and verbosity preference)
        instructions = self._build_response_instructions(
            query=query,
            lang_name=lang_name,
            script_instruction=script_instruction,
            mode='theory'
        )

        _p = user_profile or {}
        _cd = _p.get('chart_data') or {}
        _planets = _cd.get('planets', {})

        # Build planet list block when chart data is available — prevents LLM from
        # inferring house lords or placements from its training knowledge.
        planet_block = ""
        if _cd and _planets:
            planet_block = self._compute_house_lords_block(_cd)
            _planet_lines = ["\nBIRTH CHART DATA (use ONLY these positions for any chart-specific reasoning):"]
            _order = ['SUN', 'MOON', 'MARS', 'MERCURY', 'JUPITER', 'VENUS', 'SATURN', 'RAHU', 'KETU']
            for _pl in _order:
                _pd = _planets.get(_pl, {})
                if _pd:
                    _retro = '  [RETRO]' if _pd.get('retrograde') else ''
                    _combust = '  [COMBUST]' if _pd.get('combust') else ''
                    _pada = _pd.get('nakshatra_pada', '?')
                    _nksh = _pd.get('nakshatra', 'N/A')
                    _deg = _pd.get('degree', 0.0)
                    _dignity = _pd.get('dignity', {}).get('status', '') if isinstance(_pd.get('dignity'), dict) else ''
                    _planet_lines.append(
                        f"• {_pl:8}: {_pd.get('sign', 'N/A'):12} H{_pd.get('house', '?')} {_deg:.1f}° | {_nksh} P{_pada} | {_dignity}{_retro}{_combust}"
                    )
            if planet_block:
                _planet_lines.append("")
                _planet_lines.append(planet_block)
            planet_block = "\n".join(_planet_lines)

        prompt = f"""You are an expert Vedic astrologer explaining astrological concepts.

USER PROFILE:
• Name: {_p.get('name', 'User')}
• Date of Birth: {_p.get('date_of_birth', 'Unknown')}
• Time of Birth: {_p.get('time_of_birth', 'Unknown')}
• Place of Birth: {_p.get('place_of_birth', 'Unknown')}
• Moon Sign: {_planets.get('MOON', {}).get('sign', _p.get('moon_sign', 'Unknown'))}
• Lagna (Ascendant): {_cd.get('lagna', {}).get('sign', _p.get('lagna', 'Unknown'))}
{planet_block}

====USER_QUERY_MARKER====
"{query}"

RELEVANT KNOWLEDGE FROM CLASSICAL TEXTS:
{context}

{system_prompt}

{instructions}"""
        
        return prompt
    
    def _verify_response_safety(self, query: str, answer: str, chart_data: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        [CRITIC] Verify if the answer adheres to the Astrologer's Constitution.
        Returns: (is_safe, feedback)
        """
        constitution = get_constitution_injection()
        
        data_context = ""
        if chart_data:
            planets = chart_data.get('planets', {})
            # Use 'sign' key (primary) with 'current_sign' as fallback
            formatted_planets = ", ".join([
                f"{p}: H{d.get('house', '?')} {d.get('sign') or d.get('current_sign', 'Unknown')}"
                for p, d in planets.items()
            ])
            # Compute house lords as ground-truth so verifier can catch wrong-lord claims
            house_lords_truth = self._compute_house_lords_block(chart_data)
            data_context = (
                f"\nCALCULATED CHART DATA (GROUND TRUTH — verify response against these):\n"
                f"PLANETS: {formatted_planets}\n"
                f"{house_lords_truth}\n"
            )

        prompt = f"""You are the Guardian of the Astrologer's Constitution.
Your job is to specifically check if the following AI response violates any Immutable Rules.

THE CONSTITUTION:
{constitution}
{data_context}
USER QUERY: "{query}"
AI RESPONSE: "{answer}"

TASK:
1. Check for DEATH predictions (Violates Rule 2).
2. Check for FATALISM (Violates Rule 2).
3. Check for SYCOPHANCY (Agreeing with user against facts - Rule 3).
4. Check for SCOPE violations (Medical/Financial advice - Rule 4).
5. Check for HALLUCINATED PLACEMENTS. If Chart Data is provided above, ensure the response does NOT contradict it (e.g., saying Sun is in Aries when Data says Libra).
6. Check for WRONG HOUSE LORDS. If House Lords are provided above, ensure the response does NOT name an incorrect lord for any house (e.g., claiming Venus is the 7th lord when the chart shows Jupiter rules H7).

OUTPUT FORMAT:
Return ONLY "SAFE" if no violations found.
Return "UNSAFE: <reason>" if violations found.
"""
        try:
            # Use fast LLM if available, else main LLM
            llm_to_use = self.fast_llm or self.llm
            if not llm_to_use:
                return True, "No LLM for validation"
                
            _raw = llm_to_use.invoke(prompt)
            response = _raw.content.strip() if hasattr(_raw, 'content') else str(_raw)
            
            if response.startswith("SAFE"):
                return True, ""
            else:
                return False, response.replace("UNSAFE:", "").strip()
                
        except Exception as e:
            print(f"[CRITIC] Validation failed: {e}")
            return True, f"Validation error: {e}"  # Fail open to avoid blocking users on technical error
            
    def _validate_response_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3.5: The Critic - Verification Loop.
        Checks generated answer against safety constitution.
        """
        print("[CRITIC] Validating response safety...")
        
        # Skip validation for calculation-only or if already validated
        if state.get('intent') == 'CALCULATION_ONLY' or state.get('is_safe', False) is True: 
            return state

        answer = state.get('answer', '')
        query = state.get('query', '')
        chart_data = state.get('chart_data')
        
        is_safe, feedback = self._verify_response_safety(query, answer, chart_data)
        
        state['is_safe'] = is_safe
        state['validation_attempts'] += 1
        
        if not is_safe:
            print(f"[CRITIC] [FAIL] Unsafe response detected: {feedback}")
            state['validation_feedback'] = feedback
            
            # Simple Self-Correction (Rewrite)
            # If this is the first failure, try to fix it.
            if state['validation_attempts'] <= 1:
                print("[CRITIC] Attempting to rewrite safely...")
                constitution = get_constitution_injection()
                rewrite_prompt = f"""The following response violated the Astrologer's Constitution.
VIOLATION: {feedback}

THE CONSTITUTION:
{constitution}

ORIGINAL QUERY: "{query}"
UNSAFE RESPONSE: "{answer}"

TASK: Rewrite the response to be strict, safe, and adhering to the Constitution. 
Retain the astrological data but remove the violating content (e.g., remove death prediction, reframe fatalism, refuse medical advice).
"""
                try:
                    state['answer'] = self._call_llm(state, rewrite_prompt)
                    state['is_safe'] = True # Assume fixed (single loop for now)
                    print("[CRITIC] [OK] Response rewritten.")
                except Exception as e:
                    state['error'] = f"Rewriting failed: {e}"
                    state['answer'] = "I cannot answer this query due to safety guidelines."
            else:
                # If we failed twice, block it.
                state['answer'] = "I must decline to answer this request as it violates my safety constitution regarding harmful or fatalistic predictions."
        else:
            print("[CRITIC] [OK] Response is SAFE.")
            
        return state

    def _format_response_node(self, state: NakshatraState) -> NakshatraState:
        """Node 4: Format final response."""
        
        if not state.get('error'):
            final_response = state.get('answer', '')
            
            # PHASE 10.5: Disclaimer Injection
            disclaimer_type = state.get('disclaimer_type')
            if disclaimer_type:
                detected_lang = state.get('detected_language', 'en')
                disclaimer_text = get_disclaimer(disclaimer_type, language=detected_lang, llm=self.fast_llm)
                final_response = f"{final_response}\n\n{disclaimer_text}"
            
            # PHASE 12: Validation Disclaimer Injection
            validation_disclaimer = state.get('validation_disclaimer')
            if validation_disclaimer:
                final_response = f"{final_response}{validation_disclaimer}"
                print("[FORMATTING] Added validation disclaimer")

            # PHASE 10.5: Reframe Intro Injection
            if state.get('is_reframed', False):
                from src.safety.templates import format_reframe_response
                reframe_intro = format_reframe_response(state.get('original_query', ''), state.get('query', ''))
                final_response = f"{reframe_intro}{final_response}"
            
            state['answer'] = final_response
            print("[FORMATTING] Formatted final response.")
            
        return state
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    

    def _detect_persona_preference(self, query: str) -> str:
        """
        Detect if user prefers Western or Vedic persona based on query.
        Default is 'vedic'.
        """
        q = query.lower()
        western_triggers = [
            'western', 'tropical', 'psychological', 'archetype', 
            'evolutionary', 'sun sign', 'rising sign'
        ]
        
        if any(trigger in q for trigger in western_triggers):
            return 'western'
            
        return 'vedic'

    def _user_wants_detail(self, query: str) -> bool:
        """
        Detect if user is asking for more detail or elaboration.
        Semantic approach: checks for intent to expand, not just specific phrases.
        Covers English, Hindi, Hinglish, and Tamil.
        """
        q = query.lower().strip()

        # Direct expansion signals (any language)
        expansion_signals = [
            # English
            'tell me more', 'more detail', 'more information', 'elaborate',
            'explain in detail', 'explain more', 'explain fully',
            'detailed explanation', 'full explanation', 'complete explanation',
            'in depth', 'in-depth', 'give me more', 'expand on',
            'break it down', 'walk me through', 'go deeper', 'dig deeper',
            'what else', 'tell me everything', 'full breakdown', 'more please',
            'yes', 'yes please', 'sure', 'go ahead', 'please explain',
            # Hindi / Hinglish
            'aur batao', 'aur bataiye', 'aur samjhao', 'seedha batao',
            'detail mein', 'detail se', 'vistar se', 'poora batao',
            'aur detail', 'haan', 'bilkul', 'haan bataiye',
            # General short affirmatives after a bot offer
            'details', 'detail', 'yes, please', 'please',
        ]

        return any(sig in q for sig in expansion_signals)

    def _get_domain_pratyantar_spotlight(self, query: str) -> str:
        """Returns a domain-specific block telling the LLM which Pratyantar planets
        to prioritize from the upcoming_pratyantardashas list for this query type.
        Each domain has a distinct priority list to prevent all queries from
        converging on the same Jupiter Pratyantar window."""
        q = query.lower()

        if any(w in q for w in ['marriage', 'marry', 'married', 'shaadi', 'shadi', 'vivah', 'wedding',
                                  'partner', 'love', 'spouse', 'husband', 'wife', 'rishta', 'relationship',
                                  'pyaar', 'prem', 'milega', 'milegi', 'life partner',
                                  'kesi hogi', 'kaisi hogi', 'kesa hoga', 'kaisa hoga',
                                  'groom', 'bride', 'dulha', 'dulhan', 'shaadi kab', 'vivah kab']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Marriage/Partner):\n"
                "   1st: VENUS Pratyantar — primary karaka for marriage\n"
                "   2nd: 7th house lord's Pratyantar (see HOUSE LORDS table above)\n"
                "   3rd: Jupiter only as secondary confirmation\n"
                "   ❌ Do NOT use Jupiter as the primary timing window for marriage.\n"
                "   ⚠ Also describe the partner's nature from 7th house sign and planets in H7.\n"
            )

        if any(w in q for w in ['ghar', 'makaan', 'makan', 'home', 'house', 'flat', 'plot',
                                  'real estate', 'zameen', 'naya ghar', 'new home', 'ghar lena',
                                  'ghar kharidna', 'buy house', 'buy home', 'bhumi', 'land',
                                  'renovation', 'construction']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Home/Property):\n"
                "   1st: MOON Pratyantar — primary karaka for home and domestic life\n"
                "   2nd: MARS Pratyantar — karaka for land and property\n"
                "   3rd: 4th house lord's Pratyantar (see HOUSE LORDS table above)\n"
                "   ❌ Do NOT reuse the Jupiter/Venus Pratyantar cited for marriage or career.\n"
                "   ❌ Jupiter is only relevant here if it is the 4th house lord.\n"
            )

        if any(w in q for w in ['foreign', 'abroad', 'videsh', 'travel', 'yatra', 'immigration',
                                  'visa', 'overseas', 'bahar', 'foreign land', 'settle abroad', 'job abroad']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Foreign Travel/Abroad):\n"
                "   1st: RAHU Pratyantar — primary karaka for foreign connection\n"
                "   2nd: 9th house lord's Pratyantar (check HOUSE LORDS table — NOT always Jupiter)\n"
                "   3rd: 12th house lord's Pratyantar (check HOUSE LORDS table)\n"
                "   ❌ Use Jupiter ONLY if HOUSE LORDS table lists Jupiter as 9th or 12th lord.\n"
                "   ❌ Do NOT default to Jupiter generically for foreign travel.\n"
            )

        if any(w in q for w in ['career', 'job', 'business', 'naukri', 'profession', 'promotion',
                                  'kaam', 'vyapar', 'work', 'salary', 'office', 'interview', 'appointment']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Career/Job):\n"
                "   1st: SATURN Pratyantar — karaka for sustained career and work\n"
                "   2nd: SUN Pratyantar — karaka for authority and status\n"
                "   3rd: 10th house lord's Pratyantar (see HOUSE LORDS table)\n"
                "   ❌ Do NOT use Venus or Jupiter as the primary timing window for career.\n"
            )

        if any(w in q for w in ['child', 'children', 'baby', 'pregnancy', 'bachha', 'bacche',
                                  'santan', 'offspring', 'conceive', 'delivery']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Children/Progeny):\n"
                "   1st: JUPITER Pratyantar — primary karaka for children\n"
                "   2nd: MOON Pratyantar — karaka for nurturing and motherhood\n"
                "   3rd: 5th house lord's Pratyantar (see HOUSE LORDS table)\n"
            )

        if any(w in q for w in ['money', 'wealth', 'paisa', 'dhan', 'rich', 'invest', 'finance',
                                  'loan', 'debt', 'savings', 'profit', 'loss']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Wealth/Finance):\n"
                "   1st: VENUS Pratyantar — karaka for wealth and luxury\n"
                "   2nd: 2nd house lord's Pratyantar (see HOUSE LORDS table)\n"
                "   3rd: 11th house lord's Pratyantar (see HOUSE LORDS table)\n"
                "   ❌ Jupiter is a secondary trigger only — not the primary wealth window.\n"
            )

        if any(w in q for w in ['health', 'illness', 'sick', 'disease', 'bimari', 'sehat', 'swasth',
                                  'hospital', 'surgery', 'pain', 'accident', 'injury']):
            return (
                "\n⭐ PRATYANTAR PRIORITY FOR THIS QUERY (Health):\n"
                "   Watch: SATURN, MARS, RAHU, KETU Pratyantar — stress and health challenge indicators\n"
                "   Check 6th house lord and 8th house lord Pratyantar periods.\n"
                "   ❌ Do NOT cite Jupiter or Venus as primary health timing windows.\n"
            )

        return ""

    def _build_response_instructions(
        self,
        query: str,
        lang_name: str,
        script_instruction: str,
        mode: str = 'theory'  # 'theory' or 'prediction'
    ) -> str:
        """
        Build adaptive response instructions based on what the user is actually asking.
        Returns fuller instructions for detail requests, concise for standard queries.
        Dynamically adds domain-specific guidance (career, timing, health, compatibility).
        """
        q = query.lower()
        wants_detail = self._user_wants_detail(query)

        # Domain-specific timing guidance — tells the LLM which Pratyantar windows
        # and Gochara factors are relevant for THIS specific query type.
        domain_hints = []

        # ── Generic timing hint (always add when timing is asked) ──────────────
        if any(w in q for w in ['when', 'kab', 'timing', 'which year', 'how long',
                                  'kitne din', 'which month', 'period', 'dasha', 'antardasha',
                                  'kab hoga', 'kab milega', 'kab hogi']):
            domain_hints.append(
                "TIMING PRECISION: Use the Pratyantar Dasha windows (listed above under 'Upcoming Pratyantardashas') "
                "combined with the Gochara factors to narrow timing to a specific 1-4 week window. "
                "Do NOT just repeat the Antardasha range — that is a multi-month bracket, not a specific date. "
                "State the specific Pratyantar that aligns with the relevant Gochara factor as the PEAK timing."
            )

        # ── Marriage / relationship ─────────────────────────────────────────────
        if any(w in q for w in ['marriage', 'marry', 'married', 'shaadi', 'shadi', 'vivah', 'wedding',
                                  'partner', 'love', 'spouse', 'husband', 'wife', 'rishta', 'relationship',
                                  'bypass', 'saat phere', 'pyaar', 'prem', 'milega', 'milegi',
                                  'life partner', 'kesi hogi', 'kaisi hogi', 'kesa hoga', 'kaisa hoga',
                                  'groom', 'bride', 'dulha', 'dulhan', 'shaadi kab', 'vivah kab']):
            domain_hints.append(
                "MARRIAGE & PARTNER ANALYSIS — Answer ALL parts of the user's question:\n"
                "  PART A — PARTNER QUALITIES (always include, regardless of exact question wording):\n"
                "  • 7th house SIGN: directly describes the partner's personality and nature\n"
                "  • Planets IN 7th house: each planet modifies the partner's traits\n"
                "  • 7th lord sign and house: adds nuance to partner's character and circumstances of meeting\n"
                "  • Venus sign (for male chart) / Jupiter sign (for female chart): partner's personal qualities\n"
                "  ⚠ ALWAYS describe what the partner will be like from these placements — do NOT skip this.\n"
                "  PART B — CHART FACTORS FOR TIMING:\n"
                "  • 7th lord: which house is it placed in? Its dignity? Is it afflicted by Saturn/Rahu/Ketu?\n"
                "  • 2nd house (Wealth & Family): its lord, condition — supports marital stability\n"
                "  • 5th house (Children & Intellect): its lord — romance, love, attraction\n"
                "  • 11th house (Gains & Desires): its lord — fulfillment of marital desire\n"
                "  PART C — TIMING (use this priority order):\n"
                "  1. Find VENUS Pratyantar first — Venus is the primary marriage karaka.\n"
                "  2. If no Venus Pratyantar in current AD, check 7th house lord's Pratyantar (see HOUSE LORDS table).\n"
                "  3. Cross-check: Is Jupiter Gochar in H5, H7, or H9 from natal Moon? (Gochara section)\n"
                "  4. Is there a Sade Sati? If yes, marriage may be delayed or come with challenges.\n"
                "  5. Use Jupiter Pratyantar ONLY as a secondary confirmatory trigger — NEVER as the primary marriage window.\n"
                "  6. State the specific Pratyantar date range as the peak window, NOT the full Antardasha range.\n"
                "  ⚠ You MUST cover Part A (partner description) AND Part C (timing) in every relationship response.\n"
                "  ⚠ You MUST discuss at least H7, H2, and H5 lords from the computed table — not just H7 alone."
            )

        # ── Career / job / business ────────────────────────────────────────────
        if any(w in q for w in ['career', 'job', 'business', 'naukri', 'profession', 'promotion',
                                  'kaam', 'vyapar', 'work', 'income', 'salary', 'office',
                                  'interview', 'selection', 'appointment']):
            domain_hints.append(
                "CAREER ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS (check each from birth chart positions above):\n"
                "  • 10th house (Career & Status): its lord, sign, planets placed there\n"
                "  • 10th lord: which house is it placed in? Its dignity? Retrograde? Combust?\n"
                "  • 6th house (Health & Enemies): its lord — governs service, job, daily work\n"
                "  • 2nd house (Wealth & Family): its lord — income, accumulated wealth\n"
                "  • 11th house (Gains & Desires): its lord — income gains, career fulfilment\n"
                "  • 1st house (Self & Personality): lagnesh — personal initiative and effort\n"
                "  • Sun (natural karaka of career/status): its sign, house, dignity\n"
                "  • Saturn (karaka of profession and hard work): its sign, house, dignity\n"
                "  TIMING (use this priority order):\n"
                "  1. Find the Saturn, Sun, or Mercury Pratyantar in the upcoming Pratyantardasha list.\n"
                "  2. Cross-check: Jupiter Gochar in H6, H10, or H11 from natal Moon supports career gains.\n"
                "  3. Is Ashtama Shani active? If yes, job changes face obstacles; advise patience.\n"
                "  4. Check 10th house lord's Pratyantar period.\n"
                "  5. State the specific Pratyantar start–end date as the peak career window.\n"
                "  ⚠ You MUST discuss at least H10, H6, and H2 lords from the computed table — not just H10 alone."
            )

        # ── Foreign travel / abroad ────────────────────────────────────────────
        if any(w in q for w in ['foreign', 'abroad', 'videsh', 'travel', 'yatra', 'immigration',
                                  'visa', 'overseas', 'bahar', 'country', 'settle abroad',
                                  'job abroad', 'foreign land']):
            domain_hints.append(
                "FOREIGN TRAVEL ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS (check each from birth chart positions above):\n"
                "  • 9th house (Luck & Dharma): its lord, sign, planets — long journeys, fortune abroad\n"
                "  • 9th lord: which house is it placed in? Its dignity? (9th lord ≠ Jupiter by default — check table)\n"
                "  • 12th house (Losses & Moksha): its lord, sign — foreign lands, settlements abroad\n"
                "  • 12th lord: which house is it placed in? Planets in H12?\n"
                "  • 3rd house (Courage & Siblings): short journeys, initiative for travel\n"
                "  • Rahu: sign and house from Lagna — strong karaka for foreign connections\n"
                "  • Jupiter: sign and house — opportunity and protection in foreign lands\n"
                "  TIMING (use this priority order):\n"
                "  1. Find RAHU Pratyantar first — Rahu is the primary karaka for foreign/overseas connection.\n"
                "  2. Find 9th house lord's Pratyantar (check HOUSE LORDS table — 9th lord is NOT always Jupiter).\n"
                "  3. Find 12th house lord's Pratyantar (check HOUSE LORDS table).\n"
                "  4. Use Jupiter Pratyantar ONLY if HOUSE LORDS table shows Jupiter as 9th or 12th lord for this Lagna.\n"
                "  5. Check: Is Rahu transiting H9 or H12 from Lagna? (Gochara section)\n"
                "  6. State the specific Pratyantar date range as the peak window. DO NOT cite the full Antardasha range.\n"
                "  ⚠ You MUST discuss H9 and H12 lords from the computed table. NEVER substitute Jupiter as 9th lord "
                "unless the HOUSE LORDS table explicitly shows Jupiter as the 9th lord for this Lagna."
            )

        # ── Children ───────────────────────────────────────────────────────────
        if any(w in q for w in ['child', 'children', 'baby', 'pregnancy', 'bachha', 'bacche',
                                  'santan', 'offspring', 'conceive', 'delivery']):
            domain_hints.append(
                "CHILDREN ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS (check each from birth chart positions above):\n"
                "  • 5th house (Children & Intellect): its lord, sign, planets placed there\n"
                "  • 5th lord: which house is it placed in? Its dignity? Afflicted?\n"
                "  • 9th house (Luck & Dharma): its lord — bhagya for children, dharma\n"
                "  • Jupiter (natural karaka of children): its sign, house, dignity\n"
                "  • Moon: its condition — emotional readiness, nurturing\n"
                "  TIMING (use this priority order):\n"
                "  1. Find the Jupiter or Moon Pratyantar in the upcoming Pratyantardasha list.\n"
                "  2. Jupiter Gochar in H5 from natal Moon is the strongest trigger for children.\n"
                "  3. Check 5th house lord's Pratyantar period.\n"
                "  4. State the specific Pratyantar date range as the peak window.\n"
                "  ⚠ You MUST discuss H5 and H9 lords from the computed table — not just Jupiter generically."
            )

        # ── Home / property / real estate ──────────────────────────────────────
        if any(w in q for w in ['ghar', 'makaan', 'makan', 'home', 'house', 'flat', 'plot', 'property',
                                  'real estate', 'zameen', 'naya ghar', 'new home', 'ghar lena',
                                  'ghar kharidna', 'buy house', 'buy home', 'property buy',
                                  'renovation', 'construction', 'bhumi', 'land']):
            domain_hints.append(
                "HOME & PROPERTY ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS (check each from birth chart positions above):\n"
                "  • 4th house (Home & Mother): its lord, sign, planets placed there — PRIMARY house for home/property\n"
                "  • 4th lord: which house is it placed in? Its dignity? Retrograde?\n"
                "  • 2nd house (Wealth & Family): its lord — fixed assets, family wealth\n"
                "  • 11th house (Gains & Desires): its lord — fulfillment of desire for property\n"
                "  • Moon (natural karaka of home and mother): its sign, house, dignity\n"
                "  • Mars (natural karaka of land and property): its sign, house, dignity\n"
                "  • Saturn: long-term fixed assets, construction timelines\n"
                "  TIMING (use this priority order):\n"
                "  1. Find MOON Pratyantar first — Moon is the primary karaka for home and domestic life.\n"
                "  2. Find MARS Pratyantar — karaka for land, property, and construction.\n"
                "  3. Find 4th house lord's Pratyantar (see HOUSE LORDS table).\n"
                "  4. Jupiter Gochar in H4 from natal Moon strongly supports home purchase.\n"
                "  5. State the specific Pratyantar date range as the peak window — NOT the full Antardasha range.\n"
                "  ⚠ You MUST discuss H4 and H2 lords from the computed table.\n"
                "  ⚠ Do NOT use the same Jupiter/Venus Pratyantar cited for marriage or career — this query is about HOME."
            )

        # ── Finance / wealth ───────────────────────────────────────────────────
        if any(w in q for w in ['money', 'wealth', 'paisa', 'dhan', 'rich', 'invest', 'finance',
                                  'loan', 'debt', 'savings', 'profit', 'loss']):
            domain_hints.append(
                "FINANCE ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS (check each from birth chart positions above):\n"
                "  • 2nd house (Wealth & Family): its lord, sign, planets — accumulated wealth\n"
                "  • 11th house (Gains & Desires): its lord, sign, planets — income and gains\n"
                "  • 5th house (Children & Intellect): its lord — speculation, investments\n"
                "  • 9th house (Luck & Dharma): its lord — fortune and windfalls\n"
                "  • 10th house (Career & Status): its lord — earned income from career\n"
                "  • Jupiter (natural karaka of wealth): its sign, house, dignity\n"
                "  • Venus (karaka of luxury and comforts): its sign, house, dignity\n"
                "  TIMING (use this priority order):\n"
                "  1. Find VENUS Pratyantar first — karaka for wealth, luxury, and material gains.\n"
                "  2. Find 2nd house lord's Pratyantar (from HOUSE LORDS table) — direct wealth accumulation.\n"
                "  3. Find 11th house lord's Pratyantar (from HOUSE LORDS table) — income and gains.\n"
                "  4. Use Jupiter Pratyantar as a secondary confirmatory trigger only, not the primary window.\n"
                "  5. Jupiter Gochar in H2, H5, or H11 from natal Moon supports financial gains.\n"
                "  6. Sade Sati or Ashtama Shani may restrict gains; advise caution if active.\n"
                "  ⚠ You MUST discuss both H2 and H11 lords from the computed table."
            )

        # ── Health ─────────────────────────────────────────────────────────────
        if any(w in q for w in ['health', 'illness', 'sick', 'disease', 'bimari', 'sehat', 'swasth',
                                  'hospital', 'surgery', 'pain', 'accident', 'injury']):
            domain_hints.append(
                "HEALTH ANALYSIS — Cross-reference ALL of the following from the HOUSE LORDS table:\n"
                "  CHART FACTORS:\n"
                "  • 1st house (Self & Personality): lagnesh — constitution, vitality\n"
                "  • 6th house (Health & Enemies): its lord — disease, health struggles\n"
                "  • 8th house (Longevity & Transformation): its lord — chronic illness, longevity\n"
                "  • Saturn and Mars: their placement and dignity — indicators of physical stress\n"
                "  TIMING: Saturn or Mars Pratyantar can indicate health stress periods.\n"
                "  ⚠ Always note: consult a qualified doctor for medical concerns — astrology shows tendencies only.\n"
                "  ⚠ You MUST discuss H1, H6, and H8 lords from the computed table — not just one house."
            )

        domain_text = ("\n" + "\n".join(f"- {h}" for h in domain_hints)) if domain_hints else ""

        if wants_detail:
            if mode == 'prediction':
                return f"""INSTRUCTIONS:
1. Provide a comprehensive, detailed prediction with full reasoning.
2. Ground every claim in specific chart data (actual houses, signs, planets listed above).
3. Include dasha periods AND approximate calendar timeframes for any timing claims.
4. Do NOT cite classical texts or provide book names as sources unless the user explicitly demands it.
5. {script_instruction}{domain_text}

Provide a thorough, detailed prediction:"""
            else:
                return f"""INSTRUCTIONS:
1. Provide a comprehensive explanation covering the concept fully.
2. Ground the answer in the retrieved classical texts above.
3. Do NOT cite books or provide source names unless the user explicitly demands it.
4. {script_instruction}{domain_text}

Provide a detailed explanation:"""
        else:
            if mode == 'prediction':
                return f"""INSTRUCTIONS (CONCISE MODE):
1. Give a direct, astrological answer in 2-3 short sentences.
2. Mention only ONE or TWO key chart factors.
3. If timing is relevant, give one specific period (e.g., "mid-2026").
4. Do NOT cite sources or provide book names unless the user explicitly demands it.
5. {script_instruction}{domain_text}

Provide a highly concise, self-contained response:"""
            else:
                return f"""INSTRUCTIONS (CONCISE MODE):
1. Answer in 1-2 focused sentences (50-80 words maximum).
2. Base the answer only on retrieved texts above.
3. Do NOT cite sources or provide book names unless the user explicitly demands it.
4. {script_instruction}{domain_text}

Provide a highly concise answer:"""

    def _format_conversation_for_llm(
        self,
        conversation_history: List[Dict]
    ) -> List[Dict[str, str]]:
        """
        Format conversation history for LLM.

        Skips any leading assistant-only messages (e.g. app-generated welcome/greeting
        messages that have no corresponding user turn). These cause the LLM to see a
        conversation that starts with the bot talking to itself, which produces
        inconsistent and off-topic responses — especially visible in the mobile app
        which seeds history with 1-2 app-generated messages at session init.

        Args:
            conversation_history: List of {role, content, timestamp} dicts

        Returns:
            List of {role, content} dicts ready for LLM (always starts with user turn)
        """
        if not conversation_history:
            return []

        # Find the index of the first user message so we start the LLM context there.
        # Any assistant messages before the first user turn are app-generated preamble
        # and should not be injected into the LLM conversation.
        first_user_idx = None
        for i, msg in enumerate(conversation_history):
            if msg.get("role") == "user":
                first_user_idx = i
                break

        if first_user_idx is None:
            # No user messages at all — history is entirely bot preamble; send nothing.
            return []

        if first_user_idx > 0:
            print(f"[HISTORY] Skipping {first_user_idx} leading assistant-only message(s) from LLM context")

        formatted = []
        skipped_external = 0
        for msg in conversation_history[first_user_idx:]:
            # ── EXTERNAL SOURCE FILTER ────────────────────────────────────────
            # Messages imported from the old system (source: "external" or
            # source: "openai") contain answers generated WITHOUT a real chart
            # calculation — they are hallucinated by the old chatbot.
            # Injecting them as LLM context causes the new LLM to treat those
            # wrong house lords and wrong dignities as established facts and
            # repeat them.  Strip assistant messages from external sources;
            # keep user messages so conversation flow is preserved.
            if msg.get("role") == "assistant":
                src = msg.get("metadata", {}).get("source", "")
                if src in ("external", "openai"):
                    skipped_external += 1
                    continue  # Drop this message from LLM context

            formatted.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })

        if skipped_external:
            print(f"[HISTORY] Filtered {skipped_external} external/openai assistant message(s) from LLM context (stale data)")

        return formatted

    def _format_enhanced_analysis(
        self, 
        enhanced: Dict, 
        synthesis: Dict,
        query_type: str
    ) -> str:
        """
        Format enhanced analysis and synthesis for LLM consumption.
        
        This is the SECRET SAUCE — gives LLM pre-analyzed astrological factors
        instead of making it guess from raw positions.
        """
        lines = ["ENHANCED CHART ANALYSIS:", ""]
        
        # Planetary Strengths
        lines.append("PLANETARY STRENGTHS (0-10 scale):")
        strengths = synthesis.get('planetary_strengths', {})
        for planet in ['SUN', 'MOON', 'MARS', 'MERCURY', 'JUPITER', 'VENUS', 'SATURN']:
            if planet in strengths:
                strength = strengths[planet]
                assessment = "STRONG" if strength >= 7 else "MODERATE" if strength >= 4 else "WEAK"
                lines.append(f"  • {planet}: {strength:.1f}/10 ({assessment})")
        lines.append("")
        
        # Dignities
        lines.append("PLANETARY DIGNITIES:")
        for d in enhanced.get('dignities', [])[:7]:
            deep = " [DEEP]" if d.get('is_deep') else ""
            lines.append(f"  • {d['planet']}: {d['dignity'].upper()}{deep} in {d['sign']}")
        lines.append("")
        
        # House Lords for Key Houses
        key_houses = synthesis.get('key_houses', [])
        if key_houses:
            lines.append(f"KEY HOUSES FOR {query_type.upper()}:")
            for ha in key_houses[:4]:  # Top 4 most relevant
                lord_info = ha.get('lord_placement', {})
                lines.append(
                    f"  • House {ha['house']}: {ha['sign']} ruled by {ha['lord']} "
                    f"(strength: {ha['lord_strength']:.1f}/10, placed in H{lord_info.get('house')} {lord_info.get('dignity', '')})"
                )
            lines.append("")
        
        # Yogas
        yogas = synthesis.get('yogas_detected', [])
        if yogas:
            lines.append("YOGAS DETECTED:")
            for y in yogas[:3]:
                lines.append(f"  • {y['name']}: {y['description']}")
            lines.append("")
        
        # Chart Strengths
        strengths_list = synthesis.get('chart_strengths', [])
        if strengths_list:
            lines.append("CHART STRENGTHS:")
            for s in strengths_list[:5]:
                lines.append(f"  ✓ {s}")
            lines.append("")
        
        # Chart Challenges
        challenges_list = synthesis.get('chart_challenges', [])
        if challenges_list:
            lines.append("CHART CHALLENGES:")
            for c in challenges_list[:5]:
                lines.append(f"  ⚠ {c}")
            lines.append("")
        
        # Aspects (top 3)
        aspects = enhanced.get('aspects', [])
        if aspects:
            lines.append("KEY ASPECTS:")
            for asp in aspects[:3]:
                houses = ', '.join(map(str, asp['aspects_houses']))
                lines.append(f"  • {asp['planet']} from H{asp['from_house']} aspects houses: {houses}")
            lines.append("")
        
        # Combustion
        combustion = enhanced.get('combustion', {})
        combust_planets = [p for p, is_c in combustion.items() if is_c]
        if combust_planets:
            lines.append(f"COMBUST PLANETS: {', '.join(combust_planets)} — weakened, results partially blocked")
            lines.append("")

        # Retrograde
        retrograde = enhanced.get('retrograde', [])
        if retrograde:
            lines.append(f"RETROGRADE: {', '.join(retrograde)} — introspective energy, karmic themes, delays then breakthroughs")
            lines.append("")

        # Vargottama (sourced from chart_data if available via synthesis)
        vargottama = enhanced.get('vargottama', [])
        if vargottama:
            lines.append(f"VARGOTTAMA (D1=D9 rashi): {', '.join(vargottama)} — highly potent, amplified results in their Dasha periods")
            lines.append("")
        
        return "\n".join(lines)

    def _compute_house_lords_block(self, chart_data: Dict) -> str:
        """
        Compute all 12 house lords deterministically from chart_data.

        This runs unconditionally — no dependency on ChartAnalyzer or
        ENHANCED_ANALYSIS_AVAILABLE. Uses only the lagna sign and planetary
        positions already present in chart_data.
        """
        _SIGNS = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]
        _SIGN_LORDS = {
            'Aries': 'MARS', 'Taurus': 'VENUS', 'Gemini': 'MERCURY',
            'Cancer': 'MOON', 'Leo': 'SUN', 'Virgo': 'MERCURY',
            'Libra': 'VENUS', 'Scorpio': 'MARS', 'Sagittarius': 'JUPITER',
            'Capricorn': 'SATURN', 'Aquarius': 'SATURN', 'Pisces': 'JUPITER'
        }
        _EXALT = {
            'SUN': 'Aries', 'MOON': 'Taurus', 'MARS': 'Capricorn',
            'MERCURY': 'Virgo', 'JUPITER': 'Cancer', 'VENUS': 'Pisces', 'SATURN': 'Libra'
        }
        _DEBIL = {
            'SUN': 'Libra', 'MOON': 'Scorpio', 'MARS': 'Cancer',
            'MERCURY': 'Pisces', 'JUPITER': 'Capricorn', 'VENUS': 'Virgo', 'SATURN': 'Aries'
        }
        _OWN = {
            'SUN': ['Leo'], 'MOON': ['Cancer'], 'MARS': ['Aries', 'Scorpio'],
            'MERCURY': ['Gemini', 'Virgo'], 'JUPITER': ['Sagittarius', 'Pisces'],
            'VENUS': ['Taurus', 'Libra'], 'SATURN': ['Capricorn', 'Aquarius']
        }
        _SANSKRIT = {
            'Mesha': 'Aries', 'Vrishabha': 'Taurus', 'Mithuna': 'Gemini',
            'Karka': 'Cancer', 'Simha': 'Leo', 'Kanya': 'Virgo',
            'Tula': 'Libra', 'Vrischika': 'Scorpio', 'Dhanu': 'Sagittarius',
            'Makara': 'Capricorn', 'Kumbha': 'Aquarius', 'Meena': 'Pisces'
        }

        def _norm(s):
            if not s:
                return s
            return _SANSKRIT.get(s, _SANSKRIT.get(s.title(), s))

        def _dignity(planet, sign):
            if _EXALT.get(planet) == sign:
                return 'exalted'
            if _DEBIL.get(planet) == sign:
                return 'debilitated'
            if sign in _OWN.get(planet, []):
                return 'own sign'
            return ''

        lagna_data = chart_data.get('lagna') or chart_data.get('ascendant', {})
        lagna_sign = _norm(lagna_data.get('sign') or lagna_data.get('rashi', ''))

        if not lagna_sign or lagna_sign not in _SIGNS:
            return ""

        lagna_idx = _SIGNS.index(lagna_sign)
        planets = chart_data.get('planets', {})

        lines = [
            "HOUSE LORDS (calculated from Lagna — use ONLY these values, never derive lords from your training knowledge):"
        ]
        for h in range(1, 13):
            house_sign = _SIGNS[(lagna_idx + h - 1) % 12]
            lord = _SIGN_LORDS.get(house_sign, '?')
            lord_data = planets.get(lord, {})
            lord_house = lord_data.get('house', '?')
            lord_sign = _norm(lord_data.get('sign') or lord_data.get('rashi') or '?')
            dgn = _dignity(lord, lord_sign)
            dgn_str = f" [{dgn}]" if dgn else ""
            lines.append(
                f"  H{h:2d} ({house_sign:13}) lord = {lord:8} | placed H{lord_house} in {lord_sign}{dgn_str}"
            )

        return "\n".join(lines)

    def _build_prediction_prompt(
        self,
        query: str,
        chart_data: Dict,
        dasha_data: Dict,
        transit_data: Dict,
        knowledge_chunks: List,
        user_profile: Dict,
        conversation_history: List = None,
        language: str = "hi-lat",
        validation_result: Optional[Dict] = None,
        enhanced_analysis: Optional[Dict] = None,  # NEW
        synthesis: Optional[Dict] = None,  # NEW
    ) -> str:
        
        context_parts = []
        for i, chunk in enumerate(knowledge_chunks[:3], 1):
            source = chunk.metadata.get('source_book', 'Unknown') if hasattr(chunk, 'metadata') else 'Unknown'
            chapter = chunk.metadata.get('chapter', '') if hasattr(chunk, 'metadata') else ''
            verse = chunk.metadata.get('verse_number', '') if hasattr(chunk, 'metadata') else ''
            
            # Format with book name prominently
            source_citation = f"[{source}"
            if chapter:
                source_citation += f" - Chapter {chapter}"
            if verse:
                source_citation += f", Verse {verse}"
            source_citation += "]"
            
            content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
            context_parts.append(f"{source_citation}\n{content}")
        
        context = "\n\n".join(context_parts) if context_parts else "No specific texts retrieved."
        
        # PHASE 6: Safe extraction for stateless mode (handle None)
        dasha_data = dasha_data or {}
        transit_data = transit_data or {}
        chart_data = chart_data or {}
        
        # ── DATE ANCHOR — single definition used by all filters below ──────────
        from datetime import date as _date_anchor
        _today_str = _date_anchor.today().isoformat()   # e.g. "2026-03-06"

        # ── STALE MAHADASHA CHECK ─────────────────────────────────────────────
        # If the cached Mahadasha end date is in the past, the entire dasha_data
        # is from the wrong MD period. Clear it so the orchestrator recalculates.
        _md_end = (dasha_data or {}).get('mahadasha', {}).get('end', '9999')
        if dasha_data and _md_end < _today_str:
            print(f"[DASHA STALE] Mahadasha end ({_md_end}) is in the past — "
                  f"cache is from wrong MD period. Clearing dasha_data for recalc.")
            dasha_data = {}
            state['dasha_data'] = {}

        # Extract dasha info safely
        maha_planet = dasha_data.get('mahadasha', {}).get('planet', 'Unknown')
        antar_planet = dasha_data.get('antardasha', {}).get('planet', 'Unknown')
        dasha_sequence = dasha_data.get('dasha_sequence', f"{maha_planet}/{antar_planet}")
        
        # DEBUG: Print dasha data to verify it has dates
        print(f"[DEBUG] Dasha data in prompt:")
        print(f"  Mahadasha: {maha_planet} ({dasha_data.get('mahadasha', {}).get('start', 'NO DATE')} to {dasha_data.get('mahadasha', {}).get('end', 'NO DATE')})")
        print(f"  Antardasha: {antar_planet} ({dasha_data.get('antardasha', {}).get('start', 'NO DATE')} to {dasha_data.get('antardasha', {}).get('end', 'NO DATE')})")
        calc_details = dasha_data.get('calculation_details', {})
        print(f"  Calculation details: Moon={calc_details.get('moon_longitude', 'MISSING')}, Nakshatra={calc_details.get('moon_nakshatra', 'MISSING')}")
        
        # Build upcoming antardashas timeline
        upcoming_ads = dasha_data.get('upcoming_antardashas', [])
        # Filter past antardashas too (same stale-cache issue)
        upcoming_ads_filtered = [ad for ad in upcoming_ads
                                  if ad.get('end', '9999') >= _today_str]
        skipped_past_ads = len(upcoming_ads) - len(upcoming_ads_filtered)
        if skipped_past_ads > 0:
            print(f"[DASHA FILTER] Removed {skipped_past_ads} past antardasha(s) from prompt.")

        upcoming_ads_str = ""
        if upcoming_ads_filtered:
            upcoming_ads_str = "\nStep 3 - Upcoming Antardashas (for future timing):\n"
            for ad in upcoming_ads_filtered:
                upcoming_ads_str += f"• {ad.get('planet', 'Unknown')} ({ad.get('start', 'Unknown')} to {ad.get('end', 'Unknown')})\n"

        # Build upcoming pratyantardashas timeline (precise week/month level timing)
        upcoming_pds = dasha_data.get('upcoming_pratyantardashas', [])
        # ── CODE-LEVEL PAST-DATE FILTER ───────────────────────────────────────
        # Strip pratyantar periods whose end date has already passed.
        # No nested functions — inline comparison avoids all closure issues.
        upcoming_pds_filtered = [
            pd for pd in upcoming_pds
            if (pd.get('end') or '9999') >= _today_str
        ]
        skipped_past_pds = len(upcoming_pds) - len(upcoming_pds_filtered)
        if skipped_past_pds > 0:
            print(f"[DASHA FILTER] Removed {skipped_past_pds} past pratyantar(s) from prompt "
                  f"(end date < {_today_str}). Only {len(upcoming_pds_filtered)} period(s) remain.")

        upcoming_pds_str = ""
        if upcoming_pds_filtered:
            upcoming_pds_str = f"\nStep 3.5 - Pratyantardashas within current Antardasha (TODAY = {_today_str}):\n"
            upcoming_pds_str += "  ⚠ ONLY use windows listed here for timing. DO NOT compute sub-windows yourself.\n"
            for pd in upcoming_pds_filtered:
                status = pd.get('status', 'upcoming')
                upcoming_pds_str += (
                    f"• {pd.get('planet', 'Unknown'):10} "
                    f"{pd.get('start', 'Unknown')} → {pd.get('end', 'Unknown')} "
                    f"({pd.get('duration_days', '?')} days) [{status}]\n"
                )
        elif upcoming_pds:
            # All pratyantardashas in current AD have passed — tell LLM explicitly
            upcoming_pds_str = (
                f"\nStep 3.5 - Pratyantardashas (TODAY = {_today_str}):\n"
                "  ⚠ ALL pratyantardashas in the current Antardasha have already passed.\n"
                "  Use the NEXT Antardasha's opening Pratyantar for timing (see Step 3.6 below).\n"
            )
        print(f"[DEBUG] upcoming_pratyantardashas: {len(upcoming_pds)} total, "
              f"{len(upcoming_pds_filtered)} after past-date filter")
        for _pd in upcoming_pds_filtered:
            print(f"  Pratyantar: {_pd.get('planet'):10} {_pd.get('start')} → {_pd.get('end')} [{_pd.get('status')}]")

        # First pratyantar of each upcoming Antardasha (cross-level convergence)
        next_ad_fp = dasha_data.get('next_antardasha_first_pratyantar', [])
        next_ad_fp_str = ""
        if next_ad_fp:
            next_ad_fp_str = "\nStep 3.6 - Opening Pratyantar of Next Antardashas (convergence windows):\n"
            for entry in next_ad_fp:
                next_ad_fp_str += (
                    f"• When {entry.get('antardasha_planet')} AD starts ({entry.get('antardasha_start')}): "
                    f"first Pratyantar = {entry.get('first_pratyantar_planet')} "
                    f"({entry.get('first_pratyantar_start')} to {entry.get('first_pratyantar_end')})\n"
                )
        
        # Extract transit info safely
        transit_planets_raw = transit_data.get('transits', {})
        jupiter_transit = transit_planets_raw.get('JUPITER', transit_planets_raw.get('Jupiter', 'Unknown'))
        saturn_transit  = transit_planets_raw.get('SATURN',  transit_planets_raw.get('Saturn',  'Unknown'))
        mars_transit    = transit_planets_raw.get('MARS',    transit_planets_raw.get('Mars',    'Unknown'))
        transit_date = transit_data.get('date', 'current')
        today_date = _today_str  # reuse _today_str already defined above

        # ── Gochara Analysis (transit relative to natal chart) ───────────────
        gochara_str = ""
        try:
            # Rashi → 0-based index mapping (English + Sanskrit)
            _R = {n: i for i, n in enumerate([
                "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
            ])}
            _R.update({n: i for i, n in enumerate([
                "Mesha","Vrishabha","Mithuna","Karka","Simha","Kanya",
                "Tula","Vrischika","Dhanu","Makara","Kumbha","Meena"
            ])})
            # Also accept uppercase Rashi enum names (e.g. "MESHA")
            _R.update({k.upper(): v for k, v in _R.items()})

            moon_sign   = chart_data.get('planets', {}).get('MOON', {}).get('sign', '')
            lagna_sign  = chart_data.get('lagna', {}).get('sign', '')
            moon_idx    = _R.get(moon_sign, -1)
            lagna_idx   = _R.get(lagna_sign, -1)

            def _house_from(base_idx, transit_sign, _r=None):
                # default arg pins _R at definition time — no free-variable closure
                _r = _r if _r is not None else _R
                t_idx = _r.get(transit_sign, -1)
                if base_idx < 0 or t_idx < 0:
                    return None
                return (t_idx - base_idx) % 12 + 1

            retro = transit_data.get('retrograde_status', {})
            gochara_lines = ["GOCHARA ANALYSIS (Transits relative to natal chart):"]

            # ── Sade Sati / Ashtama Shani ────────────────────────────────────
            sat_house_moon = _house_from(moon_idx, saturn_transit)
            if sat_house_moon is not None:
                if sat_house_moon in (12, 1, 2):
                    phase_name = {12: "Rising phase (12th from Moon)",
                                  1:  "Peak phase (on natal Moon)",
                                  2:  "Setting phase (2nd from Moon)"}[sat_house_moon]
                    gochara_lines.append(
                        f"• ⚠ SADE SATI ACTIVE — Saturn in {saturn_transit} ({phase_name}). "
                        f"Expect challenges/delays in major life decisions; also a period of deep inner transformation."
                    )
                elif sat_house_moon == 8:
                    gochara_lines.append(
                        f"• ⚠ ASHTAMA SHANI — Saturn in 8th from natal Moon ({saturn_transit}). "
                        f"Obstacles, health concerns, hidden enemies possible."
                    )
                else:
                    gochara_lines.append(
                        f"• Shani Gochar: Saturn transiting H{sat_house_moon} from natal Moon ({saturn_transit}) — no Sade Sati."
                    )

            # ── Jupiter Gochar from Moon ──────────────────────────────────────
            jup_house_moon = _house_from(moon_idx, jupiter_transit)
            if jup_house_moon is not None:
                FAVOURABLE_JUP = {1, 2, 5, 7, 9, 11}
                fav = "✓ FAVOURABLE" if jup_house_moon in FAVOURABLE_JUP else "✗ UNFAVOURABLE"
                retro_jup = " (Retrograde)" if retro.get('JUPITER') or retro.get('Jupiter') else ""
                gochara_lines.append(
                    f"• Guru Gochar: Jupiter transiting H{jup_house_moon} from natal Moon ({jupiter_transit}{retro_jup}) — {fav}. "
                    + ("Supports marriage, children, wealth, and dharmic events." if jup_house_moon in FAVOURABLE_JUP
                       else "Less supportive for major auspicious events; focus on inner growth.")
                )

            # ── Rahu-Ketu axis from Lagna ─────────────────────────────────────
            rahu_sign = transit_planets_raw.get('RAHU', transit_planets_raw.get('Rahu', ''))
            rahu_house_lagna = _house_from(lagna_idx, rahu_sign)
            if rahu_house_lagna is not None:
                ketu_house = (rahu_house_lagna - 1 + 6) % 12 + 1
                gochara_lines.append(
                    f"• Rahu-Ketu Axis: Rahu transiting H{rahu_house_lagna} / Ketu H{ketu_house} from Lagna ({rahu_sign}). "
                    f"Areas of karmic focus and past-life themes."
                )

            # ── All transits mapped to natal houses ───────────────────────────
            gochara_lines.append("• All transit planet positions (natal house from Lagna):")
            planet_order = ['SUN','MOON','MARS','MERCURY','JUPITER','VENUS','SATURN','RAHU','KETU']
            for p in planet_order:
                t_sign = transit_planets_raw.get(p, transit_planets_raw.get(p.capitalize(), ''))
                if not t_sign:
                    continue
                h = _house_from(lagna_idx, t_sign)
                h_str = f"H{h}" if h else "?"
                r_mark = " (R)" if retro.get(p) or retro.get(p.capitalize()) else ""
                gochara_lines.append(f"    {p:9}: {t_sign:12} → natal {h_str}{r_mark}")

            gochara_str = "\n".join(gochara_lines)
        except Exception as _ge:
            print(f"[GOCHARA] Computation error: {_ge}")
            gochara_str = ""

        # ── Vargottama ────────────────────────────────────────────────────────
        vargottama_str = ""
        vargottama = chart_data.get('vargottama', [])
        if vargottama:
            vargottama_str = (
                f"\nVARGOTTAMA PLANETS (same rashi in D1 and D9 — extremely potent): "
                f"{', '.join(vargottama)}\n"
                "These planets give strongly amplified results in their Dasha/Antardasha periods."
            )
        
        # Get persona based on language
        try:
            from src.ai.personas import get_persona
            persona = get_persona(user_profile.get('preferred_system', 'vedic'))
            system_prompt = persona.get_system_prompt(
                user_name=user_profile.get('name', 'User'),
                language=language,
                llm=self.fast_llm
            )
        except:
            system_prompt = "You are an expert Vedic astrologer explaining predictions."

        # PHASE 10: Inject Constitution
        constitution = get_constitution_injection()
        system_prompt = f"{system_prompt}\n\n{constitution}"

        # ── CHART ANCHOR: inject at the very top of system_prompt ─────────────
        # Must come AFTER persona/constitution are built so we prepend to the
        # final combined string.  Placing it first means the LLM reads the
        # verified Lagna and forbidden-claims list before any other instruction.
        chart_anchor = self._build_chart_anchor_block(chart_data)
        if chart_anchor:
            system_prompt = chart_anchor + "\n\n" + system_prompt

        # ── Hard timing rule injected into system prompt ──────────────────────
        # Placed here (system prompt level) so the LLM reliably follows it
        # regardless of where it appears in the user context.
        _ref_date = _today_str  # reuse _today_str already defined above
        system_prompt += (
            f"\n\nCRITICAL TIMING RULE: Today's date is {_ref_date}. "
            "NEVER predict or cite any date range that ended before today. "
            "If a Pratyantar or Antardasha period has already fully elapsed "
            f"(its end date is before {_ref_date}), you MUST skip it and find the next future window. "
            "For a period currently 'IN PROGRESS', cite only today → its end date, not its original start. "
            "NEVER compute or invent sub-windows from your training knowledge — "
            "use ONLY the Pratyantar dates explicitly listed in the prompt."
        )

        # ════════════════════════════════════════════════════════════════════════
        # GREETING CONTROL (Mobile App Context-Aware)
        # ════════════════════════════════════════════════════════════════════════
        # Determine whether there are real prior user-assistant exchanges.
        # "Real" means: at least one user message exists in the history (not just
        # app-generated bot preamble with no corresponding user turn).
        user_msgs_in_history = [m for m in (conversation_history or []) if m.get('role') == 'user']
        app_greeting_present = (
            bool(conversation_history)
            and len(conversation_history) >= 2
            and not user_msgs_in_history  # All messages so far are from the app/assistant
        )
        if app_greeting_present:
            print(f"[GREETING] App-provided initial greeting detected (no user turns yet)")

        if app_greeting_present or (user_msgs_in_history and len(user_msgs_in_history) >= 1):
            system_prompt += """

ONGOING CONVERSATION - CONTEXT HANDLING:
- NO greetings (Namaste/Hello/Hari Om) - user already greeted
- NO thanking for birth details - details already provided via app
- Get STRAIGHT to answering the user's question
- Review ALL previous messages before responding
- When user says "it", "this", "that" -> check conversation history
- Connect follow-up questions to earlier topics
- Build upon previous insights, don't repeat
- Maintain conversation flow with context awareness
"""
        else:
            # First user message (conversation_history empty or has only 1-2 messages)
            system_prompt += """

EARLY CONVERSATION:
- A brief greeting is appropriate (1 sentence max): "Namaste [Name]!"
- Then get straight to the answer
- NO thanking for details (details provided via app backend)
- Example: "Namaste! Aapki 7th house lord Venus..."
"""
        
        # PHASE 12: Inject Validation Context (NEW)
        validation_context = ""
        if validation_result and VALIDATION_AVAILABLE:
            try:
                validation_context = format_validation_for_prompt(validation_result)
            except Exception as e:
                print(f"[VALIDATION] Error formatting validation: {e}")

        divisional_context = ""
        if validation_result:
            query_type = validation_result.get('query_type', 'general')
            try:
                divisional_context = get_divisional_chart_context(
                    query_type=query_type,
                    chart_data=chart_data,
                    include_secondary=True,
                    verbose=True
                )
            except Exception as e:
                print(f"[DIVISIONAL] Error adding divisional chart context: {e}")

        # Map language code to descriptive name for LLM
        loc_manager = get_localization_manager()
        lang_name = loc_manager.get_language_name(language)

        # Build script instruction for language enforcement
        if '-lat' in language:
            script_instruction = f"Respond in {lang_name} using ROMAN ALPHABET only (no native script)."
        elif language != 'en':
            script_instruction = f"Respond entirely in {lang_name} (native script)."
        else:
            script_instruction = "Respond in clear, professional English."

        # Use dynamic instruction builder — adapts to query content (timing, career, etc) and verbosity
        instructions = self._build_response_instructions(
            query=query,
            lang_name=lang_name,
            script_instruction=script_instruction,
            mode='prediction'
        )

        # Domain-specific Pratyantar spotlight — injected into the dasha block so the LLM
        # knows which planet's Pratyantar window to prioritize for this exact query type.
        domain_spotlight = self._get_domain_pratyantar_spotlight(query)

        # ════════════════════════════════════════════════════════════════════════
        # MOBILE RESPONSE LENGTH CONTROL (150 words max)
        # ════════════════════════════════════════════════════════════════════════
        mobile_length_instruction = """

RESPONSE FORMAT (CRITICAL - MUST FOLLOW):
1. MAXIMUM LENGTH: 150-200 words total. Be thorough but not padded.
2. FIRST SENTENCE: Direct, clear answer to the question.
3. STRUCTURE: Direct Answer → 2-3 Key Factors from the chart → Timing → Remedy (if applicable). DO NOT ask follow-up questions.
4. HOUSE ANNOTATIONS (MANDATORY): Every time you mention a house by number, ALWAYS
   add its primary domain in parentheses immediately after. No exceptions.
   Use this exact mapping:
     1st house (Self & Personality)
     2nd house (Wealth & Family)
     3rd house (Courage & Siblings)
     4th house (Home & Mother)
     5th house (Children & Intellect)
     6th house (Health & Enemies)
     7th house (Marriage & Partnership)
     8th house (Longevity & Transformation)
     9th house (Luck & Dharma)
     10th house (Career & Status)
     11th house (Gains & Desires)
     12th house (Losses & Moksha)
   Examples:
     ✅ "7th house (Marriage & Partnership) ki lord Venus..."
     ✅ "10th house (Career & Status) mein Sun strong hai..."
     ❌ "7th house ki lord Venus..." (missing annotation)
5. NO META-COMMENTARY: Don't explain what you're doing or analyzing.
   - Bad: "Based on your chart, I can see..."
   - Good: "Your 7th house (Marriage & Partnership) lord Venus is..."
6. NO THANKING: User details from backend.
7. GET STRAIGHT TO THE POINT: Cut all filler words. Make every word count.
8. NO FOLLOW-UP QUESTIONS: Never end with questions like "Do you want remedies?", "Shall I explain more?", "Would you like to know...?" Just give the complete answer directly.

EXAMPLE GOOD RESPONSE (Marriage — shows multi-house analysis):
"Aapki 7th house (Marriage & Partnership) ki lord Venus H2 mein hai — marital stability ke liye accha, lekin H5 (Children & Intellect) ki lord Saturn ki 7th par drishti thodi delay de raha hai. 2nd house (Wealth & Family) ka lord Jupiter strong hai jo family support dikhata hai. Timing: Venus Pratyantar [cite exact start→end from Pratyantar table above] — yeh peak marriage window hai."

EXAMPLE GOOD RESPONSE (Career — shows multi-house analysis):
"10th house (Career & Status) ki lord Mercury H2 mein hai — communication-based income. 6th house (Health & Enemies) ka lord Saturn H10 mein hai — service sector mein stability. 11th house (Gains & Desires) ka lord Moon strong hai — gains ka yog. Saturn Pratyantar [cite exact start→end from Pratyantar table above] mein Saturn gochar H10 se align kar raha hai — promotion ya new role ka peak time."

EXAMPLE GOOD RESPONSE (Foreign Travel — shows multi-house analysis):
"9th house (Luck & Dharma) ki lord Venus H12 mein hai — yahi foreign settlement ka strong yog hai. 12th house (Losses & Moksha) ka lord Mars active hai. Rahu H9 se transit kar raha hai — foreign connection trigger. Rahu Pratyantar [cite exact start→end from Pratyantar table above] — foreign opportunity ki peak window."
"""
        instructions += mobile_length_instruction

        # CHANGE 5: Add conversation summary section
        conversation_summary_section = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_summary_section = """
CONVERSATION CONTEXT:
This is an ongoing conversation. Previous messages contain:
- Topics already discussed
- Chart placements mentioned
- Questions answered

When user uses "it", "this", "that" or asks "why", "how" -> connect to conversation history.
"""

        enhanced_context = ""
        if enhanced_analysis and synthesis:
            enhanced_context = self._format_enhanced_analysis(
                enhanced_analysis, synthesis, query_type=validation_result.get('query_type', 'general') if validation_result else 'general'
            )

        # Always compute house lords from lagna — no dependency on enhanced analysis pipeline
        house_lords_block = self._compute_house_lords_block(chart_data)

        # ── LAGNESH NOTE: prevent LLM from conflating lagna-lordship with exaltation ──
        # Common LLM error: "Virgo Lagna → Mercury lagnesh → Mercury is exalted"
        # Reality: exaltation requires the planet to be in its specific exaltation SIGN.
        _LORDS_FOR_LAGNESH = {
            'Aries': 'MARS', 'Taurus': 'VENUS', 'Gemini': 'MERCURY',
            'Cancer': 'MOON', 'Leo': 'SUN', 'Virgo': 'MERCURY',
            'Libra': 'VENUS', 'Scorpio': 'MARS', 'Sagittarius': 'JUPITER',
            'Capricorn': 'SATURN', 'Aquarius': 'SATURN', 'Pisces': 'JUPITER',
            # Sanskrit aliases
            'Mesha': 'MARS', 'Vrishabha': 'VENUS', 'Mithuna': 'MERCURY',
            'Karka': 'MOON', 'Simha': 'SUN', 'Kanya': 'MERCURY',
            'Tula': 'VENUS', 'Vrischika': 'MARS', 'Dhanu': 'JUPITER',
            'Makara': 'SATURN', 'Kumbha': 'SATURN', 'Meena': 'JUPITER',
        }
        _lagna_sign_raw = chart_data.get('lagna', {}).get('sign', '')
        _lagnesh = _LORDS_FOR_LAGNESH.get(_lagna_sign_raw, '')
        lagnesh_note = ""
        if _lagnesh:
            _ld = chart_data.get('planets', {}).get(_lagnesh, {})
            _ld_dignity = _ld.get('dignity', {}).get('status', 'unknown')
            _ld_sign    = _ld.get('sign', 'unknown')
            _ld_house   = _ld.get('house', '?')
            lagnesh_note = (
                f"\n⚠ LAGNESH CLARIFICATION: {_lagnesh} is the lord of {_lagna_sign_raw} Lagna (lagnesh). "
                f"Actual placement: {_ld_sign}, H{_ld_house}, dignity = {_ld_dignity}. "
                f"Being lagnesh does NOT make {_lagnesh} exalted — use the dignity column above, not Lagna ownership."
            )

        # ════════════════════════════════════════════════════════════════════════
        # PROMPT STRUCTURE (order matters for LLM compliance):
        #   1. System prompt (persona + constitution + chart anchor + timing rule)
        #   2. ALL computed chart data (birth chart, house lords, dasha, transits)
        #   3. Classical text knowledge (RAG)
        #   4. Response instructions
        #   5. User query LAST — so LLM reads all ground truth before the question
        # ════════════════════════════════════════════════════════════════════════

        prompt = f"""{system_prompt}

{validation_context}

{enhanced_context}

{conversation_summary_section}

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}

════════════════════════════════════════════════════════════════════════
COMPUTED CHART DATA — Swiss Ephemeris (Sidereal/Lahiri)
All values below are CALCULATED, not inferred. Use ONLY these values.
════════════════════════════════════════════════════════════════════════

BIRTH CHART PLANETARY POSITIONS:
  Format: Sign | House | Degree | Nakshatra Pada | Dignity | [RETRO] [COMBUST]
  INTERPRETATION PRIORITY (apply in this order — each layer modifies the one before):
  1. Dignity     — sets the base strength (Exalted > Own/Moolatrikona > Friend > Neutral > Enemy > Debilitated)
  2. [RETRO]     — retrograde planet turns results inward; expression is delayed then intensified; treat as strengthened but internalized
  3. [COMBUST]   — within Sun's orb; planet's significations are weakened/suppressed; reduce strength assessment
  4. Nakshatra   — colours the planet's expression (Ketu-ruled nakshatras = karmic; Rahu = material ambition, etc.)
  5. Pada        — navamsa quarter; odd pada = more outward, even = more inward expression; P1/P3 often stronger for material results
  6. Degree      — note degrees 0–1 (very new energy, unsteady) and 29° (critical, culminating); gandanta at water-fire sign junctions
  NOTE: A [RETRO][COMBUST] planet has competing modifiers — retrograde strengthens, combustion weakens; net effect is partial and erratic.
• Ascendant (Lagna): {chart_data.get('lagna', {}).get('sign', 'Not available')} {chart_data.get('lagna', {}).get('degree', 0.0):.2f}° | Nakshatra: {chart_data.get('lagna', {}).get('nakshatra', 'N/A')} (Lord: {chart_data.get('lagna', {}).get('nakshatra_lord', 'N/A')})
• Sun:     {chart_data.get('planets', {}).get('SUN',     {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('SUN',     {}).get('house', '?')} {chart_data.get('planets', {}).get('SUN',     {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('SUN',     {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('SUN',     {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('SUN',     {}).get('dignity', {}).get('status', '')}
• Moon:    {chart_data.get('planets', {}).get('MOON',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MOON',    {}).get('house', '?')} {chart_data.get('planets', {}).get('MOON',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MOON',    {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('MOON',    {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MOON',    {}).get('dignity', {}).get('status', '')}{'  [COMBUST]' if chart_data.get('planets', {}).get('MOON', {}).get('combust') else ''}
• Mars:    {chart_data.get('planets', {}).get('MARS',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MARS',    {}).get('house', '?')} {chart_data.get('planets', {}).get('MARS',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MARS',    {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('MARS',    {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MARS',    {}).get('dignity', {}).get('status', '')}{'  [RETRO]' if chart_data.get('planets', {}).get('MARS', {}).get('retrograde') else ''}{'  [COMBUST]' if chart_data.get('planets', {}).get('MARS', {}).get('combust') else ''}
• Mercury: {chart_data.get('planets', {}).get('MERCURY', {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MERCURY', {}).get('house', '?')} {chart_data.get('planets', {}).get('MERCURY', {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MERCURY', {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('MERCURY', {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MERCURY', {}).get('dignity', {}).get('status', '')}{'  [RETRO]' if chart_data.get('planets', {}).get('MERCURY', {}).get('retrograde') else ''}{'  [COMBUST]' if chart_data.get('planets', {}).get('MERCURY', {}).get('combust') else ''}
• Jupiter: {chart_data.get('planets', {}).get('JUPITER', {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('JUPITER', {}).get('house', '?')} {chart_data.get('planets', {}).get('JUPITER', {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('JUPITER', {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('JUPITER', {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('JUPITER', {}).get('dignity', {}).get('status', '')}{'  [RETRO]' if chart_data.get('planets', {}).get('JUPITER', {}).get('retrograde') else ''}{'  [COMBUST]' if chart_data.get('planets', {}).get('JUPITER', {}).get('combust') else ''}
• Venus:   {chart_data.get('planets', {}).get('VENUS',   {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('VENUS',   {}).get('house', '?')} {chart_data.get('planets', {}).get('VENUS',   {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('VENUS',   {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('VENUS',   {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('VENUS',   {}).get('dignity', {}).get('status', '')}{'  [RETRO]' if chart_data.get('planets', {}).get('VENUS', {}).get('retrograde') else ''}{'  [COMBUST]' if chart_data.get('planets', {}).get('VENUS', {}).get('combust') else ''}
• Saturn:  {chart_data.get('planets', {}).get('SATURN',  {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('SATURN',  {}).get('house', '?')} {chart_data.get('planets', {}).get('SATURN',  {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('SATURN',  {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('SATURN',  {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('SATURN',  {}).get('dignity', {}).get('status', '')}{'  [RETRO]' if chart_data.get('planets', {}).get('SATURN', {}).get('retrograde') else ''}{'  [COMBUST]' if chart_data.get('planets', {}).get('SATURN', {}).get('combust') else ''}
• Rahu:    {chart_data.get('planets', {}).get('RAHU',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('RAHU',    {}).get('house', '?')} {chart_data.get('planets', {}).get('RAHU',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('RAHU',    {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('RAHU',    {}).get('nakshatra_pada', '?')} [always Retro]
• Ketu:    {chart_data.get('planets', {}).get('KETU',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('KETU',    {}).get('house', '?')} {chart_data.get('planets', {}).get('KETU',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('KETU',    {}).get('nakshatra', 'N/A')} P{chart_data.get('planets', {}).get('KETU',    {}).get('nakshatra_pada', '?')} [always Retro]
{lagnesh_note}

{house_lords_block}

{divisional_context}

VIMSHOTTARI DASHA CALCULATION (Transparent & Auditable):

Step 1 - Moon's Position at Birth:
• Moon Longitude: {dasha_data.get('calculation_details', {}).get('moon_longitude', 'Not available')}
• Moon Nakshatra: {dasha_data.get('calculation_details', {}).get('moon_nakshatra', 'Not available')}
• First Dasha Lord (Nakshatra Ruler): {dasha_data.get('calculation_details', {}).get('first_dasha_lord', 'Not available')}
• Balance of First Dasha at Birth: {dasha_data.get('calculation_details', {}).get('balance_at_birth_years', 'Not available')} years

Step 2 - Current Dasha Periods (Calculated from Moon Nakshatra):
• Mahadasha: {maha_planet} ({dasha_data.get('mahadasha', {}).get('start', 'Unknown')} to {dasha_data.get('mahadasha', {}).get('end', 'Unknown')})
• Antardasha: {antar_planet} ({dasha_data.get('antardasha', {}).get('start', 'Unknown')} to {dasha_data.get('antardasha', {}).get('end', 'Unknown')})
• Pratyantardasha: {dasha_data.get('pratyantardasha', {}).get('planet', 'Unknown')} ({dasha_data.get('pratyantardasha', {}).get('start', 'Unknown')} to {dasha_data.get('pratyantardasha', {}).get('end', 'Unknown')})
• Dasha Sequence: {dasha_sequence}
{upcoming_pds_str}{next_ad_fp_str}{upcoming_ads_str}{domain_spotlight}
TODAY'S DATE: {today_date}

⚠ PAST DATE RULE (MANDATORY): NEVER cite a date range as a prediction if it has already ended (end date < {today_date}).
  - Periods marked "IN PROGRESS": cite only the remaining window (today → end date), NOT the original start.
  - Only cite periods that are "IN PROGRESS" (remaining portion) or fully in the future.
  - If all favorable Pratyantardashas in the current Antardasha have already passed, move to the NEXT Antardasha.

TIMING GUIDANCE: Pratyantardasha gives month-level precision, Antardasha gives multi-month context, Mahadasha gives year-level context. When Pratyantar + Gochara alignment point to the same window, cite that specific Pratyantar date range as the peak timing.
CRITICAL: These dates are CALCULATED using Swiss Ephemeris. Use ONLY these exact dates. Do not invent or estimate dates.

CURRENT TRANSITS (as of {transit_date}):
• Jupiter: {jupiter_transit}
• Saturn: {saturn_transit}
• Mars: {mars_transit}

{gochara_str}

{vargottama_str}

════════════════════════════════════════════════════════════════════════
END OF COMPUTED DATA
════════════════════════════════════════════════════════════════════════

RELEVANT ASTROLOGICAL KNOWLEDGE FROM CLASSICAL TEXTS:
{context}

DATA-GROUNDING RULE (MANDATORY — ZERO EXCEPTIONS):
Every factual claim MUST trace to a specific data point in the COMPUTED CHART DATA block above.
Before stating any fact, perform this internal audit:

  CLAIM TYPE                    │ MUST TRACE TO
  ─────────────────────────────────────────────────────────────────────────────
  Planet dignity (strong/weak/  │ Dignity column in BIRTH CHART PLANETARY POSITIONS
  exalted/debilitated)          │ NOT general planet reputation from training knowledge
  Retrograde effect             │ [RETRO] flag on that planet's row — ONLY if flag present
                                │ If absent, planet is DIRECT — do not assume retrograde
  Combustion effect             │ [COMBUST] flag on that planet's row — ONLY if flag present
                                │ If absent, planet is NOT combust — do not assume it
  House lord                    │ HOUSE LORDS table — cite both planet AND house sign
                                │ Format: "Nth house (domain) lord [PLANET]"
  Dasha/timing dates            │ Step 2/3/3.5/3.6 dasha tables — exact dates only
  Transit effect on native      │ CURRENT TRANSITS + GOCHARA ANALYSIS block
  Planet sign/house/nakshatra   │ BIRTH CHART PLANETARY POSITIONS rows
  Nakshatra pada                │ Pada column (P1–P4) in BIRTH CHART PLANETARY POSITIONS
  Vargottama claim              │ VARGOTTAMA PLANETS line — only if planet listed there
  ─────────────────────────────────────────────────────────────────────────────

PROHIBITED INFERENCES (NEVER do these):
  X Claiming a planet is strong/weak without citing its computed dignity status
  X Stating a planet is retrograde unless [RETRO] appears on its row in the table
  X Stating a planet is combust unless [COMBUST] appears on its row in the table
  X Reducing a planet's strength due to combustion when [COMBUST] is not flagged
  X Amplifying a planet's results as retrograde when [RETRO] is not flagged
  X Deriving house lords from birth date or Sun sign using training knowledge
  X Citing transit positions or effects not shown in CURRENT TRANSITS section
  X Computing or inventing sub-period dates not listed in Step 3.5/3.6
  X Using Sun sign as Lagna, or Moon sign as Lagna — they are listed separately
  X Stating yoga effects (Raj Yoga, Gajakesari, etc.) unless the yoga is present
    in the enhanced_context above or directly calculable from the listed positions
  X Claiming a planet is EXALTED because it is the Lagna lord (lagnesh).
    Lagna lordship ≠ exaltation. Exaltation requires the planet to physically be
    in its specific exaltation sign. Check the LAGNESH CLARIFICATION line above.
  X Stating a planet's transit-house from Lagna or Moon unless it matches the
    GOCHARA ANALYSIS block exactly. Never self-compute "Jupiter is in H10 from Lagna"
    — only use the house numbers shown in the GOCHARA ANALYSIS block.

CROSS-REFERENCING FORMAT (MANDATORY in every response):
  • House lords  → "Nth house (domain) lord [PLANET]"
                   e.g. "7th house (Marriage & Partnership) lord Venus is in H3"
  • Timing       → "During [PLANET] Pratyantar ([START] to [END])..."
  • Dignity      → "[PLANET] is [dignity] in [sign]" — match the table exactly
  • Transit      → "[PLANET] transiting H[N] from Moon/Lagna ([sign])"

If computed data is absent for a claim, write "data not available" rather than
substituting a training-knowledge default.

{instructions}

====USER_QUERY_MARKER====
"{query}"
"""
        
        return prompt
    
    def _route_by_intent(self, state: NakshatraState) -> str:
        """4-way routing based on intent."""
        
        if not state.get('authenticated'):
            return "error"
        
        intent = state.get('intent', 'RAG_WITH_CALCULATION')
        
        if intent == "CHITCHAT":
            return "chitchat"
        elif intent == "AMBIGUOUS":  # NEW: Route ambiguous queries to clarification
            return "clarification"
        elif intent == "CALCULATION_ONLY":
            return "calculation_only"
        elif intent == "RAG_ONLY":
            return "rag_only"
        elif intent == "safety_block":  # PHASE 10
            return "safety_block"
        else:
            # Default: RAG_WITH_CALCULATION (most common)
            return "rag_with_calculation"
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def process_query(
        self,
        query: str,
        user_id: str,
        conversation_history: Optional[List[Dict]] = None,
        user_profile_override: Optional[Dict] = None,
        session_data: Optional[Dict] = None
    ) -> Dict:
        """Process query through enhanced orchestrator."""
        start_time = datetime.now()
        
        initial_state: NakshatraState = {
            "query": query,
            "user_id": user_id,
            "conversation_history": conversation_history, # Preserved as None for tiered lookup
            "session_data": session_data,
            "user_profile": user_profile_override,
            "authenticated": user_profile_override is not None,
            "intent": None,
            "confidence": 0.0,
            "intent_reasoning": "",
            "cached": False,
            "detected_language": "en",
            "original_query": query,
            "chart_data": None,
            "dasha_data": None,
            "transit_data": None,
            "knowledge_chunks": None,
            "answer": "",
            "error": None,
            "processing_time": 0.0,
            "messages": [],
            # PHASE 9 Fix: Use explicit user preference or default to 'vedic'. Do NOT detect from query.
            "persona_type": "vedic", 
            
            # PHASE 10: Validation Init
            
            # PHASE 10: Validation Init
            "validation_attempts": 0,
            "validation_feedback": None,
            "is_safe": True,
            
            # PHASE 10.5: Advanced Safety
            "safety_result": None,
            "disclaimer_type": None,
            "is_reframed": False,

            # PHASE 12: Validation initialization
            "validation_result": None,
            "validation_strength": None,
            "validation_can_proceed": True,
            "validation_query_type": None,
            "validation_disclaimer": None,

            # Context management fields (populated externally by chat_stateless.py but
            # must be present in initial_state to satisfy TypedDict contract)
            "conversation_summary": None,
            "intent_analysis": None,
            "resolution_result": None,
        }

        
        # Run through graph
        final_state = self.graph.invoke(initial_state)
        
        # Calculate processing time
        final_state['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        return final_state
    
    def process_query_stream(
        self,
        query: str,
        user_id: str,
        conversation_history: Optional[List[Dict]] = None,
        session_data: Optional[Dict] = None
    ):
        """
        Process query with streaming response generation.
        
        Yields:
            dict: Chunks with 'chunk' key for streaming tokens, 
                  final dict with 'answer' and metadata
        """
        start_time = datetime.now()
        
        initial_state: NakshatraState = {
            "query": query,
            "user_id": user_id,
            "conversation_history": conversation_history, # Preserved as None for tiered lookup
            "session_data": session_data,
            "user_profile": None,
            "authenticated": False,
            "intent": None,
            "confidence": 0.0,
            "intent_reasoning": "",
            "cached": False,
            "detected_language": "hi-lat",
            "original_query": query,
            "chart_data": None,
            "dasha_data": None,
            "transit_data": None,
            "knowledge_chunks": None,
            "answer": "",
            "error": None,
            "processing_time": 0.0,
            "messages": [],
            # PHASE 9 Fix: Use explicit user preference or default to 'vedic'. Do NOT detect from query.
            "persona_type": "vedic",
            
            # PHASE 10: Validation Init
            
            # PHASE 10: Validation Init
            "validation_attempts": 0,
            "validation_feedback": None,
            "is_safe": True
        }
        
        # Run through graph (non-streaming for routing & preparation)
        final_state = self.graph.invoke(initial_state)
        
        # Calculate processing time
        final_state['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # Always yield the final state with the answer
        yield final_state



# ========================================================================
# FOR TESTING
# ========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ENHANCED ORCHESTRATOR - Integration Test")
    print("=" * 70)
    print()
    print("This orchestrator now uses REAL VedicEngine calculations!")
    print()
    print("Changes made:")
    print("  1. Auto-loads calculation tools from src/tools/tools.py")
    print("  2. _handle_calculation_node uses real chart calculations")
    print("  3. _handle_rag_node uses real chart/dasha/transit calculations")
    print("  4. _build_prediction_prompt uses rich chart data structure")
    print()
    print("=" * 70)


# ========================================================================
# FACTORY FUNCTION (for test compatibility)
# ========================================================================

def create_enhanced_orchestrator(
    intent_classifier=None,
    hybrid_retriever=None,
    prompt_builder=None,
    calculation_tools=None,
    llm=None,
    fast_llm=None
):
    """
    Factory function to create an EnhancedLangGraphOrchestrator.
    
    This is a convenience function for tests and external code.
    """
    return EnhancedLangGraphOrchestrator(
        intent_classifier=intent_classifier,
        hybrid_retriever=hybrid_retriever,
        prompt_builder=prompt_builder,
        calculation_tools=calculation_tools,
        llm=llm,
        fast_llm=fast_llm
    )