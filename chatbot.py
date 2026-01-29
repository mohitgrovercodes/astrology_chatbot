#!/usr/bin/env python3
"""
Astrology AI Chatbot - Phase 5 (LangGraph Orchestrated)

Fully orchestrated chatbot with:
- Calculation engine integration (Vedic & Western)
- RAG-powered interpretations
- Safety guardrails
- Smart routing
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from orchestrator import AstrologyOrchestrator
from conversation_store import ConversationStore, get_default_store


class AstrologyChatbotPhase5:
    """Phase 5 chatbot with complete orchestration."""
    
    WELCOME_MESSAGE = """
╔═══════════════════════════════════════════════════════════════════╗
║          🌟 Astrology AI Chatbot (Phase 5 - Final) 🌟           ║
║                                                                   ║
║  Unified system for birth chart calculations AND classical       ║
║  Vedic astrology interpretations.                                ║
║                                                                   ║
║  ✨ NEW in Phase 5:                                              ║
║    • Birth chart calculations (Vedic & Western)                  ║
║    • Automatic dasha periods                                     ║
║    • Transit calculations                                        ║
║    • Intelligent routing (calculation vs interpretation)         ║
║    • Safety guardrails (blocks harmful queries)                  ║
║    • Hybrid responses (calculation + interpretation)             ║
║                                                                   ║
║  What I can help with:                                           ║
║    📊 "Calculate my birth chart" (+ birth details)               ║
║    📚 "What does Jupiter in 5th house mean?"                     ║
║    🌙 "Show me my current dasha periods"                         ║
║    🔄 "What are the transits today?"                             ║
║    ❓ "Explain the concept of Rahu-Ketu"                         ║
║                                                                   ║
║  Commands:                                                        ║
║    /help      - Show this help                                   ║
║    /history   - View conversation                                ║
║    /clear     - Clear session                                    ║
║    /quit      - Exit                                             ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        enable_storage: bool = True
    ):
        """Initialize Phase 5 chatbot."""
        print("Initializing Astrology AI Chatbot (Phase 5)...")
        
        # Initialize orchestrator
        self.orchestrator = AstrologyOrchestrator()
        
        # Initialize conversation storage
        self.enable_storage = enable_storage
        self.session_id = session_id
        
        if self.enable_storage:
            self.store = get_default_store()
            
            if session_id:
                print(f"[INFO] Resuming session: {session_id}")
            else:
                self.session_id = self.store.create_session(
                    metadata={"phase": "5", "orchestrated": True}
                )
                print(f"[INFO] Created new session: {self.session_id}")
        
        print("✅ Ready!\n")
    
    def run(self):
        """Run interactive chatbot loop."""
        print(self.WELCOME_MESSAGE)
        
        if self.enable_storage:
            print(f"Session ID: {self.session_id}\n")
        
        while True:
            try:
                # Get user input
                user_input = input("\n🔮 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    if not self._handle_command(user_input):
                        break  # Exit
                    continue
                
                # Process query through orchestrator
                self._process_query(user_input)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 🌙")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
    
    def _process_query(self, query: str):
        """Process query through orchestrator."""
        print("\n🤔 Processing...\n")
        
        # Get conversation history
        history = []
        if self.enable_storage:
            history = self.store.get_history(self.session_id, max_turns=10)
        
        # Process through orchestrator
        result = self.orchestrator.process_query(
            query=query,
            conversation_history=history
        )
        
        # Display result
        self._display_result(result)
        
        # Save to storage
        if self.enable_storage:
            try:
                self.store.add_turn(
                    self.session_id,
                    query,
                    result["answer"]
                )
            except Exception as e:
                print(f"[WARN] Failed to save conversation: {e}")
    
    def _display_result(self, result: dict):
        """Display orchestrator result."""
        print("=" * 70)
        print("✨ ANSWER")
        print("=" * 70)
        print(result["answer"])
        print()
        
        # Show metadata (debug info)
        if result.get("processing_path"):
            path = " → ".join(result["processing_path"])
            print(f"[Processing Path: {path}]")
        
        if result.get("error"):
            print(f"⚠️  Warning: {result['error']}")
        
        print()
    
    def _handle_command(self, command: str) -> bool:
        """
        Handle chatbot commands.
        
        Returns:
            False if should exit, True otherwise
        """
        cmd = command.lower().split()[0]
        
        if cmd in ["/quit", "/exit"]:
            print("\nGoodbye! 🌙")
            return False
        
        elif cmd == "/help":
            print(self.WELCOME_MESSAGE)
        
        elif cmd == "/history":
            self._show_history()
        
        elif cmd == "/clear":
            if self.enable_storage:
                self.store.delete_session(self.session_id)
                self.session_id = self.store.create_session(
                    metadata={"phase": "5", "orchestrated": True}
                )
                print(f"✅ Conversation cleared. New session: {self.session_id}")
            else:
                print("⚠️  Storage disabled")
        
        elif cmd == "/session":
            self._show_session_info()
        
        else:
            print(f"❌ Unknown command: {cmd}")
            print("Type /help for available commands")
        
        return True
    
    def _show_history(self):
        """Display conversation history."""
        if not self.enable_storage:
            print("⚠️  Storage disabled")
            return
        
        history = self.store.get_history(self.session_id)
        
        if not history:
            print("No conversation history yet.")
            return
        
        print("\n" + "=" * 70)
        print(f"CONVERSATION HISTORY ({len(history)} turns)")
        print("=" * 70)
        
        for i, turn in enumerate(history, 1):
            print(f"\n[Turn {i}]")
            print(f"You: {turn['user']}")
            print(f"Bot: {turn['assistant'][:200]}...")
        
        print("\n" + "=" * 70)
    
    def _show_session_info(self):
        """Show session information."""
        print("\n" + "=" * 70)
        print("SESSION INFO")
        print("=" * 70)
        
        if self.enable_storage:
            history = self.store.get_history(self.session_id)
            print(f"Session ID: {self.session_id}")
            print(f"Turns: {len(history)}")
            print(f"Storage: JSON (data/conversations/)")
        else:
            print("Storage: Disabled")
        
        print("=" * 70)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Astrology AI Chatbot - Phase 5 (Orchestrated)"
    )
    parser.add_argument(
        "--session",
        help="Resume existing session ID"
    )
    parser.add_argument(
        "--no-storage",
        action="store_true",
        help="Disable conversation storage"
    )
    
    args = parser.parse_args()
    
    # Initialize and run
    chatbot = AstrologyChatbotPhase5(
        session_id=args.session,
        enable_storage=not args.no_storage
    )
    
    chatbot.run()


if __name__ == "__main__":
    main()