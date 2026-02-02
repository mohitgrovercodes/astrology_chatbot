"""
Dynamic Prompt Builder for NakshatraAI.
Builds context-aware prompts - NO rigid templates.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime


class PromptBuilder:
    """Dynamic prompt construction for NakshatraAI."""
    
    def build_prompt(
        self,
        query: str,
        intent: str,
        user_profile: Dict[str, Any],
        birth_chart: Optional[Dict] = None,
        transits: Optional[Dict] = None,
        dasha: Optional[Dict] = None,
        knowledge_chunks: Optional[List] = None,
        conversation_history: Optional[List[Dict]] = None,
        language: str = "en"
    ) -> str:
        """Build dynamic prompt for query."""
        
        # Get persona
        try:
            from .personas import get_persona
            persona = get_persona(user_profile.get('preferred_system', 'vedic'))
            system_prompt = persona.get_system_prompt(
                user_name=user_profile.get('name', 'Client'),
                language=language
            )
        except:
            system_prompt = f"You are NakshatraAI, a professional astrologer.\nCLIENT: {user_profile.get('name', 'Client')}"
        
        sections = [system_prompt]
        
        # User Profile
        sections.append(f"""USER PROFILE:
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth', 'Unknown')}
• Time of Birth: {user_profile.get('time_of_birth', 'Unknown')}
• Place of Birth: {user_profile.get('place_of_birth', 'Unknown')}""")
        
        # Conversation context
        if conversation_history:
            sections.append(f"\nCONTEXT:\n{self._format_conversation(conversation_history[-3:])}")
        
        # Chart data
        if birth_chart and intent in ["PREDICTION", "CALCULATION", "INTERPRETATION"]:
            sections.append(f"\nCHART:\n{self._format_chart(birth_chart, user_profile.get('preferred_system', 'vedic'))}")
        
        # Current conditions
        if intent == "PREDICTION" and (transits or dasha):
            sections.append(f"\nCURRENT:\n{self._format_conditions(transits, dasha)}")
        
        # Knowledge
        if knowledge_chunks:
            sections.append(f"\nKNOWLEDGE:\n{self._format_knowledge(knowledge_chunks)}")
        
        # Guidance
        guidance = self._get_guidance(intent, query)
        if guidance:
            sections.append(f"\nGUIDANCE:\n{guidance}")
        
        # Query
        sections.append(f"\nQUESTION:\n\"{query}\"")
        
        # Instructions
        sections.append(f"\nRESPOND:\n{self._get_instructions(intent, language)}")
        
        return "\n".join(sections)
    
    def _format_conversation(self, turns: List[Dict]) -> str:
        lines = []
        for t in turns:
            if 'user' in t:
                lines.append(f"User: {t['user']}")
            if 'assistant' in t:
                lines.append(f"You: {t['assistant'][:150]}...")
        return "\n".join(lines) if lines else "No previous context"
    
    def _format_chart(self, chart: Dict, system: str) -> str:
        if system.lower() == "vedic":
            return f"Lagna: {chart.get('lagna', '?')}, Rashi: {chart.get('rashi', '?')}, Sun: {chart.get('sun_sign', '?')}"
        else:
            return f"Sun: {chart.get('sun_sign', '?')}, Moon: {chart.get('moon_sign', '?')}, Asc: {chart.get('ascendant', '?')}"
    
    def _format_conditions(self, transits: Optional[Dict], dasha: Optional[Dict]) -> str:
        parts = [f"Date: {datetime.now().strftime('%B %d, %Y')}"]
        if dasha:
            parts.append(f"Dasha: {dasha.get('mahadasha', '?')}/{dasha.get('antardasha', '?')}")
        return "\n".join(parts)
    
    def _format_knowledge(self, chunks: List) -> str:
        texts = []
        for i, c in enumerate(chunks[:3], 1):
            text = c.page_content[:200] if hasattr(c, 'page_content') else str(c)[:200]
            texts.append(f"[{i}] {text}...")
        return "\n".join(texts)
    
    def _get_guidance(self, intent: str, query: str) -> Optional[str]:
        if intent == "PREDICTION":
            return "Analyze chart + transits. Be optimistic but realistic. Never guarantee."
        elif intent == "INTERPRETATION":
            return "Explain meaning. Cite texts when relevant."
        elif intent == "LEARNING":
            return "Teach concept clearly."
        return None
    
    def _get_instructions(self, intent: str, language: str = "en") -> str:
        base = "Be professional, warm, clear. Cite sources."
        if language == "hi":
            base = "पेशेवर, मिलनसार और स्पष्ट रहें। स्रोतों का हवाला दें।"
        elif language == "ta":
            base = "தொழில்முறை, அன்பான மற்றும் தெளிவாக இருங்கள். ஆதாரங்களைக் குறிப்பிடவும்."
            
        lang_instruction = f" Respond entirely in {language}." if language != "en" else ""
        
        if intent == "PREDICTION":
            pred = " Focus on timing. Emphasize free will."
            if language == "hi": pred = " समय (timing) पर ध्यान दें। स्वतंत्र इच्छा (free will) पर जोर दें।"
            elif language == "ta": pred = " நேரத்தின் முக்கியத்துவத்தில் (timing) கவனம் செலுத்துங்கள். விருப்ப சுதந்திரத்தை (free will) வலியுறுத்துங்கள்."
            return base + pred + lang_instruction
            
        return base + lang_instruction


if __name__ == "__main__":
    print("PromptBuilder class loaded successfully")