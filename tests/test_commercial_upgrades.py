import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.user import get_vip_tier_info, format_currency_display
from services.batstore import BatStoreService


def test_vip_tiers():
    tier, disc = get_vip_tier_info(0.0)
    assert tier == "Standard"
    assert disc == 0.0

    tier, disc = get_vip_tier_info(150.0)
    assert "Silver" in tier
    assert disc == 3.0

    tier, disc = get_vip_tier_info(600.0)
    assert "Gold" in tier
    assert disc == 7.0

    tier, disc = get_vip_tier_info(1200.0)
    assert "Platinum" in tier
    assert disc == 10.0


def test_currency_formatting():
    assert format_currency_display(10.0, "USD") == "$10.00"
    eur = format_currency_display(10.0, "EUR")
    assert "€" in eur
    syp = format_currency_display(10.0, "SYP")
    assert "ل.س" in syp
    xtr = format_currency_display(10.0, "XTR")
    assert "⭐" in xtr


def test_tiered_margin_curve():
    # Cheap goods (<=$10) get higher margin (+40%)
    m1 = BatStoreService.compute_tiered_margin(5.0)
    assert m1 == 40.0

    # Mid goods ($10 - $50) get +25%
    m2 = BatStoreService.compute_tiered_margin(25.0)
    assert m2 == 25.0

    # High-ticket goods (>$50) get +15%
    m3 = BatStoreService.compute_tiered_margin(100.0)
    assert m3 == 15.0


@pytest.mark.asyncio
async def test_tma_catalog_api(monkeypatch):
    from bot import get_tma_catalog
    from models.batstore_product import BatStoreProductDTO

    products = [
        BatStoreProductDTO(
            product_id=1,
            name="ChatGPT 4o",
            category="AI & Chatbots",
            sell_price_usd=20.0,
            emoji="🤖",
        )
    ]

    async def fake_cats(session):
        return ["AI & Chatbots"]

    async def fake_visible(session):
        return products

    monkeypatch.setattr("repositories.batstore_product.BatStoreProductRepository.get_categories", fake_cats)
    monkeypatch.setattr("repositories.batstore_product.BatStoreProductRepository.get_visible", fake_visible)

    catalog = await get_tma_catalog()
    assert "categories" in catalog
    assert "products" in catalog
    assert len(catalog["products"]) == 1
    assert catalog["products"][0]["name"] == "ChatGPT 4o"
    assert catalog["products"][0]["price"] == 20.0
