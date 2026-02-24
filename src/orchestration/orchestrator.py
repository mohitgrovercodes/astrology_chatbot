# src\orchestration\orchestrator.py
"""
Enhanced LangGraph Orchestrator with REAL Calculation Integration.

UPDATED: Now uses actual VedicEngine calculations (no placeholders!)

3-way routing:
1. CHITCHAT -> Quick response
2. NEEDS_CALCULATION -> Real birth chart calculation
3. NEEDS_RAG -> Knowledge + Real chart data + Interpretation/Prediction
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
from src.tools.calculation_tools import get_calculation_tools, format_chart_for_llm

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
                    "dhanyavad", "shukriya", "धन्यवाद", "शुक्रिया"
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
            print("[VALIDATION] Validation engine enabled ✅")

        self.graph = self._build_graph()
        
        print("[LANGGRAPH] [SUCCESS] Enhanced orchestrator initialized")
        print("[LANGGRAPH] Routes: CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY")
        print("[LANGGRAPH] Safety guardrails enabled (Phase 6)")
    
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
        workflow.add_conditional_edges(
            "safety_check",
            lambda state: "blocked" if state.get('intent') == 'BLOCKED' else "safe",
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
            
            # Merge session keys (overwrites DB fields if conflict)
            state['user_profile'].update(session_data)
            
            # Promoting internal state keys (Priority injection)
            internal_keys = ['chart_data', 'dasha_data', 'transit_data', 'detected_language', 'persona_type']
            for key in internal_keys:
                if key in session_data:
                    print(f"[AUTH] [PRIORITY] Using injected context: {key}")
                    state[key] = session_data[key]
            
            # If session data provides name, we consider user at least partially authenticated for context
            if 'name' in session_data:
                state['authenticated'] = True

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
                print(f"[SAFETY] 🚫 BLOCKED: {safety_result.decision.reason}")
                
                # WORKAROUND: Don't block chitchat queries
                CHITCHAT_REASONS = ['greeting', 'identity', 'gratitude', 'wellbeing', 'farewell']
                if safety_result.decision.reason in CHITCHAT_REASONS:
                    print(f"[SAFETY] ✅ Chitchat query - allowing through")
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
            
            # If conditional, flag for disclaimer
            if safety_result.needs_disclaimer:
                state['needs_disclaimer'] = safety_result.decision.disclaimer_type
            
            # Safe to proceed
            state['is_safe'] = True
            print(f"[SAFETY] ✅ Safe to proceed")
            
        except Exception as e:
            print(f"[SAFETY] ⚠️ Error in safety check: {e}")
            import traceback
            traceback.print_exc()
            # On error, allow to proceed (fail open for availability)
            state['is_safe'] = True
        
        return state

    def _classify_intent_node(self, state: NakshatraState) -> NakshatraState:
        """Node 2: Classify intent."""
        print(f"[INTENT] Classifying query: '{state['query'][:50]}...'")

        # ── CONTINUATION GUARD ────────────────────────────────────────────────
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
            or (len(q.split()) <= 5 and q.split()[0] in _SHORT_QUESTION_STARTERS)
        )
        if is_continuation and len(history) > 0:
            print(f"[INTENT] [CONTINUATION] CONTINUATION GUARD: routed to RAG_ONLY (history={len(history)} msgs)")
            state['intent'] = 'RAG_ONLY'
            state['confidence'] = 0.85
            state['intent_reasoning'] = 'Bare continuation query with active conversation'
            state['is_safe'] = True
            return state
        # ─────────────────────────────────────────────────────────────────────

        # PHASE 11: Semantic Chitchat Router
        # Check for simple greetings semantically
        chitchat_match = None
        if self.semantic_router.model:
            chitchat_match = self.semantic_router.route(state['query'], threshold=0.7)
            
        if chitchat_match and chitchat_match.name == "chitchat":
            print(f"[INTENT] Semantic Chitchat Match: '{state['query']}' ({chitchat_match.confidence:.2f})")
            state['intent'] = 'CHITCHAT'
            state['confidence'] = chitchat_match.confidence
            state['intent_reasoning'] = "Semantic Chitchat Match"
            state['is_safe'] = True
            return state

        # PHASE 10.5: Multi-Gate Safety Check
        # Check before ANY LLM classification
        if self.safety_classifier:
            safety_result = self.safety_classifier.classify(
                state['query'], 
                state.get('conversation_history', [])
            )
            
            # Store safety metadata
            state['safety_result'] = safety_result.decision.model_dump()
            state['disclaimer_type'] = safety_result.decision.disclaimer_type
            state['is_reframed'] = False
            
            # 1. HARD / SOFT BLOCK: Refuse immediately
            if safety_result.is_blocked:
                # Double Check: If soft block is "out_of_scope", check if it's actually chitchat via LLM fallback
                if safety_result.decision.category == "SOFT_BLOCK":
                    print("[GUARD] Soft block detected. Checking if actually chitchat...")
                    # Let it fall through to intent classifier which handles chitchat better
                    pass 
                else:
                    print(f"[GUARD] [BLOCK] BLOCKING REQUEST: {safety_result.decision.category} ({safety_result.decision.reason})")
                    state['intent'] = 'safety_block'
                    state['answer'] = get_template(safety_result.get_template_key())
                    state['is_safe'] = False
                    state['confidence'] = safety_result.decision.confidence
                    return state
                
            # 2. REFRAME: Transform query and proceed
            if safety_result.decision.category == "REFRAME":
                print(f"[GUARD] [REFRAME] REFRAMING QUERY: {state['query']} -> {safety_result.processed_query}")
                state['original_query'] = state['query']
                state['query'] = safety_result.processed_query
                state['is_reframed'] = True
                # Continue process with better query
                
            # 3. CONDITIONAL: Mark for disclaimer (handled in format_response)
            if safety_result.decision.disclaimer_type:
                print(f"[GUARD] [WARN] CONDITIONAL: Needs {safety_result.decision.disclaimer_type} disclaimer")
                state['disclaimer_type'] = safety_result.decision.disclaimer_type
        
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
        chitchat_match = None
        if self.semantic_router.model:
            chitchat_match = self.semantic_router.route(query, threshold=0.70)
        
        # Handle based on semantic match
        if chitchat_match:
            match_type = chitchat_match.name
            confidence = chitchat_match.confidence
            print(f"[CHITCHAT] Semantic match: {match_type} (confidence: {confidence:.2f})")
            
            # 0. PERSONAL PROFILE QUERIES — "Mera naam kya hai?", "What is my name?"
            #    Must be checked BEFORE identity to avoid misrouting.
            if match_type == "personal_profile_query":
                state['answer'] = self._answer_personal_profile_query(
                    query=query, user_profile=state['user_profile'], language=lang
                )
                return state

            # 1. GREETING
            if match_type == "greeting":
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

            # Multilingual/Complex path: Use fast LLM with persona
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
                
                # Map language code to descriptive name
                loc_manager = get_localization_manager()
                lang_name = loc_manager.get_language_name(lang)
                
                if '-lat' in lang:
                    script_instruction = f"IMPORTANT: You must write in {lang_name} using ROMAN ALPHABET (English Script). Do NOT use native script."
                else:
                    script_instruction = f"Respond entirely in {lang_name} (Native Script)."
                
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
                _profile_lines = []
                if _up.get('name'):
                    _profile_lines.append(f"User name: {_up['name']}")
                if _bd.get('date'):
                    _profile_lines.append(f"Date of birth: {_bd['date']}")
                if _bd.get('time'):
                    _profile_lines.append(f"Time of birth: {_bd['time']}")
                if _loc.get('city') or _loc.get('address'):
                    _profile_lines.append(f"Birth place: {_loc.get('city') or _loc.get('address')}")
                if _up.get('sun_sign'):
                    _profile_lines.append(f"Sun sign: {_up['sun_sign']}")
                if _up.get('moon_sign'):
                    _profile_lines.append(f"Moon sign: {_up['moon_sign']}")
                if _up.get('ascendant'):
                    _profile_lines.append(f"Ascendant: {_up['ascendant']}")
                user_profile_context = (
                    "USER PROFILE (use this if the user asks about their own details):\n"
                    + "\n".join(_profile_lines)
                ) if _profile_lines else ""

                prompt = f"""{system_prompt}
                
        {history_context}
        User: "{state['query']}"

        INSTRUCTIONS:
        1. Provide a warm, empathetic, professional response.
        2. If the user greets, greet back warmly.
        3. If the user asks about previous messages or personal context, ANSWER DIRECTLY based on CONVERSATION CONTEXT.
        4. If the question is entirely outside astrology and NOT in history, politely explain your scope.
        5. {script_instruction}
        6. Keep it brief (under 60 words).

        {user_profile_context}

        Response:"""
                
                llm_response = self.fast_llm.invoke(prompt)
                state['answer'] = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
                
            except Exception as e:
                print(f"[CHITCHAT] Error generating response: {e}")
                state['answer'] = get_greeting(lang)

            return state

    # ------------------------------------------------------------------
    # PERSONAL PROFILE QUERY HELPER
    # ------------------------------------------------------------------
    def _answer_personal_profile_query(
        self, query: str, user_profile: dict, language: str
    ) -> str:
        """
        Answer questions about the USER's own details (name, DOB, location, sign)
        using the structured user_profile dict — no LLM guesswork.
        """
        name = user_profile.get('name', '')
        bd = user_profile.get('birth_details', {})
        dob = bd.get('date', '')
        tob = bd.get('time', '')
        location = bd.get('location', {})
        city = location.get('city', '') or location.get('address', '')
        sun_sign = user_profile.get('sun_sign', '')
        moon_sign = user_profile.get('moon_sign', '')
        ascendant = user_profile.get('ascendant', '')

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
   → Learn about {topic} in Vedic astrology (classical principles)

2️⃣ **Personalized Analysis** (Your Chart)
   → Understand {topic} specifically in YOUR birth chart

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
                from src.tools.calculation_tools import calculate_vedic_birth_chart
                # Mock the tool logic to get the formatted dict from existing chart
                # Actually, simpler: have a helper in calculation_tools to format a chart
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
                chart_data = format_chart_for_llm(full_chart)
            else:
                state['answer'] = "Could not generate or load your birth chart. Please check your birth details."
                return state
            
            print(f"[CALCULATION_ONLY] Chart: Lagna={chart_data['lagna']}, Rashi={chart_data['moon_sign']}")
            
            # Use LLM to extract only what was asked for
            extraction_prompt = f"""You are a data extraction assistant. The user asked: "{state['query']}"
 
