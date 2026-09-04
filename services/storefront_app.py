"""Telegram Mini App (TMA) Mobile-First Storefront.

Features:
- Glassmorphic, iOS-style bottom navigation bar with safe-area notch padding.
- Homepage Catalog Cards Grid (categories as distinct collections with item counts, starting prices, preview tags).
- Category drill-down with '← All Catalogs' navigation.
- Dedicated in-app Product Page with live balance check, quantity stepper, VIP discounts, and instant in-app checkout (POST /api/buy) — no text chat redirect!
- In-app Order Success screen with 1-tap copyable credentials.
- Real Telegram user profile picture and username integration.
- Orders page with robust loading/empty states, 1-tap copyable license keys, and in-app warranty claims.
- Client-side multi-language translation and RTL support for Arabic.
"""

STOREFRONT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>GH Store</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      --bg: var(--tg-theme-bg-color, #0a0f1d);
      --text: var(--tg-theme-text-color, #f8fafc);
      --hint: var(--tg-theme-hint-color, #94a3b8);
      --btn: var(--tg-theme-button-color, #38bdf8);
      --btn-text: var(--tg-theme-button-text-color, #04121d);
      --card: var(--tg-theme-secondary-bg-color, #172033);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #38bdf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --nav-height: 52px;
      --safe-bottom: env(safe-area-inset-bottom, 20px);
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding-bottom: calc(var(--nav-height) + var(--safe-bottom) + 24px);
      user-select: none;
      -webkit-user-select: none;
      overflow-x: hidden;
    }

    /* Top Sticky Navigation Bar */
    .top-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      background: rgba(10, 15, 29, 0.88);
      border-bottom: 0.5px solid var(--border);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .user-avatar-img {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      object-fit: cover;
      border: 1.5px solid var(--accent);
      cursor: pointer;
    }
    .user-avatar-fallback {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #6366f1);
      color: white;
      font-size: 15px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .header-titles h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .header-titles span {
      font-size: 11px;
      color: var(--hint);
      font-weight: 500;
    }
    .header-balance {
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent);
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
    }
    .vip-chip {
      background: rgba(245, 158, 11, 0.15);
      color: #f59e0b;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
    }

    /* Views */
    .view-content {
      padding: 16px;
      display: none;
      animation: fadeIn 0.2s ease-out;
    }
    .view-content.active { display: block; }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Search Bar */
    .search-box {
      position: relative;
      margin-bottom: 16px;
    }
    .search-box input {
      width: 100%;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      color: var(--text);
      padding: 12px 16px 12px 40px;
      font-size: 14px;
      outline: none;
    }
    .search-box input:focus { border-color: var(--accent); }
    .search-icon {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 15px;
      color: var(--hint);
    }
    .clear-search {
      position: absolute;
      right: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--hint);
      cursor: pointer;
      display: none;
    }

    /* Catalog Cards Grid (Homepage Collections) */
    .catalogs-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }
    @media (min-width: 480px) {
      .catalogs-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .catalog-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      transition: transform 0.15s, border-color 0.15s;
    }
    .catalog-card:active {
      transform: scale(0.98);
      border-color: var(--accent);
    }
    .catalog-left {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1;
      overflow: hidden;
    }
    .catalog-icon {
      font-size: 28px;
      width: 48px;
      height: 48px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .catalog-info {
      flex: 1;
      overflow: hidden;
    }
    .catalog-title {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .catalog-meta {
      font-size: 12px;
      color: var(--hint);
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .catalog-arrow {
      color: var(--hint);
      font-size: 18px;
      margin-left: 10px;
    }

    /* Products View (inside a catalog) */
    .subview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .back-catalog-btn {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--accent);
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }
    .subview-title {
      font-size: 16px;
      font-weight: 700;
    }

    /* Product Cards */
    .products-list {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    .product-item {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
      transition: transform 0.15s, border-color 0.15s;
    }
    .product-item:active {
      transform: scale(0.99);
      border-color: var(--accent);
    }
    .item-left {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      overflow: hidden;
    }
    .item-icon {
      font-size: 26px;
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .item-details {
      flex: 1;
      overflow: hidden;
    }
    .item-name {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .item-sub {
      font-size: 12px;
      color: var(--hint);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .item-right {
      text-align: right;
      flex-shrink: 0;
    }
    .item-price {
      font-size: 16px;
      font-weight: 800;
      color: var(--accent);
    }
    .item-stock {
      font-size: 11px;
      color: var(--hint);
      margin-top: 2px;
    }

    /* Dedicated In-App Product Detail Page */
    .product-page-hero {
      text-align: center;
      padding: 20px 0;
      background: radial-gradient(circle at center, rgba(56, 189, 248, 0.12), transparent 70%);
      border-radius: 20px;
      margin-bottom: 16px;
    }
    .product-page-icon {
      font-size: 54px;
      margin-bottom: 10px;
    }
    .product-page-name {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.3px;
      margin-bottom: 6px;
    }
    .product-page-cat {
      font-size: 12px;
      color: var(--accent);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .info-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 14px;
    }
    .info-title {
      font-size: 12px;
      color: var(--hint);
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .info-body {
      font-size: 14px;
      line-height: 1.5;
      color: var(--text);
    }
    .badges-row {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .feature-badge {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .price-box {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .price-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .price-large {
      font-size: 26px;
      font-weight: 800;
      color: var(--accent);
    }
    .qty-stepper {
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 4px 10px;
    }
    .qty-btn {
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 16px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .qty-val { font-size: 15px; font-weight: 700; }
    .btn-checkout {
      width: 100%;
      background: var(--btn);
      color: var(--btn-text);
      border: none;
      border-radius: 14px;
      padding: 16px;
      font-size: 16px;
      font-weight: 800;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: transform 0.15s, opacity 0.15s;
    }
    .btn-checkout:active { transform: scale(0.98); }
    .insufficient-box {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
      text-align: center;
      font-size: 13px;
      color: #fca5a5;
    }

    /* Order Success Page */
    .success-hero {
      text-align: center;
      padding: 30px 16px;
    }
    .success-icon { font-size: 64px; margin-bottom: 14px; }
    .success-title { font-size: 24px; font-weight: 800; margin-bottom: 6px; }
    .success-sub { font-size: 13px; color: var(--hint); margin-bottom: 20px; }

    /* Orders Tab */
    .order-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 12px;
    }
    .order-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .status-tag {
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 10px;
      text-transform: uppercase;
    }
    .status-completed { background: rgba(16, 185, 129, 0.15); color: var(--success); }
    .status-pending { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
    .status-failed { background: rgba(239, 68, 68, 0.15); color: var(--danger); }
    .key-box {
      background: rgba(0, 0, 0, 0.35);
      border: 1px dashed rgba(56, 189, 248, 0.4);
      border-radius: 10px;
      padding: 12px;
      font-family: monospace;
      font-size: 13px;
      color: #38bdf8;
      word-break: break-all;
      margin: 8px 0;
      cursor: pointer;
    }
    .key-box:active { background: rgba(56, 189, 248, 0.15); }

    /* Wallet Tab */
    .wallet-banner {
      background: linear-gradient(135deg, #1e293b 0%, #0b1120 100%);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 20px;
      padding: 24px;
      text-align: center;
      margin-bottom: 20px;
    }
    .wallet-hero-amount {
      font-size: 36px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin: 6px 0;
    }
    .presets-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 20px;
    }
    .preset-pill {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 0;
      font-size: 14px;
      font-weight: 700;
      text-align: center;
      cursor: pointer;
    }
    .preset-pill:active { background: var(--btn); color: var(--btn-text); }
    .rail-item {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      cursor: pointer;
    }
    .rail-item:active { border-color: var(--accent); }

    /* Settings Tab */
    .settings-profile-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .settings-group {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 14px;
    }
    .group-title {
      font-size: 12px;
      color: var(--hint);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 10px;
    }
    .segment-chips {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .seg-chip {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }
    .seg-chip.active {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent);
      color: var(--accent);
    }
    .referral-container {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 10px;
    }

    /* iPhone Bottom Tab Bar */
    .iphone-navbar {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: calc(var(--nav-height) + var(--safe-bottom));
      padding-bottom: var(--safe-bottom);
      background: rgba(10, 15, 29, 0.88);
      backdrop-filter: blur(28px) saturate(190%);
      -webkit-backdrop-filter: blur(28px) saturate(190%);
      border-top: 0.5px solid rgba(255, 255, 255, 0.12);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
    }
    .tab-btn {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: #8e8e93;
      cursor: pointer;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .tab-btn.active {
      color: #38bdf8;
      transform: scale(1.04);
    }
    .tab-btn .tab-icon {
      font-size: 21px;
      line-height: 1;
    }
    .tab-btn .tab-label {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: -0.2px;
    }

    /* Toast */
    .toast-pill {
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%) translateY(-100px);
      background: rgba(16, 185, 129, 0.95);
      color: white;
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      z-index: 200;
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    }
    .toast-pill.show { transform: translateX(-50%) translateY(0); }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header class="top-header">
    <div class="header-left">
      <div id="header-avatar-box" onclick="switchTab('settings')">
        <div class="user-avatar-fallback" id="header-avatar-initial">U</div>
      </div>
      <div class="header-titles">
        <h1 id="i18n-brand">🛍️ GH Store <span class="vip-chip" id="header-vip-tag" style="display: none;">VIP</span></h1>
        <span id="header-sub-label">Verified Digital Reseller</span>
      </div>
    </div>
    <div class="header-balance" onclick="switchTab('wallet')">
      <span id="top-balance-val">$0.00</span>
      <span style="font-size: 10px;">➕</span>
    </div>
  </header>

  <!-- TAB 1: STORE VIEW -->
  <section id="view-store" class="view-content active">
    <!-- Global Search -->
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="global-search" placeholder="Search ChatGPT, Claude, Gemini, Netflix..." oninput="onSearchInput()">
      <span class="clear-search" id="clear-search-btn" onclick="clearSearch()">✕</span>
    </div>

    <!-- Mode A: Catalogs Cards Grid (Homepage Collections) -->
    <div id="catalogs-mode">
      <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--hint); margin: 0 0 12px 2px;" id="i18n-catalogs-title">
        Featured Collections
      </div>
      <div class="catalogs-grid" id="catalogs-grid"></div>
    </div>

    <!-- Mode B: Products in Selected Catalog (or Search Results) -->
    <div id="products-mode" style="display: none;">
      <div class="subview-header">
        <button class="back-catalog-btn" onclick="returnToCatalogs()">
          <span>←</span>
          <span id="i18n-all-catalogs">All Catalogs</span>
        </button>
        <div class="subview-title" id="active-catalog-title">Catalog</div>
      </div>
      <div class="products-list" id="products-list"></div>
    </div>
  </section>

  <!-- DEDICATED IN-APP PRODUCT DETAIL PAGE -->
  <section id="view-product-detail" class="view-content">
    <div class="subview-header">
      <button class="back-catalog-btn" onclick="backFromProductPage()">
        <span>←</span>
        <span>Back</span>
      </button>
      <div class="subview-title" id="product-page-cat">Product</div>
    </div>

    <div class="product-page-hero">
      <div class="product-page-icon" id="page-icon">⚡</div>
      <h2 class="product-page-name" id="page-name">Product Name</h2>
      <div class="product-page-cat" id="page-category">Category</div>
    </div>

    <div class="badges-row">
      <div class="feature-badge" id="page-delivery-badge">⚡ Instant Automated Delivery</div>
      <div class="feature-badge" id="page-warranty-badge">🛡️ 30 Days Warranty</div>
      <div class="feature-badge" id="page-stock-badge">🟢 In Stock</div>
    </div>

    <div class="info-card">
      <div class="info-title">Description</div>
      <div class="info-body" id="page-desc">Instant automated license key delivery.</div>
    </div>

    <div class="price-box">
      <div class="price-row">
        <div>
          <div style="font-size: 12px; color: var(--hint); text-transform: uppercase;">Total Price</div>
          <div class="price-large" id="page-total-price">$0.00</div>
          <div style="font-size: 12px; color: var(--success); font-weight: 700;" id="page-discount-line"></div>
        </div>
        <div class="qty-stepper">
          <div class="qty-btn" onclick="stepQty(-1)">-</div>
          <span class="qty-val" id="page-qty">1</span>
          <div class="qty-btn" onclick="stepQty(1)">+</div>
        </div>
      </div>

      <div id="insufficient-alert" class="insufficient-box" style="display: none;">
        <div>⚠️ <b>Insufficient Balance</b></div>
        <div id="insufficient-text" style="margin-top: 4px;">You need $10.00 more.</div>
      </div>

      <button class="btn-checkout" id="page-buy-btn" onclick="executeInAppBuy()">
        <span>⚡ Instant Buy</span>
        <span id="btn-price-label">($0.00)</span>
      </button>
    </div>
  </section>

  <!-- IN-APP ORDER SUCCESS VIEW -->
  <section id="view-order-success" class="view-content">
    <div class="success-hero">
      <div class="success-icon">🎉</div>
      <h2 class="success-title">Order Successful!</h2>
      <p class="success-sub" id="success-order-sub">Order #000 · Completed</p>
    </div>

    <div class="info-card">
      <div class="info-title">Delivered License / Credentials</div>
      <div id="success-keys-container"></div>
      <div style="font-size: 11px; color: var(--hint); text-align: center; margin-top: 6px;">
        Tap on credentials above to copy instantly!
      </div>
    </div>

    <div style="display: flex; gap: 10px;">
      <button class="btn-checkout" onclick="switchTab('orders')" style="background: var(--card); color: var(--text); border: 1px solid var(--border);">
        📦 View in Orders
      </button>
      <button class="btn-checkout" onclick="switchTab('store')">
        🛍️ Continue Shopping
      </button>
    </div>
  </section>

  <!-- TAB 2: ORDERS VIEW -->
  <section id="view-orders" class="view-content">
    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--hint); margin: 0 0 12px 2px;">
      Your Purchases
    </div>
    <div id="orders-list"></div>
  </section>

  <!-- TAB 3: WALLET VIEW -->
  <section id="view-wallet" class="view-content">
    <div class="wallet-banner">
      <div style="font-size: 12px; color: var(--hint); text-transform: uppercase; letter-spacing: 1px;">Account Balance</div>
      <div class="wallet-hero-amount" id="wallet-balance-num">$0.00</div>
      <div style="font-size: 13px; color: var(--accent); font-weight: 600;" id="wallet-alt-curr">Available for instant purchases</div>
    </div>

    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--hint); margin: 0 0 10px 2px;">
      Quick Deposit Amounts
    </div>
    <div class="presets-row">
      <div class="preset-pill" onclick="sendBotTopup(10)">+$10</div>
      <div class="preset-pill" onclick="sendBotTopup(25)">+$25</div>
      <div class="preset-pill" onclick="sendBotTopup(50)">+$50</div>
      <div class="preset-pill" onclick="sendBotTopup(100)">+$100</div>
    </div>

    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--hint); margin: 0 0 10px 2px;">
      Payment Channels
    </div>
    <div class="rail-item" onclick="launchBotRail('stars')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">⭐</span>
        <div>
          <div style="font-size: 15px; font-weight: 700;">Telegram Stars</div>
          <div style="font-size: 12px; color: var(--hint);">Instant in-app payment with Apple / Google Pay</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>

    <div class="rail-item" onclick="launchBotRail('crypto')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">🪙</span>
        <div>
          <div style="font-size: 15px; font-weight: 700;">Cryptocurrency</div>
          <div style="font-size: 12px; color: var(--hint);">BTC, USDT, SOL, LTC, DOGE via KryptoExpress</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>

    <div class="rail-item" onclick="launchBotRail('sam')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">📱</span>
        <div>
          <div style="font-size: 15px; font-weight: 700;">SAM Syriatel & ShamCash</div>
          <div style="font-size: 12px; color: var(--hint);">Direct Syrian mobile wallet payment</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>
  </section>

  <!-- TAB 4: SETTINGS VIEW -->
  <section id="view-settings" class="view-content">
    <div class="settings-profile-card">
      <div id="settings-avatar-box">
        <div class="user-avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">U</div>
      </div>
      <div>
        <div style="font-size: 17px; font-weight: 800;" id="user-display-name">Customer</div>
        <div style="font-size: 12px; color: var(--hint); font-family: monospace;" id="user-tg-id">ID: 000000000</div>
        <div style="margin-top: 4px;" id="user-vip-badge"></div>
      </div>
    </div>

    <div class="settings-group">
      <div class="group-title">💱 Display Currency Preference</div>
      <div class="segment-chips" id="currency-chips">
        <div class="seg-chip" onclick="updateCurrencyPref('USD')">USD ($)</div>
        <div class="seg-chip" onclick="updateCurrencyPref('EUR')">EUR (€)</div>
        <div class="seg-chip" onclick="updateCurrencyPref('SYP')">SYP (ل.س)</div>
        <div class="seg-chip" onclick="updateCurrencyPref('XTR')">Stars (⭐)</div>
      </div>
    </div>

    <div class="settings-group">
      <div class="group-title">🌐 Language / اللغة</div>
      <div class="segment-chips" id="language-chips">
        <div class="seg-chip" onclick="updateLanguagePref('en')">English</div>
        <div class="seg-chip" onclick="updateLanguagePref('ar')">العربية</div>
        <div class="seg-chip" onclick="updateLanguagePref('de')">Deutsch</div>
        <div class="seg-chip" onclick="updateLanguagePref('es')">Español</div>
        <div class="seg-chip" onclick="updateLanguagePref('fr')">Français</div>
        <div class="seg-chip" onclick="updateLanguagePref('it')">Italiano</div>
        <div class="seg-chip" onclick="updateLanguagePref('zh')">中文</div>
      </div>
    </div>

    <div class="settings-group">
      <div class="group-title">🎁 Invite & Earn Referral Link</div>
      <div style="font-size: 12px; color: var(--hint); margin-bottom: 8px;">
        Earn instant balance rewards on every deposit your referrals make!
      </div>
      <div class="referral-container">
        <span id="ref-link-display" style="font-family: monospace; font-size: 12px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 8px;">https://t.me/...</span>
        <button class="back-catalog-btn" onclick="copyRefLink()" style="flex: none;">Copy</button>
      </div>
    </div>
  </section>

  <!-- iPhone-style Bottom Navigation Bar -->
  <nav class="iphone-navbar">
    <div class="tab-btn active" id="tab-nav-store" onclick="switchTab('store')">
      <div class="tab-icon">🛍️</div>
      <div class="tab-label" id="i18n-tab-store">Store</div>
    </div>
    <div class="tab-btn" id="tab-nav-orders" onclick="switchTab('orders')">
      <div class="tab-icon">📦</div>
      <div class="tab-label" id="i18n-tab-orders">Orders</div>
    </div>
    <div class="tab-btn" id="tab-nav-wallet" onclick="switchTab('wallet')">
      <div class="tab-icon">💳</div>
      <div class="tab-label" id="i18n-tab-wallet">Wallet</div>
    </div>
    <div class="tab-btn" id="tab-nav-settings" onclick="switchTab('settings')">
      <div class="tab-icon">⚙️</div>
      <div class="tab-label" id="i18n-tab-settings">Settings</div>
    </div>
  </nav>

  <!-- Toast Pill -->
  <div class="toast-pill" id="toast-pill">Copied!</div>

  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
    }

    function haptic(type = 'light') {
      try {
        if (tg?.HapticFeedback) {
          if (type === 'success' || type === 'error' || type === 'warning') {
            tg.HapticFeedback.notificationOccurred(type);
          } else {
            tg.HapticFeedback.impactOccurred(type);
          }
        }
      } catch (e) {}
    }

    function showToast(msg) {
      const t = document.getElementById('toast-pill');
      t.innerText = msg;
      t.classList.add('show');
      haptic('success');
      setTimeout(() => t.classList.remove('show'), 2000);
    }

    // State
    let allProducts = [];
    let categoriesList = [];
    let userData = null;
    let activeCatalog = null;
    let currentSelectedProduct = null;
    let selectedQuantity = 1;
    let activeTab = 'store';

    // Telegram User ID Resolution
    const urlParams = new URLSearchParams(window.location.search);
    const tgUser = tg?.initDataUnsafe?.user;
    const resolvedUserId = tgUser?.id || urlParams.get('tg_id') || 0;

    // Catalog Mapping Data (icons, previews)
    const CATALOG_META = {
      "AI & Chatbots": { icon: "🤖", preview: "Claude · ChatGPT · Gemini · Grok" },
      "Streaming & Entertainment": { icon: "🎬", preview: "Netflix · Peacock · Shahid · Apple TV" },
      "VPN & Security": { icon: "🛡️", preview: "NordVPN · Surfshark · Proton" },
      "Design & Creative": { icon: "🎨", preview: "Canva · Adobe · Figma · Framer" },
      "Productivity": { icon: "📝", preview: "Notion · CapCut · Office" },
      "Other": { icon: "📦", preview: "Licenses, keys & digital goods" }
    };

    // Client-side i18n
    const I18N = {
      en: { store: "Store", orders: "Orders", wallet: "Wallet", settings: "Settings", search: "Search products...", collections: "Featured Collections", all_catalogs: "All Catalogs", buy_now: "Instant Buy" },
      ar: { store: "المتجر", orders: "طلباتي", wallet: "المحفظة", settings: "الإعدادات", search: "البحث في المنتجات...", collections: "التصنيفات المميزة", all_catalogs: "جميع التصنيفات", buy_now: "شراء فوري" },
      de: { store: "Shop", orders: "Bestellungen", wallet: "Guthaben", settings: "Einstellungen", search: "Produkte suchen...", collections: "Kategorien", all_catalogs: "Alle Kategorien", buy_now: "Sofort kaufen" },
      es: { store: "Tienda", orders: "Pedidos", wallet: "Billetera", settings: "Ajustes", search: "Buscar productos...", collections: "Colecciones", all_catalogs: "Todas las Colecciones", buy_now: "Comprar ahora" },
      fr: { store: "Boutique", orders: "Commandes", wallet: "Portefeuille", settings: "Paramètres", search: "Rechercher...", collections: "Collections", all_catalogs: "Toutes les Collections", buy_now: "Acheter" },
      it: { store: "Negozio", orders: "Ordini", wallet: "Portafoglio", settings: "Impostazioni", search: "Cerca prodotti...", collections: "Collezioni", all_catalogs: "Tutte le Collezioni", buy_now: "Acquista" },
      zh: { store: "商店", orders: "订单", wallet: "钱包", settings: "设置", search: "搜索产品...", collections: "精选分类", all_catalogs: "所有分类", buy_now: "立即购买" }
    };

    function applyLanguage(lang) {
      const d = I18N[lang] || I18N.en;
      document.getElementById('i18n-tab-store').innerText = d.store;
      document.getElementById('i18n-tab-orders').innerText = d.orders;
      document.getElementById('i18n-tab-wallet').innerText = d.wallet;
      document.getElementById('i18n-tab-settings').innerText = d.settings;
      document.getElementById('global-search').placeholder = d.search;
      document.getElementById('i18n-catalogs-title').innerText = d.collections;
      document.getElementById('i18n-all-catalogs').innerText = d.all_catalogs;
      document.documentElement.dir = (lang === 'ar') ? 'rtl' : 'ltr';
    }

    // Tab Navigation
    function switchTab(tab) {
      haptic('light');
      activeTab = tab;
      document.querySelectorAll('.view-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

      const targetView = document.getElementById('view-' + tab);
      if (targetView) targetView.classList.add('active');

      const targetBtn = document.getElementById('tab-nav-' + tab);
      if (targetBtn) targetBtn.classList.add('active');

      if (tab === 'orders' || tab === 'wallet' || tab === 'settings') {
        loadUserData();
      }
      if (tab === 'store') {
        returnToCatalogs();
      }
    }

    // Load Catalog
    async function fetchCatalogData() {
      try {
        const res = await fetch('/api/catalog');
        const data = await res.json();
        allProducts = data.products || [];
        categoriesList = data.categories || [];
        renderCatalogCards();
      } catch (e) {
        document.getElementById('catalogs-grid').innerHTML = '<div style="color: var(--hint); text-align: center; padding: 30px;">Failed to load catalog.</div>';
      }
    }

    function renderCatalogCards() {
      const container = document.getElementById('catalogs-grid');
      // Build grouped stats
      const groups = {};
      categoriesList.forEach(c => {
        groups[c] = allProducts.filter(p => p.category === c);
      });

      container.innerHTML = Object.keys(groups).map(catName => {
        const items = groups[catName];
        if (!items || !items.length) return '';
        const meta = CATALOG_META[catName] || { icon: "📦", preview: "Digital Products" };
        const minPrice = Math.min(...items.map(p => p.price || 999));
        const sym = items[0]?.sym || '$';

        return `
          <div class="catalog-card" onclick="openCatalog('${catName.replace(/'/g, "\\\\'")}')">
            <div class="catalog-left">
              <div class="catalog-icon">${meta.icon}</div>
              <div class="catalog-info">
                <div class="catalog-title">${catName}</div>
                <div class="catalog-meta">
                  <span>${items.length} products</span> ·
                  <span style="color: var(--accent); font-weight: 700;">From ${minPrice.toFixed(2)}${sym}</span>
                </div>
                <div style="font-size: 11px; color: var(--hint); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${meta.preview}
                </div>
              </div>
            </div>
            <div class="catalog-arrow">➔</div>
          </div>
        `;
      }).join('');
    }

    function openCatalog(catName) {
      haptic('medium');
      activeCatalog = catName;
      document.getElementById('catalogs-mode').style.display = 'none';
      document.getElementById('products-mode').style.display = 'block';
      document.getElementById('active-catalog-title').innerText = catName;

      const filtered = allProducts.filter(p => p.category === catName);
      renderProductsList(filtered);
    }

    function returnToCatalogs() {
      haptic('light');
      activeCatalog = null;
      document.getElementById('global-search').value = '';
      document.getElementById('clear-search-btn').style.display = 'none';
      document.getElementById('products-mode').style.display = 'none';
      document.getElementById('catalogs-mode').style.display = 'block';
    }

    function onSearchInput() {
      const q = (document.getElementById('global-search').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('clear-search-btn');

      if (q) {
        clearBtn.style.display = 'block';
        document.getElementById('catalogs-mode').style.display = 'none';
        document.getElementById('products-mode').style.display = 'block';
        document.getElementById('active-catalog-title').innerText = `Search: "${q}"`;

        const matched = allProducts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
        renderProductsList(matched);
      } else {
        clearBtn.style.display = 'none';
        returnToCatalogs();
      }
    }

    function clearSearch() {
      document.getElementById('global-search').value = '';
      returnToCatalogs();
    }

    function renderProductsList(products) {
      const container = document.getElementById('products-list');
      if (!products.length) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--hint);">No products found in this category.</div>';
        return;
      }
      container.innerHTML = products.map(p => `
        <div class="product-item" onclick="openProductPage(${p.id})">
          <div class="item-left">
            <div class="item-icon">${p.emoji || '⚡'}</div>
            <div class="item-details">
              <div class="item-name">${p.name}</div>
              <div class="item-sub">
                <span>${p.stock ? p.stock + ' in stock' : 'Instant Delivery'}</span>
              </div>
            </div>
          </div>
          <div class="item-right">
            <div class="item-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
            <div class="item-stock">Tap to view ➔</div>
          </div>
        </div>
      `).join('');
    }

    // DEDICATED IN-APP PRODUCT DETAIL PAGE
    function openProductPage(productId) {
      haptic('medium');
      currentSelectedProduct = allProducts.find(p => p.id === productId);
      if (!currentSelectedProduct) return;
      selectedQuantity = 1;

      document.getElementById('page-icon').innerText = currentSelectedProduct.emoji || '⚡';
      document.getElementById('page-name').innerText = currentSelectedProduct.name;
      document.getElementById('page-category').innerText = currentSelectedProduct.category || 'Digital Good';
      document.getElementById('page-desc').innerText = currentSelectedProduct.description || 'Instant automated license activation & credential delivery.';

      const isInstant = currentSelectedProduct.delivery_type !== 'activation';
      document.getElementById('page-delivery-badge').innerText = isInstant ? '⚡ Instant Automated Delivery' : '⏳ Custom Activation';
      document.getElementById('page-stock-badge').innerText = currentSelectedProduct.stock ? `🟢 In Stock (${currentSelectedProduct.stock})` : '⚡ Instant Stock';

      updatePageCalculations();

      document.querySelectorAll('.view-content').forEach(el => el.classList.remove('active'));
      document.getElementById('view-product-detail').classList.add('active');
    }

    function backFromProductPage() {
      haptic('light');
      document.getElementById('view-product-detail').classList.remove('active');
      document.getElementById('view-store').classList.add('active');
    }

    function stepQty(delta) {
      haptic('light');
      selectedQuantity = Math.max(1, Math.min(10, selectedQuantity + delta));
      document.getElementById('page-qty').innerText = selectedQuantity;
      updatePageCalculations();
    }

    function updatePageCalculations() {
      if (!currentSelectedProduct) return;
      const unitPrice = currentSelectedProduct.price || 0.0;
      let total = unitPrice * selectedQuantity;
      const sym = currentSelectedProduct.sym || '$';

      // Check VIP discount
      let discountLine = '';
      if (userData?.vip_discount) {
        const discVal = total * (userData.vip_discount / 100);
        total = Math.max(0.01, total - discVal);
        discountLine = `🎖️ ${userData.vip_tier}: -${userData.vip_discount}% applied!`;
      }
      document.getElementById('page-discount-line').innerText = discountLine;
      document.getElementById('page-total-price').innerText = `${total.toFixed(2)}${sym}`;
      document.getElementById('btn-price-label').innerText = `(${total.toFixed(2)}${sym})`;

      // Balance check
      const userBalance = userData?.balance || 0.0;
      const alertBox = document.getElementById('insufficient-alert');
      const buyBtn = document.getElementById('page-buy-btn');

      if (userBalance < total) {
        alertBox.style.display = 'block';
        const shortage = (total - userBalance).toFixed(2);
        document.getElementById('insufficient-text').innerText = `You need ${shortage}${sym} more. Tap below to top up!`;
        buyBtn.innerHTML = `<span>💳 Top up Balance (+${shortage}${sym} needed)</span>`;
        buyBtn.onclick = () => switchTab('wallet');
      } else {
        alertBox.style.display = 'none';
        buyBtn.innerHTML = `<span>⚡ Instant Buy</span> <span>(${total.toFixed(2)}${sym})</span>`;
        buyBtn.onclick = executeInAppBuy;
      }
    }

    // IN-APP CHECKOUT EXECUTION (POST /api/buy)
    async function executeInAppBuy() {
      if (!currentSelectedProduct || !resolvedUserId) {
        showToast('Please open inside Telegram to purchase');
        return;
      }
      haptic('medium');
      const buyBtn = document.getElementById('page-buy-btn');
      buyBtn.disabled = true;
      buyBtn.innerHTML = '<span>⏳ Processing Order...</span>';

      try {
        const res = await fetch('/api/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: resolvedUserId,
            product_id: currentSelectedProduct.id,
            quantity: selectedQuantity
          })
        });
        const d = await res.json();
        buyBtn.disabled = false;

        if (d.status === 'success') {
          haptic('success');
          // Update live balance
          if (userData) {
            userData.balance = Math.max(0, userData.balance - d.total_paid);
            updateBalancePills();
          }

          // Show in-app success screen
          document.getElementById('success-order-sub').innerText = `Order #${d.order_id} · ${d.product_name} (${d.quantity}×)`;
          const keysBox = document.getElementById('success-keys-container');
          if (d.goods && d.goods.length) {
            keysBox.innerHTML = d.goods.map(g => `
              <div class="key-box" onclick="copyCred('${g.replace(/'/g, "\\\\'")}')">
                <code>${g}</code>
                <div style="font-size: 10px; color: var(--hint); margin-top: 4px;">📋 Tap to copy</div>
              </div>
            `).join('');
          } else {
            keysBox.innerHTML = '<div style="padding: 12px; color: var(--warning); text-align: center;">⏳ Custom activation in progress. Delivered shortly!</div>';
          }

          document.querySelectorAll('.view-content').forEach(el => el.classList.remove('active'));
          document.getElementById('view-order-success').classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || 'Order failed. Please try again.');
          updatePageCalculations();
        }
      } catch (e) {
        buyBtn.disabled = false;
        haptic('error');
        showToast('Connection error. Please retry.');
        updatePageCalculations();
      }
    }

    // User Data & Profile Loading
    async function loadUserData() {
      try {
        if (!resolvedUserId) {
          renderEmptyOrders();
          return;
        }
        const res = await fetch('/api/user-data?tg_id=' + resolvedUserId);
        const d = await res.json();
        if (d.error) {
          renderEmptyOrders();
          return;
        }
        userData = d;
        updateBalancePills();

        // User Avatar (Telegram Real Image or Fallback Initial)
        const avatarBox = document.getElementById('header-avatar-box');
        const setAvatarBox = document.getElementById('settings-avatar-box');
        const firstLetter = (tgUser?.first_name || d.username || 'U')[0].toUpperCase();

        if (d.photo_url) {
          avatarBox.innerHTML = `<img src="${d.photo_url}" class="user-avatar-img" alt="Avatar">`;
          setAvatarBox.innerHTML = `<img src="${d.photo_url}" class="user-avatar-img" style="width: 48px; height: 48px;" alt="Avatar">`;
        } else {
          document.getElementById('header-avatar-initial').innerText = firstLetter;
          document.getElementById('settings-avatar-initial').innerText = firstLetter;
        }

        // Settings View Info
        document.getElementById('user-display-name').innerText = tgUser?.first_name ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : (d.username ? '@' + d.username : 'Customer');
        document.getElementById('user-tg-id').innerText = `Telegram ID: ${d.telegram_id}`;
        document.getElementById('user-vip-badge').innerHTML = `<span class="vip-chip">${d.vip_tier} (-${d.vip_discount}% discount)</span>`;

        // Active currency chips
        document.querySelectorAll('#currency-chips .seg-chip').forEach(el => {
          el.classList.toggle('active', el.innerText.includes(d.currency_preference));
        });

        // Active language chips
        document.querySelectorAll('#language-chips .seg-chip').forEach(el => {
          el.classList.toggle('active', el.getAttribute('onclick')?.includes(`'${d.language}'`));
        });
        applyLanguage(d.language || 'en');

        // Referral link
        const refLink = `https://t.me/${d.bot_username}?start=${d.referral_code || ''}`;
        document.getElementById('ref-link-display').innerText = refLink;

        // Render Orders
        renderOrdersList(d.orders || []);
      } catch (e) {
        renderEmptyOrders();
      }
    }

    function updateBalancePills() {
      if (!userData) return;
      document.getElementById('top-balance-val').innerText = userData.display_balance || `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-num').innerText = `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-alt-curr').innerText = userData.currency_preference !== 'USD'
        ? `≈ ${userData.display_balance}`
        : 'Available for instant purchases';

      if (userData.vip_tier && userData.vip_tier !== 'Standard') {
        const tag = document.getElementById('header-vip-tag');
        tag.innerText = userData.vip_tier;
        tag.style.display = 'inline-block';
      }
    }

    function renderEmptyOrders() {
      document.getElementById('orders-list').innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: var(--hint);">
          <div style="font-size: 40px; margin-bottom: 10px;">📦</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px;">No Orders Yet</div>
          <p style="font-size: 13px; line-height: 1.4; margin-bottom: 16px;">Browse collections and purchase products with 1 tap!</p>
          <button class="btn-checkout" onclick="switchTab('store')" style="width: auto; padding: 10px 20px; margin: 0 auto;">Browse Store</button>
        </div>
      `;
    }

    function renderOrdersList(orders) {
      const container = document.getElementById('orders-list');
      if (!orders.length) {
        renderEmptyOrders();
        return;
      }
      container.innerHTML = orders.map(o => `
        <div class="order-card">
          <div class="order-header">
            <span style="font-weight: 700; font-size: 14px;">#${o.id} · ${o.created_at || ''}</span>
            <span class="status-tag status-${o.status.includes('completed') ? 'completed' : o.status.includes('fail') ? 'failed' : 'pending'}">${o.status}</span>
          </div>
          <div style="font-size: 15px; font-weight: 700; margin-bottom: 4px;">${o.products}</div>
          <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-bottom: 8px;">Total: ${o.total.toFixed(2)}${o.sym}</div>

          ${o.goods && o.goods.length ? o.goods.map(g => `
            <div class="key-box" onclick="copyCred('${g.replace(/'/g, "\\\\'")}')">
              <code>${g}</code>
              <div style="font-size: 10px; color: var(--hint); margin-top: 4px;">📋 Tap to copy credentials</div>
            </div>
          `).join('') : ''}

          <div style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px;">
            ${o.warranty_days && !o.warranty_claimed && o.status === 'completed' ? `
              <button class="back-catalog-btn" onclick="inAppWarrantyClaim(${o.id})">🛡️ Claim Warranty</button>
            ` : ''}
            <button class="back-catalog-btn" onclick="inAppReportIssue(${o.id})">⚠️ Report Issue</button>
          </div>
        </div>
      `).join('');
    }

    function copyCred(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Credentials copied to clipboard!');
      });
    }

    function copyRefLink() {
      const link = document.getElementById('ref-link-display').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast('Referral link copied!');
      });
    }

    async function updateCurrencyPref(code) {
      haptic('light');
      document.querySelectorAll('#currency-chips .seg-chip').forEach(el => {
        el.classList.toggle('active', el.innerText.includes(code));
      });
      if (resolvedUserId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: resolvedUserId, currency: code })
        });
        showToast(`Currency set to ${code}`);
        loadUserData();
      }
    }

    async function updateLanguagePref(code) {
      haptic('light');
      applyLanguage(code);
      if (resolvedUserId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: resolvedUserId, language: code })
        });
        showToast('Language updated!');
        loadUserData();
      }
    }

    async function inAppWarrantyClaim(orderId) {
      haptic('medium');
      try {
        const res = await fetch('/api/warranty/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: resolvedUserId, order_id: orderId })
        });
        const d = await res.json();
        if (d.status === 'success') {
          showToast('Warranty approved! New credentials issued.');
          loadUserData();
        } else {
          showToast('Warranty claim sent to support review.');
        }
      } catch (e) {
        showToast('Failed to claim warranty.');
      }
    }

    function inAppReportIssue(orderId) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "report_issue", order_id: orderId }));
        tg.close();
      }
    }

    function sendBotTopup(amount) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "topup_prompt", amount: amount }));
        tg.close();
      }
    }

    function launchBotRail(rail) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "open_rail", rail: rail }));
        tg.close();
      }
    }

    // Startup
    fetchCatalogData();
    loadUserData();
  </script>
</body>
</html>
"""
