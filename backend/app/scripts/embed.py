"""Build or refresh the product embeddings used by semantic search.

Usage, inside the backend container::

    python -m app.scripts.embed

Only products that are missing or whose text or embedding model changed are embedded, so
running it again right after leaves everything untouched. Requires Ollama with the
embedding model pulled (make pull-models) and the catalog loaded (make seed).
"""

import logging
import sys

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.llm.ollama_embeddings import OllamaEmbeddings
from app.adapters.persistence.embedding_indexer import EmbeddingIndexer, IndexSummary
from app.adapters.persistence.session import get_session_factory
from app.application.ports import EmbeddingModel
from app.config import get_settings
from app.domain.search import SearchUnavailable

logger = logging.getLogger("embed")


def run_embed(session_factory: sessionmaker[Session], embedder: EmbeddingModel) -> IndexSummary:
    with session_factory() as session:
        return EmbeddingIndexer(session, embedder).run()


def format_summary(summary: IndexSummary) -> str:
    return f"Products: {summary.total}  embedded: {summary.embedded}  skipped: {summary.skipped}"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    embedder = OllamaEmbeddings(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout_seconds
    )
    logger.info("Embedding with %s at %s", settings.embedding_model, settings.ollama_base_url)
    try:
        summary = run_embed(get_session_factory(), embedder)
    except SearchUnavailable as error:
        logger.error(
            "Ollama is unavailable (%s). Check that it is running and the model is pulled "
            "(make pull-models). Batches already embedded were saved; run again to continue.",
            error,
        )
        return 1
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
