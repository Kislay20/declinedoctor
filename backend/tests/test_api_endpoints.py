from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.detection import detect_anomalies
from app.models import Incident

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_dashboard_summary_endpoint():
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "global_success_rate" in data
    assert "active_incident_count" in data
    assert "revenue_at_risk" in data
    assert "total_recovered_revenue" in data
    assert "funnel" in data
    assert "approval_queue" in data


def test_evaluation_endpoint():
    res = client.get("/api/evaluation")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert data["dataset_size"] == 60


def test_observability_endpoint():
    res = client.get("/api/observability")
    assert res.status_code == 200
    data = res.json()
    assert "database" in data
    assert "audit_chain" in data
    assert "processing_metrics" in data


def test_segments_analytics_endpoint():
    res = client.get("/api/segments/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "segments" in data
    assert "filters" in data


def test_simulation_recovery_sandbox():
    payload = {
        "segment_issuer": "Bank X",
        "segment_payment_method": "card",
        "transaction_count": 200,
        "failure_rate": 0.35,
        "average_amount": 2000.0,
        "diagnosis_hypothesis": "ROUTING_CONNECTIVITY_ISSUE",
        "action": "REROUTE",
        "confidence": 0.85,
        "human_approved": False,
        "user_role": "OPERATOR",
    }
    res = client.post("/api/simulate/recovery", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["projected_outcome"] == "RESOLVED"
    assert data["post_metrics"]["transactions_flipped"] == int(200 * 0.35 * 0.42)


def test_stream_event_ingestion():
    payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 2500.0,
        "success": True,
    }
    res = client.post("/api/simulate/stream", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["lifecycle_stage"] == "COMPLETED_SUCCESS"


def test_stream_failed_event_pipeline_regression():
    # 1. Reset baseline demo data to ensure active Bank X anomaly exists
    reset_res = client.post("/api/simulate/inject")
    assert reset_res.status_code == 200

    # 2. Ingest failed processor_declined transaction with auto_execute=False
    payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 1500.0,
        "success": False,
        "decline_code": "processor_declined",
        "decline_reason": "Processor communication timeout",
        "auto_execute": False,
        "auto_recover": False,
        "user_role": "OPERATOR",
    }
    res = client.post("/api/simulate/stream", json=payload)

    # Must NOT be HTTP 500
    assert res.status_code == 200
    data = res.json()

    # Verify pipeline trace contains the expected processing stages
    assert data["transaction_id"] is not None
    assert data["success"] is False
    assert data["issuer"] == "Bank X"
    assert data["payment_method"] == "card"
    assert "incident_id" in data
    assert data["hypothesis"] == "ROUTING_CONNECTIVITY_ISSUE"
    assert data["confidence"] >= 0.70
    assert data["recommended_action"] == "REROUTE"
    assert "safety_check" in data
    assert data["safety_check"]["status"] in {"SAFE_TO_EXECUTE", "RECOVERY_LOCKED_RESOLVED"}

    # Verify auto_execute=False does NOT accidentally execute recovery
    assert data["lifecycle_stage"] != "RECOVERY_EXECUTED"
    assert "recovery_result" not in data
    assert data["lifecycle_stage"].startswith("POLICY_")


def test_stream_auto_execute_true_executes_recovery():
    # 1. Reset baseline demo data
    reset_res = client.post("/api/simulate/inject")
    assert reset_res.status_code == 200

    # 2. Ingest failed transaction with auto_execute=True on active safe Bank X incident
    payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 1500.0,
        "success": False,
        "decline_code": "processor_declined",
        "auto_execute": True,
        "user_role": "OPERATOR",
    }
    res = client.post("/api/simulate/stream", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["lifecycle_stage"] == "RECOVERY_EXECUTED"
    assert data["recovery_result"] is not None
    assert data["recovery_result"]["status"] == "RESOLVED"
    assert data["recovery_result"]["recovered_revenue"] > 0

    # 3. Ingest another transaction on the segment: policy guardrails prevent re-execution
    res2 = client.post("/api/simulate/stream", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["lifecycle_stage"] in {"POLICY_RECOVERY_LOCKED_RESOLVED", "POLICY_RECOVERY_BLOCKED_LOW_CONFIDENCE"}
    assert "recovery_result" not in data2
    assert data2["lifecycle_stage"] != "RECOVERY_EXECUTED"


def test_detection_idempotency_repeated_calls():
    # 1. Reset demo database to initial state
    reset_res = client.post("/api/simulate/inject")
    assert reset_res.status_code == 200

    # 2. Verify initial baseline has exactly 3 incidents
    db = SessionLocal()
    try:
        initial_incidents = db.query(Incident).all()
        assert len(initial_incidents) == 3
        initial_ids = {inc.id for inc in initial_incidents}

        # 3. Re-run detect_anomalies repeatedly (5 times)
        for _ in range(5):
            detected = detect_anomalies(db)
            assert len(detected) == 3

        # 4. Total incidents in DB must still be strictly 3 (no duplicate rows created)
        post_incidents = db.query(Incident).all()
        assert len(post_incidents) == 3
        post_ids = {inc.id for inc in post_incidents}
        assert initial_ids == post_ids

        # 5. Segment Explorer API must show exactly 1 incident per anomalous segment
        seg_res = client.get("/api/segments/analytics")
        assert seg_res.status_code == 200
        segments = seg_res.json()["segments"]
        for seg in segments:
            if seg["incidents"]:
                assert len(seg["incidents"]) == 1
    finally:
        db.close()


def test_failed_stream_event_followed_by_detection():
    # 1. Reset baseline demo data
    reset_res = client.post("/api/simulate/inject")
    assert reset_res.status_code == 200

    # 2. Record initial incident count and IDs
    db = SessionLocal()
    try:
        initial_incidents = db.query(Incident).all()
        assert len(initial_incidents) == 3
        initial_bank_x = db.query(Incident).filter(Incident.segment_issuer == "Bank X").first()
        initial_icici = db.query(Incident).filter(Incident.segment_issuer == "ICICI").first()
        initial_sbi = db.query(Incident).filter(Incident.segment_issuer == "SBI").first()
    finally:
        db.close()

    # 3. Emit a single failed stream event on Bank X
    stream_payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 1200.0,
        "success": False,
        "decline_code": "processor_declined",
        "auto_execute": False,
        "user_role": "OPERATOR",
    }
    stream_res = client.post("/api/simulate/stream", json=stream_payload)
    assert stream_res.status_code == 200

    # 4. Verify no duplicate incidents were created for Bank X, ICICI, or SBI
    db = SessionLocal()
    try:
        incidents_after_stream = db.query(Incident).all()
        assert len(incidents_after_stream) == 3
        current_icici = db.query(Incident).filter(Incident.segment_issuer == "ICICI").all()
        assert len(current_icici) == 1
        assert current_icici[0].id == initial_icici.id

        current_sbi = db.query(Incident).filter(Incident.segment_issuer == "SBI").all()
        assert len(current_sbi) == 1
        assert current_sbi[0].id == initial_sbi.id

        current_bank_x = db.query(Incident).filter(Incident.segment_issuer == "Bank X").all()
        assert len(current_bank_x) == 1
        assert current_bank_x[0].id == initial_bank_x.id

        # 5. Call detect_anomalies again explicitly
        detected = detect_anomalies(db)
        assert len(detected) == 3

        # 6. Verify total incidents remain exactly 3
        final_incidents = db.query(Incident).all()
        assert len(final_incidents) == 3

        # 7. Segment Explorer must show exactly 1 incident per segment
        seg_res = client.get("/api/segments/analytics")
        assert seg_res.status_code == 200
        for seg in seg_res.json()["segments"]:
            if seg["issuer"] in {"Bank X", "ICICI", "SBI"} and seg["incidents"]:
                assert len(seg["incidents"]) == 1
    finally:
        db.close()
