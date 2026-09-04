"""Telegram Mini App (TMA) Storefront HTML, CSS, and Client Logic.

Fully features:
- Native iPhone-style 49px TabBar with SF-style SVG icons and system blue (#007aff) active states.
- iPhone system buttons (rounded-12px filled buttons, iOS segmented steppers, inset grouped cards).
- Direct In-App Telegram Stars Invoice Checkout via window.Telegram.WebApp.openInvoice().
- Direct In-App Balance Recharging via POST /api/invoice/topup (Stars, Crypto, SAM) without sendData failures.
- Real Telegram profile picture and user info from bot.get_user_profile_photos().
- Homepage Featured Catalog Cards Grid (AI & Chatbots, Streaming, VPN, etc.) with drill-down and '← All Catalogs' navigation.
- Dedicated In-App Product Page with live balance check, quantity stepper, volume discounts, and instant in-app purchase (POST /api/buy) — no text chat redirect!
- In-App Order Success Screen with copyable credentials and celebratory confetti particle burst.
- Orders page with timeline stepper (Placed ── Fulfilling ── Delivered), 1-tap copy, in-app warranty claim, and in-app review dialog.
- Trending search chips and recent searches in localStorage.
- Skeleton shimmer loading screens (zero content shift).
- Auto-sliding promotional hero carousel at top of store.
- Pull-to-refresh with haptic feedback.
- Lifetime savings card and VIP loyalty progress bar in Wallet.
- Client-side multi-language translation (7 languages) with RTL support for Arabic.
"""

