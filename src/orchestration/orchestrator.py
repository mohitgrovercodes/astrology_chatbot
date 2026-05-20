# src\orchestration\orchestrator.py
"""
Enhanced LangGraph Orchestrator with REAL Calculation Integration.

UPDATED: Now uses actual VedicEngine calculations (no placeholders!)

4-way routing:
1. CHITCHAT -> Quick response
2. NEEDS_CALCULATION -> Real birth chart calculation
3. NEEDS_RAG -> Knowledge + Real chart data + Interpretation/Prediction
4. RAG_ONLY -> Knowledge only
"""

from datetime import datetime
from config.logger import get_logger
from src.utils.localization import get_localization_manager

logger = get_logger("orchestrator")
from src.safety.constitution import get_constitution_injection
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Tuple
import random
import re
from src.ai.voice_charter import (
    get_voice_charter,
    get_response_structure_policy,
    pick_initial_closing,
)

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
    logger.info("[VALIDATION] vedic_validation_engine_v2 not found - validation disabled")
    VALIDATION_AVAILABLE = False
    
try:
    from src.engines.vedic.chart_analyzer import ChartAnalyzer, analyze_chart
    from src.validation.chart_synthesis_engine import ChartSynthesisEngine, synthesize_chart_analysis
    ENHANCED_ANALYSIS_AVAILABLE = True
except ImportError:
    logger.info("[ENHANCED_ANALYSIS] chart_analyzer/synthesis_engine not found - using basic analysis")
    ENHANCED_ANALYSIS_AVAILABLE = False

try:
    from src.prediction.factor_scorer import score_factors, FactorPlan
    FACTOR_SCORER_AVAILABLE = True
except ImportError:
    logger.info("[FACTOR_SCORER] factor_scorer not found - focus-factor block disabled")
    FACTOR_SCORER_AVAILABLE = False

try:
    from src.prediction.answer_planner import build_answer_plan, AnswerPlan
    ANSWER_PLANNER_AVAILABLE = True
except ImportError:
    logger.info("[ANSWER_PLANNER] answer_planner not found - committed plan disabled")
    ANSWER_PLANNER_AVAILABLE = False

try:
    from src.prediction.accuracy_gate import check_factor_accuracy
    ACCURACY_GATE_AVAILABLE = True
except ImportError:
    logger.info("[ACCURACY_GATE] accuracy_gate not found - factor accuracy check disabled")
    ACCURACY_GATE_AVAILABLE = False

try:
    from src.rag.memory_writer import maybe_store_user_facts_async
    MEMORY_WRITER_AVAILABLE = True
except ImportError:
    logger.info("[MEMORY_WRITER] memory_writer not found - user fact storage disabled")
    MEMORY_WRITER_AVAILABLE = False

from src.prompts.few_shot_selector import get_few_shot_block
from src.orchestration.orchestrator_validation_helpers import (
    detect_query_type,
    determine_validation_tier,
    determine_live_chat_rule_cap,
    is_analysis_only_request,
    prepare_chart_for_validation,
    should_hard_halt,
    build_halt_response,
    build_validation_disclaimer,
    format_validation_for_prompt
)
from src.orchestration.phase_resolver import (
    get_phase,
    get_phase_data,
    resolve_response_type,
    resolve_phase_transition,
    make_phase_data as make_phase_data_dict,
)
from src.orchestration.response_quality import (
    assess_initial_timeline_quality,
    assess_detailed_answer_quality,
    build_initial_timeline_rewrite_prompt,
    build_detailed_quality_rewrite_prompt,
    build_coherence_hint,
    analyze_query_context,
    inject_deterministic_initial_timeline_diversity,
    collect_recent_cross_topic_window_keys,
    collect_recent_planet_factors,
    collect_future_candidate_window_keys,
    collect_future_timing_years,
    extract_month_year_range_keys,
    filter_non_ended_range_keys,
    infer_topic_from_text,
    assess_timeline_layer_coverage,
    analyze_timeline_overlap,
    llm_check_future_favorable,
)
from src.prediction.astro_intelligence_layer import (
    build_astro_evidence,
    format_evidence_for_prompt,
)

# Module-level chitchat keyword map — single source of truth shared with SemanticFrame.
# _classify_intent_node uses this instead of a copy-pasted inline dict.
try:
    from src.ai.semantic_frame import _CHITCHAT_KEYWORD_ROUTES as _MODULE_CHITCHAT_KW_ROUTES
