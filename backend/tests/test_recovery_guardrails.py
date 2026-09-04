from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction
from app.recovery_agent import execute_recovery


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_case(db, *, revenue, confidence=0.80, hypothesis="ROUTING_CONNECTIVITY_ISSUE", state="DIAGNOSED", retry_count=0):
    now = datetime.now()
    incident = Incident(
        id="inc_test",
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
        state=state,
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_test", incident_id=incident.id, hypothesis=hypothesis,
        confidence=confidence, dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.80, evidence_json="{}"
    ))

    # One failed transaction carrying the requested revenue and enough successful
    # transactions to make the incident rate meaningful.
    db.add(Transaction(
        id="txn_failed", merchant_id="m", amount=revenue, timestamp=now,
        payment_method="card", issuer="Bank X", success=False, retry_count=retry_count
    ))
    db.add(Transaction(
        id="txn_success", merchant_id="m", amount=1000, timestamp=now,
        payment_method="card", issuer="Bank X", success=True, retry_count=0
    ))
    db.commit()
    return incident


def test_low_revenue_blocks_auto_recovery():
    db = make_db()
    make_case(db, revenue=49_999)
    result = execute_recovery(db, "inc_test", {"recommended_action": "REROUTE"})
    assert result["reason"] == "low_revenue"
    assert db.query(Incident).first().state == "ESCALATED_LOW_REVENUE"


def test_high_revenue_requires_human_approval():
    db = make_db()
    make_case(db, revenue=500_001)
    result = execute_recovery(db, "inc_test", {"recommended_action": "REROUTE"})
    assert result["status"] == "pending_human_approval"
    assert db.query(Incident).first().state == "AWAITING_HUMAN_APPROVAL"


def test_incompatible_action_is_rejected_by_backend():
    db = make_db()
    make_case(db, revenue=60_000, hypothesis="ROUTING_CONNECTIVITY_ISSUE")
    try:
        execute_recovery(db, "inc_test", {"recommended_action": "ADJUST_RETRY_TIMING"})
    except ValueError as exc:
        assert "incompatible" in str(exc)
    else:
        raise AssertionError("Incompatible action was not rejected")


def test_terminal_incident_cannot_be_retried_with_alternate_action():
    db = make_db()
    make_case(db, revenue=60_000, state="ESCALATED_INSUFFICIENT_RECOVERY")
    result = execute_recovery(db, "inc_test", {"recommended_action": "REROUTE"})
    assert result["reason"] == "terminal_incident"


def test_retry_budget_is_capped_at_two():
    db = make_db()
    make_case(db, revenue=60_000, retry_count=1)
    result = execute_recovery(db, "inc_test", {"recommended_action": "REROUTE"})
    tx = db.query(Transaction).filter(Transaction.id == "txn_failed").first()
    assert tx.retry_count <= 2
    assert result["status"] in {"RESOLVED", "ESCALATED_INSUFFICIENT_RECOVERY"}
