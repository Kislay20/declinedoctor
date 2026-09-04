"""DeclineDoctor Observability API.

Exposes telemetry, uptime, database health, audit integrity, and latency metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..observability import get_system_observability

router = APIRouter(prefix="/api/observability", tags=["Observability"])


@router.get("")
def get_observability_metrics(db: Session = Depends(get_db)):
    """Retrieve system health, audit verification, processing metrics, and latencies."""
    return get_system_observability(db)
