import logging
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text, Result, CursorResult
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

import config
from models.base import Base

"""
Imports of these models are needed to correctly create tables in the database.
For more information see https://stackoverflow.com/questions/7478403/sqlalchemy-classes-across-files
"""
from models.item import Item
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from models.buy import Buy
from models.buyItem import BuyItem
from models.category import Category
from models.subcategory import Subcategory
from models.deposit import Deposit
from models.button_media import ButtonMedia
from models.payment import Payment
from models.coupon import Coupon
from models.shipping_option import ShippingOption
from models.review import Review
from models.referral import ReferralBonus
from models.app_config import AppConfig
from models.batstore_product import BatStoreProduct
from models.batstore_order import BatStoreOrder
from models.sam_payment import SamPayment
from models.restock_subscription import RestockSubscription
from models.stars_payment import StarsPayment
from models.admin_audit_log import AdminAuditLog
from models.gift_voucher import GiftVoucher
url = f"postgresql+asyncpg://{config.DB_USER}:{config.DB_PASS}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
engine = create_async_engine(
    url,
    echo=False,
    pool_size=20,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
)
session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_db_session() -> AsyncSession | Session:
    session = None
    try:
        async with session_maker() as async_session:
            session = async_session
            yield session
    finally:
        if isinstance(session, AsyncSession):
            await session.close()
        elif isinstance(session, Session):
            session.close()


async def session_execute(stmt, session: AsyncSession | Session) -> Result[Any] | CursorResult[Any]:
    if isinstance(session, AsyncSession):
        query_result = await session.execute(stmt)
        return query_result
    else:
        query_result = session.execute(stmt)
        return query_result


async def session_flush(session: AsyncSession | Session) -> None:
    if isinstance(session, AsyncSession):
        await session.flush()
    else:
        session.flush()


async def session_commit(session: AsyncSession | Session) -> None:
    if isinstance(session, AsyncSession):
        await session.commit()
    else:
        session.commit()


