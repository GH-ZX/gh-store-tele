# GHstore — Knowledge Base & Implementation Plan

Captured during setup session (2026-08-30). Goal: a private Telegram reseller shop
that sells BatStore/SAM digital products to known customers at a margin, wallet-backed
by crypto (KryptoExpress built-in) + Telegram Stars, running 24/7 in Docker, portable.

Repo state: local copy (`/home/it/Coding/GHstore`) of upstream
`ilyarolf/AiogramShopBot` (MIT license — free to use/modify).

---

## 1. What the upstream repo already gives us

Full e-commerce Telegram bot (Aiogram 3 + FastAPI + SQLAlchemy async + Postgres + Redis).

- Storefront: categories / subcategories / cart / checkout / purchase history.
- Admin menu + SQLAdmin web panel (`/admin`).
- Crypto payments via **KryptoExpress** SDK (balance top-up → `user.top_up_amount`).
- Referral system, coupons, shipping/addresses, reviews, multi-language (i18n JSON).
- Docker Compose: `caddy` (reverse proxy/TLS), `bot`, `redis`, `postgres`.
- Multibot mode (not needed for us — keep `MULTIBOT=false`).

### Key files (where our work lives)

| Concern | File | Notes |
|---|---|---|
| Config/env | `config.py`, `.env.template` | Add our keys here |
| Product row | `models/item.py` | `Item.private_data` holds the delivered good |
| Buy/order row | `models/buy.py`, `models/buyItem.py` | Records a purchase (`BuyStatus`) |
| **Purchase completion** | `services/cart.py` `buy_processing()` (~line 300) | **Integration kill-point** |
| Balance top-up (crypto) | `services/payment.py`, `processing/processing.py` | KryptoExpress webhook |
| Webhook ingress | `bot.py:133` + `processing.py` | Crypto callback |
| Admin inventory | `handlers/admin/inventory_management.py` | Preload goods |
| DB engine | `db.py` | SQLAlchemy async engine |
| Migrations | `migrations/` | Alembic |

---

## 2. The core mismatch: stock-model vs on-demand reseller

The upstream bot's digital-goods model is a **pre-loaded inventory**: each `Item` is a
single unit with `private_data`, marked `is_sold` when purchased
(`services/cart.py:360-362`).

Our model is the **opposite**: we do NOT hold inventory. When a customer buys, we
call the BatStore/SAM reseller API which fulfills **on demand** and debits **our**
reseller wallet.

**Consequence:** the "virtual stock" of a product is whatever the reseller currently
has (and stock may be infinite for activation/supplier_api types). We must:

1. Show products at **our margin price** (defined by us), not raw reseller cost.
2. On a successful purchase, call reseller `quote`/`order`, get the delivered good
   (or an order id for manual/activation delivery), and store it.
3. Handle **async/activation** delivery types (some products are fulfilled later, e.g.
   via `activation-identifier` submit) — must poll or use reseller webhooks.

This means we should NOT repurpose the built-in `Item.is_sold` stock flow as-is; the
cleanest path is a new `batstore`/`sam` service + a catalog mapping table
(category/subcategory ↔ reseller `product_id`) + a "fulfillment state" per buy.

---

## 3. Reseller API (VenteBot) — reference spec we already pulled

> The "BatStore" reseller API the user referred to maps to this VenteBot spec below
> (`https://ventetelegrambotrailway-production.up.railway.app/api/reseller/openapi.json`).

## 3b. SAM API (`sam-api.pro`) — ACTUAL nature: it is a WALLET/PAYMENT API, not a product reseller

⚠️ **Important correction from the SAM API docs the user pasted.** Helpfully, this
is NOT a goods-reseller API at all. It is a **mobile-wallet / payments API**
(ShamCash + Syriatel Cash in Syria). It lets us read wallet balances, list/transfer
between wallets, and — crucially — create **payment invoices** that payers open in a
browser to credit a wallet. This is a *payment rail*, like the crypto/Stars rails, NOT
the product supply.

### What SAM API gives us
- **Wallets view:** `GET /v1/wallets` — list wallets linked to the key (provider,
  label, phone, walletAddress, accountNumber, region, status).
- **ShamCash** (provider `shamcash`):
  - `GET /v1/wallets/shamcash/{walletAddress}/balance` → balances (USD / SYP / EUR).
  - `GET /v1/wallets/shamcash/{walletAddress}/transactions?direction=in|out|all`.
  - `POST /v1/wallets/shamcash/{walletAddress}/transfer` with
    `{ recipientAddress, currencyId (1=USD,2=SYP,3=EUR), amount, note? }`.
