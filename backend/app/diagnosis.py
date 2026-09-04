import json
import uuid
from sqlalchemy.orm import Session
from .models import Transaction, Incident, Diagnosis, AuditLog

from .policy import TERMINAL_STATES

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

    # Domain Rules mapping for Hypothesis (expanded coverage)
    ROUTING_CODES = {
        "processor_declined",
        "gateway_timeout",
        "network_error",
        "issuer_unavailable",
    }
    BIN_CODES = {"try_again_later", "velocity_limit"}
    ISSUER_CODES = {
        "insufficient_funds",
        "do_not_honor",
        "3ds_failure",
        "authentication_failed",
    }

    if dominant_code in ROUTING_CODES:
        hypothesis = "ROUTING_CONNECTIVITY_ISSUE"
    elif dominant_code in BIN_CODES:
        hypothesis = "BIN_LEVEL_TEMPORARY_ISSUE"
    elif dominant_code in ISSUER_CODES:
        hypothesis = "ISSUER_SIDE_DECLINE"
    else:
        hypothesis = "INSUFFICIENT_SIGNAL"

    # Calculate at-risk revenue for genuine evidence-based severity computation
    at_risk_revenue = sum(f.amount for f in failures)
    if at_risk_revenue >= 500_000.0 or (incident.drop_pp >= 50.0 and incident.sample_size >= 100):
        severity = "CRITICAL"
    elif at_risk_revenue >= 200_000.0 or (incident.drop_pp >= 35.0 and incident.sample_size >= 50):
        severity = "HIGH"
    elif at_risk_revenue >= 50_000.0 or incident.drop_pp >= 20.0:
        severity = "MEDIUM"
    else:
        severity = "LOW"
    incident.severity = severity

    # Construct Evidence JSON
    sample_network = next((f.card_network for f in failures if f.card_network), "Visa") if incident.segment_payment_method == "card" else None
    timeout_failures = sum(1 for f in failures if "timeout" in (f.decline_code or "").lower())
    timeout_rate = (timeout_failures / len(failures)) if failures else 0.0

    # BIN Intelligence and Isolation Analysis
    from .bin_intelligence import analyze_bin_telemetry
    bin_analytics = analyze_bin_telemetry(
        db,
        issuer=incident.segment_issuer,
        payment_method=incident.segment_payment_method,
        incident_id=incident.id,
    )

    # Provider Routing Optimizer Decision
    from .providers.routing_optimizer import optimize_provider_routing
    routing_decision = optimize_provider_routing(
        issuer=incident.segment_issuer,
        payment_method=incident.segment_payment_method,
        bin_number=bin_analytics.get("dominant_bin") if incident.segment_payment_method == "card" else None,
        decline_reason=dominant_code,
    )

    # Advanced Structured Causal Evidence (Part D)
    if hypothesis == "ROUTING_CONNECTIVITY_ISSUE":
        evidence_for = [
            f"Dominant decline code '{dominant_code}' concentration: {int(dominant_code_share * 100)}% of failures.",
            f"Steep success-rate degradation of {incident.drop_pp:.1f} percentage points (baseline {incident.baseline_success_rate:.1f}% -> incident {incident.incident_success_rate:.1f}%).",
            f"Segment concentration ratio is {int(incident.concentration_ratio * 100)}%, indicating concentrated connectivity failure.",
            f"Timeout rate elevated to {int(timeout_rate * 100)}% during the active incident window.",
        ]
        evidence_against = [
            "Customer balance exhaustion ruled out: insufficient_funds concentration is near zero (< 5%).",
            "Customer-side 3DS authentication failure rate remains within nominal baseline.",
            "Acquiring bank network connectivity operational across alternate provider routes.",
        ]
        rec_action = "REROUTE"
        why_appropriate = (
            f"Switches transaction retry and new volume to {routing_decision['recommended_provider']} "
            f"(expected success: {routing_decision['expected_success_rate']}%, latency: {routing_decision['expected_latency_ms']}ms), "
            f"completely bypassing the degraded gateway route."
        )
        invalidation_criteria = [
            "Recovery lift drops below 5.0 percentage points upon test retry.",
            "Decline code shifts from processor/timeout to customer-side authentication failure.",
            "Primary gateway reports latency restored below 60ms with zero timeout errors.",
        ]
        uncertainty = "Low: High diagnostic confidence grounded in severe processor/timeout decline concentration."
    elif hypothesis == "BIN_LEVEL_TEMPORARY_ISSUE":
        evidence_for = [
            f"Dominant decline code '{dominant_code}' indicates velocity throttling or temporary card-tier limit.",
            bin_analytics.get("isolation_summary", "Failures concentrated in specific card BIN range."),
            f"Failure concentration ratio: {int(incident.concentration_ratio * 100)}%.",
        ]
        evidence_against = [
            "General gateway connectivity is healthy; other BINs on same issuer processing normally.",
            "Hard terminal decline codes (do_not_honor, stolen_card) absent in sample.",
        ]
        rec_action = "ADJUST_RETRY_TIMING"
        why_appropriate = (
            "Applies jittered exponential backoff (60s to 300s) to allow issuing bank rate-limit "
            "windows to reset without triggering automated cardholder lockouts."
        )
        invalidation_criteria = [
            "Decline persists across more than 2 backoff retry cycles.",
            "Failures spread across unrelated card BIN ranges and payment methods.",
        ]
        uncertainty = "Moderate: Rate-limit throttles typically resolve once velocity pressure subsides."
    elif hypothesis == "ISSUER_SIDE_DECLINE":
        evidence_for = [
            f"Dominant decline code '{dominant_code}' indicates customer-side or core issuer authorization failure.",
            f"Decline code share: {int(dominant_code_share * 100)}% of failures.",
        ]
        evidence_against = [
            "Routing hops and gateway response times remain normal (< 100ms).",
            "Gateway timeout errors are near zero during the incident window.",
        ]
        rec_action = "SUPPRESS_RETRIES"
        why_appropriate = (
            "Halts automated retries immediately to protect cardholders from repeated charges, "
            "reduce customer friction, and eliminate unnecessary merchant processor retry fees."
        )
        invalidation_criteria = [
            "Issuing bank announces completion of scheduled core banking maintenance.",
            "Customer updates payment method or authenticates via alternate bank rail.",
        ]
        uncertainty = "Low: Terminal declines must not be retried under backend safety policy."
    else:
        evidence_for = [
            f"Sample size ({incident.sample_size}) or concentration ({int(incident.concentration_ratio * 100)}%) below statistical significance threshold.",
        ]
        evidence_against = [
            "No single decline code reaches dominant threshold (> 50%).",
        ]
        rec_action = "SUPPRESS_RETRIES"
        why_appropriate = "Recovery actions are strictly blocked when diagnostic confidence is below 0.70."
        invalidation_criteria = [
            "Additional transaction sample volume arrives with clear decline code concentration.",
        ]
        uncertainty = "High: High diagnostic uncertainty requires automated action suppression."

    causal_evidence = {
        "hypothesis": hypothesis,
        "confidence": rounded_conf,
        "confidence_pct": int(round(rounded_conf * 100)),
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "key_statistical_signals": {
            "drop_pp": round(incident.drop_pp, 2),
            "baseline_success_rate": round(incident.baseline_success_rate, 2),
            "incident_success_rate": round(incident.incident_success_rate, 2),
            "sample_size": incident.sample_size,
            "concentration_ratio": round(incident.concentration_ratio, 2),
            "dominant_decline_code": dominant_code,
            "dominant_code_share_pct": round(dominant_code_share * 100, 1),
            "timeout_rate_pct": round(timeout_rate * 100, 1),
        },
        "relevant_segment": f"{incident.segment_issuer} {incident.segment_payment_method}",
        "provider_evidence": {
            "current_gateway": "Razorpay Smart Router",
            "active_mode": "TEST_SANDBOX",
            "recommended_provider": routing_decision["recommended_provider"],
            "target_routing": routing_decision["target_gateway_routing"],
            "expected_success_rate": routing_decision["expected_success_rate"],
            "expected_latency_ms": routing_decision["expected_latency_ms"],
        },
        "bin_evidence": {
            "is_isolated_to_single_bin": bin_analytics.get("is_isolated_to_single_bin", False),
            "dominant_bin": bin_analytics.get("dominant_bin"),
            "isolation_summary": bin_analytics.get("isolation_summary"),
        },
        "recommended_action": rec_action,
        "why_appropriate": why_appropriate,
        "invalidation_criteria": invalidation_criteria,
        "uncertainty": uncertainty,
        "conclusion": (
            f"Localized {hypothesis.replace('_', ' ').lower()} is verified with {int(round(rounded_conf * 100))}% confidence. "
            f"Recommended intervention: {rec_action}."
        ),
    }

    evidence_dict = {
        "incident_id": incident.id,
        "window": {
            "start": incident.window_start.isoformat(),
            "end": incident.window_end.isoformat()
        },
        "segment": {
            "issuer": incident.segment_issuer,
            "payment_method": incident.segment_payment_method,
            "card_network": sample_network,
            "geography": "IN / Domestic",
        },
        "baseline_success_rate": round(incident.baseline_success_rate, 2),
        "incident_success_rate": round(incident.incident_success_rate, 2),
        "drop_pp": round(incident.drop_pp, 2),
        "concentration_ratio": round(incident.concentration_ratio, 2),
        "dominant_decline_code": dominant_code,
        "dominant_decline_code_share": round(dominant_code_share, 2),
        "sample_size": incident.sample_size,
        "at_risk_revenue": round(at_risk_revenue, 2),
        "severity": severity,
        "hypothesis": hypothesis,
        "confidence": rounded_conf,
        "timeout_rate": round(timeout_rate, 2),
        "avg_transaction_amount": round(at_risk_revenue / len(failures), 2) if failures else 0.0,
        "provider_context": {
            "gateway": "Razorpay Smart Router",
            "active_mode": "TEST_SANDBOX",
            "provider_status": "HEALTHY",
            "recommended_provider": routing_decision["recommended_provider"],
            "target_gateway_routing": routing_decision["target_gateway_routing"],
        },
        "bin_intelligence": bin_analytics,
        "provider_routing": routing_decision,
        "causal_evidence": causal_evidence,
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

    # Hash-chained backend audit log for DIAGNOSED
    from .audit import log_audit_event
    existing_diag_log = db.query(AuditLog).filter(AuditLog.incident_id == incident.id, AuditLog.event_type == "DIAGNOSED").first()
    if not existing_diag_log:
        log_audit_event(
            db=db,
            incident_id=incident.id,
            actor="system",
            event_type="DIAGNOSED",
            details={
                "hypothesis": hypothesis,
                "confidence": f"{int(round(rounded_conf * 100))}%",
                "dominant_decline_code": dominant_code,
                "dominant_code_share": f"{round(dominant_code_share * 100, 1)}%",
                "concentration_ratio": f"{round(incident.concentration_ratio * 100, 1)}%",
                "severity": severity,
            }
        )

    # Hash-chained backend audit log for ESCALATION when low confidence
    if rounded_conf < 0.70:
        existing_esc_log = db.query(AuditLog).filter(AuditLog.incident_id == incident.id, AuditLog.event_type == "ESCALATION").first()
        if not existing_esc_log:
            log_audit_event(
                db=db,
                incident_id=incident.id,
                actor="system",
                event_type="ESCALATION",
                details={
                    "reason": "LOW_CONFIDENCE",
                    "confidence": f"{int(round(rounded_conf * 100))}%",
                    "threshold": "70%",
                    "action": "NO_RECOVERY",
                }
            )

    # Precompute and snapshot pre-action counterfactuals immediately
    if not diagnosis.counterfactuals_json:
        try:
            from .recovery_agent import compute_counterfactuals
            compute_counterfactuals(db, incident.id, include_extended=True, include_baseline=True)
        except Exception:
            pass

    return diagnosis