"""DeclineDoctor Recovery Simulator Engine.

Executes controlled recovery simulations using the identical mathematical model,
retry cap boundaries, and policy safety checks as the production recovery engine.
"""

from typing import Dict, Any
from .recovery_agent import EFFECT_SIZES
from .policy import (
    MAX_SIMULATED_RETRIES,
    CONFIDENCE_THRESHOLD,
    MIN_REVENUE_FOR_AUTO_ACTION,
    MAX_REVENUE_FOR_AUTO_APPROVE,
    is_action_compatible,
    check_recovery_safety,
    ACTION_HYPOTHESIS_MAP,
)


def run_recovery_simulation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a controlled sandbox simulation using genuine recovery mathematics."""
    issuer = params.get("segment_issuer", "Bank X")
    payment_method = params.get("segment_payment_method", "card")
    tx_count = max(1, int(params.get("transaction_count", 500)))
    failure_rate = max(0.0, min(1.0, float(params.get("failure_rate", 0.40))))
    avg_amount = max(1.0, float(params.get("average_amount", 1850.0)))
    hypothesis = params.get("diagnosis_hypothesis", "ROUTING_CONNECTIVITY_ISSUE")
    action = params.get("action", "REROUTE")
    confidence = float(params.get("confidence", 0.85))
    user_role = params.get("user_role", "OPERATOR")
    human_approved = bool(params.get("human_approved", False))

    # Calculate baseline metrics
    total_failures = int(round(tx_count * failure_rate))
    total_successes = tx_count - total_failures
    pre_success_rate = (total_successes / tx_count) * 100.0
    at_risk_revenue = total_failures * avg_amount

    # Safety evaluation via policy module
    safety_check = check_recovery_safety(
        incident_state="DIAGNOSED",
        confidence=confidence,
        at_risk_revenue=at_risk_revenue,
        hypothesis=hypothesis,
        action=action,
        human_approved=human_approved,
        user_role=user_role,
    )

    # Recovery mathematics (identical to recovery_agent.py)
    compatible = is_action_compatible(hypothesis, action)
    effect_size = EFFECT_SIZES.get(action, 0.0)

    # In a fresh batch, all failures have retry_count 0 (< MAX_SIMULATED_RETRIES)
    eligible_failures = total_failures
    transactions_flipped = int(eligible_failures * effect_size)
    recovered_revenue = transactions_flipped * avg_amount

    post_successes = total_successes + transactions_flipped
    post_success_rate = (post_successes / tx_count) * 100.0
    improvement_pp = post_success_rate - pre_success_rate

    resolved = improvement_pp >= 5.0 and compatible and safety_check["status"] == "SAFE_TO_EXECUTE"

    return {
        "parameters": {
            "issuer": issuer,
            "payment_method": payment_method,
            "transaction_count": tx_count,
            "failure_rate": failure_rate,
            "average_amount": avg_amount,
            "diagnosis_hypothesis": hypothesis,
            "action": action,
            "confidence": confidence,
            "human_approved": human_approved,
        },
        "pre_metrics": {
            "total_transactions": tx_count,
            "total_failures": total_failures,
            "total_successes": total_successes,
            "pre_success_rate": round(pre_success_rate, 2),
            "at_risk_revenue": round(at_risk_revenue, 2),
        },
        "post_metrics": {
            "transactions_flipped": transactions_flipped,
            "recovered_revenue": round(recovered_revenue, 2),
            "post_success_rate": round(post_success_rate, 2),
            "improvement_pp": round(improvement_pp, 2),
            "effect_size": effect_size,
            "retry_cap_applied": MAX_SIMULATED_RETRIES,
        },
        "safety_evaluation": safety_check,
        "is_compatible": compatible,
        "expected_action": ACTION_HYPOTHESIS_MAP.get(hypothesis, "SUPPRESS_RETRIES"),
        "projected_outcome": "RESOLVED" if resolved else ("BLOCKED" if safety_check["status"] != "SAFE_TO_EXECUTE" else "INSUFFICIENT_RECOVERY"),
    }
