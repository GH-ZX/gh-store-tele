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
    """Return the storefront HTML with deploy-stable cache-busting on static assets."""
    global _CACHED_HTML
    if _CACHED_HTML is None or reload:
        if _TEMPLATE_PATH.exists():
            try:
                _base = _TEMPLATE_PATH.parent
                _mtimes = [_TEMPLATE_PATH.stat().st_mtime]
                for _rel in ("../static/storefront/app.js", "../static/storefront/app.css"):
                    _p = (_base / _rel).resolve()
                    if _p.exists():
                        _mtimes.append(_p.stat().st_mtime)
                v_ts = int(max(_mtimes))
            except Exception:
                v_ts = int(time.time())
            raw = _TEMPLATE_PATH.read_text(encoding="utf-8")
            # Stable per-deploy tag: identical HTML until a template/asset file changes,
            # so the in-app stale-shell guard cannot reload-loop.
            raw = raw.replace('/static/storefront/app.css', f'/static/storefront/app.css?v={v_ts}')
            raw = raw.replace('/static/storefront/app.js', f'/static/storefront/app.js?v={v_ts}')
            raw = raw.replace('__BUILD_TAG__', str(v_ts))
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
