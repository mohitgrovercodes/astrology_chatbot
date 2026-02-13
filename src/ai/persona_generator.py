# src\ai\persona_generator.py
"""
Persona Generator Module

Generates astrologer personas dynamically for any language using LLM.
Uses English personas as templates and adapts them to target languages.
"""

import json
import logging
from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class PersonaGenerator:
    """
    Generates language-specific astrologer personas using LLM.
    
    Features:
    - Generates Vedic and Western personas
    - Adapts terminology and cultural references
    - Maintains professional astrology standards
    - Uses English template as reference
    """
    
    def __init__(self, llm: BaseChatModel, english_locale: Dict[str, Any]):
        """
        Initialize persona generator.
        
        Args:
            llm: Language model for generation
            english_locale: English locale data to use as template
        """
        self.llm = llm
        self.english_locale = english_locale
    
    def generate_full_locale(
        self,
        language_code: str,
        language_name: str
    ) -> Dict[str, Any]:
        """
        Generate complete locale data for a language.
        
        Args:
            language_code: ISO language code (e.g., 'es', 'fr')
            language_name: Human-readable language name (e.g., 'Spanish', 'French')
            
        Returns:
            Complete locale dictionary with personas and templates
        """
        logger.info(f"Generating locale for {language_name} ({language_code})")
        
        try:
            # Generate both personas
            vedic_persona = self._generate_vedic_persona(language_code, language_name)
            western_persona = self._generate_western_persona(language_code, language_name)
            
            # Generate prompt templates
            prompt_templates = self._generate_prompt_templates(language_code, language_name)
            
            # Construct full locale
            locale_data = {
                "language_name": language_name,
                "prompt_templates": prompt_templates,
                "personas": {
                    "vedic": vedic_persona,
                    "western": western_persona
                }
            }
            
            logger.info(f"Successfully generated locale for {language_name}")
            return locale_data
            
        except Exception as e:
            logger.error(f"Error generating locale for {language_name}: {e}")
            raise
    
    def _generate_vedic_persona(
        self,
        language_code: str,
        language_name: str
    ) -> Dict[str, Any]:
        """Generate Vedic astrologer persona."""
        english_vedic = self.english_locale["personas"]["vedic"]
        
        prompt = f"""You are creating a professional Vedic astrologer persona for {language_name} language.

**English Template:**
{json.dumps(english_vedic, indent=2, ensure_ascii=False)}

**Task:**
Generate an equivalent Vedic astrologer persona in {language_name} that:

1. **Identity Section:**
   - Translate the identity description to natural {language_name}
   - Keep Sanskrit terms (BPHS, Jataka Parijata, etc.) in original form
   - Maintain the same structure and expertise level

2. **Guidelines Section:**
   - Adapt guidelines to {language_name} linguistic norms
   - Keep astrological terminology appropriate for {language_name} speakers
   - Maintain professional tone
   - Include guidance on using {language_name} naturally

3. **Timing Rules Section (if present):**
   - Translate critical timing rules to {language_name}
   - Keep the warnings about not fabricating dates

**Important:**
- Use natural {language_name} expressions
- Keep Sanskrit/technical terms where appropriate
- Maintain the same professional standards
- Adapt cultural references if needed

**Output Format:**
Return ONLY valid JSON matching this exact schema:
{{
    "identity": "string in {language_name}",
    "guidelines": ["array", "of", "strings", "in", "{language_name}"],
    "timing_rules": ["optional", "array", "if", "present"]
}}

Generate the persona now:"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            persona = json.loads(content)
            logger.info(f"Generated Vedic persona for {language_name}")
            return persona
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Vedic persona JSON for {language_name}: {e}")
            logger.error(f"Response content: {content}")
            # Fallback to English
            return english_vedic
        except Exception as e:
            logger.error(f"Error generating Vedic persona for {language_name}: {e}")
            return english_vedic
    
    def _generate_western_persona(
        self,
        language_code: str,
        language_name: str
    ) -> Dict[str, Any]:
        """Generate Western astrologer persona."""
        english_western = self.english_locale["personas"].get("western", {})
        
        if not english_western:
            logger.warning(f"No Western persona in English template, skipping for {language_name}")
            return {}
        
        prompt = f"""You are creating a professional Western astrologer persona for {language_name} language.

**English Template:**
{json.dumps(english_western, indent=2, ensure_ascii=False)}

**Task:**
Generate an equivalent Western astrologer persona in {language_name} that:

1. **Identity Section:**
   - Translate to natural {language_name}
   - Maintain psychological and modern astrology focus
   - Keep the same expertise level

2. **Guidelines Section:**
   - Adapt to {language_name} linguistic norms
   - Use appropriate Western astrology terminology
   - Maintain professional tone

**Output Format:**
Return ONLY valid JSON matching this schema:
{{
    "identity": "string in {language_name}",
    "guidelines": ["array", "of", "strings", "in", "{language_name}"]
}}

Generate the persona now:"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            persona = json.loads(content)
            logger.info(f"Generated Western persona for {language_name}")
            return persona
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Western persona JSON for {language_name}: {e}")
            return english_western
        except Exception as e:
            logger.error(f"Error generating Western persona for {language_name}: {e}")
            return english_western
    
    def _generate_prompt_templates(
        self,
        language_code: str,
        language_name: str
    ) -> Dict[str, str]:
        """Generate language-specific prompt templates."""
        english_templates = self.english_locale["prompt_templates"]
        
        prompt = f"""You are creating prompt templates for an astrology chatbot in {language_name}.

**English Templates:**
{json.dumps(english_templates, indent=2, ensure_ascii=False)}

**Task:**
Translate these prompt templates to natural {language_name}:

1. **header**: Professional standards header
2. **voice**: Voice guidelines header
3. **footer**: Reminder about being a professional astrologer
4. **brief_style**: Brief response style instruction
5. **detailed_style**: Detailed response style instruction
6. **offer_details**: Offer for more details

**Important:**
- Use natural {language_name} phrasing
- Maintain professional tone
- Keep the same meaning and intent

**Output Format:**
Return ONLY valid JSON matching this schema:
{{
    "header": "string in {language_name}",
    "voice": "string in {language_name}",
    "footer": "string in {language_name}",
    "brief_style": "string in {language_name}",
    "detailed_style": "string in {language_name}",
    "offer_details": "string in {language_name}"
}}

Generate the templates now:"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            templates = json.loads(content)
            logger.info(f"Generated prompt templates for {language_name}")
            return templates
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse templates JSON for {language_name}: {e}")
            return english_templates
        except Exception as e:
            logger.error(f"Error generating templates for {language_name}: {e}")
            return english_templates


def generate_persona_for_language(
    language_code: str,
    language_name: str,
    llm: BaseChatModel,
    english_locale: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to generate a complete locale for a language.
    
    Args:
        language_code: ISO code (e.g., 'es')
        language_name: Full name (e.g., 'Spanish')
        llm: Language model
        english_locale: English locale as template
        
    Returns:
        Complete locale dictionary
    """
    generator = PersonaGenerator(llm, english_locale)
    return generator.generate_full_locale(language_code, language_name)
