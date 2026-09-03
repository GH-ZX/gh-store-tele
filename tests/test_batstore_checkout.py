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
        self.edits = []
    async def edit_text(self, text, reply_markup=None):
        self.edits.append(text)


class _Callback:
    def __init__(self, uid=1):
        self.from_user = SimpleNamespace(id=uid)
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

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, None, None)
    assert "no longer available" in caption.lower() or "not found" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_rejects_insufficient_balance(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=50.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=10.0, consume=0.0)

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, None, None)
    assert "insufficient" in caption.lower() or "balance" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_success_stock_delivery(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0, delivery="stock", stock=5)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0, consume=0.0)

    async def fake_quote(session, pid, qty):
        return {"success": True}

    async def fake_place_order(session, pid, qty, **kwargs):
        return {"success": True, "order": {
            "id": 12345,
            "items": [{"value": "LICENSE-KEY-1234"}]
        }}

    async def fake_update(user, session):
        return user

    async def fake_create(dto, session):
        return dto

    async def fake_commit(session):
        pass

    async def fake_send_to_admins(text, reply_markup):
        pass

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreService.quote", fake_quote)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreService.place_order", fake_place_order)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.update", fake_update)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreOrderRepository.create", fake_create)
    monkeypatch.setattr(
        "services.batstore_store.session_commit", fake_commit)
    monkeypatch.setattr(
        "services.batstore_store.NotificationService.send_to_admins",
        fake_send_to_admins)

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=2, confirmation=True)
    state = _State()

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, state, None, None)
    assert "2" in caption
    assert "20.0" in caption


@pytest.mark.asyncio
async def test_checkout_handles_quote_failure(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback
    from services.batstore import BatStoreAPIError

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0)

    async def fake_quote(session, pid, qty):
        raise BatStoreAPIError("out of stock")

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreService.quote", fake_quote)

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, None, None)
    assert "failed" in caption.lower() or "error" in caption.lower()


@pytest.mark.asyncio
async def test_checkout_handles_place_order_failure(monkeypatch):
    from services.batstore_store import BatStoreStoreService
    from callbacks import BatStoreCallback
    from services.batstore import BatStoreAPIError

    async def fake_get_by_product_id(pid, session):
        return _ProductOrm(sell=10.0)

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=100.0)

    async def fake_quote(session, pid, qty):
        return {"success": True}

    async def fake_place_order(session, pid, qty, **kwargs):
        raise BatStoreAPIError("payment required")

    monkeypatch.setattr(
        "services.batstore_store.BatStoreProductRepository.get_by_product_id",
        fake_get_by_product_id)
    monkeypatch.setattr(
        "services.batstore_store.UserRepository.get_by_tgid",
        fake_get_by_tgid)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreService.quote", fake_quote)
    monkeypatch.setattr(
        "services.batstore_store.BatStoreService.place_order", fake_place_order)

    cb = _Callback()
    cb_data = BatStoreCallback.create(level=3, product_id=42, quantity=1, confirmation=True)

    caption, kb = await BatStoreStoreService.checkout(cb, cb_data, None, None, None)
    assert "failed" in caption.lower() or "error" in caption.lower()