- **Syriatel Cash** (provider `syriatel`):
  - `GET /v1/wallets/syriatel/{phoneOrCode}/balance` → SYP only.
  - `GET /v1/wallets/syriatel/{phoneOrCode}/transactions?direction=...`.
  - `POST /v1/wallets/syriatel/{phoneOrCode}/transfer` with
    `{ toGsmOrCode, amount, pinCode }`.
- **Invoicing (payment acceptance):**
  - `POST /v1/invoices` body
    `{ method: "shamcash"|"syriatel", identifier, amount, currency: "USD"|"SYP"|"EUR", webhookUrl }`
    → `{ invoiceId, paymentUrl, expiresAt }` (valid **15 min**).
  - `GET /pay/{invoiceId}` → full invoice status (public, no auth).
  - `POST /pay/{invoiceId}/verify` body `{ transactionRef }` → confirms payment and
    auto-sends webhook.
  - **Webhook** `POST /your-webhook-url` events: `invoice.paid` (with `transactionRef`,
    `paidAmount`, `counterparty`, `paidAt`) or `invoice.expired` (with `expiredAt`).
    Server must answer HTTP 2xx.
- **Auth:** header `Authorization: Bearer sk_...` (or `X-Api-Key: sk_...`).
- **Base URL:** `https://www.sam-api.pro/api`.
- **Errors:** 401 MISSING/INVALID_API_KEY, 400 VALIDATION_ERROR / INVALID_IDENTIFIER,
  404 NOT_FOUND, 410 EXPIRED, 401 WALLET_SESSION_EXPIRED, 502 WALLET_UPSTREAM_ERROR /
  PROVIDER_ERROR.
- Requires an **active subscription** and the wallet must be **linked to the account**
  for invoicing.

### How SAM API fits the build (payment rail, like crypto/Stars)
SAM invoices are a clean way for **customers to top up their bot balance** using
ShamCash/Syriatel wallets, and/or for **us (admin) to pay** for reseller products from
our wallet top-ups. Two candidate uses:
1. **Customer balance top-up via SAM invoice**: add a "Top up with Sam Cash / Syriatel"
   button → `POST /v1/invoices` (amount in USD or SYP) → customer opens `paymentUrl`,
   pays, we get `invoice.paid` webhook → credit `user.top_up_amount`.
2. **Admin wallet funding / payments**: use `balance` + `transfer` to move money
   between our linked wallets or pay for reseller goods with wallet funds.

This is yet another fiat payment rail alongside crypto (KryptoExpress) and Stars —
it does NOT supply products. Products still come from the VenteBot/BatStore reseller
API (or the user's "SAM" terminology may conflate the two — must clarify which is the
product source).

OpenAPI spec saved at session temp during recon. Base: VenteBot Reseller API v1.2.0.
Auth via header `X-Reseller-Key` (or `X-API-Key`). Rate limit 60 req/60s.
Purchases debit the reseller account wallet.

Endpoints (from `/api/reseller/openapi.json`):

| Endpoint | Purpose |
|---|---|
| `GET /me` | Verify key, read wallet balance |
| `GET /products` | List active products |
| `POST /quote` | Calculate price before buying (`product_id`, `quantity`) |
| `POST /orders` | Create an order (debits wallet) |
| `GET /orders/{order_id}` | Read order status/result |
| `POST /orders/{order_id}/activation-identifier` | Submit activation identifier later |
| `GET /wallet/transactions` | Wallet history |
| `GET /wallet/deposit-methods`, `POST /wallet/deposits` ... | Top up reseller wallet |

Product shape (relevant fields): `id`, `name`, `price_usd`, `standard_price_usd`,
`pricing_type` (standard | reseller_special), `delivery_type`
(stock | activation | supplier_api | api_test), `stock` (nullable),
`warranty_days`, `api_test`.

Quote response: `quote.unit_price`, `quote.standard_unit_price`, `quote.total`,
`quote.delivery_type`, `quote.stock`, plus `wallet_balance`.

**Design reference — new service module:**

```python
# services/batstore.py  (or services/sam.py once SAM spec is provided)
class BatStoreService:
    BASE = config.BATSTORE_API_URL
    KEY = config.BATSTORE_API_KEY
    HEADERS = {"X-Reseller-Key": KEY}

    @staticmethod
    async def list_products(): ...          # GET /products
    @staticmethod
    async def quote(product_id, qty=1): ... # POST /quote
    @staticmethod
    async def place_order(product_id, qty=1): ...  # POST /orders
    @staticmethod
    async def get_order(order_id): ...      # GET /orders/{order_id}
```

We add async HTTP (the repo already depends on `aiohttp-socks`; a small `aiohttp`
session or `httpx`). Config additions to `config.py` / `.env`:

```ini
BATSTORE_API_URL=https://ventetelegrambotrailway-production.up.railway.app
BATSTORE_API_KEY=...
GHSTORE_MARGIN_PERCENT=0        # e.g. 20 => charge 20% above reseller cost
GHSTORE_MARGIN_FIXED=0.0        # optional flat USD adder to unit price
```

