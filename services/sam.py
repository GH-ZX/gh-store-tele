try:
    import httpx
except Exception:  # pragma: no cover - httpx optional at import in tests
    httpx = None  # type: ignore

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from services.config import ConfigService


class SamAPIError(Exception):
    """Raised when the sam-api.pro wallet/payments API returns an error."""


class SamService:
    DEFAULT_BASE = "https://www.sam-api.pro/api"

    @staticmethod
    async def _resolve(session: AsyncSession | Session) -> tuple[str, str | None]:
        """DB-first (admin-editable) base URL + API key, falling back to env."""
        try:
            base = await ConfigService.get(session, "SAM_API_BASE",
                                           env_fallback=config.SAM_API_BASE,
                                           default=SamService.DEFAULT_BASE)
            key = await ConfigService.get(session, "SAM_API_KEY",
                                          env_fallback=config.SAM_API_KEY)
        except Exception:
            base = ConfigService.fallback_from_env("SAM_API_BASE", SamService.DEFAULT_BASE)
            key = ConfigService.fallback_from_env("SAM_API_KEY")
        return (base or SamService.DEFAULT_BASE), key

    @staticmethod
    async def _client() -> "httpx.AsyncClient":
        return httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def _headers(key: str | None) -> dict:
        headers = {"Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    # ------------------------------------------------------------------ invoices

    @staticmethod
    async def create_invoice(session: AsyncSession | Session,
                             method: str,
                             identifier: str,
                             amount: str | float,
                             currency: str = "USD",
                             webhook_url: str | None = None) -> dict:
        base, key = await SamService._resolve(session)
        webhook = webhook_url or config.BATSTORE_WEBHOOK_URL
        payload = {
            "method": method,
            "identifier": identifier,
            "amount": str(amount),
            "currency": currency,
            "webhookUrl": webhook,
        }
        async with await SamService._client() as client:
            resp = await client.post(f"{base}/v1/invoices", json=payload,
                                     headers=SamService._headers(key))
        if resp.status_code not in (200, 201):
            raise SamAPIError(f"POST /v1/invoices {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if data.get("invoiceId") is None and data.get("paymentUrl") is None:
            raise SamAPIError(f"POST /v1/invoices invalid response: {resp.text[:300]}")
        return data

    @staticmethod
    async def get_invoice(session: AsyncSession | Session, invoice_id: str) -> dict:
        base, _ = await SamService._resolve(session)
        async with await SamService._client() as client:
            resp = await client.get(f"{base}/pay/{invoice_id}")
        if resp.status_code != 200:
            raise SamAPIError(f"GET /pay/{invoice_id} {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    @staticmethod
    async def verify_invoice(session: AsyncSession | Session,
                             invoice_id: str,
                             transaction_ref: str) -> dict:
        base, key = await SamService._resolve(session)
        async with await SamService._client() as client:
            resp = await client.post(f"{base}/pay/{invoice_id}/verify",
                                     json={"transactionRef": transaction_ref},
                                     headers=SamService._headers(key))
        if resp.status_code not in (200, 201, 202):
            raise SamAPIError(f"POST /pay/{invoice_id}/verify {resp.status_code}: {resp.text[:300]}")
        return resp.json()