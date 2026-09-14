import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from datetime import datetime, timezone
from fastapi import Request


@pytest.mark.asyncio
async def test_api_orders_returns_orders():
    from routes.tma_catalog import get_tma_orders
    from services.telegram_auth import generate_session_token

    tg_id = 99887766
    tok = generate_session_token(tg_id)

    # Mock order in DB
    order = SimpleNamespace(
        id=101,
        status="completed",
        total_sell=15.50,
        telegram_id=tg_id,
        created_at=datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc),
        warranty_claimed=False,
        details=[{
            "name": "Gemini Pro Subscription",
            "warranty_days": 30,
            "delivery_goods": ["user:pass123"],
            "instructions_ar": ["خطوة 1"],
            "instructions_en": ["Step 1"]
        }]
    )

    request = MagicMock(spec=Request)
    request.headers = {"Authorization": f"Bearer {tok}"}
    request.query_params = {"tg_id": str(tg_id)}
    request.cookies = {}

    with patch("routes.tma_catalog.BatStoreOrderRepository.get_by_telegram_id", new=AsyncMock(return_value=[order])):
        with patch("routes.tma_catalog.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session

            res = await get_tma_orders(request, tg_id=tg_id)
            assert res["status"] == "ok"
            assert len(res["orders"]) == 1
            o = res["orders"][0]
            assert o["id"] == 101
            assert o["status"] == "completed"
            assert o["total_sell"] == 15.50
            assert o["product_name"] == "Gemini Pro Subscription"
            assert o["delivery_goods"] == ["user:pass123"]
            assert o["warranty_days"] == 30


@pytest.mark.asyncio
async def test_api_orders_check_recovery():
    from routes.tma_checkout import check_order_recovery
    from services.telegram_auth import generate_session_token

    tg_id = 55443322
    tok = generate_session_token(tg_id)
    key = "idem-key-12345"

    order = SimpleNamespace(
        id=202,
        status="completed",
        total_sell=8.00,
        telegram_id=tg_id,
        checkout_key=key,
        details=[{
            "name": "ChatGPT Plus Key",
            "delivery_goods": ["KEY-ABC-123"]
        }]
    )

    request = MagicMock(spec=Request)
    request.headers = {"Authorization": f"Bearer {tok}"}
    request.query_params = {}
    request.cookies = {}
    request.json = AsyncMock(return_value={"tg_id": tg_id, "idempotency_key": key})

    with patch("routes.tma_checkout.get_db_session") as mock_db:
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = order
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_db.return_value.__aenter__.return_value = mock_session

        res = await check_order_recovery(request)
        assert res["status"] == "ok"
        assert res["order"]["id"] == 202
        assert res["order"]["status"] == "completed"
        assert res["order"]["delivery_goods"] == ["KEY-ABC-123"]


@pytest.mark.asyncio
async def test_bot_batstore_orders_rendering():
    from handlers.user.my_profile import batstore_orders
    from enums.language import Language

    tg_id = 112233
    order = SimpleNamespace(
        id=50,
        status="completed",
        total_sell=2.80,
        telegram_id=tg_id,
        created_at=datetime(2026, 9, 13, 11, 0, 0, tzinfo=timezone.utc),
        warranty_claimed=False,
        details=[{
            "name": "Gemini 18M",
            "delivery_goods": ["https://activation.google.com/test"],
            "warranty_days": 15
        }]
    )

    mock_msg = AsyncMock()
    mock_msg.from_user.id = tg_id
    mock_session = AsyncMock()

    with patch("repositories.batstore_order.BatStoreOrderRepository.get_by_telegram_id", new=AsyncMock(return_value=[order])):
        await batstore_orders(message=mock_msg, session=mock_session, language=Language.AR)

        assert mock_msg.answer.called
        text_arg = mock_msg.answer.call_args[0][0]
        assert "طلب #50" in text_arg
        assert "Gemini 18M" in text_arg
        assert "https://activation.google.com/test" in text_arg
        assert "$2.80" in text_arg


@pytest.mark.asyncio
async def test_api_user_me_authenticated():
    from routes.tma_catalog import get_tma_user_data
    from services.telegram_auth import generate_session_token

    tg_id = 7635553403
    tok = generate_session_token(tg_id)

    mock_user = SimpleNamespace(
        id=1,
        telegram_id=tg_id,
        telegram_username="ahmed_admin",
        language="ar",
        top_up_amount=50.0,
        consume_records=10.0,
        currency_preference="USD",
        referral_code="U_ABC123",
        custom_discount_pct=None,
        is_reseller=False,
    )

    request = MagicMock(spec=Request)
    request.headers = {"Authorization": f"Bearer {tok}"}
    request.query_params = {"tg_id": str(tg_id)}
    request.cookies = {}

    with patch("routes.tma_catalog.UserRepository.get_by_tgid", new=AsyncMock(return_value=mock_user)), \
         patch("routes.tma_catalog.BatStoreOrderRepository.get_by_telegram_id", new=AsyncMock(return_value=[])), \
         patch("routes.tma_catalog.UserRepository.get_referrals_qty_by_referrer_id", new=AsyncMock(return_value=3)), \
         patch("routes.tma_catalog.ReferralRepository.get_bonus_sum_as_referrer", new=AsyncMock(return_value=5.0)), \
         patch("routes.tma_catalog.ReferralRepository.get_referrals_breakdown", new=AsyncMock(return_value=[])), \
         patch("routes.tma_catalog.ConfigService.get", new=AsyncMock(return_value="14500")), \
         patch("routes.tma_catalog.get_db_session") as mock_db:
        mock_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_session

        res = await get_tma_user_data(request, tg_id=tg_id)
        assert res["telegram_id"] == tg_id
        assert res["username"] == "ahmed_admin"
        assert res["balance"] == 40.0
        assert res["total_spent"] == 10.0
        assert res["referrals_count"] == 3
        assert res["referrals_total_earned"] == 5.0
        assert "store_announcement" in res
        assert "orders" in res
        assert "recharges" in res

