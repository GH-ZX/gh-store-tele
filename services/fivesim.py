"""5sim Virtual SMS Number Provider Service.

Integrates with 5sim API (https://5sim.net/docs) for virtual phone number
allocation, incoming SMS verification code polling, and order lifecycle management
(finish, cancel, and ban).
"""
import datetime
import logging
from typing import Any

import aiohttp

import config

import os
import time
from services.config import ConfigService

logger = logging.getLogger(__name__)


class FiveSimAPIError(Exception):
    """Base exception for 5sim API failures."""
    pass


class FiveSimOutOfStockError(FiveSimAPIError):
    """Raised when no numbers are available for the requested service/country."""
    pass


class FiveSimLowBalanceError(FiveSimAPIError):
    """Raised when the 5sim account has insufficient balance."""
    pass


class FiveSimService:
    BASE_URL = getattr(config, "FIVESIM_API_URL", "https://5sim.net/v1") or "https://5sim.net/v1"
    API_KEY = getattr(config, "FIVESIM_API_KEY", None)
    # Default estimated rate: 1 RUB ≈ 0.011 USD (can be overridden via config)
    RUB_TO_USD_RATE = 0.011
    _cached_balance: dict[str, Any] = {"usd": 0.0, "rub": 0.0, "expires_at": 0.0}

    @classmethod
    async def resolve_api_key(cls, session=None) -> str:
        if session is not None:
            try:
                db_key = await ConfigService.get(session, "FIVESIM_API_KEY")
                if db_key and str(db_key).strip():
                    return str(db_key).strip()
            except Exception:
                pass
        env_key = os.environ.get("FIVESIM_API_KEY", "").strip()
        if env_key:
            return env_key
        return str(cls.API_KEY or getattr(config, "FIVESIM_API_KEY", "") or "").strip()

    @classmethod
    async def resolve_base_url(cls, session=None) -> str:
        if session is not None:
            try:
                db_url = await ConfigService.get(session, "FIVESIM_API_URL")
                if db_url and str(db_url).strip():
                    return str(db_url).strip().rstrip("/")
            except Exception:
                pass
        env_url = os.environ.get("FIVESIM_API_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")
        return str(getattr(config, "FIVESIM_API_URL", "https://5sim.net/v1") or "https://5sim.net/v1").strip().rstrip("/")

    @classmethod
    async def resolve_rub_usd_rate(cls, session=None) -> float:
        if session is not None:
            try:
                val = await ConfigService.get(session, "FIVESIM_RUB_USD_RATE")
                if val and float(val) > 0:
                    return float(val)
            except Exception:
                pass
        env_rate = os.environ.get("FIVESIM_RUB_USD_RATE", "")
        if env_rate:
            try:
                return float(env_rate)
            except ValueError:
                pass
        return cls.RUB_TO_USD_RATE

    @classmethod
    async def is_enabled(cls, session=None) -> bool:
        if session is not None:
            try:
                val = await ConfigService.get(session, "FIVESIM_ENABLED", default="true")
                return str(val).lower() in ("true", "1", "yes")
            except Exception:
                pass
        env_en = os.environ.get("FIVESIM_ENABLED", "true")
        return env_en.lower() in ("true", "1", "yes")

    @classmethod
    def _headers(cls, key: str | None = None) -> dict[str, str]:
        token = key or cls.API_KEY or getattr(config, "FIVESIM_API_KEY", None) or ""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "GHStore/2.0",
        }

    @classmethod
    async def get_balance(cls, session=None, custom_key: str | None = None, custom_url: str | None = None) -> dict[str, Any]:
        """Fetch 5sim account profile and balance."""
        key = custom_key if custom_key is not None else await cls.resolve_api_key(session)
        base_url = custom_url if custom_url is not None else await cls.resolve_base_url(session)
        rate = await cls.resolve_rub_usd_rate(session)
        url = f"{base_url.rstrip('/')}/user/profile"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client_session:
            try:
                async with client_session.get(url, headers=cls._headers(key)) as resp:
                    if resp.status == 401:
                        raise FiveSimAPIError("Invalid 5sim API key")
                    if resp.status != 200:
                        txt = await resp.text()
                        raise FiveSimAPIError(f"5sim API returned status {resp.status}: {txt[:100]}")
                    data = await resp.json()
                    balance_rub = float(data.get("balance", 0.0))
                    balance_usd = round(balance_rub * rate, 2)
                    cls._cached_balance = {
                        "usd": balance_usd,
                        "rub": balance_rub,
                        "expires_at": time.time() + 60.0
                    }
                    return {
                        "status": "ok",
                        "id": data.get("id"),
                        "email": data.get("email"),
                        "balance_rub": balance_rub,
                        "balance_usd": balance_usd,
                        "rating": data.get("rating"),
                    }
            except Exception as e:
                logger.error("5sim get_balance failed: %s", e)
                raise FiveSimAPIError(f"5sim connection error: {e}") from e

    @classmethod
    async def get_cached_balance(cls, session=None, force_refresh: bool = False) -> float:
        """Return cached USD balance of 5sim account."""
        now = time.time()
        if not force_refresh and cls._cached_balance["expires_at"] > now:
            return float(cls._cached_balance["usd"])
        try:
            res = await cls.get_balance(session=session)
            return float(res.get("balance_usd") or 0.0)
        except Exception:
            return float(cls._cached_balance.get("usd") or 0.0)

    @classmethod
    async def get_prices(cls, country: str | None = None, service: str | None = None) -> dict[str, Any]:
        """Query live prices and stock levels for services and countries."""
        params = {}
        if country:
            params["country"] = country
        if service:
            params["product"] = service

        url = f"{cls.BASE_URL.rstrip('/')}/guest/prices"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, params=params, headers={"Accept": "application/json"}) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise FiveSimAPIError(f"5sim prices error: {resp.status} - {text}")
                    return await resp.json()
            except Exception as e:
                logger.error("5sim get_prices failed: %s", e)
                raise FiveSimAPIError(f"5sim prices inquiry failed: {e}") from e

    @classmethod
    async def buy_activation(cls, country: str, service: str, operator: str = "any") -> dict[str, Any]:
        """Purchase a virtual number for SMS activation."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/buy/activation/{country}/{operator}/{service}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        import json
                        data = json.loads(text)
                        price_rub = float(data.get("price", 0.0))
                        cost_usd = round(price_rub * cls.RUB_TO_USD_RATE, 2)
                        return {
                            "status": "ok",
                            "activation_id": str(data["id"]),
                            "phone": str(data["phone"]),
                            "operator": data.get("operator", operator),
                            "product": data.get("product", service),
                            "price_rub": price_rub,
                            "cost_usd": cost_usd,
                            "expires": data.get("expires"),
                            "created_at": data.get("created_at"),
                            "raw": data,
                        }
                    if "no free phones" in text.lower():
                        raise FiveSimOutOfStockError(f"No available numbers for {service} in {country}")
                    if "not enough" in text.lower() or "balance" in text.lower():
                        raise FiveSimLowBalanceError("5sim account has insufficient balance")
                    raise FiveSimAPIError(f"5sim purchase rejected ({resp.status}): {text}")
            except (FiveSimOutOfStockError, FiveSimLowBalanceError):
                raise
            except Exception as e:
                logger.error("5sim buy_activation failed: %s", e)
                raise FiveSimAPIError(f"5sim order placement error: {e}") from e

    @classmethod
    async def check_order(cls, activation_id: str | int) -> dict[str, Any]:
        """Poll the current state of an allocated number and any received SMS."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/check/{activation_id}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise FiveSimAPIError(f"5sim check error ({resp.status}): {text}")
                    data = await resp.json()
                    status = (data.get("status") or "PENDING").upper()
                    sms_list = data.get("sms") or []
                    latest_code = None
                    latest_text = None
                    if sms_list:
                        latest = sms_list[-1]
                        latest_code = latest.get("code")
                        latest_text = latest.get("text")

                    return {
                        "status": status,  # PENDING, RECEIVED, CANCELED, TIMEOUT, FINISHED, BANNED
                        "phone": data.get("phone"),
                        "sms_code": latest_code,
                        "sms_text": latest_text,
                        "sms_list": sms_list,
                        "expires": data.get("expires"),
                        "raw": data,
                    }
            except Exception as e:
                logger.error("5sim check_order %s failed: %s", activation_id, e)
                raise FiveSimAPIError(f"Failed to check 5sim order: {e}") from e

    @classmethod
    async def finish_order(cls, activation_id: str | int) -> dict[str, Any]:
        """Mark an activation completed upstream."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/finish/{activation_id}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    text = await resp.text()
                    return {"status": "ok" if resp.status == 200 else "error", "response": text}
            except Exception as e:
                logger.error("5sim finish_order %s failed: %s", activation_id, e)
                return {"status": "error", "error": str(e)}

    @classmethod
    async def cancel_order(cls, activation_id: str | int) -> dict[str, Any]:
        """Cancel an order before SMS arrival and refund 5sim balance."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/cancel/{activation_id}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    text = await resp.text()
                    return {"status": "ok" if resp.status == 200 else "error", "response": text}
            except Exception as e:
                logger.error("5sim cancel_order %s failed: %s", activation_id, e)
                return {"status": "error", "error": str(e)}

    @classmethod
    async def ban_order(cls, activation_id: str | int) -> dict[str, Any]:
        """Report a number as already used / banned and release it."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/ban/{activation_id}"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    text = await resp.text()
                    return {"status": "ok" if resp.status == 200 else "error", "response": text}
            except Exception as e:
                logger.error("5sim ban_order %s failed: %s", activation_id, e)
                return {"status": "error", "error": str(e)}
