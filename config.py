import os

from dotenv import load_dotenv

from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment
from utils.utils import get_sslipio_external_url, start_ngrok, hash_password

load_dotenv(".env.bot.dev")
RUNTIME_ENVIRONMENT = RuntimeEnvironment(os.environ.get("RUNTIME_ENVIRONMENT"))
# Explicit public base URL (e.g. your Cloudflare-Tunnel-backed domain). When set,
# it is used as-is; otherwise fall back to ngrok (DEV) or your public IP via
# sslip.io (PROD). Great for a fixed domain served through a tunnel.
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
        WEBHOOK_HOST = start_ngrok()
    else:
        WEBHOOK_HOST = get_sslipio_external_url()
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/")
WEBAPP_HOST = os.environ.get("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT", "5000"))
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
TOKEN = os.environ.get("TOKEN")
ADMIN_ID_LIST = os.environ.get("ADMIN_ID_LIST").split(',')
ADMIN_ID_LIST = [int(admin_id) for admin_id in ADMIN_ID_LIST]
SUPPORT_LINK = os.environ.get("SUPPORT_LINK")
# POSTGRESQL
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASS = os.environ.get("POSTGRES_PASSWORD")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_NAME = os.environ.get("POSTGRES_DB", "ghstore")
PAGE_ENTRIES = int(os.environ.get("PAGE_ENTRIES", "8"))
MULTIBOT = os.environ.get("MULTIBOT", False) == 'true'
CURRENCY = Currency(os.environ.get("CURRENCY", "USD"))
KRYPTO_EXPRESS_API_KEY = os.environ.get("KRYPTO_EXPRESS_API_KEY")
KRYPTO_EXPRESS_API_URL = os.environ.get("KRYPTO_EXPRESS_API_URL")
KRYPTO_EXPRESS_API_SECRET = os.environ.get("KRYPTO_EXPRESS_API_SECRET")
WEBHOOK_SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET_TOKEN")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
TELEGRAM_PROXY_URL = os.environ.get("TELEGRAM_PROXY_URL")
# VARIABLES FOR CRYPTO FORWARDING
CRYPTO_FORWARDING_MODE = os.environ.get("CRYPTO_FORWARDING_MODE", False) == 'true'
BTC_FORWARDING_ADDRESS = os.environ.get("BTC_FORWARDING_ADDRESS")
LTC_FORWARDING_ADDRESS = os.environ.get("LTC_FORWARDING_ADDRESS")
ETH_FORWARDING_ADDRESS = os.environ.get("ETH_FORWARDING_ADDRESS")
SOL_FORWARDING_ADDRESS = os.environ.get("SOL_FORWARDING_ADDRESS")
BNB_FORWARDING_ADDRESS = os.environ.get("BNB_FORWARDING_ADDRESS")
DOGE_FORWARDING_ADDRESS = os.environ.get("DOGE_FORWARDING_ADDRESS")
# VARIABLES FOR THE REFERRAL SYSTEM
MIN_REFERRER_TOTAL_DEPOSIT = int(os.environ.get("MIN_REFERRER_TOTAL_DEPOSIT", "500"))
REFERRAL_BONUS_PERCENT = float(os.environ.get("REFERRAL_BONUS_PERCENT", "5"))
REFERRAL_BONUS_DEPOSIT_LIMIT = int(os.environ.get("REFERRAL_BONUS_DEPOSIT_LIMIT", "3"))
REFERRER_BONUS_PERCENT = float(os.environ.get("REFERRER_BONUS_PERCENT", "3"))
REFERRER_BONUS_DEPOSIT_LIMIT = int(os.environ.get("REFERRER_BONUS_DEPOSIT_LIMIT", "5"))
REFERRAL_BONUS_CAP_PERCENT = float(os.environ.get("REFERRAL_BONUS_CAP_PERCENT", "7"))
REFERRER_BONUS_CAP_PERCENT = float(os.environ.get("REFERRER_BONUS_CAP_PERCENT", "7"))
TOTAL_BONUS_CAP_PERCENT = float(os.environ.get("TOTAL_BONUS_CAP_PERCENT", "12"))
# SQLADMIN
SQLADMIN_RAW_PASSWORD = os.environ.get("SQLADMIN_RAW_PASSWORD")
SQLADMIN_HASHED_PASSWORD = hash_password(SQLADMIN_RAW_PASSWORD)
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
# ADMIN-EDITABLE CONFIG (DB-first via services.config.ConfigService).
# These env values are only fallbacks. Managed from the App Config admin page.
BATSTORE_API_URL = os.environ.get("BATSTORE_API_URL")
BATSTORE_API_KEY = os.environ.get("BATSTORE_API_KEY")
BATSTORE_SYNC_ENABLED = os.environ.get("BATSTORE_SYNC_ENABLED", "true") == 'true'
BATSTORE_WEBHOOK_URL = os.environ.get("BATSTORE_WEBHOOK_URL")
SAM_API_BASE = os.environ.get("SAM_API_BASE")
SAM_API_KEY = os.environ.get("SAM_API_KEY")
SAM_RECEIVING_WALLET = os.environ.get("SAM_RECEIVING_WALLET")
SAM_CURRENCY = os.environ.get("SAM_CURRENCY", "USD")
SAM_SYP_USD_RATE = os.environ.get("SAM_SYP_USD_RATE", "0.002551")
MARGIN_PERCENT = os.environ.get("MARGIN_PERCENT", "0")
MARGIN_FIXED = os.environ.get("MARGIN_FIXED", "0")
DEFAULT_MARGIN_TYPE = os.environ.get("DEFAULT_MARGIN_TYPE", "percent")
GHSTORE_STARS_ENABLED = os.environ.get("GHSTORE_STARS_ENABLED", "false") == 'true'
GHSTORE_STARS_TO_USD = os.environ.get("GHSTORE_STARS_TO_USD", "0.01")

TOPUP_ENABLE_BTC = os.environ.get("TOPUP_ENABLE_BTC", "false") == 'true'
TOPUP_ENABLE_ETH = os.environ.get("TOPUP_ENABLE_ETH", "false") == 'true'
TOPUP_ENABLE_BNB = os.environ.get("TOPUP_ENABLE_BNB", "false") == 'true'
TOPUP_ENABLE_DOGE = os.environ.get("TOPUP_ENABLE_DOGE", "false") == 'true'
TOPUP_ENABLE_LTC = os.environ.get("TOPUP_ENABLE_LTC", "false") == 'true'
TOPUP_ENABLE_SOL = os.environ.get("TOPUP_ENABLE_SOL", "false") == 'true'
TOPUP_ENABLE_USDT = os.environ.get("TOPUP_ENABLE_USDT", "false") == 'true'
TOPUP_ENABLE_USDC = os.environ.get("TOPUP_ENABLE_USDC", "false") == 'true'
TOPUP_ENABLE_SHAMCASH = os.environ.get("TOPUP_ENABLE_SHAMCASH", "false") == 'true'
TOPUP_ENABLE_SYRIATEL = os.environ.get("TOPUP_ENABLE_SYRIATEL", "false") == 'true'
