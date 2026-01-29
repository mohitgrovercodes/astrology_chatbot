"""
LangGraph Orchestrator for Astrology AI Chatbot.

Coordinates between calculation tools and RAG engine to provide
intelligent routing and response synthesis.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import calculation tools
from calculation_tools import (
    calculate_vedic_birth_chart,
    calculate_western_birth_chart,
    calculate_vedic_transits,
    classify_astrology_query,
    extract_birth_data_from_query,
)

# Import RAG engine
try:
    from rag_engine_phase4 import RAGEngine, RAGResponse
    RAG_AVAILABLE = True
except ImportError:
    print("[WARN] RAG engine not available")
    RAG_AVAILABLE = False


# =============================================================================
# STATE DEFINITION
# =============================================================================

class ConversationState(TypedDict):
    """
    State maintained throughout the conversation flow.
    
    This state is passed between nodes and updated at each step.
    """
    # Input
    query: str
    user_id: Optional[str]
    conversation_history: List[Dict[str, str]]
    
    # Classification
    intent_type: Optional[str]  # 'calculation', 'interpretation', 'chitchat', 'blocked'
    astro_system: Optional[str]  # 'vedic', 'western'
    calculation_type: Optional[str]  # 'birth_chart', 'transits', 'dasha'
    
    # Birth data (if calculation)
    birth_data: Optional[Dict[str, Any]]
    birth_data_complete: bool
    missing_fields: List[str]
    
    # Execution results
    calculation_result: Optional[Dict[str, Any]]
    rag_result: Optional[Dict[str, Any]]
    
    # Safety
    is_blocked: bool
    block_reason: Optional[str]
    
    # Output
    final_answer: str
    requires_followup: bool
    followup_question: Optional[str]
    
    # Metadata
    processing_path: List[str]  # Track which nodes were executed
    error: Optional[str]


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

def classify_intent_node(state: ConversationState) -> ConversationState:
    """
    Node 1: Classify user intent.
    
    Determines if query is:
    - Calculation (requires birth data & computation)
    - Interpretation (requires RAG/LLM only)
    - Chitchat (greeting, thanks, etc.)
    - Blocked (harmful content)
    """
    query = state["query"]
    
    # Use classification tool
    classification = classify_astrology_query.invoke({"query": query})
    
    state["intent_type"] = classification["type"]
    state["astro_system"] = classification.get("system", "vedic")
    state["calculation_type"] = classification.get("calculation_type")
    state["is_blocked"] = classification["type"] == "blocked"
    
    # Update processing path
    state["processing_path"] = state.get("processing_path", [])
    state["processing_path"].append("classify_intent")
    
    print(f"[CLASSIFY] Intent: {state['intent_type']}, System: {state['astro_system']}")
    
    return state


def safety_check_node(state: ConversationState) -> ConversationState:
    """
    Node 2: Safety and ethics check.
    
    Blocks queries about:
    - Death timing predictions
    - Medical diagnosis
    - Gambling/lottery numbers
    - Legal advice
    """
    if state["is_blocked"]:
        state["block_reason"] = "This query involves predictions that astrology ethics discourage."
        state["final_answer"] = """I appreciate your question, but I must respectfully decline to answer queries about:

• Specific death timing predictions
• Medical diagnosis or treatment
• Gambling or lottery predictions
• Legal advice or court case outcomes

These topics fall outside the ethical boundaries of astrological consultation. 

However, I'd be happy to help with:
• Understanding planetary influences on health tendencies (not diagnosis)
• Timing for new ventures or important decisions
• Character analysis and life path guidance
• Relationship compatibility
• Career direction

Would you like to rephrase your question in one of these areas?"""
        
        state["requires_followup"] = False
    
    state["processing_path"].append("safety_check")
    
    return state


def extract_birth_data_node(state: ConversationState) -> ConversationState:
    """
    Node 3: Extract birth data from query (if calculation type).
    
    Extracts:
    - Birth date
    - Birth time
    - Birth location
    
    Sets flags for missing data.
    """
    if state["intent_type"] != "calculation":
        # Skip if not calculation
        state["birth_data_complete"] = True
        state["processing_path"].append("extract_birth_data [skipped]")
        return state
    
    query = state["query"]
    
    # Extract birth data
    extracted = extract_birth_data_from_query.invoke({"query": query})
    
    state["birth_data"] = {
        "date": extracted.get("birth_date"),
        "time": extracted.get("birth_time"),
        "location_text": extracted.get("location_text"),
        "latitude": None,  # Would need geocoding
        "longitude": None,
    }
    
    state["missing_fields"] = extracted.get("missing_fields", [])
    state["birth_data_complete"] = len(state["missing_fields"]) == 0
    
    state["processing_path"].append("extract_birth_data")
    
    print(f"[EXTRACT] Birth data complete: {state['birth_data_complete']}")
    if not state["birth_data_complete"]:
        print(f"[EXTRACT] Missing: {state['missing_fields']}")
    
    return state


def request_missing_data_node(state: ConversationState) -> ConversationState:
    """
    Node 4: Request missing birth data from user.
    
    If birth data is incomplete, generate a friendly prompt
    asking for missing information.
    """
    missing = state.get("missing_fields", [])
    
    if not missing:
        return state
    
    # Generate request message
    missing_str = ", ".join(missing)
    
    state["final_answer"] = f"""To calculate your birth chart accurately, I need the following information:

