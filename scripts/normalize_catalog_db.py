"""Script to standardize product categories, clean custom names, and reorder storefront categories in DB."""
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, update

from db import get_db_session, session_commit, session_execute
from models.product import Product, auto_categorize, auto_detect_icon
from models.storefront_category import StorefrontCategory
from services.product_spec import ProductSpecParser

logging.basicConfig(level=logging.INFO)

CATEGORY_SORT_ORDERS = {
    "AI & Chatbots": 1,
    "Streaming & Entertainment": 2,
    "Design & Creative": 3,
    "Office & Productivity": 4,
    "Software Keys": 5,
    "VPN & Security": 6,
    "Productivity": 7,
    "Education": 8,
    "Communication": 9,
    "Social Media": 10,
    "Accounts & Email": 11,
    "Other": 12,
}

# Explicit high-quality custom names for key services to guarantee perfect variant differentiation
CUSTOM_NAME_OVERRIDES = {
    # Gemini
    16: "Gemini Advanced + 5TB Cloud (18M)",
    2082123: "Gemini Pro 18M (رابط تفعيل)",
    162: "Gemini Pro + 5TB Cloud (1Y)",
    # CapCut
    2667681: "CapCut Pro · 7 Days",
    97: "CapCut Pro · 7 Days",
    18: "CapCut Pro · 1 Month",
    2839953: "CapCut Pro · 1 Month",
    26: "CapCut Pro · 6 Months",
    2739617: "CapCut Pro · 6 Months",
    # ChatGPT
    56: "ChatGPT Plus · 1M (Apple Pay)",
    89: "ChatGPT Plus · 1M (MoMo)",
    95: "ChatGPT Plus · 1M (GoPay)",
    # Netflix
    41: "Netflix Premium 4K · 1M (5 Profiles)",
    2080947: "Netflix Premium 4K · 1M (Private)",
    # Windows
    98: "Windows 10 Pro · Lifetime Retail Key",
    87: "Windows 11 Pro · Lifetime Retail Key",
    # Office
    147: "Microsoft 365 Family · 1 Year (Invite)",
    35: "Microsoft Office 365 Plus · 1 Year",
    2353804: "Microsoft Office 365 Plus · 1 Year",
    # Miro
    126: "Miro Edu · Lifetime Activation Link",
    2687452: "Miro Edu · Lifetime Activation Link",
    151: "Miro Edu Panel · 100 Members",
    2798925: "Miro Edu Panel · 100 Invites",
    # Canva
    29: "Canva Pro Edu · 5M Warranty",
    2085660: "Canva Pro Admin · 500 Invites",
    # Autodesk
    51: "Autodesk Education · 1 Year",
    2687248: "Autodesk Education · 1 Year",
    150: "Autodesk Admin · 3000 Invites",
    2711066: "Autodesk Admin · 3000 Invites",
    # Zoom
    129: "Zoom Pro · 1 Month",
    130: "Zoom Pro · 3 Months",
    132: "Zoom Pro · 6 Months",
    131: "Zoom Pro · 12 Months",
}


async def main():
    async with get_db_session() as session:
        # 1. Normalize Category Sort Orders
        logging.info("Updating storefront category sort orders...")
        cats = (await session_execute(select(StorefrontCategory), session)).scalars().all()
        for c in cats:
            if c.name in CATEGORY_SORT_ORDERS:
                c.sort_order = CATEGORY_SORT_ORDERS[c.name]
        await session_commit(session)

        # 2. Re-categorize Products
        logging.info("Re-categorizing products in batstore_products...")
        prods = (await session_execute(select(Product), session)).scalars().all()
        recat_count = 0
        override_count = 0

        for p in prods:
            new_cat = auto_categorize(p.name)
            if p.category != new_cat:
                logging.info("Re-categorizing [%s] %s: %s -> %s", p.product_id, p.name, p.category, new_cat)
                p.category = new_cat
                recat_count += 1

            if p.product_id in CUSTOM_NAME_OVERRIDES:
                p.custom_name = CUSTOM_NAME_OVERRIDES[p.product_id]
                override_count += 1

            # Auto-detect icon if missing
            if not p.emoji or p.emoji == "⚡":
                icon, emoji_id = auto_detect_icon(p.name)
                if icon and icon != "⚡":
                    p.emoji = icon
                if emoji_id and not p.custom_emoji_id:
                    p.custom_emoji_id = emoji_id

        await session_commit(session)
        logging.info("Finished: %d products re-categorized, %d custom names standardized.", recat_count, override_count)


if __name__ == "__main__":
    asyncio.run(main())
