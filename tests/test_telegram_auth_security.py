"""Authentication regression tests use real HMAC credentials, never identity mocks."""
import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
import config
from routes.common import verify_admin
from services import telegram_auth as auth


def signed_init(user=None, auth_date=None, **extra):
    data = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "user": json.dumps({"id": 123} if user is None else user),
        **extra,
    }
    secret = hmac.new(b"WebAppData", config.TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def request(headers=None, query=None, body=None):
    async def read_body():
        return body or {}
    return SimpleNamespace(headers=headers or {}, query_params=query or {}, json=read_body)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer forged"}, {"X-Telegram-Init-Data": "hash=forged"}])
def test_claimed_id_cannot_authenticate_or_elevate(headers, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ID_LIST", [123])
    req = request(headers)
    with pytest.raises(auth.HTTPException) as exc:
        auth.extract_and_verify_telegram_user(req, 123)
    assert exc.value.status_code == 401
    assert verify_admin(123, req) is False


def test_signed_session_mismatch_is_forbidden_even_with_another_valid_init_data():
    req = request({"Authorization": "Bearer " + auth.generate_session_token(123),
                   "X-Telegram-Init-Data": signed_init({"id": 999})})
    with pytest.raises(auth.HTTPException) as exc:
        auth.extract_and_verify_telegram_user(req, 999)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("header", ["Authorization", "X-Session-Token"])
def test_real_signed_session_authenticates(header):
    token = auth.generate_session_token(123)
    req = request({header: ("Bearer " if header == "Authorization" else "") + token})
    assert auth.extract_and_verify_telegram_user(req, 123) == 123


@pytest.mark.parametrize("offset,error", [(-3601, "expired_init_data"), (300, "future_init_data")])
def test_init_data_freshness(offset, error):
    data = signed_init(auth_date=int(time.time()) + offset)
    with pytest.raises(ValueError, match=error):
        auth.validate_telegram_init_data_multi(data)
    with pytest.raises(auth.HTTPException) as exc:
        auth.extract_and_verify_telegram_user(request({"X-Telegram-Init-Data": data}), 123)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("user", [[], "bad", {}, {"id": -1}, {"id": True}, {"id": "123"}])
def test_malformed_signed_user_rejected(user):
    with pytest.raises(ValueError, match="invalid_user_in_init_data"):
        auth.validate_telegram_init_data_multi(signed_init(user))


def test_optional_telegram_signature_is_included_in_hmac():
    assert auth.validate_telegram_init_data_multi(signed_init(signature="telegram-signature"))["user"]["id"] == 123


def test_duplicate_fields_rejected():
    with pytest.raises(ValueError, match="duplicate_init_data_field"):
        auth.validate_telegram_init_data_multi(signed_init() + "&user=%7B%22id%22%3A999%7D")


def test_missing_bot_token_cannot_use_public_fallback_secret(monkeypatch):
    monkeypatch.setattr(config, "TOKEN", "")
    monkeypatch.setattr(auth, "_CANDIDATE_TOKENS", [])
    payload = f"123:{int(time.time()) + 300}"
    sig = hmac.new(b"ghstore_bot_secret", payload.encode(), hashlib.sha256).hexdigest()[:32]
    token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    assert auth.verify_session_token(token) is None
    with pytest.raises(ValueError, match="missing_bot_token"):
        auth.generate_session_token(123)


def test_expired_session_rejected():
    assert auth.verify_session_token(auth.generate_session_token(123, expiry_seconds=-1)) is None


@pytest.mark.asyncio
async def test_session_exchange_rejects_stale_init_data():
    from routes.tma_catalog import create_auth_session
    response = await create_auth_session(request(body={"init_data": signed_init(auth_date=int(time.time()) - 3601)}))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_session_exchange_returns_one_day_signed_session():
    from routes.tma_catalog import create_auth_session
    response = await create_auth_session(request(body={"init_data": signed_init()}))
    assert auth.verify_session_token(response["token"]) == 123
    expiration = int(base64.urlsafe_b64decode(response["token"]).decode().split(":")[1])
    assert 86395 <= expiration - time.time() <= 86400


@pytest.mark.asyncio
async def test_session_exchange_rejects_revoked_launch_token(monkeypatch):
    from routes import tma_catalog
    token = auth.generate_session_token(123)

    @asynccontextmanager
    async def _revoked_db(*a, **k):
        class _Result:
            def scalar(self):
                return datetime.fromtimestamp(int(time.time()) + 60)

        class _Session:
            async def execute(self, stmt):
                return _Result()

        yield _Session()

    monkeypatch.setattr(tma_catalog, "get_db_session", _revoked_db)
    resp = await tma_catalog.create_auth_session(request(body={"auth_token": token}))
    assert resp.status_code == 401
    assert b"session_revoked" in resp.body


@pytest.mark.asyncio
async def test_session_exchange_accepts_active_launch_token():
    from routes.tma_catalog import create_auth_session
    token = auth.generate_session_token(123)
    resp = await create_auth_session(request(body={"auth_token": token}))
    assert resp["status"] == "ok"
    assert auth.verify_session_token(resp["token"]) == 123


# ---- Session revocation (audit item 11) ----
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock


def test_session_token_embeds_issued_at():
    token = auth.generate_session_token(123)
    decoded = auth.decode_session_token(token)
    assert decoded is not None
    tg_id, exp, iat = decoded
    assert tg_id == 123
    assert 0 < iat <= exp
    assert abs(iat - int(time.time())) < 60


def test_legacy_three_part_token_still_verifies():
    exp = int(time.time()) + 3600
    payload = f"123:{exp}"
    sig = hmac.new(config.TOKEN.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    legacy = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    assert auth.verify_session_token(legacy) == 123
    assert auth.decode_session_token(legacy) == (123, exp, 0)


def test_decode_rejects_tampered_or_malformed_token():
    assert auth.decode_session_token("") is None
    assert auth.decode_session_token("garbage") is None
    assert auth.decode_session_token(None) is None
    token = auth.generate_session_token(123)
    parts = base64.urlsafe_b64decode(token).decode().split(":")
    tampered = base64.urlsafe_b64encode(f"{parts[0]}:{parts[1]}:{parts[2]}:{'0' * 32}".encode()).decode()
    assert auth.decode_session_token(tampered) is None


@pytest.mark.parametrize("iat,revoked_at,expected", [
    (0, datetime(2026, 1, 1), True),
    (1700000000, datetime(2026, 1, 1), True),
    (1780000000, datetime(2026, 1, 1), False),
    (0, None, False),
])
def test_session_is_revoked_logic(iat, revoked_at, expected):
    assert auth.session_is_revoked(iat, revoked_at) is expected


def _make_scope(path="/api/catalog/items", headers=()):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "state": {},
    }


class _RecordingApp:
    def __init__(self):
        self.calls = []
        self.sent = []

    async def __call__(self, scope, receive, send):
        self.calls.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b"{}"})


