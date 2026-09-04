from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction, RecoveryAction
from app.recovery_agent import execute_recovery, execute_rollback


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_rollback_reverts_transactions_and_state():
    db = make_db()
    now = datetime.now()
    incident = Incident(
        id="inc_rb_test",
        detected_at=now,
        segment_issuer="Bank X",
        segment_payment_method="card",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        baseline_success_rate=95.0,
        incident_success_rate=50.0,
        drop_pp=45.0,
        concentration_ratio=0.80,
        sample_size=100,
        state="DIAGNOSED",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_rb_test",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.85,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.80,
        evidence_json="{}",
    ))
    # 10 failed transactions at ₹10,000 each = ₹100,000
    for i in range(10):
        db.add(Transaction(
            id=f"tx_fail_{i}",
            merchant_id="m",
            amount=10_000.0,
            timestamp=now,
            payment_method="card",
            issuer="Bank X",
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
            issuer="Bank X",
            success=True,
            retry_count=0,
        ))
    db.commit()

    # Step 1: Execute Recovery
    rec_result = execute_recovery(db, "inc_rb_test", {"recommended_action": "REROUTE"})
    assert rec_result["status"] == "RESOLVED"
    assert incident.state == "RESOLVED"

    # Step 2: Attempt Rollback by Unauthorized Role
    unauth = execute_rollback(
        db,
        "inc_rb_test",
        user_role="VIEWER",
        operator_name="viewer_bob",
        reason="Testing unauthorized rollback",
    )
    assert unauth["status"] == "blocked"
    assert unauth["reason"] == "unauthorized_role"
    assert incident.state == "RESOLVED"

    # Step 3: Execute Rollback by OPERATOR
    rb_result = execute_rollback(
        db,
        "inc_rb_test",
        user_role="OPERATOR",
        operator_name="operator_alice",
        reason="Partner circuit breaker tripped; rolling back",
    )

    assert rb_result["status"] == "ROLLED_BACK"
    assert incident.state == "ROLLED_BACK"
    assert rb_result["reverted_transactions"] == 4
    assert rb_result["reverted_revenue"] == 40_000.0

    # Verify rollback action record exists
    rb_action = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.incident_id == "inc_rb_test", RecoveryAction.is_rollback == True)
        .first()
    )
    assert rb_action is not None
    assert rb_action.action_type == "ROLLBACK"
    assert rb_action.approved_by == "operator_alice"
