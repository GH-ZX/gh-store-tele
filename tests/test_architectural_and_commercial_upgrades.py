import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.subscription_tracker import SubscriptionTrackerService
from services.batstore import BatStoreService
from services.user import UserService
from routes.common import verify_admin
import config


def test_parse_duration_days():
    # Explicit month
    assert SubscriptionTrackerService.parse_duration_days("ChatGPT Plus 1 Month") == 30
    assert SubscriptionTrackerService.parse_duration_days("Claude Pro 3 Months") == 90
    assert SubscriptionTrackerService.parse_duration_days("Gemini Advanced 6m") == 180

    # Explicit year
    assert SubscriptionTrackerService.parse_duration_days("Netflix Premium 1 Year") == 365
    assert SubscriptionTrackerService.parse_duration_days("NordVPN 2 Years") == 730

    # Explicit days
    assert SubscriptionTrackerService.parse_duration_days("Canva Pro 30 Days") == 30
    assert SubscriptionTrackerService.parse_duration_days("Spotify 14d Trial") == 14

    # Lifetime / no duration
    assert SubscriptionTrackerService.parse_duration_days("Windows 11 Pro Lifetime License") is None
    assert SubscriptionTrackerService.parse_duration_days("Office 365 مدى الحياة") is None
    assert SubscriptionTrackerService.parse_duration_days("") is None


@pytest.mark.asyncio
async def test_subscription_tracker_alert_dispatch():
    now = datetime.datetime.now(datetime.timezone.utc)
    # Order created 28 days ago for a 30-day product (2 days left = within 1-3 day window)
    created_date = now - datetime.timedelta(days=28)

    mock_order = MagicMock()
    mock_order.id = 101
    mock_order.telegram_id = 777888
    mock_order.status = "completed"
    mock_order.created_at = created_date
    mock_order.details = [{
        "product_id": 45,
        "name": "Claude Pro 1 Month",
        "quantity": 1,
    }]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_order]

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Not previously alerted

    with patch("services.subscription_tracker.session_execute", return_value=mock_result), \
         patch("services.notification.NotificationService.send_to_user", new_callable=AsyncMock) as mock_notify:

        alerts = await SubscriptionTrackerService.check_expiring_subscriptions(
            session=mock_session,
            redis_client=mock_redis
        )
        assert alerts == 1
        mock_notify.assert_awaited_once()
        call_args = mock_notify.await_args
        assert "ينتهي خلال" in call_args[0][0]
        assert call_args[0][1] == 777888
        mock_redis.setex.assert_awaited_once()


