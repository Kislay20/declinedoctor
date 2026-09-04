"""Payment Provider Abstraction Layer for DeclineDoctor.

Defines the contract for gateway routing, retry policy injection, and health status.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class PaymentProvider(ABC):
    """Abstract interface for payment gateway operations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the payment processor."""
        pass

    @abstractmethod
    def reroute_traffic(self, segment: str, target_gateway: str) -> Dict[str, Any]:
        """Direct payment requests for a given segment to an alternate gateway."""
        pass

    @abstractmethod
    def adjust_retry_timing(self, segment: str, backoff_seconds: int, max_retries: int) -> Dict[str, Any]:
        """Configure backoff retry intervals for a segment."""
        pass

    @abstractmethod
    def suppress_retries(self, segment: str) -> Dict[str, Any]:
        """Halt automatic retries for terminal issuer failures."""
        pass

    @abstractmethod
    def check_gateway_health(self, gateway_id: str) -> Dict[str, Any]:
        """Check live latency and availability of a gateway partner."""
        pass

    @abstractmethod
    def rollback_reroute(self, segment: str, original_gateway: str) -> Dict[str, Any]:
        """Revert traffic routing back to original gateway."""
        pass
