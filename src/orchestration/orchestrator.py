"""
Enhanced LangGraph Orchestrator with REAL Calculation Integration.

UPDATED: Now uses actual VedicEngine calculations (no placeholders!)

3-way routing:
1. CHITCHAT -> Quick response
2. NEEDS_CALCULATION -> Real birth chart calculation
3. NEEDS_RAG -> Knowledge + Real chart data + Interpretation/Prediction
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
import operator
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# NEW: Import calculation tools
from src.tools.calculation_tools import get_calculation_tools

# PHASE 6: Import safety module
from src.safety.guardrails import QueryAnalyzer, ResponseEnhancer
from src.safety.input_validator import InputValidator


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
    
    # Calculation results (for PREDICTION flow)
    chart_data: Optional[Dict]  # Birth chart
    dasha_data: Optional[Dict]  # Current dashas
    transit_data: Optional[Dict]  # Current transits
    
    # RAG results
    knowledge_chunks: Optional[List]
    
    # PHASE 6: Safety analysis
    query_analysis: Optional[Dict]  # Sensitivity analysis from QueryAnalyzer
    
    # Response
    answer: str
    error: Optional[str]
    processing_time: float
    
    messages: Annotated[List, operator.add]


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
        mongodb_uri: Optional[str] = None
    ):
        """Initialize enhanced orchestrator."""
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
        self.llm = llm
        
        # [DONE] Connect LLM to intent classifier for accurate classification
        if hasattr(self.intent_classifier, 'set_llm') and llm is not None:
            self.intent_classifier.set_llm(llm)
            print("[LANGGRAPH] LLM connected to intent classifier")
        
        # PHASE 6: Initialize safety components
        self.query_analyzer = QueryAnalyzer()
        self.response_enhancer = ResponseEnhancer()
        self.input_validator = InputValidator()
        
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
                "error": END
            }
        )
        
        # All paths go to format_response
        workflow.add_edge("handle_chitchat", "format_response")
        workflow.add_edge("handle_calculation_only", "format_response")
        workflow.add_edge("handle_rag_with_calculation", "format_response")
        workflow.add_edge("handle_rag_only", "format_response")
        
        # End
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def _authenticate_node(self, state: NakshatraState) -> NakshatraState:
        """Node 1: Authenticate user."""
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
        """Node 1.5: Detect query language."""
        query = state['query']
        print(f"[LANG] Detecting language for: '{query[:30]}...'")
        
        # Use LLM for robust detection (handles Hinglish/Tamilish better than regex)
        detection_prompt = f"""Identify the language of the following text. 
