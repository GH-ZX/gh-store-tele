"""Shared utilities and authorization helpers for FastAPI routes."""
from fastapi import Request
import config
from services.telegram_auth import extract_and_verify_telegram_user


def is_admin_id(tg_id: int | None) -> bool:
    """Return True if telegram_id is configured in ADMIN_ID_LIST."""
    if not tg_id:
        return False
    try:
        return int(tg_id) in config.ADMIN_ID_LIST
    except (ValueError, TypeError):
        return False


def verify_admin(tg_id: int | None, request: Request | None = None) -> bool:
    """Verify that a given Telegram user ID has admin privileges based on config.ADMIN_ID_LIST.

    Requires authenticated request identity; use is_admin_id only for trusted identities.
    """
    if not tg_id:
        return False
    if request is not None:
        try:
            verified_tg_id = extract_and_verify_telegram_user(request, int(tg_id))
            return is_admin_id(verified_tg_id)
        except Exception:
            return False
    return False

def normalize_delivery_good(g) -> str:
    """Extract clean credentials if g is a dictionary or dict string representation."""
    if not g:
        return ""
    if isinstance(g, dict):
        return str(
            g.get("account_data")
            or g.get("value")
            or g.get("data")
            or g.get("credentials")
            or g.get("key")
            or g.get("code")
            or g.get("token")
            or (f"{g['email']}:{g['password']}" if "email" in g and "password" in g else None)
            or (f"{g['username']}:{g['password']}" if "username" in g and "password" in g else None)
            or str(g)
        )
    s = str(g).strip()
    if s.startswith("{") and s.endswith("}"):
        import json
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return normalize_delivery_good(parsed)
        except Exception:
            pass
        import re
        m = re.search(r"['\"](?:account_data|value|data|credentials|key|code|token)['\"]\s*:\s*['\"]([^'\"]+)['\"]", s)
        if m:
            return m.group(1)
    return s
