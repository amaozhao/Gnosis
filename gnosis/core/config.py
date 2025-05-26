"""
Configuration settings for the Gnosis application.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 基础配置
    PROJECT_NAME: str = "Gnosis"
    DEBUG: bool = True

    # OpenAI 配置
    OPENAI_API_KEY: str = "your-api-key-here"
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"

    # Mistral 配置
    MISTRAL_API_KEY: str = "your-api-key-here"
    MISTRAL_API_BASE: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-large-latest"

    # Deepseek引擎配置
    DEEPSEEK_BASE_URL: str = "your-base-url-here"
    DEEPSEEK_API_KEY: str = "your-api-key-here"
    DEEPSEEK_MODEL: str = "your-model-name-here"

    # 日志设置
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    LOG_FILE: Optional[Path] = None
    JSON_LOGS: bool = True

    # 字幕处理配置
    MAX_CONCURRENT_REQUESTS: int = 5

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow",  # 允许额外的字段
        "validate_default": True,
    }


# Create a global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the settings instance.

    Returns:
        Settings: The application settings.
    """
    return settings
