"""Chooses the answer language (Korean or English) and writes the instruction that enforces it."""
import re

from app.schemas.chat import ChatMessage

APP_NAME = "내 손안의 분리배출"

_HANGUL = re.compile("[가-힣]")


def detect_language(text: str) -> str:
    return "ko" if _HANGUL.search(text) else "en"


def resolve_language(choice: str, history: list[ChatMessage]) -> str:
    """A language picked with the header button wins; otherwise detect from the latest question."""
    if choice != "auto":
        return choice
    for message in reversed(history):
        if message.role == "user":
            return detect_language(message.content)
    return "en"


def language_instruction(lang: str) -> str:
    if lang == "ko":
        return (
            "Respond ONLY in Korean. Each label is just the Korean term, with no English "
            "and no repeated term, e.g. '비닐류'."
        )
    return (
        "Respond ONLY in English. Translate everything from the Korean knowledge base into English. "
        "Write ALL JSON fields (reply, label, item, action, tip) in English; keep the Korean term "
        "in parentheses only for bin/category names, e.g. 'Plastic film (비닐류)'. "
        "Every label MUST be exactly '<name in English> (<Korean term>)', ending with the Korean "
        "term in parentheses, with no term repeated. "
        f"Always write the app name {APP_NAME} in Korean letters, never transliterated; "
        "you may add a translation in parentheses after it. "
        "The 'source' field stays as is."
    )
