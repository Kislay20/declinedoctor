"""DeclineDoctor Recovery Economics Engine.

Provides transparent gross vs. net financial calculations, retry costs,
gateway fee overhead, and return-on-investment (ROI) telemetry.
All formulas are bounded and auditable.
"""

from typing import Dict, Any


# Configurable economic parameters (explicitly labeled demo assumptions)
DEFAULT_RETRY_UNIT_COST = 15.0      # Estimated gateway retry fee in INR
DEFAULT_GATEWAY_FEE_PCT = 0.012     # 1.2% merchant processing fee
DEFAULT_FRICTION_COST_PER_TX = 5.0  # Estimated friction/churn risk per retry attempt


def calculate_recovery_economics(
    gross_recovered: float,
    transactions_recovered: int,
    retry_unit_cost: float = DEFAULT_RETRY_UNIT_COST,
    gateway_fee_pct: float = DEFAULT_GATEWAY_FEE_PCT,
    friction_cost_per_tx: float = DEFAULT_FRICTION_COST_PER_TX,
) -> Dict[str, Any]:
    """Calculate net recovered revenue and ROI with complete transparent cost breakdown."""
    retry_cost = round(transactions_recovered * retry_unit_cost, 2)
    gateway_fee = round(gross_recovered * gateway_fee_pct, 2)
    friction_cost = round(transactions_recovered * friction_cost_per_tx, 2)
    total_operational_cost = round(retry_cost + gateway_fee + friction_cost, 2)

    net_recovered = round(max(gross_recovered - total_operational_cost, 0.0), 2)
    roi_pct = round((net_recovered / total_operational_cost * 100.0), 1) if total_operational_cost > 0 else 0.0

    return {
        "gross_recovered_revenue": round(gross_recovered, 2),
        "gross_recovered": round(gross_recovered, 2),
        "total_recovery_cost": total_operational_cost,
        "recovery_cost": total_operational_cost,
        "net_recovered_revenue": net_recovered,
        "net_recovered": net_recovered,
        "roi_pct": roi_pct,
        "disclaimer": "SAFE SIMULATION ECONOMICS: Cost assumptions calibrated for enterprise gateway interchange in India.",
        "cost_breakdown": {
            "retry_fees": retry_cost,
            "gateway_processing_fees": gateway_fee,
            "processor_routing_cost": gateway_fee,
            "customer_friction_cost": friction_cost,
        },
        "assumptions": {
            "retry_unit_cost_inr": retry_unit_cost,
            "gateway_fee_pct": round(gateway_fee_pct * 100, 2),
            "friction_cost_per_tx_inr": friction_cost_per_tx,
            "model_type": "DETERMINISTIC_COST_BENEFIT_V2",
            "disclaimer": "Cost assumptions calibrated for enterprise gateway interchange in India.",
        },
    }
