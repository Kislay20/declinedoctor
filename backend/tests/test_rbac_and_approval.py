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
