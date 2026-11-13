"""GET /api/health."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.adapters.persistence.database_probe import SqlAlchemyDatabaseProbe
from app.adapters.persistence.session import get_engine
from app.application.health import check_health
from app.application.ports import DatabaseProbe

router = APIRouter(prefix="/api", tags=["health"])

State = Literal["ok", "down", "unknown"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    db: State
    llm: State
    stt: State


def get_database_probe() -> DatabaseProbe:
    return SqlAlchemyDatabaseProbe(get_engine())


@router.get("/health", response_model=HealthResponse)
def health(database: DatabaseProbe = Depends(get_database_probe)) -> HealthResponse:
    report = check_health(database)
    return HealthResponse(status=report.status, db=report.db, llm=report.llm, stt=report.stt)
