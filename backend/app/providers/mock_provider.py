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
