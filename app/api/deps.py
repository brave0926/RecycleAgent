"""Shared route dependencies."""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    # Behind a hosting proxy the real visitor is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
