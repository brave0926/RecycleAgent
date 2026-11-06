"""Request and response shapes for POST /api/chat."""
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]  # Clients cannot send their own system prompt.
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    lang: Literal["auto", "en", "ko"] = "auto"


class AnswerPart(BaseModel):
    label: str
    # Plain str on purpose: one unexpected category should not throw away a good
    # answer. The page can style unknown values.
    category: str
    item: str = ""  # The model sometimes leaves this out; the page then shows just the action.
    action: str


class ChatResponse(BaseModel):
    reply: str
    parts: list[AnswerPart]
    tip: str
    source: str

    @classmethod
    def plain(cls, text: str) -> "ChatResponse":
        """A reply with no parts: same JSON shape, so the page needs no special case."""
        return cls(reply=text, parts=[], tip="", source="")


class LocalizedText(BaseModel):
    en: str
    ko: str


class LocalizedAnswer(BaseModel):
    en: ChatResponse
    ko: ChatResponse


class QuickAnswer(BaseModel):
    id: str
    label: LocalizedText
    answer: LocalizedAnswer


class QuickAnswers(BaseModel):
    chips: list[QuickAnswer]
