"""DeclineDoctor Recovery Learning API.

Exposes endpoints for closed-loop learning metrics, historical action effectiveness,
and dynamic confidence adjustments.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..learning import get_learning_summary, get_action_effectiveness

router = APIRouter(prefix="/api/learning", tags=["Learning"])


@router.get("/summary")
def get_recovery_learning_summary(db: Session = Depends(get_db)):
    """Retrieve global closed-loop recovery learning metrics and action effectiveness."""
    return get_learning_summary(db)


@router.get("/effectiveness")
def get_candidate_effectiveness(
    action: str,
    segment: str = None,
    hypothesis: str = None,
    db: Session = Depends(get_db),
):
    """Retrieve historical effectiveness and confidence modifier for a proposed recovery strategy."""
    return get_action_effectiveness(db, segment=segment, hypothesis=hypothesis, action=action)
