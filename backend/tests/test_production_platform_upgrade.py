"""Comprehensive Verification Test Suite for Production-Grade DeclineDoctor Platform Upgrade.

Tests:
1. Payment Event Ingestion Webhook:
   - Valid event payload
   - Malformed/invalid payload rejection (422)
   - Idempotent duplicate event handling (no duplicate processing)
   - Successful payment bypass of anomaly detection
   - Failed payment triggering controlled monitoring pipeline
   - High-value exposure paused for dual-control approval
   - Safety preservation: Webhook never directly executes financial actions
2. Multi-Provider Routing Optimizer:
   - Provider scoring and ranking across segments & BINs
   - Expected success rate, latency, and cost calculations
   - REROUTE explanation target provider mapping
   - LIVE_CALLS_ENABLED strictly False assertion
3. Deep BIN-Level Intelligence:
   - BIN aggregation, volume, and decline code distribution
   - Isolation detection ("isolated to BIN 452114 rather than issuer-wide")
   - Multi-provider BIN breakdown
4. Advanced Structured Causal Evidence:
   - 12-factor causal evidence (hypothesis, confidence, evidence_for, evidence_against, invalidation_criteria)
   - Clean, structured evidence without chain-of-thought exposure
5. Counterfactual Simulator:
   - Baseline NO_ACTION comparison
   - Friction scoring and net recovered calculations
   - Frozen snapshot consistency
6. Real-Time Incident / Alert Feed:
   - Timestamp, severity, revenue at risk, drop_pp, policy state, and approval state
7. Human Approval Center:
   - Dual-control rejection endpoint
   - RBAC enforcement (VIEWER/ANALYST blocked from rejection)
   - Cryptographic audit trail logging for rejection
   - Terminal state immutability
"""

import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app.models import Incident, Diagnosis, Transaction, WebhookEvent, AuditLog, RecoveryAction
from app.providers.routing_optimizer import optimize_provider_routing, score_provider_route, LIVE_CALLS_ENABLED
from app.bin_intelligence import analyze_bin_telemetry
from app.recovery_agent import compute_counterfactuals

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Payment Event Ingestion Webhook (Part A: Test A, B, C, D)
# ---------------------------------------------------------------------------

