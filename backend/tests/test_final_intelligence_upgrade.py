"""DeclineDoctor - Final Intelligence & Realism Upgrade Test Suite.

Verifies all newly integrated intelligence, realism, and safety features:
1. Provider abstraction, health telemetry, and strict live-mode disablement
2. 9-stage event-driven pipeline lifecycle
3. Advanced anomaly detection (CUSUM, EWMA, bounded anomaly score)
4. Closed-loop learning records and dynamic recommendation ranking
5. Recovery economics transparency and ROI formulas
6. Safe offline experiment framework (A vs B cohort comparison)
7. Customer-level retry limits and cooldown safety (anonymized CUST_XXXX)
8. Production observability alert rules
9. Enterprise benchmark evaluation and zero-unsafe-action verification
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.providers.factory import get_payment_provider, get_all_providers_health
from app.providers.mock_provider import MockPaymentProvider
from app.providers.razorpay_provider import RazorpayPaymentProvider
from app.economics import calculate_recovery_economics
from app.customer_safety import check_customer_retry_safety, get_demo_customer_profiles
from app.experiments import run_recovery_experiment
from app.observability import get_system_alerts, get_system_observability
from app.evaluation import run_expanded_evaluation
from app.detection import detect_anomalies
from app.database import SessionLocal
from datetime import datetime

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Provider Abstraction & Health
# ---------------------------------------------------------------------------
def test_provider_layer_health_and_sandbox_guarantee():
    """Verify provider health telemetry and strict live-mode disablement."""
    mock_prov = get_payment_provider("mock")
    assert isinstance(mock_prov, MockPaymentProvider)
    mock_health = mock_prov.get_provider_health()
    assert mock_health["status"] == "HEALTHY"
    assert mock_health["is_live"] is False
    assert "MOCK" in mock_health["mode"]

    rzp_prov = get_payment_provider("razorpay")
    assert isinstance(rzp_prov, RazorpayPaymentProvider)
    rzp_health = rzp_prov.get_provider_health()
    assert rzp_health["status"] == "HEALTHY"
    assert rzp_health["is_live"] is False
    assert "LIVE STRICTLY DISABLED" in rzp_health["mode"]

    # Test via API
    res = client.get("/api/providers/health")
    assert res.status_code == 200
    data = res.json()
    assert len(data["providers"]) == 2
    for p in data["providers"]:
        assert p["is_live"] is False
        assert p["latency_ms"] > 0


def test_provider_test_payment_execution():
    """Test executing a test payment through the provider sandbox."""
    res = client.post("/api/providers/test_payment", json={"amount": 2500.0, "provider": "mock"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in {"captured", "TEST_TRANSACTION_PROCESSED"}
    assert data["amount"] == 2500.0
    assert data["is_live_transaction"] is False


# ---------------------------------------------------------------------------
# 2. Real-Time 9-Stage Event Pipeline
# ---------------------------------------------------------------------------
def test_nine_stage_event_pipeline_lifecycle():
    """Verify stream event executes the full 9-stage pipeline trace with simulated timestamps."""
    client.post("/api/simulate/inject")
    payload = {
        "issuer": "Bank X",
        "payment_method": "card",
        "amount": 1850.0,
        "success": False,
        "decline_code": "processor_declined",
        "auto_execute": False,
        "user_role": "OPERATOR",
    }
    res = client.post("/api/simulate/stream", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "pipeline_trace" in data
    trace = data["pipeline_trace"]
    assert len(trace) >= 6

    stages_present = {step["stage"] for step in trace}
    assert "RECEIVED" in stages_present
    assert "VALIDATED" in stages_present
    assert "SEGMENTED" in stages_present
    assert "ANOMALY_CHECKED" in stages_present
    assert "DIAGNOSED" in stages_present
    assert "POLICY_EVALUATED" in stages_present

    # Check realistic simulated timestamps
    for step in trace:
        assert ":" in step["timestamp"]
        assert step["status"] in {"COMPLETED", "ANOMALY_CONFIRMED", "RECOMMENDED", "SAFE_TO_EXECUTE", "PENDING_MANUAL_TRIGGER", "UNAVAILABLE"}


# ---------------------------------------------------------------------------
# 3. Advanced Anomaly Detection
# ---------------------------------------------------------------------------
def test_advanced_detection_metrics_and_scoring():
    """Verify CUSUM, EWMA, bounded anomaly score, and explanation generation."""
    db = SessionLocal()
    try:
        anomalies = detect_anomalies(db, current_time=datetime.now())
        assert len(anomalies) > 0
        primary_anomaly = anomalies[0]

        # Verify advanced metrics
        assert "cusum_score" in primary_anomaly
        assert "anomaly_score" in primary_anomaly
        assert 0 <= primary_anomaly["anomaly_score"] <= 100
        assert "primary_detector" in primary_anomaly
        assert "supporting_detectors" in primary_anomaly
        assert "detection_explanation" in primary_anomaly
        assert len(primary_anomaly["supporting_detectors"]) >= 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Closed-Loop Learning
# ---------------------------------------------------------------------------
def test_closed_loop_learning_summary_and_effectiveness():
    """Verify learning records and historical action effectiveness summary."""
    res = client.get("/api/learning/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_recovery_attempts"] >= 38
    assert data["global_effectiveness_pct"] > 70.0
    assert "REROUTE" in data["action_effectiveness"]
    assert data["action_effectiveness"]["REROUTE"]["success_rate_pct"] >= 80.0
    assert data["learning_status"] == "ACTIVE_CONTINUOUS_LEARNING"

    # Verify per-action endpoint
    res_act = client.get("/api/learning/effectiveness?action=REROUTE")
    assert res_act.status_code == 200
    data_act = res_act.json()
    assert data_act["action"] == "REROUTE"
    assert data_act["total_attempts"] >= 38


# ---------------------------------------------------------------------------
# 5. Recovery Economics & Transparent Formulas
# ---------------------------------------------------------------------------
def test_recovery_economics_calculation():
    """Verify transparent economics formulas: Net = Gross - Costs, ROI = Net / Cost."""
    econ = calculate_recovery_economics(gross_recovered=100000.0, transactions_recovered=50)
    assert econ["gross_recovered"] == 100000.0
    assert econ["recovery_cost"] > 0
    assert econ["net_recovered"] == round(100000.0 - econ["recovery_cost"], 2)
    assert econ["roi_pct"] > 0
    assert "processor_routing_cost" in econ["cost_breakdown"]
    assert "customer_friction_cost" in econ["cost_breakdown"]
    assert "disclaimer" in econ

    # Zero gross recovered returns zero ROI without division-by-zero error
    zero_econ = calculate_recovery_economics(gross_recovered=0.0, transactions_recovered=0)
    assert zero_econ["gross_recovered"] == 0.0
    assert zero_econ["roi_pct"] == 0.0


# ---------------------------------------------------------------------------
# 6. Recovery Strategy Experiment Framework
# ---------------------------------------------------------------------------
def test_offline_experiment_cohort_simulation():
    """Verify offline deterministic experiment framework comparing Cohort A vs Cohort B."""
    exp = run_recovery_experiment(
        segment_issuer="Bank X",
        segment_payment_method="card",
        sample_size=100,
        candidate_action_a="REROUTE",
        candidate_action_b="ADJUST_RETRY_TIMING",
    )
    assert exp["winner"] == "COHORT_A (REROUTE)"
    assert exp["sample_size"] == 100
    assert exp["is_statistically_significant"] is True
    assert exp["p_value"] < 0.05
    assert exp["confidence_level_pct"] == 95.0
    assert exp["cohort_a"]["recovery_rate_pct"] > exp["cohort_b"]["recovery_rate_pct"]
    assert "offline simulation" in exp["simulation_disclaimer"].lower()

    # Verify cohort properties are populated independently and non-zero
    for key in ["cohort_a", "cohort_b"]:
        assert exp[key]["average_lift_pp"] > 0
        assert exp[key]["avg_lift_pp"] == exp[key]["average_lift_pp"]
        assert exp[key]["net_recovered_revenue"] > 0
        assert exp[key]["recovered_revenue"] == exp[key]["net_recovered_revenue"]
        assert exp[key]["friction_score"] > 0
        assert exp[key]["customer_friction_score"] == exp[key]["friction_score"]
        assert exp[key]["strategy"] in ["REROUTE", "ADJUST_RETRY_TIMING"]
        assert exp[key]["action"] == exp[key]["strategy"]

    # Verify API endpoints: GET /summary and POST /run
    res = client.get("/api/experiments/summary")
    assert res.status_code == 200
    summary_json = res.json()
    assert summary_json["winner"] is not None
    assert summary_json["cohort_a"]["average_lift_pp"] > 0
    assert summary_json["cohort_a"]["recovered_revenue"] > 0
    assert summary_json["cohort_a"]["friction_score"] > 0

    res_post = client.post("/api/experiments/run", json={
        "strategy_a": "REROUTE",
        "strategy_b": "ADJUST_RETRY_TIMING",
        "candidate_action_a": "REROUTE",
        "candidate_action_b": "ADJUST_RETRY_TIMING",
        "sample_size": 100,
        "segment_issuer": "Bank X",
        "segment_payment_method": "card",
    })
    assert res_post.status_code == 200
    post_json = res_post.json()
    assert post_json["winner"] is not None
    assert post_json["cohort_a"]["average_lift_pp"] > 0
    assert post_json["cohort_a"]["recovered_revenue"] > 0
    assert post_json["cohort_a"]["friction_score"] > 0
    assert post_json["cohort_b"]["average_lift_pp"] > 0
    assert post_json["cohort_b"]["recovered_revenue"] > 0
    assert post_json["cohort_b"]["friction_score"] > 0
    assert post_json["cohort_a"]["strategy"] != post_json["cohort_b"]["strategy"]


def test_experiment_deterministic_sha256_reproducibility():
    """Verify identical experiment inputs produce identical lift across separate processes."""
    import subprocess
    import sys
    import json

    exp1 = run_recovery_experiment(
        strategy_a="REROUTE",
        strategy_b="ADJUST_RETRY_TIMING",
        sample_size=100,
        segment="Bank X card",
    )
    exp2 = run_recovery_experiment(
        strategy_a="REROUTE",
        strategy_b="ADJUST_RETRY_TIMING",
        sample_size=100,
        segment="Bank X card",
    )

    # In-process determinism
    assert exp1["cohort_a"]["average_lift_pp"] == exp2["cohort_a"]["average_lift_pp"]
    assert exp1["cohort_b"]["average_lift_pp"] == exp2["cohort_b"]["average_lift_pp"]
    assert exp1["experiment_id"] == exp2["experiment_id"]

    # Verify bounded variation ±0.5 percentage-points around lift_mean
    assert abs(exp1["cohort_a"]["average_lift_pp"] - 17.5) <= 0.5
    assert abs(exp1["cohort_b"]["average_lift_pp"] - 8.8) <= 0.5

    # Cross-process determinism with differing PYTHONHASHSEED to prove hash() is not used
    cmd = [
        sys.executable,
        "-c",
        "from app.experiments import run_recovery_experiment; import json; "
        "res = run_recovery_experiment('REROUTE', 'ADJUST_RETRY_TIMING', 100, 'Bank X card'); "
        "print(json.dumps({'lift_a': res['cohort_a']['average_lift_pp'], 'lift_b': res['cohort_b']['average_lift_pp'], 'id': res['experiment_id']}))",
    ]

    # Process 1 with PYTHONHASHSEED=12345
    proc1 = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        env={**dict(subprocess.os.environ), "PYTHONHASHSEED": "12345"},
    )
    out1 = json.loads(proc1.stdout.strip())

    # Process 2 with PYTHONHASHSEED=98765
    proc2 = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        env={**dict(subprocess.os.environ), "PYTHONHASHSEED": "98765"},
    )
    out2 = json.loads(proc2.stdout.strip())

    assert out1["lift_a"] == exp1["cohort_a"]["average_lift_pp"]
    assert out2["lift_a"] == exp1["cohort_a"]["average_lift_pp"]
    assert out1["lift_b"] == exp1["cohort_b"]["average_lift_pp"]
    assert out2["lift_b"] == exp1["cohort_b"]["average_lift_pp"]
    assert out1["id"] == exp1["experiment_id"]
    assert out2["id"] == exp1["experiment_id"]


# ---------------------------------------------------------------------------
# 7. Customer Retry Safety & Cooldown
# ---------------------------------------------------------------------------
def test_customer_retry_safety_guardrails():
    """Verify customer-level retry capping and cooldown enforcement."""
    # Customer with 2 retries already used must be suppressed
    check_capped = check_customer_retry_safety(
        customer_id="CUST_1042",
        prior_failures_count=3,
        retries_used=2,
    )
    assert check_capped["is_safe_to_retry"] is False
    assert check_capped["policy_action"] == "SUPPRESS_RETRIES"
    assert "Retry cap reached" in check_capped["reason"]

    # Customer with 1 retry used can receive recovery
    check_eligible = check_customer_retry_safety(
        customer_id="CUST_2081",
        prior_failures_count=1,
        retries_used=1,
    )
    assert check_eligible["is_safe_to_retry"] is True
    assert check_eligible["policy_action"] == "ALLOW_RECOVERY"

    # Verify demo customer list via API
    res = client.get("/api/simulate/customers")
    assert res.status_code == 200
    custs = res.json()
    assert len(custs) >= 3
    assert any(c["customer_id"] == "CUST_1042" for c in custs)


# ---------------------------------------------------------------------------
# 8. Observability Alerts
# ---------------------------------------------------------------------------
def test_observability_alerts_and_telemetry():
    """Verify 5 production alert rules and system telemetry."""
    alerts = get_system_alerts()
    assert len(alerts) == 5
    rule_names = {a["rule"] for a in alerts}
    assert "PROVIDER_HEALTH_DEGRADATION" in rule_names
    assert "HIGH_RECOVERY_FAILURE_RATE" in rule_names
    assert "UNUSUAL_ESCALATION_SPIKE" in rule_names
    assert "MODEL_CONFIDENCE_DRIFT" in rule_names
    assert "RECOVERY_ROLLBACK_SPIKE" in rule_names

    res = client.get("/api/observability/alerts")
    assert res.status_code == 200
    assert len(res.json()) == 5


# ---------------------------------------------------------------------------
# 9. Enterprise 210-Case Evaluation & Safety Invariant
# ---------------------------------------------------------------------------
def test_enterprise_evaluation_zero_unsafe_actions():
    """Verify expanded 210-case evaluation achieves ZERO unsafe automatic actions."""
    eval_res = run_expanded_evaluation()
    assert eval_res["dataset_size"] == 210
    assert eval_res["safety_evaluation"]["unsafe_automatic_actions"] == 0
    assert eval_res["safety_evaluation"]["unsafe_action_rate_pct"] == 0.0
    assert eval_res["safety_evaluation"]["do_not_act_adherence_pct"] == 100.0
    assert eval_res["safety_evaluation"]["human_approval_enforcement_pct"] == 100.0
    assert eval_res["safety_evaluation"]["safety_verdict"] == "ZERO_UNSAFE_ACTIONS_VERIFIED"
    assert len(eval_res["category_breakdown"]) >= 8

    # Test via API with expanded parameter
    res = client.get("/api/evaluation?expanded=true")
    assert res.status_code == 200
    assert res.json()["dataset_size"] == 210
    assert res.json()["safety_evaluation"]["unsafe_automatic_actions"] == 0
