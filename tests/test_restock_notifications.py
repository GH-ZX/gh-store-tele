import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from callbacks import AllCategoriesCallback, BatStoreCallback, RestockCallback
from enums.bot_entity import BotEntity
from enums.language import Language
from models.batstore_product import BatStoreProductDTO
from models.restock_subscription import RestockSubscription, RestockSubscriptionDTO
from repositories.restock_subscription import RestockSubscriptionRepository
from services.restock_notification import RestockNotificationService
from utils.utils import get_text


class _FakeProduct:
    def __init__(self, pid=1, name="Netflix Premium", cost=5.0, sell=10.0, delivery="stock", stock=0):
        self.product_id = pid
        self.name = name
        self.cost_usd = cost
        self.sell_price_usd = sell
        self.delivery_type = delivery
        self.stock = stock
        self.description = "Test subscription"
        self.hidden = False
        self.warranty_days = 30
        self.image_url = None
        self.category = "Subscriptions"


def test_is_batstore_out_of_stock():
    # Stock delivery with 0 stock -> out of stock
    p1 = _FakeProduct(delivery="stock", stock=0)
    assert RestockNotificationService.is_batstore_out_of_stock(p1) is True

    # Stock delivery with None stock -> out of stock
    p2 = _FakeProduct(delivery="stock", stock=None)
    assert RestockNotificationService.is_batstore_out_of_stock(p2) is True

    # Stock delivery with positive stock -> in stock
    p3 = _FakeProduct(delivery="stock", stock=5)
    assert RestockNotificationService.is_batstore_out_of_stock(p3) is False

    # Activation delivery with stock=0 -> out of stock
    p4 = _FakeProduct(delivery="activation", stock=0)
    assert RestockNotificationService.is_batstore_out_of_stock(p4) is True

    # Activation delivery with stock=None -> in stock (on demand)
    p5 = _FakeProduct(delivery="activation", stock=None)
    assert RestockNotificationService.is_batstore_out_of_stock(p5) is False


@pytest.mark.asyncio
async def test_auto_subscribe_and_toggle(monkeypatch):
    # Mock repository
    stored_subs = {}

    async def fake_subscribe(telegram_id, user_id, batstore_product_id, subcategory_id, language, session):
        key = (telegram_id, batstore_product_id)
        dto = RestockSubscriptionDTO(
            id=1,
            telegram_id=telegram_id,
            user_id=user_id,
            batstore_product_id=batstore_product_id,
            subcategory_id=subcategory_id,
            language=language,
        )
        stored_subs[key] = dto
        return dto, True

    async def fake_unsubscribe(telegram_id, batstore_product_id, subcategory_id, session):
        key = (telegram_id, batstore_product_id)
        if key in stored_subs:
            del stored_subs[key]
            return True
        return False

    async def fake_is_subscribed(telegram_id, batstore_product_id, subcategory_id, session):
        return (telegram_id, batstore_product_id) in stored_subs

    monkeypatch.setattr(RestockSubscriptionRepository, "subscribe", fake_subscribe)
    monkeypatch.setattr(RestockSubscriptionRepository, "unsubscribe", fake_unsubscribe)
    monkeypatch.setattr(RestockSubscriptionRepository, "is_subscribed", fake_is_subscribed)

    session = MagicMock()

    # Product is out of stock -> auto-subscribe returns True
    oos_product = _FakeProduct(pid=101, stock=0)
    did_sub = await RestockNotificationService.auto_subscribe_if_out_of_stock(
        telegram_id=12345,
        user_id=1,
        product=oos_product,
        language=Language.EN,
        session=session,
    )
    assert did_sub is True
    assert (12345, 101) in stored_subs

    # Product in stock -> auto-subscribe returns False
    in_stock_product = _FakeProduct(pid=102, stock=5)
    did_sub_2 = await RestockNotificationService.auto_subscribe_if_out_of_stock(
        telegram_id=12345,
        user_id=1,
        product=in_stock_product,
        language=Language.EN,
        session=session,
    )
    assert did_sub_2 is False

    # Toggle subscription: currently subscribed -> should unsubscribe
    now_sub = await RestockNotificationService.toggle_batstore_subscription(
        telegram_id=12345,
        user_id=1,
        product_id=101,
        language=Language.EN,
        session=session,
    )
    assert now_sub is False
    assert (12345, 101) not in stored_subs

    # Toggle again -> should subscribe
    now_sub_2 = await RestockNotificationService.toggle_batstore_subscription(
        telegram_id=12345,
        user_id=1,
        product_id=101,
        language=Language.EN,
        session=session,
    )
    assert now_sub_2 is True
    assert (12345, 101) in stored_subs


@pytest.mark.asyncio
async def test_notify_batstore_product_restocked(monkeypatch):
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    sub = RestockSubscriptionDTO(
        id=42,
        telegram_id=98765,
        batstore_product_id=50,
        language="ar",
    )

    async def fake_get_active(pid, session):
        if pid == 50:
            return [sub]
        return []

    marked_notified = []

    async def fake_mark_notified(ids, session):
        marked_notified.extend(ids)

    monkeypatch.setattr(RestockSubscriptionRepository, "get_active_subscribers_for_product", fake_get_active)
    monkeypatch.setattr(RestockSubscriptionRepository, "mark_notified", fake_mark_notified)

    session = MagicMock()
    count = await RestockNotificationService.notify_batstore_product_restocked(
        batstore_product_id=50,
        product_name="Telegram Premium 1 Year",
        session=session,
        bot=mock_bot,
    )

    assert count == 1
    assert 42 in marked_notified
    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs["chat_id"] == 98765
    assert "Telegram Premium 1 Year" in call_args.kwargs["text"]
    # Verify the Arabic notification text was sent
    assert "بشرى سارة" in call_args.kwargs["text"]
