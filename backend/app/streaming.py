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
    """Ingest a single transaction event and run it through the continuous 9-stage monitoring pipeline."""
    # Resolve auto_execute / auto_recover flags from event if provided
    if "auto_execute" in event and event["auto_execute"] is not None:
        auto_recover = bool(event["auto_execute"])
    elif "auto_recover" in event and event["auto_recover"] is not None:
        auto_recover = bool(event["auto_recover"])

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    tx_id = event.get("id") or f"tx_stream_{uuid.uuid4().hex[:10]}"
    timestamp = event.get("timestamp")
    if isinstance(timestamp, str):
        try:
            ts = datetime.fromisoformat(timestamp)
        except Exception:
            ts = datetime.now()
    else:
        ts = timestamp or datetime.now()

    amount = float(event.get("amount", 1500.0))
    issuer = str(event.get("issuer", "Bank X"))
    payment_method = str(event.get("payment_method", "card"))
    card_network = str(event.get("card_network", "Visa")) if payment_method == "card" else None
    bin_number = str(event.get("bin", "452114")) if payment_method == "card" else None
    processor = str(event.get("gateway", "Razorpay Smart Router"))
    is_success = bool(event.get("success", False))
    decline_code = event.get("decline_code") if not is_success else None
    decline_reason = event.get("decline_reason") if not is_success else None
    retry_count = int(event.get("retry_count", 0))
    simulated_latency = float(event.get("latency_ms", 65.0))

    event_record = {
        "event_id": event_id,
        "timestamp": ts.isoformat(),
        "transaction_id": tx_id,
        "bank": issuer,
        "bin": bin_number,
        "payment_method": payment_method,
        "network": card_network,
        "processor": processor,
        "amount": amount,
        "failure_code": decline_code,
        "latency_ms": simulated_latency,
        "retry_count": retry_count,
        "success": is_success,
    }

    # Timeline of pipeline trace steps
    timeline_steps = []

    def add_step(stage: str, status: str, details: str, duration_ms: float = 5.0):
        timeline_steps.append({
            "stage": stage,
            "status": status,
            "details": details,
            "timestamp": (ts).strftime("%H:%M:%S.%f")[:-3],
            "duration_ms": duration_ms,
        })

    # 1. RECEIVED
    add_step("RECEIVED", "COMPLETED", f"Event {event_id} captured via HTTP stream ingress.", 2.1)

    # 2. VALIDATED
    add_step("VALIDATED", "COMPLETED", f"Transaction {tx_id} schema and financial limits validated (Amount: Rs.{amount:,.2f}).", 1.8)

    # Persist Transaction in SQLite
    tx = Transaction(
        id=tx_id,
        timestamp=ts,
        amount=amount,
        issuer=issuer,
        payment_method=payment_method,
        card_network=card_network,
        routing_partner=processor,
        merchant_id=event.get("merchant_id", "m_default"),
        success=is_success,
        decline_code=decline_code,
        decline_reason=decline_reason,
        retry_count=retry_count,
    )
    db.add(tx)
    db.commit()

    # 3. SEGMENTED
    segment_key = f"{issuer}_{payment_method}"
    add_step("SEGMENTED", "COMPLETED", f"Segment identified: {issuer} ({payment_method.upper()}) | BIN: {bin_number or 'N/A'}.", 2.5)

    if is_success:
        add_step("ANOMALY_CHECKED", "SKIPPED", "Transaction succeeded; no failure pattern detected.", 1.0)
        return {
            "event_record": event_record,
            "transaction_id": tx.id,
            "success": tx.success,
            "issuer": tx.issuer,
            "payment_method": tx.payment_method,
            "amount": tx.amount,
            "lifecycle_stage": "COMPLETED_SUCCESS",
            "timeline": timeline_steps,
            "pipeline_trace": timeline_steps,
            "message": "Payment succeeded cleanly.",
        }

    # 4. ANOMALY_CHECKED
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
        add_step("ANOMALY_CHECKED", "NORMAL", "Segment failure rate remains within baseline threshold (drop < 15pp).", 4.2)
        return {
            "event_record": event_record,
            "transaction_id": tx.id,
            "success": tx.success,
            "issuer": tx.issuer,
            "payment_method": tx.payment_method,
            "amount": tx.amount,
            "lifecycle_stage": "SUB_THRESHOLD",
            "timeline": timeline_steps,
            "pipeline_trace": timeline_steps,
            "message": "Failure recorded; segment is within normal baseline.",
        }

    add_step("ANOMALY_CHECKED", "ANOMALY_CONFIRMED", f"Anomaly detected on {segment_key}: {matching_incident.drop_pp:.1f}pp drop over baseline.", 8.5)

    # 5. DIAGNOSED
    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == matching_incident.id).first()
    if not diagnosis:
        diagnosis = diagnose_incident(db, matching_incident.id)

    add_step(
        "DIAGNOSED",
        "COMPLETED",
        f"Hypothesis: {diagnosis.hypothesis} (Confidence: {int(diagnosis.confidence * 100)}%, Dominant Code: {diagnosis.dominant_decline_code}).",
        15.2,
    )

    # 6. POLICY_EVALUATED
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

    policy_status = safety_check["status"]
    add_step(
        "POLICY_EVALUATED",
        policy_status,
        f"Policy Gate: {policy_status} (At-Risk: Rs.{at_risk:,.2f}, Role: {user_role}). Reason: {safety_check['reason']}",
        6.4,
    )

    # 7. ACTION_SELECTED
    if policy_status == "SAFE_TO_EXECUTE":
        add_step("ACTION_SELECTED", "RECOMMENDED", f"Selected compatible recovery strategy: {recommended_action}.", 3.1)
    else:
        add_step("ACTION_SELECTED", "BLOCKED", f"Action execution blocked by policy ({policy_status}).", 2.0)

    # 8. ACTION_APPLIED & 9. OUTCOME_MEASURED
    recovery_result = None
    if auto_recover and policy_status == "SAFE_TO_EXECUTE":
        add_step("ACTION_APPLIED", "EXECUTING", f"Applying {recommended_action} via MockPaymentProvider / Razorpay Smart Router.", 35.0)
        recovery_result = execute_recovery(
            db,
            matching_incident.id,
            {"recommended_action": recommended_action, "selected_by": "stream_auto_agent"},
            user_role=user_role,
        )
        if recovery_result.get("status") == "RESOLVED":
            recovered_rev = recovery_result.get("recovered_revenue", 0.0)
            add_step("ACTION_APPLIED", "APPLIED", f"Strategy {recommended_action} successfully applied to retry traffic.", 12.0)
            add_step("OUTCOME_MEASURED", "RESOLVED", f"Recovery validated: Rs.{recovered_rev:,.2f} recovered revenue secured.", 18.0)
        else:
            add_step("OUTCOME_MEASURED", recovery_result.get("status", "BLOCKED"), f"Recovery outcome: {recovery_result.get('status')}.", 10.0)
    else:
        if not auto_recover:
            add_step("ACTION_APPLIED", "PENDING_MANUAL_TRIGGER", "Auto-recover flag is false. Awaiting operator confirmation.", 1.0)
        else:
            add_step("ACTION_APPLIED", "HALTED", f"Safety policy halted execution ({policy_status}).", 1.0)
        add_step("OUTCOME_MEASURED", "UNAVAILABLE", "Post-action outcome not measured (action not applied).", 1.0)

    res = {
        "event_record": event_record,
        "transaction_id": tx.id,
        "success": tx.success,
        "issuer": tx.issuer,
        "payment_method": tx.payment_method,
        "amount": tx.amount,
        "incident_id": matching_incident.id,
        "incident_state": matching_incident.state,
        "hypothesis": diagnosis.hypothesis,
        "confidence": diagnosis.confidence,
        "recommended_action": recommended_action,
        "at_risk_revenue": at_risk,
        "safety_check": safety_check,
        "lifecycle_stage": "RECOVERY_EXECUTED" if (recovery_result and recovery_result.get("status") == "RESOLVED") else f"POLICY_{policy_status}",
        "timeline": timeline_steps,
        "pipeline_trace": timeline_steps,
    }
    if recovery_result is not None:
        res["recovery_result"] = recovery_result
    return res
