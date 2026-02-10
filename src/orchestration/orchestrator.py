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
from src.safety.constitution import get_constitution_injection # PHASE 10
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Tuple

# Types for state managementor
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# NEW: Import calculation tools
from src.tools.calculation_tools import get_calculation_tools, format_chart_for_llm

# PHASE 10.5: Import new safety framework
from src.safety import create_safety_classifier, get_template, get_disclaimer
from src.safety.input_validator import InputValidator
# PHASE 11: Semantic Routing
from src.routing import SemanticRouter

# PERSISTENCE & CACHING
from src.engines.vedic.vedic_engine import VedicEngine, VedicChart
import json


class NakshatraState(TypedDict):
    """Enhanced state with calculation results."""
    
    # Input
    query: str
    user_id: str
    conversation_history: List[Dict]
    
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


class EnhancedLangGraphOrchestrator:
    """
    Enhanced orchestrator with 3-way routing and REAL calculations.
    """
    
    def __init__(
        self,
        intent_classifier,
        user_manager,
        hybrid_retriever,
        prompt_builder,
        calculation_tools: Optional[Dict] = None,  # [DONE] CHANGED: Now optional
        llm=None,
        fast_llm=None  # NEW: Fast LLM for classification
    ):
        """Initialize enhanced orchestrator with dual LLM support."""
        self.intent_classifier = intent_classifier
        self.user_manager = user_manager
        self.hybrid_retriever = hybrid_retriever
        self.prompt_builder = prompt_builder
        
        # NEW: Auto-load calculation tools if not provided
        if calculation_tools is None:
            print("[LANGGRAPH] Loading calculation tools...")
            calculation_tools = get_calculation_tools()
            print(f"[LANGGRAPH] Loaded {len(calculation_tools)} calculation tools")
        
        self.calculation_tools = calculation_tools
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
            self.semantic_router.add_route(
                name="chitchat",
                examples=[
                    "hi", "hello", "hey", "namaste", "namaskaram", "vanakkam", "hola",
                    "good morning", "good evening", "good afternoon", "how are you",
                    "who are you", "what are you", "thanks", "thank you", "bye", "goodbye",
                    "wassup", "sup", "yo", "nice to meet you", "greetings"
                ],
                metadata={"type": "chitchat"}
            )
        
        self.graph = self._build_graph()
        
        print("[LANGGRAPH] [SUCCESS] Enhanced orchestrator initialized")
        print("[LANGGRAPH] Routes: CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY")
        print("[LANGGRAPH] Safety guardrails enabled (Phase 6)")
    
    def _build_graph(self) -> StateGraph:
        """Build enhanced graph with 4-way routing."""
        
        workflow = StateGraph(NakshatraState)
        
        # Nodes
        workflow.add_node("authenticate", self._authenticate_node)
        workflow.add_node("detect_language", self._detect_language_node)
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("handle_chitchat", self._handle_chitchat_node)
        workflow.add_node("handle_calculation_only", self._handle_calculation_only_node)
        workflow.add_node("handle_rag_with_calculation", self._handle_rag_with_calculation_node)
        workflow.add_node("handle_rag_only", self._handle_rag_only_node)
        workflow.add_node("validate_response", self._validate_response_node)  # PHASE 10: Validation
        workflow.add_node("format_response", self._format_response_node)
        
        # Entry point
        workflow.set_entry_point("authenticate")
        
        # Edges
        workflow.add_edge("authenticate", "detect_language")
        workflow.add_edge("detect_language", "classify_intent")
        
        # 4-way conditional routing
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "chitchat": "handle_chitchat",
                "calculation_only": "handle_calculation_only",
                "rag_with_calculation": "handle_rag_with_calculation",
                "rag_only": "handle_rag_only",
                "safety_block": "format_response",  # PHASE 10: Blocked requests go to format
                "error": END
            }
        )
        
        # RAG paths go to VALIDATION first
        workflow.add_edge("handle_rag_with_calculation", "validate_response")
        workflow.add_edge("handle_rag_only", "validate_response")
        
        # Validation goes to Format
        workflow.add_edge("validate_response", "format_response")
        
        # Direct paths (Skip validation for now)
        workflow.add_edge("handle_chitchat", "format_response")
        workflow.add_edge("handle_calculation_only", "format_response")
        
        # End
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def _authenticate_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1: Authenticate user."""
        # Check if profile is already provided (e.g., from external context)
        if state.get('user_profile'):
            print(f"[AUTH] Using provided user profile for: {state['user_id']}")
            state['authenticated'] = True
            return state
            
        print(f"[AUTH] Authenticating user: {state['user_id']}")
        
        # Check if user exists
        if not self.user_manager.user_exists(state['user_id']):
            print(f"[AUTH] [FAIL] User not found: {state['user_id']}")
            state['authenticated'] = False
            state['error'] = "User not found. Please register first."
            state['answer'] = state['error']
            return state
        
        # Load profile
        user_profile = self.user_manager.get_user_profile(state['user_id'])
        
        if user_profile is None:
            print(f"[AUTH] [FAIL] Could not load profile")
            state['authenticated'] = False
            state['error'] = "Could not load user profile."
            state['answer'] = state['error']
            return state
        
        # Success
        state['authenticated'] = True
        state['user_profile'] = user_profile.to_dict()
        
        # Update last active
        self.user_manager.update_last_active(state['user_id'])
        
        print(f"[AUTH] [SUCCESS] Authenticated: {user_profile.name}")
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
    
    def _classify_intent_node(self, state: NakshatraState) -> NakshatraState:
        """Node 2: Classify intent."""
        print(f"[INTENT] Classifying query: '{state['query'][:50]}...'")
        
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
                    print(f"[GUARD] 🚫 BLOCKING REQUEST: {safety_result.decision.category} ({safety_result.decision.reason})")
                    state['intent'] = 'safety_block'
                    state['answer'] = get_template(safety_result.get_template_key())
                    state['is_safe'] = False
                    state['confidence'] = safety_result.decision.confidence
                    return state
                
            # 2. REFRAME: Transform query and proceed
            if safety_result.decision.category == "REFRAME":
                print(f"[GUARD] 🔄 REFRAMING QUERY: {state['query']} -> {safety_result.processed_query}")
                state['original_query'] = state['query']
                state['query'] = safety_result.processed_query
                state['is_reframed'] = True
                # Continue process with better query
                
            # 3. CONDITIONAL: Mark for disclaimer (handled in format_response)
            if safety_result.decision.disclaimer_type:
                print(f"[GUARD] ⚠️ CONDITIONAL: Needs {safety_result.decision.disclaimer_type} disclaimer")
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
        """Node 3a: Handle conversational queries with multilingual support."""
        print(f"[CHITCHAT] Response for language: {state.get('detected_language', 'en')}")
        
        user_name = state['user_profile'].get('name', 'User')
        q = state['query'].lower().strip()
        lang = state.get('detected_language', 'en')
        
        # Fast path for English common chitchat
        if lang == 'en':
            if any(word in q for word in ['hi', 'hello', 'hey', 'namaste']):
                state['answer'] = f"Namaste, {user_name}! I'm NakshatraAI, your professional astrology consultant. How may I assist you today?"
                return state
            elif any(word in q for word in ['who are you', 'what are you']):
                state['answer'] = f"I'm NakshatraAI, a professional Vedic astrology consultant. I can analyze your birth chart, predict timing for life events, and provide guidance based on classical astrological principles."
                return state
            elif any(word in q for word in ['thanks', 'thank you']):
                state['answer'] = f"You're welcome, {user_name}! Feel free to ask anything about your chart or astrological concepts."
                return state

        # Multilingual/Complex path: Use fast LLM with persona
        try:
            from src.ai.personas import get_persona
            # Always default to 'vedic' for persona tone, or use user profile preference
            persona_type = state['user_profile'].get('preferred_system', 'vedic')
            persona = get_persona(persona_type)
            
            system_prompt = persona.get_system_prompt(
                user_name=user_name,
                language=lang
            )
            
            # Map language code to descriptive name
            loc_manager = get_localization_manager()
            lang_name = loc_manager.get_language_name(lang)
            
            if '-lat' in lang:
                script_instruction = f"IMPORTANT: You must writing in {lang_name} using ROMAN ALPHABET (English Script). Do NOT use native script."
            else:
                script_instruction = f"Respond entirely in {lang_name} (Native Script)."
            
            prompt = f"""{system_prompt}
            
