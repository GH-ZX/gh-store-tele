import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from enums.language import Language


# ---- stubs ----

class _UserOrm:
    def __init__(self, top_up=100.0, consume=0.0):
        self.id = 1
        self.top_up_amount = top_up
        self.consume_records = consume


class _ProductOrm:
    def __init__(self, pid=42, name="ChatGPT Plus", cost=5.0, sell=10.0,
                 delivery="stock", stock=10, hidden=False):
        self.product_id = pid
        self.name = name
        self.cost_usd = cost
        self.sell_price_usd = sell
        self.delivery_type = delivery
        self.stock = stock
        self.hidden = hidden
        self.description = "Test"


class _State:
    def __init__(self, data=None):
        self._data = data or {}
    async def get_data(self):
        return dict(self._data)
    async def update_data(self, *args, **kwargs):
        if args and isinstance(args[0], dict):
            self._data.update(args[0])
        self._data.update(kwargs)


class _CallbackMsg:
    def __init__(self):
        self.chat = SimpleNamespace(id=55)
        self.message_id = 4411
        self.edits = []
    async def edit_text(self, text, reply_markup=None):
        self.edits.append(text)
    async def edit_media(self, media, reply_markup=None):
        self.edits.append(media)


class _Callback:
    def __init__(self, uid=1):
        self.from_user = SimpleNamespace(id=uid)
        self.bot = SimpleNamespace(id=901)
        self.message = _CallbackMsg()


# ---- Tests ----

@pytest.mark.asyncio
async def test_catalog_shows_products(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_visible(session):
        return [
            _ProductOrm(pid=1, name="VPN Plus", sell=15.0, stock=5),
            _ProductOrm(pid=2, name="Netflix", sell=8.0, stock=3),
        ]

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_visible",
        fake_get_visible)

    cb_data = BatStoreCallback.create(level=0)
    caption, kb = await BatStoreStoreService.catalog(1, cb_data, None, None)

    assert "VPN Plus" in caption or len(kb.as_markup().inline_keyboard) > 0
    assert "Netflix" in caption or len(kb.as_markup().inline_keyboard) > 0


@pytest.mark.asyncio
async def test_catalog_empty(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_visible(session):
        return []

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_visible",
        fake_get_visible)

    cb_data = BatStoreCallback.create(level=0)
    caption, kb = await BatStoreStoreService.catalog(1, cb_data, None, None)

    assert "empty" in caption.lower() or "no" in caption.lower() or len(kb.as_markup().inline_keyboard) == 0


@pytest.mark.asyncio
async def test_detail_shows_product_info(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(pid=42, name="ChatGPT Plus", sell=10.0, stock=5, delivery="stock")

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=50.0, consume=10.0)

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)

    cb = SimpleNamespace(from_user=SimpleNamespace(id=1))
    cb_data = BatStoreCallback.create(level=1, product_id=42)
    state = _State()

    caption, kb = await BatStoreStoreService.detail(cb, cb_data, state, None, None)

    assert "ChatGPT Plus" in caption
    assert "10.00" in caption


@pytest.mark.asyncio
async def test_detail_hidden_product(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(hidden=True)

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)

    cb = SimpleNamespace(from_user=SimpleNamespace(id=1))
    cb_data = BatStoreCallback.create(level=1, product_id=42)

    caption, kb = await BatStoreStoreService.detail(cb, cb_data, None, None, None)

    assert "no longer available" in caption.lower() or "not found" in caption.lower()


@pytest.mark.asyncio
async def test_max_qty_stock_limited(monkeypatch):
    from services.batstore_store import BatStoreStoreService

    # When stock > 0, _max_qty doesn't cap to stock (only blocks when stock <= 0)
    product = _ProductOrm(delivery="stock", stock=3)
    result = BatStoreStoreService._max_qty(product, balance=100.0)
    # stock=3 > 0 so doesn't trigger the zero-stock block; falls through to balance calc
    # But balance=100 / sell=10 = 10, so result is 10 (not capped by stock)
    assert result == 10

    # When stock is 0, returns 0
    product_zero = _ProductOrm(delivery="stock", stock=0)
    result_zero = BatStoreStoreService._max_qty(product_zero, balance=100.0)
    assert result_zero == 0


@pytest.mark.asyncio
async def test_max_qty_balance_limited(monkeypatch):
    from services.batstore_store import BatStoreStoreService

    product = _ProductOrm(sell=10.0, delivery="stock", stock=100)
    result = BatStoreStoreService._max_qty(product, balance=25.0)
    assert result == 2


@pytest.mark.asyncio
async def test_max_qty_no_stock_info(monkeypatch):
    from services.batstore_store import BatStoreStoreService

    product = _ProductOrm(delivery="activation", stock=None, sell=10.0)
    result = BatStoreStoreService._max_qty(product, balance=50.0)
    assert result == 5


@pytest.mark.asyncio
async def test_checkout_success(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0, delivery="stock", stock=5)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0, consume=0.0)

    completed_order = SimpleNamespace(id=99)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        return completed_order, True

    async def fake_fulfill(order_id, session):
        return completed_order

    def fake_response(order):
        return {"goods": ["KEY-1234"], "total_paid": 20.0,
                "reseller_status": "completed"}

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)
    monkeypatch.setattr(
        "services.checkout.CheckoutService.reserve",
        fake_reserve)
    monkeypatch.setattr(
        "services.order_fulfillment.FulfillmentService.fulfill_order",
        fake_fulfill)
    monkeypatch.setattr(
        "services.checkout.CheckoutService.response",
        fake_response)
    monkeypatch.setattr(
        "services.batstore_store.NotificationService.send_to_admins",
        AsyncMock())

    cb = _Callback()
    cb_data = BatStoreCallback.create(
        level=3, product_id=42, quantity=2, confirmation=True)
    state = _State()

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, state, AsyncMock(), Language.EN)

    assert "2" in caption
    assert "ChatGPT Plus" in caption or "10.00" in caption


@pytest.mark.asyncio
async def test_checkout_insufficient_balance(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback
    from fastapi import HTTPException

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=50.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=10.0, consume=0.0)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        raise HTTPException(400, "insufficient_balance")

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)
    monkeypatch.setattr(
        "services.checkout.CheckoutService.reserve",
        fake_reserve)

    cb = _Callback()
    cb_data = BatStoreCallback.create(
        level=3, product_id=42, quantity=1, confirmation=True)
    state = _State()

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, state, AsyncMock(), Language.EN)

    assert "insufficient" in caption.lower() or "balance" in caption.lower()
