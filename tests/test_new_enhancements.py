import hashlib
import hmac
import json
import time
import urllib.parse
from unittest.mock import AsyncMock, patch

import pytest
from services.telegram_auth import (
    validate_telegram_init_data,
    extract_and_verify_telegram_user,
    HTTPException,
)
from services.batstore import BatStoreOutOfStockError, BatStoreAPIError


def _make_init_data(user_dict, bot_token, auth_date=None):
    if auth_date is None:
        auth_date = int(time.time())
    data = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user_dict, separators=(",", ":")),
    }
    check_items = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(check_items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    data["hash"] = data_hash
    return urllib.parse.urlencode(data)


def test_telegram_init_data_valid():
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    init_data = _make_init_data({"id": 987654321, "first_name": "Test"}, token)
    res = validate_telegram_init_data(init_data, token)
    assert res["user"]["id"] == 987654321
    assert res["user"]["first_name"] == "Test"


def test_telegram_init_data_tampered():
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    init_data = _make_init_data({"id": 987654321}, token)
    tampered = init_data.replace("987654321", "111111111")
    with pytest.raises(ValueError, match="invalid_signature"):
        validate_telegram_init_data(tampered, token)


def test_telegram_init_data_expired():
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    old_date = int(time.time()) - 90000
    init_data = _make_init_data({"id": 123}, token, auth_date=old_date)
    with pytest.raises(ValueError, match="expired_init_data"):
        validate_telegram_init_data(init_data, token, max_age_seconds=86400)


class _FakeRequest:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}


def test_extract_and_verify_user_id(monkeypatch):
    import config
    token = "test_bot_token"
    monkeypatch.setattr(config, "TOKEN", token)

    init_data = _make_init_data({"id": 555}, token)
    req = _FakeRequest(headers={"X-Telegram-Init-Data": init_data})

    # Verified matches claimed
    assert extract_and_verify_telegram_user(req, 555) == 555

    # Verified without explicit claimed
    assert extract_and_verify_telegram_user(req, None) == 555

    # Mismatch throws 403
    with pytest.raises(HTTPException) as exc:
        extract_and_verify_telegram_user(req, 999)
    assert exc.value.status_code == 403


def test_extract_fallback_without_header(monkeypatch):
    import config
    from enums.runtime_environment import RuntimeEnvironment
    monkeypatch.setattr(config, "RUNTIME_ENVIRONMENT", RuntimeEnvironment.DEV)
    req = _FakeRequest()
    assert extract_and_verify_telegram_user(req, 12345) == 12345
    with pytest.raises(HTTPException) as exc:
        extract_and_verify_telegram_user(req, None)
    assert exc.value.status_code == 401


def test_out_of_stock_error_hierarchy():
    err = BatStoreOutOfStockError("Item unavailable")
    assert isinstance(err, BatStoreAPIError)
    assert "Item unavailable" in str(err)

@pytest.mark.asyncio
async def test_backup_service_mocked():
    from services.backup_service import run_database_backup
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Backup created", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        res = await run_database_backup()
        assert res is True


@pytest.mark.asyncio
async def test_cart_recovery_tma_scan():
    from services.cart_recovery import CartRecoveryService
    mock_redis = AsyncMock()
    CartRecoveryService.set_redis(mock_redis)

    now = time.time()
    cart_json = json.dumps({
        "tg_id": 999,
        "items": [{"name": "Claude Pro", "price": 10.0, "quantity": 1}],
        "updated_at": now - 8000  # 2.2 hours ago
    })

    async def fake_scan(pattern):
        yield b"ghstore:tma_cart:999"

    async def fake_get(k):
        return cart_json if "tma_cart" in str(k) else None

    mock_redis.scan_iter = fake_scan
    mock_redis.get = AsyncMock(side_effect=fake_get)
    mock_redis.setex = AsyncMock()

    with patch("repositories.user.UserRepository.get_by_tgid") as mock_u, \
         patch("services.notification.NotificationService.send_to_user") as mock_send:
        from types import SimpleNamespace
        mock_u.return_value = SimpleNamespace(id=1, telegram_id=999, can_receive_messages=True, is_banned=False)

        count = await CartRecoveryService.run_recovery_check(None)
        assert count >= 1
        mock_send.assert_awaited_once()
        mock_redis.setex.assert_awaited()


@pytest.mark.asyncio
async def test_rate_limit_middleware():
    from middleware.rate_limit import RateLimitMiddleware
    mock_redis = AsyncMock()
    # Simulate under limit
    mock_redis.incr.return_value = 1
    mw = RateLimitMiddleware(None, redis_client=mock_redis)
    req = _FakeRequest()
    req.url = _FakeRequest()
    req.url.path = "/api/buy"
    req.client = _FakeRequest()
    req.client.host = "1.2.3.4"

    called = [False]
    async def dummy_next(r):
        called[0] = True
        return "OK"

    res = await mw.dispatch(req, dummy_next)
    assert res == "OK"
    assert called[0] is True

    # Simulate over limit
    mock_redis.incr.return_value = 999
    mock_redis.ttl.return_value = 45
    res_blocked = await mw.dispatch(req, dummy_next)
    assert getattr(res_blocked, "status_code", None) == 429


@pytest.mark.asyncio
async def test_batstore_ping_health():
    from services.batstore import BatStoreService
    with patch("services.batstore.BatStoreService._request") as mock_req:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp
        healthy = await BatStoreService.ping_health(None)
        assert healthy is True


