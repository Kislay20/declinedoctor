from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional, List
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Incident, Diagnosis, RecoveryAction, Outcome, AuditLog, Transaction
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
    target_provider: Optional[str] = None
    projected_lift_pp: Optional[float] = None
    projected_gross_recovery: Optional[float] = None
    projected_net_recovery: Optional[float] = None


class RollbackRequest(BaseModel):
    reason: str = Field(default="Manual operator rollback", max_length=500)
    role: Optional[str] = "OPERATOR"
    operator_name: Optional[str] = "operator"


class ApprovalRejectRequest(BaseModel):
    reason: str = Field(default="Rejected by operator during dual-control review", max_length=500)
    role: Optional[str] = "OPERATOR"
    operator_name: Optional[str] = "operator"


@router.get("/feed")
def get_incident_feed(db: Session = Depends(get_db)):
    """Retrieve real-time activity feed of payment incidents with severity, diagnosis, and policy states."""
    incidents = db.query(Incident).order_by(Incident.detected_at.desc()).limit(50).all()
    feed = []
    for inc in incidents:
        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()
        at_risk = round(_at_risk_revenue(db, inc), 2)
        hyp = diag.hypothesis if diag else "UNAVAILABLE"
        conf = diag.confidence if diag else 0.0

        # Policy & Approval status
        if inc.state in TERMINAL_STATES:
            approval_state = "TERMINAL_LOCKED"
            policy_result = "LOCKED"
        elif at_risk > 500_000.0 or inc.state == "AWAITING_HUMAN_APPROVAL":
            approval_state = "APPROVAL_REQUIRED"
            policy_result = "PAUSED_FOR_APPROVAL"
        elif conf < 0.70 or inc.state == "ESCALATED_LOW_CONFIDENCE":
            approval_state = "NOT_REQUIRED_BLOCKED"
            policy_result = "BLOCKED_LOW_CONFIDENCE"
        else:
            approval_state = "AUTONOMOUS_ELIGIBLE"
            policy_result = "SAFE_TO_EXECUTE"

        rec_action = ACTION_HYPOTHESIS_MAP.get(hyp, "SUPPRESS_RETRIES")
        dominant_code = diag.dominant_decline_code if diag else "none"

        feed.append({
            "incident_id": inc.id,
            "timestamp": inc.detected_at.strftime("%H:%M:%S") if inc.detected_at else "00:00:00",
            "iso_timestamp": inc.detected_at.isoformat() if inc.detected_at else None,
            "severity": getattr(inc, "severity", "MEDIUM"),
            "issuer": inc.segment_issuer,
            "payment_method": inc.segment_payment_method,
            "revenue_at_risk": at_risk,
            "drop_pp": round(inc.drop_pp, 2),
            "current_state": inc.state,
            "diagnosis": {
                "hypothesis": hyp,
                "confidence": conf,
                "confidence_pct": int(conf * 100),
                "dominant_code": dominant_code,
            },
            "policy_result": policy_result,
            "recommended_action": rec_action,
            "approval_state": approval_state,
            "summary": f"{dominant_code} spike (drop: -{inc.drop_pp:.1f}pp, ₹{at_risk:,.0f} at risk)",
        })
    return feed


@router.get("/approval-queue")
def get_approval_queue_endpoint(db: Session = Depends(get_db)):
    """Retrieve authoritative list of incidents pending dual-control human approval."""
    from ..policy import get_dual_control_approval_queue
    return get_dual_control_approval_queue(db)


