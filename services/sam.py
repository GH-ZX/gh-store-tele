import logging

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

class _PersistentClientContext:
    def __init__(self, client: "httpx.AsyncClient"):
        self._client = client

    async def __aenter__(self) -> "httpx.AsyncClient":
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class SamService:
    DEFAULT_BASE = "https://www.sam-api.pro/api"
    _shared_client: "httpx.AsyncClient | None" = None

    @classmethod
    async def _client(cls):
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(timeout=30.0)
        return _PersistentClientContext(cls._shared_client)

    @classmethod
    async def close_client(cls) -> None:
        if cls._shared_client is not None and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None

    @staticmethod
    async def _resolve(session: AsyncSession | Session) -> tuple[str, str | None]:
        """DB-first (admin-editable) base URL + API key, falling back to env."""
        try:
            base = await ConfigService.get(session, "SAM_API_BASE",
                                           env_fallback=config.SAM_API_BASE,
                                           default=SamService.DEFAULT_BASE)
            key = await ConfigService.get(session, "SAM_API_KEY",
                                          env_fallback=config.SAM_API_KEY)
        except Exception as e:
            logging.warning("ConfigService resolution failed, using env fallback: %s", e)
            base = ConfigService.fallback_from_env("SAM_API_BASE", SamService.DEFAULT_BASE)
            key = ConfigService.fallback_from_env("SAM_API_KEY")
        return (base or SamService.DEFAULT_BASE), key
    @staticmethod
    def _headers(key: str | None) -> dict:
        headers = {"Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    # ------------------------------------------------------------------ wallets

    @staticmethod
    async def list_wallets(session: AsyncSession | Session) -> list[dict]:
        """Fetch registered wallets from sam-api.pro /v1/wallets."""
        base, key = await SamService._resolve(session)
        async with await SamService._client() as client:
            try:
                resp = await client.get(f"{base}/v1/wallets", headers=SamService._headers(key))
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logging.warning("Failed to fetch wallets from sam-api: %s", e)
        return []

    @staticmethod
    async def resolve_wallet_identifier(session: AsyncSession | Session,
                                        provider: str,
                                        candidate: str | None = None) -> str:
        """Resolve the valid wallet identifier (32-hex address, UUID, or phone)."""
        prov = "syriatel" if provider in ("syriatel", "syriatelcash") else "shamcash"

        # 1. If candidate is already a 32-hex address or UUID, use it directly
        if candidate and (len(candidate) >= 32 or "-" in candidate):
            return candidate

        # 2. Query sam-api.pro /v1/wallets
        try:
            wallets = await SamService.list_wallets(session)
            for w in wallets:
                if w.get("provider") == prov and w.get("status") == "active":
                    if prov == "shamcash":
                        return w.get("walletAddress") or w.get("id") or w.get("accountNumber")
                    else:
                        return w.get("phone") or w.get("walletAddress") or w.get("id")
            if wallets:
                first = wallets[0]
                if prov == "shamcash":
                    return first.get("walletAddress") or first.get("id") or first.get("accountNumber")
                return first.get("phone") or first.get("walletAddress") or first.get("id")
        except Exception as e:
            logging.warning("Could not auto-resolve wallet identifier: %s", e)

        if candidate:
            return candidate
        fallback = await ConfigService.get(session, "SAM_RECEIVING_WALLET", env_fallback=config.SAM_RECEIVING_WALLET)
        return fallback or "wallet"

    # ------------------------------------------------------------------ invoices

    @staticmethod
    async def create_invoice(session: AsyncSession | Session,
                             method: str,
                             identifier: str | None = None,
                             amount: str | float = 10.0,
                             currency: str = "USD",
                             webhook_url: str | None = None) -> dict:
        base, key = await SamService._resolve(session)
        method_clean = "syriatel" if method in ("syriatel", "syriatelcash") else "shamcash"
        wallet_id = await SamService.resolve_wallet_identifier(session, method_clean, identifier)
        webhook = webhook_url or config.BATSTORE_WEBHOOK_URL
        payload = {
            "method": method_clean,
            "identifier": wallet_id,
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