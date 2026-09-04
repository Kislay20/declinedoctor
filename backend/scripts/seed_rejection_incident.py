"""Seed a fresh high-value ICICI test incident specifically for human rejection testing.

Requirements:
- Exposure > ₹500,000 (e.g. ₹660,000)
- Canonical Incident persistence model with full advanced_stats_json
- Hash-chained ANOMALY_DETECTED audit log entry matching production detection pipeline
- Enters ANOMALY_DETECTED state
- Has genuine failed & success transactions in its window
- Diagnosis produces confidence >= 0.70 (0.89) and recommended action REROUTE
- Preserves all existing incidents (Bank X, SBI, resolved ICICI)
"""
import os
import sys
import json
import math
from datetime import datetime, timedelta

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.database import SessionLocal
from app.models import Incident, Transaction, Diagnosis, RecoveryAction, Outcome, AuditLog
from app.recovery_agent import _at_risk_revenue
from app.audit import log_audit_event


def seed_rejection_incident(db=None):
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True
    try:
        incident_id = "inc_icici_rejection_test"

        # 1. Clean up any prior test run of THIS specific test incident only
        db.query(AuditLog).filter(AuditLog.incident_id == incident_id).delete()
        db.query(Outcome).filter(Outcome.id.like(f"%{incident_id}%")).delete()
        db.query(RecoveryAction).filter(RecoveryAction.incident_id == incident_id).delete()
        db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).delete()
        db.query(Transaction).filter(Transaction.id.like("tx_rej_%")).delete()
        db.query(Incident).filter(Incident.id == incident_id).delete()
        db.commit()

        # 2. Window definition (current time, strictly after earlier historical demo windows)
        now = datetime.now()
        window_start = now - timedelta(minutes=30)
        window_end = now

        # Statistical calculations matching canonical detection.py model
        n1 = 140
        p1 = 0.95
        n2 = 120
        p2 = 0.5417
        drop_pp = round((p1 - p2) * 100, 2)
        concentration_ratio = 0.85

        pooled_p = (n1 * p1 + n2 * p2) / (n1 + n2)
        se_pooled = math.sqrt(pooled_p * (1.0 - pooled_p) * (1.0 / n1 + 1.0 / n2))
        z_score = round((p1 - p2) / se_pooled, 2)
        p_value = round(math.erfc(abs(z_score) / math.sqrt(2)), 6)
        cusum = round(max(0.0, drop_pp * math.sqrt(n2 / 100.0)), 2)
        anomaly_score = min(
            100.0,
            round(
                (0.40 * min(drop_pp * 2.0, 100.0))
                + (0.30 * min(abs(z_score) * 12.0, 100.0))
                + (0.20 * (concentration_ratio * 100.0))
                + (0.10 * min(n2, 100.0)),
                1,
            ),
        )

        advanced_stats = {
            "z_score": z_score,
            "p_value": p_value,
            "statistically_significant": True,
            "95_ci": [45.2, 63.14],
            "baseline_95_ci": [91.4, 98.6],
            "incident_95_ci": [45.2, 63.14],
            "confidence_interval_95": [45.2, 63.14],
            "ewma": 54.17,
            "final_ewma_rate": 54.17,
            "ewma_success_rate": 54.17,
            "cusum_score": cusum,
            "anomaly_score": anomaly_score,
            "drift_severity": "HIGH_DRIFT",
            "primary_detector": f"Success rate dropped {drop_pp:.1f}pp below trailing baseline",
            "supporting_detectors": {
                "ewma_anomaly": True,
                "zscore_anomaly": True,
                "cusum_anomaly": True,
                "rolling_baseline_deviation_pp": drop_pp,
            },
            "detection_explanation": (
                f"Triggered by primary threshold (drop {drop_pp:.1f}pp >= 15pp, sample {n2} >= 50). "
                f"Corroborated by z-score {z_score} (p < 0.001), CUSUM {cusum}, and EWMA 54.2%."
            ),
        }

        # 3. Create fresh high-value ICICI incident in ANOMALY_DETECTED with canonical schema
        incident = Incident(
            id=incident_id,
            detected_at=now,
            segment_issuer="ICICI",
            segment_payment_method="card",
            window_start=window_start,
            window_end=window_end,
            baseline_success_rate=95.0,
            incident_success_rate=54.17,
            drop_pp=drop_pp,
            concentration_ratio=concentration_ratio,
            sample_size=n2,
            state="ANOMALY_DETECTED",
            severity="CRITICAL",
            advanced_stats_json=json.dumps(advanced_stats),
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        # 4. Hash-chained initial audit log entry for ANOMALY_DETECTED (canonical audit trail)
        log_audit_event(
            db=db,
            incident_id=incident.id,
            actor="system",
            event_type="ANOMALY_DETECTED",
            details={
                "segment": "ICICI card",
                "drop_pp": f"{drop_pp:.1f}%",
                "sample_size": n2,
                "baseline_success_rate": "95.0%",
                "incident_success_rate": "54.2%",
                "concentration_ratio": f"{concentration_ratio * 100:.1f}%",
                "z_score": z_score,
                "p_value": p_value,
                "significant": True,
            },
            timestamp=now,
        )

        # 5. Generate 55 failed transactions of ₹12,000 each => ₹660,000 at-risk exposure (> ₹500,000)
        transactions = []
        for i in range(55):
            ts = window_start + timedelta(minutes=(i * 28) / 55)
            transactions.append(Transaction(
                id=f"tx_rej_fail_{i:03d}",
                merchant_id="merchant_demo_01",
                amount=12000.0,
                timestamp=ts,
                payment_method="card",
                issuer="ICICI",
                card_network="Visa",
                card_bin="476543",
                decline_code="processor_declined",
                decline_reason="Routing gateway rejected the BIN path",
                retry_count=0,
                customer_id=f"cust_rej_f_{i}",
                routing_partner="Router_Alpha",
                success=False,
            ))

        # 6. Generate 65 successful transactions to provide sample_size = 120 and stable detection metrics
        for i in range(65):
            ts = window_start + timedelta(minutes=(i * 28) / 65)
            transactions.append(Transaction(
                id=f"tx_rej_succ_{i:03d}",
                merchant_id="merchant_demo_01",
                amount=4500.0,
                timestamp=ts,
                payment_method="card",
                issuer="ICICI",
                card_network="Visa",
                card_bin="476543",
                decline_code=None,
                decline_reason=None,
                retry_count=0,
                customer_id=f"cust_rej_s_{i}",
                routing_partner="Provider A",
                success=True,
            ))

        db.add_all(transactions)
        db.commit()

        # 7. Verify exposure and state
        at_risk = _at_risk_revenue(db, incident)
        print(f"Fresh Incident ID: {incident.id}")
        print(f"State: {incident.state}")
        print(f"Issuer: {incident.segment_issuer} {incident.segment_payment_method}")
        print(f"At-Risk Revenue: INR {at_risk:,.2f} (> INR 500,000 dual-control threshold)")
        print(f"Total Transactions: {len(transactions)}")
        return incident

    finally:
        if own_db:
            db.close()


if __name__ == "__main__":
    seed_rejection_incident()
