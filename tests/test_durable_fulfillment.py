from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.order_fulfillment import FulfillmentService, aggregate_status, normalized_details


def make_order(details):
    return SimpleNamespace(id=12, telegram_id=7, total_sell=30, status="pending_fulfillment",
                           details=details, external_order_ref=None)


@pytest.mark.asyncio
async def test_partial_failure_refunds_only_failed_line_once():
    order = make_order([
        {"status": "completed", "sell_usd": 20, "delivery_goods": ["credential"]},
        {"status": "pending_fulfillment", "sell_usd": 10, "supplier": "g2bulk", "external_order_ref": "g2b-vouch-4"},
    ])
    session = SimpleNamespace(flush=AsyncMock())
    with patch("services.order_fulfillment.locked_order", AsyncMock(return_value=order)), \
         patch("services.order_fulfillment.UserRepository.refund_balance", AsyncMock()) as refund:
        _, changed = await FulfillmentService.transition_item(12, 1, "failed", [], session)
        assert changed and order.status == "partially_completed"
        refund.assert_awaited_once_with(7, 10.0, session)
        _, changed = await FulfillmentService.transition_item(12, 1, "failed", [], session)
        assert not changed
        assert refund.await_count == 1
        assert order.details[0]["delivery_goods"] == ["credential"]


@pytest.mark.asyncio
async def test_refund_error_prevents_failed_status_commit():
    order = make_order([{"status": "pending_fulfillment", "sell_usd": 30}])
    session = SimpleNamespace(flush=AsyncMock())
    with patch("services.order_fulfillment.locked_order", AsyncMock(return_value=order)), \
         patch("services.order_fulfillment.UserRepository.refund_balance", AsyncMock(side_effect=RuntimeError("database failure"))):
        with pytest.raises(RuntimeError):
            await FulfillmentService.transition_item(12, 0, "failed", [], session)
    assert order.details[0]["status"] == "pending_fulfillment"
    assert order.status == "pending_fulfillment"


@pytest.mark.asyncio
async def test_delivery_replaces_empty_json_and_preserves_other_lines():
    original = [{"status": "pending_fulfillment", "delivery_goods": []}, {"status": "pending_fulfillment"}]
    order = make_order(original)
    with patch("services.order_fulfillment.locked_order", AsyncMock(return_value=order)):
        await FulfillmentService.transition_item(12, 0, "completed", ["secret"], SimpleNamespace(flush=AsyncMock()))
    assert order.details is not original
    assert original[0]["delivery_goods"] == []
    assert order.details[0]["delivery_goods"] == ["secret"]
    assert order.details[1]["status"] == "pending_fulfillment"
    assert order.status == "pending_fulfillment"


@pytest.mark.asyncio
async def test_supplier_reference_mismatch_cannot_transition():
    order = make_order([{"status": "pending_fulfillment", "supplier": "prodseller", "external_order_ref": "123"}])
    with patch("services.order_fulfillment.locked_order", AsyncMock(return_value=order)):
        _, changed = await FulfillmentService.transition_item(12, 0, "completed", ["wrong"],
            SimpleNamespace(flush=AsyncMock()), supplier="batstore", external_ref="123")
    assert not changed
    assert order.status == "pending_fulfillment"


@pytest.mark.asyncio
async def test_unknown_cart_line_amount_never_refunds_entire_order():
    order = make_order([{"status": "pending_fulfillment"}, {"status": "completed"}])
    with patch("services.order_fulfillment.locked_order", AsyncMock(return_value=order)), \
         patch("services.order_fulfillment.UserRepository.refund_balance", AsyncMock()) as refund:
        await FulfillmentService.transition_item(12, 0, "failed", [], SimpleNamespace(flush=AsyncMock()))
    refund.assert_not_awaited()
    assert order.status == "requires_manual_review"


def test_legacy_numeric_reference_does_not_guess_provider():
    order = make_order([{}])
    order.external_order_ref = "123"
    item = normalized_details(order)[0]
    assert item["external_order_ref"] == "123"
    assert "supplier" not in item
    assert aggregate_status([{"status": "completed"}, {"status": "pending_fulfillment"}]) == "pending_fulfillment"
