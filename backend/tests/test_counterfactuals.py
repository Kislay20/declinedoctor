from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction
from app.recovery_agent import compute_counterfactuals


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_counterfactual_action_comparison():
    db = make_db()
    now = datetime.now()
    incident = Incident(
        id="inc_cf_test",
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
        id="diag_cf_test",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.85,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.80,
        evidence_json="{}",
    ))

    # Add 10 failed transactions at ₹10,000 each = ₹100,000 failed
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
    # Add 10 successful transactions at ₹10,000 each
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

    cfs = compute_counterfactuals(db, "inc_cf_test")
    assert len(cfs) == 3

    cf_dict = {c["action_type"]: c for c in cfs}

    # REROUTE: effect size 0.42 -> 10 * 0.42 = 4 transactions flipped -> ₹40,000
    reroute = cf_dict["REROUTE"]
    assert reroute["transactions_affected"] == 4
    assert reroute["expected_recovered_revenue"] == 40_000.0
    assert reroute["is_compatible"] is True
    assert reroute["is_recommended"] is True

    # ADJUST_RETRY_TIMING: effect size 0.21 -> 10 * 0.21 = 2 transactions flipped -> ₹20,000
    timing = cf_dict["ADJUST_RETRY_TIMING"]
    assert timing["transactions_affected"] == 2
    assert timing["expected_recovered_revenue"] == 20_000.0
    assert timing["is_compatible"] is False

    # SUPPRESS_RETRIES: effect size 0.0 -> 0 transactions flipped -> ₹0
    suppress = cf_dict["SUPPRESS_RETRIES"]
    assert suppress["transactions_affected"] == 0
    assert suppress["expected_recovered_revenue"] == 0.0
