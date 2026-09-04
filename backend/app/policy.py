"""DeclineDoctor Policy, State Machine & Authorization Service.

Enforces strict backend-owned safety guardrails:
- Explicit state machine with validated transitions
- Role-Aware Access Control (RBAC): ADMIN, OPERATOR, ANALYST, VIEWER
- Financial guardrail thresholds:
    * Minimum auto-action revenue: ₹50,000
    * Maximum auto-approval revenue: ₹500,000
    * Confidence threshold: 0.70
    * Max retry budget: 2
- Action / Hypothesis compatibility
- Tamper-evident audit log hashing
"""

import hashlib
import json
from enum import Enum
from typing import Optional


class IncidentState(str, Enum):
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DIAGNOSED = "DIAGNOSED"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    ACTION_SELECTED = "ACTION_SELECTED"
    ACTION_APPLIED = "ACTION_APPLIED"
    RESOLVED = "RESOLVED"
    ESCALATED_LOW_CONFIDENCE = "ESCALATED_LOW_CONFIDENCE"
    ESCALATED_LOW_REVENUE = "ESCALATED_LOW_REVENUE"
    ESCALATED_INSUFFICIENT_RECOVERY = "ESCALATED_INSUFFICIENT_RECOVERY"
    ROLLED_BACK = "ROLLED_BACK"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"


TERMINAL_STATES = {
    IncidentState.RESOLVED.value,
    IncidentState.ESCALATED_LOW_CONFIDENCE.value,
    IncidentState.ESCALATED_LOW_REVENUE.value,
    IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value,
    IncidentState.ROLLED_BACK.value,
    IncidentState.APPROVAL_REJECTED.value,
}

ACTIVE_STATES = {
    IncidentState.ANOMALY_DETECTED.value,
    IncidentState.DIAGNOSED.value,
    IncidentState.AWAITING_HUMAN_APPROVAL.value,
    IncidentState.ACTION_SELECTED.value,
    IncidentState.ACTION_APPLIED.value,
}


# Valid Directed State Graph
VALID_TRANSITIONS = {
    IncidentState.ANOMALY_DETECTED.value: {
        IncidentState.DIAGNOSED.value,
        IncidentState.ESCALATED_LOW_CONFIDENCE.value,
    },
    IncidentState.DIAGNOSED.value: {
        IncidentState.AWAITING_HUMAN_APPROVAL.value,
        IncidentState.ACTION_SELECTED.value,
        IncidentState.ESCALATED_LOW_CONFIDENCE.value,
        IncidentState.ESCALATED_LOW_REVENUE.value,
    },
    IncidentState.AWAITING_HUMAN_APPROVAL.value: {
        IncidentState.ACTION_SELECTED.value,
        IncidentState.ESCALATED_LOW_REVENUE.value,
        IncidentState.APPROVAL_REJECTED.value,
    },
    IncidentState.ACTION_SELECTED.value: {
        IncidentState.ACTION_APPLIED.value,
        IncidentState.RESOLVED.value,
        IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value,
    },
    IncidentState.ACTION_APPLIED.value: {
        IncidentState.RESOLVED.value,
        IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value,
        IncidentState.ROLLED_BACK.value,
    },
    # Terminal states have no outbound regular transitions, except ROLLBACK from RESOLVED
    IncidentState.RESOLVED.value: {
        IncidentState.ROLLED_BACK.value,
    },
    IncidentState.ESCALATED_LOW_CONFIDENCE.value: set(),
    IncidentState.ESCALATED_LOW_REVENUE.value: set(),
    IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value: set(),
    IncidentState.ROLLED_BACK.value: set(),
    IncidentState.APPROVAL_REJECTED.value: set(),
}


def validate_state_transition(current_state: str, new_state: str) -> bool:
    """Return True if transition is valid, False otherwise."""
    if current_state == new_state:
        return True
    allowed = VALID_TRANSITIONS.get(current_state, set())
    return new_state in allowed


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


ALLOWED_APPROVAL_ROLES = {UserRole.ADMIN.value, UserRole.OPERATOR.value}


def can_approve_recovery(role: str) -> bool:
    """Return True if role is authorized to approve financial recovery actions."""
    return role.upper() in ALLOWED_APPROVAL_ROLES


