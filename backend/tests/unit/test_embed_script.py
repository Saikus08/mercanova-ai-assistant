"""Wiring of the embed script: settings reach the embedder and the indexer."""

from app.scripts import embed


class FakeSettings:
    ollama_base_url = "http://ollama:11434"
    embedding_model = "nomic-embed-text"
    embedding_timeout_seconds = 120.0
    embedding_batch_size = 7


def test_main_passes_configured_batch_size_and_closes_embedder(monkeypatch):
    captured: dict = {}

    class FakeIndexer:
        def __init__(self, session, embedder, batch_size):
            captured["batch_size"] = batch_size
            captured["embedder"] = embedder

        def run(self):
            return embed.IndexSummary(0, 0, 0)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(embed, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(embed, "get_session_factory", lambda: FakeSession)
    monkeypatch.setattr(embed, "EmbeddingIndexer", FakeIndexer)

    assert embed.main() == 0

    assert captured["batch_size"] == 7
    assert captured["embedder"]._client.is_closed


def test_settings_default_to_a_batch_that_fits_the_timeout():
    from app.config import Settings

    settings = Settings(database_url="postgresql+psycopg://x")

    assert settings.embedding_batch_size == 16
    assert settings.embedding_timeout_seconds == 120.0
