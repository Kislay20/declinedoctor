import json
import uuid
from sqlalchemy.orm import Session
from .models import Transaction, Incident, Diagnosis, AuditLog

TERMINAL_STATES = {
    "RESOLVED",
    "ESCALATED_INSUFFICIENT_RECOVERY",
    "ESCALATED_LOW_CONFIDENCE",
    "ESCALATED_LOW_REVENUE",
}

def diagnose_incident(db: Session, incident_id: str):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    # Terminal Protection: never re-diagnose or reopen a terminal incident
    existing_diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()
    if incident.state in TERMINAL_STATES and existing_diagnosis:
        return existing_diagnosis

    # Fetch segment failures in the incident window
    failures = db.query(Transaction).filter(
        Transaction.timestamp >= incident.window_start,
        Transaction.timestamp <= incident.window_end,
        Transaction.issuer == incident.segment_issuer,
        Transaction.payment_method == incident.segment_payment_method,
        Transaction.success == False
    ).all()

    if not failures:
        return None

    # Find dominant decline code
    decline_counts = {}
    for f in failures:
        code = f.decline_code or "unknown"
        decline_counts[code] = decline_counts.get(code, 0) + 1
        
    dominant_code = max(decline_counts, key=decline_counts.get)
    dominant_code_share = decline_counts[dominant_code] / len(failures)

    # Calculate Confidence using the exact deterministic formula from the spec
    sample_size_factor = min(incident.sample_size / 150.0, 1.0)
    raw_confidence = (0.5 * incident.concentration_ratio) + \
                     (0.3 * dominant_code_share) + \
                     (0.2 * sample_size_factor)
                     
    confidence = min(raw_confidence, 1.0) # Cap at 1.0
    rounded_conf = round(confidence, 2)

    # Domain Rules mapping for Hypothesis
    hypothesis = "INSUFFICIENT_SIGNAL"
    if dominant_code in ["processor_declined", "gateway_timeout"]:
        hypothesis = "ROUTING_CONNECTIVITY_ISSUE"
    elif dominant_code in ["try_again_later"]:
        hypothesis = "BIN_LEVEL_TEMPORARY_ISSUE"
    elif dominant_code in ["insufficient_funds", "do_not_honor"]:
        hypothesis = "ISSUER_SIDE_DECLINE"

    # Construct Evidence JSON
    evidence_dict = {
        "incident_id": incident.id,
        "window": {
            "start": incident.window_start.isoformat(),
            "end": incident.window_end.isoformat()
        },
        "segment": {
            "issuer": incident.segment_issuer,
            "payment_method": incident.segment_payment_method
        },
        "baseline_success_rate": round(incident.baseline_success_rate, 2),
        "incident_success_rate": round(incident.incident_success_rate, 2),
        "drop_pp": round(incident.drop_pp, 2),
        "concentration_ratio": round(incident.concentration_ratio, 2),
        "dominant_decline_code": dominant_code,
        "dominant_decline_code_share": round(dominant_code_share, 2),
        "sample_size": incident.sample_size,
        "hypothesis": hypothesis,
        "confidence": rounded_conf
    }

    # Update state only if not already terminal
    if incident.state not in TERMINAL_STATES:
        if rounded_conf < 0.70:
            incident.state = "ESCALATED_LOW_CONFIDENCE"
        else:
            incident.state = "DIAGNOSED"
        db.commit()

    # Prevent duplicate rows: reuse existing diagnosis record if present
    diagnosis = existing_diagnosis
    if not diagnosis:
        diagnosis = Diagnosis(
            id=f"diag_{uuid.uuid4().hex[:12]}",
            incident_id=incident.id,
            hypothesis=hypothesis,
            confidence=rounded_conf,
            dominant_decline_code=dominant_code,
            dominant_decline_code_share=round(dominant_code_share, 2),
            evidence_json=json.dumps(evidence_dict)
        )
        db.add(diagnosis)
        db.commit()
        db.refresh(diagnosis)
    else:
        diagnosis.hypothesis = hypothesis
        diagnosis.confidence = rounded_conf
        diagnosis.dominant_decline_code = dominant_code
        diagnosis.dominant_decline_code_share = round(dominant_code_share, 2)
        diagnosis.evidence_json = json.dumps(evidence_dict)
        db.commit()

    # Real backend audit log for DIAGNOSED
    existing_diag_log = db.query(AuditLog).filter(AuditLog.incident_id == incident.id, AuditLog.event_type == "DIAGNOSED").first()
    if not existing_diag_log:
        db.add(AuditLog(
            incident_id=incident.id,
            actor="system",
            event_type="DIAGNOSED",
            details_json=json.dumps({
                "hypothesis": hypothesis,
                "confidence": f"{int(round(rounded_conf * 100))}%",
                "dominant_decline_code": dominant_code,
                "dominant_code_share": f"{round(dominant_code_share * 100, 1)}%",
                "concentration_ratio": f"{round(incident.concentration_ratio * 100, 1)}%"
            })
        ))
        db.commit()

    # Real backend audit log for ESCALATION when low confidence
    if rounded_conf < 0.70:
        existing_esc_log = db.query(AuditLog).filter(AuditLog.incident_id == incident.id, AuditLog.event_type == "ESCALATION").first()
        if not existing_esc_log:
            db.add(AuditLog(
                incident_id=incident.id,
                actor="system",
                event_type="ESCALATION",
                details_json=json.dumps({
                    "reason": "LOW_CONFIDENCE",
                    "confidence": f"{int(round(rounded_conf * 100))}%",
                    "threshold": "70%",
                    "action": "NO_RECOVERY"
                })
            ))
            db.commit()

    return diagnosis