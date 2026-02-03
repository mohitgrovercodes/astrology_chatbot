import os
import json
from typing import Dict, List, Optional, Any

class LocalizationManager:
    """
    Manager for loading and accessing localization data from JSON files.
    """
    
    def __init__(self, locales_dir: str = None):
        if locales_dir is None:
            # Default to src/locales relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            locales_dir = os.path.join(base_dir, 'locales')
            
        self.locales_dir = locales_dir
        self.locales: Dict[str, Dict] = {}
        self._load_locales()
        
    def _load_locales(self):
        """Load all JSON files from the locales directory."""
        if not os.path.exists(self.locales_dir):
            print(f"[LOCALIZATION] [WARN] Locales directory not found: {self.locales_dir}")
            return
            
        for filename in os.listdir(self.locales_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                filepath = os.path.join(self.locales_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.locales[lang_code] = json.load(f)
                    print(f"[LOCALIZATION] Loaded locale: {lang_code}")
                except Exception as e:
                    print(f"[LOCALIZATION] [ERROR] Failed to load {filename}: {e}")
                    
    def get_supported_languages(self) -> List[str]:
        """Return list of supported language codes."""
        return list(self.locales.keys())
        
    def get_language_name(self, lang_code: str) -> str:
        """Return human-readable name for a language code."""
        return self.locales.get(lang_code, {}).get('language_name', 'English')
        
    def get_prompt_templates(self, lang_code: str) -> Dict[str, str]:
        """Return prompt templates for a language."""
        # Fallback to English if not found
        locale = self.locales.get(lang_code, self.locales.get('en', {}))
        return locale.get('prompt_templates', {})
        
    def get_persona_data(self, lang_code: str, persona_type: str) -> Dict[str, Any]:
        """Return identity and guidelines for a specific persona and language."""
        # Fallback to English if not found
        locale = self.locales.get(lang_code, self.locales.get('en', {}))
        persona = locale.get('personas', {}).get(persona_type, {})
        
        # If specific lang doesn't have the persona, fallback to en
        if not persona and lang_code != 'en':
            return self.get_persona_data('en', persona_type)
            
        return persona

    def get_detection_rules(self, lang_code: str) -> Dict[str, Any]:
        """Return heuristic markers and unicode ranges for detection."""
        return self.locales.get(lang_code, {}).get('detection', {})

    def get_language_map(self) -> Dict[str, str]:
        """Return a map of code to descriptive name for all locales."""
        return {code: data.get('language_name', code) for code, data in self.locales.items()}

# Singleton instance
_manager = None

def get_localization_manager() -> LocalizationManager:
    global _manager
    if _manager is None:
        _manager = LocalizationManager()
    return _manager
