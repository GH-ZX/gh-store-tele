import datetime
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from models.sms_activation import SmsActivation, SmsServiceConfig, SmsCountryConfig
from models.order import Order
from models.user import UserDTO
from routes.tma_sms import (
    get_sms_services,
    get_sms_countries,
    get_sms_price_quote,
    buy_sms_activation,
    get_sms_order_status,
    cancel_sms_order,
    ban_sms_order,
    admin_get_sms_settings,
    admin_toggle_sms_service,
    admin_toggle_sms_country,
)
from services.fivesim import FiveSimService


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeRequest:
    def __init__(self, json_data=None, headers=None):
        self._json = json_data or {}
        self.headers = headers or {}

    async def json(self):
        return self._json


@pytest.mark.asyncio
async def test_get_sms_services():
    mock_session = AsyncMock()
    mock_svc = SmsServiceConfig(
        service_code="telegram",
        name_en="Telegram",
        name_ar="تيليجرام",
        icon="📱",
        is_enabled=True,
        sort_order=1
    )
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_svc]
    mock_session.execute.return_value = mock_res

    with patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):
        res = await get_sms_services()
        assert res["status"] == "ok"
        assert len(res["services"]) == 1
        assert res["services"][0]["code"] == "telegram"
        assert res["services"][0]["name_en"] == "Telegram"


@pytest.mark.asyncio
async def test_get_sms_countries():
    mock_session = AsyncMock()
    mock_ctry = SmsCountryConfig(
        country_code="usa",
        name_en="USA",
        name_ar="أمريكا",
        flag_emoji="🇺🇸",
        is_enabled=True,
        sort_order=1
    )
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_ctry]
    mock_session.execute.return_value = mock_res

    with patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):
        res = await get_sms_countries()
        assert res["status"] == "ok"
        assert len(res["countries"]) == 1
        assert res["countries"][0]["code"] == "usa"
        assert res["countries"][0]["flag_emoji"] == "🇺🇸"


@pytest.mark.asyncio
async def test_get_sms_price_quote():
    prices = {
        "usa": {
            "telegram": {
                "virtual4": {"cost": 50.0, "count": 10},
                "virtual21": {"cost": 45.0, "count": 15},
            }
        }
    }
    with patch.object(FiveSimService, "get_prices", AsyncMock(return_value=prices)):
        res = await get_sms_price_quote("telegram", "usa")
        assert res["status"] == "ok"
        assert res["available"] is True
        assert res["stock_count"] == 25
        assert res["cost_usd"] == round(45.0 * FiveSimService.RUB_TO_USD_RATE, 2)
        assert res["sell_price_usd"] >= res["cost_usd"]


@pytest.mark.asyncio
async def test_buy_sms_activation_insufficient_balance():
    mock_session = AsyncMock()

    # Enable service and country
    svc_mock = MagicMock()
    svc_mock.scalar_one_or_none.return_value = SmsServiceConfig(service_code="telegram", is_enabled=True)
    ctry_mock = MagicMock()
    ctry_mock.scalar_one_or_none.return_value = SmsCountryConfig(country_code="usa", is_enabled=True)

    mock_session.execute.side_effect = [svc_mock, ctry_mock]

    # User with $0 balance
    user = MagicMock()
    user.top_up_amount = 0.0
    user.consume_records = 0.0

    prices = {"usa": {"telegram": {"v1": {"cost": 50.0, "count": 10}}}}

    req = FakeRequest(json_data={"tg_id": 12345, "service": "telegram", "country": "usa"})

    with patch("routes.tma_sms.extract_and_verify_telegram_user", return_value=12345), \
         patch("routes.tma_sms.UserRepository.get_by_tgid", AsyncMock(return_value=user)), \
         patch.object(FiveSimService, "get_prices", AsyncMock(return_value=prices)), \
         patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):

        res = await buy_sms_activation(req)
        assert res.status_code == 402


