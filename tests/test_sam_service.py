import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


class TestSamServiceCreateInvoice:
    """Test SamService.create_invoice with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_create_invoice_success(self, monkeypatch):
        from services.sam import SamService

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "invoiceId": "inv_123",
            "paymentUrl": "https://sam-api.pro/pay/inv_123",
            "expiresAt": "2026-01-01T00:00:00Z"
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def fake_client():
            return mock_client

        async def fake_resolve(session):
            return ("https://www.sam-api.pro/api", "sk_test_key")

        monkeypatch.setattr("services.sam.SamService._resolve", fake_resolve)
        monkeypatch.setattr("services.sam.SamService._client", fake_client)

        result = await SamService.create_invoice(
            session=None,
            method="shamcash",
            identifier="wallet123",
            amount=25.0,
            currency="USD",
            webhook_url="https://example.com/webhook"
        )

        assert result["invoiceId"] == "inv_123"
        assert result["paymentUrl"] == "https://sam-api.pro/pay/inv_123"

    @pytest.mark.asyncio
    async def test_create_invoice_failure(self, monkeypatch):
        from services.sam import SamService, SamAPIError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "VALIDATION_ERROR"

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def fake_client():
            return mock_client

        async def fake_resolve(session):
            return ("https://www.sam-api.pro/api", "sk_test_key")

        monkeypatch.setattr("services.sam.SamService._resolve", fake_resolve)
        monkeypatch.setattr("services.sam.SamService._client", fake_client)

        with pytest.raises(SamAPIError):
            await SamService.create_invoice(
                session=None,
                method="shamcash",
                identifier="wallet123",
                amount=25.0,
            )


class TestSamServiceGetInvoice:
    @pytest.mark.asyncio
    async def test_get_invoice_success(self, monkeypatch):
        from services.sam import SamService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "invoiceId": "inv_123",
            "status": "paid"
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def fake_client():
            return mock_client

        async def fake_resolve(session):
            return ("https://www.sam-api.pro/api", None)

        monkeypatch.setattr("services.sam.SamService._resolve", fake_resolve)
        monkeypatch.setattr("services.sam.SamService._client", fake_client)

        result = await SamService.get_invoice(None, "inv_123")
        assert result["status"] == "paid"
