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
        
        System attempts to load:
        1. Exact match (e.g., 'hi-lat')
        2. Base language match (e.g., 'hi')
        3. Fallback to English ('en')
        """
        # 1. Try exact match
        if lang_code in self.locales:
            persona = self.locales[lang_code].get('personas', {}).get(persona_type, {})
            if persona:
                return persona
                
        # 2. Try base language (handle -lat suffix)
        if "-lat" in lang_code:
            base_code = lang_code.split("-")[0]
            if base_code in self.locales:
                # Use base persona (content is in native script, but PromptBuilder dictates output script)
                target_persona = self.locales[base_code].get('personas', {}).get(persona_type, {})
                if target_persona:
                    return target_persona

        # 3. Fallback to English
        return self.locales.get('en', {}).get('personas', {}).get(persona_type, {})

    def get_language_map(self) -> Dict[str, str]:
        """Return a map of code to descriptive name for all locales."""
        result = {}
        for code, data in self.locales.items():
            result[code] = data.get('language_name', code)
        return result


# Singleton instance
_manager = None


def get_localization_manager() -> LocalizationManager:
    global _manager
    if _manager is None:
        _manager = LocalizationManager()
    return _manager
