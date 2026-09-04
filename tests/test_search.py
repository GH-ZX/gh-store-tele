import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from callbacks import AllCategoriesCallback
from enums.language import Language
from handlers.user.search import execute_search, _build_search_kb
from models.batstore_product import BatStoreProductDTO


class _Msg:
    def __init__(self):
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))


def test_build_search_kb():
    products = [
        BatStoreProductDTO(
            product_id=101,
            name="Claude 3.5 Sonnet",
            sell_price_usd=12.50,
            emoji="🧠",
            category="AI & Chatbots",
        ),
        BatStoreProductDTO(
            product_id=102,
            name="Netflix 4K",
            sell_price_usd=9.00,
            emoji="🎬",
            category="Streaming & Entertainment",
        ),
    ]

    kb = _build_search_kb(products, Language.EN)
    markup = kb.as_markup()
    buttons = [b for row in markup.inline_keyboard for b in row]

    assert len(buttons) == 3  # 2 products + 1 back button
    assert "Claude 3.5 Sonnet" in buttons[0].text
    assert "🧠" in buttons[0].text
    assert "12.50" in buttons[0].text
    assert "Netflix 4K" in buttons[1].text
    assert "🎬" in buttons[1].text


@pytest.mark.asyncio
async def test_execute_search_empty(monkeypatch):
    msg = _Msg()

    async def fake_search(query, session, limit=15):
        return []

    monkeypatch.setattr(
        "handlers.user.search.BatStoreProductRepository.search",
        fake_search
    )

    await execute_search(msg, "nonexistent", None, Language.EN)

    assert len(msg.answers) == 1
    text, _ = msg.answers[0]
    assert "No products found" in text
    assert "nonexistent" in text


@pytest.mark.asyncio
async def test_execute_search_results_found(monkeypatch):
    msg = _Msg()
    products = [
        BatStoreProductDTO(
            product_id=201,
            name="Gemini Advanced",
            sell_price_usd=14.00,
            emoji="✨",
            category="AI & Chatbots",
        )
    ]

    async def fake_search(query, session, limit=15):
        return products

    monkeypatch.setattr(
        "handlers.user.search.BatStoreProductRepository.search",
        fake_search
    )

    await execute_search(msg, "gemini", None, Language.EN)

    assert len(msg.answers) == 1
    text, kb = msg.answers[0]
    assert "Search Results for" in text
    assert "gemini" in text
    assert kb is not None
