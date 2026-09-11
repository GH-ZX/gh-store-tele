import re
from typing import Any
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Index, JSON
from sqladmin import ModelView
from starlette.requests import Request

from models.base import Base


# ---- Auto-categorisation keywords (lowercase) ----
# Maps a keyword found in the product name to a category label.
# Order matters: first match wins.
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    # AI & Chatbots
    ("chatgpt", "AI & Chatbots"),
    ("chat gpt", "AI & Chatbots"),
    ("claude", "AI & Chatbots"),
    ("gemini", "AI & Chatbots"),
    ("copilot", "AI & Chatbots"),
    ("grok", "AI & Chatbots"),
    ("kiro", "AI & Chatbots"),
    ("manus", "AI & Chatbots"),
    ("cursor", "AI & Chatbots"),
    ("lovable", "AI & Chatbots"),
    ("lovalbe", "AI & Chatbots"),
    ("magic patterns", "AI & Chatbots"),
    ("factory", "AI & Chatbots"),
    ("api", "AI & Chatbots"),
    ("codex", "AI & Chatbots"),
    ("elevenlabs", "AI & Chatbots"),
    ("wispr", "AI & Chatbots"),
    ("gamma", "AI & Chatbots"),
    # VPN & Security
    ("vpn", "VPN & Security"),
    ("nord", "VPN & Security"),
    ("surfshark", "VPN & Security"),
    ("hma", "VPN & Security"),
    ("proton", "VPN & Security"),
    ("avira", "VPN & Security"),
    # Streaming & Entertainment
    ("netflix", "Streaming & Entertainment"),
    ("hbo max", "Streaming & Entertainment"),
    ("hbomax", "Streaming & Entertainment"),
    ("paramount", "Streaming & Entertainment"),
    ("spotify", "Streaming & Entertainment"),
    ("peacock", "Streaming & Entertainment"),
    ("shahid", "Streaming & Entertainment"),
    ("apple tv", "Streaming & Entertainment"),
    ("amazon prime", "Streaming & Entertainment"),
    ("prime video", "Streaming & Entertainment"),
    # Social Media
    ("snapchat", "Social Media"),
    # Productivity & Collaboration
    ("notion", "Productivity"),
    ("miro", "Productivity"),
    ("linear", "Productivity"),
    ("brain.fm", "Productivity"),
    ("trading view", "Productivity"),
    ("tradingview", "Productivity"),
    # Design & Creative
    ("figma", "Design & Creative"),
    ("framer", "Design & Creative"),
    ("capcut", "Design & Creative"),
    ("canva", "Design & Creative"),
    ("adobe", "Design & Creative"),
    ("autodesk", "Design & Creative"),
    ("envato", "Design & Creative"),
    ("mobbin", "Design & Creative"),
    ("meitu", "Design & Creative"),
    ("supercut", "Design & Creative"),
    ("descript", "Design & Creative"),
    ("wink", "Design & Creative"),
    # Office & Productivity
    ("microsoft office", "Office & Productivity"),
    ("microsoft 365", "Office & Productivity"),
    ("office 365", "Office & Productivity"),
    # Software Licenses & Developer Keys
    ("windows", "Software Keys"),
    ("jetbrains", "Software Keys"),
    ("replit", "Software Keys"),
    ("railway", "Software Keys"),
    ("warp", "Software Keys"),
    # Education & Learning
    ("wordwall", "Education"),
    ("coursera", "Education"),
    ("cousera", "Education"),
    ("edx", "Education"),
    ("duolingo", "Education"),
    ("quillbot", "Education"),
    ("quizlet", "Education"),
    ("amboss", "Education"),
    ("uptodate", "Education"),
    ("scribd", "Education"),
    ("ilovepdf", "Education"),
    # Communication
    ("zoom", "Communication"),
    # Accounts & Email
    ("gmail", "Accounts & Email"),
]


def auto_categorize(name: str) -> str:
    """Return a category label based on keywords in the product name."""
    lower = name.lower()
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in lower:
            return category
    return "Other"


