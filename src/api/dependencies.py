# src/api/dependencies.py
"""
API Dependencies
=================

Dependency injection for FastAPI routes.
Provides singleton instances of core components.
"""

from functools import lru_cache
from typing import Optional
import os

from src.orchestration.orchestrator import create_enhanced_orchestrator
from src.ai.intent_classifier import LLMIntentClassifier
from src.ai.hybrid_retriever import HybridRetriever
from src.ai.prompt_builder import PromptBuilder
from src.engines.vedic.vedic_engine import VedicEngine
from src.engines.western.western_engine import WesternAstroEngine
from src.api.config import settings


# Singleton instances
_orchestrator_instance: Optional[object] = None
_vedic_engine_instance: Optional[VedicEngine] = None
_western_engine_instance: Optional[WesternAstroEngine] = None
_session_manager_instance: Optional[object] = None
_context_manager_instance: Optional[object] = None


def get_session_manager():
    """Get singleton session manager."""
    global _session_manager_instance
    if _session_manager_instance is None:
        from src.session.manager import SessionManager
        _session_manager_instance = SessionManager()
    return _session_manager_instance


def get_context_manager():
    """Get singleton context manager."""
    global _context_manager_instance
    if _context_manager_instance is None:
        from src.ai.context_manager import ContextManager
        _context_manager_instance = ContextManager()
    return _context_manager_instance


def get_llm():
    """
    Get LLM instance.
    
    Uses Centralized LLM Factory to support switching providers.
    """
    from src.llm.factory import LLMFactory
    return LLMFactory.create(purpose="general")


def get_fast_llm():
    """
    Get fast LLM for classification tasks.
    """
    from src.llm.factory import LLMFactory
    return LLMFactory.create(purpose="classification")


def get_embeddings():
    """Get embeddings model."""
    from langchain_openai import OpenAIEmbeddings
    
    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    )


def get_vector_store():
    """Get Vector Store instance (ChromaDB)."""
    from langchain_chroma import Chroma
    import chromadb
    
    embeddings = get_embeddings()
    
    # Ensure directory exists
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    
    # Initialize client with persistent storage
    try:
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        
        # Use the correct collection name that matches your VectorDB
        collection_name = "vedic_astrology_books_knowledge"
        
        return Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embeddings,
        )
    except Exception as e:
        print(f"[API] Error initializing vector store: {e}")
        raise e


def get_orchestrator():
    """
    Get singleton orchestrator instance.
    Creates on first call, returns cached instance on subsequent calls.
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        print("[API] Initializing orchestrator...")
        
        try:
            llm = get_llm()
            fast_llm = get_fast_llm()
            vector_store = get_vector_store()
            embeddings = get_embeddings()
            
            # Initialize intent classifier with fast LLM and embeddings
            intent_classifier = LLMIntentClassifier(llm=fast_llm, embeddings=embeddings)

            hybrid_retriever = HybridRetriever(
                vector_store=vector_store,
                llm=llm
            )

            prompt_builder = PromptBuilder()

            # Get calculation tools
            from src.tools.tools import get_calculation_tools
            calculation_tools = get_calculation_tools()

            _orchestrator_instance = create_enhanced_orchestrator(
                intent_classifier=intent_classifier,
                hybrid_retriever=hybrid_retriever,
                prompt_builder=prompt_builder,
                calculation_tools=calculation_tools,
                llm=llm,
                fast_llm=fast_llm
            )
            
            print("[API] Orchestrator initialized successfully")
            
        except Exception as e:
            print(f"[API] Orchestrator initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    return _orchestrator_instance



def get_vedic_engine() -> VedicEngine:
    """
    Get singleton Vedic engine instance.
    """
    global _vedic_engine_instance
    
    if _vedic_engine_instance is None:
        print("[API] Initializing Vedic engine...")
        _vedic_engine_instance = VedicEngine()
        print("[API] Vedic engine initialized")
    
    return _vedic_engine_instance


def get_western_engine() -> WesternAstroEngine:
    """
    Get singleton Western engine instance.
    """
    global _western_engine_instance
    
    if _western_engine_instance is None:
        print("[API] Initializing Western engine...")
        _western_engine_instance = WesternAstroEngine()
        print("[API] Western engine initialized")
    
    return _western_engine_instance


# Reset function for testing
def reset_dependencies():
    """Reset all singleton instances (for testing)."""
    global _orchestrator_instance, _vedic_engine_instance, _western_engine_instance, _session_manager_instance, _context_manager_instance
    _orchestrator_instance = None
    _vedic_engine_instance = None
    _western_engine_instance = None
    _session_manager_instance = None
    _context_manager_instance = None
    print("[API] Dependencies reset")
