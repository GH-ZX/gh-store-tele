import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.responses import JSONResponse
from routes.tma_admin import (
    admin_get_users,
    admin_adjust_balance,
    admin_toggle_ban,
    admin_toggle_reseller,
    admin_set_discount,
    admin_send_user_message
)


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
async def test_admin_get_users_success():
    mock_session = AsyncMock()
    req = FakeRequest()

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.telegram_id = 999999
    fake_user.telegram_username = "testuser"
    fake_user.top_up_amount = 50.0
    fake_user.consume_records = 10.0
    fake_user.custom_discount_pct = 5.0
    fake_user.is_banned = False
    fake_user.is_reseller = True
    fake_user.registered_at = None

    mock_exec_result = MagicMock()
    mock_exec_result.scalars.return_value.all.return_value = [fake_user]

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("routes.tma_admin.session_execute", AsyncMock(return_value=mock_exec_result)), \
         patch("routes.tma_admin.UserRepository.get_referrals_qty_by_referrer_id", AsyncMock(return_value=3)):

        res = await admin_get_users(tg_id=12345, request=req, query="", filter="all")
        assert "users" in res
        assert len(res["users"]) == 1
        user_data = res["users"][0]
        assert user_data["telegram_id"] == 999999
        assert user_data["balance"] == 40.0
        assert user_data["is_reseller"] is True
        assert user_data["referrals_count"] == 3


@pytest.mark.asyncio
async def test_admin_adjust_balance_success():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 12345,
        "target_tg_id": 999999,
        "amount": 15.0,
        "action": "add"
    })

    fake_user = MagicMock()
    fake_user.top_up_amount = 20.0
    fake_user.consume_records = 5.0

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("routes.tma_admin.UserRepository.get_by_tgid", AsyncMock(return_value=fake_user)), \
         patch("routes.tma_admin.UserRepository.update", AsyncMock()), \
         patch("routes.tma_admin.session_commit", AsyncMock()), \
         patch("routes.tma_admin.invalidate_admin_stats_cache"):

        res = await admin_adjust_balance(request=req)
        assert res["status"] == "ok"
        assert res["new_balance"] == 30.0
        assert fake_user.top_up_amount == 35.0


@pytest.mark.asyncio
async def test_admin_toggle_ban():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 12345,
        "target_tg_id": 999999
    })

    fake_user = MagicMock()
    fake_user.is_banned = False

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("routes.tma_admin.UserRepository.get_by_tgid", AsyncMock(return_value=fake_user)), \
         patch("routes.tma_admin.UserRepository.update", AsyncMock()), \
         patch("routes.tma_admin.session_commit", AsyncMock()):

        res = await admin_toggle_ban(request=req)
        assert res["status"] == "ok"
        assert res["is_banned"] is True
        assert fake_user.is_banned is True