---

## 4. Margin pricing

Sell price to customer = `reseller_cost * (1 + GHSTORE_MARGIN_PERCENT/100) + GHSTORE_MARGIN_FIXED`.

- Do this at **display** time (categories/subcategories) and at **checkout**.
- Suggested approach: a `batstore_product` table storing `product_id`, name,
  description/emoji/image, `cost_usd` (reseller), `sell_price_usd` (our price).
  Admin refreshes from `GET /products`.
- Optionally a per-category override so you can set different margins.
- Use `quote` before charging to catch price changes / stock / balance issues.
- Currency: keep bot in USD (`CURRENCY=USD`). The crypto + Stars flows credit fiat
  `user.consume_records` in USD; our margin price is also USD → consistent.

---

## 5. Purchase flow with reseller fulfillment (the planned edit)

Current `buy_processing` (`services/cart.py:300`):
1. checks stock availability, applies coupon,
2. checks `is_enough_money = (top_up_amount - consume_records) >= cart_total_price`,
3. creates `Buy` + `BuyItem`, marks items sold, deducts balance.

Planned GHstore version:
1. Reuse cart + balance check (**charge customer first**).
2. On confirmation & sufficient balance: create `Buy` (status `PENDING_FULFILLMENT`).
3. For each reseller line: call `quote` (verify total still within customer's paid
   amount) then `place_order`. On success, save reseller `order_id` + delivered good
   / status on the buy record.
4. If `delivery_type` is immediate (stock/supplier_api/api_test): deliver the good to
   the customer immediately and mark `COMPLETED`.
5. If `activation` (manual/async): keep `PENDING` and complete when the reseller
   signals via webhook/polling or when the admin confirms; optionally use
   `activation-identifier`.
6. On reseller failure (no balance / out of stock / error): **do not** keep the
   customer's money — either refund the recorded `consume_records` + cancel the buy,
   or show an error and let them retry. This protects our wallet and our customers.

> Risk note (business, not code): debiting our reseller wallet draws down **our**
> balance. Only fulfill after the customer has paid, and surface
> `GET /me` wallet balance to the admin so you know your reserves.

---

## 6. Telegram Stars top-up (new payment rail)

User wants customers to top up balance with **Telegram Stars** in addition to crypto.
aiogram 3.14 fully supports Stars.

Add a buyer:
- Implement `Telegram Payments API`: create **Star invoices** via
  `bot.create_invoice_link` / `payments` (aiogram `aiogram.methods.create_invoice_link`)
  with `XTR` currency; customers pay with Stars via `/pay`.
- Capture confirmation in `Message.successful_payment` (Stars payload →
  `telegram_payment_charge_id`), credit `user.top_up_amount` in USD
  (Stars ≈ 1 Star = 1 cent per Telegram pricing; apply `GHSTORE_STARS_TO_USD` factor).
- **Optionally** auto-cancel unpaid invoices via `bot.cancel_invoice_link`.
- Refund path: `bot.refund_star_payment(user_id, telegram_payment_charge_id)`.

This is additive on top of the built-in `PaymentService` top-up flow
(`handlers/user/my_profile.py` triggers it) — add a "Top up with ⭐" button that
branches into Star invoice creation instead of a KryptoExpress invoice.

New config keys:
```ini
GHSTORE_STARS_ENABLED=true
GHSTORE_STARS_TO_USD=0.01      # 1 Star = 1 cent by default
```

### 6b. SAM invoice top-up (ShamCash / Syriatel Cash) — additional payment rail

Because SAM API is a wallet/payment API (see §3b), the natural use in GHstore is a
**balance top-up rail** for customers who use ShamCash/Syriatel instead of crypto/Stars.

Planned flow (mirrors the existing `PaymentService` top-up):
1. Add a "Top up with ShamCash / Syriatel" button in `handlers/user/my_profile.py`.
2. Build the invoice via `POST /v1/invoices`:
   ```
   POST https://www.sam-api.pro/api/v1/invoices
   Authorization: Bearer sk_...
   { "method": "shamcash",
     "identifier": "<our receiving wallet addr>",
     "amount": "<usd or syp>",
     "currency": "USD",
     "webhookUrl": "https://<our-host>/samwebhook" }
   ```
3. Send the customer `paymentUrl` (web app link). Invoice valid 15 min.
4. Handle `POST /samwebhook` (`processing/processing.py` style router):
   - `invoice.paid` → find pending user by stored invoiceId → credit
     `user.top_up_amount` (convert SYP→USD with `GHSTORE_SYP_USD_RATE`), notify user.
   - `invoice.expired` → just notify; no credit.
   - Return HTTP 2xx to SAM always.
