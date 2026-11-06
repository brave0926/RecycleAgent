"""GET /api/quick-answers: chip labels and prepared answers."""
from fastapi import APIRouter

from app.schemas.chat import QuickAnswers
from app.services.quick_answers import QUICK_ANSWERS

router = APIRouter()


@router.get("/api/quick-answers", response_model=QuickAnswers)
async def quick_answers() -> QuickAnswers:
    return QUICK_ANSWERS
