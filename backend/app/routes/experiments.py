"""DeclineDoctor Recovery Strategy Experiment API.

Exposes endpoints to run bounded A/B recovery strategy evaluations on synthetic cohorts.
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..experiments import run_recovery_experiment

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])


class ExperimentRequest(BaseModel):
    strategy_a: Optional[str] = "REROUTE"
    strategy_b: Optional[str] = "ADJUST_RETRY_TIMING"
    candidate_action_a: Optional[str] = None
    candidate_action_b: Optional[str] = None
    sample_size: int = Field(default=100)
    segment: Optional[str] = "Bank X card"
    segment_issuer: Optional[str] = None
    segment_payment_method: Optional[str] = None


@router.get("/summary")
def get_default_experiment():
    """Retrieve benchmark A/B strategy experiment comparing REROUTE vs ADJUST_RETRY_TIMING."""
    return run_recovery_experiment()


@router.post("/run")
def trigger_experiment(payload: ExperimentRequest):
    """Run an ad-hoc recovery strategy experiment on a synthetic cohort."""
    strat_a = payload.candidate_action_a or payload.strategy_a or "REROUTE"
    strat_b = payload.candidate_action_b or payload.strategy_b or "ADJUST_RETRY_TIMING"
    seg = payload.segment or "Bank X card"
    if payload.segment_issuer and payload.segment_payment_method:
        seg = f"{payload.segment_issuer} {payload.segment_payment_method}"

    return run_recovery_experiment(
        strategy_a=strat_a,
        strategy_b=strat_b,
        sample_size=payload.sample_size,
        segment=seg,
        candidate_action_a=strat_a,
        candidate_action_b=strat_b,
        segment_issuer=payload.segment_issuer,
        segment_payment_method=payload.segment_payment_method,
    )
