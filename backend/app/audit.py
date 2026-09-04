"""DeclineDoctor Cryptographic Audit Service.

Implements an append-only, tamper-evident audit trail using SHA-256 hash chaining.
Every log entry stores the cryptographic hash of the previous record.
"""

from datetime import datetime
import json
from sqlalchemy.orm import Session
from .models import AuditLog
from .policy import compute_audit_hash


def log_audit_event(
    db: Session,
    incident_id: str,
    actor: str,
    event_type: str,
    details: dict,
    timestamp: datetime = None,
) -> AuditLog:
    """Record a cryptographically hashed, append-only audit event."""
    ts = timestamp or datetime.now()
    details_str = json.dumps(details, sort_keys=True)

    # Get the latest audit log entry for this incident to obtain the parent hash
    last_entry = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    previous_hash = last_entry.record_hash if (last_entry and last_entry.record_hash) else None

    # Compute current record hash
    current_hash = compute_audit_hash(
        previous_hash=previous_hash,
        timestamp_str=ts.isoformat(),
        actor=actor,
        event_type=event_type,
        details_json=details_str,
    )

    log_entry = AuditLog(
        incident_id=incident_id,
        timestamp=ts,
        actor=actor,
        event_type=event_type,
        details_json=details_str,
        previous_hash=previous_hash,
        record_hash=current_hash,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def verify_audit_chain(db: Session, incident_id: str) -> dict:
    """Verify cryptographic integrity of the audit trail for an incident."""
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident_id)
        .order_by(AuditLog.id.asc())
        .all()
    )

    if not logs:
        return {"valid": True, "count": 0, "status": "NO_RECORDS"}

    expected_prev = None
    for log in logs:
        if log.previous_hash != expected_prev:
            return {
                "valid": False,
                "corrupted_log_id": log.id,
                "expected_previous_hash": expected_prev,
                "actual_previous_hash": log.previous_hash,
                "status": "HASH_MISMATCH",
            }
        # Verify current record hash
        computed = compute_audit_hash(
            previous_hash=expected_prev,
            timestamp_str=log.timestamp.isoformat(),
            actor=log.actor,
            event_type=log.event_type,
            details_json=log.details_json,
        )
        if log.record_hash and log.record_hash != computed:
            return {
                "valid": False,
                "corrupted_log_id": log.id,
                "expected_record_hash": computed,
                "actual_record_hash": log.record_hash,
                "status": "CONTENT_TAMPERED",
            }
        expected_prev = log.record_hash

    return {
        "valid": True,
        "count": len(logs),
        "status": "VERIFIED_TAMPER_FREE",
        "latest_hash": expected_prev,
    }
