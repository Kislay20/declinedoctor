from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Incident, Diagnosis, RecoveryAction, Outcome, AuditLog
from ..diagnosis import diagnose_incident
from ..llm_narrator import generate_narrative_and_action, get_deterministic_action
from ..recovery_agent import execute_recovery, TERMINAL_STATES, _at_risk_revenue
import json

router = APIRouter()


class RecoveryRequest(BaseModel):
    """Backend-validated recovery request contract exposed in OpenAPI."""
    model_config = ConfigDict(extra="forbid")

    recommended_action: Literal[
        "REROUTE", "ADJUST_RETRY_TIMING", "SUPPRESS_RETRIES"
    ]
    selected_by: str = Field(default="system", min_length=1)
    reasoning: str = Field(default="", max_length=2000)
    human_approved: bool = False

@router.get("")
def get_active_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.detected_at.desc()).all()
    for inc in incidents:
        rev = round(_at_risk_revenue(db, inc), 2)
        inc.at_risk_revenue = rev
        inc.estimated_loss = rev
    return incidents

@router.get("/{id}")
def get_incident_detail(id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    rev = round(_at_risk_revenue(db, incident), 2)
    incident.at_risk_revenue = rev
    incident.estimated_loss = rev

    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == id).first()
    recovery_action = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.incident_id == id)
        .order_by(RecoveryAction.applied_at.desc())
        .first()
    )
    outcome = None
    if recovery_action:
        outcome = (
            db.query(Outcome)
            .filter(Outcome.recovery_action_id == recovery_action.id)
            .first()
        )

    return {
        "incident": incident,
        "diagnosis": diagnosis,
        "recovery_action": recovery_action,
        "outcome": outcome
    }

@router.post("/{id}/diagnose")
def trigger_diagnosis(id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    is_terminal = incident.state in TERMINAL_STATES

    # 1. Deterministic Diagnosis (terminal-protected)
    diagnosis = diagnose_incident(db, id)
    if not diagnosis:
        raise HTTPException(status_code=400, detail="Could not diagnose incident")
        
    # 2. LLM Narrative Generation (skip if already terminal or narrative already exists)
    if not diagnosis.narrative_text and not is_terminal:
        try:
            action_data = generate_narrative_and_action(diagnosis.evidence_json)
            diagnosis.narrative_text = action_data.get("narrative", "")
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        action_data = {
            "narrative": diagnosis.narrative_text or "Incident already diagnosed.",
            "recommended_action": get_deterministic_action(diagnosis.hypothesis),
            "reasoning": "Existing diagnosis retained.",
            "selected_by": "system"
        }
    
    return {
        "diagnosis": diagnosis,
        "proposed_action": action_data,
        "is_terminal": is_terminal
    }

@router.post("/{id}/recover")
def trigger_recovery(id: str, action_data: RecoveryRequest, db: Session = Depends(get_db)):
    try:
        result = execute_recovery(db, id, action_data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    
    # Do not return a stale historical outcome when the recovery request was
    # blocked before a new recovery action/outcome was created.
    if result.get("status") == "blocked":
        return {
            "status": "blocked",
            "reason": result.get("reason"),
            "state": result.get("state"),
            "outcome": None
        }

    # Only return an outcome when this request actually created a recovery outcome.
    recovery_completed = result.get("status") in {
        "RESOLVED",
        "ESCALATED_INSUFFICIENT_RECOVERY"
    }

    outcome = None

    if recovery_completed:
        outcome = (
            db.query(Outcome)
            .join(RecoveryAction)
            .filter(RecoveryAction.incident_id == id)
            .order_by(Outcome.id.desc())
            .first()
        )

    return {
        "status": result["status"],
        "outcome": outcome
    }

@router.get("/{id}/audit")
def get_audit_trail(id: str, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(AuditLog.incident_id == id).order_by(AuditLog.timestamp.asc()).all()
    return logs