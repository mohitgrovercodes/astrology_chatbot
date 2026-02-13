# tests\test_dynamic_personas.py
"""
Tests for dynamic persona generation system.

Tests:
- Cache functionality (memory + disk)
- LLM-based persona generation
- Fallback to English
- Manual locale priority
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import shutil
from unittest.mock import Mock, MagicMock
from src.utils.localization import LocalizationManager
from src.ai.persona_generator import PersonaGenerator


class TestDynamicPersonaGeneration:
    """Test dynamic persona generation with LLM."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that returns valid JSON."""
        llm = Mock()
        
        # Mock response for persona generation
        mock_response = Mock()
        mock_response.content = json.dumps({
            "identity": "Vous êtes NakshatraAI, un astrologue védique professionnel.",
            "guidelines": [
                "Utilisez des termes sanskrits avec traduction française",
                "Maintenez un ton professionnel"
            ],
            "timing_rules": [
                "Ne jamais inventer des dates de Dasha"
            ]
        }, ensure_ascii=False)
        
        llm.invoke.return_value = mock_response
        return llm
    
    @pytest.fixture
    def english_locale(self):
        """Load English locale as template."""
        import json
        locale_path = os.path.join(
            os.path.dirname(__file__),
            '../src/locales/en.json'
        )
        with open(locale_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @pytest.fixture
    def temp_locales_dir(self, tmp_path):
        """Create temporary locales directory."""
        locales_dir = tmp_path / "locales"
        locales_dir.mkdir()
        
        # Copy English locale
        import shutil
        src = os.path.join(os.path.dirname(__file__), '../src/locales/en.json')
        dst = locales_dir / "en.json"
        shutil.copy(src, dst)
        
        return str(locales_dir)
    
    def test_persona_generator_creates_valid_locale(self, mock_llm, english_locale):
        """Test that PersonaGenerator creates valid locale structure."""
        generator = PersonaGenerator(mock_llm, english_locale)
        
        locale = generator.generate_full_locale("fr", "French")
        
        # Verify structure
        assert "language_name" in locale
        assert locale["language_name"] == "French"
        assert "prompt_templates" in locale
        assert "personas" in locale
        assert "vedic" in locale["personas"]
        assert "western" in locale["personas"]
    
    def test_manual_locale_priority(self, temp_locales_dir):
        """Test that manual locales are used without LLM calls."""
        manager = LocalizationManager(temp_locales_dir)
        mock_llm = Mock()
        
        # Get English persona (manual locale)
        persona = manager.get_persona_data("en", "vedic", llm=mock_llm)
        
        # Verify LLM was NOT called
        assert mock_llm.invoke.call_count == 0
        assert persona is not None
        assert "identity" in persona
    
    def test_dynamic_generation_for_new_language(self, temp_locales_dir, mock_llm):
        """Test dynamic generation for unsupported language."""
        manager = LocalizationManager(temp_locales_dir)
        
        # Request Spanish persona (not in manual locales)
        persona = manager.get_persona_data("es", "vedic", llm=mock_llm)
        
        # Verify LLM was called
        assert mock_llm.invoke.call_count > 0
        assert persona is not None
    
    def test_cache_hit_no_llm_call(self, temp_locales_dir, mock_llm):
        """Test that cached personas don't trigger LLM calls."""
        manager = LocalizationManager(temp_locales_dir)
        
        # First call: generates
        persona1 = manager.get_persona_data("fr", "vedic", llm=mock_llm)
        call_count_after_first = mock_llm.invoke.call_count
        
        # Second call: should use cache
        persona2 = manager.get_persona_data("fr", "vedic", llm=mock_llm)
        call_count_after_second = mock_llm.invoke.call_count
        
        # Verify cache hit (no new LLM calls)
        assert call_count_after_second == call_count_after_first
        assert persona1 == persona2
    
    def test_disk_persistence(self, temp_locales_dir, mock_llm):
        """Test that generated locales are saved to disk."""
        manager = LocalizationManager(temp_locales_dir)
        
        # Generate persona
        manager.get_persona_data("de", "vedic", llm=mock_llm)
        
        # Check that file was created
        generated_file = os.path.join(temp_locales_dir, "generated", "de.json")
        assert os.path.exists(generated_file)
        
        # Verify file contains valid JSON
        with open(generated_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert "language_name" in data
            assert "personas" in data
    
    def test_fallback_to_english(self, temp_locales_dir):
        """Test fallback to English when LLM is not provided."""
        manager = LocalizationManager(temp_locales_dir)
        
        # Request unsupported language without LLM
        persona = manager.get_persona_data("ja", "vedic", llm=None)
        
        # Should fallback to English
        assert persona is not None
        # English persona should have identity
        assert "identity" in persona


class TestLocalizationManagerEnhancements:
    """Test enhanced LocalizationManager features."""
    
    @pytest.fixture
    def temp_locales_dir(self, tmp_path):
        """Create temporary locales directory with manual locales."""
        locales_dir = tmp_path / "locales"
        locales_dir.mkdir()
        
        # Copy manual locales
        manual_locales = ['en.json', 'hi.json', 'ta.json']
        for locale_file in manual_locales:
            src = os.path.join(os.path.dirname(__file__), f'../src/locales/{locale_file}')
            if os.path.exists(src):
                dst = locales_dir / locale_file
                shutil.copy(src, dst)
        
        return str(locales_dir)
    
    def test_load_manual_locales(self, temp_locales_dir):
        """Test loading of manual locale files."""
        manager = LocalizationManager(temp_locales_dir)
        
        supported = manager.get_supported_languages()
        assert 'en' in supported
    
    def test_load_generated_locales_from_disk(self, temp_locales_dir):
        """Test loading previously generated locales from disk cache."""
        # Create generated directory with a locale
        generated_dir = os.path.join(temp_locales_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)
        
        test_locale = {
            "language_name": "Spanish",
            "prompt_templates": {},
            "personas": {
                "vedic": {
                    "identity": "Test identity",
                    "guidelines": []
                }
            }
        }
        
        with open(os.path.join(generated_dir, "es.json"), 'w', encoding='utf-8') as f:
            json.dump(test_locale, f, ensure_ascii=False)
        
        # Create new manager instance (simulates restart)
        manager = LocalizationManager(temp_locales_dir)
        
        # Verify generated locale was loaded
        supported = manager.get_supported_languages()
        assert 'es' in supported
        
        # Verify can get persona without LLM
        persona = manager.get_persona_data('es', 'vedic', llm=None)
        assert persona['identity'] == "Test identity"
    
    def test_get_language_name_from_cache(self, temp_locales_dir):
        """Test getting language name from generated cache."""
        manager = LocalizationManager(temp_locales_dir)
        
        # Add to cache
        manager._persona_cache['it'] = {
            "language_name": "Italian",
            "personas": {}
        }
        
        name = manager.get_language_name('it')
        assert name == "Italian"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
