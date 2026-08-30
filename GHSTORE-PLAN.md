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
