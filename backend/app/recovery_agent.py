import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from .models import Incident, Diagnosis, RecoveryAction, Outcome, Transaction, AuditLog
from .audit import log_audit_event
from .policy import (
    IncidentState,
    TERMINAL_STATES,
    CONFIDENCE_THRESHOLD,
    MIN_REVENUE_FOR_AUTO_ACTION,
    MAX_REVENUE_FOR_AUTO_APPROVE,
    MAX_SIMULATED_RETRIES,
    MIN_MEASURABLE_IMPROVEMENT_PP,
    ALLOWED_ACTIONS,
    ACTION_HYPOTHESIS_MAP,
    is_action_compatible,
    can_approve_recovery,
    validate_state_transition,
    check_recovery_safety,
)

# Fixed effect-size assumptions from Spec Section 3 & Expanded Strategies
EFFECT_SIZES = {
    "REROUTE": 0.42,
    "ADJUST_RETRY_TIMING": 0.21,
    "SUPPRESS_RETRIES": 0.00,
    "PAYMENT_METHOD_FALLBACK": 0.35,
    "INTELLIGENT_RETRY": 0.28,
    "PROVIDER_WEIGHT_ADJUSTMENT": 0.38,
}

# Compatibility mapping
ALLOWED_ACTIONS_BY_HYPOTHESIS = ACTION_HYPOTHESIS_MAP


def _incident_transactions(db: Session, incident: Incident) -> List[Transaction]:
    """Fetch all transactions in the incident window and segment."""
    return db.query(Transaction).filter(
        Transaction.timestamp >= incident.window_start,
        Transaction.timestamp <= incident.window_end,
        Transaction.issuer == incident.segment_issuer,
        Transaction.payment_method == incident.segment_payment_method,
    ).all()


def _at_risk_revenue(db: Session, incident: Incident) -> float:
    """Calculate at-risk revenue as the sum of failed transactions in the window."""
    return sum(t.amount for t in _incident_transactions(db, incident) if not t.success)


