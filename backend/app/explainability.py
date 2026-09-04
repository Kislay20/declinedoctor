"""DeclineDoctor Explainability Engine.

Produces evidence-grounded answers to key operational questions:
- Why did DeclineDoctor act?
- Why did DeclineDoctor not act?
- Why did DeclineDoctor stop?
- Why is human approval required?

All explanations are derived strictly from persisted database records,
including incidents, diagnoses, recovery actions, and audit logs.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Incident, Diagnosis, RecoveryAction, Outcome, AuditLog
from .recovery_agent import _at_risk_revenue
from .policy import (
    CONFIDENCE_THRESHOLD,
    MIN_REVENUE_FOR_AUTO_ACTION,
    MAX_REVENUE_FOR_AUTO_APPROVE,
    TERMINAL_STATES,
)


def get_incident_explanation(db: Session, incident_id: str) -> Dict[str, Any]:
    """Generate structured, evidence-based explainability report for an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident not found: {incident_id}")

    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident.id).first()
    action = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.incident_id == incident.id)
        .order_by(RecoveryAction.applied_at.desc())
        .first()
    )
    outcome = (
        db.query(Outcome)
        .filter(Outcome.recovery_action_id == action.id)
        .first()
        if action
        else None
    )

    at_risk = _at_risk_revenue(db, incident)
    conf = diagnosis.confidence if diagnosis else 0.0
    hyp = diagnosis.hypothesis if diagnosis else "UNKNOWN"
    drop_pp = incident.baseline_success_rate - incident.incident_success_rate

    # 1. Why did DeclineDoctor act?
    if action and not action.is_rollback:
        why_acted = (
            f"DeclineDoctor initiated recovery action '{action.action_type}' because a genuine "
            f"success-rate drop of {drop_pp:.1f} percentage points was detected "
            f"(baseline {incident.baseline_success_rate:.1f}% -> incident {incident.incident_success_rate:.1f}%) "
            f"in segment {incident.segment_issuer} {incident.segment_payment_method}. "
            f"Diagnostic confidence was {conf:.2f} (>= {CONFIDENCE_THRESHOLD:.2f}), and revenue at risk was "
            f"₹{at_risk:,.2f} (>= ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f}). "
            f"Action was selected by {action.selected_by} and validated by backend policy."
        )
    elif incident.state in {"AWAITING_HUMAN_APPROVAL"}:
        why_acted = (
            "DeclineDoctor has prepared an action proposal but has not yet acted pending required "
            "dual-control human approval for high-value financial exposure."
        )
    else:
        why_acted = (
            "DeclineDoctor has not taken automated recovery action for this incident. "
            "Interventions require all backend confidence, revenue, and compatibility criteria to be satisfied."
        )

    # 2. Why did DeclineDoctor not act?
    if incident.state == "ESCALATED_LOW_CONFIDENCE":
        why_not_acted = (
            f"Automated recovery was blocked because diagnostic confidence was {conf:.2f}, "
            f"which is below the mandatory safety threshold of {CONFIDENCE_THRESHOLD:.2f}. "
            f"Intervening under high diagnosis uncertainty risks routing transactions to incompatible "
            f"channels or creating false customer alerts."
        )
    elif incident.state == "ESCALATED_LOW_REVENUE":
        why_not_acted = (
            f"Automated recovery was blocked because at-risk revenue (₹{at_risk:,.2f}) is below "
            f"the minimum auto-action threshold of ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f}. "
            f"To prevent operational churn, incidents with low financial impact are routed for batch review."
        )
    elif incident.state == "AWAITING_HUMAN_APPROVAL":
        why_not_acted = (
            f"Automated recovery is currently held because at-risk revenue (₹{at_risk:,.2f}) "
            f"exceeds the automatic approval limit of ₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f}. "
            f"Execution is paused until an authorized OPERATOR or ADMIN approves."
        )
    elif action:
        why_not_acted = "Not applicable; safety checks passed and recovery was executed."
    else:
        why_not_acted = "Incident is awaiting diagnosis or pending evaluation against safety thresholds."

    # 3. Why did DeclineDoctor stop?
    if incident.state == "RESOLVED":
        improvement_txt = f" (improved by +{outcome.post_success_rate - outcome.pre_success_rate:.1f} pp)" if outcome else ""
        why_stopped = (
            f"DeclineDoctor reached terminal state RESOLVED{improvement_txt}. All eligible transactions "
            f"were evaluated within the bounded retry budget (maximum 2 retries per transaction) to prevent "
            f"gateway quota exhaustion."
        )
    elif incident.state == "ESCALATED_INSUFFICIENT_RECOVERY":
        improvement_val = (outcome.post_success_rate - outcome.pre_success_rate) if outcome else 0.0
        why_stopped = (
            f"Recovery was halted and escalated because measured improvement (+{improvement_val:.2f} pp) "
            f"did not meet the minimum efficacy threshold of 5.0 pp. DeclineDoctor prohibits secondary "
            f"unrelated retry attempts to protect the payment funnel from repeated failures."
        )
    elif incident.state in {"ESCALATED_LOW_CONFIDENCE", "ESCALATED_LOW_REVENUE"}:
        why_stopped = (
            f"Processing stopped at the safety gate ({incident.state}) before any transactions were modified."
        )
    elif incident.state == "ROLLED_BACK":
        why_stopped = (
            "Recovery intervention was rolled back by operator command. Flipped transaction states were "
            "reverted and the incident marked ROLLED_BACK."
        )
    else:
        why_stopped = f"Incident has not stopped; it is actively in state '{incident.state}'."

    # 4. Why is human approval required?
    if at_risk > MAX_REVENUE_FOR_AUTO_APPROVE:
        why_approval_required = (
            f"At-risk revenue is ₹{at_risk:,.2f}, which exceeds the automatic execution ceiling of "
            f"₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f}. Under DeclineDoctor Dual-Control Policy, any "
            f"intervention on exposure exceeding ₹500,000 must be reviewed and approved by an authorized "
            f"role (ADMIN or OPERATOR) to protect merchant cash flow."
        )
    else:
        why_approval_required = (
            f"Human approval is not required. The at-risk revenue of ₹{at_risk:,.2f} is within the "
            f"autonomous execution window (between ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f} and ₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f})."
        )

    return {
        "incident_id": incident.id,
        "state": incident.state,
        "at_risk_revenue": round(at_risk, 2),
        "confidence": round(conf, 2),
        "hypothesis": hyp,
        "questions": {
            "why_did_declinedoctor_act": why_acted,
            "why_did_declinedoctor_not_act": why_not_acted,
            "why_did_declinedoctor_stop": why_stopped,
            "why_is_human_approval_required": why_approval_required,
        },
    }
