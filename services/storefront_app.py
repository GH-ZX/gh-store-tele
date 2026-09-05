"""Telegram Mini App (TMA) Mobile-First Storefront Loader.

The frontend HTML, CSS, and JS have been extracted into:
- templates/storefront.html
- static/storefront/app.css
- static/storefront/app.js

This eliminates python file bloat and enables standard asset caching,
linter validation, and clean template rendering.
"""
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "storefront.html"
_CACHED_HTML: str | None = None
import time

def get_storefront_html(reload: bool = False) -> str:
    """Return the storefront HTML with dynamic cache-busting on static assets."""
    global _CACHED_HTML
    if _CACHED_HTML is None or reload:
        if _TEMPLATE_PATH.exists():
            raw = _TEMPLATE_PATH.read_text(encoding="utf-8")
            # Dynamic timestamp cache-buster prevents iOS/Android Telegram WebView from reusing stale cached JS
            v_ts = int(time.time())
            raw = raw.replace('/static/storefront/app.css', f'/static/storefront/app.css?v={v_ts}')
            raw = raw.replace('/static/storefront/app.js', f'/static/storefront/app.js?v={v_ts}')
            _CACHED_HTML = raw
        else:
            _CACHED_HTML = "<!DOCTYPE html><html><body><h1>Storefront template not found</h1></body></html>"
    return _CACHED_HTML
class _StorefrontHtmlProxy(str):
    def __str__(self) -> str:
        return get_storefront_html()

    def __repr__(self) -> str:
        return f"<StorefrontHTML len={len(get_storefront_html())}>"


STOREFRONT_HTML = _StorefrontHtmlProxy()