User: "{state['query']}"

INSTRUCTIONS:
1. Provide a warm, empathetic, professional response.
2. If the user greets, greet back warmly.
3. If the question is outside astrology, politely explain your scope.
4. {script_instruction}
5. Keep it brief (under 50 words).

Response:"""
            
            llm_response = self.fast_llm.invoke(prompt)
            state['answer'] = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
        except Exception as e:
            print(f"[CHITCHAT] Error generating response: {e}")
            state['answer'] = f"Namaste, {user_name}! How can I help you with your astrology chart?"
            
        return state
    
    def _get_or_calculate_chart(self, user_id: str, user_profile: Dict) -> Tuple[Optional[Dict], Optional[VedicChart]]:
        """
        Helper to get chart data, prioritizing the cache.
        Returns (tool_dict, full_chart_object).
        """
        cached_json = user_profile.get('birth_chart_cache')
        
        if cached_json:
            try:
                print(f"[CACHE] Found cached chart for {user_id}. Deserializing...")
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
            
            # Save to cache if db is available
            if self.user_manager.db:
                chart_json = json.dumps(full_chart.to_dict())
                self.user_manager.db.update_user_chart(user_id, chart_json)
                print(f"[CACHE] Chart saved to database for {user_id}")
            
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
        
        # Check if user has birth data
        if not user_profile.get('date_of_birth'):
            state['answer'] = "I don't have your birth details. Please update your profile with date, time, and place of birth."
            return state
        
        try:
            # Calculate or load from cache
            _, full_chart = self._get_or_calculate_chart(state['user_id'], user_profile)
            
            if not full_chart:
                state['answer'] = "Could not generate or load your birth chart. Please check your birth details."
                return state
            
            # Use formatting helper (unified with the tool)
            chart_data = format_chart_for_llm(full_chart)
            
            print(f"[CALCULATION_ONLY] Chart: Lagna={chart_data['lagna']}, Rashi={chart_data['moon_sign']}")
            
            # Use LLM to extract only what was asked for
            extraction_prompt = f"""You are a data extraction assistant. The user asked: "{state['query']}"

