import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import get_db_session, session_commit
from repositories.config import AppConfigRepository
from models.app_config import AppConfig

# Known configurable keys: default secret-flag + description.
# DB value overrides environment fallback when present and non-empty.
CONFIG_DEFINITIONS = {
    "BATSTORE_API_KEY": {"secret": True, "desc": "Reseller/product supply API key (VenteBot/BatStore)."},
    "BATSTORE_API_URL": {"secret": False,
                         "desc": "Reseller API base URL. Default: "
                                 "https://ventetelegrambotrailway-production.up.railway.app"},
    "SAM_API_KEY": {"secret": True, "desc": "sam-api.pro wallet/payments API key (sk_...)."},
    "SAM_API_BASE": {"secret": False, "desc": "sam-api.pro base URL. Default: https://www.sam-api.pro/api"},
    "KRYPTO_EXPRESS_API_KEY": {"secret": True, "desc": "KryptoExpress crypto payment API key."},
    "KRYPTO_EXPRESS_API_SECRET": {"secret": True, "desc": "KryptoExpress crypto payment callback secret."},
    "KRYPTO_EXPRESS_API_URL": {"secret": False,
                               "desc": "KryptoExpress API base URL. Default: "
                                       "https://kryptoexpress.pro/api"},
    "MARGIN_PERCENT": {"secret": False, "desc": "Global default margin on top of reseller cost, percent (0-100)."},
    "MARGIN_FIXED": {"secret": False, "desc": "Global default flat USD adder on top of reseller cost."},
    "DEFAULT_MARGIN_TYPE": {"secret": False,
                            "desc": "Default per-product pricing mode: percent | fixed | fixed_price."},
    "BATSTORE_SYNC_ENABLED": {"secret": False,
                              "desc": "Auto-sync the BatStore product catalog on startup (true/false)."},
    "BATSTORE_WEBHOOK_URL": {"secret": False,
                             "desc": "Public URL where VenteBot sends deposit/order webhooks (e.g. https://bot.gh-store.me/ventebot)."},
    "GHSTORE_STARS_ENABLED": {"secret": False, "desc": "Enable Telegram Stars top-up rail (true/false)."},
    "GHSTORE_STARS_TO_USD": {"secret": False,
                             "desc": "USD credited per Telegram Star (default 0.01)."},
    "TOPUP_ENABLE_BTC": {"secret": False, "desc": "Show BTC top-up option (true/false)."},
    "TOPUP_ENABLE_ETH": {"secret": False, "desc": "Show ETH top-up option (true/false)."},
    "TOPUP_ENABLE_BNB": {"secret": False, "desc": "Show BNB top-up option (true/false)."},
    "TOPUP_ENABLE_DOGE": {"secret": False, "desc": "Show DOGE top-up option (true/false)."},
    "TOPUP_ENABLE_LTC": {"secret": False, "desc": "Show LTC top-up option (true/false)."},
    "TOPUP_ENABLE_SOL": {"secret": False, "desc": "Show SOL top-up option (true/false)."},
    "TOPUP_ENABLE_USDT": {"secret": False, "desc": "Show USDT top-up option (true/false)."},
    "TOPUP_ENABLE_USDC": {"secret": False, "desc": "Show USDC top-up option (true/false)."},
    "TOPUP_ENABLE_SHAMCASH": {"secret": False, "desc": "Show ShamCash top-up option (true/false)."},
    "TOPUP_ENABLE_SYRIATEL": {"secret": False, "desc": "Show Syriatel Cash top-up option (true/false)."},
    "SAM_RECEIVING_WALLET": {"secret": True,
                             "desc": "Our sam-api.pro receiving wallet address/phone/identifier for invoices."},
    "SAM_CURRENCY": {"secret": False, "desc": "SAM invoice currency: USD | SYP | EUR."},
    "SAM_SYP_USD_RATE": {"secret": False,
                         "desc": "Optional SYP->USD rate used for SYP-denominated SAM top-ups."},
}


class ConfigService:
    @staticmethod
    async def get(session: AsyncSession | Session,
                  key: str,
                  env_fallback: str | None = None,
                  default: str | None = None) -> str | None:
        """Resolve a config value DB-first, then env fallback, then default.

        Returns None only if nothing is set anywhere for a non-defaulted value.
        """
        row = await AppConfigRepository.get_by_key(key, session)
        if row is not None and row.value not in (None, ""):
            return row.value
        if env_fallback not in (None, ""):
            return env_fallback
        return default

    @staticmethod
    async def get_prefixed(session: AsyncSession | Session, env_prefix: str = "") -> dict[str, str]:
        """Return all DB config values keyed by config key, overlaid on env para."""
        resolved: dict[str, str] = {}
        rows = await AppConfigRepository.get_all(session)
        for row in rows:
            if row.value not in (None, ""):
                resolved[row.key] = row.value
        return resolved

    @staticmethod
    async def seed_defaults(session: AsyncSession | Session, env_prefix: str = "") -> None:
        """Insert any missing config keys into the DB so they appear in the admin panel.

        Existing rows are never overwritten. Values are NOT copied from env here
        (env remain a fallback); keys are seeded with empty values for the admin
        to fill in, keeping the DB authoritative when set.
        """
        existing = {k: v for k, v in [(row.key, row) for row in await AppConfigRepository.get_all(session)]}
        for key, definition in CONFIG_DEFINITIONS.items():
            if key in existing:
                continue
            await AppConfigRepository.create(
                key=key,
                value=None,
                is_secret=definition["secret"],
                description=definition["desc"],
                session=session,
            )
        await session_commit(session)

    @staticmethod
    async def seed_from_env(session: AsyncSession | Session) -> None:
        """Backfill empty DB config values from environment variables.

        Makes every key visible in the admin panel with its current effective
        value. DB values always win afterwards (admin edits persist).
        """
        imported = 0
        for row in await AppConfigRepository.get_all(session):
            if row.value not in (None, ""):
                continue
            env_value = os.getenv(row.key)
            if env_value in (None, ""):
                continue
            row.value = env_value
            session.add(row)
            imported += 1
        if imported:
            await session_commit(session)
        return imported

    @staticmethod
    def fallback_from_env(key: str, default: str | None = None) -> str | None:
        value = os.getenv(key)
        return value if value not in (None, "") else default

    @staticmethod
    async def resolve(key: str, env_fallback: str | None = None, default: str | None = None) -> str | None:
        """Resolve a config value by opening its own DB session.

        Intended for services that do not already hold a session (e.g. crypto API
        calls). DB value takes precedence, then env, then default.
        """
        async with get_db_session() as session:
            return await ConfigService.get(session, key, env_fallback, default)
