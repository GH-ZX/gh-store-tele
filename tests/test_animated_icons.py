import pytest
from models.batstore_product import (
    auto_detect_icon,
    format_product_icon,
    BatStoreProduct,
    BatStoreProductDTO,
)


def test_gemini_detection():
    emoji, custom_id = auto_detect_icon("Google Gemini Pro 1.5 Advanced")
    assert emoji == "✨"
    assert custom_id == "5465366406979267926"


def test_claude_complex_naming():
    # User's exact example: "api 500m xx claude 1d"
    emoji, custom_id = auto_detect_icon("api 500m xx claude 1d")
    assert emoji == "🧠"
    assert custom_id == "5368324170671202286"

    emoji2, custom_id2 = auto_detect_icon("1mo claude opus unlimited")
    assert emoji2 == "🧠"
    assert custom_id2 == "5368324170671202286"


def test_chatgpt_detection():
    emoji, custom_id = auto_detect_icon("ChatGPT Plus 1 Month Private")
    assert emoji == "🤖"
    assert custom_id == "5465366406979267927"


def test_streaming_and_vpn():
    emoji_nf, custom_nf = auto_detect_icon("Netflix Premium 4K UHD 1 Month")
    assert emoji_nf == "🎬"
    assert custom_nf == "5465366406979267934"

    emoji_vpn, custom_vpn = auto_detect_icon("NordVPN 2 Years Dedicated IP")
    assert emoji_vpn == "🛡️"
    assert custom_vpn == "5465366406979267942"


def test_unknown_fallback():
    emoji, custom_id = auto_detect_icon("Random Product Key XYZ")
    assert emoji == "⚡"
    assert custom_id is None


def test_format_product_icon_html_and_button():
    p = BatStoreProductDTO(
        name="Claude 3.5 Sonnet",
        emoji="🧠",
        custom_emoji_id="5368324170671202286",
    )
    # Text / caption rendering: HTML tg-emoji tag
    caption_icon = format_product_icon(p, for_button=False)
    assert '<tg-emoji emoji-id="5368324170671202286">🧠</tg-emoji>' == caption_icon

    # Inline button text: plain unicode emoji (Telegram buttons cannot render tg-emoji)
    btn_icon = format_product_icon(p, for_button=True)
    assert btn_icon == "🧠"
