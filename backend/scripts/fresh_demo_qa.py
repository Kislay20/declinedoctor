import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal, engine, Base
from scripts.seed_data import seed_database
from app.detection import detect_anomalies
from app.diagnosis import diagnose_incident
from app.recovery_agent import execute_recovery, _at_risk_revenue
from app.models import Incident, Diagnosis, RecoveryAction, Outcome, AuditLog
from app.routes.dashboard import get_dashboard_summary

print("==============================================")
print("=== 1. FRESH DEMO SEED & ANOMALY DETECTION ===")
print("==============================================")
seed_database()
db = SessionLocal()
now = datetime.now()
detected = detect_anomalies(db, now)
print(f"Detected {len(detected)} anomalies.")

print("\n==============================================")
print("=== 2. INITIAL DASHBOARD METRICS (ACTIVE)  ===")
print("==============================================")
summary_initial = get_dashboard_summary(db)
print("Dashboard summary:", json.dumps(summary_initial, indent=2))
assert summary_initial["active_incident_count"] == 3
assert summary_initial["revenue_at_risk"] > 1000000

print("\n==============================================")
print("=== 3. SCENARIO 1: BANK X (CARD)           ===")
print("==============================================")
bank_x = db.query(Incident).filter(Incident.segment_issuer == "Bank X").first()
assert bank_x is not None
print(f"Bank X Initial State: {bank_x.state}, Drop: {bank_x.drop_pp:.1f}pp, Sample: {bank_x.sample_size}")
diag_bank_x = diagnose_incident(db, bank_x.id)
at_risk_bank_x = _at_risk_revenue(db, bank_x)
print(f"Bank X Diagnosed: Hypothesis={diag_bank_x.hypothesis}, Confidence={diag_bank_x.confidence:.2f}, At-Risk=Rs.{at_risk_bank_x:,.2f}")
assert diag_bank_x.confidence >= 0.70
assert bank_x.state == "DIAGNOSED"
assert at_risk_bank_x < 500000

# Execute recovery (REROUTE)
rec_bank_x = execute_recovery(db, bank_x.id, {"recommended_action": "REROUTE", "selected_by": "system"})
print("Bank X Recovery Result:", rec_bank_x["status"], f"Recovered: Rs.{rec_bank_x['recovered_revenue']:,.2f}")
assert rec_bank_x["status"] == "RESOLVED"
assert rec_bank_x["recovered_revenue"] > 0
assert bank_x.state == "RESOLVED"

# Verify terminal protection
diag_bank_x_term = diagnose_incident(db, bank_x.id)
assert bank_x.state == "RESOLVED"
rec_bank_x_term = execute_recovery(db, bank_x.id, {"recommended_action": "REROUTE", "selected_by": "system"})
assert rec_bank_x_term["status"] == "blocked"
assert rec_bank_x_term["reason"] == "terminal_incident"

print("\n==============================================")
print("=== 4. SCENARIO 2: SBI (UPI)               ===")
print("==============================================")
sbi = db.query(Incident).filter(Incident.segment_issuer == "SBI").first()
assert sbi is not None
print(f"SBI Initial State: {sbi.state}, Drop: {sbi.drop_pp:.1f}pp, Sample: {sbi.sample_size}")
diag_sbi = diagnose_incident(db, sbi.id)
at_risk_sbi = _at_risk_revenue(db, sbi)
print(f"SBI Diagnosed: Hypothesis={diag_sbi.hypothesis}, Confidence={diag_sbi.confidence:.2f}, State={sbi.state}")
assert diag_sbi.confidence < 0.70
assert sbi.state == "ESCALATED_LOW_CONFIDENCE"

# Attempt recovery - must be blocked!
rec_sbi = execute_recovery(db, sbi.id, {"recommended_action": "SUPPRESS_RETRIES", "selected_by": "system"})
print("SBI Recovery Attempt on Low-Confidence Incident:", rec_sbi)
assert rec_sbi["status"] == "blocked"
assert rec_sbi["reason"] == "terminal_incident"
assert sbi.state == "ESCALATED_LOW_CONFIDENCE"

print("\n==============================================")
print("=== 5. SCENARIO 3: ICICI (HIGH-VALUE)      ===")
print("==============================================")
icici = db.query(Incident).filter(Incident.segment_issuer == "ICICI").first()
assert icici is not None
print(f"ICICI Initial State: {icici.state}, Drop: {icici.drop_pp:.1f}pp, Sample: {icici.sample_size}")
diag_icici = diagnose_incident(db, icici.id)
at_risk_icici = _at_risk_revenue(db, icici)
print(f"ICICI Diagnosed: Hypothesis={diag_icici.hypothesis}, Confidence={diag_icici.confidence:.2f}, At-Risk=Rs.{at_risk_icici:,.2f}")
assert diag_icici.confidence >= 0.70
assert at_risk_icici > 500000

# Attempt recovery WITHOUT human approval - must be blocked and transitioned to AWAITING_HUMAN_APPROVAL
rec_icici_unapproved = execute_recovery(db, icici.id, {"recommended_action": "REROUTE", "selected_by": "system", "human_approved": False})
print("ICICI Recovery Attempt without Human Approval:", rec_icici_unapproved)
assert rec_icici_unapproved["status"] == "pending_human_approval"
assert rec_icici_unapproved["reason"] == "high_revenue"
assert icici.state == "AWAITING_HUMAN_APPROVAL"

# Execute recovery WITH explicit human approval
rec_icici_approved = execute_recovery(db, icici.id, {"recommended_action": "REROUTE", "selected_by": "system", "human_approved": True})
print("ICICI Recovery Attempt with Explicit Human Approval:", rec_icici_approved["status"], f"Recovered: Rs.{rec_icici_approved['recovered_revenue']:,.2f}")
assert rec_icici_approved["status"] == "RESOLVED"
assert rec_icici_approved["recovered_revenue"] > 0
assert icici.state == "RESOLVED"

# Verify terminal protection
rec_icici_term = execute_recovery(db, icici.id, {"recommended_action": "REROUTE", "selected_by": "system", "human_approved": True})
assert rec_icici_term["status"] == "blocked"
assert rec_icici_term["reason"] == "terminal_incident"

print("\n==============================================")
print("=== 6. FINAL DASHBOARD METRICS (RESOLVED)  ===")
print("==============================================")
summary_final = get_dashboard_summary(db)
print("Final Dashboard summary:", json.dumps(summary_final, indent=2))
assert summary_final["active_incident_count"] == 0
assert summary_final["revenue_at_risk"] == 0.0
assert summary_final["total_recovered_revenue"] > 350000

print("\n==============================================")
print("=== 7. AUDIT TRAIL VERIFICATION            ===")
print("==============================================")
for inc in [bank_x, sbi, icici]:
    logs = db.query(AuditLog).filter(AuditLog.incident_id == inc.id).order_by(AuditLog.timestamp.asc()).all()
    events = [l.event_type for l in logs]
    print(f"{inc.segment_issuer} {inc.segment_payment_method} Audit Events: {' -> '.join(events)}")

print("\n>>> ALL DEMO QA ACCEPTANCE CRITERIA MET WITH 100% SUCCESS! <<<")
