"""Ports (interfaces) that adapters implement."""

from typing import Protocol


class DatabaseProbe(Protocol):
    def is_available(self) -> bool:
        """Return True when the database answers a trivial query."""
        ...