USER'S BIRTH DETAILS:
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}
 
COMPLETE BIRTH CHART DATA:
• Lagna (Ascendant): {chart_data.get('lagna', 'Unknown')}
• Moon Sign (Rashi): {chart_data.get('moon_sign', 'Unknown')}
• Sun Sign: {chart_data.get('sun_sign', 'Unknown')}
• Moon Nakshatra: {chart_data.get('moon_nakshatra', 'Unknown')}
 
Planetary Positions:
• Sun: {chart_data.get('planets', {}).get('Sun', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Sun', {}).get('house', '?')})
• Moon: {chart_data.get('planets', {}).get('Moon', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Moon', {}).get('house', '?')})
• Mars: {chart_data.get('planets', {}).get('Mars', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Mars', {}).get('house', '?')})
• Mercury: {chart_data.get('planets', {}).get('Mercury', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Mercury', {}).get('house', '?')})
• Jupiter: {chart_data.get('planets', {}).get('Jupiter', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Jupiter', {}).get('house', '?')})
• Venus: {chart_data.get('planets', {}).get('Venus', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Venus', {}).get('house', '?')})
• Saturn: {chart_data.get('planets', {}).get('Saturn', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Saturn', {}).get('house', '?')})
• Rahu: {chart_data.get('planets', {}).get('Rahu', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Rahu', {}).get('house', '?')})
• Ketu: {chart_data.get('planets', {}).get('Ketu', {}).get('rashi', 'Unknown')} (House {chart_data.get('planets', {}).get('Ketu', {}).get('house', '?')})
 
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
                    dasha_tool = self.calculation_tools['current_dasha']
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
                    transit_tool = self.calculation_tools['current_transits']
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
                            state['chart_data'] = format_chart_for_llm(full_chart)
                            
                        if state.get('chart_data'):
                            print(f"[RAG_WITH_CALCULATION] Chart ready: Lagna={state['chart_data'].get('lagna') or state['chart_data'].get('ascendant', {}).get('rashi', 'Unknown')}")
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Chart calculation error: {e}")

                # Calculate current dasha (UN-NESTED from chart check)
                if not state.get('dasha_data'):
                    try:
                        print("[RAG_WITH_CALCULATION] Calculating dasha...")
                        dasha_tool = self.calculation_tools['current_dasha']
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
                        transit_tool = self.calculation_tools['current_transits']
                        transit_data = transit_tool.invoke({})
                        
                        if "error" not in transit_data:
                            state['transit_data'] = transit_data
                            print(f"[RAG_WITH_CALCULATION] Transits for {transit_data.get('date', 'current')}")
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Transit calculation error: {e}")

            else:
                print("[RAG_WITH_CALCULATION] No birth data - proceeding without chart")

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
                                    print("[VALIDATION] ✅ Engine ready")
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
            # STEP 2: Retrieve Relevant Knowledge
            # ================================================================
            print("[RAG_WITH_CALCULATION] Step 2: Retrieving knowledge...")
            
            knowledge_chunks = state.get('knowledge_chunks') or []

            if not knowledge_chunks and self.hybrid_retriever:
                # Enhance query for better retrieval if we have chart data
                retrieval_query = state['query']
                if state.get('chart_data'):
                    c = state['chart_data']
                    lagna = c.get('lagna') or c.get('ascendant', {}).get('rashi', 'Unknown')
                    moon_sign = c.get('moon_sign') or c.get('planets', {}).get('Moon', {}).get('rashi', 'Unknown')
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
                    validation_result=state.get('validation_result'),  # NEW: Pass validation
                    conversation_history=state.get('conversation_history', []),
                    language=state.get('detected_language', 'en')
                )
            else:
                prompt = self.prompt_builder.build_prompt(
                    query=state['query'],
                    intent="RAG_WITH_CALCULATION",
                    user_profile=state['user_profile'],
                    knowledge_chunks=knowledge_chunks,
                    conversation_history=state.get('conversation_history', []),
                    language=state.get('detected_language', 'en')
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
                state['answer'] = f"""Namaste, {user_name}.

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
        prompt = f"""You are an expert Vedic astrologer explaining astrological concepts.

USER PROFILE:
• Name: {_p.get('name', 'User')}
• Date of Birth: {_p.get('date_of_birth', 'Unknown')}
• Time of Birth: {_p.get('time_of_birth', 'Unknown')}
• Place of Birth: {_p.get('place_of_birth', 'Unknown')}
• Moon Sign: {(_p.get('chart_data') or {}).get('moon_sign', _p.get('moon_sign', 'Unknown'))}
• Lagna (Ascendant): {(_p.get('chart_data') or {}).get('lagna', _p.get('lagna', 'Unknown'))}

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
            # Format minimal chart data for checking
            planets = chart_data.get('planets', {})
            formatted_planets = ", ".join([f"{p}: {d.get('current_sign', 'Unknown')}" for p, d in planets.items()])
            data_context = f"\nCALCULATED CHART DATA (TRUTH): {formatted_planets}\n"
        
        prompt = f"""You are the Guardian of the Astrologer's Constitution.
Your job is to specificially check if the following AI response violates any Immutable Rules.

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

OUTPUT FORMAT:
Return ONLY "SAFE" if no violations found.
Return "UNSAFE: <reason>" if violations found.
"""
        try:
            # Use fast LLM if available, else main LLM
            llm_to_use = self.fast_llm or self.llm
            if not llm_to_use:
                return True, "No LLM for validation"
                
            response = llm_to_use.invoke(prompt).content.strip() if hasattr(llm_to_use.invoke(prompt), 'content') else str(llm_to_use.invoke(prompt).content)
            
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
            print(f"[CRITIC] ❌ Unsafe response detected: {feedback}")
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
                    print("[CRITIC] ✅ Response rewritten.")
                except Exception as e:
                    state['error'] = f"Rewriting failed: {e}"
                    state['answer'] = "I cannot answer this query due to safety guidelines."
            else:
                # If we failed twice, block it.
                state['answer'] = "I must decline to answer this request as it violates my safety constitution regarding harmful or fatalistic predictions."
        else:
            print("[CRITIC] ✅ Response is SAFE.")
            
        return state

    def _format_response_node(self, state: NakshatraState) -> NakshatraState:
        """Node 4: Format final response."""
        
        if not state.get('error'):
            final_response = state.get('answer', '')
            
            # PHASE 10.5: Disclaimer Injection
            disclaimer_type = state.get('disclaimer_type')
            if disclaimer_type:
                disclaimer_text = get_disclaimer(disclaimer_type)
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

        # Domain-specific additions
        domain_hints = []

        if any(w in q for w in ['when', 'kab', 'timing', 'which year', 'how long', 'kitne din',
                                  'which month', 'period', 'dasha', 'antardasha']):
            domain_hints.append("For timing: give specific months/seasons (e.g., 'March-April 2026'), never just dasha names alone.")

        if any(w in q for w in ['career', 'job', 'business', 'naukri', 'profession',
                                  'promotion', 'kaam', 'vyapar', 'work', 'income']):
            domain_hints.append("Career: focus on 10th house, Saturn, Sun, and the active Dasha lord's work-related significations.")

        if any(w in q for w in ['marriage', 'shaadi', 'vivah', 'partner', 'love',
                                  'spouse', 'husband', 'wife', 'rishta', 'relationship']):
            domain_hints.append("Relationships: analyze 7th house, Venus, Jupiter. Speak of tendencies, not certainties.")

        if any(w in q for w in ['health', 'illness', 'sick', 'disease', 'bimari', 'sehat', 'swasth']):
            domain_hints.append("Health: discuss constitutional tendencies from lagna and 6th house. Always note: consult a doctor for medical concerns.")

        if any(w in q for w in ['money', 'wealth', 'paisa', 'dhan', 'rich', 'invest', 'finance']):
            domain_hints.append("Finance: focus on 2nd/11th house lords and Jupiter. Note that effort and timing matter equally.")

        domain_text = ("\n" + "\n".join(f"- {h}" for h in domain_hints)) if domain_hints else ""

        if wants_detail:
            if mode == 'prediction':
                return f"""INSTRUCTIONS:
1. Provide a comprehensive, detailed prediction with full reasoning.
2. Ground every claim in specific chart data (actual houses, signs, planets listed above).
3. Include dasha periods AND approximate calendar timeframes for any timing claims.
4. Cite classical texts only if they appear in the retrieved sources above.
5. {script_instruction}{domain_text}

Provide a thorough, detailed prediction:"""
            else:
                return f"""INSTRUCTIONS:
1. Provide a comprehensive explanation covering the concept fully.
2. Ground the answer in the retrieved classical texts above.
3. Only cite books that appear in the sources above.
4. {script_instruction}{domain_text}

Provide a detailed explanation:"""
        else:
            if mode == 'prediction':
                return f"""INSTRUCTIONS (CONCISE MODE):
1. Give a direct, astrological answer in 3-5 sentences.
2. Mention up to TWO key chart factors (e.g., "Jupiter in your 7th house suggests...").
3. If timing is relevant, give one specific period (e.g., "mid-2026").
4. Cite sources only if genuinely referenced.
5. {script_instruction}{domain_text}

Provide a concise, self-contained response:"""
            else:
                return f"""INSTRUCTIONS (CONCISE MODE):
1. Answer in 2-3 focused sentences (100-150 words maximum).
2. Base the answer only on retrieved texts above.
3. Only cite books that appear in the sources above.
4. {script_instruction}{domain_text}
5. End with: "Sources: [book names if any]" — skip this line if no sources.

Provide a concise answer:"""

    def _format_conversation_for_llm(
        self, 
        conversation_history: List[Dict]
    ) -> List[Dict[str, str]]:
        """
        Format conversation history for LLM.
        
        Args:
            conversation_history: List of {role, content, timestamp} dicts
            
        Returns:
            List of {role, content} dicts ready for LLM
        """
        if not conversation_history:
            return []
        
        formatted = []
        for msg in conversation_history:
            # Convert our format to LLM format
            formatted.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
        
        return formatted

    def _build_prediction_prompt(
        self,
        query: str,
        chart_data: Dict,
        dasha_data: Dict,
        transit_data: Dict,
        knowledge_chunks: List,
        user_profile: Dict,
        conversation_history: List = None,  # Added argument
        language: str = "hi-lat",
        validation_result: Optional[Dict] = None  # ADD THIS LINE
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
        
        # Extract dasha info safely
        maha_planet = dasha_data.get('mahadasha', {}).get('planet', 'Unknown')
        antar_planet = dasha_data.get('antardasha', {}).get('planet', 'Unknown')
        dasha_sequence = dasha_data.get('dasha_sequence', f"{maha_planet}/{antar_planet}")
        
        # DEBUG: Print dasha data to verify it has dates
        print(f"[DEBUG] Dasha data in prompt:")
        print(f"  Mahadasha: {maha_planet} ({dasha_data.get('mahadasha', {}).get('start_date', 'NO DATE')} to {dasha_data.get('mahadasha', {}).get('end_date', 'NO DATE')})")
        print(f"  Antardasha: {antar_planet} ({dasha_data.get('antardasha', {}).get('start_date', 'NO DATE')} to {dasha_data.get('antardasha', {}).get('end_date', 'NO DATE')})")
        calc_details = dasha_data.get('calculation_details', {})
        print(f"  Calculation details: Moon={calc_details.get('moon_longitude', 'MISSING')}, Nakshatra={calc_details.get('moon_nakshatra', 'MISSING')}")
        
        
        # Extract transit info safely
        jupiter_transit = transit_data.get('transits', {}).get('Jupiter', 'Unknown')
        saturn_transit = transit_data.get('transits', {}).get('Saturn', 'Unknown')
        mars_transit = transit_data.get('transits', {}).get('Mars', 'Unknown')
        transit_date = transit_data.get('date', 'current')
        
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

      # CHANGE 6: Enhanced context handling instructions
        if conversation_history and len(conversation_history) > 0:
            system_prompt += """

ONGOING CONVERSATION - CONTEXT HANDLING:
- No greetings (Namaste/Hello/Hari Om) - get straight to answer
- Review ALL previous messages before responding
- When user says "it", "this", "that" → check conversation history
- Connect follow-up questions to earlier topics
- Build upon previous insights, don't repeat
- Maintain conversation flow with context awareness
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

        # CHANGE 5: Add conversation summary section
        conversation_summary_section = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_summary_section = """
CONVERSATION CONTEXT:
This is an ongoing conversation. Previous messages contain:
- Topics already discussed
- Chart placements mentioned
- Questions answered

When user uses "it", "this", "that" or asks "why", "how" → connect to conversation history.
"""

        prompt = f"""{system_prompt}

{validation_context}

{conversation_summary_section}

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}

====USER_QUERY_MARKER====
"{query}"

BIRTH CHART DATA (Sidereal/Lahiri):
• Ascendant (Lagna): {chart_data.get('ascendant', {}).get('rashi', 'Not available')} ({chart_data.get('ascendant', {}).get('degrees', 0.0):.2f}°)
• Sun: {chart_data.get('planets', {}).get('Sun', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Sun', {}).get('house', '?')} ({chart_data.get('planets', {}).get('Sun', {}).get('nakshatra', 'Not available')})
• Moon: {chart_data.get('planets', {}).get('Moon', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Moon', {}).get('house', '?')} ({chart_data.get('planets', {}).get('Moon', {}).get('nakshatra', 'Not available')})
• Mars: {chart_data.get('planets', {}).get('Mars', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Mars', {}).get('house', '?')}
• Mercury: {chart_data.get('planets', {}).get('Mercury', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Mercury', {}).get('house', '?')}
• Jupiter: {chart_data.get('planets', {}).get('Jupiter', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Jupiter', {}).get('house', '?')}
• Venus: {chart_data.get('planets', {}).get('Venus', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Venus', {}).get('house', '?')}
• Saturn: {chart_data.get('planets', {}).get('Saturn', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Saturn', {}).get('house', '?')}
• Rahu: {chart_data.get('planets', {}).get('Rahu', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Rahu', {}).get('house', '?')}
• Ketu: {chart_data.get('planets', {}).get('Ketu', {}).get('rashi', 'Not available')} in House {chart_data.get('planets', {}).get('Ketu', {}).get('house', '?')}

{divisional_context}

VIMSHOTTARI DASHA CALCULATION (Transparent & Auditable):

Step 1 - Moon's Position at Birth:
• Moon Longitude: {dasha_data.get('calculation_details', {}).get('moon_longitude', 'Not available')}
• Moon Nakshatra: {dasha_data.get('calculation_details', {}).get('moon_nakshatra', 'Not available')}
• First Dasha Lord (Nakshatra Ruler): {dasha_data.get('calculation_details', {}).get('first_dasha_lord', 'Not available')}
• Balance of First Dasha at Birth: {dasha_data.get('calculation_details', {}).get('balance_at_birth_years', 'Not available')} years

Step 2 - Current Dasha Periods (Calculated from Moon Nakshatra):
• Mahadasha: {maha_planet} ({dasha_data.get('mahadasha', {}).get('start_date', 'Unknown')} to {dasha_data.get('mahadasha', {}).get('end_date', 'Unknown')})
• Antardasha: {antar_planet} ({dasha_data.get('antardasha', {}).get('start_date', 'Unknown')} to {dasha_data.get('antardasha', {}).get('end_date', 'Unknown')})
• Pratyantardasha: {dasha_data.get('pratyantardasha', {}).get('planet', 'Unknown')} ({dasha_data.get('pratyantardasha', {}).get('start_date', 'Unknown')} to {dasha_data.get('pratyantardasha', {}).get('end_date', 'Unknown')})
• Dasha Sequence: {dasha_sequence}

CRITICAL: These dates are CALCULATED using Swiss Ephemeris, not estimated. The calculation follows classical Vimshottari Dasha rules: Moon's Nakshatra → Nakshatra Lord → Dasha sequence. Use ONLY these exact dates for timing predictions.


CURRENT TRANSITS (as of {transit_date}):
• Jupiter: {jupiter_transit}
• Saturn: {saturn_transit}
• Mars: {mars_transit}

RELEVANT ASTROLOGICAL KNOWLEDGE FROM CLASSICAL TEXTS:
{context}

{instructions}"""
        
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
            "validation_disclaimer": None
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
    print("  1. Auto-loads calculation tools from src/tools/calculation_tools.py")
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