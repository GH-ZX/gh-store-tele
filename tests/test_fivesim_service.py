import json
import pytest
from unittest.mock import AsyncMock, patch

from services.fivesim import (
    FiveSimService,
    FiveSimAPIError,
    FiveSimOutOfStockError,
    FiveSimLowBalanceError,
)
from services.supplier_registry import FiveSimAdapter, SupplierCapability


class MockResponse:
    def __init__(self, status, json_data=None, text_data=None):
        self.status = status
        self._json = json_data or {}
        self._text = text_data if text_data is not None else json.dumps(self._json)

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_fivesim_get_balance_success():
    mock_data = {"id": 1234, "email": "test@ghstore.me", "balance": 150.50, "rating": 98}
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, mock_data)):
        bal = await FiveSimService.get_balance()
        assert bal["balance_rub"] == 150.50
        assert bal["balance_usd"] == round(150.50 * FiveSimService.RUB_TO_USD_RATE, 2)
        assert bal["email"] == "test@ghstore.me"


@pytest.mark.asyncio
async def test_fivesim_get_balance_unauthorized():
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(401, {"error": "unauthorized"})):
        with pytest.raises(FiveSimAPIError, match="Invalid 5sim API key"):
            await FiveSimService.get_balance()


@pytest.mark.asyncio
async def test_fivesim_get_prices():
    prices = {
        "usa": {
            "telegram": {
                "virtual21": {"cost": 45.0, "count": 10},
                "virtual4": {"cost": 40.0, "count": 25},
            }
        }
    }
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, prices)):
        res = await FiveSimService.get_prices(country="usa", service="telegram")
        assert "usa" in res
        assert "telegram" in res["usa"]
        assert res["usa"]["telegram"]["virtual4"]["cost"] == 40.0


@pytest.mark.asyncio
async def test_fivesim_buy_activation_success():
    buy_resp = {
        "id": 998877,
        "phone": "+1234567890",
        "operator": "virtual4",
        "product": "telegram",
        "price": 40.0,
        "status": "PENDING",
        "expires": "2026-09-13T12:00:00Z",
        "country": "usa",
        "created_at": "2026-09-13T11:45:00Z",
    }
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, buy_resp)):
        act = await FiveSimService.buy_activation(country="usa", service="telegram", operator="any")
        assert act["status"] == "ok"
        assert act["activation_id"] == "998877"
        assert act["phone"] == "+1234567890"
        assert act["price_rub"] == 40.0


@pytest.mark.asyncio
async def test_fivesim_buy_activation_no_free_phones():
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(400, text_data="no free phones")):
        with pytest.raises(FiveSimOutOfStockError, match="No available numbers"):
            await FiveSimService.buy_activation(country="usa", service="telegram")


@pytest.mark.asyncio
async def test_fivesim_buy_activation_low_balance():
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(400, text_data="not enough balance")):
        with pytest.raises(FiveSimLowBalanceError, match="insufficient balance"):
            await FiveSimService.buy_activation(country="usa", service="telegram")


@pytest.mark.asyncio
async def test_fivesim_check_order_with_sms():
    order_resp = {
        "id": 998877,
        "phone": "+1234567890",
        "status": "RECEIVED",
        "sms": [
            {
                "created_at": "2026-09-13T11:47:00Z",
                "date": "2026-09-13T11:47:00Z",
                "sender": "Telegram",
                "text": "Your login code is 849201",
                "code": "849201",
            }
        ]
    }
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, order_resp)):
        status = await FiveSimService.check_order("998877")
        assert status["status"] == "RECEIVED"
        assert status["sms_code"] == "849201"
        assert "849201" in status["sms_text"]


@pytest.mark.asyncio
async def test_fivesim_finish_order():
    finish_resp = {"id": 998877, "status": "FINISHED"}
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, finish_resp)):
        res = await FiveSimService.finish_order("998877")
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_fivesim_cancel_order():
    cancel_resp = {"id": 998877, "status": "CANCELED"}
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, cancel_resp)):
        res = await FiveSimService.cancel_order("998877")
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_fivesim_ban_order():
    ban_resp = {"id": 998877, "status": "BANNED"}
    with patch("aiohttp.ClientSession.get", return_value=MockResponse(200, ban_resp)):
        res = await FiveSimService.ban_order("998877")
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_fivesim_adapter():
    adapter = FiveSimAdapter()
    assert adapter.name == "5sim"
    assert adapter.supports(SupplierCapability.SMS_ACTIVATION)
    assert adapter.supports(SupplierCapability.CANCEL)
    assert adapter.supports(SupplierCapability.BALANCE)

    with patch.object(FiveSimService, "get_balance", AsyncMock(return_value={"balance_usd": 25.0})):
        bal = await adapter.get_cached_balance(None)
        assert bal == 25.0

    with patch.object(FiveSimService, "check_order", AsyncMock(return_value={"status": "RECEIVED", "sms_code": "12345"})):
        st_info = await adapter.order_status(None, {"external_order_ref": "act-123"})
        assert st_info["status"] == "RECEIVED"
        assert st_info["sms_code"] == "12345"

    with patch.object(FiveSimService, "cancel_order", AsyncMock(return_value={"status": "ok"})):
        cancel_res = await adapter.cancel(None, {"external_order_ref": "act-123"})
        assert cancel_res["status"] == "ok"
