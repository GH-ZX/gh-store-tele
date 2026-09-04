import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from callbacks import ResellerManagementCallback
from enums.language import Language
from handlers.admin.reseller_management import (
    reseller_menu,
    reseller_action,
    receive_margin_percent,
)


class _Msg:
    def __init__(self, text="25"):
        self.text = text
        self.caption = None
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_text(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def delete(self):
        pass


class _Callback:
    def __init__(self, data=""):
        self.data = data
        self.from_user = SimpleNamespace(id=999)
        self.message = _Msg()

    async def answer(self, *args, **kwargs):
        pass


class _State:
    def __init__(self, current_state=None):
        self._state = current_state
        self._data = {}

    async def clear(self):
        self._state = None
        self._data = {}

    async def set_state(self, state):
        self._state = state

    async def get_state(self):
        return self._state


@pytest.mark.asyncio
async def test_reseller_menu_renders(monkeypatch):
    cb = _Callback()
    cb_data = ResellerManagementCallback.create(level=0)
    state = _State()

    async def fake_get(session, key, **kwargs):
        return "20"

    monkeypatch.setattr("handlers.admin.reseller_management.ConfigService.get", fake_get)

    await reseller_menu(cb, cb_data, None, state, Language.EN)

    assert len(cb.message.answers) == 1
    text, kb = cb.message.answers[0]
    assert "GH Store Reseller & Margins Dashboard" in text
    assert "20%" in text
    assert kb is not None


@pytest.mark.asyncio
async def test_reseller_action_balance(monkeypatch):
    cb = _Callback()
    cb_data = ResellerManagementCallback.create(level=1, action="balance")
    state = _State()

    async def fake_me(session):
        return {
            "success": True,
            "user": {"username": "ghstore_admin", "tier": "gold"},
            "wallet": {"balance": "142.50"},
        }

    monkeypatch.setattr("handlers.admin.reseller_management.BatStoreService.me", fake_me)

    await reseller_action(cb, cb_data, None, state, Language.EN)

    text, kb = cb.message.answers[0]
    assert "Reseller API Wallet Balance" in text
    assert "ghstore_admin" in text
    assert "$142.50" in text


@pytest.mark.asyncio
async def test_reseller_action_sync(monkeypatch):
    cb = _Callback()
    cb_data = ResellerManagementCallback.create(level=1, action="sync")
    state = _State()

    async def fake_sync(session):
        return 3, 12

    monkeypatch.setattr("handlers.admin.reseller_management.BatStoreService.sync_catalog", fake_sync)

    await reseller_action(cb, cb_data, None, state, Language.EN)

    # First answer is "Syncing...", second is final result
    final_text, _ = cb.message.answers[-1]
    assert "BatStore Catalog Synchronized!" in final_text
    assert "New products created:</b> 3" in final_text
    assert "Existing products updated:</b> 12" in final_text


@pytest.mark.asyncio
async def test_receive_margin_percent_valid(monkeypatch):
    msg = _Msg(text="25%")
    state = _State()
    saved = {}

    async def fake_set(session, key, value):
        saved[key] = value

    async def fake_commit(session):
        pass

    monkeypatch.setattr("handlers.admin.reseller_management.ConfigService.set", fake_set)
    monkeypatch.setattr("handlers.admin.reseller_management.session_commit", fake_commit)

    await receive_margin_percent(msg, None, state, Language.EN)

    assert saved.get("MARGIN_PERCENT") == "25.0"
    assert len(msg.answers) == 1
    assert "Global margin updated to 25%" in msg.answers[0][0]


@pytest.mark.asyncio
async def test_receive_margin_percent_invalid():
    msg = _Msg(text="invalid_number")
    state = _State()

    await receive_margin_percent(msg, None, state, Language.EN)

    assert len(msg.answers) == 1
    assert "Invalid percentage" in msg.answers[0][0]
