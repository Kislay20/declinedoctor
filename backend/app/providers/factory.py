"""Payment Provider Factory for DeclineDoctor."""

import os
from .base import PaymentProvider
from .mock_provider import MockPaymentProvider
from .razorpay_provider import RazorpayPaymentProvider

_provider_instance = None


def get_payment_provider(provider_type: str = None) -> PaymentProvider:
    """Return configured payment provider instance (defaulting to MockPaymentProvider for demo)."""
    target_type = (provider_type or os.getenv("PAYMENT_PROVIDER", "mock")).lower()
    if target_type == "razorpay":
        return RazorpayPaymentProvider()
    return MockPaymentProvider()


def get_all_providers_health() -> dict:
    """Return live status and telemetry across both Mock and Razorpay providers."""
    mock = MockPaymentProvider()
    rzp = RazorpayPaymentProvider()
    return {
        "active_provider": os.getenv("PAYMENT_PROVIDER", "mock").lower(),
        "providers": [
            mock.get_provider_health(),
            rzp.get_provider_health(),
        ],
    }
