"""DeclineDoctor Streaming Event Processor.

Processes real-time transaction events through the end-to-end lifecycle:
Transaction Event -> Detection -> Diagnosis -> Policy Guardrails -> Recovery -> Measurement.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import Transaction, Incident, Diagnosis
from .detection import detect_anomalies
from .diagnosis import diagnose_incident
from .policy import check_recovery_safety, can_approve_recovery, ACTION_HYPOTHESIS_MAP
from .recovery_agent import execute_recovery, _at_risk_revenue


def process_transaction_event(
    db: Session,
    event: Dict[str, Any],
    auto_recover: bool = False,
    user_role: str = "OPERATOR",
) -> Dict[str, Any]:
    """Ingest a single transaction event and run it through the continuous monitoring pipeline."""
    # Resolve auto_execute / auto_recover flags from event if provided
    if "auto_execute" in event and event["auto_execute"] is not None:
        auto_recover = bool(event["auto_execute"])
    elif "auto_recover" in event and event["auto_recover"] is not None:
        auto_recover = bool(event["auto_recover"])
    # 1. Ingest Transaction
    tx_id = event.get("id") or f"tx_stream_{uuid.uuid4().hex[:10]}"
    timestamp = event.get("timestamp")
    if isinstance(timestamp, str):
        try:
            ts = datetime.fromisoformat(timestamp)
        except Exception:
            ts = datetime.now()
    else:
        ts = timestamp or datetime.now()

    tx = Transaction(
        id=tx_id,
        timestamp=ts,
        amount=float(event.get("amount", 1000.0)),
        issuer=event.get("issuer", "Unknown Bank"),
        payment_method=event.get("payment_method", "card"),
        routing_partner=event.get("gateway", "razorpay"),
        merchant_id=event.get("merchant_id", "m_default"),
        success=bool(event.get("success", True)),
        decline_code=event.get("decline_code") if not event.get("success") else None,
        decline_reason=event.get("decline_reason") if not event.get("success") else None,
        retry_count=int(event.get("retry_count", 0)),
    )
    db.add(tx)
    db.commit()

    pipeline_trace = {
        "transaction_id": tx.id,
        "ingested_at": ts.isoformat(),
        "success": tx.success,
        "issuer": tx.issuer,
        "payment_method": tx.payment_method,
        "amount": tx.amount,
        "lifecycle_stage": "INGESTED",
    }

    # If transaction succeeded, no failure anomaly triggered
    if tx.success:
        pipeline_trace["lifecycle_stage"] = "COMPLETED_SUCCESS"
        return pipeline_trace

    # 2. Anomaly Detection
    # Run detection on segment
    detect_anomalies(db, current_time=ts)
    matching_incident = (
        db.query(Incident)
        .filter(
            Incident.segment_issuer == tx.issuer,
            Incident.segment_payment_method == tx.payment_method,
        )
        .order_by(Incident.detected_at.desc())
        .first()
    )

    if not matching_incident:
        pipeline_trace["lifecycle_stage"] = "INGESTED_SUB_THRESHOLD"
        pipeline_trace["message"] = "Failure recorded; segment is within normal baseline."
        return pipeline_trace

    pipeline_trace["incident_id"] = matching_incident.id
    pipeline_trace["incident_state"] = matching_incident.state
    pipeline_trace["lifecycle_stage"] = "ANOMALY_DETECTED"

    # 3. Diagnosis
    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == matching_incident.id).first()
    if not diagnosis:
        diagnosis = diagnose_incident(db, matching_incident.id)

    pipeline_trace["hypothesis"] = diagnosis.hypothesis
    pipeline_trace["confidence"] = diagnosis.confidence
    pipeline_trace["lifecycle_stage"] = "DIAGNOSED"

    # 4. Policy Guardrail Evaluation
    at_risk = _at_risk_revenue(db, matching_incident)
    recommended_action = ACTION_HYPOTHESIS_MAP.get(diagnosis.hypothesis, "SUPPRESS_RETRIES")

    safety_check = check_recovery_safety(
        incident_state=matching_incident.state,
        confidence=diagnosis.confidence,
        at_risk_revenue=at_risk,
        hypothesis=diagnosis.hypothesis,
        action=recommended_action,
        human_approved=False,
        user_role=user_role,
        has_diagnosis=True,
    )
    pipeline_trace["safety_check"] = safety_check
    pipeline_trace["recommended_action"] = recommended_action
    pipeline_trace["at_risk_revenue"] = at_risk

    # 5. Recovery Execution (if auto_recover is requested and policy allows)
    if auto_recover and safety_check["status"] == "SAFE_TO_EXECUTE":
        recovery_result = execute_recovery(
            db,
            matching_incident.id,
            {"recommended_action": recommended_action, "selected_by": "stream_auto_agent"},
            user_role=user_role,
        )
        pipeline_trace["lifecycle_stage"] = "RECOVERY_EXECUTED"
        pipeline_trace["recovery_result"] = recovery_result
    else:
        pipeline_trace["lifecycle_stage"] = f"POLICY_{safety_check['status']}"

    return pipeline_trace
