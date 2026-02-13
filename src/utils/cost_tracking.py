# src\utils\cost_tracking.py
"""
Cost tracking utilities for LLM integrations.

Provides decorators, wrappers, and LangChain callbacks for automatic cost logging.
"""

import time
import functools
from typing import Any, Dict, List, Optional, Callable
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .cost_logger import get_cost_logger
from .logger import get_logger

logger = get_logger(__name__)


# ============================================
# LangChain Callback for Cost Tracking
# ============================================

class CostTrackerCallback(BaseCallbackHandler):
    """
    LangChain callback to automatically track LLM costs.
    
    Usage:
        from src.utils.cost_tracking import CostTrackerCallback
        
        callback = CostTrackerCallback(provider="google", model="gemini-2.5-flash")
        llm = ChatGoogleGenerativeAI(callbacks=[callback], ...)
    """
    
    def __init__(
        self,
        provider: str,
        model: str,
        operation: str = "llm_generation",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize cost tracking callback.
        
        Args:
            provider: LLM provider name (google, openai, etc.)
            model: Model name
            operation: Operation type for logging
            metadata: Additional metadata to include in logs
        """
        super().__init__()
        self.provider = provider
        self.model = model
        self.operation = operation
        self.base_metadata = metadata or {}
        self.cost_logger = get_cost_logger()
    
    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """
        Called when LLM finishes running.
        
        Args:
            response: LLM result containing token usage
            **kwargs: Additional arguments
        """
        try:
            # SKIP: Flash models (usage not tracked/shared)
            if "flash" in self.model.lower():
                return

            # Extract token usage from response
            input_tokens = 0
            output_tokens = 0
            
            if response.llm_output and "token_usage" in response.llm_output:
                usage = response.llm_output["token_usage"]
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
            elif hasattr(response, "usage_metadata") and response.usage_metadata:
                # Vertex AI / Google GenAI / Newer LangChain format
                usage_meta = response.usage_metadata
                
                if hasattr(usage_meta, "prompt_token_count"):
                    input_tokens = usage_meta.prompt_token_count
                    output_tokens = getattr(usage_meta, "candidates_token_count", 0) or getattr(usage_meta, "total_token_count", 0) - input_tokens
                elif isinstance(usage_meta, dict):
                    input_tokens = usage_meta.get("input_tokens") or usage_meta.get("prompt_token_count", 0)
                    output_tokens = usage_meta.get("output_tokens") or usage_meta.get("candidates_token_count", 0)
                else:
                    input_tokens = getattr(usage_meta, "input_tokens", 0)
                    output_tokens = getattr(usage_meta, "output_tokens", 0)
            
            # Ollama Specific Fallback: Sometimes info is in generation_info of the first generation
            if input_tokens == 0 and output_tokens == 0 and response.generations:
                try:
                    first_gen_info = response.generations[0][0].generation_info
                    if first_gen_info:
                        input_tokens = first_gen_info.get("prompt_eval_count", 0)
                        output_tokens = first_gen_info.get("eval_count", 0)
                except (IndexError, AttributeError):
                    pass

            # Final check
            if input_tokens == 0 and output_tokens == 0:
                # No token usage info available
                logger.warning(f"No token usage info in LLM response for {self.model}")
                return
            
            # Build metadata
            metadata = {
                **self.base_metadata,
                "provider": self.provider,
                "callback": True,
            }
            
            # Log the cost
            self.cost_logger.log_llm_call(
                model_name=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation=self.operation,
                metadata=metadata,
            )
            
        except Exception as e:
            logger.error(f"Failed to track cost in callback: {e}")


# ============================================
# Decorator for Direct API Call Tracking
# ============================================

def track_llm_cost(
    model_name: str,
    operation: str = "llm_generation",
    extract_tokens: Optional[Callable] = None,
):
    """
    Decorator to track LLM API call costs.
    
    Args:
        model_name: Name of the model being called
        operation: Operation type for categorization
        extract_tokens: Optional function to extract token counts from response
                       Should return (input_tokens, output_tokens)
    
    Usage:
        @track_llm_cost(model_name="gemini-2.5-flash", operation="vision_extraction")
        def extract_page(self, image):
            response = self.model.generate_content([prompt, image])
            return response
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original function
            result = func(*args, **kwargs)
            
            try:
                # SKIP: Flash models
                if "flash" in model_name.lower():
                    return result

                # Extract token counts
                if extract_tokens:
                    input_tokens, output_tokens = extract_tokens(result)
                elif hasattr(result, "usage_metadata"):
                    # Gemini API response format
                    input_tokens = result.usage_metadata.prompt_token_count
                    output_tokens = result.usage_metadata.candidates_token_count
                else:
                    logger.warning(f"Cannot extract tokens from {func.__name__} response")
                    return result
                
                # Log the cost
                cost_logger = get_cost_logger()
                cost_logger.log_llm_call(
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation=operation,
                    metadata={"function": func.__name__},
                )
                
            except Exception as e:
                logger.error(f"Failed to track cost for {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator


def track_embedding_cost(
    model_name: str,
    extract_tokens: Optional[Callable] = None,
):
    """
    Decorator to track embedding API call costs.
    
    Args:
        model_name: Name of the embedding model
        extract_tokens: Optional function to extract token count from response
                       Should return total_tokens
    
    Usage:
        @track_embedding_cost(model_name="text-embedding-3-large")
        def embed_batch(self, texts):
            response = self.client.embeddings.create(...)
            return response
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original function
            result = func(*args, **kwargs)
            
            try:
                # Extract token count
                if extract_tokens:
                    tokens = extract_tokens(result)
                elif hasattr(result, "usage"):
                    # OpenAI API response format
                    tokens = result.usage.total_tokens
                else:
                    logger.warning(f"Cannot extract tokens from {func.__name__} response")
                    return result
                
                # Log the cost
                cost_logger = get_cost_logger()
                cost_logger.log_embedding_call(
                    model_name=model_name,
                    tokens=tokens,
                    metadata={"function": func.__name__},
                )
                
            except Exception as e:
                logger.error(f"Failed to track embedding cost for {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator


# ============================================
# Manual Tracking Wrappers
# ============================================

class CostTrackingWrapper:
    """
    Wrapper class to manually track costs for API calls.
    
    Useful when decorators can't be used or for more complex scenarios.
    
    Usage:
        tracker = CostTrackingWrapper(model_name="gemini-2.5-flash")
        
        # Make API call
        response = model.generate_content(prompt)
        
        # Track the cost
        tracker.log_from_response(response, operation="text_generation")
    """
    
    def __init__(self, model_name: str, model_type: str = "llm"):
        """
        Initialize cost tracking wrapper.
        
        Args:
            model_name: Name of the model
            model_type: Type of model ('llm', 'embedding', 'vision')
        """
        self.model_name = model_name
        self.model_type = model_type
        self.cost_logger = get_cost_logger()
    
    def log_from_response(
        self,
        response: Any,
        operation: str = "api_call",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Log cost from an API response object.
        
        Args:
            response: API response object
            operation: Operation type
            metadata: Additional metadata
            
        Returns:
            Database row ID if successful
        """
        try:
            # Extract tokens based on response type
            if hasattr(response, "usage_metadata"):
                # Gemini API format
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
            elif hasattr(response, "usage"):
                # OpenAI API format
                if hasattr(response.usage, "prompt_tokens"):
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = getattr(response.usage, "completion_tokens", 0)
                else:
                    # Embedding format
                    input_tokens = response.usage.total_tokens
                    output_tokens = 0
            else:
                logger.warning(f"Unknown response format for cost tracking")
                return None
            
            # Log the cost
            if self.model_type == "embedding":
                return self.cost_logger.log_embedding_call(
                    model_name=self.model_name,
                    tokens=input_tokens,
                    metadata=metadata,
                )
            else:
                return self.cost_logger.log_llm_call(
                    model_name=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation=operation,
                    metadata=metadata,
                )
                
        except Exception as e:
            logger.error(f"Failed to log cost from response: {e}")
            return None
    
    def log_manual(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        operation: str = "api_call",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Manually log cost with known token counts.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation: Operation type
            metadata: Additional metadata
            
        Returns:
            Database row ID if successful
        """
        if self.model_type == "embedding":
            return self.cost_logger.log_embedding_call(
                model_name=self.model_name,
                tokens=input_tokens,
                metadata=metadata,
            )
        else:
            return self.cost_logger.log_llm_call(
                model_name=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation=operation,
                metadata=metadata,
            )


# ============================================
# Context Manager for Batch Tracking
# ============================================

class BatchCostTracker:
    """
    Context manager for tracking costs of batch operations.
    
    Usage:
        with BatchCostTracker("gemini-2.5-flash", "batch_enrichment") as tracker:
            for item in items:
                response = process_item(item)
                tracker.add_from_response(response)
        
        # Automatically logs aggregate cost on exit
    """
    
    def __init__(
        self,
        model_name: str,
        operation: str,
        model_type: str = "llm",
    ):
        """
        Initialize batch cost tracker.
        
        Args:
            model_name: Name of the model
            operation: Operation type
            model_type: Type of model
        """
        self.model_name = model_name
        self.operation = operation
        self.model_type = model_type
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.cost_logger = get_cost_logger()
    
    def __enter__(self):
        """Enter context manager."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and log aggregate cost."""
        duration = time.time() - self.start_time
        
        if self.call_count > 0:
            metadata = {
                "batch_size": self.call_count,
                "duration_seconds": round(duration, 2),
            }
            
            if self.model_type == "embedding":
                self.cost_logger.log_embedding_call(
                    model_name=self.model_name,
                    tokens=self.total_input_tokens,
                    metadata=metadata,
                )
            else:
                self.cost_logger.log_llm_call(
                    model_name=self.model_name,
                    input_tokens=self.total_input_tokens,
                    output_tokens=self.total_output_tokens,
                    operation=self.operation,
                    metadata=metadata,
                )
            
            logger.info(
                f"Batch {self.operation}: {self.call_count} calls, "
                f"{self.total_input_tokens + self.total_output_tokens} tokens, "
                f"{duration:.2f}s"
            )
    
    def add_from_response(self, response: Any):
        """
        Add token counts from a response.
        
        Args:
            response: API response object
        """
        try:
            if hasattr(response, "usage_metadata"):
                self.total_input_tokens += response.usage_metadata.prompt_token_count
                self.total_output_tokens += response.usage_metadata.candidates_token_count
            elif hasattr(response, "usage"):
                if hasattr(response.usage, "prompt_tokens"):
                    self.total_input_tokens += response.usage.prompt_tokens
                    self.total_output_tokens += response.usage.completion_tokens
                else:
                    self.total_input_tokens += response.usage.total_tokens
            
            self.call_count += 1
            
        except Exception as e:
            logger.error(f"Failed to add cost from response: {e}")
    
    def add_manual(self, input_tokens: int, output_tokens: int = 0):
        """
        Manually add token counts.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    """Test cost tracking utilities."""
    
    print("=" * 70)
    print("COST TRACKING UTILITIES TEST")
    print("=" * 70)
    print()
    
    # Test manual wrapper
    print("Testing CostTrackingWrapper...")
    wrapper = CostTrackingWrapper("gemini-2.5-flash", "llm")
    wrapper.log_manual(
        input_tokens=1000,
        output_tokens=500,
        operation="test_manual",
        metadata={"test": True}
    )
    print("[DONE] Manual logging works")
    
    # Test batch tracker
    print("\nTesting BatchCostTracker...")
    with BatchCostTracker("gemini-2.5-flash", "test_batch") as tracker:
        for i in range(3):
            tracker.add_manual(input_tokens=500, output_tokens=250)
    print("[DONE] Batch tracking works")
    
    # View summary
    from src.utils.cost_logger import get_cost_logger
    cost_logger = get_cost_logger()
    summary = cost_logger.get_summary()
    
    print("\n" + "=" * 70)
    print("COST SUMMARY")
    print("=" * 70)
    print(f"Total Calls: {summary.total_calls}")
    print(f"Total Cost: ${summary.total_cost:.6f}")
    
    print("\n[DONE] All cost tracking utilities working!")
