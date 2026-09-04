"""DeclineDoctor Model Evaluation API.

Exposes endpoints to trigger and retrieve ground-truth benchmark metrics.
"""

from fastapi import APIRouter
from ..evaluation import run_ground_truth_evaluation

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("")
def get_model_evaluation():
    """Run model evaluation over 60 ground-truth payment scenarios and return calculated metrics."""
    return run_ground_truth_evaluation()
