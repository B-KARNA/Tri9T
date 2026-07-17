import os
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"
    PROJECT_NAME: str = "Tri9T"
    API_V1_STR: str = "/api/v1"

    # SQLite / Relational Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"

    # Document Database Settings (supports 'json' file store or 'mongodb')
    DOCUMENT_STORE_TYPE: Literal["json", "mongodb"] = "json"
    DOCUMENT_STORE_PATH: str = "./data/document_db.json"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "tri9t_db"

    # Logging
    LOG_LEVEL: str = "INFO"


# Initialize settings instance
settings = Settings()
