from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.database import Base
from app.models import Incident, Diagnosis, Transaction, RecoveryAction
from app.recovery_agent import execute_recovery
from app.policy import can_approve_recovery, UserRole, check_recovery_safety


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_high_value_case(db):
    now = datetime.now()
    incident = Incident(
        id="inc_high_val",
        detected_at=now,
        segment_issuer="ICICI",
        segment_payment_method="card",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        baseline_success_rate=95.0,
        incident_success_rate=50.0,
        drop_pp=45.0,
        concentration_ratio=0.85,
        sample_size=100,
        state="DIAGNOSED",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_high_val",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.85,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.85,
        evidence_json="{}",
    ))
    # Revenue > ₹500,000 (10 transactions * ₹60,000 = ₹600,000)
    for i in range(10):
        db.add(Transaction(
            id=f"tx_fail_{i}",
            merchant_id="m",
            amount=60_000.0,
            timestamp=now,
            payment_method="card",
            issuer="ICICI",
            success=False,
            retry_count=0,
        ))
    for i in range(10):
        db.add(Transaction(
            id=f"tx_succ_{i}",
            merchant_id="m",
            amount=10_000.0,
            timestamp=now,
            payment_method="card",
            issuer="ICICI",
            success=True,
            retry_count=0,
        ))
    db.commit()
    return incident


def test_rbac_role_definitions():
    assert can_approve_recovery("ADMIN") is True
    assert can_approve_recovery("OPERATOR") is True
    assert can_approve_recovery("ANALYST") is False
    assert can_approve_recovery("VIEWER") is False


def test_unapproved_high_value_moves_to_awaiting_approval():
    db = make_db()
    make_high_value_case(db)

    result = execute_recovery(db, "inc_high_val", {
        "recommended_action": "REROUTE",
        "human_approved": False,
    })

    assert result["status"] == "pending_human_approval"
    inc = db.query(Incident).filter(Incident.id == "inc_high_val").first()
    assert inc.state == "AWAITING_HUMAN_APPROVAL"


def test_unauthorized_role_cannot_approve():
    db = make_db()
    make_high_value_case(db)

    result = execute_recovery(
        db,
        "inc_high_val",
        {
            "recommended_action": "REROUTE",
            "human_approved": True,
            "role": "VIEWER",
            "selected_by": "guest_viewer",
        },
        user_role="VIEWER",
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "unauthorized_role"


def test_authorized_role_approval_executes_recovery():
    db = make_db()
    make_high_value_case(db)

    result = execute_recovery(
        db,
        "inc_high_val",
        {
            "recommended_action": "REROUTE",
            "human_approved": True,
            "role": "OPERATOR",
            "selected_by": "lead_operator",
        },
        user_role="OPERATOR",
        operator_name="lead_operator",
    )

    assert result["status"] == "RESOLVED"
    action = db.query(RecoveryAction).filter(RecoveryAction.incident_id == "inc_high_val").first()
    assert action.approved_by == "lead_operator"
    assert action.role == "OPERATOR"
    assert action.approved_at is not None


def make_standard_case(db):
    now = datetime.now()
    incident = Incident(
        id="inc_std_case",
        detected_at=now,
        segment_issuer="Bank X",
        segment_payment_method="card",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        baseline_success_rate=95.0,
        incident_success_rate=55.0,
        drop_pp=40.0,
        concentration_ratio=0.85,
        sample_size=100,
        state="DIAGNOSED",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_std_case",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.75,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.85,
        evidence_json="{}",
    ))
    # Revenue ₹150,000 (10 failures * ₹15,000) -> >= ₹50k and <= ₹500k
    for i in range(10):
        db.add(Transaction(
            id=f"tx_std_fail_{i}",
            merchant_id="m",
            amount=15_000.0,
            timestamp=now,
            payment_method="card",
            issuer="Bank X",
            success=False,
            retry_count=0,
        ))
    for i in range(10):
        db.add(Transaction(
            id=f"tx_std_succ_{i}",
            merchant_id="m",
            amount=15_000.0,
            timestamp=now,
            payment_method="card",
            issuer="Bank X",
            success=True,
            retry_count=0,
        ))
    db.commit()
    return incident


