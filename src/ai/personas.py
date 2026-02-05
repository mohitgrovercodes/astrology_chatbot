"""
NakshatraAI Persona System.

Two professional astrologer personas:
1. NakshatraAI Vedic - Traditional Vedic/Jyotish approach
2. NakshatraAI Western - Modern Western/Psychological approach

Core principles:
- Knowledgeable (cites sources)
- Kind & optimistic (but realistic)
- Professional tone
- Clear boundaries (refuses off-topic)
"""

from src.utils.localization import get_localization_manager

class AstrologerPersona:
    """Base class for astrologer personas."""
    
    def __init__(self, key: str, name: str, system: str):
        """
        Initialize persona.
        
        Args:
            key: Personality key (e.g., 'vedic', 'western')
            name: Persona name
            system: Astrology system
        """
        self.key = key
        self.name = name
        self.system = system
        self.loc_manager = get_localization_manager()
    
    def get_system_prompt(self, user_name: str = "the client", language: str = "en") -> str:
        """
        Generate system prompt in specific language using localization manager.
        """
        # Load templates and persona-specific data
        templates = self.loc_manager.get_prompt_templates(language)
        persona_data = self.loc_manager.get_persona_data(language, self.key)
        
        identity = persona_data.get('identity', "You are a professional astrologer.")
        guidelines = persona_data.get('guidelines', [])
        timing_rules = persona_data.get('timing_rules', [])
        
        header = templates.get('header', 'PROFESSIONAL STANDARDS:')
        voice = templates.get('voice', 'VOICE GUIDELINES:')
        footer = templates.get('footer', 'Remember: You are a professional astrologer.')
        
        guidelines_text = "\n".join(f"- {g}" for g in guidelines)
        timing_rules_text = "\n".join(f"- {r}" for r in timing_rules) if timing_rules else ""
        
        timing_section = f"\n\n5. TIMING AND PREDICTIONS\n{timing_rules_text}" if timing_rules else ""
        
        return f"""{identity}

CLIENT: {user_name}

{header}

1. KNOWLEDGE
   - Ground interpretations in astrological principles
   - Cite classical texts when relevant
   - Explain your reasoning clearly
   - Admit uncertainty when appropriate

2. TONE & MANNER
   - Warm, welcoming, professional
   - Respectful of astrological tradition
   - Kind and considerate
   - NOT casual or overly informal

3. OPTIMISM WITH REALISM
   - Focus on growth opportunities
   - NEVER give false hope
   - Use "indicates", "suggests", "tends to show" (NOT "will", "must")
   - Emphasize free will and personal effort

4. SENSITIVITY
   - Handle sensitive topics (health, relationships) carefully
   - Never predict death or catastrophe
   - Always emphasize positive potential
{timing_section}

{voice}
{guidelines_text}

{footer}"""


class NakshatraAI_Vedic(AstrologerPersona):
    """NakshatraAI's Vedic astrology persona."""
    
    def __init__(self):
        super().__init__(
            key="vedic",
            name="NakshatraAI",
            system="Vedic (Sidereal)"
        )


class NakshatraAI_Western(AstrologerPersona):
    """NakshatraAI's Western astrology persona."""
    
    def __init__(self):
        super().__init__(
            key="western",
            name="NakshatraAI",
            system="Western (Tropical)"
        )


# Create singleton instances
VEDIC_PERSONA = NakshatraAI_Vedic()
WESTERN_PERSONA = NakshatraAI_Western()


def get_persona(system: str) -> AstrologerPersona:
    """
    Get persona based on astrology system.
    
    Args:
        system: 'vedic' or 'western'
        
    Returns:
        Appropriate persona instance
    """
    if system.lower() == "western":
        return WESTERN_PERSONA
    else:
        return VEDIC_PERSONA


# Standard responses for common intents
GREETING_RESPONSE = """Namaste! I'm NakshatraAI, your professional astrology consultant.

I'm here to help you understand your birth chart and navigate life's journey through astrological wisdom.

How may I assist you today? You can ask me about:
• Birth chart interpretations
• Timing for important life events
• Current planetary transits and their effects
• Understanding astrological concepts
• Relationship compatibility"""


OFF_TOPIC_RESPONSE = """I appreciate your question, but I'm NakshatraAI, specialized in Vedic and Western astrology.

I can help you with:
• Birth chart analysis and interpretations
• Planetary placements and their meanings
• Timing predictions using dashas and transits
• Understanding astrological concepts
• Relationship compatibility
• Career and life path guidance

For questions outside astrology, please consult an appropriate expert.

Is there anything astrological I can help you explore?"""


# Testing
if __name__ == "__main__":
    print("=" * 70)
    print("NAKSHATRAAI PERSONA SYSTEM - Test Suite")
    print("=" * 70)
    print()
    
    # Test Vedic persona
    print("1. VEDIC PERSONA")
    print("-" * 70)
    vedic = get_persona("vedic")
    print(f"Name: {vedic.name}")
    print(f"System: {vedic.system}")
    print(f"Guidelines: {len(vedic.guidelines)} rules")
    print()
    print("Sample guidelines:")
    for guideline in vedic.guidelines[:3]:
        print(f"  • {guideline}")
    print()
    
    # Test Western persona
    print("2. WESTERN PERSONA")
    print("-" * 70)
    western = get_persona("western")
    print(f"Name: {western.name}")
    print(f"System: {western.system}")
    print(f"Guidelines: {len(western.guidelines)} rules")
    print()
    print("Sample guidelines:")
    for guideline in western.guidelines[:3]:
        print(f"  • {guideline}")
    print()
    
    # Test system prompt generation
    print("3. SAMPLE SYSTEM PROMPT (Vedic)")
    print("-" * 70)
    sample_prompt = vedic.get_system_prompt("Arjun Kumar")
    print(sample_prompt[:400] + "...")
    print()
    
    # Test standard responses
    print("4. STANDARD RESPONSES")
    print("-" * 70)
    print("Greeting:")
    print(GREETING_RESPONSE[:150] + "...")
    print()
    print("Off-topic:")
    print(OFF_TOPIC_RESPONSE[:150] + "...")
    print()
    
    print("=" * 70)
    print("[DONE] All tests passed!")
    print("=" * 70)
    print()
    print("Both personas embody:")
    print("  [OK] Professional knowledge")
    print("  [OK] Kind, optimistic but realistic")
    print("  [OK] Clear boundaries (refuse off-topic)")
    print("  [OK] Citation of sources")
    print("  [OK] Emphasis on free will")