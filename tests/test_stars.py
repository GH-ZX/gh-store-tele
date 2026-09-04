import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from enums.language import Language


# ---- stubs ----

class _UserOrm:
    def __init__(self, top_up=0.0):
        self.id = 1
        self.top_up_amount = top_up
        self.consume_records = 0.0


class _State:
    def __init__(self, data=None):
        self._data = data or {}
    async def get_data(self):
        return dict(self._data)
    async def update_data(self, **kwargs):
        self._data.update(kwargs)


# ---- Tests ----

def test_stars_rate_default():
    from handlers.user.stars import get_rate
    import config
    original = config.GHSTORE_STARS_TO_USD
    try:
        config.GHSTORE_STARS_TO_USD = "0.01"
        assert get_rate() == 0.01
    finally:
        config.GHSTORE_STARS_TO_USD = original


def test_stars_rate_custom():
    from handlers.user.stars import get_rate
    import config
    original = config.GHSTORE_STARS_TO_USD
    try:
        config.GHSTORE_STARS_TO_USD = "0.05"
        assert get_rate() == 0.05
    finally:
        config.GHSTORE_STARS_TO_USD = original


def test_stars_enabled_toggle():
    from handlers.user.stars import is_enabled
    import config
    original = config.GHSTORE_STARS_ENABLED
    try:
        config.GHSTORE_STARS_ENABLED = True
        assert is_enabled() is True
        config.GHSTORE_STARS_ENABLED = False
        assert is_enabled() is False
    finally:
        config.GHSTORE_STARS_ENABLED = original


@pytest.mark.asyncio
async def test_stars_successful_payment_credits_balance(monkeypatch):
    from handlers.user.stars import stars_successful_payment

    committed = []

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=5.0)

    async def fake_update(user, session):
        return user

    async def fake_commit(session):
        committed.append(True)

    async def fake_send_to_admins(text, reply_markup):
        pass

    monkeypatch.setattr(
        "handlers.user.stars.UserRepository.get_by_tgid", fake_get_by_tgid)
    monkeypatch.setattr(
        "handlers.user.stars.UserRepository.update", fake_update)
    monkeypatch.setattr(
        "handlers.user.stars.session_commit", fake_commit)
    monkeypatch.setattr(
        "handlers.user.stars.NotificationService.send_to_admins",
        fake_send_to_admins)

    sp = SimpleNamespace(
        invoice_payload="stars:1:100:1.00",
        total_amount=100,
    )
    msg = SimpleNamespace(
        successful_payment=sp,
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )

    await stars_successful_payment(msg, None, Language.EN)

    msg.answer.assert_called_once()
    answer_text = msg.answer.call_args[0][0]
    assert "1.0" in answer_text


@pytest.mark.asyncio
async def test_stars_successful_payment_bad_payload(monkeypatch):
    from handlers.user.stars import stars_successful_payment

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(top_up=0.0)

    async def fake_update(user, session):
        return user

    async def fake_commit(session):
        pass

    async def fake_send_to_admins(text, reply_markup):
        pass

    monkeypatch.setattr(
        "handlers.user.stars.UserRepository.get_by_tgid", fake_get_by_tgid)
    monkeypatch.setattr(
        "handlers.user.stars.UserRepository.update", fake_update)
    monkeypatch.setattr(
        "handlers.user.stars.session_commit", fake_commit)
    monkeypatch.setattr(
        "handlers.user.stars.NotificationService.send_to_admins",
        fake_send_to_admins)

    sp = SimpleNamespace(
        invoice_payload="invalid_payload",
        total_amount=500000,
    )
    msg = SimpleNamespace(
        successful_payment=sp,
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )

    await stars_successful_payment(msg, None, Language.EN)

    msg.answer.assert_called_once()
    answer_text = msg.answer.call_args[0][0]
    # Fallback uses total_amount/1000000 * rate (0.01) = 0.005 -> rounded to 0.01
    assert "0.01" in answer_text or "0.00" in answer_text


@pytest.mark.asyncio
async def test_stars_duplicate_payment_is_ignored(monkeypatch):
    from handlers.user.stars import stars_successful_payment

    user = _UserOrm(top_up=10.0)
    updated = []

    async def fake_get_by_tgid(tgid, session):
        return user

    async def fake_update(user_obj, session):
        updated.append(user_obj)

    async def fake_get_by_charge_id(charge_id, session):
        return SimpleNamespace(id=1, telegram_payment_charge_id=charge_id)

    monkeypatch.setattr("handlers.user.stars.UserRepository.get_by_tgid", fake_get_by_tgid)
    monkeypatch.setattr("handlers.user.stars.UserRepository.update", fake_update)
    monkeypatch.setattr("handlers.user.stars.StarsPaymentRepository.get_by_charge_id", fake_get_by_charge_id)

    sp = SimpleNamespace(
        invoice_payload="stars:1:100:1.00",
        total_amount=100,
        telegram_payment_charge_id="ch_dup_123",
        provider_payment_charge_id="prov_123",
    )
    msg = SimpleNamespace(
        successful_payment=sp,
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )

    await stars_successful_payment(msg, None, Language.EN)

    # Should return early without updating balance
    assert len(updated) == 0
    assert user.top_up_amount == 10.0
    msg.answer.assert_not_called()
