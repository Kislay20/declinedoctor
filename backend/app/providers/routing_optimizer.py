"""Multi-Provider Routing Optimizer & Intelligence Layer for DeclineDoctor.

Provides realistic multi-provider profiling, multi-dimensional scoring, and optimal target
gateway recommendation for the REROUTE recovery action in simulation/test mode.
Strictly simulation-only: LIVE_CALLS_ENABLED remains False at all times.
"""

from typing import Dict, Any, List, Optional

LIVE_CALLS_ENABLED: bool = False

# Realistic Multi-Gateway Provider Profiles with Segment & BIN Specializations
SIMULATED_PROVIDER_PROFILES = {
    "Provider A": {
        "id": "provider_a",
        "name": "Provider A (Primary Low-Latency Route)",
        "tier": "Tier-1 Direct Bank Switch",
        "base_success_rate": 96.2,
        "base_latency_ms": 78,
        "cost_pct": 1.85,
        "availability_pct": 99.98,
        "error_rate_pct": 0.4,
        "decline_rate_pct": 3.4,
        "timeout_rate_pct": 0.2,
        "health": "OPTIMAL",
        "specialties": {
            "issuers": {"Bank X": 97.4, "HDFC": 96.8, "ICICI": 95.1, "SBI": 92.0},
            "payment_methods": {"card": 96.5, "netbanking": 95.8, "upi": 96.0},
            "bins": {"452114": 97.2, "524188": 96.9, "401200": 91.5, "411111": 95.5, "476543": 96.8},
        },
        "description": "Lowest overall latency with direct Visa/Mastercard processing pipes.",
    },
    "Provider B": {
        "id": "provider_b",
        "name": "Provider B (Card Network Direct / Fallback)",
        "tier": "Card Network Direct Hub",
        "base_success_rate": 93.8,
        "base_latency_ms": 115,
        "cost_pct": 1.95,
        "availability_pct": 99.95,
        "error_rate_pct": 0.8,
        "decline_rate_pct": 5.4,
        "timeout_rate_pct": 0.5,
        "health": "HEALTHY",
        "specialties": {
            "issuers": {"Bank X": 94.2, "HDFC": 95.0, "ICICI": 96.8, "SBI": 94.5},
            "payment_methods": {"card": 95.5, "netbanking": 91.0, "upi": 92.5},
            "bins": {"452114": 94.8, "524188": 95.2, "401200": 94.0, "411111": 97.0, "476543": 97.2},
        },
        "description": "High resilience routing with optimal performance on ICICI and SBI card tiers.",
    },
    "Provider C": {
        "id": "provider_c",
        "name": "Provider C (Global High-Throughput Edge)",
        "tier": "Edge Clearing Network",
        "base_success_rate": 91.5,
        "base_latency_ms": 142,
        "cost_pct": 2.10,
        "availability_pct": 99.90,
        "error_rate_pct": 1.2,
        "decline_rate_pct": 7.3,
        "timeout_rate_pct": 0.8,
        "health": "DEGRADED_FAILOVER",
        "specialties": {
            "issuers": {"Bank X": 90.5, "HDFC": 92.0, "ICICI": 93.0, "SBI": 90.0},
            "payment_methods": {"card": 91.8, "netbanking": 89.5, "upi": 93.5},
            "bins": {"452114": 91.0, "524188": 92.5, "401200": 89.5, "411111": 92.8, "476543": 92.5},
        },
        "description": "Secondary failover clearing path when primary domestic routes suffer outages.",
    },
    "Razorpay Smart Router": {
        "id": "razorpay_smart_router",
        "name": "Razorpay Smart Router (Adaptive Aggregator Adapter)",
        "tier": "Dynamic Multi-Terminal Aggregator",
        "base_success_rate": 95.5,
        "base_latency_ms": 88,
        "cost_pct": 1.90,
        "availability_pct": 99.97,
        "error_rate_pct": 0.5,
        "decline_rate_pct": 4.0,
        "timeout_rate_pct": 0.3,
        "health": "OPTIMAL",
        "specialties": {
            "issuers": {"Bank X": 96.5, "HDFC": 96.2, "ICICI": 95.8, "SBI": 93.8},
            "payment_methods": {"card": 96.0, "netbanking": 94.5, "upi": 97.5},
            "bins": {"452114": 96.5, "524188": 96.0, "401200": 93.5, "411111": 96.2, "476543": 96.5},
        },
        "description": "ML-driven dynamic load distribution across verified acquiring bank terminals.",
    },
}


