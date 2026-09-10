"""Backward-compatibility proxy for models.batstore_product.

Canonical model is now models.product (Product, ProductDTO, ProductAdmin).
This module re-exports all identifiers so legacy callers and migrations do not break.
"""
from models.product import (
    auto_categorize,
    auto_detect_icon,
    format_product_icon,
    MarginType,
    Product,
    Product as BatStoreProduct,
    ProductDTO,
    ProductDTO as BatStoreProductDTO,
    ProductAdmin,
    ProductAdmin as BatStoreProductAdmin,
    _CATEGORY_KEYWORDS,
    _PRODUCT_ICON_MAP,
)

__all__ = [
    "auto_categorize",
    "auto_detect_icon",
    "format_product_icon",
    "MarginType",
    "Product",
    "BatStoreProduct",
    "ProductDTO",
    "BatStoreProductDTO",
    "ProductAdmin",
    "BatStoreProductAdmin",
    "_CATEGORY_KEYWORDS",
    "_PRODUCT_ICON_MAP",
]