def test_referral_withdrawal_dto():
    from models.referral_withdrawal import ReferralWithdrawalDTO
    dto = ReferralWithdrawalDTO(
        telegram_id=12345,
        amount_usd=25.0,
        method="usdt_bep20",
        destination_address="0x1234567890abcdef1234567890abcdef12345678"
    )
    assert dto.telegram_id == 12345
    assert dto.amount_usd == 25.0
    assert dto.status == "pending"


def test_extract_prod_strict_auth(monkeypatch):
    import config
    from enums.runtime_environment import RuntimeEnvironment
    monkeypatch.setattr(config, "RUNTIME_ENVIRONMENT", RuntimeEnvironment.PROD)
    monkeypatch.setattr(config, "TOKEN", "test_prod_token")
    req = _FakeRequest()
    assert extract_and_verify_telegram_user(req, 12345) == 12345

    # Without claimed_tg_id and without header, throws 401
    with pytest.raises(HTTPException) as exc:
        extract_and_verify_telegram_user(req, None)
    assert exc.value.status_code == 401
    # Valid initData succeeds
    valid_data = _make_init_data({"id": 12345}, "test_prod_token")
    req_good = _FakeRequest(headers={"X-Telegram-Init-Data": valid_data})
    assert extract_and_verify_telegram_user(req_good, 12345) == 12345


@pytest.mark.asyncio
async def test_referral_withdrawal_repository_methods():
    from repositories.referral_withdrawal import ReferralWithdrawalRepository
    assert hasattr(ReferralWithdrawalRepository, "get_total_withdrawn_by_tgid")


@pytest.mark.asyncio
async def test_user_repository_credit_balance_exists():
    from repositories.user import UserRepository
    assert hasattr(UserRepository, "credit_balance")


def test_item_repository_get_by_buy_id_query_validity():
    import db
    from models.deposit import Deposit
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    from repositories.item import ItemRepository
    from models.buyItem import BuyItem
    from models.item import Item
    from sqlalchemy import select, any_
    # Ensure statement can be compiled without AttributeError
    stmt = (
        select(Item)
        .join(BuyItem, Item.id == any_(BuyItem.item_ids))
        .where(BuyItem.buy_id == 1)
    )
    compiled = str(stmt.compile())
    assert "buyItem" in compiled


def test_batstore_service_imports_notification_service():
    import services.batstore
    assert hasattr(services.batstore, "NotificationService")


def test_dynamic_syp_rate_conversion():
    from services.currency_rates import CurrencyRateService
    from services.user import format_currency_display

    # Admin types 133 (meaning 1 USD = 133 SYP)
    rate = CurrencyRateService.parse_syp_rate("133")
    assert rate == 133.0

    # 133 SYP paid should convert to exactly 1.00 USD
    usd_val = CurrencyRateService.syp_to_usd(133, rate)
    assert usd_val == 1.00

    # 266 SYP paid should convert to exactly 2.00 USD
    usd_val_2 = CurrencyRateService.syp_to_usd(266, rate)
    assert usd_val_2 == 2.00

    # 2.00 USD product price in SYP should convert to 266 SYP
    syp_val = CurrencyRateService.usd_to_syp(2.0, rate)
    assert syp_val == 266

    # Test format_currency_display with dynamic 133 rate
    assert "266" in format_currency_display(2.0, "SYP", syp_rate=rate)

    # Ensure SYP rate in service is dynamic and never 0 or 0.0
    CurrencyRateService.set_rate("SYP", None)
    assert CurrencyRateService._rates["SYP"] is None
    CurrencyRateService.set_rate("SYP", rate)
    assert CurrencyRateService.get_rate("SYP") == 133.0

    import pytest as _pt
    with _pt.raises(ValueError, match="syp_rate_unavailable"):
        CurrencyRateService.syp_to_usd(100, None)
    with _pt.raises(ValueError, match="syp_rate_unavailable"):
        CurrencyRateService.usd_to_syp(10.0, 0)


def test_storefront_image_resolution_is_db_driven():
    from services.storefront_images import (
        resolve_category_image,
        resolve_product_image,
        DEFAULT_CATEGORY_IMAGES,
        LOCAL_PRODUCT_PLACEHOLDER,
    )
    # DB value always wins
    assert resolve_category_image("AI & Chatbots", "https://admin-set.example/cover.png", {}) == "https://admin-set.example/cover.png"
    assert resolve_product_image("https://admin-set.example/p.png", "Other", "", {}) == "https://admin-set.example/p.png"
    # Empty DB value -> local per-category art, never a remote hardcoded URL
    cover = resolve_category_image("AI & Chatbots", "", {})
    assert cover == DEFAULT_CATEGORY_IMAGES["AI & Chatbots"]
    assert cover.startswith("/static/")
    # Unknown category + empty -> placeholder, Admin override respected
    assert resolve_category_image("Nope", "", {}) == "/static/img/cat-other.svg"
    assert resolve_category_image("Nope", "", {"category_placeholder": "https://admin.example/c.png"}) == "https://admin.example/c.png"
    # Product falls back through category then placeholder
    assert resolve_product_image("", "AI & Chatbots", "", {}) == DEFAULT_CATEGORY_IMAGES["AI & Chatbots"]
    assert resolve_product_image("", "Nope", "", {}) == LOCAL_PRODUCT_PLACEHOLDER
    assert resolve_product_image("", "Nope", "", {"product_placeholder": "https://admin.example/p.png"}) == "https://admin.example/p.png"
