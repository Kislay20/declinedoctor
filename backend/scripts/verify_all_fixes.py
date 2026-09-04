import json
import urllib.request
import urllib.parse
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000/api"

def request(method, path, data=None, role=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if role:
        headers["X-User-Role"] = role
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== STARTING COMPREHENSIVE END-TO-END VERIFICATION ===")

# Reset demo data first
print("\n--- 1. Resetting demo data ---")
seed_res = request("POST", "/simulate/inject")
print("Reset response:", seed_res)

# A. Dashboard Verification
print("\n--- A. Dashboard Verification ---")
summary = request("GET", "/dashboard/summary")
print(f"Active Incidents: {summary['active_incident_count']}")
print(f"Revenue at Risk: Rs.{summary['revenue_at_risk']:,.2f}")
print(f"Global Success Rate: {summary['global_success_rate']:.2f}%")
print(f"Funnel At Risk: Rs.{summary['funnel']['at_risk']:,.2f}")

assert summary["active_incident_count"] == 3
assert summary["revenue_at_risk"] > 1000000

incidents = request("GET", "/incidents")
assert len(incidents) == 3
for inc in incidents:
    issuer = inc["segment_issuer"]
    at_risk = inc["at_risk_revenue"]
    drop_pp = inc["drop_pp"]
    baseline = inc["baseline_success_rate"]
    incident_rate = inc["incident_success_rate"]
    sample = inc["sample_size"]
    print(f"  Incident {inc['id']} ({issuer}): Baseline={baseline:.2f}%, Rate={incident_rate:.2f}%, Drop={drop_pp:.2f}pp, Risk=Rs.{at_risk:,.2f}, Sample={sample}")
    assert at_risk > 0, f"{issuer} has 0 at-risk revenue"
    assert drop_pp > 0, f"{issuer} has non-positive drop"

# B. Bank X Flow
print("\n--- B. Scenario 1: Bank X (Card) Flow ---")
bank_x = next(i for i in incidents if i["segment_issuer"] == "Bank X")
bank_x_id = bank_x["id"]

# Check safety check BEFORE diagnosis
safety_pre = request("GET", f"/incidents/{bank_x_id}/safety")
print("Pre-diagnosis safety banner status:", safety_pre["status"])
print("Pre-diagnosis safety banner reason:", safety_pre["reason"])
print("Pre-diagnosis confidence check value:", safety_pre["confidence_check"]["value"])
assert safety_pre["status"] == "RECOVERY_NOT_YET_EVALUATED"
assert safety_pre["confidence_check"]["value"] is None
assert "Run diagnosis" in safety_pre["reason"]

# Check advanced stats on incident
inc_detail_pre = request("GET", f"/incidents/{bank_x_id}")
adv_stats = json.loads(inc_detail_pre["incident"]["advanced_stats_json"])
print("Advanced Detection Statistics:", {
    "z_score": adv_stats["z_score"],
    "p_value": adv_stats["p_value"],
    "95_ci": adv_stats["confidence_interval_95"],
    "ewma": adv_stats["ewma_success_rate"],
})
assert adv_stats["z_score"] is not None
assert adv_stats["p_value"] is not None
assert len(adv_stats["confidence_interval_95"]) == 2
assert adv_stats["ewma_success_rate"] is not None

# Run AI diagnosis
print("Diagnosing Bank X...")
diag_res = request("POST", f"/incidents/{bank_x_id}/diagnose")
print("Diagnosis response keys:", list(diag_res.keys()))
print("Diagnosis response content:", diag_res)
diag = diag_res.get("diagnosis")
print(f"Bank X Diagnosed: Hypothesis={diag['hypothesis']}, Confidence={diag['confidence']}")
assert diag["confidence"] >= 0.70

# Check counterfactuals PRE-ACTION
cf_pre = request("GET", f"/incidents/{bank_x_id}/counterfactuals")
reroute_pre = next(c for c in cf_pre if c["action_type"] == "REROUTE")
print(f"Pre-Action REROUTE Counterfactual: Lift=+{reroute_pre['expected_improvement_pp']:.2f}pp, Recovered=Rs.{reroute_pre['expected_recovered_revenue']:,.2f}, Recommended={reroute_pre['is_recommended']}")
assert reroute_pre["is_recommended"] is True
assert reroute_pre["expected_recovered_revenue"] > 100000

# Execute recovery (REROUTE)
print("Executing recovery on Bank X...")
rec_res = request("POST", f"/incidents/{bank_x_id}/recover", {
    "recommended_action": "REROUTE",
    "selected_by": "system",
    "role": "OPERATOR",
})
print("Recovery result status:", rec_res["status"])
print(f"Recovered Revenue: Rs.{rec_res['outcome']['recovered_revenue']:,.2f}")
assert rec_res["status"] == "RESOLVED"
assert rec_res["outcome"]["recovered_revenue"] > 0

# Check terminal safety check
safety_post = request("GET", f"/incidents/{bank_x_id}/safety")
print("Post-recovery safety status:", safety_post["status"])
print("Post-recovery safety reason:", safety_post["reason"])
assert safety_post["status"] == "RECOVERY_LOCKED_RESOLVED"
assert "terminal-state protection" in safety_post["reason"]

# Check Counterfactual Action Matrix STABILITY (Issue 6)
cf_post = request("GET", f"/incidents/{bank_x_id}/counterfactuals")
reroute_post = next(c for c in cf_post if c["action_type"] == "REROUTE")
print(f"Post-Action REROUTE Counterfactual: Lift=+{reroute_post['expected_improvement_pp']:.2f}pp, Recovered=Rs.{reroute_post['expected_recovered_revenue']:,.2f}")
assert reroute_post["expected_recovered_revenue"] == reroute_pre["expected_recovered_revenue"], "Counterfactual changed after recovery!"
assert reroute_post["expected_improvement_pp"] == reroute_pre["expected_improvement_pp"], "Counterfactual changed after recovery!"

# Check detail for exposure distinction (Issue 9)
inc_detail_post = request("GET", f"/incidents/{bank_x_id}")
print(f"Initial At-Risk Exposure: Rs.{inc_detail_post['incident']['initial_at_risk_revenue']:,.2f}")
print(f"Recovered Revenue: Rs.{inc_detail_post['outcome']['recovered_revenue']:,.2f}")
print(f"Remaining Exposure: Rs.{inc_detail_post['incident']['remaining_exposure']:,.2f}")
assert inc_detail_post["incident"]["initial_at_risk_revenue"] > inc_detail_post["outcome"]["recovered_revenue"]

# C. SBI Flow (Low Confidence)
print("\n--- C. Scenario 2: SBI (UPI) Flow ---")
sbi = next(i for i in incidents if i["segment_issuer"] == "SBI")
sbi_id = sbi["id"]

print("Diagnosing SBI...")
diag_sbi_res = request("POST", f"/incidents/{sbi_id}/diagnose")
diag_sbi = diag_sbi_res["diagnosis"]
print(f"SBI Diagnosed: Hypothesis={diag_sbi['hypothesis']}, Confidence={diag_sbi['confidence']}")
assert diag_sbi["confidence"] < 0.70

# Check safety check
safety_sbi = request("GET", f"/incidents/{sbi_id}/safety")
print("SBI Safety status:", safety_sbi["status"])
print("SBI Safety reason:", safety_sbi["reason"])
assert safety_sbi["status"] == "RECOVERY_BLOCKED_LOW_CONFIDENCE"

# Check counterfactual labels (Issue 7)
cf_sbi = request("GET", f"/incidents/{sbi_id}/counterfactuals")
suppress_sbi = next(c for c in cf_sbi if c["action_type"] == "SUPPRESS_RETRIES")
print("SBI SUPPRESS_RETRIES counterfactual:", {
    "is_compatible": suppress_sbi["is_compatible"],
    "is_recommended": suppress_sbi["is_recommended"],
    "policy_status": suppress_sbi.get("policy_status"),
})
assert suppress_sbi["is_recommended"] is False, "Low-confidence SBI recommended recovery execution!"
assert suppress_sbi["is_compatible"] is True
assert suppress_sbi["policy_status"] == "NOT_EXECUTED_LOW_CONFIDENCE"

# D. ICICI Flow (Human Approval)
print("\n--- D. Scenario 3: ICICI (High-Value) Flow ---")
icici = next(i for i in incidents if i["segment_issuer"] == "ICICI")
icici_id = icici["id"]

print("Diagnosing ICICI...")
diag_icici_res = request("POST", f"/incidents/{icici_id}/diagnose")
diag_icici = diag_icici_res["diagnosis"]
print(f"ICICI Diagnosed: Hypothesis={diag_icici['hypothesis']}, Confidence={diag_icici['confidence']}")
assert diag_icici["confidence"] >= 0.70

# Check safety check (Issue 8)
safety_icici = request("GET", f"/incidents/{icici_id}/safety")
print("ICICI Safety status:", safety_icici["status"])
print("ICICI Safety reason:", safety_icici["reason"])
assert safety_icici["status"] == "HUMAN_APPROVAL_REQUIRED"
assert safety_icici["revenue_ceiling_check"]["requires_approval"] is True

# Test unauthorized role approval restriction
print("Testing unauthorized VIEWER approval...")
viewer_res = request("POST", f"/incidents/{icici_id}/recover", {
    "recommended_action": "REROUTE",
    "selected_by": "viewer_user",
    "human_approved": True,
    "role": "VIEWER",
}, role="VIEWER")
print("Viewer approval response:", viewer_res)
assert viewer_res["status"] == "blocked"
assert viewer_res["reason"] == "unauthorized_role"
print("Correctly blocked unauthorized VIEWER role!")

# Approve with authorized OPERATOR role
print("Executing human approval with authorized OPERATOR role...")
rec_icici = request("POST", f"/incidents/{icici_id}/recover", {
    "recommended_action": "REROUTE",
    "selected_by": "operator",
    "human_approved": True,
    "role": "OPERATOR",
})
print("ICICI recovery status:", rec_icici["status"])
print(f"ICICI recovered revenue: Rs.{rec_icici['outcome']['recovered_revenue']:,.2f}")
assert rec_icici["status"] == "RESOLVED"
assert rec_icici["outcome"]["recovered_revenue"] > 0

# E. Audit Trail Verification
print("\n--- E. Audit Trail & Cryptographic Verification ---")
audit_icici = request("GET", f"/incidents/{icici_id}/audit")
print(f"Audit log events recorded for ICICI: {len(audit_icici)}")
event_types = [log["event_type"] for log in audit_icici]
print("Event sequence:", " -> ".join(event_types))
assert "HUMAN_APPROVAL_GRANTED" in event_types
assert "ACTION_APPLIED" in event_types
assert "OUTCOME_MEASURED" in event_types

# Verify hash chain
audit_verify = request("GET", f"/incidents/{icici_id}/audit/verify")
print("Audit chain verification:", audit_verify)
assert audit_verify["valid"] is True
assert audit_verify["status"] == "VERIFIED_TAMPER_FREE"

print("\n>>> ALL AUTOMATED VERIFICATION CHECKS PASSED WITH 100% SUCCESS! <<<")