# Mapping keyword -> (fallback_emoji, telegram_custom_emoji_id)
# Keywords checked in order. Matches return specific animated custom emoji ID and fallback unicode emoji.
_PRODUCT_ICON_MAP: list[tuple[str, str, str | None]] = [
    # AI & Chatbots
    ("gemini", "✨", "5465366406979267926"),
    ("claude", "🧠", "5368324170671202286"),
    ("chatgpt", "🤖", "5465366406979267927"),
    ("chat gpt", "🤖", "5465366406979267927"),
    ("gpt", "🤖", "5465366406979267927"),
    ("copilot", "✈️", "5465366406979267928"),
    ("grok", "⚡", "5465366406979267929"),
    ("codex", "💻", "5465366406979267930"),
    ("elevenlabs", "🎙️", "5465366406979267931"),
    ("midjourney", "🎨", "5465366406979267932"),
    ("perplexity", "🔍", "5465366406979267933"),
    # Streaming & Video
    ("netflix", "🎬", "5465366406979267934"),
    ("hbo", "🍿", "5465366406979267936"),
    ("paramount", "⛰️", "5465366406979267934"),
    ("peacock", "🦚", "5465366406979267935"),
    ("shahid", "🍿", "5465366406979267936"),
    ("apple tv", "🍎", "5465366406979267937"),
    ("amazon prime", "📦", "5465366406979267938"),
    ("prime video", "📦", "5465366406979267938"),
    ("disney", "🏰", "5465366406979267939"),
    ("youtube", "▶️", "5465366406979267940"),
    ("crunchyroll", "🍥", "5465366406979267941"),
    # VPN & Privacy
    ("nord", "🛡️", "5465366406979267942"),
    ("surfshark", "🦈", "5465366406979267943"),
    ("expressvpn", "⚡", "5465366406979267944"),
    ("proton", "🔒", "5465366406979267945"),
    ("avira", "🛡️", "5465366406979267942"),
    ("hma", "🫏", "5465366406979267946"),
    ("vpn", "🛡️", "5465366406979267947"),
    # Music & Audio
    ("spotify", "🎵", "5465366406979267948"),
    ("deezer", "🎧", "5465366406979267949"),
    ("tidal", "🌊", "5465366406979267950"),
    ("apple music", "🍎", "5465366406979267951"),
    # Creative & Productivity
    ("canva", "🖌️", "5465366406979267952"),
    ("adobe", "🔴", "5465366406979267953"),
    ("figma", "📐", "5465366406979267954"),
    ("framer", "🖼️", "5465366406979267955"),
    ("notion", "📝", "5465366406979267956"),
    ("miro", "📋", "5465366406979267956"),
    ("linear", "🎯", "5465366406979267956"),
    ("tradingview", "📈", "5465366406979267956"),
    ("trading view", "📈", "5465366406979267956"),
    ("capcut", "✂️", "5465366406979267957"),
    ("github", "🐙", "5465366406979267958"),
    ("telegram", "✈️", "5465366406979267959"),
    ("windows", "🪟", None),
    ("office", "💼", None),
    ("coursera", "🎓", None),
    ("duolingo", "🦉", None),
    ("zoom", "💬", None),
    ("cursor", "⚡", "5465366406979267930"),
    ("lovable", "❤️", "5465366406979267926"),
    ("lovalbe", "❤️", "5465366406979267926"),
]


def auto_detect_icon(name: str) -> tuple[str, str | None]:
    """Detect appropriate fallback emoji and custom_emoji_id from product name."""
    lower = name.lower()
    for kw, fallback_emoji, custom_id in _PRODUCT_ICON_MAP:
        if kw in lower:
            return fallback_emoji, custom_id
    return "⚡", None

def format_product_icon(product, for_button: bool = False) -> str:
    """Format icon: HTML custom animated emoji for text/captions, plain emoji for keyboard buttons."""
    emoji = getattr(product, "emoji", None) or "⚡"
    custom_id = getattr(product, "custom_emoji_id", None)
    if not for_button and custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{emoji}</tg-emoji>'
    return emoji


class MarginType:
    PERCENT = "percent"
    FIXED = "fixed"
    FIXED_PRICE = "fixed_price"


