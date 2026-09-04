from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction
from app.recovery_agent import execute_recovery


def test_human_approval_flow():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    db = TestingSessionLocal()

    now = datetime.now()
    window_start = now - timedelta(minutes=10)
    window_end = now

    incident = Incident(
        id="test_human_approval",
        segment_issuer="TEST_BANK",
        segment_payment_method="card",
        window_start=window_start,
        window_end=window_end,
        baseline_success_rate=95.0,
        incident_success_rate=40.0,
        drop_pp=55.0,
        concentration_ratio=0.80,
        sample_size=20,
        state="DIAGNOSED",
    )

    diagnosis = Diagnosis(
        id="diag_human_approval",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.85,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.80,
        evidence_json="{}",
        narrative_text="High-confidence routing issue.",
    )

    db.add(incident)
    db.add(diagnosis)

    for i in range(20):
        is_failure = i >= 8

        db.add(
            Transaction(
                id=f"test_tx_{i}",
                merchant_id="test_merchant",
                amount=50_000.0,
                timestamp=now,
                payment_method="card",
                issuer="TEST_BANK",
                card_network="visa",
                decline_code="processor_declined" if is_failure else None,
                decline_reason="test" if is_failure else None,
                retry_count=0,
                customer_id=f"customer_{i}",
                routing_partner="test_router",
                success=not is_failure,
            )
        )

    db.commit()

    # First attempt: no human approval.
    first = execute_recovery(
        db,
        incident.id,
        {
            "recommended_action": "REROUTE",
            "selected_by": "llm",
            "human_approved": False,
        },
    )

    assert first["status"] == "pending_human_approval"
    assert incident.state == "AWAITING_HUMAN_APPROVAL"

    # Second attempt: explicit human approval.
    second = execute_recovery(
        db,
        incident.id,
        {
            "recommended_action": "REROUTE",
            "selected_by": "llm",
            "human_approved": True,
        },
    )

    assert second["status"] == "RESOLVED"
    assert second["recovered_revenue"] > 0
