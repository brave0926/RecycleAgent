"""POST /api/chat: validate → language → rate limit → service → response."""
from fastapi import APIRouter, Depends

from app.api.deps import get_client_ip
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import llm_service
from app.services.language import resolve_language
from app.services.rate_limiter import limit_reply, limiter

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, ip: str = Depends(get_client_ip)) -> ChatResponse:
    lang = resolve_language(body.lang, body.messages)
    if not limiter.check(ip):
        return limit_reply(lang)
    return await llm_service.ask(body.messages, lang)