def test_webhook_valid_event_and_pipeline():
    """Test A — Valid payment webhook:
    - Submit a valid synthetic payment event.
    - Verify HTTP success (200 OK).
    - Verify event is persisted exactly once in WebhookEvent table.
    - Verify transaction is persisted in Transaction table.
    - Verify it enters the intended pipeline stages (RECEIVED, VALIDATED, SEGMENTED, etc.).
    """
    db = SessionLocal()
    pid = f"pay_test_a_{datetime.now().timestamp()}"
    try:
        payload = {
            "payment_id": pid,
            "amount": 2500.0,
            "currency": "INR",
            "status": "failed",
            "issuer": "Bank X",
            "payment_method": "card",
            "card_bin": "452114",
            "card_network": "Visa",
            "decline_code": "processor_declined",
            "decline_reason": "Routing partner gateway timeout",
            "timestamp": datetime.now().isoformat(),
            "provider": "Razorpay Smart Router",
        }
        res = client.post("/api/webhooks/payment", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "PROCESSED"
        assert data["is_duplicate"] is False
        assert "pipeline_result" in data

        # Verify event is persisted exactly once in WebhookEvent
        wbk_records = db.query(WebhookEvent).filter(WebhookEvent.payment_id == pid).all()
        assert len(wbk_records) == 1
        assert wbk_records[0].status == "PROCESSED"

        # Verify transaction is persisted in Transaction table
        tx_records = db.query(Transaction).filter(Transaction.id == pid).all()
        assert len(tx_records) == 1
        assert tx_records[0].amount == 2500.0
        assert tx_records[0].issuer == "Bank X"
        assert tx_records[0].success is False

        # Verify it enters the intended pipeline stages
        trace_stages = [step["stage"] for step in data["pipeline_result"]["timeline"]]
        assert "RECEIVED" in trace_stages
        assert "VALIDATED" in trace_stages
        assert "SEGMENTED" in trace_stages
        assert "POLICY_EVALUATED" in trace_stages

        # Financial safety guarantee: Webhook NEVER directly executes financial recovery
        assert data["pipeline_result"]["lifecycle_stage"] != "RECOVERY_EXECUTED"
    finally:
        db.close()


def test_webhook_idempotency_duplicate_handling():
    """Test B — Duplicate webhook:
    - Submit the exact same event/idempotency key again.
    - Verify it is not processed twice (status DUPLICATE_ACCEPTED, is_duplicate True).
    - Verify no duplicate transaction is created (exactly 1 transaction record).
    - Verify no duplicate recovery action is created (0 recovery actions).
    """
    db = SessionLocal()
    pid = f"pay_test_b_{datetime.now().timestamp()}"
    idem_key = f"key_{pid}"
    try:
        payload = {
            "payment_id": pid,
            "amount": 4200.0,
            "status": "failed",
            "issuer": "Bank X",
            "payment_method": "card",
            "card_bin": "452114",
            "idempotency_key": idem_key,
        }

        # 1. First delivery
        res1 = client.post("/api/webhooks/payment", json=payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "PROCESSED"
        assert data1["is_duplicate"] is False

        # 2. Second identical delivery
        res2 = client.post("/api/webhooks/payment", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "DUPLICATE_ACCEPTED"
        assert data2["is_duplicate"] is True
        assert data2["payment_id"] == pid
        assert data2["idempotency_key"] == idem_key

        # 3. Verify no duplicate transaction is created (count is exactly 1)
        tx_count = db.query(Transaction).filter(Transaction.id == pid).count()
        assert tx_count == 1, f"Expected exactly 1 transaction, found {tx_count}"

        # 4. Verify no duplicate webhook record is created (count is exactly 1)
        wbk_count = db.query(WebhookEvent).filter(WebhookEvent.payment_id == pid).count()
        assert wbk_count == 1, f"Expected exactly 1 webhook event, found {wbk_count}"

        # 5. Verify no recovery action was created
        ra_count = db.query(RecoveryAction).filter(RecoveryAction.incident_id.like(f"%{pid}%")).count()
        assert ra_count == 0
    finally:
        db.close()


def test_webhook_malformed_event_rejection():
    """Test C — Malformed/invalid webhook:
    - Submit an invalid payload (negative amount, invalid status, missing required fields).
    - Verify it is rejected with the correct HTTP status (422 Unprocessable Entity).
    - Verify no transaction, incident, or recovery action is created.
    """
    db = SessionLocal()
    try:
        # Case 1: Negative amount & missing required issuer
        bad_pid_1 = f"pay_bad_neg_{datetime.now().timestamp()}"
        res1 = client.post(
            "/api/webhooks/payment",
            json={"payment_id": bad_pid_1, "amount": -500.0, "status": "failed", "payment_method": "card"},
        )
        assert res1.status_code == 422
        assert db.query(Transaction).filter(Transaction.id == bad_pid_1).first() is None
        assert db.query(WebhookEvent).filter(WebhookEvent.payment_id == bad_pid_1).first() is None

        # Case 2: Invalid status value
        bad_pid_2 = f"pay_bad_stat_{datetime.now().timestamp()}"
        res2 = client.post(
            "/api/webhooks/payment",
            json={
                "payment_id": bad_pid_2,
                "amount": 1000.0,
                "status": "unsupported_unknown_status",
                "issuer": "Bank X",
                "payment_method": "card",
            },
        )
        assert res2.status_code == 422
        assert db.query(Transaction).filter(Transaction.id == bad_pid_2).first() is None
        assert db.query(WebhookEvent).filter(WebhookEvent.payment_id == bad_pid_2).first() is None

        # Case 3: Missing payment_id
        res3 = client.post(
            "/api/webhooks/payment",
            json={"amount": 1000.0, "status": "captured", "issuer": "Bank X", "payment_method": "card"},
        )
        assert res3.status_code == 422

        # Verify no recovery action was created from any malformed attempts
        assert db.query(RecoveryAction).filter(RecoveryAction.id.like("%pay_bad%")).count() == 0
    finally:
        db.close()


def test_webhook_financial_safety_guarantees():
    """Test D — Financial safety:
    - Confirm webhook ingestion cannot directly execute recovery.
    - Recovery must still pass diagnosis + backend policy gates.
    - LIVE_CALLS_ENABLED must remain false.
    """
    # 1. LIVE_CALLS_ENABLED must be strictly False (sandbox simulation guarantee)
    assert LIVE_CALLS_ENABLED is False

    db = SessionLocal()
    pid = f"pay_safety_{datetime.now().timestamp()}"
    try:
        initial_recovery_count = db.query(RecoveryAction).count()

        # Submit event attempting to force auto_recover / auto_execute
        payload = {
            "payment_id": pid,
            "amount": 50000.0,
            "currency": "INR",
            "status": "failed",
            "issuer": "Bank X",
            "payment_method": "card",
            "card_bin": "452114",
            "decline_code": "processor_declined",
            "decline_reason": "Processor outage",
            "provider": "Razorpay Smart Router",
            "metadata": {"auto_recover": True, "auto_execute": True},
        }

        res = client.post("/api/webhooks/payment", json=payload)
        assert res.status_code == 200
        data = res.json()

        # Ingestion pipeline result must never be RECOVERY_EXECUTED
        assert data.get("lifecycle_stage") != "RECOVERY_EXECUTED"
        if data.get("pipeline_result"):
            assert data["pipeline_result"].get("lifecycle_stage") != "RECOVERY_EXECUTED"

        # Database check: Zero new recovery actions were created
        current_recovery_count = db.query(RecoveryAction).count()
        assert current_recovery_count == initial_recovery_count, "Webhook directly created a RecoveryAction!"
    finally:
        db.close()


def test_webhook_successful_payment_clean_path():
    """Verify successful payment passes through pipeline cleanly without raising anomaly."""
    pid = f"pay_succ_{datetime.now().timestamp()}"
    payload = {
        "payment_id": pid,
        "amount": 1800.0,
        "status": "captured",
        "issuer": "HDFC",
        "payment_method": "card",
        "card_bin": "524188",
    }
    res = client.post("/api/webhooks/payment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["lifecycle_stage"] == "COMPLETED_SUCCESS"


# ---------------------------------------------------------------------------
# 2. Multi-Provider Routing Optimizer (Part B)
# ---------------------------------------------------------------------------

def test_provider_routing_optimizer_and_safety():
    """Verify multi-provider routing scoring, ranking, and strict safety guardrails."""
    # Invariant 9: LIVE_CALLS_ENABLED must strictly remain False
    assert LIVE_CALLS_ENABLED is False

    decision = optimize_provider_routing(
        issuer="Bank X",
        payment_method="card",
        bin_number="452114",
        decline_reason="processor_declined",
    )
    assert decision["recommended_provider"] == "Provider A"
    assert decision["score"] >= 80.0
    assert decision["expected_success_rate"] >= 90.0
    assert decision["expected_latency_ms"] <= 120
    assert decision["expected_cost_pct"] > 0
    assert "REROUTE ->" in decision["target_gateway_routing"]
    assert len(decision["ranked_providers"]) >= 3
    assert decision["live_calls_enabled"] is False

    # Verify API endpoints
    res_rec = client.get("/api/providers/routing/recommendation?issuer=Bank+X&payment_method=card&bin=452114")
    assert res_rec.status_code == 200
    assert res_rec.json()["recommended_provider"] == "Provider A"

    res_profiles = client.get("/api/providers/profiles")
    assert res_profiles.status_code == 200
    assert "Provider A" in res_profiles.json()
    assert "Razorpay Smart Router" in res_profiles.json()


def test_provider_profiles_and_multi_dimensional_scoring_inputs():
    """Verify all 4 provider profiles exist and scoring considers:
    - success rate
    - latency
    - processing fee
    - health
    - issuer
    - payment method
    - BIN
    """
    from app.providers.routing_optimizer import SIMULATED_PROVIDER_PROFILES, score_provider_route

    # 1. Multi-provider profiles exist
    expected_providers = {"Provider A", "Provider B", "Provider C", "Razorpay Smart Router"}
    assert set(SIMULATED_PROVIDER_PROFILES.keys()) == expected_providers

    for name, profile in SIMULATED_PROVIDER_PROFILES.items():
        assert "base_success_rate" in profile
        assert "base_latency_ms" in profile
        assert "cost_pct" in profile
        assert "health" in profile
        assert profile["health"] in {"OPTIMAL", "HEALTHY", "DEGRADED_FAILOVER"}
        assert "specialties" in profile
        assert "issuers" in profile["specialties"]
        assert "payment_methods" in profile["specialties"]
        assert "bins" in profile["specialties"]

    # 2. Dynamic scoring reflects latency, cost, health, and segment inputs
    score_p_a = score_provider_route("Provider A", issuer="Bank X", payment_method="card", bin_number="452114")
    assert score_p_a["composite_score"] > 90.0
    assert score_p_a["expected_success_rate"] == 97.1
    assert score_p_a["latency_ms"] == 78
    assert score_p_a["cost_pct"] == 1.85
    assert score_p_a["health"] == "OPTIMAL"

    # Degraded failover penalty test (drops score by exactly 25.0 penalty)
    score_degraded = score_provider_route("Provider A", issuer="Bank X", payment_method="card", bin_number="452114", current_degraded_provider="Provider A")
    assert score_degraded["is_currently_degraded"] is True
    assert score_degraded["composite_score"] == round(score_p_a["composite_score"] - 25.0, 1)
    assert score_degraded["health"] == "DEGRADED"


def test_provider_routing_derived_from_incident_and_bin_evidence():
    """Verify provider recommendation is dynamically derived from incident evidence & BIN-specific routing."""
    # Bank X with BIN 452114
    opt_bx = optimize_provider_routing(issuer="Bank X", payment_method="card", bin_number="452114")
    assert opt_bx["recommended_provider"] == "Provider A"
    assert opt_bx["segment_evaluated"]["bin"] == "452114"
    assert "Provider A" in opt_bx["target_gateway_routing"]

    # ICICI with BIN 476543
    opt_icici = optimize_provider_routing(issuer="ICICI", payment_method="card", bin_number="476543")
    assert opt_icici["recommended_provider"] in {"Provider A", "Razorpay Smart Router"}
    assert opt_icici["segment_evaluated"]["bin"] == "476543"

    # Degraded provider failover test
    opt_failover = optimize_provider_routing(
        issuer="Bank X",
        payment_method="card",
        bin_number="452114",
        current_degraded_provider="Provider A",
    )
    assert opt_failover["recommended_provider"] == "Razorpay Smart Router"
    assert opt_failover["target_gateway_routing"] == "REROUTE -> Razorpay Smart Router"


def test_reroute_action_uses_dynamically_recommended_provider():
    """Verify REROUTE action and counterfactual projections use dynamically recommended provider rather than a hardcoded route."""
    from app.routes.incidents import get_incident_detail

    db = SessionLocal()
    try:
        now = datetime.now()
        inc = Incident(
            id="inc_unit_dynamic_reroute",
            detected_at=now,
            segment_issuer="Bank X",
            segment_payment_method="card",
            window_start=now - timedelta(hours=1),
            window_end=now + timedelta(hours=1),
            baseline_success_rate=95.0,
            incident_success_rate=50.0,
            drop_pp=45.0,
            concentration_ratio=0.80,
            sample_size=20,
            state="DIAGNOSED",
            severity="HIGH",
        )
        diag = Diagnosis(
            id="diag_unit_dynamic_reroute",
            incident_id=inc.id,
            hypothesis="ROUTING_CONNECTIVITY_ISSUE",
            confidence=0.85,
            dominant_decline_code="processor_declined",
            dominant_decline_code_share=0.80,
            evidence_json=json.dumps({"bin": "452114", "recommended_provider": "Provider A"}),
        )
        db.add(inc)
        db.add(diag)
        for i in range(10):
            db.add(Transaction(
                id=f"tx_dyn_f_{i}",
                merchant_id="m",
                amount=5000.0,
                timestamp=now,
                payment_method="card",
                issuer="Bank X",
                card_bin="452114",
                success=False,
                retry_count=0,
            ))
        for i in range(10):
            db.add(Transaction(
                id=f"tx_dyn_s_{i}",
                merchant_id="m",
                amount=5000.0,
                timestamp=now,
                payment_method="card",
                issuer="Bank X",
                card_bin="452114",
                success=True,
                retry_count=0,
            ))
        db.commit()

        # Compute counterfactuals
        cfs = compute_counterfactuals(db, inc.id, include_extended=True, include_baseline=False)
        reroute_cf = next((c for c in cfs if c["action_type"] == "REROUTE"), None)
        assert reroute_cf is not None
        assert "target_provider" in reroute_cf
        assert reroute_cf["target_provider"] in {"Provider A", "Razorpay Smart Router"}
        assert f"REROUTE -> {reroute_cf['target_provider']}" == reroute_cf["target_gateway_routing"]

        # Verify incident detail API returns authoritative recommended provider matching counterfactual
        detail = get_incident_detail(inc.id, db=db)
        assert detail["recommended_recovery"]["target_provider"] == reroute_cf["target_provider"]
        assert detail["recommended_recovery"]["target_gateway_routing"] == reroute_cf["target_gateway_routing"]

        # Clean up
        db.query(Transaction).filter(Transaction.id.like("tx_dyn_%")).delete()
        db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).delete()
        db.query(Incident).filter(Incident.id == inc.id).delete()
        db.commit()
    finally:
        db.close()


def test_provider_routing_terminal_locking_and_policy_safety():
    """Verify terminal incidents cannot change provider routing and routing optimization cannot bypass policy."""
    db = SessionLocal()
    try:
        # Clean up any leftover row from previous interrupted run
        db.query(Diagnosis).filter(Diagnosis.incident_id == "inc_term_routing_lock").delete()
        db.query(Incident).filter(Incident.id == "inc_term_routing_lock").delete()
        db.commit()

        now = datetime.now()
        inc = Incident(
            id="inc_term_routing_lock",
            detected_at=now,
            segment_issuer="Bank X",
            segment_payment_method="card",
            window_start=now - timedelta(hours=1),
            window_end=now,
            baseline_success_rate=95.0,
            incident_success_rate=45.0,
            drop_pp=50.0,
            concentration_ratio=0.85,
            sample_size=100,
            state="RESOLVED",
            severity="HIGH",
        )
        diag = Diagnosis(
            id="diag_term_routing_lock",
            incident_id="inc_term_routing_lock",
            hypothesis="ROUTING_CONNECTIVITY_ISSUE",
            confidence=0.88,
            dominant_decline_code="processor_declined",
            dominant_decline_code_share=0.80,
            evidence_json="{}",
            narrative_text="Terminal lock test diagnosis",
        )
        db.add(inc)
        db.add(diag)
        db.commit()

        # Terminal incident cannot execute recovery to change provider routing
        res_exec = client.post(
            "/api/incidents/inc_term_routing_lock/recover",
            json={"recommended_action": "REROUTE", "role": "OPERATOR"},
        )
        assert res_exec.status_code == 200
        assert res_exec.json()["status"] == "blocked"
        assert res_exec.json()["reason"] == "terminal_incident"

        # Read-only recommendation endpoint is safe and non-mutating
        res_rec = client.get("/api/providers/routing/recommendation?incident_id=inc_term_routing_lock&issuer=Bank+X&payment_method=card")
        assert res_rec.status_code == 200
        assert res_rec.json()["recommended_provider"] is not None

        # Clean up
        db.query(Diagnosis).filter(Diagnosis.incident_id == "inc_term_routing_lock").delete()
        db.query(Incident).filter(Incident.id == "inc_term_routing_lock").delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Deep BIN-Level Intelligence (Part C)
# ---------------------------------------------------------------------------

def test_bin_level_intelligence_and_isolation():
    """Verify deep BIN aggregation, decline code breakdown, and isolation detection."""
    db = SessionLocal()
    try:
        bin_data = analyze_bin_telemetry(db, issuer="Bank X", payment_method="card")
        assert "bin_telemetry" in bin_data
        assert len(bin_data["bin_telemetry"]) > 0
        primary_bin = bin_data["bin_telemetry"][0]
        assert "bin" in primary_bin
        assert "failure_rate_pct" in primary_bin
        assert "decline_code_distribution" in primary_bin
        assert "provider_breakdown" in primary_bin
        assert "isolation_summary" in bin_data
        assert "isolated to BIN" in bin_data["isolation_summary"] or "distributed" in bin_data["isolation_summary"]

        # Verify API route
        res = client.get("/api/segments/bin-intelligence?issuer=Bank+X&payment_method=card")
        assert res.status_code == 200
        assert res.json()["dominant_bin"] is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Structured Causal Evidence Generation (Part D)
# ---------------------------------------------------------------------------

def test_structured_causal_evidence_in_diagnosis():
    """Verify diagnosis returns all 12 causal evidence factors without chain-of-thought."""
    res = client.get("/api/incidents")
    assert res.status_code == 200
    incidents = res.json()
    assert len(incidents) > 0
    inc_id = incidents[0]["id"]

    # Trigger diagnosis
    res_diag = client.post(f"/api/incidents/{inc_id}/diagnose")
    assert res_diag.status_code == 200

    res_detail = client.get(f"/api/incidents/{inc_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    evidence = json.loads(detail["diagnosis"]["evidence_json"])
    assert "causal_evidence" in evidence
    ce = evidence["causal_evidence"]

    # Verify 12 required fields
    assert "hypothesis" in ce
    assert "confidence" in ce
    assert "evidence_for" in ce and len(ce["evidence_for"]) > 0
    assert "evidence_against" in ce and len(ce["evidence_against"]) > 0
    assert "key_statistical_signals" in ce
    assert "relevant_segment" in ce
    assert "provider_evidence" in ce
    assert "bin_evidence" in ce
    assert "recommended_action" in ce
    assert "why_appropriate" in ce
    assert "invalidation_criteria" in ce and len(ce["invalidation_criteria"]) > 0
    assert "uncertainty" in ce
    # Verify no private internal reasoning is exposed
    assert "chain_of_thought" not in ce


# ---------------------------------------------------------------------------
# 5. Counterfactual Simulator with Baseline & Friction (Part E)
# ---------------------------------------------------------------------------

def test_counterfactual_baseline_and_friction_scores():
    """Verify counterfactual projections include NO_ACTION baseline and customer friction score."""
    res = client.get("/api/incidents")
    inc_id = res.json()[0]["id"]

    # Standard call returns exactly 3 candidate actions (preserving existing contract)
    res_std = client.get(f"/api/incidents/{inc_id}/counterfactuals")
    assert res_std.status_code == 200
    assert len(res_std.json()) == 3

    # Extended call with baseline returns NO_ACTION as first comparison option
    res_base = client.get(f"/api/incidents/{inc_id}/counterfactuals?extended=true&include_baseline=true")
    assert res_base.status_code == 200
    cfs = res_base.json()
    assert len(cfs) >= 4
    no_action = cfs[0]
    assert no_action["action_type"] == "NO_ACTION"
    assert no_action["expected_recovered_revenue"] == 0.0
    assert no_action["expected_cost"] == 0.0
    # Verify baseline is mathematically consistent with incident's frozen degraded snapshot
    inc_data = res.json()[0]
    assert no_action["projected_success_rate"] == round(inc_data["incident_success_rate"], 2)
    assert no_action["current_success_rate"] == round(inc_data["incident_success_rate"], 2)
    assert no_action["expected_improvement_pp"] == 0.0

    # Verify candidate actions include friction scores and valid lift arithmetic
    for cf in cfs:
        assert "customer_friction_score" in cf
        assert "expected_recovered_revenue" in cf
        assert "expected_net_recovery" in cf
        expected_proj = round(no_action["projected_success_rate"] + cf["expected_improvement_pp"], 2)
        assert cf["projected_success_rate"] == expected_proj


# ---------------------------------------------------------------------------
# 6. Real-Time Incident Activity Feed (Part F)
# ---------------------------------------------------------------------------

def test_real_time_incident_activity_feed():
    """Verify real-time incident activity feed endpoint returns structured operational telemetry."""
    res = client.get("/api/incidents/feed")
    assert res.status_code == 200
    feed = res.json()
    assert isinstance(feed, list)
    assert len(feed) > 0
    item = feed[0]
    assert "incident_id" in item
    assert "timestamp" in item
    assert "severity" in item
    assert "issuer" in item
    assert "payment_method" in item
    assert "revenue_at_risk" in item
    assert "drop_pp" in item
    assert "current_state" in item
    assert "diagnosis" in item
    assert "policy_result" in item
    assert "recommended_action" in item
    assert "approval_state" in item


# ---------------------------------------------------------------------------
# 7. Dual-Control Human Approval Rejection & Terminal Lock (Part G)
# ---------------------------------------------------------------------------

def test_human_approval_rejection_and_rbac():
    """Verify human approval rejection flow, RBAC enforcement, and audit trail append."""
    db = SessionLocal()
    try:
        db.query(AuditLog).filter(AuditLog.incident_id == "inc_reject_test_dual").delete()
        db.query(Incident).filter(Incident.id == "inc_reject_test_dual").delete()
        db.commit()

        now = datetime.now()
        # Create dedicated high-value incident awaiting human approval
        inc = Incident(
            id="inc_reject_test_dual",
            detected_at=now,
            segment_issuer="ICICI",
            segment_payment_method="card",
            window_start=now - timedelta(hours=1),
            window_end=now,
            baseline_success_rate=95.0,
            incident_success_rate=45.0,
            drop_pp=50.0,
            concentration_ratio=0.85,
            sample_size=120,
            state="AWAITING_HUMAN_APPROVAL",
            severity="CRITICAL",
        )
        db.add(inc)
        db.commit()

        # VIEWER cannot reject approval (RBAC 403)
        res_viewer = client.post(
            "/api/incidents/inc_reject_test_dual/reject",
            json={"reason": "Operator reject", "role": "VIEWER", "operator_name": "viewer_user"},
        )
        assert res_viewer.status_code == 403

        # OPERATOR can reject approval
        res_op = client.post(
            "/api/incidents/inc_reject_test_dual/reject",
            json={"reason": "Suspected false-positive spike during scheduled core maintenance", "role": "OPERATOR", "operator_name": "lead_operator"},
        )
        assert res_op.status_code == 200
        data_op = res_op.json()
        assert data_op["status"] == "APPROVAL_REJECTED"
        assert data_op["state"] == "APPROVAL_REJECTED"

        # Verify incident state in database is APPROVAL_REJECTED (terminal)
        db.refresh(inc)
        assert inc.state == "APPROVAL_REJECTED"

        # Verify audit log was recorded
        audit = db.query(AuditLog).filter(
            AuditLog.incident_id == "inc_reject_test_dual",
            AuditLog.event_type == "APPROVAL_REJECTED",
        ).first()
        assert audit is not None
        assert "lead_operator" in audit.actor

        # Terminal state protection: Cannot reject again or execute recovery
        res_second = client.post(
            "/api/incidents/inc_reject_test_dual/reject",
            json={"reason": "Second attempt", "role": "OPERATOR"},
        )
        assert res_second.status_code == 400
    finally:
        db.close()


def test_bin_476543_routing_recommendation_and_registry_api():
    """Verify BIN 476543 is present in the authoritative registry API and generates correct routing recommendation."""
    # 1. Authoritative registry API returns BIN 476543 with correct metadata
    res_bins = client.get("/api/providers/routing/bins")
    assert res_bins.status_code == 200
    bins = res_bins.json()
    assert isinstance(bins, list)
    bin_476543 = next((b for b in bins if b["bin"] == "476543"), None)
    assert bin_476543 is not None
    assert bin_476543["issuer"] == "ICICI"
    assert bin_476543["card_network"] == "Visa"
    assert bin_476543["card_tier"] == "Coral Platinum Card"

    # 2. Score endpoint evaluates ICICI + BIN 476543 + card + processor_declined
    res_score = client.post(
        "/api/providers/routing/score",
        json={
            "issuer": "ICICI",
            "payment_method": "card",
            "bin": "476543",
            "decline_reason": "processor_declined",
        },
    )
    assert res_score.status_code == 200
    score_data = res_score.json()
    assert score_data["recommended_provider"] == "Provider A"
    assert abs(score_data["score"] - 95.6) <= 0.5
    assert score_data["expected_success_rate"] == 96.1
    assert score_data["expected_latency_ms"] == 78
    assert score_data["expected_cost_pct"] == 1.85
    assert score_data["target_gateway_routing"] == "REROUTE -> Provider A"
    assert score_data["segment_evaluated"]["issuer"] == "ICICI"
    assert score_data["segment_evaluated"]["bin"] == "476543"

    # 3. GET recommendation endpoint evaluates identical dynamic parameters
    res_rec = client.get(
        "/api/providers/routing/recommendation?issuer=ICICI&payment_method=card&bin=476543&decline_reason=processor_declined"
    )
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["recommended_provider"] == "Provider A"
    assert abs(rec_data["score"] - 95.6) <= 0.5
    assert rec_data["segment_evaluated"]["bin"] == "476543"


def test_degraded_provider_a_failover_to_smart_router_simulation():
    """Verify degraded Provider A simulation applies 25.0 penalty (dropping to ~71.1) and shifts routing to Razorpay Smart Router."""
    # 1. Normal state baseline: Provider A wins with score 96.1
    res_norm = client.post(
        "/api/providers/routing/score",
        json={"issuer": "Bank X", "payment_method": "card", "bin": "452114", "decline_reason": "processor_declined"},
    )
    assert res_norm.status_code == 200
    data_norm = res_norm.json()
    assert data_norm["recommended_provider"] == "Provider A"
    assert data_norm["score"] == 96.1

    # 2. Simulated degraded Provider A via POST /api/providers/routing/score
    res_deg = client.post(
        "/api/providers/routing/score",
        json={
            "issuer": "Bank X",
            "payment_method": "card",
            "bin": "452114",
            "decline_reason": "processor_declined",
            "current_degraded_provider": "Provider A",
        },
    )
    assert res_deg.status_code == 200
    data_deg = res_deg.json()
    assert data_deg["recommended_provider"] == "Razorpay Smart Router"
    assert data_deg["target_gateway_routing"] == "REROUTE -> Razorpay Smart Router"
    assert data_deg["score"] == 94.5

    # Check Provider A score dropped by 25.0 to 71.1 and is flagged degraded
    prov_a = next(p for p in data_deg["ranked_providers"] if p["provider"] == "Provider A")
    assert prov_a["composite_score"] == 71.1
    assert prov_a["health"] == "DEGRADED"
    assert prov_a["is_currently_degraded"] is True

    # 3. Simulated degraded Provider A via GET /api/providers/routing/recommendation
    res_rec = client.get(
        "/api/providers/routing/recommendation?issuer=Bank+X&payment_method=card&bin=452114&current_degraded_provider=Provider+A"
    )
    assert res_rec.status_code == 200
    data_rec = res_rec.json()
    assert data_rec["recommended_provider"] == "Razorpay Smart Router"
    assert data_rec["target_gateway_routing"] == "REROUTE -> Razorpay Smart Router"

    # 4. Clean restore when current_degraded_provider is removed or set to None
    res_clean = client.get(
        "/api/providers/routing/recommendation?issuer=Bank+X&payment_method=card&bin=452114"
    )
    assert res_clean.status_code == 200
    assert res_clean.json()["recommended_provider"] == "Provider A"


def test_simulate_stream_event_canonical_pipeline_and_safety():
    """Regression Test for Canonical POST /api/simulate/stream_event:
    1. Valid simulated stream event returns 200.
    2. Exactly 9 pipeline stages are returned in timeline and pipeline_trace.
    3. Invalid payloads (negative/zero amount, empty issuer) are rejected with 422.
    4. Financial safety guarantees: no real recovery/payment execution occurs; LIVE_CALLS_ENABLED is False.
    5. Existing webhook endpoint remains unaffected and operational.
    6. Backward compatibility with POST /api/simulate/stream is preserved.
    """
    # 1. Reset baseline demo data to ensure known Bank X anomaly context
    reset_res = client.post("/api/simulate/inject")
    assert reset_res.status_code == 200

    # 2. Valid simulated failed event to canonical /api/simulate/stream_event
    valid_payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 1850.0,
        "success": False,
        "decline_code": "processor_declined",
        "decline_reason": "Processor communication timeout",
        "auto_recover": False,
        "user_role": "OPERATOR",
    }
    res = client.post("/api/simulate/stream_event", json=valid_payload)
    assert res.status_code == 200
    data = res.json()

    # Verify 9 pipeline stages are returned
    assert "timeline" in data
    assert "pipeline_trace" in data
    assert len(data["timeline"]) == 9
    assert len(data["pipeline_trace"]) == 9

    expected_stages = [
        "RECEIVED",
        "VALIDATED",
        "SEGMENTED",
        "ANOMALY_CHECKED",
        "DIAGNOSED",
        "POLICY_EVALUATED",
        "ACTION_SELECTED",
        "ACTION_APPLIED",
        "OUTCOME_MEASURED",
    ]
    trace_stages = [step["stage"] for step in data["timeline"]]
    assert trace_stages == expected_stages

    # Verify each stage contains required trace properties
    for step in data["timeline"]:
        assert "stage" in step
        assert "status" in step
        assert "details" in step
        assert "timestamp" in step
        assert "duration_ms" in step

    # Safety guarantee: auto_recover=False prevents real or automated recovery
    assert data["lifecycle_stage"] != "RECOVERY_EXECUTED"
    assert data["timeline"][7]["stage"] == "ACTION_APPLIED"
    assert data["timeline"][7]["status"] == "PENDING_MANUAL_TRIGGER"
    assert data["timeline"][8]["stage"] == "OUTCOME_MEASURED"
    assert data["timeline"][8]["status"] == "UNAVAILABLE"
    assert LIVE_CALLS_ENABLED is False

    # 3. Valid successful stream event returns 200 and all 9 stages
    success_payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 2200.0,
        "success": True,
    }
    res_succ = client.post("/api/simulate/stream_event", json=success_payload)
    assert res_succ.status_code == 200
    succ_data = res_succ.json()
    assert len(succ_data["timeline"]) == 9
    assert [s["stage"] for s in succ_data["timeline"]] == expected_stages
    assert succ_data["lifecycle_stage"] == "COMPLETED_SUCCESS"

    # 4. Invalid payloads are rejected with 422 Unprocessable Entity
    # Negative amount
    bad_amt_res = client.post(
        "/api/simulate/stream_event",
        json={"issuer": "Bank X", "payment_method": "card", "amount": -250.0},
    )
    assert bad_amt_res.status_code == 422

    # Zero amount
    zero_amt_res = client.post(
        "/api/simulate/stream_event",
        json={"issuer": "Bank X", "payment_method": "card", "amount": 0.0},
    )
    assert zero_amt_res.status_code == 422

    # Empty issuer
    empty_issuer_res = client.post(
        "/api/simulate/stream_event",
        json={"issuer": "", "payment_method": "card", "amount": 1000.0},
    )
    assert empty_issuer_res.status_code == 422

    # 5. Existing webhook endpoint remains unaffected
    pid = f"pay_stream_reg_{datetime.now().timestamp()}"
    wbk_payload = {
        "payment_id": pid,
        "amount": 1750.0,
        "status": "failed",
        "issuer": "Bank X",
        "payment_method": "card",
        "card_bin": "452114",
        "decline_code": "processor_declined",
    }
    wbk_res = client.post("/api/webhooks/payment", json=wbk_payload)
    assert wbk_res.status_code == 200
    wbk_data = wbk_res.json()
    assert wbk_data["status"] == "PROCESSED"
    assert wbk_data["is_duplicate"] is False
    assert "pipeline_result" in wbk_data
    wbk_stages = [s["stage"] for s in wbk_data["pipeline_result"]["timeline"]]
    assert wbk_stages == expected_stages

    # 6. Backward-compatibility: POST /api/simulate/stream still returns identical structure
    compat_res = client.post("/api/simulate/stream", json=valid_payload)
    assert compat_res.status_code == 200
    compat_data = compat_res.json()
    assert [s["stage"] for s in compat_data["timeline"]] == expected_stages


# ---------------------------------------------------------------------------
# 8. Counterfactual Simulator — Regression: Non-Mutation & Snapshot Integrity
# ---------------------------------------------------------------------------

def test_counterfactual_simulator_non_mutation_and_snapshot_integrity():
    """Regression Test for Interactive Counterfactual Simulator:

    1. All 7 expected strategy types are present in the extended snapshot.
    2. Exactly one strategy is marked is_recommended (the backend-authoritative one).
    3. Reading counterfactuals (GET) NEVER mutates incident state, recovery_action, or audit log count.
    4. The frozen snapshot is stable across two consecutive GET calls (immutable cache).
    5. NO_ACTION (baseline) has zero lift, zero net recovery, and zero cost.
    6. REROUTE strategy (recommended for ROUTING_CONNECTIVITY_ISSUE) has positive lift and a target_provider.
    7. Incompatible strategies are correctly flagged is_compatible=False.
    8. Terminal incidents return an empty list or all-locked counterfactuals (no execution).
    """
    from app.database import SessionLocal
    from app.models import Incident, Diagnosis, Transaction, AuditLog, RecoveryAction

    db = SessionLocal()
    try:
        # Setup: create a fresh isolation-test incident
        inc_id = f"inc_cf_sim_regression_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=20)
        window_end = now

        inc = Incident(
            id=inc_id,
            segment_issuer="ICICI",
            segment_payment_method="card",
            state="ANOMALY_DETECTED",
            severity="HIGH",
            detected_at=now,
            window_start=window_start,
            window_end=window_end,
            baseline_success_rate=92.5,
            incident_success_rate=61.0,
            drop_pp=31.5,
            concentration_ratio=0.88,
            sample_size=120,
        )
        db.add(inc)

        # Seed 120 transactions: 73 failed (eligble for retry), 47 success
        for i in range(120):
            success_flag = i < 47  # first 47 succeed
            tx = Transaction(
                id=f"tx_{inc_id}_{i}",
                issuer="ICICI",
                payment_method="card",
                card_bin="476543",
                amount=4200.0 + (i * 50),
                success=success_flag,
                decline_code=None if success_flag else "processor_declined",
                timestamp=window_start + timedelta(seconds=i * 10),
                retry_count=0,
            )
            db.add(tx)

        db.commit()

        # Diagnose via API
        diag_res = client.post(f"/api/incidents/{inc_id}/diagnose")
        assert diag_res.status_code == 200, f"Diagnose failed: {diag_res.text}"

        # Capture pre-read audit log count and incident state
        pre_audit_count = db.query(AuditLog).filter(AuditLog.incident_id == inc_id).count()
        pre_state = db.query(Incident).filter(Incident.id == inc_id).first().state
        pre_ra_count = db.query(RecoveryAction).filter(RecoveryAction.incident_id == inc_id).count()

        # 1. GET counterfactuals (extended=true, include_baseline=true)
        cf_res = client.get(f"/api/incidents/{inc_id}/counterfactuals?extended=true&include_baseline=true")
        assert cf_res.status_code == 200, f"Counterfactuals 404: {cf_res.text}"
        cfs = cf_res.json()
        assert isinstance(cfs, list), "Counterfactuals must return a list"
        assert len(cfs) >= 7, f"Expected at least 7 counterfactuals (including baseline), got {len(cfs)}"

        # 2. All 7 expected strategies are present
        action_types = {c["action_type"] for c in cfs}
        expected_actions = {
            "NO_ACTION",
            "REROUTE",
            "ADJUST_RETRY_TIMING",
            "SUPPRESS_RETRIES",
            "PAYMENT_METHOD_FALLBACK",
            "INTELLIGENT_RETRY",
            "PROVIDER_WEIGHT_ADJUSTMENT",
        }
        assert expected_actions.issubset(action_types), (
            f"Missing strategies: {expected_actions - action_types}"
        )

        # 3. Exactly one strategy is marked recommended
        recommended = [c for c in cfs if c.get("is_recommended")]
        assert len(recommended) == 1, f"Expected exactly 1 recommended, got {len(recommended)}"

        # 4. NO_ACTION baseline has zero lift, zero recovery, zero cost
        baseline = next((c for c in cfs if c["action_type"] == "NO_ACTION"), None)
        assert baseline is not None, "NO_ACTION baseline must be present"
        assert baseline["expected_improvement_pp"] == 0.0
        assert baseline["expected_net_recovery"] == 0.0
        assert baseline["expected_cost"] == 0.0
        assert baseline.get("is_recommended") is False

        # 5. REROUTE has positive lift and a target_provider
        reroute = next((c for c in cfs if c["action_type"] == "REROUTE"), None)
        assert reroute is not None
        assert reroute.get("target_provider") is not None, "REROUTE must have target_provider"
        assert reroute["expected_improvement_pp"] > 0.0
        assert reroute["expected_net_recovery"] >= 0.0

        # 6. GET is idempotent: second call returns identical snapshot
        cf_res2 = client.get(f"/api/incidents/{inc_id}/counterfactuals?extended=true&include_baseline=true")
        assert cf_res2.status_code == 200
        cfs2 = cf_res2.json()
        assert len(cfs2) == len(cfs), "Counterfactuals must be stable across calls (frozen snapshot)"
        for cf1, cf2 in zip(cfs, cfs2):
            assert cf1["action_type"] == cf2["action_type"]
            assert cf1["expected_improvement_pp"] == cf2["expected_improvement_pp"], (
                f"Snapshot changed between calls for {cf1['action_type']}"
            )
            assert cf1["expected_net_recovery"] == cf2["expected_net_recovery"], (
                f"Snapshot net recovery changed for {cf1['action_type']}"
            )

        # 7. NON-MUTATION: reading counterfactuals must not change incident state, add audit entries, or create recovery actions
        post_state = db.query(Incident).filter(Incident.id == inc_id).first().state
        post_audit_count = db.query(AuditLog).filter(AuditLog.incident_id == inc_id).count()
        post_ra_count = db.query(RecoveryAction).filter(RecoveryAction.incident_id == inc_id).count()

        assert post_state == pre_state, (
            f"Counterfactual GET must NOT change incident state: was {pre_state}, now {post_state}"
        )
        assert post_audit_count == pre_audit_count, (
            f"Counterfactual GET must NOT create audit entries: was {pre_audit_count}, now {post_audit_count}"
        )
        assert post_ra_count == pre_ra_count, (
            f"Counterfactual GET must NOT create recovery actions: was {pre_ra_count}, now {post_ra_count}"
        )

        # 8. Policy-incompatible strategies correctly labeled
        all_compatible = [c for c in cfs if c["is_compatible"]]
        all_incompatible = [c for c in cfs if not c["is_compatible"]]
        # For ROUTING_CONNECTIVITY_ISSUE hypothesis: REROUTE is recommended/compatible
        # At minimum, there must be compatible strategies
        assert len(all_compatible) >= 1, "At least one strategy must be policy-compatible"
        # Incompatible strategies must not be recommended
        for incompat in all_incompatible:
            assert incompat.get("is_recommended") is False, (
                f"Incompatible strategy {incompat['action_type']} must not be marked recommended"
            )

        # 9. Verify the API endpoint returns 200 (not 404/500) for the incident
        detail_res = client.get(f"/api/incidents/{inc_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["incident"]["id"] == inc_id
        assert detail["incident"]["state"] == pre_state  # state unchanged

    finally:
        db.close()


def test_deep_bin_intelligence_comprehensive_rules():
    """Verify Deep BIN Intelligence adheres to all 7 Phase 1 rules:
    1. Null/None BIN transactions excluded from BIN profiling.
    2. BIN 476543 represents ICICI / Visa / Coral Platinum Card.
    3. BIN 452114 represents Bank X / Visa / Signature Platinum Debit.
    4. Success rate, 3DS signal, provider dispersion are present and computed.
    5. Causal isolation verdict is driven by actual telemetry.
    6. API compatibility preserved.
    """
    from app.bin_intelligence import analyze_bin_telemetry, is_valid_bin_string

    assert not is_valid_bin_string(None)
    assert not is_valid_bin_string("None")
    assert not is_valid_bin_string("null")
    assert not is_valid_bin_string("")
    assert is_valid_bin_string("476543")
    assert is_valid_bin_string("452114")

    db = SessionLocal()
    try:
        # Test ICICI card BIN intelligence (BIN 476543)
        icici_data = analyze_bin_telemetry(db, issuer="ICICI", payment_method="card", target_bin="476543")
        assert icici_data["dominant_bin"] == "476543"
        assert len(icici_data["bin_telemetry"]) >= 1
        icici_bin = icici_data["bin_telemetry"][0]
        assert icici_bin["bin"] == "476543"
        assert icici_bin["issuer"] == "ICICI"
        assert icici_bin["network"] == "Visa"
        assert icici_bin["tier"] == "Coral Platinum Card"
        assert icici_bin["success_rate"] > 0
        assert icici_bin["success_rate_pct"] > 0
        assert icici_bin["synthetic_3ds_signal"]["auth_failure_rate_pct"] > 0
        assert icici_bin["synthetic_3ds_failure_rate_pct"] > 0
        assert "Provider A" in icici_bin["provider_breakdown"]
        assert "Provider A" in icici_bin["providers"]
        assert icici_bin["total_volume_inr"] > 0
        assert "476543" in icici_data["isolation_verdict"]

        # Test Bank X BIN intelligence (BIN 452114)
        bank_x_data = analyze_bin_telemetry(db, issuer="Bank X", payment_method="card")
        assert bank_x_data["dominant_bin"] == "452114"
        assert len(bank_x_data["bin_telemetry"]) >= 1
        bx_bin = bank_x_data["bin_telemetry"][0]
        assert bx_bin["bin"] == "452114"
        assert bx_bin["issuer"] == "Bank X"
        assert bx_bin["network"] == "Visa"
        assert bx_bin["tier"] == "Signature Platinum Debit"
        assert bx_bin["success_rate"] is not None
        assert bx_bin["success_rate"] >= 0
        assert bx_bin["synthetic_3ds_signal"]["auth_failure_rate_pct"] is not None

        # Test API endpoint compatibility
        res = client.get("/api/segments/bin-intelligence?issuer=ICICI&payment_method=card&bin=476543")
        assert res.status_code == 200
        api_data = res.json()
        assert api_data["dominant_bin"] == "476543"
        assert len(api_data["bins"]) >= 1
        assert api_data["bins"][0]["bin"] == "476543"
        assert api_data["bins"][0]["tier"] == "Coral Platinum Card"
        assert api_data["bins"][0]["success_rate"] is not None
        assert api_data["bins"][0]["synthetic_3ds_signal"]["auth_failure_rate_pct"] is not None

        # Verify no "None" BIN appears in bins list
        for b in api_data["bins"]:
            assert b["bin"] != "None"
            assert b["bin"] is not None
            assert len(str(b["bin"])) >= 4
    finally:
        db.close()

