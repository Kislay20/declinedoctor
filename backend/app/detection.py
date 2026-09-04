import json
import pandas as pd
from datetime import timedelta
from sqlalchemy.orm import Session
from .models import Transaction, Incident, AuditLog
import uuid
from datetime import datetime

def detect_anomalies(db: Session, current_time: datetime):
    start_time = current_time - timedelta(days=7)
    txns = db.query(Transaction).filter(Transaction.timestamp >= start_time, Transaction.timestamp <= current_time).all()
    
    if not txns:
        return []

    df = pd.DataFrame([{
        "id": t.id,
        "timestamp": t.timestamp,
        "segment": f"{t.issuer}_{t.payment_method}",
        "issuer": t.issuer,
        "payment_method": t.payment_method,
        "success": t.success
    } for t in txns])

    window_start = current_time - timedelta(hours=12)
    
    baseline_df = df[df["timestamp"] < window_start]
    # FIX: Strictly bound the incident window so it doesn't read future data
    incident_df = df[(df["timestamp"] >= window_start) & (df["timestamp"] <= current_time)]
    
    detected_incidents = []
    
    baseline_stats = baseline_df.groupby("segment")["success"].agg(["mean", "count"]).reset_index()
    baseline_stats = baseline_stats.rename(columns={"mean": "baseline_rate"})
    
    incident_stats = incident_df.groupby("segment")["success"].agg(["mean", "count"]).reset_index()
    incident_stats = incident_stats.rename(columns={"mean": "incident_rate", "count": "sample_size"})
    
    comparison = pd.merge(baseline_stats, incident_stats, on="segment")
    comparison["drop_pp"] = (comparison["baseline_rate"] - comparison["incident_rate"]) * 100
    
    anomalies = comparison[(comparison["drop_pp"] >= 15.0) & (comparison["sample_size"] >= 50)]

    
    for _, row in anomalies.iterrows():
        issuer, method = row["segment"].split("_")
        
        segment_failures = len(
            incident_df[
                (incident_df["segment"] == row["segment"])
                & (incident_df["success"] == False)
            ]
        )

        method_failures = len(
            incident_df[
                (incident_df["payment_method"] == method)
                & (incident_df["success"] == False)
            ]
        )
        concentration_ratio = (
            segment_failures / method_failures
            if method_failures > 0
            else 0
        )
        
        incident = Incident(
            id=f"inc_{uuid.uuid4().hex[:12]}",
            detected_at=current_time,
            segment_issuer=issuer,
            segment_payment_method=method,
            window_start=window_start,
            window_end=current_time,
            # FIX: Multiply by 100 so it stores 93.0 instead of 0.93
            baseline_success_rate=row["baseline_rate"] * 100,
            incident_success_rate=row["incident_rate"] * 100,
            drop_pp=row["drop_pp"],
            concentration_ratio=concentration_ratio,
            sample_size=row["sample_size"],
            state="ANOMALY_DETECTED"
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        # Real backend audit log for ANOMALY_DETECTED
        audit = AuditLog(
            incident_id=incident.id,
            timestamp=current_time,
            actor="system",
            event_type="ANOMALY_DETECTED",
            details_json=json.dumps({
                "segment": f"{issuer} {method}",
                "drop_pp": f"{row['drop_pp']:.1f}%",
                "sample_size": int(row["sample_size"]),
                "baseline_success_rate": f"{row['baseline_rate'] * 100:.1f}%",
                "incident_success_rate": f"{row['incident_rate'] * 100:.1f}%",
                "concentration_ratio": f"{concentration_ratio * 100:.1f}%"
            })
        )
        db.add(audit)
        db.commit()

        detected_incidents.append(incident)
        
    return detected_incidents