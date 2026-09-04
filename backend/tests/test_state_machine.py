import pytest
from app.policy import (
    IncidentState,
    TERMINAL_STATES,
    validate_state_transition,
    VALID_TRANSITIONS,
)


def test_valid_forward_transitions():
    assert validate_state_transition("ANOMALY_DETECTED", "DIAGNOSED") is True
    assert validate_state_transition("DIAGNOSED", "ACTION_SELECTED") is True
    assert validate_state_transition("DIAGNOSED", "AWAITING_HUMAN_APPROVAL") is True
    assert validate_state_transition("AWAITING_HUMAN_APPROVAL", "ACTION_SELECTED") is True
    assert validate_state_transition("ACTION_SELECTED", "RESOLVED") is True
    assert validate_state_transition("ACTION_SELECTED", "ESCALATED_INSUFFICIENT_RECOVERY") is True
    assert validate_state_transition("RESOLVED", "ROLLED_BACK") is True


def test_invalid_transitions_rejected():
    # Cannot jump backwards from RESOLVED to DIAGNOSED
    assert validate_state_transition("RESOLVED", "DIAGNOSED") is False
    # Cannot jump from ANOMALY_DETECTED directly to RESOLVED
    assert validate_state_transition("ANOMALY_DETECTED", "RESOLVED") is False
    # Terminal escalation states cannot transition to ACTION_SELECTED
    assert validate_state_transition("ESCALATED_LOW_CONFIDENCE", "ACTION_SELECTED") is False
    assert validate_state_transition("ESCALATED_LOW_REVENUE", "ACTION_SELECTED") is False
    assert validate_state_transition("ESCALATED_INSUFFICIENT_RECOVERY", "ACTION_SELECTED") is False
    assert validate_state_transition("ROLLED_BACK", "RESOLVED") is False


def test_terminal_states_are_immutable():
    for state in ["ESCALATED_LOW_CONFIDENCE", "ESCALATED_LOW_REVENUE", "ESCALATED_INSUFFICIENT_RECOVERY", "ROLLED_BACK"]:
        assert state in TERMINAL_STATES
        # Outbound transitions should be empty
        assert len(VALID_TRANSITIONS.get(state, set())) == 0