class Product(Base):
    """Universal Digital Product Catalog Model.
    Backed by table 'batstore_products' for seamless DB continuity.
    Supports products across multiple suppliers (BatStore, ProdSeller, etc.).
    """
    __tablename__ = 'batstore_products'
    __table_args__ = (
        Index("idx_batstore_products_hidden_cat", "hidden", "category"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    custom_name = Column(String, nullable=True)  # Admin-overridden clean display name (English/general)
    custom_name_ar = Column(String, nullable=True, default=None)  # Admin-overridden Arabic display name
    custom_group = Column(String, nullable=True, default=None)  # Admin-overridden brand folder / subcategory (English)
    custom_group_ar = Column(String, nullable=True, default=None)  # Admin-overridden brand folder / subcategory (Arabic)
    description = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)
    emoji = Column(String, nullable=True)
    custom_emoji_id = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    cost_usd = Column(Float, nullable=False, default=0.0)
    standard_price_usd = Column(Float, nullable=True)
    delivery_type = Column(String, nullable=True)
    stock = Column(Integer, nullable=True)
    warranty_days = Column(Integer, nullable=True)
    margin_type = Column(String, nullable=True, default=None)
    margin_value = Column(Float, nullable=True, default=None)
    category = Column(String, nullable=True, default=None, index=True)
    sell_price_usd = Column(Float, nullable=False, default=0.0)
    hidden = Column(Boolean, nullable=False, default=False, index=True)
    reseller_key_override = Column(String, nullable=True)
    supplier = Column(String, nullable=False, default="batstore")
    server_badge = Column(String, nullable=True)

    # Reseller-specific pricing
    reseller_price_usd = Column(Float, nullable=True, default=None)
    reseller_margin_pct = Column(Float, nullable=True, default=None)
    extra_meta = Column(JSON, nullable=True, default=None)

    def __repr__(self):
        return f"Product[{self.product_id}] {self.name} (supplier={self.supplier})"


class ProductDTO(BaseModel):
    id: int | None = None
    product_id: int | None = None
    name: str | None = None
    custom_name: str | None = None
    custom_name_ar: str | None = None
    custom_group: str | None = None
    custom_group_ar: str | None = None
    description: str | None = None
    description_ar: str | None = None
    emoji: str | None = None
    custom_emoji_id: str | None = None
    image_url: str | None = None
    cost_usd: float = 0.0
    standard_price_usd: float | None = None
    delivery_type: str | None = None
    stock: int | None = None
    warranty_days: int | None = None
    margin_type: str | None = None
    margin_value: float | None = None
    category: str | None = None
    sell_price_usd: float = 0.0
    hidden: bool = False
    reseller_key_override: str | None = None
    supplier: str = "batstore"
    server_badge: str | None = None

    # Reseller-specific pricing
    reseller_price_usd: float | None = None
    reseller_margin_pct: float | None = None
    extra_meta: dict | list | None = None


class ProductAdmin(ModelView, model=Product):
    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-box"
    category = "Catalog"

    column_list = [
        Product.product_id,
        Product.name,
        Product.custom_name,
        Product.custom_name_ar,
        Product.custom_group,
        Product.custom_group_ar,
        Product.emoji,
        Product.custom_emoji_id,
        Product.category,
        Product.cost_usd,
        Product.sell_price_usd,
        Product.reseller_price_usd,
        Product.margin_type,
        Product.margin_value,
        Product.supplier,
        Product.delivery_type,
        Product.stock,
        Product.hidden
    ]
    column_labels = {
        Product.product_id: "Product ID",
        Product.name: "Raw Name",
        Product.custom_name: "Custom Display Name (EN)",
        Product.custom_name_ar: "Custom Display Name (AR)",
        Product.custom_group: "Folder / Subcategory (EN)",
        Product.custom_group_ar: "Folder / Subcategory (AR)",
        Product.category: "Category",
        Product.cost_usd: "Cost (USD)",
        Product.sell_price_usd: "Sell (USD)",
        Product.reseller_price_usd: "Reseller (USD)",
        Product.reseller_margin_pct: "Reseller Margin %",
        Product.margin_type: "Margin type",
        Product.margin_value: "Margin value",
        Product.delivery_type: "Delivery",
        Product.stock: "Stock",
        Product.hidden: "Hidden",
        Product.supplier: "Supplier",
        Product.reseller_key_override: "Reseller key (override)",
        Product.emoji: "Icon Emoji",
        Product.custom_emoji_id: "Animated Emoji ID",
    }
    column_sortable_list = [
        Product.product_id,
        Product.name,
        Product.cost_usd,
        Product.sell_price_usd,
        Product.reseller_price_usd,
        Product.stock
    ]
    column_default_sort = [(Product.name, True)]
    column_searchable_list = [
        Product.product_id,
        Product.name,
        Product.custom_name,
        Product.custom_group,
        Product.category,
        Product.supplier,
    ]
    column_filters = [
        Product.supplier,
        Product.category,
        Product.hidden,
        Product.delivery_type,
    ]

    form_columns = [
        "name", "custom_name", "category", "cost_usd", "sell_price_usd",
        "reseller_price_usd", "reseller_margin_pct",
        "margin_type", "margin_value", "supplier",
        "hidden", "delivery_type", "stock", "warranty_days", "description", "description_ar"
    ]

    can_delete = False
    can_create = True
    can_edit = True
    can_export = True

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        if "sell_price_usd" in data and data["sell_price_usd"] is not None:
            m_type = data.get("margin_type")
            if not m_type or m_type == MarginType.FIXED_PRICE:
                model.margin_type = MarginType.FIXED_PRICE
                model.margin_value = float(data["sell_price_usd"])


# Backward-compatibility aliases
BatStoreProduct = Product
BatStoreProductDTO = ProductDTO
BatStoreProductAdmin = ProductAdmin