def test_verify_admin_check(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ID_LIST", [12345, 67890])
    assert verify_admin(12345) is True
    assert verify_admin(67890) is True
    assert verify_admin(99999) is False
    assert verify_admin(None) is False
    assert verify_admin(0) is False


def test_tiered_margin_bands_with_global_type():
    # Micro product (<= $2.00) with global_type='tiered' -> 50% markup
    sell_micro = BatStoreService.compute_sell_price(
        cost=1.50,
        global_percent=0.0,
        global_fixed=0.0,
        margin_type=None,
        margin_value=None,
        global_type="tiered"
    )
    assert sell_micro == 2.25

    # Standard product ($5.00) with global_type='tiered' -> 40% markup
    sell_std = BatStoreService.compute_sell_price(
        cost=5.00,
        global_percent=0.0,
        global_fixed=0.0,
        margin_type=None,
        margin_value=None,
        global_type="tiered"
    )
    assert sell_std == 7.00


@pytest.mark.asyncio
async def test_channel_membership_check():
    mock_bot = AsyncMock()
    mock_member = MagicMock()
    mock_member.status = "member"
    mock_bot.get_chat_member.return_value = mock_member

    # Active member returns True
    is_member = await UserService.check_channel_membership(mock_bot, user_id=123, channel_id="-1001234567")
    assert is_member is True

    # Left / kicked member returns False
    mock_member.status = "left"
    is_left = await UserService.check_channel_membership(mock_bot, user_id=123, channel_id="-1001234567")
    assert is_left is False

    # Exception returns False gracefully
    mock_bot.get_chat_member.side_effect = Exception("Chat not found")
    is_err = await UserService.check_channel_membership(mock_bot, user_id=123, channel_id="-1001234567")
    assert is_err is False


@pytest.mark.asyncio
async def test_bot_startup_description_config():
    mock_bot = AsyncMock()
    mock_bot.set_my_description = AsyncMock()
    mock_bot.set_my_short_description = AsyncMock()
    mock_bot.set_my_commands = AsyncMock()

    await mock_bot.set_my_description("Store description")
    await mock_bot.set_my_short_description("Short summary")
    mock_bot.set_my_description.assert_awaited_once_with("Store description")
    mock_bot.set_my_short_description.assert_awaited_once_with("Short summary")


@pytest.mark.asyncio
async def test_stars_subscription_update_handler():
    from handlers.user.stars import stars_subscription_update
    mock_event = MagicMock()
    mock_event.user.id = 998877
    mock_event.invoice_payload = "stars_sub:998877:prod_1"
    mock_event.state = "active"

    mock_session = AsyncMock()
    mock_bot = AsyncMock()

    with patch("services.notification.NotificationService.send_to_admins", new_callable=AsyncMock) as mock_admin:
        await stars_subscription_update(mock_event, mock_session, mock_bot)
        mock_bot.send_message.assert_awaited_once()
        call_text = mock_bot.send_message.await_args[1]["text"]
        assert "تم تجديد اشتراكك بنجاح" in call_text
        mock_admin.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_share_message_endpoint():
    from routes.tma_catalog import prepare_share_message
    from fastapi import Request

    class _MockReq:
        async def json(self):
            return {"product_id": 1, "tg_id": 12345}
        headers = {}
        query_params = {}

    mock_req = _MockReq()
    mock_prod = MagicMock()
    mock_prod.product_id = 1
    mock_prod.name = "Claude Pro 1 Month"
    mock_prod.sell_price_usd = 20.0

    mock_prep = MagicMock()
    mock_prep.id = "prep_msg_123"

    with patch("routes.tma_catalog.extract_and_verify_telegram_user", return_value=12345), \
         patch("repositories.batstore_product.BatStoreProductRepository.get_by_product_id", new_callable=AsyncMock, return_value=mock_prod), \
         patch("bot.bot.get_me", new_callable=AsyncMock, return_value=MagicMock(username="GHStoreBot")), \
         patch("bot.bot.save_prepared_inline_message", new_callable=AsyncMock, return_value=mock_prep):

        res = await prepare_share_message(mock_req)
        assert res["status"] == "ok"
        assert res["prepared_message_id"] == "prep_msg_123"


@pytest.mark.asyncio
async def test_supplier_recharge_fulfillment():
    from services.supplier_recharge import SupplierRechargeService
    mock_session = AsyncMock()
    mock_order = MagicMock()
    mock_order.id = 505
    mock_order.status = "pending_supplier_recharge"
    mock_order.details = [{"product_id": 1, "quantity": 1, "name": "Gemini Ultra"}]
    mock_order.telegram_id = 999111

    mock_prod = MagicMock()
    mock_prod.product_id = 1
    mock_prod.supplier = "batstore"

    with patch("repositories.batstore_order.BatStoreOrderRepository.get_by_id", new_callable=AsyncMock, return_value=mock_order), \
         patch("repositories.batstore_product.BatStoreProductRepository.get_by_product_id", new_callable=AsyncMock, return_value=mock_prod), \
         patch("services.batstore.BatStoreService.place_order", new_callable=AsyncMock, return_value={"order": {"items": [{"value": "key-12345"}]}}), \
         patch("repositories.batstore_order.BatStoreOrderRepository.update", new_callable=AsyncMock), \
         patch("db.session_commit", new_callable=AsyncMock), \
         patch("bot.bot.send_message", new_callable=AsyncMock) as mock_send, \
         patch("services.pdf_receipt.PDFReceiptService.dispatch_pdf_receipt", new_callable=AsyncMock):

        success, msg, goods = await SupplierRechargeService.check_and_fulfill_order(505, mock_session)
        assert success is True
        assert "key-12345" in goods
        assert mock_order.status == "completed"
        mock_send.assert_awaited_once()


def test_pdf_receipt_generation():
    from services.pdf_receipt import PDFReceiptService
    pdf_bytes = PDFReceiptService.generate_receipt_bytes(1001, {
        "total_sell": 19.99,
        "telegram_id": 123456789,
        "details": [{"name": "Claude Pro 1 Month", "quantity": 1, "sell_usd": 19.99, "delivery_goods": ["user:pass:2fa"]}],
    })
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_supplier_webhook_push():
    from routes.webhooks import supplier_order_webhook

    class _FakeReq:
        async def json(self):
            return {
                "order_id": "ext-777",
                "status": "completed",
                "items": [{"value": "activated_token_xyz"}]
            }

    mock_order = MagicMock()
    mock_order.id = 888
    mock_order.status = "pending_fulfillment"
    mock_order.external_order_ref = "ext-777"
    mock_order.customer_reference = "cust-888"
    mock_order.details = [{"name": "Netflix 1 Month", "delivery_goods": []}]
    mock_order.telegram_id = 444555

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_order

    with patch("routes.webhooks.session_execute", new_callable=AsyncMock, return_value=mock_res), \
         patch("repositories.batstore_order.BatStoreOrderRepository.update", new_callable=AsyncMock), \
         patch("db.session_commit", new_callable=AsyncMock), \
         patch("bot.bot.send_message", new_callable=AsyncMock) as mock_send, \
         patch("services.pdf_receipt.PDFReceiptService.dispatch_pdf_receipt", new_callable=AsyncMock):

        res = await supplier_order_webhook("batstore", _FakeReq())
        assert res["status"] == "completed"
        assert mock_order.status == "completed"
        mock_send.assert_awaited_once()


def test_promotional_banner_dto():
    from models.promotional_banner import PromotionalBannerDTO
    dto = PromotionalBannerDTO(
        title_ar="عرض خاص",
        title_en="Special Offer",
        badge_en="NEW",
        image_url="https://example.com/banner.png",
        product_id=42,
        is_active=True,
        sort_order=1
    )
    assert dto.title_en == "Special Offer"
    assert dto.product_id == 42
    assert dto.is_active is True
