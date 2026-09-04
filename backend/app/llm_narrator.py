import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

# Ensure .env is loaded from backend directory
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class ActionProposal(BaseModel):
    narrative: str = Field(description="A clear, professional incident narrative explaining what happened, grounded ONLY in the provided evidence numbers.")
    recommended_action: Literal["REROUTE", "ADJUST_RETRY_TIMING", "SUPPRESS_RETRIES"] = Field(description="The bounded recovery action to take.")
    reasoning: str = Field(description="Why this specific action was chosen based on the dominant decline code and hypothesis.")

def get_deterministic_action(hypothesis: str) -> str:
    # Domain rules mapping (Section 5 of Spec)
    if hypothesis == "ROUTING_CONNECTIVITY_ISSUE":
        return "REROUTE"
    elif hypothesis == "BIN_LEVEL_TEMPORARY_ISSUE":
        return "ADJUST_RETRY_TIMING"
    else:
        return "SUPPRESS_RETRIES"

def _validate_narrative_numbers(narrative: str, evidence: dict) -> None:
    """Reject numeric claims that cannot be grounded in the structured evidence.
    Legitimate timestamps, dates, durations, identifiers, and list numbering are ignored.
    """
    evidence_numbers = set()

    def collect(value):
        if isinstance(value, bool):
            return
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)
        elif isinstance(value, (int, float)):
            evidence_numbers.add(str(value))
            evidence_numbers.add(str(round(float(value), 2)))
            evidence_numbers.add(str(round(float(value), 1)))
            evidence_numbers.add(str(int(round(float(value)))))
            if isinstance(value, float) and value <= 1.0:
                evidence_numbers.add(str(int(round(value * 100))))
                evidence_numbers.add(str(round(value * 100, 1)))
        elif isinstance(value, str):
            for num_token in re.findall(r"\d+(?:\.\d+)?", value):
                evidence_numbers.add(num_token)
                try:
                    vf = float(num_token)
                    evidence_numbers.add(str(round(vf, 2)))
                    evidence_numbers.add(str(round(vf, 1)))
                    evidence_numbers.add(str(int(round(vf))))
                except ValueError:
                    pass

    collect(evidence)

    # 1. Strip dates, timestamps, durations, and list numbering before token validation
    cleaned = narrative
    # Full ISO dates and timestamps (including fractional seconds/microseconds and timezone offsets)
    cleaned = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[T\s]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b", " ", cleaned)
    # Clock times: 10:00, 14:30:00, 01:53:28.410481, 2:30 PM
    cleaned = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:AM|PM|am|pm)?\b", " ", cleaned)
    # Hyphenated durations like 12-hour, 24-hour, 4-hr
    cleaned = re.sub(r"\b\d+-(?:hour|minute|day|hr|min|second|sec)s?\b", " ", cleaned, flags=re.IGNORECASE)
    # Spaced durations like 12 hours, 24h, 30 mins
    cleaned = re.sub(r"\b\d+\s*(?:h|hr|hrs|hours?|m|min|mins?|minutes?|days?|s|seconds?)\b", " ", cleaned, flags=re.IGNORECASE)
    # List numbering / bullet points: 1. or 1) or Step 1
    cleaned = re.sub(r"(?:^|[\n\s])\d+[\.\)]\s+", " ", cleaned)
    cleaned = re.sub(r"\b(?:Step|Rule|Item|Point|Scenario|Option|Phase)\s+\d+\b", " ", cleaned, flags=re.IGNORECASE)
    # Identifiers: ref #1234, ID 1234, BIN 452114, ticket #456
    cleaned = re.sub(r"\b(?:id|ref|reference|txn|transaction|ticket|bin|card)\s*[:#]?\s*[A-Za-z0-9_-]+\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"#[A-Za-z0-9_-]+\b", " ", cleaned)
    # Alphanumeric tokens containing letters and digits (e.g. inc_844b714d85c2, cust_123, router1)
    cleaned = re.sub(r"\b[A-Za-z0-9_-]*[A-Za-z_]+[A-Za-z0-9_-]*\d+[A-Za-z0-9_-]*\b", " ", cleaned)
    cleaned = re.sub(r"\b\d+[A-Za-z0-9_-]*[A-Za-z_]+[A-Za-z0-9_-]*\b", " ", cleaned)
    # Commas within numbers (e.g. ₹50,000 -> ₹50000)
    cleaned = re.sub(r"(?<=\d),(?=\d)", "", cleaned)

    # Extract all remaining numeric tokens
    tokens = re.findall(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])", cleaned)
    for token in tokens:
        normalized = str(round(float(token), 2)) if "." in token else token
        normalized_int = str(int(round(float(token))))
        if token not in evidence_numbers and normalized not in evidence_numbers and normalized_int not in evidence_numbers:
            raise ValueError(f"Narrative contains unsupported numeric claim: {token}")

def _validate_llm_result(result: dict, evidence: dict, deterministic_action: str) -> dict:
    """Validate the complete structured LLM response at the trust boundary."""
    try:
        proposal = ActionProposal.model_validate(result)
    except AttributeError:
        # Pydantic v1 compatibility
        try:
            proposal = ActionProposal.parse_obj(result)
        except ValidationError as exc:
            raise ValueError(f"Malformed LLM output rejected: {exc}") from exc
    except ValidationError as exc:
        raise ValueError(f"Malformed LLM output rejected: {exc}") from exc

    validated = proposal.model_dump() if hasattr(proposal, "model_dump") else proposal.dict()

    if validated["recommended_action"] != deterministic_action:
        raise ValueError(
            f"LLM action rejected: '{validated['recommended_action']}' is incompatible with "
            f"diagnosis '{evidence.get('hypothesis')}'. Expected '{deterministic_action}'."
        )

    _validate_narrative_numbers(validated["narrative"], evidence)
    return validated

def generate_narrative_and_action(evidence_json_str: str) -> dict:
    evidence = json.loads(evidence_json_str)

    deterministic_action = get_deterministic_action(evidence.get("hypothesis", ""))

    fallback_response = {
        "narrative": f"Detected a success rate drop of {evidence.get('drop_pp')}% on {evidence['segment']['issuer']} {evidence['segment']['payment_method']} segment. The dominant decline pattern is '{evidence.get('dominant_decline_code')}' at {evidence.get('dominant_decline_code_share')*100}%.",
        "recommended_action": deterministic_action,
        "reasoning": "Deterministic fallback selected based on hypothesis domain rules.",
        "selected_by": "deterministic_fallback"
    }

    # No API key means no LLM call; the bounded deterministic fallback is safe.
    if not api_key:
        return fallback_response

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        You are DeclineDoctor, a payment recovery AI agent.
        Analyze this incident evidence and provide a structured JSON response.

        Evidence:
        {evidence_json_str}

        Rules:
        1. Ground your narrative strictly in the provided numbers. Do not invent any metrics.
        2. Based on the hypothesis '{evidence.get("hypothesis")}', you MUST select '{deterministic_action}' as the recommended_action.
        """

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ActionProposal,
                temperature=0.1
            )
        )

        # A response that cannot be parsed/validated is rejected at the LLM trust boundary.
        try:
            result = json.loads(response.text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Malformed LLM JSON output rejected") from exc

        validated = _validate_llm_result(result, evidence, deterministic_action)
        validated["selected_by"] = "llm"
        return validated

    except ValueError:
        # Safety violation / malformed model output must not be silently accepted.
        raise
    except Exception as e:
        # Availability failures may use the deterministic safe fallback.
        print(f"LLM Error: {e}")
        return fallback_response