def compute_counterfactuals(
    db: Session,
    incident_id: str,
    include_extended: bool = False,
    include_baseline: bool = False,
) -> List[Dict]:
    """Compute and preserve genuine pre-action expected outcomes for candidate recovery actions.

    Maintains an authoritative, immutable frozen historical snapshot in diagnosis.counterfactuals_json
    so that post-diagnosis webhooks, telemetry shifts, and recovery executions NEVER distort pre-action projections.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()
    if not incident or not diagnosis:
        raise ValueError(f"Incident or Diagnosis not found for id {incident_id}")

    standard_action_types = {"REROUTE", "ADJUST_RETRY_TIMING", "SUPPRESS_RETRIES"}

    # 1. If an immutable snapshot already exists, serve directly from frozen cache
    if diagnosis.counterfactuals_json:
        try:
            cached_data = json.loads(diagnosis.counterfactuals_json)
            baseline = None
            candidates = []

            if isinstance(cached_data, dict) and "candidates" in cached_data:
                baseline = cached_data.get("baseline")
                candidates = cached_data.get("candidates", [])
            elif isinstance(cached_data, list) and len(cached_data) > 0:
                if cached_data[0].get("action_type") == "NO_ACTION":
                    baseline = cached_data[0]
                    candidates = cached_data[1:]
                else:
                    candidates = cached_data

            if candidates and (not include_extended or len(candidates) >= 6):
                if not baseline and candidates:
                    first_c = candidates[0]
                    tot_tx = first_c.get("total_txns") or incident.sample_size or 0
                    tot_elig = first_c.get("total_eligible_failures") or 0
                    pre_rate = first_c.get("baseline_incident_success_rate") or round(float(incident.incident_success_rate or 0.0), 2)
                    baseline = {
                        "action_type": "NO_ACTION",
                        "name": "No Intervention",
                        "effect_size": 0.0,
                        "is_compatible": True,
                        "is_recommended": False,
                        "policy_status": "BASELINE_EXPOSURE",
                        "transactions_affected": 0,
                        "tx_to_flip": 0,
                        "total_txns": tot_tx,
                        "sample_size": tot_tx,
                        "total_failures": first_c.get("total_failures", tot_elig),
                        "total_eligible_failures": tot_elig,
                        "baseline_incident_success_rate": pre_rate,
                        "current_success_rate": pre_rate,
                        "projected_success_rate": pre_rate,
                        "expected_improvement_pp": 0.0,
                        "expected_recovered_revenue": 0.0,
                        "gross_recovered_revenue": 0.0,
                        "expected_cost": 0.0,
                        "retry_cost": 0.0,
                        "expected_net_recovery": 0.0,
                        "net_recovered_revenue": 0.0,
                        "expected_roi": 0.0,
                        "projected_failure_exposure": tot_elig,
                        "projected_lost_revenue": round(sum(c.get("expected_recovered_revenue", 0.0) for c in candidates if c.get("action_type") == "SUPPRESS_RETRIES") or 0.0, 2),
                        "friction_score": 45.0,
                        "customer_friction_score": 45.0,
                        "rationale": "Takes no automated mitigation. 100% of eligible failures remain unrecovered, incurring full revenue loss.",
                    }

                active_candidates = (
                    candidates if include_extended
                    else [c for c in candidates if c.get("action_type") in standard_action_types]
                )

                if include_baseline and baseline:
                    return [baseline] + active_candidates
                return active_candidates
        except Exception:
            pass

    # 2. First-time snapshot generation: freeze authoritative projection inputs from incident window
    all_txns = _incident_transactions(db, incident)
    total_txns = len(all_txns)
    current_successes = sum(1 for t in all_txns if t.success)

    if incident.incident_success_rate is not None:
        pre_success_rate = round(float(incident.incident_success_rate), 2)
    elif total_txns > 0:
        pre_success_rate = round(current_successes / total_txns * 100, 2)
    else:
        pre_success_rate = 0.0

    failures = [t for t in all_txns if not t.success]
    total_failures = len(failures)
    eligible_failures = [t for t in failures if t.retry_count < MAX_SIMULATED_RETRIES]
    total_eligible = len(eligible_failures)
    lost_revenue = round(sum(t.amount for t in eligible_failures), 2)

    rationales = {
        "REROUTE": (
            "Switches gateway partner route for retry traffic. Optimal for connectivity "
            "failures, gateway timeouts, and provider-side degradation."
        ),
        "ADJUST_RETRY_TIMING": (
            "Applies jittered exponential backoff (30s to 300s). Optimal for rate/velocity "
            "throttles and transient bank network congestion."
        ),
        "SUPPRESS_RETRIES": (
            "Halts automated retries immediately. Protects merchants from duplicate fees "
            "and customers from account lockouts on hard/terminal declines."
        ),
        "PAYMENT_METHOD_FALLBACK": (
            "Offers customer alternate payment method (UPI / Netbanking) upon card issuer decline."
        ),
        "INTELLIGENT_RETRY": (
            "Uses dynamic retry scheduling with randomized exponential backoff and BIN awareness."
        ),
        "PROVIDER_WEIGHT_ADJUSTMENT": (
            "Dynamically re-balances gateway traffic allocation across multiple provider terminals."
        ),
    }

    friction_scores = {
        "REROUTE": 12.0,
        "ADJUST_RETRY_TIMING": 24.0,
        "SUPPRESS_RETRIES": 5.0,
        "PAYMENT_METHOD_FALLBACK": 38.0,
        "INTELLIGENT_RETRY": 18.0,
        "PROVIDER_WEIGHT_ADJUSTMENT": 14.0,
    }

    # Frozen NO_ACTION baseline item
    no_action_item = {
        "action_type": "NO_ACTION",
        "name": "No Intervention",
        "effect_size": 0.0,
        "is_compatible": True,
        "is_recommended": False,
        "policy_status": "BASELINE_EXPOSURE",
        "transactions_affected": 0,
        "tx_to_flip": 0,
        "total_txns": total_txns,
        "sample_size": total_txns,
        "total_failures": total_failures,
        "total_eligible_failures": total_eligible,
        "baseline_incident_success_rate": pre_success_rate,
        "current_success_rate": pre_success_rate,
        "projected_success_rate": pre_success_rate,
        "expected_improvement_pp": 0.0,
        "expected_recovered_revenue": 0.0,
        "gross_recovered_revenue": 0.0,
        "expected_cost": 0.0,
        "retry_cost": 0.0,
        "expected_net_recovery": 0.0,
        "net_recovered_revenue": 0.0,
        "expected_roi": 0.0,
        "projected_failure_exposure": total_eligible,
        "projected_lost_revenue": lost_revenue,
        "friction_score": 45.0,
        "customer_friction_score": 45.0,
        "rationale": "Takes no automated mitigation. 100% of eligible failures remain unrecovered, incurring full revenue loss.",
    }

    recommended_for_hypothesis = ACTION_HYPOTHESIS_MAP.get(diagnosis.hypothesis, "SUPPRESS_RETRIES")
    is_low_confidence = (diagnosis.confidence is not None) and (diagnosis.confidence < CONFIDENCE_THRESHOLD)

    candidate_actions = [
        "REROUTE",
        "ADJUST_RETRY_TIMING",
        "SUPPRESS_RETRIES",
        "PAYMENT_METHOD_FALLBACK",
        "INTELLIGENT_RETRY",
        "PROVIDER_WEIGHT_ADJUSTMENT",
    ]

    # Derive dynamically recommended provider from diagnosis evidence or routing optimizer
    rec_provider = "Provider A"
    target_routing_str = "REROUTE -> Provider A"
    if diagnosis and diagnosis.evidence_json:
        try:
            ev = json.loads(diagnosis.evidence_json) if isinstance(diagnosis.evidence_json, str) else diagnosis.evidence_json
            r_dec = ev.get("provider_routing") or ev.get("causal_evidence", {}).get("provider_evidence")
            if r_dec and r_dec.get("recommended_provider"):
                rec_provider = r_dec.get("recommended_provider")
                target_routing_str = r_dec.get("target_gateway_routing") or f"REROUTE -> {rec_provider}"
        except Exception:
            pass
    if not rec_provider or rec_provider == "Provider A":
        try:
            from .providers.routing_optimizer import optimize_provider_routing
            r_opt = optimize_provider_routing(
                issuer=incident.segment_issuer,
                payment_method=incident.segment_payment_method,
                decline_reason=diagnosis.dominant_decline_code if diagnosis else "processor_declined",
            )
            rec_provider = r_opt.get("recommended_provider", "Provider A")
            target_routing_str = r_opt.get("target_gateway_routing", f"REROUTE -> {rec_provider}")
        except Exception:
            rec_provider = "Provider A"
            target_routing_str = "REROUTE -> Provider A"

    all_candidates = []
    for action_type in candidate_actions:
        effect_size = EFFECT_SIZES[action_type]
        compatible = is_action_compatible(diagnosis.hypothesis, action_type)

        tx_to_flip = int(total_eligible * effect_size)
        expected_recovered_revenue = round(sum(t.amount for t in eligible_failures[:tx_to_flip]), 2)
        expected_improvement_pp = round((tx_to_flip / total_txns * 100), 2) if total_txns > 0 else 0.0
        projected_success_rate = round(pre_success_rate + expected_improvement_pp, 2)

        retry_unit_cost = 15.0 if action_type != "SUPPRESS_RETRIES" else 0.0
        expected_cost = round(tx_to_flip * retry_unit_cost, 2)
        expected_net_recovery = round(max(expected_recovered_revenue - expected_cost, 0.0), 2)
        expected_roi = round((expected_net_recovery / expected_cost * 100.0), 1) if expected_cost > 0 else 0.0

        if is_low_confidence:
            is_recommended = False
            policy_status = "NOT_EXECUTED_LOW_CONFIDENCE" if compatible else "INCOMPATIBLE"
        else:
            is_recommended = (action_type == recommended_for_hypothesis)
            policy_status = "RECOMMENDED" if is_recommended else ("COMPATIBLE" if compatible else "INCOMPATIBLE")

        item = {
            "action_type": action_type,
            "name": action_type,
            "effect_size": effect_size,
            "is_compatible": compatible,
            "is_recommended": is_recommended,
            "policy_status": policy_status,
            "transactions_affected": tx_to_flip,
            "tx_to_flip": tx_to_flip,
            "total_txns": total_txns,
            "sample_size": total_txns,
            "total_failures": total_failures,
            "total_eligible_failures": total_eligible,
            "baseline_incident_success_rate": pre_success_rate,
            "current_success_rate": pre_success_rate,
            "projected_success_rate": projected_success_rate,
            "expected_improvement_pp": expected_improvement_pp,
            "expected_recovered_revenue": expected_recovered_revenue,
            "gross_recovered_revenue": expected_recovered_revenue,
            "expected_cost": expected_cost,
            "retry_cost": expected_cost,
            "expected_net_recovery": expected_net_recovery,
            "net_recovered_revenue": expected_net_recovery,
            "expected_roi": expected_roi,
            "friction_score": friction_scores.get(action_type, 15.0),
            "customer_friction_score": friction_scores.get(action_type, 15.0),
            "rationale": rationales.get(action_type, ""),
        }
        if action_type == "REROUTE":
            item["target_provider"] = rec_provider
            item["target_gateway_routing"] = target_routing_str

        all_candidates.append(item)

    # Persist the immutable historical snapshot
    snapshot_payload = {
        "baseline": no_action_item,
        "candidates": all_candidates,
    }
    try:
        diagnosis.counterfactuals_json = json.dumps(snapshot_payload)
        db.commit()
    except Exception:
        db.rollback()

    active_results = (
        all_candidates if include_extended
        else [c for c in all_candidates if c["action_type"] in standard_action_types]
    )

    if include_baseline:
        return [no_action_item] + active_results

    return active_results


def execute_recovery(
    db: Session,
    incident_id: str,
    action_data: dict,
    user_role: str = "OPERATOR",
    operator_name: str = "operator",
) -> dict:
    """Execute evidence-grounded, backend-authorized recovery action."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()

    if not incident or not diagnosis:
        raise ValueError("Incident or Diagnosis not found")

    # Override role from payload if provided
    role = action_data.get("role", user_role)
    actor = action_data.get("selected_by", operator_name)
    human_approved = bool(action_data.get("human_approved", False))

    # 1. Terminal State Check: Terminal incidents cannot be reopened or re-acted upon.
    if incident.state in TERMINAL_STATES:
        log_audit_event(db, incident.id, actor, "RECOVERY_BLOCKED", {
            "reason": "Incident is already in a terminal state",
            "state": incident.state,
        })
        return {
            "status": "blocked",
            "reason": "terminal_incident",
            "state": incident.state,
        }

    # 2. Guardrail Check: Confidence Threshold (< 0.70)
    if diagnosis.confidence < CONFIDENCE_THRESHOLD:
        target_state = IncidentState.ESCALATED_LOW_CONFIDENCE.value
        if validate_state_transition(incident.state, target_state):
            incident.state = target_state
            db.commit()
        log_audit_event(db, incident.id, "system", "ESCALATION", {
            "reason": f"Diagnostic confidence {diagnosis.confidence:.2f} < threshold {CONFIDENCE_THRESHOLD:.2f}",
            "confidence": diagnosis.confidence,
            "state": incident.state,
        })
        return {
            "status": "escalated",
            "reason": "low_confidence",
            "confidence": diagnosis.confidence,
        }

    # Calculate authoritative at-risk revenue from actual incident window
    at_risk_revenue = _at_risk_revenue(db, incident)

    # 3. Minimum revenue gate: do not auto-act on immaterial exposure (< ₹50,000)
    if at_risk_revenue < MIN_REVENUE_FOR_AUTO_ACTION:
        target_state = IncidentState.ESCALATED_LOW_REVENUE.value
        if validate_state_transition(incident.state, target_state):
            incident.state = target_state
            db.commit()
        log_audit_event(db, incident.id, "system", "ESCALATION", {
            "reason": f"At-risk revenue ₹{at_risk_revenue:,.2f} below auto-action threshold ₹{MIN_REVENUE_FOR_AUTO_ACTION:,.2f}",
            "at_risk_revenue": round(at_risk_revenue, 2),
            "minimum_revenue_for_auto_action": MIN_REVENUE_FOR_AUTO_ACTION,
        })
        return {
            "status": "escalated",
            "reason": "low_revenue",
            "at_risk_revenue": at_risk_revenue,
        }

    # 4. Maximum automatic approval ceiling (> ₹500,000 requires human approval)
    if at_risk_revenue > MAX_REVENUE_FOR_AUTO_APPROVE and not human_approved:
        target_state = IncidentState.AWAITING_HUMAN_APPROVAL.value
        if validate_state_transition(incident.state, target_state):
            incident.state = target_state
            db.commit()
        log_audit_event(db, incident.id, "system", "HUMAN_APPROVAL_REQUIRED", {
            "reason": f"At-risk revenue ₹{at_risk_revenue:,.2f} exceeds auto-approval limit ₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f}",
            "at_risk_revenue": round(at_risk_revenue, 2),
            "maximum_revenue_for_auto_approve": MAX_REVENUE_FOR_AUTO_APPROVE,
        })
        return {
            "status": "pending_human_approval",
            "reason": "high_revenue",
            "at_risk_revenue": at_risk_revenue,
        }

    # 5. Role-aware authorization check: ADMIN or OPERATOR required for all recoveries
    if not can_approve_recovery(role):
        log_audit_event(db, incident.id, actor, "RECOVERY_BLOCKED", {
            "reason": f"Role '{role}' is not authorized to execute or approve recovery. Requires ADMIN or OPERATOR.",
            "role": role,
        })
        return {
            "status": "blocked",
            "reason": "unauthorized_role",
            "role": role,
        }

    if human_approved:
        log_audit_event(db, incident.id, actor, "HUMAN_APPROVAL_GRANTED", {
            "approved_by": actor,
            "role": role,
            "at_risk_revenue": round(at_risk_revenue, 2),
        })

    # 6. Action selection and domain compatibility validation
    action_type = action_data.get("recommended_action")
    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid action type proposed: '{action_type}'")

    if not is_action_compatible(diagnosis.hypothesis, action_type):
        expected_action = ACTION_HYPOTHESIS_MAP.get(diagnosis.hypothesis, "SUPPRESS_RETRIES")
        raise ValueError(
            f"Action '{action_type}' is incompatible with diagnosis '{diagnosis.hypothesis}'. "
            f"Expected '{expected_action}'."
        )

    # Persist RecoveryAction
    recovery_action = RecoveryAction(
        id=f"act_{uuid.uuid4().hex[:12]}",
        incident_id=incident.id,
        action_type=action_type,
        selected_by=actor,
        reasoning_text=action_data.get("reasoning", ""),
        applied_at=datetime.now(),
        approved_by=actor if human_approved else None,
        approved_at=datetime.now() if human_approved else None,
        role=role,
    )
    db.add(recovery_action)
    db.commit()
    db.refresh(recovery_action)

    # Ensure authoritative projection from frozen counterfactual snapshot
    rec_cf = None
    if diagnosis and diagnosis.counterfactuals_json:
        try:
            cf_data = json.loads(diagnosis.counterfactuals_json)
            candidates = cf_data.get("candidates", []) if isinstance(cf_data, dict) else cf_data
            for c in candidates:
                if c.get("action_type") == action_type:
                    rec_cf = c
                    break
        except Exception:
            rec_cf = None

    target_provider = (
        action_data.get("target_provider")
        or (rec_cf.get("target_provider") if rec_cf else None)
        or ("Provider A" if action_type == "REROUTE" else None)
    )
    projected_lift_pp = (
        action_data.get("projected_lift_pp")
        if action_data.get("projected_lift_pp") is not None
        else (rec_cf.get("expected_improvement_pp") if rec_cf else None)
    )
    projected_gross_recovery = (
        action_data.get("projected_gross_recovery")
        if action_data.get("projected_gross_recovery") is not None
        else (rec_cf.get("expected_recovered_revenue") if rec_cf else None)
    )
    projected_net_recovery = (
        action_data.get("projected_net_recovery")
        if action_data.get("projected_net_recovery") is not None
        else (rec_cf.get("expected_net_recovery") if rec_cf else None)
    )

    audit_details = {
        "action": action_type,
        "at_risk_revenue": round(at_risk_revenue, 2),
        "human_approved": human_approved,
        "role": role,
    }
    if target_provider:
        audit_details["target_provider"] = target_provider
    if projected_lift_pp is not None:
        audit_details["projected_lift_pp"] = round(float(projected_lift_pp), 2)
    if projected_gross_recovery is not None:
        audit_details["projected_gross_recovery"] = round(float(projected_gross_recovery), 2)
    if projected_net_recovery is not None:
        audit_details["projected_net_recovery"] = round(float(projected_net_recovery), 2)

    log_audit_event(db, incident.id, actor, "ACTION_SELECTED", audit_details)

    incident.state = IncidentState.ACTION_SELECTED.value
    db.commit()

    # 7. Simulate bounded recovery
    failures = [
        t for t in _incident_transactions(db, incident)
        if not t.success and t.retry_count < MAX_SIMULATED_RETRIES
    ]

    total_failed_txns = len(failures)
    effect_size = EFFECT_SIZES[action_type]
    transactions_to_flip = int(total_failed_txns * effect_size)

    recovered_revenue = 0.0
    flipped_ids = []
    for i in range(transactions_to_flip):
        failures[i].success = True
        flipped_ids.append(failures[i].id)
        if action_type == "REROUTE" and target_provider:
            failures[i].routing_partner = target_provider
        if action_type in {"REROUTE", "ADJUST_RETRY_TIMING", "PAYMENT_METHOD_FALLBACK", "INTELLIGENT_RETRY", "PROVIDER_WEIGHT_ADJUSTMENT"}:
            failures[i].retry_count = min(
                failures[i].retry_count + 1,
                MAX_SIMULATED_RETRIES,
            )
        recovered_revenue += failures[i].amount

    db.commit()
    incident.state = IncidentState.ACTION_APPLIED.value
    db.commit()

    applied_audit = {
        "action": action_type,
        "transactions_flipped": transactions_to_flip,
        "flipped_tx_ids": flipped_ids[:10], # sample
    }
    if target_provider:
        applied_audit["target_provider"] = target_provider

    log_audit_event(db, incident.id, "system", "ACTION_APPLIED", applied_audit)

    # 8. Re-measure outcomes
    all_segment_txns = _incident_transactions(db, incident)
    post_successes = sum(1 for t in all_segment_txns if t.success)
    post_success_rate = (post_successes / len(all_segment_txns) * 100) if all_segment_txns else 0.0
    improvement = post_success_rate - incident.incident_success_rate

    result_state = (
        IncidentState.RESOLVED.value
        if improvement >= MIN_MEASURABLE_IMPROVEMENT_PP
        else IncidentState.ESCALATED_INSUFFICIENT_RECOVERY.value
    )
    incident.state = result_state
    db.commit()

    outcome = Outcome(
        id=f"out_{uuid.uuid4().hex[:12]}",
        recovery_action_id=recovery_action.id,
        pre_success_rate=incident.incident_success_rate,
        post_success_rate=post_success_rate,
        recovered_revenue=recovered_revenue,
        transactions_flipped=transactions_to_flip,
        result=result_state,
    )
    db.add(outcome)
    db.commit()

    # Closed-Loop Learning Hook
    try:
        from .learning import record_recovery_learning
        record_recovery_learning(
            db=db,
            incident=incident,
            recovery_action=recovery_action,
            outcome=outcome,
            predicted_lift=float(round(projected_lift_pp, 2)) if projected_lift_pp is not None else float(round(improvement, 2)),
            predicted_revenue=float(round(projected_gross_recovery, 2)) if projected_gross_recovery is not None else float(round(recovered_revenue, 2)),
        )
    except Exception:
        pass

    log_audit_event(db, incident.id, "system", "OUTCOME_MEASURED", {
        "improvement_pp": round(improvement, 2),
        "recovered_revenue": round(recovered_revenue, 2),
        "result": result_state,
        "at_risk_revenue": round(at_risk_revenue, 2),
        "transactions_flipped": transactions_to_flip,
    })

    return {
        "status": result_state,
        "recovered_revenue": recovered_revenue,
        "improvement": improvement,
        "at_risk_revenue": at_risk_revenue,
        "action_id": recovery_action.id,
    }


