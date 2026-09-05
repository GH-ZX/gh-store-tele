from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, String, Boolean
from models.base import Base


class PromotionalBanner(Base):
    """Dynamic promotional banners for the storefront."""
    __tablename__ = 'promotional_banners'

    id = Column(Integer, primary_key=True)
    title_ar = Column(String, nullable=False)
    title_en = Column(String, nullable=False)
    subtitle_ar = Column(String, nullable=True)
    subtitle_en = Column(String, nullable=True)
    badge_ar = Column(String, nullable=True)
    badge_en = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    target_category = Column(String, nullable=True)
    product_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=1, nullable=False)

    def __repr__(self):
        return f"PromotionalBanner[{self.id}] {self.title_en}"


class PromotionalBannerDTO(BaseModel):
    id: int | None = None
    title_ar: str
    title_en: str
    subtitle_ar: str | None = None
    subtitle_en: str | None = None
    badge_ar: str | None = None
    badge_en: str | None = None
    image_url: str | None = None
    target_category: str | None = None
    product_id: int | None = None
    is_active: bool = True
    sort_order: int = 1


class PromotionalBannerAdmin(ModelView, model=PromotionalBanner):
    name = "Promotional Banner"
    name_plural = "Promotional Banners"
    icon = "fa-solid fa-bullhorn"
    category = "Storefront"

    column_list = [
        PromotionalBanner.id,
        PromotionalBanner.title_en,
        PromotionalBanner.title_ar,
        PromotionalBanner.badge_en,
        PromotionalBanner.is_active,
        PromotionalBanner.sort_order,
    ]
    column_searchable_list = [PromotionalBanner.title_en, PromotionalBanner.title_ar]
    column_sortable_list = [PromotionalBanner.id, PromotionalBanner.sort_order, PromotionalBanner.is_active]
    form_columns = [
        "title_en", "title_ar", "subtitle_en", "subtitle_ar",
        "badge_en", "badge_ar", "image_url", "target_category",
        "product_id", "is_active", "sort_order"
    ]
