# src/llm/factory.py
# src\llm\factory.py
"""
LLM Factory for Astrology AI Chatbot.

Supports OpenAI and Ollama.
Includes built-in rate limiting to prevent 429 errors.
"""

import os
import time
from typing import Optional, List
from langchain_core.language_models.chat_models import BaseChatModel

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
# Rate-Limited LLM Wrapper
# ============================================

from langchain_core.runnables import Runnable

class RateLimitedLLM(Runnable):
    """Wrapper for LLM with rate limiting to prevent 429 errors."""
    
    def __init__(self, llm: BaseChatModel, min_delay: float = 2.0, max_retries: int = 3, base_backoff: float = 4.0):
        super().__init__()
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
    
    def invoke(self, input, config=None, **kwargs):
        """Invoke LLM with rate limiting and retry logic."""
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                return self.llm.invoke(input, config=config, **kwargs)
                
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

    def stream(self, input, config=None, **kwargs):
        """Stream LLM responses with rate limiting."""
        self._wait_if_needed()
        yield from self.llm.stream(input, config=config, **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        """Async invoke."""
        # Note: Rate limiting is blocking here, ideally use async sleep
        import asyncio
        for attempt in range(self.max_retries):
            try:
                # Basic sync wait for now to keep logic simple
                self._wait_if_needed()
                return await self.llm.ainvoke(input, config=config, **kwargs)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.base_backoff * (2 ** attempt))
                else:
                    raise

    def __getattr__(self, name):
        """Delegate to underlying LLM."""
        return getattr(self.llm, name)


# ============================================
# LLM Factory
# ============================================