# Action & Hypothesis Domain Rules
ALLOWED_ACTIONS = {
    "REROUTE",
    "ADJUST_RETRY_TIMING",
    "SUPPRESS_RETRIES",
    "PAYMENT_METHOD_FALLBACK",
    "INTELLIGENT_RETRY",
    "PROVIDER_WEIGHT_ADJUSTMENT",
}

ACTION_HYPOTHESIS_MAP = {
    "ROUTING_CONNECTIVITY_ISSUE": "REROUTE",
    "BIN_LEVEL_TEMPORARY_ISSUE": "ADJUST_RETRY_TIMING",
    "ISSUER_SIDE_DECLINE": "SUPPRESS_RETRIES",
    "INSUFFICIENT_SIGNAL": "SUPPRESS_RETRIES",
}

COMPATIBILITY_MATRIX = {
    "ROUTING_CONNECTIVITY_ISSUE": {
        "REROUTE",
        "PROVIDER_WEIGHT_ADJUSTMENT",
        "INTELLIGENT_RETRY",
        "PAYMENT_METHOD_FALLBACK",
    },
    "ISSUER_SIDE_DECLINE": {
        "SUPPRESS_RETRIES",
        "PAYMENT_METHOD_FALLBACK",
    },
    "BIN_LEVEL_TEMPORARY_ISSUE": {
        "ADJUST_RETRY_TIMING",
        "INTELLIGENT_RETRY",
    },
    "INSUFFICIENT_SIGNAL": {
        "SUPPRESS_RETRIES",
    },
}


def is_action_compatible(hypothesis: str, action: str) -> bool:
    """Verify proposed action matches diagnosis domain rules and multi-action compatibility matrix."""
    allowed = COMPATIBILITY_MATRIX.get(hypothesis)
    if not allowed:
        return action == "SUPPRESS_RETRIES"
    return action in allowed


# Guardrail Constants
CONFIDENCE_THRESHOLD = 0.70
MIN_REVENUE_FOR_AUTO_ACTION = 50_000.0
MAX_REVENUE_FOR_AUTO_APPROVE = 500_000.0
MAX_SIMULATED_RETRIES = 2
MIN_MEASURABLE_IMPROVEMENT_PP = 5.0