{chr(10).join('• ' + field.replace('_', ' ').title() for field in missing)}

Please provide these details in your next message. For example:
"I was born on March 15, 1990 at 2:30 PM in New York City"

Looking forward to generating your chart! 🌟"""
    
    state["requires_followup"] = True
    state["followup_question"] = f"Please provide your {missing_str}"
    
    state["processing_path"].append("request_missing_data")
    
    return state


def execute_calculation_node(state: ConversationState) -> ConversationState:
    """
    Node 5: Execute astrological calculations.
    
    Calls appropriate calculation tool based on:
    - System (Vedic vs Western)
    - Type (birth chart, transits, dasha)
    """
    if state["intent_type"] != "calculation" or not state["birth_data_complete"]:
        state["processing_path"].append("execute_calculation [skipped]")
        return state
    
    birth_data = state["birth_data"]
    system = state["astro_system"]
    calc_type = state["calculation_type"]
    
    print(f"[CALCULATE] System: {system}, Type: {calc_type}")
    
    try:
        # TODO: In production, you'd geocode location_text to get lat/lon
        # For now, using placeholder coordinates
        if not birth_data["latitude"]:
            birth_data["latitude"] = 28.6139  # Delhi default
            birth_data["longitude"] = 77.2090
        
        # Execute calculation
        if system == "vedic":
            if calc_type == "transits":
                result = calculate_vedic_transits.invoke({
                    "birth_date": birth_data["date"],
                    "birth_time": birth_data["time"],
                    "latitude": birth_data["latitude"],
                    "longitude": birth_data["longitude"]
                })
            else:  # birth_chart
                result = calculate_vedic_birth_chart.invoke({
                    "birth_date": birth_data["date"],
                    "birth_time": birth_data["time"],
                    "latitude": birth_data["latitude"],
                    "longitude": birth_data["longitude"]
                })
        
        elif system == "western":
            result = calculate_western_birth_chart.invoke({
                "birth_date": birth_data["date"],
                "birth_time": birth_data["time"],
                "latitude": birth_data["latitude"],
                "longitude": birth_data["longitude"]
            })
        
        else:
            result = {"error": True, "message": f"Unknown system: {system}"}
        
        state["calculation_result"] = result
        
        if result.get("error"):
            state["error"] = result.get("message", "Calculation failed")
            print(f"[ERROR] {state['error']}")
        else:
            print(f"[CALCULATE] Success! Chart type: {result.get('chart_type')}")
        
    except Exception as e:
        state["error"] = f"Calculation error: {str(e)}"
        print(f"[ERROR] {state['error']}")
    
    state["processing_path"].append("execute_calculation")
    
    return state


def retrieve_knowledge_node(state: ConversationState) -> ConversationState:
    """
    Node 6: Retrieve astrological knowledge via RAG.
    
    Uses RAG engine to fetch relevant classical text passages
    for interpretation queries.
    """
    if not RAG_AVAILABLE:
        state["processing_path"].append("retrieve_knowledge [unavailable]")
        return state
    
    # Skip RAG for pure calculations (unless user asks for interpretation too)
    if state["intent_type"] == "calculation" and "what" not in state["query"].lower():
        state["processing_path"].append("retrieve_knowledge [skipped]")
        return state
    
    query = state["query"]
    
    # Initialize RAG engine
    try:
        rag_engine = RAGEngine(
            persona="hybrid",
            enable_storage=False  # Orchestrator manages history
        )
        
        # Get answer from RAG
        response = rag_engine.answer_question(
            query=query,
            top_k=5,
            conversation_history=state.get("conversation_history", []),
            save_to_store=False  # Managed externally
        )
        
        state["rag_result"] = {
            "answer": response.answer,
            "sources": [
                {
                    "book": chunk.metadata.get("source_book"),
                    "chapter": chunk.metadata.get("chapter"),
                    "relevance": chunk.score
                }
                for chunk in response.sources[:3]  # Top 3 sources
            ]
        }
        
        print(f"[RAG] Retrieved {len(response.sources)} sources")
        
    except Exception as e:
        state["error"] = f"RAG error: {str(e)}"
        print(f"[ERROR] {state['error']}")
    
    state["processing_path"].append("retrieve_knowledge")
    
    return state


def synthesize_response_node(state: ConversationState) -> ConversationState:
    """
    Node 7: Synthesize final response.
    
    Combines:
    - Calculation results (if any)
    - RAG knowledge (if any)
    - Appropriate formatting
    
    Into a coherent, helpful response.
    """
    # If already has final answer (blocked, missing data), skip
    if state.get("final_answer"):
        state["processing_path"].append("synthesize_response [skipped]")
        return state
    
    parts = []
    
    # Part 1: Calculation results
    calc_result = state.get("calculation_result")
    if calc_result and not calc_result.get("error"):
        parts.append("## 📊 Your Chart Calculation\n")
        
        if calc_result.get("chart_type") == "vedic":
            parts.append(f"**Lagna (Ascendant):** {calc_result['lagna']['rashi']}")
            parts.append(f"**Rashi (Moon Sign):** {calc_result['rashi']}")
            parts.append(f"**Sun Sign:** {calc_result['sun_sign']}")
            parts.append(f"**Moon Nakshatra:** {calc_result['moon_nakshatra']}\n")
            
            # Current Dasha
            dasha = calc_result.get("current_dasha", {})
            if dasha:
                parts.append("**Current Dasha Periods:**")
                for level, planet in dasha.items():
                    parts.append(f"  • {level}: {planet}")
                parts.append("")
            
            # Top planets
            planets = calc_result.get("planets", {})
            if planets:
                parts.append("**Key Planetary Positions:**")
                for name, data in list(planets.items())[:5]:  # Top 5
                    house = data.get("house")
                    rashi = data.get("rashi")
                    parts.append(f"  • {name.title()}: {rashi}, {house}th house")
                parts.append("")
        
        elif calc_result.get("chart_type") == "western":
            parts.append(f"**Sun Sign:** {calc_result['sun_sign']}")
            parts.append(f"**Moon Sign:** {calc_result['moon_sign']}")
            parts.append(f"**Ascendant:** {calc_result['ascendant']}\n")
    
    # Part 2: RAG interpretation
    rag_result = state.get("rag_result")
    if rag_result:
        if parts:  # If we have calculations, add interpretation section
            parts.append("\n## 📚 Classical Interpretation\n")
        
        parts.append(rag_result["answer"])
        
        # Add sources
        sources = rag_result.get("sources", [])
        if sources:
            parts.append("\n\n**Sources:**")
            for i, source in enumerate(sources[:3], 1):
                book = source.get("book", "Unknown")
                chapter = source.get("chapter", "")
                parts.append(f"{i}. {book}" + (f" - {chapter}" if chapter else ""))
    
    # Part 3: Error handling
    if state.get("error"):
        parts.append(f"\n⚠️ Note: {state['error']}")
    
    # Part 4: Chitchat fallback
    if state["intent_type"] == "chitchat" and not parts:
        parts.append("Namaste! 🙏 How may I assist you with your astrological questions today?")
    
    # Combine all parts
    state["final_answer"] = "\n".join(parts) if parts else "I apologize, but I couldn't generate a response. Please try rephrasing your question."
    state["requires_followup"] = False
    
    state["processing_path"].append("synthesize_response")
    
    return state


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def route_after_safety_check(state: ConversationState) -> str:
    """
    Decide next step after safety check.
    
    Routes:
    - blocked → END
    - calculation → extract_birth_data
    - interpretation → retrieve_knowledge
    - chitchat → synthesize_response
    """
    if state["is_blocked"]:
        return END
    
    intent = state["intent_type"]
    
    if intent == "calculation":
        return "extract_birth_data"
    elif intent == "interpretation":
        return "retrieve_knowledge"
    else:  # chitchat
        return "synthesize_response"


def route_after_birth_data_extraction(state: ConversationState) -> str:
    """
    Decide next step after birth data extraction.
    
    Routes:
    - data complete → execute_calculation
    - data incomplete → request_missing_data
    """
    if state.get("birth_data_complete"):
        return "execute_calculation"
    else:
        return "request_missing_data"


def route_after_calculation(state: ConversationState) -> str:
    """
    Decide next step after calculation.
    
    Routes:
    - error → synthesize_response (will show error)
    - success + interpretation needed → retrieve_knowledge
    - success + no interpretation → synthesize_response
    """
    # Check if user also wants interpretation
    query_lower = state["query"].lower()
    wants_interpretation = any(w in query_lower for w in ["what", "mean", "signify", "indicate", "explain"])
    
    if wants_interpretation:
        return "retrieve_knowledge"
    else:
        return "synthesize_response"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_orchestration_graph() -> StateGraph:
    """
    Create the complete LangGraph orchestration flow.
    
    Flow:
    1. Classify intent
    2. Safety check
    3. [If calculation] Extract birth data
    4. [If missing data] Request data → END
    5. [If calculation] Execute calculation
    6. [If interpretation needed] Retrieve knowledge
    7. Synthesize final response
    """
    # Initialize graph
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("extract_birth_data", extract_birth_data_node)
    workflow.add_node("request_missing_data", request_missing_data_node)
    workflow.add_node("execute_calculation", execute_calculation_node)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
    workflow.add_node("synthesize_response", synthesize_response_node)
    
    # Define edges
    workflow.set_entry_point("classify_intent")
    
    workflow.add_edge("classify_intent", "safety_check")
    
    workflow.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            END: END,
            "extract_birth_data": "extract_birth_data",
            "retrieve_knowledge": "retrieve_knowledge",
            "synthesize_response": "synthesize_response",
        }
    )
    
    workflow.add_conditional_edges(
        "extract_birth_data",
        route_after_birth_data_extraction,
        {
            "execute_calculation": "execute_calculation",
            "request_missing_data": "request_missing_data",
        }
    )
    
    workflow.add_edge("request_missing_data", END)
    
    workflow.add_conditional_edges(
        "execute_calculation",
        route_after_calculation,
        {
            "retrieve_knowledge": "retrieve_knowledge",
            "synthesize_response": "synthesize_response",
        }
    )
    
    workflow.add_edge("retrieve_knowledge", "synthesize_response")
    workflow.add_edge("synthesize_response", END)
    
    return workflow.compile()


# =============================================================================
# ORCHESTRATOR CLASS
# =============================================================================

class AstrologyOrchestrator:
    """
    Main orchestrator for astrology chatbot.
    
    Manages conversation flow using LangGraph.
    """
    
    def __init__(self):
        """Initialize orchestrator."""
        self.graph = create_orchestration_graph()
        print("[ORCHESTRATOR] Initialized")
    
    def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the orchestration graph.
        
        Args:
            query: User's question or request
            conversation_history: Previous conversation turns
            user_id: User identifier (optional)
            
        Returns:
            Dictionary with final answer and metadata
        """
        # Initialize state
        initial_state = ConversationState(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history or [],
            intent_type=None,
            astro_system=None,
            calculation_type=None,
            birth_data=None,
            birth_data_complete=False,
            missing_fields=[],
            calculation_result=None,
            rag_result=None,
            is_blocked=False,
            block_reason=None,
            final_answer="",
            requires_followup=False,
            followup_question=None,
            processing_path=[],
            error=None
        )
        
        # Execute graph
        print(f"\n[ORCHESTRATOR] Processing: '{query[:60]}...'")
        final_state = self.graph.invoke(initial_state)
        
        # Extract result
        result = {
            "answer": final_state["final_answer"],
            "requires_followup": final_state.get("requires_followup", False),
            "followup_question": final_state.get("followup_question"),
            "intent_type": final_state.get("intent_type"),
            "processing_path": final_state.get("processing_path", []),
            "has_calculation": final_state.get("calculation_result") is not None,
            "has_interpretation": final_state.get("rag_result") is not None,
            "error": final_state.get("error"),
        }
        
        print(f"[ORCHESTRATOR] Complete. Path: {' → '.join(result['processing_path'])}")
        
        return result


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("LANGGRAPH ORCHESTRATOR - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize orchestrator
    orchestrator = AstrologyOrchestrator()
    
    # Test queries
    test_queries = [
        "Hello! How are you?",
        "What does Mars in the 7th house mean?",
        "Calculate my birth chart. I was born March 15, 1990 at 2:30 PM",
        "When will I die?",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {i}: {query}")
        print('=' * 70)
        
        result = orchestrator.process_query(query)
        
        print(f"\n[RESULT]")
        print(f"Intent: {result['intent_type']}")
        print(f"Path: {' → '.join(result['processing_path'])}")
        print(f"\n{result['answer'][:300]}...")
        
        if result.get("error"):
            print(f"\n⚠️ Error: {result['error']}")
    
    print("\n" + "=" * 70)
    print("✅ Orchestrator tests complete!")
    print("=" * 70)