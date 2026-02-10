import os
import json
from typing import Dict, List, Optional, Any
from langchain_core.language_models import BaseChatModel
import logging

logger = logging.getLogger(__name__)


class LocalizationManager:
    """
    Manager for loading and accessing localization data from JSON files.
    
    All personas are pre-generated and stored in src/locales/.
    Supports 40+ languages including all major Indian and foreign languages.
    """
    

    
    def __init__(self, locales_dir: str = None):
        if locales_dir is None:
            # Default to src/locales relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            locales_dir = os.path.join(base_dir, 'locales')
            
        self.locales_dir = locales_dir
        
        # All locales loaded from disk
        self.locales: Dict[str, Dict] = {}
        
        self._load_locales()
        
    def _load_locales(self):
        """Load all manual JSON files from the locales directory."""
        if not os.path.exists(self.locales_dir):
            logger.warning(f"[LOCALIZATION] Locales directory not found: {self.locales_dir}")
            return
            
        for filename in os.listdir(self.locales_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                filepath = os.path.join(self.locales_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.locales[lang_code] = json.load(f)
                    logger.info(f"[LOCALIZATION] Loaded locale: {lang_code}")
                except Exception as e:
                    logger.error(f"[LOCALIZATION] Failed to load {filename}: {e}")
    

    
    def get_supported_languages(self) -> List[str]:
        """Return list of all supported language codes."""
        return list(self.locales.keys())
        
    def get_language_name(self, lang_code: str) -> str:
        """Return human-readable name for a language code."""
        if lang_code in self.locales:
            return self.locales[lang_code].get('language_name', 'English')
        return lang_code
        
    def get_prompt_templates(self, lang_code: str) -> Dict[str, str]:
        """Return prompt templates for a language."""
        if lang_code in self.locales:
            return self.locales[lang_code].get('prompt_templates', {})
        
        # Fallback to English
        return self.locales.get('en', {}).get('prompt_templates', {})
        
    def get_persona_data(
        self,
        lang_code: str,
        persona_type: str,
        llm: Optional[BaseChatModel] = None
    ) -> Dict[str, Any]:
        """
        Return identity and guidelines for a specific persona and language.
        
        All personas are pre-generated and loaded from disk.
        Falls back to English if language not found.
        
        Args:
            lang_code: Language code (e.g., 'es', 'fr')
            persona_type: 'vedic' or 'western'
            llm: Unused (kept for backward compatibility)
            
        Returns:
            Persona dictionary with identity and guidelines
        """
        # Check if language exists
        if lang_code in self.locales:
            persona = self.locales[lang_code].get('personas', {}).get(persona_type, {})
            if persona:
                logger.debug(f"[LOCALIZATION] Using locale for {lang_code}/{persona_type}")
                return persona
        
        # Fallback to English
        logger.warning(f"[LOCALIZATION] Falling back to English for {lang_code}/{persona_type}")
        return self.locales.get('en', {}).get('personas', {}).get(persona_type, {})

    def get_language_map(self) -> Dict[str, str]:
        """Return a map of code to descriptive name for all locales."""
        result = {}
        
        # Manual locales
        for code, data in self.locales.items():
            result[code] = data.get('language_name', code)
        
        # Generated locales
        for code, data in self._persona_cache.items():
            if code not in result:
                result[code] = data.get('language_name', code)
        
        return result


# Singleton instance
_manager = None


def get_localization_manager() -> LocalizationManager:
    global _manager
    if _manager is None:
        _manager = LocalizationManager()
    return _manager
