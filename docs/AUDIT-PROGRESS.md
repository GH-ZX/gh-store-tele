# GH Store — Audit Progress Tracker (Items 10–20)

Where we are in the 20-item ChatGPT audit of the GH Store Telegram bot.
Work advances **top to bottom**; every change must pass the health gate before being
considered done. Items are left uncommitted until the user asks to deploy; when a
deploy is requested we commit, push, run pending migrations, and rebuild in Docker.

## Health gate (run after every change)

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/inspect_project.py   # expect "ALL SYSTEM HEALTH CHECKS PASSED"
alembic current                                # expect DB at head (f5e6d7c8b9a0 + pending c9d8e7f6a5b4)
```

## Status snapshot

| Item | Topic | Status | Notes |
|---|---|---|---|
| 10 | Telegram Stars digital-goods decision | ✅ DONE | Decision recorded in `docs/adr/ADR-010-telegram-stars-digital-goods.md` (keep wallet + document, no refactor of legacy `stars.py` flow) |
| 11 | Session revocation (deprecate hard 30-day tokens) | ✅ DONE | Tokens now `tg_id:exp:iat:sig` (default 1 day); `middleware/session_revocation.py`; `/api/admin/sessions/revoke`+`/unrevoke`; migration `f5e6d7c8b9a0` adds `users.sessions_revoked_at` |
| 12 | Supplier capability registry | ✅ DONE | `services/supplier_registry.py` (SupplierCapability enum + BatStore/ProdSeller/G2Bulk adapters); `MultiSupplierService` dispatches through it; order_fulfillment whitelist uses registry |
| 13 | `product_id` uniqueness / cross-supplier collisions | ✅ DONE | Guard `supplier_owns_row()` in `repositories/product.py` wired into all 3 syncs (skip+log, never silently overwrite); intra-ProdSeller id-hash collision guard; range tests |
| 14 | Failover = admin-approved equivalent offers | ✅ DONE (deployed) | `models/approved_equivalent.py` table + SQLAdmin view; `find_alternate_in_stock` resolves approved pairs first, then deterministic token match (replaces fuzzy substring); migration `c9d8e7f6a5b4` |
| 15 | Minor findings sweep (part 1) | ⏳ TODO | |
| 16 | Wallet float / Decimal audit | ⏳ TODO | |
| 17 | Minor findings sweep (part 2) | ⏳ TODO | |
| 18 | Backup script / Dockerfile review | ⏳ TODO | |
| 19 | Misc robustness sweep | ⏳ TODO | |
| 20 | Split `static/storefront/app.js` | ⏳ TODO | |

## Completed work (details)

### Item 10 — ADR-010 (decision only)
- Chose **keep the wallet + document** over refactoring the legacy
  `handlers/user/stars.py` external-payment flow. No code change.

### Item 11 — session revocation
- `services/telegram_auth.py`:
  - `generate_session_token` → `tg_id:exp:iat:sig`, default `expiry_seconds=86400` (was 30 days).
  - New `decode_session_token`, `session_is_revoked`, `extract_session_token_from_request`.
  - `verify_session_token` unchanged signature, backward-compatible with legacy 3-part tokens.
- `middleware/session_revocation.py` (`BaseHTTPMiddleware`, fail-open on DB errors) wired into `bot.py`; rejects `/api` requests bearing revoked tokens.
- `routes/tma_admin.py` → `POST /api/admin/sessions/revoke` + `/unrevoke` with `AdminAuditLog` (`revoke_sessions` / `unrevoke_sessions`).
- `routes/tma_catalog.py` → `create_auth_session` (token exchange) refuses revoked tokens (closes the body-carried-token bypass).
- Migration `f5e6d7c8b9a0_session_revocation.py` → `users.sessions_revoked_at` (`DateTime(timezone=True)`, nullable).
- `models/__init__.py` created (imports every model → fixes latent `Subcategory → 'CartItem'` mapper crash).
- Revocation semantics: token revoked iff `iat <= users.sessions_revoked_at`. Legacy tokens decode with `iat=0` → revoked once a user revokes.

### Item 12 — supplier capability registry
- `services/supplier_registry.py`: `SupplierCapability` (`catalog/quote/purchase/status/cancel/balance`),
  `SupplierCapabilityUnsupported`, `SupplierAdapter` ABC, `BatStoreAdapter` /
  `ProdSellerAdapter` / `G2BulkAdapter`, and `SupplierRegistry`
  (`register/get/all/names/has/capabilities_of`, fallback = `batstore`).
- Capability declarations: batstore = catalog+quote+purchase+status+balance;
  prodseller & g2bulk = no quote/cancel. G2Bulk game-vs-voucher branching moved into the adapter.
- Purchase output shapes + "بديل" failover badges preserved byte-compatible; existing
  tests still patch `BatStoreService.place_order`/`ProdSellerService.place_order`/`G2BulkService.create_game_order`
  because adapters call those attributes at runtime.
- `MultiSupplierService`: `sync_all_suppliers` loops registry adapters (`G2BULK_SYNC_ENABLED`
  skip retained; records `skipped`/`error` flags); `get_cached_supplier_balance` dispatches via adapter;
  `place_order_with_failover` uses `adapter.purchase` + `adapter.is_out_of_stock` with
  `alternate_badge=True` on failover. Failover pairs unchanged:
  `prodseller → batstore`; `batstore → prodseller` (requires `alternate.reseller_key_override`).
- `services/order_fulfillment.py` whitelist → `SupplierRegistry.names()`.

### Item 13 — product_id collision guards
Audit result: **no collisions in live data** (batstore 16–184, prodseller 2.0M–2.84M,
g2bulk 30M+/35M+), but the risk was real and previously silenced by the global unique index
(second writer would overwrite the first). Fixes:
- `repositories/product.py` → `supplier_owns_row(existing, supplier, id)`: skips + logs on
  cross-supplier id overlap; wired into `batstore.py`, `prodseller.py`, and both `g2bulk.py` upsert sites.
- `prodseller.py`: distinct mongo ids hashing to the same `product_id` now warn + skip.
- `tests/test_product_id_ranges.py` (5 tests): guard matrix + reserved-range disjointness.

### Item 14 — approved-equivalent failover  ✅ deployed
- `models/approved_equivalent.py`: `ApprovedEquivalent` table (bidirectional pair of
  `product_id` values) + `ApprovedEquivalentAdmin` SQLAdmin view (category "Catalog").
- `repositories/product.py`:
  - `find_alternate_in_stock(name, target_supplier, session, product_id=None)`:
    1) admin-approved pair (exact, always wins) → 2) deterministic token score
    (≥ `_MIN_MATCH_SCORE` 0.5, ties → smallest `product_id`). Skips hidden/OOS rows
    and never returns the primary row itself.
  - New `match_tokens`, `token_overlap`, `find_approved_equivalent` (both directions).
- `services/multi_supplier.py` failover passes `product_id` so approved pairs resolve
  even when display names differ completely.
- Migration `c9d8e7f6a5b4_approved_equivalents.py` (down_revision `f5e6d7c8b9a0`).
- `tests/test_approved_equivalents.py` (9 tests).

## Commits (this audit cycle)

```
eef7529 feat(failover): admin-approved equivalent offers and deterministic fallback matching
c40ba2b feat(supply): supplier capability registry and product_id collision guards
ca444e6 feat(auth): session revocation via iat tokens, middleware, and admin controls
c458a71 feat(commerce): durable checkout with idempotency keys and resilient fulfillment
```

## Deployment

- Migrations run manually (`alembic upgrade head`) — entrypoint does **not** run them.
- Current deployed state: DB at head `f5e6d7c8b9a0` then **newer `c9d8e7f6a5b4` pending → HEAD** (apply before restart).
- Redeploy:
  ```bash
  git push origin master
  .venv/bin/alembic upgrade head
  docker compose build bot && docker compose up -d bot
  curl -s http://localhost:5000/health    # expect 200, postgres+redis connected
  ```

## Known notes / invariants
- Python 3.12: `datetime.utcnow()` removed → use `datetime.datetime.now(datetime.timezone.utc)`.
- `routes.tma_admin.py` binds `get_db_session` at import → tests patch `admin_routes.get_db_session`;
  the revocation middleware lazy-imports `db.get_db_session` at request time.
- `models/withdrawal.py` holds only `WithdrawalDTO` (no ORM class — not in `models/__init__.py`);
  `models/batstore_order.py` / `batstore_product.py` are backward-compat proxies.
- G2Bulk `/games/servers` upstream 403s in logs are expected (plan/rate limits); catalogue & fields return 200.