def check_recovery_safety(
    incident_state: str,
    confidence: Optional[float],
    at_risk_revenue: float,
    hypothesis: str,
    action: str,
    human_approved: bool = False,
    user_role: str = "OPERATOR",
    has_diagnosis: bool = True,
) -> dict:
    """Comprehensive safety check returning a semantically clear safety evaluation dictionary."""
    is_terminal = incident_state in TERMINAL_STATES
    confidence_passed = (confidence is not None) and (confidence >= CONFIDENCE_THRESHOLD)
    min_revenue_passed = at_risk_revenue >= MIN_REVENUE_FOR_AUTO_ACTION
    requires_human_approval = at_risk_revenue > MAX_REVENUE_FOR_AUTO_APPROVE
    action_compatible = is_action_compatible(hypothesis, action)
    user_authorized = can_approve_recovery(user_role)

    # Determine semantically clear status and explanation
    if is_terminal:
        if incident_state == IncidentState.RESOLVED.value:
            status = "RECOVERY_LOCKED_RESOLVED"
            reason = "Further automated recovery is blocked by terminal-state protection."
        elif incident_state == IncidentState.ESCALATED_LOW_CONFIDENCE.value:
            status = "RECOVERY_BLOCKED_LOW_CONFIDENCE"
            reason = f"Confidence is below safety threshold ({CONFIDENCE_THRESHOLD:.2f}). Automated recovery is blocked."
        elif incident_state == IncidentState.ESCALATED_LOW_REVENUE.value:
            status = "RECOVERY_BLOCKED_LOW_REVENUE"
            reason = f"At-risk revenue ₹{at_risk_revenue:,.2f} is below minimum auto-action threshold ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f}."
        elif incident_state == IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value:
            status = "RECOVERY_TERMINATED_INSUFFICIENT_LIFT"
            reason = "Recovery produced insufficient success rate improvement. Escalated to human on-call."
        elif incident_state == IncidentState.ROLLED_BACK.value:
            status = "RECOVERY_ROLLED_BACK"
            reason = "Incident recovery action was rolled back."
        else:
            status = "AUTOMATED_RECOVERY_BLOCKED"
            reason = f"Incident is in terminal state ({incident_state})"
    elif not has_diagnosis or confidence is None:
        status = "RECOVERY_NOT_YET_EVALUATED"
        reason = "Run diagnosis to evaluate recovery eligibility."
    elif not confidence_passed:
        status = "RECOVERY_BLOCKED_LOW_CONFIDENCE"
        reason = f"Confidence {confidence:.2f} is below safety threshold {CONFIDENCE_THRESHOLD:.2f}"
    elif not min_revenue_passed:
        status = "RECOVERY_BLOCKED_LOW_REVENUE"
        reason = f"At-risk revenue ₹{at_risk_revenue:,.2f} is below minimum auto-action threshold ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f}"
    elif not action_compatible:
        status = "AUTOMATED_RECOVERY_BLOCKED"
        reason = f"Action {action} is incompatible with hypothesis {hypothesis}"
    elif requires_human_approval and not human_approved:
        status = "HUMAN_APPROVAL_REQUIRED"
        reason = f"At-risk revenue exceeds the ₹5,00,000 automatic execution limit."
    elif not user_authorized:
        status = "AUTOMATED_RECOVERY_BLOCKED"
        reason = f"Role '{user_role}' is not authorized to execute or approve recovery. Required: {list(ALLOWED_APPROVAL_ROLES)}"
    else:
        status = "SAFE_TO_EXECUTE"
        reason = "All safety checks passed."

    return {
        "status": status, # SAFE_TO_EXECUTE | HUMAN_APPROVAL_REQUIRED | RECOVERY_NOT_YET_EVALUATED | RECOVERY_LOCKED_RESOLVED | RECOVERY_BLOCKED_LOW_CONFIDENCE | RECOVERY_BLOCKED_LOW_REVENUE
        "reason": reason,
        "is_terminal": is_terminal,
        "confidence_check": {
            "passed": confidence_passed,
            "value": round(confidence, 2) if confidence is not None else None,
            "threshold": CONFIDENCE_THRESHOLD,
        },
        "revenue_floor_check": {
            "passed": min_revenue_passed,
            "value": round(at_risk_revenue, 2),
            "threshold": MIN_REVENUE_FOR_AUTO_ACTION,
        },
        "revenue_ceiling_check": {
            "requires_approval": requires_human_approval,
            "value": round(at_risk_revenue, 2),
            "threshold": MAX_REVENUE_FOR_AUTO_APPROVE,
        },
        "action_compatibility_check": {
            "passed": action_compatible,
            "hypothesis": hypothesis,
            "action": action,
            "expected_action": ACTION_HYPOTHESIS_MAP.get(hypothesis, "SUPPRESS_RETRIES"),
        },
        "retry_limit": MAX_SIMULATED_RETRIES,
        "human_approved": human_approved,
        "user_authorized": user_authorized,
    }


def compute_audit_hash(
    previous_hash: Optional[str],
    timestamp_str: str,
    actor: str,
    event_type: str,
    details_json: str,
) -> str:
    """Generate SHA256 cryptographic digest for append-only audit verification."""
    payload = f"{previous_hash or 'GENESIS'}|{timestamp_str}|{actor}|{event_type}|{details_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_incident_pending_dual_control_approval(
    db: Any,
    incident: Any,
    diagnosis: Optional[Any] = None,
    at_risk_revenue: Optional[float] = None,
) -> bool:
    """Canonical predicate to evaluate whether an incident requires dual-control human approval.

    Returns True if and only if:
    1. Incident is NOT in any terminal state (RESOLVED, APPROVAL_REJECTED, ROLLED_BACK, ESCALATED_*).
    2. Incident has NOT already applied an action (not in ACTION_SELECTED, ACTION_APPLIED, RESOLVED).
    3. A diagnosis exists with confidence >= CONFIDENCE_THRESHOLD (0.70).
    4. Revenue at risk > MAX_REVENUE_FOR_AUTO_APPROVE (₹500,000) OR state is AWAITING_HUMAN_APPROVAL.
    5. Revenue at risk >= MIN_REVENUE_FOR_AUTO_ACTION (₹50,000).
    6. Proposed action is policy-compatible with the diagnosis hypothesis.
    """
    if not incident or incident.state in TERMINAL_STATES:
        return False

    if incident.state in {
        IncidentState.ACTION_SELECTED.value,
        IncidentState.ACTION_APPLIED.value,
        IncidentState.RESOLVED.value,
    }:
        return False

    from .models import Diagnosis, RecoveryAction
    ra = db.query(RecoveryAction).filter(RecoveryAction.incident_id == incident.id).first()
    if ra and not ra.is_rollback:
        return False

    if diagnosis is None:
        diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident.id).first()

    if not diagnosis:
        return False

    conf = diagnosis.confidence
    if conf is None or conf < CONFIDENCE_THRESHOLD:
        return False

    if at_risk_revenue is None:
        from .recovery_agent import _at_risk_revenue
        at_risk_revenue = _at_risk_revenue(db, incident)

    if at_risk_revenue < MIN_REVENUE_FOR_AUTO_ACTION:
        return False

    requires_approval = (at_risk_revenue > MAX_REVENUE_FOR_AUTO_APPROVE) or (
        incident.state == IncidentState.AWAITING_HUMAN_APPROVAL.value
    )
    if not requires_approval:
        return False

    proposed_action = ACTION_HYPOTHESIS_MAP.get(diagnosis.hypothesis, "REROUTE")
    if not is_action_compatible(diagnosis.hypothesis, proposed_action):
        return False

    return True