5. Persist a mapping `invoiceId → (user, fiat_amount_usd)` (reuse `Payment` / `Deposit`
   tables or a small `sam_payment` table).

New config keys:
```ini
SAM_API_BASE=https://www.sam-api.pro/api
SAM_API_KEY=sk_...
SAM_RECEIVING_WALLET_ID=...    # our linked receiving wallet UUID/addr/phone
SAM_CURRENCY=USD               # USD or SYP for invoices
SAM_SYP_USD_RATE=0.002551       # only if charging in SYP (≈ 2026 rough rate)
```

> Note: SAM invoices only **credit the wallet the customer pays into** (`identifier`
> = OUR receiving wallet). So a customer-paying-invoice credits OUR wallet — to credit
> the *customer's bot balance* we must trust the `invoice.paid` webhook and record the
> fiat amount manually. If instead you want the *customer's* own wallet debited
> directly to us, use the `transfer` endpoints from their wallet — but that requires
> their wallet credentials/PIN, which they won't share; the **invoice** model is the
> correct one for bot top-ups.

---

## 7. Docker / 24-7 portability

Repo already ships `Dockerfile` + `docker-compose.yml` (caddy + bot + redis + postgres).
Steps to make it yours and portable:

1. Copy `.env.template` → `.env` and fill keys (token, DB password, Redis password,
   SQLAdmin password, JWT secret, KryptoExpress keys, BatStore keys, margin).
2. `docker compose up -d --build` on this PC.
3. To move to another PC: copy the **project directory** (including `postgres_data/`
   volume for your DB) and run `docker compose up -d --build` there. Everything is
   containerized → no environment drift.
4. **Networking/TLS note:** repo supports two webhook modes:
   - DEV: auto `ngrok` tunnel (needs `NGROK_TOKEN`).
   - PROD: expects `RUNTIME_ENVIRONMENT=PROD` + a public domain via sship.io/`Caddyfile`
     (caddy gives free TLS). For 24/7 on a home laptop you'll need either a domain or
     a stable public URL for the Telegram webhook + crypto callback. Decide this.
5. Persist data: `postgres_data/`, `redis_data/`, `caddy_data/`, `i18n/` bind mounts.

Env essentials (from `.env.template`):
```
TOKEN=                  # BotFather bot token
ADMIN_ID_LIST=          # comma-separated admin telegram ids
POSTGRES_PASSWORD=      # DB password
REDIS_PASSWORD=         # Redis password
SQLADMIN_RAW_PASSWORD=  # /admin login password
JWT_SECRET_KEY=         # random secret
KRYPTO_EXPRESS_API_KEY= # KryptoExpress key (crypto top-ups)
KRYPTO_EXPRESS_API_SECRET=
RUNTIME_ENVIRONMENT=    # DEV or PROD
NGROK_TOKEN=            # only for DEV tunnel
```

---

## 8. Required inputs from the user to continue

- [ ] **BotFather telegram token** (`TOKEN`).
- [ ] **PRODUCT SUPPLY source** — the critical missing piece. The SAM API docs you
      pasted are a *wallet/payment* API, NOT a product reseller. We still need the
      product source. Is it the **VenteBot/BatStore** spec (§3, `GET /products`,
      `POST /orders`), or a different "SAM" product API? Please confirm + paste the
      product list/token so we can build the catalog + fulfillment.
- [ ] **SAM API token** (`sk_...`) — only for the top-up/payment rail, if we use it.
- [ ] **KryptoExpress API key + secret** (crypto top-ups), or decide which rail(s) to
      ship first (crypto / Stars / SAM).
- [ ] Desired **margin % / fixed USD** and which products to list.
- [ ] For 24-7: a **public URL** approach (domain + Caddy, or ngrok for now) — needed
      for Telegram webhook, crypto callback, AND SAM invoice webhook.

## 9. Ordered build plan (when inputs arrive)

0. **Clarify product supply**: confirm whether products come from VenteBot/BatStore
   `GET /products`/`POST /orders`, or another API. This drives the catalog + the
   charge-then-fulfill logic in `buy_processing`.
1. Fill `.env` with token + DB/Redis/SQLAdmin/JWT (+ relevant API keys). Bring bot up
   in Docker (stock baseline). Verify `/admin`, storefront, top-up.
2. Add product-supply service (`services/batstore.py`) + config keys + catalog table
   (`batstore_product`) with margin pricing at display & checkout.
3. Modify `buy_processing` to charge-then-fulfill with reseller order + delivery-type
   handling (immediate vs activation).
4. Add balance top-up rails: **Telegram Stars** (see §6) and/or **SAM invoice** (see
   §6b), additive to built-in crypto.
