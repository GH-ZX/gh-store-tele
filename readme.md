# 🛍️ GH Store — Modern Telegram E-Commerce Bot & Mini App

<p align="center">
  <strong>High-performance digital products storefront, automated key fulfillment, and multi-currency top-up powered by Aiogram 3, FastAPI, and Telegram Mini Apps.</strong>
</p>

<p align="center">
  <a href="https://t.me/ahmedghxx">
    <img src="https://img.shields.io/badge/Developer-Ahmed_GH-0088cc?logo=telegram&logoColor=white" alt="Developer Telegram"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Aiogram-3.31-2CA5E0?logo=telegram&logoColor=white" alt="Aiogram 3.31"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-18-336791?logo=postgresql&logoColor=white" alt="PostgreSQL 18"/>
  <img src="https://img.shields.io/badge/Redis-6.0-DC382D?logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/Tooling-uv-DE5FE9?logo=astral&logoColor=white" alt="uv"/>
</p>

---

## 🌟 Overview

**GH Store** is a full-featured automated digital goods store and reseller platform built for Telegram. It combines a conversational Telegram bot with a modern, high-speed **Telegram Mini App (TMA)** storefront, enabling customers to browse digital services, manage carts, top up balances, and receive instant digital delivery directly inside Telegram.

Built with **Python 3.12**, **Aiogram 3.31**, **FastAPI**, **SQLAlchemy 2.0 async**, and powered by **uv** for lightning-fast builds and test execution.

---

## ✨ Key Features

### 🛍️ Modern Telegram Mini App (TMA) Storefront
- **Responsive Mobile-First UI**: Dark and light mode themes, glassmorphism design, and touch gestures.
- **Smart Catalog & Search**: Real-time filtering across streaming, AI tools, gaming, and subscription categories with auto-categorization.
- **In-App Cart Drawer**: Multi-item cart, live quantity management, warranty indicators, and instant balance checkout.
- **Activity & Orders Tracker**: In-app purchase history, 1-tap license key copying, and warranty status tracking.

### 💳 Multi-Currency Recharge & Payments
- **USDT (BEP-20 / BNB Smart Chain)**: Direct blockchain top-ups with instant copyable deposit addresses, QR codes, and BscScan explorer verification.
- **Telegram Stars**: Official in-app Telegram Stars billing with automatic payment confirmation.
- **Syrian Local Methods (SAM API)**: Full support for **Sham Cash** and **Syriatel Cash** with live Syrian Pound (SYP/USD) conversion.
- **Native 1-Tap Copying**: Telegram Bot API 8.0 `CopyTextButton` support in chat payments.

### ⚙️ Automated Reseller Operations
- **BatStore & SAM Reseller Integration**: Automated product catalog synchronization, stock tracking, and supplier order placement.
- **Out-of-Stock Protection & Restock Alerts**: Visual stock status indicators with 1-tap notification alerts when products are replenished.
- **Automated Order Polling**: Continuous background verification with automatic user refunds if supplier fulfillment encounters issues.

### 🛡️ Admin Control Center
- **In-App Control Center**: Live store statistics (revenue, active users, total orders, user balances).
- **Supplier Wallets Monitor**: Live real-time balance tracker for BatStore and SAM (USD and SYP) with on-demand refresh.
- **Dynamic Rates & Pricing**: Live SYP/USD exchange rate controls and global margin percentage adjustments.
- **Web Admin Panel**: Full SQLAdmin dashboard at `/admin` for low-level database inspection and management.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Bot Framework** | [Aiogram 3.31](https://github.com/aiogram/aiogram) (Telegram Bot API 8.0+) |
| **Web & API Backend** | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| **Database & ORM** | [PostgreSQL 18](https://www.postgresql.org/) + [SQLAlchemy 2.0 (Async)](https://www.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/) |
| **Caching & FSM** | [Redis](https://redis.io/) (Aiogram FSM storage, rate limiting, and event queues) |
| **Web Admin** | [SQLAdmin](https://github.com/aminalaee/sqladmin) (Session-authenticated dashboard) |
| **Package Management** | [uv](https://github.com/astral-sh/uv) by Astral |
| **Containerization** | Docker + Docker Compose + Cloudflare Tunnel |

---

## ⚡ Quick Start

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Python 3.12+ (optional, for local development outside Docker)

### 2. Clone & Configure
```bash
git clone https://github.com/GH-ZX/gh-store-tele.git
cd gh-store-tele

# Copy template and configure your secrets
cp .env.template .env
nano .env
```

Key environment variables to configure in `.env`:
```ini
TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
ADMIN_ID_LIST=[123456789]
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=postgres
REDIS_PASSWORD=your_redis_password
WEBHOOK_HOST=https://bot.yourdomain.com
KRYPTO_EXPRESS_API_KEY=your_key
BATSTORE_API_KEY=your_key
SAM_API_KEY=your_key
```

### 3. Launch with Docker Compose
```bash
docker compose -p ghstore up -d --build
```

View live container logs:
```bash
docker logs -f GHstore
```

---

## 🧪 Local Testing & Health Check

Run the comprehensive project diagnostic tool (powered by `uv`):
```bash
# Run all AST syntax checks, i18n key audits, and unit tests
uv run python scripts/inspect_project.py

# Or run pytest directly
uv run pytest
```

---

## 📬 Contact & Support

Developed and maintained by **Ahmed GH**:

- **Telegram**: [@ahmedghxx](https://t.me/ahmedghxx)
- **Project Repository**: [github.com/GH-ZX/gh-store-tele](https://github.com/GH-ZX/gh-store-tele)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
