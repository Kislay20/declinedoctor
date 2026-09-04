from app.routes.incidents import RecoveryRequest
from pydantic import ValidationError
import pytest


def test_recovery_request_accepts_only_supported_action():
    req = RecoveryRequest(recommended_action="REROUTE")
    assert req.recommended_action == "REROUTE"


def test_recovery_request_rejects_invalid_action():
    with pytest.raises(ValidationError):
        RecoveryRequest(recommended_action="DO_ANYTHING")


def test_recovery_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RecoveryRequest(recommended_action="REROUTE", unexpected=True)


def test_recovery_request_accepts_authoritative_projection_fields():
    req = RecoveryRequest(
        recommended_action="REROUTE",
        target_provider="Provider A",
        projected_lift_pp=18.71,
        projected_gross_recovery=272925.82,
        projected_net_recovery=272490.82,
        human_approved=True,
        role="ADMIN",
    )
    assert req.recommended_action == "REROUTE"
    assert req.target_provider == "Provider A"
    assert req.projected_lift_pp == 18.71
    assert req.projected_gross_recovery == 272925.82
    assert req.projected_net_recovery == 272490.82