5. Production webhook/public-URL setup for 24-7 up-time (Telegram, crypto, SAM webhooks).
6. Seed products, set margin, test end-to-end with a real paid order.

---

## 10. Audit progress tracker (items 10–20)

Where we are in the 20-item ChatGPT audit of the GH Store Telegram bot.
Work advances **top to bottom**; every change must pass the health gate before being
considered done. Items are left uncommitted until the user asks to deploy; when a
deploy is requested we commit, push, run pending migrations, and rebuild in Docker.

### Health gate (run after every change)

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/inspect_project.py   # expect "ALL SYSTEM HEALTH CHECKS PASSED"
alembic current                                # expect DB at head
```

### Status snapshot

| Item | Topic | Status | Notes |
|---|---|---|---|
| 10 | Telegram Stars digital-goods decision | ✅ DONE | Decision recorded in `docs/adr/ADR-010-telegram-stars-digital-goods.md` (keep wallet + document, no refactor of legacy `stars.py` flow) |
| 11 | Session revocation (deprecate hard 30-day tokens) | ✅ DONE | Tokens now `tg_id:exp:iat:sig` (default 1 day); `middleware/session_revocation.py`; `/api/admin/sessions/revoke`+`/unrevoke`; migration `f5e6d7c8b9a0` adds `users.sessions_revoked_at` |
| 12 | Supplier capability registry | ✅ DONE | `services/supplier_registry.py` (SupplierCapability enum + BatStore/ProdSeller/G2Bulk adapters); `MultiSupplierService` dispatches through it; order_fulfillment whitelist uses registry |
| 13 | `product_id` uniqueness / cross-supplier collisions | ✅ DONE | Guard `supplier_owns_row()` in `repositories/product.py` wired into all 3 syncs (skip+log, never silently overwrite); intra-ProdSeller id-hash collision guard; range tests |
| 14 | Failover = admin-approved equivalent offers | ✅ DONE (deployed) | `models/approved_equivalent.py` table + SQLAdmin view; `find_alternate_in_stock` resolves approved pairs first, then deterministic token match (replaces fuzzy substring); migration `c9d8e7f6a5b4` |
| 15 | SMS-activation lifecycle for 5sim-like providers | ⏳ NEXT | Country/operator/service selection, phone allocation, code polling, resend/cancel, expiration timeouts |
| 16 | Wallet float / Decimal audit & append-only ledger | ⏳ TODO | `models/user.py` balance float → Decimal, ledger records for credit/capture/refund |
| 17 | Multi-process background worker durability | ⏳ TODO | Durable job queue, claim jobs atomically, persist poll attempts |
| 18 | Backups executable, persistent, and encrypted | ⏳ TODO | Docker backup tools, volumes, encryption, tested restore |
| 19 | Fix tests protecting legacy/incorrect behaviors | ⏳ TODO | True integration tests, eliminate tests expecting unauthenticated fallbacks |
| 20 | Split Mini App storefront JS & test mobile journeys | ✅ DONE | Decomposed 9,160-line `app.js` into `api.js`, `storefront.js`, `wallet.js`, `checkout.js`, `admin.js`, and `app.js`; enabled viewport zoom; added automated headless Chromium browser coverage suite (`tests/test_storefront_browser.cjs`) |

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

### Item 14 — approved-equivalent failover  (deployed)
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

### Item 20 — split Mini App storefront JS & browser coverage  ✅ DONE
- Decomposed monolithic `static/storefront/app.js` into focused, cohesive modules with shared API/auth layer:
  - `static/storefront/api.js`: Session token storage, fetch auto-interceptor, Telegram WebApp SDK bindings, haptics, safe areas, i18n dictionary, RTL/LTR layout switcher, navStack, and keyboard handlers.
  - `static/storefront/storefront.js`: Categories rendering (grid vs list), folder cards, in-stock priority partitioning, alias-powered search (`SEARCH_ALIASES`), product detail sheet, countdown timer, and reviews/support modals.
  - `static/storefront/wallet.js`: Multi-currency balance rendering (USD, SYP, Stars), VIP tier progression, recharge rails (Stars invoice, Crypto BEP-20, ShamCash, Syriatel Cash), voucher redemption, and receipt modal.
  - `static/storefront/checkout.js`: Multi-item cart drawer, dynamic game account fields, coupon validation, durable checkout recovery engine (`savePendingCheckout`, `recoverPendingCheckout`), and post-purchase credential view.
  - `static/storefront/admin.js`: Admin overview dashboard, liquidity monitor, live product/category/folder/banner editors, user balance adjustment, and session revocation triggers.
  - `static/storefront/app.js`: Master bootstrap orchestrator, window global backward compatibility, and security formatters preservation.
- Viewport zoom: Removed `maximum-scale=1.0, user-scalable=no` from `templates/storefront.html` to allow pinch-to-zoom and accessibility scaling while preserving `viewport-fit=cover`.
- Asset caching: `services/storefront_app.py` computes max mtime across all modular `.js` scripts for deploy-stable cache-busting.
- Automated browser test coverage:
  - `tests/test_storefront_browser.cjs`: Headless Chromium test suite (36 tests) covering checkout recovery, Arabic/English RTL/LTR toggling, navigation stack & Telegram BackButton, keyboard behaviors (Enter on search/coupon, Escape on modals), and viewport zoom.
  - `tests/test_storefront_browser.py`: Pytest integration runner.
  - `tests/storefront_security.cjs`: Re-verified (118 security tests pass).

### Item 15 — SMS-activation lifecycle (5sim)  ✅ DONE
- Complete virtual phone number provisioning and SMS activation lifecycle backed by **5sim** (`https://5sim.net/v1`).
- Models & Database (`models/sms_activation.py`):
  - `SmsActivation`: Dedicated tracking of virtual number allocations, incoming SMS codes, 15-minute countdown timeouts, and refund states.
  - `SmsServiceConfig`: Admin-curated list of popular SMS activation services (Telegram, WhatsApp, OpenAI/ChatGPT, Google/Gmail, Instagram, TikTok, Discord, Steam, X/Twitter, Microsoft) with enable/disable toggles and icons.
  - `SmsCountryConfig`: Admin-curated list of high-success / good-rate regions (USA, UK, Netherlands, Germany, Poland, Sweden, France, Canada, Indonesia, Malaysia, Turkey, Brazil, Kazakhstan) with enable/disable toggles and flags.
  - SQLAdmin views: `SmsActivationAdmin`, `SmsServiceConfigAdmin`, `SmsCountryConfigAdmin` registered under the "Catalog" category.
