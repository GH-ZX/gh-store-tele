import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.g2bulk import G2BulkService
from services.multi_supplier import MultiSupplierService


class _FakeClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"

    def json(self):
        return self._payload


class _JsonRequest:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_create_game_order_sends_contract_and_uuid_idempotency():
    client = MagicMock()
    client.post = AsyncMock(return_value=_Response({
        "success": True,
        "order": {"order_id": 42, "status": "PENDING", "player_name": "Player"},
    }))

    with patch.object(G2BulkService, "resolve_api_url", AsyncMock(return_value="https://g2bulk.test/v1")), \
         patch.object(G2BulkService, "_headers", AsyncMock(return_value={"X-API-Key": "secret"})), \
         patch.object(G2BulkService, "_client", AsyncMock(return_value=_FakeClientContext(client))):
        result = await G2BulkService.create_game_order(
            AsyncMock(),
            "mlbb",
            "86 Diamonds",
            "123456",
            server_id="2001",
            charname="Player",
            remark="customer-ref",
            idempotency_key="customer-ref",
        )

    request = client.post.await_args
    assert request.args[0] == "https://g2bulk.test/v1/games/mlbb/order"
    assert request.kwargs["json"] == {
        "catalogue_name": "86 Diamonds",
        "player_id": "123456",
        "server_id": "2001",
        "charname": "Player",
        "remark": "customer-ref",
    }
    assert len(request.kwargs["headers"]["X-Idempotency-Key"]) == 36
    assert result["order_id"] == 42
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_check_player_id_maps_valid_response():
    client = MagicMock()
    client.post = AsyncMock(return_value=_Response({
        "valid": "valid",
        "name": "Player Name",
        "openid": "open-1",
    }))

    with patch.object(G2BulkService, "resolve_api_url", AsyncMock(return_value="https://g2bulk.test/v1")), \
         patch.object(G2BulkService, "_headers", AsyncMock(return_value={})), \
         patch.object(G2BulkService, "_client", AsyncMock(return_value=_FakeClientContext(client))):
        result = await G2BulkService.check_player_id(
            "mlbb", "123456", server_id="2001", charname="Player Name"
        )

    assert result == {
        "valid": True,
        "name": "Player Name",
        "openid": "open-1",
        "message": "Player verified successfully",
        "raw": {"valid": "valid", "name": "Player Name", "openid": "open-1"},
    }
    assert client.post.await_args.kwargs["json"] == {
        "game": "mlbb",
        "user_id": "123456",
        "server_id": "2001",
        "charname": "Player Name",
    }


@pytest.mark.asyncio
async def test_purchase_voucher_polls_pending_delivery():
    client = MagicMock()
    client.post = AsyncMock(return_value=_Response({
        "success": True,
        "order_id": 77,
        "status": "PENDING",
        "delivery_items": [],
    }))
    delivery = {"status": "COMPLETED", "delivery_items": [{"code": "PIN-777"}]}

    with patch.object(G2BulkService, "resolve_api_url", AsyncMock(return_value="https://g2bulk.test/v1")), \
         patch.object(G2BulkService, "_headers", AsyncMock(return_value={"X-API-Key": "secret"})), \
         patch.object(G2BulkService, "_client", AsyncMock(return_value=_FakeClientContext(client))), \
         patch.object(G2BulkService, "get_delivery", AsyncMock(return_value=delivery)), \
         patch("services.g2bulk.asyncio.sleep", AsyncMock()):
        result = await G2BulkService.purchase_voucher(
            AsyncMock(), 9001, idempotency_key="voucher-ref", max_poll_attempts=1
        )

    assert result["status"] == "COMPLETED"
    assert result["delivery_items"] == [{"code": "PIN-777"}]
    assert G2BulkService.extract_delivery_goods(result) == ["PIN-777"]
    assert client.post.await_args.args[0] == "https://g2bulk.test/v1/products/9001/purchase"
    assert client.post.await_args.kwargs["json"] == {"quantity": 1}


@pytest.mark.asyncio
async def test_multisupplier_game_order_stays_pending_without_voucher_goods():
    product = SimpleNamespace(
        product_id=30000001,
        supplier="g2bulk",
        delivery_type="direct_topup",
        reseller_key_override="mlbb",
        extra_meta={"game_code": "mlbb"},
    )
    with patch.object(G2BulkService, "create_game_order", AsyncMock(return_value={
        "order_id": 88,
        "status": "PENDING",
    })) as create_order:
        result = await MultiSupplierService.place_order_with_failover(
            AsyncMock(),
            product,
            customer_reference="cust-1",
            idempotency_key="cust-1",
            extra_params={
                "catalogue_name": "86 Diamonds",
                "player_id": "123456",
                "server_id": "2001",
            },
        )

    create_order.assert_awaited_once()
    assert result["external_order_ref"] == "g2b-game-88"
    assert result["status"] == "PENDING"
    assert result["goods"] == []


@pytest.mark.asyncio
async def test_games_check_player_endpoint_authenticates_and_forwards_request():
    from routes.tma_catalog import check_game_player

    with patch("routes.tma_catalog.extract_and_verify_telegram_user", return_value=1), \
         patch("routes.tma_catalog.get_db_session", return_value=_SessionContext(AsyncMock())), \
         patch.object(G2BulkService, "check_player_id", AsyncMock(return_value={
             "valid": True,
             "name": "Player Name",
         })) as check_player:
        missing = await check_game_player(_JsonRequest({"tg_id": 1, "game_code": "mlbb"}))
        assert missing.status_code == 400

        response = await check_game_player(_JsonRequest({
            "tg_id": 1,
            "game_code": "mlbb",
            "user_id": "123456",
            "server_id": "2001",
        }))

    assert response == {"valid": True, "name": "Player Name"}
    check_player.assert_awaited_once()
    assert check_player.await_args.kwargs["game_code"] == "mlbb"
    assert check_player.await_args.kwargs["user_id"] == "123456"
    assert check_player.await_args.kwargs["server_id"] == "2001"

def test_voucher_category_filter_and_guide_are_game_specific():
    assert G2BulkService.is_game_voucher_category("PUBG Mobile UC Vouchers") is True
    assert G2BulkService.is_game_voucher_category("Netflix Gift Cards") is False
    guide = G2BulkService.get_redemption_guide_for_title("Steam Wallet Gift Card")
    assert guide["url"] == "https://store.steampowered.com/account/redeemwalletcode"
    assert guide["steps_en"]
