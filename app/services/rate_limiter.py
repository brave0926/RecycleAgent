"""In-memory per-IP rate limit. Resets on restart; works for one server process only."""
import logging
import time
from collections import defaultdict

from app.core.config import settings
from app.schemas.chat import ChatResponse

log = logging.getLogger("recycle")

LIMIT_REPLY = {
    "ko": "질문을 많이 해 주셔서 감사해요! 잠시 후 다시 시도해 주세요.",
    "en": "You've asked a lot of questions — thank you! Please try again a little later.",
}


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, ip: str) -> bool:
        """Returns True if this request is allowed, and counts it."""
        now = time.monotonic()
        recent = [t for t in self._hits[ip] if now - t < self.window_seconds]
        allowed = len(recent) < self.limit
        if allowed:
            recent.append(now)
        else:
            log.warning("rate limit hit: %s", ip)
        self._hits[ip] = recent
        return allowed

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter(settings.rate_limit, settings.rate_window)


def limit_reply(lang: str) -> ChatResponse:
    return ChatResponse.plain(LIMIT_REPLY[lang])
