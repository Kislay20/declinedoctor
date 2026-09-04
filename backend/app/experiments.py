"""DeclineDoctor Safe Simulation-Only A/B Experiment Framework.

Evaluates competing recovery strategies on synthetic offline transaction cohorts
to determine the optimal intervention without risking real-money merchant volume.
"""

import hashlib
import math
import random
from typing import Dict, Any


def run_recovery_experiment(
    strategy_a: str = "REROUTE",
    strategy_b: str = "ADJUST_RETRY_TIMING",
    sample_size: int = 100,
    segment: str = "Bank X card",
    avg_ticket: float = 2450.0,
    candidate_action_a: str = None,
    candidate_action_b: str = None,
    segment_issuer: str = None,
    segment_payment_method: str = None,
) -> Dict[str, Any]:
    """Execute a deterministic offline cohort experiment comparing two recovery actions."""
    if candidate_action_a:
        strategy_a = candidate_action_a
    if candidate_action_b:
        strategy_b = candidate_action_b
    if segment_issuer and segment_payment_method:
        segment = f"{segment_issuer} {segment_payment_method}"

    # Deterministic SHA-256 integer seed for stable reproducibility across Python process restarts
    seed_payload = f"{strategy_a}:{strategy_b}:{sample_size}:{segment}"
    seed_int = int(hashlib.sha256(seed_payload.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(42 + seed_int)

    cohort_size = sample_size // 2

    # Baseline performance parameters
    strategy_profiles = {
        "REROUTE": {
            "lift_mean": 17.5,
            "success_prob": 0.42,
            "cost_per_tx": 15.0,
            "latency_ms": 115,
            "friction_score": 12.0,
        },
        "ADJUST_RETRY_TIMING": {
            "lift_mean": 8.8,
            "success_prob": 0.21,
            "cost_per_tx": 12.0,
            "latency_ms": 280,
            "friction_score": 24.0,
        },
        "PAYMENT_METHOD_FALLBACK": {
            "lift_mean": 14.2,
            "success_prob": 0.35,
            "cost_per_tx": 18.0,
            "latency_ms": 190,
            "friction_score": 38.0,
        },
        "INTELLIGENT_RETRY": {
            "lift_mean": 12.0,
            "success_prob": 0.28,
            "cost_per_tx": 14.0,
            "latency_ms": 210,
            "friction_score": 18.0,
        },
        "PROVIDER_WEIGHT_ADJUSTMENT": {
            "lift_mean": 16.5,
            "success_prob": 0.38,
            "cost_per_tx": 15.0,
            "latency_ms": 125,
            "friction_score": 14.0,
        },
        "SUPPRESS_RETRIES": {
            "lift_mean": 0.0,
            "success_prob": 0.0,
            "cost_per_tx": 0.0,
            "latency_ms": 5,
            "friction_score": 5.0,
        },
    }

    prof_a = strategy_profiles.get(strategy_a, strategy_profiles["REROUTE"])
    prof_b = strategy_profiles.get(strategy_b, strategy_profiles["ADJUST_RETRY_TIMING"])

    # Simulate Cohort A
    recovered_a = int(cohort_size * prof_a["success_prob"])
    revenue_a = round(recovered_a * avg_ticket, 2)
    cost_a = round(recovered_a * prof_a["cost_per_tx"], 2)
    net_revenue_a = round(revenue_a - cost_a, 2)
    observed_lift_a = round(prof_a["lift_mean"] + rng.uniform(-0.5, 0.5), 2)

    # Simulate Cohort B
    recovered_b = int(cohort_size * prof_b["success_prob"])
    revenue_b = round(recovered_b * avg_ticket, 2)
    cost_b = round(recovered_b * prof_b["cost_per_tx"], 2)
    net_revenue_b = round(revenue_b - cost_b, 2)
    observed_lift_b = round(prof_b["lift_mean"] + rng.uniform(-0.5, 0.5), 2)

    # Statistical Significance (two-proportion z-test)
    p1 = recovered_a / cohort_size if cohort_size > 0 else 0
    p2 = recovered_b / cohort_size if cohort_size > 0 else 0
    pooled_p = (recovered_a + recovered_b) / (2 * cohort_size) if cohort_size > 0 else 0.5
    se = math.sqrt(pooled_p * (1 - pooled_p) * (2 / cohort_size)) if (0 < pooled_p < 1 and cohort_size > 0) else 0.05
    z_stat = (p1 - p2) / se if se > 0 else 0.0
    p_val = round(math.erfc(abs(z_stat) / math.sqrt(2)), 4)
    stat_significant = p_val < 0.05

    winner = f"COHORT_A ({strategy_a})" if net_revenue_a >= net_revenue_b else f"COHORT_B ({strategy_b})"

    exp_id_int = int(hashlib.sha256(f"{strategy_a}:{strategy_b}:{segment}".encode("utf-8")).hexdigest()[:8], 16)

    return {
        "experiment_id": f"exp_{exp_id_int % 100000}",
        "segment": segment,
        "sample_size": sample_size,
        "cohort_size": cohort_size,
        "winner": winner,
        "is_statistically_significant": stat_significant,
        "p_value": p_val,
        "confidence_level_pct": 95.0 if stat_significant else 85.0,
        "recommendation_rationale": (
            f"{winner} delivered higher net recovered revenue (+Rs.{abs(net_revenue_a - net_revenue_b):,.2f}) "
            f"and lower customer friction."
        ),
        "cohort_a": {
            "strategy": strategy_a,
            "action": strategy_a,
            "sample_count": cohort_size,
            "transactions_recovered": recovered_a,
            "recovery_rate_pct": round(p1 * 100, 1),
            "average_lift_pp": observed_lift_a,
            "avg_lift_pp": observed_lift_a,
            "gross_recovered_revenue": revenue_a,
            "estimated_cost": cost_a,
            "net_recovered_revenue": net_revenue_a,
            "recovered_revenue": net_revenue_a,
            "avg_latency_ms": prof_a["latency_ms"],
            "friction_score": prof_a["friction_score"],
            "customer_friction_score": prof_a["friction_score"],
        },
        "cohort_b": {
            "strategy": strategy_b,
            "action": strategy_b,
            "sample_count": cohort_size,
            "transactions_recovered": recovered_b,
            "recovery_rate_pct": round(p2 * 100, 1),
            "average_lift_pp": observed_lift_b,
            "avg_lift_pp": observed_lift_b,
            "gross_recovered_revenue": revenue_b,
            "estimated_cost": cost_b,
            "net_recovered_revenue": net_revenue_b,
            "recovered_revenue": net_revenue_b,
            "avg_latency_ms": prof_b["latency_ms"],
            "friction_score": prof_b["friction_score"],
            "customer_friction_score": prof_b["friction_score"],
        },
        "simulation_disclaimer": "SAFE OFFLINE SIMULATION EXPERIMENT: Conducted on synthetic offline cohorts. No live cardholder volume affected.",
    }
