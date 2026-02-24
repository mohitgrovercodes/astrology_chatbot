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
    Semantic LLM-based intent classifier (fallback for orchestrator_helper).
    Uses the same semantic approach as the main LLMIntentClassifier.
    """

    SEMANTIC_PROMPT = """You are an intelligent intent classifier for a Vedic astrology chatbot.
The user ALWAYS has birth details on file. The query may be in ANY language — English, Hindi, Tamil, Hinglish, or mixed.

Classify into exactly ONE of four categories based on what the user fundamentally wants to achieve:

**CHITCHAT** — Casual conversation: greeting, thanking, asking about the bot, saying goodbye.
Core signal: No astrological intent.

**CALCULATION_ONLY** — User wants raw astrological data displayed (positions, placements, dashas), not interpreted.
Core signal: Wants data shown, not explained or predicted.

**RAG_WITH_CALCULATION** — User wants a personalized prediction, guidance, or insight tailored to their own life.
Core signal: The answer must be specific to THIS person's chart. Includes any life area (career, marriage, health, timing).
This includes queries in any language that express personal intent: "mere liye", "mujhe batao", "for me", "my career", etc.
When uncertain between RAG_ONLY and RAG_WITH_CALCULATION, always prefer RAG_WITH_CALCULATION.

**RAG_ONLY** — User asks about astrology as a subject — concepts, theories, general principles.
Core signal: Answer would be the same for any person, no personalization needed.
Only choose this if the query is clearly educational with no personal framing.

Think: What does the user want — data, a personal answer, education, or just conversation?
If personal even slightly → RAG_WITH_CALCULATION.

Respond ONLY with valid JSON:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "reasoning": "One sentence."}}"""

    def __init__(self):
        self.llm = None
        print("[INTENT] Simple classifier initialized")

    def set_llm(self, llm):
        """Set the LLM to use for classification."""
        self.llm = llm
        print("[INTENT] LLM-based classifier initialized")

    def _pure_logic_fallback(self, query: str) -> dict:
        """Pure-logic fallback when LLM is unavailable. Semantic > pattern."""
        q = query.lower().strip()

        # Greetings — short, no astrological content
        greeting_words = ['hi', 'hello', 'hey', 'namaste', 'vanakkam', 'jai', 'shukriya',
                          'thanks', 'thank you', 'bye', 'goodbye', 'dhanyawad']
        if any(q == w or q.startswith(w + ' ') or q.endswith(' ' + w) for w in greeting_words):
            return {'intent': 'CHITCHAT', 'confidence': 0.92, 'reasoning': 'Greeting/farewell detected', 'cached': False}

        # Raw data display — no interpretation desire
        display_signals = ['show my', 'display my', 'show chart', 'my chart', 'my kundali',
                           'my kundli', 'my horoscope', 'my lagna', 'my ascendant',
                           'my dasha', 'planetary positions', 'current transits']
        if any(s in q for s in display_signals) and not any(
            w in q for w in ['predict', 'when will', 'will i', 'should i', 'career', 'marriage']):
            return {'intent': 'CALCULATION_ONLY', 'confidence': 0.88, 'reasoning': 'Raw data display request', 'cached': False}

        # Default: any ambiguous personal query → safest route
        return {'intent': 'RAG_WITH_CALCULATION', 'confidence': 0.80, 'reasoning': 'Default: personal or prediction query', 'cached': False}

    def classify(self, query: str, user_profile: dict = None, conversation_history: list = None):
        """Classify intent using semantic LLM prompt with smart fallback."""
        if not self.llm:
            return self._pure_logic_fallback(query)

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SEMANTIC_PROMPT),
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