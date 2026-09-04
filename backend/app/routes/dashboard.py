from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Transaction, Incident, Diagnosis, RecoveryAction, Outcome
from datetime import datetime, timedelta
from sqlalchemy import func
from typing import Dict, Any, List
from ..recovery_agent import _at_risk_revenue
from ..policy import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    CONFIDENCE_THRESHOLD,
    MIN_REVENUE_FOR_AUTO_ACTION,
    MAX_REVENUE_FOR_AUTO_APPROVE,
    ACTION_HYPOTHESIS_MAP,
)

router = APIRouter()


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    demo_time = datetime.now()
    window_start = demo_time - timedelta(hours=24)

    # 1. Global Success Rate in past 24 hours
    txns = (
        db.query(Transaction)
        .filter(Transaction.timestamp >= window_start, Transaction.timestamp <= demo_time)
        .all()
    )
    total_txns = len(txns)
    success_txns = sum(1 for t in txns if t.success)
    global_rate = (success_txns / total_txns) * 100 if total_txns > 0 else 0.0

    # 2. Active Incidents & Revenue at Risk
    all_incidents = db.query(Incident).all()
    active_incidents = [inc for inc in all_incidents if inc.state in ACTIVE_STATES]
    active_count = len(active_incidents)
    revenue_at_risk = sum(_at_risk_revenue(db, inc) for inc in active_incidents)

    # 3. Recovered Revenue from real outcomes
    recovered_rev = db.query(func.sum(Outcome.recovered_revenue)).scalar() or 0.0
    transactions_flipped = db.query(func.sum(Outcome.transactions_flipped)).scalar() or 0

    # 4. Extended Metrics (Phase 5)
    # Total at risk across all incidents (historical + active)
    total_at_risk_all = sum(_at_risk_revenue(db, inc) for inc in all_incidents)
    recovery_rate = (
        round((recovered_rev / total_at_risk_all * 100), 2)
        if total_at_risk_all > 0
        else 0.0
    )

    actions_executed = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.is_rollback == False)
        .count()
    )
    escalated_incidents = sum(
        1 for inc in all_incidents if inc.state.startswith("ESCALATED_")
    )
    stopped_incidents = sum(
        1 for inc in all_incidents if inc.state in TERMINAL_STATES
    )
    human_approvals_granted = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.approved_by.isnot(None))
        .count()
    )

    # Recovery effectiveness: average success rate improvement in percentage points
    outcomes = db.query(Outcome).all()
    avg_improvement = (
        round(
            sum(o.post_success_rate - o.pre_success_rate for o in outcomes)
            / len(outcomes),
            2,
        )
        if outcomes
        else 0.0
    )

    # 5. Revenue Recovery Funnel (Phase 6)
    # AT RISK -> DIAGNOSED -> ELIGIBLE -> RECOVERED
    funnel_at_risk = total_at_risk_all

    # Diagnosed revenue: sum at-risk revenue for incidents with a Diagnosis record
    diagnosed_incident_ids = {d.incident_id for d in db.query(Diagnosis.incident_id).all()}
    funnel_diagnosed = sum(
        _at_risk_revenue(db, inc)
        for inc in all_incidents
        if inc.id in diagnosed_incident_ids
    )

    # Eligible revenue: diagnosed with confidence >= 0.70 and at_risk >= 50,000
    eligible_revenue = 0.0
    for inc in all_incidents:
        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()
        if diag and diag.confidence >= CONFIDENCE_THRESHOLD:
            at_risk = _at_risk_revenue(db, inc)
            if at_risk >= MIN_REVENUE_FOR_AUTO_ACTION:
                eligible_revenue += at_risk

    funnel_eligible = eligible_revenue
    funnel_recovered = recovered_rev

    # 6. Approval Queue (Phase 7)
    awaiting_approval = [
        inc for inc in all_incidents if inc.state == "AWAITING_HUMAN_APPROVAL"
    ]
    approval_queue = []
    for inc in awaiting_approval:
        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()
        at_risk = _at_risk_revenue(db, inc)
        prop_action = (
            ACTION_HYPOTHESIS_MAP.get(diag.hypothesis, "REROUTE")
            if diag
            else "REROUTE"
        )
        approval_queue.append({
            "incident_id": inc.id,
            "segment_issuer": inc.segment_issuer,
            "segment_payment_method": inc.segment_payment_method,
            "severity": getattr(inc, "severity", "HIGH"),
            "revenue_at_risk": round(at_risk, 2),
            "confidence": diag.confidence if diag else 0.0,
            "hypothesis": diag.hypothesis if diag else "UNKNOWN",
            "proposed_action": prop_action,
            "reason": (
                f"Revenue at risk (₹{at_risk:,.2f}) exceeds the auto-approval threshold "
                f"(₹{MAX_REVENUE_FOR_AUTO_APPROVE:,.2f}). Requires authorized human verification."
            ),
            "created_at": inc.detected_at.isoformat() if inc.detected_at else None,
            "allowed_roles": ["ADMIN", "OPERATOR"],
        })

    return {
        # Core original fields (backwards compatibility)
        "global_success_rate": round(global_rate, 2),
        "active_incident_count": active_count,
        "revenue_at_risk": round(revenue_at_risk, 2),
        "total_recovered_revenue": round(recovered_rev, 2),
        # Extended metrics (Phase 5)
        "recovery_rate_pct": recovery_rate,
        "transactions_affected": transactions_flipped,
        "actions_executed": actions_executed,
        "escalated_incidents": escalated_incidents,
        "stopped_incidents": stopped_incidents,
        "human_approvals_granted": human_approvals_granted,
        "average_recovery_improvement_pp": avg_improvement,
        # Revenue Funnel (Phase 6)
        "funnel": {
            "at_risk": round(funnel_at_risk, 2),
            "diagnosed": round(funnel_diagnosed, 2),
            "eligible": round(funnel_eligible, 2),
            "recovered": round(funnel_recovered, 2),
        },
        # Approval Queue (Phase 7)
        "approval_queue": approval_queue,
    }