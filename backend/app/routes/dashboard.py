from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Transaction, Incident, Outcome
from datetime import datetime, timedelta
from sqlalchemy import func

from ..recovery_agent import _at_risk_revenue

router = APIRouter()

ACTIVE_STATES = [
    "ANOMALY_DETECTED",
    "DIAGNOSED",
    "AWAITING_HUMAN_APPROVAL",
    "ACTION_SELECTED",
    "ACTION_APPLIED"
]

@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    demo_time = datetime.now()
    window_start = demo_time - timedelta(hours=24)
    
    txns = db.query(Transaction).filter(Transaction.timestamp >= window_start, Transaction.timestamp <= demo_time).all()
    total_txns = len(txns)
    success_txns = sum(1 for t in txns if t.success)
    global_rate = (success_txns / total_txns) * 100 if total_txns > 0 else 0
    
    active_incidents = db.query(Incident).filter(Incident.state.in_(ACTIVE_STATES)).all()
    active_count = len(active_incidents)
    revenue_at_risk = sum(_at_risk_revenue(db, inc) for inc in active_incidents)
    
    recovered_rev = db.query(func.sum(Outcome.recovered_revenue)).scalar() or 0.0
    
    return {
        "global_success_rate": round(global_rate, 2),
        "active_incident_count": active_count,
        "revenue_at_risk": round(revenue_at_risk, 2),
        "total_recovered_revenue": round(recovered_rev, 2)
    }