"""
LLM Factory for Astrology AI Chatbot.

This module provides a factory pattern to create LLM instances from multiple providers:
- OpenAI (GPT-4o, GPT-4o-mini)
- Google (Gemini 2.5 Pro, Flash)
- xAI (Grok-2, Grok-2-mini)
- Anthropic (Claude Sonnet)

All LLMs are created using LangChain abstractions for consistency.
Automatic cost tracking is enabled for all LLM instances.
"""

from typing import Optional, Dict, Any, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# Note: langchain-xai requires installation of langchain-xai package
# If not available, it will be handled gracefully
try:
    from langchain_xai import ChatXAI
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False

from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.cost_tracking import CostTrackerCallback


logger = get_logger(__name__)


# ============================================
# LLM Factory
# ============================================

class LLMFactory:
    """
    Factory class for creating LLM instances from multiple providers.
    
    Supports:
    - OpenAI (gpt-4o, gpt-4o-mini, gpt-4-turbo)
    - Google (gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite)
    - xAI (grok-2, grok-2-mini)
    - Anthropic (claude-sonnet-4, claude-3-5-sonnet)
    
    Uses configuration from config.yaml and .env for defaults and API keys.
    """
    
    # Mapping of provider names to LangChain classes
    PROVIDER_MAP = {
        "openai": ChatOpenAI,
        "google": ChatGoogleGenerativeAI,
        "anthropic": ChatAnthropic,
    }
    
    # Add xAI if available
    if XAI_AVAILABLE:
        PROVIDER_MAP["xai"] = ChatXAI
    
    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        Create an LLM instance.
        
        Args:
            provider: Provider name (openai, google, xai, anthropic)
                     If None, uses default from config
            model: Model name (e.g., gpt-4o-mini)
                  If None, uses default from config
            temperature: Sampling temperature (0.0 to 1.0)
                       If None, uses default from config
            max_tokens: Maximum tokens in response
                      If None, uses default from config
            api_key: API key for the provider
                    If None, loads from environment
            **kwargs: Additional provider-specific parameters
        
        Returns:
            LangChain BaseChatModel instance
        
        Raises:
            ValueError: If provider is not supported or API key is missing
        
        Example:
            >>> # Use defaults from config
            >>> llm = LLMFactory.create()
            
            >>> # Use specific provider and model
            >>> llm = LLMFactory.create(provider="google", model="gemini-2.5-pro")
            
            >>> # Override temperature
            >>> llm = LLMFactory.create(temperature=0.7)
        """
        config = get_config()
        
        # Use defaults from config if not provided
        if provider is None:
            provider = config.llm.default_provider
        if model is None:
            model = config.llm.default_model
        if temperature is None:
            temperature = config.llm.temperature
        if max_tokens is None:
            max_tokens = config.llm.max_tokens
        
        # Validate provider
        provider = provider.lower()
        if provider not in cls.PROVIDER_MAP:
            available = list(cls.PROVIDER_MAP.keys())
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Available providers: {available}"
            )
        
        # Get API key
        if api_key is None:
            api_key = config.get_api_key(provider)
            if not api_key:
                raise ValueError(
                    f"API key for provider '{provider}' not found. "
                    f"Please set {provider.upper()}_API_KEY in your .env file."
                )
        
        # Get LangChain class for provider
        llm_class = cls.PROVIDER_MAP[provider]
        
        # Build kwargs for LLM
        llm_kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Add API key with provider-specific parameter name
        if provider == "openai":
            llm_kwargs["api_key"] = api_key
        elif provider == "google":
            llm_kwargs["google_api_key"] = api_key
        elif provider == "xai":
            llm_kwargs["xai_api_key"] = api_key
        elif provider == "anthropic":
            llm_kwargs["anthropic_api_key"] = api_key
        
        # Create and return LLM instance
        try:
            llm = llm_class(**llm_kwargs)
            
            # Add cost tracking callback
            cost_callback = CostTrackerCallback(
                provider=provider,
                model=model,
                operation="llm_generation",
                metadata={"factory": True}
            )
            
            # Attach callback to LLM
            if hasattr(llm, 'callbacks'):
                if llm.callbacks is None:
                    llm.callbacks = [cost_callback]
                else:
                    llm.callbacks.append(cost_callback)
            
            logger.info(
                f"Created LLM with cost tracking: provider={provider}, model={model}, "
                f"temperature={temperature}, max_tokens={max_tokens}"
            )
            return llm
        except Exception as e:
            logger.error(f"Failed to create LLM: {e}")
            raise
    
    @classmethod
    def create_default(cls) -> BaseChatModel:
        """
        Create an LLM using default configuration.
        
        Returns:
            LangChain BaseChatModel instance with default settings
        
        Example:
            >>> llm = LLMFactory.create_default()
        """
        return cls.create()
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available providers with configured API keys.
        
        Returns:
            List of provider names
        
        Example:
            >>> providers = LLMFactory.get_available_providers()
            >>> print(providers)
            ['openai', 'google']
        """
        config = get_config()
        return config.get_available_providers()
    
    @classmethod
    def get_supported_models(cls, provider: str) -> List[str]:
        """
        Get list of supported models for a provider.
        
        Args:
            provider: Provider name
        
        Returns:
            List of model names
        
        Raises:
            ValueError: If provider is not supported
        
        Example:
            >>> models = LLMFactory.get_supported_models("openai")
            >>> print(models)
            ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo']
        """
        config = get_config()
        provider = provider.lower()
        
        if provider not in config.llm.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Access the provider config and get models
        provider_config = config.llm.providers[provider]
        return provider_config.models


