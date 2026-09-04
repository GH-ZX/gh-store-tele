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
        StorefrontCategory.name_ar,
        StorefrontCategory.name_en,
        StorefrontCategory.icon,
        StorefrontCategory.sort_order,
        StorefrontCategory.hidden,
    ]
    column_searchable_list = [
        StorefrontCategory.name,
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
