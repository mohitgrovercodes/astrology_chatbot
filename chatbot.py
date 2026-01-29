#!/usr/bin/env python3
"""
Astrology AI Chatbot - Phase 5.1 (User-Authenticated)

Integrated with existing app's user database.
- Only paid subscribers can use the chatbot
- Birth data auto-loaded from user profile
- Personalized experience
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from orchestrator import AstrologyOrchestrator
from conversation_store import ConversationStore, get_default_store
from user_profile_manager import UserProfileManager, get_default_profile_manager


class AstrologyChatbotAuth:
    """Phase 5.1 chatbot with user authentication."""
    
    WELCOME_MESSAGE = """
╔═══════════════════════════════════════════════════════════════════╗
║     🌟 Astrology AI Chatbot (Phase 5.1 - Authenticated) 🌟      ║
║                                                                   ║
║  Welcome {user_name}! 👋                                          
║                                                                   ║
║  I have your birth details from your profile, so you can         ║
║  immediately ask for calculations without providing data         ║
║  repeatedly!                                                      ║
║                                                                   ║
║  What I can help with:                                           ║
║    📊 "Calculate my birth chart"                                 ║
║    📚 "What does Jupiter in 5th house mean?"                     ║
║    🌙 "Show me my current dasha periods"                         ║
║    🔄 "What are the transits today?"                             ║
║    ❓ "Explain Rahu-Ketu"                                         ║
║                                                                   ║
║  Commands:                                                        ║
║    /help      - Show this help                                   ║
║    /profile   - View your birth data                             ║
║    /history   - View conversation                                ║
║    /clear     - Clear session                                    ║
║    /quit      - Exit                                             ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    
    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        enable_storage: bool = True
    ):
        """
        Initialize authenticated chatbot.
        
        Args:
            user_id: User identifier (from your app's database)
            session_id: Resume existing session (optional)
            enable_storage: Enable conversation persistence
        """
        print("Initializing Astrology AI Chatbot (Phase 5.1)...")
        
        self.user_id = user_id
        
        # Initialize profile manager
        self.profile_manager = get_default_profile_manager()
        
        # Authenticate user
        print(f"[AUTH] Authenticating user: {user_id}")
        if not self.profile_manager.authenticate_user(user_id):
            raise ValueError(f"Authentication failed for user: {user_id}. Please check subscription status.")
        
        # Load user profile
        self.user_profile = self.profile_manager.get_user_profile(user_id)
        if not self.user_profile:
            raise ValueError(f"User profile not found: {user_id}")
        
        print(f"[AUTH] Welcome {self.user_profile.name}!")
        
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
                    user_id=user_id,
                    metadata={
                        "phase": "5.1",
                        "orchestrated": True,
                        "user_name": self.user_profile.name
                    }
                )
                print(f"[INFO] Created new session: {self.session_id}")
        
        print("✅ Ready!\n")
    
    def run(self):
        """Run interactive chatbot loop."""
        welcome = self.WELCOME_MESSAGE.format(
            user_name=self.user_profile.name.split()[0]  # First name
        )
        print(welcome)
        
        if self.enable_storage:
            print(f"Session ID: {self.session_id}")
        
        # Show birth data status
        if self.user_profile.has_complete_birth_data():
            print(f"✓ Birth data on file: {self.user_profile.place_of_birth}")
        else:
            print(f"⚠ Birth data incomplete - please update your profile")
        
        print()
        
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
        """Process query through orchestrator with user context."""
        print("\n🤔 Processing...\n")
        
        # Get conversation history
        history = []
        if self.enable_storage:
            history = self.store.get_history(self.session_id, max_turns=10)
        
        # Process through orchestrator (with user_id)
        result = self.orchestrator.process_query(
            query=query,
            conversation_history=history,
            user_id=self.user_id  # Pass user_id for authentication & profile
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
        
        # Show processing path (debug)
        if result.get("processing_path"):
            path = " → ".join(result["processing_path"])
            print(f"[Path: {path}]")
        
        if result.get("error"):
            print(f"⚠️  Note: {result['error']}")
        
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
            print(self.WELCOME_MESSAGE.format(user_name=self.user_profile.name.split()[0]))
        
        elif cmd == "/profile":
            self._show_profile()
        
        elif cmd == "/history":
            self._show_history()
        
        elif cmd == "/clear":
            if self.enable_storage:
                self.store.delete_session(self.session_id)
                self.session_id = self.store.create_session(
                    user_id=self.user_id,
                    metadata={
                        "phase": "5.1",
                        "orchestrated": True,
                        "user_name": self.user_profile.name
                    }
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
    
    def _show_profile(self):
        """Display user profile information."""
        print("\n" + "=" * 70)
        print("USER PROFILE")
        print("=" * 70)
        print(f"Name: {self.user_profile.name}")
        print(f"User ID: {self.user_profile.user_id}")
        print(f"Subscription: {self.user_profile.subscription_status} ({self.user_profile.subscription_tier})")
        print()
        print("Birth Data:")
        print(f"  Date: {self.user_profile.date_of_birth}")
        print(f"  Time: {self.user_profile.time_of_birth}")
        print(f"  Place: {self.user_profile.place_of_birth}")
        print(f"  Coordinates: ({self.user_profile.latitude}, {self.user_profile.longitude})")
        print()
        print("Preferences:")
        print(f"  Astrology System: {self.user_profile.preferred_system.title()}")
        print(f"  Language: {self.user_profile.language}")
        print("=" * 70)
    
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
            print(f"User: {self.user_profile.name} ({self.user_id})")
            print(f"Turns: {len(history)}")
            print(f"Storage: JSON (data/conversations/)")
        else:
            print("Storage: Disabled")
        
        print("=" * 70)


def select_user() -> str:
    """
    Interactive user selection for testing.
    
    In production, user_id would come from your app's authentication.
    """
    print("\n" + "=" * 70)
    print("USER AUTHENTICATION")
    print("=" * 70)
    print()
    
    # Get profile manager
    profile_manager = get_default_profile_manager()
    
    # List dummy users (if available)
    dummy_users = profile_manager.list_dummy_users()
    
    if dummy_users:
        print("Available test users:")
        for i, user_id in enumerate(dummy_users, 1):
            info = profile_manager.get_dummy_user_info(user_id)
            if info:
                print(f"  {i}. {info['name']} ({user_id})")
                print(f"     Status: {info['subscription']}")
                print(f"     Location: {info['location']}")
        print()
        
        choice = input("Select user (1-4) or enter user_id: ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(dummy_users):
            return dummy_users[int(choice) - 1]
        else:
            return choice
    else:
        # Manual entry
        return input("Enter user_id: ").strip()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Astrology AI Chatbot - Phase 5.1 (Authenticated)"
    )
    parser.add_argument(
        "--user",
        help="User ID (from your app's database)"
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
    
    # Get user_id
    user_id = args.user
    if not user_id:
        user_id = select_user()
    
    if not user_id:
        print("❌ User ID required")
        return
    
    try:
        # Initialize and run
        chatbot = AstrologyChatbotAuth(
            user_id=user_id,
            session_id=args.session,
            enable_storage=not args.no_storage
        )
        
        chatbot.run()
        
    except ValueError as e:
        print(f"\n❌ {e}")
        print("\nPlease verify:")
        print("  • User exists in database")
        print("  • Subscription is active")
        print("  • Birth data is complete (optional but recommended)")


if __name__ == "__main__":
    main()