@pytest.mark.asyncio
async def test_buy_sms_activation_success():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    svc_mock = MagicMock()
    svc_mock.scalar_one_or_none.return_value = SmsServiceConfig(service_code="telegram", is_enabled=True)
    ctry_mock = MagicMock()
    ctry_mock.scalar_one_or_none.return_value = SmsCountryConfig(country_code="usa", is_enabled=True)

    mock_session.execute.side_effect = [svc_mock, ctry_mock]

    user = MagicMock()
    user.top_up_amount = 10.0
    user.consume_records = 0.0

    prices = {"usa": {"telegram": {"v1": {"cost": 50.0, "count": 10}}}}
    act_data = {
        "status": "ok",
        "activation_id": "act-999",
        "phone": "+1999888777",
        "price_rub": 50.0,
        "operator": "virtual4",
        "expires": "2026-09-13T12:00:00Z"
    }

    req = FakeRequest(json_data={"tg_id": 12345, "service": "telegram", "country": "usa"})

    with patch("routes.tma_sms.extract_and_verify_telegram_user", return_value=12345), \
         patch("routes.tma_sms.UserRepository.get_by_tgid", AsyncMock(return_value=user)), \
         patch.object(FiveSimService, "get_prices", AsyncMock(return_value=prices)), \
         patch.object(FiveSimService, "buy_activation", AsyncMock(return_value=act_data)), \
         patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):

        res = await buy_sms_activation(req)
        assert res["status"] == "ok"
        assert res["activation_id"] == "act-999"
        assert res["phone"] == "+1999888777"
        assert user.consume_records > 0.0


@pytest.mark.asyncio
async def test_get_sms_order_status_receives_code():
    mock_session = AsyncMock()

    activation = SmsActivation(
        id=1,
        order_id=10,
        telegram_id=12345,
        activation_id="act-999",
        phone="+1999888777",
        service="telegram",
        country="usa",
        status="pending",
        sell_price_usd=0.75,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    )
    act_res = MagicMock()
    act_res.scalar_one_or_none.return_value = activation

    order = Order(id=10, telegram_id=12345, status="pending_sms", details=[{"status": "pending_sms"}])
    ord_res = MagicMock()
    ord_res.scalar_one_or_none.return_value = order

    mock_session.execute.side_effect = [act_res, ord_res]

    upstream_data = {
        "status": "RECEIVED",
        "sms_code": "554433",
        "sms_text": "Code: 554433"
    }

    with patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)), \
         patch.object(FiveSimService, "check_order", AsyncMock(return_value=upstream_data)), \
         patch.object(FiveSimService, "finish_order", AsyncMock()):

        req = FakeRequest()
        res = await get_sms_order_status("act-999", req)
        assert res["status"] == "finished"
        assert res["sms_code"] == "554433"
        assert res["completed"] is True
        assert order.status == "completed"


@pytest.mark.asyncio
async def test_cancel_sms_order_and_refund():
    mock_session = AsyncMock()

    activation = SmsActivation(
        id=1,
        order_id=10,
        telegram_id=12345,
        activation_id="act-999",
        phone="+1999888777",
        service="telegram",
        country="usa",
        status="pending",
        sell_price_usd=0.75,
    )
    act_res = MagicMock()
    act_res.scalar_one_or_none.return_value = activation

    order = Order(id=10, telegram_id=12345, status="pending_sms", details=[{"status": "pending_sms"}])
    ord_res = MagicMock()
    ord_res.scalar_one_or_none.return_value = order

    mock_session.execute.side_effect = [act_res, ord_res]

    with patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)), \
         patch.object(FiveSimService, "cancel_order", AsyncMock()), \
         patch("routes.tma_sms.UserRepository.refund_balance", AsyncMock()) as mock_refund:

        req = FakeRequest()
        res = await cancel_sms_order("act-999", req)
        assert res["status"] == "ok"
        assert res["message"] == "activation_canceled_and_refunded"
        assert res["refunded_usd"] == 0.75
        mock_refund.assert_awaited_once_with(12345, 0.75, mock_session)
        assert activation.status == "canceled"
        assert order.status == "refunded"


