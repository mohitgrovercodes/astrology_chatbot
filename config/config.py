# config/config.py
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
from config.rag_config import RAGConfig


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
        valid_providers = ['google', 'free']
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of {valid_providers}, got: {v}")
        return v


class EmbeddingsConfig(BaseSettings):
    """Embeddings configuration from YAML."""
    provider: str = "google"
    model: str = "gemini-embedding-001"
    dimensions: int = 1536
    batch_size: int = 100

    model_config = SettingsConfigDict(extra='allow')


class RAGConfig(BaseSettings):
    """RAG pipeline configuration from YAML."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    # REMOVED: top_k: int = 5
    # Now uses config/rag_config.py dynamically
    score_threshold: float = 0.7
    collection_name: str = "vedic_astrology_books_knowledge"
    use_python_config: bool = True  # NEW

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

    # Google Cloud / Vertex AI
    google_cloud_project: Optional[str] = Field(None, validation_alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field("us-central1", validation_alias="GOOGLE_CLOUD_LOCATION")
    google_application_credentials: Optional[str] = Field(None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS")

    # Default LLM Configuration (can override YAML)
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None

    # Embeddings Configuration (can override YAML)
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 1536

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
    """

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path("config/config.yaml")

        self._yaml_config = self._load_yaml(config_path)
        self.env = EnvConfig()

        self.llm = LLMConfig(**self._yaml_config.get("llm", {}))
        self.embeddings = EmbeddingsConfig(**self._yaml_config.get("embeddings", {}))
        self.rag = RAGConfig(**self._yaml_config.get("rag", {}))
        self.safety = SafetyConfig(**self._yaml_config.get("safety", {}))
        self.astrology = AstrologyConfig(**self._yaml_config.get("astrology", {}))
        self.api = APIConfig(**self._yaml_config.get("api", {}))
        self.logging = LoggingConfig(**self._yaml_config.get("logging", {}))

        self._apply_env_overrides()

    def _load_yaml(self, config_path: Path) -> Dict[str, Any]:
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
        if self.env.default_llm_provider:
            self.llm.default_provider = self.env.default_llm_provider
        if self.env.default_llm_model:
            self.llm.default_model = self.env.default_llm_model
        if self.env.embedding_model:
            self.embeddings.model = self.env.embedding_model
        if self.env.embedding_dimensions:
            self.embeddings.dimensions = self.env.embedding_dimensions
        if self.env.log_level:
            self.logging.level = self.env.log_level

    def get_api_key(self, provider: str) -> Optional[str]:
        provider = provider.lower()
        key_map = {
            'google': self.env.google_cloud_project,
            'free': None,
        }
        if provider not in key_map:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: {list(key_map.keys())}"
            )
        return key_map[provider]

    def validate_provider_setup(self, provider: str) -> bool:
        if provider == 'free':
            return True
        api_key = self.get_api_key(provider)
        return api_key is not None and len(api_key) > 0

    def get_available_providers(self) -> List[str]:
        available = []
        for provider in ['google']:
            if self.validate_provider_setup(provider):
                available.append(provider)
        available.append('free')
        return available

    def to_dict(self) -> Dict[str, Any]:
        def mask_value(val: Optional[str]) -> str:
            if not val:
                return "NOT_SET"
            if len(val) < 8:
                return "***"
            return f"{val[:4]}...{val[-4:]}"

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
            },
            "google_cloud": {
                "project": self.env.google_cloud_project or "NOT_SET",
                "location": self.env.google_cloud_location,
                "credentials": mask_value(self.env.google_application_credentials),
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
    """Get the global configuration instance (singleton pattern)."""
    global _config_instance

    if _config_instance is None or reload:
        _config_instance = AppConfig(config_path=config_path)

    return _config_instance


def validate_config() -> None:
    """Validate that required configuration is present."""
    config = get_config()

    if not config.env.google_cloud_project:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT is required (for Vertex AI LLM & embeddings). "
            "Please set it in your .env file."
        )

    default_provider = config.llm.default_provider
    if default_provider != 'free' and not config.validate_provider_setup(default_provider):
        raise ValueError(
            f"Default LLM provider '{default_provider}' is not configured. "
            f"Please set GOOGLE_CLOUD_PROJECT in your .env file, "
            f"or switch to 'free' (Ollama) by setting LLM_PROVIDER=free."
        )

    chroma_dir = Path(config.env.chroma_persist_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("CONFIGURATION LOADER TEST")
    print("=" * 60)

    try:
        config = get_config()
        print("\n[OK] Configuration loaded successfully!\n")
        print("Configuration Summary:")
        print(json.dumps(config.to_dict(), indent=2))

        print("\n" + "=" * 60)
        print("VALIDATION CHECK")
        print("=" * 60)

        validate_config()
        print("\n[OK] Configuration is valid!")

    except Exception as e:
        print(f"\n[FAIL] Configuration Error: {e}")
        raise