# ============================================
# Convenience Functions
# ============================================

def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> BaseChatModel:
    """
    Convenience function to create an LLM instance.
    
    This is a shorthand for LLMFactory.create().
    
    Args:
        provider: Provider name (if None, uses default)
        model: Model name (if None, uses default)
        **kwargs: Additional parameters
    
    Returns:
        LangChain BaseChatModel instance
    
    Example:
        >>> from src.llm.factory import create_llm
        >>> llm = create_llm()
        >>> llm = create_llm(provider="google", temperature=0.5)
    """
    return LLMFactory.create(provider=provider, model=model, **kwargs)


def create_default_llm() -> BaseChatModel:
    """
    Create an LLM with default configuration.
    
    Returns:
        LangChain BaseChatModel instance
    
    Example:
        >>> from src.llm.factory import create_default_llm
        >>> llm = create_default_llm()
    """
    return LLMFactory.create_default()


# ============================================
# Provider-Specific Helpers
# ============================================

def create_openai_llm(
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    **kwargs
) -> ChatOpenAI:
    """
    Create an OpenAI LLM instance.
    
    Args:
        model: OpenAI model name
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        ChatOpenAI instance
    """
    return LLMFactory.create(
        provider="openai",
        model=model,
        temperature=temperature,
        **kwargs
    )


def create_google_llm(
    model: str = "gemini-2.5-flash",
    temperature: float = 0.3,
    **kwargs
) -> ChatGoogleGenerativeAI:
    """
    Create a Google Gemini LLM instance.
    
    Args:
        model: Gemini model name
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        ChatGoogleGenerativeAI instance
    """
    return LLMFactory.create(
        provider="google",
        model=model,
        temperature=temperature,
        **kwargs
    )


def create_anthropic_llm(
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.3,
    **kwargs
) -> ChatAnthropic:
    """
    Create an Anthropic Claude LLM instance.
    
    Args:
        model: Claude model name
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        ChatAnthropic instance
    """
    return LLMFactory.create(
        provider="anthropic",
        model=model,
        temperature=temperature,
        **kwargs
    )


def create_xai_llm(
    model: str = "grok-2-mini",
    temperature: float = 0.3,
    **kwargs
):
    """
    Create an xAI Grok LLM instance.
    
    Args:
        model: Grok model name
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        ChatXAI instance
    
    Raises:
        ImportError: If langchain-xai is not installed
    """
    if not XAI_AVAILABLE:
        raise ImportError(
            "langchain-xai is not installed. "
            "Install it with: pip install langchain-xai"
        )
    
    return LLMFactory.create(
        provider="xai",
        model=model,
        temperature=temperature,
        **kwargs
    )


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    """
    Test LLM factory functionality.
    
    Run: python -m src.llm.factory
    """
    import sys
    
    print("=" * 60)
    print("LLM FACTORY TEST")
    print("=" * 60)
    print()
    
    # Check available providers
    print("Available Providers:")
    available = LLMFactory.get_available_providers()
    for provider in available:
        print(f"  ✅ {provider}")
    print()
    
    if not available:
        print("❌ No providers configured! Please set API keys in .env")
        sys.exit(1)
    
    # Test creating default LLM
    print("Creating default LLM...")
    try:
        llm = create_default_llm()
        print(f"✅ Created: {type(llm).__name__}")
        print(f"   Model: {llm.model_name if hasattr(llm, 'model_name') else 'N/A'}")
        print()
    except Exception as e:
        print(f"❌ Failed: {e}")
        print()
    
    # Test creating LLMs for each available provider
    for provider in available:
        print(f"Testing {provider}...")
        try:
            # Get supported models
            models = LLMFactory.get_supported_models(provider)
            print(f"  Supported models: {', '.join(models)}")
            
            # Create LLM with first model
            llm = create_llm(provider=provider, model=models[0])
            print(f"  ✅ Created: {type(llm).__name__}")
            
            # Test a simple invoke
            response = llm.invoke("Say 'Hello' in one word")
            print(f"  Test response: {response.content[:50]}")
            print()
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            print()
    
    print("=" * 60)
    print("✅ LLM Factory test complete!")
    print("=" * 60)