@pytest.mark.asyncio
async def test_admin_sms_settings_and_toggles():
    mock_session = AsyncMock()

    svcs = [SmsServiceConfig(id=1, service_code="telegram", is_enabled=True, sort_order=1, name_en="TG", name_ar="تيلي")]
    ctries = [SmsCountryConfig(id=1, country_code="usa", is_enabled=True, sort_order=1, name_en="USA", name_ar="أمريكا", flag_emoji="🇺🇸")]

    s_res = MagicMock()
    s_res.scalars.return_value.all.return_value = svcs
    c_res = MagicMock()
    c_res.scalars.return_value.all.return_value = ctries

    mock_session.execute.side_effect = [s_res, c_res]

    req = FakeRequest(headers={"X-Telegram-User-Id": "1"})

    with patch("routes.tma_sms.verify_admin", return_value=True), \
         patch.object(FiveSimService, "get_balance", AsyncMock(return_value={"balance_rub": 100.0})), \
         patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):

        settings_res = await admin_get_sms_settings(req)
        assert settings_res["status"] == "ok"
        assert len(settings_res["services"]) == 1
        assert len(settings_res["countries"]) == 1
        assert settings_res["balance"]["balance_rub"] == 100.0

    # Toggle service
    mock_session2 = AsyncMock()
    svc = SmsServiceConfig(id=1, service_code="telegram", is_enabled=True)
    svc_res = MagicMock()
    svc_res.scalar_one_or_none.return_value = svc
    mock_session2.execute.return_value = svc_res

    toggle_req = FakeRequest(json_data={"admin_tg_id": 1, "service_code": "telegram", "is_enabled": False})
    with patch("routes.tma_sms.verify_admin", return_value=True), \
         patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session2)):

        res = await admin_toggle_sms_service(toggle_req)
        assert res["status"] == "ok"
        assert res["is_enabled"] is False
        assert svc.is_enabled is False


@pytest.mark.asyncio
async def test_admin_toggle_sms_country():
    mock_session = AsyncMock()
    ctry = SmsCountryConfig(id=1, country_code="usa", is_enabled=True)
    ctry_res = MagicMock()
    ctry_res.scalar_one_or_none.return_value = ctry
    mock_session.execute.return_value = ctry_res

    toggle_req = FakeRequest(json_data={"admin_tg_id": 1, "country_code": "usa", "is_enabled": False})
    with patch("routes.tma_sms.verify_admin", return_value=True), \
         patch("routes.tma_sms.get_db_session", return_value=_SessionContext(mock_session)):

        res = await admin_toggle_sms_country(toggle_req)
        assert res["status"] == "ok"
        assert res["is_enabled"] is False
        assert ctry.is_enabled is False


@pytest.mark.asyncio
async def test_poll_one_sms_activation_code_arrival():
    from services.order_polling import poll_one_sms_activation

    mock_session = AsyncMock()
    activation = SmsActivation(
        id=42,
        order_id=100,
        telegram_id=777,
        activation_id="act-42",
        phone="+1234567890",
        service="telegram",
        status="pending",
        sell_price_usd=0.80,
    )
    act_res = MagicMock()
    act_res.scalar_one_or_none.return_value = activation

    order = Order(id=100, telegram_id=777, status="pending_sms", details=[{"status": "pending_sms"}])
    ord_res = MagicMock()
    ord_res.scalar_one_or_none.return_value = order

    mock_session.execute.side_effect = [act_res, ord_res]

    upstream = {"status": "RECEIVED", "sms_code": "998811", "sms_text": "Code: 998811"}

    with patch.object(FiveSimService, "check_order", AsyncMock(return_value=upstream)), \
         patch.object(FiveSimService, "finish_order", AsyncMock()) as mock_finish, \
         patch("services.notification.NotificationService.send_to_user", AsyncMock()) as mock_notify:

        await poll_one_sms_activation(42, mock_session)

        assert activation.status == "finished"
        assert activation.sms_code == "998811"
        assert order.status == "completed"
        mock_finish.assert_awaited_once_with("act-42")
        mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_one_sms_activation_timeout_refund():
    from services.order_polling import poll_one_sms_activation

    mock_session = AsyncMock()
    activation = SmsActivation(
        id=43,
        order_id=101,
        telegram_id=888,
        activation_id="act-43",
        phone="+1234567891",
        service="whatsapp",
        status="pending",
        sell_price_usd=0.90,
        expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
    )
    act_res = MagicMock()
    act_res.scalar_one_or_none.return_value = activation

    order = Order(id=101, telegram_id=888, status="pending_sms", details=[{"status": "pending_sms"}])
    ord_res = MagicMock()
    ord_res.scalar_one_or_none.return_value = order

    mock_session.execute.side_effect = [act_res, ord_res]

    upstream = {"status": "TIMEOUT"}

    with patch.object(FiveSimService, "check_order", AsyncMock(return_value=upstream)), \
         patch("repositories.user.UserRepository.refund_balance", AsyncMock()) as mock_refund, \
         patch("services.notification.NotificationService.send_to_user", AsyncMock()) as mock_notify:

        await poll_one_sms_activation(43, mock_session)

        assert activation.status == "timeout"
        assert order.status == "refunded"
        mock_refund.assert_awaited_once_with(888, 0.90, mock_session)
        mock_notify.assert_awaited_once()

