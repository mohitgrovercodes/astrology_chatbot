# src/api/orchestrator_helper.py
"""
Orchestrator Helper for API Routes.

Ensures orchestrator is properly initialized.
Passes None for components that will auto-initialize or are optional.
"""

from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from src.rag.retriever import AstrologyRetriever

# In get_orchestrator():
retriever = AstrologyRetriever(
    collection_name="vedic_astrology_books_knowledge",
    db_path="data/vectordb"
)

# Global orchestrator instance (singleton per worker)
_orchestrator_instance = None


class SimpleIntentClassifier:
    """
    Simple LLM-based intent classifier.
    
    Classifies user queries into intents using the LLM.
    """
    
    def __init__(self):
        self.llm = None
        print("[INTENT] Simple classifier initialized")
    
    def set_llm(self, llm):
        """Set the LLM to use for classification."""
        self.llm = llm
        print("[INTENT] LLM-based classifier initialized")
    
    def classify(self, query: str, user_profile: dict = None, conversation_history: list = None):
        """
        Classify intent using LLM.
        
        Returns classification result with intent, confidence, and reasoning.
        """
        if not self.llm:
            # Fallback to simple rule-based classification
            query_lower = query.lower()
            
            # Check for greetings
            if any(word in query_lower for word in ['hi', 'hello', 'hey', 'namaste']):
                return {
                    'intent': 'CHITCHAT',
                    'confidence': 0.95,
                    'reasoning': 'Greeting detected',
                    'cached': False
                }
            
            # Check for chart display requests
            if any(phrase in query_lower for phrase in ['show', 'display', 'what is my']):
                return {
                    'intent': 'CALCULATION_ONLY',
                    'confidence': 0.90,
                    'reasoning': 'Display request detected',
                    'cached': False
                }
            
            # Default to RAG_WITH_CALCULATION for predictions
            return {
                'intent': 'RAG_WITH_CALCULATION',
                'confidence': 0.85,
                'reasoning': 'Prediction query',
                'cached': False
            }
        
        # Use LLM for classification
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intent classifier for a Vedic astrology chatbot.

Classify queries into one of these intents:
- CHITCHAT: Greetings, thanks, or questions about the bot
- CALCULATION_ONLY: Requests to show/display chart data (moon sign, ascendant, etc.)
- RAG_WITH_CALCULATION: Prediction queries requiring chart analysis + knowledge
- RAG_ONLY: General astrology questions (no personal chart needed)
- AMBIGUOUS: Unclear queries

Return JSON: {{"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}}"""),
            ("user", "Query: {query}")
        ])
        
        try:
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"query": query})
            result['cached'] = False
            return result
        except Exception as e:
            print(f"[INTENT] LLM classification failed: {e}, using fallback")
            return {
                'intent': 'RAG_WITH_CALCULATION',
                'confidence': 0.70,
                'reasoning': 'Fallback classification',
                'cached': False
            }


def get_orchestrator():
    """
    Get or create orchestrator instance with all required dependencies.
    
    Uses singleton pattern to avoid recreating orchestrator on every request.
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        print("[ORCHESTRATOR] Initializing for API...")
        
        # Create simple intent classifier
        print("[ORCHESTRATOR] Creating intent classifier...")
        intent_classifier = SimpleIntentClassifier()
        
        # Create orchestrator - other components will auto-initialize
        # hybrid_retriever, prompt_builder, calculation_tools, llm all auto-load if None
        _orchestrator_instance = EnhancedLangGraphOrchestrator(
            intent_classifier=intent_classifier,
            hybrid_retriever=retriever,
            prompt_builder=None,     # Auto-loads
            calculation_tools=None,  # Auto-loads
            llm=None,                # Auto-loads
            fast_llm=None            # Auto-loads
        )
        
        print("[ORCHESTRATOR] ✅ Initialized successfully")
    
    return _orchestrator_instance