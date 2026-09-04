def test_blocked_recovery_response_has_no_stale_outcome():
    result = {"status": "blocked", "reason": "terminal_incident", "state": "RESOLVED"}
    response = {
        "status": "blocked",
        "reason": result.get("reason"),
        "state": result.get("state"),
        "outcome": None
    }
    assert response["status"] == "blocked"
    assert response["reason"] == "terminal_incident"
    assert response["state"] == "RESOLVED"
    assert response["outcome"] is None