def score_provider_route(
    provider_key: str,
    issuer: str = "Bank X",
    payment_method: str = "card",
    bin_number: Optional[str] = None,
    decline_reason: Optional[str] = None,
    current_degraded_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Score a single provider route for a specific transaction segment and context."""
    profile = SIMULATED_PROVIDER_PROFILES.get(provider_key)
    if not profile:
        raise ValueError(f"Unknown provider: {provider_key}")

    # Baseline success probability
    spec = profile["specialties"]
    issuer_spec = spec["issuers"].get(issuer, profile["base_success_rate"])
    method_spec = spec["payment_methods"].get(payment_method, profile["base_success_rate"])
    bin_spec = spec["bins"].get(bin_number, profile["base_success_rate"]) if bin_number else profile["base_success_rate"]

    # Blended expected success rate
    if bin_number and bin_number in spec["bins"]:
        expected_success = (0.40 * bin_spec) + (0.35 * issuer_spec) + (0.25 * method_spec)
    else:
        expected_success = (0.60 * issuer_spec) + (0.40 * method_spec)

    expected_success = round(min(expected_success, 99.5), 1)

    # Health & Availability score (0 - 100)
    health_multipliers = {"OPTIMAL": 1.0, "HEALTHY": 0.95, "DEGRADED_FAILOVER": 0.80}
    health_factor = health_multipliers.get(profile["health"], 0.90)

    # Latency penalty: 100 at 50ms, decreases as latency rises
    latency_score = max(0.0, min(100.0, 110.0 - (profile["base_latency_ms"] * 0.4)))

    # Cost score: lower cost gets higher score (1.8% -> ~95, 2.2% -> ~75)
    cost_score = max(0.0, min(100.0, 150.0 - (profile["cost_pct"] * 30.0)))

    # Decline reason compatibility bonus
    decline_bonus = 0.0
    if decline_reason and "timeout" in decline_reason.lower():
        # Providers with lower timeout rate get high priority
        if profile["timeout_rate_pct"] <= 0.3:
            decline_bonus = 4.0
    elif decline_reason and "processor" in decline_reason.lower():
        if profile["base_success_rate"] >= 95.0:
            decline_bonus = 3.5

    # Penalize if this provider is the currently degraded provider
    degradation_penalty = 0.0
    if current_degraded_provider and (current_degraded_provider.lower() in provider_key.lower()):
        degradation_penalty = 25.0

    # Composite weighted score (0 - 100)
    # Success rate: 45%, Latency: 25%, Health/Availability: 15%, Cost: 15%
    raw_score = (
        (expected_success * 0.45)
        + (latency_score * 0.25)
        + (profile["availability_pct"] * 0.15 * health_factor)
        + (cost_score * 0.15)
        + decline_bonus
        - degradation_penalty
    )
    final_score = round(max(5.0, min(99.9, raw_score)), 1)

    return {
        "provider": provider_key,
        "name": profile["name"],
        "tier": profile["tier"],
        "composite_score": final_score,
        "expected_success_rate": expected_success,
        "latency_ms": profile["base_latency_ms"],
        "cost_pct": profile["cost_pct"],
        "availability_pct": profile["availability_pct"],
        "health": "DEGRADED" if bool(degradation_penalty > 0) else profile["health"],
        "is_currently_degraded": bool(degradation_penalty > 0),
        "description": profile["description"],
    }


def optimize_provider_routing(
    issuer: str = "Bank X",
    payment_method: str = "card",
    bin_number: Optional[str] = None,
    decline_reason: Optional[str] = "processor_declined",
    current_degraded_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate all simulated providers and return optimal routing decision."""
    scored_providers = []
    for key in SIMULATED_PROVIDER_PROFILES:
        scored = score_provider_route(
            provider_key=key,
            issuer=issuer,
            payment_method=payment_method,
            bin_number=bin_number,
            decline_reason=decline_reason,
            current_degraded_provider=current_degraded_provider,
        )
        scored_providers.append(scored)

    # Rank providers descending by composite score
    scored_providers.sort(key=lambda p: p["composite_score"], reverse=True)
    winner = scored_providers[0]

    bin_context = f" and BIN {bin_number}" if bin_number else ""
    rationale = (
        f"{winner['provider']} has the strongest expected success rate ({winner['expected_success_rate']}%) "
        f"and lowest operational latency ({winner['latency_ms']}ms) for {issuer} ({payment_method}{bin_context}) "
        f"while maintaining a competitive cost structure ({winner['cost_pct']}%)."
    )

    return {
        "recommended_provider": winner["provider"],
        "recommended_provider_name": winner["name"],
        "score": winner["composite_score"],
        "expected_success_rate": winner["expected_success_rate"],
        "expected_latency_ms": winner["latency_ms"],
        "expected_cost_pct": winner["cost_pct"],
        "target_gateway_routing": f"REROUTE -> {winner['provider']}",
        "reason": rationale,
        "ranked_providers": scored_providers,
        "segment_evaluated": {
            "issuer": issuer,
            "payment_method": payment_method,
            "bin": bin_number or "ALL_BINS",
            "decline_trigger": decline_reason,
        },
        "mode": "SIMULATION_OPTIMIZER (LIVE_CALLS_STRICTLY_DISABLED)",
        "live_calls_enabled": LIVE_CALLS_ENABLED,
    }
