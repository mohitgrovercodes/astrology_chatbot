#!/usr/bin/env python3
"""
Astrology AI Chatbot - Interactive CLI

RAG-powered chatbot for Vedic astrology questions.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.rag.rag_engine import RAGEngine


class AstrologyChatbot:
    """Interactive chatbot for astrology questions."""
    
    WELCOME_MESSAGE = """
╔══════════════════════════════════════════════════════════════╗
║          🌟 Astrology AI Chatbot 🌟                         ║
║                                                              ║
║  Ask questions about Vedic astrology based on classical     ║
║  texts like Brihat Parasara Hora Shastra.                   ║
║                                                              ║
║  Commands:                                                   ║
║    /help      - Show this help message                      ║
║    /filter    - Set metadata filters                        ║
║    /clear     - Clear conversation history                  ║
║    /sources   - Toggle source display                       ║
║    /quit      - Exit chatbot                                ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    HELP_MESSAGE = """
Available Commands:
  /help                    - Show this help message
  /filter planet=Mars      - Filter by planet
  /filter house=5          - Filter by house
  /filter clear            - Clear all filters
  /clear                   - Clear conversation history
  /sources on|off          - Toggle source citations
  /quit                    - Exit chatbot

Examples:
  What does Mars in the 5th house signify?
  Explain the concept of Gulika
  /filter planet=Jupiter
  What are the effects of Jupiter?
"""
    
    def __init__(
        self,
        collection_name: str = "Jataka Parijata Vol 1 By Vaidyanatha Dikshita",
        db_path: str = "data/vectordb",
        llm_provider: str = "google",
        llm_model: Optional[str] = None,
        use_reranker: bool = False,
        reranker_method: str = "cohere",
    ):
        """Initialize chatbot."""
        print("Initializing Astrology AI Chatbot...")
        
        self.engine = RAGEngine(
            collection_name=collection_name,
            db_path=db_path,
            llm_provider=llm_provider,
            llm_model=llm_model,
            use_reranker=use_reranker,
            reranker_method=reranker_method,
        )
        
        self.conversation_history: List[Dict[str, str]] = []
        self.filters: Dict[str, Any] = {}
        self.show_sources = True
        
        print("✅ Ready!\n")
    
    def run(self):
        """Run interactive chatbot loop."""
        print(self.WELCOME_MESSAGE)
        
        while True:
            try:
                # Get user input
                user_input = input("\n🔮 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    if not self._handle_command(user_input):
                        break  # Exit if command returns False
                    continue
                
                # Process question
                self._answer_question(user_input)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 🌙")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def _handle_command(self, command: str) -> bool:
        """
        Handle chatbot commands.
        
        Returns:
            False if should exit, True otherwise
        """
        cmd = command.lower().split()[0]
        
        if cmd == "/quit" or cmd == "/exit":
            print("\nGoodbye! 🌙")
            return False
        
        elif cmd == "/help":
            print(self.HELP_MESSAGE)
        
        elif cmd == "/clear":
            self.conversation_history = []
            print("✅ Conversation history cleared")
        
        elif cmd == "/filter":
            self._handle_filter_command(command)
        
        elif cmd == "/sources":
            parts = command.split()
            if len(parts) > 1:
                self.show_sources = parts[1].lower() in ["on", "true", "yes"]
            else:
                self.show_sources = not self.show_sources
            
            status = "ON" if self.show_sources else "OFF"
            print(f"✅ Source citations: {status}")
        
        else:
            print(f"❌ Unknown command: {cmd}")
            print("Type /help for available commands")
        
        return True
    
    def _handle_filter_command(self, command: str):
        """Handle /filter command."""
        parts = command.split(maxsplit=1)
        
        if len(parts) == 1:
            # Show current filters
            if self.filters:
                print("Current filters:")
                for key, value in self.filters.items():
                    print(f"  {key}: {value}")
            else:
                print("No filters set")
            return
        
        filter_arg = parts[1].strip()
        
        if filter_arg.lower() == "clear":
            self.filters = {}
            print("✅ Filters cleared")
            return
        
        # Parse filter (e.g., "planet=Mars" or "house=5")
        if "=" in filter_arg:
            key, value = filter_arg.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            
            # Map to metadata field names
            if key == "planet":
                self.filters["planets"] = value
            elif key == "house":
                self.filters["houses"] = value
            elif key == "sign":
                self.filters["signs"] = value
            elif key == "nakshatra":
                self.filters["nakshatras"] = value
            elif key in ["planets", "houses", "signs", "nakshatras", "yogas", "concepts"]:
                self.filters[key] = value
            else:
                print(f"❌ Unknown filter key: {key}")
                return
            
            print(f"✅ Filter set: {key} = {value}")
        else:
            print("❌ Invalid filter format. Use: /filter key=value")
            print("Example: /filter planet=Mars")
    
    def _answer_question(self, question: str):
        """Process and answer a question."""
        print("\n🤔 Thinking...\n")
        
        # Get answer from RAG engine
        # Auto-Routing Enabled: Passing None for hyde/hybrid lets the engine decide based on query intent.
        response = self.engine.answer_question(
            query=question,
            top_k=5,
            filters=self.filters if self.filters else None,
            use_hyde=None,   # Auto
            use_hybrid=None, # Auto
            expand_context=True,
            conversation_history=self.conversation_history,
        )
        
        # Display answer
        print("=" * 60)
        print("✨ ANSWER")
        print("=" * 60)
        print(response.answer)
        
        # Display sources if enabled
        if self.show_sources and response.sources:
            print("\n" + "=" * 60)
            print("📚 SOURCES")
            print("=" * 60)
            for i, chunk in enumerate(response.sources, 1):
                source_info = f"[{i}] {chunk.metadata.get('source_book', 'Unknown')}"
                if chunk.metadata.get('chapter'):
                    source_info += f" - {chunk.metadata['chapter']}"
                if chunk.metadata.get('verse_number'):
                    source_info += f" (Verse {chunk.metadata['verse_number']})"
                source_info += f" - Relevance: {chunk.score:.1%}"
                print(source_info)
        
        # Update conversation history
        self.conversation_history.append({
            "user": question,
            "assistant": response.answer,
        })
        
        # Keep only last 5 turns
        if len(self.conversation_history) > 5:
            self.conversation_history = self.conversation_history[-5:]


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Astrology AI Chatbot - Interactive CLI"
    )
    parser.add_argument(
        "--collection",
        default="brihat_parasara_hora_sastra",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--db-path",
        default="data/vectordb",
        help="Path to vector database"
    )
    parser.add_argument(
        "--provider",
        default="google",
        choices=["google", "openai"],
        help="LLM provider (google or openai)"
    )
    parser.add_argument(
        "--model",
        help="LLM model to use (auto-selected if not specified)"
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Enable reranking for better precision"
    )
    parser.add_argument(
        "--reranker-method",
        default="cohere",
        choices=["cohere", "cross-encoder"],
        help="Reranker method (cohere or cross-encoder)"
    )
    
    args = parser.parse_args()
    
    # ==========================================
    # Interactive Configuration
    # ==========================================
    collection_name = args.collection
    db_path = args.db_path
    provider = args.provider
    
    if len(sys.argv) == 1:  # No args provided
        print("\n" + "=" * 60)
        print("🤖 Chatbot Setup")
        print("=" * 60)
        
        # 1. Collection
        # 1. Collection
        import chromadb
        try:
            client = chromadb.PersistentClient(path=db_path)
            collections = client.list_collections()
            col_names = [c.name for c in collections]
        except Exception:
            col_names = []

        print(f"\n[1/3] Collection Selection")
        if col_names:
            print("Found existing collections:")
            for i, name in enumerate(col_names, 1):
                print(f"  {i}. {name}")
            
            sel = input(f"      Select [1] or type name: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(col_names):
                collection_name = col_names[int(sel)-1]
            elif sel:
                collection_name = sel
            else:
                collection_name = col_names[0]
        else:
            default_col = "brihat_parasara_hora_sastra"
            user_col = input(f"      Enter Name [{default_col}]: ").strip()
            collection_name = user_col if user_col else default_col
        
        # 2. LLM Provider
        print(f"\n[2/3] Select LLM Provider:")
        print("      1. Google (Gemini) [Default]")
        print("      2. OpenAI (GPT-4)")
        prov_choice = input("      Choice: ").strip()
        if prov_choice == "2":
            provider = "openai"
        else:
            provider = "google"
            
    # Initialize and run chatbot
    chatbot = AstrologyChatbot(
        collection_name=collection_name,
        db_path=db_path,
        llm_provider=provider,
        llm_model=args.model,
        use_reranker=args.rerank,
        reranker_method=args.reranker_method,
    )
    
    chatbot.run()


if __name__ == "__main__":
    main()
