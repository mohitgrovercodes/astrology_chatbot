
# src/api/config.py
"""
API Configuration
==================

Centralized configuration for the FastAPI application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings with backward compatibility for existing .env files."""
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "NakshatraAI"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = Field(default="0.0.0.0", validation_alias="api_host")
    PORT: int = Field(default=8000, validation_alias="api_port")
    
    # Security - API Key Authentication
    API_KEY_HEADER: str = "X-API-Key"
    VALID_API_KEYS: str = ""  # Comma-separated string, parsed in __init__
    _parsed_api_keys: List[str] = []  # Internal parsed list
    
    # Security - Internal Service Authentication
    INTERNAL_SERVICE_SECRET: str = Field(default="change-me", validation_alias="internal_service_secret")
    
    # Redis Session Management
    REDIS_HOST: str = Field(default="localhost", validation_alias="redis_host")
    REDIS_PORT: int = Field(default=6379, validation_alias="redis_port")
    REDIS_PASSWORD: Optional[str] = Field(default=None, validation_alias="redis_password")
    SESSION_EXPIRY_HOURS: int = 0  # 0 or None means permanent storage in Redis
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]  # Restrict in production
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100
    

    # LLM Configuration - OpenAI
    OPENAI_API_KEY: str = ""
    
    # LLM Provider and Model
    LLM_PROVIDER: str = Field(
        default="openai",
        validation_alias="default_llm_provider"
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias="default_llm_model"
    )
    
    # Embeddings
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-large",
        validation_alias="openai_embedding_model"
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=3072,
        validation_alias="embedding_dimensions"
    )
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/vectordb",
        validation_alias="chroma_persist_dir"
    )
    
    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias="log_level"
    )
    
    # Orchestrator
    ENABLE_CACHING: bool = True
    MAX_CONVERSATION_HISTORY: int = 10
    
    # Conversation Context Management
    CONVERSATION_CONTEXT_WINDOW: int = Field(
        default=20,
        validation_alias="conversation_context_window",
        description="Number of recent messages to include in conversation history"
    )
    CONVERSATION_SUMMARY_THRESHOLD: int = Field(
        default=20,
        validation_alias="conversation_summary_threshold",
        description="Update conversation summary after this many messages (increased from 6 to preserve context)"
    )

    # Transit Data Freshness
    # Planetary transits change daily, so cached transit data is evicted and
    # recomputed after this many hours. All other cached data (chart, dasha)
    # is permanent since birth-chart positions never change.
    TRANSIT_REFRESH_HOURS: int = Field(
        default=24,
        validation_alias="transit_refresh_hours",
        description="Hours before cached transit data is considered stale and recomputed"
    )

    # Dasha periods (Antardasha) shift over months.  Recompute after this many days.
    DASHA_REFRESH_DAYS: int = Field(
        default=30,
        validation_alias="dasha_refresh_days",
        description="Days before cached Dasha data is considered stale and recomputed"
    )
    
    # Additional LLM Settings
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", validation_alias="ollama_base_url")
    FAST_LLM_PROVIDER: str = Field(default="openai", validation_alias="fast_llm_provider")
    FAST_LLM_MODEL: str = Field(default="gpt-4o-mini", validation_alias="fast_llm_model")
    
    # Legacy Authentication
    ASTRO_USERNAME: str = Field(default="", validation_alias="astro_username")
    ASTRO_PASSWORD: str = Field(default="", validation_alias="astro_password")
    
    # Hugging Face Settings
    HF_OFFLINE_MODE: bool = Field(default=False, validation_alias="hf_offline_mode")
    HF_TIMEOUT: int = Field(default=10, validation_alias="hf_timeout")
    
    # CRITICAL FIX: Use model_config instead of Config class
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
        extra='ignore'  # CRITICAL: Ignore extra env vars instead of forbidding them
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse API keys from comma-separated string
        if self.VALID_API_KEYS:
            self._parsed_api_keys = [k.strip() for k in self.VALID_API_KEYS.split(",") if k.strip()]
        else:
            self._parsed_api_keys = []
    
    def get_api_keys(self) -> List[str]:
        """Get parsed API keys list."""
        return self._parsed_api_keys


# Singleton settings instance
settings = Settings()