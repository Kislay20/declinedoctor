"""DeclineDoctor Payment Provider Health API.

Exposes endpoints for gateway provider health, sandbox status, and test transaction inspection.
"""

from fastapi import APIRouter
from ..providers.factory import get_all_providers_health, get_payment_provider

router = APIRouter(prefix="/api/providers", tags=["Providers"])


@router.get("/health")
def get_providers_health():
    """Retrieve operational telemetry and sandbox modes for all payment providers."""
    return get_all_providers_health()


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