except ImportError:
    _MODULE_CHITCHAT_KW_ROUTES = None

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
    validation_debug: Optional[Dict]

    # NEW: Context Management Fields
    conversation_summary: Optional[str]      # LLM-generated summary
    intent_analysis: Optional[Dict]          # From context manager
    resolution_result: Optional[Dict]        # From semantic interpreter

    # Progressive Disclosure Phase
    conversation_phase: Optional[Dict]       # Phase data for progressive disclosure
    astro_evidence: Optional[Dict]           # Deterministic evidence payload
    _detailed_followup: Optional[str]        # Pre-generated cross-domain follow-up question for AWAITING_DETAIL→FOLLOWUP_LOOP

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
            logger.info("[LANGGRAPH] Loading calculation tools...")
            calculation_tools = get_calculation_tools()
            logger.info(f"[LANGGRAPH] Loaded {len(calculation_tools)} calculation tools")
        
        self.calculation_tools = calculation_tools

        # [NEW] Auto-load prompt builder if not provided
        if prompt_builder is None:
            try:
                from src.ai.prompt_builder import PromptBuilder
                logger.info("[LANGGRAPH] Auto-loading PromptBuilder...")
                prompt_builder = PromptBuilder()
            except ImportError as e:
                logger.info(f"[LANGGRAPH] [ERROR] Failed to auto-load PromptBuilder: {e}")
        
        self.prompt_builder = prompt_builder

        # [NEW] Auto-load intent classifier if not provided
        if intent_classifier is None:
            try:
                from src.ai.intent_classifier import LLMIntentClassifier
                logger.info("[LANGGRAPH] Auto-loading LLMIntentClassifier...")
                intent_classifier = LLMIntentClassifier(llm=fast_llm or llm)
            except ImportError as e:
                logger.info(f"[LANGGRAPH] [ERROR] Failed to auto-load LLMIntentClassifier: {e}")
        
        self.intent_classifier = intent_classifier
        
        # [PHASE 6] Auto-load LLM if not provided
        if llm is None:
            from src.llm.factory import LLMFactory
            logger.info("[LANGGRAPH] Auto-loading default LLM...")
            llm = LLMFactory.create()
            
        self.llm = llm  # Quality LLM for responses
        self.llm_json = None  # Initialized on first structured call (JSON mode)
        self.fast_llm = fast_llm or llm  # Fast LLM for classification (fallback to quality LLM)
        
        # [DONE] Connect fast LLM to intent classifier
        if hasattr(self.intent_classifier, 'set_llm') and self.fast_llm is not None:
            self.intent_classifier.set_llm(self.fast_llm)
            logger.info("[LANGGRAPH] Fast LLM connected to intent classifier")
        
        # PHASE 10.5: Initialize new safety components
        self.safety_classifier = create_safety_classifier(llm=self.fast_llm)
        self.input_validator = InputValidator()
        
        # PHASE 11: Initialize Semantic Router for Chitchat
        # PERF: Use add_routes_batch() → single OpenAI API call for ALL routes.
        #       Embeddings are disk-cached so subsequent restarts load in <1s.
        self.semantic_router = SemanticRouter()
        if self.semantic_router.model:
            self.semantic_router.add_routes_batch([
                {
                    "name": "greeting",
                    "examples": [
                        "hi", "hello", "hey", "namaste", "namaskaram", "vanakkam", "hola",
                        "good morning", "good evening", "good afternoon", "howdy",
                        "wassup", "sup", "yo", "greetings", "salaam", "bonjour"
                    ],
                    "metadata": {"type": "greeting", "subtype": "simple_greeting"},
                },
                {
                    # Route 2b must appear BEFORE identity so the router resolves correctly
                    "name": "personal_profile_query",
                    "examples": [
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
                    "metadata": {"type": "chitchat", "subtype": "personal_profile_query"},
                },
                {
                    "name": "identity",
                    "examples": [
                        "who are you", "what are you", "tell me about yourself",
                        "what can you do", "introduce yourself",
                        "what is your name", "what's your name",
                        "kaun ho tum", "kya ho tum", "aap kaun hain",
                        "aapka naam kya hai", "tumhara naam kya hai",
                    ],
                    "metadata": {"type": "chitchat", "subtype": "identity"},
                },
                {
                    "name": "gratitude",
                    "examples": [
                        "thanks", "thank you", "appreciate it", "grateful", "thankyou",
                        "dhanyavad", "shukriya", "dhanyawad", "shukriya-ji"
                    ],
                    "metadata": {"type": "chitchat", "subtype": "gratitude"},
                },
                {
                    "name": "wellbeing",
                    "examples": [
                        "how are you", "how's it going", "what's up", "how do you do",
                        "kaise ho", "kya haal hai", "all good"
                    ],
                    "metadata": {"type": "chitchat", "subtype": "wellbeing"},
                },
                {
                    "name": "closure",
                    "examples": [
                        "ok", "okay", "got it", "understood", "alright", "sure",
                        "theek hai", "samajh gaya", "thik hai", "achha",
                        "fine", "makes sense"
                    ],
                    "metadata": {"type": "chitchat", "subtype": "closure"},
                },
                {
                    "name": "farewell",
                    "examples": [
                        "bye", "goodbye", "see you", "talk later", "take care",
                        "alvida", "khuda hafiz", "catch you later"
                    ],
                    "metadata": {"type": "chitchat", "subtype": "farewell"},
                },
            ])
        
        # PHASE 12: Initialize Validation Engine
        self.validation_engine = None
        self.validation_enabled = VALIDATION_AVAILABLE
        
        if self.validation_enabled:
            logger.info("[VALIDATION] Validation engine enabled")

        self.graph = self._build_graph()
        
        logger.info("[LANGGRAPH] [SUCCESS] Enhanced orchestrator initialized")
        logger.info("[LANGGRAPH] Routes: CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY")
        logger.info("[LANGGRAPH] Safety guardrails enabled (Phase 6)")

        self.chart_analyzer = None
        self.synthesis_engine = None
        
        if ENHANCED_ANALYSIS_AVAILABLE:
            try:
                self.chart_analyzer = ChartAnalyzer()
                self.synthesis_engine = ChartSynthesisEngine(
                    indexed_rules_path="optimized/indexed_rules.json",
                    tiered_rules_path="optimized/tiered_rules.json"
                )
                logger.info("[ENHANCED_ANALYSIS] Engines initialized")
            except Exception as e:
                logger.info(f"[ENHANCED_ANALYSIS] Init failed: {e}")
    
    def _build_graph(self):
        """Build LangGraph workflow."""
        logger.info("[LANGGRAPH] Building enhanced workflow graph...")
        
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
        logger.info("[LANGGRAPH] Compiling workflow...")
        return workflow.compile()
        
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def _authenticate_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1: Authenticate user and merge session data."""
        # Check if profile is already provided (e.g., from external context)
        if state.get('user_profile'):
            logger.info(f"[AUTH] Using provided user profile for: {state['user_id']}")
            state['authenticated'] = True
        else:
            logger.info(f"[AUTH] Authenticating user: {state['user_id']}")
            
            # Use UserManager ONLY if it exists (Bypassed in stateless production)
            if self.user_manager and self.user_manager.user_exists(state['user_id']):
                # Load profile from DB
                user_profile = self.user_manager.get_user_profile(state['user_id'])
                if user_profile:
                    state['user_profile'] = user_profile.to_dict()
                    state['authenticated'] = True
                    logger.info(f"[AUTH] [FALLBACK] Loaded profile from database for {state['user_id']}")
                    # Update last active
                    self.user_manager.update_last_active(state['user_id'])
            else:
                if not self.user_manager:
                    logger.info(f"[AUTH] [INFO] Stateless mode: No UserManager provided")
                else:
                    logger.info(f"[AUTH] [INFO] User not in DB: {state['user_id']}")
                state['user_profile'] = {}
                state['authenticated'] = False

        # SESSION DATA OVERWRITES DB DATA (Priority Tier)
        session_data = state.get('session_data')
        if session_data:
            logger.info(f"[AUTH] [PRIORITY] Merging session mapping for {state['user_id']}")
            if not state['user_profile']:
                state['user_profile'] = {}

            # Promoting internal state keys (Priority injection)
            # NOTE: Do NOT do user_profile.update(session_data) — it pollutes user_profile
            # with chart_data, dasha_data, transit_data, summary, intent_analysis etc.
            internal_keys = ['chart_data', 'dasha_data', 'transit_data', 'detected_language', 'persona_type', 'voice_preferences']
            for key in internal_keys:
                if key in session_data:
                    logger.info(f"[AUTH] [PRIORITY] Using injected context: {key}")
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
                logger.info(f"[AUTH] [FALLBACK] Loading conversation history from database for {state['user_id']}")
                state['conversation_history'] = self.user_manager.get_history(state['user_id'], limit=5)
            else:
                state['conversation_history'] = []
        else:
            logger.info(f"[AUTH] [PRIORITY] Using injected conversation history ({len(state['conversation_history'])} messages)")

        return state

    def _detect_language_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1.5: Detect query language using library-based detection with LLM fallback."""
        from src.locales.language_detector import get_language_detector

        # Always detect language from the user's ORIGINAL text (before any semantic
        # expansion or internal rewriting). This guarantees that the chatbot replies
        # in the same language and script the user actually used, instead of switching
        # to English when the semantic interpreter rewrites the query.
        _session_data = state.get('session_data') or {}
        query = _session_data.get('original_user_question') or state['query']
        logger.info(f"[LANG] Detecting language for original user text: '{query[:30]}...'")

        # ── Session language prior ──────────────────────────────────────────────
        # If the session already stored a non-English detected_language from a
        # previous turn (injected via session_data), use it as a fallback for short,
        # low-confidence responses (e.g. "Haan batao", "Theek hai", "OK").
        # This prevents langdetect from flipping to English on short Hinglish phrases.
        _session_lang = state.get('detected_language')  # injected by authenticate_node
        _session_lang_is_indian = (
            _session_lang and _session_lang != 'en' and _session_lang in {
                'hi', 'hi-lat', 'ta', 'ta-lat', 'te', 'te-lat',
                'ml', 'ml-lat', 'mr', 'mr-lat', 'pa', 'pa-lat'
            }
        )
        _query_word_count = len(query.strip().split())
        # ───────────────────────────────────────────────────────────────────────

        # Use new LanguageDetector with LLM fallback
        detector = get_language_detector(llm=self.fast_llm)

        try:
            # Get language with confidence
            detected_lang, confidence = detector.detect_with_confidence(query)

            # ── Session-prior fallback ──────────────────────────────────────────
            # If the freshly detected language is English BUT:
            #   (a) the session was previously non-English, AND
            #   (b) the query is short (≤ 4 words), AND
            #   (c) confidence is not high (≤ 0.75)
            # → trust the session language (the user didn't switch languages).
            if (
                detected_lang == 'en'
                and _session_lang_is_indian
                and _query_word_count <= 4
                and confidence <= 0.75
            ):
                logger.info(
                    f"[LANG] Low-confidence English ({confidence:.2f}) on short query "
                    f"({_query_word_count}w) — keeping session language: {_session_lang}"
                )
                detected_lang = _session_lang
                confidence = 0.80  # synthetic confidence for the inherited value
            # ───────────────────────────────────────────────────────────────────

            state['detected_language'] = detected_lang
            state['original_query'] = query

            # Log detection method
            method = "library" if confidence > 0.7 else "LLM fallback"
            logger.info(f"[LANG] Detected: {detected_lang} ({method}, confidence: {confidence:.2f})")

        except Exception as e:
            logger.info(f"[LANG] Detection error: {e}, defaulting to 'en'")
            state['detected_language'] = _session_lang if _session_lang_is_indian else 'en'
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

        # ── Progressive Disclosure Phase Bypass ──────────────────────────────
        # Short affirmative/negative responses to a bot's follow-up question must
        # bypass the safety classifier (it sees them without the prior bot question
        # and wrongly flags "haan" / "samjhao" as out-of-scope).
        from src.ai.context_manager import PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP
        _safety_phase = get_phase(state)
        _safety_orig_q = (state.get('session_data') or {}).get('original_user_question') or query
        _is_short = len(_safety_orig_q.strip().split()) <= 5
        _last_bot_safety = next(
            (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
             if m.get('role') == 'assistant'), ''
        )
        _safety_resp_type = resolve_response_type(
            _safety_orig_q, _safety_phase,
            last_bot_msg=_last_bot_safety,
            fast_llm=getattr(self, 'fast_llm', None),
            log=logger,
        )
        if _safety_phase in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP) and (
            _safety_resp_type in ('AFFIRMATIVE', 'NEGATIVE') or _is_short
        ):
            logger.info(f"[SAFETY] Phase bypass: phase={_safety_phase}, response={_safety_resp_type} — skipping safety classifier")
            state['is_safe'] = True
            return state
        # ─────────────────────────────────────────────────────────────────────

        logger.info(f"[SAFETY] Checking query safety...")

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
                logger.info(f"[SAFETY] BLOCKED: {safety_result.decision.reason}")
                
                # WORKAROUND: Don't block chitchat queries
                CHITCHAT_REASONS = ['greeting', 'identity', 'gratitude', 'wellbeing', 'farewell', 'closure']
                if safety_result.decision.reason in CHITCHAT_REASONS:
                    logger.info(f"[SAFETY] Chitchat query - allowing through")
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

                # Language-aware rendering for safety responses: translate templates
                # into the user's detected language/script where possible, so even
                # soft blocks and warnings respect the user's language choice.
                try:
                    detected_lang = (state.get("session_data") or {}).get("detected_language") or "en"
                    if detected_lang != "en":
                        llm = getattr(self, "fast_llm", None)
                        if llm is not None:
                            from src.utils.localization import get_localization_manager
                            loc = get_localization_manager()
                            lang_name = loc.get_language_name(detected_lang)
                            if "-lat" in detected_lang:
                                script_instruction = f" Respond in {lang_name} using ROMAN ALPHABET only (no native script)."
                            else:
                                script_instruction = f" Respond entirely in {lang_name} (native script)."

                            prompt = (
                                "You are a professional Vedic astrologer translating a safety / disclaimer message for a user. "
                                "Translate the following message accurately, keeping the same warm and respectful tone."
                                f"{script_instruction}\n\n"
                                f"Message:\n{response}\n\n"
                                "Translation (ONLY output the exact translated message without quotes):"
                            )
                            _resp = llm.invoke(prompt)
                            translated = (getattr(_resp, "content", str(_resp)) or "").strip()
                            if translated and len(translated) > 10:
                                response = translated
                except Exception as _e:
                    logger.info(f"[SAFETY] Translation of safety response failed or skipped: {_e}")
                
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
                logger.info(f"[SAFETY] [REFRAME] Reframing query: {state['query']} -> {safety_result.processed_query}")
                state['original_query'] = state['query']
                state['query'] = safety_result.processed_query
                state['is_reframed'] = True

            # If conditional, flag for disclaimer
            if safety_result.needs_disclaimer:
                state['needs_disclaimer'] = safety_result.decision.disclaimer_type

            # Safe to proceed
            state['is_safe'] = True
            logger.info(f"[SAFETY] [OK] Safe to proceed")
            
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
                logger.info(f"[AGE_CHECK] Validated DOB live: {dob} -> {dob_validation.get('issue') or 'ok'} (age {dob_validation.get('age_years')}y)")
            else:
                dob_validation = {}

            # Check if DOB is invalid — use `is False` not `== False` so that a
            # missing/None 'valid' key (empty dict case) does not silently pass through.
            if dob_validation.get('valid') is False:
                logger.info(f"[AGE_CHECK] Invalid DOB: {dob_validation.get('issue')}")
                state['intent'] = "DATA_VALIDATION_ERROR"
                state['answer'] = dob_validation.get('message')
                return state

            # Check age-appropriateness for query
            age_years = dob_validation.get('age_years', 0)
            query_type = AgeValidator.detect_query_type(state.get('query', ''))

            if query_type:
                logger.info(f"[AGE_CHECK] Query type: {query_type}, User age: {age_years}")
                
                language = state.get('detected_language', 'en')
                appropriateness = AgeValidator.is_query_appropriate(
                    query_type=query_type,
                    age_years=age_years,
                    language=language
                )
                
                if not appropriateness['appropriate']:
                    logger.info(f"[AGE_CHECK] ⚠️  Not appropriate: {appropriateness['reason']}")
                    state['intent'] = "AGE_INAPPROPRIATE"
                    state['answer'] = appropriateness['message']
                    return state  # Or your return format

                logger.info(f"[AGE_CHECK] Age-appropriate query")

                

        except Exception as e:
            logger.info(f"[SAFETY] [ERROR] Error in safety check: {e}")
            import traceback
            traceback.print_exc()
            # On error, allow to proceed (fail open for availability)
            state['is_safe'] = True
        
        return state

    def _classify_intent_node(self, state: NakshatraState) -> NakshatraState:
        """Node 2: Classify intent."""
        logger.info(f"[INTENT] Classifying query: '{state['query'][:50]}...'")

        # == PROGRESSIVE DISCLOSURE PHASE GUARD ================================
        # When the bot asked "Want more details?" or asked a follow-up question,
        # short affirmative/negative responses must be routed to RAG_WITH_CALCULATION
        # (not CHITCHAT) so the progressive disclosure flow continues.
        from src.ai.context_manager import PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP
        current_phase = get_phase(state)

        if current_phase in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP):
            _original_q = (state.get('session_data') or {}).get('original_user_question') or state['query']
            _intent_analysis = (state.get('session_data') or {}).get('intent_analysis', {})
            _last_bot_intent = next(
                (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                 if m.get('role') == 'assistant'), ''
            )
            user_response = resolve_response_type(
                _original_q, current_phase,
                intent_info=_intent_analysis,
                last_bot_msg=_last_bot_intent,
                fast_llm=getattr(self, 'fast_llm', None),
                log=logger,
            )
            logger.info(f"[INTENT] [PHASE_GUARD] original='{_original_q[:40]}' -> response_type={user_response}")
            if user_response in ('AFFIRMATIVE', 'NEGATIVE'):
                logger.info(f"[INTENT] [PHASE_GUARD] Phase={current_phase}, response={user_response} -> RAG_WITH_CALCULATION")
                state['intent'] = 'RAG_WITH_CALCULATION'
                state['confidence'] = 0.95
                state['intent_reasoning'] = f'Progressive disclosure: {user_response} in {current_phase}'
                state['is_safe'] = True
                return state
        # ─────────────────────────────────────────────────────────────────────

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
            logger.info(f"[INTENT] [CONTINUATION] CONTINUATION GUARD: routed to RAG_WITH_CALCULATION (history={len(history)} msgs)")

            state['intent'] = 'RAG_WITH_CALCULATION'
            state['confidence'] = 0.85
            state['intent_reasoning'] = 'Bare continuation query with active conversation'
            state['is_safe'] = True
            return state
        # ─────────────────────────────────────────────────────────────────────

        # == UNIFIED SEMANTIC FRAME FAST PATH ==================================
        # If chat_stateless built a SemanticFrame for this turn, use frame.route
        # directly. This replaces the keyword-chitchat → semantic-router →
        # LLMIntentClassifier cascade — the frame already resolved all of that
        # in ONE call (or one fast-path hit). Phase guards above still get to
        # override before we reach this point.
        _frame_dict = (state.get('session_data') or {}).get('semantic_frame')
        if _frame_dict and _frame_dict.get('route'):
            _frame_route = _frame_dict.get('route')
            state['intent'] = _frame_route
            state['confidence'] = float(_frame_dict.get('route_confidence') or _frame_dict.get('confidence') or 0.85)
            state['intent_reasoning'] = f"semantic_frame.{_frame_dict.get('source', 'unknown')}: {_frame_dict.get('reasoning', '')[:120]}"
            state['cached'] = _frame_dict.get('source') in ('cache', 'keyword', 'semantic_router')
            if _frame_dict.get('chitchat_subtype'):
                state['chitchat_subtype'] = _frame_dict['chitchat_subtype']
            logger.info(
                f"[INTENT] [FRAME] -> {_frame_route} "
                f"(source={_frame_dict.get('source')}, conf={state['confidence']:.2f})"
            )
            return state
        # ─────────────────────────────────────────────────────────────────────

        # Keyword pre-check for all chitchat routes.
        # Short single-word / common phrases (especially multilingual ones) often fall
        # below the 0.7 embedding threshold because the mean route vector is diluted
        # across many diverse examples. Exact keyword matching bypasses this reliably.
        #
        # SINGLE SOURCE OF TRUTH: uses module-level import from semantic_frame.
        # If that import failed at startup, falls back to a minimal inline dict so
        # the node never crashes.
        _CHITCHAT_KEYWORD_ROUTES = _MODULE_CHITCHAT_KW_ROUTES or {
            'hi': 'greeting', 'hello': 'greeting', 'hey': 'greeting',
            'namaste': 'greeting', 'bye': 'farewell', 'goodbye': 'farewell',
            'thanks': 'gratitude', 'thank you': 'gratitude',
            'ok': 'closure', 'okay': 'closure', 'got it': 'closure',
        }
        q_normalized = state['query'].lower().strip().rstrip('!.')
        _kw_route = _CHITCHAT_KEYWORD_ROUTES.get(q_normalized)
        if _kw_route:
            logger.info(f"[INTENT] Keyword chitchat match: '{state['query']}' -> {_kw_route}")
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
            logger.info(f"[INTENT] Semantic Chitchat Match: '{state['query']}' -> {chitchat_match.name} ({chitchat_match.confidence:.2f})")
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
            logger.info(f"[INTENT] Using safety result from safety_check node: {category}")
            if disclaimer:
                logger.info(f"[INTENT] Disclaimer carried forward: {disclaimer}")
        
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
        logger.info(f"[INTENT] [LLM] -> {state['intent']} (confidence: {state['confidence']:.2f})")
        
        return state
    
    def _handle_chitchat_node(self, state: NakshatraState) -> NakshatraState:
        """Node 3a: Handle conversational queries with semantic understanding."""
        logger.info(f"[CHITCHAT] Response for language: {state.get('detected_language', 'en')}")
        
        user_name = state['user_profile'].get('name', 'User')
        query = state['query']
        lang = state.get('detected_language', 'en')
        conversation_history = state.get('conversation_history', [])
        
        # Import greeting functions
        from src.ai.personas import get_contextual_greeting, get_greeting

        # Deterministic profile-query fast-path:
        # profile detail questions should never rely on semantic threshold/LLM fallback.
        if self._is_personal_profile_query(query):
            logger.info("[CHITCHAT] [PROFILE] Deterministic profile-query detection hit")
            state['answer'] = self._answer_personal_profile_query(
                query=query,
                user_profile=state['user_profile'],
                language=lang,
                chart_data=state.get('chart_data')
            )
            return state
        
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
            logger.info(f"[CHITCHAT] Semantic match: {match_type} (confidence: {confidence:.2f})")
            
            # 0. PERSONAL PROFILE QUERIES — "Mera naam kya hai?", "What is my name?"
            #    Must be checked BEFORE identity to avoid misrouting.
            if match_type == "personal_profile_query":
                logger.info(f"[CHITCHAT] [PROFILE] Match found. Calling profile helper...")
                state['answer'] = self._answer_personal_profile_query(
                    query=query, 
                    user_profile=state['user_profile'], 
                    language=lang,
                    chart_data=state.get('chart_data')
                )
                logger.info(f"[CHITCHAT] [PROFILE] Result length: {len(state['answer'])} characters")
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
        logger.info(f"[CHITCHAT] No specific semantic match or unhandled type. Using LLM fallback.")
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
            
            # PHASE 6: Tiered History Support — use full CONVERSATION_CONTEXT_WINDOW (10 messages)
            history_context = ""
            if state.get('conversation_history'):
                history_turns = state['conversation_history'][-10:]
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
            logger.info(f"[CHITCHAT] [LLM] Result: {len(state['answer'])} chars")
            
        except Exception as e:
            logger.info(f"[CHITCHAT] Error generating response: {e}")
            state['answer'] = get_greeting(lang)

        return state


    # ------------------------------------------------------------------
    # PERSONAL PROFILE QUERY DETECTION
    # ------------------------------------------------------------------
    def _is_personal_profile_query(self, query: str) -> bool:
        """Return True when query asks for user's initialized profile details."""
        q = (query or "").lower().strip()
        triggers = [
            "mera naam", "mera name", "what is my name", "what's my name", "do you know my name",
            "meri dob", "date of birth", "birth date", "janam kab", "janm tithi",
            "place of birth", "birthplace", "birth place", "where was i born", "kahan paida",
            "janam sthan", "janmsthan", "birth city",
            "mera sign", "meri rashi", "mera lagna", "moon sign", "sun sign", "ascendant",
            "mere baare", "what do you know about me", "tell me my details",
        ]
        return any(t in q for t in triggers)

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
        logger.info(f"[PROFILE_DEBUG] Answering profile query: {query}")
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
                "Abhi system mein aapki details uplabdh nahi hain. "
                "Kripya app mein apna profile update karein."
            )
        return (
            "Your details are not available in the system yet. "
            "Please update your profile in the app."
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
        logger.info(f"[CLARIFICATION] Asking user to specify intent")
        
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
        
        logger.info(f"[CLARIFICATION] Topic: {topic}, Language: {lang}")
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
            logger.info(f"[CALC] [PRIORITY] Using injected chart data for {user_id}")
            return state['chart_data'], None

        # TIER 2: Database Cache (Fallback)
        cached_json = user_profile.get('birth_chart_cache')
        if cached_json:
            try:
                logger.info(f"[CALC] [FALLBACK] Using cached chart for {user_id}. Deserializing...")
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
                logger.info(f"[CACHE] [WARN] Failed to load cached chart: {e}")
        
        # No cache or error: Calculate fresh
        logger.info(f"[CACHE] No cache found. Calculating fresh chart for {user_id}...")
        try:
            # Standardize field names (UserProfile uses date_of_birth)
            dob = user_profile.get('date_of_birth')
            tob = user_profile.get('time_of_birth', '12:00:00')
            lat = user_profile.get('latitude')
            lon = user_profile.get('longitude')
            tz = user_profile.get('timezone', 'Asia/Kolkata')
            
            if not dob or lat is None or lon is None:
                logger.info(f"[CACHE] [WARN] Missing birth data for {user_id}: dob={dob}, lat={lat}, lon={lon}")
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
            logger.info(f"[CACHE] [ERROR] Fresh calculation failed: {e}")
            return None, None

    def _handle_calculation_only_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3b: CALCULATION_ONLY - Return raw chart data without interpretation.
        Uses VedicEngine, NO RAG, NO LLM interpretation.
        """
        logger.info("[CALCULATION_ONLY] Generating raw chart data")
        
        user_profile = state['user_profile']
        query = state['query'].lower()
        
        # Check if user has birth data
        if not user_profile.get('date_of_birth'):
            lang = state.get('detected_language', 'en')
            if lang in ('hi', 'hi-lat'):
                state['answer'] = "System mein aapki janm details uplabdh nahi hain. Kripya app mein apna profile update karein."
            else:
                state['answer'] = "Your birth details are not available in the system. Please update your profile in the app."
            return state
        
        # FIX #4: Check if user is asking about their profile/birth data
        profile_keywords = ['dob', 'date of birth', 'birth date', 'birthday', 
                           'birth time', 'time of birth', 'birth place', 
                           'place of birth', 'born', 'when was i born', 
                           'where was i born', 'what time was i born']
        
        if any(keyword in query for keyword in profile_keywords):
            # User asking about their own birth details - provide direct answer
            logger.info("[CALCULATION_ONLY] User asking about profile data")
            
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
            
            logger.info(f"[CALCULATION_ONLY] Chart: Lagna={chart_data.get('lagna', {}).get('sign', 'Unknown')}, Rashi={chart_data.get('planets', {}).get('MOON', {}).get('sign', 'Unknown')}")
            
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

            # Calculate current dasha if missing/stale
            _today_dt = datetime.utcnow().date()
            _dasha_existing = state.get('dasha_data') or {}

            def _parse_iso_date_for_staleness(value: Any):
                if value is None:
                    return None
                if hasattr(value, "date") and not isinstance(value, str):
                    try:
                        return value.date()
                    except Exception:
                        return None
                if isinstance(value, str):
                    v = value.split("T")[0].strip()
                    try:
                        return datetime.strptime(v, "%Y-%m-%d").date()
                    except Exception:
                        return None
                return None

            _ad_end_raw = (_dasha_existing.get('antardasha') or {}).get('end')
            _pd_end_raw = (_dasha_existing.get('pratyantardasha') or {}).get('end')
            _ad_end_dt = _parse_iso_date_for_staleness(_ad_end_raw)
            _pd_end_dt = _parse_iso_date_for_staleness(_pd_end_raw)
            _dasha_stale = (
                (_ad_end_dt is not None and _ad_end_dt < _today_dt)
                or (_pd_end_dt is not None and _pd_end_dt < _today_dt)
            )
            if _dasha_stale:
                logger.info(
                    f"[DASHA STALE] Clearing cached dasha_data (calculation_only): "
                    f"antardasha_end={_ad_end_raw!r} pratyantardasha_end={_pd_end_raw!r} < TODAY."
                )
                state['dasha_data'] = None

            if not state.get('dasha_data'):
                try:
                    logger.info("[CALCULATION_ONLY] Calculating dasha...")
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
                    logger.info(f"[CALCULATION_ONLY] Dasha calculation error: {e}")

            # Calculate current transits if missing
            if not state.get('transit_data'):
                try:
                    logger.info("[CALCULATION_ONLY] Calculating transits...")
                    transit_tool = self.calculation_tools.get('calculate_current_transits')
                    if transit_tool:
                        transit_data = transit_tool.invoke({})
                        if "error" not in transit_data:
                            state['transit_data'] = transit_data
                except Exception as e:
                    logger.info(f"[CALCULATION_ONLY] Transit calculation error: {e}")

        except Exception as e:
            logger.error(f"[ERROR] Calculation failed: {e}")
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
        logger.info("[RAG_WITH_CALCULATION] Personalized prediction flow with validation")
        
        user_profile = state['user_profile']
        
        try:
            # ================================================================
            # STEP 1: Calculate user's chart
            # ================================================================
            if user_profile.get('date_of_birth'):
                logger.info("[RAG_WITH_CALCULATION] Step 1: Calculating user's chart...")
                
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
                            logger.info(f"[RAG_WITH_CALCULATION] Chart ready: Lagna={state['chart_data'].get('lagna') or state['chart_data'].get('ascendant', {}).get('rashi', 'Unknown')}")
                    except Exception as e:
                        logger.info(f"[RAG_WITH_CALCULATION] Chart calculation error: {e}")

                # Calculate current dasha (UN-NESTED from chart check)
                # If cached dasha_data is internally stale (e.g., Antardasha end already
                # passed), do a fresh recalc so Step 2 doesn't leak past-month ranges.
                _today_dt = datetime.utcnow().date()
                _dasha_existing = state.get('dasha_data') or {}

                def _parse_iso_date_for_staleness(value: Any):
                    if value is None:
                        return None
                    if hasattr(value, "date") and not isinstance(value, str):
                        try:
                            return value.date()
                        except Exception:
                            return None
                    if isinstance(value, str):
                        v = value.split("T")[0].strip()
                        try:
                            return datetime.strptime(v, "%Y-%m-%d").date()
                        except Exception:
                            return None
                    return None

                _ad_end_raw = (_dasha_existing.get('antardasha') or {}).get('end')
                _pd_end_raw = (_dasha_existing.get('pratyantardasha') or {}).get('end')
                _ad_end_dt = _parse_iso_date_for_staleness(_ad_end_raw)
                _pd_end_dt = _parse_iso_date_for_staleness(_pd_end_raw)
                _dasha_stale = (
                    (_ad_end_dt is not None and _ad_end_dt < _today_dt)
                    or (_pd_end_dt is not None and _pd_end_dt < _today_dt)
                )
                if _dasha_stale:
                    logger.info(
                        f"[DASHA STALE] Clearing cached dasha_data: "
                        f"antardasha_end={_ad_end_raw!r} pratyantardasha_end={_pd_end_raw!r} < TODAY."
                    )
                    state['dasha_data'] = None

                if not state.get('dasha_data'):
                    try:
                        logger.info("[RAG_WITH_CALCULATION] Calculating dasha...")
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
                                logger.info(f"[RAG_WITH_CALCULATION] Dasha: {dasha_data.get('dasha_sequence', 'Unknown')}")
                    except Exception as e:
                        logger.info(f"[RAG_WITH_CALCULATION] Dasha calculation error: {e}")
                
                # Calculate current transits (UN-NESTED from chart check)
                if not state.get('transit_data'):
                    try:
                        logger.info("[RAG_WITH_CALCULATION] Calculating transits...")
                        transit_tool = self.calculation_tools.get('calculate_current_transits')
                        if transit_tool:
                            transit_data = transit_tool.invoke({})
                            if "error" not in transit_data:
                                state['transit_data'] = transit_data
                                logger.info(f"[RAG_WITH_CALCULATION] Transits for {transit_data.get('date', 'current')}")
                    except Exception as e:
                        logger.info(f"[RAG_WITH_CALCULATION] Transit calculation error: {e}")

            else:
                logger.info("[RAG_WITH_CALCULATION] No birth data. Routing to ask for profile.")
                lang = state.get('detected_language', 'en')
                if lang in ('hi', 'hi-lat'):
                    state['answer'] = "Apki kundli ka vishleshan karne ke liye janm vivran ki avashyakta hai. Kripya app mein apna profile pura karein."
                else:
                    state['answer'] = "To provide a personalized astrological analysis, your birth details are required. Please ensure your profile is complete in the app."
                return state

            # ================================================================
            # STEP 1.25: ENHANCED CHART ANALYSIS (PHASE 13 - NEW)
            # ================================================================
            enhanced_analysis = None
            synthesis = None
            
            if state.get('chart_data') and ENHANCED_ANALYSIS_AVAILABLE and self.chart_analyzer:
                try:
                    logger.info("[ENHANCED_ANALYSIS] Calculating dignities, lords, aspects...")
                    enhanced_analysis = self.chart_analyzer.analyze_chart(state['chart_data'])
                    
                    # Log key findings
                    logger.info(f"[ENHANCED_ANALYSIS] Found {len(enhanced_analysis['dignities'])} planetary dignities")
                    logger.info(f"[ENHANCED_ANALYSIS] Calculated {len(enhanced_analysis['house_lords'])} house lordships")
                    logger.info(f"[ENHANCED_ANALYSIS] Mapped {len(enhanced_analysis['aspects'])} aspect patterns")
                    
                    # Store in state for later use
                    state['enhanced_analysis'] = enhanced_analysis
                    
                except Exception as e:
                    logger.info(f"[ENHANCED_ANALYSIS] Error: {e}")

            # ================================================================
            # STEP 1.5: VALIDATE CHART (PHASE 12 - NEW)
            # ================================================================
            if state.get('chart_data') and VALIDATION_AVAILABLE:
                try:
                    # Fast-path: if chat_stateless already fetched a valid cached
                    # validation result for this session+query_type, reuse it and
                    # skip the expensive LLM-based validation (~34s per call).
                    _cached_val = (state.get('session_data') or {}).get('cached_validation_result')
                    if _cached_val and isinstance(_cached_val, dict) and _cached_val.get('query_type'):
                        _cached_qt = _cached_val['query_type']
                        # Determine the expected query_type from intent domain hint
                        _ia_quick = (state.get('session_data') or {}).get('intent_analysis') or {}
                        _hint_quick = (_ia_quick.get('domain') or '').strip().lower() or None
                        if _hint_quick == 'foreign_travel':
                            _hint_quick = 'foreign'
                        if _hint_quick and _cached_qt == _hint_quick:
                            logger.info(f"[VALIDATION] Using cached result (query_type={_cached_qt}, skipping LLM validation)")
                            state['validation_result'] = _cached_val
                            state['validation_query_type'] = _cached_qt
                            state['validation_strength'] = _cached_val.get('overall_strength', 5.0)
                            state['validation_can_proceed'] = _cached_val.get('can_proceed', True)
                            # Skip to synthesis — jump out of this try block via a flag
                            _validation_used_cache = True
                        else:
                            _validation_used_cache = False
                    else:
                        _validation_used_cache = False

                    logger.info("[VALIDATION] Running validation...")

                    # Detect query type with LLM confirmation, biased by high-level
                    # intent domain from the ContextManager (if available).
                    _ia = (state.get('session_data') or {}).get('intent_analysis') or {}
                    _intent_domain = (_ia.get('domain') or '').strip().lower() or None
                    # If user is affirming a cross-domain follow-up offer, override the
                    # semantic domain BEFORE validation/synthesis so all downstream logic
                    # (query_type, dasha filtering, synthesis) aligns to the pivot topic.
                    try:
                        from src.ai.context_manager import (
                            PHASE_AWAITING_DETAIL as _PAD_PREVAL,
                            PHASE_FOLLOWUP_LOOP as _PFL_PREVAL,
                        )
                        from src.ai.context_manager import detect_user_response_type as _resp_detect
                        _phase_data_preval = get_phase_data(state)
                        _phase_now_preval = _phase_data_preval.get('phase', 'INITIAL')
                        _topic_now_preval = (_phase_data_preval.get('topic') or '').lower()
                        _orig_q_preval = (state.get('session_data') or {}).get('original_user_question') or state.get('query', '')
                        _resp_now_preval = _resp_detect(_orig_q_preval)
                        if _phase_now_preval in (_PAD_PREVAL, _PFL_PREVAL) and _resp_now_preval == 'AFFIRMATIVE':
                            _last_bot_preval = next(
                                (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                                 if m.get('role') == 'assistant'),
                                ''
                            )
                            _pivot_topic_preval = None
                            if _last_bot_preval:
                                import re as _re_preval
                                _sentences_preval = _re_preval.split(r'(?<=[.!?।])\s+', _last_bot_preval.strip())
                                _q_sentences_preval = [s.strip() for s in _sentences_preval if '?' in s]
                                _last_q_preval = _q_sentences_preval[-1].lower() if _q_sentences_preval else ''
                                _domain_kws_preval = {
                                    'marriage': ['shadi', 'shaadi', 'vivah', 'marriage', 'partner', 'spouse', 'love', 'rishta', 'relationship'],
                                    'career': ['career', 'job', 'naukri', 'kaam', 'vyavsay', 'profession', 'business', 'rojgar'],
                                    'finance': ['finance', 'money', 'paisa', 'dhan', 'wealth', 'arthik', 'investment'],
                                    'health': ['health', 'sehat', 'swasthya', 'bimari', 'illness', 'disease'],
                                    'children': ['child', 'children', 'bacche', 'santaan', 'aulad', 'beta', 'beti'],
                                    'foreign': ['foreign', 'videsh', 'abroad', 'overseas', 'travel', 'settlement'],
                                }
                                for _d_preval, _kws_preval in _domain_kws_preval.items():
                                    if any(_kw in _last_q_preval for _kw in _kws_preval):
                                        _pivot_topic_preval = _d_preval
                                        break
                            if _pivot_topic_preval and (
                                _phase_now_preval == _PFL_PREVAL or _pivot_topic_preval != _topic_now_preval
                            ):
                                _intent_domain = _pivot_topic_preval
                                _ia = {**_ia, "domain": _pivot_topic_preval}
                                logger.info(
                                    f"[VALIDATION] Pivot-aware domain override: "
                                    f"{_topic_now_preval or 'none'} -> {_pivot_topic_preval}"
                                )
                            elif _topic_now_preval:
                                # Stabilize repeated-turn validation: for short affirmatives in active
                                # phases, keep domain anchored to current topic when no valid pivot
                                # topic is present.
                                _intent_domain = _topic_now_preval
                                _ia = {**_ia, "domain": _topic_now_preval}
                                logger.info(
                                    f"[VALIDATION] Continuation domain lock applied: "
                                    f"{_topic_now_preval}"
                                )
                    except Exception:
                        pass
                    # Prefer the SemanticFrame's validation_query_type — it was
                    # resolved during the unified LLM call in chat_stateless and
                    # already accounts for divorce→marriage / foreign_travel→foreign
                    # normalization. Pivot-aware overrides above (`_intent_domain`)
                    # still win because they reflect runtime conversation state
                    # the frame couldn't have known.
                    _frame_dict_q = (state.get('session_data') or {}).get('semantic_frame') or {}
                    _frame_qt = _frame_dict_q.get('validation_query_type')
                    if _intent_domain:
                        # Pivot/continuation override applied above; route through detect_query_type
                        # so the override is normalized into the engine's allowed set.
                        query_type = detect_query_type(
                            state['query'],
                            llm=None,                      # no LLM call — just normalization
                            use_llm_confirmation=False,
                            intent_domain_hint=_intent_domain,
                        )
                        logger.info(f"[QUERY_TYPE] Using pivot-aware override: {query_type}")
                    elif _frame_qt:
                        query_type = _frame_qt
                        logger.info(f"[QUERY_TYPE] Using semantic_frame.validation_query_type={query_type}")
                    else:
                        # Frame missing (e.g. orchestrator called directly in tests) — fall
                        # back to the legacy detector so behaviour is preserved.
                        query_type = detect_query_type(
                            state['query'],
                            llm=self.fast_llm if hasattr(self, 'fast_llm') else None,
                            use_llm_confirmation=True,
                            intent_domain_hint=_intent_domain,
                        )
                    state['validation_query_type'] = query_type
                    
                    # Skip validation for general questions
                    if query_type == 'general':
                        logger.info(f"[VALIDATION] Skipping validation for general question")
                    else:
                        # Determine tier using semantic frame + voice_preferences (not just keywords)
                        _frame_for_tier = (state.get('session_data') or {}).get('semantic_frame') or {}
                        _vp_for_tier = state.get('voice_preferences') or {}
                        tier = determine_validation_tier(
                            state['query'],
                            question_mode=_frame_for_tier.get('question_mode', 'summary'),
                            domain=_frame_for_tier.get('domain', 'general'),
                            detail_level=(_vp_for_tier.get('detail_level') or 'balanced'),
                        )
                        live_rule_cap = determine_live_chat_rule_cap(tier, state.get('query', ''))
                        include_yoga_live = True  # always include yoga rules for richer analysis
                        logger.info(
                            f"[VALIDATION] Query: {query_type}, Tier: {tier}, "
                            f"LiveCap: {live_rule_cap}, IncludeYoga: {include_yoga_live}"
                        )
                        
                        # Get or create validation engine
                        if not hasattr(self, 'validation_engine'):
                            self.validation_engine = None
                        
                        if self.validation_engine is None:
                            try:
                                from pathlib import Path
                                rules_path = Path("optimized/tiered_rules.json")
                                
                                if rules_path.exists():
                                    logger.info("[VALIDATION] Initializing engine...")
                                    self.validation_engine = VedicValidationEngineV2(
                                        tiered_rules_path=str(rules_path),
                                        indexed_rules_path="optimized/indexed_rules.json"
                                    )
                                    logger.info("[VALIDATION] [OK] Engine ready")
                                else:
                                    logger.info("[VALIDATION] Rules file not found")
                            except Exception as e:
                                logger.info(f"[VALIDATION] Init failed: {e}")
                        
                        if self.validation_engine:
                            # If a pre-validated cached result already covers this query_type,
                            # skip the expensive LLM-based engine call (~34s) and use it.
                            if _validation_used_cache and state.get('validation_result', {}).get('query_type') == query_type:
                                logger.info(f"[VALIDATION] Skipped engine call — using pre-populated cache for query_type={query_type}")
                            else:
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
                                    live_chat_max_rules=live_rule_cap,
                                    include_yoga_rules_in_live_chat=include_yoga_live,
                                    timeout_sec=None
                                )
                            
                            # Only store/use val_result when we actually ran the engine
                            if not (_validation_used_cache and state.get('validation_result', {}).get('query_type') == query_type):
                                # Store results (also attach upstream intent_analysis so downstream
                                # components can treat this as the canonical semantic label set).
                                state['validation_result'] = {
                                    'query_type': val_result.query_type,
                                    'overall_strength': val_result.overall_strength,
                                    'can_proceed': val_result.can_proceed,
                                    'rules_checked': val_result.rules_checked,
                                    'rules_passed': val_result.passed,
                                    'rules_failed': val_result.failed,
                                    'debug_stats': val_result.debug_stats or {},
                                    'critical_failures': [
                                        {
                                            'rule_id': f.rule_id,
                                            'rule_name': f.rule_name,
                                            'reason': f.reason,
                                            'recommendation': f.recommendation,
                                            'classical_ref': f.classical_ref
                                        }
                                        for f in val_result.critical_failures
                                    ],
                                    'intent_analysis': _ia,
                                }
                                state['validation_debug'] = val_result.debug_stats or {}
                                state['validation_strength'] = val_result.overall_strength
                                state['validation_can_proceed'] = val_result.can_proceed
                                logger.info(f"[VALIDATION] [OK] Strength: {val_result.overall_strength:.1f}/10")
                                logger.info(f"[VALIDATION] Critical failures: {len(val_result.critical_failures)}")
                                logger.info(
                                    "[VALIDATION][DEBUG] pool=%s filtered=%s checked=%s cap=%s include_yoga=%s index=%s",
                                    (val_result.debug_stats or {}).get('rules_initial_pool'),
                                    (val_result.debug_stats or {}).get('rules_after_live_filter'),
                                    val_result.rules_checked,
                                    (val_result.debug_stats or {}).get('live_cap'),
                                    (val_result.debug_stats or {}).get('include_yoga_live'),
                                    (val_result.debug_stats or {}).get('index_used'),
                                )
                                # HARD HALT CHECK (only for extreme cases)
                                if should_hard_halt(val_result.overall_strength, val_result.critical_failures):
                                    logger.info(f"[VALIDATION] [STOP] HARD HALT - Refusing prediction")
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
                                    logger.info(f"[VALIDATION] Added disclaimer for weak chart")
                
                except Exception as e:
                    logger.info(f"[VALIDATION] Error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Don't block on validation errors - proceed without validation
            
            # ================================================================
            # STEP 1.75: RULE-BASED SYNTHESIS (PHASE 13 - NEW)
            # ================================================================
            if ENHANCED_ANALYSIS_AVAILABLE and enhanced_analysis:
                try:
                    # Synthesis query_type chain — single source of truth, no extra LLM call.
                    # 1. Reuse validation_query_type set above (already aligns with frame
                    #    + pivot override).
                    # 2. Else fall back to the SemanticFrame's validation_query_type.
                    # 3. Else fall back to detect_query_type with LLM confirmation
                    #    (only happens when orchestrator was invoked without a frame).
                    query_type_for_synthesis = state.get('validation_query_type')
                    if not query_type_for_synthesis and state.get('chart_data'):
                        _frame_dict_s = (state.get('session_data') or {}).get('semantic_frame') or {}
                        _frame_qt_s = _frame_dict_s.get('validation_query_type')
                        if _frame_qt_s:
                            query_type_for_synthesis = _frame_qt_s
                            logger.info(f"[SYNTHESIS] Using semantic_frame.validation_query_type={query_type_for_synthesis}")
                        else:
                            try:
                                # SemanticFrame was absent — use pattern-only detection.
                                # LLM confirmation is intentionally disabled here: an
                                # extra classify call at synthesis time adds ~300ms and
                                # is not reliable because the synthesis path only runs
                                # when the frame is already missing.
                                query_type_for_synthesis = detect_query_type(
                                    state['query'],
                                    llm=self.fast_llm if hasattr(self, 'fast_llm') else None,
                                    use_llm_confirmation=False,
                                    intent_domain_hint=_intent_domain,
                                )
                            except Exception:
                                query_type_for_synthesis = 'general'
                    
                    if query_type_for_synthesis and query_type_for_synthesis != 'general' and self.synthesis_engine:
                        logger.info(f"[SYNTHESIS] Building rule-based analysis for {query_type_for_synthesis}...")
                        
                        synthesis = self.synthesis_engine.synthesize(
                            chart_data=state['chart_data'],
                            chart_enhanced=enhanced_analysis,
                            query_type=query_type_for_synthesis,
                            validation_result=state.get('validation_result')
                        )
                        
                        state['synthesis'] = synthesis
                        
                        logger.info(f"[SYNTHESIS] [OK] Identified {len(synthesis.get('chart_strengths', []))} strengths")
                        logger.info(f"[SYNTHESIS] [OK] Identified {len(synthesis.get('chart_challenges', []))} challenges")
                        logger.info(f"[SYNTHESIS] [OK] Detected {len(synthesis.get('yogas_detected', []))} yogas")
                        logger.info(f"[SYNTHESIS] [OK] Analyzed {len(synthesis.get('key_houses', []))} key houses")
                    else:
                        logger.info(f"[SYNTHESIS] Skipped - query_type is '{query_type_for_synthesis}'")
                        
                except Exception as e:
                    logger.info(f"[SYNTHESIS] Error: {e}")
                    import traceback
                    traceback.print_exc()

            # ================================================================
            # STEP 1.5: Pre-build FactorPlan for agent-guided retrieval
            # ================================================================
            # FactorPlan was previously built inside _build_prediction_prompt (Step 3),
            # so retrieval had no knowledge of ranked factors. Building it here lets
            # the agent use factor scores to craft targeted retrieval queries.
            _fp_prebuilt = None
            if FACTOR_SCORER_AVAILABLE:
                try:
                    _ia_for_fp = (state.get('session_data') or {}).get('intent_analysis', {}) or {}
                    _fp_prebuilt = score_factors(
                        synthesis=state.get('synthesis'),
                        validation_result=state.get('validation_result'),
                        dasha_data=state.get('dasha_data'),
                        domain=_ia_for_fp.get('domain') or 'general',
                        question_mode=_ia_for_fp.get('question_mode') or 'summary',
                    )
                    logger.debug("[AGENT_LOOP] FactorPlan pre-built: %d factors", len(getattr(_fp_prebuilt, 'top_factors', []) or []))
                except Exception as _fp_err:
                    logger.debug("[AGENT_LOOP] FactorPlan pre-build skipped: %s", _fp_err)

            # ================================================================
            # STEP 2: Agentic Retrieval Loop
            # ================================================================
            # The agent decides which tools to call (retrieve_knowledge up to 2×,
            # get_chart_snapshot, get_dasha_snapshot) using FactorPlan + SemanticFrame
            # as grounding context. Falls back gracefully to empty chunks on error.
            logger.info("[RAG_WITH_CALCULATION] Step 2: Agentic retrieval...")

            knowledge_chunks = state.get('knowledge_chunks') or []

            if not knowledge_chunks and self.hybrid_retriever:
                from src.orchestration.agent_loop import run_agent_loop
                _frame_for_agent = (state.get('session_data') or {}).get('semantic_frame') or {}
                _agent_result = run_agent_loop(
                    query=state['query'],
                    frame=_frame_for_agent,
                    factor_plan=_fp_prebuilt,
                    state=state,
                    retriever=self.hybrid_retriever,
                    llm=getattr(self, 'fast_llm', self.llm),
                    max_retrievals=2,
                    max_iters=3,
                    log=logger,
                )
                knowledge_chunks = _agent_result.retrieval_chunks
                if _agent_result.chart_context:
                    state['_agent_chart_context'] = _agent_result.chart_context
                if _agent_result.dasha_context:
                    state['_agent_dasha_context'] = _agent_result.dasha_context
            elif not knowledge_chunks:
                logger.info("[RAG_WITH_CALCULATION] No retriever - proceeding with zero knowledge")

            state['knowledge_chunks'] = knowledge_chunks
            state['_fp_prebuilt'] = _fp_prebuilt  # passed to prompt builder to avoid re-computation
            logger.info("[RAG_WITH_CALCULATION] Retrieved %d chunks", len(knowledge_chunks))
            
            # ================================================================
            # STEP 3: Build Prompt (with validation constraints)
            # ================================================================
            # Pre-read the phase so we can pass it into the prompt builder
            # (suppresses "Next Favorable Window" for the INITIAL short response)
            from src.ai.context_manager import (
                PHASE_INITIAL as _PI, PHASE_AWAITING_DETAIL as _PAD, PHASE_FOLLOWUP_LOOP as _PFL,
            )
            _pre_phase_data = get_phase_data(state)
            _pre_phase = _pre_phase_data.get('phase', _PI)
            _pre_orig_q = (state.get('session_data') or {}).get('original_user_question') or state['query']
            _pre_intent_info = (state.get('session_data') or {}).get('intent_analysis', {})
            _pre_resp = resolve_response_type(
                _pre_orig_q, _pre_phase,
                intent_info=_pre_intent_info,
                fast_llm=getattr(self, 'fast_llm', None),
                log=logger,
            )
            _pre_current_topic = (_pre_phase_data.get('topic') or '').lower()

            def _extract_followup_target_from_last_bot(last_bot_msg: str) -> Tuple[str, Optional[str]]:
                """Extract final offered follow-up question and its domain from last assistant message."""
                import re as _re
                _q = ""
                if last_bot_msg:
                    _sentences = _re.split(r'(?<=[.!?।])\s+', last_bot_msg.strip())
                    _q_sentences = [s.strip() for s in _sentences if '?' in s]
                    if _q_sentences:
                        _q = _q_sentences[-1]
                if not _q:
                    return "", None
                _q_lower = _q.lower()
                _domain_keywords = {
                    'marriage': ['shadi', 'shaadi', 'vivah', 'marriage', 'partner', 'spouse', 'love', 'rishta', 'byah', 'relationship'],
                    'career': ['career', 'job', 'naukri', 'kaam', 'vyavsay', 'profession', 'business', 'rojgar'],
                    'finance': ['finance', 'money', 'paisa', 'dhan', 'wealth', 'invest', 'gold', 'property', 'arthik'],
                    'health': ['health', 'swasthya', 'sehat', 'bimari', 'disease', 'illness'],
                    'children': ['child', 'bacche', 'santaan', 'son', 'daughter', 'beta', 'beti', 'aulad'],
                    'foreign': ['foreign', 'videsh', 'abroad', 'travel', 'settlement', 'overseas'],
                }
                for _d, _kws in _domain_keywords.items():
                    if any(_kw in _q_lower for _kw in _kws):
                        return _q, _d
                # Generic detail-offer prompts should not be treated as cross-topic pivots.
                _generic_detail_markers = [
                    "would you like me to explain the detailed astrological reasoning",
                    "would you like me to explain in detail",
                    "would you like more detail",
                    "would you like to know more",
                    "kya aap iske peeche ki vistarit jyotishiya wajah jaanna chahenge",
                    "kya aap iske baare mein aur detail",
                    "aur detail mein jaanna",
                    "vistarit jyotishiya wajah",
                ]
                if any(_m in _q_lower for _m in _generic_detail_markers):
                    return "", None
                return _q, None

            # BUG FIX #2: Short CONTINUATION in AWAITING_DETAIL or FOLLOWUP_LOOP
            # Both phases accept short CONTINUATION queries as AFFIRMATIVE.
            # Previously only FOLLOWUP_LOOP was covered — AWAITING_DETAIL was missing.
            if (
                _pre_phase in (_PAD, _PFL)
                and _pre_resp == 'OTHER'
                and len(_pre_orig_q.strip().split()) <= 6
                and _pre_intent_info.get('intent_type') in ('CONTINUATION', 'CLARIFICATION')
            ):
                _pre_resp = 'AFFIRMATIVE'

            # BUG FIX #1: LLM fallback in STEP 3 to match STEP 3.5's fallback logic.
            # Without this, STEP 3 could set response_mode='initial' for an ambiguous
            # message that STEP 3.5 later classifies as AFFIRMATIVE via the LLM, producing
            # conflicting instructions (response_mode suppresses timing window while
            # phase_instruction explicitly says to include it).
            if _pre_resp == 'OTHER' and _pre_phase in (_PAD, _PFL):
                _last_bot_s3 = next(
                    (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                     if m.get('role') == 'assistant'), ''
                )
                _pre_resp = _durt_llm(
                    _pre_orig_q, _last_bot_s3, getattr(self, 'fast_llm', None), _pre_phase
                )

            # Choose effective query for prompt domain-hint generation:
            # - In AWAITING_DETAIL, short pure affirmatives ("Haan", "batao", "ok")
            #   should use last_query so domain hints stay on the same topic.
            # - In FOLLOWUP_LOOP, an affirmative means "yes to the pivot question", so
            #   we must NOT force last_query (old topic), otherwise the model drifts
            #   back to the previous domain (e.g., marriage instead of career).
            # - Long direct questions use state['query'] so hints match what user asked.
            _last_q = _pre_phase_data.get('last_query', '')
            _is_short_affirmative = len(_pre_orig_q.strip().split()) <= 5
            _last_bot_s3 = next(
                (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                 if m.get('role') == 'assistant'), ''
            )
            _pivot_q_pre, _pivot_topic_pre = _extract_followup_target_from_last_bot(_last_bot_s3)
            _is_affirmative_pivot_pre = (
                _pre_resp == 'AFFIRMATIVE'
                and _pre_phase in (_PAD, _PFL)
                and bool(_pivot_topic_pre)
                and (_pre_phase == _PFL or _pivot_topic_pre != _pre_current_topic)
            )
            _is_continuation_affirmative = (
                _pre_phase == _PAD
                and _pre_resp == 'AFFIRMATIVE'
                and _last_q
                and _is_short_affirmative  # Only redirect for short pure affirmatives
                and not _is_affirmative_pivot_pre
            )
            if _is_affirmative_pivot_pre and _pivot_q_pre:
                _effective_query = _pivot_q_pre
            else:
                _effective_query = _last_q if _is_continuation_affirmative else state['query']

            # Determine prompt response mode — must agree with STEP 3.5's phase_instruction
            # so that timing-window suppression and word-limits are consistent.
            if _is_affirmative_pivot_pre:
                _prompt_response_mode = 'followup'
            elif _pre_phase == _PAD and _pre_resp == 'AFFIRMATIVE':
                _prompt_response_mode = 'detailed'
            elif _pre_phase == _PFL and _pre_resp == 'AFFIRMATIVE':
                _prompt_response_mode = 'followup'
            elif _pre_phase in (_PI, '') or _pre_phase is None:
                _prompt_response_mode = 'initial'
            else:
                _prompt_response_mode = 'initial'  # Default to short for any new/ambiguous question

            # Future timeline horizon metadata for anti-repetition guard:
            # if multiple future years exist in computed dasha windows, don't let
            # final answer collapse to only current-year timing.
            _available_future_years = self._collect_future_timing_years(state.get('dasha_data', {}))
            _current_year = datetime.utcnow().year
            _has_cross_year_future_options = any(y > _current_year for y in _available_future_years)

            if state.get('chart_data'):
                domain_hint = (((state.get("validation_result") or {}).get("intent_analysis") or {}).get("domain"))
                state["astro_evidence"] = build_astro_evidence(
                    query=_effective_query,
                    chart_data=state.get("chart_data") or {},
                    dasha_data=state.get("dasha_data") or {},
                    transit_data=state.get("transit_data") or {},
                    domain_hint=domain_hint,
                )
                prompt = self._build_prediction_prompt(
                    query=_effective_query,
                    chart_data=state['chart_data'],
                    dasha_data=state.get('dasha_data', {}),
                    transit_data=state.get('transit_data', {}),
                    knowledge_chunks=knowledge_chunks,
                    user_profile=user_profile,
                    conversation_history=state.get('conversation_history', []),
                    language=state.get('detected_language', 'en'),
                    validation_result=state.get('validation_result'),
                    enhanced_analysis=state.get('enhanced_analysis'),
                    synthesis=state.get('synthesis'),
                    response_mode=_prompt_response_mode,
                    astro_evidence=state.get("astro_evidence"),
                    voice_preferences=state.get("voice_preferences"),
                    validation_disclaimer=state.get("validation_disclaimer"),
                    prebuilt_factor_plan=state.get('_fp_prebuilt'),
                )
            else:
                # Chart calculation failed — do NOT hallucinate chart-specific details.
                # Fall back to RAG_ONLY mode and tell the LLM explicitly that birth chart
                # data is unavailable so it provides general guidance only.
                logger.info("[RAG_WITH_CALCULATION] [WARN] No chart data — falling back to RAG_ONLY prompt")
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
                    logger.info("[RAG_WITH_CALCULATION] [ERROR] No prompt_builder - using fallback template")
                    prompt = (
                        f"You are a Vedic astrology assistant.{no_chart_notice}\n\n"
                        f"====USER_QUERY_MARKER====\n\"{state['query']}\""
                    )
            
            # ================================================================
            # STEP 3.5: PROGRESSIVE DISCLOSURE — Phase-Aware Prompt Injection
            # ================================================================
            from src.ai.context_manager import (
                PHASE_INITIAL, PHASE_AWAITING_DETAIL,
                PHASE_FOLLOWUP_LOOP, FOLLOWUP_QUESTION_BANK,
                generate_followup_question
            )
            conv_phase_data = get_phase_data(state)
            _intent_info = (state.get('session_data') or {}).get('intent_analysis', {})
            current_phase = conv_phase_data.get('phase', PHASE_INITIAL)
            # When user intent is NEW_TOPIC, always treat as INITIAL so we give short response + offer detail
            if _intent_info.get('intent_type') == 'NEW_TOPIC':
                current_phase = PHASE_INITIAL
                logger.info(f"[PHASE] intent_type=NEW_TOPIC → forcing phase to INITIAL (short response + offer detail)")
            current_topic = conv_phase_data.get('topic')
            followup_count = conv_phase_data.get('followup_count', 0)
            _orig_q = (state.get('session_data') or {}).get('original_user_question') or state['query']
            _last_bot_for_resp = next(
                (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                 if m.get('role') == 'assistant'), ''
            )
            user_response_type = resolve_response_type(
                _orig_q, current_phase,
                intent_info=_intent_info,
                last_bot_msg=_last_bot_for_resp,
                fast_llm=getattr(self, 'fast_llm', None),
                log=logger,
            )
            logger.info(f"[PHASE] user_response_type={user_response_type} (from original: '{_orig_q[:40]}')")

            # Robust pivot guard:
            # If the last assistant turn ended with a cross-domain follow-up question and
            # user now gives an affirmative, force handling as "yes to pivot question" even
            # when stored phase is stale/misaligned.
            _pivot_question, _pivot_topic = _extract_followup_target_from_last_bot(_last_bot_for_resp)
            _current_topic_norm = (current_topic or '').lower()
            _is_affirmative_to_pivot = (
                user_response_type == 'AFFIRMATIVE'
                and current_phase in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP)
                and bool(_pivot_topic)
                and (current_phase == PHASE_FOLLOWUP_LOOP or _pivot_topic != _current_topic_norm)
            )
            if _is_affirmative_to_pivot:
                logger.info(
                    f"[PHASE] Affirmative mapped to prior follow-up offer "
                    f"(phase={current_phase}, current_topic={_current_topic_norm}, pivot_topic={_pivot_topic})"
                )
                current_phase = PHASE_FOLLOWUP_LOOP

            # If user asks a fresh question while waiting for "want details?" response,
            # treat it as a new short-response cycle for this turn to avoid mode/phase desync.
            if current_phase == PHASE_AWAITING_DETAIL and user_response_type == 'OTHER':
                current_phase = PHASE_INITIAL
                _prompt_response_mode = 'initial'
                logger.info("[PHASE] AWAITING_DETAIL + OTHER -> treating as fresh INITIAL turn")

            # Detect the query domain for follow-up question selection
            # For AWAITING_DETAIL/FOLLOWUP_LOOP affirmatives, validation ran on "Haan karo"
            # (detected as 'general') — preserve the stored topic from the conversation phase.
            _val_qt = state.get('validation_query_type')
            if _is_affirmative_to_pivot and _pivot_topic:
                _topic = _pivot_topic
            elif _is_continuation_affirmative and current_topic and (_val_qt in (None, 'general')):
                _topic = current_topic
            else:
                _topic = _val_qt or current_topic or 'general'
            logger.info(f"[PHASE] topic={_topic} (val_qt={_val_qt}, current_topic={current_topic})")

            # Choose follow-up question — prefer LLM-generated (contextual) over static bank.
            # generate_followup_question() has a 4-second hard timeout internally so it
            # NEVER blocks the pipeline — falls back to the static bank on timeout/error.
            _followup_bank = FOLLOWUP_QUESTION_BANK.get(_topic, FOLLOWUP_QUESTION_BANK['general'])
            _followup_idx = followup_count % len(_followup_bank) if _followup_bank else 0
            _static_followup = _followup_bank[_followup_idx] if _followup_bank else ""
            _last_bot_msg_for_fq = next(
                (m.get('content', '') for m in reversed(state.get('conversation_history') or [])
                 if m.get('role') == 'assistant'), ''
            )
            # Infer conversation language from the last bot message rather than from the
            # current user message. Short affirmatives like "Haan" are detected as English
            # by langdetect, which would make the LLM generate English follow-up questions
            # in an otherwise Hindi conversation.
            _detected_lang = state.get('detected_language', 'en')
            _fq_language = _detected_lang
            if _detected_lang in ('en', '') and _last_bot_msg_for_fq:
                _bot_lower = _last_bot_msg_for_fq.lower()
                _hinglish_markers = ['hai', ' hain', ' ke ', ' ka ', ' ki ', ' aur ', ' mein ', ' se ', ' jo ', 'aap', 'kya']
                if any(m in _bot_lower for m in _hinglish_markers):
                    _fq_language = 'hi-lat'
                elif any('\u0900' <= c <= '\u097F' for c in _last_bot_msg_for_fq):
                    _fq_language = 'hi'
            # Build a compact chart context string with specific planet placements so the
            # LLM generates personalized questions ("Jupiter in your 3rd house...") instead
            # of generic/conditional ones ("agar koi planet hai toh...").
            _chart_ctx = None
            _cd = state.get('chart_data') or {}
            if _cd:
                try:
                    _hl = (state.get('enhanced_analysis') or {}).get('house_lords', {})
                    _planets = _cd.get('planets', {})
                    _lagna = _cd.get('lagna', {})
                    _ctx_lines = []
                    if _lagna:
                        _ctx_lines.append(f"Lagna: {_lagna.get('sign','?')} ({_lagna.get('nakshatra','?')})")
                    # Topic-relevant lords
                    _topic_lords = {
                        'marriage': ['H7', 'H2', 'H5'],
                        'career':   ['H10', 'H6', 'H11'],
                        'finance':  ['H2', 'H11', 'H5'],
                        'health':   ['H6', 'H8', 'H1'],
                        'children': ['H5', 'H9'],
                        'foreign':  ['H12', 'H9', 'H3'],
                    }.get(_topic, ['H1', 'H9', 'H10'])
                    for _hk in _topic_lords:
                        _lord = _hl.get(_hk, {})
                        _lord_name = _lord.get('lord') or _lord.get('planet')
                        if _lord_name and _lord_name in _planets:
                            _p = _planets[_lord_name]
                            _ctx_lines.append(
                                f"{_hk} lord {_lord_name}: {_p.get('sign','?')} in house {_p.get('house','?')}"
                                + (' (R)' if _p.get('is_retrograde') else '')
                                + (' [combust]' if _p.get('is_combust') else '')
                            )
                    # Venus and Jupiter always relevant for marriage/general
                    for _pn in ('VENUS', 'JUPITER', 'SATURN'):
                        if _pn in _planets and _pn not in [l.get('lord','') for l in _hl.values()]:
                            _p = _planets[_pn]
                            _ctx_lines.append(f"{_pn}: {_p.get('sign','?')} in house {_p.get('house','?')}")
                    if _ctx_lines:
                        _chart_ctx = '\n'.join(_ctx_lines)
                except Exception:
                    pass
            # Build a compact findings summary from synthesis so the follow-up can pivot
            # to the strongest unused chart signal rather than guessing a generic area.
            _findings_summary = None
            _syn_for_fq = state.get('synthesis') or {}
            if _syn_for_fq:
                try:
                    _ff_lines = []
                    for _s in (_syn_for_fq.get('chart_strengths') or [])[:2]:
                        _ff_lines.append(f"• [STRENGTH] {_s}")
                    for _c in (_syn_for_fq.get('chart_challenges') or [])[:1]:
                        _ff_lines.append(f"• [CHALLENGE] {_c}")
                    for _y in (_syn_for_fq.get('yogas_detected') or [])[:1]:
                        _y_text = _y.get('name', '') if isinstance(_y, dict) else str(_y)
                        if _y_text:
                            _ff_lines.append(f"• [YOGA] {_y_text}")
                    if _ff_lines:
                        _findings_summary = '\n'.join(_ff_lines)
                except Exception:
                    pass

            # Only generate a cross-domain follow-up question for phases that actually use it.
            # INITIAL phase no longer shows a follow-up question, so skip the LLM call.
            _needs_followup_question = current_phase != PHASE_INITIAL
            if _needs_followup_question:
                logger.info(f"[PHASE] Generating follow-up question (topic={_topic}, lang={_fq_language}, timeout=4s)...")
                _suggested_followup = generate_followup_question(
                    topic=_topic,
                    last_answer=_last_bot_msg_for_fq,
                    language=_fq_language,
                    fast_llm=getattr(self, 'fast_llm', None),
                    fallback=_static_followup,
                    chart_context=_chart_ctx,
                    findings_summary=_findings_summary,
                    timeout=4.0
                )
                logger.info(f"[PHASE] Follow-up question ready: {_suggested_followup[:80]}")
            else:
                _suggested_followup = _static_followup
                logger.info(f"[PHASE] Skipping follow-up question generation (INITIAL phase)")

            phase_instruction = ""
            new_phase_data = {}  # Will be set on state for chat_stateless to persist

            # ── Query context modifier — LLM reads query + history to detect intent shifts ──
            _query_context_note = self._analyze_query_context(
                query=state.get('query') or '',
                conversation_history=state.get('conversation_history') or [],
            )

            if current_phase == PHASE_AWAITING_DETAIL and user_response_type == 'NEGATIVE':
                # ── User declined details → Ask an alternative follow-up question ──
                logger.info(f"[PHASE] AWAITING_DETAIL + NEGATIVE → generating alternative follow-up")
                # Pick a different follow-up than the one we would have asked
                _alt_idx = (_followup_idx + 1) % len(_followup_bank) if _followup_bank else 0
                alt_followup = _followup_bank[_alt_idx] if _followup_bank else "Would you like to explore another aspect of your chart?"

                state['answer'] = (
                    f"No problem! Here's something interesting from your chart though — {alt_followup}"
                )
                new_phase_data = make_phase_data_dict(
                    PHASE_FOLLOWUP_LOOP, _topic,
                    conv_phase_data.get('last_query', state['query']),
                    followup_count + 1,
                )
                state['conversation_phase'] = new_phase_data
                return state  # Skip LLM call — direct response

            elif current_phase == PHASE_AWAITING_DETAIL and user_response_type == 'AFFIRMATIVE':
                # ── User wants details → Generate comprehensive response + follow-up question ──
                logger.info(f"[PHASE] AWAITING_DETAIL + AFFIRMATIVE > detailed response with follow-up")
                _lang_for_phase = state.get('detected_language', 'en')
                _voice_charter = get_voice_charter(_lang_for_phase)
                _flow_policy = get_response_structure_policy()

                # Topic-specific slot hints so the scaffold is semantically grounded
                _TOPIC_SLOT_HINTS = {
                    'marriage':   dict(house='7th house (Marriage and Partnership)',    planet='Venus',   secondary='Jupiter',  divisional='Navamsa',          div_focus='spouse nature and marriage quality'),
                    'career':     dict(house='10th house (Career and Profession)',      planet='Saturn',  secondary='Sun',       divisional='Dasamsa',          div_focus='career trajectory and professional status'),
                    'finance':    dict(house='2nd house (Wealth) and 11th house (Gains)', planet='Jupiter', secondary='Mercury', divisional='Hora',             div_focus='wealth accumulation and financial gains'),
                    'health':     dict(house='1st house (Self) and 6th house (Disease)', planet='Sun',    secondary='Mars',      divisional='Shashtamsa',       div_focus='health vulnerabilities and recovery patterns'),
                    'children':   dict(house='5th house (Children and Progeny)',        planet='Jupiter', secondary='Moon',      divisional='Saptamsa',         div_focus='children and progeny prospects'),
                    'education':  dict(house='4th house (Learning) and 5th house (Intellect)', planet='Mercury', secondary='Jupiter', divisional='Chaturvimsamsa', div_focus='academic success and knowledge'),
                    'property':   dict(house='4th house (Property and Home)',           planet='Mars',    secondary='Moon',      divisional='Chaturthamsa',     div_focus='real estate and fixed assets'),
                    'foreign':    dict(house='12th house (Foreign Lands) and 9th house (Long Journeys)', planet='Rahu', secondary='Moon', divisional='Dwadasamsa', div_focus='foreign travel and settlement abroad'),
                    'foreign_travel': dict(house='12th house (Foreign Lands) and 9th house (Long Journeys)', planet='Rahu', secondary='Moon', divisional='Dwadasamsa', div_focus='foreign travel and settlement abroad'),
                    'spirituality': dict(house='9th house (Dharma) and 12th house (Moksha)', planet='Jupiter', secondary='Ketu', divisional='Vimsamsa',       div_focus='spiritual inclination and religious practices'),
                }
                _sh = _TOPIC_SLOT_HINTS.get(_topic or 'general', _TOPIC_SLOT_HINTS.get('marriage', dict(
                    house='relevant house for this topic', planet='the key significator planet',
                    secondary='supporting planet', divisional='the relevant divisional chart',
                    div_focus='this topic\'s prospects'
                )))

                phase_instruction = f"""
PROGRESSIVE DISCLOSURE -- DETAILED RESPONSE MODE:
Write a flowing prose response — no JSON, no numbered lists, no markdown headers.
LANGUAGE: Write entirely in {_lang_for_phase}.

Study the STYLE EXAMPLES above. For a detailed response, expand the 5-part structure:
1. Brief acknowledgment of the short answer — "chaliye aur gehrai mein dekhte hain" or similar (1 sentence)
2. House lord + dignity — {_sh['house']} lord, its sign/condition, what it means practically (2 sentences)
3. Planet placement — {_sh['planet']}: sign, house, practical effect on {_topic or 'this topic'} (2 sentences)
4. Dasha combination — current Mahadasha + Antardasha, why this supports or challenges {_topic or 'this topic'} (2 sentences)
5. Timing window — upcoming Pratyantar with explicit month-year range and practical expectation (2 sentences)
6. Supporting factors — yoga OR transit (Jupiter/Saturn gochara) relevant to {_topic or 'this topic'} (2 sentences)
7. {_sh['divisional']} chart — what it shows about {_sh['div_focus']} (1-2 sentences)
8. A natural, woven-in nuance — acknowledge a real challenge (debilitation, weak planet, timing uncertainty) but frame it as something to navigate through, not a label or warning. (1 sentence)
9. Close with: {_suggested_followup}

{(_query_context_note + chr(10)) if _query_context_note else ""}Rules:
- Show reason chain: astrological factor → interpretation → practical outcome.
- Use explicit month-year ranges from the dasha data — never duration-only like "6 months".
- Do NOT repeat the initial short answer word-for-word — add genuine depth.
- Timing must stay consistent with the window given in the initial answer.
- Target length: 300-400 words.
{ _voice_charter }
{ self._build_coherence_hint(state.get("conversation_history", []), (_topic or "general").lower(), current_query=state.get('query', '')) }
"""
                new_phase_data = make_phase_data_dict(
                    PHASE_FOLLOWUP_LOOP, _topic,
                    conv_phase_data.get('last_query', state['query']),
                    followup_count + 1,
                )
                # So we can append the related follow-up if the LLM omits it
                state['_detailed_followup'] = _suggested_followup

            elif current_phase == PHASE_FOLLOWUP_LOOP and user_response_type == 'AFFIRMATIVE':
                # ── User agreed to a follow-up question → Answer it, then STOP asking ──
                logger.info(f"[PHASE] FOLLOWUP_LOOP + AFFIRMATIVE → new topic cycle (short answer + offer detail)")
                # User said YES to the cross-domain follow-up question.
                # Treat this as a new INITIAL topic: give a short answer about the new topic
                # and end with an offer to explain in detail (same pattern as INITIAL phase).
                # Extract the exact follow-up question the bot asked so we can answer it.
                _last_question = _pivot_question
                _new_topic = _pivot_topic or 'general'
                if not _last_question:
                    _hist = state.get('conversation_history') or []
                    _last_bot_msg = next(
                        (m.get('content', '') for m in reversed(_hist) if m.get('role') == 'assistant'),
                        ''
                    )
                    _last_question, _fallback_topic = _extract_followup_target_from_last_bot(_last_bot_msg)
                    if _fallback_topic:
                        _new_topic = _fallback_topic
                if not _new_topic or _new_topic == 'general' or not _last_question:
                    # Guard against generic "yes to detail" being misread as cross-domain pivot.
                    _new_topic = (_topic or current_topic or 'general')
                    _last_question = conv_phase_data.get('last_query', state.get('query', ''))
                    logger.info(
                        f"[PHASE] FOLLOWUP affirm received without a valid pivot target; "
                        f"staying on topic={_new_topic}."
                    )
                logger.info(f"[PHASE] New topic question: {_last_question[:80]}")

                # Detect the new domain from the follow-up question text
                if _new_topic == 'general' and _last_question:
                    _fq_lower = _last_question.lower()
                    _domain_keywords = {
                        'marriage':  ['shadi', 'vivah', 'marriage', 'partner', 'spouse', 'love', 'rishta', 'byah', 'relationship'],
                        'career':    ['career', 'job', 'naukri', 'kaam', 'vyavsay', 'profession', 'business', 'rojgar'],
                        'finance':   ['finance', 'money', 'paisa', 'dhan', 'wealth', 'invest', 'gold', 'property', 'arthik'],
                        'health':    ['health', 'swasthya', 'sehat', 'bimari', 'disease', 'illness'],
                        'children':  ['child', 'bacche', 'santaan', 'son', 'daughter', 'beta', 'beti', 'aulad'],
                        'foreign':   ['foreign', 'videsh', 'abroad', 'travel', 'settlement', 'overseas'],
                    }
                    for _d, _kws in _domain_keywords.items():
                        if any(_kw in _fq_lower for _kw in _kws):
                            _new_topic = _d
                            break

                _lang_now = state.get('detected_language', 'en')
                _closing_q = pick_initial_closing(
                    rng=random.Random(_last_question or state.get('query', '')),
                    language=_lang_now,
                    domain=_new_topic,
                )
                _voice_charter = get_voice_charter(_lang_now)
                _flow_policy = get_response_structure_policy()
                _answer_topic = f'"{_last_question}"' if _last_question else "the follow-up topic in your previous message"
                phase_instruction = f"""
PROGRESSIVE DISCLOSURE -- NEW TOPIC SHORT RESPONSE (OVERRIDES ALL OTHER FORMAT INSTRUCTIONS):
The user said YES to your follow-up question. This starts a fresh topic cycle. Give a short initial answer about the new topic.

ANSWER THIS SPECIFIC QUESTION: {_answer_topic}

1. LENGTH: You MUST write at least 150 words. Target range is 150-200 words. Do not stop before 150 words — a response shorter than 150 words will be rejected.
2. Include 2-3 critical astrological factors explicitly (for example: house-lord logic, dasha/pratyantar trigger, transit support, yoga, planetary condition). Keep it readable by briefly explaining each factor in practical language.
3. Give a smart 3-layer timeline for the new topic:
   - present context (current trend),
   - near-term activation period with explicit month-year range,
   - broader supportive phase with explicit month-year range (may cross years).
   Ground these in dasha/pratyantar/transit data and briefly explain WHY each window matters.
4. Make the favorable future window explicit and practical (where to act, what to prioritise in that period).
5. Do NOT repeat anything already covered in earlier responses.
6. Write the ENTIRE response in {_lang_now}.
7. End with EXACTLY this closing line — do not rephrase it:
   "{_closing_q}"
8. {_voice_charter}
9. {_flow_policy}
"""
                # Start a fresh AWAITING_DETAIL cycle for the new topic.
                new_phase_data = make_phase_data_dict(
                    PHASE_AWAITING_DETAIL, _new_topic,
                    _last_question or conv_phase_data.get('last_query', state['query']),
                    0,
                )


            elif current_phase == PHASE_FOLLOWUP_LOOP and user_response_type == 'NEGATIVE':
                # ── User declined follow-up → Offer alternative ──
                logger.info(f"[PHASE] FOLLOWUP_LOOP + NEGATIVE → alternative follow-up")
                _alt_idx = (followup_count + 2) % len(_followup_bank) if _followup_bank else 0
                alt_followup = _followup_bank[_alt_idx] if _followup_bank else "Your chart has more to reveal — what else are you curious about?"
                state['answer'] = f"Sure! Here's something else interesting from your chart — {alt_followup}"
                new_phase_data = make_phase_data_dict(
                    PHASE_FOLLOWUP_LOOP, _topic,
                    conv_phase_data.get('last_query', state['query']),
                    followup_count + 1,
                )
                state['conversation_phase'] = new_phase_data
                return state  # Skip LLM call — direct response

            else:
                # ── INITIAL / NEW TOPIC → Short response with richer astrology anchors ──
                logger.info(f"[PHASE] INITIAL -> short response with 2-3 critical factors and realistic timing")
                _lang_now = state.get('detected_language', 'en')
                _topic_norm = (_topic or "general").lower()
                _initial_horizon_combo_families_by_topic = {
                    # Near = pratyantar windows, Mid = antardasha-level windows, Broad = macro support/transit layer
                    "career": [
                        [("near", "mid"), ("mid", "broad"), ("near", "broad")],
                        [("mid", "broad"), ("broad", "near"), ("mid", "near")],
                        [("near", "broad"), ("broad", "mid"), ("near", "mid")],
                    ],
                    "finance": [
                        [("near", "mid"), ("mid", "broad"), ("near", "broad")],
                        [("mid", "broad"), ("broad", "near"), ("mid", "near")],
                        [("near", "broad"), ("broad", "mid"), ("near", "mid")],
                    ],
                    "health": [
                        [("near", "mid"), ("near", "broad"), ("mid", "broad")],
                        [("mid", "near"), ("broad", "near"), ("mid", "broad")],
                        [("near", "broad"), ("broad", "mid"), ("near", "mid")],
                    ],
                    "marriage": [
                        [("mid", "broad"), ("near", "mid"), ("near", "broad")],
                        [("broad", "mid"), ("mid", "near"), ("broad", "near")],
                        [("near", "broad"), ("mid", "broad"), ("near", "mid")],
                    ],
                    "children": [
                        [("mid", "broad"), ("near", "mid"), ("near", "broad")],
                        [("broad", "mid"), ("mid", "near"), ("broad", "near")],
                        [("near", "broad"), ("mid", "broad"), ("near", "mid")],
                    ],
                    "foreign": [
                        [("mid", "broad"), ("near", "broad"), ("near", "mid")],
                        [("broad", "mid"), ("broad", "near"), ("mid", "near")],
                        [("near", "broad"), ("mid", "broad"), ("near", "mid")],
                    ],
                    "general": [
                        [("near", "mid"), ("near", "broad"), ("mid", "broad")],
                        [("mid", "broad"), ("broad", "near"), ("mid", "near")],
                        [("near", "broad"), ("broad", "mid"), ("near", "mid")],
                    ],
                }
                _orig_for_seed = (state.get('session_data') or {}).get('original_user_question') or state.get('query', '')
                _conv_turn_count = len(state.get('conversation_history') or [])
                _combo_rng = random.Random(f"{state.get('user_id','')}|{_topic_norm}|{_orig_for_seed}|{_conv_turn_count}")
                _combo_families = _initial_horizon_combo_families_by_topic.get(
                    _topic_norm,
                    _initial_horizon_combo_families_by_topic["general"]
                )
                _primary_family_idx = _combo_rng.randrange(len(_combo_families))
                _primary_combo_pool = _combo_families[_primary_family_idx]
                if len(_combo_families) > 1:
                    _alternate_family_idx = (_primary_family_idx + 1 + _combo_rng.randrange(len(_combo_families) - 1)) % len(_combo_families)
                else:
                    _alternate_family_idx = _primary_family_idx
                _alternate_combo_pool = _combo_families[_alternate_family_idx]
                _primary_horizon, _secondary_horizon = _primary_combo_pool[_combo_rng.randrange(len(_primary_combo_pool))]
                _alt_primary_horizon, _alt_secondary_horizon = _alternate_combo_pool[_combo_rng.randrange(len(_alternate_combo_pool))]
                _horizon_hint = (
                    f"For the timing window in this answer, prefer a { _primary_horizon.upper() } horizon. "
                    "Horizon guide: NEAR=pratyantar-like short activation (2-4 months), "
                    "MID=antardasha-level medium runway (3-8 months), "
                    "BROAD=larger supportive phase from antardasha/transit convergence (6-18 months). "
                    "Pick ONE clear window from the dasha data that fits this horizon — do not list multiple windows."
                )
                _recent_window_hint = self._collect_recent_cross_topic_window_keys(
                    state.get("conversation_history", []),
                    _topic_norm,
                )
                _recent_samples = (_recent_window_hint.get("samples") or [])[:2]
                _window_reuse_hint = (
                    f"Avoid reusing these recently-used month windows if alternatives exist: {_recent_samples}."
                    if _recent_samples else
                    "Prefer a distinct timing expression from the most recently used one when alternatives exist."
                )
                _recent_planets = self._collect_recent_planet_factors(
                    state.get("conversation_history", [])
                )
                _planet_variety_hint = (
                    f"Recently emphasized planets: {', '.join(_recent_planets)}. "
                    "For variety, lead with a different planetary factor or yoga if the chart supports it."
                    if _recent_planets else ""
                )
                _coherence_hint = self._build_coherence_hint(
                    state.get("conversation_history", []),
                    _topic_norm,
                    current_query=state.get('query', ''),
                )
                _closing_q = pick_initial_closing(
                    rng=random.Random(state.get('query', '')),
                    language=_lang_now,
                    domain=_topic,
                )
                _voice_charter = get_voice_charter(_lang_now)
                _flow_policy = get_response_structure_policy()

                # Compute the earliest allowed pratyantar start month for INITIAL responses.
                # Matches the 2-month deferral in _build_prediction_prompt so the LLM can't
                # cite an earlier month derived from Vimshottari sequence math.
                _min_timing_month_hint = ""
                try:
                    _today_iso = datetime.utcnow().date().isoformat()
                    _min_lead = 2  # months — must match _min_lead_months_initial in _build_prediction_prompt
                    _all_pds = (state.get('dasha_data') or {}).get('upcoming_pratyantardashas', []) or []
                    _eligible_starts = []
                    for _pd in _all_pds:
                        _s = _pd.get('start', '9999')
                        if _s <= _today_iso:
                            continue
                        try:
                            _s_dt = datetime.strptime(_s.strip(), "%Y-%m-%d").date()
                            _t_dt = datetime.strptime(_today_iso, "%Y-%m-%d").date()
                            _lead = max(0, (_s_dt.year - _t_dt.year) * 12 + (_s_dt.month - _t_dt.month))
                            if _lead >= _min_lead:
                                _eligible_starts.append(_s_dt)
                        except Exception:
                            continue
                    if _eligible_starts:
                        _earliest = min(_eligible_starts)
                        _min_timing_month_hint = (
                            f"TIMING FLOOR (MANDATORY): Do NOT cite any month before "
                            f"{_earliest.strftime('%B %Y')} as a timing window. "
                            f"Earlier months are deferred for follow-up responses. "
                            f"Use ONLY windows from Step 3.5/3.8 in the dasha data."
                        )
                except Exception:
                    pass

                phase_instruction = f"""
PROGRESSIVE DISCLOSURE -- INITIAL SHORT RESPONSE:
Write a single flowing prose response — no JSON, no numbered lists, no markdown headers or labels.
LANGUAGE: Write entirely in {_lang_now}.

Study the STYLE EXAMPLES above for tone and flow only — their chart facts are for DIFFERENT users and must NEVER be copied. Structure your response as:
1. Personal opener — address the user by name with ONE sentence that is specific and grounded. If the question implies impatience ("kab hogi?") acknowledge the wait warmly and tie it to a concrete chart signal ("Venus ka period shuru ho raha hai"). If hopeful, match that energy with something specific from the chart. If anxious or under pressure, reflect that context lightly. BANNED openers (these will be rejected): any variant of "samay favorable hai", "achhe samay ki nishaniyan hain", "great news", "bahut achha time aa raha hai", "chart mein positive indicators hain" — these are hollow and feel like a template. The opener must reference ONE specific thing from this user's chart or life context. Example of good openers: "Kartikeya, intezaar zyada nahi — Venus ka sub-period jaldi shuru ho raha hai aur ye period exactly rishton ke liye bana hai." or "Kartikeya, chart dekh ke keh sakta hoon ki ye wait meaningful hai — ek khaas window aa rahi hai."
2. Two to three astrological factors directly relevant to the user's question. BANNED: parenthetical labels after house numbers like "7th house (Marriage & Partnership)" or "2nd house (Wealth & Family)" — a real astrologer does not explain what the 7th house means to every client. Just say "7th house" or "7th lord". BANNED: vague claims like "Navamsa mein Venus ki position positive hai" — if you mention a divisional chart, say WHY it matters for this user specifically (e.g., what sign Venus is in, or what its dignity is there). BANNED: claiming a transit aspect (e.g., "Jupiter 7th house ko support karega") unless the TRANSITS section above explicitly shows Jupiter aspecting the 7th house. Relevant factors by domain: marriage → 7th lord, Venus dasha/antardasha, D9 (Navamsa) chart, Jupiter transit to 7th house (only if shown in transit data); foreign → 12th house lord, Rahu/Ketu axis, 9th house, relevant dasha; career → 10th lord, Saturn dasha/transit, D10. For each factor, say what it means for THIS person's specific situation. (2-3 sentences total)
3. ONE specific timing window — explicit month-year range derived from the dasha/transit data above, with a practical reason why that window is good. (1-2 sentences) STRICT: Give exactly ONE timing window. Do NOT list a second or backup window. Do NOT say "or" between two date ranges. Secondary windows belong in the DETAILED response only.
4. A natural, woven-in nuance — name a SPECIFIC planet or yoga and what it means practically; acknowledge a real challenge without labeling it or making it sound like a disclaimer. (1 sentence)
5. Close with ONE question that offers to go DEEPER into the astrological analysis. The question must be about chart depth — e.g., "Chahein toh main D9 chart aur exact dasha timings aur detail mein bataun?" or "Would you like me to walk through the D12/D10 chart factors and their exact dates?" NEVER ask the user about their preferences, goals, or what kind of opportunity they want — that is not astrology. The closing question is always an OFFER OF MORE CHART ANALYSIS.

{(_query_context_note + chr(10)) if _query_context_note else ""}Rules:
- Use explicit month-year ranges from Step 3.5/3.8 dasha data above. NEVER compute or infer pratyantar dates yourself — only use the exact windows listed.
- TIMING CONSISTENCY: If you mention a period in the opener (e.g. "Venus pratyantar [month] se"), use the SAME dates in the timing section. Do NOT introduce a different month-year range for the same period later in the response.
- Ground every claim in the chart/dasha/transit data above — no training-knowledge defaults.
- DIGNITY LANGUAGE: Use the exact term from the chart data. A planet is EITHER exalted OR in own sign — never both. "apne hi sign mein exalted" is contradictory and must never be written. If the chart says "exalted", write "exalted" (or "uccha"). If it says "own sign", write "apne hi sign mein". Never combine.
- Do NOT start with technical terms like "Mahadasha", "10th house lord". Start with a human outcome sentence.
- Explain any technical term immediately in plain language — but NEVER add parenthetical labels after house numbers like "7th house (Marriage & Partnership)" or planet names "Venus (love planet)". An astrologer speaks to a client who knows basics, not a student who needs a textbook glossary.
- Warm, direct, consultative tone — not mechanical or formulaic.
- Target length: 100-130 words. Be concise. Every sentence must earn its place.
- ABSOLUTELY NO EMOJIS. Not a single emoji character anywhere in the response.
- {_horizon_hint}
- {_window_reuse_hint}
{("- " + _min_timing_month_hint) if _min_timing_month_hint else ""}
{("- " + _planet_variety_hint) if _planet_variety_hint else ""}
{_coherence_hint}
{ _voice_charter }
"""
                # BUG FIX #4: Store the true original question (pre-semantic-expansion)
                # as last_query so that future AFFIRMATIVE turns have domain keywords.
                _orig_user_q = (state.get('session_data') or {}).get('original_user_question') or state['query']
                new_phase_data = make_phase_data_dict(
                    PHASE_AWAITING_DETAIL, _topic, _orig_user_q, 0,
                )
                state['_was_initial_response'] = True

            state['conversation_phase'] = new_phase_data

            # Inject phase instruction into the prompt (before the USER_QUERY_MARKER)
            if phase_instruction and "====USER_QUERY_MARKER====" in prompt:
                parts = prompt.split("====USER_QUERY_MARKER====")
                prompt = parts[0] + "\n" + phase_instruction + "\n====USER_QUERY_MARKER====" + parts[1]
            elif phase_instruction:
                prompt = prompt + "\n" + phase_instruction

            # ================================================================
            # PROMPT DEBUG LOGGING — confirms instructions reach the LLM
            # ================================================================
            system_part = prompt.split("====USER_QUERY_MARKER====")[0].strip()
            logger.debug(f"[PROMPT_DEBUG] phase={current_phase} | system_prompt_length={len(system_part)}")
            # Log key sections to verify they are present
            has_engine_guidelines = "ENGINE USAGE GUIDELINES" in system_part
            has_planetary_conditions = "PLANETARY CONDITIONS" in system_part
            has_yogas = "Yogas (from YOGAS DETECTED" in system_part
            has_dosha_reframe = "FEARED PLACEMENT REFRAMING" in system_part
            has_convergence = "convergence sentence" in system_part
            has_dispositor = "DISPOSITOR CHAIN" in system_part
            has_divisional = "DIVISIONAL CHART ANALYSIS" in system_part
            logger.info(
                f"[PROMPT_CHECKLIST] phase={current_phase} | "
                f"ENGINE_GUIDELINES={has_engine_guidelines} | "
                f"PLANETARY_CONDITIONS={has_planetary_conditions} | "
                f"YOGAS={has_yogas} | "
                f"DOSHA_REFRAME={has_dosha_reframe} | "
                f"CONVERGENCE={has_convergence} | "
                f"DISPOSITOR={has_dispositor} | "
                f"DIVISIONAL_CHARTS={has_divisional}"
            )
            if phase_instruction:
                logger.info(f"[PHASE_INSTRUCTION] length={len(phase_instruction)} | preview={phase_instruction[:200].replace(chr(10), ' ')!r}")

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

            # Add current query with chart context
            user_prompt = "USER_QUERY:" + prompt.split("====USER_QUERY_MARKER====")[1]
            messages.append({
                "role": "user",
                "content": user_prompt
            })

            # ================================================================
            # STEP 5: Generate LLM Response with Full Context
            # ================================================================
            logger.info(f"[LLM] Sending {len(messages)} messages to LLM (phase={current_phase})")

            _use_json_mode = False  # Prose mode: few-shot examples teach structure better than JSON fields
            _json_llm = self._get_json_llm() if _use_json_mode else None

            if _json_llm and _use_json_mode:
                try:
                    raw = _json_llm.invoke(messages)
                    raw_text = raw.content if hasattr(raw, 'content') else str(raw)
                    _parsed = json.loads(raw_text)
                    if _prompt_response_mode == 'initial':
                        state['answer'] = self._assemble_short_response(_parsed)
                    else:
                        state['answer'] = self._assemble_detailed_response(_parsed)
                    logger.info(f"[JSON_LLM] Structured response assembled ({len(state['answer'].split())} words)")
                except Exception as _je:
                    logger.warning(f"[JSON_LLM] Failed ({_je}), falling back to standard LLM call")
                    response = self.llm.invoke(messages)
                    state['answer'] = response.content if hasattr(response, 'content') else str(response)
            else:
                response = self.llm.invoke(messages)
                state['answer'] = response.content if hasattr(response, 'content') else str(response)

            # Strip triple-quote delimiters that smaller models echo from the prompt template.
            def _strip_llm_wrapper(text: str) -> str:
                t = (text or "").strip()
                if t.startswith('"""') and t.endswith('"""') and len(t) > 6:
                    t = t[3:-3].strip()
                elif t.startswith("'''") and t.endswith("'''") and len(t) > 6:
                    t = t[3:-3].strip()
                return t
            state['answer'] = _strip_llm_wrapper(state.get('answer', ''))

            # ── Factor Accuracy Gate ──────────────────────────────────────────
            # Cross-check every planet-house and planet-sign claim in the answer
            # against chart_data. Violations are logged and stored on state for
            # observability; the gate never rewrites the answer.
            if ACCURACY_GATE_AVAILABLE and state.get('chart_data'):
                try:
                    _acc_result = check_factor_accuracy(
                        answer=state.get('answer', ''),
                        chart_data=state.get('chart_data'),
                    )
                    state['accuracy_gate'] = _acc_result.to_dict()
                except Exception as _ag_err:
                    logger.debug("[ACCURACY_GATE] skipped: %s", _ag_err)

            # ── User Memory Write (fire-and-forget) ───────────────────────────
            # Extract any personal facts the user stated ("I work in finance",
            # "my wife is named Priya", "I'm 34 years old") and store them in
            # the memory collection so future turns can personalise follow-ups.
            # Runs in a daemon thread — zero latency impact on the response.
            if MEMORY_WRITER_AVAILABLE and state.get('user_id') and state.get('query'):
                try:
                    _mem_retriever = getattr(
                        getattr(self, 'hybrid_retriever', None), 'memory_retriever', None
                    )
                    if _mem_retriever:
                        _mem_frame = (state.get('session_data') or {}).get('semantic_frame') or {}
                        _mem_domain = _mem_frame.get('domain') or 'general'
                        maybe_store_user_facts_async(
                            user_message=state['query'],
                            user_id=state['user_id'],
                            memory_retriever=_mem_retriever,
                            fast_llm=getattr(self, 'fast_llm', None),
                            domain=_mem_domain,
                        )
                except Exception as _mw_err:
                    logger.debug("[MEMORY_WRITER] skipped: %s", _mw_err)

            # Runtime quality gate for initial short responses:
            # enforce practical timeline diversity (present + short + long).
            _detected_lang = state.get('detected_language', 'en')
            _current_qt = ((state.get('validation_result') or {}).get('query_type') or "general")
            _novelty_recent = self._collect_recent_cross_topic_window_keys(
                state.get("conversation_history", []),
                _current_qt,
            )
            _recent_cross_topic_keys = set(_novelty_recent.get("keys") or set())
            # Also track cross-topic start months (YYYY-MM) for partial-overlap detection.
            _recent_cross_topic_start_months_qa: set[str] = {
                k.split("|")[0] for k in _recent_cross_topic_keys if "|" in k
            }
            _candidate_keys = self._collect_future_candidate_window_keys(state.get("dasha_data", {}))
            _novelty_alternatives_exist = bool(_candidate_keys - _recent_cross_topic_keys)

            def _apply_cross_topic_novelty_issue(_answer_text: str, _quality: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
                if not _recent_cross_topic_keys or not _novelty_alternatives_exist:
                    return (len(_quality.get("issues", []) or []) == 0), _quality
                _today_ym = datetime.utcnow().strftime("%Y-%m")
                _answer_keys = self._filter_non_ended_range_keys(
                    self._extract_month_year_range_keys(_answer_text or ""),
                    today_ym=_today_ym,
                )
                _recent_keys_live = self._filter_non_ended_range_keys(set(_recent_cross_topic_keys), today_ym=_today_ym)
                # Exact key reuse
                _reused = sorted(_answer_keys.intersection(_recent_keys_live))
                # Same-start-month reuse (different end date but same opening month)
                _answer_start_months = {k.split("|")[0] for k in _answer_keys if "|" in k}
                _reused_start_months = sorted(
                    _answer_start_months.intersection(_recent_cross_topic_start_months_qa)
                )
                if _reused or _reused_start_months:
                    _issues = list(_quality.get("issues", []) or [])
                    _issue_id = "reused_cross_topic_timeline_window_despite_available_alternatives"
                    if _issue_id not in _issues:
                        _issues.append(_issue_id)
                    _quality["issues"] = _issues
                    _quality["reused_cross_topic_windows"] = (_reused or _reused_start_months)[:4]
                    logger.info(
                        "[TIMELINE_NOVELTY] Cross-topic timeline reuse detected in answer "
                        f"(query_type={_current_qt}, reused={(_reused or _reused_start_months)[:3]}, "
                        f"start_month_overlap={_reused_start_months[:3]}, "
                        f"alternatives={len(_candidate_keys - _recent_keys_live)})."
                    )
                return (len(_quality.get("issues", []) or []) == 0), _quality

            def _log_novelty_summary(_tag: str) -> None:
                if _prompt_response_mode not in ("initial", "detailed"):
                    return
                _today_ym = datetime.utcnow().strftime("%Y-%m")
                _answer_keys = self._filter_non_ended_range_keys(
                    self._extract_month_year_range_keys(state.get("answer", "")),
                    today_ym=_today_ym,
                )
                _recent_keys_live = self._filter_non_ended_range_keys(set(_recent_cross_topic_keys), today_ym=_today_ym)
                _candidate_keys_live = self._filter_non_ended_range_keys(set(_candidate_keys), today_ym=_today_ym)
                _reused_now = sorted(_answer_keys.intersection(_recent_keys_live))
                _available_alt = sorted(_candidate_keys_live - _recent_keys_live)
                _chosen_distinct = sorted(_answer_keys.intersection(set(_available_alt)))
                logger.info(
                    f"[TIMELINE_NOVELTY][{_tag}] query_type={_current_qt} "
                    f"reused_in_final={_reused_now[:4]} "
                    f"distinct_chosen={_chosen_distinct[:4]} "
                    f"alternatives_available={len(_available_alt)} "
                    f"recent_cross_topic_count={len(_recent_keys_live)} "
                    f"answer_window_count={len(_answer_keys)}"
                )

            if _prompt_response_mode == 'initial':
                _ok_init, _quality_init = self._assess_initial_timeline_quality(state.get('answer', ''), language=_detected_lang)
                _ok_init, _quality_init = _apply_cross_topic_novelty_issue(state.get('answer', ''), _quality_init)
                if not _ok_init:
                    _issues_init = ", ".join(_quality_init.get("issues", [])) or "insufficient timeline structure"
                    logger.info(
                        f"[INITIAL_QA] Quality gate failed "
                        f"(words={_quality_init.get('word_count')}, "
                        f"timeline_expr={(_quality_init.get('timeline_layers') or {}).get('timeline_expression_count')}). "
                        f"Issues: {_issues_init}."
                    )

                    # Middle path: only a missing *reasoning* sentence triggers an LLM rewrite
                    # (one pass only — no second strict pass). All other issues (missing dates,
                    # duration-only phrasing, cross-topic reuse) are handled cheaply by the
                    # deterministic injection below, without additional LLM calls.
                    _critical_init_issues = {
                        "missing_future_favorable_reason_in_short_answer",
                    }

                    def _issue_score(_q: Dict[str, Any]) -> Tuple[int, int]:
                        _issues = _q.get("issues", []) or []
                        _critical_count = sum(1 for _x in _issues if _x in _critical_init_issues)
                        return (_critical_count, len(_issues))

                    _orig_score = _issue_score(_quality_init)

                    if _orig_score[0] > 0:
                        # Single LLM rewrite pass — only for missing timing reasoning.
                        rewrite_prompt = self._build_initial_timeline_rewrite_prompt(
                            query=_effective_query,
                            draft_answer=state.get('answer', ''),
                            language=state.get('detected_language', 'en'),
                            quality=_quality_init,
                        )
                        try:
                            revised_init = self.llm.invoke(rewrite_prompt)
                            revised_init_text = _strip_llm_wrapper(revised_init.content if hasattr(revised_init, 'content') else str(revised_init))
                            _ok_init2, _quality_init2 = self._assess_initial_timeline_quality(revised_init_text, language=_detected_lang)
                            _ok_init2, _quality_init2 = _apply_cross_topic_novelty_issue(revised_init_text, _quality_init2)
                            _rev_score = _issue_score(_quality_init2)
                            if _ok_init2 or _rev_score < _orig_score:
                                state['answer'] = revised_init_text
                                logger.info(
                                    f"[INITIAL_QA] LLM rewrite accepted "
                                    f"(critical/issues {_orig_score} -> {_rev_score})."
                                )
                            else:
                                logger.info(
                                    f"[INITIAL_QA] LLM rewrite did not improve; keeping original "
                                    f"(critical/issues {_orig_score} -> {_rev_score})."
                                )
                        except Exception as _re:
                            logger.info(f"[INITIAL_QA] LLM rewrite skipped due to error: {_re}")
                    else:
                        logger.info(
                            "[INITIAL_QA] Skipping LLM rewrite: no reasoning issues "
                            f"(issues={', '.join(_quality_init.get('issues', []))})."
                        )

                    # Deterministic injection: always runs after the (optional) LLM pass.
                    # Fixes remaining date/window/reuse issues without an extra LLM call.
                    _det_text = state.get('answer', '')
                    _ok_det, _quality_det = self._assess_initial_timeline_quality(_det_text, language=_detected_lang)
                    _ok_det, _quality_det = _apply_cross_topic_novelty_issue(_det_text, _quality_det)
                    _det_trigger_issues = {
                        "insufficient_explicit_month_year_windows_in_short_answer",
                        "duration_only_timeline_without_explicit_month_year_ranges",
                        "reused_cross_topic_timeline_window_despite_available_alternatives",
                    }
                    if not _ok_det and bool(set(_quality_det.get("issues", [])).intersection(_det_trigger_issues)):
                        _patched = self._inject_deterministic_initial_timeline_diversity(
                            answer=_det_text,
                            dasha_data=state.get("dasha_data", {}),
                            language=_detected_lang,
                            recent_cross_topic_keys=_recent_cross_topic_keys,
                            min_lead_months=2,
                        )
                        if _patched != _det_text:
                            _ok_p, _quality_p = self._assess_initial_timeline_quality(_patched, language=_detected_lang)
                            _ok_p, _quality_p = _apply_cross_topic_novelty_issue(_patched, _quality_p)
                            _det_before = _issue_score(_quality_det)
                            _det_after = _issue_score(_quality_p)
                            if _ok_p or _det_after < _det_before:
                                state['answer'] = _patched
                                logger.info(
                                    f"[INITIAL_QA] Deterministic injection accepted "
                                    f"(critical/issues {_det_before} -> {_det_after})."
                                )

                    _final_issues_log = ", ".join(
                        self._assess_initial_timeline_quality(state.get('answer', ''), language=_detected_lang)[1].get("issues", [])
                    ) or "none"
                    logger.info(f"[INITIAL_QA] Final issues: {_final_issues_log}.")
            # Runtime quality gate for detailed responses:
            # enforce depth + timeline richness with one auto-regeneration pass.
            if _prompt_response_mode == 'detailed':
                _factor_profile = self._get_available_factor_categories_for_response(state)
                _ok, _quality = self._assess_detailed_answer_quality(
                    state.get('answer', ''),
                    factor_profile=_factor_profile,
                    language=_detected_lang,
                )
                _ok, _quality = _apply_cross_topic_novelty_issue(state.get('answer', ''), _quality)
                if not _ok:
                    _detailed_original_answer = state.get('answer', '')
                    _issues = ", ".join(_quality.get("issues", [])) or "insufficient detail"
                    logger.info(
                        f"[DETAILED_QA] Quality gate failed "
                        f"(words={_quality.get('word_count')}/min={_quality.get('min_words_threshold')}, lang={_detected_lang}, "
                        f"points={_quality.get('numbered_points')}, "
                        f"timing_ranges={_quality.get('timing_range_markers')}, years={_quality.get('year_mentions')}, "
                        f"factor_coverage={_quality.get('factor_coverage_count')}/{_quality.get('available_factor_count')}, "
                        f"underutilized={_quality.get('underutilized_mentioned_count')}/{_quality.get('underutilized_available_count')}). "
                        f"Issues: {_issues}. Regenerating once."
                    )
                    _critical_detailed_issues = {
                        "contains_past_year_timeline_reference",
                        "duration_only_timeline_without_explicit_month_year_ranges",
                        # timeline_not_varied_enough, multiple_major_claims_collapsed_into_same_short_window,
                        # and missing_distinct_cross_year_secondary_window are intentionally NOT critical:
                        # when all upcoming pratyantar windows fall within the same calendar year it is a
                        # data constraint, not a quality failure.  The rewrite prompt still guides the LLM
                        # to mention antardasha-level cross-year context when this is detected.
                        "missing_future_favorable_timeline_reason",
                        # fewer_than_7_numbered_points REMOVED — numbered structure is NOT required.
                        # The DETAILED instruction uses flowing prose. Forcing 7 numbered points produces
                        # bold markdown headers (1. **Mars ki Position**) which breaks prose style.
                        "structural_label_style_leak_in_user_facing_text",
                        "reused_cross_topic_timeline_window_despite_available_alternatives",
                    }

                    def _detailed_issue_score(_q: Dict[str, Any]) -> Tuple[int, int]:
                        _issues_local = _q.get("issues", []) or []
                        _critical_count = sum(1 for _x in _issues_local if _x in _critical_detailed_issues)
                        return (_critical_count, len(_issues_local))

                    _orig_score = _detailed_issue_score(_quality)
                    # _has_structural_gap removed — prose responses don't need 7 numbered points.
                    # Rewrite only when there are genuine critical issues (wrong dates, missing timing reasons, etc.)
                    _should_attempt_rewrite = _orig_score[0] > 0

                    if not _should_attempt_rewrite:
                        logger.info(
                            "[DETAILED_QA] Skipping rewrite: no critical issues "
                            f"(points={_quality.get('numbered_points')}, issues={', '.join(_quality.get('issues', []))})."
                        )
                        _current_issues = set(_quality.get("issues", []) or [])
                        _orig_words = int(_quality.get("word_count") or 0)
                        # Keep detailed answers compact by default. Only enrich when the draft is
                        # genuinely too short, not merely because it could be longer.
                        _should_enrich = (
                            "answer_too_short_for_detailed_mode" in _current_issues
                            and _orig_words < 260
                        )
                        if _should_enrich:
                            logger.info(
                                "[DETAILED_QA] Running one lightweight enrichment pass "
                                "for non-critical richness/timeline variety gaps."
                            )
                            _enrich_prompt = f"""You are lightly enriching a detailed astrology answer.
Keep ALL existing astrological facts unchanged.

User query: "{_effective_query}"
Language code to preserve: {state.get('detected_language', 'en')}

Current answer:
\"\"\"{state.get('answer', '')}\"\"\"

Requirements:
1) Keep ALL existing planet names, dasha/timing facts, and prose structure. Do NOT add numbered lists or bold headers.
2) Add concise depth so the answer feels fuller (typically +40 to +80 words), woven naturally into the prose.
3) If timeline variety is narrow, add one natural secondary future window (month-year phrasing) with reason,
   but do NOT contradict or change existing windows.
