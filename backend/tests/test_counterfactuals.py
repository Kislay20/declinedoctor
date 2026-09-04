from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction
from app.recovery_agent import compute_counterfactuals


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_counterfactual_action_comparison():
    db = make_db()
    now = datetime.now()
    incident = Incident(
        id="inc_cf_test",
        detected_at=now,
        segment_issuer="Bank X",
        segment_payment_method="card",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        baseline_success_rate=95.0,
        incident_success_rate=50.0,
        drop_pp=45.0,
        concentration_ratio=0.80,
        sample_size=100,
        state="DIAGNOSED",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_cf_test",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.85,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.80,
        evidence_json="{}",
    ))

    # Add 10 failed transactions at ₹10,000 each = ₹100,000 failed
    for i in range(10):
        db.add(Transaction(
            id=f"tx_fail_{i}",
            merchant_id="m",
            amount=10_000.0,
            timestamp=now,
            payment_method="card",
            issuer="Bank X",
            success=False,
            retry_count=0,
        ))
    # Add 10 successful transactions at ₹10,000 each
    for i in range(10):
        db.add(Transaction(
            id=f"tx_succ_{i}",
            merchant_id="m",
            amount=10_000.0,
            timestamp=now,
            payment_method="card",
            issuer="Bank X",
            success=True,
            retry_count=0,
        ))
    db.commit()

    cfs = compute_counterfactuals(db, "inc_cf_test")
    assert len(cfs) == 3

    cf_dict = {c["action_type"]: c for c in cfs}

    # REROUTE: effect size 0.42 -> 10 * 0.42 = 4 transactions flipped -> ₹40,000
    reroute = cf_dict["REROUTE"]
    assert reroute["transactions_affected"] == 4
    assert reroute["expected_recovered_revenue"] == 40_000.0
    assert reroute["is_compatible"] is True
    assert reroute["is_recommended"] is True

    # ADJUST_RETRY_TIMING: effect size 0.21 -> 10 * 0.21 = 2 transactions flipped -> ₹20,000
    timing = cf_dict["ADJUST_RETRY_TIMING"]
    assert timing["transactions_affected"] == 2
    assert timing["expected_recovered_revenue"] == 20_000.0
    assert timing["is_compatible"] is False

    # SUPPRESS_RETRIES: effect size 0.0 -> 0 transactions flipped -> ₹0
    suppress = cf_dict["SUPPRESS_RETRIES"]
    assert suppress["transactions_affected"] == 0
    assert suppress["expected_recovered_revenue"] == 0.0


