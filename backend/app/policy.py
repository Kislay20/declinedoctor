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


TERMINAL_STATES = {
    IncidentState.RESOLVED.value,
    IncidentState.ESCALATED_LOW_CONFIDENCE.value,
    IncidentState.ESCALATED_LOW_REVENUE.value,
    IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value,
    IncidentState.ROLLED_BACK.value,
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
ALLOWED_ACTIONS = {"REROUTE", "ADJUST_RETRY_TIMING", "SUPPRESS_RETRIES"}

ACTION_HYPOTHESIS_MAP = {
    "ROUTING_CONNECTIVITY_ISSUE": "REROUTE",
    "BIN_LEVEL_TEMPORARY_ISSUE": "ADJUST_RETRY_TIMING",
    "ISSUER_SIDE_DECLINE": "SUPPRESS_RETRIES",
    "INSUFFICIENT_SIGNAL": "SUPPRESS_RETRIES",
}


def is_action_compatible(hypothesis: str, action: str) -> bool:
    """Verify proposed action matches diagnosis domain rules."""
    expected = ACTION_HYPOTHESIS_MAP.get(hypothesis)
    if not expected:
        return action == "SUPPRESS_RETRIES"
    return action == expected


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
