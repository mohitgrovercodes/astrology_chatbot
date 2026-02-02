"""
Configuration loader for Astrology AI Chatbot.

This module loads and validates configuration from:
1. Environment variables (.env file)
2. YAML configuration (config/config.yaml)

Environment variables take precedence over YAML values for overlapping settings.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


# ============================================
# Pydantic Models for YAML Configuration
# ============================================

class LLMProviderConfig(BaseSettings):
    """Configuration for a specific LLM provider."""
    models: List[str]
    
    model_config = SettingsConfigDict(extra='allow')


class LLMConfig(BaseSettings):
    """LLM configuration from YAML."""
    default_provider: str
    default_model: str
    temperature: float = 0.3
    max_tokens: int = 2048
    providers: Dict[str, LLMProviderConfig]
    
    model_config = SettingsConfigDict(extra='allow')
    
    @field_validator('default_provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is one of the supported ones."""
        valid_providers = ['openai', 'google', 'xai', 'anthropic']
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of {valid_providers}, got: {v}")
        return v


class EmbeddingsConfig(BaseSettings):
    """Embeddings configuration from YAML."""
    provider: str = "openai"
    model: str = "text-embedding-3-large"
    dimensions: int = 3072
    
    model_config = SettingsConfigDict(extra='allow')


class RAGConfig(BaseSettings):
    """RAG pipeline configuration from YAML."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    score_threshold: float = 0.7
    collection_name: str = "astrology_knowledge"
    
    model_config = SettingsConfigDict(extra='allow')


class SafetyConfig(BaseSettings):
    """Safety and guardrails configuration from YAML."""
    blocked_topics: List[str]
    disclaimer_topics: Dict[str, Dict[str, str]]
    
    model_config = SettingsConfigDict(extra='allow')


class AstrologyConfig(BaseSettings):
    """Astrology-specific configuration from YAML."""
    systems: List[str]
    default_system: str = "vedic"
    ayanamsa: str = "lahiri"
    
    model_config = SettingsConfigDict(extra='allow')
    
    @field_validator('default_system')
    @classmethod
    def validate_system(cls, v: str) -> str:
        """Validate system is supported."""
        valid_systems = ['vedic', 'western']
        if v not in valid_systems:
            raise ValueError(f"System must be one of {valid_systems}, got: {v}")
        return v


class APIConfig(BaseSettings):
    """API configuration from YAML."""
    title: str = "Astrology AI Chatbot API"
    version: str = "1.0.0"
    description: str = "Expert-level Astrology Chatbot"
    rate_limit: int = 60
    timeout: int = 30
    
    model_config = SettingsConfigDict(extra='allow')


class LoggingConfig(BaseSettings):
    """Logging configuration from YAML."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_logging: bool = False
    log_file: str = "./logs/app.log"
    
    model_config = SettingsConfigDict(extra='allow')


# ============================================
# Environment Variables Configuration
# ============================================

class EnvConfig(BaseSettings):
    """Environment variables configuration (.env file)."""
    
    # LLM Provider API Keys
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Default LLM Configuration (can override YAML)
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None
    
    # Embeddings Configuration (can override YAML)
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    
    # ChromaDB
    chroma_persist_dir: str = "./data/vectordb"
    
    # Application Settings
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )


# ============================================
# Main Application Configuration
# ============================================

