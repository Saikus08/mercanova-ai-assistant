"""Application configuration, read only from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # SQLAlchemy URL using the psycopg 3 driver,
    # e.g. postgresql+psycopg://user:password@db:5432/mercanova
    database_url: str
    ollama_base_url: str = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_seconds: float = 30.0
    # Course Excel, mounted read-only from ./data by docker compose.
    dataset_path: str = "/data/MercaNova_dataset_obligatorio_2.xlsx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