def test_admin_standard_recovery_allowed():
    db = make_db()
    make_standard_case(db)
    res = execute_recovery(db, "inc_std_case", {
        "recommended_action": "REROUTE",
        "human_approved": False,
        "role": "ADMIN",
    }, user_role="ADMIN")
    assert res["status"] == "RESOLVED"
    assert res["recovered_revenue"] > 0


def test_operator_standard_recovery_allowed():
    db = make_db()
    make_standard_case(db)
    res = execute_recovery(db, "inc_std_case", {
        "recommended_action": "REROUTE",
        "human_approved": False,
        "role": "OPERATOR",
    }, user_role="OPERATOR")
    assert res["status"] == "RESOLVED"
    assert res["recovered_revenue"] > 0


def test_analyst_standard_recovery_blocked():
    db = make_db()
    make_standard_case(db)
    res = execute_recovery(db, "inc_std_case", {
        "recommended_action": "REROUTE",
        "human_approved": False,
        "role": "ANALYST",
    }, user_role="ANALYST")
    assert res["status"] == "blocked"
    assert res["reason"] == "unauthorized_role"


def test_viewer_standard_recovery_blocked():
    db = make_db()
    make_standard_case(db)
    res = execute_recovery(db, "inc_std_case", {
        "recommended_action": "REROUTE",
        "human_approved": False,
        "role": "VIEWER",
    }, user_role="VIEWER")
    assert res["status"] == "blocked"
    assert res["reason"] == "unauthorized_role"


def test_analyst_cannot_approve_high_value():
    db = make_db()
    make_high_value_case(db)
    res = execute_recovery(db, "inc_high_val", {
        "recommended_action": "REROUTE",
        "human_approved": True,
        "role": "ANALYST",
    }, user_role="ANALYST")
    assert res["status"] == "blocked"
    assert res["reason"] == "unauthorized_role"


def test_admin_high_value_approval_allowed():
    db = make_db()
    make_high_value_case(db)
    res = execute_recovery(db, "inc_high_val", {
        "recommended_action": "REROUTE",
        "human_approved": True,
        "role": "ADMIN",
        "selected_by": "lead_admin",
    }, user_role="ADMIN")
    assert res["status"] == "RESOLVED"
    assert res["recovered_revenue"] > 0


def test_safety_check_rbac_gating():
    # Standard case
    safety_admin = check_recovery_safety(
        incident_state="DIAGNOSED",
        confidence=0.75,
        at_risk_revenue=150000.0,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        action="REROUTE",
        user_role="ADMIN",
    )
    assert safety_admin["status"] == "SAFE_TO_EXECUTE"
    assert safety_admin["user_authorized"] is True

    safety_operator = check_recovery_safety(
        incident_state="DIAGNOSED",
        confidence=0.75,
        at_risk_revenue=150000.0,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        action="REROUTE",
        user_role="OPERATOR",
    )
    assert safety_operator["status"] == "SAFE_TO_EXECUTE"
    assert safety_operator["user_authorized"] is True

    safety_analyst = check_recovery_safety(
        incident_state="DIAGNOSED",
        confidence=0.75,
        at_risk_revenue=150000.0,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        action="REROUTE",
        user_role="ANALYST",
    )
    assert safety_analyst["status"] == "AUTOMATED_RECOVERY_BLOCKED"
    assert safety_analyst["user_authorized"] is False

    safety_viewer = check_recovery_safety(
        incident_state="DIAGNOSED",
        confidence=0.75,
        at_risk_revenue=150000.0,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        action="REROUTE",
        user_role="VIEWER",
    )
    assert safety_viewer["status"] == "AUTOMATED_RECOVERY_BLOCKED"
    assert safety_viewer["user_authorized"] is False


