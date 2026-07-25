from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Thailand AIaaS Platform"
    API_V1_STR: str = "/api"
    
    # Secrets & API Keys (Loaded from .env at runtime)
    DATABASE_URL: str
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    QWEN_MODEL_NAME: str = "qwen/qwen3.6-flash"
    
    # Optional / Future Services
    AI4THAI_API_KEY: Optional[str] = None
    MCP_SERVER_URL: str = "http://localhost:8001/mcp"

    # Pydantic Settings Config: auto-load local .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()