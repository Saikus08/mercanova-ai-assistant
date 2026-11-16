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
    # Applies to one request, which embeds one batch; a CPU batch of 32 took about 15 s.
    embedding_timeout_seconds: float = 120.0
    embedding_batch_size: int = 16
    # Course Excel, mounted read-only from ./data by docker compose.
    dataset_path: str = "/data/MercaNova_dataset_obligatorio_2.xlsx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