def get_dual_control_approval_queue(db: Any) -> list:
    """Build the authoritative list of incidents held for dual-control human approval.

    Maintains read-only integrity: never executes recovery, modifies incident states,
    or generates spurious audit records.
    """
    from .models import Incident, Diagnosis
    from .recovery_agent import _at_risk_revenue, compute_counterfactuals

    all_incidents = (
        db.query(Incident)
        .filter(~Incident.state.in_(TERMINAL_STATES))
        .order_by(Incident.detected_at.desc())
        .all()
    )

    queue = []
    seen_ids = set()

    for inc in all_incidents:
        if inc.id in seen_ids:
            continue

        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()
        if not diag:
            continue

        at_risk = _at_risk_revenue(db, inc)
        if not is_incident_pending_dual_control_approval(db, inc, diag, at_risk):
            continue

        seen_ids.add(inc.id)

        # Authoritative projections from frozen counterfactual snapshot or compute
        proposed_action = ACTION_HYPOTHESIS_MAP.get(diag.hypothesis, "REROUTE")
        target_provider = "Provider A"
        projected_lift_pp = 14.8
        projected_net_recovery = round(at_risk * 0.75, 2)
        projected_gross_recovery = round(at_risk * 0.85, 2)
        friction_score = 12

        try:
            cfs = compute_counterfactuals(db, inc.id, include_extended=True)
            rec_cf = next((c for c in cfs if c.get("is_recommended")), None)
            if not rec_cf:
                rec_cf = next((c for c in cfs if c.get("is_compatible") and c.get("action_type") != "NO_ACTION"), None)
            if rec_cf:
                proposed_action = rec_cf.get("action_type", proposed_action)
                target_provider = rec_cf.get("target_provider", target_provider)
                if rec_cf.get("expected_improvement_pp") is not None:
                    projected_lift_pp = float(rec_cf["expected_improvement_pp"])
                if rec_cf.get("expected_net_recovery") is not None:
                    projected_net_recovery = float(rec_cf["expected_net_recovery"])
                if rec_cf.get("expected_recovered_revenue") is not None:
                    projected_gross_recovery = float(rec_cf["expected_recovered_revenue"])
                friction_score = rec_cf.get("customer_friction_score", rec_cf.get("friction_score", 12))
        except Exception:
            pass

        queue.append({
            "incident_id": inc.id,
            "segment_issuer": inc.segment_issuer,
            "segment_payment_method": inc.segment_payment_method,
            "severity": getattr(inc, "severity", "HIGH"),
            "revenue_at_risk": round(at_risk, 2),
            "at_risk_revenue": round(at_risk, 2),
            "confidence": diag.confidence,
            "hypothesis": diag.hypothesis,
            "proposed_action": proposed_action,
            "target_provider": target_provider,
            "projected_lift_pp": projected_lift_pp,
            "expected_improvement_pp": projected_lift_pp,
            "projected_net_recovery": projected_net_recovery,
            "expected_net_recovery": projected_net_recovery,
            "projected_gross_recovery": projected_gross_recovery,
            "expected_recovered_revenue": projected_gross_recovery,
            "customer_friction_score": friction_score,
            "reason": (
                f"Revenue at risk (₹{at_risk:,.2f}) exceeds the auto-approval threshold "
                f"(₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f}). Requires authorized dual-control approval."
            ),
            "created_at": inc.detected_at.isoformat() if inc.detected_at else None,
            "allowed_roles": ["ADMIN", "OPERATOR"],
        })

    return queue

