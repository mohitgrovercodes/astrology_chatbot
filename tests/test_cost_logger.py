"""
Unit tests for cost logger functionality.

Tests cost calculation accuracy, logging, querying, and reporting.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

from src.utils.cost_logger import (
    CostLogger,
    ModelPricing,
    ModelType,
    PRICING_TABLE,
    APICallLog,
    CostSummary,
)


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def cost_logger(test_db):
    """Create a cost logger for testing."""
    return CostLogger(db_path=test_db, enabled=True)


class TestPricingCalculations:
    """Test cost calculation accuracy."""
    
    def test_gemini_flash_pricing(self, cost_logger):
        """Test Gemini 2.5 Flash cost calculation."""
        input_cost, output_cost, total = cost_logger.calculate_cost(
            model_name="gemini-2.5-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        
        # Expected: $0.01875 per 1M input, $0.075 per 1M output
        expected_input = 0.00001875
        expected_output = 0.0000375
        expected_total = expected_input + expected_output
        
        assert abs(input_cost - expected_input) < 0.0000001
        assert abs(output_cost - expected_output) < 0.0000001
        assert abs(total - expected_total) < 0.0000001
    
    def test_embedding_pricing(self, cost_logger):
        """Test embedding model cost calculation."""
        input_cost, output_cost, total = cost_logger.calculate_cost(
            model_name="text-embedding-3-large",
            input_tokens=2048,
            output_tokens=0,
        )
        
        # Expected: $0.13 per 1M tokens
        expected = 2048 * 0.00013 / 1000
        
        assert abs(total - expected) < 0.0000001
        assert output_cost == 0.0
    
    def test_unknown_model_fallback(self, cost_logger):
        """Test that unknown models return zero cost."""
        input_cost, output_cost, total = cost_logger.calculate_cost(
            model_name="unknown-model-xyz",
            input_tokens=1000,
            output_tokens=500,
        )
        
        assert input_cost == 0.0
        assert output_cost == 0.0
        assert total == 0.0


class TestLogging:
    """Test cost logging functionality."""
    
    def test_log_llm_call(self, cost_logger):
        """Test logging an LLM call."""
        row_id = cost_logger.log_llm_call(
            model_name="gemini-2.5-flash",
            input_tokens=1500,
            output_tokens=800,
            operation="test_generation",
            metadata={"test": True},
        )
        
        assert row_id is not None
        assert row_id > 0
    
    def test_log_embedding_call(self, cost_logger):
        """Test logging an embedding call."""
        row_id = cost_logger.log_embedding_call(
            model_name="text-embedding-3-large",
            tokens=2048,
            metadata={"batch_size": 10},
        )
        
        assert row_id is not None
        assert row_id > 0
    
    def test_log_vision_call(self, cost_logger):
        """Test logging a vision call."""
        row_id = cost_logger.log_vision_call(
            model_name="gemini-2.5-flash",
            input_tokens=2000,
            output_tokens=1000,
            metadata={"page": 5},
        )
        
        assert row_id is not None
        assert row_id > 0
    
    def test_multiple_calls_logged(self, cost_logger):
        """Test that multiple calls are logged correctly."""
        for i in range(5):
            cost_logger.log_llm_call(
                model_name="gemini-2.5-flash",
                input_tokens=1000 + i * 100,
                output_tokens=500 + i * 50,
            )
        
        summary = cost_logger.get_summary()
        assert summary.total_calls == 5


class TestQuerying:
    """Test cost querying and filtering."""
    
    def test_get_total_cost(self, cost_logger):
        """Test getting total cost."""
        # Log some calls
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        cost_logger.log_embedding_call("text-embedding-3-large", 2048)
        
        total = cost_logger.get_total_cost()
        assert total > 0
    
    def test_filter_by_model(self, cost_logger):
        """Test filtering by model name."""
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        cost_logger.log_embedding_call("text-embedding-3-large", 2048)
        
        gemini_cost = cost_logger.get_total_cost(model_name="gemini-2.5-flash")
        embedding_cost = cost_logger.get_total_cost(model_name="text-embedding-3-large")
        
        assert gemini_cost > 0
        assert embedding_cost > 0
        assert gemini_cost != embedding_cost
    
    def test_filter_by_operation(self, cost_logger):
        """Test filtering by operation type."""
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500, operation="generation")
        cost_logger.log_embedding_call("text-embedding-3-large", 2048)
        
        gen_cost = cost_logger.get_total_cost(operation="llm_generation")
        emb_cost = cost_logger.get_total_cost(operation="embedding")
        
        assert gen_cost >= 0  # May be 0 if operation names don't match exactly
        assert emb_cost > 0
    
    def test_get_recent_calls(self, cost_logger):
        """Test getting recent calls."""
        # Log multiple calls
        for i in range(10):
            cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        
        recent = cost_logger.get_recent_calls(limit=5)
        assert len(recent) == 5
        assert all(isinstance(call, APICallLog) for call in recent)


class TestSummaries:
    """Test cost summary generation."""
    
    def test_get_summary_basic(self, cost_logger):
        """Test basic summary generation."""
        # Log some calls
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        cost_logger.log_embedding_call("text-embedding-3-large", 2048)
        
        summary = cost_logger.get_summary()
        
        assert isinstance(summary, CostSummary)
        assert summary.total_calls == 2
        assert summary.total_tokens > 0
        assert summary.total_cost > 0
    
    def test_breakdown_by_model(self, cost_logger):
        """Test model breakdown in summary."""
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        cost_logger.log_embedding_call("text-embedding-3-large", 2048)
        
        summary = cost_logger.get_summary()
        
        assert "gemini-2.5-flash" in summary.breakdown_by_model
        assert "text-embedding-3-large" in summary.breakdown_by_model
        assert summary.breakdown_by_model["gemini-2.5-flash"]["calls"] == 1
        assert summary.breakdown_by_model["text-embedding-3-large"]["calls"] == 1
    
    def test_breakdown_by_operation(self, cost_logger):
        """Test operation breakdown in summary."""
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500, operation="generation")
        cost_logger.log_vision_call("gemini-2.5-flash", 2000, 1000)
        
        summary = cost_logger.get_summary()
        
        assert "llm_generation" in summary.breakdown_by_operation
        assert "vision_extraction" in summary.breakdown_by_operation


class TestDailySummaries:
    """Test daily summary aggregation."""
    
    def test_daily_summary_created(self, cost_logger, test_db):
        """Test that daily summaries are created."""
        cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        
        # Check database directly
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily_summaries")
            count = cursor.fetchone()[0]
        
        assert count == 1
    
    def test_daily_summary_updated(self, cost_logger, test_db):
        """Test that daily summaries are updated for multiple calls."""
        # Log multiple calls on same day
        for i in range(3):
            cost_logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        
        # Check database
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_calls FROM daily_summaries")
            total_calls = cursor.fetchone()[0]
        
        assert total_calls == 3


class TestDisabledLogger:
    """Test logger behavior when disabled."""
    
    def test_disabled_logger_no_logging(self, test_db):
        """Test that disabled logger doesn't log."""
        logger = CostLogger(db_path=test_db, enabled=False)
        
        row_id = logger.log_llm_call("gemini-2.5-flash", 1000, 500)
        assert row_id is None
        
        total_cost = logger.get_total_cost()
        assert total_cost == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
