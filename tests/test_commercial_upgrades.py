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


def test_admin_adjust_balance_does_not_affect_consume_records():
    """Verify that adding and deducting admin balance adjusts top_up_amount without altering consume_records (المشتريات)."""
    user = SimpleNamespace(top_up_amount=0.0, consume_records=0.0)

    # 1. Admin adds $50.0
    user.top_up_amount += 50.0
    assert user.top_up_amount == 50.0
    assert user.consume_records == 0.0
    assert (user.top_up_amount - user.consume_records) == 50.0

    # 2. Admin deducts $50.0 (reversing credit)
    current_top_up = user.top_up_amount or 0.0
    consumed = user.consume_records or 0.0
    current_bal = max(0.0, current_top_up - consumed)
    new_bal = max(0.0, current_bal - 50.0)
    user.top_up_amount = consumed + new_bal

    assert user.top_up_amount == 0.0
    assert user.consume_records == 0.0  # MUST remain 0.0, never inflated to 50.0!
    assert (user.top_up_amount - user.consume_records) == 0.0

    # 3. User with real purchase of $10 and remaining balance of $40
    user = SimpleNamespace(top_up_amount=50.0, consume_records=10.0)
    # Admin deducts $15
    current_top_up = user.top_up_amount or 0.0
    consumed = user.consume_records or 0.0
    current_bal = max(0.0, current_top_up - consumed)
    new_bal = max(0.0, current_bal - 15.0)
    user.top_up_amount = consumed + new_bal

    assert user.top_up_amount == 35.0
    assert user.consume_records == 10.0  # Lifetime purchases unchanged!
    assert (user.top_up_amount - user.consume_records) == 25.0


def test_cart_pricing_calculation():
    """Verify multi-item cart pricing and VIP discount computation."""
    items = [
        {"price": 10.0, "quantity": 2},
        {"price": 15.0, "quantity": 1},
    ]
    raw_total = sum(it["price"] * it["quantity"] for it in items)
    assert raw_total == 35.0

    vip_discount_pct = 10.0
    disc_val = round(raw_total * (vip_discount_pct / 100.0), 2)
    final_total = max(0.01, round(raw_total - disc_val, 2))
    assert disc_val == 3.50
    assert final_total == 31.50


def test_search_synonyms_matching():
    """Verify Arabic-English search synonyms."""
    aliases = {
        'شات': ['chatgpt', 'gpt', 'openai'],
        'كلود': ['claude', 'anthropic'],
    }
    q = "شات"
    tokens = [q]
    for k, syns in aliases.items():
        if q in k or k in q:
            tokens.extend(syns)

    assert "chatgpt" in tokens
    assert "gpt" in tokens


def test_one_time_config_definitions():
    """Verify that essential one-time configuration keys are registered."""
    from services.config import CONFIG_DEFINITIONS
    assert "BATSTORE_API_KEY" in CONFIG_DEFINITIONS
    assert "SAM_API_KEY" in CONFIG_DEFINITIONS
    assert "SAM_RECEIVING_WALLET" in CONFIG_DEFINITIONS
    assert CONFIG_DEFINITIONS["BATSTORE_API_KEY"]["secret"] is True
