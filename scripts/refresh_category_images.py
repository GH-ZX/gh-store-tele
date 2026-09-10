"""One-shot data migration: point category covers at local DB-driven art.

Replaces external/slow cover URLs (Unsplash, postimg, empty) with the
local artwork paths defined in services.storefront_images, stored per-row
in storefront_categories.image_url (editable anytime via SQLAdmin / TMA admin).
Safe to re-run: only touches rows whose URL is empty or external.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from db import get_db_session, session_commit
from services.storefront_images import DEFAULT_CATEGORY_IMAGES, LOCAL_CATEGORY_PLACEHOLDER

_EXTERNAL_PREFIXES = ("http://", "https://")


def _needs_refresh(url: str | None) -> bool:
    u = (url or "").strip()
    if not u:
        return True
    if u.startswith("/static/img/"):
        return False
    return u.startswith(_EXTERNAL_PREFIXES)


async def main() -> int:
    from sqlalchemy import select
    from models.storefront_category import StorefrontCategory

    async with get_db_session() as session:
        rows = list((await session.execute(select(StorefrontCategory))).scalars().all())
        updated = 0
        for c in rows:
            if _needs_refresh(c.image_url):
                c.image_url = DEFAULT_CATEGORY_IMAGES.get(c.name, LOCAL_CATEGORY_PLACEHOLDER)
                updated += 1
        if updated:
            await session_commit(session)
        print(f"[refresh-images] checked={len(rows)} updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
