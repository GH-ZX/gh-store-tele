from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Boolean, Column, Integer, String, Text

from models.base import Base


class StorefrontFolder(Base):
    """Database model for brand folders / subcategories within storefront categories.

    Managed via SQLAdmin web panel (/admin) and MiniApp Admin Center.
    Allows admins to customize folder keys, English and Arabic titles,
    icons, custom emoji IDs, parent category, sort order, matching keywords,
    and visibility.
    """
    __tablename__ = "storefront_folders"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)  # e.g. "gemini", "chatgpt"
    category = Column(String, nullable=False, index=True)  # Parent category, e.g. "AI & Chatbots"
    title_en = Column(String, nullable=False)
    title_ar = Column(String, nullable=False)
    icon = Column(String, nullable=True, default="📁")
    custom_emoji_id = Column(String, nullable=True)
    sort_order = Column(Integer, default=50, nullable=False)
    hidden = Column(Boolean, default=False, nullable=False)
    matching_keywords = Column(Text, nullable=True)  # Comma-separated regex/keywords for auto-matching products

    def __repr__(self):
        return f"StorefrontFolder[{self.key}]({self.title_en})"


class StorefrontFolderDTO(BaseModel):
    id: int | None = None
    key: str
    category: str
    title_en: str
    title_ar: str
    icon: str | None = "📁"
    custom_emoji_id: str | None = None
    sort_order: int = 50
    hidden: bool = False
    matching_keywords: str | None = None


class StorefrontFolderAdmin(ModelView, model=StorefrontFolder):
    name = "Storefront Folder"
    name_plural = "Storefront Folders"
    icon = "fa-solid fa-folder"
    category = "Catalog"

    column_list = [
        StorefrontFolder.id,
        StorefrontFolder.key,
        StorefrontFolder.category,
        StorefrontFolder.title_en,
        StorefrontFolder.title_ar,
        StorefrontFolder.icon,
        StorefrontFolder.sort_order,
        StorefrontFolder.hidden,
    ]
    column_searchable_list = [
        StorefrontFolder.key,
        StorefrontFolder.category,
        StorefrontFolder.title_en,
        StorefrontFolder.title_ar,
    ]
    column_sortable_list = [
        StorefrontFolder.id,
        StorefrontFolder.sort_order,
        StorefrontFolder.category,
        StorefrontFolder.key,
    ]
    form_columns = [
        "key",
        "category",
        "title_en",
        "title_ar",
        "icon",
        "custom_emoji_id",
        "sort_order",
        "hidden",
        "matching_keywords",
    ]

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