def test_counterfactual_baseline_consistency_and_snapshot_freeze():
    """Ensure NO_ACTION baseline is mathematically and semantically consistent with
    the incident's frozen baseline/incident snapshot, lifts are exact, and the snapshot
    remains immutable after subsequent transactions or recovery execution.
    """
    from app.recovery_agent import execute_recovery

    db = make_db()
    now = datetime.now()
    incident = Incident(
        id="inc_cf_consistency",
        detected_at=now,
        segment_issuer="Bank X",
        segment_payment_method="card",
        window_start=now - timedelta(hours=2),
        window_end=now,
        baseline_success_rate=96.94,
        incident_success_rate=57.99,
        drop_pp=38.95,
        concentration_ratio=0.85,
        sample_size=219,
        state="DIAGNOSED",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_cf_consistency",
        incident_id=incident.id,
        hypothesis="ROUTING_CONNECTIVITY_ISSUE",
        confidence=0.88,
        dominant_decline_code="processor_declined",
        dominant_decline_code_share=0.85,
        evidence_json="{}",
    ))

    # Populate 127 successes and 92 failures (127/219 ~ 57.99%)
    for i in range(127):
        db.add(Transaction(
            id=f"tx_succ_c_{i}",
            merchant_id="m",
            amount=1500.0,
            timestamp=now - timedelta(minutes=30),
            payment_method="card",
            issuer="Bank X",
            success=True,
            retry_count=0,
        ))
    for i in range(92):
        db.add(Transaction(
            id=f"tx_fail_c_{i}",
            merchant_id="m",
            amount=2500.0,
            timestamp=now - timedelta(minutes=30),
            payment_method="card",
            issuer="Bank X",
            success=False,
            retry_count=0,
        ))
    db.commit()

    # 1. Baseline & Lift Consistency Verification
    cfs = compute_counterfactuals(db, "inc_cf_consistency", include_extended=True, include_baseline=True)
    assert len(cfs) == 7
    no_action = cfs[0]
    assert no_action["action_type"] == "NO_ACTION"
    # MUST match incident's frozen degraded success rate snapshot
    assert no_action["projected_success_rate"] == 57.99
    assert no_action["current_success_rate"] == 57.99
    assert no_action["expected_improvement_pp"] == 0.0

    # Every action's projected success rate must mathematically equal baseline + lift
    for cf in cfs:
        expected_proj = round(no_action["projected_success_rate"] + cf["expected_improvement_pp"], 2)
        assert cf["projected_success_rate"] == expected_proj
        assert round(cf["projected_success_rate"] - no_action["projected_success_rate"], 2) == round(cf["expected_improvement_pp"], 2)

    reroute_pre = next(c for c in cfs if c["action_type"] == "REROUTE")
    assert reroute_pre["expected_improvement_pp"] > 0.0
    assert reroute_pre["projected_success_rate"] > 57.99

    fields_to_check = [
        "action_type",
        "effect_size",
        "is_compatible",
        "is_recommended",
        "policy_status",
        "transactions_affected",
        "tx_to_flip",
        "total_txns",
        "sample_size",
        "total_failures",
        "total_eligible_failures",
        "baseline_incident_success_rate",
        "current_success_rate",
        "projected_success_rate",
        "expected_improvement_pp",
        "expected_recovered_revenue",
        "gross_recovered_revenue",
        "expected_cost",
        "retry_cost",
        "expected_net_recovery",
        "net_recovered_revenue",
        "expected_roi",
        "friction_score",
        "customer_friction_score",
        "rationale",
    ]

    # 2. Add subsequent transactions (simulating stream / webhook ingestion)
    for i in range(10):
        db.add(Transaction(
            id=f"tx_extra_fail_{i}",
            merchant_id="m",
            amount=3000.0,
            timestamp=now - timedelta(minutes=5),
            payment_method="card",
            issuer="Bank X",
            success=False,
            retry_count=0,
        ))
    for i in range(5):
        db.add(Transaction(
            id=f"tx_extra_succ_{i}",
            merchant_id="m",
            amount=1500.0,
            timestamp=now - timedelta(minutes=5),
            payment_method="card",
            issuer="Bank X",
            success=True,
            retry_count=0,
        ))
    db.commit()

    # Verify counterfactual baseline and ALL candidate projection fields remain strictly identical
    cfs_after_extra = compute_counterfactuals(db, "inc_cf_consistency", include_extended=True, include_baseline=True)
    assert len(cfs_after_extra) == len(cfs)
    for orig, after in zip(cfs, cfs_after_extra):
        for f in fields_to_check:
            assert orig[f] == after[f], f"Field '{f}' mismatch for {orig['action_type']} after transaction addition!"

    # 3. Preserve Historical Snapshot Semantics After Recovery Execution
    exec_res = execute_recovery(
        db,
        "inc_cf_consistency",
        action_data={"recommended_action": "REROUTE"},
        user_role="OPERATOR",
    )
    assert exec_res["status"] == "RESOLVED"

    # Fetch counterfactuals after recovery execution and verify complete snapshot immutability
    cfs_post_recovery = compute_counterfactuals(db, "inc_cf_consistency", include_extended=True, include_baseline=True)
    assert len(cfs_post_recovery) == len(cfs)
    for orig, post in zip(cfs, cfs_post_recovery):
        for f in fields_to_check:
            assert orig[f] == post[f], f"Field '{f}' mismatch for {orig['action_type']} after recovery execution!"

