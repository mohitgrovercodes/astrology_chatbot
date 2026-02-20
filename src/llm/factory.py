# src/llm/factory.py
"""
Enhanced LLM Factory for NakshatraAI - Three Provider Support

This factory supports three LLM providers based on deployment context:
1. Google (Vertex AI) - Development phase with GCP credits
2. OpenAI (GPT-4o-mini) - Production deployment  
3. Free (Llama 3.2 via Ollama) - Testing and fallback

Provider Selection:
- Set via LLM_PROVIDER environment variable ("google" | "openai" | "free")
- Each provider requires different credentials/setup
- Automatic model selection based on purpose (general vs classification)

Rate Limiting:
- Built-in protection against 429 errors
- Configurable delays and retry logic
- Exponential backoff on failures
"""

import os
import time
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel

# Utilities
try:
    from src.utils.config import get_config
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    CONFIG_AVAILABLE = True
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    CONFIG_AVAILABLE = False


# ============================================================================
# RATE-LIMITED LLM WRAPPER
# ============================================================================

from langchain_core.runnables import Runnable

class RateLimitedLLM(Runnable):
    """
    Wrapper that adds rate limiting to any LangChain LLM.
    
    Prevents 429 errors by enforcing minimum delays between calls and
    implementing exponential backoff on failures.
    """
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        min_delay: float = 2.0, 
        max_retries: int = 3, 
        base_backoff: float = 4.0
    ):
        super().__init__()
        self.llm = llm
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._last_call_time = 0
    
    def _wait_if_needed(self):
        """Enforce minimum delay between API calls."""
        current_time = time.time()
        elapsed = current_time - self._last_call_time
        
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        
        self._last_call_time = time.time()
    
    def invoke(self, input, config=None, **kwargs):
        """Invoke with rate limiting and exponential backoff retry logic."""
        for attempt in range(self.max_retries):
            try:
                self._wait_if_needed()
                return self.llm.invoke(input, config=config, **kwargs)
                
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any([
                    "429" in error_str, 
                    "rate limit" in error_str,
                    "resource exhausted" in error_str,
                    "quota" in error_str
                ])
                
                if is_rate_limit and attempt < self.max_retries - 1:
                    wait_time = self.base_backoff * (2 ** attempt)
                    logger.warning(
                        f"Rate limit hit. Waiting {wait_time}s... "
                        f"(Attempt {attempt+1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    raise
        
        raise RuntimeError(f"Failed after {self.max_retries} retries")

    def stream(self, input, config=None, **kwargs):
        """Stream with rate limiting."""
        self._wait_if_needed()
        yield from self.llm.stream(input, config=config, **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        """Async invoke with rate limiting."""
        import asyncio
        for attempt in range(self.max_retries):
            try:
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


# ============================================================================
# THREE-PROVIDER LLM FACTORY
# ============================================================================

class LLMFactory:
    """
    Factory for creating LLM instances across three providers.
    
    Provider Decision Tree:
    1. Check LLM_PROVIDER environment variable
    2. If not set, use config.yaml default
    3. If no config, default to "openai"
    
    Model Selection:
    - Purpose "general": Use best model for quality responses
    - Purpose "classification": Use fast model for routing/validation
    - Purpose "validation": Use model suitable for rule evaluation
    """
    
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
        Create an LLM instance with automatic provider and model selection.
        
        Args:
            provider: "google" | "openai" | "free" (overrides env and config)
            model: Specific model name (overrides automatic selection)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            use_rate_limiting: Wrap with RateLimitedLLM
            rate_limit_delay: Minimum seconds between calls
            purpose: "general" | "classification" | "validation"
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Configured LLM instance (optionally rate-limited)
            
        Environment Variables Required by Provider:
            Google (Vertex AI):
                - GOOGLE_CLOUD_PROJECT
                - GOOGLE_APPLICATION_CREDENTIALS (path to JSON key)
                - GOOGLE_CLOUD_REGION (optional, default: us-central1)
            
            OpenAI:
                - OPENAI_API_KEY
            
            Free (Ollama):
                - OLLAMA_BASE_URL (optional, default: http://localhost:11434)
        """
        
        # Step 1: Determine Provider
        provider = cls._determine_provider(provider)
        
        # Step 2: Select Model (if not explicitly provided)
        if model is None:
            model = cls._select_model_for_provider(provider, purpose)
        
        # Step 3: Get Temperature and Max Tokens
        if temperature is None:
            temperature = 0.3 if purpose == "classification" else 0.5
        
        if max_tokens is None:
            # Enhanced purpose-based token allocation
            # Fixes Issue #4: Response truncation by allocating appropriate tokens per use case
            purpose_token_map = {
                "classification": 1024,   # Fast classification (intent, safety)
                "chitchat": 1024,           # Brief conversational responses
                "general": 4096,           # Standard responses
                "prediction": 4096,        # Detailed predictions with timing
                "rag": 4096,               # Knowledge-heavy RAG responses
                "validation": 4096,        # Validation engine batch processing
            }
            max_tokens = purpose_token_map.get(purpose, 2048)  # Default: 2048
            
            logger.debug(f"Token allocation for purpose '{purpose}': {max_tokens}")
        
        logger.info(
            f"Creating LLM: provider={provider}, model={model}, "
            f"purpose={purpose}, temp={temperature}, max_tokens={max_tokens}"
        )
        
        # Step 4: Create Provider-Specific LLM
        if provider == "google":
            llm = cls._create_google_llm(model, temperature, max_tokens, **kwargs)
        
        elif provider == "openai":
            llm = cls._create_openai_llm(model, temperature, max_tokens, **kwargs)
        
        elif provider == "free":
            llm = cls._create_free_llm(model, temperature, max_tokens, **kwargs)
        
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Must be 'google', 'openai', or 'free'"
            )
        
        # Step 5: Optionally Wrap with Rate Limiter
        if use_rate_limiting:
            llm = RateLimitedLLM(llm, min_delay=rate_limit_delay)
        
        return llm
    
    # ------------------------------------------------------------------------
    # PROVIDER DETERMINATION
    # ------------------------------------------------------------------------
    
    @classmethod
    def _determine_provider(cls, override: Optional[str] = None) -> str:
        """
        Determine which LLM provider to use.
        
        Priority:
        1. Function argument (override)
        2. Environment variable LLM_PROVIDER
        3. Config file default
        4. Hardcoded default ("openai")
        """
        if override:
            return override.lower()
        
        # Check environment variable
        env_provider = os.getenv("LLM_PROVIDER", "").lower()
        if env_provider in ["google", "openai", "free"]:
            return env_provider
        
        # Check config file
        if CONFIG_AVAILABLE:
            config_provider = get_config().llm.default_provider
            if config_provider and config_provider.lower() in ["google", "openai", "free"]:
                return config_provider.lower()
        
        # Default to OpenAI (production-ready)
        return "openai"
    
    @classmethod
    def _select_model_for_provider(cls, provider: str, purpose: str) -> str:
        """
        Select appropriate model based on provider and purpose.
        
        Model Selection Strategy:
        - Google: gemini-2.5-flash for all purposes (fast + capable)
        - OpenAI: gpt-4o-mini for all purposes (cost-effective + good)
        - Free: llama3.2:3b (small enough to run locally, decent quality)
        """
        if provider == "google":
            # Gemini models via Vertex AI
            return "gemini-2.5-flash"  # Fast and capable
        
        elif provider == "openai":
            # OpenAI models
            if purpose == "classification":
                return "gpt-4o-mini"  # Fast and cheap
            else:
                return "gpt-4o-mini"  # Good balance of quality/cost
        
        elif provider == "free":
            # Ollama local models
            if purpose == "classification":
                return "llama3.2:1b"  # Ultra-fast for simple tasks
            else:
                return "llama3.2:3b"  # Good quality for 3B parameter model
        
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    # ------------------------------------------------------------------------
    # GOOGLE (VERTEX AI) LLM CREATION
    # ------------------------------------------------------------------------
    
    @classmethod
    def _create_google_llm(
        cls, 
        model: str, 
        temperature: float, 
        max_tokens: int,
        **kwargs
    ) -> BaseChatModel:
        """
        Create Google Gemini LLM via Vertex AI.
        
        Requires:
            - GOOGLE_CLOUD_PROJECT environment variable
            - GOOGLE_APPLICATION_CREDENTIALS pointing to service account JSON
            - google-cloud-aiplatform package installed
        """
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError:
            raise ImportError(
                "Vertex AI not available. Install with:\n"
                "pip install langchain-google-vertexai google-cloud-aiplatform"
            )
        
        # Get required configuration
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable not set. "
                "This is required for Vertex AI."
            )
        
        location = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if credentials_path and not os.path.exists(credentials_path):
            logger.warning(
                f"GOOGLE_APPLICATION_CREDENTIALS points to non-existent file: "
                f"{credentials_path}"
            )
        
        logger.info(
            f"Initializing Vertex AI: project={project}, "
            f"location={location}, model={model}"
        )
        
        # Create Vertex AI LLM
        llm = ChatVertexAI(
            model=model,
            project=project,
            location=location,
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs
        )
        
        return llm
    
    # ------------------------------------------------------------------------
    # OPENAI LLM CREATION
    # ------------------------------------------------------------------------
    
    @classmethod
    def _create_openai_llm(
        cls, 
        model: str, 
        temperature: float, 
        max_tokens: int,
        **kwargs
    ) -> BaseChatModel:
        """
        Create OpenAI LLM.
        
        Requires:
            - OPENAI_API_KEY environment variable
            - langchain-openai package installed
        """
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "OpenAI not available. Install with:\n"
                "pip install langchain-openai"
            )
        
        # Get API key
        api_key = kwargs.pop("api_key", None) or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in environment or kwargs"
            )
        
        logger.info(f"Initializing OpenAI: model={model}")
        
        # Create OpenAI LLM
        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            **kwargs
        )
        
        return llm
    
    # ------------------------------------------------------------------------
    # FREE (OLLAMA) LLM CREATION
    # ------------------------------------------------------------------------
    
    @classmethod
    def _create_free_llm(
        cls, 
        model: str, 
        temperature: float, 
        max_tokens: int,
        **kwargs
    ) -> BaseChatModel:
        """
        Create free Llama model via Ollama.
        
        Requires:
            - Ollama running locally (or OLLAMA_BASE_URL set)
            - langchain-ollama package installed
            - Model pulled: `ollama pull llama3.2:3b`
        """
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "Ollama not available. Install with:\n"
                "pip install langchain-ollama"
            )
        
        # Get Ollama base URL
        base_url = kwargs.pop("base_url", None) or os.getenv(
            "OLLAMA_BASE_URL", 
            "http://localhost:11434"
        )
        
        logger.info(f"Initializing Ollama: model={model}, base_url={base_url}")
        
        try:
            # Create Ollama LLM
            llm = ChatOllama(
                model=model,
                temperature=temperature,
                base_url=base_url,
                **kwargs
            )
            
            return llm
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "404" in error_msg or "not found" in error_msg:
                logger.error(
                    f"Ollama model '{model}' not found. "
                    f"Please run: ollama pull {model}"
                )
            
            raise


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    purpose: str = "general",
    **kwargs
) -> BaseChatModel:
    """
    Convenience function for creating LLMs.
    
    Usage:
        # Use default provider and model
        llm = create_llm()
        
        # Use specific provider
        llm = create_llm(provider="google")
        
        # Use specific model
        llm = create_llm(provider="openai", model="gpt-4")
        
        # Fast LLM for classification
        fast_llm = create_llm(purpose="classification")
    """
    return LLMFactory.create(provider=provider, model=model, purpose=purpose, **kwargs)


def get_validation_llm() -> BaseChatModel:
    """
    Get LLM specifically configured for validation engine use.
    
    Uses the primary LLM provider but optimized for batch rule evaluation.
    Higher max_tokens for detailed reasoning, moderate temperature.
    """
    return create_llm(
        purpose="validation",
        temperature=0.2,  # Lower for consistency
        max_tokens=4096,  # Higher for batch processing
        use_rate_limiting=True,
        rate_limit_delay=2.0  # Conservative to avoid quota issues
    )


# ============================================================================
# MODULE-LEVEL DEFAULTS
# ============================================================================

# Default LLM for general use (lazy-loaded)
_default_llm = None

def get_default_llm() -> BaseChatModel:
    """Get or create the default LLM instance."""
    global _default_llm
    if _default_llm is None:
        _default_llm = create_llm()
    return _default_llm


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """Test three-provider LLM creation"""
    print("=" * 70)
    print("LLM FACTORY - Three Provider Test")
    print("=" * 70)
    print()
    
    # Test provider determination
    print("1. Provider Determination Test:")
    print(f"   Default provider: {LLMFactory._determine_provider()}")
    print(f"   Override to 'google': {LLMFactory._determine_provider('google')}")
    print(f"   Override to 'free': {LLMFactory._determine_provider('free')}")
    print()
    
    # Test model selection
    print("2. Model Selection Test:")
    for provider in ["google", "openai", "free"]:
        for purpose in ["general", "classification"]:
            model = LLMFactory._select_model_for_provider(provider, purpose)
            print(f"   {provider}/{purpose}: {model}")
    print()
    
    # Test actual LLM creation (comment out providers you don't have configured)
    print("3. LLM Creation Test:")
    
    try:
        # Test provider based on environment
        current_provider = LLMFactory._determine_provider()
        print(f"   Creating LLM with current provider ({current_provider})...")
        llm = create_llm()
        print(f"   ✅ Successfully created {current_provider} LLM")
        
        # Test invocation
        response = llm.invoke("Say 'Hello from NakshatraAI' in one sentence.")
        print(f"   Test response: {response.content[:100]}...")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    print("=" * 70)