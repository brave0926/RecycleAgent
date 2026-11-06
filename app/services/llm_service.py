"""Talks to the model: builds the request, parses the answer, maps errors to replies."""
import json
import logging

from openai import AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.schemas.chat import ChatMessage, ChatResponse
from app.services.knowledge_base import SYSTEM_PROMPT
from app.services.language import language_instruction

log = logging.getLogger("recycle")

MAX_ATTEMPTS = 2  # One retry when the model's answer is invalid; API errors are not retried.

# Fixed replies in the language chosen on the page.
NOTICES = {
    "ko": {
        "busy": "지금 질문이 너무 많아요. 1분 뒤에 다시 시도해 주세요.",
        "error": "죄송해요, 문제가 생겼어요. 다시 시도해 주세요.",
    },
    "en": {
        "busy": "Too many questions right now — please try again in a minute.",
        "error": "Sorry, something went wrong. Please try again.",
    },
}

# A placeholder key lets the app start without one; /api/chat then returns the error reply.
client = AsyncOpenAI(
    api_key=settings.openai_api_key or "missing",
    base_url=settings.openai_base_url,
    timeout=settings.openai_timeout,
    max_retries=0,  # Fail fast: the visitor sees the error reply and can simply try again.
)


def _log_usage(completion) -> None:
    usage = completion.usage
    if usage is None:
        log.info("tokens: usage not reported")
        return
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None)
    log.info(
        "tokens: prompt=%s completion=%s cached=%s",
        usage.prompt_tokens,
        usage.completion_tokens,
        cached if cached is not None else "n/a",
    )


def _parse_answer(raw_text: str) -> ChatResponse:
    """Parses the first {...} block, which also handles ```json fences and text around it.

    Raises ValueError if there is no valid answer.
    """
    start = raw_text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    data, _ = json.JSONDecoder().raw_decode(raw_text, start)
    return ChatResponse.model_validate(data)


async def ask(history: list[ChatMessage], lang: str) -> ChatResponse:
    """Sends the trimmed history to the model. Never raises: failures become replies.

    The language instruction goes last so the fixed system prompt stays cacheable and
    earlier answers in another language can't pull the reply back to that language.
    """
    notices = NOTICES[lang]
    # Only questions are cut: stored answers are JSON, and cutting them would break it.
    trimmed = [
        {
            "role": m.role,
            "content": m.content[: settings.max_msg_chars] if m.role == "user" else m.content,
        }
        for m in history[-settings.max_history :]
    ]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *trimmed,
        # Must stay a user message: on Gemini's OpenAI-compatible API a second
        # system message replaces the first, which drops the knowledge base.
        {"role": "user", "content": language_instruction(lang)},
    ]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            completion = await client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except RateLimitError as exc:
            log.error("OpenAI rate limit: %s", exc)
            return ChatResponse.plain(notices["busy"])
        except Exception:
            log.exception("Chat request failed")
            return ChatResponse.plain(notices["error"])

        _log_usage(completion)

        raw_text = completion.choices[0].message.content or ""
        try:
            return _parse_answer(raw_text)
        except ValueError as exc:  # Covers both bad JSON and Pydantic validation errors.
            log.warning("Invalid model output (attempt %s of %s): %s", attempt, MAX_ATTEMPTS, exc)

    return ChatResponse.plain(notices["error"])  # Never show raw model output to a visitor.
