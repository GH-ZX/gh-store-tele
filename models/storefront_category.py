from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Boolean, Column, Integer, String, Text

from models.base import Base


class StorefrontCategory(Base):
    """Database model for storefront categories with customizable visuals and metadata.

    Managed via SQLAdmin web panel (/admin), allowing admins to edit images,
    bilingual titles, preview subtitles, sort orders, and visibility.
    """
    __tablename__ = "storefront_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)  # Links to BatStoreProduct.category
    product_category = Column(String, nullable=True)  # Canonical product category this storefront category aggregates
    name_ar = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    image_url = Column(Text, nullable=False)
    icon = Column(String, nullable=True, default="📦")
    preview_ar = Column(Text, nullable=True)
    preview_en = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    hidden = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"StorefrontCategory[{self.name}]"


class StorefrontCategoryDTO(BaseModel):
    id: int | None = None
    name: str
    product_category: str | None = None
    name_ar: str
    name_en: str
    image_url: str
    icon: str = "📦"
    preview_ar: str | None = None
    preview_en: str | None = None
    sort_order: int = 0
    hidden: bool = False


class StorefrontCategoryAdmin(ModelView, model=StorefrontCategory):
    name = "Storefront Category"
    name_plural = "Storefront Categories"
    icon = "fa-solid fa-layer-group"

    column_list = [
        StorefrontCategory.id,
        StorefrontCategory.name,
        StorefrontCategory.product_category,
        StorefrontCategory.name_ar,
        StorefrontCategory.name_en,
        StorefrontCategory.icon,
        StorefrontCategory.sort_order,
        StorefrontCategory.hidden,
    ]
    column_searchable_list = [
        StorefrontCategory.name,
        StorefrontCategory.product_category,
        StorefrontCategory.name_ar,
        StorefrontCategory.name_en,
    ]
    column_sortable_list = [
        StorefrontCategory.id,
        StorefrontCategory.sort_order,
        StorefrontCategory.name,
    ]
    form_columns = [
        "name",
        "product_category",
        "name_ar",
        "name_en",
        "image_url",
        "icon",
        "preview_ar",
        "preview_en",
        "sort_order",
        "hidden",
    ]

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True

async def on_model_change(self, data: dict, model, is_created, request):
        try:
            from sqlalchemy import select, update as sa_update
            from db import get_db_session
            async with get_db_session() as db:
                old_obj = (await db.execute(select(StorefrontCategory).where(StorefrontCategory.id == model.id))).scalar_one_or_none()
                if old_obj is None:
                    return
                new_name = (data.get("name") or old_obj.name or "").strip()
                updates = []
                if new_name and new_name != old_obj.name:
                    updates.append((old_obj.name, new_name))
                new_key = (data.get("product_category") or old_obj.product_category or "").strip()
                if new_key and new_key != old_obj.product_category and new_key != new_name:
                    updates.append((old_obj.product_category or "", new_name))
                for src, dst in updates:
                    if src and src != dst:
                        from models.product import Product
                        await db.execute(sa_update(Product).where(Product.category == src).values(category=dst))
                await db.commit()
        except Exception:
            pass
