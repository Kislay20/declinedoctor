import uuid
import json
from sqlalchemy.orm import Session
from .models import Incident, Diagnosis, RecoveryAction, Outcome, Transaction, AuditLog

# Fixed effect-size assumptions from Spec Section 3
EFFECT_SIZES = {
    "REROUTE": 0.42,
    "ADJUST_RETRY_TIMING": 0.21,
    "SUPPRESS_RETRIES": 0.00
}

# Backend-owned safety boundaries from the Product Spec.
MIN_REVENUE_FOR_AUTO_ACTION = 50_000.0
MAX_REVENUE_FOR_AUTO_APPROVE = 500_000.0
CONFIDENCE_THRESHOLD = 0.70
MAX_SIMULATED_RETRIES_PER_TRANSACTION = 2

# Diagnosis/action compatibility is enforced here, at the recovery boundary,
# independently of whatever the LLM proposes.
ALLOWED_ACTIONS_BY_HYPOTHESIS = {
    "ROUTING_CONNECTIVITY_ISSUE": "REROUTE",
    "BIN_LEVEL_TEMPORARY_ISSUE": "ADJUST_RETRY_TIMING",
    "ISSUER_SIDE_DECLINE": "SUPPRESS_RETRIES",
    "INSUFFICIENT_SIGNAL": "SUPPRESS_RETRIES",
}

TERMINAL_STATES = {
    "RESOLVED",
    "ESCALATED_INSUFFICIENT_RECOVERY",
    "ESCALATED_LOW_CONFIDENCE",
    "ESCALATED_LOW_REVENUE",
}

def log_audit(db: Session, incident_id: str, actor: str, event_type: str, details: dict):
    audit = AuditLog(
        incident_id=incident_id,
        actor=actor,
        event_type=event_type,
        details_json=json.dumps(details)
    )
    db.add(audit)
    db.commit()


def _incident_transactions(db: Session, incident: Incident):
    return db.query(Transaction).filter(
        Transaction.timestamp >= incident.window_start,
        Transaction.timestamp <= incident.window_end,
        Transaction.issuer == incident.segment_issuer,
        Transaction.payment_method == incident.segment_payment_method
    ).all()


def _at_risk_revenue(db: Session, incident: Incident) -> float:
    return sum(t.amount for t in _incident_transactions(db, incident) if not t.success)


