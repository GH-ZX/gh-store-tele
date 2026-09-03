import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from services.order_polling import (
    poll_pending_orders,
    _refund_and_notify,
    _notify_order_complete,
)


class TestRefundAndNotify:

    @pytest.mark.asyncio
    async def test_refunds_user_balance(self):
        user = SimpleNamespace(
            telegram_id=123,
            consume_records=10.0,
        )
        order = SimpleNamespace(
            id=1,
            telegram_id=123,
            total_sell=5.5,
            status="failed",
        )

        mock_session = AsyncMock()

        with patch("repositories.user.UserRepository") as MockRepo, \
             patch("services.order_polling.NotificationService") as MockNotif:
            MockRepo.get_by_tgid = AsyncMock(return_value=user)
            MockRepo.update = AsyncMock()
            MockNotif.send_to_user = AsyncMock()

            await _refund_and_notify(order, mock_session)

        assert user.consume_records == pytest.approx(4.5)
        MockRepo.update.assert_awaited_once_with(user, mock_session)
        MockNotif.send_to_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clamps_refund_to_zero(self):
        user = SimpleNamespace(
            telegram_id=456,
            consume_records=2.0,
        )
        order = SimpleNamespace(
            id=2,
            telegram_id=456,
            total_sell=5.5,
            status="failed",
        )
        mock_session = AsyncMock()

        with patch("repositories.user.UserRepository") as MockRepo, \
             patch("services.order_polling.NotificationService") as MockNotif:
            MockRepo.get_by_tgid = AsyncMock(return_value=user)
            MockRepo.update = AsyncMock()
            MockNotif.send_to_user = AsyncMock()

            await _refund_and_notify(order, mock_session)

        assert user.consume_records == 0.0

    @pytest.mark.asyncio
    async def test_handles_missing_user(self):
        order = SimpleNamespace(
            id=3, telegram_id=789, total_sell=5.0, status="failed",
        )
        mock_session = AsyncMock()

        with patch("repositories.user.UserRepository") as MockRepo:
            MockRepo.get_by_tgid = AsyncMock(return_value=None)
            await _refund_and_notify(order, mock_session)


class TestNotifyOrderComplete:

    @pytest.mark.asyncio
    async def test_sends_notification(self):
        order = SimpleNamespace(id=10, telegram_id=123)
        goods = ["user1:pass1", "user2:pass2"]

        with patch("services.order_polling.NotificationService") as MockNotif:
            MockNotif.send_to_user = AsyncMock()
            await _notify_order_complete(order, goods)
            MockNotif.send_to_user.assert_awaited_once()
            call_args = MockNotif.send_to_user.call_args
            assert "user1:pass1" in call_args[0][0]
