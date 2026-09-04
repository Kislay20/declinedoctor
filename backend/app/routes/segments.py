"""DeclineDoctor Segment Explorer API.

Provides granular segment analytics and decline breakdown filtered by issuer,
payment method, and decline code.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Transaction, Incident

router = APIRouter(prefix="/api/segments", tags=["segments"])


@router.get("/analytics")
def get_segment_analytics(
    issuer: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    decline_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve historical success rates, failure codes, and incidents grouped by segment."""
    query = db.query(Transaction)
    if issuer:
        query = query.filter(Transaction.issuer == issuer)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)
    if decline_code:
        query = query.filter(Transaction.decline_code == decline_code)

    transactions = query.all()

    # Group by (issuer, payment_method)
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for tx in transactions:
        key = (tx.issuer, tx.payment_method)
        if key not in grouped:
            grouped[key] = {
                "issuer": tx.issuer,
                "payment_method": tx.payment_method,
                "total_transactions": 0,
                "successful_transactions": 0,
                "failed_transactions": 0,
                "total_volume": 0.0,
                "declined_volume": 0.0,
                "decline_codes": {},
            }
        g = grouped[key]
        g["total_transactions"] += 1
        g["total_volume"] += tx.amount
        if tx.success:
            g["successful_transactions"] += 1
        else:
            g["failed_transactions"] += 1
            g["declined_volume"] += tx.amount
            code = tx.decline_code or "unknown"
            g["decline_codes"][code] = g["decline_codes"].get(code, 0) + 1

    results = []
    for key, data in grouped.items():
        total = data["total_transactions"]
        success_rate = (data["successful_transactions"] / total * 100) if total > 0 else 0.0
        
        # Fetch matching incidents for this segment
        incidents = (
            db.query(Incident)
            .filter(
                Incident.segment_issuer == data["issuer"],
                Incident.segment_payment_method == data["payment_method"],
            )
            .order_by(Incident.detected_at.desc())
            .all()
        )

        incident_summaries = [
            {
                "id": inc.id,
                "state": inc.state,
                "severity": getattr(inc, "severity", "MEDIUM"),
                "drop_pp": round(inc.drop_pp, 2),
                "created_at": inc.detected_at.isoformat() if inc.detected_at else None,
            }
            for inc in incidents
        ]

        results.append({
            "issuer": data["issuer"],
            "payment_method": data["payment_method"],
            "total_transactions": data["total_transactions"],
            "successful_transactions": data["successful_transactions"],
            "failed_transactions": data["failed_transactions"],
            "success_rate": round(success_rate, 2),
            "total_volume": round(data["total_volume"], 2),
            "declined_volume": round(data["declined_volume"], 2),
            "decline_codes": data["decline_codes"],
            "incidents": incident_summaries,
        })

    # Available filter choices
    all_issuers = [r[0] for r in db.query(Transaction.issuer).distinct().all() if r[0]]
    all_methods = [r[0] for r in db.query(Transaction.payment_method).distinct().all() if r[0]]
    all_codes = [r[0] for r in db.query(Transaction.decline_code).distinct().all() if r[0]]

    return {
        "segments": sorted(results, key=lambda s: s["declined_volume"], reverse=True),
        "filters": {
            "issuers": sorted(all_issuers),
            "payment_methods": sorted(all_methods),
            "decline_codes": sorted(all_codes),
        },
    }


@router.get("/bin-intelligence")
def get_bin_intelligence_route(
    issuer: Optional[str] = Query(None),
    payment_method: Optional[str] = Query("card"),
    bin: Optional[str] = Query(None),
    incident_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve deep BIN-level telemetry, failure distribution, and isolation diagnosis."""
    from ..bin_intelligence import analyze_bin_telemetry
    return analyze_bin_telemetry(
        db=db,
        issuer=issuer,
        payment_method=payment_method or "card",
        target_bin=bin,
        incident_id=incident_id,
    )