async def check_all_tables_exist(session: AsyncSession | Session, schema: str = "public"):
    for table in Base.metadata.tables.values():
        sql_query = text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table_name
            LIMIT 1;
        """)

        params = {
            "schema": schema,
            "table_name": table.name,
        }

        if isinstance(session, AsyncSession):
            result = await session.execute(sql_query, params)
            if result.scalar() is None:
                return False
        else:
            result = session.execute(sql_query, params)
            if result.scalar() is None:
                return False

    return True


async def create_db_and_tables():
    async with get_db_session() as session:
        if not await check_all_tables_exist(session):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        # Ensure new schema columns exist in existing deployments
        try:
            await session.execute(text("ALTER TABLE batstore_products ADD COLUMN IF NOT EXISTS description_ar TEXT;"))
            await session.execute(text("ALTER TABLE batstore_products ADD COLUMN IF NOT EXISTS custom_name TEXT;"))
            await session.execute(text("ALTER TABLE batstore_products ADD COLUMN IF NOT EXISTS reseller_price_usd FLOAT;"))
            await session.execute(text("ALTER TABLE batstore_products ADD COLUMN IF NOT EXISTS reseller_margin_pct FLOAT;"))
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_discount_pct FLOAT;"))
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_reseller BOOLEAN DEFAULT FALSE;"))
            await session_commit(session)
        except Exception:
            pass

        # Ensure storefront_categories table exists and seed initial data if empty
        try:
            from models.storefront_category import StorefrontCategory, StorefrontCategoryDTO
            from repositories.storefront_category import StorefrontCategoryRepository
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            cats_count = await StorefrontCategoryRepository.count(session)
            if cats_count == 0:
                seed_categories = [
                    {"name": "AI & Chatbots", "name_ar": "🤖 الذكاء الاصطناعي", "name_en": "🤖 AI & Chatbots", "icon": "🤖", "image_url": "/static/img/cat-ai.svg", "preview_ar": "كلود · شات جي بي تي · جيميني · جروك", "preview_en": "Claude · ChatGPT · Gemini · Grok", "sort_order": 1},
                    {"name": "Streaming & Entertainment", "name_ar": "🎬 البث والترفيه", "name_en": "🎬 Streaming & Media", "icon": "🎬", "image_url": "/static/img/cat-streaming.svg", "preview_ar": "نتفلكس · بيكوك · شاهد · أبل تي في", "preview_en": "Netflix · Peacock · Shahid · Apple TV", "sort_order": 2},
                    {"name": "VPN & Security", "name_ar": "🛡️ الحماية والـ VPN", "name_en": "🛡️ VPN & Security", "icon": "🛡️", "image_url": "/static/img/cat-vpn.svg", "preview_ar": "نورد في بي ان · سيرف شارك · بروتون", "preview_en": "NordVPN · Surfshark · Proton VPN", "sort_order": 3},
                    {"name": "Design & Creative", "name_ar": "🎨 التصميم والإبداع", "name_en": "🎨 Design & Creative", "icon": "🎨", "image_url": "/static/img/cat-design.svg", "preview_ar": "كانفا · أدوبي · فيجما · فريمر", "preview_en": "Canva · Adobe · Figma · Framer", "sort_order": 4},
                    {"name": "Productivity", "name_ar": "📝 الإنتاجية والأدوات", "name_en": "📝 Productivity & Tools", "icon": "📝", "image_url": "/static/img/cat-productivity.svg", "preview_ar": "نوشن · كاب كات · أوفيس", "preview_en": "Notion · CapCut · MS Office 365", "sort_order": 5},
                    {"name": "Office & Productivity", "name_ar": "💼 برامج الأوفيس والأعمال", "name_en": "💼 Office & Business", "icon": "💼", "image_url": "/static/img/cat-office.svg", "preview_ar": "مايكروسوفت 365 · إكسيل · وورد", "preview_en": "Microsoft 365 · Word · Excel", "sort_order": 6},
                    {"name": "Accounts & Email", "name_ar": "📧 الحسابات والبريد الإلكتروني", "name_en": "📧 Accounts & Email", "icon": "📧", "image_url": "/static/img/cat-accounts.svg", "preview_ar": "جي ميل قديم · بريد أعمال موثق", "preview_en": "Aged Gmail · Business Mail", "sort_order": 7},
                    {"name": "Education", "name_ar": "🎓 التعليم والمنصات الدراسية", "name_en": "🎓 Education & Learning", "icon": "🎓", "image_url": "/static/img/cat-education.svg", "preview_ar": "كورسيرا · كويزلت · أوتوديسك", "preview_en": "Coursera · Quizlet · Autodesk", "sort_order": 8},
                    {"name": "Communication", "name_ar": "💬 برامج التواصل والمحادثات", "name_en": "💬 Communication", "icon": "💬", "image_url": "/static/img/cat-comms.svg", "preview_ar": "زوم برو · ميرو · مكالمات فيديو", "preview_en": "Zoom Pro · Miro · Team Chats", "sort_order": 9},
                    {"name": "Social Media", "name_ar": "📱 وسائل التواصل الاجتماعي", "name_en": "📱 Social Media", "icon": "📱", "image_url": "/static/img/cat-social.svg", "preview_ar": "سناب شات بلس · قنوات موثقة", "preview_en": "Snapchat+ · Social Boost", "sort_order": 10},
                    {"name": "Software Keys", "name_ar": "🔑 مفاتيح وتراخيص البرامج", "name_en": "🔑 Software Licenses", "icon": "🔑", "image_url": "/static/img/cat-keys.svg", "preview_ar": "ويندوز 10/11 برو · جيت برينز", "preview_en": "Windows 10/11 Pro · JetBrains", "sort_order": 11},
                    {"name": "Other", "name_ar": "📦 منتجات رقمية متنوعة", "name_en": "📦 Digital Subscriptions", "icon": "📦", "image_url": "/static/img/cat-other.svg", "preview_ar": "تراخيص، مفاتيح واشتراكات", "preview_en": "Licenses, activations and keys", "sort_order": 12},
                ]
                for c_data in seed_categories:
                    await StorefrontCategoryRepository.create(StorefrontCategoryDTO(**c_data), session)
                await session_commit(session)
        except Exception as e:
            logging.warning("Storefront category initialization: %s", e)
