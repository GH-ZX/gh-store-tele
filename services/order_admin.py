"""Administrative order transitions use the same locks as provider events."""
from fastapi import HTTPException
from services.order_fulfillment import FulfillmentService, locked_order, normalized_details, TERMINAL


async def refund_unfulfilled(order_id, session):
    order = await locked_order(order_id, session)
    if order is None:
        raise HTTPException(404, "order_not_found")
    details = normalized_details(order)
    if any(item.get("status") == "submitting" for item in details):
        raise HTTPException(409, "supplier_request_in_progress")
    amount = 0.0
    for index, item in enumerate(details):
        if item.get("status") in TERMINAL:
            continue
        order, changed = await FulfillmentService.transition_item(order_id, index, "refunded", None, session)
        if changed:
            updated = order.details[index]
            if updated.get("refund_applied"):
                amount += float(updated.get("refund_amount") or 0)
    return order, round(amount, 2)


async def administrative_status(order_id, new_status, session):
    if new_status == "refunded":
        return await refund_unfulfilled(order_id, session)
    if new_status not in {"completed", "failed", "cancelled", "requires_manual_review"}:
        raise HTTPException(400, "invalid_order_transition")
    order = await locked_order(order_id, session)
    if order is None:
        raise HTTPException(404, "order_not_found")
    details = normalized_details(order)
    if any(item.get("status") == "submitting" for item in details):
        raise HTTPException(409, "supplier_request_in_progress")
    for index, item in enumerate(details):
        if item.get("status") not in TERMINAL:
            order, _ = await FulfillmentService.transition_item(order_id, index, new_status, None, session)
    return order, 0.0
