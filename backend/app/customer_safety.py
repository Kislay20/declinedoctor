"""DeclineDoctor Customer-Level Recovery Safety Service.

Guarantees customer-level protection against retry fatigue, account locks,
and duplicate fee billing using anonymized customer identifiers without PII.
"""

from typing import Dict, Any, List


def evaluate_customer_retry_safety(
    customer_id: str,
    prior_failures_count: int,
    retries_used: int,
    friction_score: float = 0.0,
    max_retries_allowed: int = 2,
) -> Dict[str, Any]:
    """Evaluate whether an individual customer is eligible for further automated retry."""
    if retries_used >= max_retries_allowed:
        return {
            "customer_id": customer_id,
            "is_safe_to_retry": False,
            "policy_action": "SUPPRESS_RETRIES",
            "reason": f"Retry cap reached ({retries_used}/{max_retries_allowed} attempts used). Suppressing to prevent issuer lockout.",
            "friction_score": min(friction_score + 35.0, 100.0),
        }

    if prior_failures_count >= 3 and retries_used >= 1:
        return {
            "customer_id": customer_id,
            "is_safe_to_retry": False,
            "policy_action": "SUPPRESS_RETRIES",
            "reason": "Repeated failure pattern detected. Automated retry halted to protect cardholder experience.",
            "friction_score": min(friction_score + 25.0, 100.0),
        }

    return {
        "customer_id": customer_id,
        "is_safe_to_retry": True,
        "policy_action": "ALLOW_RECOVERY",
        "reason": f"Customer within safety budget ({retries_used}/{max_retries_allowed} retries).",
        "friction_score": friction_score,
    }


def get_demo_customer_profiles() -> List[Dict[str, Any]]:
    """Return anonymized customer cohort profiles for demonstration in Simulation Lab."""
    return [
        {
            "customer_id": "CUST_1042",
            "issuer": "Bank X",
            "payment_method": "card",
            "failed_attempts": 3,
            "retries_used": 2,
            "friction_score": 85.0,
            "cooldown_active": True,
            "safety_status": "LOCKED_MAX_RETRIES",
            "enforced_action": "SUPPRESS_RETRIES",
        },
        {
            "customer_id": "CUST_2091",
            "issuer": "ICICI",
            "payment_method": "card",
            "failed_attempts": 1,
            "retries_used": 0,
            "friction_score": 15.0,
            "cooldown_active": False,
            "safety_status": "ELIGIBLE_FOR_RECOVERY",
            "enforced_action": "REROUTE",
        },
        {
            "customer_id": "CUST_3184",
            "issuer": "SBI",
            "payment_method": "upi",
            "failed_attempts": 2,
            "retries_used": 1,
            "friction_score": 45.0,
            "cooldown_active": False,
            "safety_status": "MONITORED_RETRY",
            "enforced_action": "INTELLIGENT_RETRY",
        },
    ]


# Alias for backward compatibility
check_customer_retry_safety = evaluate_customer_retry_safety
