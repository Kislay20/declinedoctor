from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AuditLog
from app.audit import log_audit_event, verify_audit_chain


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_audit_hash_chain_creation_and_verification():
    db = make_db()
    incident_id = "inc_audit_test"

    # Log events in sequence
    e1 = log_audit_event(db, incident_id, "system", "ANOMALY_DETECTED", {"drop": 30.0})
    assert e1.previous_hash is None
    assert e1.record_hash is not None

    e2 = log_audit_event(db, incident_id, "system", "DIAGNOSED", {"hypothesis": "ROUTING"})
    assert e2.previous_hash == e1.record_hash
    assert e2.record_hash is not None

    e3 = log_audit_event(db, incident_id, "operator", "HUMAN_APPROVAL_GRANTED", {"role": "OPERATOR"})
    assert e3.previous_hash == e2.record_hash

    # Verify chain
    result = verify_audit_chain(db, incident_id)
    assert result["valid"] is True
    assert result["count"] == 3
    assert result["status"] == "VERIFIED_TAMPER_FREE"


def test_audit_chain_tamper_detection():
    db = make_db()
    incident_id = "inc_tamper_test"

    e1 = log_audit_event(db, incident_id, "system", "ANOMALY_DETECTED", {"drop": 30.0})
    e2 = log_audit_event(db, incident_id, "system", "DIAGNOSED", {"hypothesis": "ROUTING"})

    # Tamper with event details
    e2.details_json = '{"hypothesis": "TAMPERED_CONTENT"}'
    db.commit()

    tamper_result = verify_audit_chain(db, incident_id)
    assert tamper_result["valid"] is False
    assert tamper_result["status"] == "CONTENT_TAMPERED"
    assert tamper_result["corrupted_log_id"] == e2.id
