"""DatabaseProbe adapter backed by SQLAlchemy."""

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

PROBE_STATEMENT = "SELECT 1"
DEFAULT_TIMEOUT_SECONDS = 2.0

# One shared pair of threads: if the database freezes, at most two checks stay stuck and the
# next ones are answered "down" without piling up more threads.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="database-probe")


class SqlAlchemyDatabaseProbe:
    """Answers "available" only if the database runs a trivial query within the timeout.

    The wait is bounded on the client side. A pooled connection to a database that stopped
    answering would otherwise block in the pool's ping or in the query for as long as the
    operating system keeps the connection open (minutes), and a server-side statement timeout
    cannot fire when the server itself is frozen.
    """

    def __init__(self, engine: Engine, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds

    def _ping(self) -> None:
        with self._engine.connect() as connection:
            connection.execute(text(PROBE_STATEMENT))

    def is_available(self) -> bool:
        future = _executor.submit(self._ping)
        try:
            future.result(timeout=self._timeout_seconds)
            return True
        except FutureTimeout:
            logger.warning("Database health probe timed out after %.1f s", self._timeout_seconds)
            return False
        except SQLAlchemyError:
            logger.warning("Database health probe failed", exc_info=True)
            return False