- Backend Services & Routing:
  - `services/fivesim.py`: `FiveSimService` providing `get_balance()`, `get_prices()`, `buy_activation()`, `check_order()`, `finish_order()`, `cancel_order()`, and `ban_order()`.
  - `services/supplier_registry.py`: Registered `FiveSimAdapter` under `SupplierRegistry` declaring `SMS_ACTIVATION`, `CANCEL`, `BALANCE`, and `STATUS` capabilities.
  - `routes/tma_sms.py`: REST endpoints for Mini App:
    - `GET /api/sms/services`: Active popular services.
    - `GET /api/sms/countries`: Active good-rate regions.
    - `GET /api/sms/quote`: Real-time stock count, cost calculation, and margin USD pricing.
    - `POST /api/sms/buy`: Verified Telegram user identity check, atomic balance debit, virtual number allocation, and order creation.
    - `GET /api/sms/order/{id}`: Live SMS code polling with auto-completion and auto-finish upstream.
    - `POST /api/sms/order/{id}/cancel`: Cancellation with atomic wallet refund.
    - `POST /api/sms/order/{id}/ban`: Number ban reporting with atomic wallet refund.
    - `GET /api/admin/sms/settings`: Admin dashboard for 5sim balance and service/country switches.
    - `POST /api/admin/sms/services/toggle` & `/countries/toggle`: Instant admin switch toggles.
- Background Poller & Resilience:
  - `services/order_polling.py`: `poll_pending_sms_activations()` background task checks pending activations every 10s:
    - On code arrival: finishes upstream, updates order to completed, and sends a push notification to user via `NotificationService.send_to_user`.
    - On timeout/cancellation: marks timeout, executes atomic refund via `UserRepository.refund_balance`, and notifies user.
- Frontend Mini App (`static/storefront/sms.js` & `templates/storefront.html`):
  - Added interactive `#sms-activation-modal` with two-stage flow:
    - Stage 1: Service/Country select, stock badge, real-time USD and local currency pricing, 15-minute guarantee note, and "Buy Number" button.
    - Stage 2: Allocated phone number display with 1-tap copy, animated pulsing radar waiting indicator, 15:00 countdown timer, received code card with 1-tap copy, and instant Cancel & Ban refund buttons.
  - Added `#filter-sms-chip` to the storefront filter chips bar.
  - Added `#admin-sms-modal` and `#btn-admin-sms-drawer` in Settings to let admins toggle services/countries and view 5sim balance in real-time.
- Automated Tests:
  - `tests/test_fivesim_service.py` (11 passed).
  - `tests/test_tma_sms_routes.py` (11 passed).
  - `tests/test_storefront_browser.cjs` (46 passed).
  - Total pytest suite: 309 passed.
  - Migration: `d1e2f3a4b5c6_sms_activations.py` applied.

### Item 16 — exact money values & append-only wallet ledger  ✅ DONE
- Converted floating-point monetary columns to exact fixed-point `Numeric(12, 2)`:
  - `users.top_up_amount` and `users.consume_records` in `models/user.py`.
  - `batstore_orders.total_sell` in `models/order.py`.