def execute_recovery(db: Session, incident_id: str, action_data: dict):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()

    if not incident or not diagnosis:
        raise ValueError("Incident or Diagnosis not found")

    # Terminal incidents cannot be acted on again. This also prevents an
    # alternate action after ESCALATED_INSUFFICIENT_RECOVERY.
    if incident.state in TERMINAL_STATES:
        log_audit(db, incident.id, "system", "RECOVERY_BLOCKED", {
            "reason": "Incident is already in a terminal state",
            "state": incident.state
        })
        return {"status": "blocked", "reason": "terminal_incident", "state": incident.state}

    # 1. Guardrail Check: Confidence Threshold
    if diagnosis.confidence < CONFIDENCE_THRESHOLD:
        incident.state = "ESCALATED_LOW_CONFIDENCE"
        db.commit()
        log_audit(db, incident.id, "system", "ESCALATION", {
            "reason": "Confidence < 0.70",
            "confidence": diagnosis.confidence
        })
        return {"status": "escalated", "reason": "low_confidence"}

    # Calculate revenue at risk from the same incident window/segment used by
    # the recovery simulation. This is a backend-owned financial boundary.
    at_risk_revenue = _at_risk_revenue(db, incident)

    # 2. Minimum revenue gate: do not auto-act on immaterial exposure.
    if at_risk_revenue < MIN_REVENUE_FOR_AUTO_ACTION:
        incident.state = "ESCALATED_LOW_REVENUE"
        db.commit()
        log_audit(db, incident.id, "system", "ESCALATION", {
            "reason": "At-risk revenue below auto-action threshold",
            "at_risk_revenue": round(at_risk_revenue, 2),
            "minimum_revenue_for_auto_action": MIN_REVENUE_FOR_AUTO_ACTION
        })
        return {
            "status": "escalated",
            "reason": "low_revenue",
            "at_risk_revenue": at_risk_revenue
        }

    # 3. High-value incidents require explicit human approval. The LLM cannot
    # satisfy this gate; the approval must be supplied to the API.
    if at_risk_revenue > MAX_REVENUE_FOR_AUTO_APPROVE and not action_data.get("human_approved", False):
        incident.state = "AWAITING_HUMAN_APPROVAL"
        db.commit()
        log_audit(db, incident.id, "system", "HUMAN_APPROVAL_REQUIRED", {
            "reason": "At-risk revenue exceeds auto-approval limit",
            "at_risk_revenue": round(at_risk_revenue, 2),
            "maximum_revenue_for_auto_approve": MAX_REVENUE_FOR_AUTO_APPROVE
        })
        return {
            "status": "pending_human_approval",
            "reason": "high_revenue",
            "at_risk_revenue": at_risk_revenue
        }

    # 4. Action selection and backend domain validation.
    action_type = action_data.get("recommended_action")
    if action_type not in EFFECT_SIZES:
        raise ValueError("Invalid action type proposed")

    expected_action = ALLOWED_ACTIONS_BY_HYPOTHESIS.get(diagnosis.hypothesis)
    if expected_action is not None and action_type != expected_action:
        raise ValueError(
            f"Action '{action_type}' is incompatible with diagnosis '{diagnosis.hypothesis}'. "
            f"Expected '{expected_action}'."
        )

    recovery_action = RecoveryAction(
        id=f"act_{uuid.uuid4().hex[:12]}",
        incident_id=incident.id,
        action_type=action_type,
        selected_by=action_data.get("selected_by", "system"),
        reasoning_text=action_data.get("reasoning", "")
    )
    db.add(recovery_action)
    db.commit()
    db.refresh(recovery_action)

    log_audit(db, incident.id, action_data.get("selected_by", "system"), "ACTION_SELECTED", {
        "action": action_type,
        "at_risk_revenue": round(at_risk_revenue, 2),
        "human_approved": bool(action_data.get("human_approved", False))
    })

    incident.state = "ACTION_SELECTED"
    db.commit()

    # 5. Simulate bounded recovery. Retry-producing actions may never push a
    # transaction above the hard limit of 2 simulated retries.
    failures = [
        t for t in _incident_transactions(db, incident)
        if not t.success and t.retry_count < MAX_SIMULATED_RETRIES_PER_TRANSACTION
    ]

    total_failed_txns = len(failures)
    effect_size = EFFECT_SIZES[action_type]
    transactions_to_flip = int(total_failed_txns * effect_size)

    recovered_revenue = 0.0
    for i in range(transactions_to_flip):
        failures[i].success = True
        if action_type in {"REROUTE", "ADJUST_RETRY_TIMING"}:
            failures[i].retry_count = min(
                failures[i].retry_count + 1,
                MAX_SIMULATED_RETRIES_PER_TRANSACTION
            )
        recovered_revenue += failures[i].amount

    db.commit()
    incident.state = "ACTION_APPLIED"
    db.commit()

    # 6. Re-measure outcomes
    all_segment_txns = _incident_transactions(db, incident)
    post_successes = sum(1 for t in all_segment_txns if t.success)
    post_success_rate = (post_successes / len(all_segment_txns) * 100) if all_segment_txns else 0.0
    improvement = post_success_rate - incident.incident_success_rate

    result_state = "RESOLVED" if improvement >= 5.0 else "ESCALATED_INSUFFICIENT_RECOVERY"
    incident.state = result_state
    db.commit()

    outcome = Outcome(
        id=f"out_{uuid.uuid4().hex[:12]}",
        recovery_action_id=recovery_action.id,
        pre_success_rate=incident.incident_success_rate,
        post_success_rate=post_success_rate,
        recovered_revenue=recovered_revenue,
        transactions_flipped=transactions_to_flip,
        result=result_state
    )
    db.add(outcome)
    db.commit()

    log_audit(db, incident.id, "system", "OUTCOME_MEASURED", {
        "improvement_pp": round(improvement, 2),
        "recovered_revenue": round(recovered_revenue, 2),
        "result": result_state,
        "at_risk_revenue": round(at_risk_revenue, 2),
        "transactions_flipped": transactions_to_flip
    })

    return {
        "status": result_state,
        "recovered_revenue": recovered_revenue,
        "improvement": improvement,
        "at_risk_revenue": at_risk_revenue
    }
