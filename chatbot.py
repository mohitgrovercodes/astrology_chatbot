"""
NakshatraAI Chatbot - V2 Architecture
Uses LangGraph orchestrator with 3-category intent classification.
"""

# Suppress Google Generative AI deprecation warning
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='langchain_google_genai')

import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Load environment
load_dotenv()

# Import V2 components
from src.ai.intent_classifier import EnhancedIntentClassifier
from src.ai.user_manager import get_user_manager
from src.ai.hybrid_retriever import HybridRetriever
from src.ai.prompt_builder import PromptBuilder
from src.orchestration.orchestrator import create_enhanced_orchestrator
from src.tools.calculation_tools import CALCULATION_TOOLS
import argparse


def main():
    print("=" * 60)
    print("NakshatraAI - Professional Astrology Consultant (V2)")
    print("=" * 60)
    print()
    
    # Parse CLI Arguments
    parser = argparse.ArgumentParser(description="NakshatraAI Chatbot")
    parser.add_argument("--provider", type=str, help="LLM Provider (google, openai, ollama)")
    parser.add_argument("--model", type=str, help="LLM Model name")
    args = parser.parse_args()
    
    # Initialize components
    print("Initializing NakshatraAI V2...")
    
    # 1. User Manager
    mongodb_uri = os.getenv('MONGODB_URI')
    user_manager = get_user_manager(mongodb_uri)
    
    # 2. LLM Setup - Centralized Factory
    # Supports switching via CLI args or LLM_PROVIDER env var
    from src.llm.factory import LLMFactory
    
    provider_override = args.provider
    model_override = args.model
    
    # Quality LLM for final responses
    llm = LLMFactory.create(
        provider=provider_override,
        model=model_override,
        purpose="general", 
        streaming=True
    )
    
    # Fast LLM for classification and intent routing
    # This prevents OOM errors by using a smaller model for simple logic
    fast_llm = LLMFactory.create(
        purpose="classification"
    )
    
    # Get actual config used (in case of defaults)
    active_provider = provider_override or os.getenv("LLM_PROVIDER", "google")
    print(f"[OK] Quality LLM: {active_provider}")
    if model_override:
        print(f"[OK] Quality Model: {model_override}")
    
    # 3. Embeddings (MUST MATCH the model used during ingestion!)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",
        dimensions=3072  # Reduce from 3072 to match collection
    )
    print("[OK] Embeddings: OpenAI text-embedding-3-large (3072-dim)")
    
    # 4. Vector Store
    vector_store = Chroma(
        collection_name="astrology_default",
        embedding_function=embeddings,
        persist_directory="./data/vectordb"
    )
    print("[OK] Vector Store: ChromaDB (astrology_default)")
    
    # 5. Intent Classifier (4 categories)
    intent_classifier = EnhancedIntentClassifier(
        llm=fast_llm,  # Use FAST LLM for classification
        use_cache=True
    )
    
    # 6. Hybrid Retriever
    hybrid_retriever = HybridRetriever(
        vector_store=vector_store,
        llm=llm
    )
    
    # 7. Prompt Builder
    prompt_builder = PromptBuilder()
    
    # 8. LangGraph Orchestrator
    orchestrator = create_enhanced_orchestrator(
        intent_classifier=intent_classifier,
        user_manager=user_manager,
        hybrid_retriever=hybrid_retriever,
        prompt_builder=prompt_builder,
        calculation_tools=CALCULATION_TOOLS,
        llm=llm,          # Quality LLM for interpreting
        fast_llm=fast_llm  # Fast LLM for classification/routing
    )
    
    print()
    print("=" * 60)
    print("✅ NakshatraAI V2 initialized!")
    print("=" * 60)
    print()
    print("4-Category Intent System:")
    print("  • CHITCHAT - General conversation")
    print("  • CALCULATION_ONLY - Pure calculation (show chart)")
    print("  • RAG_WITH_CALCULATION - Prediction/Timing (Calculate + Interpret)")
    print("  • RAG_ONLY - Astrological concepts (RAG)")
    print()
    print("=" * 60)
    
    # Get user ID
    user_id = input("\nEnter user_id (or press Enter for user011): ").strip()
    if not user_id:
        user_id = "user011"
    
    print(f"\n🔐 Authenticating as: {user_id}")
    
    # Check if user exists
    if not user_manager.user_exists(user_id):
        print(f"❌ User '{user_id}' not found!")
        print("\nAvailable test users:")
        print("  • user001 - Arjun Kumar (Vedic)")
        print("  • user002 - Priya Sharma (Vedic)")
        print("  • user003 - Sophia Anderson (Western)")
        print("\nRun: python add_test_user.py to add your own user")
        return
    
    # Load profile
    profile = user_manager.get_user_profile(user_id)
    print(f"✓ Welcome, {profile.name}!")
    print(f"  System: {profile.preferred_system}")
    print(f"  Birth Data: {'✓ Complete' if profile.has_birth_data() else '✗ Missing'}")
    print()
    
    
    print("=" * 60)
    print("Chat started. Type 'quit' to exit.")
    print("=" * 60)
    print()
    
    # Main loop
    while True:
        # Get query
        query = input("🔮 You: ").strip()
        
        if not query:
            continue
        
        if query.lower() in ['quit', 'exit', 'bye']:
            print("\n✨ May the stars guide your path! Om Shanti! 🙏\n")
            break
            
        # Log user message
        try:
            user_manager.add_message(user_id, "user", query)
        except Exception as e:
            print(f"[ERROR] Failed to save message: {e}")
        
        # Get history from DB
        conversation_history = user_manager.get_history(user_id, limit=5)
        
        # Process query with streaming
        print("🤔 Thinking...")
        
        try:
            # Check if streaming is supported
            result = orchestrator.process_query_stream(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history
            )
            
            # Display streaming response
            print("\n✨ NakshatraAI: ", end="", flush=True)
            
            full_answer = ""
            intent = "unknown"
            for chunk in result:
                if 'chunk' in chunk:
                    print(chunk['chunk'], end="", flush=True)
                    full_answer += chunk['chunk']
                elif 'answer' in chunk:
                    # Final result with metadata
                    intent = chunk.get('intent', 'unknown')
                    cached = chunk.get('cached', False)
                    processing_time = chunk.get('processing_time', 0)
                    
                    print("\n")  # New line after response
                    
                    # Metadata
                    cache_status = "[CACHED]" if cached else "[STREAMED]"
                    print(f"[Intent: {intent}, {cache_status}, Time: {processing_time:.2f}s]")
                    print()
                    
                    # Use final answer if streaming didn't provide chunks
                    if not full_answer:
                        full_answer = chunk['answer']
                        # Print the answer since it wasn't streamed
                        print(full_answer)
            
            # Save assistant response to DB
            user_manager.add_message(user_id, "assistant", full_answer, intent=intent)
            
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()