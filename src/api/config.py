"""
API Configuration
==================

Centralized configuration for the FastAPI application.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
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
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]  # Restrict in production
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100
    
    # Database
    MONGODB_URI: str = ""
    USE_DUMMY_USER_DB: bool = True
    
    # LLM Configuration - Google Cloud (Vertex AI)
    # Support both new and old field names for backward compatibility
    GOOGLE_CREDENTIALS_PATH: str = Field(
        default="",
        validation_alias="google_application_credentials"
    )
    GOOGLE_PROJECT_ID: str = Field(
        default="",
        validation_alias="google_cloud_project"
    )
    GOOGLE_LOCATION: str = Field(
        default="us-central1",
        validation_alias="vertex_ai_location"
    )
    
    # LLM Configuration - OpenAI
    OPENAI_API_KEY: str = ""
    
    # LLM Provider and Model
    LLM_PROVIDER: str = Field(
        default="google",
        validation_alias="default_llm_provider"
    )
    LLM_MODEL: str = Field(
        default="gemini-2.0-flash-exp",
        validation_alias="default_llm_model"
    )
    
    # Additional settings from your existing .env
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-large",
        validation_alias="openai_embedding_model"
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=3072,
        validation_alias="embedding_dimensions"
    )
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/vectordb",
        validation_alias="chroma_persist_dir"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias="log_level"
    )
    
    # Orchestrator
    ENABLE_CACHING: bool = True
    MAX_CONVERSATION_HISTORY: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        populate_by_name = True  # Allow using both field name and alias
    
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
