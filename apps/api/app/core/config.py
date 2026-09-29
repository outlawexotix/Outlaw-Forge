import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Outlaw Forge"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # CORS configuration
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "data/outlaw_forge.db")
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/outlaw_forge.db"

    # Storage
    STORAGE_BASE_DIR: str = os.getenv("STORAGE_BASE_DIR", "data")
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
