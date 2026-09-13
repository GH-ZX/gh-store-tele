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

    @classmethod
    def _headers(cls) -> dict[str, str]:
        key = cls.API_KEY or getattr(config, "FIVESIM_API_KEY", None)
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "GHStore/2.0",
        }

    @classmethod
    async def get_balance(cls) -> dict[str, Any]:
        """Fetch 5sim account profile and balance."""
        url = f"{cls.BASE_URL.rstrip('/')}/user/profile"
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=cls._headers()) as resp:
                    if resp.status == 401:
                        raise FiveSimAPIError("Invalid 5sim API key")
                    data = await resp.json()
                    balance_rub = float(data.get("balance", 0.0))
                    return {
                        "status": "ok",
                        "id": data.get("id"),
                        "email": data.get("email"),
                        "balance_rub": balance_rub,
                        "balance_usd": round(balance_rub * cls.RUB_TO_USD_RATE, 2),
                        "rating": data.get("rating"),
                    }
            except Exception as e:
                logger.error("5sim get_balance failed: %s", e)
                raise FiveSimAPIError(f"5sim connection error: {e}") from e

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
