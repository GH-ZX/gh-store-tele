import time
from collections import defaultdict

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

import config
from config import SQLADMIN_HASHED_PASSWORD
from enums.user_role import UserRole
from utils.utils import create_access_token, decode_token, verify_password

_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        _login_attempts[client_ip] = [
            t for t in _login_attempts[client_ip] if now - t < _WINDOW_SECONDS
        ]
        if len(_login_attempts[client_ip]) >= _MAX_ATTEMPTS:
            return False

        if username == "admin" and verify_password(password, SQLADMIN_HASHED_PASSWORD):
            token = create_access_token(
                {
                    "sub": UserRole.ADMIN.name,
                }
            )
            request.session.update({"token": token})
            _login_attempts[client_ip].clear()
            return True
        else:
            _login_attempts[client_ip].append(now)
            return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False

        payload = decode_token(token)
        if not payload:
            return False

        exp = payload.get("exp")
        if exp is not None:
            import datetime
            now = datetime.datetime.now(datetime.UTC)
            exp_dt = datetime.datetime.fromtimestamp(exp, tz=datetime.UTC)
            if now > exp_dt:
                request.session.clear()
                return False

        return True


authentication_backend = AdminAuth(secret_key=config.JWT_SECRET_KEY)
