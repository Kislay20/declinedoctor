from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Incident, Diagnosis, Transaction
from app.evaluation import run_ground_truth_evaluation
from app.providers.base import PaymentProvider
from app.providers.mock_provider import MockPaymentProvider
from app.providers.razorpay_provider import RazorpayPaymentProvider
from app.providers.factory import get_payment_provider
from app.explainability import get_incident_explanation


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_model_evaluation_ground_truth():
    eval_result = run_ground_truth_evaluation()
    assert eval_result["dataset_size"] == 60
    metrics = eval_result["metrics"]

    assert metrics["precision"] > 80.0
    assert metrics["recall"] > 80.0
    assert metrics["f1_score"] > 80.0
    assert metrics["accuracy"] > 80.0
    assert metrics["false_positive_rate"] < 20.0
    assert metrics["false_negative_rate"] < 20.0


def test_payment_provider_abstraction():
    mock_p = MockPaymentProvider()
    assert isinstance(mock_p, PaymentProvider)
    assert "mock" in mock_p.provider_name.lower()

    res = mock_p.reroute_traffic("Bank X card", "partner_gateway_b")
    assert res["status"].lower() in {"success", "rerouted"}
    assert "target_gateway" in res or "provider" in res

    health = mock_p.check_gateway_health("partner_gateway_b")
    assert "healthy" in health or "status" in health

    # Razorpay provider initialized without live secrets works in simulation mode
    rzp_p = RazorpayPaymentProvider()
    assert isinstance(rzp_p, PaymentProvider)
    assert "razorpay" in rzp_p.provider_name.lower()

    # Factory returns mock provider by default for buildathon demo
    factory_provider = get_payment_provider("mock")
    assert isinstance(factory_provider, MockPaymentProvider)


def test_explainability_answers():
    db = make_db()
    now = datetime.now()
    incident = Incident(
        id="inc_exp_test",
        detected_at=now,
        segment_issuer="SBI",
        segment_payment_method="upi",
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        baseline_success_rate=95.0,
        incident_success_rate=45.0,
        drop_pp=50.0,
        concentration_ratio=0.35,
        sample_size=60,
        state="ESCALATED_LOW_CONFIDENCE",
    )
    db.add(incident)
    db.add(Diagnosis(
        id="diag_exp_test",
        incident_id=incident.id,
        hypothesis="ISSUER_SIDE_DECLINE",
        confidence=0.48,
        dominant_decline_code="insufficient_funds",
        dominant_decline_code_share=0.45,
        evidence_json="{}",
    ))
    db.add(Transaction(
        id="tx_sbi_1",
        merchant_id="m",
        amount=25_000.0,
        timestamp=now,
        payment_method="upi",
        issuer="SBI",
        success=False,
        retry_count=0,
    ))
    db.commit()

    exp = get_incident_explanation(db, "inc_exp_test")
    assert exp["incident_id"] == "inc_exp_test"
    qs = exp["questions"]
    assert "why_did_declinedoctor_act" in qs
    assert "why_did_declinedoctor_not_act" in qs
    assert "why_did_declinedoctor_stop" in qs
    assert "why_is_human_approval_required" in qs
    # Verify low confidence is explicitly cited
    assert "0.70" in qs["why_did_declinedoctor_not_act"] or "confidence" in qs["why_did_declinedoctor_not_act"].lower()
