from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Thailand AIaaS Platform"
    API_V1_STR: str = "/api"
    
    # Database Credentials
    DATABASE_URL: str
    
    # Pathumma / ThaiLLM AI4Thai Service Config
    APP_AI4THAI_API_KEY: str
    PATHUMMA_BASE_URL: str = "https://tokenmind.pathumma.in.th/v1"
    PATHUMMA_MODEL_NAME: str = "thaillm-8b" # or your assigned Pathumma model slug
    
    # ASR Config
    ASR_URL: str = "https://tokenmind.pathumma.in.th"
    ASR_MODEL: str = "ptm-asr-1"
    
    # MCP Server Configuration
    MCP_SERVER_URL: str = "http://localhost:8001/mcp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()