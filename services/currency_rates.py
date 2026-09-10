import asyncio
import logging
try:
    import httpx
except ImportError:
    httpx = None

import config


class CurrencyRateService:
    _rates: dict[str, float | None] = {
        "USD": 1.0,
        "EUR": 0.92,
        "SYP": None,
        "XTR": 100.0,
    }

    @classmethod
    def set_rate(cls, currency_code: str, rate: float | None) -> None:
        """Dynamically set rate in memory (e.g. when admin sets 133 for SYP)."""
        code = (currency_code or "").upper()
        cls._rates[code] = float(rate) if rate is not None else None

    @staticmethod
    def parse_syp_rate(raw_val) -> float | None:
        """Parse SYP rate configured dynamically by admin in settings.

        Accepts either direct market rate e.g. 133 (1 USD = 133 SYP)
        or fractional rate e.g. 0.0075188 (1 SYP = 0.0075188 USD),
        returning the rate in SYP per 1 USD.
        """
        if not raw_val:
            return None
        try:
            val = float(raw_val)
            if val <= 0:
                return None
            if 0 < val < 1.0:
                return round(1.0 / val, 4)
            return val
        except (ValueError, TypeError):
            return None

    @staticmethod
    def syp_to_usd(syp_amount: float, syp_per_usd: float | None) -> float:
        """Convert SYP amount to USD using dynamic syp_per_usd rate. Fail-fast if unset."""
        if not syp_per_usd or float(syp_per_usd) <= 0:
            raise ValueError("syp_rate_unavailable")
        return round(float(syp_amount) / float(syp_per_usd), 2)

    @staticmethod
    def usd_to_syp(usd_amount: float, syp_per_usd: float | None) -> int:
        """Convert USD amount to SYP using dynamic syp_per_usd rate. Fail-fast if unset."""
        if not syp_per_usd or float(syp_per_usd) <= 0:
            raise ValueError("syp_rate_unavailable")
        return int(round(float(usd_amount) * float(syp_per_usd)))

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
                    logging.info("Live currency rates updated: EUR=%s", cls._rates.get("EUR"))
        except Exception as e:
            logging.debug("Forex rate update skipped (using cached): %s", e)

    @classmethod
    def get_rate(cls, currency_code: str) -> float | None:
        code = (currency_code or "USD").upper()
        if code == "USD":
            return 1.0
        val = cls._rates.get(code)
        if val is not None:
            return val
        if code == "SYP":
            resolved = cls.parse_syp_rate(getattr(config, "SAM_SYP_USD_RATE", None))
            if resolved is not None:
                cls._rates["SYP"] = resolved
            return resolved
        return cls._rates.get(code)


async def currency_rates_cron():
    """Background task updating exchange rates every 6 hours."""
    while True:
        await asyncio.sleep(21600)  # 6 hours
        await CurrencyRateService.update_rates()