- Built an immutable, append-only `WalletLedger` model (`models/wallet_ledger.py`, table `wallet_ledger`):
  - Records every balance event: `reservation` (hold/debit), `refund`, `credit` (deposit/top-up), and `capture` (fulfillment).
  - Unique idempotency reference per transaction (`reference`, indexed and unique) preventing double-spending and duplicate credits.
  - Retains actual upstream supplier wholesale cost (`supplier_cost`, `Numeric(12, 4)`) and wholesale currency (`supplier_currency`, e.g., `USD`, `USDT`, `RUB`) at fulfillment/capture time.
  - SQLAdmin view `WalletLedgerAdmin` registered with `can_create = False`, `can_edit = False`, `can_delete = False`.
- Integrated ledger recording atomically into repository operations:
  - `UserRepository.try_debit_balance`: Records `reservation` ledger entry with balance before and after.
  - `UserRepository.refund_balance`: Records `refund` ledger entry with balance before and after.
  - `UserRepository.credit_balance`: Records `credit` ledger entry with balance before and after.
  - `UserRepository.record_capture`: Records `capture` ledger entry persisting supplier wholesale cost and currency.
- Applied Alembic migration `e2f3a4b5c6d7_wallet_ledger_exact_money.py`.
- Automated test suite: `tests/test_wallet_ledger.py` (7 tests covering reservation, refund, credit, capture, idempotency, and admin view restrictions).

### Item 17 — durable & safe multi-process background work  ✅ DONE
- Distributed Leader Leases & Locks (`services/distributed_lock.py`):
  - `DistributedLock` supporting Redis (with token-matched Lua release) and automatic PostgreSQL advisory lock fallback (`pg_try_advisory_lock` with signed 64-bit key hashing).
  - `leader_lease(job_name)` context manager ensuring only one worker process runs singleton background cron jobs.
  - `order_lock(order_id)` and `sms_lock(activation_id)` context managers preventing concurrent double-processing of individual orders or SMS activations across worker processes.
- Applied Leader Leases across background jobs:
  - `periodic_catalog_sync` (1-hour leader lease).
  - `periodic_balance_monitor` (15-minute leader lease).
  - `daily_digest_cron` (24-hour leader lease in `services/financial_digest.py`).
  - `periodic_backup_cron` (24-hour leader lease in `services/backup_service.py`).
- Atomic Order Job Claiming:
  - `OrderRepository.get_pending(..., skip_locked=True)` adding `FOR UPDATE SKIP LOCKED` support to eliminate duplicate polling across concurrent transactions.
  - Per-order distributed lock in `poll_pending_orders` and per-activation lock in `poll_pending_sms_activations`.
- Queue Age Monitoring (> 30 min escalation):
  - `poll_pending_orders` monitors order creation age. Pending orders older than 30 minutes trigger admin escalation warnings with rate-limited deduplicated alerts (`NotificationService.send_error_to_admins`).
- Provider Failure Tracking (`services/provider_health.py`):
  - `ProviderHealthTracker` tracks consecutive failures per upstream provider (`batstore`, `prodseller`, `g2bulk`, `5sim`).
  - Successful API/status calls reset the failure counter to 0.
  - Consecutive failures $\ge 5$ trigger deduplicated high-priority admin alerts with recent error message (window: 30 minutes).
- Automated test suite: `tests/test_distributed_workers.py` (9 tests covering key hashing, Redis lock/release, Postgres fallback, contention, leader lease, order lock, provider failure escalation, skip-locked queries, and queue age monitoring).

### Item 18 — executable, protected, and recoverable backups  ✅ DONE
- Container Environment:
  - `Dockerfile`: Runtime stage copies PostgreSQL 18 client utilities (`pg_dump`, `pg_restore`, `psql`) directly from `postgres:18` image and installs `postgresql-client` and `curl`. Eliminates server/client major version mismatches.
  - `docker-compose.yml`: Mounted `./backups:/bot/backups` volume on `bot` service for persistent storage on the host.
  - `requirements.txt`: Added `cryptography>=42.0.0`.
- Cryptographic Engine (`services/backup_crypto.py`):
  - Authenticated AES-256-GCM encryption (`encrypt_payload`, `decrypt_payload`) with PBKDF2-HMAC-SHA256 (100,000 iterations) key derivation from `BACKUP_ENCRYPTION_KEY`.
  - Random 16-byte salt and 12-byte nonce generated per archive with tamper detection (GCM 16-byte authentication tag).
  - Generates companion standard SHA-256 checksum manifest files (`<archive>.sha256`) via `compute_sha256` and `write_sha256_manifest`.
