from types import SimpleNamespace

import pytest

from utils.telegram import create_telegram_session, create_bot, clean_tg_emojis


def test_create_telegram_session_without_proxy(monkeypatch):
    monkeypatch.setattr("config.TELEGRAM_PROXY_URL", None)

    session = create_telegram_session()

    assert session._proxy is None


def test_create_telegram_session_with_proxy(monkeypatch):
    monkeypatch.setattr("config.TELEGRAM_PROXY_URL", "socks5://192.168.1.1:10808")

    session = create_telegram_session()

    assert session._proxy == "socks5://192.168.1.1:10808"


def test_create_bot_uses_proxy_session_by_default(monkeypatch):
    fake_session = SimpleNamespace()
    captured = {}

    class _FakeBot:
        def __init__(self, token, session, default):
            captured["token"] = token
            captured["session"] = session
            captured["default"] = default

    monkeypatch.setattr("utils.telegram.create_telegram_session", lambda: fake_session)
    monkeypatch.setattr("utils.telegram.Bot", _FakeBot)

    create_bot("123:ABC")

    assert captured["token"] == "123:ABC"
    assert captured["session"] is fake_session


def test_clean_tg_emojis():
    raw = '<tg-emoji emoji-id="5372937764411031477">📱</tg-emoji> Microsoft 365 <tg-emoji emoji-id="5204103055271817225">✅</tg-emoji>'
    cleaned = clean_tg_emojis(raw)
    assert cleaned == "📱 Microsoft 365 ✅"

    raw_leaked = "Features: TG_EMOJI_0 Word, TG_EMOJI_1 Excel, __TG_EMOJI_2__, TGemoji3"
    cleaned_leak = clean_tg_emojis(raw_leaked)
    assert "TG_EMOJI" not in cleaned_leak
    assert "TGemoji" not in cleaned_leak

    assert clean_tg_emojis(None) == ""
    assert clean_tg_emojis("Plain text 🤖 🚀") == "Plain text 🤖 🚀"
