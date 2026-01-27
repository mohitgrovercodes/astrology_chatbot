"""
LLM Factory for Astrology AI Chatbot.

VERTEX AI ONLY - No OpenAI, No AI Studio
Includes built-in rate limiting to prevent 429 errors.
"""

import os
import time
from typing import Optional, List
from langchain_core.language_models.chat_models import BaseChatModel

# Vertex AI only
try:
    from langchain_google_vertexai import ChatVertexAI
    import vertexai
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    raise ImportError("Vertex AI not available. Install: pip install google-cloud-aiplatform langchain-google-vertexai")

# Config and utilities
try:
    from src.utils.config import get_config
    from src.utils.logger import get_logger
    from src.utils.cost_tracking import CostTrackerCallback
    logger = get_logger(__name__)
    CONFIG_AVAILABLE = True
    COST_TRACKING_AVAILABLE = True
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    CONFIG_AVAILABLE = False
    COST_TRACKING_AVAILABLE = False


# ============================================
# Vertex AI Initialization
# ============================================

_VERTEX_INITIALIZED = False

def initialize_vertex_ai(project_id: str = "445806945384", location: str = "us-central1"):
    """Initialize Vertex AI globally."""
    global _VERTEX_INITIALIZED
    
    if _VERTEX_INITIALIZED:
        return
    
    try:
        vertexai.init(project=project_id, location=location)
        _VERTEX_INITIALIZED = True
        logger.info(f"✅ Vertex AI initialized: project={project_id}, location={location}")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        raise


# ============================================
# Rate-Limited LLM Wrapper
# ============================================

class RateLimitedLLM:
    """Wrapper for LLM with rate limiting to prevent 429 errors."""
    
    def __init__(self, llm: BaseChatModel, min_delay: float = 1.5, max_retries: int = 3, base_backoff: float = 2.0):
        self.llm = llm
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._last_call_time = 0
    
    def _wait_if_needed(self):
        """Enforce minimum delay between calls."""
        current_time = time.time()
        elapsed = current_time - self._last_call_time
        
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        
        self._last_call_time = time.time()
    
    def invoke(self, *args, **kwargs):
        """Invoke LLM with rate limiting and retry logic."""
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                return self.llm.invoke(*args, **kwargs)
                
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(["429" in error_str, "rate limit" in error_str, 
                                    "resource exhausted" in error_str, "quota" in error_str])
                
                if is_rate_limit and attempt < self.max_retries - 1:
                    wait_time = self.base_backoff * (2 ** attempt)
                    logger.warning(f"Rate limit hit. Waiting {wait_time}s... (Attempt {attempt+1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    raise
        
        raise RuntimeError(f"Failed after {self.max_retries} retries")
    
    def __getattr__(self, name):
        """Delegate to underlying LLM."""
        return getattr(self.llm, name)


# ============================================
# LLM Factory
# ============================================

class LLMFactory:
    """Factory for creating Vertex AI LLM instances only."""
    
    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_rate_limiting: bool = True,
        rate_limit_delay: float = 1.5,
        **kwargs
    ) -> BaseChatModel:
        """
        Create a Vertex AI LLM instance.
        
        Args:
            provider: Ignored (always uses google/vertex)
            model: Gemini model name (default: gemini-2.5-flash)
            temperature: Sampling temperature
            max_tokens: Max output tokens
            use_rate_limiting: Enable rate limiting (default: True)
            rate_limit_delay: Minimum seconds between requests
        
        Returns:
            ChatVertexAI instance (wrapped with rate limiter)
        """
        # Get config or use defaults
        if CONFIG_AVAILABLE:
            config = get_config()
            model = model or config.llm.default_model
            temperature = temperature if temperature is not None else config.llm.temperature
            max_tokens = max_tokens or config.llm.max_tokens
        else:
            model = model or "gemini-2.5-flash"
            temperature = temperature if temperature is not None else 0.3
            max_tokens = max_tokens or 2048
        
        # Initialize Vertex AI
        if not _VERTEX_INITIALIZED:
            initialize_vertex_ai()
        
        # Create Vertex AI LLM
        logger.info(f"Creating Vertex AI LLM: model={model}")
        llm = ChatVertexAI(
            model_name=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            project="445806945384",
            location="us-central1",
            **kwargs
        )
        
        # Add cost tracking
        if COST_TRACKING_AVAILABLE:
            cost_callback = CostTrackerCallback(
                provider="google", model=model, operation="llm_generation", metadata={"factory": True}
            )
            if hasattr(llm, 'callbacks'):
                llm.callbacks = [cost_callback] if llm.callbacks is None else llm.callbacks + [cost_callback]
        
        logger.info(f"✅ Created Vertex AI LLM: model={model}, temperature={temperature}, max_tokens={max_tokens}")
        
        # Wrap with rate limiter
        if use_rate_limiting:
            logger.info(f"✅ Rate limiting enabled: {rate_limit_delay}s delay")
            return RateLimitedLLM(llm, min_delay=rate_limit_delay, max_retries=3, base_backoff=2.0)
        
        return llm
    
    @classmethod
    def create_default(cls) -> BaseChatModel:
        """Create LLM with defaults (Gemini 2.5 Flash)."""
        return cls.create()
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available providers (always returns ['google'])."""
        return ["google"]


# ============================================
# Convenience Functions
# ============================================

def create_llm(provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> BaseChatModel:
    """Create a Vertex AI LLM instance."""
    return LLMFactory.create(provider=provider, model=model, **kwargs)


def create_default_llm() -> BaseChatModel:
    """Create default LLM (Gemini 2.5 Flash on Vertex AI)."""
    return LLMFactory.create_default()


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("LLM FACTORY TEST (Vertex AI Only)")
    print("=" * 60)
    print()
    
    print("Available Providers:")
    available = LLMFactory.get_available_providers()
    for provider in available:
        print(f"  ✅ {provider}")
    print()
    
    print("Creating default LLM (Gemini 2.5 Flash on Vertex AI)...")
    try:
        llm = create_default_llm()
        
        if isinstance(llm, RateLimitedLLM):
            actual_llm = llm.llm
            print(f"✅ Created: RateLimitedLLM wrapping {type(actual_llm).__name__}")
        else:
            print(f"✅ Created: {type(llm).__name__}")
        print()
        
        print("Testing invoke...")
        response = llm.invoke("Say 'Hello' in one word")
        print(f"Response: {response.content}")
        print()
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("✅ Test complete!")
    print("=" * 60)