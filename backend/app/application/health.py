"""Health check use case."""

from dataclasses import dataclass
from typing import Literal

from app.application.ports import DatabaseProbe

ServiceState = Literal["ok", "down", "unknown"]


@dataclass(frozen=True)
class HealthReport:
    # "ok" means the API process itself answers; each dependency reports its own state
    # so the store keeps working when one of them is down.
    status: Literal["ok"]
    db: ServiceState
    llm: ServiceState
    stt: ServiceState


def check_health(database: DatabaseProbe) -> HealthReport:
    db_state: ServiceState = "ok" if database.is_available() else "down"
    # LLM and speech-to-text probes are added together with those adapters.
    return HealthReport(status="ok", db=db_state, llm="unknown", stt="unknown")