- Automated Backup Tool (`scripts/backup_db.py`):
  - Dumps PostgreSQL via native `pg_dump` or `docker exec GHstore-postgres pg_dump` fallback.
  - Compresses with gzip and encrypts with AES-256-GCM into `ghstore_backup_<timestamp>.sql.gz.enc`.
  - Automatic archive rotation (`rotate_old_backups`) retaining last $N$ archives and pruning older `.sha256` manifests.
  - Streams encrypted archives and checksum manifests to Cloudflare R2 / AWS S3 buckets.
  - `services/backup_service.py` streams encrypted archives and SHA-256 checksum digests directly to Telegram backup channel (`BACKUP_CHANNEL_ID`).
- Verified Restoration Tool (`scripts/restore_db.py`):
  - Supports `--verify-only` mode (checks SHA-256 manifest and AES-GCM tag without database writes).
  - Supports `--decrypt-only` mode (extracts plain SQL for manual inspection).
  - Interactive safety confirmation (`Type 'YES' to proceed`) before modifying database, with `--force` option for automated scripting.
  - Restores via local `psql` or `docker exec -i GHstore-postgres psql`.
- Automated test suite: `tests/test_backup_restore.py` (12 tests covering key derivation, round-trip encryption/decryption, wrong key rejection, tampering detection, manifest verification, rotation, plain gzip fallback, and Telegram streaming).

### Item 19 — fix tests protecting incorrect behavior & live integration tests  ✅ DONE
- Replaced incorrect assertions:
  - Verified and asserted strict production auth rules in `tests/test_new_enhancements.py` and `tests/test_telegram_auth_security.py` (unauthenticated claimed IDs are strictly rejected with 401 Unauthorized; session mismatch rejected with 403).
- Real Database & Redis Integration Test Suite (`tests/test_integration_scenarios.py`):
  - Runs directly against live PostgreSQL (`ghstore`) and Redis instances using `NullPool` isolation and auto-cleanup fixtures.
  - Scenario 1 (Duplicate purchases & idempotency): Replaying checkouts with same idempotency key returns the existing order with `created=False` and strictly prevents double-debiting user balance; conflicting request bodies trigger HTTP 409 `idempotency_key_conflict`.
  - Scenario 2 (Timeout-after-acceptance): Order fulfillment timeout leaves durable order in `pending_fulfillment` with funds safely reserved; background poller or manual review claims order with `FOR UPDATE SKIP LOCKED`, completes fulfillment, and records `capture` ledger row with wholesale supplier cost.
  - Scenario 3 (Webhook vs. Poller Concurrency Race): Concurrent tasks simulate webhook and background poller arriving at the same millisecond; serialized by `order_lock(order_id)` and PostgreSQL row locks (`with_for_update`), guaranteeing exactly one transition to `completed` and exactly one capture ledger entry without duplication or data loss.
  - Scenario 4 (Variant mismatches & price tampering): Rejects forged variant selectors, unauthorized variant modifications, and out-of-stock variants with HTTP 400 without debiting user funds or generating ledger entries.
  - Scenario 5 (Mixed-success multi-item carts): Multi-item cart checkout where Item 1 completes and Item 2 fails; triggers automatic atomic partial refund for Item 2, sets order status to `partially_completed`, and records exact `reservation`, `capture`, and `refund` ledger rows.
- Test Suite Health: 342 pytest tests passed (100%), 118 storefront security checks passed, 46 storefront browser checks passed, zero errors across all 267 Python files.

### Deployment
- Migrations run manually (`alembic upgrade head`) — entrypoint does **not** run them.
- DB currently at head `e2f3a4b5c6d7` (migrations `a7b8c9d0e1f2` checkout idempotency,
  `f5e6d7c8b9a0` session revocation, `c9d8e7f6a5b4` approved equivalents, `d1e2f3a4b5c6` sms activations, `e2f3a4b5c6d7` wallet ledger exact money applied).
- Redeploy:
  ```bash
  git push origin master
  .venv/bin/alembic upgrade head
  docker compose build bot && docker compose up -d bot
  curl -s http://localhost:5000/health    # expect 200, postgres+redis connected
  ```

### Known notes / invariants
- Python 3.12: `datetime.utcnow()` removed → use `datetime.datetime.now(datetime.timezone.utc)`.
- `routes.tma_admin.py` binds `get_db_session` at import → tests patch `admin_routes.get_db_session`;
  the revocation middleware lazy-imports `db.get_db_session` at request time.
- `models/withdrawal.py` holds only `WithdrawalDTO` (no ORM class — not in `models/__init__.py`);
  `models/batstore_order.py` / `batstore_product.py` are backward-compat proxies.
- G2Bulk `/games/servers` upstream 403s in logs are expected (plan/rate limits); catalogue & fields return 200.
