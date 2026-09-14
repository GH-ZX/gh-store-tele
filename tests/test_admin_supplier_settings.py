import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.responses import JSONResponse
from routes.tma_admin import (
    admin_get_supplier_details,
    admin_update_supplier_config,
    admin_test_supplier_key,
    admin_sync_all_suppliers
)
from services.config import ConfigService
from services.fivesim import FiveSimService


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
async def test_admin_get_supplier_details_includes_fivesim():
    mock_session = AsyncMock()
    req = FakeRequest(query_params={"refresh": "false"})

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch("routes.tma_admin.session_execute") as mock_exec, \
         patch.object(ConfigService, "get", AsyncMock(side_effect=lambda s, k, **kw: {
             "FIVESIM_API_KEY": "5sim_secret_token_12345",
             "FIVESIM_API_URL": "https://5sim.net/v1",
             "FIVESIM_ENABLED": "true",
             "FIVESIM_RUB_USD_RATE": "0.011",
             "SUPPLIER_ROUTING_STRATEGY": "auto_cheapest",
             "BATSTORE_SYNC_ENABLED": "true",
             "PRODSELLER_SYNC_ENABLED": "true",
             "G2BULK_SYNC_ENABLED": "true",
             "SUPPLIER_AUTO_FAILOVER": "true"
         }.get(k, kw.get("default", "")))), \
         patch.object(FiveSimService, "get_balance", AsyncMock(return_value={
             "balance_rub": 250.0,
             "balance_usd": 2.75,
             "email": "admin@example.com",
             "rating": 98
         })), \
         patch("services.batstore.BatStoreService.get_cached_reseller_balance", AsyncMock(return_value=15.0)), \
         patch("services.prodseller.ProdSellerService.get_cached_balance", AsyncMock(return_value=25.0)), \
         patch("services.g2bulk.G2BulkService.get_cached_balance", AsyncMock(return_value=35.0)), \
         patch("services.sam.SamService.get_cached_wallet_balances", AsyncMock(return_value={"usd": 10.0, "syp": 150000})):

        mock_exec_res = MagicMock()
        mock_exec_res.scalar.return_value = 5
        mock_exec.return_value = mock_exec_res

        data = await admin_get_supplier_details(tg_id=1, request=req)

        assert "fivesim" in data
        assert data["fivesim"]["api_key_configured"] is True
        assert data["fivesim"]["enabled"] is True
        assert data["fivesim"]["balance_rub"] == 250.0
        assert data["fivesim"]["balance_usd"] == 2.75
        assert data["fivesim"]["rub_usd_rate"] == 0.011
        assert "batstore" in data
        assert "prodseller" in data
        assert "g2bulk" in data
        assert data["balances"]["fivesim_usd"] == 2.75
        assert data["balances"]["total_supplier_usd"] == round(15.0 + 25.0 + 35.0 + 2.75 + 10.0, 2)


@pytest.mark.asyncio
async def test_admin_update_supplier_config_persists_fivesim():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 1,
        "fivesim_api_key": "new_fivesim_bearer_token",
        "fivesim_api_url": "https://custom.5sim.net/v1",
        "fivesim_enabled": True,
        "fivesim_rub_usd_rate": 0.0125,
        "routing_strategy": "batstore_primary",
        "auto_failover": True
    })

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch.object(ConfigService, "set", AsyncMock()) as mock_set, \
         patch("routes.tma_admin.session_commit", AsyncMock()):

        res = await admin_update_supplier_config(req)
        assert res["status"] == "ok"
        mock_set.assert_any_await(mock_session, "FIVESIM_API_KEY", "new_fivesim_bearer_token")
        mock_set.assert_any_await(mock_session, "FIVESIM_API_URL", "https://custom.5sim.net/v1")
        mock_set.assert_any_await(mock_session, "FIVESIM_ENABLED", "true")
        mock_set.assert_any_await(mock_session, "FIVESIM_RUB_USD_RATE", "0.0125")
        mock_set.assert_any_await(mock_session, "SUPPLIER_ROUTING_STRATEGY", "batstore_primary")
        mock_set.assert_any_await(mock_session, "SUPPLIER_AUTO_FAILOVER", "true")


@pytest.mark.asyncio
async def test_admin_test_supplier_key_fivesim():
    mock_session = AsyncMock()
    req = FakeRequest(json_data={
        "admin_tg_id": 1,
        "supplier": "5sim",
        "api_key": "test_token_live",
        "api_url": "https://5sim.net/v1"
    })

    with patch("routes.tma_admin.verify_admin", return_value=True), \
         patch("routes.tma_admin.get_db_session", return_value=_SessionContext(mock_session)), \
         patch.object(FiveSimService, "get_balance", AsyncMock(return_value={
             "balance_rub": 300.0,
             "balance_usd": 3.30,
             "email": "test@5sim.net",
             "rating": 99
         })):

        res = await admin_test_supplier_key(req)
        assert res["status"] == "ok"
        assert res["supplier"] == "5sim"
        assert res["balance_rub"] == 300.0
        assert res["balance_usd"] == 3.30
        assert "300.0 RUB" in res["message"]
