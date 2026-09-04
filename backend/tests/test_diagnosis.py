import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction, AuditLog
from app.diagnosis import diagnose_incident, TERMINAL_STATES


def make_test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def create_incident_with_txns(
    db,
    *,
    issuer="Bank X",
    method="card",
    baseline=95.0,
    concentration=0.80,
    sample_size=100,
    dominant_code="processor_declined",
    dominant_share=0.85,
    state="ANOMALY_DETECTED",
    total_failures=20
):
    now = datetime.now()
    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    incident = Incident(
        id=incident_id,
        detected_at=now,
        segment_issuer=issuer,
        segment_payment_method=method,
        window_start=now - timedelta(hours=2),
        window_end=now,
        baseline_success_rate=baseline,
        incident_success_rate=50.0,
        drop_pp=45.0,
        concentration_ratio=concentration,
        sample_size=sample_size,
        state=state,
    )
    db.add(incident)

    # Add failure transactions according to dominant share
    dom_count = int(round(total_failures * dominant_share))
    other_count = total_failures - dom_count

    for i in range(dom_count):
        db.add(Transaction(
            id=f"fail_dom_{incident_id}_{i}",
            merchant_id="m1",
            amount=2000.0,
            timestamp=now - timedelta(minutes=30),
            payment_method=method,
            issuer=issuer,
            success=False,
            decline_code=dominant_code,
            decline_reason="Dom decline reason",
            retry_count=0
        ))

    for i in range(other_count):
        db.add(Transaction(
            id=f"fail_oth_{incident_id}_{i}",
            merchant_id="m1",
            amount=2000.0,
            timestamp=now - timedelta(minutes=30),
            payment_method=method,
            issuer=issuer,
            success=False,
            decline_code="try_again_later",
            decline_reason="Other reason",
            retry_count=0
        ))

    db.commit()
    return incident


def test_confidence_formula_calculation():
    """Verify exact formula: 0.5 * concentration + 0.3 * dominant_share + 0.2 * min(sample_size / 150, 1.0)"""
    db = make_test_db()
    # concentration = 0.80 -> 0.40
    # dominant_share = 20 / 20 = 1.0 -> 0.30
    # sample_size = 150 -> factor 1.0 -> 0.20
    # total = 0.40 + 0.30 + 0.20 = 0.90
    inc = create_incident_with_txns(
        db,
        concentration=0.80,
        sample_size=150,
        dominant_code="processor_declined",
        dominant_share=1.0,
        total_failures=20
    )

    diag = diagnose_incident(db, inc.id)
    assert diag is not None
    assert diag.confidence == 0.90
    assert inc.state == "DIAGNOSED"


def test_dominant_decline_mapping():
    """Verify mapping from dominant decline code to hypothesis."""
    db = make_test_db()

    mappings = [
        ("processor_declined", "ROUTING_CONNECTIVITY_ISSUE"),
        ("gateway_timeout", "ROUTING_CONNECTIVITY_ISSUE"),
        ("try_again_later", "BIN_LEVEL_TEMPORARY_ISSUE"),
        ("insufficient_funds", "ISSUER_SIDE_DECLINE"),
        ("do_not_honor", "ISSUER_SIDE_DECLINE"),
        ("unknown_weird_error", "INSUFFICIENT_SIGNAL"),
    ]

    for code, expected_hypothesis in mappings:
        inc = create_incident_with_txns(
            db,
            issuer=f"Bank_{code}",
            dominant_code=code,
            dominant_share=1.0,
            total_failures=10
        )
        diag = diagnose_incident(db, inc.id)
        assert diag.hypothesis == expected_hypothesis, f"Expected {expected_hypothesis} for {code}, got {diag.hypothesis}"


def test_low_confidence_escalation():
    """Verify confidence < 0.70 sets ESCALATED_LOW_CONFIDENCE and logs ESCALATION audit event."""
    db = make_test_db()
    # concentration = 0.50 -> 0.25
    # dominant_share = 0.50 -> 0.15
    # sample_size = 60 / 150 = 0.4 -> 0.08
    # total = 0.48 < 0.70
    inc = create_incident_with_txns(
        db,
        concentration=0.50,
        sample_size=60,
        dominant_code="processor_declined",
        dominant_share=0.50,
        total_failures=20
    )

    diag = diagnose_incident(db, inc.id)
    assert diag.confidence < 0.70
    assert inc.state == "ESCALATED_LOW_CONFIDENCE"

    # Audit event should be present
    esc_log = db.query(AuditLog).filter(
        AuditLog.incident_id == inc.id,
        AuditLog.event_type == "ESCALATION"
    ).first()
    assert esc_log is not None
    assert "LOW_CONFIDENCE" in esc_log.details_json


def test_terminal_protection_prevents_reopening():
    """Verify terminal incident state is never overwritten back to DIAGNOSED."""
    db = make_test_db()
    inc = create_incident_with_txns(
        db,
        concentration=0.90,
        sample_size=150,
        dominant_code="processor_declined",
        dominant_share=1.0,
        state="RESOLVED"
    )

    # First diagnosis while in RESOLVED
    diag1 = diagnose_incident(db, inc.id)
    # The incident state must remain RESOLVED
    assert inc.state == "RESOLVED"

    # Now test for ESCALATED_INSUFFICIENT_RECOVERY
    inc.state = "ESCALATED_INSUFFICIENT_RECOVERY"
    db.commit()

    diag2 = diagnose_incident(db, inc.id)
    assert inc.state == "ESCALATED_INSUFFICIENT_RECOVERY"


def test_no_duplicate_diagnosis_rows():
    """Verify repeated diagnose calls reuse the existing Diagnosis row."""
    db = make_test_db()
    inc = create_incident_with_txns(db)

    diag1 = diagnose_incident(db, inc.id)
    diag2 = diagnose_incident(db, inc.id)

    diag_count = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).count()
    assert diag_count == 1
    assert diag1.id == diag2.id
