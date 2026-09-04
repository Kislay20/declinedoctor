"""Deterministic Mock Payment Provider for DeclineDoctor Buildathon Demo."""

from typing import Dict, Any
from .base import PaymentProvider


class MockPaymentProvider(PaymentProvider):
    """Deterministic mock provider simulating multi-gateway routing and backoff policies."""

    @property
    def provider_name(self) -> str:
        return "MockPaymentProvider (Demo Mode)"

    def reroute_traffic(self, segment: str, target_gateway: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "action": "REROUTE",
            "segment": segment,
            "target_gateway": target_gateway,
            "rule_id": f"rule_reroute_{segment.replace(' ', '_').lower()}",
            "simulated_latency_ms": 42,
        }

    def adjust_retry_timing(self, segment: str, backoff_seconds: int, max_retries: int) -> Dict[str, Any]:
        return {
            "status": "success",
            "action": "ADJUST_RETRY_TIMING",
            "segment": segment,
            "backoff_seconds": backoff_seconds,
            "max_retries": max_retries,
            "rule_id": f"rule_retry_{segment.replace(' ', '_').lower()}",
        }

    def suppress_retries(self, segment: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "action": "SUPPRESS_RETRIES",
            "segment": segment,
            "rule_id": f"rule_suppress_{segment.replace(' ', '_').lower()}",
        }

    def check_gateway_health(self, gateway_id: str) -> Dict[str, Any]:
        if gateway_id == "Router_Beta":
            return {"gateway": gateway_id, "healthy": True, "success_rate": 96.5, "latency_ms": 115}
        return {"gateway": gateway_id, "healthy": False, "success_rate": 58.2, "latency_ms": 450}

    def rollback_reroute(self, segment: str, original_gateway: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "action": "ROLLBACK",
            "segment": segment,
            "restored_gateway": original_gateway,
            "message": f"Traffic for {segment} successfully reverted to {original_gateway}",
        }

    def create_test_payment(
        self,
        amount: float,
        currency: str = "INR",
        customer_id: str = "cust_test",
        payment_method: str = "card",
        issuer: str = "Bank X",
        simulate_failure_code: str = None,
    ) -> Dict[str, Any]:
        is_success = simulate_failure_code is None
        payment_id = f"pay_mock_{abs(hash((amount, customer_id, payment_method))) % 1000000:06d}"
        return {
            "id": payment_id,
            "amount": amount,
            "currency": currency,
            "status": "captured" if is_success else "failed",
            "method": payment_method,
            "issuer": issuer,
            "customer_id": customer_id,
            "error_code": simulate_failure_code,
            "error_description": "Routing gateway rejected the BIN path" if simulate_failure_code else None,
            "provider": "MockPaymentProvider",
            "mode": "DEMO_SANDBOX",
            "is_live_transaction": False,
            "simulated_latency_ms": 42,
        }

    def inspect_payment(self, payment_id: str) -> Dict[str, Any]:
        return {
            "id": payment_id,
            "status": "captured",
            "amount": 1500.0,
            "currency": "INR",
            "provider": "MockPaymentProvider",
            "retry_count": 0,
            "routing_partner": "Router_Beta",
            "mode": "DEMO_SANDBOX",
        }

    def get_provider_health(self) -> Dict[str, Any]:
        from datetime import datetime
        return {
            "provider": "Mock Payment Provider",
            "status": "HEALTHY",
            "latency_ms": 42.0,
            "error_rate": 0.0,
            "recent_failure_rate": 0.0,
            "last_checked": datetime.now().isoformat(),
            "mode": "MOCK / DEMO MODE",
            "is_live": False,
            "is_live_allowed": False,
            "active_rules_count": 3,
        }
