"""DeclineDoctor Payment Provider Health API.

Exposes endpoints for gateway provider health, sandbox status, and test transaction inspection.
"""

from fastapi import APIRouter, Query
from typing import Optional
from ..providers.factory import get_all_providers_health, get_payment_provider
from ..providers.routing_optimizer import optimize_provider_routing, SIMULATED_PROVIDER_PROFILES

router = APIRouter(prefix="/api/providers", tags=["Providers"])


@router.get("/health")
def get_providers_health():
    """Retrieve operational telemetry and sandbox modes for all payment providers."""
    return get_all_providers_health()


@router.get("/profiles")
def get_provider_profiles():
    """Retrieve all simulated provider profiles and operational metrics."""
    return SIMULATED_PROVIDER_PROFILES


@router.get("/routing/bins")
def get_routing_bins():
    """Retrieve authoritative BIN registry and associated issuer/tier metadata."""
    from ..bin_intelligence import BIN_REGISTRY
    result = []
    for bin_code, meta in BIN_REGISTRY.items():
        result.append({
            "bin": bin_code,
            "issuer": meta.get("issuer"),
            "card_network": meta.get("card_network"),
            "card_tier": meta.get("card_tier"),
            "category": meta.get("category"),
            "label": f"{bin_code} ({meta.get('issuer')} {meta.get('card_network')} {meta.get('card_tier')})",
        })
    return result


@router.get("/routing/recommendation")
def get_routing_recommendation(
    issuer: str = Query(default="Bank X"),
    payment_method: str = Query(default="card"),
    bin: Optional[str] = Query(default=None),
    incident_id: Optional[str] = Query(default=None),
    decline_reason: Optional[str] = Query(default="processor_declined"),
    current_degraded_provider: Optional[str] = Query(default=None),
):
    """Retrieve real multi-provider routing recommendation and ranked scoring."""
    target_bin = bin
    if not target_bin and incident_id:
        from ..database import SessionLocal
        from ..bin_intelligence import analyze_bin_telemetry
        db = SessionLocal()
        try:
            bdata = analyze_bin_telemetry(db, incident_id=incident_id)
            target_bin = bdata.get("dominant_bin")
        finally:
            db.close()

    return optimize_provider_routing(
        issuer=issuer,
        payment_method=payment_method,
        bin_number=target_bin,
        decline_reason=decline_reason,
        current_degraded_provider=current_degraded_provider,
    )


@router.post("/routing/score")
def score_routing_payload(payload: dict = None):
    """Score routing decision from request payload."""
    payload = payload or {}
    return optimize_provider_routing(
        issuer=str(payload.get("issuer", "Bank X")),
        payment_method=str(payload.get("payment_method", "card")),
        bin_number=payload.get("bin") or payload.get("card_bin"),
        decline_reason=payload.get("decline_reason", "processor_declined"),
        current_degraded_provider=payload.get("current_degraded_provider"),
    )


@router.post("/test_payment")
def test_payment(payload: dict = None):
    """Execute a simulated payment probe in demo sandbox."""
    payload = payload or {}
    provider = get_payment_provider()
    return provider.create_test_payment(
        amount=float(payload.get("amount", 2500.0)),
        currency=str(payload.get("currency", "INR")),
        customer_id=str(payload.get("customer_id", "cust_sandbox_demo")),
        payment_method=str(payload.get("payment_method", "card")),
        issuer=str(payload.get("issuer", "Bank X")),
        simulate_failure_code=payload.get("simulate_failure_code"),
    )
