"""Backward-compatibility proxy for repositories.batstore_order.

Canonical repository is now repositories.order.OrderRepository.
"""
from repositories.order import OrderRepository, BatStoreOrderRepository

__all__ = [
    "OrderRepository",
    "BatStoreOrderRepository",
]