async def _drive_middleware(middleware, scope):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware(scope, receive, send)
    return sent


def _bind_get_db_session(monkeypatch, factory=None, result=None):
    import db as db_module

    @asynccontextmanager
    async def _db_cm(*a, **k):
        class _Result:
            def scalar(self):
                return result

        class _Session:
            async def execute(self, stmt):
                return _Result()

        yield (_Session() if factory is None else factory())

    monkeypatch.setattr(db_module, "get_db_session", _db_cm)


from middleware.session_revocation import SessionRevocationMiddleware  # noqa: E402


@pytest.mark.asyncio
async def test_middleware_rejects_revoked_session(monkeypatch):
    token = auth.generate_session_token(123)
    _bind_get_db_session(monkeypatch, result=datetime.fromtimestamp(int(time.time()) + 60))
    app = _RecordingApp()
    mw = SessionRevocationMiddleware(app)
    sent = await _drive_middleware(
        mw, _make_scope(headers=[(b"authorization", b"Bearer " + token.encode())])
    )
    assert app.calls == []
    assert sent[0]["status"] == 401
    body = b"".join(m["body"] for m in sent if m["type"] == "http.response.body")
    assert b"session_revoked" in body


@pytest.mark.asyncio
async def test_middleware_allows_session_when_not_revoked(monkeypatch):
    token = auth.generate_session_token(123)
    _bind_get_db_session(monkeypatch, result=None)
    app = _RecordingApp()
    mw = SessionRevocationMiddleware(app)
    sent = await _drive_middleware(
        mw, _make_scope(headers=[(b"authorization", b"Bearer " + token.encode())])
    )
    assert app.calls == ["/api/catalog/items"]
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_fails_open_when_db_unavailable(monkeypatch):
    token = auth.generate_session_token(123)
    import db as db_module

    @asynccontextmanager
    async def _broken_db(*a, **k):
        raise RuntimeError("db down")
        yield None  # pragma: no cover

    monkeypatch.setattr(db_module, "get_db_session", _broken_db)
    app = _RecordingApp()
    mw = SessionRevocationMiddleware(app)
    sent = await _drive_middleware(
        mw, _make_scope(headers=[(b"authorization", b"Bearer " + token.encode())])
    )
    assert app.calls == ["/api/catalog/items"]
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_skips_non_api_paths():
    app = _RecordingApp()
    mw = SessionRevocationMiddleware(app)
    sent = await _drive_middleware(mw, _make_scope(path="/health", headers=[(b"authorization", b"Bearer x")]))
    assert app.calls == ["/health"]
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_admin_revoke_session_endpoint(monkeypatch):
    import routes.tma_admin as admin_routes
    from models.user import UserDTO

    target = UserDTO(telegram_id=777, sessions_revoked_at=None)

    @asynccontextmanager
    async def _fake_db(*a, **k):
        yield SimpleNamespace(add=lambda obj: None)

    async def fake_get(tgid, session):
        return target

    monkeypatch.setattr(admin_routes, "get_db_session", _fake_db)
    monkeypatch.setattr(admin_routes, "verify_admin", lambda *a, **k: True)
    monkeypatch.setattr(admin_routes.UserRepository, "get_by_tgid", fake_get)
    monkeypatch.setattr(admin_routes.UserRepository, "update", AsyncMock())
    monkeypatch.setattr(admin_routes, "session_commit", AsyncMock())
    monkeypatch.setattr(admin_routes, "invalidate_admin_stats_cache", lambda: None)

    resp = await admin_routes.admin_revoke_session(request(body={"admin_tg_id": 1, "target_tg_id": 777}))
    assert resp["status"] == "ok"
    assert target.sessions_revoked_at is not None


