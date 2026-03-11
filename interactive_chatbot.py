# interactive_chatbot.py
"""
Interactive Chatbot with Redis Backend

Usage:
    python interactive_chatbot.py

This script provides an interactive chat interface that uses the Redis-based API.
Similar to chatbot.py but works with the new stateless architecture.
"""

import requests
import json
import os
import sys
from datetime import datetime
from typing import Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:6262/api/v1/chat"

# Colors for terminal
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


# ============================================================================
# USER PROFILE COLLECTION
# ============================================================================

def collect_user_profile():
    """Collect user birth details interactively."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}Welcome to NakshatraAI - Vedic Astrology Chatbot{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")
    
    print(f"{Colors.YELLOW}To provide accurate astrological insights, I need your birth details.{Colors.ENDC}\n")
    
    # Name
    name = input(f"{Colors.CYAN}Your name: {Colors.ENDC}").strip()
    if not name:
        name = "User"
    
    # Date of birth
    while True:
        dob = input(f"{Colors.CYAN}Date of birth (YYYY-MM-DD): {Colors.ENDC}").strip()
        try:
            datetime.strptime(dob, "%Y-%m-%d")
            break
        except ValueError:
            print(f"{Colors.RED}Invalid format. Please use YYYY-MM-DD (e.g., 1990-07-15){Colors.ENDC}")
    
    # Time of birth
    while True:
        tob = input(f"{Colors.CYAN}Time of birth (HH:MM:SS, 24-hour format): {Colors.ENDC}").strip()
        try:
            datetime.strptime(tob, "%H:%M:%S")
            break
        except ValueError:
            print(f"{Colors.RED}Invalid format. Please use HH:MM:SS (e.g., 14:30:00){Colors.ENDC}")
    
    # Place of birth
    place = input(f"{Colors.CYAN}Place of birth: {Colors.ENDC}").strip()
    if not place:
        place = "Unknown"
    
    # Coordinates
    print(f"\n{Colors.YELLOW}Birth coordinates (you can find these on Google Maps):{Colors.ENDC}")
    while True:
        try:
            lat = float(input(f"{Colors.CYAN}Latitude (-90 to 90): {Colors.ENDC}").strip())
            if -90 <= lat <= 90:
                break
            print(f"{Colors.RED}Latitude must be between -90 and 90{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number{Colors.ENDC}")
    
    while True:
        try:
            lng = float(input(f"{Colors.CYAN}Longitude (-180 to 180): {Colors.ENDC}").strip())
            if -180 <= lng <= 180:
                break
            print(f"{Colors.RED}Longitude must be between -180 and 180{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number{Colors.ENDC}")
    
    # Timezone (optional)
    timezone = input(f"{Colors.CYAN}Timezone (press Enter for Asia/Kolkata): {Colors.ENDC}").strip()
    if not timezone:
        timezone = "Asia/Kolkata"
    
    # Generate user_id
    user_id = f"user_{int(datetime.now().timestamp())}"
    
    profile = {
        "user_id": user_id,
        "name": name,
        "date_of_birth": dob,
        "time_of_birth": tob,
        "place_of_birth": place,
        "latitude": lat,
        "longitude": lng,
        "timezone": timezone,
        "preferred_system": "vedic"
    }
    
    return user_id, profile


# ============================================================================
# API FUNCTIONS
# ============================================================================

def initialize_session(user_id: str, user_profile: dict) -> bool:
    """Initialize chatbot session."""
    print(f"\n{Colors.YELLOW}Initializing session...{Colors.ENDC}")
    
    payload = {
        "user_id": user_id,
        "user_profile": user_profile,
        "conversation_history": []
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/initialize",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                print(f"{Colors.GREEN}✓ Session initialized successfully!{Colors.ENDC}\n")
                return True
            else:
                print(f"{Colors.RED}✗ Session initialization failed: {data}{Colors.ENDC}")
                return False
        else:
            print(f"{Colors.RED}✗ API error: {response.status_code}{Colors.ENDC}")
            print(response.text)
            return False
    
    except requests.exceptions.ConnectionError:
        print(f"{Colors.RED}✗ Cannot connect to API. Is it running on port 6262?{Colors.ENDC}")
        print(f"{Colors.YELLOW}Start it with: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 6262{Colors.ENDC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
        return False


def send_message(user_id: str, question: str) -> Optional[dict]:
    """Send a message to the chatbot."""
    payload = {
        "user_id": user_id,
        "question": question
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/message",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"{Colors.RED}✗ Session not found. Please restart the chatbot.{Colors.ENDC}")
            return None
        else:
            print(f"{Colors.RED}✗ API error: {response.status_code}{Colors.ENDC}")
            print(response.text)
            return None
    
    except requests.exceptions.Timeout:
        print(f"{Colors.RED}✗ Request timeout. The chatbot is taking too long to respond.{Colors.ENDC}")
        return None
    except Exception as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
        return None


# ============================================================================
# CHAT INTERFACE
# ============================================================================

def print_bot_response(response: dict):
    """Print bot response in a nice format."""
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}NakshatraAI:{Colors.ENDC}")
    print(f"{Colors.MAGENTA}{response['answer']}{Colors.ENDC}\n")
    
    # Show source indicator
    source = response.get('source', 'unknown')
    if source == 'openai':
        source_icon = "🤖"
    else:
        source_icon = "📦"
    
    print(f"{Colors.CYAN}[{source_icon} Source: {source}]{Colors.ENDC}")
    print(f"{Colors.CYAN}{'─'*70}{Colors.ENDC}")


def show_help():
    """Show help commands."""
    print(f"\n{Colors.YELLOW}Available commands:{Colors.ENDC}")
    print(f"{Colors.CYAN}/help{Colors.ENDC}     - Show this help")
    print(f"{Colors.CYAN}/status{Colors.ENDC}   - Show session status")
    print(f"{Colors.CYAN}/clear{Colors.ENDC}    - Clear screen")
    print(f"{Colors.CYAN}/exit{Colors.ENDC}     - Exit chatbot")
    print(f"{Colors.CYAN}/quit{Colors.ENDC}     - Exit chatbot\n")


def get_session_status(user_id: str):
    """Get and display session status."""
    try:
        response = requests.get(f"{API_BASE_URL}/session/{user_id}/status")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
            print(f"{Colors.CYAN}{Colors.BOLD}Session Status{Colors.ENDC}")
            print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
            print(f"Session ID: {data.get('session_id')}")
            print(f"User ID: {data.get('user_id')}")
            print(f"Messages in history: {data.get('cached_data', {}).get('conversation_messages', 0)}")
            print(f"Chart cached: {'✓' if data.get('cached_data', {}).get('chart_data') else '✗'}")
            print(f"Dasha cached: {'✓' if data.get('cached_data', {}).get('dasha_data') else '✗'}")
            print(f"Context window: {data.get('context_window_size', 5)} messages")
            print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
        else:
            print(f"{Colors.RED}Failed to get session status{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Error getting status: {e}{Colors.ENDC}")


def chat_loop(user_id: str, user_name: str):
    """Main chat loop."""
    print(f"\n{Colors.GREEN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.GREEN}{Colors.BOLD}Chat started! Ask me anything about your astrology.{Colors.ENDC}")
    print(f"{Colors.GREEN}Type /help for commands or /exit to quit{Colors.ENDC}")
    print(f"{Colors.GREEN}{'='*70}{Colors.ENDC}\n")
    
    message_count = 0
    
    while True:
        try:
            # Get user input
            user_input = input(f"{Colors.BLUE}{Colors.BOLD}You: {Colors.ENDC}").strip()
            
            # Handle empty input
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ['/exit', '/quit']:
                print(f"\n{Colors.YELLOW}Thank you for chatting! Namaste! 🙏{Colors.ENDC}\n")
                break
            
            elif user_input.lower() == '/help':
                show_help()
                continue
            
            elif user_input.lower() == '/status':
                get_session_status(user_id)
                continue
            
            elif user_input.lower() == '/clear':
                os.system('cls' if os.name == 'nt' else 'clear')
                continue
            
            # Send message to chatbot
            print(f"\n{Colors.YELLOW}⏳ Thinking...{Colors.ENDC}")
            
            response = send_message(user_id, user_input)
            
            if response:
                # Clear the "Thinking..." line
                print("\033[F\033[K", end='')  # Move up and clear line
                
                print_bot_response(response)
                message_count += 1
                
                # Show cache info on first few messages
                if message_count <= 3:
                    print(f"{Colors.CYAN}[IDEA] Tip: Your chart data is being cached for faster responses{Colors.ENDC}\n")
            else:
                print(f"{Colors.RED}Failed to get response. Please try again.{Colors.ENDC}\n")
        
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Chat interrupted. Type /exit to quit properly.{Colors.ENDC}\n")
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.ENDC}\n")


# ============================================================================
# QUICK START MODE
# ============================================================================

def quick_start():
    """Quick start with demo profile."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}Quick Start Mode{Colors.ENDC}")
    print(f"{Colors.YELLOW}Using demo profile for quick testing...{Colors.ENDC}\n")
    
    user_id = f"demo_user_{int(datetime.now().timestamp())}"
    
    profile = {
        "user_id": user_id,
        "name": "Demo User",
        "date_of_birth": "1990-07-15",
        "time_of_birth": "08:30:00",
        "place_of_birth": "New Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic"
    }
    
    print(f"{Colors.CYAN}Demo Profile:{Colors.ENDC}")
    print(f"  Name: {profile['name']}")
    print(f"  DOB: {profile['date_of_birth']} at {profile['time_of_birth']}")
    print(f"  Place: {profile['place_of_birth']}")
    
    return user_id, profile


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main function."""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}")
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║                                                                 ║")
    print("║              NakshatraAI - Interactive Chatbot                  ║")
    print("║              Powered by Redis & OpenAI                          ║")
    print("║                                                                 ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")
    
    # Check if quick start argument
    if len(sys.argv) > 1 and sys.argv[1] == '--demo':
        user_id, profile = quick_start()
    else:
        # Ask user preference
        print(f"{Colors.YELLOW}Choose an option:{Colors.ENDC}")
        print(f"{Colors.CYAN}1.{Colors.ENDC} Enter your birth details")
        print(f"{Colors.CYAN}2.{Colors.ENDC} Quick start with demo profile")
        
        choice = input(f"\n{Colors.CYAN}Your choice (1/2): {Colors.ENDC}").strip()
        
        if choice == '2':
            user_id, profile = quick_start()
        else:
            user_id, profile = collect_user_profile()
    
    # Initialize session
    if not initialize_session(user_id, profile):
        print(f"\n{Colors.RED}Failed to initialize session. Exiting.{Colors.ENDC}\n")
        return
    
    # Start chat
    chat_loop(user_id, profile['name'])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Goodbye! 👋{Colors.ENDC}\n")
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.ENDC}\n")
        import traceback
        traceback.print_exc()
