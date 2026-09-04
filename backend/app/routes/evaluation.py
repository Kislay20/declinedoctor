"""DeclineDoctor Model Evaluation API.

Exposes endpoints to trigger and retrieve ground-truth benchmark metrics.
"""

from typing import Optional
from fastapi import APIRouter, Query
from ..evaluation import run_ground_truth_evaluation, run_expanded_evaluation

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("")
def get_model_evaluation(expanded: bool = Query(False, description="Whether to run the 210-case expanded enterprise benchmark")):
    """Run model evaluation over ground-truth payment scenarios (60 default or 210 expanded) and return calculated metrics."""
    if expanded:
        return run_expanded_evaluation()
    return run_ground_truth_evaluation()


@router.get("/expanded")
def get_expanded_model_evaluation():
    """Run enterprise expanded model evaluation over 210 varied ground-truth payment scenarios including safety cases."""
    return run_expanded_evaluation()