@pytest.mark.asyncio
async def test_admin_unrevoke_session_endpoint(monkeypatch):
    import routes.tma_admin as admin_routes
    from models.user import UserDTO

    target = UserDTO(telegram_id=777, sessions_revoked_at=datetime(2026, 1, 1))

    @asynccontextmanager
    async def _fake_db(*a, **k):
        yield SimpleNamespace(add=lambda obj: None)

    async def fake_get(tgid, session):
        return target

    monkeypatch.setattr(admin_routes, "get_db_session", _fake_db)
    monkeypatch.setattr(admin_routes, "verify_admin", lambda *a, **k: True)
    monkeypatch.setattr(admin_routes.UserRepository, "get_by_tgid", fake_get)
    monkeypatch.setattr(admin_routes.UserRepository, "update", AsyncMock())
    monkeypatch.setattr(admin_routes, "session_commit", AsyncMock())
    monkeypatch.setattr(admin_routes, "invalidate_admin_stats_cache", lambda: None)

    resp = await admin_routes.admin_unrevoke_session(request(body={"admin_tg_id": 1, "target_tg_id": 777}))
    assert resp["status"] == "ok"
    assert target.sessions_revoked_at is None


@pytest.mark.asyncio
async def test_admin_revoke_session_requires_admin(monkeypatch):
    import routes.tma_admin as admin_routes
    monkeypatch.setattr(admin_routes, "verify_admin", lambda *a, **k: False)
    resp = await admin_routes.admin_revoke_session(request(body={"admin_tg_id": 1, "target_tg_id": 777}))
    assert resp.status_code == 403
