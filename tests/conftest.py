import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


sys.path = [
    path for path in sys.path
    if "AiogramShopBot\\Lib" not in path and "AiogramShopBot/Lib" not in path
]


def _build_config_module() -> ModuleType:
    config = ModuleType("config")
    currency = SimpleNamespace(
        value="USD",
        get_localized_text=lambda: "USD",
        get_localized_symbol=lambda: "$",
    )
    config.PAGE_ENTRIES = 8
    config.WEBHOOK_URL = "https://example.com/"
    config.KRYPTO_EXPRESS_API_KEY = "test-api-key"
    config.KRYPTO_EXPRESS_API_URL = "https://kryptoexpress.pro/api"
    config.KRYPTO_EXPRESS_API_SECRET = "test-secret"
    config.WEBHOOK_HOST = "https://example.com"
    config.WEBHOOK_PATH = "/"
    config.WEBHOOK_SECRET_TOKEN = "secret"
    config.WEBAPP_HOST = "127.0.0.1"
    config.WEBAPP_PORT = 5000
    config.CRYPTO_FORWARDING_MODE = False
    config.BTC_FORWARDING_ADDRESS = "btc-forward"
    config.LTC_FORWARDING_ADDRESS = "ltc-forward"
    config.DOGE_FORWARDING_ADDRESS = "doge-forward"
    config.ETH_FORWARDING_ADDRESS = "eth-forward"
    config.SOL_FORWARDING_ADDRESS = "sol-forward"
    config.BNB_FORWARDING_ADDRESS = "bnb-forward"
    config.ADMIN_ID_LIST = [1]
    config.TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789"
    config.MULTIBOT = False
    config.TELEGRAM_PROXY_URL = None
    config.REDIS_HOST = "localhost"
    config.REDIS_PASSWORD = "password"
    config.CURRENCY = currency
    config.DB_USER = "postgres"
    config.DB_PASS = "postgres"
    config.DB_HOST = "localhost"
    config.DB_PORT = 5432
    config.DB_NAME = "test"
    config.JWT_EXPIRE_MINUTES = 30
    config.JWT_SECRET_KEY = "secret"
    config.JWT_ALGORITHM = "HS256"
    config.BATSTORE_WEBHOOK_URL = "https://example.com/webhook"
    config.SAM_API_BASE = "https://www.sam-api.pro/api"
    config.SAM_API_KEY = "sk_test"
    config.SAM_RECEIVING_WALLET = "test_wallet"
    config.SAM_CURRENCY = "USD"
    config.SAM_SYP_USD_RATE = "0.002551"
    config.SAM_WEBHOOK_URL = None
    config.get_sam_webhook_url = lambda: "https://example.com/samwebhook"
    config.MARGIN_PERCENT = "0"
    config.MARGIN_FIXED = "0"
    config.DEFAULT_MARGIN_TYPE = "percent"
    config.GHSTORE_STARS_ENABLED = False
    config.GHSTORE_STARS_TO_USD = "0.01"
    config.BATSTORE_API_URL = ""
    config.BATSTORE_API_KEY = ""
    config.BATSTORE_SYNC_ENABLED = False
    config.SQLADMIN_RAW_PASSWORD = "admin"
    config.SQLADMIN_HASHED_PASSWORD = "hashed:admin"
    config.WEBHOOK_SECRET_TOKEN = "test_secret"
    config.TOPUP_ENABLE_BTC = True
    config.TOPUP_ENABLE_USDT = True
    config.TOPUP_ENABLE_ETH = True
    config.TOPUP_ENABLE_BNB = True
    config.TOPUP_ENABLE_DOGE = True
    config.TOPUP_ENABLE_LTC = True
    config.TOPUP_ENABLE_SOL = True
    config.TOPUP_ENABLE_USDC = True
    config.TOPUP_ENABLE_SHAMCASH = False
    config.TOPUP_ENABLE_SYRIATEL = False
    return config


sys.modules.setdefault("config", _build_config_module())

try:
    import sqladmin
except ImportError:
    sqladmin_module = ModuleType("sqladmin")
    sqladmin_module.ModelView = type("ModelView", (), {"__init_subclass__": classmethod(lambda cls, **kwargs: None)})
    sqladmin_module.Admin = type("Admin", (), {"__init__": lambda self, *args, **kwargs: None, "add_model_view": lambda self, *args, **kwargs: None})
    sys.modules.setdefault("sqladmin", sqladmin_module)

jose_module = ModuleType("jose")
jose_module.JWTError = Exception
jose_module.jwt = SimpleNamespace(
    encode=lambda payload, secret, algorithm=None: "token",
    decode=lambda token, secret, algorithms=None: {"sub": "test"},
)
sys.modules.setdefault("jose", jose_module)

passlib_module = ModuleType("passlib")
passlib_context_module = ModuleType("passlib.context")


class _CryptContext:
    def __init__(self, *args, **kwargs):
        pass

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return plain_password == hashed_password

    def hash(self, plain_password: str) -> str:
        return f"hashed:{plain_password}"


passlib_context_module.CryptContext = _CryptContext
passlib_module.context = passlib_context_module
sys.modules.setdefault("passlib", passlib_module)
sys.modules.setdefault("passlib.context", passlib_context_module)

pyngrok_module = ModuleType("pyngrok")
pyngrok_module.ngrok = SimpleNamespace(
    set_auth_token=lambda token: None,
    connect=lambda *args, **kwargs: SimpleNamespace(public_url="https://example.ngrok"),
)
sys.modules.setdefault("pyngrok", pyngrok_module)

try:
    import redis
    import redis.asyncio
except ImportError:
    redis_module = ModuleType("redis")
    redis_asyncio_module = ModuleType("redis.asyncio")

    class _Redis:
        def __init__(self, *args, **kwargs):
            pass
        async def close(self):
            return None

    redis_asyncio_client_module = ModuleType("redis.asyncio.client")
    redis_asyncio_client_module.Redis = _Redis
    redis_asyncio_module.Redis = _Redis
    redis_asyncio_module.client = redis_asyncio_client_module
    redis_module.asyncio = redis_asyncio_module
    sys.modules.setdefault("redis", redis_module)
    sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
    sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
db_module = ModuleType("db")


from contextlib import asynccontextmanager

@asynccontextmanager
async def _noop_session_cm(*args, **kwargs):
    yield None
class _FakeResult:
    def scalars(self):
        return self
    def first(self):
        return None
    def all(self):
        return []
    def scalar(self):
        return 0.0
    def scalar_one(self):
        return 0.0
    def scalar_one_or_none(self):
        return None
async def _noop_async(*args, **kwargs):
    return _FakeResult()
db_module.session_execute = _noop_async
db_module.session_flush = _noop_async
db_module.session_commit = _noop_async
db_module.get_db_session = _noop_session_cm
db_module.create_db_and_tables = _noop_async
db_module.engine = SimpleNamespace()
sys.modules.setdefault("db", db_module)


import pytest

@pytest.fixture(autouse=True)
def _isolate_notification_bot():
    try:
        from services.notification import NotificationService
        old_bot = NotificationService._shared_bot
        NotificationService._shared_bot = None
        yield
        NotificationService._shared_bot = old_bot
    except Exception:
        yield
