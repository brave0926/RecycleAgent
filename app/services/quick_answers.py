"""Prepared answers for the quick chips. A broken file stops the app at startup."""
from app.core.config import QUICK_ANSWERS_PATH
from app.schemas.chat import QuickAnswers

QUICK_ANSWERS = QuickAnswers.model_validate_json(QUICK_ANSWERS_PATH.read_text(encoding="utf-8"))