def test_approval_center_projection_consistency_with_counterfactuals():
    """Regression test: Human Approval Center projected lift, gross recovery, net recovery,
    action, and target provider must exactly match the frozen recommended counterfactual,
    and must not mutate upon subsequent live transactions.
    """
    import json
    from app.routes.incidents import get_incident_detail
    from app.recovery_agent import compute_counterfactuals
    from app.models import AuditLog

    db = make_db()
    incident = make_high_value_case(db)

    # 1. Compute initial frozen counterfactuals snapshot
    cfs = compute_counterfactuals(db, incident.id, include_extended=True, include_baseline=False)
    frozen_rec = next(c for c in cfs if c.get("is_recommended"))

    # Assert basic expectations on the frozen counterfactual recommendation
    assert frozen_rec["action_type"] == "REROUTE"
    assert frozen_rec["target_provider"] == "Provider A"
    assert frozen_rec["expected_improvement_pp"] > 0
    assert frozen_rec["expected_recovered_revenue"] > 0
    assert frozen_rec["expected_net_recovery"] > 0

    # 2. Query incident detail (the endpoint consumed by human approval center)
    detail = get_incident_detail(incident.id, db)
    rec_approval = detail.get("recommended_recovery")
    assert rec_approval is not None

    # Strict consistency: approval center projected values match frozen recommended counterfactual
    assert rec_approval["action_type"] == frozen_rec["action_type"]
    assert rec_approval["target_provider"] == frozen_rec["target_provider"]
    assert rec_approval["expected_improvement_pp"] == frozen_rec["expected_improvement_pp"]
    assert rec_approval["expected_recovered_revenue"] == frozen_rec["expected_recovered_revenue"]
    assert rec_approval["expected_net_recovery"] == frozen_rec["expected_net_recovery"]
    assert detail["proposed_action"] == frozen_rec["action_type"]

    # 3. Inject live/mutated transactions after diagnosis
    now = datetime.now()
    for i in range(5):
        db.add(Transaction(
            id=f"tx_late_fail_{i}",
            merchant_id="m",
            amount=85_000.0,
            timestamp=now,
            payment_method="card",
            issuer="ICICI",
            success=False,
            retry_count=0,
        ))
    db.commit()

    # Re-verify that incident detail and counterfactuals do NOT recalculate from live transaction state
    detail_post = get_incident_detail(incident.id, db)
    rec_post = detail_post["recommended_recovery"]
    assert rec_post["expected_improvement_pp"] == frozen_rec["expected_improvement_pp"]
    assert rec_post["expected_recovered_revenue"] == frozen_rec["expected_recovered_revenue"]
    assert rec_post["expected_net_recovery"] == frozen_rec["expected_net_recovery"]

    # 4. Execute dual-control approval passing authoritative projection payload
    approval_payload = {
        "recommended_action": rec_approval["action_type"],
        "target_provider": rec_approval["target_provider"],
        "projected_lift_pp": rec_approval["expected_improvement_pp"],
        "projected_gross_recovery": rec_approval["expected_recovered_revenue"],
        "projected_net_recovery": rec_approval["expected_net_recovery"],
        "human_approved": True,
        "role": "ADMIN",
        "selected_by": "operator_admin",
    }
    result = execute_recovery(db, incident.id, approval_payload, user_role="ADMIN")
    assert result["status"] == "RESOLVED"

    # 5. Verify ACTION_SELECTED audit log contains authoritative projection fields
    audit_action = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident.id, AuditLog.event_type == "ACTION_SELECTED")
        .first()
    )
    assert audit_action is not None
    details = json.loads(audit_action.details_json)
    assert details["action"] == frozen_rec["action_type"]
    assert details["target_provider"] == frozen_rec["target_provider"]
    assert details["projected_lift_pp"] == round(frozen_rec["expected_improvement_pp"], 2)
    assert details["projected_gross_recovery"] == round(frozen_rec["expected_recovered_revenue"], 2)
    assert details["projected_net_recovery"] == round(frozen_rec["expected_net_recovery"], 2)
    assert details["human_approved"] is True


