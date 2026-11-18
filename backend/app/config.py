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
    # Minimum cosine similarity for a search hit to be shown. Provisional: measured on 16 queries
    # (catalog queries scored 0.661-0.776, off-catalog ones 0.494-0.588); tune with the evaluations.
    search_min_similarity: float = 0.62
    # Chat model of the shopping assistant (decision 0001); LLM_MODEL overrides it.
    llm_model: str = "qwen3:8b"
    # Applies to one chat request; local CPU inference can be slow.
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.1
    llm_num_ctx: int = 8192
    # Reasoning mode of the model. Off by default (decision 0011): qwen3 turns it on by itself
    # and a turn then takes about 52 s instead of 13 s. True forces it on; None leaves the
    # model default.
    llm_think: bool | None = False
    # Maximum model calls per chat turn before a degraded answer.
    agent_max_steps: int = 6
    # Recent messages sent to the model besides the system prompt and the state.
    agent_history_messages: int = 8
    # Course Excel, mounted read-only from ./data by docker compose.
    dataset_path: str = "/data/MercaNova_dataset_obligatorio_2.xlsx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
