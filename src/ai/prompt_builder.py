# src/ai/prompt_builder.py
# src\ai\prompt_builder.py
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
        
        # User Profile - Enhanced with more details
        profile_section = f"""USER PROFILE (Use this information to answer questions about the user):
• Name: {user_profile.get('name', 'User')}
• Date of Birth: {user_profile.get('date_of_birth', 'Unknown')}
• Time of Birth: {user_profile.get('time_of_birth', 'Unknown')}
• Place of Birth: {user_profile.get('place_of_birth', 'Unknown')}
• Latitude: {user_profile.get('latitude', 'Unknown')}
• Longitude: {user_profile.get('longitude', 'Unknown')}
• Timezone: {user_profile.get('timezone', 'Unknown')}
• Preferred System: {user_profile.get('preferred_system', 'vedic').title()}
• Language: {user_profile.get('language', 'en')}"""
        sections.append(profile_section)
        
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
        sections.append(f"\n====USER_QUERY_MARKER====\n\"{query}\"")
        
        # Instructions
        sections.append(f"\nRESPOND:\n{self._get_instructions(intent, language)}")
        
        return "\n".join(sections)
    
    def _format_conversation(self, turns: List[Dict]) -> str:
        lines = []
        for t in turns:
            # Handle standard role/content format
            if 'role' in t and 'content' in t:
                role_label = "User" if t['role'] == "user" else "You"
                lines.append(f"{role_label}: {t['content']}")
            # Handle legacy format
            elif 'user' in t:
                lines.append(f"User: {t['user']}")
            elif 'assistant' in t:
                lines.append(f"You: {t['assistant'][:150]}...")
        return "\n".join(lines) if lines else "No previous context"
    
    def _format_chart(self, chart: Dict, system: str) -> str:
        if system.lower() == "vedic":
            return f"Lagna: {chart.get('lagna', {}).get('sign', '?')}, Rashi: {chart.get('planets', {}).get('MOON', {}).get('sign', '?')}, Sun: {chart.get('planets', {}).get('SUN', {}).get('sign', '?')}"
        else:
            return f"Sun: {chart.get('planets', {}).get('SUN', {}).get('sign', '?')}, Moon: {chart.get('planets', {}).get('MOON', {}).get('sign', '?')}, Asc: {chart.get('ascendant', {}).get('sign', '?')}"
    
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
        """Generate contextual guidance based on WHAT the user is actually asking."""
        q = query.lower()
        parts = []

        if intent in ["PREDICTION", "RAG_WITH_CALCULATION"]:
            parts.append("Analyze the chart, dasha, and transits together. Be insightful but realistic — never guarantee outcomes.")

            # Timing guidance — activated when user asks about timing semantically
            if any(w in q for w in ['when', 'timing', 'what time', 'which year', 'kab', 'kab hoga',
                                     'which month', 'what period', 'kitne din', 'how long']):
                parts.append("""
TIMING — You MUST give specific timeframes:
- Near-term: "February–March 2026"
- Mid-term: "April–June 2026"
- Longer: "Late 2026 to 2027"
NEVER say just "during Saturn Mahadasha" — always include actual months or seasons.""")

            # Compatibility guidance — marriage, relationships, partner
            if any(w in q for w in ['marriage', 'shaadi', 'vivah', 'partner', 'spouse', 'compatibility',
                                     'relationship', 'love', 'husband', 'wife', 'rishta']):
                parts.append("""
COMPATIBILITY — Discuss 7th house, Venus, and Jupiter placement. Speak of tendencies and patterns, not guarantees.""")

            # Career guidance — job, profession, business
            if any(w in q for w in ['career', 'job', 'profession', 'business', 'work', 'naukri',
                                     'promotion', 'success', 'money', 'income', 'finance', 'wealth',
                                     'paisa', 'kaam', 'vyapar']):
                parts.append("""
CAREER — Focus on 10th house, Saturn, Sun, and active Dasha lord's significations. Discuss periods of professional growth.""")

            # Health guidance
            if any(w in q for w in ['health', 'illness', 'disease', 'sick', 'body', 'swasth',
                                     'problem', 'pain', 'bimari', 'sehat']):
                parts.append("""
HEALTH — Discuss constitutional tendencies from 6th house and lagna. Always add: chart shows tendencies, not diagnosis — consult a doctor.""")

            parts.append("""
VOICE — English names first, Sanskrit in parentheses. Example: "Mars (Mangal)" not "Mangal (Mars)". Max 2-3 Sanskrit terms per paragraph. Always explain what a placement MEANS for this person.""")

        elif intent in ["INTERPRETATION", "RAG_ONLY"]:
            parts.append("Explain the astrological meaning clearly. Cite classical texts when relevant.")
            parts.append("Keep language accessible: say 'career house' before '10th Bhava', 'planetary period' before 'Dasha'. Explain concepts, don't just list them.")

        elif intent == "LEARNING":
            parts.append("Teach the concept clearly with a real example. Use analogies where helpful. Verify accuracy against classical principles.")

        return "\n".join(parts) if parts else None
    
    def _get_instructions(self, intent: str, language: str = "en") -> str:
        """Generate response instructions dynamically based on intent AND language."""
        from src.locales.language_detector import get_language_detector
        detector = get_language_detector()
        lang_name = detector.get_language_name(language)

        # Build language enforcement instruction
        if "-lat" in language:
            lang_instr = f"Respond entirely in {lang_name} using ROMAN ALPHABET (English script only, NOT native script)."
        elif language != "en":
            lang_instr = f"Respond entirely in {lang_name} (native script)."
        else:
            lang_instr = "Respond in clear, professional English."

        # Build tone instruction based on what the conversation is about
        base = (
            "Be professional, warm, and conversational. "
            "Speak as a knowledgeable astrologer — insightful and empathetic, not robotic. "
            "Explain clearly without unnecessary jargon. "
            "IMPORTANT: Limit your response to a maximum of 300 words."
        )

        if intent in ["PREDICTION", "RAG_WITH_CALCULATION"]:
            return (
                f"{base} "
                "Focus on the most relevant astrological factor for this specific question. "
                "NO greetings (Namaste, Hello, etc.) — get straight to the analysis. "
                "When timing is asked, give specific months or seasons — never just dasha names. "
                "Emphasize that free will and effort shape outcomes. "
                f"{lang_instr}"
            )
        elif intent in ["INTERPRETATION", "RAG_ONLY"]:
            return (
                f"{base} "
                "Ground your interpretation in classical principles. "
                "Cite texts only when they genuinely support the point. "
                "Prioritize clarity: English planet names first, Sanskrit in parentheses. "
                f"{lang_instr}"
            )
        elif intent == "LEARNING":
            return (
                f"{base} "
                "Teach the concept step by step. Use one concrete example per key idea. "
                f"{lang_instr}"
            )

        return f"{base} {lang_instr}"

if __name__ == "__main__":
    print("PromptBuilder class loaded successfully")