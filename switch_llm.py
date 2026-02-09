"""
Interactive CLI utility to switch between LLM providers and models.
Updates the .env file automatically.
"""

import os
import sys
from dotenv import load_dotenv, set_key
from pathlib import Path

# Try to import factory to get valid providers
try:
    from src.llm.factory import LLMFactory
    FACTORY_AVAILABLE = True
except ImportError:
    FACTORY_AVAILABLE = False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_env_path():
    return Path(__file__).parent / ".env"

def main():
    env_path = get_env_path()
    if not env_path.exists():
        print(f"❌ .env file not found at {env_path}")
        return

    load_dotenv(env_path)

    while True:
        clear_screen()
        print("=" * 60)
        print("🤖 NakshatraAI - LLM Provider Switcher")
        print("=" * 60)
        print()
        
        current_provider = os.getenv("LLM_PROVIDER", "ollama")
        current_model = os.getenv("LLM_MODEL", "qwen3:8b")
        
        print(f"Current Configuration:")
        print(f"  Provider: {current_provider}")
        print(f"  Model:    {current_model}")
        print()
        print("Available Providers:")
        print("  1. OpenAI (Default)")
        print("  2. Ollama (Local/Remote)")
        print("  q. Quit")
        print()
        
        choice = input("Select provider (1-3) or 'q': ").strip().lower()
        
        if choice == 'q':
            break
            
        new_provider = ""
        models = []
        
        if choice == '1':
            new_provider = "openai"
            models = ["gpt-4o-mini", "gpt-4o", "o1-mini"]
        elif choice == '2':
            new_provider = "ollama"
            models = ["qwen3:8b", "phi4", "qwen2.5:7b", "custom"]
        else:
            continue

        print(f"\nSelect a model for {new_provider}:")
        for i, m in enumerate(models, 1):
            print(f"  {i}. {m}")
        
        m_choice = input(f"Select model (1-{len(models)}) [Default 1]: ").strip()
        
        if not m_choice:
            new_model = models[0]
        else:
            try:
                idx = int(m_choice) - 1
                if 0 <= idx < len(models):
                    new_model = models[idx]
                    if new_model == "custom":
                        new_model = input("Enter custom model name (e.g., deepseek-r1:7b): ").strip()
                else:
                    print("Invalid choice.")
                    input("Press Enter to continue...")
                    continue
            except ValueError:
                print("Invalid input.")
                input("Press Enter to continue...")
                continue

        # Update .env
        print(f"\nUpdating {env_path}...")
        set_key(str(env_path), "LLM_PROVIDER", new_provider)
        set_key(str(env_path), "LLM_MODEL", new_model)
        
        # Also update legacy/alias if present
        set_key(str(env_path), "DEFAULT_LLM_PROVIDER", new_provider)
        set_key(str(env_path), "DEFAULT_LLM_MODEL", new_model)

        print(f"✅ Successfully switched to {new_provider} / {new_model}")
        
        verify = input("\nWould you like to verify the connection? (y/n) [n]: ").strip().lower()
        if verify == 'y':
            print("\nVerifying...")
            # Reload env for this process
            load_dotenv(env_path, override=True)
            try:
                if FACTORY_AVAILABLE:
                    llm = LLMFactory.create()
                    response = llm.invoke("Hi, are you ready?")
                    print(f"✅ Connection successful!")
                    print(f"Response: {response.content[:50]}...")
                else:
                    print("⚠️ Factory not available for direct verification.")
            except Exception as e:
                print(f"❌ Verification failed: {e}")
        
        input("\nPress Enter to return to menu...")

if __name__ == "__main__":
    main()