4) Maintain warm, natural astrologer tone — no structural labels like "Cross-Year Window", no markdown.
5) Keep it practical and user-facing.

Return ONLY the improved answer text."""
                            try:
                                _enriched = self.llm.invoke(_enrich_prompt)
                                _enriched_text = _strip_llm_wrapper(_enriched.content if hasattr(_enriched, 'content') else str(_enriched))
                                _ok_en, _quality_en = self._assess_detailed_answer_quality(
                                    _enriched_text,
                                    factor_profile=_factor_profile,
                                    language=_detected_lang,
                                )
                                _ok_en, _quality_en = _apply_cross_topic_novelty_issue(_enriched_text, _quality_en)
                                _en_score = _detailed_issue_score(_quality_en)
                                _en_words = int(_quality_en.get("word_count") or 0)
                                # Accept enriched if: passes QA, or improves score, or meaningfully longer (prose mode — no point count check)
                                _accept_enriched = (
                                    _ok_en
                                    or (_en_score < _orig_score)
                                    or (
                                        _en_score[0] == _orig_score[0] == 0
                                        and _en_words >= (_orig_words + 35)
                                        and _en_words <= 520
                                    )
                                )
                                if _accept_enriched:
                                    state['answer'] = _enriched_text
                                    logger.info(
                                        f"[DETAILED_QA] Lightweight enrichment accepted "
                                        f"(words={_orig_words}->{_en_words}, critical/issues {_orig_score}->{_en_score})."
                                    )
                                else:
                                    logger.info(
                                        f"[DETAILED_QA] Lightweight enrichment skipped (no meaningful gain) "
                                        f"(words={_orig_words}->{_en_words}, critical/issues {_orig_score}->{_en_score})."
                                    )
                            except Exception as _en_e:
                                logger.info(f"[DETAILED_QA] Lightweight enrichment skipped due to error: {_en_e}")
                    else:
                        rewrite_prompt = self._build_detailed_quality_rewrite_prompt(
                            query=_effective_query,
                            draft_answer=state.get('answer', ''),
                            language=state.get('detected_language', 'en'),
                            quality=_quality,
                            factor_profile=_factor_profile,
                        )
                        try:
                            revised = self.llm.invoke(rewrite_prompt)
                            revised_text = _strip_llm_wrapper(revised.content if hasattr(revised, 'content') else str(revised))
                            _ok2, _quality2 = self._assess_detailed_answer_quality(
                                revised_text,
                                factor_profile=_factor_profile,
                                language=_detected_lang,
                            )
                            _ok2, _quality2 = _apply_cross_topic_novelty_issue(revised_text, _quality2)
                            if _ok2:
                                state['answer'] = revised_text
                                logger.info(
                                    f"[DETAILED_QA] Regeneration passed "
                                    f"(words={_quality2.get('word_count')}, points={_quality2.get('numbered_points')}, "
                                    f"factor_coverage={_quality2.get('factor_coverage_count')}/{_quality2.get('available_factor_count')})."
                                )
                            else:
                                _rev_score = _detailed_issue_score(_quality2)
                                if _rev_score < _orig_score:
                                    state['answer'] = revised_text
                                    logger.info(
                                        f"[DETAILED_QA] Regeneration improved but not fully passing "
                                        f"(critical/issues {_orig_score} -> {_rev_score})."
                                    )
                                else:
                                    state['answer'] = _detailed_original_answer
                                    logger.info(
                                        f"[DETAILED_QA] Regeneration did not improve critical quality "
                                        f"(critical/issues {_orig_score} -> {_rev_score}). Keeping safer original draft."
                                    )

                                _chosen_text = state.get('answer', '')
                                _ok3, _quality3 = self._assess_detailed_answer_quality(
                                    _chosen_text,
                                    factor_profile=_factor_profile,
                                    language=_detected_lang,
                                )
                                _ok3, _quality3 = _apply_cross_topic_novelty_issue(_chosen_text, _quality3)
                                _critical_remaining = any(
                                    _x in _critical_detailed_issues for _x in (_quality3.get("issues", []) or [])
                                )
                                if _critical_remaining:
                                    logger.info(
                                        "[DETAILED_QA] Critical issues remain after first rewrite. "
                                        "Applying one strict corrective pass."
                                    )
                                    strict_prompt = self._build_detailed_quality_rewrite_prompt(
                                        query=_effective_query,
                                        draft_answer=_chosen_text,
                                        language=state.get('detected_language', 'en'),
                                        quality=_quality3,
                                        factor_profile=_factor_profile,
                                    )
                                    strict_resp = self.llm.invoke(strict_prompt)
                                    strict_text = _strip_llm_wrapper(strict_resp.content if hasattr(strict_resp, 'content') else str(strict_resp))
                                    _ok4, _quality4 = self._assess_detailed_answer_quality(
                                        strict_text,
                                        factor_profile=_factor_profile,
                                        language=_detected_lang,
                                    )
                                    _ok4, _quality4 = _apply_cross_topic_novelty_issue(strict_text, _quality4)
                                    _chosen_score = _detailed_issue_score(_quality3)
                                    _strict_score = _detailed_issue_score(_quality4)
                                    # Only accept strict pass when critical count decreases or fully passes.
                                    # A reduction in non-critical issues only (same critical count) is not
                                    # sufficient to replace the draft — factual drift risk outweighs minor gains.
                                    if _ok4 or _strict_score[0] < _chosen_score[0]:
                                        state['answer'] = strict_text
                                        _quality3 = _quality4  # update to reflect final accepted answer
                                        logger.info(
                                            f"[DETAILED_QA] Strict corrective pass accepted "
                                            f"(critical/issues {_chosen_score} -> {_strict_score})."
                                        )
                                    else:
                                        logger.info(
                                            f"[DETAILED_QA] Strict corrective pass did not reduce critical issues "
                                            f"(critical/issues {_chosen_score} -> {_strict_score}). Retaining safer draft."
                                        )

                                # _quality3 now reflects the actual final chosen answer quality
                                logger.info(
                                    f"[DETAILED_QA] Regeneration still below target "
                                    f"(words={_quality3.get('word_count')}, "
                                    f"points={_quality3.get('numbered_points')}, "
                                    f"timing_ranges={_quality3.get('timing_range_markers')}, "
                                    f"factor_coverage={_quality3.get('factor_coverage_count')}/{_quality3.get('available_factor_count')}, "
                                    f"issues={', '.join(_quality3.get('issues', []))})."
                                )
                        except Exception as _re:
                            logger.info(f"[DETAILED_QA] Regeneration skipped due to error: {_re}")

            # Deterministic year-diversity guard:
            # If computed timing data has future cross-year options, avoid collapsing
            # the final response to only current-year windows for every query.
            try:
                _q_low = (_effective_query or "").lower()
                _urgent_now = any(k in _q_low for k in ["immediate", "immediately", "urgent", "asap", "abhi", "jaldi", "right now"])
                if _prompt_response_mode in ("initial", "detailed") and _has_cross_year_future_options and not _urgent_now:
                    import re as _re_yd
                    _years_in_answer = sorted({
                        int(y) for y in _re_yd.findall(r"\b((?:19|20)\d{2})\b", state.get("answer", ""))
                    })
                    _answer_is_current_year_only = bool(_years_in_answer) and max(_years_in_answer) <= _current_year
                    if _answer_is_current_year_only:
                        _future_years_text = ", ".join(str(y) for y in _available_future_years if y > _current_year)
                        logger.info(
                            f"[TIMELINE_DIVERSITY] Current-year-only output detected (years={_years_in_answer}) "
                            f"despite future options={_available_future_years}. Regenerating once."
                        )
                        _yd_prompt = f"""You are refining an astrology answer.
