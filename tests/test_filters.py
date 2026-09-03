import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock


class _UserOrm:
    def __init__(self, is_banned=False, is_admin=False):
        self.is_banned = is_banned
        self.is_admin = is_admin


@pytest.mark.asyncio
async def test_banned_filter_blocks_banned_non_admin(monkeypatch):
    from utils.custom_filters import IsUserBannedFilter

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(is_banned=True, is_admin=False)

    monkeypatch.setattr(
        "utils.custom_filters.UserRepository.get_by_tgid", fake_get_by_tgid)

    # Mock get_db_session to return an async context manager
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr("utils.custom_filters.get_db_session", fake_session)

    f = IsUserBannedFilter()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=100))
    result = await f(msg)
    assert result is True


@pytest.mark.asyncio
async def test_banned_filter_allows_admin(monkeypatch):
    from utils.custom_filters import IsUserBannedFilter

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(is_banned=True, is_admin=True)

    monkeypatch.setattr(
        "utils.custom_filters.UserRepository.get_by_tgid", fake_get_by_tgid)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr("utils.custom_filters.get_db_session", fake_session)

    f = IsUserBannedFilter()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1))
    result = await f(msg)
    assert result is False


@pytest.mark.asyncio
async def test_banned_filter_allows_non_banned_user(monkeypatch):
    from utils.custom_filters import IsUserBannedFilter

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(is_banned=False, is_admin=False)

    monkeypatch.setattr(
        "utils.custom_filters.UserRepository.get_by_tgid", fake_get_by_tgid)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr("utils.custom_filters.get_db_session", fake_session)

    f = IsUserBannedFilter()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=200))
    result = await f(msg)
    assert result is False


@pytest.mark.asyncio
async def test_banned_filter_allows_unknown_user(monkeypatch):
    from utils.custom_filters import IsUserBannedFilter

    async def fake_get_by_tgid(tgid, session):
        return None

    monkeypatch.setattr(
        "utils.custom_filters.UserRepository.get_by_tgid", fake_get_by_tgid)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr("utils.custom_filters.get_db_session", fake_session)

    f = IsUserBannedFilter()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=999))
    result = await f(msg)
    assert result is False


@pytest.mark.asyncio
async def test_banned_filter_handles_no_from_user():
    from utils.custom_filters import IsUserBannedFilter

    f = IsUserBannedFilter()
    msg = SimpleNamespace(from_user=None)
    result = await f(msg)
    assert result is False


@pytest.mark.asyncio
async def test_banned_filter_handles_callback_query(monkeypatch):
    from utils.custom_filters import IsUserBannedFilter

    async def fake_get_by_tgid(tgid, session):
        return _UserOrm(is_banned=True, is_admin=False)

    monkeypatch.setattr(
        "utils.custom_filters.UserRepository.get_by_tgid", fake_get_by_tgid)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr("utils.custom_filters.get_db_session", fake_session)

    f = IsUserBannedFilter()
    callback = SimpleNamespace(from_user=SimpleNamespace(id=300))
    result = await f(callback)
    assert result is True
