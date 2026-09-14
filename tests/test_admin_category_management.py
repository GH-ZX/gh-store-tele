import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.responses import JSONResponse
from routes.tma_admin import (
    admin_create_category,
    admin_update_category
)
from models.storefront_category import StorefrontCategory, StorefrontCategoryDTO


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeRequest:
    def __init__(self, json_data=None, query_params=None, headers=None):
        self._json = json_data or {}
        self.query_params = query_params or {}
        self.headers = headers or {}

    async def json(self):
        return self._json


@pytest.mark.asyncio
async def test_admin_create_category_success():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 123456,
        "name_en": "Developer Tools",
        "name_ar": "أدوات المطورين",
        "product_category": "Dev Tools",
        "icon": "💻",
        "image_url": "/static/img/dev.svg",
        "preview_ar": "أدوات برمجية واشتراكات",
        "preview_en": "Coding tools & subscriptions",
        "sort_order": 10,
        "hidden": False
    })

    created_cat = MagicMock()
    created_cat.id = 99
    created_cat.name = "Developer Tools"

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("repositories.storefront_category.StorefrontCategoryRepository.get_by_name", AsyncMock(return_value=None)), \
         patch("repositories.storefront_category.StorefrontCategoryRepository.create", AsyncMock(return_value=created_cat)), \
         patch("routes.tma_admin.session_commit", AsyncMock()), \
         patch("routes.tma_admin.invalidate_catalog_cache") as mock_inv:

        res = await admin_create_category(req)
        assert isinstance(res, dict)
        assert res["status"] == "ok"
        assert res["category_id"] == 99
        mock_inv.assert_called_once()


@pytest.mark.asyncio
async def test_admin_create_category_duplicate_rejected():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 123456,
        "name_en": "Existing Category",
        "name_ar": "تصنيف موجود"
    })

    existing_cat = MagicMock()
    existing_cat.id = 55
    existing_cat.name = "Existing Category"

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("repositories.storefront_category.StorefrontCategoryRepository.get_by_name", AsyncMock(return_value=existing_cat)):

        res = await admin_create_category(req)
        assert isinstance(res, JSONResponse)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_update_category_redirects_to_create_when_no_id():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 123456,
        "category_id": 0,
        "name_en": "Brand New Category",
        "name_ar": "تصنيف جديد كلياً"
    })

    created_cat = MagicMock()
    created_cat.id = 105
    created_cat.name = "Brand New Category"

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("repositories.storefront_category.StorefrontCategoryRepository.get_by_name", AsyncMock(return_value=None)), \
         patch("repositories.storefront_category.StorefrontCategoryRepository.create", AsyncMock(return_value=created_cat)), \
         patch("routes.tma_admin.session_commit", AsyncMock()), \
         patch("routes.tma_admin.invalidate_catalog_cache"):

        res = await admin_update_category(req)
        assert isinstance(res, dict)
        assert res["status"] == "ok"
        assert res["category_id"] == 105
