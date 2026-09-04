"""Telegram Mini App (TMA) Mobile-First Storefront.

Features:
- Floating Liquid Glass Flyout Navbar (translucent, glossy reflection, smooth active pill, safe-area).
- Arabic First by default with full RTL support (plus English, German, Spanish, French, Italian, Chinese).
- Homepage Catalog Cards Grid (AI & Chatbots, Streaming, VPN, Design, Productivity) with item counts, starting prices, and '← All Catalogs' drill-down.
- Robust Markdown & HTML Product Description Formatter (handles **bold**, *italic*, bullets, line breaks, <tg-emoji>).
- Fixed Product Exploration (Number-safe matching so entering any product never breaks navigating others).
- Dedicated In-App Product Page with live balance check, quantity stepper, volume discounts, and instant in-app checkout (POST /api/buy) — no text chat redirect!
- In-App Order Success Screen with copyable credentials and confetti particle burst.
- Real Telegram profile picture via bot.get_user_profile_photos().
- Orders page with timeline stepper, 1-tap copy, in-app warranty claim, and in-app review dialog.
"""

STOREFRONT_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>GH Store</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      --bg: #090e1a;
      --card: #151d30;
      --card-hover: #1c263e;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.2);
      --text: #f8fafc;
      --hint: #94a3b8;
      --border: rgba(255, 255, 255, 0.1);
      --glass-border: rgba(255, 255, 255, 0.18);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --nav-height: 62px;
      --safe-bottom: env(safe-area-inset-bottom, 16px);
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding-bottom: calc(var(--nav-height) + var(--safe-bottom) + 36px);
      user-select: none;
      -webkit-user-select: none;
      overflow-x: hidden;
    }

    /* Top Sticky Navigation Bar */
    .top-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(28px) saturate(200%);
      -webkit-backdrop-filter: blur(28px) saturate(200%);
      background: rgba(9, 14, 26, 0.88);
      border-bottom: 1px solid var(--border);
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
      border: 1.5px solid var(--accent);
    }
    .avatar-fallback {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #6366f1);
      color: white;
      font-size: 15px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .header-meta h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .vip-tag {
      background: rgba(245, 158, 11, 0.18);
      color: var(--warning);
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
    }
    .header-balance-btn {
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: var(--accent);
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 5px;
      cursor: pointer;
      box-shadow: 0 2px 8px var(--accent-glow);
    }
    .header-balance-btn:active { transform: scale(0.96); }

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

    /* Search Bar */
    .search-box {
      position: relative;
      margin-bottom: 12px;
    }
    .search-box input {
      width: 100%;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      color: var(--text);
      padding: 11px 40px 11px 16px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    [dir="ltr"] .search-box input {
      padding: 11px 16px 11px 40px;
    }
    .search-box input:focus { border-color: var(--accent); }
    .search-icon {
      position: absolute;
      right: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--hint);
    }
    [dir="ltr"] .search-icon { right: auto; left: 14px; }
    .clear-search {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 13px;
      color: var(--hint);
      cursor: pointer;
      display: none;
    }
    [dir="ltr"] .clear-search { left: auto; right: 14px; }

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
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--hint);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 13px;
      border-radius: 16px;
      white-space: nowrap;
      cursor: pointer;
      transition: all 0.15s;
    }
    .trend-chip:active { background: rgba(56, 189, 248, 0.18); color: #fff; border-color: var(--accent); }

    /* Promotional Hero Banner */
    .hero-banner {
      background: linear-gradient(135deg, #1e293b, #0f172a);
      border: 1px solid var(--glass-border);
      border-radius: 16px;
      padding: 16px 18px;
      margin-bottom: 16px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      position: relative;
      overflow: hidden;
    }
    .hero-banner::after {
      content: '';
      position: absolute;
      width: 120px;
      height: 120px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.25) 0%, transparent 70%);
      top: -20px;
      left: -20px;
    }
    .banner-badge {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--accent);
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .banner-title { font-size: 16px; font-weight: 700; margin-bottom: 2px; }
    .banner-sub { font-size: 12px; color: var(--hint); }

    /* Section Header */
    .section-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--hint);
      margin: 16px 0 10px 4px;
    }

    /* Homepage Catalog Cards Grid */
    .catalogs-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
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
      background: var(--card-hover);
    }
    .catalog-left {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1;
      overflow: hidden;
    }
    .catalog-icon-box {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.05);
      font-size: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .catalog-info {
      flex: 1;
      overflow: hidden;
    }
    .catalog-name {
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 3px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .catalog-sub {
      font-size: 12px;
      color: var(--hint);
    }
    .chevron {
      color: var(--hint);
      font-size: 18px;
      font-weight: 700;
      margin-left: 8px;
    }

    /* Subview Header (inside category) */
    .subview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .btn-back-catalog {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--accent);
      border-radius: 10px;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }
    .btn-back-catalog:active { opacity: 0.7; }

    /* Product Row Item */
    .product-row {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
      transition: transform 0.15s, border-color 0.15s;
    }
    .product-row:active {
      transform: scale(0.99);
      border-color: var(--accent);
      background: var(--card-hover);
    }
    .prod-left {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      overflow: hidden;
    }
    .prod-icon {
      font-size: 24px;
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .prod-details {
      flex: 1;
      overflow: hidden;
    }
    .prod-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .prod-desc {
      font-size: 12px;
      color: var(--hint);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .prod-price-box {
      text-align: left;
      flex-shrink: 0;
    }
    [dir="ltr"] .prod-price-box { text-align: right; }
    .prod-price {
      font-size: 16px;
      font-weight: 800;
      color: var(--accent);
    }
    .prod-tap-hint {
      font-size: 11px;
      color: var(--hint);
      margin-top: 2px;
    }

    /* IN-APP DEDICATED PRODUCT DETAIL PAGE */
    .page-hero {
      text-align: center;
      padding: 20px 0;
      background: radial-gradient(circle at center, rgba(56, 189, 248, 0.12), transparent 70%);
      border-radius: 18px;
      margin-bottom: 14px;
    }
    .hero-icon { font-size: 54px; margin-bottom: 8px; }
    .hero-name { font-size: 22px; font-weight: 800; letter-spacing: -0.3px; margin-bottom: 4px; }
    .hero-cat { font-size: 12px; color: var(--accent); text-transform: uppercase; font-weight: 700; }
    .inset-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 12px;
    }
    .badges-flex {
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .pill-badge {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
    }

    /* Rich Description Formatted Container */
    .rich-desc-container {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text);
      word-break: break-word;
    }
    .rich-desc-container .desc-heading {
      font-size: 15px;
      font-weight: 700;
      color: #38bdf8;
      margin: 10px 0 4px 0;
    }
    .rich-desc-container .desc-bullet {
      margin: 4px 0 4px 10px;
    }
    .rich-desc-container .desc-inline-code {
      background: rgba(0, 0, 0, 0.35);
      color: #38bdf8;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 13px;
    }
    .rich-desc-container a { color: #38bdf8; text-decoration: underline; }

    /* Stepper & Action Controls */
    .stepper-capsule {
      display: inline-flex;
      align-items: center;
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
    }
    .stepper-btn {
      width: 38px;
      height: 34px;
      border: none;
      background: transparent;
      color: var(--accent);
      font-size: 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .stepper-btn:active { background: rgba(255, 255, 255, 0.08); }
    .stepper-divider { width: 1px; height: 20px; background: var(--border); }
    .stepper-val { padding: 0 14px; font-size: 15px; font-weight: 700; }

    /* iPhone Action Buttons */
    .btn-action-primary {
      width: 100%;
      height: 50px;
      border-radius: 14px;
      background: #007aff;
      color: #ffffff;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.3px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      box-shadow: 0 4px 16px rgba(0, 122, 255, 0.35);
      transition: opacity 0.15s, transform 0.15s;
    }
    .btn-action-primary:active { opacity: 0.8; transform: scale(0.98); }
    .btn-action-secondary {
      background: rgba(120, 120, 128, 0.18);
      color: var(--accent);
      border: none;
      border-radius: 10px;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }
    .btn-action-secondary:active { opacity: 0.7; }
    .btn-stars-checkout {
      width: 100%;
      height: 50px;
      border-radius: 14px;
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: #ffffff;
      font-size: 16px;
      font-weight: 700;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-top: 10px;
      box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
    }
    .btn-stars-checkout:active { opacity: 0.8; transform: scale(0.98); }

    /* Timeline Stepper for Orders */
    .timeline-box {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 14px 0;
      position: relative;
    }
    .timeline-track {
      position: absolute;
      top: 50%;
      right: 20px;
      left: 20px;
      height: 2px;
      background: rgba(255, 255, 255, 0.1);
      z-index: 1;
      transform: translateY(-50%);
    }
    .timeline-node {
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
    }
    .node-circle {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--card);
      border: 2px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 9px;
      font-weight: 700;
    }
    .node-circle.done { background: var(--success); border-color: var(--success); color: #fff; }
    .node-circle.active { background: var(--warning); border-color: var(--warning); animation: pulseDot 1.5s infinite; }
    @keyframes pulseDot {
      0% { transform: scale(1); }
      50% { transform: scale(1.2); }
      100% { transform: scale(1); }
    }
    .node-label { font-size: 10px; color: var(--hint); font-weight: 600; }

    /* Copyable Code Box */
    .copyable-box {
      background: rgba(0, 0, 0, 0.4);
      border: 1px dashed rgba(56, 189, 248, 0.4);
      border-radius: 10px;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, monospace;
      font-size: 13px;
      color: #38bdf8;
      word-break: break-all;
      margin: 8px 0;
      cursor: pointer;
    }
    .copyable-box:active { background: rgba(56, 189, 248, 0.15); }

    /* FLOATING LIQUID GLASS BOTTOM NAVBAR (Flyout Island) */
    .liquid-glass-nav {
      position: fixed;
      bottom: calc(var(--safe-bottom) + 10px);
      left: 16px;
      right: 16px;
      margin: 0 auto;
      max-width: 440px;
      height: var(--nav-height);
      border-radius: 36px;
      background: rgba(18, 24, 40, 0.72);
      backdrop-filter: blur(36px) saturate(220%);
      -webkit-backdrop-filter: blur(36px) saturate(220%);
      border: 1px solid var(--glass-border);
      box-shadow: 
        0 16px 40px rgba(0, 0, 0, 0.6),
        0 4px 12px rgba(0, 0, 0, 0.35),
        inset 0 1px 1px rgba(255, 255, 255, 0.35);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
      padding: 0 10px;
    }
    .liquid-tab-item {
      flex: 1;
      height: 48px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: #94a3b8;
      cursor: pointer;
      border-radius: 24px;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .liquid-tab-item.active {
      color: #38bdf8;
      background: rgba(56, 189, 248, 0.14);
    }
    .liquid-tab-item svg {
      width: 20px;
      height: 20px;
      fill: currentColor;
    }
    .liquid-tab-label {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: -0.2px;
    }

    /* Skeleton Loader */
    .skeleton-card {
      background: var(--card);
      border-radius: 14px;
      height: 76px;
      margin-bottom: 10px;
      position: relative;
      overflow: hidden;
    }
    .skeleton-card::after {
      content: '';
      position: absolute;
      inset: 0;
      transform: translateX(-100%);
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.05), transparent);
      animation: shimmer 1.5s infinite;
    }
    @keyframes shimmer { 100% { transform: translateX(100%); } }

    /* Canvas Confetti */
    #confetti-canvas {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 200;
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
      font-weight: 700;
      z-index: 250;
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .toast-pill.show { transform: translateX(-50%) translateY(0); }
  </style>
</head>
<body>
  <canvas id="confetti-canvas"></canvas>
  <div class="toast-pill" id="toast">تم النسخ!</div>

  <!-- Top Sticky Bar -->
  <header class="top-header">
    <div class="header-user" onclick="switchTab('settings')">
      <div id="top-avatar-box">
        <div class="avatar-fallback" id="top-avatar-initial">U</div>
      </div>
      <div class="header-meta">
        <h1>🛍️ GH Store <span class="vip-tag" id="top-vip-tag" style="display: none;">VIP</span></h1>
        <span id="top-sub-caption">المتجر الرقمي المعتمد</span>
      </div>
    </div>
    <div class="header-balance-btn" onclick="switchTab('wallet')">
      <span id="top-balance-str">$0.00</span>
      <span>➕</span>
    </div>
  </header>

  <!-- TAB 1: STORE VIEW -->
  <main id="view-store" class="tab-view active">
    <!-- Search Bar -->
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="store-search-input" placeholder="ابحث عن كلود، جيميني، نتفلكس، في بي ان..." oninput="handleSearch()">
      <span class="clear-search" id="store-clear-btn" onclick="clearSearch()">✕</span>
    </div>

    <!-- Trending Quick Chips -->
    <div class="trending-chips" id="trending-chips">
      <div class="trend-chip" onclick="applyTrend('Claude')">🧠 Claude 3.5</div>
      <div class="trend-chip" onclick="applyTrend('Gemini')">✨ Gemini Pro</div>
      <div class="trend-chip" onclick="applyTrend('ChatGPT')">🤖 ChatGPT 4o</div>
      <div class="trend-chip" onclick="applyTrend('Netflix')">🎬 Netflix 4K</div>
      <div class="trend-chip" onclick="applyTrend('VPN')">🛡️ NordVPN</div>
    </div>

    <!-- Promotional Hero Banner -->
    <div class="hero-banner">
      <div class="banner-badge" id="banner-badge-text">تحديثات المتجر</div>
      <div class="banner-title" id="banner-title-text">✨ اشتراكات كلود وجيميني متوفرة فورياً</div>
      <div class="banner-sub" id="banner-sub-text">تسليم تلقائي فوري للمفاتيح والحسابات على مدار الساعة</div>
    </div>

    <!-- Mode A: Catalogs Cards Grid (Homepage Collections) -->
    <div id="catalogs-collection-mode">
      <div class="section-title" id="title-collections">التصنيفات المميزة</div>
      <div class="catalogs-grid" id="catalogs-grid">
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
      </div>
    </div>

    <!-- Mode B: Products in Selected Collection -->
    <div id="products-catalog-mode" style="display: none;">
      <div class="subview-header">
        <button class="btn-back-catalog" onclick="returnToCollections()">
          <span>→</span>
          <span id="btn-back-to-catalogs">جميع التصنيفات</span>
        </button>
        <div style="font-size: 16px; font-weight: 700;" id="active-collection-title">التصنيف</div>
      </div>
      <div id="catalog-products-list"></div>
    </div>
  </main>

  <!-- DEDICATED IN-APP PRODUCT DETAIL PAGE -->
  <section id="view-product-detail" class="tab-view">
    <div class="subview-header">
      <button class="btn-back-catalog" onclick="closeProductDetailPage()">
        <span>→</span>
        <span id="btn-back-product">رجوع</span>
      </button>
      <span style="font-size: 13px; color: var(--accent); font-weight: 700;" id="detail-category-header">المنتج</span>
    </div>

    <div class="page-hero">
      <div class="hero-icon" id="prod-hero-icon">⚡</div>
      <h2 class="hero-name" id="prod-hero-name">اسم المنتج</h2>
      <div class="hero-cat" id="prod-hero-cat">حساب رقمي</div>
    </div>

    <div class="badges-flex">
      <div class="pill-badge" id="prod-delivery-badge">⚡ تسليم تلقائي فوري</div>
      <div class="pill-badge" id="prod-warranty-badge">🛡️ ضمان 30 يوم</div>
      <div class="pill-badge" id="prod-stock-badge">🟢 متوفر</div>
    </div>

    <div class="inset-card">
      <div style="font-size: 12px; font-weight: 700; color: var(--hint); margin-bottom: 6px;" id="label-desc-title">الوصف</div>
      <div class="rich-desc-container" id="prod-rich-desc">تسليم فوري للمفاتيح.</div>
    </div>

    <div class="inset-card">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
        <div>
          <div style="font-size: 12px; color: var(--hint);" id="label-total-title">السعر الإجمالي</div>
          <div style="font-size: 24px; font-weight: 800; color: var(--accent);" id="prod-total-price">$0.00</div>
          <div style="font-size: 12px; color: var(--success); font-weight: 700;" id="prod-discount-tag"></div>
        </div>
        <div class="stepper-capsule">
          <button class="stepper-btn" onclick="adjustQty(-1)">–</button>
          <div class="stepper-divider"></div>
          <span class="stepper-val" id="prod-qty-val">1</span>
          <div class="stepper-divider"></div>
          <button class="stepper-btn" onclick="adjustQty(1)">+</button>
        </div>
      </div>

      <div id="insufficient-funds-alert" style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 10px; padding: 10px; text-align: center; font-size: 13px; color: #fca5a5; margin-bottom: 12px; display: none;">
        ⚠️ الرصيد المتاح غير كافٍ لهذا الطلب.
      </div>

      <button class="btn-action-primary" id="btn-inapp-purchase" onclick="executeProductBuy()">
        <span>⚡ شراء فوري</span>
        <span id="btn-price-tag">($0.00)</span>
      </button>

      <button class="btn-stars-checkout" id="btn-stars-purchase" onclick="executeStarsDirectBuy()">
        <span>⭐ الدفع عبر نجوم تيليجرام</span>
      </button>
    </div>
  </section>

  <!-- IN-APP ORDER SUCCESS VIEW -->
  <section id="view-order-success" class="tab-view">
    <div style="text-align: center; padding: 24px 0 16px 0;">
      <div style="font-size: 60px; margin-bottom: 8px;">🎉</div>
      <h2 style="font-size: 22px; font-weight: 800; margin-bottom: 4px;">تم الطلب بنجاح!</h2>
      <p style="font-size: 13px; color: var(--hint);" id="success-meta-sub">طلب #000 · تم التسليم</p>
    </div>

    <div class="inset-card">
      <div style="font-size: 12px; font-weight: 700; color: var(--hint); margin-bottom: 8px;">بيانات الحساب / المفاتيح المسلمة</div>
      <div id="success-delivered-keys"></div>
      <div style="font-size: 11px; color: var(--hint); text-align: center; margin-top: 6px;">
        انقر على أي كود بالأعلى للنسخ الفوري!
      </div>
    </div>

    <div style="display: flex; gap: 10px;">
      <button class="btn-action-secondary" onclick="switchTab('orders')" style="flex: 1; height: 48px;">📦 عرض في طلباتي</button>
      <button class="btn-action-primary" onclick="switchTab('store')" style="flex: 1; height: 48px;">🛍️ متابعة التسوق</button>
    </div>
  </section>

  <!-- TAB 2: ORDERS VIEW -->
  <main id="view-orders" class="tab-view">
    <div class="section-title" id="title-orders-history">سجل الطلبات والمشتريات</div>
    <div id="orders-container-box">
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    </div>
  </main>

  <!-- TAB 3: WALLET VIEW -->
  <main id="view-wallet" class="tab-view">
    <div class="hero-banner" style="text-align: center; padding: 24px 16px;">
      <div style="font-size: 12px; color: var(--hint); text-transform: uppercase; letter-spacing: 0.5px;">الرصيد المتاح للشراء</div>
      <div style="font-size: 36px; font-weight: 800; margin: 4px 0;" id="wallet-balance-hero">$0.00</div>
      <div style="font-size: 13px; color: var(--accent); font-weight: 700;" id="wallet-balance-approx">جاهز للشراء الفوري</div>
    </div>

    <!-- VIP Progress Bar -->
    <div class="inset-card" style="padding: 14px;">
      <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
        <span>التقدم نحو رتبة <strong id="next-vip-rank" style="color: var(--warning);">Gold VIP</strong></span>
        <span id="vip-progress-num" style="color: var(--accent); font-weight: 700;">60%</span>
      </div>
      <div style="width: 100%; height: 6px; background: var(--card-hover); border-radius: 3px; overflow: hidden;">
        <div id="vip-progress-fill" style="width: 0%; height: 100%; background: var(--accent); transition: width 0.3s;"></div>
      </div>
    </div>

    <div class="section-title">شحن رصيد سريع</div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px;">
      <div class="btn-action-secondary" style="text-align: center; padding: 12px 0;" onclick="triggerQuickTopup(10)">+$10</div>
      <div class="btn-action-secondary" style="text-align: center; padding: 12px 0;" onclick="triggerQuickTopup(25)">+$25</div>
      <div class="btn-action-secondary" style="text-align: center; padding: 12px 0;" onclick="triggerQuickTopup(50)">+$50</div>
      <div class="btn-action-secondary" style="text-align: center; padding: 12px 0;" onclick="triggerQuickTopup(100)">+$100</div>
    </div>

    <div class="section-title">طرق الدفع والشحن</div>
    <div class="product-row" onclick="triggerRailPayment('stars')">
      <div class="prod-left">
        <span style="font-size: 26px;">⭐</span>
        <div>
          <div style="font-weight: 700; font-size: 15px;">نجوم تيليجرام (Telegram Stars)</div>
          <div style="font-size: 12px; color: var(--hint);">دفع فوري عبر Apple Pay أو Google Pay</div>
        </div>
      </div>
      <span class="chevron">‹</span>
    </div>

    <div class="product-row" onclick="triggerRailPayment('crypto')">
      <div class="prod-left">
        <span style="font-size: 26px;">🪙</span>
        <div>
          <div style="font-weight: 700; font-size: 15px;">العملات الرقمية (Crypto)</div>
          <div style="font-size: 12px; color: var(--hint);">USDT, BTC, SOL عبر KryptoExpress</div>
        </div>
      </div>
      <span class="chevron">‹</span>
    </div>

    <div class="product-row" onclick="triggerRailPayment('sam')">
      <div class="prod-left">
        <span style="font-size: 26px;">📱</span>
        <div>
          <div style="font-weight: 700; font-size: 15px;">سيرياتيل كاش وشام كاش (SAM)</div>
          <div style="font-size: 12px; color: var(--hint);">دفع مباشر عبر المحافظ السورية</div>
        </div>
      </div>
      <span class="chevron">‹</span>
    </div>

    <div class="section-title">شحن عبر كرت هدية (Voucher)</div>
    <div class="inset-card" style="display: flex; gap: 8px; padding: 10px;">
      <input type="text" id="voucher-code-input" placeholder="GH-XXXX-YYYY" style="flex: 1; background: transparent; border: none; color: #fff; font-size: 14px; outline: none; font-family: monospace; text-transform: uppercase;">
      <button class="btn-action-secondary" onclick="submitVoucherRedeem()" style="padding: 6px 14px;">شحن</button>
    </div>
  </main>

  <!-- TAB 4: SETTINGS VIEW -->
  <main id="view-settings" class="tab-view">
    <div class="inset-card" style="display: flex; align-items: center; gap: 14px;">
      <div id="settings-avatar-box">
        <div class="avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">U</div>
      </div>
      <div>
        <div style="font-size: 17px; font-weight: 800;" id="user-name-title">العميل</div>
        <div style="font-size: 12px; color: var(--hint); font-family: monospace;" id="user-tg-num">ID: 000000000</div>
        <div style="margin-top: 4px;" id="user-vip-pill-box"></div>
      </div>
    </div>

    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;">💱 عملة العرض المفضلة</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="currency-picker-chips">
        <div class="trend-chip" onclick="selectDisplayCurrency('USD')">USD ($)</div>
        <div class="trend-chip" onclick="selectDisplayCurrency('EUR')">EUR (€)</div>
        <div class="trend-chip" onclick="selectDisplayCurrency('SYP')">SYP (ل.س)</div>
        <div class="trend-chip" onclick="selectDisplayCurrency('XTR')">Stars (⭐)</div>
      </div>
    </div>

    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;">🌐 اللغة / Language</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="language-picker-chips">
        <div class="trend-chip" onclick="changeStoreLanguage('ar')">العربية</div>
        <div class="trend-chip" onclick="changeStoreLanguage('en')">English</div>
        <div class="trend-chip" onclick="changeStoreLanguage('de')">Deutsch</div>
        <div class="trend-chip" onclick="changeStoreLanguage('es')">Español</div>
        <div class="trend-chip" onclick="changeStoreLanguage('fr')">Français</div>
        <div class="trend-chip" onclick="changeStoreLanguage('it')">Italiano</div>
        <div class="trend-chip" onclick="changeStoreLanguage('zh')">中文</div>
      </div>
    </div>

    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;">🎁 برنامج الإحالة والأرباح</div>
      <div style="font-size: 12px; color: var(--hint); margin-bottom: 8px;">
        شارك رابط الإحالة الخاص بك واحصل على عمولات رصيد فورية عند شحن أصدقائك!
      </div>
      <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0, 0, 0, 0.35); border-radius: 8px; padding: 10px; margin-top: 8px;">
        <span id="referral-link-display" style="font-family: monospace; font-size: 12px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-left: 8px;">https://t.me/...</span>
        <button class="btn-action-secondary" onclick="copyReferralLink()" style="padding: 4px 10px;">نسخ</button>
      </div>
    </div>
  </main>

  <!-- FLOATING LIQUID GLASS BOTTOM NAVBAR (Flyout Capsule) -->
  <nav class="liquid-glass-nav">
    <div class="liquid-tab-item active" id="tab-store" onclick="switchTab('store')">
      <svg viewBox="0 0 24 24"><path d="M19 6h-2c0-2.76-2.24-5-5-5S7 3.24 7 6H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-7-3c1.66 0 3 1.34 3 3H9c0-1.66 1.34-3 3-3zm7 17H5V8h14v12zm-7-8c-1.66 0-3-1.34-3-3H7c0 2.76 2.24 5 5 5s5-2.24 5-5h-2c0 1.66-1.34 3-3 3z"/></svg>
      <span class="liquid-tab-label" id="i18n-tab-store">المتجر</span>
    </div>
    <div class="liquid-tab-item" id="tab-orders" onclick="switchTab('orders')">
      <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
      <span class="liquid-tab-label" id="i18n-tab-orders">طلباتي</span>
    </div>
    <div class="liquid-tab-item" id="tab-wallet" onclick="switchTab('wallet')">
      <svg viewBox="0 0 24 24"><path d="M21 18v1c0 1.1-.9 2-2 2H5c-1.11 0-2-.9-2-2V5c0-1.1.89-2 2-2h14c1.1 0 2 .9 2 2v1h-9c-1.11 0-2 .9-2 2v8c0 1.1.89 2 2 2h9zm-9-2h10V8H12v8zm4-2.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>
      <span class="liquid-tab-label" id="i18n-tab-wallet">المحفظة</span>
    </div>
    <div class="liquid-tab-item" id="tab-settings" onclick="switchTab('settings')">
      <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
      <span class="liquid-tab-label" id="i18n-tab-settings">الإعدادات</span>
    </div>
  </nav>

  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      try {
        if (tg.setHeaderColor) tg.setHeaderColor('#090e1a');
        if (tg.setBackgroundColor) tg.setBackgroundColor('#090e1a');
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

    // Canvas Confetti
    function fireConfetti() {
      const canvas = document.getElementById('confetti-canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      const particles = [];
      const colors = ['#38bdf8', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];
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
          p.vy += 0.35;
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

    // State
    let allProducts = [];
    let categoriesList = [];
    let userData = null;
    let activeCatalog = null;
    let selectedProduct = null;
    let selectedQty = 1;
    let activeTab = 'store';
    let currentAppLanguage = 'ar'; // Arabic First

    // Telegram User ID Resolution
    const urlParams = new URLSearchParams(window.location.search);
    const tgUser = tg?.initDataUnsafe?.user;
    const userId = tgUser?.id || Number(urlParams.get('tg_id') || 0);

    // Bilingual Collections Config (Arabic First)
    const CATALOG_META = {
      "AI & Chatbots": { arTitle: "🤖 الذكاء الاصطناعي", icon: "🤖", preview: "كلود · شات جي بي تي · جيميني · جروك" },
      "Streaming & Entertainment": { arTitle: "🎬 البث والترفيه", icon: "🎬", preview: "نتفلكس · بيكوك · شاهد · أبل تي في" },
      "VPN & Security": { arTitle: "🛡️ الحماية والـ VPN", icon: "🛡️", preview: "نورد في بي ان · سيرف شارك · بروتون" },
      "Design & Creative": { arTitle: "🎨 التصميم والإبداع", icon: "🎨", preview: "كانفا · أدوبي · فيجما · فريمر" },
      "Productivity": { arTitle: "📝 الإنتاجية والأدوات", icon: "📝", preview: "نوشن · كاب كات · أوفيس" },
      "Other": { arTitle: "📦 منتجات رقمية متنوعة", icon: "📦", preview: "تراخيص، مفاتيح واشتراكات" }
    };

    // Robust Markdown & HTML Formatter
    function formatRichDescription(raw) {
      if (!raw) return '<span style="color: var(--hint)">لا يوجد وصف إضافي.</span>';
      let text = String(raw).trim();

      // Decode entities
      const entityMap = { '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&amp;': '&' };
      text = text.replace(/&(lt|gt|quot|apos|amp);/g, (m) => entityMap[m] || m);

      // Preserve <tg-emoji>
      const emojis = [];
      text = text.replace(/<tg-emoji[^>]*emoji-id="([^"]+)"[^>]*>(.*?)<\/tg-emoji>/gi, (m, id, char) => {
        const placeholder = `__TG_EMOJI_${emojis.length}__`;
        emojis.push(`<span style="display:inline-flex; align-items:center; vertical-align:middle;">${char}</span>`);
        return placeholder;
      });

      // Headers (### Header)
      text = text.replace(/^###\s*(.*$)/gim, '<div class="desc-heading">$1</div>');
      text = text.replace(/^##\s*(.*$)/gim, '<div class="desc-heading">$1</div>');
      text = text.replace(/^#\s*(.*$)/gim, '<div class="desc-heading">$1</div>');

      // Bold & Underline
      text = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
      text = text.replace(/__(.*?)__/g, '<u>$1</u>');

      // Italic
      text = text.replace(/\*([^\*\n]+)\*/g, '<i>$1</i>');
      text = text.replace(/_([^_\n]+)_/g, '<i>$1</i>');

      // Inline code
      text = text.replace(/`([^`]+)`/g, '<code class="desc-inline-code">$1</code>');

      // Bullets
      text = text.replace(/^[\s]*[-*•]\s+(.+)$/gim, '<div class="desc-bullet">• $1</div>');

      // Line breaks
      text = text.replace(/\r?\n/g, '<br>');
      text = text.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');

      // Restore custom emojis
      emojis.forEach((em, idx) => {
        text = text.replace(`__TG_EMOJI_${idx}__`, em);
      });

      return text;
    }

    // Client-side i18n
    const I18N = {
      ar: {
        store: "المتجر", orders: "طلباتي", wallet: "المحفظة", settings: "الإعدادات",
        search: "ابحث عن كلود، جيميني، نتفلكس، في بي ان...", collections: "التصنيفات المميزة",
        all_catalogs: "جميع التصنيفات", brand: "🛍️ GH Store", caption: "المتجر الرقمي المعتمد",
        buy_now: "شراء فوري", in_stock: "متوفر", left: "متبقي", instant: "تسليم فوري",
        total: "السعر الإجمالي", qty: "الكمية", desc: "الوصف", warranty: "ضمان 30 يوم"
      },
      en: {
        store: "Store", orders: "Orders", wallet: "Wallet", settings: "Settings",
        search: "Search Claude, Gemini, Netflix, VPN...", collections: "Featured Catalogs",
        all_catalogs: "All Catalogs", brand: "🛍️ GH Store", caption: "Verified Digital Reseller",
        buy_now: "Instant Buy", in_stock: "In Stock", left: "left", instant: "Instant Delivery",
        total: "Total Price", qty: "Quantity", desc: "Description", warranty: "30 Days Warranty"
      },
      de: {
        store: "Shop", orders: "Bestellungen", wallet: "Guthaben", settings: "Einstellungen",
        search: "Produkte suchen...", collections: "Kategorien", all_catalogs: "Alle Kategorien",
        brand: "🛍️ GH Store", caption: "Verifizierter Reseller", buy_now: "Sofort kaufen",
        in_stock: "Vorrätig", left: "übrig", instant: "Sofortige Lieferung",
        total: "Gesamtpreis", qty: "Menge", desc: "Beschreibung", warranty: "30 Tage Garantie"
      },
      es: {
        store: "Tienda", orders: "Pedidos", wallet: "Billetera", settings: "Ajustes",
        search: "Buscar productos...", collections: "Colecciones", all_catalogs: "Todas las Colecciones",
        brand: "🛍️ GH Store", caption: "Distribuidor Verificado", buy_now: "Comprar ahora",
        in_stock: "En stock", left: "disponibles", instant: "Entrega instantánea",
        total: "Precio Total", qty: "Cantidad", desc: "Descripción", warranty: "30 Días de Garantía"
      },
      fr: {
        store: "Boutique", orders: "Commandes", wallet: "Portefeuille", settings: "Paramètres",
        search: "Rechercher...", collections: "Collections", all_catalogs: "Toutes les Collections",
        brand: "🛍️ GH Store", caption: "Revendeur Vérifié", buy_now: "Acheter",
        in_stock: "En stock", left: "restants", instant: "Livraison instantanée",
        total: "Prix Total", qty: "Quantité", desc: "Description", warranty: "Garantie 30 jours"
      },
      it: {
        store: "Negozio", orders: "Ordini", wallet: "Portafoglio", settings: "Impostazioni",
        search: "Cerca prodotti...", collections: "Collezioni", all_catalogs: "Tutte le Collezioni",
        brand: "🛍️ GH Store", caption: "Rivenditore Verificato", buy_now: "Acquista",
        in_stock: "Disponibile", left: "rimasti", instant: "Consegna istantanea",
        total: "Prezzo Totale", qty: "Quantità", desc: "Descrizione", warranty: "Garanzia 30 giorni"
      },
      zh: {
        store: "商店", orders: "订单", wallet: "钱包", settings: "设置",
        search: "搜索产品...", collections: "精选分类", all_catalogs: "所有分类",
        brand: "🛍️ GH Store", caption: "官方认证分销商", buy_now: "立即购买",
        in_stock: "现货", left: "剩余", instant: "自动秒发",
        total: "总计", qty: "数量", desc: "商品说明", warranty: "30天质保"
      }
    };

    function applyLanguage(lang) {
      currentAppLanguage = lang;
      const d = I18N[lang] || I18N.ar;
      document.getElementById('i18n-tab-store').innerText = d.store;
      document.getElementById('i18n-tab-orders').innerText = d.orders;
      document.getElementById('i18n-tab-wallet').innerText = d.wallet;
      document.getElementById('i18n-tab-settings').innerText = d.settings;
      document.getElementById('store-search-input').placeholder = d.search;
      document.getElementById('title-collections').innerText = d.collections;
      document.getElementById('btn-back-to-catalogs').innerText = d.all_catalogs;
      document.getElementById('top-sub-caption').innerText = d.caption;
      document.getElementById('label-desc-title').innerText = d.desc;
      document.getElementById('label-total-title').innerText = d.total;

      const isRtl = (lang === 'ar');
      document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
      document.documentElement.lang = lang;
    }

    // Tab Navigation
    function switchTab(tab) {
      haptic('light');
      activeTab = tab;
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.liquid-tab-item').forEach(el => el.classList.remove('active'));

      const view = document.getElementById('view-' + tab);
      if (view) view.classList.add('active');

      const btn = document.getElementById('tab-' + tab);
      if (btn) btn.classList.add('active');

      if (tab === 'orders' || tab === 'wallet' || tab === 'settings') {
        loadUserData();
      }
      if (tab === 'store') {
        returnToCollections();
      }
    }

    // Catalog Data Fetching
    async function fetchCatalogData() {
      try {
        const res = await fetch('/api/catalog');
        const d = await res.json();
        allProducts = d.products || [];
        categoriesList = d.categories || [];
        renderCatalogsGrid();
      } catch (e) {
        document.getElementById('catalogs-grid').innerHTML = '<div style="color: var(--hint); text-align: center; padding: 30px;">فشل تحميل التصنيفات.</div>';
      }
    }

    function renderCatalogsGrid() {
      const container = document.getElementById('catalogs-grid');
      const groups = {};
      categoriesList.forEach(c => {
        groups[c] = allProducts.filter(p => p.category === c);
      });

      container.innerHTML = Object.keys(groups).map(catName => {
        const items = groups[catName];
        if (!items || !items.length) return '';
        const meta = CATALOG_META[catName] || { arTitle: catName, icon: "📦", preview: "منتجات رقمية" };
        const minPrice = Math.min(...items.map(p => p.price || 999));
        const sym = items[0]?.sym || '$';
        const displayTitle = (currentAppLanguage === 'ar' && meta.arTitle) ? meta.arTitle : catName;

        return `
          <div class="catalog-card" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
            <div class="catalog-left">
              <div class="catalog-icon-box">${meta.icon}</div>
              <div class="catalog-info">
                <div class="catalog-name">${displayTitle}</div>
                <div class="catalog-sub">
                  <span>${items.length} منتج</span> ·
                  <span style="color: var(--accent); font-weight: 700;">يبدأ من ${minPrice.toFixed(2)}${sym}</span>
                </div>
                <div style="font-size: 11px; color: var(--hint); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${meta.preview}
                </div>
              </div>
            </div>
            <span class="chevron">‹</span>
          </div>
        `;
      }).join('');
    }

    function openCollection(catName) {
      haptic('medium');
      activeCatalog = catName;
      document.getElementById('catalogs-collection-mode').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'block';
      const meta = CATALOG_META[catName];
      document.getElementById('active-collection-title').innerText = (currentAppLanguage === 'ar' && meta?.arTitle) ? meta.arTitle : catName;

      const filtered = allProducts.filter(p => p.category === catName);
      renderProductItems(filtered);
    }

    function returnToCollections() {
      haptic('light');
      activeCatalog = null;
      document.getElementById('store-search-input').value = '';
      document.getElementById('store-clear-btn').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'none';
      document.getElementById('catalogs-collection-mode').style.display = 'block';
    }

    function applyTrend(kw) {
      document.getElementById('store-search-input').value = kw;
      handleSearch();
    }

    function handleSearch() {
      const q = (document.getElementById('store-search-input').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('store-clear-btn');

      if (q) {
        clearBtn.style.display = 'block';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
        document.getElementById('products-catalog-mode').style.display = 'block';
        document.getElementById('active-collection-title').innerText = `بحث: "${q}"`;

        const matched = allProducts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
        renderProductItems(matched);
      } else {
        clearBtn.style.display = 'none';
        returnToCollections();
      }
    }

    function clearSearch() {
      document.getElementById('store-search-input').value = '';
      returnToCollections();
    }

    function renderProductItems(products) {
      const container = document.getElementById('catalog-products-list');
      if (!products.length) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--hint);">لا توجد منتجات مطابقة في هذا التصنيف.</div>';
        return;
      }
      container.innerHTML = products.map(p => `
        <div class="product-row" onclick="openProductDetail(${Number(p.id)})">
          <div class="prod-left">
            <div class="prod-icon">${p.emoji || '⚡'}</div>
            <div class="prod-details">
              <div class="prod-title">${p.name}</div>
              <div class="prod-desc">
                <span>${p.stock ? 'متوفر (' + p.stock + ')' : 'تسليم فوري'}</span> ·
                <span>${p.delivery_type === 'activation' ? 'تفعيل مخصص' : 'تسليم تلقائي'}</span>
              </div>
            </div>
          </div>
          <div class="prod-price-box">
            <div class="prod-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
            <div class="prod-tap-hint">عرض التفاصيل ‹</div>
          </div>
        </div>
      `).join('');
    }

    // DEDICATED IN-APP PRODUCT DETAIL PAGE
    function openProductDetail(productId) {
      haptic('medium');
      // Number-safe comparison prevents navigation breaking
      selectedProduct = allProducts.find(p => Number(p.id) === Number(productId));
      if (!selectedProduct) return;
      selectedQty = 1;

      document.getElementById('prod-hero-icon').innerText = selectedProduct.emoji || '⚡';
      document.getElementById('prod-hero-name').innerText = selectedProduct.name;
      document.getElementById('prod-hero-cat').innerText = selectedProduct.category || 'منتج رقمي';
      document.getElementById('detail-category-header').innerText = selectedProduct.category || 'المنتج';

      // Rich formatted description (Markdown + HTML)
      document.getElementById('prod-rich-desc').innerHTML = formatRichDescription(selectedProduct.description);

      const isInstant = selectedProduct.delivery_type !== 'activation';
      document.getElementById('prod-delivery-badge').innerText = isInstant ? '⚡ تسليم تلقائي فوري' : '⏳ تفعيل مخصص';
      document.getElementById('prod-stock-badge').innerText = selectedProduct.stock ? `🟢 متوفر (${selectedProduct.stock})` : '⚡ تسليم فوري';

      updateDetailPagePrice();

      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      document.getElementById('view-product-detail').classList.add('active');
    }

    function closeProductDetailPage() {
      haptic('light');
      document.getElementById('view-product-detail').classList.remove('active');
      document.getElementById('view-store').classList.add('active');
    }

    function adjustQty(delta) {
      haptic('light');
      selectedQty = Math.max(1, Math.min(10, selectedQty + delta));
      document.getElementById('prod-qty-val').innerText = selectedQty;
      updateDetailPagePrice();
    }

    function updateDetailPagePrice() {
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
        discountText = `خصم مطبق: -${totalDiscount}%!`;
      }
      document.getElementById('prod-discount-tag').innerText = discountText;
      document.getElementById('prod-total-price').innerText = `${total.toFixed(2)}${sym}`;
      document.getElementById('btn-price-tag').innerText = `(${total.toFixed(2)}${sym})`;

      // Balance check
      const userBalance = userData?.balance || 0.0;
      const alertBox = document.getElementById('insufficient-funds-alert');
      const buyBtn = document.getElementById('btn-inapp-purchase');

      if (userBalance < total) {
        alertBox.style.display = 'block';
        alertBox.innerHTML = `⚠️ الرصيد المتاح غير كافٍ (تحتاج ${total.toFixed(2)}${sym}، رصيدك $${userBalance.toFixed(2)}).`;
        buyBtn.innerHTML = `<span>💳 شحن الرصيد للمتابعة</span>`;
        buyBtn.onclick = () => switchTab('wallet');
      } else {
        alertBox.style.display = 'none';
        buyBtn.innerHTML = `<span>⚡ شراء فوري</span> <span>(${total.toFixed(2)}${sym})</span>`;
        buyBtn.onclick = executeProductBuy;
      }
    }

    // IN-APP CHECKOUT (POST /api/buy)
    async function executeProductBuy() {
      if (!selectedProduct || !userId) {
        showToast('يرجى فتح المتجر من داخل تيليجرام');
        return;
      }

      // Biometric Verification for high-value orders ($50+)
      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      if (total >= 50.0 && tg?.BiometricManager?.isBiometricAvailable) {
        tg.BiometricManager.authenticate({ reason: `تأكيد طلب بقيمة $${total.toFixed(2)}` }, (success) => {
          if (success) processOrderPlacement();
          else showToast('تم إلغاء التحقق الحيوي');
        });
        return;
      }

      processOrderPlacement();
    }

    async function processOrderPlacement() {
      haptic('medium');
      const buyBtn = document.getElementById('btn-inapp-purchase');
      buyBtn.disabled = true;
      buyBtn.innerHTML = '<span>⏳ جاري معالجة الطلب...</span>';

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
            updateBalancePills();
          }

          // Show in-app success screen
          document.getElementById('success-meta-sub').innerText = `طلب #${d.order_id} · ${d.product_name} (${d.quantity}×)`;
          const keysBox = document.getElementById('success-delivered-keys');
          if (d.goods && d.goods.length) {
            keysBox.innerHTML = d.goods.map(g => `
              <div class="copyable-box" onclick="copyCredText('${g.replace(/'/g, "\\\\'")}')">
                <code>${g}</code>
                <div style="font-size: 10px; color: var(--hint); margin-top: 4px;">📋 انقر للنسخ الفوري</div>
              </div>
            `).join('');
          } else {
            keysBox.innerHTML = '<div style="padding: 12px; color: var(--warning); text-align: center;">⏳ جاري التفعيل، سيتم التسليم قريباً.</div>';
          }

          document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
          document.getElementById('view-order-success').classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || 'فشل إتمام الطلب.');
          updateDetailPagePrice();
        }
      } catch (e) {
        buyBtn.disabled = false;
        haptic('error');
        showToast('خطأ في الاتصال. يرجى إعادة المحاولة.');
        updateDetailPagePrice();
      }
    }

    // Direct Telegram Stars Invoice (openInvoice)
    async function executeStarsDirectBuy() {
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
          tg.openInvoice(d.invoice_link, (status) => {
            if (status === 'paid') {
              fireConfetti();
              showToast('تم الدفع بنجاح عبر نجوم تيليجرام!');
              switchTab('orders');
            } else if (status === 'failed') {
              showToast('فشلت عملية الدفع بالنجوم');
            }
          });
        } else {
          showToast('تعذر فتح فاتورة النجوم');
        }
      } catch (e) {
        showToast('خطأ في شبكة الفواتير');
      }
    }

    // Top-Up Rails (Native openInvoice & openLink)
    async function triggerQuickTopup(amount) {
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
              showToast(`تم شحن +$${amount} بنجاح!`);
              loadUserData();
            }
          });
        }
      } catch (e) {
        showToast('تعذر إنشاء فاتورة الشحن');
      }
    }

    async function triggerRailPayment(rail) {
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
              showToast('تم شحن الرصيد بنجاح!');
              loadUserData();
            }
          });
        } else if (d.type === 'url' && d.url) {
          tg.openLink(d.url);
        }
      } catch (e) {
        showToast('بوابة الدفع غير متاحة حالياً');
      }
    }

    async function submitVoucherRedeem() {
      const code = (document.getElementById('voucher-code-input').value || '').trim();
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
          showToast(d.message || 'تم شحن الكوبون!');
          document.getElementById('voucher-code-input').value = '';
          loadUserData();
        } else {
          showToast(d.error || 'كود الهدية غير صالح');
        }
      } catch (e) {
        showToast('فشلت عملية شحن الكوبون');
      }
    }

    // User Data & Profile Loading
    async function loadUserData() {
      if (!userId) {
        renderEmptyOrders();
        return;
      }
      try {
        const res = await fetch('/api/user-data?tg_id=' + userId);
        const d = await res.json();
        if (d.error) {
          renderEmptyOrders();
          return;
        }
        userData = d;
        updateBalancePills();

        // Real Profile Picture (Telegram Bot API or Initial)
        const topAvatarBox = document.getElementById('top-avatar-box');
        const setAvatarBox = document.getElementById('settings-avatar-box');
        const firstLetter = (tgUser?.first_name || d.username || 'U')[0].toUpperCase();

        if (d.photo_url) {
          topAvatarBox.innerHTML = `<img src="${d.photo_url}" class="avatar-img" alt="Avatar">`;
          setAvatarBox.innerHTML = `<img src="${d.photo_url}" class="avatar-img" style="width: 48px; height: 48px;" alt="Avatar">`;
        } else {
          document.getElementById('top-avatar-initial').innerText = firstLetter;
          document.getElementById('settings-avatar-initial').innerText = firstLetter;
        }

        // Settings View Info
        const displayName = tgUser?.first_name ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : (d.username ? '@' + d.username : 'العميل');
        document.getElementById('user-name-title').innerText = displayName;
        document.getElementById('user-tg-num').innerText = 'ID: ' + d.telegram_id;
        document.getElementById('user-vip-pill-box').innerHTML = `<span class="vip-tag">${d.vip_tier} (خصم ${d.vip_discount}%)</span>`;

        // VIP Progress Bar
        const spent = d.total_spent || 0.0;
        let nextTarget = 100.0;
        let nextLabel = "Silver VIP (خصم 3%)";
        if (spent >= 500) { nextTarget = 1000.0; nextLabel = "Platinum VIP (خصم 10%)"; }
        else if (spent >= 100) { nextTarget = 500.0; nextLabel = "Gold VIP (خصم 7%)"; }
        const pct = Math.min(100, Math.round((spent / nextTarget) * 100));
        document.getElementById('next-vip-rank').innerText = nextLabel;
        document.getElementById('vip-progress-num').innerText = `${pct}% ($${spent.toFixed(0)} / $${nextTarget.toFixed(0)})`;
        document.getElementById('vip-progress-fill').style.width = `${pct}%`;

        // Referral link
        const refLink = `https://t.me/${d.bot_username}?start=${d.referral_code || ''}`;
        document.getElementById('referral-link-display').innerText = refLink;

        // Active Chips
        document.querySelectorAll('#currency-picker-chips .trend-chip').forEach(el => {
          el.classList.toggle('active', el.innerText.includes(d.currency_preference));
        });
        document.querySelectorAll('#language-picker-chips .trend-chip').forEach(el => {
          el.classList.toggle('active', el.getAttribute('onclick')?.includes(`'${d.language}'`));
        });

        // Set Language
        applyLanguage(d.language || 'ar');

        // Render Orders
        renderOrders(d.orders || []);
      } catch (e) {
        renderEmptyOrders();
      }
    }

    function updateBalancePills() {
      if (!userData) return;
      document.getElementById('top-balance-str').innerText = userData.display_balance || `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-hero').innerText = `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-approx').innerText = userData.currency_preference !== 'USD'
        ? `≈ ${userData.display_balance}`
        : 'جاهز للشراء الفوري';

      if (userData.vip_tier && userData.vip_tier !== 'Standard') {
        const tag = document.getElementById('top-vip-tag');
        tag.innerText = userData.vip_tier;
        tag.style.display = 'inline-block';
      }
    }

    function renderEmptyOrders() {
      document.getElementById('orders-container-box').innerHTML = `
        <div style="text-align: center; padding: 40px 16px; color: var(--hint);">
          <div style="font-size: 40px; margin-bottom: 8px;">📦</div>
          <div style="font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 4px;">لا توجد طلبات بعد</div>
          <p style="font-size: 13px; margin-bottom: 16px;">تصفح التصنيفات واطلب الحسابات والمفاتيح بضغطة واحدة!</p>
          <button class="btn-action-primary" onclick="switchTab('store')" style="width: auto; padding: 0 24px; margin: 0 auto; height: 42px;">تصفح المتجر</button>
        </div>
      `;
    }

    function renderOrders(orders) {
      const container = document.getElementById('orders-container-box');
      if (!orders.length) {
        renderEmptyOrders();
        return;
      }
      container.innerHTML = orders.map(o => `
        <div class="inset-card" style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="font-size: 15px;">#${o.id} · ${o.created_at || ''}</strong>
            <span class="pill-badge" style="background: ${o.status.includes('completed') ? 'rgba(16,185,129,0.2); color:#10b981' : o.status.includes('fail') ? 'rgba(239,68,68,0.2); color:#ef4444' : 'rgba(245,158,11,0.2); color:#f59e0b'}; font-size:11px;">${o.status}</span>
          </div>
          <div style="font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 2px;">${o.products}</div>
          <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-bottom: 8px;">الإجمالي: ${o.total.toFixed(2)}${o.sym}</div>

          <!-- Timeline Stepper -->
          <div class="timeline-box">
            <div class="timeline-track"></div>
            <div class="timeline-node">
              <div class="node-circle done">✓</div>
              <div class="node-label">تم الطلب</div>
            </div>
            <div class="timeline-node">
              <div class="node-circle ${o.status.includes('completed') ? 'done' : 'active'}">${o.status.includes('completed') ? '✓' : '●'}</div>
              <div class="node-label">قيد المعالجة</div>
            </div>
            <div class="timeline-node">
              <div class="node-circle ${o.status.includes('completed') ? 'done' : ''}">${o.status.includes('completed') ? '✓' : '○'}</div>
              <div class="node-label">تم التسليم</div>
            </div>
          </div>

          ${o.goods && o.goods.length ? o.goods.map(g => `
            <div class="copyable-box" onclick="copyCredText('${g.replace(/'/g, "\\\\'")}')">
              <code>${g}</code>
              <div style="font-size: 10px; color: var(--hint); margin-top: 4px;">📋 انقر للنسخ الفوري</div>
            </div>
          `).join('') : ''}

          <div style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px;">
            ${o.warranty_days && !o.warranty_claimed && o.status === 'completed' ? `
              <button class="btn-action-secondary" onclick="claimOrderWarranty(${o.id})">🛡️ طلب تعويض الضمان</button>
            ` : ''}
            <button class="btn-action-secondary" onclick="reportOrderProblem(${o.id})">⚠️ إبلاغ عن مشكلة</button>
          </div>
        </div>
      `).join('');
    }

    function copyCredText(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('تم نسخ بيانات الحساب بنجاح!');
      });
    }

    function copyReferralLink() {
      const link = document.getElementById('referral-link-display').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast('تم نسخ رابط الإحالة!');
      });
    }

    async function selectDisplayCurrency(code) {
      haptic('light');
      document.querySelectorAll('#currency-picker-chips .trend-chip').forEach(el => {
        el.classList.toggle('active', el.innerText.includes(code));
      });
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, currency: code })
        });
        showToast(`تم تعيين عملة العرض إلى ${code}`);
        loadUserData();
      }
    }

    async function changeStoreLanguage(code) {
      haptic('light');
      applyLanguage(code);
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, language: code })
        });
        showToast('تم تحديث لغة التطبيق!');
        loadUserData();
      }
    }

    async function claimOrderWarranty(orderId) {
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
          showToast('تم اعتماد الضمان وتسليم البيانات الجديدة!');
          loadUserData();
        } else {
          showToast('تم إرسال طلب الضمان لمراجعة الدعم');
        }
      } catch (e) {
        showToast('فشل تقديم طلب الضمان');
      }
    }

    function reportOrderProblem(orderId) {
      haptic('medium');
      switchTab('settings');
      showToast('يرجى مراسلة الدعم الفني وتزويدهم برقم الطلب #' + orderId);
    }

    // Real-Time Server-Sent Events (SSE)
    function initSSE() {
      try {
        const evSource = new EventSource('/api/events');
        evSource.onmessage = (e) => {
          if (e.data && e.data !== 'ping') {
            fetchCatalogData();
          }
        };
      } catch (e) {}
    }

    // Initial Startup: Arabic First
    applyLanguage('ar');
    fetchCatalogData();
    loadUserData();
    initSSE();
  </script>
</body>
</html>
"""