STOREFRONT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>GH Store</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    /* iOS System Color Palette & Dark Theme */
    :root {
      --ios-bg: #000000;
      --ios-card: #1c1c1e;
      --ios-secondary-card: #2c2c2e;
      --ios-tertiary-card: #3a3a3c;
      --ios-blue: #007aff;
      --ios-blue-tint: rgba(0, 122, 255, 0.15);
      --ios-green: #34c759;
      --ios-orange: #ff9500;
      --ios-red: #ff3b30;
      --ios-text: #ffffff;
      --ios-secondary-text: #8e8e93;
      --ios-tertiary-text: #636366;
      --ios-border: rgba(255, 255, 255, 0.12);
      --ios-hairline: 0.5px solid rgba(255, 255, 255, 0.15);
      --tab-height: 49px;
      --safe-bottom: env(safe-area-inset-bottom, 20px);
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
      background: var(--ios-bg);
      color: var(--ios-text);
      min-height: 100vh;
      padding-bottom: calc(var(--tab-height) + var(--safe-bottom) + 20px);
      user-select: none;
      -webkit-user-select: none;
      overflow-x: hidden;
    }

    /* iOS Navigation Header */
    .ios-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(25px) saturate(190%);
      -webkit-backdrop-filter: blur(25px) saturate(190%);
      background: rgba(24, 24, 26, 0.85);
      border-bottom: var(--ios-hairline);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header-user {
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
    }
    .avatar-img {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      object-fit: cover;
      border: 1.5px solid var(--ios-blue);
    }
    .avatar-placeholder {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #007aff, #5856d6);
      color: #fff;
      font-size: 16px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .header-meta h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.4px;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .vip-tag {
      background: rgba(255, 149, 0, 0.2);
      color: var(--ios-orange);
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
    }
    .header-balance-btn {
      background: var(--ios-blue-tint);
      color: var(--ios-blue);
      border: none;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
    }
    .header-balance-btn:active { opacity: 0.7; }

    /* Views */
    .tab-view {
      padding: 16px;
      display: none;
      animation: viewFade 0.2s ease-out;
    }
    .tab-view.active { display: block; }
    @keyframes viewFade {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* iOS Search Bar */
    .ios-search-wrapper {
      position: relative;
      margin-bottom: 12px;
    }
    .ios-search-input {
      width: 100%;
      background: rgba(118, 118, 128, 0.24);
      border: none;
      border-radius: 10px;
      color: #fff;
      padding: 9px 36px 9px 36px;
      font-size: 15px;
      outline: none;
    }
    .ios-search-input::placeholder { color: var(--ios-secondary-text); }
    .search-glyph {
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--ios-secondary-text);
    }
    .search-clear {
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #8e8e93;
      color: #000;
      font-size: 12px;
      display: none;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }

    /* Trending Quick Search Chips */
    .trending-chips {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 8px;
      margin-bottom: 14px;
      scrollbar-width: none;
    }
    .trending-chips::-webkit-scrollbar { display: none; }
    .trend-chip {
      background: var(--ios-card);
      border: var(--ios-hairline);
      color: var(--ios-secondary-text);
      font-size: 12px;
      font-weight: 500;
      padding: 5px 12px;
      border-radius: 14px;
      white-space: nowrap;
      cursor: pointer;
    }
    .trend-chip:active { background: var(--ios-secondary-card); color: #fff; }

    /* Promotional Hero Carousel */
    .carousel-container {
      position: relative;
      border-radius: 16px;
      overflow: hidden;
      margin-bottom: 18px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .carousel-track {
      display: flex;
      transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
    }
    .carousel-slide {
      min-width: 100%;
      padding: 20px 18px;
      background: linear-gradient(135deg, #1e293b, #0f172a);
      border: var(--ios-hairline);
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .slide-badge {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--ios-blue);
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .slide-title {
      font-size: 17px;
      font-weight: 700;
      margin-bottom: 4px;
      color: #fff;
    }
    .slide-sub {
      font-size: 12px;
      color: var(--ios-secondary-text);
    }

    /* Section Headers */
    .ios-section-header {
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: -0.1px;
      color: var(--ios-secondary-text);
      margin: 16px 0 8px 4px;
    }

    /* Catalog Cards Grid (Collections Homepage) */
    .catalogs-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    @media (min-width: 480px) {
      .catalogs-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .catalog-card {
      background: var(--ios-card);
      border: var(--ios-hairline);
      border-radius: 14px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      transition: transform 0.15s, background 0.15s;
    }
    .catalog-card:active {
      transform: scale(0.98);
      background: var(--ios-secondary-card);
    }
    .catalog-icon-box {
      width: 46px;
      height: 46px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.06);
      font-size: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-right: 14px;
    }
    .catalog-texts {
      flex: 1;
      overflow: hidden;
    }
    .catalog-name {
      font-size: 16px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .catalog-sub {
      font-size: 12px;
      color: var(--ios-secondary-text);
    }
    .chevron-right {
      color: var(--ios-tertiary-text);
      font-size: 18px;
      font-weight: 600;
      margin-left: 8px;
    }

    /* Subview Navigation Header */
    .subview-nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .ios-back-btn {
      background: transparent;
      border: none;
      color: var(--ios-blue);
      font-size: 16px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
    }
    .ios-back-btn:active { opacity: 0.6; }

    /* Product Cards in Collection */
    .product-row {
      background: var(--ios-card);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
      border: var(--ios-hairline);
      transition: transform 0.15s;
    }
    .product-row:active {
      transform: scale(0.99);
      background: var(--ios-secondary-card);
    }
    .product-info {
      flex: 1;
      overflow: hidden;
    }
    .product-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #fff;
    }
    .product-desc {
      font-size: 12px;
      color: var(--ios-secondary-text);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .product-price-box {
      text-align: right;
      flex-shrink: 0;
    }
    .product-price {
      font-size: 16px;
      font-weight: 700;
      color: var(--ios-blue);
    }
    .stock-label {
      font-size: 11px;
      color: var(--ios-secondary-text);
      margin-top: 2px;
    }

    /* iPhone System Buttons */
    .ios-btn-primary {
      width: 100%;
      height: 50px;
      border-radius: 12px;
      background: var(--ios-blue);
      color: #ffffff;
      font-size: 17px;
      font-weight: 600;
      letter-spacing: -0.4px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      box-shadow: 0 4px 14px rgba(0, 122, 255, 0.35);
      transition: opacity 0.15s, transform 0.15s;
    }
    .ios-btn-primary:active { opacity: 0.8; transform: scale(0.98); }
    .ios-btn-secondary {
      background: rgba(120, 120, 128, 0.18);
      color: var(--ios-blue);
      border: none;
      border-radius: 10px;
      padding: 8px 14px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }
    .ios-btn-secondary:active { opacity: 0.7; }
    .ios-btn-stars {
      width: 100%;
      height: 50px;
      border-radius: 12px;
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: #ffffff;
      font-size: 16px;
      font-weight: 700;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      margin-top: 10px;
      box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
    }
    .ios-btn-stars:active { opacity: 0.8; transform: scale(0.98); }

    /* iOS Native Stepper */
    .ios-stepper {
      display: inline-flex;
      align-items: center;
      background: rgba(118, 118, 128, 0.24);
      border-radius: 9px;
      overflow: hidden;
    }
    .ios-stepper-btn {
      width: 36px;
      height: 32px;
      border: none;
      background: transparent;
      color: var(--ios-blue);
      font-size: 18px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .ios-stepper-btn:active { background: rgba(255, 255, 255, 0.1); }
    .ios-stepper-divider {
      width: 0.5px;
      height: 18px;
      background: rgba(255, 255, 255, 0.2);
    }
    .ios-stepper-val {
      padding: 0 12px;
      font-size: 15px;
      font-weight: 600;
      color: #fff;
    }

    /* In-App Product Page */
    .page-hero {
      text-align: center;
      padding: 24px 0 16px 0;
    }
    .hero-icon { font-size: 56px; margin-bottom: 12px; }
    .hero-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
    .hero-cat { font-size: 12px; color: var(--ios-blue); text-transform: uppercase; font-weight: 700; }
    .inset-card {
      background: var(--ios-card);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
      border: var(--ios-hairline);
    }

    /* Order Timeline Stepper */
    .timeline-wrapper {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 14px 0;
      position: relative;
    }
    .timeline-line {
      position: absolute;
      top: 50%;
      left: 20px;
      right: 20px;
      height: 2px;
      background: var(--ios-tertiary-card);
      z-index: 1;
      transform: translateY(-50%);
    }
    .step-item {
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
    }
    .step-dot {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--ios-tertiary-card);
      border: 2px solid var(--ios-card);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 9px;
    }
    .step-dot.done { background: var(--ios-green); color: #fff; }
    .step-dot.active { background: var(--ios-orange); animation: pulse 1.5s infinite; }
    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.2); }
      100% { transform: scale(1); }
    }
    .step-label { font-size: 10px; color: var(--ios-secondary-text); font-weight: 600; }

    /* Code Box for License Keys */
    .code-box {
      background: rgba(0, 0, 0, 0.4);
      border: 1px dashed rgba(0, 122, 255, 0.4);
      border-radius: 10px;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      color: #38bdf8;
      word-break: break-all;
      margin: 8px 0;
      cursor: pointer;
    }
    .code-box:active { background: rgba(0, 122, 255, 0.15); }

    /* Skeleton Shimmer Loading */
    .skeleton-card {
      background: var(--ios-card);
      border-radius: 14px;
      height: 80px;
      margin-bottom: 10px;
      position: relative;
      overflow: hidden;
    }
    .skeleton-card::after {
      content: '';
      position: absolute;
      top: 0; right: 0; bottom: 0; left: 0;
      transform: translateX(-100%);
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.05), transparent);
      animation: shimmer 1.5s infinite;
    }
    @keyframes shimmer {
      100% { transform: translateX(100%); }
    }

    /* iPhone Bottom Tab Bar */
    .iphone-tabbar {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: calc(var(--tab-height) + var(--safe-bottom));
      padding-bottom: var(--safe-bottom);
      background: rgba(22, 22, 24, 0.88);
      backdrop-filter: blur(30px) saturate(210%);
      -webkit-backdrop-filter: blur(30px) saturate(210%);
      border-top: var(--ios-hairline);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
    }
    .tab-item {
      flex: 1;
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: #8e8e93;
      cursor: pointer;
      transition: color 0.12s;
    }
    .tab-item.active {
      color: #007aff;
    }
    .tab-item svg {
      width: 22px;
      height: 22px;
      fill: currentColor;
    }
    .tab-label {
      font-size: 10px;
      font-weight: 500;
      letter-spacing: -0.24px;
    }

    /* Review Modal */
    .modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.65);
      backdrop-filter: blur(8px);
      z-index: 150;
      display: none;
      align-items: flex-end;
    }
    .modal-overlay.open { display: flex; }
    .modal-sheet {
      width: 100%;
      background: var(--ios-card);
      border-top-left-radius: 20px;
      border-top-right-radius: 20px;
      padding: 20px 20px calc(20px + var(--safe-bottom)) 20px;
      border-top: var(--ios-hairline);
    }
    .star-picker {
      display: flex;
      justify-content: center;
      gap: 12px;
      font-size: 32px;
      margin: 16px 0;
      cursor: pointer;
    }

    /* Confetti Canvas */
    #confetti-canvas {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 200;
    }

    /* Toast */
    .ios-toast {
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%) translateY(-100px);
      background: rgba(52, 199, 89, 0.95);
      color: #fff;
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      z-index: 250;
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    .ios-toast.show { transform: translateX(-50%) translateY(0); }
  </style>
