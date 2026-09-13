"""Telegram WebApp initData HMAC-SHA256 Cryptographic Validator.

Validates that request payloads and query parameters genuinely originate from
the Telegram client for the specified bot token, preventing client impersonation.
"""
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any

try:
    from fastapi import HTTPException, Request, status
except ImportError:
    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code=400, detail=""):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    class Request:  # type: ignore
        pass
    class status:  # type: ignore
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
import config

_CANDIDATE_TOKENS: list[str] = []
INIT_DATA_MAX_AGE_SECONDS = 3600
AUTH_CLOCK_SKEW_SECONDS = 30


def _candidate_tokens() -> list[str]:
    """Bot tokens accepted for initData HMAC (primary first, then cached mirrors)."""
    seen: list[str] = []
    for tok in ([getattr(config, "TOKEN", "")] + list(_CANDIDATE_TOKENS)):
        if tok and tok not in seen:
            seen.append(tok)
    return seen


async def refresh_known_bot_tokens() -> None:
    """Refresh cached mirror-bot tokens so WebApps opened from any linked bot validate."""
    global _CANDIDATE_TOKENS
    try:
        from services.multibot import MultibotService
        all_toks = await MultibotService.get_all_tokens_with_main()
        _CANDIDATE_TOKENS = [t for t in (all_toks or []) if t and t != getattr(config, "TOKEN", "")]
    except Exception as e:
        logging.debug("Bot token refresh skipped: %s", e)


def validate_telegram_init_data_multi(init_data: str, max_age_seconds: int = INIT_DATA_MAX_AGE_SECONDS) -> dict[str, Any]:
    """Validate initData against each known bot token; raise ValueError if none match."""
    last_err: Exception | None = None
    for tok in _candidate_tokens():
        try:
            return validate_telegram_init_data(init_data, tok, max_age_seconds)
        except ValueError as e:
            last_err = e
            continue
    raise last_err if last_err is not None else ValueError("missing_bot_token")


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = INIT_DATA_MAX_AGE_SECONDS) -> dict[str, Any]:
    """Cryptographically validate Telegram WebApp initData string using HMAC-SHA256.

    1. Parse query string into key-value pairs.
    2. Extract and remove 'hash' (the HMAC covers all other fields).
    3. Generate secret_key = HMAC_SHA256("WebAppData", bot_token).
    4. Build data_check_string = sorted key=value pairs joined with '\n'.
    5. Compare HMAC_SHA256(data_check_string, secret_key).hexdigest() == hash.
    6. Verify auth_date freshness within max_age_seconds.
    """
    if not init_data or not isinstance(init_data, str):
        raise ValueError("missing_init_data")
    logging.debug("Telegram initData received: len=%s", len(init_data))
    if not bot_token:
        raise ValueError("missing_bot_token")
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    parsed = dict(pairs)
    if len(pairs) != len(parsed):
        raise ValueError("duplicate_init_data_field")
    received_hash = parsed.pop("hash", None)

    if not received_hash:
        raise ValueError("missing_hash")
    if len(received_hash) != 64 or any(char not in "0123456789abcdef" for char in received_hash):
        raise ValueError("invalid_signature")

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw:
        raise ValueError("missing_auth_date")

    try:
        auth_date = int(auth_date_raw)
    except (ValueError, TypeError):
        raise ValueError("invalid_auth_date")

    now = time.time()
    if auth_date > now + AUTH_CLOCK_SKEW_SECONDS:
        raise ValueError("future_init_data")
    if max_age_seconds <= 0:
        raise ValueError("invalid_max_age_seconds")
    if (now - auth_date) > max_age_seconds:
        raise ValueError("expired_init_data")

    check_items = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(check_items)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logging.warning("Telegram initData HMAC mismatch")
        raise ValueError("invalid_signature")

    result = dict(parsed)
    if "user" in result and isinstance(result["user"], str):
        try:
            result["user"] = json.loads(result["user"])
        except (ValueError, TypeError):
            raise ValueError("invalid_user_in_init_data")
    user = result.get("user")
    if not isinstance(user, dict) or type(user.get("id")) is not int or user["id"] <= 0:
        raise ValueError("invalid_user_in_init_data")

    return result


