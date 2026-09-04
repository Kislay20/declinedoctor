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