def execute_rollback(
    db: Session,
    incident_id: str,
    user_role: str = "OPERATOR",
    operator_name: str = "operator",
    reason: str = "Manual operator rollback",
) -> dict:
    """Roll back applied recovery action, reverting transaction state and updating audit trail."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident not found: {incident_id}")

    if not can_approve_recovery(user_role):
        log_audit_event(db, incident.id, operator_name, "RECOVERY_BLOCKED", {
            "reason": f"Role '{user_role}' not authorized to perform rollback. Requires ADMIN or OPERATOR.",
        })
        return {
            "status": "blocked",
            "reason": "unauthorized_role",
            "role": user_role,
        }

    # Find the most recent non-rollback recovery action
    action = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.incident_id == incident.id, RecoveryAction.is_rollback == False)
        .order_by(RecoveryAction.applied_at.desc())
        .first()
    )

    if not action:
        return {
            "status": "error",
            "message": "No executed recovery action found to roll back.",
        }

    outcome = db.query(Outcome).filter(Outcome.recovery_action_id == action.id).first()

    # Revert transactions: find transactions in the segment where success=True and retry_count > 0
    # and revert up to transactions_flipped count
    txns = _incident_transactions(db, incident)
    flipped_count = outcome.transactions_flipped if outcome else 0
    reverted_count = 0
    reverted_revenue = 0.0

    for t in txns:
        if reverted_count >= flipped_count:
            break
        if t.success and t.retry_count > 0:
            t.success = False
            t.retry_count = max(0, t.retry_count - 1)
            reverted_count += 1
            reverted_revenue += t.amount

    db.commit()

    # Create Rollback RecoveryAction record
    rollback_action = RecoveryAction(
        id=f"act_rb_{uuid.uuid4().hex[:10]}",
        incident_id=incident.id,
        action_type="ROLLBACK",
        selected_by=operator_name,
        reasoning_text=f"Rollback of action {action.id}. Reason: {reason}",
        applied_at=datetime.now(),
        approved_by=operator_name,
        approved_at=datetime.now(),
        role=user_role,
        is_rollback=True,
        rolled_back_from_id=action.id,
    )
    db.add(rollback_action)

    # Set incident state to ROLLED_BACK
    incident.state = IncidentState.ROLLED_BACK.value
    db.commit()

    log_audit_event(db, incident.id, operator_name, "ROLLBACK_EXECUTED", {
        "original_action_id": action.id,
        "original_action_type": action.action_type,
        "reverted_transactions": reverted_count,
        "reverted_revenue": round(reverted_revenue, 2),
        "reason": reason,
        "operator_role": user_role,
    })

    return {
        "status": "ROLLED_BACK",
        "incident_id": incident.id,
        "reverted_transactions": reverted_count,
        "reverted_revenue": round(reverted_revenue, 2),
        "reason": reason,
    }
