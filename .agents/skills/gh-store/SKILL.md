---
name: gh-store
description: Architecture, operational runbook, fulfillment models, payment rails, animated icons, and change-verification workflow for the GH Store Telegram bot.
globs:
  - "**/*.py"
  - "i18n/*.json"
  - "docker-compose.yml"
---

# GH Store Telegram Bot — Architecture & Change Runbook

This skill is the single source of truth for working with the **GH Store** Telegram shop bot (`gh-store-tele`). It eliminates the need to inspect every file from scratch on new tasks or sessions.

---

## 1. Quick Architecture & Entry Points

GH Store is an e-commerce Telegram reseller bot built on **Aiogram 3.14**, **FastAPI 0.115**, **SQLAlchemy 2.0 (asyncpg)**, **PostgreSQL 18**, **Redis 6**, and **SQLAdmin 0.22**.

```
Telegram / Client
       │ (Webhook)
Cloudflare Tunnel (gh-store.me) / Worker (bot.gh-store.me)
       │
   FastAPI (bot.py:5000)
   ├── Aiogram Dispatcher (dp / run.py)
   │     ├── Handlers (user/, admin/, common/)
   │     ├── Middleware (DBSession, I18n, Throttling)
   │     └── Services & Repositories
   ├── Webhook Endpoints
   │     ├── POST /webhook           (Telegram updates)
   │     ├── POST /cryptoprocessing  (KryptoExpress crypto events)
   │     └── POST /samwebhook        (sam-api.pro Syriatel/ShamCash invoices)
   ├── Monitoring & Health
   │     ├── GET /health & /status   (DB & Redis connectivity check)
   │     └── Daily P&L Digest        (Automated 24h executive summary)
   ├── SQLAdmin Web Panel (/admin)
   └── Background Tasks (order_polling.py, catalog sync, balance monitor, digest cron)
```

### Primary Entry Points
- `run.py`: Aiogram router assembly, root `/start` & `/help`, global error handling, middleware injection.
- `bot.py`: FastAPI app, lifespan setup/teardown, webhooks, `/health`, SQLAdmin views registration, background tasks.
- `config.py`: Environment variable loading, currency presets, API keys, webhook URLs.
- `db.py`: Async SQLAlchemy engine (`pool_size=20`, `max_overflow=20`, `pool_pre_ping=True`), session maker, `get_db_session()`, `session_commit()`.
- `scripts/inspect_project.py`: Automated instant project health and delta checker.

---

## 2. The Dual-Fulfillment Model (Crucial Invariant)

The codebase has **two distinct fulfillment flows**:

| Feature | Static Stock (Upstream Shop) | BatStore / VenteBot Reseller (GH Store) |
|---|---|---|
| **Inventory Source** | Pre-loaded in `items` table | Fetched on-demand from Reseller API |
| **Stock Model** | `Item.is_sold = True` on purchase | Virtual upstream stock (`p.stock`) |
| **Cart/Checkout** | Multi-item cart (`services/cart.py`) | Instant checkout (`services/batstore_store.py`) |
| **Pricing** | Fixed unit price in DB | `cost_usd * (1 + margin%) + margin_fixed` |
| **Delivery** | Immediate `private_data` string | Immediate (stock/supplier_api) or Async Activation |
| **Order Table** | `buys` + `buyItem` | `batstore_orders` (`status: completed \| pending_fulfillment \| requires_manual_review`) |

> **Rule:** Never repurpose `Item.is_sold` for BatStore products. BatStore catalog products live in `batstore_products`, synced from `GET /products` by `BatStoreService.sync_catalog()`.

---

## 3. Animated Product Icons & Custom Emoji System

The bot automatically identifies digital services and renders **animated custom Telegram emojis**:
- **Keyword Auto-Detection**: `models.batstore_product.auto_detect_icon(name)` inspects product naming patterns (e.g. `api 500m xx claude 1d`, `1mo claude` -> Claude icon, `gemini` -> Gemini icon, `chatgpt` -> ChatGPT icon, `netflix`, `nordvpn`, `spotify`, etc.).
- **Dual Format Support**:
  - **Message Text / Captions**: Renders `<tg-emoji emoji-id="{custom_emoji_id}">{fallback_emoji}</tg-emoji>` (Telegram renders animated sticker emoji).
  - **Keyboard Buttons**: Renders `{fallback_emoji}` (plain UTF-8 emoji for button text).
