from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional, List
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Incident, Diagnosis, RecoveryAction, Outcome, AuditLog
from ..diagnosis import diagnose_incident
from ..llm_narrator import generate_narrative_and_action, get_deterministic_action
from ..recovery_agent import (
    execute_recovery,
    execute_rollback,
    compute_counterfactuals,
    TERMINAL_STATES,
    _at_risk_revenue,
)
from ..policy import check_recovery_safety, ACTION_HYPOTHESIS_MAP
from ..explainability import get_incident_explanation
from ..audit import verify_audit_chain
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
    role: Optional[str] = "OPERATOR"
    operator_name: Optional[str] = "operator"


class RollbackRequest(BaseModel):
    reason: str = Field(default="Manual operator rollback", max_length=500)
    role: Optional[str] = "OPERATOR"
    operator_name: Optional[str] = "operator"


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
    initial_at_risk = rev
    if diagnosis and diagnosis.evidence_json:
        try:
            ev_data = json.loads(diagnosis.evidence_json)
            initial_at_risk = ev_data.get("at_risk_revenue", rev)
        except Exception:
            initial_at_risk = rev

    incident.initial_at_risk_revenue = round(initial_at_risk, 2)
    incident.remaining_exposure = rev

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
        "outcome": outcome,
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
            "selected_by": "system",
        }

    db.refresh(diagnosis)
    return {
        "diagnosis": diagnosis,
        "proposed_action": action_data,
        "is_terminal": is_terminal,
    }


@router.post("/{id}/recover")
def trigger_recovery(
    id: str,
    action_data: RecoveryRequest,
    x_user_role: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    # Prefer role in payload, then header, default to OPERATOR
    payload = action_data.model_dump()
    role = payload.get("role") or x_user_role or "OPERATOR"
    payload["role"] = role

    try:
        result = execute_recovery(
            db,
            id,
            payload,
            user_role=role,
            operator_name=payload.get("operator_name", "operator"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result.get("status") == "blocked":
        return {
            "status": "blocked",
            "reason": result.get("reason"),
            "state": result.get("state"),
            "outcome": None,
        }

    recovery_completed = result.get("status") in {
        "RESOLVED",
        "ESCALATED_INSUFFICIENT_RECOVERY",
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
        "outcome": outcome,
    }


@router.get("/{id}/counterfactuals")
def get_incident_counterfactuals(id: str, extended: bool = False, db: Session = Depends(get_db)):
    """Retrieve counterfactual projections for candidate recovery actions."""
    try:
        return compute_counterfactuals(db, id, include_extended=extended)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{id}/explanation")
def get_explanation(id: str, db: Session = Depends(get_db)):
    """Retrieve evidence-grounded answers to Why Acted, Why Not Acted, Why Stopped, Why Approval Required."""
    try:
        return get_incident_explanation(db, id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{id}/safety")
def get_safety_check(
    id: str,
    x_user_role: Optional[str] = Header(None),
    role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retrieve complete safety evaluation and gate status for UI display."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == id).first()
    conf = diagnosis.confidence if diagnosis else None
    hyp = diagnosis.hypothesis if diagnosis else "UNKNOWN"
    at_risk = _at_risk_revenue(db, incident)
    action = ACTION_HYPOTHESIS_MAP.get(hyp, "SUPPRESS_RETRIES")
    effective_role = x_user_role or role or "OPERATOR"

    return check_recovery_safety(
        incident_state=incident.state,
        confidence=conf,
        at_risk_revenue=at_risk,
        hypothesis=hyp,
        action=action,
        human_approved=False,
        user_role=effective_role,
        has_diagnosis=(diagnosis is not None),
    )


@router.post("/{id}/rollback")
def trigger_rollback(
    id: str,
    payload: RollbackRequest,
    x_user_role: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Revert applied recovery intervention, restore transaction failure state, and log audit."""
    role = payload.role or x_user_role or "OPERATOR"
    try:
        result = execute_rollback(
            db=db,
            incident_id=id,
            user_role=role,
            operator_name=payload.operator_name,
            reason=payload.reason,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{id}/audit")
def get_audit_trail(id: str, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return logs


@router.get("/{id}/audit/verify")
def verify_audit(id: str, db: Session = Depends(get_db)):
    """Verify cryptographic SHA-256 hash-chain integrity of the incident audit trail."""
    return verify_audit_chain(db, id)