def test_freshly_seeded_rejection_incident_resolution_across_all_endpoints():
    """Regression test: Proves that a freshly seeded rejection-test incident can be retrieved
    through:
    - /api/incidents/{id}
    - /counterfactuals
    - /explanation
    - /safety
    - /audit
    both in fresh ANOMALY_DETECTED state and after diagnosis / rejection.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from scripts.seed_rejection_incident import seed_rejection_incident
    from app.database import SessionLocal

    # 1. Seed the canonical rejection test incident
    db = SessionLocal()
    try:
        inc = seed_rejection_incident(db)
        incident_id = inc.id
    finally:
        db.close()

    client = TestClient(app)

    # 2. Verify all 5 endpoints resolve the freshly seeded incident (ANOMALY_DETECTED)
    # /api/incidents/{id}
    res_detail = client.get(f"/api/incidents/{incident_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["incident"]["id"] == incident_id
    assert detail_data["incident"]["state"] == "ANOMALY_DETECTED"
    assert detail_data["incident"]["at_risk_revenue"] > 500_000

    # /counterfactuals
    res_cf = client.get(f"/api/incidents/{incident_id}/counterfactuals?extended=true&include_baseline=true")
    assert res_cf.status_code == 200
    assert isinstance(res_cf.json(), list)

    # /explanation
    res_exp = client.get(f"/api/incidents/{incident_id}/explanation")
    assert res_exp.status_code == 200
    exp_data = res_exp.json()
    assert exp_data["incident_id"] == incident_id
    assert "questions" in exp_data

    # /safety
    res_safe = client.get(f"/api/incidents/{incident_id}/safety")
    assert res_safe.status_code == 200
    safe_data = res_safe.json()
    assert safe_data["status"] == "RECOVERY_NOT_YET_EVALUATED"
    assert safe_data["revenue_ceiling_check"]["requires_approval"] is True

    # /audit
    res_audit = client.get(f"/api/incidents/{incident_id}/audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert len(audit_data) >= 1
    assert audit_data[0]["event_type"] == "ANOMALY_DETECTED"

    # /audit/verify
    res_verify = client.get(f"/api/incidents/{incident_id}/audit/verify")
    assert res_verify.status_code == 200
    assert res_verify.json()["valid"] is True

    # 3. Diagnose the incident
    res_diag = client.post(f"/api/incidents/{incident_id}/diagnose")
    assert res_diag.status_code == 200
    diag_data = res_diag.json()
    assert diag_data["diagnosis"]["confidence"] >= 0.70

    # 4. Verify endpoints after diagnosis: counterfactuals and approval gating active
    res_cf_post = client.get(f"/api/incidents/{incident_id}/counterfactuals?extended=true&include_baseline=true")
    assert res_cf_post.status_code == 200
    cfs = res_cf_post.json()
    assert len(cfs) > 0

    res_safe_post = client.get(f"/api/incidents/{incident_id}/safety")
    assert res_safe_post.status_code == 200
    safe_post = res_safe_post.json()
    assert safe_post["status"] == "HUMAN_APPROVAL_REQUIRED"
    assert safe_post["revenue_ceiling_check"]["requires_approval"] is True

    # 5. Reject the proposal through the human rejection branch
    res_reject = client.post(
        f"/api/incidents/{incident_id}/reject",
        json={"reason": "Operator rejected mitigation during review", "role": "OPERATOR", "operator_name": "lead_operator"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "APPROVAL_REJECTED"

    # 6. Verify terminal state preserved across endpoints
    res_detail_term = client.get(f"/api/incidents/{incident_id}")
    assert res_detail_term.status_code == 200
    assert res_detail_term.json()["incident"]["state"] == "APPROVAL_REJECTED"

    res_audit_term = client.get(f"/api/incidents/{incident_id}/audit")
    assert res_audit_term.status_code == 200
    event_types = [a["event_type"] for a in res_audit_term.json()]
    assert "APPROVAL_REJECTED" in event_types

    # 7. Verify non-existent incident returns 404 uniformly across all endpoints
    for suffix in ["", "/counterfactuals", "/explanation", "/safety", "/audit", "/audit/verify"]:
        res_404 = client.get(f"/api/incidents/non_existent_inc_123{suffix}")
        assert res_404.status_code == 404
        assert res_404.json()["detail"] == "Incident not found"


def test_rejection_incident_bin_intelligence_derived_from_transaction_evidence():
    """Regression test proving the rejection-test incident's BIN intelligence comes
    from its canonical transaction evidence (seeded BIN 476543) rather than a hardcoded default 452114,
    while preserving Bank X BIN 452114 behavior, SBI netbanking behavior, and terminal immutability.
    """
    import json
    from fastapi.testclient import TestClient
    from app.main import app
    from scripts.seed_rejection_incident import seed_rejection_incident
    from app.database import SessionLocal
    from app.bin_intelligence import analyze_bin_telemetry

    db = SessionLocal()
    try:
        inc = seed_rejection_incident(db)
        incident_id = inc.id

        # 1. Direct function call to analyze_bin_telemetry with incident_id
        bin_data = analyze_bin_telemetry(db, incident_id=incident_id)
        assert bin_data["dominant_bin"] == "476543", f"Expected dominant BIN 476543, got {bin_data['dominant_bin']}"
        assert bin_data["is_isolated_to_single_bin"] is True
        assert len(bin_data["bin_telemetry"]) >= 1

        primary = bin_data["bin_telemetry"][0]
        assert primary["bin"] == "476543"
        assert primary["tier"] == "Coral Platinum Card"
        assert primary["failure_concentration_share_pct"] == 100.0
        assert primary["failures"] == 55
        assert primary["synthetic_3ds_failure_rate_pct"] == 16.0
        assert "476543" in bin_data["isolation_summary"]
        assert "Coral Platinum Card" in bin_data["isolation_summary"]

        # 2. Existing Bank X default BIN 452114 behavior must remain unchanged
        bank_x_data = analyze_bin_telemetry(db, issuer="Bank X", payment_method="card")
        assert bank_x_data["dominant_bin"] == "452114"
        assert bank_x_data["bin_telemetry"][0]["tier"] == "Signature Platinum Debit"

        # 3. Existing SBI netbanking behavior must remain unchanged
        sbi_data = analyze_bin_telemetry(db, issuer="SBI", payment_method="netbanking")
        assert sbi_data["payment_method"] == "netbanking"
    finally:
        db.close()

    client = TestClient(app)

    # 4. API endpoint verification for rejection test incident
    res_bin_api = client.get(f"/api/segments/bin-intelligence?incident_id={incident_id}&issuer=ICICI&payment_method=card")
    assert res_bin_api.status_code == 200
    api_json = res_bin_api.json()
    assert api_json["dominant_bin"] == "476543"
    assert api_json["is_isolated_to_single_bin"] is True
    assert api_json["bin_telemetry"][0]["tier"] == "Coral Platinum Card"
    assert api_json["bin_telemetry"][0]["failure_concentration_share_pct"] == 100.0
    assert api_json["bin_telemetry"][0]["synthetic_3ds_failure_rate_pct"] == 16.0

    # 5. API endpoint verification for Bank X remains unchanged
    res_bank_x = client.get("/api/segments/bin-intelligence?issuer=Bank+X&payment_method=card")
    assert res_bank_x.status_code == 200
    assert res_bank_x.json()["dominant_bin"] == "452114"

    # 6. Provider routing recommendation evaluates actual incident BIN 476543
    res_routing = client.get(f"/api/providers/routing/recommendation?incident_id={incident_id}&issuer=ICICI&payment_method=card")
    assert res_routing.status_code == 200
    r_json = res_routing.json()
    assert r_json["segment_evaluated"]["bin"] == "476543"
    assert r_json["recommended_provider"] is not None

    # 7. Diagnose produces causal evidence grounded in BIN 476543
    res_diag = client.post(f"/api/incidents/{incident_id}/diagnose")
    assert res_diag.status_code == 200
    diag_data = res_diag.json()
    ev_json = json.loads(diag_data["diagnosis"]["evidence_json"])
    assert ev_json["bin_intelligence"]["dominant_bin"] == "476543"
    assert ev_json["bin_intelligence"]["is_isolated_to_single_bin"] is True
    assert ev_json["causal_evidence"]["bin_evidence"]["dominant_bin"] == "476543"
    assert ev_json["causal_evidence"]["bin_evidence"]["is_isolated_to_single_bin"] is True

    # 8. Terminal state immutability: Rejection keeps state terminal without reopening
    res_reject = client.post(
        f"/api/incidents/{incident_id}/reject",
        json={"reason": "Operator reject test", "role": "OPERATOR"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "APPROVAL_REJECTED"

    # Further diagnosis or recovery attempts must not modify terminal state
    res_diag_term = client.post(f"/api/incidents/{incident_id}/diagnose")
    assert res_diag_term.status_code == 200
    assert res_diag_term.json()["is_terminal"] is True

    res_detail_final = client.get(f"/api/incidents/{incident_id}")
    assert res_detail_final.status_code == 200
    assert res_detail_final.json()["incident"]["state"] == "APPROVAL_REJECTED"


def test_dual_control_approval_queue_canonical_predicate_and_endpoints():
    """Regression test for Dual-Control Approval Queue:
    1. High-value diagnosed incident appears in queue.
    2. Low-value diagnosed incident (< ₹500,000) is excluded.
    3. Low-confidence incident is excluded.
    4. Terminal/rejected incident (APPROVAL_REJECTED) is permanently excluded.
    5. Terminal states are excluded.
    6. Queue GET is strictly non-mutating (no state change, no audit entry, no recovery action).
    7. Queue data matches IncidentView's authoritative approval requirement.
    8. No duplicate queue entries.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import SessionLocal
    from app.models import Incident, AuditLog, RecoveryAction
    from app.policy import (
        is_incident_pending_dual_control_approval,
        get_dual_control_approval_queue,
        TERMINAL_STATES,
    )

    client = TestClient(app)
    db = SessionLocal()
    try:
        # Resolve active high-value ICICI incident in the DB
        inc_icici = db.query(Incident).filter(
            Incident.segment_issuer == "ICICI",
            Incident.segment_payment_method == "card",
            ~Incident.state.in_(TERMINAL_STATES),
        ).first()
        assert inc_icici is not None, "Active high-value ICICI incident must exist in DB"

        # If not yet diagnosed, run diagnose to populate diagnosis evidence
        if inc_icici.state == "ANOMALY_DETECTED":
            client.post(f"/api/incidents/{inc_icici.id}/diagnose")
            db.refresh(inc_icici)

        # Pre-state capture for non-mutation verification
        pre_state = inc_icici.state
        pre_audit_count = db.query(AuditLog).filter(AuditLog.incident_id == inc_icici.id).count()
        pre_ra_count = db.query(RecoveryAction).filter(RecoveryAction.incident_id == inc_icici.id).count()

        # 1. Test canonical predicate directly
        inc_bx = db.query(Incident).filter(Incident.segment_issuer == "Bank X").first()
        inc_sbi = db.query(Incident).filter(Incident.segment_issuer == "SBI").first()
        inc_rej = db.query(Incident).filter(Incident.state == "APPROVAL_REJECTED").first()

        assert is_incident_pending_dual_control_approval(db, inc_icici) is True, "High-value ICICI must require approval"
        if inc_bx:
            assert is_incident_pending_dual_control_approval(db, inc_bx) is False, "Bank X (< ₹500k) must be excluded"
        if inc_sbi:
            assert is_incident_pending_dual_control_approval(db, inc_sbi) is False, "SBI (low conf/no diag) must be excluded"
        if inc_rej:
            assert is_incident_pending_dual_control_approval(db, inc_rej) is False, "Terminal APPROVAL_REJECTED must be excluded"

        # 2. Test queue via canonical service
        queue = get_dual_control_approval_queue(db)
        queue_ids = [item["incident_id"] for item in queue]

        # No duplicates guarantee
        assert len(queue_ids) == len(set(queue_ids)), "Queue must contain no duplicate entries"

        # High-value incident present with required attributes
        assert inc_icici.id in queue_ids, f"{inc_icici.id} must be in approval queue"
        icici_item = next(item for item in queue if item["incident_id"] == inc_icici.id)
        assert icici_item["segment_issuer"] == "ICICI"
        assert icici_item["segment_payment_method"] == "card"
        assert icici_item["revenue_at_risk"] > 500_000.0
        assert icici_item["at_risk_revenue"] > 500_000.0
        assert icici_item["hypothesis"] == "ROUTING_CONNECTIVITY_ISSUE"
        assert icici_item["proposed_action"] == "REROUTE"
        assert icici_item["target_provider"] == "Provider A"
        assert icici_item["confidence"] >= 0.70
        assert icici_item["projected_lift_pp"] > 0
        assert icici_item["projected_net_recovery"] > 0

        # Exclusions
        if inc_bx:
            assert inc_bx.id not in queue_ids, "Bank X must NOT appear in approval queue"
        if inc_sbi:
            assert inc_sbi.id not in queue_ids, "SBI must NOT appear in approval queue"
        if inc_rej:
            assert inc_rej.id not in queue_ids, "Terminal rejection must NOT appear in approval queue"

        # 3. Test GET /api/dashboard/summary endpoint
        sum_res = client.get("/api/dashboard/summary")
        assert sum_res.status_code == 200
        summary_data = sum_res.json()
        assert "approval_queue" in summary_data
        dash_queue = summary_data["approval_queue"]
        assert len(dash_queue) >= 1, "Dashboard approval_queue count must be >= 1"
        assert any(item["incident_id"] == inc_icici.id for item in dash_queue)
        if inc_bx:
            assert not any(item["incident_id"] == inc_bx.id for item in dash_queue)
        if inc_sbi:
            assert not any(item["incident_id"] == inc_sbi.id for item in dash_queue)
        if inc_rej:
            assert not any(item["incident_id"] == inc_rej.id for item in dash_queue)

        # 4. Test dedicated GET /api/incidents/approval-queue endpoint
        q_res = client.get("/api/incidents/approval-queue")
        assert q_res.status_code == 200
        q_data = q_res.json()
        assert len(q_data) >= 1
        assert any(item["incident_id"] == inc_icici.id for item in q_data)

        # 5. Non-mutation verification: queue read did not alter DB state
        db.refresh(inc_icici)
        assert inc_icici.state == pre_state, "Reading queue must NOT change incident state"
        post_audit_count = db.query(AuditLog).filter(AuditLog.incident_id == inc_icici.id).count()
        assert post_audit_count == pre_audit_count, "Reading queue must NOT create audit entries"
        post_ra_count = db.query(RecoveryAction).filter(RecoveryAction.incident_id == inc_icici.id).count()
        assert post_ra_count == pre_ra_count, "Reading queue must NOT create recovery actions"

        # 6. Verify IncidentView safety policy matches approval queue verdict
        safety_res = client.get(f"/api/incidents/{inc_icici.id}/safety")
        assert safety_res.status_code == 200
        safety_json = safety_res.json()
        assert safety_json["status"] == "HUMAN_APPROVAL_REQUIRED"
        assert safety_json["revenue_ceiling_check"]["requires_approval"] is True
    finally:
        db.close()