class LLMFactory:
    """Factory for creating LLM instances (Vertex AI, OpenAI, or Ollama)."""
    
    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_rate_limiting: bool = True,
        rate_limit_delay: float = 1.5,
        purpose: str = "general",
        **kwargs
    ) -> BaseChatModel:
        """
        Create an LLM instance.
        
        Args:
            provider: 'openai', or 'ollama' (defaults to config.llm.default_provider)
            model: Model name. If None, selected based on provider and purpose.
            temperature: Sampling temperature
            max_tokens: Max output tokens
            use_rate_limiting: Enable rate limiting (default: True)
            rate_limit_delay: Minimum seconds between requests
            purpose: 'general', 'classification', 'reasoning' (affects default model)
        
        Returns:
            LLM instance (wrapped with rate limiter)
        """
        # Get config
        if CONFIG_AVAILABLE:
            config = get_config()
            default_provider = config.llm.default_provider or "ollama"
            
            # Use configured defaults if not overridden
            # Determine provider (legacy support for 'google'/'openai' prefix)
            provider = (provider or default_provider).lower()
            
            # FAST LLM Support: Check if we should use a specific fast model for this purpose
            is_fast_purpose = purpose in ["classification", "language_detection"]
            fast_provider = config.env.fast_llm_provider
            fast_model = config.env.fast_llm_model or getattr(config.llm, 'fast_model', None)

            if not model:
                # Use Fast LLM if specified for classification/routing
                if is_fast_purpose and (fast_provider or fast_model):
                    provider = (fast_provider or provider).lower()
                    model = fast_model
                
                # If still no model, select based on provider and purpose
                if not model:
                    if provider == "openai":
                        if purpose == "classification":
                            model = "gpt-4o-mini"
                        else:
                            model = config.llm.default_model or "gpt-4o-mini"
                    elif provider == "ollama":
                        if purpose == "classification":
                            model = getattr(config.llm, 'fast_model', "qwen2.5:1.5b")
                        elif purpose == "reasoning":
                            model = config.llm.default_model or "qwen3:8b"
                        else:
                            model = config.llm.default_model or "qwen3:8b"
            
            temperature = temperature if temperature is not None else config.llm.temperature
            max_tokens = max_tokens or config.llm.max_tokens
            
        else:
            # Fallback without config
            provider = (provider or "ollama").lower()
            if not model:
                if provider == "openai":
                    model = "gpt-4o-mini"
                elif provider == "ollama":
                    model = "qwen3:8b"
                else:
                    model = "gpt-4o-mini"
            temperature = temperature if temperature is not None else 0.3
            max_tokens = max_tokens or 2048
        
        # Create LLM based on provider
        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                raise ImportError("OpenAI not available. Install: pip install langchain-openai")
            
            # Get API key
            api_key = kwargs.pop("api_key", None) or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment or kwargs")
            
            # Create OpenAI LLM
            logger.info(f"Creating OpenAI LLM: model={model}")
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                **kwargs
            )
        
        elif provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
            except ImportError:
                raise ImportError("Ollama not available. Install: pip install langchain-ollama")
                
            try:
                base_url = kwargs.pop("base_url", None)
                if not base_url and CONFIG_AVAILABLE:
                    base_url = get_config().env.ollama_base_url
                
                # Defensive cleaning of URL
                if base_url:
                    base_url = base_url.split('(')[0].strip()
                
                logger.info(f"Creating Ollama LLM: model={model}, base_url={base_url}")
                llm = ChatOllama(
                    model=model,
                    temperature=temperature,
                    base_url=base_url or "http://localhost:11434",
                    **kwargs
                )
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.error(f"Ollama model '{model}' not found. Please run 'ollama pull {model}'.")
                    if purpose == "classification":
                        logger.warning("Falling back to qwen2.5:1.5b for classification...")
                        model = "qwen2.5:1.5b"
                        llm = ChatOllama(
                            model=model,
                            temperature=temperature,
                            base_url=base_url or "http://localhost:11434",
                            **kwargs
                        )
                    else:
                        raise
                else:
                    raise
        
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'ollama'")
        
        # Add cost tracking
        if COST_TRACKING_AVAILABLE:
            cost_callback = CostTrackerCallback(
                provider=provider, model=model, operation="llm_generation", metadata={"factory": True}
            )
            if hasattr(llm, 'callbacks'):
                llm.callbacks = [cost_callback] if llm.callbacks is None else llm.callbacks + [cost_callback]
        
        logger.info(f"[DONE] Created {provider.upper()} LLM: model={model}, temperature={temperature}, max_tokens={max_tokens}")
        
        # Wrap with rate limiter
        if use_rate_limiting:
            logger.info(f"[DONE] Rate limiting enabled: {rate_limit_delay}s delay")
            return RateLimitedLLM(llm, min_delay=rate_limit_delay, max_retries=3, base_backoff=2.0)
        
        return llm
    
    @classmethod
    def create_default(cls) -> BaseChatModel:
        """Create LLM with defaults (Qwen3:8B)."""
        return cls.create()
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available providers."""
        providers = []
             
        try:
             import langchain_openai
             providers.append("openai")
        except ImportError: pass

        try:
             import langchain_ollama
             providers.append("ollama")
        except ImportError: pass
        
        return providers


# ============================================
# Convenience Functions
# ============================================

def create_llm(provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> BaseChatModel:
    """Create a Vertex AI LLM instance."""
    return LLMFactory.create(provider=provider, model=model, **kwargs)


def create_default_llm() -> BaseChatModel:
    """Create default LLM (Qwen3:8B on Ollama)."""
    return LLMFactory.create_default()


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("LLM FACTORY TEST")
    print("=" * 60)
    print()
    
    print("Available Providers:")
    available = LLMFactory.get_available_providers()
    for provider in available:
        print(f"  [DONE] {provider}")
    print()
    
    print("Creating default LLM (Qwen3:8B on Ollama)...")
    try:
        llm = create_default_llm()
        
        if isinstance(llm, RateLimitedLLM):
            actual_llm = llm.llm
            print(f"[DONE] Created: RateLimitedLLM wrapping {type(actual_llm).__name__}")
        else:
            print(f"[DONE] Created: {type(llm).__name__}")
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
    print("[DONE] Test complete!")
    print("=" * 60)