Return ONLY the ISO 639-1 code (e.g., 'en', 'hi', 'ta').
If it's multi-lingual (like Hinglish), return the primary language or 'hi'.
Text: "{query}"
Language Code:"""
        
        try:
            response = self.llm.invoke(detection_prompt)
            lang = response.content.strip().lower()[:2] if hasattr(response, 'content') else str(response).strip().lower()[:2]
            
            # Support known codes, default to 'en'
            if lang not in ['en', 'hi', 'ta', 'te', 'mr', 'bn', 'gu', 'kn', 'ml']:
                lang = 'en'
                
            state['detected_language'] = lang
            state['original_query'] = query
            print(f"[LANG] Detected: {lang}")
        except Exception as e:
            print(f"[LANG] Detection error: {e}")
            state['detected_language'] = 'en'
            state['original_query'] = query
            
        return state
    
    def _classify_intent_node(self, state: NakshatraState) -> NakshatraState:
        """Node 2: Classify intent."""
        print(f"[INTENT] Classifying query: '{state['query'][:50]}...'")
        
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
        """Node 3a: Handle conversational queries."""
        print("[CHITCHAT] Quick response")
        
        user_name = state['user_profile'].get('name', 'User')
        q = state['query'].lower().strip()
        
        # Simple pattern matching for common chitchat
        if any(word in q for word in ['hi', 'hello', 'hey', 'namaste']):
            state['answer'] = f"Namaste, {user_name}! I'm NakshatraAI, your professional astrology consultant. How may I assist you today?"
        elif any(word in q for word in ['who are you', 'what are you']):
            state['answer'] = f"I'm NakshatraAI, a professional Vedic astrology consultant. I can analyze your birth chart, predict timing for life events, and provide guidance based on classical astrological principles."
        elif any(word in q for word in ['thanks', 'thank you']):
            state['answer'] = f"You're welcome, {user_name}! Feel free to ask anything about your chart or astrological concepts."
        else:
            state['answer'] = f"Hello {user_name}! I'm here to help with astrological guidance. What would you like to know?"
        
        return state
    
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
            # Calculate birth chart
            print("[CALCULATION_ONLY] Calling VedicEngine...")
            chart_tool = self.calculation_tools['vedic_birth_chart']
            chart_data = chart_tool.invoke({
                "date_of_birth": user_profile.get('date_of_birth'),
                "time_of_birth": user_profile.get('time_of_birth'),
                "latitude": user_profile.get('latitude'),
                "longitude": user_profile.get('longitude'),
                "timezone": user_profile.get('timezone', 'Asia/Kolkata')
            })
            
            # Check for errors
            if "error" in chart_data:
                state['answer'] = f"Error calculating chart: {chart_data['error']}"
                state['error'] = chart_data['error']
                return state
            
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
        
        # PHASE 6: Analyze query for sensitive content
        query_analysis = self.query_analyzer.analyze(state['query'])
        state['query_analysis'] = {
            'category': query_analysis.category.value,
            'sensitivity_level': query_analysis.sensitivity_level,
            'handling_strategy': query_analysis.handling_strategy.value,
            'requires_disclaimer': query_analysis.requires_disclaimer,
            'clarifying_question': query_analysis.clarifying_question,
            'positive_redirect': query_analysis.positive_redirect
        }
        
        print(f"[SAFETY] Category: {query_analysis.category.value}, "
              f"Sensitivity: {query_analysis.sensitivity_level:.2f}, "
              f"Strategy: {query_analysis.handling_strategy.value}")
        
        # Check if we should ask clarifying question first (C in C->B->A)
        should_clarify, clarifying_q = self.response_enhancer.should_ask_clarification(query_analysis)
        if should_clarify and clarifying_q:
            print(f"[SAFETY] High sensitivity detected - asking clarifying question first")
            state['answer'] = clarifying_q
            return state
        
        user_profile = state['user_profile']
        
        try:
            # Step 1: Calculate user's chart (always needed for personalized predictions)
            if user_profile.get('date_of_birth'):
                print("[RAG_WITH_CALCULATION] Step 1: Calculating user's chart...")
                
                if not state.get('chart_data'):
                    try:
                        # Calculate birth chart
                        chart_tool = self.calculation_tools['vedic_birth_chart']
                        chart_data = chart_tool.invoke({
                            "date_of_birth": user_profile.get('date_of_birth'),
                            "time_of_birth": user_profile.get('time_of_birth'),
                            "latitude": user_profile.get('latitude'),
                            "longitude": user_profile.get('longitude'),
                            "timezone": user_profile.get('timezone', 'Asia/Kolkata')
                        })
                        
                        if "error" not in chart_data:
                            state['chart_data'] = chart_data
                            print(f"[RAG_WITH_CALCULATION] Chart: Lagna={chart_data['lagna']}, Rashi={chart_data['moon_sign']}")
                        
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
            
            # Step 3: Generate response with LLM
            response = self.llm.invoke(prompt)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[RAG_ONLY] Generated response ({len(state['answer'])} chars)")
            
        except Exception as e:
            print(f"[ERROR] RAG_ONLY path failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error during theory explanation: {e}"
        
        return state
    
    def _build_theory_prompt(self, query: str, knowledge_chunks: list, user_profile: dict, language: str = "en") -> str:
        """Build prompt for general astrology theory explanations."""
        
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
        
        # Format knowledge context
        context = "\n\n".join([
            f"Source: {chunk.metadata.get('source', 'Unknown') if hasattr(chunk, 'metadata') else 'Unknown'}\n{chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)}"
            for chunk in knowledge_chunks[:4]
        ]) if knowledge_chunks else "No specific texts retrieved."
        
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

INSTRUCTIONS:
1. Provide a clear, educational explanation of the astrological concept
2. Use classical Vedic astrology principles
3. Include practical examples where helpful
4. Reference the classical texts when possible
5. Keep the tone professional but accessible
6. This is a GENERAL explanation, not specific to any person's chart
7. Respond entirely in {language}

Provide a detailed explanation:"""
        
        return prompt
    
    def _format_response_node(self, state: NakshatraState) -> NakshatraState:
        """Node 4: Format final response."""
        
        if not state.get('error'):
            intent = state.get('intent', 'UNKNOWN')
            cache = "CACHED" if state.get('cached', False) else "LLM"
            state['answer'] += f"\n\n[Intent: {intent}, {cache}]"
        
        return state
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _build_prediction_prompt(
        self,
        query: str,
        chart_data: Dict,
        dasha_data: Dict,
        transit_data: Dict,
        knowledge_chunks: List,
        user_profile: Dict,
        language: str = "en"
    ) -> str:
        """
        Build personalized prediction prompt with REAL chart context.
        [DONE] UPDATED: Now uses rich data structure from VedicEngine
        """
        
        # Format knowledge context
        context = "\n\n".join([
            f"Source: {chunk.get('source', 'Unknown')}\n{chunk.get('content', '')}"
            for chunk in knowledge_chunks[:3]
        ]) if knowledge_chunks else "No specific texts retrieved."
        
        # Extract dasha info safely
        maha_planet = dasha_data.get('mahadasha', {}).get('planet', 'Unknown')
        antar_planet = dasha_data.get('antardasha', {}).get('planet', 'Unknown')
        dasha_sequence = dasha_data.get('dasha_sequence', f"{maha_planet}/{antar_planet}")
        
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
            system_prompt = "You are an expert Vedic astrologer."

        # NEW: Enhanced prompt with rich chart data
        prompt = f"""{system_prompt}

USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth')}
• Time of Birth: {user_profile.get('time_of_birth')}
• Place of Birth: {user_profile.get('place_of_birth')}

USER'S QUERY: "{query}"

USER'S COMPLETE BIRTH CHART:
• Lagna (Ascendant): {chart_data.get('lagna')}
• Moon Sign (Rashi): {chart_data.get('moon_sign')}
• Sun Sign: {chart_data.get('sun_sign')}
• Moon Nakshatra: {chart_data.get('moon_nakshatra')}

KEY PLANETARY POSITIONS:
• Sun: {chart_data['planets']['Sun']['rashi']} in House {chart_data['planets']['Sun']['house']} ({chart_data['planets']['Sun']['nakshatra']})
• Moon: {chart_data['planets']['Moon']['rashi']} in House {chart_data['planets']['Moon']['house']} ({chart_data['planets']['Moon']['nakshatra']})
• Mars: {chart_data['planets']['Mars']['rashi']} in House {chart_data['planets']['Mars']['house']}
• Mercury: {chart_data['planets']['Mercury']['rashi']} in House {chart_data['planets']['Mercury']['house']}
• Jupiter: {chart_data['planets']['Jupiter']['rashi']} in House {chart_data['planets']['Jupiter']['house']}
• Venus: {chart_data['planets']['Venus']['rashi']} in House {chart_data['planets']['Venus']['house']}
• Saturn: {chart_data['planets']['Saturn']['rashi']} in House {chart_data['planets']['Saturn']['house']}
• Rahu: {chart_data['planets']['Rahu']['rashi']} in House {chart_data['planets']['Rahu']['house']}
• Ketu: {chart_data['planets']['Ketu']['rashi']} in House {chart_data['planets']['Ketu']['house']}

CURRENT VIMSHOTTARI DASHA PERIODS:
• Mahadasha: {maha_planet}
• Antardasha: {antar_planet}
• Dasha Sequence: {dasha_sequence}

CURRENT TRANSITS (as of {transit_date}):
• Jupiter: {jupiter_transit}
• Saturn: {saturn_transit}
• Mars: {mars_transit}

RELEVANT ASTROLOGICAL KNOWLEDGE FROM CLASSICAL TEXTS:
{context}

INSTRUCTIONS:
1. Analyze the user's SPECIFIC chart placements (not generic interpretations)
2. Consider the current dasha period and its relationship with natal chart
3. Factor in current transits and their impact on natal positions
4. Use classical astrological principles from the provided context
5. Provide a PERSONALIZED prediction with timing based on dasha/transits
6. Be specific about THEIR chart - mention actual signs, houses, and planets
7. If timing is relevant, provide approximate time frames based on dasha periods

Provide a detailed, personalized prediction in {language}:"""
        
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
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """Process query through enhanced orchestrator."""
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
            "detected_language": "en",
            "original_query": query,
            "chart_data": None,
            "dasha_data": None,
            "transit_data": None,
            "knowledge_chunks": None,
            "answer": "",
            "error": None,
            "processing_time": 0.0,
            "messages": []
        }
        
        # Run through graph
        final_state = self.graph.invoke(initial_state)
        
        # Calculate processing time
        final_state['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        return final_state


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
    mongodb_uri=None
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
        mongodb_uri=mongodb_uri
    )