import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..detection import detect_anomalies
from ..simulation import run_recovery_simulation
from ..streaming import process_transaction_event

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.seed_data import seed_database

router = APIRouter()


class SimulationRequest(BaseModel):
    segment_issuer: str = Field(default="Bank X")
    segment_payment_method: str = Field(default="card")
    transaction_count: int = Field(default=500, ge=10, le=100000)
    failure_rate: float = Field(default=0.40, ge=0.0, le=1.0)
    average_amount: float = Field(default=1850.0, ge=1.0)
    diagnosis_hypothesis: str = Field(default="ROUTING_CONNECTIVITY_ISSUE")
    action: str = Field(default="REROUTE")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    user_role: str = Field(default="OPERATOR")
    human_approved: bool = Field(default=False)


class StreamEventRequest(BaseModel):
    issuer: str = Field(default="Bank X")
    payment_method: str = Field(default="card")
    amount: float = Field(default=1500.0, ge=1.0)
    success: bool = Field(default=False)
    decline_code: Optional[str] = Field(default="processor_declined")
    decline_reason: Optional[str] = Field(default="Processor communication timeout")
    auto_recover: bool = Field(default=False)
    auto_execute: Optional[bool] = Field(default=None)
    user_role: str = Field(default="OPERATOR")


@router.post("/inject")
def reset_and_detect():
    """Reset database to fresh demo baseline and run detection."""
    seed_database()
    demo_time = datetime.now()
    db = SessionLocal()
    try:
        anomalies = detect_anomalies(db, demo_time)
        return {
            "status": "success",
            "message": "Data seeded and anomalies detected.",
            "incidents_detected": len(anomalies),
        }
    finally:
        db.close()


@router.post("/recovery")
def simulate_recovery(payload: SimulationRequest):
    """Run controlled recovery sandbox simulation with exact recovery mathematics."""
    return run_recovery_simulation(payload.model_dump())


@router.post("/stream")
def stream_transaction_event(payload: StreamEventRequest, db: Session = Depends(get_db)):
    """Ingest a live stream event and process it through detection, diagnosis, policy, and recovery."""
    should_auto_recover = payload.auto_recover if payload.auto_execute is None else payload.auto_execute
    return process_transaction_event(
        db=db,
        event=payload.model_dump(),
        auto_recover=should_auto_recover,
        user_role=payload.user_role,
    )