class AppConfig:
    """
    Main application configuration.
    
    Loads configuration from:
    1. config/config.yaml (base configuration)
    2. .env file (environment variables, overrides YAML where applicable)
    
    Usage:
        from src.utils.config import get_config
        
        config = get_config()
        print(config.llm.default_provider)
        print(config.env.openai_api_key)
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config.yaml file. 
                        Defaults to ./config/config.yaml
        """
        # Set default config path
        if config_path is None:
            config_path = Path("config/config.yaml")
        
        # Load YAML configuration
        self._yaml_config = self._load_yaml(config_path)
        
        # Load environment variables
        self.env = EnvConfig()
        
        # Parse YAML into typed models
        self.llm = LLMConfig(**self._yaml_config.get("llm", {}))
        self.embeddings = EmbeddingsConfig(**self._yaml_config.get("embeddings", {}))
        self.rag = RAGConfig(**self._yaml_config.get("rag", {}))
        self.safety = SafetyConfig(**self._yaml_config.get("safety", {}))
        self.astrology = AstrologyConfig(**self._yaml_config.get("astrology", {}))
        self.api = APIConfig(**self._yaml_config.get("api", {}))
        self.logging = LoggingConfig(**self._yaml_config.get("logging", {}))
        
        # Apply environment variable overrides
        self._apply_env_overrides()
    
    def _load_yaml(self, config_path: Path) -> Dict[str, Any]:
        """
        Load YAML configuration file.
        
        Args:
            config_path: Path to config.yaml
            
        Returns:
            Dictionary of configuration values
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please create it or check the path."
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                config = yaml.safe_load(f)
                if config is None:
                    raise ValueError("Config file is empty")
                return config
            except yaml.YAMLError as e:
                raise yaml.YAMLError(f"Error parsing YAML config: {e}")
    
    def _apply_env_overrides(self) -> None:
        """
        Apply environment variable overrides to YAML configuration.
        
        Environment variables take precedence over YAML values.
        """
        # Override LLM provider and model if set in env
        if self.env.default_llm_provider:
            self.llm.default_provider = self.env.default_llm_provider
        
        if self.env.default_llm_model:
            self.llm.default_model = self.env.default_llm_model
        
        # Override embeddings if set in env
        if self.env.openai_embedding_model:
            self.embeddings.model = self.env.openai_embedding_model
        
        if self.env.embedding_dimensions:
            self.embeddings.dimensions = self.env.embedding_dimensions
        
        # Override log level if set in env
        if self.env.log_level:
            self.logging.level = self.env.log_level
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a specific provider.
        
        Args:
            provider: Provider name (openai, google, xai, anthropic)
            
        Returns:
            API key string or None if not set
            
        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()
        
        key_map = {
            'openai': self.env.openai_api_key,
            'google': self.env.google_api_key,
            'xai': self.env.xai_api_key,
            'anthropic': self.env.anthropic_api_key,
        }
        
        if provider not in key_map:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: {list(key_map.keys())}"
            )
        
        return key_map[provider]
    
    def validate_provider_setup(self, provider: str) -> bool:
        """
        Check if a provider is properly configured with API key.
        
        Args:
            provider: Provider name
            
        Returns:
            True if provider has API key set
        """
        api_key = self.get_api_key(provider)
        return api_key is not None and len(api_key) > 0
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of providers that have API keys configured.
        
        Returns:
            List of provider names with valid API keys
        """
        available = []
        for provider in ['openai', 'google', 'xai', 'anthropic']:
            if self.validate_provider_setup(provider):
                available.append(provider)
        return available
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary (for debugging/logging).
        
        Note: API keys are masked for security.
        
        Returns:
            Dictionary representation of config
        """
        def mask_api_key(key: Optional[str]) -> str:
            """Mask API key for display."""
            if not key:
                return "NOT_SET"
            if len(key) < 8:
                return "***"
            return f"{key[:4]}...{key[-4:]}"
        
        return {
            "llm": {
                "default_provider": self.llm.default_provider,
                "default_model": self.llm.default_model,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "embeddings": {
                "provider": self.embeddings.provider,
                "model": self.embeddings.model,
                "dimensions": self.embeddings.dimensions,
            },
            "rag": {
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
                "top_k": self.rag.top_k,
            },
            "api_keys": {
                "openai": mask_api_key(self.env.openai_api_key),
                "google": mask_api_key(self.env.google_api_key),
                "xai": mask_api_key(self.env.xai_api_key),
                "anthropic": mask_api_key(self.env.anthropic_api_key),
            },
            "chroma_persist_dir": self.env.chroma_persist_dir,
            "log_level": self.logging.level,
            "available_providers": self.get_available_providers(),
        }


# ============================================
# Singleton Instance
# ============================================

_config_instance: Optional[AppConfig] = None


def get_config(config_path: Optional[Path] = None, reload: bool = False) -> AppConfig:
    """
    Get the global configuration instance (singleton pattern).
    
    Args:
        config_path: Path to config.yaml (only used on first call)
        reload: Force reload of configuration
        
    Returns:
        AppConfig instance
        
    Example:
        >>> from src.utils.config import get_config
        >>> config = get_config()
        >>> print(config.llm.default_provider)
        'openai'
        >>> print(config.env.openai_api_key)
        'sk-...'
    """
    global _config_instance
    
    if _config_instance is None or reload:
        _config_instance = AppConfig(config_path=config_path)
    
    return _config_instance


# ============================================
# Convenience Functions
# ============================================

def validate_config() -> None:
    """
    Validate that required configuration is present.
    
    Raises:
        ValueError: If critical configuration is missing
    """
    config = get_config()
    
    # Check that at least OpenAI key is set (required for embeddings)
    if not config.env.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required (for embeddings). "
            "Please set it in your .env file."
        )
    
    # Check that default provider has API key
    default_provider = config.llm.default_provider
    if not config.validate_provider_setup(default_provider):
        raise ValueError(
            f"Default LLM provider '{default_provider}' is not configured. "
            f"Please set {default_provider.upper()}_API_KEY in your .env file."
        )
    
    # Check that ChromaDB directory exists or can be created
    chroma_dir = Path(config.env.chroma_persist_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    """
    Test configuration loading.
    
    Run: python -m src.utils.config
    """
    import json
    
    print("=" * 60)
    print("CONFIGURATION LOADER TEST")
    print("=" * 60)
    
    try:
        config = get_config()
        print("\n[DONE] Configuration loaded successfully!\n")
        
        print("Configuration Summary:")
        print(json.dumps(config.to_dict(), indent=2))
        
        print("\n" + "=" * 60)
        print("VALIDATION CHECK")
        print("=" * 60)
        
        validate_config()
        print("\n[DONE] Configuration is valid!")
        
    except Exception as e:
        print(f"\n❌ Configuration Error: {e}")
        raise