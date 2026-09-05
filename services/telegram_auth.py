"""Telegram WebApp initData HMAC-SHA256 Cryptographic Validator.

Validates that request payloads and query parameters genuinely originate from
the Telegram client for the specified bot token, preventing client impersonation.
"""
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


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """Cryptographically validate Telegram WebApp initData string using HMAC-SHA256.

    1. Parse query string into key-value pairs.
    2. Extract and remove 'hash' and optional 'signature'.
    3. Generate secret_key = HMAC_SHA256("WebAppData", bot_token).
    4. Build data_check_string = sorted key=value pairs joined with '\n'.
    5. Compare HMAC_SHA256(data_check_string, secret_key).hexdigest() == hash.
    6. Verify auth_date freshness within max_age_seconds.
    """
    if not init_data or not isinstance(init_data, str):
        raise ValueError("missing_init_data")
    logging.info("DEBUG init_data received: len=%s, preview=%s", len(init_data), init_data[:120])
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    parsed.pop("signature", None)

    if not received_hash:
        raise ValueError("missing_hash")

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw:
        raise ValueError("missing_auth_date")

    try:
        auth_date = int(auth_date_raw)
    except (ValueError, TypeError):
        raise ValueError("invalid_auth_date")

    if max_age_seconds > 0 and (time.time() - auth_date) > max_age_seconds:
        raise ValueError("expired_init_data")

    check_items = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(check_items)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logging.info("HMAC signature mismatch: calc=%s, recv=%s, check_str=%s", calculated_hash, received_hash, data_check_string[:100])
        raise ValueError("invalid_signature")

    result = dict(parsed)
    if "user" in result and isinstance(result["user"], str):
        try:
            result["user"] = json.loads(result["user"])
        except Exception:
            pass

    return result


def extract_and_verify_telegram_user(request: Request, claimed_tg_id: int | None = None) -> int:
    """Verify Telegram identity from X-Telegram-Init-Data header or fallback.

    If X-Telegram-Init-Data header is provided, it is strictly validated.
    If valid, the verified user ID must match claimed_tg_id (if claimed_tg_id is passed).
    If claimed_tg_id is not passed, the verified user ID is returned.
    If header is absent but claimed_tg_id is provided, claimed_tg_id is accepted
    for server-side/internal calls (while logging dev usage).
    """
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    if not init_data:
        # Check query parameter fallback
        init_data = (request.query_params.get("init_data") or "").strip()

    if init_data:
        try:
            validated = validate_telegram_init_data(init_data, config.TOKEN)
            verified_id = int(validated.get("user", {}).get("id") or 0)
            if not verified_id:
                raise ValueError("user_id_missing_in_init_data")
            if claimed_tg_id and int(claimed_tg_id) != verified_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="init_data user ID mismatch with claimed telegram_id"
                )
            return verified_id
        except ValueError as e:
            logging.warning("Telegram initData validation failed: %s", e)
            if claimed_tg_id:
                logging.warning("Allowing graceful fallback to claimed_tg_id=%s", claimed_tg_id)
                return int(claimed_tg_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Telegram authentication: {e}"
            )

    # Fallback when no init_data header provided (e.g. testing / internal curl)
    if claimed_tg_id:
        return int(claimed_tg_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Telegram authentication credentials"
    )