Keep all existing factual astrological reasoning intact.

User query: "{_effective_query}"
Language code to preserve: {state.get('detected_language', 'en')}

Current answer:
\"\"\"{state.get('answer', '')}\"\"\"

Mandatory improvements:
1) Keep the same main conclusion and same core logic.
2) Keep one practical near-term timeline if already present.
3) ALSO include at least one clearly reasoned secondary future window in a later year
   (available future years include: {_future_years_text}).
4) Use month-year ranges only; no exact day dates.
5) Do not use robotic labels; keep language natural and professional.

Return ONLY the improved answer text."""
                        _yd_resp = self.llm.invoke(_yd_prompt)
                        _yd_text = _strip_llm_wrapper(_yd_resp.content if hasattr(_yd_resp, "content") else str(_yd_resp))
                        if _yd_text and _yd_text.strip():
                            state["answer"] = _yd_text.strip()
            except Exception as _yd_e:
                logger.info(f"[TIMELINE_DIVERSITY] Guard skipped due to error: {_yd_e}")

            _log_novelty_summary("FINAL")
            
        except Exception as e:
            logger.error(f"[ERROR] RAG_WITH_CALCULATION failed: {e}")
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
        logger.info("[RAG_ONLY] General theory question - no chart calculation needed")
        
        try:
            knowledge_chunks = state.get('knowledge_chunks') or []

            if not knowledge_chunks and self.hybrid_retriever:
                knowledge_chunks = self.hybrid_retriever.retrieve(
                    query=state['query'],
                    intent="RAG_ONLY",
                    top_k=RAGConfig.get_top_k(content_type='general'),  # Auto: 8 chunks
                    language=state.get('detected_language', 'en'),
                    content_type='general',
                    user_id=state.get('user_id')
                )
            elif not knowledge_chunks:
                 logger.info("[RAG_ONLY] [WARN] No retriever provided and no chunks injected.")
            
            state['knowledge_chunks'] = knowledge_chunks
            logger.info(f"[RAG_ONLY] Retrieved {len(knowledge_chunks)} knowledge chunks")
            
            # Step 2: Build prompt for general theory
            prompt = self._build_theory_prompt(
                query=state['query'],
                knowledge_chunks=knowledge_chunks,
                user_profile=state['user_profile'],
                language=state.get('detected_language', 'en')
            )
            
            if not knowledge_chunks or len(knowledge_chunks) == 0:
                logger.info("[RAG_ONLY] [WARN] No chunks - using fallback")
                
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
                logger.info("[RAG_ONLY] [GROUNDED] Refused to answer without sources")
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

            # Current query
            user_prompt = "USER_QUERY:" + prompt.split("====USER_QUERY_MARKER====")[1]
            messages.append({
                "role": "user",
                "content": user_prompt
            })

            # Invoke with full context
            logger.info(f"[LLM] Sending {len(messages)} messages to LLM")
            response = self.llm.invoke(messages)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            logger.error(f"[ERROR] RAG_ONLY path failed: {e}")
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
            script_instruction = f"Respond entirely in {lang_name} using ROMAN ALPHABET (English script only, NOT native script)."
        elif language != 'en':
            script_instruction = f"Respond entirely in {lang_name} (native script)."
        else:
            script_instruction = "Respond in clear, professional English."

        # Use dynamic instruction builder (adapts to query content and verbosity preference)
        # We don't have intent_analysis in this pure-theory path, so we rely on
        # query-only classification inside _build_response_instructions.
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
            logger.info(f"[CRITIC] Validation failed: {e}")
            return True, f"Validation error: {e}"  # Fail open to avoid blocking users on technical error
            
    def _validate_response_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3.5: The Critic - Verification Loop.
        Checks generated answer against safety constitution.
        """
        logger.info("[CRITIC] Validating response safety...")
        
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
            logger.info(f"[CRITIC] [FAIL] Unsafe response detected: {feedback}")
            state['validation_feedback'] = feedback
            
            # Simple Self-Correction (Rewrite)
            # If this is the first failure, try to fix it.
            if state['validation_attempts'] <= 1:
                logger.info("[CRITIC] Attempting to rewrite safely...")
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
                    logger.info("[CRITIC] [OK] Response rewritten.")
                except Exception as e:
                    state['error'] = f"Rewriting failed: {e}"
                    state['answer'] = "I cannot answer this query due to safety guidelines."
            else:
                # If we failed twice, block it.
                state['answer'] = "I must decline to answer this request as it violates my safety constitution regarding harmful or fatalistic predictions."
        else:
            logger.info("[CRITIC] [OK] Response is SAFE.")
            
        return state

    def _format_response_node(self, state: NakshatraState) -> NakshatraState:
        """Node 4: Format final response."""
        
        if not state.get('error'):
            final_response = state.get('answer', '')
            
            # PHASE 10.5: Disclaimer Injection
            # Skip for INITIAL responses — they are short teasers; disclaimer belongs in DETAILED.
            disclaimer_type = state.get('disclaimer_type')
            if disclaimer_type and not state.get('_was_initial_response'):
                detected_lang = state.get('detected_language', 'en')
                disclaimer_text = get_disclaimer(disclaimer_type, language=detected_lang, llm=self.fast_llm)
                final_response = f"{final_response}\n\n{disclaimer_text}"
            
            # PHASE 12: Validation Disclaimer — injected into prompt context, NOT appended to final response.
            # build_validation_disclaimer() now returns a [CONTEXT FOR LLM: ...] instruction block.
            # The prompt builder picks it up from state['validation_disclaimer'] via the
            # validation_context section. We do NOT append it here — that would expose raw
            # instruction text to the user.
            # (No-op in the formatting phase — disclaimer already in prompt via _build_synthesis_prompt.)

            # PHASE 10.5: Reframe Intro Injection
            if state.get('is_reframed', False):
                from src.safety.templates import format_reframe_response
                reframe_intro = format_reframe_response(state.get('original_query', ''), state.get('query', ''))
                final_response = f"{reframe_intro}{final_response}"
            
            state['answer'] = final_response
            logger.info("[FORMATTING] Formatted final response.")
            
        return state
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_available_factor_categories_for_response(self, state: NakshatraState) -> Dict[str, Any]:
        """
        Build a compact profile of computed astrological factor categories available
        for this response, so detailed QA can enforce richer factor usage.
        """
        chart = state.get('chart_data') or {}
        dasha = state.get('dasha_data') or {}
        transit = state.get('transit_data') or {}
        enhanced = state.get('enhanced_analysis') or {}
        synthesis = state.get('synthesis') or {}
        validation = state.get('validation_result') or {}

        available = set()

        # Core deterministic layers
        if chart and self._compute_house_lords_block(chart):
            available.add("house_lords")
        if dasha.get('mahadasha') or dasha.get('antardasha'):
            available.add("dasha_stack")
        if dasha.get('upcoming_pratyantardashas'):
            available.add("pratyantar_windows")
        if transit.get('transits'):
            available.add("gochara_transits")

        # Enriched chart layers
        if chart.get('yogas') or synthesis.get('yogas_detected'):
            available.add("yogas")
        if chart.get('divisional_charts_simple') or chart.get('navamsa') or chart.get('vargas'):
            available.add("divisional_confirmation")

        _planets = chart.get('planets') or {}
        if isinstance(_planets, dict):
            _has_conditions = any(
                isinstance(pd, dict) and (
                    pd.get('retrograde') or
                    pd.get('combust') or
                    pd.get('is_stationary') or
                    (pd.get('combustion_status') not in (None, "", "not_combust"))
                )
                for pd in _planets.values()
            )
            if _has_conditions:
                available.add("planetary_conditions")

        if chart.get('vargottama'):
            available.add("vargottama")
        if chart.get('vimshopaka'):
            available.add("vimshopaka")
        if chart.get('planetary_wars'):
            available.add("planetary_wars")
        if chart.get('house_occupancy'):
            available.add("house_occupancy")
        if enhanced.get('aspects') or chart.get('aspects'):
            available.add("aspects")

        # Structured analysis layers
        if validation:
            available.add("validation_findings")
        if synthesis.get('chart_strengths') or synthesis.get('chart_challenges'):
            available.add("synthesis_strengths_challenges")

        underutilized_priority = [
            "gochara_transits",
            "yogas",
            "divisional_confirmation",
            "planetary_conditions",
            "vargottama",
            "vimshopaka",
            "planetary_wars",
            "house_occupancy",
            "aspects",
        ]
        underutilized_available = [c for c in underutilized_priority if c in available]

        return {
            "available_categories": sorted(available),
            "underutilized_available": underutilized_available,
        }

    def _get_json_llm(self):
        """
        Return a JSON-mode LLM instance (cached).  Uses .bind() on the
        underlying ChatVertexAI to set response_format=json_object.
        Falls back to None if the provider does not support JSON mode.
        """
        if self.llm_json is None:
            try:
                base = self.llm.llm if hasattr(self.llm, 'llm') else self.llm
                self.llm_json = base.bind(response_format={"type": "json_object"})
                logger.info("[JSON_LLM] JSON-mode LLM initialised")
            except Exception as e:
                logger.warning(f"[JSON_LLM] Cannot create JSON-mode LLM: {e}")
                self.llm_json = False  # False = permanently unavailable
        return self.llm_json if self.llm_json else None

    def _assemble_short_response(self, data: dict) -> str:
        """Assemble 5-field JSON dict into a flowing short prose response."""
        parts = []
        for key in ("current_context", "key_factor", "near_term_window", "broader_window", "closing"):
            val = (data.get(key) or "").strip()
            if val:
                parts.append(val)
        return "\n\n".join(parts)

    def _assemble_detailed_response(self, data: dict) -> str:
        """Assemble 9-point JSON dict into numbered detailed response."""
        parts = []
        for i in range(1, 10):
            val = (data.get(f"point_{i}") or "").strip()
            if val:
                parts.append(f"{i}. {val}")
        result = "\n\n".join(parts)
        convergence = (data.get("convergence") or "").strip()
        if convergence:
            result += f"\n\n{convergence}"
        followup = (data.get("followup_question") or "").strip()
        if followup:
            result += f"\n\n{followup}"
        return result

    def _llm_check_future_favorable(self, text: str) -> bool:
        return llm_check_future_favorable(text, fast_llm=getattr(self, "fast_llm", self.llm))

    def _assess_detailed_answer_quality(
        self,
        answer: str,
        factor_profile: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> Tuple[bool, Dict[str, Any]]:
        return assess_detailed_answer_quality(
            answer, factor_profile, language,
            fast_llm=getattr(self, "fast_llm", self.llm),
        )

    def _assess_timeline_layer_coverage(self, answer: str) -> Dict[str, Any]:
        return assess_timeline_layer_coverage(answer)

    def _analyze_timeline_overlap(self, answer: str) -> Dict[str, Any]:
        return analyze_timeline_overlap(answer)

    def _collect_future_timing_years(self, dasha_data, max_years_ahead: int = 5) -> List[int]:
        return collect_future_timing_years(dasha_data, max_years_ahead)

    def _extract_month_year_range_keys(self, text: str) -> set:
        return extract_month_year_range_keys(text)

    def _filter_non_ended_range_keys(self, keys: set, today_ym: Optional[str] = None) -> set:
        return filter_non_ended_range_keys(keys, today_ym)

    def _infer_topic_from_text(self, text: str) -> str:
        return infer_topic_from_text(text)

    def _collect_recent_cross_topic_window_keys(
        self, conversation_history, current_query_type: str, max_assistant_turns: int = 8,
    ) -> Dict[str, Any]:
        return collect_recent_cross_topic_window_keys(conversation_history, current_query_type, max_assistant_turns)

    def _collect_recent_planet_factors(self, conversation_history, max_turns: int = 3) -> List[str]:
        return collect_recent_planet_factors(conversation_history, max_turns)

    def _analyze_query_context(self, query: str, conversation_history) -> str:
        return analyze_query_context(query, conversation_history, fast_llm=getattr(self, "fast_llm", self.llm))

    def _build_coherence_hint(self, conversation_history, current_topic: str, current_query: str = "") -> str:
        return build_coherence_hint(conversation_history, current_topic, current_query)

    def _collect_future_candidate_window_keys(self, dasha_data) -> set:
        return collect_future_candidate_window_keys(dasha_data)

    def _inject_deterministic_initial_timeline_diversity(
        self,
        answer: str,
        dasha_data: Optional[Dict[str, Any]],
        language: str = "en",
        recent_cross_topic_keys: Optional[set[str]] = None,
        min_lead_months: int = 2,
    ) -> str:
        return inject_deterministic_initial_timeline_diversity(
            answer, dasha_data, language, recent_cross_topic_keys, min_lead_months
        )

    def _assess_initial_timeline_quality(self, answer: str, language: str = "en") -> Tuple[bool, Dict[str, Any]]:
        return assess_initial_timeline_quality(answer, language, fast_llm=getattr(self, "fast_llm", self.llm))

    def _build_initial_timeline_rewrite_prompt(
        self,
        query: str,
        draft_answer: str,
        language: str,
        quality: Dict[str, Any],
    ) -> str:
        return build_initial_timeline_rewrite_prompt(query, draft_answer, language, quality)

    def _build_detailed_quality_rewrite_prompt(
        self,
        query: str,
        draft_answer: str,
        language: str,
        quality: Dict[str, Any],
        factor_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        return build_detailed_quality_rewrite_prompt(query, draft_answer, language, quality, factor_profile)


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
        mode: str = 'theory',  # 'theory' or 'prediction'
        response_mode: str = 'default',  # 'initial' | 'detailed' | 'followup' | 'default'
        intent_domain: Optional[str] = None,
        question_mode: Optional[str] = None,
        polarity: Optional[str] = None,
    ) -> str:
        """
        Build adaptive response instructions based on what the user is actually asking.
        Returns fuller instructions for detail requests, concise for standard queries.
        Dynamically adds domain-specific guidance (career, timing, health, compatibility).
        """
        q = query.lower()
        wants_detail = self._user_wants_detail(query)

        # Prefer LLM-classified domain/mode/polarity when available (from context_manager.analyze_message_intent)
        # Fall back to keyword-based detection only when these are missing.
        _domain = (intent_domain or "").lower().strip() if intent_domain else ""
        _qmode = (question_mode or "").lower().strip() if question_mode else ""
        _polarity = (polarity or "").lower().strip() if polarity else ""

        # Domain-specific timing guidance — tells the LLM which Pratyantar windows
        # and Gochara factors are relevant for THIS specific query type.
        domain_hints = []

        # ── Generic timing hint (LLM-driven when possible) ──────────────
        _is_timing_mode = _qmode == 'timing' or any(
            w in q for w in ['when', 'kab', 'timing', 'which year', 'how long',
                             'kitne din', 'which month', 'period', 'dasha', 'antardasha',
                             'kab hoga', 'kab milega', 'kab hogi']
        )
        if _is_timing_mode:
            domain_hints.append(
                "TIMING WINDOW: Use the Pratyantar Dasha windows (listed above under 'Upcoming Pratyantardashas') "
                "combined with the Gochara factors to identify the most supportive phase. Build timing in TWO LAYERS: "
                "(1) a broader supportive phase (typically 9-24 months, and can cross calendar years when data supports it), and "
                "(2) one concrete trigger sub-window from the relevant Pratyantar inside that broader phase. "
                "Do NOT narrow the answer down to specific weeks or exact days; avoid phrases like 'second week of March' or 'last week of the year'. "
                "Always speak in terms of broader month+year ranges that feel natural in conversation."
            )

        # ── Marriage / relationship / divorce ───────────────────────────────────
        _marriage_keywords = [
            'marriage', 'marry', 'married', 'shaadi', 'shadi', 'vivah', 'wedding',
            'partner', 'love', 'spouse', 'husband', 'wife', 'rishta', 'relationship',
            'bypass', 'saat phere', 'pyaar', 'prem', 'milega', 'milegi',
            'life partner', 'kesi hogi', 'kaisi hogi', 'kesa hoga', 'kaisa hoga',
            'groom', 'bride', 'dulha', 'dulhan', 'shaadi kab', 'vivah kab'
        ]
        _divorce_keywords = [
            'divorce', 'separation', 'separate', 'alag hona', 'talaq', 'breakup',
            'break-up', 'judicial separation', 'relationship end', 'marriage end'
        ]

        # HARD OVERRIDE 1: if the literal query mentions divorce/separation, force the
        # semantic domain to 'divorce' even if the LLM classified it as 'marriage'.
        if any(w in q for w in _divorce_keywords):
            _domain = 'divorce'

        # HARD OVERRIDE 2: if the LLM polarity is explicitly negative for a relationship
        # query, prefer the divorce/strain framing over a celebratory marriage framing.
        if _polarity == 'negative' and _domain == 'marriage':
            _domain = 'divorce'

        if _domain == 'marriage' or (_domain == "" and any(w in q for w in _marriage_keywords) and not any(w in q for w in _divorce_keywords)):
            # Standard marriage / partner-focus instructions
            domain_hints.append(
                "MARRIAGE & PARTNER ANALYSIS — Answer ALL parts of the user's question:\n"
                "  PART A — PARTNER QUALITIES (always include, regardless of exact question wording):\n"
                "  • 7th house (Marriage & Partnership) sign and planets: describe the partner's nature in simple words.\n"
                "  • 7th lord sign and house: add 1 short line on how/where the partner may come into life.\n"
                "  PART B — CHART FACTORS FOR TIMING (only when user is asking 'when'):\n"
                "  • 7th lord dignity and afflictions (Saturn/Rahu/Ketu/Mars).\n"
                "  • 2nd house (Wealth & Family) and 11th house (Gains & Desires) support for stable married life.\n"
                "  PART C — TIMING (use this priority order):\n"
                "  1. Find VENUS Pratyantar first — Venus is the primary marriage karaka.\n"
                "  2. If no Venus Pratyantar in current AD, check 7th house lord's Pratyantar (see HOUSE LORDS table).\n"
                "  3. Cross-check: Is Jupiter Gochar in H5, H7, or H9 from natal Moon? (Gochara section)\n"
                "  4. Give a broader supportive phase first (9-24 months when data supports), then cite the relevant Pratyantar as the trigger inside that phase.\n"
                "  PART D — RELATIONSHIP QUALITY (include in detailed responses):\n"
                "  • Briefly trace the DISPOSITOR CHAIN of Venus (or the 7th lord): what sign is Venus in? Who rules that sign?"
                " What does that ruler's placement say about the emotional quality of the relationship?\n"
                "  • If Venus is in a sign ruled by Moon (Cancer), emotional depth is high; if Mercury (Gemini/Virgo),"
                " intellectual compatibility matters; if Saturn (Capricorn/Aquarius), the relationship is serious and structured — etc.\n"
                "  • Keep this to 1-2 sentences and always translate into what it means for the person's actual love life.\n"
                "  ⚠ You MUST discuss at least 7th, 2nd, and 5th house lords from the computed table — not just 7th alone."
            )

        # Divorce / separation specific guidance – must NOT talk like a generic 'good marriage timing' question
        if _domain == 'divorce' or (_domain == "" and any(w in q for w in _divorce_keywords)):
            domain_hints.append(
                "DIVORCE / SEPARATION QUERY — interpret the question as assessing relationship strain, not new marriage timing:\n"
                "  • Focus on 7th house (Marriage & Partnership), 8th house (Longevity & Transformation), and 12th house (Foreign & Moksha) for stress indicators.\n"
                "  • Highlight difficult combinations involving Mars, Saturn, Rahu, or Ketu on the 7th lord or 7th house.\n"
                "  • Discuss whether current or upcoming Pratyantar periods of these planets show heightened conflict or the need for counseling/space.\n"
                "  • DO NOT talk about 'favourable marriage time' or new marriage windows unless the user clearly asks about remarriage.\n"
                "  • Keep language supportive and practical (communication, counseling, boundaries) rather than fatalistic."
            )

        # ── Career / job / business ────────────────────────────────────────────
        if _domain == 'career' or (_domain == "" and any(
            w in q for w in ['career', 'job', 'business', 'naukri', 'profession', 'promotion',
                             'kaam', 'vyapar', 'work', 'income', 'salary', 'office',
                             'interview', 'selection', 'appointment']
        )):
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
                "  5. Give a broader supportive phase first (9-24 months when data supports), then cite the relevant Pratyantar as the trigger inside that phase.\n"
                "  ⚠ You MUST discuss at least H10, H6, and H2 lords from the computed table — not just H10 alone."
            )

        # ── Foreign travel / abroad ────────────────────────────────────────────
        if _domain in ('foreign', 'foreign_travel') or (_domain == "" and any(
            w in q for w in ['foreign', 'abroad', 'videsh', 'travel', 'yatra', 'immigration',
                             'visa', 'overseas', 'bahar', 'country', 'settle abroad',
                             'job abroad', 'foreign land']
        )):
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
                "  6. Give a broader supportive phase first (9-24 months when data supports), then cite the relevant Pratyantar as the trigger inside that phase.\n"
                "  ⚠ You MUST discuss H9 and H12 lords from the computed table. NEVER substitute Jupiter as 9th lord "
                "unless the HOUSE LORDS table explicitly shows Jupiter as the 9th lord for this Lagna."
            )

        # ── Children ───────────────────────────────────────────────────────────
        if _domain == 'children' or (_domain == "" and any(
            w in q for w in ['child', 'children', 'baby', 'pregnancy', 'bachha', 'bacche',
                             'santan', 'offspring', 'conceive', 'delivery']
        )):
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
                "  4. Give a broader supportive phase first (9-24 months when data supports), then cite the relevant Pratyantar as the trigger inside that phase.\n"
                "  ⚠ You MUST discuss H5 and H9 lords from the computed table — not just Jupiter generically."
            )

        # ── Home / property / real estate ──────────────────────────────────────
        if _domain in ('home', 'property') or (_domain == "" and any(
            w in q for w in ['ghar', 'makaan', 'makan', 'home', 'house', 'flat', 'plot', 'property',
                             'real estate', 'zameen', 'naya ghar', 'new home', 'ghar lena',
                             'ghar kharidna', 'buy house', 'buy home', 'property buy',
                             'renovation', 'construction', 'bhumi', 'land']
        )):
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
                "  5. Give a broader supportive phase first (9-24 months when data supports), then cite the relevant Pratyantar as the trigger inside that phase.\n"
                "  ⚠ You MUST discuss H4 and H2 lords from the computed table.\n"
                "  ⚠ Do NOT use the same Jupiter/Venus Pratyantar cited for marriage or career — this query is about HOME."
            )

        # ── Finance / wealth ───────────────────────────────────────────────────
        if _domain in ('finance', 'wealth') or (_domain == "" and any(
            w in q for w in ['money', 'wealth', 'paisa', 'dhan', 'rich', 'invest', 'finance',
                             'loan', 'debt', 'savings', 'profit', 'loss']
        )):
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
        if _domain == 'health' or (_domain == "" and any(
            w in q for w in ['health', 'illness', 'sick', 'disease', 'bimari', 'sehat', 'swasth',
                             'hospital', 'surgery', 'pain', 'accident', 'injury']
        )):
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

        # ── Generic fallback hint for uncategorized prediction queries ────────────
        # Fires only when NO domain-specific hint was matched above (domain_hints is empty)
        # AND the query looks like a chart-reading / outcome question, not a pure
        # conceptual explanation.
        _CONCEPTUAL_MARKERS = {
            'what is', 'what does', 'what are', 'explain', 'tell me about',
            'kya hai', 'kya hota', 'kya matlab', 'samjhao', 'batao kya',
            'define', 'meaning of', 'means', 'which planet', 'which house',
        }
        _OUTCOME_MARKERS = {
            'when', 'kab', 'will i', 'hoga', 'hogi', 'milega', 'milegi',
            'how long', 'kitne', 'period', 'future', 'upcoming', 'prediction',
            'my life', 'mera jeevan', 'meri zindagi', 'sade sati', 'bad phase',
            'bura samay', 'achha samay', 'good time', 'bad time', 'relief',
        }
        _is_conceptual = any(m in q for m in _CONCEPTUAL_MARKERS)
        _is_outcome = any(m in q for m in _OUTCOME_MARKERS)

        if not domain_hints:
            if _is_outcome or (not _is_conceptual):
                # Genuine prediction query that doesn't fit a named domain —
                # e.g. "Sade Sati kab khatam hogi?", "When will my bad phase end?",
                # "What does my 8th house predict for me?", "My Rahu period effects"
                domain_hints.append(
                    "GENERAL PREDICTION — this query doesn't match a named life domain (marriage/career/etc.) "
                    "but is still a chart-reading question. Follow these steps:\n"
                    "  1. Identify which house(s) and planet(s) are most relevant to the query topic.\n"
                    "  2. Check those planets' dignity, retrograde, and combustion flags from the chart table.\n"
                    "  3. For timing: find the Pratyantar of the most relevant planet in Step 3.5 above.\n"
                    "  4. For Sade Sati or Saturn-related phases: check Saturn's current transit house "
                    "     from Moon (Gochara block) — Sade Sati ends when Saturn leaves the sign just after "
                    "     natal Moon sign. Use these dates only as the mathematical basis.\n"
                    "  5. In user-facing text, express timing as a broader supportive window (typically 9–24 months, month/year only), "
                    "     never as exact calendar days."
                )

        domain_text = ("\n" + "\n".join(f"- {h}" for h in domain_hints)) if domain_hints else ""

        # ── NEXT FAVORABLE WINDOW — only for outcome/timing queries ───────────
        # NOT injected for pure conceptual/explanatory queries like
        # "What does debilitated Venus mean?" or "Explain my 8th house."
        # The data is already in the prompt (upcoming_pds_str, next_ad_fp_str,
        # upcoming_ads_str) so no extra calculation is needed when it is relevant.
        _needs_timing_window = _is_outcome or any(domain_hints) and not _is_conceptual
        next_window_block = """

SECONDARY SUPPORTIVE WINDOW (NO SPECIAL HEADING):
If useful, you may mention one additional supportive window in natural prose.
Do NOT use any heading like "Next Favorable Window".

CRITICAL — HOW TO PICK THIS WINDOW:
  Pratyantar periods are consecutive — every period starts when the previous one
  ends. Do NOT simply pick the chronologically next Pratyantar.
  Pick a genuinely topic-relevant later window (typically 4–8+ weeks after the
  primary window already cited), and skip unrelated planets.

  Topic → Relevant planets to scan for (priority order):
  • Marriage / relationship → Venus, then Jupiter, then 7th house lord
  • Career / job           → Saturn, then Sun, then Mercury, then 10th house lord
  • Home / property        → Moon, then Mars, then 4th house lord
  • Foreign travel         → Rahu, then 9th house lord, then 12th house lord
  • Finance / wealth       → Venus, then Jupiter, then 2nd house lord, then 11th house lord
  • Children               → Jupiter, then Moon, then 5th house lord
  • Health                 → Sun, then Saturn

NEVER fabricate dates. NEVER repeat the same Pratyantar already cited as the primary window."""

        # Suppress extra timing window only for FOLLOWUP phase:
        # follow-up questions are often about a specific factor and can become noisy.
        # INITIAL/NEW_TOPIC now supports richer short answers, so one secondary
        # supportive window is allowed when relevant.
        _timing_section = (
            (next_window_block if _needs_timing_window else "")
            if response_mode != 'followup'
            else ""
        )

        # Global stylistic reminder so the LLM does not copy any of these
        # instruction bullets verbatim into user-facing text.
        _style_flex = (
            "\nSTYLE FLEXIBILITY (IMPORTANT): These bullets are constraints, not sentences to copy. "
            "Do NOT echo their wording. Write in your own natural style while staying inside these rules."
        )
        _voice_charter = "\n" + get_voice_charter(lang_name.lower())
        _response_flow = "\n" + get_response_structure_policy()

        if wants_detail:
            if mode == 'prediction':
                return f"""INSTRUCTIONS:
1. Provide a comprehensive, detailed prediction with full reasoning.
2. TARGET LENGTH: 380-500 words. Keep it concise but complete; avoid unnecessary repetition.
3. Explain 7 to 9 numbered astrological factors (minimum 7), prioritizing the most decision-relevant ones.
4. Ground every claim in specific chart data (actual houses, signs, planets listed above).
5. Use layered timing with reasoning:
   - current context,
   - one near-term activation period from relevant Pratyantar (explicit month-year),
   - one broader future period (explicit month-year; may cross years),
   - optional later consolidation period when data supports it.
   - For every major prediction claim, include at least one future favorable/supportive timeline with reason.
   For both, show reason chain: factor -> timing logic -> practical implication.
   - IMPORTANT STYLE: do not use framework labels like "short trigger window",
     "long supportive phase", "maturation horizon", or "timeline ladder" in user-facing text.
6. Include all relevant available layers where present: house lords, dasha/pratyantar, gochara, yogas, divisional confirmation, planetary conditions, and strength modifiers (vargottama/vimshopaka/planetary war/house occupancy).
7. Do NOT cite classical texts or provide book names as sources unless the user explicitly demands it.
8. {script_instruction}{domain_text}{_timing_section}{_style_flex}{_voice_charter}{_response_flow}

Provide a thorough, detailed prediction:"""
            else:
                return f"""INSTRUCTIONS:
1. Provide a comprehensive explanation covering the concept fully.
2. Ground the answer in the retrieved classical texts above.
3. Do NOT cite books or provide source names unless the user explicitly demands it.
4. {script_instruction}{domain_text}{_style_flex}{_voice_charter}{_response_flow}

Provide a detailed explanation:"""
        else:
            if mode == 'prediction':
                return f"""INSTRUCTIONS:
1. Give a warm, human, narrative answer. MINIMUM LENGTH: 150 words (range 150-200). You MUST reach 150 words — do not stop early.
2. Include 2-3 critical astrological factors (house-lord logic, dasha/pratyantar, gochara, yoga, planetary condition, etc.).
   Technical terms are allowed, but each factor must be translated into practical real-life meaning.
3. State the prediction clearly with a 3-layer timeline:
   - present context (current/ongoing trend),
   - one concrete near-term activation period from relevant Pratyantar (explicit month-year),
   - broader future period (explicit month-year; may cross years).
   Every major prediction claim must include a future favorable/supportive timeline with a reason.
   Do not use framework labels in user-facing text; keep it natural.
4. Use explicit month-year ranges for all major timelines; do not keep any core window as duration-only text.
5. Use only future-facing computed dates and month/year ranges; never exact day-level dates.
6. At the end, briefly offer to explain the astrological reasoning in more detail if the user wants it.
7. Do NOT cite sources or provide book names unless the user explicitly demands it.
8. {script_instruction}{domain_text}{_timing_section}{_style_flex}{_voice_charter}{_response_flow}

Provide a warm, self-contained response:"""
            else:
                return f"""INSTRUCTIONS (CONCISE MODE):
1. Answer in 2-3 focused sentences (80-120 words).
2. Base the answer only on retrieved texts above.
3. Do NOT cite sources or provide book names unless the user explicitly demands it.
4. {script_instruction}{domain_text}{_style_flex}{_voice_charter}{_response_flow}

Provide a concise, clear answer:"""

    def _format_conversation_for_llm(
        self,
        conversation_history: List[Dict],
        max_messages: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Format conversation history for LLM, enforcing CONVERSATION_CONTEXT_WINDOW.

        - Caps history at `max_messages` (default 10 = CONVERSATION_CONTEXT_WINDOW).
          chat_stateless.py pre-slices before calling the orchestrator, but this
          ensures the cap is respected even if the orchestrator is called directly.
        - Skips leading assistant-only messages (e.g. app welcome/greeting preamble).
        - Drops assistant messages sourced from the old system ("external"/"gemini"/"openai")
          to prevent hallucinated house lords from polluting the new LLM's context.

        Args:
            conversation_history: List of {role, content, metadata, ...} dicts
            max_messages: Context window cap (default: 10)

        Returns:
            List of {role, content} dicts ready for LLM, always starting with a user turn.
        """
        if not conversation_history:
            return []

        # Enforce context window — keep only the most recent N messages
        history = conversation_history[-max_messages:]

        # Skip leading assistant-only messages (welcome preamble has no user turn)
        first_user_idx = None
        for i, msg in enumerate(history):
            if msg.get("role") == "user":
                first_user_idx = i
                break

        if first_user_idx is None:
            return []  # No user messages — only bot preamble, nothing to send

        if first_user_idx > 0:
            logger.info(f"[HISTORY] Skipping {first_user_idx} leading assistant-only message(s) from LLM context")

        formatted = []
        skipped_external = 0
        skipped_app = 0
        for msg in history[first_user_idx:]:
            if msg.get("role") == "assistant":
                src = (msg.get("metadata") or {}).get("source", "")
                # Drop messages from old system — they contain hallucinated chart data
                if src in ("external", "openai", "gemini"):
                    skipped_external += 1
                    continue
                # Drop app-generated assistant messages (welcome messages, user detail
                # confirmations, etc. injected by the mobile backend at /initialize time)
                if src == "app":
                    skipped_app += 1
                    continue

            formatted.append({
                "role": msg.get("role"),
                "content": msg.get("content") or "",
            })

        if skipped_external:
            logger.info(f"[HISTORY] Filtered {skipped_external} old-system assistant message(s) from LLM context")
        if skipped_app:
            logger.info(f"[HISTORY] Filtered {skipped_app} app-generated assistant message(s) from LLM context")

        logger.info(f"[HISTORY] {len(formatted)} message(s) passed to LLM (cap={max_messages}, total_in_redis={len(conversation_history)})")
        return formatted

    def _format_enhanced_analysis(
        self,
        enhanced: Dict,
        synthesis: Dict,
        query_type: str,
        chart_data: Optional[Dict] = None,
        dasha_data: Optional[Dict] = None,
        validation_result: Optional[Dict] = None,
        question_mode: Optional[str] = None,
    ) -> str:
        """
        Format enhanced analysis and synthesis for LLM consumption.

        This is the SECRET SAUCE — gives LLM pre-analyzed astrological factors
        instead of making it guess from raw positions.

        The FactorScorer prepends a ranked FOCUS FACTORS block so the LLM sees
        the 2-3 most relevant factors for THIS domain/question_mode/dasha context
        before the full detailed dump, steering its attention without removing
        the detailed section (which serves CoT and quality gates).
        """
        lines = ["ENHANCED CHART ANALYSIS:", ""]

        # ── FOCUS FACTORS block (injected at top) ──────────────────────
        if FACTOR_SCORER_AVAILABLE and synthesis:
            try:
                _domain = (
                    (validation_result or {}).get("intent_analysis", {}).get("domain")
                    or query_type
                    or "general"
                )
                _qmode = question_mode or (
                    (validation_result or {}).get("intent_analysis", {}).get("question_mode")
                    or "summary"
                )
                _plan = score_factors(
                    synthesis=synthesis,
                    validation_result=validation_result,
                    dasha_data=dasha_data,
                    domain=_domain,
                    question_mode=_qmode,
                )
                _focus = _plan.focus_block
                if _focus:
                    lines.append(_focus)
            except Exception as _e:
                logger.debug(f"[FACTOR_SCORER] focus block skipped: {_e}")
        
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

        # Vimshopaka Bala — varga-based overall planetary strength (0-20 scale, Saptavarga)
        # Higher score = planet's results are more reliable and amplified across all life areas.
        # Typical interpretation: 15-20 = very strong, 10-14 = moderate, 5-9 = weak, <5 = very weak.
        vimshopaka = (chart_data or {}).get('vimshopaka', {})
        if vimshopaka:
            lines.append("VIMSHOPAKA BALA (planetary strength across varga charts, 0-20 scale):")
            _planet_order = ['JUPITER', 'VENUS', 'MERCURY', 'MOON', 'SUN', 'SATURN', 'MARS', 'RAHU', 'KETU']
            for _p in _planet_order:
                _score = vimshopaka.get(_p) or vimshopaka.get(_p.capitalize())
                if _score is not None:
                    _label = "STRONG" if _score >= 15 else "MODERATE" if _score >= 10 else "WEAK" if _score >= 5 else "VERY WEAK"
                    lines.append(f"  • {_p:10} {_score:4.1f}/20  ({_label})")
            lines.append("  → Use these scores when discussing a planet's dasha: a planet with score ≥15 delivers strong, reliable results.")
            lines.append("")

        return "\n".join(lines)

    def _get_house_lords(self, chart_data: Dict) -> Dict[str, str]:
        """
        Computes and returns a dictionary of all 12 house lords.
        Returns: Dict mapping "H1", "H2"... to planet names e.g., {"H1": "MARS", "H7": "VENUS"}
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

        lagna_data = chart_data.get('lagna') or chart_data.get('ascendant', {})
        lagna_sign = _norm(lagna_data.get('sign') or lagna_data.get('rashi', ''))

        if not lagna_sign or lagna_sign not in _SIGNS:
            return {}

        lagna_idx = _SIGNS.index(lagna_sign)
        
        lords = {}
        for h in range(1, 13):
            house_sign = _SIGNS[(lagna_idx + h - 1) % 12]
            lord = _SIGN_LORDS.get(house_sign, '?')
            lords[f'H{h}'] = lord
            
        return lords

    def _compute_house_lords_block(self, chart_data: Dict) -> str:
        """
        Compute all 12 house lords deterministically from chart_data.

        This runs unconditionally — no dependency on ChartAnalyzer or
        ENHANCED_ANALYSIS_AVAILABLE. Uses only the lagna sign and planetary
        positions already present in chart_data.
        """
        lords_map = self._get_house_lords(chart_data)
        if not lords_map:
            return ""
            
        _SIGNS = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]
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
        lagna_idx = _SIGNS.index(lagna_sign)
        planets = chart_data.get('planets', {})

        lines = [
            "HOUSE LORDS (calculated from Lagna — use ONLY these values, never derive lords from your training knowledge):"
        ]
        for h in range(1, 13):
            house_sign = _SIGNS[(lagna_idx + h - 1) % 12]
            lord = lords_map.get(f'H{h}', '?')
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
        response_mode: str = "default",  # PROGRESSIVE DISCLOSURE: "initial" | "detailed" | "followup" | "default"
        astro_evidence: Optional[Dict] = None,
        voice_preferences: Optional[Dict] = None,
        validation_disclaimer: Optional[str] = None,
        prebuilt_factor_plan: Optional[Any] = None,
    ) -> str:
        # Build USER PREFERENCES block for prompt (long-term consultation style memory)
        user_preferences_block = ""
        if voice_preferences and isinstance(voice_preferences, dict):
            parts = []
            if voice_preferences.get("detail_level"):
                parts.append(f"• Detail: {voice_preferences['detail_level']} (brief / balanced / detailed)")
            if voice_preferences.get("remedy_preference"):
                parts.append(f"• Remedies: {voice_preferences['remedy_preference']} (include / avoid / neutral)")
            if voice_preferences.get("tone"):
                parts.append(f"• Tone: {voice_preferences['tone']} (cautious / balanced / encouraging)")
            if parts:
                user_preferences_block = (
                    "\nUSER PREFERENCES (honor when possible — e.g. 'As you prefer, I'll keep this practical and short.'):\n"
                    + "\n".join(parts)
                    + "\n"
                )

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

        # Normalize node naming so user-facing text uses Vedic names.
        # This prevents raw engine labels like MEAN_NODE/TRUE_NODE leaking into responses.
        def _canonical_planet_name(name: str) -> str:
            n = (name or "").strip().upper()
            if n in {"MEAN_NODE", "TRUE_NODE", "NORTH_NODE", "DRAGON_HEAD"}:
                return "RAHU"
            if n in {"SOUTH_NODE", "DESC_NODE", "DESCENDING_NODE", "DRAGON_TAIL"}:
                return "KETU"
            return n or "UNKNOWN"

        def _display_planet_name(name: str) -> str:
            c = _canonical_planet_name(name)
            pretty = {
                "SUN": "Sun", "MOON": "Moon", "MARS": "Mars", "MERCURY": "Mercury",
                "JUPITER": "Jupiter", "VENUS": "Venus", "SATURN": "Saturn",
                "RAHU": "Rahu", "KETU": "Ketu", "UNKNOWN": "Unknown",
            }
            return pretty.get(c, c.title())

        def _parse_iso_date(value: str):
            try:
                return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
            except Exception:
                return None

        def _month_year_label(value: str) -> str:
            d = _parse_iso_date(value)
            return d.strftime("%B %Y") if d else (value or "Unknown")

        def _clip_start_if_in_progress(start: str, end: str) -> str:
            """
            For in-progress windows, clip user-facing start to today so answers do not
            frame past starts as new future events.
            """
            s = _parse_iso_date(start)
            e = _parse_iso_date(end)
            t = _parse_iso_date(_today_str)
            if s and e and t and s < t <= e:
                return _today_str
            return start

        # ── STALE MAHADASHA CHECK ─────────────────────────────────────────────
        # If the cached Mahadasha end date is in the past, the entire dasha_data
        # is from the wrong MD period. Clear it so the orchestrator recalculates.
        _md_end = (dasha_data or {}).get('mahadasha', {}).get('end', '9999')
        if dasha_data and _md_end < _today_str:
            logger.info(f"[DASHA STALE] Mahadasha end ({_md_end}) is in the past — "
                  f"cache is from wrong MD period. Clearing dasha_data for recalc.")
            dasha_data = {}

        # Extract dasha info safely
        maha_planet = _display_planet_name(dasha_data.get('mahadasha', {}).get('planet', 'Unknown'))
        antar_planet = _display_planet_name(dasha_data.get('antardasha', {}).get('planet', 'Unknown'))
        praty_planet = _display_planet_name(dasha_data.get('pratyantardasha', {}).get('planet', 'Unknown'))
        _raw_sequence = dasha_data.get('dasha_sequence', "")
        md_start_disp = _month_year_label(
            _clip_start_if_in_progress(
                dasha_data.get('mahadasha', {}).get('start', 'Unknown'),
                dasha_data.get('mahadasha', {}).get('end', 'Unknown'),
            )
        )
        md_end_disp = _month_year_label(dasha_data.get('mahadasha', {}).get('end', 'Unknown'))
        ad_start_disp = _month_year_label(
            _clip_start_if_in_progress(
                dasha_data.get('antardasha', {}).get('start', 'Unknown'),
                dasha_data.get('antardasha', {}).get('end', 'Unknown'),
            )
        )
        ad_end_disp = _month_year_label(dasha_data.get('antardasha', {}).get('end', 'Unknown'))
        pd_start_disp = _month_year_label(
            _clip_start_if_in_progress(
                dasha_data.get('pratyantardasha', {}).get('start', 'Unknown'),
                dasha_data.get('pratyantardasha', {}).get('end', 'Unknown'),
            )
        )
        _pd_end_raw = dasha_data.get('pratyantardasha', {}).get('end', 'Unknown')
        pd_end_disp = _month_year_label(_pd_end_raw)

        # Defense-in-depth:
        # If an upstream bug still causes Step 2 to include a dasha end-date
        # that is already < TODAY, suppress month-year ranges entirely so the
        # model cannot leak past timelines in the final answer.
        _today_date_obj = _parse_iso_date(_today_str)

        def _is_end_in_past(end_raw: Any) -> bool:
            end_dt = _parse_iso_date(str(end_raw)) if end_raw is not None else None
            return bool(end_dt and _today_date_obj and end_dt < _today_date_obj)

        _md_end_raw = dasha_data.get('mahadasha', {}).get('end', 'Unknown')
        _ad_end_raw = dasha_data.get('antardasha', {}).get('end', 'Unknown')
        _md_ended = _is_end_in_past(_md_end_raw)
        _ad_ended = _is_end_in_past(_ad_end_raw)
        _pd_ended = _is_end_in_past(_pd_end_raw)

        if _md_ended or _ad_ended or _pd_ended:
            logger.info(
                f"[DASHA PROMPT SUPPRESS] md_ended={_md_ended} ad_ended={_ad_ended} pd_ended={_pd_ended} "
                f"(today={_today_str})."
            )

        md_range_disp = "(ended - date hidden)" if _md_ended else f"({md_start_disp} to {md_end_disp})"
        ad_range_disp = "(ended - date hidden)" if _ad_ended else f"({ad_start_disp} to {ad_end_disp})"

        # For INITIAL responses, hide all Pratyantardasha dates from Step 2.
        # Even "Mercury (Feb 2026 to ongoing)" gives GPT-4o enough to compute
        # that Venus starts April 2026. Show only the active planet name; direct
        # the LLM to Step 3.5 for permitted timing windows.
        if response_mode == "initial":
            _praty_step2_line = f"• Pratyantardasha: {praty_planet} (active — timing windows in Step 3.5 below)"
        else:
            if _pd_ended:
                _praty_step2_line = f"• Pratyantardasha: {praty_planet} (ended - date hidden)"
            else:
                _praty_step2_line = f"• Pratyantardasha: {praty_planet} ({pd_start_disp} to {pd_end_disp})"

        if _raw_sequence:
            _seq_parts = [_display_planet_name(p.strip()) for p in str(_raw_sequence).split("/") if p.strip()]
            dasha_sequence = "/".join(_seq_parts) if _seq_parts else f"{maha_planet}/{antar_planet}"
        else:
            dasha_sequence = f"{maha_planet}/{antar_planet}"
        
        # DEBUG: Print dasha data to verify it has dates
        logger.info(f"[DEBUG] Dasha data in prompt:")
        logger.debug(f"  Mahadasha: {maha_planet} ({dasha_data.get('mahadasha', {}).get('start', 'NO DATE')} to {dasha_data.get('mahadasha', {}).get('end', 'NO DATE')})")
        logger.debug(f"  Antardasha: {antar_planet} ({dasha_data.get('antardasha', {}).get('start', 'NO DATE')} to {dasha_data.get('antardasha', {}).get('end', 'NO DATE')})")
        calc_details = dasha_data.get('calculation_details', {})
        logger.debug(f"  Calculation details: Moon={calc_details.get('moon_longitude', 'MISSING')}, Nakshatra={calc_details.get('moon_nakshatra', 'MISSING')}")
        
        # Build upcoming antardashas timeline
        upcoming_ads = dasha_data.get('upcoming_antardashas', [])
        # Keep any antardasha that has NOT YET ENDED — this includes the currently
        # active one (started <= today but end > today) so the model can see the
        # full span of the ongoing period and plan timing correctly.
        upcoming_ads_filtered = [
            ad for ad in upcoming_ads
            if ad.get('end', '9999') > _today_str
        ]
        skipped_past_ads = len(upcoming_ads) - len(upcoming_ads_filtered)
        if skipped_past_ads > 0:
            logger.info(f"[DASHA FILTER] Removed {skipped_past_ads} fully-elapsed antardasha(s) from prompt (end <= today).")

        upcoming_ads_str = ""
        if upcoming_ads_filtered:
            upcoming_ads_str = "\nStep 3 - Upcoming Antardashas (for future timing):\n"
            for ad in upcoming_ads_filtered:
                ad_planet = _display_planet_name(ad.get('planet', 'Unknown'))
                ad_start = _month_year_label(ad.get('start', 'Unknown'))
                ad_end = _month_year_label(ad.get('end', 'Unknown'))
                upcoming_ads_str += f"• {ad_planet} ({ad_start} to {ad_end})\n"

        # Build upcoming pratyantardashas timeline (precise week/month level timing)
        upcoming_pds = dasha_data.get('upcoming_pratyantardashas', [])

        # REFACTORED: Centralized DOMAIN-SPECIFIC FILTERING
        # Keys here must match validation_result['query_type'] values (e.g. marriage, career, finance, health, children)
        DOMAIN_PLANETS = {
            # Relationship / marriage timing
            "marriage": {"planets": ["VENUS", "JUPITER"], "lords": ["H7"]},
            # Divorce / separation / strain periods in relationship
            "divorce": {"planets": ["SATURN", "MARS", "RAHU", "KETU"], "lords": ["H7", "H8", "H12"]},
            # Career / job / profession
            "career": {"planets": ["SATURN", "SUN", "MERCURY"], "lords": ["H10"]},
            # Finance / wealth / gains
            "finance": {"planets": ["VENUS", "JUPITER"], "lords": ["H2", "H11"]},
            "wealth": {"planets": ["VENUS", "JUPITER"], "lords": ["H2", "H11"]},
            # Children / fertility
            "children": {"planets": ["JUPITER", "MOON"], "lords": ["H5"]},
            # Health / disease
            "health": {"planets": ["SATURN", "MARS", "RAHU", "KETU"], "lords": ["H6", "H8"]},
            # Property / home
            "home": {"planets": ["MOON", "MARS"], "lords": ["H4"]},
            "property": {"planets": ["MOON", "MARS"], "lords": ["H4"]},
            # Foreign travel / settlement — RAHU primary, VENUS (journey desire) and MOON (displacement/movement) secondary
            "foreign": {"planets": ["RAHU", "VENUS", "MOON"], "lords": ["H9", "H12"]},
            "foreign_travel": {"planets": ["RAHU", "VENUS", "MOON"], "lords": ["H9", "H12"]},
        }
        
        query_type = validation_result.get('query_type', 'general') if validation_result else 'general'
        domain_info = DOMAIN_PLANETS.get(query_type)

        if domain_info:
            # Start with the core domain planets
            relevant_planets = list(domain_info["planets"])

            # Add the actual house lords for the domain houses (e.g. H7 for marriage, H10 for career)
            house_lords = self._get_house_lords(chart_data)
            lords_to_add = []
            for h in domain_info.get("lords", []):
                lord = house_lords.get(h)
                if lord:
                    lords_to_add.append(lord)

            if lords_to_add:
                relevant_planets.extend(lords_to_add)
                # De-duplicate while preserving upper-case planet names
                relevant_planets = list({p.upper() for p in relevant_planets})

                logger.info(f"[DASHA_FILTER] Query domain filtering for '{query_type}': relevant_planets={relevant_planets}")

                domain_filtered_pds = [
                    pd for pd in upcoming_pds
                    if _canonical_planet_name(pd.get('planet', '')) in relevant_planets
                ]

                # Minimum window diversity threshold — QA requires at least 4 distinct
                # pratyantar windows to produce a multi-phase timeline answer.
                _MIN_WINDOWS = 4

                if len(domain_filtered_pds) >= _MIN_WINDOWS:
                    logger.info(f"[DASHA_FILTER] Filtered {len(upcoming_pds) - len(domain_filtered_pds)} pratyantars based on query domain. {len(domain_filtered_pds)} domain-relevant windows kept.")
                    upcoming_pds = domain_filtered_pds
                elif len(domain_filtered_pds) > 0:
                    # Backfill with next chronological non-domain periods to reach _MIN_WINDOWS
                    existing_starts = {pd.get('start') for pd in domain_filtered_pds}
                    backfill = [
                        pd for pd in upcoming_pds
                        if pd.get('start') not in existing_starts
                    ]
                    # Sort backfill by start date ascending and take only what's needed
                    backfill.sort(key=lambda p: p.get('start', '9999'))
                    needed = _MIN_WINDOWS - len(domain_filtered_pds)
                    combined = domain_filtered_pds + backfill[:needed]
                    # Re-sort combined list by start date to preserve chronological order
                    combined.sort(key=lambda p: p.get('start', '9999'))
                    logger.info(
                        f"[DASHA_FILTER] Only {len(domain_filtered_pds)} domain-relevant pratyantar(s) for '{query_type}'. "
                        f"Backfilled {min(needed, len(backfill))} non-domain windows to reach {len(combined)} total for timeline diversity."
                    )
                    upcoming_pds = combined
                else:
                    logger.info(f"[DASHA_FILTER] No domain-relevant pratyantars found for '{query_type}', using all upcoming.")


        # ── CODE-LEVEL FUTURE-DATE FILTER ─────────────────────────────────────
        # Keep ONLY Pratyantar periods whose start date is strictly in the future.
        # We do NOT expose "in-progress" windows in the prompt; user-facing timing
        # must always refer to future periods.
        def _months_until_for_filter(start_iso: str) -> Optional[int]:
            s = _parse_iso_date(start_iso)
            t = _parse_iso_date(_today_str)
            if not s or not t:
                return None
            return max(0, (s.year - t.year) * 12 + (s.month - t.month))

        upcoming_pds_filtered = [
            pd for pd in upcoming_pds
            if (pd.get('start') or '9999') > _today_str
        ]
        # For INITIAL short responses, avoid ultra-near windows unless user explicitly asks urgent timing.
        _query_l = (query or "").lower()
        _is_urgent_timing = any(k in _query_l for k in ["immediately", "urgent", "abhi", "right now", "jaldi", "asap"])
        _min_lead_months_initial = 2
        if response_mode == "initial" and not _is_urgent_timing:
            _future_distinct = []
            for _pd in upcoming_pds_filtered:
                _lead = _months_until_for_filter(_pd.get("start"))
                if _lead is not None and _lead >= _min_lead_months_initial:
                    _future_distinct.append(_pd)
            # Only defer if at least 2 windows survive — otherwise the LLM
            # has no variety and the response cites a single timeline.
            if len(_future_distinct) >= 2:
                skipped_near = len(upcoming_pds_filtered) - len(_future_distinct)
                upcoming_pds_filtered = _future_distinct
                if skipped_near > 0:
                    logger.info(
                        f"[DASHA FILTER] Deferred {skipped_near} immediate pratyantar window(s) "
                        f"(lead < {_min_lead_months_initial} months) for INITIAL response diversity."
                    )
            elif _future_distinct:
                # Only 1 distant window — keep 1 nearest non-deferred to give LLM 2 options
                _nearest_non_deferred = [
                    pd for pd in upcoming_pds_filtered if pd not in _future_distinct
                ]
                _nearest_non_deferred.sort(key=lambda p: p.get("start", "9999"))
                upcoming_pds_filtered = _future_distinct + _nearest_non_deferred[:1]
                logger.info(
                    f"[DASHA FILTER] Kept 1 near-term window (would have deferred) "
                    f"to ensure at least 2 options for INITIAL."
                )
        skipped_past_pds = len(upcoming_pds) - len(upcoming_pds_filtered)
        if skipped_past_pds > 0:
            logger.info(f"[DASHA FILTER] Removed {skipped_past_pds} non-future pratyantar(s) from prompt "
                  f"(start <= {_today_str}). Only {len(upcoming_pds_filtered)} period(s) remain.")

        upcoming_pds_str = ""
        if upcoming_pds_filtered:
            upcoming_pds_str = f"\nStep 3.5 - Pratyantardashas within current Antardasha (TODAY = {_today_str}):\n"
            upcoming_pds_str += "  ⚠ ONLY use windows listed here for timing. DO NOT compute sub-windows yourself.\n"
            for pd in upcoming_pds_filtered:
                raw_start = pd.get('start', 'Unknown')
                end_date = pd.get('end', 'Unknown')
                display_start = _month_year_label(raw_start)
                display_end = _month_year_label(end_date)
                pd_planet = _display_planet_name(pd.get('planet', 'Unknown'))
                upcoming_pds_str += (
                    f"• {pd_planet:10} "
                    f"{display_start} → {display_end} "
                    f"({pd.get('duration_days', '?')} days)\n"
                )
        elif upcoming_pds:
            # All pratyantardashas in current AD have passed — tell LLM explicitly
            upcoming_pds_str = (
                f"\nStep 3.5 - Pratyantardashas (TODAY = {_today_str}):\n"
                "  ⚠ ALL pratyantardashas in the current Antardasha have already passed.\n"
                "  Use the NEXT Antardasha's opening Pratyantar for timing (see Step 3.6 below).\n"
            )
        logger.info(f"[DEBUG] upcoming_pratyantardashas: {len(upcoming_pds)} total, "
              f"{len(upcoming_pds_filtered)} after past-date filter")
        for _pd in upcoming_pds_filtered:
            logger.debug(f"  Pratyantar: {_pd.get('planet'):10} {_pd.get('start')} -> {_pd.get('end')} [{_pd.get('status')}]")

        # ── SOOKSHMA DASHA (4th-level sub-periods for precise timing) ───────────
        # Only inject for DETAILED/FOLLOWUP phases. For INITIAL responses, sookshma
        # near-term windows (days-to-weeks) confuse the LLM into mixing current Mercury
        # pratyantar sub-windows with the upcoming domain-relevant pratyantar dates.
        sookshma_str = ""
        if response_mode not in ('initial', 'default'):
            try:
                from src.engines.vedic.dasha_systems import compute_sookshmadashas, DashaPeriod as _DP
                from datetime import datetime as _dt_cls

                # Find the current active pratyantar (started ≤ today, ends > today)
                # or the first upcoming one if none is currently active.
                _active_pd_raw = None
                _all_pds_raw = upcoming_pds  # before future-date filter
                for _raw_pd in _all_pds_raw:
                    _s = _raw_pd.get('start', '9999')
                    _e = _raw_pd.get('end', '9999')
                    if _s <= _today_str <= _e:
                        _active_pd_raw = _raw_pd
                        break
                if _active_pd_raw is None and upcoming_pds_filtered:
                    _active_pd_raw = upcoming_pds_filtered[0]

                if _active_pd_raw:
                    # Reconstruct a minimal DashaPeriod-compatible object
                    from src.engines.core.celestial_bodies import CelestialBody as _CB

                    def _pd_name_to_body(name: str) -> Optional[_CB]:
                        for body in _CB:
                            if body.name == name.upper():
                                return body
                        return None

                    _pd_lord_body = _pd_name_to_body(_active_pd_raw.get('planet', ''))
                    _pd_start_raw = _parse_iso_date(_active_pd_raw.get('start', _today_str))
                    _pd_end_raw = _parse_iso_date(_active_pd_raw.get('end', _today_str))
                    # DashaPeriod requires datetime, not date
                    from datetime import time as _time_cls
                    _pd_start_dt = datetime.combine(_pd_start_raw, _time_cls.min) if _pd_start_raw else None
                    _pd_end_dt = datetime.combine(_pd_end_raw, _time_cls.min) if _pd_end_raw else None

                    if _pd_lord_body and _pd_start_dt and _pd_end_dt:
                        _duration_days = (_pd_end_dt - _pd_start_dt).days
                        _duration_years = _duration_days / 365.25

                        _mock_pd = _DP(
                            lord=_pd_lord_body,
                            start_date=_pd_start_dt,
                            end_date=_pd_end_dt,
                            duration_years=_duration_years,
                            level="pratyantardasha",
                            parent_lord=None,
                        )
                        _sookshmas = compute_sookshmadashas(_mock_pd)

                        # Filter to future sookshmas only, show next 5
                        _today_dt = _parse_iso_date(_today_str)  # returns date object
                        _future_sookshmas = [
                            s for s in _sookshmas
                            if (s.end_date.date() if hasattr(s.end_date, 'date') else s.end_date) > _today_dt
                        ][:5]

                        if _future_sookshmas:
                            _pd_display = _display_planet_name(_active_pd_raw.get('planet', ''))
                            sookshma_str = (
                                f"\nStep 3.4 - Sookshma Dasha within {_pd_display} Pratyantar "
                                f"(precise sub-windows, use for very specific event timing):\n"
                            )
                            for _s in _future_sookshmas:
                                _s_start = _s.start_date.strftime("%b %Y")
                                _s_end = _s.end_date.strftime("%b %Y")
                                _s_days = (_s.end_date - _s.start_date).days
                                _s_planet = _display_planet_name(_s.lord.name)
                                sookshma_str += (
                                    f"  • {_s_planet:10} {_s_start} → {_s_end}  ({_s_days} days)\n"
                                )
                            sookshma_str += (
                                "  → When the pratyantar aligns with a favorable sookshma lord, "
                                "that 2-4 week window is the sharpest activation point.\n"
                            )
                            logger.info(f"[SOOKSHMA] Added {len(_future_sookshmas)} sookshma windows for {_pd_display} pratyantar")
            except Exception as _sk_err:
                logger.debug(f"[SOOKSHMA] Skipped sookshma computation: {_sk_err}")

        # ── BROAD SUPPORTIVE WINDOW (for longer, but accurate timeframes) ───────
        # Compute a mathematically correct broader window summarizing when the
        # topic-relevant Dasha energy is active, clipped to today → end.
        broader_window_str = ""
        if upcoming_pds_filtered:
            first_pd = upcoming_pds_filtered[0]
            last_pd = upcoming_pds_filtered[-1]
            bw_start_raw = first_pd.get('start', _today_str)
            bw_end_raw = last_pd.get('end', _today_str)
            if bw_end_raw and bw_end_raw >= _today_str:
                bw_start = _today_str if bw_start_raw and bw_start_raw < _today_str else bw_start_raw
                bw_start_disp = _month_year_label(bw_start)
                bw_end_disp = _month_year_label(bw_end_raw)
                broader_window_str = (
                    "\nStep 3.7 - Broader Supportive Phase (for narrative timing):\n"
                    f"  • Topic-relevant Pratyantar sequence spans {bw_start_disp} → {bw_end_disp}.\n"
                    "  Use this ONLY as a broad phase description (e.g., 'overall supportive phase'),\n"
                    "  and still mention at least one exact Pratyantar window from Step 3.5."
                )

        # First pratyantar of each upcoming Antardasha (cross-level convergence)
        next_ad_fp = dasha_data.get('next_antardasha_first_pratyantar', [])
        _next_ad_fp_for_candidates = list(next_ad_fp)
        next_ad_fp_str = ""
        if next_ad_fp:
            next_ad_fp_str = "\nStep 3.6 - Opening Pratyantar of Next Antardashas (convergence windows):\n"
            _next_ad_entries = list(next_ad_fp)
            if response_mode == "initial" and not _is_urgent_timing:
                _filtered_next_ad = []
                for entry in _next_ad_entries:
                    _lead = _months_until_for_filter(entry.get("first_pratyantar_start"))
                    if _lead is not None and _lead >= _min_lead_months_initial:
                        _filtered_next_ad.append(entry)
                if _filtered_next_ad:
                    _next_ad_entries = _filtered_next_ad
                    _next_ad_fp_for_candidates = _filtered_next_ad
            for entry in _next_ad_entries:
                ad_planet = _display_planet_name(entry.get('antardasha_planet'))
                fp_planet = _display_planet_name(entry.get('first_pratyantar_planet'))
                ad_start_disp = _month_year_label(entry.get('antardasha_start'))
                fp_start_disp = _month_year_label(entry.get('first_pratyantar_start'))
                fp_end_disp = _month_year_label(entry.get('first_pratyantar_end'))
                next_ad_fp_str += (
                    f"• When {ad_planet} AD starts ({ad_start_disp}): "
                    f"first Pratyantar = {fp_planet} "
                    f"({fp_start_disp} to {fp_end_disp})\n"
                )

        # Ranked candidate windows to avoid repetitive "immediate-next" timing across domains.
        # We score windows by domain relevance + practical lead time, then expose top options.
        def _months_until(start_iso: str) -> Optional[int]:
            s = _parse_iso_date(start_iso)
            t = _parse_iso_date(_today_str)
            if not s or not t:
                return None
            return max(0, (s.year - t.year) * 12 + (s.month - t.month))

        _query_l = (query or "").lower()
        _is_urgent_timing = any(k in _query_l for k in ["immediately", "urgent", "abhi", "right now", "jaldi", "asap"])
        _domain_target_months = {
            "career": 3,
            "finance": 3,
            "health": 1,
            "marriage": 6,
            "children": 7,
            "foreign": 5,
            "foreign_travel": 5,
            "home": 8,
            "property": 8,
            "general": 4,
        }
        _target_m = _domain_target_months.get(query_type, 4)
        _initial_duration_preference_map = {
            "career": [("medium", "long"), ("long", "medium"), ("medium", "short")],
            "finance": [("medium", "long"), ("long", "medium"), ("medium", "short")],
            "health": [("short", "medium"), ("medium", "short"), ("medium", "long")],
            "marriage": [("long", "medium"), ("medium", "long"), ("medium", "short")],
            "children": [("long", "medium"), ("medium", "long"), ("medium", "short")],
            "foreign": [("medium", "long"), ("long", "medium"), ("medium", "short")],
            "foreign_travel": [("medium", "long"), ("long", "medium"), ("medium", "short")],
            "home": [("long", "medium"), ("medium", "long"), ("medium", "short")],
            "property": [("long", "medium"), ("medium", "long"), ("medium", "short")],
            "general": [("medium", "long"), ("long", "medium"), ("medium", "short")],
        }
        _preferred_duration_primary = "medium"
        _preferred_duration_secondary = "long"
        if response_mode == "initial":
            _dur_prefs = _initial_duration_preference_map.get(query_type, _initial_duration_preference_map["general"])
            _orig_for_seed = query or ""
            _history_hint = len(conversation_history or [])
            _dur_rng = random.Random(f"{query_type}|{_orig_for_seed}|h{_history_hint}|duration")
            _preferred_duration_primary, _preferred_duration_secondary = _dur_prefs[_dur_rng.randrange(len(_dur_prefs))]

        # Session-aware anti-repetition: avoid repeating identical month-ranges
        # across different topics unless the dasha data leaves no meaningful alternative.
        def _infer_topic_from_text(text: str) -> str:
            q = (text or "").lower()
            if any(w in q for w in ["marriage", "marry", "shadi", "shaadi", "vivah", "wedding", "partner", "spouse", "relationship", "rishta"]):
                return "marriage"
            if any(w in q for w in ["career", "job", "naukri", "profession", "business", "promotion", "salary", "interview"]):
                return "career"
            if any(w in q for w in ["finance", "money", "wealth", "gold", "invest", "investment", "paisa", "dhan", "arthik"]):
                return "finance"
            if any(w in q for w in ["health", "sehat", "swasthya", "illness", "disease", "bimari"]):
                return "health"
            if any(w in q for w in ["children", "child", "santaan", "bacche", "fertility"]):
                return "children"
            if any(w in q for w in ["property", "ghar", "home", "house", "flat", "plot", "real estate", "zameen", "land"]):
                return "property"
            if any(w in q for w in ["foreign", "abroad", "videsh", "travel", "visa", "immigration", "overseas"]):
                return "foreign"
            return "general"

        _month_map = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        _range_re = re.compile(
            r"(?i)\b("
            r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
            r")\s+((?:19|20)\d{2})\b"
            r"\s*(?:to|until|till|se|tak|→|-|–|—)\s*"
            r"\b("
            r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
            r")\s+((?:19|20)\d{2})\b"
        )

        def _extract_range_keys(text: str) -> set[str]:
            keys: set[str] = set()
            for m in _range_re.finditer(text or ""):
                sm, sy = m.group(1), int(m.group(2))
                em, ey = m.group(3), int(m.group(4))
                s_m = _month_map.get((sm or "").lower(), 1)
                e_m = _month_map.get((em or "").lower(), 12)
                start_key = f"{sy:04d}-{s_m:02d}"
                end_key = f"{ey:04d}-{e_m:02d}"
                if end_key < start_key:
                    start_key, end_key = end_key, start_key
                keys.add(f"{start_key}|{end_key}")
            return keys

        def _candidate_key(start_iso: str, end_iso: str) -> str:
            s = _parse_iso_date(start_iso)
            e = _parse_iso_date(end_iso)
            if not s or not e:
                return ""
            start_key = f"{s.year:04d}-{s.month:02d}"
            end_key = f"{e.year:04d}-{e.month:02d}"
            if end_key < start_key:
                start_key, end_key = end_key, start_key
            return f"{start_key}|{end_key}"

        def _duration_months(start_iso: str, end_iso: str) -> Optional[int]:
            s = _parse_iso_date(start_iso)
            e = _parse_iso_date(end_iso)
            if not s or not e:
                return None
            return max(1, (e.year - s.year) * 12 + (e.month - s.month) + 1)

        def _duration_band(months: Optional[int]) -> str:
            if months is None:
                return "unknown"
            if months <= 4:
                return "short"
            if months <= 10:
                return "medium"
            return "long"

        _recent_cross_topic_window_keys: set[str] = set()
        _recent_cross_topic_years: set[int] = set()
        _recent_cross_topic_start_months: set[str] = set()  # "YYYY-MM" start month keys
        _recent_cross_topic_samples: List[str] = []
        if conversation_history:
            # Scan latest assistant replies and map each to its preceding user query topic.
            _assistant_seen = 0
            for idx in range(len(conversation_history) - 1, -1, -1):
                msg = conversation_history[idx] or {}
                if (msg.get("role") or "").lower() != "assistant":
                    continue
                _assistant_seen += 1
                if _assistant_seen > 8:
                    break
                _assistant_text = msg.get("content") or ""
                _preceding_user = ""
                for j in range(idx - 1, -1, -1):
                    _m2 = conversation_history[j] or {}
                    if (_m2.get("role") or "").lower() == "user":
                        _preceding_user = _m2.get("content") or ""
                        break
                _msg_topic = _infer_topic_from_text(_preceding_user)
                # Fallback: if user text is ambiguous ("Yes, go ahead"),
                # infer topic from the assistant response itself.
                if _msg_topic == "general":
                    _msg_topic = _infer_topic_from_text(_assistant_text)
                if _msg_topic in ("general", query_type):
                    continue
                _keys = _extract_range_keys(_assistant_text)
                if not _keys:
                    continue
                _recent_cross_topic_window_keys.update(_keys)
                for _k in _keys:
                    _start_token = _k.split("|")[0]  # "YYYY-MM"
                    _year_token = _start_token.split("-")[0]
                    if _year_token.isdigit():
                        _recent_cross_topic_years.add(int(_year_token))
                    _recent_cross_topic_start_months.add(_start_token)
                if len(_recent_cross_topic_samples) < 3:
                    _recent_cross_topic_samples.extend(list(_keys)[: (3 - len(_recent_cross_topic_samples))])

        if _recent_cross_topic_window_keys:
            logger.info(
                f"[TIMELINE_NOVELTY] Found {len(_recent_cross_topic_window_keys)} recent cross-topic window(s) "
                f"to avoid reusing for query_type={query_type}. Samples={_recent_cross_topic_samples}"
            )

        _priority_planets = [p.upper() for p in (domain_info or {}).get("planets", [])]
        if domain_info and (domain_info.get("lords") or []):
            _house_lords = self._get_house_lords(chart_data)
            for _h in domain_info.get("lords", []):
                _lp = (_house_lords.get(_h) or "").upper()
                if _lp and _lp not in _priority_planets:
                    _priority_planets.append(_lp)

        _candidates: List[Dict[str, Any]] = []
        for _pd in upcoming_pds_filtered:
            _candidates.append(
                {
                    "planet": _canonical_planet_name(_pd.get("planet", "")),
                    "start": _pd.get("start"),
                    "end": _pd.get("end"),
                    "source": "current_ad_pratyantar",
                }
            )
        for _entry in _next_ad_fp_for_candidates:
            _candidates.append(
                {
                    "planet": _canonical_planet_name(_entry.get("first_pratyantar_planet", "")),
                    "start": _entry.get("first_pratyantar_start"),
                    "end": _entry.get("first_pratyantar_end"),
                    "source": "next_ad_opening_pratyantar",
                }
            )
        for _ad in upcoming_ads_filtered:
            _candidates.append(
                {
                    "planet": _canonical_planet_name(_ad.get("planet", "")),
                    "start": _ad.get("start"),
                    "end": _ad.get("end"),
                    "source": "antardasha_window",
                }
            )

        _scored_candidates: List[Dict[str, Any]] = []
        for _c in _candidates:
            _lead = _months_until(_c.get("start"))
            if _lead is None:
                continue
            if response_mode == "initial" and not _is_urgent_timing and _lead < _min_lead_months_initial:
                continue
            _dur_m = _duration_months(_c.get("start"), _c.get("end"))
            _dur_band = _duration_band(_dur_m)
            _score = 0.0

            # Domain relevance first
            if _priority_planets and _c["planet"] in _priority_planets:
                _rank = _priority_planets.index(_c["planet"])
                _score += max(1.0, 9.0 - (2.0 * _rank))
            elif _priority_planets:
                _score -= 2.0

            # Practical lead-time preference to avoid same immediate window everywhere
            _score += max(0.0, 8.0 - abs(float(_lead - _target_m)))
            if not _is_urgent_timing and _lead == 0:
                _score -= 3.0
            if response_mode == "initial" and _lead > 18:
                _score -= 1.0
            if response_mode == "detailed" and _lead >= 9:
                _score += 1.5
            if response_mode == "initial":
                if _dur_band == _preferred_duration_primary:
                    _score += 2.2
                elif _dur_band == _preferred_duration_secondary:
                    _score += 1.3
                elif _dur_band == "short":
                    _score -= 0.8
            if _c.get("source") == "antardasha_window" and response_mode == "initial":
                _score += 1.1

            # Novelty guard: penalize reuse of a recent cross-topic range or start month.
            _ckey = _candidate_key(_c.get("start"), _c.get("end"))
            _is_reused = bool(_ckey and _ckey in _recent_cross_topic_window_keys)
            _c_start_dt = _parse_iso_date(_c.get("start"))
            _c_start_month = (
                f"{_c_start_dt.year:04d}-{_c_start_dt.month:02d}" if _c_start_dt else ""
            )
            _is_same_start_month = bool(
                _c_start_month and _c_start_month in _recent_cross_topic_start_months
            )
            if _is_reused:
                _score -= 4.5
            elif _is_same_start_month:
                # Different end date but same start month as a cross-topic window — still feels
                # repetitive to the user ("April 2026" appeared in marriage, now in foreign).
                _score -= 3.0
            else:
                if _c_start_dt and _c_start_dt.year not in _recent_cross_topic_years:
                    _score += 0.8

            _c["lead_months"] = _lead
            _c["duration_months"] = _dur_m
            _c["duration_band"] = _dur_band
            _c["range_key"] = _ckey
            _c["reused_recent_cross_topic_window"] = _is_reused or _is_same_start_month
            _c["score"] = round(_score, 2)
            _scored_candidates.append(_c)

        _scored_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        _deduped: List[Dict[str, Any]] = []
        _seen = set()
        for _c in _scored_candidates:
            _k = (_c.get("planet"), _c.get("start"), _c.get("end"))
            if _k in _seen:
                continue
            _seen.add(_k)
            _start_dt = _parse_iso_date(_c.get("start"))
            _c["start_month_index"] = (_start_dt.year * 12 + _start_dt.month) if _start_dt else None
            _deduped.append(_c)

        _ranked_unique: List[Dict[str, Any]] = []
        if response_mode == "initial" and not _is_urgent_timing:
            _selected: List[Dict[str, Any]] = []

            def _passes_diversity_strict(_cand: Dict[str, Any]) -> bool:
                if not _selected:
                    return True
                _cb = _cand.get("duration_band")
                _cs = _cand.get("start_month_index")
                _band_new = all(_cb != s.get("duration_band") for s in _selected)
                _start_spaced = all(
                    (_cs is None or s.get("start_month_index") is None or abs(_cs - s.get("start_month_index")) >= 3)
                    for s in _selected
                )
                return _band_new and _start_spaced

            def _passes_diversity_relaxed(_cand: Dict[str, Any]) -> bool:
                if not _selected:
                    return True
                _cb = _cand.get("duration_band")
                _cs = _cand.get("start_month_index")
                _band_new = all(_cb != s.get("duration_band") for s in _selected)
                _start_spaced = any(
                    (_cs is not None and s.get("start_month_index") is not None and abs(_cs - s.get("start_month_index")) >= 3)
                    for s in _selected
                )
                return _band_new or _start_spaced

            for _rule in (_passes_diversity_strict, _passes_diversity_relaxed):
                for _cand in _deduped:
                    if _cand in _selected:
                        continue
                    if _rule(_cand):
                        _selected.append(_cand)
                    if len(_selected) >= 4:
                        break
                if len(_selected) >= 4:
                    break

            for _cand in _deduped:
                if _cand in _selected:
                    continue
                _selected.append(_cand)
                if len(_selected) >= 4:
                    break

            _ranked_unique = _selected
        else:
            _ranked_unique = _deduped[:4]

        ranked_windows_str = ""
        if _ranked_unique:
            ranked_windows_str = "\nStep 3.8 - Ranked Topic-Relevant Timing Candidates (use this order):\n"
            for _i, _c in enumerate(_ranked_unique, start=1):
                _pname = _display_planet_name(_c.get("planet"))
                _start_disp = _month_year_label(_c.get("start"))
                _end_disp = _month_year_label(_c.get("end"))
                _src = {
                    "current_ad_pratyantar": "current AD window",
                    "next_ad_opening_pratyantar": "next AD opening window",
                    "antardasha_window": "upcoming antardasha window",
                }.get(_c.get("source"), "timing window")
                ranked_windows_str += (
                    f"• Rank {_i}: {_pname} ({_start_disp} to {_end_disp}) | "
                    f"lead ~{_c.get('lead_months')} months | duration ~{_c.get('duration_months')} months ({_c.get('duration_band')}) | source: {_src}"
                    f"{' | note: reused recent cross-topic window' if _c.get('reused_recent_cross_topic_window') else ''}\n"
                )
            ranked_windows_str += (
                "  Use Rank 1 as the primary favorable period unless the user explicitly asks for only immediate timing.\n"
                "  Also mention a secondary period from the remaining ranks for timeline variety when relevant.\n"
                "  In INITIAL short answers, ensure primary and secondary windows differ in duration profile (short/medium/long) and are not near-identical start timing when alternatives exist.\n"
                "  Prefer a rank that is not marked as a reused cross-topic window when two choices are astrologically comparable.\n"
            )
            # Explicitly name months the LLM must avoid (already appeared in a different topic answer).
            # The LLM can infer these months from Step 2 dasha data — we must tell it explicitly NOT to use them.
            if _recent_cross_topic_start_months:
                _avoid_labels = sorted(
                    {_month_year_label(f"{ym}-01") for ym in _recent_cross_topic_start_months}
                )
                ranked_windows_str += (
                    f"  ⚠ AVOID THESE START MONTHS (already cited for a different topic this session): "
                    f"{', '.join(_avoid_labels)}. "
                    "Even if these months appear in Step 2/3.5 dasha data, DO NOT use them as the primary timing window for this answer — pick a later ranked window instead.\n"
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
            logger.info(f"[GOCHARA] Computation error: {_ge}")
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

        # ── Vimshopaka Bala ───────────────────────────────────────────────────
        vimshopaka_str = ""
        vimshopaka = chart_data.get('vimshopaka', {})
        if vimshopaka:
            _PLANET_ORDER = ['SUN', 'MOON', 'MARS', 'MERCURY', 'JUPITER', 'VENUS', 'SATURN', 'RAHU', 'KETU']
            _strength_labels = {
                (15, 20): "very strong",
                (11, 15): "strong",
                (7,  11): "moderate",
                (3,   7): "weak",
                (0,   3): "very weak",
            }
            def _vim_label(score):
                for (lo, hi), label in _strength_labels.items():
                    if lo <= score < hi:
                        return label
                return "very strong" if score >= 20 else "very weak"

            vim_lines = []
            for p in _PLANET_ORDER:
                if p in vimshopaka:
                    score = vimshopaka[p]
                    vim_lines.append(f"  {p:8}: {score:4.1f}/20  ({_vim_label(score)})")
            if vim_lines:
                vimshopaka_str = (
                    "\nVIMSHOPAKA BALA — Varga Strength (Saptavarga scheme, 0–20 scale):\n"
                    "  Interpretation: ≥15 very strong | 11–14 strong | 7–10 moderate | <7 weak\n"
                    + "\n".join(vim_lines)
                    + "\n  Use this as a SECONDARY strength modifier alongside dignity. "
                    "A planet exalted in D1 but weak in vargas may give mixed/delayed results. "
                    "A planet in own sign with high Vimshopaka (≥14) is reliably potent."
                )

        # ── Planetary Wars (Graha Yuddha) ─────────────────────────────────────
        planetary_wars_str = ""
        planetary_wars = chart_data.get('planetary_wars', [])
        if planetary_wars:
            war_lines = []
            for w in planetary_wars:
                war_lines.append(
                    f"  ⚔ {w['planet1']} vs {w['planet2']}  "
                    f"(separation: {w['separation_degrees']}°) — "
                    f"WINNER: {w['winner']}, LOSER: {w['loser']}"
                )
            planetary_wars_str = (
                "\nGRAHA YUDDHA — PLANETARY WARS (within 1° separation):\n"
                + "\n".join(war_lines)
                + "\n  Classical rule: the LOSER planet's significations are severely weakened "
                "(similar to debilitation). During the loser's Dasha/Antardasha, "
                "its significations will underperform even if dignified in D1. "
                "The WINNER's significations are proportionally amplified."
            )

        # ── House Occupancy Summary ───────────────────────────────────────────
        house_occupancy_str = ""
        house_occupancy = chart_data.get('house_occupancy', {})
        if house_occupancy:
            occupied = []
            for h in range(1, 13):
                planets_in_house = house_occupancy.get(str(h), [])
                if planets_in_house:
                    occupied.append(f"  H{h:2d}: {', '.join(planets_in_house)}")
            empty_houses = [
                str(h) for h in range(1, 13)
                if not house_occupancy.get(str(h))
            ]
            if occupied:
                house_occupancy_str = (
                    "\nHOUSE OCCUPANCY (planets in each natal house):\n"
                    + "\n".join(occupied)
                    + (f"\n  Empty houses: {', '.join(empty_houses)}" if empty_houses else "")
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

        # ── Hard timing & anti-hallucination rule injected into system prompt ─
        # Placed here (system prompt level) so the LLM reliably follows it
        # regardless of where it appears in the user context.
        _ref_date = _today_str  # reuse _today_str already defined above
        _has_core_dasha = bool(dasha_data.get('upcoming_pratyantardashas') or dasha_data.get('upcoming_antardashas'))
        _has_transit = bool(transit_data)
        system_prompt += (
            f"\n\nCRITICAL TIMING RULE: Today's date is {_ref_date}. "
            "NEVER predict or cite any date range that ended before today. "
            "You MUST also avoid using 'in-progress' periods as user-facing timing anchors — "
            "only Pratyantar and Antardasha windows whose START date is strictly in the FUTURE (after today) "
            "may be used as the mathematical basis for timing. "
            "For INITIAL short answers (unless user explicitly asks for immediate timing), avoid ultra-near windows; "
            "prefer anchors that begin at least ~2 months ahead. "
            "In ALL user-facing answers, do NOT mention exact calendar days (no DD/MM or specific dates). "
            "Express timing only as approximate windows such as 'between Aug 2027 and early 2028', "
            "'in the second half of 2026', or 'across most of 2030', and when helpful say month names with years such as 'from March 2027 to October 2027'. "
            "Within the SAME conversation session, avoid repeating the exact same timing phrase for different NEW_TOPIC questions — you may point to overlapping or identical mathematical windows, but vary your wording naturally (e.g., 'around mid 2026' vs 'from June to August 2026') so the answers do not sound robotic. "
            "NEVER compute or invent sub-windows or planetary positions from your training knowledge — "
            "use ONLY the Pratyantar, Antardasha, and transit dates explicitly listed in the prompt as the mathematical basis. "
            "If any of these calculation blocks are missing or look incomplete, clearly say that you do NOT have enough data for an exact timing prediction and give only high-level, non-date-specific guidance instead."
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
            logger.info(f"[GREETING] App-provided initial greeting detected (no user turns yet)")

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
                logger.info(f"[VALIDATION] Error formatting validation: {e}")
        # Append disclaimer hint so LLM can weave uncertainty naturally into prose
        _vdisc = validation_disclaimer or ''
        if _vdisc:
            validation_context = (validation_context + "\n\n" + _vdisc).strip()

        divisional_context = ""
        if validation_result:
            query_type = validation_result.get('query_type', 'general')
            try:
                # Pass the original user query so the helper can smartly switch
                # to property/education/etc. use-cases and pull the right D-charts
                # (D1, D2, D4, D7, D9, D10, D24, etc.) for the current topic.
                divisional_context = get_divisional_chart_context(
                    query_type=query_type,
                    chart_data=chart_data,
                    include_secondary=True,
                    verbose=True,
                    original_query=query,
                )
                logger.info(f"[DIVISIONAL] context_length={len(divisional_context)} chars for query_type={query_type}")
            except Exception as e:
                logger.error(f"[DIVISIONAL] Error adding divisional chart context: {e}", exc_info=True)

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

        # Use dynamic instruction builder — adapts to query content (timing, career, etc) and verbosity.
        # LLM-classified intent/domain/polarity are passed in via validation_result when available.
        _ia = (validation_result or {}).get('intent_analysis', {}) if validation_result else {}
        analysis_only_mode = is_analysis_only_request(query, _ia.get('question_mode'))

        # ── DETERMINISTIC ANSWER PLAN ──────────────────────────────────────────
        # Build once, inject into reasoning scratchpad so the LLM works within
        # a committed plan rather than improvising structure from raw data.
        _answer_plan = None
        if ANSWER_PLANNER_AVAILABLE and synthesis:
            try:
                # Reuse the FactorPlan pre-built before retrieval (Step 1.5) when available.
                # Falling back to a fresh score_factors() call only when not provided
                # (e.g. tests, direct calls to this method).
                _fp_for_plan = prebuilt_factor_plan
                if _fp_for_plan is None and FACTOR_SCORER_AVAILABLE:
                    _fp_for_plan = score_factors(
                        synthesis=synthesis,
                        validation_result=validation_result,
                        dasha_data=dasha_data,
                        domain=_ia.get('domain') or 'general',
                        question_mode=_ia.get('question_mode') or 'summary',
                    )
                if _fp_for_plan is not None:
                    _answer_plan = build_answer_plan(
                        factor_plan=_fp_for_plan,
                        astro_evidence=astro_evidence,
                        synthesis=synthesis,
                        validation_result=validation_result,
                        intent_analysis=_ia,
                    )
            except Exception as _ap_err:
                logger.debug(f"[ANSWER_PLANNER] skipped: {_ap_err}")
        instructions = self._build_response_instructions(
            query=query,
            lang_name=lang_name,
            script_instruction=script_instruction,
            mode='prediction',
            response_mode=response_mode,
            intent_domain=_ia.get('domain'),
            question_mode=_ia.get('question_mode'),
            polarity=_ia.get('polarity'),
        )
        # Keep answers grounded in structured analysis first (validation + synthesis),
        # then use raw chart details only as supporting evidence.
        analysis_priority_instruction = """

ANALYSIS PRIORITY (MANDATORY):
- Use VALIDATION RESULT and ENHANCED CHART ANALYSIS as the primary reasoning source whenever they are present.
- Anchor your narrative first on: overall strength, can_proceed, critical_failures, chart strengths/challenges, key houses, and detected yogas.
- Use raw planetary rows/dasha tables as supporting evidence, not as the primary source of truth.
- If a claim is not supported by structured analysis or computed data in this prompt, do NOT assert it.
"""
        instructions += analysis_priority_instruction

        if response_mode == 'detailed' or self._user_wants_detail(query):
            instructions += (
                "\nDETAILED-ANALYSIS REQUEST:\n"
                "- The user asked for detailed/full analysis.\n"
                "- You MUST explicitly use all relevant analysis sections: key houses, yogas, chart strengths, chart challenges, and validation outcomes.\n"
                "- Keep the answer clearly analytical and evidence-linked (factor -> implication -> practical meaning).\n"
            )

        if analysis_only_mode:
            instructions += (
                "\nANALYSIS-ONLY MODE (NO PRIMARY TIMING FOCUS):\n"
                "- The user is asking for analysis, not event timing.\n"
                "- Focus mainly on strengths, challenges, key houses, yogas, and overall chart readiness.\n"
                "- Mention timing only briefly as secondary context if needed; avoid date-heavy windows unless explicitly requested.\n"
            )

        if validation_result:
            _strength = float(validation_result.get('overall_strength', 10.0))
            _critical = validation_result.get('critical_failures', []) or []
            if _strength < 6.0 or _critical:
                instructions += (
                    "\nWEAK-CHART / LIMITATION HANDLING:\n"
                    "- Acknowledge limitations calmly and honestly (without fear language).\n"
                    "- Keep the response constructive by prioritizing structured chart challenges and key houses.\n"
                    "- If critical failures exist, mention the key limitation(s) in plain language and suggest practical next best steps.\n"
                )

        # Domain-specific Pratyantar spotlight — injected into the dasha block so the LLM
        # knows which planet's Pratyantar window to prioritize for this exact query type.
        domain_spotlight = self._get_domain_pratyantar_spotlight(query)

        # ════════════════════════════════════════════════════════════════════════
        # ENGINE USAGE GUIDELINES
        # ════════════════════════════════════════════════════════════════════════
        engine_usage_instruction = """

ENGINE USAGE GUIDELINES (CRITICAL - USE THE DATA ABOVE):
- Base your interpretation on ALL available computed signals, not just dashas and house lords. Use EVERY relevant layer you see in the prompt:
  1) House lords — sign, dignity, and what that means for the person's life topic.
  2) Yogas (from YOGAS DETECTED section) — in detailed responses, NAME each relevant yoga explicitly (e.g., "Gaj Kesari Yoga strengthens..."). Do NOT invent yogas not in the data.
  3) Divisional charts — use D-charts as evidence; in detailed responses, explicitly reference the appropriate chart by its classical name (Navamsa for marriage, Dasamsa for career, etc.). Never use D9/D10 numbers.
  4) Active Dasha stack and Pratyantar timing windows (from ASTRO INTELLIGENCE LAYER) — show how timing windows line up with life events.
  5) Vimshopaka Bala — when a domain-key planet has a score in the Vimshopaka table, mention its strength (e.g., "Jupiter at 15.2/20 across divisional charts").
  6) Vargottama — when a relevant planet is listed in VARGOTTAMA PLANETS, SAY SO: "This planet is especially potent as it holds the same sign in both the birth chart and Navamsa, amplifying its dasha results."
  7) Gochara (transits) — when Jupiter or Saturn transit directly supports or opposes the timing, include a one-sentence Gochara crosscheck.
  8) Long Saturn phases (e.g., Sade Sati) — when the domain hints or validation context mention Saturn pressure phases, explicitly name them and explain how they colour the period (pressure, responsibility, restructuring) rather than only repeating the dasha story.
- Never invent graha positions, house placements or yogas not explicitly in the data above.
- PLANETARY CONDITIONS — DO NOT HIDE THESE (name them, then explain):
  - When a key planet is RETROGRADE: say "X is retrograde in your chart" and describe the effect as themes becoming internalised, revisited, or delayed — not completely blocked.
  - When a key planet is COMBUST or DEEPLY COMBUST: say "X is combust (close to the Sun)" and explain that its ability to deliver results is weakened or strained. Deeply combust = near-total suppression in this period.
  - When a key planet is STATIONARY: say "X is stationary" and note that stationary planets give intense, concentrated results during their period — unusually potent but slower to materialise.
- NAKSHATRA LORDS — when a key planet's nakshatra lord is the same as the active Dasha/Antardasha lord, point this out as a timing link: "The nakshatra lord of X is Y, which happens to be active in the current dasha period — a strong alignment."
- FEARED PLACEMENT REFRAMING (CRITICAL): When mentioning Mangal Dosha, debilitation, Sade Sati, Graha Yuddha losers,
  or any commonly feared placement, ALWAYS use the reframe pattern:
  (a) First state what it does NOT mean: "Iska matlab yeh nahi ki..." / "This does not mean..."
  (b) Then explain what it actually means for THIS specific person: "Balki iska matlab hai ki..." / "Rather, it means..."
  Never use fatalistic or generic fear-mongering language. Ground every reframe in the actual chart data.
- For domain-specific focus, use the appropriate divisional charts; in detailed reasoning refer to them by classical Sanskrit names (Navamsa for marriage, Dasamsa for career, etc.) and do not omit them when they are available in the DIVISIONAL CHART ANALYSIS section.
- When the user has asked for detailed reasoning, clearly expose AT LEAST 7 numbered astrological factors. Keep each point crisp and prioritize the strongest 7-9 factors from chart, divisional analysis, Vimshopaka Bala, Vargottama, planetary conditions, Saturn phases, and Gochara.
"""

        # ════════════════════════════════════════════════════════════════════════
        # MOBILE RESPONSE LENGTH CONTROL
        # ════════════════════════════════════════════════════════════════════════
        # Build mode-aware length instruction so it never conflicts with phase_instruction
        if response_mode == 'detailed':
            _default_length_line = "TARGET LENGTH: 380-500 words. Keep each numbered point concise, practical, and non-repetitive."
            _structure_closing = "- Closing: End with a convergence sentence + ONE question about a DIFFERENT life area (career, health, children, etc.). NEVER offer more detail on the same topic."
        elif response_mode == 'followup':
            _default_length_line = "DEFAULT LENGTH: 300-400 words. Answer the specific follow-up question thoroughly."
            _structure_closing = "- Closing: Give a self-contained answer. No further questions needed."
        else:  # initial / default
            _default_length_line = "MINIMUM LENGTH: 150 words (range 150-200). You MUST reach 150 words — include realistic future favorable timing plus 2-3 critical astrological factors explained in practical language."
            _structure_closing = "- Closing: One natural invitation to explain the astrological reasoning in more detail (single line, no second version)."

        mobile_length_instruction = f"""

RESPONSE FORMAT (CRITICAL - MUST FOLLOW):
1. {_default_length_line}
   The PROGRESSIVE DISCLOSURE instructions injected below this section are the final authority on length and structure — follow them precisely.
2. TONE: Write like a warm, knowledgeable astrologer speaking directly to the person — not a data sheet.
   Use natural sentence flow. Weave factors into a coherent narrative, not a bullet list.
   Show genuine care: acknowledge the importance of the question before diving into analysis.
3. STRUCTURE (narrative, not mechanical):
   - Opening: 1–2 sentences acknowledging the topic warmly and giving the headline answer in plain language.
     When the user's age or life stage is contextually meaningful (e.g., early 20s asking about first marriage,
     mid-career asking about a job change, or approaching 30 asking about children), briefly acknowledge it
     to show genuine understanding of where they are in life. Use the date_of_birth from the user profile to
     calculate their approximate current age. Keep this acknowledgment natural and non-generic.
   - Body: Key astrological factors as directed by the PROGRESSIVE DISCLOSURE section below.
   {_structure_closing}
   DO NOT use bullet lists.
4. HOUSE NUMBER FORMAT (MANDATORY): NEVER write "H1", "H2", "H10" etc. in your response.
   The H-notation is for internal data only. In your response always use ordinal format:
   1st house, 2nd house, 3rd house ... 10th house, 11th house, 12th house.
5. HOUSE ANNOTATIONS (MANDATORY): Every time you mention a house by number, ALWAYS
   add its primary domain in parentheses immediately after. No exceptions.
   Use this exact mapping:
     1st house (Self & Personality) | 2nd house (Wealth & Family) | 3rd house (Courage & Siblings)
     4th house (Home & Mother) | 5th house (Children & Intellect) | 6th house (Health & Service)
     7th house (Marriage & Partnership) | 8th house (Longevity & Transformation) | 9th house (Luck & Dharma)
     10th house (Career & Status) | 11th house (Gains & Desires) | 12th house (Foreign & Moksha)
6. NO META-COMMENTARY: Never say "Based on your chart I can see..." or "Looking at your horoscope...".
   Start directly with the insight. The user knows you're reading their chart.
7. NO THANKING: User details come from the backend — never thank them for providing details.
8. FOLLOW-UP QUESTIONS: Only ask a follow-up question when the PROGRESSIVE DISCLOSURE instructions below tell you to.
   In a detailed response, the follow-up MUST be about a different topic — never offer more detail on the same one.
"""
        instructions += engine_usage_instruction
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
                enhanced_analysis, synthesis,
                query_type=validation_result.get('query_type', 'general') if validation_result else 'general',
                chart_data=chart_data,
                dasha_data=dasha_data,
                validation_result=validation_result,
                question_mode=_ia.get('question_mode'),
            )
        deterministic_evidence = format_evidence_for_prompt(astro_evidence or {})

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
        # CHAIN-OF-THOUGHT SCRATCHPAD (hidden reasoning)
        # ════════════════════════════════════════════════════════════════════════
        # We explicitly ask the model to reason step-by-step using a scratchpad
        # BEFORE writing the final user-facing answer. The scratchpad is purely
        # internal; the assistant must not expose it verbatim to the user.
        #
        # The COMMITTED ANSWER PLAN (from AnswerPlanner) is prepended so the LLM
        # reasons WITHIN the plan, not around it.  The plan commits primary factors,
        # timing window, divisional chart, tone, and response arc deterministically
        # before any free-form reasoning begins.
        _committed_plan_prefix = (_answer_plan.plan_block if _answer_plan else "")
        reasoning_scratchpad_block = f"""{_committed_plan_prefix}
REASONING SCRATCHPAD (INTERNAL - DO NOT SHOW TO USER):
- The COMMITTED ANSWER PLAN above is your reasoning scaffold — follow it.
- First, silently reason step by step about this specific question using the chart data, dasha, transits and the ASTRO INTELLIGENCE evidence above.
- Use a mental checklist like:
  1) Identify the key houses and lords for this domain (for example: 7th for marriage, 10th for career, 4th for home, 5th for children, etc.).
  2) Check dignity, strength and major aspects/yogas that meaningfully change results.
  3) Align these with the active Mahadasha/Antardasha/Pratyantardasha and the candidate timing windows listed in ASTRO INTELLIGENCE LAYER.
  4) Note 2–4 core interpretive points that truly matter for the person (not a laundry list).
- You MUST use this scratchpad reasoning to keep your answer coherent and grounded, but you MUST NOT show the scratchpad itself to the user.
- The final answer for the user must be a single, clean paragraph-style reply in the user's language/script, without exposing any XML tags or scratchpad markers.

When you are done reasoning, write ONLY the polished answer for the user. Do NOT wrap it in <final_answer> or any other tags.
"""

        # ════════════════════════════════════════════════════════════════════════
        # PROMPT STRUCTURE (order matters for LLM compliance):
        #   1. System prompt (persona + constitution + chart anchor + timing rule)
        #   2. ALL computed chart data (birth chart, house lords, dasha, transits)
        #   3. Classical text knowledge (RAG) and deterministic evidence
        #   4. Response instructions + conversation context
        #   5. Hidden reasoning scratchpad instructions
        #   6. Few-shot quality examples (closest to query = strongest signal)
        #   7. User query LAST — so LLM reads all ground truth before the question
        # ════════════════════════════════════════════════════════════════════════

        # Select 2 golden examples matching domain/language/mode
        few_shot_block = get_few_shot_block(
            query=query,
            language_code=language,
            domain=_ia.get("domain"),
            response_mode=response_mode,
            n=2,
        )
        logger.info(f"[FEW_SHOT] block_length={len(few_shot_block)} domain={_ia.get('domain')} lang={language} mode={response_mode}")

        # Redact specific month-year dates from few-shot examples so the LLM
        # cannot anchor on them when generating the real user's response.
        # Covers: "April 2026", "April to August 2026", "(2026-04 to 2026-08)"
        import re as _re_fs
        _MONTHS_EN = (
            "January|February|March|April|May|June|"
            "July|August|September|October|November|December"
        )
        # 1. ISO ranges in chart_context: "(2026-04 to 2026-08)" → "(YYYY-MM to YYYY-MM)"
        few_shot_block = _re_fs.sub(
            r"\b(20\d\d-\d{2})\s+to\s+(20\d\d-\d{2})\b",
            "YYYY-MM to YYYY-MM",
            few_shot_block,
        )
        # 2. "Month to Month YYYY" or "Month - Month YYYY"
        few_shot_block = _re_fs.sub(
            rf"(?:{_MONTHS_EN})\s+(?:to|-)\s+(?:{_MONTHS_EN})\s+20\d\d",
            "[Month to Month Year]",
            few_shot_block,
        )
        # 3. standalone "Month YYYY"
        few_shot_block = _re_fs.sub(
            rf"(?:{_MONTHS_EN})\s+20\d\d",
            "[Month Year]",
            few_shot_block,
        )

        prompt = f"""{system_prompt}

{validation_context}

{enhanced_context}

{divisional_context}

{deterministic_evidence}

{conversation_summary_section}

{reasoning_scratchpad_block}

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}
{user_preferences_block}
════════════════════════════════════════════════════════════════════════
COMPUTED CHART DATA — Swiss Ephemeris (Sidereal/Lahiri)
All values below are CALCULATED, not inferred. Use ONLY these values.
════════════════════════════════════════════════════════════════════════

BIRTH CHART PLANETARY POSITIONS:
  Format: Sign | House | Degree | Nakshatra (Lord) Pada | Dignity | [MOTION] [COMBUST]
  INTERPRETATION PRIORITY (apply in this order — each layer modifies the one before):
  1. Dignity         — sets base strength (Exalted > Own/Moolatrikona > Friend > Neutral > Enemy > Debilitated)
  2. [RETRO]         — retrograde planet turns results inward; expression delayed then intensified
  3. [STATIONARY]    — planet about to change direction; results are concentrated and unusually potent
  4. [COMBUST]       — within Sun's orb; planet's significations weakened/suppressed
  5. [DEEPLY COMBUST]— within 3° of Sun; significations severely suppressed; near-total weakening
  6. Nakshatra Lord  — the nakshatra lord colours the planet's expression and links to the dasha timeline
  7. Pada            — navamsa quarter; P1/P3 stronger for material results; P2/P4 for inner/spiritual
  8. Degree          — 0–1° = unsteady new energy; 29° = culminating; gandanta at water-fire junctions
  NOTE: [RETRO][COMBUST] = competing modifiers — retrograde strengthens inwardly, combustion weakens delivery; net result is erratic/partial.
• Ascendant (Lagna): {chart_data.get('lagna', {}).get('sign', 'Not available')} {chart_data.get('lagna', {}).get('degree', 0.0):.2f}° | Nakshatra: {chart_data.get('lagna', {}).get('nakshatra', 'N/A')} (Lord: {chart_data.get('lagna', {}).get('nakshatra_lord', 'N/A')})
• Sun:     {chart_data.get('planets', {}).get('SUN',     {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('SUN',     {}).get('house', '?')} {chart_data.get('planets', {}).get('SUN',     {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('SUN',     {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('SUN',     {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('SUN',     {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('SUN',     {}).get('dignity', {}).get('status', '')}
• Moon:    {chart_data.get('planets', {}).get('MOON',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MOON',    {}).get('house', '?')} {chart_data.get('planets', {}).get('MOON',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MOON',    {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('MOON',    {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('MOON',    {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MOON',    {}).get('dignity', {}).get('status', '')}{'  [COMBUST]' if chart_data.get('planets', {}).get('MOON', {}).get('combust') else ''}
• Mars:    {chart_data.get('planets', {}).get('MARS',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MARS',    {}).get('house', '?')} {chart_data.get('planets', {}).get('MARS',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MARS',    {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('MARS',    {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('MARS',    {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MARS',    {}).get('dignity', {}).get('status', '')}{'  [STATIONARY]' if chart_data.get('planets', {}).get('MARS', {}).get('is_stationary') else '  [RETRO]' if chart_data.get('planets', {}).get('MARS', {}).get('retrograde') else ''}{'  [DEEPLY COMBUST]' if chart_data.get('planets', {}).get('MARS', {}).get('combustion_status') == 'deeply_combust' else '  [COMBUST]' if chart_data.get('planets', {}).get('MARS', {}).get('combust') else ''}
• Mercury: {chart_data.get('planets', {}).get('MERCURY', {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('MERCURY', {}).get('house', '?')} {chart_data.get('planets', {}).get('MERCURY', {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('MERCURY', {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('MERCURY', {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('MERCURY', {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('MERCURY', {}).get('dignity', {}).get('status', '')}{'  [STATIONARY]' if chart_data.get('planets', {}).get('MERCURY', {}).get('is_stationary') else '  [RETRO]' if chart_data.get('planets', {}).get('MERCURY', {}).get('retrograde') else ''}{'  [DEEPLY COMBUST]' if chart_data.get('planets', {}).get('MERCURY', {}).get('combustion_status') == 'deeply_combust' else '  [COMBUST]' if chart_data.get('planets', {}).get('MERCURY', {}).get('combust') else ''}
• Jupiter: {chart_data.get('planets', {}).get('JUPITER', {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('JUPITER', {}).get('house', '?')} {chart_data.get('planets', {}).get('JUPITER', {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('JUPITER', {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('JUPITER', {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('JUPITER', {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('JUPITER', {}).get('dignity', {}).get('status', '')}{'  [STATIONARY]' if chart_data.get('planets', {}).get('JUPITER', {}).get('is_stationary') else '  [RETRO]' if chart_data.get('planets', {}).get('JUPITER', {}).get('retrograde') else ''}{'  [DEEPLY COMBUST]' if chart_data.get('planets', {}).get('JUPITER', {}).get('combustion_status') == 'deeply_combust' else '  [COMBUST]' if chart_data.get('planets', {}).get('JUPITER', {}).get('combust') else ''}
• Venus:   {chart_data.get('planets', {}).get('VENUS',   {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('VENUS',   {}).get('house', '?')} {chart_data.get('planets', {}).get('VENUS',   {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('VENUS',   {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('VENUS',   {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('VENUS',   {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('VENUS',   {}).get('dignity', {}).get('status', '')}{'  [STATIONARY]' if chart_data.get('planets', {}).get('VENUS', {}).get('is_stationary') else '  [RETRO]' if chart_data.get('planets', {}).get('VENUS', {}).get('retrograde') else ''}{'  [DEEPLY COMBUST]' if chart_data.get('planets', {}).get('VENUS', {}).get('combustion_status') == 'deeply_combust' else '  [COMBUST]' if chart_data.get('planets', {}).get('VENUS', {}).get('combust') else ''}
• Saturn:  {chart_data.get('planets', {}).get('SATURN',  {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('SATURN',  {}).get('house', '?')} {chart_data.get('planets', {}).get('SATURN',  {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('SATURN',  {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('SATURN',  {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('SATURN',  {}).get('nakshatra_pada', '?')} | {chart_data.get('planets', {}).get('SATURN',  {}).get('dignity', {}).get('status', '')}{'  [STATIONARY]' if chart_data.get('planets', {}).get('SATURN', {}).get('is_stationary') else '  [RETRO]' if chart_data.get('planets', {}).get('SATURN', {}).get('retrograde') else ''}{'  [DEEPLY COMBUST]' if chart_data.get('planets', {}).get('SATURN', {}).get('combustion_status') == 'deeply_combust' else '  [COMBUST]' if chart_data.get('planets', {}).get('SATURN', {}).get('combust') else ''}
• Rahu:    {chart_data.get('planets', {}).get('RAHU',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('RAHU',    {}).get('house', '?')} {chart_data.get('planets', {}).get('RAHU',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('RAHU',    {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('RAHU',    {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('RAHU',    {}).get('nakshatra_pada', '?')} [always Retro]
• Ketu:    {chart_data.get('planets', {}).get('KETU',    {}).get('sign', 'N/A'):12} H{chart_data.get('planets', {}).get('KETU',    {}).get('house', '?')} {chart_data.get('planets', {}).get('KETU',    {}).get('degree', 0.0):.1f}° | {chart_data.get('planets', {}).get('KETU',    {}).get('nakshatra', 'N/A')} ({chart_data.get('planets', {}).get('KETU',    {}).get('nakshatra_lord', 'N/A')}) P{chart_data.get('planets', {}).get('KETU',    {}).get('nakshatra_pada', '?')} [always Retro]
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
  • Mahadasha: {maha_planet} {md_range_disp}
  • Antardasha: {antar_planet} {ad_range_disp}
{_praty_step2_line}
• Dasha Sequence: {dasha_sequence}
{upcoming_pds_str}{sookshma_str}{broader_window_str}{next_ad_fp_str}{ranked_windows_str}{upcoming_ads_str}{domain_spotlight}
TODAY'S DATE: {today_date}

⚠ PAST DATE RULE (MANDATORY): NEVER cite a date range as a prediction if it has already ended (end date < {today_date}).
  - Periods marked "IN PROGRESS": cite only the remaining window (today → end date), NOT the original start.
  - Only cite periods that are "IN PROGRESS" (remaining portion) or fully in the future.
  - If all favorable Pratyantardashas in the current Antardasha have already passed, move to the NEXT Antardasha.

TIMING GUIDANCE: Use TWO layers for timing:
  1) Broad supportive phase (prefer Step 3.7 when available; otherwise derive from topic-relevant AD/PD spans), typically 9-24 months and allowed to cross calendar years.
  2) A concrete trigger sub-window from Pratyantardasha for sharper activation inside that broad phase.
CRITICAL TIMING SELECTION RULE:
1) Use Step 3.8 ranked candidates as the default ordering for primary vs secondary windows.
2) Do NOT automatically pick the nearest upcoming period for every domain.
3) If a near-immediate window exists but has weaker domain relevance than a later one, prefer the later stronger window as the headline.
4) Only prioritize the immediate window when the user explicitly asks for "right now/immediate" timing.
5) If the same month-range appears in recent answers for other topics, prefer an alternative ranked period when astrologically comparable.
6) If overlap is unavoidable (same dasha window genuinely activates multiple topics), explicitly say so in natural language and differentiate the reason for THIS topic (house-lord/karaka/transit logic), then add one distinct secondary window.
CRITICAL: These dates are CALCULATED using Swiss Ephemeris. Use ONLY these exact dates. Do not invent or estimate dates.

CURRENT TRANSITS (as of {transit_date}):
• Jupiter: {jupiter_transit}
• Saturn: {saturn_transit}
• Mars: {mars_transit}

{gochara_str}

{vargottama_str}
{vimshopaka_str}
{planetary_wars_str}
{house_occupancy_str}

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
  Stationary planet             │ [STATIONARY] flag — if present, results concentrated/potent
  Combustion effect             │ [COMBUST] flag on that planet's row — ONLY if flag present
                                │ If absent, planet is NOT combust — do not assume it
  Deep combustion               │ [DEEPLY COMBUST] flag — within 3° of Sun; near-total weakening
  Nakshatra lord                │ The (Lord) column next to nakshatra name in planet row
  House lord                    │ HOUSE LORDS table — cite both planet AND house sign
                                │ Format: "Nth house (domain) lord [PLANET]"
  Dasha/timing dates            │ Step 2/3/3.5/3.6 dasha tables — exact dates only
  Transit effect on native      │ CURRENT TRANSITS + GOCHARA ANALYSIS block
  Planet sign/house/nakshatra   │ BIRTH CHART PLANETARY POSITIONS rows
  Nakshatra pada                │ Pada column (P1–P4) in BIRTH CHART PLANETARY POSITIONS
  Vargottama claim              │ VARGOTTAMA PLANETS line — only if planet listed there
  Vimshopaka strength           │ VIMSHOPAKA BALA table — use as secondary strength modifier
  Planetary war effect          │ GRAHA YUDDHA block — loser planet weakened; winner amplified
  House occupancy               │ HOUSE OCCUPANCY block — which planets are in which house
  ─────────────────────────────────────────────────────────────────────────────

PROHIBITED INFERENCES (NEVER do these):
  X Claiming a planet is strong/weak without citing its computed dignity status
  X Stating a planet is retrograde unless [RETRO] appears on its row in the table
  X Stating a planet is stationary unless [STATIONARY] appears on its row
  X Stating a planet is combust unless [COMBUST] appears on its row in the table
  X Calling combustion "deep" or "severe" unless [DEEPLY COMBUST] is flagged
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
  X Saying a planet in a Planetary War is "strong" if it is the LOSER — war losses
    apply regardless of dignity. State reduced delivery of significations.
  X Using Vimshopaka Bala as the sole strength indicator — it must be read alongside
    D1 dignity; a planet exalted in D1 but weak in vargas gives partial results.

CROSS-REFERENCING FORMAT (MANDATORY in every response):
  • House lords  → "Nth house (domain) lord [PLANET]"
                   e.g. "7th house (Marriage & Partnership) lord Venus is in H3"
  • Timing       → "During [PLANET] Pratyantar ([START] to [END])..."
  • Dignity      → "[PLANET] is [dignity] in [sign]" — match the table exactly
  • Transit      → "[PLANET] transiting H[N] from Moon/Lagna ([sign])"

If computed data is absent for a claim, write "data not available" rather than
substituting a training-knowledge default.

{instructions}

{few_shot_block}
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
            "validation_debug": None,

            # Context management fields (populated externally by chat_stateless.py but
            # must be present in initial_state to satisfy TypedDict contract)
            "conversation_summary": None,
            "intent_analysis": None,
            "resolution_result": None,

            # Progressive Disclosure Phase (set by rag_with_calculation node)
            "conversation_phase": None,
            "astro_evidence": None,
            "_detailed_followup": None,
        }

        
        # Run through graph
        final_state = self.graph.invoke(initial_state)

        # Calculate processing time
        final_state['processing_time'] = (datetime.now() - start_time).total_seconds()

        # Attach structured timing metadata so the API can store it without
        # relying on regex-parsing the response text later.
        # Only include windows starting within 30 months of today — distant
        # windows are irrelevant for cross-topic / coherence tracking.
        try:
            _now = datetime.utcnow()
            _cutoff_month = ((_now.month - 1 + 30) % 12) + 1
            _cutoff_year = _now.year + ((_now.month - 1 + 30) // 12)
            _cutoff_ym = f"{_cutoff_year:04d}-{_cutoff_month:02d}"
            _all_cand = self._collect_future_candidate_window_keys(final_state.get('dasha_data', {}))
            _near_cand = {
                k for k in _all_cand
                if "|" in k and k.split("|")[0] <= _cutoff_ym
            }
            final_state['response_timing_windows'] = sorted(_near_cand)
        except Exception:
            final_state['response_timing_windows'] = []

        final_state['response_topic'] = (
            (final_state.get('conversation_phase') or {}).get('topic') or ''
        )

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
            "is_safe": True,
            "astro_evidence": None,
            "validation_debug": None,
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