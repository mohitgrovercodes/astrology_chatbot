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
from src.ai.intent_classifier import IntentClassifier
from src.ai.user_manager import UserManager
from src.ai.hybrid_retriever import HybridRetriever
from src.ai.prompt_builder import PromptBuilder
from src.engines.vedic.vedic_engine import VedicEngine
from src.engines.western.western_engine import WesternAstroEngine
from src.api.config import settings


# Singleton instances
_orchestrator_instance: Optional[object] = None
_user_manager_instance: Optional[UserManager] = None
_vedic_engine_instance: Optional[VedicEngine] = None
_western_engine_instance: Optional[WesternAstroEngine] = None


def get_llm():
    """
    Get LLM instance.
    
    Supports:
    - Google Cloud (Vertex AI) with service account credentials
    - OpenAI with API key
    """
    if settings.LLM_PROVIDER == "gemini" or settings.LLM_PROVIDER == "google":
        # Use Google Cloud Vertex AI with credentials
        from langchain_google_vertexai import ChatVertexAI
        import google.auth
        
        # Load credentials from file or default
        if settings.GOOGLE_CREDENTIALS_PATH:
            print(f"[API] Loading Google credentials from: {settings.GOOGLE_CREDENTIALS_PATH}")
            credentials, project = google.auth.load_credentials_from_file(
                settings.GOOGLE_CREDENTIALS_PATH
            )
        else:
            print("[API] Using default Google credentials")
            credentials, project = google.auth.default()
        
        # Override project if specified
        project_id = settings.GOOGLE_PROJECT_ID or project
        
        return ChatVertexAI(
            model_name=settings.LLM_MODEL,
            credentials=credentials,
            project=project_id,
            temperature=0.3,
            location=settings.GOOGLE_LOCATION
        )
    else:
        # Use OpenAI
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        )


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
        
        return Chroma(
            client=client,
            collection_name="astro_rag",  # Default collection
            embedding_function=embeddings,
        )
    except Exception as e:
        print(f"[API] Error initializing vector store: {e}")
        # Return None or raise, orchestrator handles it?
        # For now return None and handle in orchestrator if possible or let it fail
        raise e


def get_orchestrator():
    """
    Get singleton orchestrator instance.
    Creates on first call, returns cached instance on subsequent calls.
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        print("[API] Initializing orchestrator...")
        
        llm = get_llm()
        vector_store = get_vector_store()
        
        # Initialize intent classifier (no LLM needed for simplified version)
        intent_classifier = IntentClassifier()
        user_manager = get_user_manager()
        hybrid_retriever = HybridRetriever(vector_store=vector_store, llm=llm)
        prompt_builder = PromptBuilder()
        
        _orchestrator_instance = create_enhanced_orchestrator(
            intent_classifier=intent_classifier,
            user_manager=user_manager,
            hybrid_retriever=hybrid_retriever,
            prompt_builder=prompt_builder,
            llm=llm
        )
        
        print("[API] ✓ Orchestrator initialized")
    
    return _orchestrator_instance


def get_user_manager() -> UserManager:
    """
    Get singleton user manager instance.
    """
    global _user_manager_instance
    
    if _user_manager_instance is None:
        print("[API] Initializing user manager...")
        # Determine MongoDB URI based on settings (None = use dummy DB)
        mongo_uri = settings.MONGODB_URI or os.getenv("MONGODB_URI")
        if settings.USE_DUMMY_USER_DB:
            mongo_uri = None
            
        _user_manager_instance = UserManager(
            mongodb_uri=mongo_uri
        )
        print("[API] ✓ User manager initialized")
    
    return _user_manager_instance


def get_vedic_engine() -> VedicEngine:
    """
    Get singleton Vedic engine instance.
    """
    global _vedic_engine_instance
    
    if _vedic_engine_instance is None:
        print("[API] Initializing Vedic engine...")
        _vedic_engine_instance = VedicEngine()
        print("[API] ✓ Vedic engine initialized")
    
    return _vedic_engine_instance


def get_western_engine() -> WesternAstroEngine:
    """
    Get singleton Western engine instance.
    """
    global _western_engine_instance
    
    if _western_engine_instance is None:
        print("[API] Initializing Western engine...")
        _western_engine_instance = WesternAstroEngine()
        print("[API] ✓ Western engine initialized")
    
    return _western_engine_instance


# Reset function for testing
def reset_dependencies():
    """Reset all singleton instances (for testing)."""
    global _orchestrator_instance, _user_manager_instance, _vedic_engine_instance, _western_engine_instance
    _orchestrator_instance = None
    _user_manager_instance = None
    _vedic_engine_instance = None
    _western_engine_instance = None
    print("[API] Dependencies reset")
