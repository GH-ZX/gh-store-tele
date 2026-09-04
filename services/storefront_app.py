"""Telegram Mini App (TMA) Storefront HTML, CSS, and Client Logic.

Provides a responsive, mobile-first 4-tab interface:
- Tab 1 (Store): Search, category chips, animated emoji icons, and slide-up checkout modal.
- Tab 2 (Orders): Order history, status pills, 1-tap copyable credentials, and warranty claims.
- Tab 3 (Wallet): Spendable balance, deposit presets ($10, $25, $50, $100), and payment rail cards.
- Tab 4 (Settings): Display currency toggle (USD, EUR, SYP, XTR), language switcher (7 languages),
                   VIP rank progress bar, referral link copy, and support contact.
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
      --bg: var(--tg-theme-bg-color, #0b1120);
      --text: var(--tg-theme-text-color, #f8fafc);
      --hint: var(--tg-theme-hint-color, #94a3b8);
      --btn: var(--tg-theme-button-color, #38bdf8);
      --btn-text: var(--tg-theme-button-text-color, #04121d);
      --card: var(--tg-theme-secondary-bg-color, #1e293b);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #38bdf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --nav-height: 64px;
      --safe-bottom: env(safe-area-inset-bottom, 16px);
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding-bottom: calc(var(--nav-height) + var(--safe-bottom) + 20px);
      user-select: none;
      -webkit-user-select: none;
    }

    /* Top Sticky Header */
    .top-header {
      position: sticky;
      top: 0;
      z-index: 40;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      background: rgba(11, 17, 32, 0.85);
      border-bottom: 1px solid var(--border);
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header-brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .header-brand h1 {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .balance-pill {
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent);
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 5px;
      cursor: pointer;
    }
    .vip-pill {
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #f59e0b;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
    }

    /* Page Container & Tab Views */
    .view-content {
      padding: 16px;
      display: none;
    }
    .view-content.active {
      display: block;
      animation: fadeIn 0.15s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Search & Category Chips */
    .search-bar {
      position: relative;
      margin-bottom: 14px;
    }
    .search-bar input {
      width: 100%;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      color: var(--text);
      padding: 11px 16px 11px 38px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-bar input:focus {
      border-color: var(--accent);
    }
    .search-icon {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--hint);
    }
    .chips-wrapper {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 10px;
      margin-bottom: 12px;
      scrollbar-width: none;
    }
    .chips-wrapper::-webkit-scrollbar { display: none; }
    .chip {
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--hint);
      border-radius: 20px;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: 500;
      white-space: nowrap;
      cursor: pointer;
      transition: all 0.2s;
    }
    .chip.active {
      background: var(--btn);
      color: var(--btn-text);
      border-color: var(--btn);
      font-weight: 700;
    }

    /* Product Cards Grid */
    .products-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }
    @media (min-width: 480px) {
      .products-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .product-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
      transition: transform 0.15s, border-color 0.15s;
    }
    .product-card:active {
      transform: scale(0.98);
      border-color: rgba(56, 189, 248, 0.4);
    }
    .card-top {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 10px;
    }
    .card-icon {
      font-size: 26px;
      width: 42px;
      height: 42px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .card-meta {
      flex: 1;
      overflow: hidden;
    }
    .card-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 3px;
      line-height: 1.3;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .card-category {
      font-size: 11px;
      color: var(--hint);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 600;
    }
    .card-desc {
      font-size: 12px;
      color: var(--hint);
      line-height: 1.4;
      margin-bottom: 12px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .card-bottom {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }
    .card-price {
      font-size: 16px;
      font-weight: 700;
      color: var(--accent);
    }
    .stock-tag {
      font-size: 11px;
      color: var(--hint);
    }
    .btn-buy {
      background: var(--btn);
      color: var(--btn-text);
      border: none;
      border-radius: 8px;
      padding: 7px 14px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    /* Orders View */
    .order-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 12px;
    }
    .order-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .order-id {
      font-weight: 700;
      font-size: 14px;
    }
    .status-badge {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .status-completed { background: rgba(16, 185, 129, 0.15); color: var(--success); }
    .status-pending { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
    .status-failed { background: rgba(239, 68, 68, 0.15); color: var(--danger); }
    .order-item-name {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .credential-box {
      background: rgba(0, 0, 0, 0.35);
      border: 1px dashed rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      padding: 10px;
      font-family: monospace;
      font-size: 13px;
      color: #38bdf8;
      word-break: break-all;
      margin: 8px 0;
      position: relative;
      cursor: pointer;
    }
    .credential-box:active {
      background: rgba(56, 189, 248, 0.15);
    }
    .copy-hint {
      font-size: 11px;
      color: var(--hint);
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .order-actions {
      display: flex;
      gap: 8px;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }
    .btn-outline {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      flex: 1;
      text-align: center;
    }

    /* Wallet View */
    .wallet-hero {
      background: linear-gradient(135deg, #1e293b, #0f172a);
      border: 1px solid rgba(56, 189, 248, 0.3);
      border-radius: 18px;
      padding: 24px;
      text-align: center;
      margin-bottom: 20px;
      position: relative;
      overflow: hidden;
    }
    .wallet-hero::after {
      content: '';
      position: absolute;
      width: 150px;
      height: 150px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.2) 0%, transparent 70%);
      top: -30px;
      right: -30px;
    }
    .wallet-label {
      font-size: 12px;
      color: var(--hint);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 6px;
    }
    .wallet-amount {
      font-size: 34px;
      font-weight: 800;
      color: #f8fafc;
      letter-spacing: -0.5px;
      margin-bottom: 4px;
    }
    .wallet-sub {
      font-size: 13px;
      color: var(--accent);
      font-weight: 600;
    }
    .section-title {
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--hint);
      margin: 20px 0 10px 4px;
    }
    .preset-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 16px;
    }
    .preset-btn {
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 12px;
      padding: 12px 0;
      font-size: 14px;
      font-weight: 700;
      text-align: center;
      cursor: pointer;
    }
    .preset-btn:active {
      background: var(--btn);
      color: var(--btn-text);
      border-color: var(--btn);
    }
    .rail-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      cursor: pointer;
    }
    .rail-card:active {
      transform: scale(0.99);
      border-color: var(--accent);
    }
    .rail-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .rail-icon {
      font-size: 24px;
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .rail-name {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 2px;
    }
    .rail-sub {
      font-size: 12px;
      color: var(--hint);
    }

    /* Settings View */
    .profile-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 20px;
    }
    .profile-row {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 14px;
    }
    .profile-avatar {
      width: 52px;
      height: 52px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      color: white;
      font-size: 22px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .profile-name {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 3px;
    }
    .profile-id {
      font-size: 12px;
      color: var(--hint);
      font-family: monospace;
    }
    .setting-group {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 14px;
    }
    .setting-header {
      font-size: 13px;
      font-weight: 600;
      color: var(--hint);
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .option-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .opt-chip {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }
    .opt-chip.selected {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent);
      color: var(--accent);
    }
    .referral-box {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 8px;
    }
    .referral-link {
      font-family: monospace;
      font-size: 13px;
      color: var(--accent);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
      margin-right: 8px;
    }

    /* Fixed Bottom Navigation Bar */
    .bottom-nav {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: calc(var(--nav-height) + var(--safe-bottom));
      padding-bottom: var(--safe-bottom);
      background: rgba(11, 17, 32, 0.92);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 50;
    }
    .nav-item {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
      color: var(--hint);
      cursor: pointer;
      padding: 6px 0;
      transition: color 0.15s;
    }
    .nav-item.active {
      color: var(--accent);
    }
    .nav-icon {
      font-size: 20px;
    }
    .nav-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: -0.2px;
    }

    /* Bottom Sheet Modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.65);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 100;
      display: none;
      align-items: flex-end;
    }
    .modal-backdrop.open {
      display: flex;
    }
    .sheet-modal {
      width: 100%;
      background: var(--card);
      border-top-left-radius: 20px;
      border-top-right-radius: 20px;
      border: 1px solid var(--border);
      border-bottom: none;
      padding: 20px 20px calc(20px + var(--safe-bottom)) 20px;
      animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      max-height: 85vh;
      overflow-y: auto;
    }
    @keyframes slideUp {
      from { transform: translateY(100%); }
      to { transform: translateY(0); }
    }
    .sheet-handle {
      width: 36px;
      height: 4px;
      border-radius: 2px;
      background: rgba(255, 255, 255, 0.2);
      margin: 0 auto 16px auto;
    }
    .sheet-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }
    .sheet-title {
      font-size: 18px;
      font-weight: 700;
    }
    .sheet-desc {
      font-size: 13px;
      color: var(--hint);
      line-height: 1.5;
      margin-bottom: 16px;
    }
    .stepper {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 8px 16px;
      margin-bottom: 16px;
    }
    .stepper-btn {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .stepper-val {
      font-size: 16px;
      font-weight: 700;
    }
    .sheet-btn {
      width: 100%;
      background: var(--btn);
      color: var(--btn-text);
      border: none;
      border-radius: 14px;
      padding: 14px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    /* Toast Notification */
    .toast {
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%) translateY(-100px);
      background: rgba(16, 185, 129, 0.95);
      color: white;
      padding: 8px 16px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      z-index: 200;
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    }
    .toast.show {
      transform: translateX(-50%) translateY(0);
    }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header class="top-header">
    <div class="header-brand">
      <h1>🛍️ GH Store</h1>
      <span class="vip-pill" id="header-vip" style="display: none;">VIP</span>
    </div>
    <div class="header-actions">
      <div class="balance-pill" onclick="switchTab('wallet')">
        <span id="header-balance">$0.00</span>
        <span style="font-size: 10px;">➕</span>
      </div>
    </div>
  </header>

  <!-- TAB 1: STORE / CATALOG -->
  <section id="view-store" class="view-content active">
    <div class="search-bar">
      <span class="search-icon">🔍</span>
      <input type="text" id="search-input" placeholder="Search ChatGPT, Gemini, Netflix..." oninput="handleSearch()">
    </div>
    <div class="chips-wrapper" id="categories-container"></div>
    <div class="products-grid" id="products-container"></div>
  </section>

  <!-- TAB 2: ORDERS -->
  <section id="view-orders" class="view-content">
    <div class="section-title">Your Purchase History</div>
    <div id="orders-container">
      <div style="text-align: center; padding: 40px 20px; color: var(--hint);">Loading orders...</div>
    </div>
  </section>

  <!-- TAB 3: WALLET -->
  <section id="view-wallet" class="view-content">
    <div class="wallet-hero">
      <div class="wallet-label">Spendable Balance</div>
      <div class="wallet-amount" id="wallet-big-balance">$0.00</div>
      <div class="wallet-sub" id="wallet-display-alt"></div>
    </div>

    <div class="section-title">Quick Top-up</div>
    <div class="preset-grid">
      <div class="preset-btn" onclick="triggerTopup(10)">+$10</div>
      <div class="preset-btn" onclick="triggerTopup(25)">+$25</div>
      <div class="preset-btn" onclick="triggerTopup(50)">+$50</div>
      <div class="preset-btn" onclick="triggerTopup(100)">+$100</div>
    </div>

    <div class="section-title">Payment Methods</div>
    <div class="rail-card" onclick="triggerRail('stars')">
      <div class="rail-left">
        <div class="rail-icon">⭐</div>
        <div>
          <div class="rail-name">Telegram Stars</div>
          <div class="rail-sub">Instant in-app payment with Apple / Google Pay</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>

    <div class="rail-card" onclick="triggerRail('crypto')">
      <div class="rail-left">
        <div class="rail-icon">🪙</div>
        <div>
          <div class="rail-name">Cryptocurrency</div>
          <div class="rail-sub">BTC, USDT, SOL, LTC, DOGE via KryptoExpress</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>

    <div class="rail-card" onclick="triggerRail('sam')">
      <div class="rail-left">
        <div class="rail-icon">📱</div>
        <div>
          <div class="rail-name">SAM Syriatel & ShamCash</div>
          <div class="rail-sub">Syrian mobile wallet invoice payment</div>
        </div>
      </div>
      <span style="color: var(--hint);">➔</span>
    </div>
  </section>

  <!-- TAB 4: SETTINGS -->
  <section id="view-settings" class="view-content">
    <div class="profile-card">
      <div class="profile-row">
        <div class="profile-avatar" id="avatar-char">U</div>
        <div>
          <div class="profile-name" id="profile-name">Telegram User</div>
          <div class="profile-id" id="profile-id">ID: 000000000</div>
        </div>
      </div>
      <div style="font-size: 13px; color: var(--hint); display: flex; justify-content: space-between;">
        <span>VIP Loyalty Status:</span>
        <strong id="profile-vip-tier" style="color: var(--accent);">Standard (0% off)</strong>
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-header">💱 Display Currency Preference</div>
      <div class="option-chips" id="currency-options">
        <div class="opt-chip" onclick="setCurrency('USD')">USD ($)</div>
        <div class="opt-chip" onclick="setCurrency('EUR')">EUR (€)</div>
        <div class="opt-chip" onclick="setCurrency('SYP')">SYP (ل.س)</div>
        <div class="opt-chip" onclick="setCurrency('XTR')">Stars (⭐)</div>
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-header">🌐 Storefront Language</div>
      <div class="option-chips" id="language-options">
        <div class="opt-chip" onclick="setLang('en')">English</div>
        <div class="opt-chip" onclick="setLang('ar')">العربية</div>
        <div class="opt-chip" onclick="setLang('de')">Deutsch</div>
        <div class="opt-chip" onclick="setLang('es')">Español</div>
        <div class="opt-chip" onclick="setLang('fr')">Français</div>
        <div class="opt-chip" onclick="setLang('it')">Italiano</div>
        <div class="opt-chip" onclick="setLang('zh')">中文</div>
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-header">🎁 Referral Program</div>
      <div style="font-size: 12px; color: var(--hint); line-height: 1.4; margin-bottom: 8px;">
        Share your link with friends to earn deposit commissions automatically on every purchase!
      </div>
      <div class="referral-box">
        <span class="referral-link" id="referral-link-text">https://t.me/...</span>
        <button class="btn-outline" onclick="copyReferralLink()" style="flex: none; padding: 4px 10px;">Copy</button>
      </div>
    </div>
  </section>

  <!-- Fixed Bottom Navigation Bar -->
  <nav class="bottom-nav">
    <div class="nav-item active" onclick="switchTab('store')">
      <div class="nav-icon">🛍️</div>
      <div class="nav-label">Store</div>
    </div>
    <div class="nav-item" onclick="switchTab('orders')">
      <div class="nav-icon">📦</div>
      <div class="nav-label">Orders</div>
    </div>
    <div class="nav-item" onclick="switchTab('wallet')">
      <div class="nav-icon">💳</div>
      <div class="nav-label">Wallet</div>
    </div>
    <div class="nav-item" onclick="switchTab('settings')">
      <div class="nav-icon">⚙️</div>
      <div class="nav-label">Settings</div>
    </div>
  </nav>

  <!-- Product Detail Bottom Sheet Modal -->
  <div class="modal-backdrop" id="product-modal" onclick="closeModalOnBackdrop(event)">
    <div class="sheet-modal" id="sheet-content">
      <div class="sheet-handle"></div>
      <div class="sheet-header">
        <div class="card-icon" id="modal-icon">⚡</div>
        <div>
          <div class="sheet-title" id="modal-title">Product</div>
          <div style="font-size: 12px; color: var(--hint);" id="modal-category">Category</div>
        </div>
      </div>
      <p class="sheet-desc" id="modal-desc"></p>

      <div class="stepper">
        <span style="font-size: 14px; font-weight: 600;">Quantity</span>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="stepper-btn" onclick="changeQty(-1)">-</div>
          <span class="stepper-val" id="modal-qty">1</span>
          <div class="stepper-btn" onclick="changeQty(1)">+</div>
        </div>
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
        <span style="font-size: 14px; color: var(--hint);">Total Price:</span>
        <strong style="font-size: 20px; color: var(--accent);" id="modal-total">$0.00</strong>
      </div>

      <button class="sheet-btn" id="modal-confirm-btn" onclick="confirmPurchase()">
        <span>Confirm & Buy in Bot</span>
        <span>➔</span>
      </button>
    </div>
  </div>

  <!-- Toast Notification -->
  <div class="toast" id="toast">Copied to clipboard!</div>

  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
    }

    // Haptics helper
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
      setTimeout(() => t.classList.remove('show'), 2000);
    }

    let allProducts = [];
    let activeCategory = "All";
    let userData = null;
    let selectedProduct = null;
    let selectedQty = 1;

    // Resolve user ID
    const urlParams = new URLSearchParams(window.location.search);
    const tgUser = tg?.initDataUnsafe?.user;
    const userId = tgUser?.id || urlParams.get('tg_id') || 0;

    // Tab Switching
    function switchTab(tabId) {
      haptic('selection');
      document.querySelectorAll('.view-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

      const view = document.getElementById('view-' + tabId);
      if (view) view.classList.add('active');

      const idx = ['store', 'orders', 'wallet', 'settings'].indexOf(tabId);
      if (idx !== -1) {
        document.querySelectorAll('.nav-item')[idx].classList.add('active');
      }

      if (tabId === 'orders' || tabId === 'wallet' || tabId === 'settings') {
        loadUserData();
      }
    }

    // Fetch Catalog
    async function loadCatalog() {
      try {
        const res = await fetch('/api/catalog');
        const data = await res.json();
        allProducts = data.products || [];
        renderCategories(["All", ...(data.categories || [])]);
        renderProducts(allProducts);
      } catch (e) {
        document.getElementById('products-container').innerHTML =
          '<div style="text-align: center; padding: 40px; color: var(--hint);">Could not load catalog.</div>';
      }
    }

    function renderCategories(cats) {
      const container = document.getElementById('categories-container');
      container.innerHTML = cats.map(c => `
        <div class="chip ${c === activeCategory ? 'active' : ''}" onclick="selectCategory('${c}')">${c}</div>
      `).join('');
    }

    function selectCategory(cat) {
      haptic('light');
      activeCategory = cat;
      document.querySelectorAll('.chip').forEach(el => el.classList.toggle('active', el.innerText === cat));
      filterProducts();
    }

    function handleSearch() {
      filterProducts();
    }

    function filterProducts() {
      const q = (document.getElementById('search-input').value || '').toLowerCase().trim();
      const filtered = allProducts.filter(p => {
        const matchesCat = activeCategory === "All" || p.category === activeCategory;
        const matchesSearch = !q || p.name.toLowerCase().includes(q) || (p.description || '').toLowerCase().includes(q);
        return matchesCat && matchesSearch;
      });
      renderProducts(filtered);
    }

    function renderProducts(list) {
      const container = document.getElementById('products-container');
      if (!list.length) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--hint); grid-column: 1/-1;">No products found.</div>';
        return;
      }
      container.innerHTML = list.map(p => `
        <div class="product-card" onclick="openProductModal(${p.id})">
          <div>
            <div class="card-top">
              <div class="card-icon">${p.emoji || '⚡'}</div>
              <div class="card-meta">
                <div class="card-category">${p.category || 'Digital Good'}</div>
                <div class="card-title">${p.name}</div>
              </div>
            </div>
            <div class="card-desc">${p.description || 'Instant digital delivery.'}</div>
          </div>
          <div class="card-bottom">
            <div>
              <div class="card-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
              <div class="stock-tag">${p.stock ? p.stock + ' left' : 'In stock'}</div>
            </div>
            <button class="btn-buy" onclick="event.stopPropagation(); openProductModal(${p.id})">
              <span>View</span>
            </button>
          </div>
        </div>
      `).join('');
    }

    // Modal Sheet
    function openProductModal(id) {
      haptic('medium');
      selectedProduct = allProducts.find(p => p.id === id);
      if (!selectedProduct) return;
      selectedQty = 1;

      document.getElementById('modal-icon').innerText = selectedProduct.emoji || '⚡';
      document.getElementById('modal-title').innerText = selectedProduct.name;
      document.getElementById('modal-category').innerText = selectedProduct.category || 'Digital Goods';
      document.getElementById('modal-desc').innerText = selectedProduct.description || 'Instant automated digital activation and delivery.';
      updateModalTotal();

      document.getElementById('product-modal').classList.add('open');
    }

    function closeModal() {
      document.getElementById('product-modal').classList.remove('open');
    }

    function closeModalOnBackdrop(e) {
      if (e.target.id === 'product-modal') closeModal();
    }

    function changeQty(delta) {
      haptic('light');
      selectedQty = Math.max(1, Math.min(10, selectedQty + delta));
      document.getElementById('modal-qty').innerText = selectedQty;
      updateModalTotal();
    }

    function updateModalTotal() {
      if (!selectedProduct) return;
      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      // apply VIP discount if loaded
      if (userData?.vip_discount) {
        total = total * (1 - userData.vip_discount / 100);
      }
      document.getElementById('modal-total').innerText = total.toFixed(2) + (selectedProduct.sym || '$');
    }

    function confirmPurchase() {
      if (!selectedProduct) return;
      haptic('success');
      if (tg) {
        tg.sendData(JSON.stringify({
          action: "buy_batstore",
          product_id: selectedProduct.id,
          quantity: selectedQty
        }));
        tg.close();
      } else {
        alert("Please open this store inside Telegram to checkout!");
      }
    }

    // User Data & Profile
    async function loadUserData() {
      if (!userId) return;
      try {
        const res = await fetch('/api/user-data?tg_id=' + userId);
        const d = await res.json();
        if (d.error) return;
        userData = d;

        // Top bar update
        document.getElementById('header-balance').innerText = d.display_balance || `$${d.balance.toFixed(2)}`;
        if (d.vip_tier && d.vip_tier !== 'Standard') {
          const vipEl = document.getElementById('header-vip');
          vipEl.innerText = d.vip_tier;
          vipEl.style.display = 'inline-block';
        }

        // Wallet view
        document.getElementById('wallet-big-balance').innerText = `$${d.balance.toFixed(2)}`;
        document.getElementById('wallet-display-alt').innerText = d.currency_preference !== 'USD'
          ? `≈ ${d.display_balance}`
          : 'Ready for instant purchases';

        // Settings view
        document.getElementById('avatar-char').innerText = (d.username ? d.username[0] : 'U').toUpperCase();
        document.getElementById('profile-name').innerText = d.username ? '@' + d.username : 'Customer';
        document.getElementById('profile-id').innerText = 'ID: ' + d.telegram_id;
        document.getElementById('profile-vip-tier').innerText = `${d.vip_tier} (${d.vip_discount}% off)`;

        // Highlight selected currency
        document.querySelectorAll('#currency-options .opt-chip').forEach(el => {
          el.classList.toggle('selected', el.innerText.includes(d.currency_preference));
        });

        // Highlight selected language
        document.querySelectorAll('#language-options .opt-chip').forEach(el => {
          el.classList.toggle('selected', el.getAttribute('onclick')?.includes(`'${d.language}'`));
        });

        // Referral link
        const refLink = `https://t.me/${d.bot_username}?start=${d.referral_code || ''}`;
        document.getElementById('referral-link-text').innerText = refLink;

        // Render orders
        renderOrders(d.orders || []);
      } catch (e) {}
    }

    function renderOrders(orders) {
      const container = document.getElementById('orders-container');
      if (!orders.length) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--hint);">No orders yet. Start exploring the store!</div>';
        return;
      }
      container.innerHTML = orders.map(o => `
        <div class="order-card">
          <div class="order-header">
            <span class="order-id">#${o.id} · ${o.created_at || ''}</span>
            <span class="status-badge status-${o.status.includes('completed') ? 'completed' : o.status.includes('fail') ? 'failed' : 'pending'}">${o.status}</span>
          </div>
          <div class="order-item-name">${o.products}</div>
          <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-bottom: 6px;">Total: ${o.total.toFixed(2)}${o.sym}</div>

          ${o.goods && o.goods.length ? o.goods.map(g => `
            <div class="credential-box" onclick="copyText('${g.replace(/'/g, "\\\\'")}')">
              <code>${g}</code>
              <div class="copy-hint">📋 Tap to copy credentials</div>
            </div>
          `).join('') : ''}

          <div class="order-actions">
            ${o.warranty_days && !o.warranty_claimed && o.status === 'completed' ? `
              <button class="btn-outline" onclick="claimWarrantyOrder(${o.id})">🛡️ Claim Warranty</button>
            ` : ''}
            <button class="btn-outline" onclick="reportOrderIssue(${o.id})">⚠️ Report Issue</button>
          </div>
        </div>
      `).join('');
    }

    function copyText(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Credentials copied to clipboard!');
      });
    }

    function copyReferralLink() {
      const link = document.getElementById('referral-link-text').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast('Referral link copied!');
      });
    }

    async function setCurrency(code) {
      haptic('light');
      document.querySelectorAll('#currency-options .opt-chip').forEach(el => {
        el.classList.toggle('selected', el.innerText.includes(code));
      });
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, currency: code })
        });
        showToast(`Display currency set to ${code}`);
        loadUserData();
      }
    }

    async function setLang(code) {
      haptic('light');
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

    function triggerTopup(amount) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "topup_prompt", amount: amount }));
        tg.close();
      }
    }

    function triggerRail(rail) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "open_rail", rail: rail }));
        tg.close();
      }
    }

    function claimWarrantyOrder(orderId) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "claim_warranty", order_id: orderId }));
        tg.close();
      }
    }

    function reportOrderIssue(orderId) {
      haptic('medium');
      if (tg) {
        tg.sendData(JSON.stringify({ action: "report_issue", order_id: orderId }));
        tg.close();
      }
    }

    // Initial Load
    loadCatalog();
    loadUserData();
  </script>
</body>
</html>
"""
