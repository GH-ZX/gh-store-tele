"""BatStore checkout logic tested at the service level.

The handler-level tests (all_categories._batstore_checkout) require the full
aiogram import chain which is hard to mock. The actual business logic lives in
services/batstore_store.py BatStoreStoreService.checkout() and is already
thoroughly tested in test_batstore_store_service.py.

These tests verify the checkout flow via the service directly.
"""
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
    def __init__(self, pid=42, name="Test Product", cost=5.0, sell=10.0,
                 delivery="stock", stock=10, hidden=False):
        self.product_id = pid
        self.name = name
        self.cost_usd = cost
        self.sell_price_usd = sell
        self.delivery_type = delivery
        self.stock = stock
        self.hidden = hidden


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


class _Callback:
    def __init__(self, uid=1):
        self.from_user = SimpleNamespace(id=uid)
        self.bot = SimpleNamespace(id=901)
        self.message = _CallbackMsg()


@pytest.mark.asyncio
async def test_checkout_rejects_hidden_product(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(hidden=True)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0)

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=999, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, AsyncMock(), Language.EN)
    assert "no longer available" in caption.lower() or "not found" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_rejects_insufficient_balance(monkeypatch):
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
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, AsyncMock(), Language.EN)
    assert "insufficient" in caption.lower() or "balance" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_success_stock_delivery(monkeypatch):
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
        return {"goods": ["LICENSE-KEY-1234"], "total_paid": 20.0,
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
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=2, confirmation=True)
    state = _State()

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, state, AsyncMock(), Language.EN)
    assert "2" in caption
    assert "20.0" in caption


@pytest.mark.asyncio
async def test_checkout_handles_price_failure(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback
    from fastapi import HTTPException

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        raise HTTPException(400, "price_unavailable")

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
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, AsyncMock(), Language.EN)
    assert "failed" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_handles_fulfillment_interruption(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback
    from unittest.mock import AsyncMock

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0)

    pending_order = SimpleNamespace(id=77)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        return pending_order, True

    async def fake_fulfill(order_id, session):
        raise TimeoutError("upstream accept result unknown")

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

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, AsyncMock(), Language.EN)
    # Unknown upstream outcome must never be reported as a charge failure.
    assert "77" in caption
    assert "failed" not in caption.lower()


@pytest.mark.asyncio
async def test_legacy_handler_checkout_uses_durable_flow(monkeypatch):
    from handlers.user.all_categories import _batstore_checkout
    from callbacks import AllCategoriesCallback

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0, consume=0.0)

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(pid=42, name="Test Product", sell=10.0, delivery="stock", stock=5)

    completed_order = SimpleNamespace(id=99)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        assert body == {"product_id": 42, "quantity": 1}
        assert key.startswith("bot_")
        return completed_order, True

    async def fake_fulfill(order_id, session):
        return completed_order

    def fake_response(order):
        return {"goods": ["KEY-1"], "total_paid": 10.0, "reseller_status": "completed"}

    monkeypatch.setattr(
        "handlers.user.all_categories.UserRepository.get_by_tgid", fake_get_by_tgid)
    monkeypatch.setattr(
        "handlers.user.all_categories.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr("services.checkout.CheckoutService.reserve", fake_reserve)
    monkeypatch.setattr(
        "services.order_fulfillment.FulfillmentService.fulfill_order", fake_fulfill)
    monkeypatch.setattr("services.checkout.CheckoutService.response", fake_response)
    monkeypatch.setattr(
        "handlers.user.all_categories.NotificationService.send_to_admins", AsyncMock())

    cb = _Callback()
    cb_data = AllCategoriesCallback.create(
        level=4, batstore_category_name="cat", batstore_product_id=42,
        quantity=1, confirmation=True)
    state = _State()

    await _batstore_checkout(cb, cb_data, state, AsyncMock(), Language.EN)

    assert cb.message.edits, "handler must edit the confirmation message"
    caption = cb.message.edits[-1]
    assert "KEY-1" in caption
    assert "10.0" in caption


@pytest.mark.asyncio
async def test_legacy_handler_insufficient_balance_is_rolled_back(monkeypatch):
    from handlers.user.all_categories import _batstore_checkout
    from callbacks import AllCategoriesCallback
    from fastapi import HTTPException

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=10.0, consume=0.0)

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(pid=42, name="Test Product", sell=50.0, delivery="stock", stock=5)

    async def fake_reserve(tg_id, body, key, session, **kwargs):
        raise HTTPException(400, "insufficient_balance")

    monkeypatch.setattr(
        "handlers.user.all_categories.UserRepository.get_by_tgid", fake_get_by_tgid)
    monkeypatch.setattr(
        "handlers.user.all_categories.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr("services.checkout.CheckoutService.reserve", fake_reserve)

    cb = _Callback()
    cb_data = AllCategoriesCallback.create(
        level=4, batstore_category_name="cat", batstore_product_id=42,
        quantity=1, confirmation=True)
    state = _State()

    await _batstore_checkout(cb, cb_data, state, AsyncMock(), Language.EN)

    assert cb.message.edits, "handler must edit the confirmation message"
    assert "insufficient" in cb.message.edits[-1].lower()
