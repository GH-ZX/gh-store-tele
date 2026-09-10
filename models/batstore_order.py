"""Backward-compatibility proxy for models.batstore_order.

Canonical model is now models.order (Order, OrderDTO, OrderAdmin).
"""
from models.order import (
    Order,
    Order as BatStoreOrder,
    OrderDTO,
    OrderDTO as BatStoreOrderDTO,
    OrderAdmin,
    OrderAdmin as BatStoreOrderAdmin,
)

__all__ = [
    "Order",
    "BatStoreOrder",
    "OrderDTO",
    "BatStoreOrderDTO",
    "OrderAdmin",
    "BatStoreOrderAdmin",
]
