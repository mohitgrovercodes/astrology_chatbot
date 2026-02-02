"""
Enhanced LangGraph Orchestrator with REAL Calculation Integration.

✅ UPDATED: Now uses actual VedicEngine calculations (no placeholders!)

3-way routing:
1. CHITCHAT → Quick response
2. NEEDS_CALCULATION → Real birth chart calculation
3. NEEDS_RAG → Knowledge + Real chart data + Interpretation/Prediction
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
import operator
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# ✅ NEW: Import calculation tools
from src.tools.calculation_tools import get_calculation_tools


class NakshatraState(TypedDict):
    """Enhanced state with calculation results."""
    
    # Input
    query: str
    user_id: str
    conversation_history: List[Dict]
    
    # User context
    user_profile: Optional[Dict]
    authenticated: bool
    
    intent: Optional[str]  # CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG
    confidence: float
    intent_reasoning: str
    cached: bool
    
    # Calculation results (for PREDICTION flow)
    chart_data: Optional[Dict]  # Birth chart
    dasha_data: Optional[Dict]  # Current dashas
    transit_data: Optional[Dict]  # Current transits
    
    # RAG results
    knowledge_chunks: Optional[List]
    
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
        calculation_tools: Optional[Dict] = None,  # ✅ CHANGED: Now optional
        llm=None,
        mongodb_uri: Optional[str] = None
    ):
        """Initialize enhanced orchestrator."""
        self.intent_classifier = intent_classifier
        self.user_manager = user_manager
        self.hybrid_retriever = hybrid_retriever
        self.prompt_builder = prompt_builder
        
        # ✅ NEW: Auto-load calculation tools if not provided
        if calculation_tools is None:
            print("[LANGGRAPH] Loading calculation tools...")
            calculation_tools = get_calculation_tools()
            print(f"[LANGGRAPH] ✓ Loaded {len(calculation_tools)} calculation tools")
        
        self.calculation_tools = calculation_tools
        self.llm = llm
        
        self.graph = self._build_graph()
        
        print("[LANGGRAPH] [SUCCESS] Enhanced orchestrator initialized")
        print("[LANGGRAPH] Routes: CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG")
    
    def _build_graph(self) -> StateGraph:
        """Build enhanced graph with 3-way routing."""
        
        workflow = StateGraph(NakshatraState)
        
        # Nodes
        workflow.add_node("authenticate", self._authenticate_node)
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("handle_chitchat", self._handle_chitchat_node)
        workflow.add_node("handle_calculation", self._handle_calculation_node)
        workflow.add_node("handle_rag", self._handle_rag_node)
        workflow.add_node("format_response", self._format_response_node)
        
        # Entry point
        workflow.set_entry_point("authenticate")
        
        # Edges
        workflow.add_edge("authenticate", "classify_intent")
        
        # 3-way conditional routing
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "chitchat": "handle_chitchat",
                "calculation": "handle_calculation",
                "rag": "handle_rag",
                "error": END
            }
        )
        
        # All paths go to format_response
        workflow.add_edge("handle_chitchat", "format_response")
        workflow.add_edge("handle_calculation", "format_response")
        workflow.add_edge("handle_rag", "format_response")
        
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
            return state
        
        # Load profile
        user_profile = self.user_manager.get_user_profile(state['user_id'])
        
        if user_profile is None:
            print(f"[AUTH] [FAIL] Could not load profile")
            state['authenticated'] = False
            state['error'] = "Could not load user profile."
            return state
        
        # Success
        state['authenticated'] = True
        state['user_profile'] = user_profile.to_dict()
        
        # Update last active
        self.user_manager.update_last_active(state['user_id'])
        
        print(f"[AUTH] [SUCCESS] Authenticated: {user_profile.name}")
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
    
    def _handle_calculation_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3b: Handle pure calculation with REAL VedicEngine.
        ✅ UPDATED: Now uses actual calculation tools (no placeholders!)
        """
        print("[CALCULATION] Generating chart data")
        
        user_profile = state['user_profile']
        
        # Check if user has birth data
        if not user_profile.get('date_of_birth'):
            state['answer'] = "I don't have your birth details. Please update your profile with date, time, and place of birth."
            return state
        
        try:
            # ✅ NEW: Use REAL calculation tool
            print("[CALCULATION] Calling VedicEngine...")
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
            
            print(f"[CALCULATION] ✓ Chart calculated: Lagna={chart_data['lagna']}, Rashi={chart_data['moon_sign']}")
            
            # Format the response
            state['answer'] = f"""Here's your Vedic birth chart:

**Birth Details:**
• Date: {user_profile.get('date_of_birth')}
• Time: {user_profile.get('time_of_birth')}
• Place: {user_profile.get('place_of_birth')}

**Chart Essentials:**
• Lagna (Ascendant): {chart_data['lagna']}
• Moon Sign (Rashi): {chart_data['moon_sign']}
• Sun Sign: {chart_data['sun_sign']}
• Moon Nakshatra: {chart_data['moon_nakshatra']}

**Planetary Positions:**
"""
            
            # Add planet positions
            for planet_name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']:
                planet_data = chart_data['planets'][planet_name]
                state['answer'] += f"• {planet_name}: {planet_data['rashi']} (House {planet_data['house']})\n"
            
            state['answer'] += f"\n• Rahu: {chart_data['planets']['Rahu']['rashi']} (House {chart_data['planets']['Rahu']['house']})"
            state['answer'] += f"\n• Ketu: {chart_data['planets']['Ketu']['rashi']} (House {chart_data['planets']['Ketu']['house']})"
            
            state['answer'] += "\n\nWould you like me to interpret any specific aspect of your chart?"
            
            # Store chart data for potential follow-up questions
            state['chart_data'] = chart_data
            
        except Exception as e:
            print(f"[ERROR] Calculation failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error generating chart: {e}"
        
        return state
    
    def _handle_rag_node(self, state: NakshatraState) -> NakshatraState:
        """
        Node 3c: Handle RAG queries with REAL calculations for predictions.
        ✅ UPDATED: Now uses actual calculation tools (no placeholders!)
        
        Flow:
        1. Determine if calculation is needed (for prediction queries)
        2. Calculate if needed (REAL calculations now!)
        3. Retrieve relevant knowledge
        4. Synthesize personalized response
        """
        print("[RAG] Unified flow: Check Calc -> Retrieve -> Interpret")
        
        user_profile = state['user_profile']
        q = state['query'].lower().strip()
        
        # Determine if this RAG query is a "Prediction" (needs calculation)
        prediction_keywords = ['when', 'will', 'future', 'timing', 'time for', 'outcome']
        is_prediction = any(kw in q for kw in prediction_keywords) or 'my' in q
        
        try:
            # ✅ UPDATED: Step 1 - REAL Calculation (if it looks like a prediction query)
            if is_prediction and user_profile.get('date_of_birth'):
                print("[RAG] Step 1: Query looks personal/predictive. Calculating chart data...")
                
                if not state.get('chart_data'):
                    try:
                        # Calculate REAL birth chart
                        print("[RAG] Calling VedicEngine for birth chart...")
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
                            print(f"[RAG] ✓ Chart calculated: Lagna={chart_data['lagna']}, Rashi={chart_data['moon_sign']}")
                        else:
                            print(f"[RAG] ✗ Chart calculation failed: {chart_data['error']}")
                            state['chart_data'] = None
                        
                        # Calculate REAL current dasha
                        print("[RAG] Calling VedicEngine for dasha periods...")
                        dasha_tool = self.calculation_tools['current_dasha']
                        dasha_data = dasha_tool.invoke({
                            "date_of_birth": user_profile.get('date_of_birth'),
                            "time_of_birth": user_profile.get('time_of_birth'),
                            "latitude": user_profile.get('latitude'),
                            "longitude": user_profile.get('longitude')
                        })
                        
                        if "error" not in dasha_data:
                            state['dasha_data'] = dasha_data
                            print(f"[RAG] ✓ Dasha calculated: {dasha_data['dasha_sequence']}")
                        else:
                            print(f"[RAG] ✗ Dasha calculation failed: {dasha_data['error']}")
                            state['dasha_data'] = None
                        
                        # Calculate REAL current transits
                        print("[RAG] Calculating current transits...")
                        transit_tool = self.calculation_tools['current_transits']
                        transit_data = transit_tool.invoke({})
                        
                        if "error" not in transit_data:
                            state['transit_data'] = transit_data
                            print(f"[RAG] ✓ Transits calculated for {transit_data['date']}")
                        else:
                            print(f"[RAG] ✗ Transit calculation failed: {transit_data['error']}")
                            state['transit_data'] = None
                        
                    except Exception as e:
                        print(f"[RAG] ERROR during calculations: {e}")
                        import traceback
                        traceback.print_exc()
                        # Graceful fallback - continue without chart data
                        state['chart_data'] = None
                        state['dasha_data'] = None
                        state['transit_data'] = None
                
                if state.get('chart_data'):
                    print(f"[RAG] [CALC] Chart loaded for: {user_profile.get('name')}")
                else:
                    print(f"[RAG] [WARN] Proceeding without chart data")
            else:
                print("[RAG] Step 1: General query. Skipping specific calculations.")

            # Step 2: Retrieve Relevant Knowledge
            print("[RAG] Step 2: Retrieving astrological knowledge...")
            
            # Enhance query for better retrieval if we have chart data
            retrieval_query = state['query']
            if state.get('chart_data'):
                c = state['chart_data']
                retrieval_query += f" (Lagna: {c.get('lagna')}, Rashi: {c.get('moon_sign')})"

            knowledge_chunks = self.hybrid_retriever.retrieve(
                query=retrieval_query,
                intent="NEEDS_RAG",
                top_k=5
            )
            
            state['knowledge_chunks'] = knowledge_chunks
            print(f"[RAG] [SUCCESS] Retrieved {len(knowledge_chunks)} knowledge chunks")
            
            # Step 3: Build Prompt
            if is_prediction and state.get('chart_data'):
                prompt = self._build_prediction_prompt(
                    query=state['query'],
                    chart_data=state['chart_data'],
                    dasha_data=state.get('dasha_data', {}),
                    transit_data=state.get('transit_data', {}),
                    knowledge_chunks=knowledge_chunks,
                    user_profile=user_profile
                )
            else:
                prompt = self.prompt_builder.build_prompt(
                    query=state['query'],
                    intent="NEEDS_RAG",
                    user_profile=state['user_profile'],
                    knowledge_chunks=knowledge_chunks,
                    conversation_history=state.get('conversation_history', [])
                )
            
            # Step 4: Generate
            response = self.llm.invoke(prompt)
            state['answer'] = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[RAG] [SUCCESS] Generated response ({len(state['answer'])} chars)")
            
        except Exception as e:
            print(f"[ERROR] RAG path failed: {e}")
            import traceback
            traceback.print_exc()
            state['error'] = str(e)
            state['answer'] = f"Error during astrological analysis: {e}"
        
        return state
    
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
        user_profile: Dict
    ) -> str:
        """
        Build personalized prediction prompt with REAL chart context.
        ✅ UPDATED: Now uses rich data structure from VedicEngine
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
        
        # ✅ NEW: Enhanced prompt with rich chart data
        prompt = f"""You are an expert Vedic astrologer. Provide a personalized prediction based on the user's actual birth chart.

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

Provide a detailed, personalized prediction:"""
        
        return prompt
    
    def _route_by_intent(self, state: NakshatraState) -> str:
        """3-way routing based on intent."""
        
        if not state.get('authenticated'):
            return "error"
        
        intent = state.get('intent', 'NEEDS_RAG')
        
        if intent == "CHITCHAT":
            return "chitchat"
        elif intent == "NEEDS_CALCULATION":
            return "calculation"
        else:
            return "rag"
    
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
    print("✅ This orchestrator now uses REAL VedicEngine calculations!")
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