@router.get("")
def list_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.detected_at.desc()).all()
    results = []
    for inc in incidents:
        rev = round(_at_risk_revenue(db, inc), 2)
        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()
        if diag:
            conf = diag.confidence
            hyp = diag.hypothesis
            dom_code = diag.dominant_decline_code
        else:
            failures = (
                db.query(Transaction)
                .filter(
                    Transaction.timestamp >= inc.window_start,
                    Transaction.timestamp <= inc.window_end,
                    Transaction.issuer == inc.segment_issuer,
                    Transaction.payment_method == inc.segment_payment_method,
                    Transaction.success == False,
                )
                .all()
            )
            if failures:
                decline_counts = {}
                for f in failures:
                    code = f.decline_code or "unknown"
                    decline_counts[code] = decline_counts.get(code, 0) + 1
                dom_code = max(decline_counts, key=decline_counts.get)
                dom_share = decline_counts[dom_code] / len(failures)
                sample_size_factor = min(inc.sample_size / 150.0, 1.0)
                raw_confidence = (
                    (0.5 * inc.concentration_ratio)
                    + (0.3 * dom_share)
                    + (0.2 * sample_size_factor)
                )
                conf = round(min(raw_confidence, 1.0), 2)
            else:
                dom_code = None
                conf = None
            hyp = None
        
        inc_dict = {
            "id": inc.id,
            "detected_at": inc.detected_at.isoformat() if inc.detected_at else None,
            "segment_issuer": inc.segment_issuer,
            "segment_payment_method": inc.segment_payment_method,
            "window_start": inc.window_start.isoformat() if inc.window_start else None,
            "window_end": inc.window_end.isoformat() if inc.window_end else None,
            "baseline_success_rate": inc.baseline_success_rate,
            "incident_success_rate": inc.incident_success_rate,
            "drop_pp": inc.drop_pp,
            "concentration_ratio": inc.concentration_ratio,
            "sample_size": inc.sample_size,
            "state": inc.state,
            "severity": getattr(inc, "severity", "MEDIUM"),
            "advanced_stats_json": inc.advanced_stats_json,
            "at_risk_revenue": rev,
            "estimated_loss": rev,
            "confidence": conf,
            "hypothesis": hyp,
            "dominant_decline_code": diag.dominant_decline_code if diag else None,
        }
        results.append(inc_dict)
    return results



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

    rec_cf = None
    if diagnosis:
        try:
            cfs = compute_counterfactuals(db, id, include_extended=True, include_baseline=False)
            rec_cf = (
                next((c for c in cfs if c.get("is_recommended")), None)
                or next((c for c in cfs if c.get("is_compatible") and c.get("action_type") != "NO_ACTION"), None)
            )
        except Exception:
            rec_cf = None

    return {
        "incident": incident,
        "diagnosis": diagnosis,
        "recovery_action": recovery_action,
        "outcome": outcome,
        "recommended_recovery": rec_cf,
        "proposed_action": rec_cf.get("action_type") if rec_cf else None,
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

    # Attach authoritative frozen counterfactual projection if available
    try:
        cfs = compute_counterfactuals(db, id, include_extended=True, include_baseline=False)
        rec_cf = (
            next((c for c in cfs if c.get("is_recommended")), None)
            or next((c for c in cfs if c.get("is_compatible") and c.get("action_type") != "NO_ACTION"), None)
        )
        if rec_cf and isinstance(action_data, dict):
            action_data["target_provider"] = rec_cf.get("target_provider")
            action_data["expected_improvement_pp"] = rec_cf.get("expected_improvement_pp")
            action_data["expected_recovered_revenue"] = rec_cf.get("expected_recovered_revenue")
            action_data["expected_net_recovery"] = rec_cf.get("expected_net_recovery")
    except Exception:
        pass

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
def get_incident_counterfactuals(
    id: str,
    extended: bool = False,
    include_baseline: bool = False,
    db: Session = Depends(get_db),
):
    """Retrieve counterfactual projections for candidate recovery actions."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == id).first()
    if not diagnosis:
        return []

    try:
        return compute_counterfactuals(
            db, id, include_extended=extended, include_baseline=include_baseline
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{id}/reject")
def reject_incident_approval(
    id: str,
    payload: ApprovalRejectRequest,
    x_user_role: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Reject human approval request for an incident, transition state, and append audit log."""
    from ..policy import can_approve_recovery
    from ..audit import log_audit_event

    role = payload.role or x_user_role or "OPERATOR"
    if not can_approve_recovery(role):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not authorized to reject or approve recovery actions. Dual-control authorization requires ADMIN or OPERATOR.",
        )

    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.state in TERMINAL_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject: Incident is already in terminal state '{incident.state}'.",
        )

    at_risk = round(_at_risk_revenue(db, incident), 2)
    old_state = incident.state
    incident.state = "APPROVAL_REJECTED"
    db.commit()

    log_audit_event(
        db=db,
        incident_id=id,
        actor=payload.operator_name or "operator",
        event_type="APPROVAL_REJECTED",
        details={
            "previous_state": old_state,
            "new_state": "APPROVAL_REJECTED",
            "role": role,
            "reason": payload.reason,
            "at_risk_revenue": at_risk,
            "action": "MITIGATION_HALTED",
        },
    )

    return {
        "status": "APPROVAL_REJECTED",
        "incident_id": id,
        "state": "APPROVAL_REJECTED",
        "reason": payload.reason,
        "operator": payload.operator_name,
        "role": role,
    }


@router.get("/{id}/explanation")
@router.get("/{id}/explain")
def get_explanation(id: str, db: Session = Depends(get_db)):
    """Retrieve evidence-grounded answers to Why Acted, Why Not Acted, Why Stopped, Why Approval Required."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
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
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
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
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return verify_audit_chain(db, id)