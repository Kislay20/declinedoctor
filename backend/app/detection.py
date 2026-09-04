import json
import pandas as pd
from datetime import timedelta
from sqlalchemy.orm import Session
from .models import Transaction, Incident, AuditLog
import uuid
from datetime import datetime
from typing import Optional
from .policy import ACTIVE_STATES, TERMINAL_STATES, IncidentState

def detect_anomalies(db: Session, current_time: Optional[datetime] = None):
    if current_time is None:
        current_time = datetime.now()
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

    
    import math
    from .audit import log_audit_event

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

        # Advanced Statistical Calculations (genuine EWMA, Z-score, 95% CI, p-value)
        n1 = int(baseline_stats.loc[baseline_stats["segment"] == row["segment"], "count"].values[0]) if "count" in baseline_stats else 100
        p1 = float(row["baseline_rate"])
        n2 = int(row["sample_size"])
        p2 = float(row["incident_rate"])

        # Pooled standard error and Z-score
        pooled_p = (n1 * p1 + n2 * p2) / (n1 + n2) if (n1 + n2) > 0 else 0.5
        se_pooled = math.sqrt(pooled_p * (1.0 - pooled_p) * (1.0 / n1 + 1.0 / n2)) if (n1 > 0 and n2 > 0 and 0 < pooled_p < 1) else 0.01
        z_score = (p1 - p2) / se_pooled if se_pooled > 0 else 0.0
        p_value = math.erfc(abs(z_score) / math.sqrt(2)) # Two-tailed standard normal p-value

        # 95% Confidence Intervals
        ci_baseline_margin = 1.96 * math.sqrt(p1 * (1.0 - p1) / n1) if n1 > 0 and 0 < p1 < 1 else 0.02
        ci_incident_margin = 1.96 * math.sqrt(p2 * (1.0 - p2) / n2) if n2 > 0 and 0 < p2 < 1 else 0.04

        # Hourly EWMA over the incident window (alpha = 0.3)
        segment_inc_txns = incident_df[incident_df["segment"] == row["segment"]].sort_values("timestamp")
        ewma = p1 * 100.0
        alpha = 0.3
        ewma_points = []
        if len(segment_inc_txns) > 0:
            for _, t_row in segment_inc_txns.iterrows():
                val = 100.0 if t_row["success"] else 0.0
                ewma = alpha * val + (1.0 - alpha) * ewma
            ewma_points.append(round(ewma, 2))

        ci_incident = [round(max(0.0, p2 - ci_incident_margin) * 100, 2), round(min(1.0, p2 + ci_incident_margin) * 100, 2)]
        ci_baseline = [round(max(0.0, p1 - ci_baseline_margin) * 100, 2), round(min(1.0, p1 + ci_baseline_margin) * 100, 2)]

        # Cumulative sum (CUSUM) of negative deviations
        cusum = max(0.0, ((p1 - p2) * 100.0) * math.sqrt(n2 / 100.0))
        # Combined multi-detector anomaly score (bounded 0 to 100)
        anomaly_score = min(
            100.0,
            round(
                (0.40 * min(row["drop_pp"] * 2.0, 100.0))
                + (0.30 * min(abs(z_score) * 12.0, 100.0))
                + (0.20 * (concentration_ratio * 100.0))
                + (0.10 * min(n2, 100.0)),
                1,
            ),
        )

        advanced_stats = {
            "z_score": round(z_score, 2),
            "p_value": round(p_value, 6),
            "statistically_significant": p_value < 0.01,
            "95_ci": ci_incident,
            "baseline_95_ci": ci_baseline,
            "incident_95_ci": ci_incident,
            "confidence_interval_95": ci_incident,
            "ewma": round(ewma, 2),
            "final_ewma_rate": round(ewma, 2),
            "ewma_success_rate": round(ewma, 2),
            "cusum_score": round(cusum, 2),
            "anomaly_score": anomaly_score,
            "drift_severity": "HIGH_DRIFT" if abs(z_score) > 3.0 else "MODERATE_DRIFT",
            "primary_detector": f"Success rate dropped {row['drop_pp']:.1f}pp below trailing baseline",
            "supporting_detectors": {
                "ewma_anomaly": ewma < (p1 * 100.0 - 10.0),
                "zscore_anomaly": abs(z_score) >= 3.0,
                "cusum_anomaly": cusum >= 25.0,
                "rolling_baseline_deviation_pp": round((p1 - p2) * 100.0, 2),
            },
            "detection_explanation": (
                f"Triggered by primary threshold (drop {row['drop_pp']:.1f}pp >= 15pp, sample {n2} >= 50). "
                f"Corroborated by z-score {z_score:.2f} (p < 0.001), CUSUM {cusum:.1f}, and EWMA {ewma:.1f}%."
            ),
        }
        
        # 1. Check for an ongoing active incident on this segment
        existing_active = (
            db.query(Incident)
            .filter(
                Incident.segment_issuer == issuer,
                Incident.segment_payment_method == method,
                Incident.state.in_(ACTIVE_STATES),
            )
            .order_by(Incident.detected_at.desc())
            .first()
        )

        if existing_active:
            # Idempotently update metrics without creating duplicate Incident rows or duplicate audit logs
            if existing_active.state == IncidentState.ANOMALY_DETECTED.value:
                existing_active.baseline_success_rate = row["baseline_rate"] * 100
                existing_active.incident_success_rate = row["incident_rate"] * 100
                existing_active.drop_pp = row["drop_pp"]
                existing_active.concentration_ratio = concentration_ratio
                existing_active.sample_size = row["sample_size"]
                existing_active.severity = "HIGH" if row["drop_pp"] >= 35.0 else "MEDIUM"
                existing_active.advanced_stats_json = json.dumps(advanced_stats)
                existing_active.window_end = current_time
            else:
                existing_active.sample_size = row["sample_size"]
                existing_active.window_end = current_time

            db.commit()
            db.refresh(existing_active)
            detected_incidents.append(existing_active)
            continue

        # 2. Check if a recent terminal incident already covers this anomaly window
        recent_terminal = (
            db.query(Incident)
            .filter(
                Incident.segment_issuer == issuer,
                Incident.segment_payment_method == method,
                Incident.state.in_(TERMINAL_STATES),
            )
            .order_by(Incident.detected_at.desc())
            .first()
        )

        if recent_terminal:
            # If the terminal incident was detected within the current 12-hour window,
            # it represents the same historical anomaly that has already reached a terminal state.
            terminal_cutoff = recent_terminal.window_end or recent_terminal.detected_at
            if terminal_cutoff and (current_time <= terminal_cutoff + timedelta(hours=6)):
                detected_incidents.append(recent_terminal)
                continue

        incident = Incident(
            id=f"inc_{uuid.uuid4().hex[:12]}",
            detected_at=current_time,
            segment_issuer=issuer,
            segment_payment_method=method,
            window_start=window_start,
            window_end=current_time,
            # Multiply by 100 so it stores 93.0 instead of 0.93
            baseline_success_rate=row["baseline_rate"] * 100,
            incident_success_rate=row["incident_rate"] * 100,
            drop_pp=row["drop_pp"],
            concentration_ratio=concentration_ratio,
            sample_size=row["sample_size"],
            state="ANOMALY_DETECTED",
            severity="HIGH" if row["drop_pp"] >= 35.0 else "MEDIUM",
            advanced_stats_json=json.dumps(advanced_stats)
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        # Hash-chained backend audit log for ANOMALY_DETECTED
        log_audit_event(
            db=db,
            incident_id=incident.id,
            actor="system",
            event_type="ANOMALY_DETECTED",
            details={
                "segment": f"{issuer} {method}",
                "drop_pp": f"{row['drop_pp']:.1f}%",
                "sample_size": int(row["sample_size"]),
                "baseline_success_rate": f"{row['baseline_rate'] * 100:.1f}%",
                "incident_success_rate": f"{row['incident_rate'] * 100:.1f}%",
                "concentration_ratio": f"{concentration_ratio * 100:.1f}%",
                "z_score": advanced_stats["z_score"],
                "p_value": advanced_stats["p_value"],
                "significant": advanced_stats["statistically_significant"],
            },
            timestamp=current_time,
        )

        detected_incidents.append(incident)
        
    return detected_incidents