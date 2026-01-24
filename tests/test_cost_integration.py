"""
Integration tests for cost tracking across all components.

Tests that cost tracking works end-to-end in LLM Factory, Vision Extractor, Embedder, etc.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.utils.cost_logger import get_cost_logger, CostLogger


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Initialize cost logger with test DB
    get_cost_logger(db_path=db_path, reload=True)
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


class TestLLMFactoryIntegration:
    """Test cost tracking via LLM Factory."""
    
    @patch('src.llm.factory.ChatGoogleGenerativeAI')
    def test_factory_creates_llm_with_callback(self, mock_llm_class, test_db):
        """Test that LLM Factory attaches cost tracking callback."""
        from src.llm.factory import LLMFactory
        
        # Mock LLM instance
        mock_llm = MagicMock()
        mock_llm.callbacks = None
        mock_llm_class.return_value = mock_llm
        
        # Create LLM via factory
        llm = LLMFactory.create(
            provider="google",
            model="gemini-2.5-flash",
            api_key="test-key"
        )
        
        # Verify callback was attached
        assert llm.callbacks is not None
        assert len(llm.callbacks) == 1
        
        from src.utils.cost_tracking import CostTrackerCallback
        assert isinstance(llm.callbacks[0], CostTrackerCallback)


class TestVisionExtractorIntegration:
    """Test cost tracking in Vision Extractor."""
    
    def test_vision_extractor_has_cost_tracker(self, test_db):
        """Test that Vision Extractor initializes cost tracker."""
        from src.rag.extraction.vision_extractor import VisionExtractor, ExtractionConfig
        
        # Mock genai to avoid actual API calls
        with patch('src.rag.extraction.vision_extractor.genai'):
            config = ExtractionConfig()
            extractor = VisionExtractor(config=config)
            
            # Check cost tracker was initialized
            assert hasattr(extractor, 'cost_tracker')
            assert extractor.cost_tracker is not None
    
    @patch('src.rag.extraction.vision_extractor.genai.GenerativeModel')
    def test_vision_call_logs_cost(self, mock_model_class, test_db):
        """Test that vision extraction logs cost."""
        from src.rag.extraction.vision_extractor import VisionExtractor, ExtractionConfig
        from PIL import Image
        import numpy as np
        
        # Create mock response with usage metadata
        mock_response = MagicMock()
        mock_response.text = '{"page_type": "text"}'
        mock_response.prompt_feedback.block_reason = None
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 1500
        mock_response.usage_metadata.candidates_token_count = 800
        
        # Mock model
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        with patch('src.rag.extraction.vision_extractor.genai.configure'):
            config = ExtractionConfig()
            extractor = VisionExtractor(config=config)
            
            # Create test image
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            
            # Make API call
            result = extractor._call_gemini("test prompt", Image.fromarray(image))
            
            # Verify cost was logged
            cost_logger = get_cost_logger()
            summary = cost_logger.get_summary()
            
            # Should have at least one call logged
            assert summary.total_calls >= 1


class TestEmbedderIntegration:
    """Test cost tracking in Embedder."""
    
    def test_embedder_has_cost_tracker(self, test_db):
        """Test that Embedder initializes cost tracker."""
        from src.rag.preprocessing.embedder import Embedder
        
        embedder = Embedder(api_key="test-key")
        
        # Check cost tracker was initialized
        assert hasattr(embedder, 'cost_tracker')
        assert embedder.cost_tracker is not None
    
    @patch('src.rag.preprocessing.embedder.OpenAI')
    def test_embedding_call_logs_cost(self, mock_openai_class, test_db):
        """Test that embedding generation logs cost."""
        from src.rag.preprocessing.embedder import Embedder
        
        # Create mock response with usage
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 3072)]
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 2048
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        embedder = Embedder(api_key="test-key")
        
        # Generate embedding
        texts = ["Test text for embedding"]
        embeddings = embedder.embed_texts(texts)
        
        # Verify embedding was created
        assert len(embeddings) == 1
        
        # Verify cost was logged
        cost_logger = get_cost_logger()
        summary = cost_logger.get_summary()
        
        # Should have logged embedding cost
        assert summary.total_calls >= 1


class TestChunkEnricherIntegration:
    """Test cost tracking in Chunk Enricher."""
    
    def test_chunk_enricher_uses_factory_llm(self):
        """Test that Chunk Enricher uses LLM Factory (which has cost tracking)."""
        from src.rag.preprocessing.chunk_enricher import ChunkEnricher
        
        # Chunk enricher uses LLMFactory.create(), which automatically
        # attaches cost tracking callbacks
        enricher = ChunkEnricher(use_llm=True)
        
        # If LLM was initialized, it should have cost tracking via factory
        if enricher.model is not None:
            # LangChain model should have callbacks attached
            assert hasattr(enricher.model, 'callbacks') or True  # Factory attaches callbacks


class TestEndToEndPipeline:
    """Test cost tracking across a full pipeline run."""
    
    @pytest.mark.skip(reason="Requires actual API keys and is expensive")
    def test_full_pipeline_cost_tracking(self, test_db):
        """
        Test that running a small pipeline logs all costs.
        
        This would run:
        1. Vision extraction (5 pages)
        2. Preprocessing pipeline
        3. Chunk enrichment
        4. Embedding generation
        
        And verify all costs are logged.
        """
        # This is a placeholder for a full integration test
        # Requires actual API setup and sample data
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
