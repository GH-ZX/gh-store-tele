import asyncio
import logging
try:
    import httpx
except ImportError:
    httpx = None

import config


class CurrencyRateService:
    _rates = {
        "USD": 1.0,
        "EUR": 0.92,
        "SYP": 392.0,  # 1 USD ≈ 392 SYP (aligned with SAM rate default)
        "XTR": 100.0,  # 1 USD = 100 Telegram Stars
    }

    @classmethod
    async def update_rates(cls) -> None:
        """Fetch live forex rates and update in-memory cache."""
        if not httpx:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://open.er-api.com/v6/latest/USD")
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates", {})
                    if "EUR" in rates:
                        cls._rates["EUR"] = round(float(rates["EUR"]), 4)
                    if "SYP" in rates:
                        cls._rates["SYP"] = round(float(rates["SYP"]), 2)
                    logging.info("Live currency rates updated: EUR=%s, SYP=%s", cls._rates["EUR"], cls._rates["SYP"])
        except Exception as e:
            logging.debug("Forex rate update skipped (using cached): %s", e)

    @classmethod
    def get_rate(cls, currency_code: str) -> float:
        code = (currency_code or "USD").upper()
        return cls._rates.get(code, 1.0)


async def currency_rates_cron():
    """Background task updating exchange rates every 6 hours."""
    while True:
        await asyncio.sleep(21600)  # 6 hours
        await CurrencyRateService.update_rates()