USER'S BIRTH DETAILS:
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}

COMPLETE BIRTH CHART DATA:
• Lagna (Ascendant): {chart_data['lagna']}
• Moon Sign (Rashi): {chart_data['moon_sign']}
• Sun Sign: {chart_data['sun_sign']}
• Moon Nakshatra: {chart_data['moon_nakshatra']}

Planetary Positions:
• Sun: {chart_data['planets']['Sun']['rashi']} (House {chart_data['planets']['Sun']['house']})
• Moon: {chart_data['planets']['Moon']['rashi']} (House {chart_data['planets']['Moon']['house']})
• Mars: {chart_data['planets']['Mars']['rashi']} (House {chart_data['planets']['Mars']['house']})
• Mercury: {chart_data['planets']['Mercury']['rashi']} (House {chart_data['planets']['Mercury']['house']})
• Jupiter: {chart_data['planets']['Jupiter']['rashi']} (House {chart_data['planets']['Jupiter']['house']})
• Venus: {chart_data['planets']['Venus']['rashi']} (House {chart_data['planets']['Venus']['house']})
• Saturn: {chart_data['planets']['Saturn']['rashi']} (House {chart_data['planets']['Saturn']['house']})
• Rahu: {chart_data['planets']['Rahu']['rashi']} (House {chart_data['planets']['Rahu']['house']})
• Ketu: {chart_data['planets']['Ketu']['rashi']} (House {chart_data['planets']['Ketu']['house']})

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
            
        except Exception as e:
            print(f"[ERROR] Calculation failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error generating chart: {e}"
        
        return state
    
    def _handle_rag_with_calculation_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3c: RAG_WITH_CALCULATION - Personalized predictions.
        Uses VedicEngine + RAG + LLM interpretation.
        
        Flow:
        1. Analyze query for sensitive content (PHASE 6 safety)
        2. Calculate birth chart, dashas, and transits
        3. Retrieve relevant knowledge from vector DB
        4. Synthesize personalized response with LLM
        """
        print("[RAG_WITH_CALCULATION] Personalized prediction flow")
        
        # PHASE 10.5: Safety handled upstream in _classify_intent_node
        # Legacy Phase 6 safety check removed.
        
        
        user_profile = state['user_profile']
        
        try:
            # Step 1: Calculate user's chart (always needed for personalized predictions)
            if user_profile.get('date_of_birth'):
                print("[RAG_WITH_CALCULATION] Step 1: Calculating user's chart...")
                
                if not state.get('chart_data'):
                    try:
                        # Calculate or load from cache
                        _, full_chart = self._get_or_calculate_chart(state['user_id'], user_profile)
                        
                        if full_chart:
                            # Use formatting helper
                            state['chart_data'] = format_chart_for_llm(full_chart)
                            print(f"[RAG_WITH_CALCULATION] Chart: Lagna={state['chart_data']['lagna']}, Rashi={state['chart_data']['moon_sign']}")
                        
                        # Calculate current dasha
                        dasha_tool = self.calculation_tools['current_dasha']
                        dasha_data = dasha_tool.invoke({
                            "date_of_birth": user_profile.get('date_of_birth'),
                            "time_of_birth": user_profile.get('time_of_birth'),
                            "latitude": user_profile.get('latitude'),
                            "longitude": user_profile.get('longitude')
                        })
                        
                        if "error" not in dasha_data:
                            state['dasha_data'] = dasha_data
                            print(f"[RAG_WITH_CALCULATION] Dasha: {dasha_data['dasha_sequence']}")
                        
                        # Calculate current transits
                        transit_tool = self.calculation_tools['current_transits']
                        transit_data = transit_tool.invoke({})
                        
                        if "error" not in transit_data:
                            state['transit_data'] = transit_data
                            print(f"[RAG_WITH_CALCULATION] Transits for {transit_data['date']}")
                        
                    except Exception as e:
                        print(f"[RAG_WITH_CALCULATION] Calculation error: {e}")
                        # Continue without chart data
            else:
                print("[RAG_WITH_CALCULATION] No birth data - proceeding without chart")

            # Step 2: Retrieve Relevant Knowledge
            print("[RAG_WITH_CALCULATION] Step 2: Retrieving knowledge...")
            
            # Enhance query for better retrieval if we have chart data
            retrieval_query = state['query']
            if state.get('chart_data'):
                c = state['chart_data']
                retrieval_query += f" (Lagna: {c.get('lagna')}, Rashi: {c.get('moon_sign')})"

            knowledge_chunks = self.hybrid_retriever.retrieve(
                query=retrieval_query,
                intent="RAG_WITH_CALCULATION",
                top_k=5,
                language=state.get('detected_language', 'en')
            )
            
            state['knowledge_chunks'] = knowledge_chunks
            print(f"[RAG_WITH_CALCULATION] Retrieved {len(knowledge_chunks)} chunks")
            
            # Step 3: Build Prompt (always use prediction prompt with chart data)
            if state.get('chart_data'):
                prompt = self._build_prediction_prompt(
                    query=state['query'],
                    chart_data=state['chart_data'],
                    dasha_data=state.get('dasha_data', {}),
                    transit_data=state.get('transit_data', {}),
                    knowledge_chunks=knowledge_chunks,
                    user_profile=user_profile,
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
            
            # Step 4: Generate
            response = self.llm.invoke(prompt)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[RAG_WITH_CALCULATION] Generated response ({len(state['answer'])} chars)")
            
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
            # Step 1: Retrieve knowledge from vector DB
            print("[RAG_ONLY] Retrieving astrological knowledge...")
            
            knowledge_chunks = self.hybrid_retriever.retrieve(
                query=state['query'],
                intent="RAG_ONLY",
                top_k=5,
                language=state.get('detected_language', 'en')
            )
            
            state['knowledge_chunks'] = knowledge_chunks
            print(f"[RAG_ONLY] Retrieved {len(knowledge_chunks)} knowledge chunks")
            
            # Step 2: Build prompt for general theory
            prompt = self._build_theory_prompt(
                query=state['query'],
                knowledge_chunks=knowledge_chunks,
                user_profile=state['user_profile'],
                language=state.get('detected_language', 'en')
            )
            
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
            response = self.llm.invoke(prompt)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[RAG_ONLY] Generated grounded response ({len(state['answer'])} chars)")
            
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
                language=language
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
        
        # Detect if user wants detailed explanation
        wants_detail = self._user_wants_detail(query)
        
        if wants_detail:
            # User asked for details - provide comprehensive explanation
            instructions = f"""INSTRUCTIONS:
1. **GROUNDING**: Base answer ONLY on the provided texts above
2. **DETAILED EXPLANATION**: Provide a comprehensive, detailed explanation with examples
3. **CITE BOOK NAMES**: Only cite books that appear in the sources above
4. **FORBIDDEN**: Do NOT cite any book unless it appears in the retrieved sources
5. Respond entirely in {lang_name}
6. At the end, list the book names from the retrieved sources

Provide a detailed, thorough explanation:"""
        else:
            # Default: Brief response
            instructions = f"""🚨 CRITICAL INSTRUCTIONS - MUST FOLLOW:
1. **MAXIMUM 100-150 WORDS** - Your ENTIRE response must be between 100-150 words maximum, nothing more
2. **GROUNDING**: Base answer ONLY on the provided texts above - DO NOT mention any book names unless they appear in the sources above
3. **CITE BOOK NAMES FROM SOURCES**: Only cite books that are explicitly shown in the knowledge above
4. **FORBIDDEN**: Do NOT cite Brihat Parasara Hora Shastra, Jataka Parijata, Uttara Kalamrita, or any other text UNLESS it appears in the sources above
5. **FORMAT**: Write 2-3 concise sentences covering the key points
6. Respond entirely in {lang_name}
7. At the end: "**Sources:** [book names if any, otherwise skip this line]"

✅ CORRECT FORMAT (THIS IS YOUR TARGET):
[2-3 concise sentences with key information, 100-150 words total]

**Sources:** [Only books from retrieved sources, if any]

❌ DO NOT write long paragraphs, detailed explanations, bullet lists, or multiple sections
❌ DO NOT exceed 150 words
❌ DO NOT cite books not in the retrieved sources
❌ User can ask "tell me more" if they want elaboration

Provide brief 100-150 word answer:"""
        
        prompt = f"""You are an expert Vedic astrologer explaining astrological concepts.

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth', 'Unknown')}
• Time of Birth: {user_profile.get('time_of_birth', 'Unknown')}
• Place of Birth: {user_profile.get('place_of_birth', 'Unknown')}

USER'S QUESTION: "{query}"

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
        Detect if user is asking for more detail/elaboration.
        
        Returns:
            True if query contains phrases requesting more information
        """
        query_lower = query.lower()
        detail_phrases = [
            'tell me more',
            'more detail',
            'more information',
            'elaborate',
            'explain in detail',
            'explain more',
            'detailed explanation',
            'full explanation',
            'complete explanation',
            'विस्तार से',  # Hindi: in detail
            'और बताओ',    # Hindi: tell more
            'aur batao',   # Hinglish: tell more
            'detail me',
            'details',
        ]
        
        return any(phrase in query_lower for phrase in detail_phrases)
    
    def _build_prediction_prompt(
        self,
        query: str,
        chart_data: Dict,
        dasha_data: Dict,
        transit_data: Dict,
        knowledge_chunks: List,
        user_profile: Dict,
        language: str = "hi-lat"
    ) -> str:
        """
        Build personalized prediction prompt with REAL chart context.
        [DONE] UPDATED: Now uses rich data structure from VedicEngine
        [DONE] UPDATED: Greeting suppression and Two-Tier response flow
        """
        
        # Check if conversation is ongoing (to suppress greetings)
        # We need to know if there's history passed to the orchestrator, 
        # but this method doesn't receive full history. 
        # Ideally, we'd pass a flag. For now, we'll assume if this method is called,
        # it's part of a flow that might have history.
        # But wait, self.process_query passes history to graph, but graph nodes might not pass it here?
        # Actually, let's just add the instruction conditionally if we can determine context.
        # Or better yet, just add a generic instruction to the system prompt if not first turn.
        # Since we don't have history length here easily without changing signature, 
        # let's add it to the BASE INSTRUCTIONS for all turns except maybe the very first?
        # A safer bet is to change the signature to accept `is_first_turn` or `conversation_history`.
        # Let's add `conversation_history` to the signature.
    
    def _build_prediction_prompt(
        self,
        query: str,
        chart_data: Dict,
        dasha_data: Dict,
        transit_data: Dict,
        knowledge_chunks: List,
        user_profile: Dict,
        conversation_history: List = None,  # Added argument
        language: str = "hi-lat"
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
                language=language
            )
        except:
            system_prompt = "You are an expert Vedic astrologer explaining predictions."
        
        # PHASE 10: Inject Constitution
        constitution = get_constitution_injection()
        system_prompt = f"{system_prompt}\n\n{constitution}"

        # GREETING CONTROL: Suppress greetings if conversation is ongoing
        if conversation_history and len(conversation_history) > 0:
            system_prompt += "\n\nNOTE: This is an ongoing conversation. Do NOT start with greetings like 'Namaste', 'Hello', or 'Hari Om'. Get straight to the answer."
        
        # Map language code to descriptive name for LLM
        loc_manager = get_localization_manager()
        lang_name = loc_manager.get_language_name(language)
        if '-lat' in language:
            script_instruction = f"IMPORTANT: You must writing in {lang_name} using ROMAN ALPHABET (English Script). Do NOT use native script."
        else:
            script_instruction = f"Respond entirely in {lang_name} (Native Script)."
            
        # Detect if user wants detailed explanation
        wants_detail = self._user_wants_detail(query)
        
        if wants_detail:
            # User asked for details - provide comprehensive prediction
            instructions = f"""INSTRUCTIONS:
1. **DETAILED PREDICTION**: Provide a comprehensive, detailed prediction with reasoning
2. **SPECIFIC TO THEIR CHART**: Use actual placements (houses, signs, planets) from the chart data above
3. **TIMING**: Include approximate timeframes based on dasha periods provided
4. **GROUNDING**: Base on chart data + classical texts above - Do NOT cite books unless they appear in sources
5. **FORBIDDEN**: Do NOT cite any book unless it appears in the retrieved sources above
6. {script_instruction}
7. At the end, list the book names from retrieved sources (if any)

Provide a detailed, comprehensive prediction:"""
        else:
            # Default: Brief response with follow-up offer
            instructions = f"""🚨 CRITICAL INSTRUCTIONS - BRIEF RESPONSE MODE:
1. **CONCISE ANSWER**: Provide a direct, astrological answer in 2-3 sentences.
2. **KEY FACTORS**: Mention ONLY the most important chart factor (e.g., "Due to Jupiter in your 7th house...").
3. **NO FLUFF**: Do not write long introductions or general philosophy.
4. **SOURCES**: Cite sources ONLY if used.
5. {script_instruction}
6. **MANDATORY ENDING**: You MUST end your response by asking: "Would you like a detailed explanation of the planetary positions and reasoning?" (in the target language).

✅ CORRECT FORMAT:
[Direct answer + key astrological reason]. [Timing if relevant].

SOURCES: [Book Name] (Optional)

[Question asking if user wants detailed breakdown]

❌ DO NOT write long paragraphs
❌ DO NOT list all planetary positions
❌ DO NOT say greetings
❌ User can say "yes" or "explian" to get the full details you skipped.

Provide brief response:"""

        prompt = f"""{system_prompt}

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}

USER'S QUERY: "{query}"

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
        user_profile_override: Optional[Dict] = None
    ) -> Dict:
        """Process query through enhanced orchestrator."""
        start_time = datetime.now()
        
        initial_state: NakshatraState = {
            "query": query,
            "user_id": user_id,
            "conversation_history": conversation_history or [],
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
            "is_reframed": False
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
        conversation_history: Optional[List[Dict]] = None
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
            "conversation_history": conversation_history or [],
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
    intent_classifier,
    user_manager,
    hybrid_retriever,
    prompt_builder,
    calculation_tools=None,
    llm=None,
    fast_llm=None  # NEW
):
    """
    Factory function to create an EnhancedLangGraphOrchestrator.
    
    This is a convenience function for tests and external code.
    """
    return EnhancedLangGraphOrchestrator(
        intent_classifier=intent_classifier,
        user_manager=user_manager,
        hybrid_retriever=hybrid_retriever,
        prompt_builder=prompt_builder,
        calculation_tools=calculation_tools,
        llm=llm,
        fast_llm=fast_llm  # NEW
    )