- **Admin Customization**: Admins can override `emoji` and `custom_emoji_id` per product in SQLAdmin (`BatStoreProductAdmin`). Sync retains custom overrides.

---

## 4. Payment Rails & Balance Invariants

Users fund a fiat USD balance (`user.top_up_amount`). Net spendable balance is:
$$\text{Available Balance} = \text{user.top_up_amount} - \text{user.consume_records}$$

There are **three balance top-up rails**:

1. **Crypto (KryptoExpress SDK)**:
   - Flow: `handlers/user/my_profile.py` → `services/payment.py` creates invoice → User pays on-chain → Webhook `POST /cryptoprocessing/event` (`processing/processing.py`) verifies `X-Signature` → Creates `Deposit` row & credits `user.top_up_amount`.
2. **Telegram Stars (Native Stars API)**:
   - Flow: `handlers/user/stars.py` → User selects Star preset → `bot.create_invoice_link` (currency `XTR`) → User pays → `F.successful_payment` handler checks `StarsPaymentRepository.get_by_charge_id()` for idempotency → Credits balance & applies referral rewards via `ReferralService.apply_deposit_referral()`.
3. **SAM API (Syriatel Cash & ShamCash)**:
   - Flow: `handlers/user/sam.py` → `SamService.create_invoice()` (`POST /v1/invoices` on `sam-api.pro`) → Sends payment web URL → Payer completes → Webhook `POST /samwebhook` (`bot.py`) receives `invoice.paid` → Credits balance & applies referral rewards via `ReferralService.apply_deposit_referral()`.

### Atomic Balance Deductions
`UserRepository.try_debit_balance(telegram_id, amount, session)` executes an atomic SQL query:
```sql
UPDATE users
SET consume_records = COALESCE(consume_records, 0) + :amount
WHERE telegram_id = :tg_id AND (COALESCE(top_up_amount, 0) - COALESCE(consume_records, 0)) >= :amount
RETURNING id;
```
If upstream supplier placement fails, `UserRepository.refund_balance(telegram_id, amount, session)` restores user funds.

---

## 5. Background Workers & Resilience

1. **Order Polling (`services/order_polling.py:poll_pending_orders`)**:
   - Polls `batstore_orders` with `status = 'pending_fulfillment'` every 60s.
   - Per-order network timeout of 15s (`asyncio.wait_for`).
   - If attempts exceed 10, marks order `requires_manual_review` and alerts admins with upstream reference.
2. **Periodic Catalog Auto-Sync (`services/order_polling.py:periodic_catalog_sync`)**:
   - Syncs BatStore catalog every 60m to maintain current prices and stock.
   - **Price Spike Circuit Breaker**: If wholesale cost increases by >30%, product is automatically hidden (`hidden=True`) and admins receive an alert to review margins.
3. **Low Reseller Balance Monitor (`services/order_polling.py:periodic_balance_monitor`)**:
   - Checks `BatStoreService.me()` every 15m.
   - Alerts admins once if reseller wallet balance drops below $5.00 (resets only after top-up).
4. **Daily Financial Digest (`services/financial_digest.py:daily_digest_cron`)**:
   - Calculates 24h P&L (Crypto, Stars, SAM deposits, gross revenue, wholesale supplier costs, net profit, new signups) and alerts admins daily. Also available on-demand in `/admin`.

---

## 6. Instant Change Verification Runbook

Whenever code is touched in this repository, **NEVER manually re-read every file**. Instead, run the project inspector:

```bash
# Run inside container:
docker run --rm -v "$(pwd):/app" -w /app ghstore-bot python scripts/inspect_project.py

# Or on host:
python scripts/inspect_project.py
```
Checks:
1. Python syntax & unbound variables across all files.
2. i18n key completeness across all 7 languages (`en`, `ar`, `de`, `es`, `fr`, `it`, `zh`).
3. Model and table registrations on `Base.metadata` (21 tables).
4. Configuration key parity between `.env.template` and `config.py`.
5. Full unit test suite execution (145 tests).