</head>
<body>
  <canvas id="confetti-canvas"></canvas>
  <div class="ios-toast" id="toast">Copied!</div>

  <!-- iOS Top Header -->
  <header class="ios-header">
    <div class="header-user" onclick="switchTab('settings')">
      <div id="avatar-container">
        <div class="avatar-placeholder" id="avatar-initial">U</div>
      </div>
      <div class="header-meta">
        <h1>🛍️ GH Store <span class="vip-tag" id="top-vip" style="display: none;">VIP</span></h1>
        <span id="header-caption">Direct Digital Reseller</span>
      </div>
    </div>
    <button class="header-balance-btn" onclick="switchTab('wallet')">
      <span id="top-balance-str">$0.00</span>
      <span style="font-size: 11px;">+</span>
    </button>
  </header>

  <!-- TAB 1: STORE / CATALOGS -->
  <main id="view-store" class="tab-view active">
    <!-- iOS Search -->
    <div class="ios-search-wrapper">
      <span class="search-glyph">🔍</span>
      <input type="text" id="catalog-search" class="ios-search-input" placeholder="Search products (Claude, Netflix, VPN...)" oninput="handleSearchInput()">
      <span class="search-clear" id="search-clear-btn" onclick="clearSearchInput()">✕</span>
    </div>

    <!-- Trending Search Chips -->
    <div class="trending-chips" id="trending-container">
      <div class="trend-chip" onclick="quickSearch('Claude')">🧠 Claude 3.5</div>
      <div class="trend-chip" onclick="quickSearch('Gemini')">✨ Gemini Pro</div>
      <div class="trend-chip" onclick="quickSearch('ChatGPT')">🤖 ChatGPT 4o</div>
      <div class="trend-chip" onclick="quickSearch('Netflix')">🎬 Netflix 4K</div>
      <div class="trend-chip" onclick="quickSearch('VPN')">🛡️ NordVPN</div>
    </div>

    <!-- Promotional Hero Carousel -->
    <div class="carousel-container">
      <div class="carousel-track" id="hero-carousel">
        <div class="carousel-slide">
          <div class="slide-badge">Restock Alert</div>
          <div class="slide-title">✨ Claude 3.5 & Gemini Advanced</div>
          <div class="slide-sub">Instant automated key activation available 24/7</div>
        </div>
      </div>
    </div>

    <!-- Mode A: Collections (Catalog Cards) -->
    <div id="collections-container">
      <div class="ios-section-header" id="label-collections">Featured Catalogs</div>
      <div class="catalogs-grid" id="catalogs-list">
        <!-- Skeleton loaders initially -->
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
      </div>
    </div>

    <!-- Mode B: Products in Selected Collection -->
    <div id="products-container" style="display: none;">
      <div class="subview-nav">
        <button class="ios-back-btn" onclick="exitToCatalogs()">
          <span>‹</span>
          <span id="back-catalog-label">All Catalogs</span>
        </button>
        <div style="font-size: 16px; font-weight: 700;" id="current-collection-title">Catalog</div>
      </div>
      <div id="products-list-box"></div>
    </div>
  </main>

  <!-- IN-APP DEDICATED PRODUCT DETAIL PAGE -->
  <section id="view-product-page" class="tab-view">
    <div class="subview-nav">
      <button class="ios-back-btn" onclick="exitProductPage()">
        <span>‹</span>
        <span>Back</span>
      </button>
      <span style="font-size: 14px; color: var(--ios-secondary-text);" id="detail-category-tag">Category</span>
    </div>

    <div class="page-hero">
      <div class="hero-icon" id="detail-hero-icon">⚡</div>
      <h2 class="hero-title" id="detail-hero-title">Product</h2>
      <div class="hero-cat" id="detail-hero-cat">Digital Account</div>
    </div>

    <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
      <div class="ios-btn-secondary" id="detail-delivery-tag">⚡ Automated Delivery</div>
      <div class="ios-btn-secondary" id="detail-warranty-tag">🛡️ 30 Days Warranty</div>
      <div class="ios-btn-secondary" id="detail-stock-tag">🟢 In Stock</div>
    </div>

    <!-- Social Proof Ratings -->
    <div class="inset-card" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px;">
      <div style="display: flex; align-items: center; gap: 6px;">
        <span style="color: var(--ios-orange); font-size: 16px;">⭐⭐⭐⭐⭐</span>
        <strong style="font-size: 14px;" id="detail-rating-score">4.9</strong>
      </div>
      <span style="font-size: 12px; color: var(--ios-secondary-text);" id="detail-rating-count">(32 verified buyers)</span>
    </div>

    <div class="inset-card">
      <div style="font-size: 12px; font-weight: 700; color: var(--ios-secondary-text); text-transform: uppercase; margin-bottom: 6px;">Description</div>
      <p style="font-size: 14px; line-height: 1.5; color: var(--ios-text);" id="detail-hero-desc">Instant digital goods delivery.</p>
    </div>

    <div class="inset-card">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
        <div>
          <div style="font-size: 12px; color: var(--ios-secondary-text); text-transform: uppercase;">Total Price</div>
          <div style="font-size: 24px; font-weight: 800; color: var(--ios-blue);" id="detail-total-price">$0.00</div>
          <div style="font-size: 12px; color: var(--ios-green); font-weight: 700;" id="detail-discount-note"></div>
        </div>
        <div class="ios-stepper">
          <button class="ios-stepper-btn" onclick="stepQuantity(-1)">–</button>
          <div class="ios-stepper-divider"></div>
          <span class="ios-stepper-val" id="stepper-val">1</span>
          <div class="ios-stepper-divider"></div>
          <button class="ios-stepper-btn" onclick="stepQuantity(1)">+</button>
        </div>
      </div>

      <div id="insufficient-funds-banner" style="background: rgba(255, 59, 48, 0.12); border: 1px solid rgba(255, 59, 48, 0.3); border-radius: 10px; padding: 10px; text-align: center; font-size: 13px; color: #ff6961; margin-bottom: 12px; display: none;">
        ⚠️ Insufficient balance for this order.
      </div>

      <button class="ios-btn-primary" id="btn-inapp-buy" onclick="submitInAppBuy()">
        <span>⚡ Instant Buy</span>
        <span id="btn-buy-total-tag">($0.00)</span>
      </button>

      <!-- Direct Stars Checkout Fallback Button -->
      <button class="ios-btn-stars" id="btn-direct-stars" onclick="payDirectStars()">
        <span>⭐ Pay with Telegram Stars</span>
      </button>
    </div>
  </section>

  <!-- IN-APP ORDER SUCCESS SCREEN -->
  <section id="view-order-success" class="tab-view">
    <div style="text-align: center; padding: 24px 0 16px 0;">
      <div style="font-size: 60px; margin-bottom: 10px;">🎉</div>
      <h2 style="font-size: 22px; font-weight: 700; margin-bottom: 4px;">Order Complete!</h2>
      <p style="font-size: 13px; color: var(--ios-secondary-text);" id="success-sub">Order #000 · Delivered</p>
    </div>

    <div class="inset-card">
      <div style="font-size: 12px; font-weight: 700; color: var(--ios-secondary-text); text-transform: uppercase; margin-bottom: 8px;">Your Credentials</div>
      <div id="delivered-keys-box"></div>
      <div style="font-size: 11px; color: var(--ios-secondary-text); text-align: center; margin-top: 6px;">
        Tap on credentials above to copy!
      </div>
    </div>

    <div style="display: flex; gap: 10px;">
      <button class="ios-btn-secondary" onclick="switchTab('orders')" style="flex: 1; height: 48px;">📦 View in Orders</button>
      <button class="ios-btn-primary" onclick="switchTab('store')" style="flex: 1; height: 48px;">🛍️ Done</button>
    </div>
  </section>

  <!-- TAB 2: ORDERS VIEW -->
  <main id="view-orders" class="tab-view">
    <div class="ios-section-header">Purchase History</div>
    <div id="orders-list-box">
      <!-- Skeletons -->
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    </div>
  </main>

  <!-- TAB 3: WALLET VIEW -->
  <main id="view-wallet" class="tab-view">
    <div class="inset-card" style="text-align: center; padding: 24px 16px; background: linear-gradient(135deg, #1c1c1e, #111827); border: var(--ios-hairline);">
      <div style="font-size: 12px; color: var(--ios-secondary-text); text-transform: uppercase; letter-spacing: 0.5px;">Account Balance</div>
      <div style="font-size: 36px; font-weight: 800; margin: 4px 0;" id="wallet-balance-hero">$0.00</div>
      <div style="font-size: 13px; color: var(--ios-blue); font-weight: 600;" id="wallet-balance-approx">Ready for purchases</div>
    </div>

    <!-- Lifetime Savings & VIP Progress -->
    <div class="inset-card" style="padding: 14px;">
      <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
        <span>Progress to <strong id="next-vip-label" style="color: var(--ios-orange);">Gold VIP</strong></span>
        <span id="vip-progress-pct" style="color: var(--ios-blue); font-weight: 700;">65%</span>
      </div>
      <div style="width: 100%; height: 6px; background: var(--ios-secondary-card); border-radius: 3px; overflow: hidden;">
        <div id="vip-progress-bar" style="width: 0%; height: 100%; background: var(--ios-blue); transition: width 0.3s;"></div>
      </div>
    </div>

    <div class="ios-section-header">Quick Top-Up Presets</div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px;">
      <div class="ios-btn-secondary" style="text-align: center; padding: 12px 0;" onclick="startTopup(10)">+$10</div>
      <div class="ios-btn-secondary" style="text-align: center; padding: 12px 0;" onclick="startTopup(25)">+$25</div>
      <div class="ios-btn-secondary" style="text-align: center; padding: 12px 0;" onclick="startTopup(50)">+$50</div>
      <div class="ios-btn-secondary" style="text-align: center; padding: 12px 0;" onclick="startTopup(100)">+$100</div>
    </div>

    <div class="ios-section-header">Deposit Rails</div>
    <div class="product-row" onclick="startRailTopup('stars')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">⭐</span>
        <div>
          <div style="font-weight: 600; font-size: 15px;">Telegram Stars</div>
          <div style="font-size: 12px; color: var(--ios-secondary-text);">Instant Apple Pay / In-App payment</div>
        </div>
      </div>
      <span class="chevron-right">›</span>
    </div>

    <div class="product-row" onclick="startRailTopup('crypto')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">🪙</span>
        <div>
          <div style="font-weight: 600; font-size: 15px;">Cryptocurrency</div>
          <div style="font-size: 12px; color: var(--ios-secondary-text);">USDT, BTC, SOL via KryptoExpress</div>
        </div>
      </div>
      <span class="chevron-right">›</span>
    </div>

    <div class="product-row" onclick="startRailTopup('sam')">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 26px;">📱</span>
        <div>
          <div style="font-weight: 600; font-size: 15px;">SAM Syriatel & ShamCash</div>
          <div style="font-size: 12px; color: var(--ios-secondary-text);">Syrian local wallet payments</div>
        </div>
      </div>
      <span class="chevron-right">›</span>
    </div>

    <!-- Voucher Redemption Box -->
    <div class="ios-section-header">Redeem Gift Voucher</div>
    <div class="inset-card" style="display: flex; gap: 8px; padding: 10px;">
      <input type="text" id="voucher-input" placeholder="GH-XXXX-YYYY" style="flex: 1; background: transparent; border: none; color: #fff; font-size: 14px; outline: none; font-family: monospace; text-transform: uppercase;">
      <button class="ios-btn-secondary" onclick="redeemVoucher()" style="padding: 6px 14px;">Redeem</button>
    </div>
  </main>

  <!-- TAB 4: SETTINGS VIEW -->
  <main id="view-settings" class="tab-view">
    <div class="inset-card" style="display: flex; align-items: center; gap: 14px;">
      <div id="settings-avatar-container">
        <div class="avatar-placeholder" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">U</div>
      </div>
      <div>
        <div style="font-size: 17px; font-weight: 700;" id="settings-name-label">Customer</div>
        <div style="font-size: 12px; color: var(--ios-secondary-text); font-family: monospace;" id="settings-tgid-label">ID: 000000000</div>
        <div style="margin-top: 4px;" id="settings-vip-pill"></div>
      </div>
    </div>

    <div class="inset-card">
      <div class="ios-section-header" style="margin-top: 0;">💱 Display Currency</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="curr-chips">
        <div class="trend-chip" onclick="selectCurrency('USD')">USD ($)</div>
        <div class="trend-chip" onclick="selectCurrency('EUR')">EUR (€)</div>
        <div class="trend-chip" onclick="selectCurrency('SYP')">SYP (ل.س)</div>
        <div class="trend-chip" onclick="selectCurrency('XTR')">Stars (⭐)</div>
      </div>
    </div>

    <div class="inset-card">
      <div class="ios-section-header" style="margin-top: 0;">🌐 Language / اللغة</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="lang-chips">
        <div class="trend-chip" onclick="selectLanguage('en')">English</div>
        <div class="trend-chip" onclick="selectLanguage('ar')">العربية</div>
        <div class="trend-chip" onclick="selectLanguage('de')">Deutsch</div>
        <div class="trend-chip" onclick="selectLanguage('es')">Español</div>
        <div class="trend-chip" onclick="selectLanguage('fr')">Français</div>
        <div class="trend-chip" onclick="selectLanguage('it')">Italiano</div>
        <div class="trend-chip" onclick="selectLanguage('zh')">中文</div>
      </div>
    </div>

    <div class="inset-card">
      <div class="ios-section-header" style="margin-top: 0;">🎁 Referral Partner Link</div>
      <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0, 0, 0, 0.3); border-radius: 8px; padding: 10px; margin-top: 8px;">
        <span id="ref-link-val" style="font-family: monospace; font-size: 12px; color: var(--ios-blue); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 8px;">https://t.me/...</span>
        <button class="ios-btn-secondary" onclick="copyRefLink()" style="padding: 4px 10px;">Copy</button>
      </div>
    </div>
  </main>

  <!-- True iPhone SF TabBar -->
  <nav class="iphone-tabbar">
    <div class="tab-item active" id="tab-store" onclick="switchTab('store')">
      <svg viewBox="0 0 24 24"><path d="M19 6h-2c0-2.76-2.24-5-5-5S7 3.24 7 6H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-7-3c1.66 0 3 1.34 3 3H9c0-1.66 1.34-3 3-3zm7 17H5V8h14v12zm-7-8c-1.66 0-3-1.34-3-3H7c0 2.76 2.24 5 5 5s5-2.24 5-5h-2c0 1.66-1.34 3-3 3z"/></svg>
      <span class="tab-label" id="i18n-nav-store">Store</span>
    </div>
    <div class="tab-item" id="tab-orders" onclick="switchTab('orders')">
      <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
      <span class="tab-label" id="i18n-nav-orders">Orders</span>
    </div>
    <div class="tab-item" id="tab-wallet" onclick="switchTab('wallet')">
      <svg viewBox="0 0 24 24"><path d="M21 18v1c0 1.1-.9 2-2 2H5c-1.11 0-2-.9-2-2V5c0-1.1.89-2 2-2h14c1.1 0 2 .9 2 2v1h-9c-1.11 0-2 .9-2 2v8c0 1.1.89 2 2 2h9zm-9-2h10V8H12v8zm4-2.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>
      <span class="tab-label" id="i18n-nav-wallet">Wallet</span>
    </div>
    <div class="tab-item" id="tab-settings" onclick="switchTab('settings')">
      <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
      <span class="tab-label" id="i18n-nav-settings">Settings</span>
    </div>
  </nav>

  <!-- Review Modal Overlay -->
  <div class="modal-overlay" id="review-modal">
    <div class="modal-sheet">
      <div style="width: 36px; height: 4px; background: rgba(255, 255, 255, 0.2); border-radius: 2px; margin: 0 auto 14px auto;"></div>
      <h3 style="font-size: 18px; font-weight: 700; text-align: center;">Rate Your Purchase</h3>
      <div class="star-picker" id="stars-row">
        <span onclick="setStarRating(1)">⭐</span>
        <span onclick="setStarRating(2)">⭐</span>
        <span onclick="setStarRating(3)">⭐</span>
        <span onclick="setStarRating(4)">⭐</span>
        <span onclick="setStarRating(5)">⭐</span>
      </div>
      <textarea id="review-text-input" placeholder="Leave feedback about delivery & service (optional)..." style="width: 100%; height: 80px; background: rgba(0, 0, 0, 0.25); border: var(--ios-hairline); border-radius: 10px; color: #fff; padding: 10px; font-size: 14px; outline: none; margin-bottom: 12px;"></textarea>
      <div style="display: flex; gap: 8px;">
        <button class="ios-btn-secondary" onclick="closeReviewModal()" style="flex: 1;">Cancel</button>
        <button class="ios-btn-primary" onclick="submitReviewAction()" style="flex: 2;">Submit Review</button>
      </div>
    </div>
  </div>

  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      try {
        if (tg.setHeaderColor) tg.setHeaderColor('#18181a');
        if (tg.setBackgroundColor) tg.setBackgroundColor('#000000');
      } catch (e) {}
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
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.classList.add('show');
      haptic('success');
      setTimeout(() => t.classList.remove('show'), 2200);
    }

    // Confetti burst on purchase / copy
    function fireConfetti() {
      const canvas = document.getElementById('confetti-canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      const particles = [];
      const colors = ['#007aff', '#34c759', '#ff9500', '#ff2d55', '#5856d6', '#38bdf8'];
      for (let i = 0; i < 60; i++) {
        particles.push({
          x: canvas.width / 2,
          y: canvas.height / 3,
          r: Math.random() * 5 + 3,
          d: Math.random() * 60,
          color: colors[Math.floor(Math.random() * colors.length)],
          tilt: Math.floor(Math.random() * 10) - 10,
          tiltAngleIncremental: (Math.random() * 0.07) + 0.05,
          tiltAngle: 0,
          vx: (Math.random() - 0.5) * 14,
          vy: (Math.random() - 0.7) * 14,
        });
      }
      let frames = 0;
      function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => {
          p.tiltAngle += p.tiltAngleIncremental;
          p.y += p.vy;
          p.x += p.vx;
          p.vy += 0.35; // gravity
          ctx.beginPath();
          ctx.lineWidth = p.r;
          ctx.strokeStyle = p.color;
          ctx.moveTo(p.x + p.tilt + p.r / 2, p.y);
          ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r / 2);
          ctx.stroke();
        });
        frames++;
        if (frames < 75) requestAnimationFrame(render);
        else ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      render();
    }

    // Client State
    let allProducts = [];
    let categoriesList = [];
    let userData = null;
    let activeCatalog = null;
    let selectedProduct = null;
    let selectedQty = 1;
    let activeTab = 'store';
    let reviewTargetOrderId = null;
    let selectedStarRating = 5;

    // Resolve user ID
    const urlParams = new URLSearchParams(window.location.search);
    const tgUser = tg?.initDataUnsafe?.user;
    const userId = tgUser?.id || urlParams.get('tg_id') || 0;

    // Collections config
    const CATALOG_META = {
      "AI & Chatbots": { icon: "🤖", preview: "Claude · ChatGPT · Gemini · Grok" },
      "Streaming & Entertainment": { icon: "🎬", preview: "Netflix · Peacock · Shahid · Apple TV" },
      "VPN & Security": { icon: "🛡️", preview: "NordVPN · Surfshark · Proton" },
      "Design & Creative": { icon: "🎨", preview: "Canva · Adobe · Figma · Framer" },
      "Productivity": { icon: "📝", preview: "Notion · CapCut · Office" },
      "Other": { icon: "📦", preview: "Digital accounts, licenses & keys" }
    };

    // Client-side i18n
    const I18N = {
      en: { store: "Store", orders: "Orders", wallet: "Wallet", settings: "Settings", search: "Search products...", collections: "Featured Catalogs", all_catalogs: "All Catalogs" },
      ar: { store: "المتجر", orders: "طلباتي", wallet: "المحفظة", settings: "الإعدادات", search: "البحث في المنتجات...", collections: "التصنيفات المميزة", all_catalogs: "جميع التصنيفات" },
      de: { store: "Shop", orders: "Bestellungen", wallet: "Guthaben", settings: "Einstellungen", search: "Produkte suchen...", collections: "Kategorien", all_catalogs: "Alle Kategorien" },
      es: { store: "Tienda", orders: "Pedidos", wallet: "Billetera", settings: "Ajustes", search: "Buscar productos...", collections: "Colecciones", all_catalogs: "Todas las Colecciones" },
      fr: { store: "Boutique", orders: "Commandes", wallet: "Portefeuille", settings: "Paramètres", search: "Rechercher...", collections: "Collections", all_catalogs: "Toutes les Collections" },
      it: { store: "Negozio", orders: "Ordini", wallet: "Portafoglio", settings: "Impostazioni", search: "Cerca prodotti...", collections: "Collezioni", all_catalogs: "Tutte le Collezioni" },
      zh: { store: "商店", orders: "订单", wallet: "钱包", settings: "设置", search: "搜索产品...", collections: "精选分类", all_catalogs: "所有分类" }
    };

    function applyLanguage(lang) {
      const d = I18N[lang] || I18N.en;
      document.getElementById('i18n-nav-store').innerText = d.store;
      document.getElementById('i18n-nav-orders').innerText = d.orders;
      document.getElementById('i18n-nav-wallet').innerText = d.wallet;
      document.getElementById('i18n-nav-settings').innerText = d.settings;
      document.getElementById('catalog-search').placeholder = d.search;
      document.getElementById('label-collections').innerText = d.collections;
      document.getElementById('back-catalog-label').innerText = d.all_catalogs;
      document.documentElement.dir = (lang === 'ar') ? 'rtl' : 'ltr';
    }

    // Tab Switching
    function switchTab(tab) {
      haptic('light');
      activeTab = tab;
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-item').forEach(el => el.classList.remove('active'));

      const view = document.getElementById('view-' + tab);
      if (view) view.classList.add('active');

      const btn = document.getElementById('tab-' + tab);
      if (btn) btn.classList.add('active');

      if (tab === 'orders' || tab === 'wallet' || tab === 'settings') {
        loadUserData();
      }
      if (tab === 'store') {
        exitToCatalogs();
      }
    }

    // Catalog Loading
    async function loadCatalog() {
      try {
        const res = await fetch('/api/catalog');
        const d = await res.json();
        allProducts = d.products || [];
        categoriesList = d.categories || [];
        renderCatalogsGrid();
      } catch (e) {
        document.getElementById('catalogs-list').innerHTML = '<div style="color: var(--ios-secondary-text); text-align: center; padding: 40px;">Failed to load catalog.</div>';
      }
    }

    function renderCatalogsGrid() {
      const container = document.getElementById('catalogs-list');
      const groups = {};
      categoriesList.forEach(c => {
        groups[c] = allProducts.filter(p => p.category === c);
      });

      container.innerHTML = Object.keys(groups).map(catName => {
        const items = groups[catName];
        if (!items || !items.length) return '';
        const meta = CATALOG_META[catName] || { icon: "📦", preview: "Digital goods" };
        const minPrice = Math.min(...items.map(p => p.price || 999));
        const sym = items[0]?.sym || '$';

        return `
          <div class="catalog-card" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
            <div style="display: flex; align-items: center; flex: 1; overflow: hidden;">
              <div class="catalog-icon-box">${meta.icon}</div>
              <div class="catalog-texts">
                <div class="catalog-name">${catName}</div>
                <div class="catalog-sub">
                  <span>${items.length} items</span> ·
                  <span style="color: var(--ios-blue); font-weight: 700;">From ${minPrice.toFixed(2)}${sym}</span>
                </div>
              </div>
            </div>
            <span class="chevron-right">›</span>
          </div>
        `;
      }).join('');
    }

    function openCollection(catName) {
      haptic('medium');
      activeCatalog = catName;
      document.getElementById('collections-container').style.display = 'none';
      document.getElementById('products-container').style.display = 'block';
      document.getElementById('current-collection-title').innerText = catName;

      const filtered = allProducts.filter(p => p.category === catName);
      renderProductRows(filtered);
    }

    function exitToCatalogs() {
      haptic('light');
      activeCatalog = null;
      document.getElementById('catalog-search').value = '';
      document.getElementById('search-clear-btn').style.display = 'none';
      document.getElementById('products-container').style.display = 'none';
      document.getElementById('collections-container').style.display = 'block';
    }

    function quickSearch(kw) {
      document.getElementById('catalog-search').value = kw;
      handleSearchInput();
    }

    function handleSearchInput() {
      const q = (document.getElementById('catalog-search').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('search-clear-btn');

      if (q) {
        clearBtn.style.display = 'flex';
        document.getElementById('collections-container').style.display = 'none';
        document.getElementById('products-container').style.display = 'block';
        document.getElementById('current-collection-title').innerText = `Search: "${q}"`;

        const matched = allProducts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
        renderProductRows(matched);
      } else {
        clearBtn.style.display = 'none';
        exitToCatalogs();
      }
    }

    function clearSearchInput() {
      document.getElementById('catalog-search').value = '';
      exitToCatalogs();
    }

    function renderProductRows(list) {
      const container = document.getElementById('products-list-box');
      if (!list.length) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--ios-secondary-text);">No products found in this category.</div>';
        return;
      }
      container.innerHTML = list.map(p => `
        <div class="product-row" onclick="openProductDetail(${p.id})">
          <div class="product-info">
            <div class="product-title">${p.emoji || '⚡'} ${p.name}</div>
            <div class="product-desc">
              <span>${p.stock ? p.stock + ' left' : 'Instant Delivery'}</span> ·
              <span>${p.delivery_type === 'activation' ? 'Custom Activation' : 'Automated Key'}</span>
            </div>
          </div>
          <div class="product-price-box">
            <div class="product-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
            <div class="stock-label">Tap to view ›</div>
          </div>
        </div>
      `).join('');
    }

    // IN-APP PRODUCT DETAIL PAGE
    function openProductDetail(productId) {
      haptic('medium');
      selectedProduct = allProducts.find(p => p.id === productId);
      if (!selectedProduct) return;
      selectedQty = 1;

      document.getElementById('detail-hero-icon').innerText = selectedProduct.emoji || '⚡';
      document.getElementById('detail-hero-title').innerText = selectedProduct.name;
      document.getElementById('detail-hero-cat').innerText = selectedProduct.category || 'Digital Good';
      document.getElementById('detail-category-tag').innerText = selectedProduct.category || 'Product';
      document.getElementById('detail-hero-desc').innerText = selectedProduct.description || 'Instant automated license activation & credential delivery.';

      const isInstant = selectedProduct.delivery_type !== 'activation';
      document.getElementById('detail-delivery-tag').innerText = isInstant ? '⚡ Automated Delivery' : '⏳ Custom Activation';
      document.getElementById('detail-stock-tag').innerText = selectedProduct.stock ? `🟢 In Stock (${selectedProduct.stock})` : '⚡ Instant Stock';

      updateDetailPrice();

      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      document.getElementById('view-product-page').classList.add('active');
    }

    function exitProductPage() {
      haptic('light');
      document.getElementById('view-product-page').classList.remove('active');
      document.getElementById('view-store').classList.add('active');
    }

    function stepQuantity(delta) {
      haptic('light');
      selectedQty = Math.max(1, Math.min(10, selectedQty + delta));
      document.getElementById('stepper-val').innerText = selectedQty;
      updateDetailPrice();
    }

    function updateDetailPrice() {
      if (!selectedProduct) return;
      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      const sym = selectedProduct.sym || '$';

      // Bulk Wholesale Discount Matrix
      let bulkPct = 0;
      if (selectedQty >= 10) bulkPct = 15;
      else if (selectedQty >= 5) bulkPct = 7;

      // VIP discount
      let vipPct = userData?.vip_discount || 0;
      let totalDiscount = Math.max(bulkPct, vipPct);

      let discountText = '';
      if (totalDiscount > 0) {
        const discVal = total * (totalDiscount / 100);
        total = Math.max(0.01, total - discVal);
        discountText = `Discount: -${totalDiscount}% applied!`;
      }
      document.getElementById('detail-discount-note').innerText = discountText;
      document.getElementById('detail-total-price').innerText = `${total.toFixed(2)}${sym}`;
      document.getElementById('btn-buy-total-tag').innerText = `(${total.toFixed(2)}${sym})`;

      // Balance check
      const userBalance = userData?.balance || 0.0;
      const alertBox = document.getElementById('insufficient-funds-banner');
      const buyBtn = document.getElementById('btn-inapp-buy');

      if (userBalance < total) {
        alertBox.style.display = 'block';
        alertBox.innerHTML = `⚠️ Insufficient balance for this order (Need ${total.toFixed(2)}${sym}, have $${userBalance.toFixed(2)}).`;
        buyBtn.innerHTML = `<span>💳 Top up Balance to Buy</span>`;
        buyBtn.onclick = () => switchTab('wallet');
      } else {
        alertBox.style.display = 'none';
        buyBtn.innerHTML = `<span>⚡ Instant Buy</span> <span>(${total.toFixed(2)}${sym})</span>`;
        buyBtn.onclick = submitInAppBuy;
      }
    }

    // IN-APP CHECKOUT (POST /api/buy)
    async function submitInAppBuy() {
      if (!selectedProduct || !userId) {
        showToast('Please open inside Telegram to buy');
        return;
      }

      // Biometric Verification for high-value orders ($50+)
      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      if (total >= 50.0 && tg?.BiometricManager?.isBiometricAvailable) {
        tg.BiometricManager.authenticate({ reason: `Confirm high-value purchase of ${selectedProduct.name}` }, (success) => {
          if (success) processBuyRequest();
          else showToast('Biometric confirmation cancelled');
        });
        return;
      }

      processBuyRequest();
    }

    async function processBuyRequest() {
      haptic('medium');
      const buyBtn = document.getElementById('btn-inapp-buy');
      buyBtn.disabled = true;
      buyBtn.innerHTML = '<span>⏳ Processing Order...</span>';

      try {
        const res = await fetch('/api/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            product_id: selectedProduct.id,
            quantity: selectedQty
          })
        });
        const d = await res.json();
        buyBtn.disabled = false;

        if (d.status === 'success') {
          fireConfetti();
          haptic('success');

          if (userData) {
            userData.balance = Math.max(0, userData.balance - d.total_paid);
            updateBalanceHeaders();
          }

          // Show in-app success screen
          document.getElementById('success-sub').innerText = `Order #${d.order_id} · ${d.product_name} (${d.quantity}×)`;
          const keysContainer = document.getElementById('delivered-keys-box');
          if (d.goods && d.goods.length) {
            keysContainer.innerHTML = d.goods.map(g => `
              <div class="code-box" onclick="copyLicenseKey('${g.replace(/'/g, "\\\\'")}')">
                <code>${g}</code>
                <div style="font-size: 10px; color: var(--ios-secondary-text); margin-top: 4px;">📋 Tap to copy credentials</div>
              </div>
            `).join('');
          } else {
            keysContainer.innerHTML = '<div style="padding: 12px; color: var(--ios-orange); text-align: center;">⏳ Custom activation in progress. You will receive keys shortly.</div>';
          }

          document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
          document.getElementById('view-order-success').classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || 'Purchase failed.');
          updateDetailPrice();
        }
      } catch (e) {
        buyBtn.disabled = false;
        haptic('error');
        showToast('Connection error. Please try again.');
        updateDetailPrice();
      }
    }

    // Direct Telegram Stars Invoice Checkout (openInvoice)
    async function payDirectStars() {
      if (!selectedProduct || !userId) return;
      haptic('medium');
      try {
        const res = await fetch('/api/invoice/stars', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            product_id: selectedProduct.id,
            quantity: selectedQty
          })
        });
        const d = await res.json();
        if (d.status === 'ok' && d.invoice_link) {
          // Native Telegram Stars Invoice Sheet
          tg.openInvoice(d.invoice_link, (status) => {
            if (status === 'paid') {
              fireConfetti();
              showToast('Stars Payment Successful!');
              switchTab('orders');
            } else if (status === 'failed') {
              showToast('Stars payment failed');
            }
          });
        } else {
          showToast('Could not open Stars invoice');
        }
      } catch (e) {
        showToast('Invoice network error');
      }
    }

    // In-App Top-Up Rails (openInvoice & openLink)
    async function startTopup(amount) {
      haptic('medium');
      if (!userId) return;
      try {
        const res = await fetch('/api/invoice/topup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, amount: amount, method: 'stars' })
        });
        const d = await res.json();
        if (d.status === 'ok' && d.invoice_link) {
          tg.openInvoice(d.invoice_link, (status) => {
            if (status === 'paid') {
              fireConfetti();
              showToast(`+$${amount} Balance Credited!`);
              loadUserData();
            }
          });
        }
      } catch (e) {
        showToast('Could not create top-up invoice');
      }
    }

    async function startRailTopup(rail) {
      haptic('medium');
      if (!userId) return;
      try {
        const res = await fetch('/api/invoice/topup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, amount: 25.0, method: rail })
        });
        const d = await res.json();
        if (d.type === 'stars' && d.invoice_link) {
          tg.openInvoice(d.invoice_link, (status) => {
            if (status === 'paid') {
              fireConfetti();
              showToast('Balance Credited!');
              loadUserData();
            }
          });
        } else if (d.type === 'url' && d.url) {
          tg.openLink(d.url);
        }
      } catch (e) {
        showToast('Payment rail unavailable');
      }
    }

    async function redeemVoucher() {
      const code = (document.getElementById('voucher-input').value || '').trim();
      if (!code || !userId) return;
      haptic('medium');
      try {
        const res = await fetch('/api/voucher/redeem', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, code: code })
        });
        const d = await res.json();
        if (d.status === 'success') {
          fireConfetti();
          showToast(d.message || 'Voucher redeemed!');
          document.getElementById('voucher-input').value = '';
          loadUserData();
        } else {
          showToast(d.error || 'Invalid voucher code');
        }
      } catch (e) {
        showToast('Redemption failed');
      }
    }

    // User Profile & Orders Loading
    async function loadUserData() {
      if (!userId) {
        renderEmptyOrdersState();
        return;
      }
      try {
        const res = await fetch('/api/user-data?tg_id=' + userId);
        const d = await res.json();
        if (d.error) {
          renderEmptyOrdersState();
          return;
        }
        userData = d;
        updateBalanceHeaders();

        // Real Profile Picture (from Telegram Bot API)
        const avatarContainer = document.getElementById('avatar-container');
        const settingsAvatar = document.getElementById('settings-avatar-container');
        const firstLetter = (tgUser?.first_name || d.username || 'U')[0].toUpperCase();

        if (d.photo_url) {
          avatarContainer.innerHTML = `<img src="${d.photo_url}" class="avatar-img" alt="Avatar">`;
          settingsAvatar.innerHTML = `<img src="${d.photo_url}" class="avatar-img" style="width: 48px; height: 48px;" alt="Avatar">`;
        } else {
          document.getElementById('avatar-initial').innerText = firstLetter;
          document.getElementById('settings-avatar-initial').innerText = firstLetter;
        }

        // Settings View Info
        const displayName = tgUser?.first_name ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : (d.username ? '@' + d.username : 'Customer');
        document.getElementById('settings-name-label').innerText = displayName;
        document.getElementById('settings-tgid-label').innerText = 'ID: ' + d.telegram_id;
        document.getElementById('settings-vip-pill').innerHTML = `<span class="vip-tag">${d.vip_tier} (-${d.vip_discount}% discount)</span>`;

        // VIP Progress Bar
        const spent = d.total_spent || 0.0;
        let nextTarget = 100.0;
        let nextLabel = "Silver VIP (3% off)";
        if (spent >= 500) { nextTarget = 1000.0; nextLabel = "Platinum VIP (10% off)"; }
        else if (spent >= 100) { nextTarget = 500.0; nextLabel = "Gold VIP (7% off)"; }
        const pct = Math.min(100, Math.round((spent / nextTarget) * 100));
        document.getElementById('next-vip-label').innerText = nextLabel;
        document.getElementById('vip-progress-pct').innerText = `${pct}% ($${spent.toFixed(0)} / $${nextTarget.toFixed(0)})`;
        document.getElementById('vip-progress-bar').style.width = `${pct}%`;

        // Referral Link
        const refLink = `https://t.me/${d.bot_username}?start=${d.referral_code || ''}`;
        document.getElementById('ref-link-val').innerText = refLink;

        // Active Chips
        document.querySelectorAll('#curr-chips .trend-chip').forEach(el => {
          el.classList.toggle('active', el.innerText.includes(d.currency_preference));
        });
        document.querySelectorAll('#lang-chips .trend-chip').forEach(el => {
          el.classList.toggle('active', el.getAttribute('onclick')?.includes(`'${d.language}'`));
        });
        applyLanguage(d.language || 'en');

        // Render Orders
        renderOrders(d.orders || []);
      } catch (e) {
        renderEmptyOrdersState();
      }
    }

    function updateBalanceHeaders() {
      if (!userData) return;
      document.getElementById('top-balance-str').innerText = userData.display_balance || `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-hero').innerText = `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-approx').innerText = userData.currency_preference !== 'USD'
        ? `≈ ${userData.display_balance}`
        : 'Available for instant purchases';

      if (userData.vip_tier && userData.vip_tier !== 'Standard') {
        const vipTag = document.getElementById('top-vip');
        vipTag.innerText = userData.vip_tier;
        vipTag.style.display = 'inline-block';
      }
    }

    function renderEmptyOrdersState() {
      document.getElementById('orders-list-box').innerHTML = `
        <div style="text-align: center; padding: 40px 16px; color: var(--ios-secondary-text);">
          <div style="font-size: 40px; margin-bottom: 8px;">📦</div>
          <div style="font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 4px;">No Orders Yet</div>
          <p style="font-size: 13px; margin-bottom: 16px;">Explore collections and purchase products directly in the app!</p>
          <button class="ios-btn-primary" onclick="switchTab('store')" style="width: auto; padding: 0 24px; margin: 0 auto; height: 42px;">Browse Store</button>
        </div>
      `;
    }

    function renderOrders(orders) {
      const container = document.getElementById('orders-list-box');
      if (!orders.length) {
        renderEmptyOrdersState();
        return;
      }
      container.innerHTML = orders.map(o => `
        <div class="inset-card" style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="font-size: 15px;">#${o.id} · ${o.created_at || ''}</strong>
            <span class="status-tag status-${o.status.includes('completed') ? 'completed' : o.status.includes('fail') ? 'failed' : 'pending'}">${o.status}</span>
          </div>
          <div style="font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 2px;">${o.products}</div>
          <div style="font-size: 13px; color: var(--ios-blue); font-weight: 700; margin-bottom: 8px;">Total: ${o.total.toFixed(2)}${o.sym}</div>

          <!-- Order Lifecycle Stepper -->
          <div class="timeline-wrapper">
            <div class="timeline-line"></div>
            <div class="step-item">
              <div class="step-dot done">✓</div>
              <div class="step-label">Placed</div>
            </div>
            <div class="step-item">
              <div class="step-dot ${o.status.includes('completed') ? 'done' : 'active'}">${o.status.includes('completed') ? '✓' : '●'}</div>
              <div class="step-label">Fulfilling</div>
            </div>
            <div class="step-item">
              <div class="step-dot ${o.status.includes('completed') ? 'done' : ''}">${o.status.includes('completed') ? '✓' : '○'}</div>
              <div class="step-label">Delivered</div>
            </div>
          </div>

          ${o.goods && o.goods.length ? o.goods.map(g => `
            <div class="code-box" onclick="copyLicenseKey('${g.replace(/'/g, "\\\\'")}')">
              <code>${g}</code>
              <div style="font-size: 10px; color: var(--ios-secondary-text); margin-top: 4px;">📋 Tap to copy credentials</div>
            </div>
          `).join('') : ''}

          <div style="display: flex; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: var(--ios-hairline);">
            ${o.status.includes('completed') ? `
              <button class="ios-btn-secondary" onclick="openReviewDialog(${o.id})">⭐ Rate Order</button>
            ` : ''}
            ${o.warranty_days && !o.warranty_claimed && o.status.includes('completed') ? `
              <button class="ios-btn-secondary" onclick="claimWarrantyAction(${o.id})">🛡️ Warranty</button>
            ` : ''}
          </div>
        </div>
      `).join('');
    }

    function copyLicenseKey(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Credentials copied to clipboard!');
      });
    }

    function copyRefLink() {
      const link = document.getElementById('ref-link-val').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast('Referral link copied!');
      });
    }

    async function selectCurrency(code) {
      haptic('light');
      document.querySelectorAll('#curr-chips .trend-chip').forEach(el => {
        el.classList.toggle('active', el.innerText.includes(code));
      });
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, currency: code })
        });
        showToast(`Currency set to ${code}`);
        loadUserData();
      }
    }

    async function selectLanguage(code) {
      haptic('light');
      applyLanguage(code);
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, language: code })
        });
        showToast('Language updated!');
        loadUserData();
      }
    }

    async function claimWarrantyAction(orderId) {
      haptic('medium');
      try {
        const res = await fetch('/api/warranty/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, order_id: orderId })
        });
        const d = await res.json();
        if (d.status === 'success') {
          fireConfetti();
          showToast('Warranty Approved! New keys issued.');
          loadUserData();
        } else {
          showToast('Warranty submitted for review.');
        }
      } catch (e) {
        showToast('Warranty claim failed');
      }
    }

    // Review Modal Functions
    function openReviewDialog(orderId) {
      reviewTargetOrderId = orderId;
      setStarRating(5);
      document.getElementById('review-modal').classList.add('open');
    }

    function closeReviewModal() {
      document.getElementById('review-modal').classList.remove('open');
    }

    function setStarRating(r) {
      haptic('light');
      selectedStarRating = r;
      const spans = document.querySelectorAll('#stars-row span');
      spans.forEach((s, idx) => {
        s.style.opacity = idx < r ? '1' : '0.25';
      });
    }

    async function submitReviewAction() {
      haptic('medium');
      const txt = (document.getElementById('review-text-input').value || '').trim();
      try {
        await fetch('/api/reviews/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            rating: selectedStarRating,
            text: txt,
            order_id: reviewTargetOrderId
          })
        });
        fireConfetti();
        showToast('Thank you for your review!');
        closeReviewModal();
      } catch (e) {
        showToast('Could not submit review');
      }
    }

    // Real-Time Server-Sent Events (SSE) for Live Restock Updates
    function initSSE() {
      try {
        const evSource = new EventSource('/api/events');
        evSource.onmessage = (e) => {
          if (e.data && e.data !== 'ping') {
            loadCatalog();
          }
        };
      } catch (e) {}
    }

    // Initial Startup
    loadCatalog();
    loadUserData();
    initSSE();
  </script>
</body>
</html>
"""
