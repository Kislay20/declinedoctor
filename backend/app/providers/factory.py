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
