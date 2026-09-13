import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from services.order_polling import (
    poll_one_order,
    _notify_order_complete,
)


class TestPollOneOrder:
    """The durable polling loop: resume unsubmitted items, escalate stale
    submitting claims, and reconcile pending supplier attempts via
    FulfillmentService (which owns atomic refunds)."""

    @pytest.mark.asyncio
    async def test_supplier_failure_is_refunded_through_transition(self):
        order = SimpleNamespace(
            id=5,
            telegram_id=9,
            total_sell=6.0,
            status="pending_fulfillment",
            external_order_ref="111",
            details=[{
                "status": "pending_fulfillment",
                "supplier": "batstore",
                "external_order_ref": "111",
                "sell_usd": 6.0,
            }],
        )
        mock_session = AsyncMock()

        with patch("services.order_fulfillment.locked_order", new=AsyncMock(return_value=order)), \
             patch("services.order_fulfillment.FulfillmentService.supplier_status",
                   new=AsyncMock(return_value=("failed", []))), \
             patch("services.order_fulfillment.UserRepository.refund_balance",
                   new_callable=AsyncMock) as refund, \
             patch("services.order_polling._notify_order_complete", new=AsyncMock()) as notify:
            await poll_one_order(5, mock_session)

        refund.assert_awaited_once_with(9, 6.0, mock_session)
        assert order.details[0]["status"] == "failed"
        assert order.details[0]["refund_applied"] is True
        assert order.details[0]["refund_amount"] == 6.0
        notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_submitting_item_flagged_manual_review(self):
        order = SimpleNamespace(
            id=3,
            telegram_id=12,
            total_sell=4.0,
            status="pending_fulfillment",
            external_order_ref=None,
            details=[{"status": "submitting", "submitted_at": "2020-01-01T00:00:00+00:00"}],
        )
        mock_session = AsyncMock()

        with patch("services.order_fulfillment.locked_order", new=AsyncMock(return_value=order)), \
             patch("services.order_fulfillment.FulfillmentService.transition_item",
                   new=AsyncMock(return_value=(order, True))) as trans:
            await poll_one_order(3, mock_session)

        trans.assert_awaited_once_with(3, 0, "requires_manual_review", None, mock_session)

    @pytest.mark.asyncio
    async def test_created_item_resumes_fulfillment(self):
        order = SimpleNamespace(
            id=7,
            telegram_id=21,
            total_sell=3.0,
            status="pending_fulfillment",
            external_order_ref=None,
            details=[{"status": "created"}],
        )
        mock_session = AsyncMock()

        with patch("services.order_fulfillment.locked_order", new=AsyncMock(return_value=order)), \
             patch("services.order_fulfillment.FulfillmentService.fulfill_order",
                   new=AsyncMock(return_value=order)) as fulfill:
            await poll_one_order(7, mock_session)

        fulfill.assert_awaited_once_with(7, mock_session)


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


class TestCheckResellerBalance:

    @pytest.mark.asyncio
    async def test_alerts_once_below_5_and_resets_on_topup(self):
        import services.order_polling as op
        op._low_balance_alerted = False
        mock_session = AsyncMock()

        with patch("services.order_polling.BatStoreService.me") as mock_me, \
             patch("services.prodseller.ProdSellerService.get_balance", new_callable=AsyncMock, return_value={"balance": 100.0}), \
             patch("services.g2bulk.G2BulkService.get_balance", new_callable=AsyncMock, return_value={"balance": 100.0}), \
             patch("services.order_polling.NotificationService.send_error_to_admins") as mock_alert:
            # 1. Balance is 0.08 (BatStore API key wallet_balance)
            mock_me.return_value = {"success": True, "wallet_balance": 0.08}
            bal1 = await op.check_reseller_balance(mock_session)
            assert bal1 == 0.08
            assert mock_alert.await_count == 1
            args = mock_alert.call_args[0]
            assert "$0.08" in args[1]
            assert "$5.00" in args[1]

            # 2. Second check still below $5.00 -> should NOT alert again
            bal2 = await op.check_reseller_balance(mock_session)
            assert bal2 == 0.08
            assert mock_alert.await_count == 1  # Still 1, not spammed!

            # 3. Top up to $15.00 -> resets trigger
            mock_me.return_value = {"success": True, "wallet_balance": 15.00}
            bal3 = await op.check_reseller_balance(mock_session)
            assert bal3 == 15.00
            assert mock_alert.await_count == 1
            assert op._low_balance_alerted is False

            # 4. Drops below $5.00 again -> alerts once more
            mock_me.return_value = {"success": True, "wallet_balance": 2.50}
            bal4 = await op.check_reseller_balance(mock_session)
            assert bal4 == 2.50
            assert mock_alert.await_count == 2
            assert "$2.50" in mock_alert.call_args[0][1]