def generate_session_token(tg_id: int, expiry_seconds: int = 86400) -> str:
    """Generate a tamper-proof signed session token for a verified Telegram user.

    Payload is ``tg_id:exp:iat``; ``iat`` (issued-at) enables server-side
    revocation of every token minted at-or-before a per-user point in time.
    """
    exp = int(time.time()) + expiry_seconds
    iat = int(time.time())
    payload = f"{tg_id}:{exp}:{iat}"
    configured_token = getattr(config, "TOKEN", "")
    if not configured_token:
        raise ValueError("missing_bot_token")
    if type(tg_id) is not int or tg_id <= 0:
        raise ValueError("invalid_telegram_id")
    secret = configured_token.encode("utf-8")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_session_token(token_str: str) -> tuple[int, int, int] | None:
    """Decode + cryptographically verify a session token.

    Returns ``(tg_id, exp, iat)`` or None. Accepts both the current
    ``tg_id:exp:iat:sig`` format and legacy ``tg_id:exp:sig`` tokens
    (legacy handled as ``iat=0`` so any revocation invalidates them).
    """
    if not token_str or not isinstance(token_str, str):
        return None
    try:
        decoded = base64.urlsafe_b64decode(token_str.encode("utf-8")).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) == 4:
            tg_id_str, exp_str, iat_str, sig = parts
            payload = f"{tg_id_str}:{exp_str}:{iat_str}"
        elif len(parts) == 3:
            tg_id_str, exp_str, sig = parts
            iat_str = "0"
            payload = f"{tg_id_str}:{exp_str}"
        else:
            return None
        exp = int(exp_str)
        iat = int(iat_str)
        tg_id = int(tg_id_str)
        if time.time() >= exp or tg_id <= 0 or iat < 0:
            return None
        for secret_cand in _candidate_tokens():
            if not secret_cand:
                continue
            expected_sig = hmac.new(secret_cand.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
            if hmac.compare_digest(sig, expected_sig):
                return (tg_id, exp, iat)
    except Exception:
        return None
    return None


def verify_session_token(token_str: str) -> int | None:
    """Verify session token HMAC and expiration; returns verified tg_id or None."""
    decoded = decode_session_token(token_str)
    return decoded[0] if decoded else None


def session_is_revoked(iat: int, revoked_at: Any | None) -> bool:
    """Return True if a token issued at ``iat`` was revoked at ``revoked_at``."""
    if revoked_at is None:
        return False
    try:
        revoked_ts = revoked_at.timestamp()
    except AttributeError:
        revoked_ts = float(revoked_at) if revoked_at else 0.0
    return iat <= revoked_ts


def extract_session_token_from_request(request: Request) -> str:
    """Return the session token carried by the request, or ''."""
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return (
        request.headers.get("X-Session-Token")
        or request.query_params.get("session_token")
        or request.query_params.get("auth_token")
        or ""
    ).strip()


def extract_and_verify_telegram_user(request: Request, claimed_tg_id: int | None = None) -> int:
    """Require a signed session or fresh initData; a claimed ID is never identity."""
    # 1. Check Session Token in Authorization: Bearer <token> or X-Session-Token
    session_token = extract_session_token_from_request(request)

    if session_token:
        verified_tg_id = verify_session_token(session_token)
        if verified_tg_id:
            if claimed_tg_id is not None and int(claimed_tg_id) != verified_tg_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session user ID mismatch with claimed telegram_id")
            return verified_tg_id

    # 2. Check Telegram WebApp cryptographic initData
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    if not init_data:
        init_data = (request.query_params.get("init_data") or "").strip()

    if init_data:
        try:
            validated = validate_telegram_init_data_multi(init_data)
            verified_id = int(validated.get("user", {}).get("id") or 0)
            if not verified_id:
                raise ValueError("user_id_missing_in_init_data")
            if claimed_tg_id is not None and int(claimed_tg_id) != verified_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="init_data user ID mismatch with claimed telegram_id"
                )
            return verified_id
        except ValueError as e:
            logging.debug("Telegram initData validation failed: %s", e)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid Telegram authentication credentials"
    )
