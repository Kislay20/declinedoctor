import json
import pytest
import app.llm_narrator as narrator


def evidence(hypothesis="ROUTING_CONNECTIVITY_ISSUE"):
    return {
        "incident_id": "inc_test",
        "segment": {"issuer": "Bank X", "payment_method": "card"},
        "baseline_success_rate": 96.9,
        "incident_success_rate": 55.5,
        "drop_pp": 41.4,
        "concentration_ratio": 0.63,
        "dominant_decline_code": "processor_declined",
        "dominant_decline_code_share": 0.70,
        "sample_size": 218,
        "hypothesis": hypothesis,
        "confidence": 0.72,
    }

def test_valid_structured_llm_output_is_accepted():
    e = evidence()
    result = narrator._validate_llm_result({
        "narrative": "Success rate dropped 41.4% from 96.9% to 55.5%.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing connectivity issue supports rerouting."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_malformed_llm_output_is_rejected():
    e = evidence()
    with pytest.raises(ValueError, match="Malformed LLM output rejected"):
        narrator._validate_llm_result({"recommended_action": "REROUTE"}, e, "REROUTE")

def test_incompatible_llm_action_is_rejected():
    e = evidence()
    with pytest.raises(ValueError, match="incompatible"):
        narrator._validate_llm_result({
            "narrative": "Success rate dropped 41.4%.",
            "recommended_action": "ADJUST_RETRY_TIMING",
            "reasoning": "Wrong action."
        }, e, "REROUTE")

def test_unsupported_numeric_claim_is_rejected():
    e = evidence()
    with pytest.raises(ValueError, match="unsupported numeric claim"):
        narrator._validate_llm_result({
            "narrative": "Success rate dropped 99.9%.",
            "recommended_action": "REROUTE",
            "reasoning": "Routing connectivity issue supports rerouting."
        }, e, "REROUTE")

def test_timestamp_and_time_in_narrative_is_accepted():
    e = evidence()
    result = narrator._validate_llm_result({
        "narrative": "Between 10:00 AM and 14:00, success rate dropped 41.4% over a 12-hour window.",
        "recommended_action": "REROUTE",
        "reasoning": "Connectivity degradation during the window."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_date_in_narrative_is_accepted():
    e = evidence()
    result = narrator._validate_llm_result({
        "narrative": "On 2026-09-04, Bank X card success dropped 41.4% from baseline 96.9%.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing degradation."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_list_numbering_in_narrative_is_accepted():
    e = evidence()
    result = narrator._validate_llm_result({
        "narrative": "1. Success rate dropped 41.4%. 2. Baseline was 96.9%. Step 1 recommended.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing connectivity issue."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_percentage_and_sample_size_are_accepted():
    e = evidence()
    result = narrator._validate_llm_result({
        "narrative": "Observed across 218 transactions, with dominant failure code processor_declined at 70%.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing connectivity issue."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_unsupported_currency_claim_is_rejected():
    e = evidence()
    with pytest.raises(ValueError, match="unsupported numeric claim"):
        narrator._validate_llm_result({
            "narrative": "Recovered ₹999,999 from the payment gateway.",
            "recommended_action": "REROUTE",
            "reasoning": "Fake recovery claim."
        }, e, "REROUTE")

def test_fractional_timestamp_with_microseconds_is_accepted():
    e = evidence()
    e["window"] = {
        "start": "2026-09-04T01:53:28.410481",
        "end": "2026-09-04T13:53:28.410481"
    }
    result = narrator._validate_llm_result({
        "narrative": "Between 2026-09-04T01:53:28.410481 and 2026-09-04T13:53:28.410481, success rate dropped 41.4% from baseline 96.9% to 55.5%.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing degradation."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"

def test_transaction_and_reference_identifier_is_accepted():
    e = evidence()
    e["incident_id"] = "inc_844b714d85c2"
    e["segment"]["bin"] = "452114"
    result = narrator._validate_llm_result({
        "narrative": "Incident inc_844b714d85c2 with BIN 452114, ref #98765, and txn_1024 dropped 41.4%.",
        "recommended_action": "REROUTE",
        "reasoning": "Routing degradation."
    }, e, "REROUTE")
    assert result["recommended_action"] == "REROUTE"


