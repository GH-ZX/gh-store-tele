"""FastAPI Sliding-Window Rate Limiting Middleware backed by Redis."""
import logging
import time
try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except ImportError:
    class BaseHTTPMiddleware:  # type: ignore
        def __init__(self, app):
            self.app = app
    class Request:  # type: ignore
        pass
    class JSONResponse:  # type: ignore
        def __init__(self, content, status_code=200, headers=None):
            self.content = content
            self.status_code = status_code
            self.headers = headers or {}


# Rate limit rules: (prefix_or_exact, max_requests, window_seconds)
RATE_LIMIT_RULES = [
    ("/api/buy", 10, 60),
    ("/api/cart/checkout", 10, 60),
    ("/api/coupon/validate", 15, 60),
    ("/api/voucher/redeem", 10, 60),
    ("/api/admin/", 60, 60),
    ("/api/price-quote", 30, 60),
    ("/api/catalog", 120, 60),
    ("/api/", 60, 60),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self.redis = redis_client

    def _get_rule(self, path: str):
        for prefix, max_reqs, window in RATE_LIMIT_RULES:
            if path.startswith(prefix):
                return max_reqs, window, prefix
        return None

    def _get_client_id(self, request: Request) -> str:
        # Prefer Cloudflare / reverse proxy IP header
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        x_fwd = request.headers.get("X-Forwarded-For")
        if x_fwd:
            return x_fwd.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown_client"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Whitelist non-API routes and health checks
        if not path.startswith("/api/"):
            return await call_next(request)

        rule = self._get_rule(path)
        if not rule or self.redis is None:
            return await call_next(request)

        max_requests, window_seconds, rule_prefix = rule
        client_id = self._get_client_id(request)
        current_minute = int(time.time()) // window_seconds
        key = f"ghstore:rl:{rule_prefix}:{client_id}:{current_minute}"

        try:
            current_count = await self.redis.incr(key)
            if current_count == 1:
                await self.redis.expire(key, window_seconds + 5)

            if current_count > max_requests:
                ttl = await self.redis.ttl(key)
                retry_after = max(1, ttl)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please slow down.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception as e:
            # Fail-open if Redis encounters connection hiccups
            logging.debug("Rate limiter check failed (failing open): %s", e)

        return await call_next(request)
