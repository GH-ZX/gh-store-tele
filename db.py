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
                    {"name": "AI & Chatbots", "name_ar": "🤖 الذكاء الاصطناعي", "name_en": "🤖 AI & Chatbots", "icon": "🤖", "image_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&auto=format&fit=crop&q=85", "preview_ar": "كلود · شات جي بي تي · جيميني · جروك", "preview_en": "Claude · ChatGPT · Gemini · Grok", "sort_order": 1},
                    {"name": "Streaming & Entertainment", "name_ar": "🎬 البث والترفيه", "name_en": "🎬 Streaming & Media", "icon": "🎬", "image_url": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&auto=format&fit=crop&q=85", "preview_ar": "نتفلكس · بيكوك · شاهد · أبل تي في", "preview_en": "Netflix · Peacock · Shahid · Apple TV", "sort_order": 2},
                    {"name": "VPN & Security", "name_ar": "🛡️ الحماية والـ VPN", "name_en": "🛡️ VPN & Security", "icon": "🛡️", "image_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&auto=format&fit=crop&q=85", "preview_ar": "نورد في بي ان · سيرف شارك · بروتون", "preview_en": "NordVPN · Surfshark · Proton VPN", "sort_order": 3},
                    {"name": "Design & Creative", "name_ar": "🎨 التصميم والإبداع", "name_en": "🎨 Design & Creative", "icon": "🎨", "image_url": "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?w=800&auto=format&fit=crop&q=85", "preview_ar": "كانفا · أدوبي · فيجما · فريمر", "preview_en": "Canva · Adobe · Figma · Framer", "sort_order": 4},
                    {"name": "Productivity", "name_ar": "📝 الإنتاجية والأدوات", "name_en": "📝 Productivity & Tools", "icon": "📝", "image_url": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=800&auto=format&fit=crop&q=85", "preview_ar": "نوشن · كاب كات · أوفيس", "preview_en": "Notion · CapCut · MS Office 365", "sort_order": 5},
                    {"name": "Office & Productivity", "name_ar": "💼 برامج الأوفيس والأعمال", "name_en": "💼 Office & Business", "icon": "💼", "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=85", "preview_ar": "مايكروسوفت 365 · إكسيل · وورد", "preview_en": "Microsoft 365 · Word · Excel", "sort_order": 6},
                    {"name": "Accounts & Email", "name_ar": "📧 الحسابات والبريد الإلكتروني", "name_en": "📧 Accounts & Email", "icon": "📧", "image_url": "https://images.unsplash.com/photo-1596526131083-e8c633c948d2?w=800&auto=format&fit=crop&q=85", "preview_ar": "جي ميل قديم · بريد أعمال موثق", "preview_en": "Aged Gmail · Business Mail", "sort_order": 7},
                    {"name": "Education", "name_ar": "🎓 التعليم والمنصات الدراسية", "name_en": "🎓 Education & Learning", "icon": "🎓", "image_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop&q=85", "preview_ar": "كورسيرا · كويزلت · أوتوديسك", "preview_en": "Coursera · Quizlet · Autodesk", "sort_order": 8},
                    {"name": "Communication", "name_ar": "💬 برامج التواصل والمحادثات", "name_en": "💬 Communication", "icon": "💬", "image_url": "https://images.unsplash.com/photo-1516251193007-45ef944ab0c6?w=800&auto=format&fit=crop&q=85", "preview_ar": "زوم برو · ميرو · مكالمات فيديو", "preview_en": "Zoom Pro · Miro · Team Chats", "sort_order": 9},
                    {"name": "Social Media", "name_ar": "📱 وسائل التواصل الاجتماعي", "name_en": "📱 Social Media", "icon": "📱", "image_url": "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&auto=format&fit=crop&q=85", "preview_ar": "سناب شات بلس · قنوات موثقة", "preview_en": "Snapchat+ · Social Boost", "sort_order": 10},
                    {"name": "Software Keys", "name_ar": "🔑 مفاتيح وتراخيص البرامج", "name_en": "🔑 Software Licenses", "icon": "🔑", "image_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&auto=format&fit=crop&q=85", "preview_ar": "ويندوز 10/11 برو · جيت برينز", "preview_en": "Windows 10/11 Pro · JetBrains", "sort_order": 11},
                    {"name": "Other", "name_ar": "📦 منتجات رقمية متنوعة", "name_en": "📦 Digital Subscriptions", "icon": "📦", "image_url": "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=800&auto=format&fit=crop&q=85", "preview_ar": "تراخيص، مفاتيح واشتراكات", "preview_en": "Licenses, activations and keys", "sort_order": 12},
                ]
                for c_data in seed_categories:
                    await StorefrontCategoryRepository.create(StorefrontCategoryDTO(**c_data), session)
                await session_commit(session)
        except Exception as e:
            logging.warning("Storefront category initialization: %s", e)
