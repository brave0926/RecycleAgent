"""GET / serves the chat page."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import STATIC_DIR

router = APIRouter()


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
