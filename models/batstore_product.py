from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqladmin import ModelView

from models.base import Base


# ---- Auto-categorisation keywords (lowercase) ----
# Maps a keyword found in the product name to a category label.
# Order matters: first match wins.
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("chatgpt", "AI & Chatbots"),
    ("chat gpt", "AI & Chatbots"),
    ("claude", "AI & Chatbots"),
    ("gemini", "AI & Chatbots"),
    ("copilot", "AI & Chatbots"),
    ("grok", "AI & Chatbots"),
    ("kiro", "AI & Chatbots"),
    ("manus", "AI & Chatbots"),
    ("api", "AI & Chatbots"),
    ("codex", "AI & Chatbots"),
    ("elevenlabs", "AI & Chatbots"),
    ("wispr", "AI & Chatbots"),
    ("gamma", "AI & Chatbots"),
    ("vpn", "VPN & Security"),
    ("nord", "VPN & Security"),
    ("surfshark", "VPN & Security"),
    ("hma", "VPN & Security"),
    ("proton", "VPN & Security"),
    ("netflix", "Streaming & Entertainment"),
    ("peacock", "Streaming & Entertainment"),
    ("shahid", "Streaming & Entertainment"),
    ("apple tv", "Streaming & Entertainment"),
    ("amazon prime", "Streaming & Entertainment"),
    ("snapchat", "Social Media"),
    ("notion", "Productivity"),
    ("miro", "Productivity"),
    ("figma", "Design & Creative"),
    ("framer", "Design & Creative"),
    ("capcut", "Design & Creative"),
    ("canva", "Design & Creative"),
    ("adobe", "Design & Creative"),
    ("autodesk", "Design & Creative"),
    ("microsoft office", "Office & Productivity"),
    ("microsoft 365", "Office & Productivity"),
    ("office 365", "Office & Productivity"),
    ("windows", "Software Keys"),
    ("jetbrains", "Software Keys"),
    ("replit", "Software Keys"),
    ("wordwall", "Education"),
    ("coursera", "Education"),
    ("quizlet", "Education"),
    ("amboss", "Education"),
    ("uptodate", "Education"),
    ("scribd", "Education"),
    ("ilovepdf", "Education"),
    ("zoom", "Communication"),
    ("gmail", "Accounts & Email"),
    ("lovalbe", "Other"),
]


def auto_categorize(name: str) -> str:
    """Return a category label based on keywords in the product name."""
    lower = name.lower()
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in lower:
            return category
    return "Other"


class MarginType:
    PERCENT = "percent"
    FIXED = "fixed"
    FIXED_PRICE = "fixed_price"


class BatStoreProduct(Base):
    """A product from the VenteBot/BatStore reseller catalog, synced locally.

    Holds per-product pricing/margin configuration so the shop owner can choose,
    for each product individually or globally, between:
      - percent      : sell = cost * (1 + margin_value/100) + MARGIN_FIXED
      - fixed        : sell = cost + margin_value (flat USD adder)
      - fixed_price  : sell = margin_value (exact fixed selling price)
    hidden=True removes the product from the storefront without losing data.
    """
    __tablename__ = 'batstore_products'

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    cost_usd = Column(Float, nullable=False, default=0.0)
    standard_price_usd = Column(Float, nullable=True)
    delivery_type = Column(String, nullable=True)
    stock = Column(Integer, nullable=True)
    warranty_days = Column(Integer, nullable=True)
    # Per-product margin config. margin_value meaning depends on margin_type.
    # When margin_type or margin_value is unset (None/0), the global margin applies.
    margin_type = Column(String, nullable=True, default=None)
    margin_value = Column(Float, nullable=True, default=None)
    # Category for grouping in the storefront (auto-assigned on sync, admin-editable).
    category = Column(String, nullable=True, default=None, index=True)
    # Computed selling price (persisted for fast display; recomputed on sync).
    sell_price_usd = Column(Float, nullable=False, default=0.0)
    hidden = Column(Boolean, nullable=False, default=False)
    reseller_key_override = Column(String, nullable=True)

    def __repr__(self):
        return f"BatStoreProduct[{self.product_id}] {self.name}"


class BatStoreProductDTO(BaseModel):
    id: int | None = None
    product_id: int | None = None
    name: str | None = None
    description: str | None = None
    emoji: str | None = None
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


class BatStoreProductAdmin(ModelView, model=BatStoreProduct):
    name = "BatStore Product"
    name_plural = "BatStore Products"
    icon = "fa-solid fa-box"
    category = "Catalog"

    column_list = [BatStoreProduct.product_id,
                   BatStoreProduct.name,
                   BatStoreProduct.category,
                   BatStoreProduct.cost_usd,
                   BatStoreProduct.sell_price_usd,
                   BatStoreProduct.margin_type,
                   BatStoreProduct.margin_value,
                   BatStoreProduct.delivery_type,
                   BatStoreProduct.stock,
                   BatStoreProduct.hidden]
    column_labels = {
        BatStoreProduct.product_id: "Product ID",
        BatStoreProduct.name: "Name",
        BatStoreProduct.category: "Category",
        BatStoreProduct.cost_usd: "Cost (USD)",
        BatStoreProduct.sell_price_usd: "Sell (USD)",
        BatStoreProduct.margin_type: "Margin type",
        BatStoreProduct.margin_value: "Margin value",
        BatStoreProduct.delivery_type: "Delivery",
        BatStoreProduct.stock: "Stock",
        BatStoreProduct.hidden: "Hidden",
        BatStoreProduct.reseller_key_override: "Reseller key (override)",
    }
    column_sortable_list = [BatStoreProduct.product_id,
                            BatStoreProduct.name,
                            BatStoreProduct.cost_usd,
                            BatStoreProduct.sell_price_usd,
                            BatStoreProduct.stock]
    column_default_sort = [(BatStoreProduct.name, True)]

    form_columns = ["name", "category", "cost_usd", "sell_price_usd", "margin_type", "margin_value",
                    "hidden", "delivery_type", "stock", "warranty_days", "description"]

    can_delete = False
    can_create = True
    can_edit = True
    can_export = True
