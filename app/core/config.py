"""All settings. This is the only module that reads environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
GUIDELINES_PATH = BASE_DIR / "data" / "guidelines.md"
QUICK_ANSWERS_PATH = BASE_DIR / "data" / "quick_answers.json"

load_dotenv(BASE_DIR / ".env")

# The OpenAI SDK reads OPENAI_BASE_URL itself and treats an empty value as a real
# (broken) URL, so an empty one must be removed, not just converted to None.
if not os.getenv("OPENAI_BASE_URL"):
    os.environ.pop("OPENAI_BASE_URL", None)


def _number(name: str, default: int) -> int:
    """Reads a whole number; a missing or empty variable gives the default."""
    return int(os.getenv(name) or default)


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str | None
    openai_timeout: int  # Seconds, per attempt.
    rate_limit: int  # Requests per IP per window.
    rate_window: int  # Window length in seconds.
    max_history: int  # Messages kept from each request.
    max_msg_chars: int  # Characters kept from each message.


settings = Settings(
    openai_api_key=os.getenv("OPENAI_API_KEY") or None,
    openai_model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
    openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
    openai_timeout=_number("OPENAI_TIMEOUT", 30),
    rate_limit=_number("RATE_LIMIT", 200),
    rate_window=_number("RATE_WINDOW", 3600),
    max_history=_number("MAX_HISTORY", 8),
    max_msg_chars=_number("MAX_MSG_CHARS", 500),
)
