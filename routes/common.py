"""Shared utilities and authorization helpers for FastAPI routes."""
from fastapi import Request
import config
from services.telegram_auth import extract_and_verify_telegram_user


def verify_admin(tg_id: int | None, request: Request | None = None) -> bool:
    """Verify that a given Telegram user ID has admin privileges.

    Optionally verifies cryptographic Telegram WebApp initData if request is provided.
    """
    if not tg_id:
        return False
    if request is not None:
        try:
            tg_id = extract_and_verify_telegram_user(request, int(tg_id))
        except Exception:
            return False
    return int(tg_id) in config.ADMIN_ID_LIST
