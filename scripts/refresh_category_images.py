"""Import admin-editable category image URLs from a JSON data manifest.

Preview by default; --apply requires a backup path. Matches canonical
product_category first, then display name. No runtime image mapping is embedded.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main(args) -> int:
    from sqlalchemy import select
    from db import get_db_session, session_commit
    from models.storefront_category import StorefrontCategory

    mapping = json.loads(Path(args.manifest).read_text())
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Manifest must map category names to image URLs")
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Category names and URLs must be strings")
        if urlparse(value).scheme != "https" or not urlparse(value).netloc:
            raise ValueError(f"Expected HTTPS image URL for {key}")
    if args.apply and not args.backup:
        raise ValueError("--apply requires --backup for the previous image records")

    async with get_db_session() as session:
        rows = list((await session.execute(select(StorefrontCategory))).scalars().all())
        changes = []
        for row in rows:
            new_url = mapping.get(row.product_category) or mapping.get(row.name)
            if new_url and new_url != row.image_url:
                changes.append({"id": row.id, "name": row.name,
                                "image_url": row.image_url, "new_image_url": new_url})
                if args.apply:
                    row.image_url = new_url
        if args.apply and changes:
            # Never overwrite a prior backup.
            with Path(args.backup).open("x") as backup:
                json.dump(changes, backup, ensure_ascii=False, indent=2)
            await session_commit(session)
        print(json.dumps({"applied": args.apply, "checked": len(rows),
                          "changed": len(changes), "changes": changes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
