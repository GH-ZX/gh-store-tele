"""Reject revoked API session tokens before route handling.

Session tokens embed an issued-at (``iat``) timestamp. When an admin revokes
a user, ``users.sessions_revoked_at`` is set; every token minted at-or-before
that instant is refused here with HTTP 401. This gate covers all ``/api``
routes uniformly, including the token-refresh endpoint that would otherwise
re-issue a revoked session.
"""
import logging
from datetime import datetime

from sqlalchemy import select

from models.user import User
from services.telegram_auth import (
    decode_session_token,
    extract_session_token_from_request,
    session_is_revoked,
)

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except ImportError:
    class BaseHTTPMiddleware:  # type: ignore
        def __init__(self, app):
            self.app = app
    class Request:  # type: ignore
        pass
    class JSONResponse:  # type: ignore
        def __init__(self, content, status_code=200, headers=None):
            self.content = content
            self.status_code = status_code
            self.headers = headers or {}


class SessionRevocationMiddleware(BaseHTTPMiddleware):
    """Reject session tokens issued at-or-before the user's revocation point."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not path.startswith("/api/"):
            return await call_next(request)

        token = extract_session_token_from_request(request)
        if not token:
            return await call_next(request)

        decoded = decode_session_token(token)
        if not decoded:
            return await call_next(request)

        tg_id, _exp, iat = decoded
        revoked_at: datetime | None = None
        try:
            from db import get_db_session
            async with get_db_session() as session:
                result = await session.execute(
                    select(User.sessions_revoked_at).where(User.telegram_id == tg_id)
                )
                revoked_at = result.scalar()
        except Exception as e:
            logging.warning("Session revocation check failed (failing open): %s", e)

        if session_is_revoked(iat, revoked_at):
            return JSONResponse({"error": "session_revoked"}, status_code=401)
        return await call_next(request)