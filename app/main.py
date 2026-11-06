"""AI Recycling Guide: creates the app, connects the routes and serves the static page."""
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, health, pages, quick_answers
from app.core.config import STATIC_DIR, settings
from app.core.logging import setup_logging

setup_logging()
log = logging.getLogger("recycle")

if not settings.openai_api_key:
    log.warning("OPENAI_API_KEY is not set: /api/chat will return the error reply.")
log.info("model: %s", settings.openai_model)

app = FastAPI(title="AI Recycling Guide")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(pages.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(quick_answers.router)
