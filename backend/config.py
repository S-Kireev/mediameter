from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Настройки приложения из .env"""
    
    # Database
    database_url: str = "sqlite:///./mediameter.db"
    
    # API
    api_key: str = "dev_key_change_in_prod"
    secret_key: str = "dev_secret_change_in_prod"
    
    # OpenAI
    openai_api_key: str = "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"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # App
    timezone: str = "Europe/Kyiv"
    debug: bool = False
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
