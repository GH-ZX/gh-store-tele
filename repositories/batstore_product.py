"""Backward-compatibility proxy for repositories.batstore_product.

Canonical repository is now repositories.product.ProductRepository.
"""
from repositories.product import ProductRepository, BatStoreProductRepository

__all__ = [
    "ProductRepository",
    "BatStoreProductRepository",
]
