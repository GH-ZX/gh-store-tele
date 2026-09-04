"""Telegram Mini App (TMA) Mobile-First Storefront.

Features:
- Category Cards: Picture & Title Visual Grid by default, with instant toggle to List view.
- Profile & Settings: Hides VIP badge if Standard (0%), shows only if real discount applied; prominently displays @username.
- Referral Program: 0.2% profit margin commission on referred purchases, stat cards, and referred friends breakdown list in Settings.
- SWR (Stale-While-Revalidate) instant 0ms launch cache via localStorage.
- Dark & Light Mode Appearance Toggle with persistent storage and Telegram theme syncing.
- Full Bidirectional Arabic & English i18n Overhaul (RTL/LTR, dynamic catalog & product re-rendering, directional arrows).
- Native Arabic product descriptions from API (?lang=ar) when app language is Arabic, English otherwise.
- UX-Hardened Recharge Flow: Step 1 method selector (Stars, Crypto, SAM), Step 2 amount chips (+$1, +$5, +$10, +$25, +$50, +$100) + custom amount input, Step 3 dynamic action button with loading state.
- Wishlist / Favorites synchronized via Telegram CloudStorage with localStorage fallback.
- In-App 1-Tap Restock Notification button ('🔔 نبهني فور التوفر') via POST /api/restock/subscribe.
- Structured Credential Splitter for delivered accounts (email:pass:2fa) with discrete copy pills.
- Add to Home Screen integration (tg.addToHomeScreen).
- 1-Tap Telegram Product & Story Sharing with referral tracking.
- Catalog Quick Filters (Instant Only, In-Stock, Low-to-High Price, Favorites).
- Web Audio zero-asset synthesized micro-clicks, pops, and celebratory chimes.
- In-App Checkout Coupon / Promo Code Input & validation (POST /api/coupon/validate).
- Floating Liquid Glass Flyout Navbar with safe-area and active pill indicator.
"""

STOREFRONT_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl" data-theme="dark">
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
      --glass-bg: rgba(18, 24, 40, 0.72);
      --header-bg: rgba(9, 14, 26, 0.88);
      --input-bg: rgba(0, 0, 0, 0.35);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --nav-height: 62px;
      --safe-bottom: env(safe-area-inset-bottom, 16px);
    }

    [data-theme="light"] {
      --bg: #f8fafc;
      --card: #ffffff;
      --card-hover: #f1f5f9;
      --accent: #0284c7;
      --accent-glow: rgba(2, 132, 199, 0.2);
      --text: #0f172a;
      --hint: #64748b;
      --border: rgba(0, 0, 0, 0.08);
      --glass-border: rgba(0, 0, 0, 0.12);
      --glass-bg: rgba(255, 255, 255, 0.82);
      --header-bg: rgba(248, 250, 252, 0.92);
      --input-bg: rgba(0, 0, 0, 0.04);
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
      transition: background-color 0.25s, color 0.25s;
    }

    /* Top Sticky Navigation Bar */
    .top-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(28px) saturate(200%);
      -webkit-backdrop-filter: blur(28px) saturate(200%);
      background: var(--header-bg);
      border-bottom: 1px solid var(--border);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      transition: background-color 0.25s, border-color 0.25s;
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
    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
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
      margin-bottom: 10px;
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
      pointer-events: none;
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

    /* Quick Filter Chips */
    .filter-chips-row {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 8px;
      margin-bottom: 10px;
      scrollbar-width: none;
    }
    .filter-chips-row::-webkit-scrollbar { display: none; }
    .filter-chip {
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--hint);
      font-size: 12px;
      font-weight: 600;
      padding: 5px 12px;
      border-radius: 14px;
      white-space: nowrap;
      cursor: pointer;
      transition: all 0.15s;
    }
    .filter-chip.active {
      background: rgba(56, 189, 248, 0.18);
      color: var(--accent);
      border-color: var(--accent);
    }

    /* Promotional Hero Banner */
    .hero-banner {
      background: linear-gradient(135deg, var(--card), var(--card-hover));
      border: 1px solid var(--glass-border);
      border-radius: 16px;
      padding: 16px 18px;
      margin-bottom: 16px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
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

    /* Section Header with View Mode Toggle */
    .section-header-flex {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 16px 0 10px 4px;
    }
    .section-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--hint);
    }
    .view-toggle-capsule {
      display: flex;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2px;
      gap: 2px;
    }
    .view-toggle-btn {
      background: transparent;
      border: none;
      color: var(--hint);
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .view-toggle-btn.active {
      background: var(--card);
      color: var(--accent);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    }

    /* Picture & Title Visual Grid Layout (Cards with image and title) */
    .catalogs-grid.grid-layout {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }
    @media (max-width: 340px) {
      .catalogs-grid.grid-layout { grid-template-columns: 1fr; }
    }
    .catalog-visual-card {
      position: relative;
      border-radius: 18px;
      overflow: hidden;
      aspect-ratio: 16 / 11;
      border: 1px solid var(--glass-border);
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
      transition: transform 0.15s, box-shadow 0.15s;
      background-size: cover;
      background-position: center;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 12px;
    }
    .catalog-visual-card:active {
      transform: scale(0.97);
    }
    .catalog-visual-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0, 0, 0, 0.15) 0%, rgba(9, 14, 26, 0.9) 100%);
      pointer-events: none;
    }
    .catalog-visual-top {
      position: relative;
      z-index: 2;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .catalog-visual-pill {
      background: rgba(18, 24, 40, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.25);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      color: #38bdf8;
      padding: 3px 8px;
      border-radius: 8px;
      font-size: 10px;
      font-weight: 800;
    }
    .catalog-visual-bottom {
      position: relative;
      z-index: 2;
    }
    .catalog-visual-title {
      font-size: 15px;
      font-weight: 800;
      color: #ffffff;
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
      margin-bottom: 3px;
      line-height: 1.25;
    }
    .catalog-visual-sub {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: #cbd5e1;
      text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
      font-weight: 700;
    }

    /* List Layout (Alternate view) */
    .catalogs-grid.list-layout {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .catalog-list-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      transition: transform 0.15s, border-color 0.15s, background 0.15s;
    }
    .catalog-list-card:active {
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
      background: var(--input-bg);
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
    .chevron-icon {
      color: var(--hint);
      font-size: 18px;
      font-weight: 700;
      margin-inline-start: 8px;
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
      position: relative;
      transition: transform 0.15s, border-color 0.15s, background 0.15s;
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
      background: var(--input-bg);
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
      text-align: end;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }
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
    .wishlist-btn-card {
      background: transparent;
      border: none;
      font-size: 18px;
      cursor: pointer;
      padding: 4px;
      line-height: 1;
      transition: transform 0.15s;
    }
    .wishlist-btn-card:active { transform: scale(1.3); }

    /* IN-APP DEDICATED PRODUCT DETAIL PAGE */
    .page-hero {
      text-align: center;
      padding: 20px 0;
      background: radial-gradient(circle at center, rgba(56, 189, 248, 0.12), transparent 70%);
      border-radius: 18px;
      margin-bottom: 14px;
      position: relative;
    }
    .hero-icon { font-size: 54px; margin-bottom: 8px; }
    .hero-name { font-size: 22px; font-weight: 800; letter-spacing: -0.3px; margin-bottom: 4px; }
    .hero-cat { font-size: 12px; color: var(--accent); text-transform: uppercase; font-weight: 700; }
    .hero-actions-bar {
      position: absolute;
      top: 14px;
      right: 14px;
      display: flex;
      gap: 8px;
    }
    [dir="ltr"] .hero-actions-bar { right: auto; left: 14px; }
    .circle-icon-btn {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--input-bg);
      border: 1px solid var(--border);
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 16px;
    }
    .circle-icon-btn:active { background: rgba(56, 189, 248, 0.2); }

    .inset-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    .badges-flex {
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .pill-badge {
      background: var(--input-bg);
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
      color: var(--accent);
      margin: 10px 0 4px 0;
    }
    .rich-desc-container .desc-bullet {
      margin: 4px 0 4px 10px;
    }
    .rich-desc-container .desc-inline-code {
      background: var(--input-bg);
      color: var(--accent);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 13px;
    }
    .rich-desc-container a { color: var(--accent); text-decoration: underline; }

    /* Stepper & Action Controls */
    .stepper-capsule {
      display: inline-flex;
      align-items: center;
      background: var(--input-bg);
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

    /* Action Buttons */
    .btn-action-primary {
      width: 100%;
      height: 50px;
      border-radius: 14px;
      background: #007aff;
      color: #ffffff;
      font-size: 16px;
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
    .btn-action-primary:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-action-warning {
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
      box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
    }
    .btn-action-warning:active { opacity: 0.8; transform: scale(0.98); }
    .btn-action-secondary {
      background: var(--input-bg);
      color: var(--accent);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
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
      background: var(--border);
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

    /* Structured Credential Splitter Cards */
    .cred-grid {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin: 8px 0;
    }
    .cred-pill-row {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .cred-meta {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .cred-type-tag {
      font-size: 10px;
      font-weight: 700;
      color: var(--hint);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .cred-val-text {
      font-family: ui-monospace, SFMono-Regular, monospace;
      font-size: 13px;
      color: var(--accent);
      word-break: break-all;
    }
    .btn-copy-mini {
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: var(--accent);
      border-radius: 8px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .btn-copy-mini:active { background: rgba(56, 189, 248, 0.25); }

    /* HARDENED RECHARGE UI COMPONENTS */
    .recharge-methods-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 14px;
    }
    .recharge-method-card {
      background: var(--card);
      border: 1.5px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .recharge-method-card.active {
      border-color: var(--accent);
      background: var(--card-hover);
      box-shadow: 0 4px 16px var(--accent-glow);
    }
    .method-card-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .method-icon { font-size: 26px; }
    .method-name { font-size: 15px; font-weight: 700; }
    .method-sub { font-size: 11px; color: var(--hint); margin-top: 2px; }
    .method-radio-check {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: 2px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      color: transparent;
      transition: all 0.15s;
    }
    .recharge-method-card.active .method-radio-check {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
      font-weight: 900;
    }

    .quick-amounts-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 6px;
      margin-bottom: 10px;
    }
    @media (max-width: 400px) {
      .quick-amounts-grid { grid-template-columns: repeat(3, 1fr); }
    }
    .quick-amount-chip {
      background: var(--card);
      border: 1.5px solid var(--border);
      color: var(--text);
      font-size: 14px;
      font-weight: 700;
      padding: 10px 0;
      border-radius: 12px;
      text-align: center;
      cursor: pointer;
      transition: all 0.15s;
    }
    .quick-amount-chip.active {
      background: rgba(56, 189, 248, 0.18);
      color: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 2px 8px var(--accent-glow);
    }

    .custom-amount-box {
      display: flex;
      align-items: center;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 14px;
      gap: 8px;
    }
    .custom-amount-box input {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 16px;
      font-weight: 700;
      outline: none;
      font-family: monospace;
    }

    /* THEME SWITCHER (SEGMENTED CONTROL) */
    .theme-segmented-control {
      display: flex;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 4px;
      gap: 6px;
    }
    .theme-segment-btn {
      flex: 1;
      height: 42px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 700;
      color: var(--hint);
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .theme-segment-btn.active {
      background: var(--card);
      color: var(--accent);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
      border: 1px solid var(--border);
    }

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
      background: var(--glass-bg);
      backdrop-filter: blur(36px) saturate(220%);
      -webkit-backdrop-filter: blur(36px) saturate(220%);
      border: 1px solid var(--glass-border);
      box-shadow: 
        0 16px 40px rgba(0, 0, 0, 0.25),
        0 4px 12px rgba(0, 0, 0, 0.15),
        inset 0 1px 1px rgba(255, 255, 255, 0.35);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
      padding: 0 10px;
      transition: background-color 0.25s, border-color 0.25s;
    }
    .liquid-tab-item {
      flex: 1;
      height: 48px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: var(--hint);
      cursor: pointer;
      border-radius: 24px;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .liquid-tab-item.active {
      color: var(--accent);
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
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
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

    /* Home Screen Banner */
    .pwa-banner {
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(99, 102, 241, 0.15));
      border: 1px solid rgba(56, 189, 248, 0.3);
      border-radius: 14px;
      padding: 12px 14px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
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
    <div class="header-actions">
      <div class="header-balance-btn" onclick="switchTab('wallet')">
        <span id="top-balance-str">$0.00</span>
        <span>➕</span>
      </div>
    </div>
  </header>

  <!-- TAB 1: STORE VIEW -->
  <main id="view-store" class="tab-view active">
    <!-- Home Screen Pin Banner (Bot API 8.0) -->
    <div class="pwa-banner" id="home-screen-banner" style="display: none;">
      <div style="font-size: 13px;">
        <strong id="pwa-banner-title">📲 أضف التطبيق للشاشة الرئيسية</strong>
        <div style="font-size: 11px; color: var(--hint);" id="pwa-banner-sub">لوصول فوري ومباشر دون فتح تيليجرام</div>
      </div>
      <button class="btn-copy-mini" id="pwa-banner-btn" onclick="promptAddToHomeScreen()">إضافة الآن</button>
    </div>

    <!-- Search Bar -->
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="store-search-input" placeholder="ابحث عن كلود، جيميني، نتفلكس، في بي ان..." oninput="handleSearch()">
      <span class="clear-search" id="store-clear-btn" onclick="clearSearch()">✕</span>
    </div>

    <!-- Quick Filters & Sorting -->
    <div class="filter-chips-row" id="quick-filters-row">
      <div class="filter-chip active" id="filter-all" onclick="applyCatalogFilter('all')">الكل</div>
      <div class="filter-chip" id="filter-wishlist" onclick="applyCatalogFilter('wishlist')">❤️ المفضلة</div>
      <div class="filter-chip" id="filter-stock" onclick="applyCatalogFilter('stock')">🟢 متوفر فقط</div>
      <div class="filter-chip" id="filter-instant" onclick="applyCatalogFilter('instant')">⚡ تسليم فوري</div>
      <div class="filter-chip" id="filter-lowprice" onclick="applyCatalogFilter('lowprice')">🪙 الأقل سعراً</div>
    </div>

    <!-- Promotional Hero Banner -->
    <div class="hero-banner">
      <div class="banner-badge" id="banner-badge-text">تحديثات المتجر</div>
      <div class="banner-title" id="banner-title-text">✨ اشتراكات كلود وجيميني متوفرة فورياً</div>
      <div class="banner-sub" id="banner-sub-text">تسليم تلقائي فوري للمفاتيح والحسابات على مدار الساعة</div>
    </div>

    <!-- Mode A: Catalogs Cards (Homepage Collections with Grid/List Toggle) -->
    <div id="catalogs-collection-mode">
      <div class="section-header-flex">
        <div class="section-title" id="title-collections">التصنيفات المميزة</div>
        <div class="view-toggle-capsule">
          <button class="view-toggle-btn active" id="btn-view-grid" onclick="setCatalogViewMode('grid')">
            <span>🖼️</span> <span id="label-view-grid">شبكة</span>
          </button>
          <button class="view-toggle-btn" id="btn-view-list" onclick="setCatalogViewMode('list')">
            <span>📋</span> <span id="label-view-list">قائمة</span>
          </button>
        </div>
      </div>
      <div class="catalogs-grid grid-layout" id="catalogs-grid">
        <div class="skeleton-card"></div>
        <div class="skeleton-card"></div>
      </div>
    </div>

    <!-- Mode B: Products in Selected Collection -->
    <div id="products-catalog-mode" style="display: none;">
      <div class="subview-header">
        <button class="btn-back-catalog" onclick="returnToCollections()">
          <span id="icon-back-to-catalogs">→</span>
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
        <span id="icon-back-product">→</span>
        <span id="btn-back-product">رجوع</span>
      </button>
      <span style="font-size: 13px; color: var(--accent); font-weight: 700;" id="detail-category-header">المنتج</span>
    </div>

    <div class="page-hero">
      <div class="hero-actions-bar">
        <button class="circle-icon-btn" id="btn-detail-wishlist" onclick="toggleCurrentProductWishlist()" title="المفضلة">🤍</button>
        <button class="circle-icon-btn" onclick="shareCurrentProduct()" title="مشاركة">↗️</button>
      </div>
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
      <!-- Direct Coupon / Promo Code Input -->
      <div style="margin-bottom: 14px;">
        <div style="font-size: 12px; color: var(--hint); margin-bottom: 6px;" id="label-promo-code-input">كود الخصم / Promo Code</div>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="coupon-code-input" placeholder="SAVE10" style="flex: 1; background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; color: var(--text); padding: 8px 12px; font-family: monospace; font-size: 13px; text-transform: uppercase; outline: none;">
          <button class="btn-action-secondary" id="btn-apply-coupon" onclick="applyCheckoutCoupon()" style="padding: 6px 14px;">تطبيق</button>
        </div>
        <div id="coupon-applied-note" style="font-size: 12px; color: var(--success); font-weight: 700; margin-top: 4px; display: none;"></div>
      </div>

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

      <!-- Out-of-Stock Restock Alert Button -->
      <div id="restock-alert-box" style="display: none; margin-bottom: 10px;">
        <button class="btn-action-warning" onclick="triggerInAppRestockSubscribe()">
          <span id="btn-restock-text">🔔 نبهني فور التوفر (Restock Alert)</span>
        </button>
      </div>

      <button class="btn-action-primary" id="btn-inapp-purchase" onclick="executeProductBuy()">
        <span id="btn-buy-action-label">⚡ شراء فوري</span>
        <span id="btn-price-tag">($0.00)</span>
      </button>

      <button class="btn-stars-checkout" id="btn-stars-purchase" onclick="executeStarsDirectBuy()">
        <span id="btn-stars-action-label">⭐ الدفع عبر نجوم تيليجرام</span>
      </button>
    </div>
  </section>

  <!-- IN-APP ORDER SUCCESS VIEW -->
  <section id="view-order-success" class="tab-view">
    <div style="text-align: center; padding: 24px 0 16px 0;">
      <div style="font-size: 60px; margin-bottom: 8px;">🎉</div>
      <h2 style="font-size: 22px; font-weight: 800; margin-bottom: 4px;" id="success-view-title">تم الطلب بنجاح!</h2>
      <p style="font-size: 13px; color: var(--hint);" id="success-meta-sub">طلب #000 · تم التسليم</p>
    </div>

    <div class="inset-card">
      <div style="font-size: 12px; font-weight: 700; color: var(--hint); margin-bottom: 8px;" id="success-keys-title">بيانات الحساب / المفاتيح المسلمة</div>
      <div id="success-delivered-keys"></div>
      <div style="font-size: 11px; color: var(--hint); text-align: center; margin-top: 6px;" id="success-copy-hint">
        انقر على أي كود بالأعلى للنسخ الفوري!
      </div>
    </div>

    <div style="display: flex; gap: 10px;">
      <button class="btn-action-secondary" id="btn-success-view-orders" onclick="switchTab('orders')" style="flex: 1; height: 48px;">📦 عرض في طلباتي</button>
      <button class="btn-action-primary" id="btn-success-continue" onclick="switchTab('store')" style="flex: 1; height: 48px;">🛍️ متابعة التسوق</button>
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

  <!-- TAB 3: WALLET VIEW (UX-HARDENED RECHARGE FLOW) -->
  <main id="view-wallet" class="tab-view">
    <div class="hero-banner" style="text-align: center; padding: 24px 16px;">
      <div style="font-size: 12px; color: var(--hint); text-transform: uppercase; letter-spacing: 0.5px;" id="label-wallet-balance-title">الرصيد المتاح للشراء</div>
      <div style="font-size: 36px; font-weight: 800; margin: 4px 0;" id="wallet-balance-hero">$0.00</div>
      <div style="font-size: 13px; color: var(--accent); font-weight: 700;" id="wallet-balance-approx">جاهز للشراء الفوري</div>
    </div>

    <!-- VIP Progress Bar -->
    <div class="inset-card" style="padding: 14px;">
      <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
        <span><span id="label-vip-progress-prefix">التقدم نحو رتبة</span> <strong id="next-vip-rank" style="color: var(--warning);">Gold VIP</strong></span>
        <span id="vip-progress-num" style="color: var(--accent); font-weight: 700;">60%</span>
      </div>
      <div style="width: 100%; height: 6px; background: var(--card-hover); border-radius: 3px; overflow: hidden;">
        <div id="vip-progress-fill" style="width: 0%; height: 100%; background: var(--accent); transition: width 0.3s;"></div>
      </div>
    </div>

    <!-- Step 1: Choose Payment Method -->
    <div class="section-title" id="recharge-method-title">1. اختر وسيلة الشحن</div>
    <div class="recharge-methods-grid">
      <div class="recharge-method-card active" id="method-card-stars" onclick="selectRechargeMethod('stars')">
        <div class="method-card-left">
          <span class="method-icon">⭐</span>
          <div>
            <div class="method-name" id="label-method-stars-name">نجوم تيليجرام (Telegram Stars)</div>
            <div class="method-sub" id="label-method-stars-sub">دفع فوري عبر Apple Pay أو Google Pay</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>

      <div class="recharge-method-card" id="method-card-crypto" onclick="selectRechargeMethod('crypto')">
        <div class="method-card-left">
          <span class="method-icon">🪙</span>
          <div>
            <div class="method-name" id="label-method-crypto-name">العملات الرقمية (Crypto)</div>
            <div class="method-sub" id="label-method-crypto-sub">USDT (TRC20/BEP20), BTC, SOL عبر KryptoExpress</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>

      <div class="recharge-method-card" id="method-card-sam" onclick="selectRechargeMethod('sam')">
        <div class="method-card-left">
          <span class="method-icon">📱</span>
          <div>
            <div class="method-name" id="label-method-sam-name">سيرياتيل كاش وشام كاش (SAM)</div>
            <div class="method-sub" id="label-method-sam-sub">دفع مباشر عبر المحافظ الإلكترونية السورية</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>
    </div>

    <!-- Step 2: Choose Amount with $1 Choice or Custom -->
    <div class="section-title" id="recharge-amount-title">2. اختر المبلغ أو حدد مخصصاً</div>
    <div class="quick-amounts-grid">
      <div class="quick-amount-chip" id="chip-amt-1" onclick="selectTopupAmount(1)">+$1</div>
      <div class="quick-amount-chip" id="chip-amt-5" onclick="selectTopupAmount(5)">+$5</div>
      <div class="quick-amount-chip active" id="chip-amt-10" onclick="selectTopupAmount(10)">+$10</div>
      <div class="quick-amount-chip" id="chip-amt-25" onclick="selectTopupAmount(25)">+$25</div>
      <div class="quick-amount-chip" id="chip-amt-50" onclick="selectTopupAmount(50)">+$50</div>
      <div class="quick-amount-chip" id="chip-amt-100" onclick="selectTopupAmount(100)">+$100</div>
    </div>

    <div class="custom-amount-box">
      <span style="font-size: 16px; font-weight: 800; color: var(--accent);">$</span>
      <input type="number" id="custom-topup-input" min="1" max="1000" step="any" placeholder="10.00" value="10.00" oninput="onCustomAmountInput()">
      <span style="font-size: 12px; color: var(--hint);" id="custom-amt-curr-tag">USD</span>
    </div>

    <!-- Step 3: Action Button with Loading State -->
    <button class="btn-action-primary" id="btn-execute-recharge" onclick="executeSelectedRecharge()" style="margin-top: 14px; height: 52px;">
      <span id="recharge-btn-icon">⚡</span>
      <span id="recharge-btn-text">شحن 10.00$ عبر نجوم تيليجرام</span>
    </button>

    <!-- Redeem Gift Voucher -->
    <div class="section-title" id="voucher-section-title" style="margin-top: 24px;">شحن عبر كرت هدية (Voucher)</div>
    <div class="inset-card" style="display: flex; gap: 8px; padding: 10px;">
      <input type="text" id="voucher-code-input" placeholder="GH-XXXX-YYYY" style="flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; font-family: monospace; text-transform: uppercase;">
      <button class="btn-action-secondary" id="voucher-redeem-btn" onclick="submitVoucherRedeem()" style="padding: 6px 14px;">شحن</button>
    </div>
  </main>

  <!-- TAB 4: SETTINGS VIEW (PROFILE, THEME, LANGUAGE, REFERRALS) -->
  <main id="view-settings" class="tab-view">
    <!-- User Profile Header -->
    <div class="inset-card" style="display: flex; align-items: center; gap: 14px;">
      <div id="settings-avatar-box">
        <div class="avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">U</div>
      </div>
      <div>
        <div style="font-size: 17px; font-weight: 800;" id="user-name-title">العميل</div>
        <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-top: 1px; display: none;" id="user-handle-title">@username</div>
        <div style="font-size: 11px; color: var(--hint); font-family: monospace; margin-top: 2px;" id="user-tg-num">ID: 000000000</div>
        <!-- VIP badge is displayed ONLY if user has a real discount applied (>0%) -->
        <div style="margin-top: 5px; display: none;" id="user-vip-pill-box"></div>
      </div>
    </div>

    <!-- Appearance: Dark / Light Mode Toggle -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-theme-title">🌓 المظهر / Appearance</div>
      <div class="theme-segmented-control">
        <div class="theme-segment-btn active" id="theme-btn-dark" onclick="setAppTheme('dark')">
          <span>🌙</span>
          <span id="label-theme-dark">داكن (Dark)</span>
        </div>
        <div class="theme-segment-btn" id="theme-btn-light" onclick="setAppTheme('light')">
          <span>☀️</span>
          <span id="label-theme-light">فاتح (Light)</span>
        </div>
      </div>
    </div>

    <!-- Install PWA Button -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-install-title">📲 تثبيت التطبيق</div>
      <div style="font-size: 12px; color: var(--hint); margin-bottom: 8px;" id="label-install-desc">
        أضف أيقونة متجر GH Store إلى شاشة هاتفك الرئيسية لتصفح العروض فورياً!
      </div>
      <button class="btn-action-secondary" id="btn-install-app" onclick="promptAddToHomeScreen()" style="width: 100%; height: 42px;">
        📲 إضافة إلى الشاشة الرئيسية
      </button>
    </div>

    <!-- Currency Picker -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-currency-title">💱 عملة العرض المفضلة</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="currency-picker-chips">
        <div class="filter-chip" onclick="selectDisplayCurrency('USD')">USD ($)</div>
        <div class="filter-chip" onclick="selectDisplayCurrency('EUR')">EUR (€)</div>
        <div class="filter-chip" onclick="selectDisplayCurrency('SYP')">SYP (ل.س)</div>
        <div class="filter-chip" onclick="selectDisplayCurrency('XTR')">Stars (⭐)</div>
      </div>
    </div>

    <!-- Language Picker -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-lang-title">🌐 اللغة / Language</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;" id="language-picker-chips">
        <div class="filter-chip active" id="lang-chip-ar" onclick="changeStoreLanguage('ar')">العربية</div>
        <div class="filter-chip" id="lang-chip-en" onclick="changeStoreLanguage('en')">English</div>
        <div class="filter-chip" id="lang-chip-de" onclick="changeStoreLanguage('de')">Deutsch</div>
        <div class="filter-chip" id="lang-chip-es" onclick="changeStoreLanguage('es')">Español</div>
        <div class="filter-chip" id="lang-chip-fr" onclick="changeStoreLanguage('fr')">Français</div>
        <div class="filter-chip" id="lang-chip-it" onclick="changeStoreLanguage('it')">Italiano</div>
        <div class="filter-chip" id="lang-chip-zh" onclick="changeStoreLanguage('zh')">中文</div>
      </div>
    </div>

    <!-- Referral Program (Comprehensive Details & Breakdown) -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-referral-title">🎁 برنامج الإحالة والأرباح</div>
      <div style="font-size: 12px; color: var(--hint); margin-bottom: 12px;" id="label-referral-desc">
        شارك رابط الإحالة الخاص بك واحصل على <strong>0.2% عمولة أرباح</strong> مباشرة من هامش كل عملية شراء يقوم بها أصدقاؤك!
      </div>

      <!-- Referral Summary Stats -->
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px;">
        <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center;">
          <div style="font-size: 10px; color: var(--hint); font-weight: 700;" id="label-ref-stat-count">المدعوون</div>
          <div style="font-size: 18px; font-weight: 800; color: var(--accent); margin-top: 2px;" id="referral-count-val">0</div>
        </div>
        <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center;">
          <div style="font-size: 10px; color: var(--hint); font-weight: 700;" id="label-ref-stat-earned">إجمالي الأرباح</div>
          <div style="font-size: 18px; font-weight: 800; color: var(--success); margin-top: 2px;" id="referral-earned-val">$0.00</div>
        </div>
        <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center;">
          <div style="font-size: 10px; color: var(--hint); font-weight: 700;" id="label-ref-stat-rate">نسبة العمولة</div>
          <div style="font-size: 16px; font-weight: 800; color: var(--warning); margin-top: 2px;">0.2%</div>
        </div>
      </div>

      <!-- Referral Link Box -->
      <div style="display: flex; align-items: center; justify-content: space-between; background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; padding: 10px; margin-bottom: 14px;">
        <span id="referral-link-display" style="font-family: monospace; font-size: 12px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-inline-end: 8px;">https://t.me/...</span>
        <button class="btn-action-secondary" id="btn-copy-ref-link" onclick="copyReferralLink()" style="padding: 4px 10px;">نسخ</button>
      </div>

      <!-- Breakdown of Invited Friends & Individual Earnings -->
      <div style="font-size: 13px; font-weight: 700; margin-bottom: 8px;" id="label-ref-breakdown-title">
        👥 سجل الأصدقاء المدعوين والأرباح
      </div>
      <div id="referrals-breakdown-list" style="display: flex; flex-direction: column; gap: 6px;"></div>
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
    }

    // Zero-Asset Synthesized Web Audio Micro-Clicks
    let audioCtx = null;
    function initAudio() {
      if (!audioCtx) {
        const AudioCtor = window.AudioContext || window.webkitAudioContext;
        if (AudioCtor) audioCtx = new AudioCtor();
      }
      if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
    }
    function playAudioTick() {
      try {
        initAudio();
        if (!audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(800, audioCtx.currentTime + 0.015);
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.015);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.016);
      } catch (e) {}
    }
    function playAudioPop() {
      try {
        initAudio();
        if (!audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(220, audioCtx.currentTime + 0.025);
        gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.025);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.026);
      } catch (e) {}
    }
    function playAudioChime() {
      try {
        initAudio();
        if (!audioCtx) return;
        [523.25, 659.25].forEach((freq, idx) => {
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, audioCtx.currentTime + idx * 0.1);
          gain.gain.setValueAtTime(0.15, audioCtx.currentTime + idx * 0.1);
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + idx * 0.1 + 0.25);
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.start(audioCtx.currentTime + idx * 0.1);
          osc.stop(audioCtx.currentTime + idx * 0.1 + 0.26);
        });
      } catch (e) {}
    }

    function haptic(type = 'light') {
      try {
        if (type === 'pop') { playAudioPop(); }
        else if (type === 'success') { playAudioChime(); }
        else { playAudioTick(); }

        if (tg?.HapticFeedback) {
          if (type === 'success' || type === 'error' || type === 'warning') {
            tg.HapticFeedback.notificationOccurred(type);
          } else {
            tg.HapticFeedback.impactOccurred(type === 'pop' ? 'light' : 'medium');
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

    // State Variables
    let allProducts = [];
    let categoriesList = [];
    let userData = null;
    let activeCatalog = null;
    let selectedProduct = null;
    let selectedQty = 1;
    let activeTab = 'store';
    let currentAppLanguage = 'ar';
    let activeCatalogFilter = 'all';
    let appliedCoupon = null;
    let wishlistSet = new Set();
    let currentCatalogViewMode = localStorage.getItem('ghstore_cat_view') || 'grid';

    // Recharge Flow State
    let selectedRechargeMethod = 'stars';
    let selectedRechargeAmount = 10.0;

    // Telegram User ID Resolution
    const urlParams = new URLSearchParams(window.location.search);
    const tgUser = tg?.initDataUnsafe?.user;
    const userId = tgUser?.id || Number(urlParams.get('tg_id') || 0);

    // Appearance / Theme Switcher
    function setAppTheme(theme) {
      haptic('pop');
      document.documentElement.setAttribute('data-theme', theme);
      try { localStorage.setItem('ghstore_theme', theme); } catch (e) {}

      document.querySelectorAll('.theme-segment-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById('theme-btn-' + theme);
      if (activeBtn) activeBtn.classList.add('active');

      const isLight = (theme === 'light');
      const bgCol = isLight ? '#f8fafc' : '#090e1a';
      try {
        if (tg?.setHeaderColor) tg.setHeaderColor(bgCol);
        if (tg?.setBackgroundColor) tg.setBackgroundColor(bgCol);
      } catch (e) {}
    }

    function initAppTheme() {
      const savedTheme = localStorage.getItem('ghstore_theme') || 'dark';
      setAppTheme(savedTheme);
    }

    // Wishlist Sync (CloudStorage + localStorage)
    function initWishlist() {
      try {
        const local = localStorage.getItem('ghstore_wishlist');
        if (local) wishlistSet = new Set(JSON.parse(local));
      } catch (e) {}

      if (tg?.CloudStorage) {
        tg.CloudStorage.getItem('ghstore_wishlist', (err, val) => {
          if (!err && val) {
            try {
              wishlistSet = new Set(JSON.parse(val));
              if (activeCatalogFilter === 'wishlist') applyCatalogFilter('wishlist');
            } catch (e) {}
          }
        });
      }
    }

    function saveWishlist() {
      const arr = Array.from(wishlistSet);
      try { localStorage.setItem('ghstore_wishlist', JSON.stringify(arr)); } catch (e) {}
      if (tg?.CloudStorage) {
        tg.CloudStorage.setItem('ghstore_wishlist', JSON.stringify(arr), () => {});
      }
    }

    function toggleWishlist(productId, e) {
      if (e) e.stopPropagation();
      haptic('pop');
      const id = Number(productId);
      if (wishlistSet.has(id)) {
        wishlistSet.delete(id);
        showToast(currentAppLanguage === 'ar' ? 'تمت الإزالة من المفضلة' : 'Removed from favorites');
      } else {
        wishlistSet.add(id);
        showToast(currentAppLanguage === 'ar' ? '❤️ تمت الإضافة للمفضلة!' : '❤️ Added to favorites!');
      }
      saveWishlist();
      updateWishlistUI();
    }

    function toggleCurrentProductWishlist() {
      if (!selectedProduct) return;
      toggleWishlist(selectedProduct.id);
    }

    function updateWishlistUI() {
      const btn = document.getElementById('btn-detail-wishlist');
      if (btn && selectedProduct) {
        btn.innerText = wishlistSet.has(Number(selectedProduct.id)) ? '❤️' : '🤍';
      }
      document.querySelectorAll('.wishlist-btn-card').forEach(b => {
        const pid = Number(b.dataset.pid);
        b.innerText = wishlistSet.has(pid) ? '❤️' : '🤍';
      });
    }

    // Bilingual Collections Config with Curated HD Visual Pictures
    const CATALOG_META = {
      "AI & Chatbots": {
        arTitle: "🤖 الذكاء الاصطناعي",
        enTitle: "🤖 AI & Chatbots",
        icon: "🤖",
        image: "https://images.unsplash.com/photo-1677442136019-21780efad99a?w=600&auto=format&fit=crop&q=80",
        arPreview: "كلود · شات جي بي تي · جيميني · جروك",
        enPreview: "Claude · ChatGPT · Gemini · Grok"
      },
      "Streaming & Entertainment": {
        arTitle: "🎬 البث والترفيه",
        enTitle: "🎬 Streaming & Media",
        icon: "🎬",
        image: "https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=600&auto=format&fit=crop&q=80",
        arPreview: "نتفلكس · بيكوك · شاهد · أبل تي في",
        enPreview: "Netflix · Peacock · Shahid · Apple TV"
      },
      "VPN & Security": {
        arTitle: "🛡️ الحماية والـ VPN",
        enTitle: "🛡️ VPN & Security",
        icon: "🛡️",
        image: "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=600&auto=format&fit=crop&q=80",
        arPreview: "نورد في بي ان · سيرف شارك · بروتون",
        enPreview: "NordVPN · Surfshark · Proton VPN"
      },
      "Design & Creative": {
        arTitle: "🎨 التصميم والإبداع",
        enTitle: "🎨 Design & Creative",
        icon: "🎨",
        image: "https://images.unsplash.com/photo-1626785774573-4b799315345d?w=600&auto=format&fit=crop&q=80",
        arPreview: "كانفا · أدوبي · فيجما · فريمر",
        enPreview: "Canva · Adobe · Figma · Framer"
      },
      "Productivity": {
        arTitle: "📝 الإنتاجية والأدوات",
        enTitle: "📝 Productivity & Tools",
        icon: "📝",
        image: "https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=600&auto=format&fit=crop&q=80",
        arPreview: "نوشن · كاب كات · أوفيس",
        enPreview: "Notion · CapCut · MS Office 365"
      },
      "Other": {
        arTitle: "📦 منتجات رقمية متنوعة",
        enTitle: "📦 Digital Subscriptions",
        icon: "📦",
        image: "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=600&auto=format&fit=crop&q=80",
        arPreview: "تراخيص، مفاتيح واشتراكات",
        enPreview: "Licenses, activations and keys"
      }
    };

    // Robust Markdown & HTML Formatter
    function formatRichDescription(raw) {
      if (!raw) return '<span style="color: var(--hint)">لا يوجد وصف إضافي.</span>';
      let text = String(raw).trim();

      const entityMap = { '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&amp;': '&' };
      text = text.replace(/&(lt|gt|quot|apos|amp);/g, (m) => entityMap[m] || m);

      const emojis = [];
      text = text.replace(/<tg-emoji[^>]*emoji-id="([^"]+)"[^>]*>(.*?)<\/tg-emoji>/gi, (m, id, char) => {
        const placeholder = `__TG_EMOJI_${emojis.length}__`;
        emojis.push(`<span style="display:inline-flex; align-items:center; vertical-align:middle;">${char}</span>`);
        return placeholder;
      });

      text = text.replace(/^###\s*(.*$)/gim, '<div class="desc-heading">$1</div>');
      text = text.replace(/^##\s*(.*$)/gim, '<div class="desc-heading">$1</div>');
      text = text.replace(/^#\s*(.*$)/gim, '<div class="desc-heading">$1</div>');

      text = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
      text = text.replace(/__(.*?)__/g, '<u>$1</u>');

      text = text.replace(/\*([^\*\n]+)\*/g, '<i>$1</i>');
      text = text.replace(/_([^_\n]+)_/g, '<i>$1</i>');

      text = text.replace(/`([^`]+)`/g, '<code class="desc-inline-code">$1</code>');
      text = text.replace(/^[\s]*[-*•]\s+(.+)$/gim, '<div class="desc-bullet">• $1</div>');

      text = text.replace(/\r?\n/g, '<br>');
      text = text.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');

      emojis.forEach((em, idx) => {
        text = text.replace(`__TG_EMOJI_${idx}__`, em);
      });

      return text;
    }

    // Structured Credential Splitter
    function renderStructuredCredentials(goods) {
      if (!goods || !goods.length) {
        return '<div style="padding: 12px; color: var(--warning); text-align: center;">⏳ جاري التفعيل، سيتم التسليم قريباً.</div>';
      }

      return goods.map(raw => {
        const line = String(raw).trim();
        let parts = [];
        if (line.includes(' | ')) { parts = line.split(' | '); }
        else if (line.includes(' / ')) { parts = line.split(' / '); }
        else if (line.includes(':') && line.split(':').length >= 2 && !line.startsWith('http')) {
          parts = line.split(':');
        }

        if (parts.length >= 2) {
          const rows = parts.map((part, idx) => {
            let label = (currentAppLanguage === 'ar') ? "بيانات" : "Credential";
            if (idx === 0) label = part.includes('@') ? (currentAppLanguage === 'ar' ? "📧 البريد / المستخدم" : "📧 Email / User") : (currentAppLanguage === 'ar' ? "👤 اسم المستخدم" : "👤 Username");
            else if (idx === 1) label = (currentAppLanguage === 'ar') ? "🔑 كلمة المرور" : "🔑 Password";
            else if (idx === 2) label = (currentAppLanguage === 'ar') ? "🛡️ كود 2FA / الأمان" : "🛡️ 2FA / Security Key";
            else label = (currentAppLanguage === 'ar') ? `معلومة ${idx + 1}` : `Field ${idx + 1}`;

            return `
              <div class="cred-pill-row">
                <div class="cred-meta">
                  <span class="cred-type-tag">${label}</span>
                  <span class="cred-val-text">${part.trim()}</span>
                </div>
                <button class="btn-copy-mini" onclick="copyCredText('${part.trim().replace(/'/g, "\\\\'")}')">${currentAppLanguage === 'ar' ? 'نسخ' : 'Copy'}</button>
              </div>
            `;
          }).join('');

          return `
            <div class="cred-grid">
              ${rows}
              <div style="text-align: left; margin-top: 2px;">
                <button class="btn-copy-mini" style="font-size: 10px;" onclick="copyCredText('${line.replace(/'/g, "\\\\'")}')">${currentAppLanguage === 'ar' ? '📋 نسخ السطر كاملاً' : '📋 Copy Full Line'}</button>
              </div>
            </div>
          `;
        }

        return `
          <div class="cred-pill-row" style="margin: 6px 0;">
            <div class="cred-meta">
              <span class="cred-type-tag">${currentAppLanguage === 'ar' ? 'مفتاح / كود التفعيل' : 'License / Key'}</span>
              <span class="cred-val-text">${line}</span>
            </div>
            <button class="btn-copy-mini" onclick="copyCredText('${line.replace(/'/g, "\\\\'")}')">${currentAppLanguage === 'ar' ? 'نسخ' : 'Copy'}</button>
          </div>
        `;
      }).join('');
    }

    // Complete i18n Translation Dictionary
    const I18N = {
      ar: {
        store: "المتجر",
        orders: "طلباتي",
        wallet: "المحفظة",
        settings: "الإعدادات",
        caption: "المتجر الرقمي المعتمد",
        search: "ابحث عن كلود، جيميني، نتفلكس، في بي ان...",
        filter_all: "الكل",
        filter_wishlist: "❤️ المفضلة",
        filter_stock: "🟢 متوفر فقط",
        filter_instant: "⚡ تسليم فوري",
        filter_lowprice: "🪙 الأقل سعراً",
        banner_badge: "تحديثات المتجر",
        banner_title: "✨ اشتراكات كلود وجيميني متوفرة فورياً",
        banner_sub: "تسليم تلقائي فوري للمفاتيح والحسابات على مدار الساعة",
        pwa_title: "📲 أضف التطبيق للشاشة الرئيسية",
        pwa_sub: "لوصول فوري ومباشر دون فتح تيليجرام",
        pwa_btn: "إضافة الآن",
        collections: "التصنيفات المميزة",
        all_catalogs: "جميع التصنيفات",
        items_suffix: "منتج",
        starts_from: "يبدأ من",
        view_details: "عرض ‹",
        back: "رجوع",
        view_grid: "شبكة",
        view_list: "قائمة",
        product: "المنتج",
        instant_delivery: "⚡ تسليم تلقائي فوري",
        custom_activation: "⏳ تفعيل مخصص",
        warranty_30d: "🛡️ ضمان 30 يوم",
        in_stock: "🟢 متوفر",
        out_of_stock: "🔴 نفد المخزون",
        desc: "الوصف",
        promo_code_label: "كود الخصم / Promo Code",
        apply: "تطبيق",
        total: "السعر الإجمالي",
        insufficient_balance: "⚠️ الرصيد المتاح غير كافٍ لهذا الطلب.",
        topup_to_continue: "💳 شحن الرصيد للمتابعة",
        buy_now: "⚡ شراء فوري",
        stars_buy: "⭐ الدفع عبر نجوم تيليجرام",
        restock_alert: "🔔 نبهني فور التوفر (Restock Alert)",
        order_success: "تم الطلب بنجاح!",
        delivered_keys: "بيانات الحساب / المفاتيح المسلمة",
        copy_hint: "انقر على أي كود بالأعلى للنسخ الفوري!",
        view_orders: "📦 عرض في طلباتي",
        continue_shopping: "🛍️ متابعة التسوق",
        orders_title: "سجل الطلبات والمشتريات",
        orders_empty_title: "لا توجد طلبات بعد",
        orders_empty_sub: "تصفح التصنيفات واطلب الحسابات والمفاتيح بضغطة واحدة!",
        browse_store: "تصفح المتجر",
        step_placed: "تم الطلب",
        step_processing: "قيد المعالجة",
        step_delivered: "تم التسليم",
        claim_warranty: "🛡️ طلب تعويض الضمان",
        wallet_balance_title: "الرصيد المتاح للشراء",
        wallet_ready: "جاهز للشراء الفوري",
        vip_progress: "التقدم نحو رتبة",
        method_section_title: "1. اختر وسيلة الشحن",
        stars_title: "نجوم تيليجرام (Telegram Stars)",
        stars_sub: "دفع فوري عبر Apple Pay أو Google Pay",
        crypto_title: "العملات الرقمية (Crypto)",
        crypto_sub: "USDT (TRC20/BEP20), BTC, SOL عبر KryptoExpress",
        sam_title: "سيرياتيل كاش وشام كاش (SAM)",
        sam_sub: "دفع مباشر عبر المحافظ الإلكترونية السورية",
        amount_section_title: "2. اختر المبلغ أو حدد مخصصاً",
        custom_amount_placeholder: "أدخل المبلغ ($)... e.g. 15",
        voucher_section_title: "شحن عبر كرت هدية (Voucher)",
        voucher_btn: "شحن الكرت",
        theme_section_title: "🌓 المظهر / Appearance",
        theme_dark: "داكن (Dark)",
        theme_light: "فاتح (Light)",
        install_section_title: "📲 تثبيت التطبيق",
        install_desc: "أضف أيقونة متجر GH Store إلى شاشة هاتفك الرئيسية لتصفح العروض فورياً!",
        install_btn: "📲 إضافة إلى الشاشة الرئيسية",
        currency_title: "💱 عملة العرض المفضلة",
        lang_title: "🌐 اللغة / Language",
        referral_title: "🎁 برنامج الإحالة والأرباح",
        referral_desc: "شارك رابط الإحالة الخاص بك واحصل على <strong>0.2% عمولة أرباح</strong> مباشرة من هامش كل عملية شراء يقوم بها أصدقاؤك!",
        ref_stat_count: "المدعوون",
        ref_stat_earned: "إجمالي الأرباح",
        ref_stat_rate: "نسبة العمولة",
        ref_breakdown_title: "👥 سجل الأصدقاء المدعوين والأرباح",
        copy: "نسخ",
        orders_word: "طلب"
      },
      en: {
        store: "Store",
        orders: "Orders",
        wallet: "Wallet",
        settings: "Settings",
        caption: "Verified Digital Reseller",
        search: "Search Claude, Gemini, Netflix, VPN...",
        filter_all: "All",
        filter_wishlist: "❤️ Favorites",
        filter_stock: "🟢 In Stock",
        filter_instant: "⚡ Instant Delivery",
        filter_lowprice: "🪙 Lowest Price",
        banner_badge: "STORE UPDATES",
        banner_title: "✨ Instant Claude & Gemini Accounts Ready",
        banner_sub: "Automated 24/7 key & account delivery with instant activation",
        pwa_title: "📲 Add App to Home Screen",
        pwa_sub: "Direct instant launch without opening Telegram",
        pwa_btn: "Add Now",
        collections: "Featured Catalogs",
        all_catalogs: "All Catalogs",
        items_suffix: "items",
        starts_from: "From",
        view_details: "View ›",
        back: "Back",
        view_grid: "Grid",
        view_list: "List",
        product: "Product",
        instant_delivery: "⚡ Instant Automated Delivery",
        custom_activation: "⏳ Custom Activation",
        warranty_30d: "🛡️ 30 Days Warranty",
        in_stock: "🟢 In Stock",
        out_of_stock: "🔴 Out of Stock",
        desc: "Description",
        promo_code_label: "Promo Code / Coupon",
        apply: "Apply",
        total: "Total Price",
        insufficient_balance: "⚠️ Insufficient balance for this order.",
        topup_to_continue: "💳 Top Up Balance to Continue",
        buy_now: "⚡ Instant Buy",
        stars_buy: "⭐ Pay with Telegram Stars",
        restock_alert: "🔔 Notify When Available (Restock Alert)",
        order_success: "Order Successful!",
        delivered_keys: "Delivered Credentials / Keys",
        copy_hint: "Tap any code above to copy instantly!",
        view_orders: "📦 View in Orders",
        continue_shopping: "🛍️ Continue Shopping",
        orders_title: "Order History & Purchases",
        orders_empty_title: "No orders yet",
        orders_empty_sub: "Browse catalogs and order accounts & keys in 1 tap!",
        browse_store: "Browse Store",
        step_placed: "Placed",
        step_processing: "Processing",
        step_delivered: "Delivered",
        claim_warranty: "🛡️ Claim Warranty",
        wallet_balance_title: "Available Balance",
        wallet_ready: "Ready for instant purchase",
        vip_progress: "Progress to",
        method_section_title: "1. Select Payment Method",
        stars_title: "Telegram Stars",
        stars_sub: "Instant pay via Apple Pay, Google Pay or Stars",
        crypto_title: "Crypto (USDT, BTC, SOL)",
        crypto_sub: "USDT (TRC20/BEP20), BTC, SOL via KryptoExpress",
        sam_title: "Syriatel Cash & Sham Cash (SAM)",
        sam_sub: "Direct payment via Syrian mobile wallets",
        amount_section_title: "2. Choose Amount or Enter Custom",
        custom_amount_placeholder: "Enter amount ($)... e.g. 15",
        voucher_section_title: "Redeem Gift Card (Voucher)",
        voucher_btn: "Redeem Card",
        theme_section_title: "🌓 Theme & Appearance",
        theme_dark: "Dark Mode",
        theme_light: "Light Mode",
        install_section_title: "📲 Install App",
        install_desc: "Add GH Store to your phone home screen for instant access!",
        install_btn: "📲 Add to Home Screen",
        currency_title: "💱 Preferred Display Currency",
        lang_title: "🌐 Language",
        referral_title: "🎁 Referral Program & Earnings",
        referral_desc: "Share your referral link and earn <strong>0.2% profit margin commission</strong> on every purchase made by friends!",
        ref_stat_count: "Invited",
        ref_stat_earned: "Total Earned",
        ref_stat_rate: "Commission",
        ref_breakdown_title: "👥 Referred Friends & Earnings Breakdown",
        copy: "Copy",
        orders_word: "orders"
      }
    };

    function applyLanguage(lang) {
      currentAppLanguage = lang;
      try { localStorage.setItem('ghstore_lang', lang); } catch (e) {}

      const d = I18N[lang] || I18N.en || I18N.ar;
      const isRtl = (lang === 'ar');
      document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
      document.documentElement.lang = lang;

      const setText = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt; };
      setText('i18n-tab-store', d.store);
      setText('i18n-tab-orders', d.orders);
      setText('i18n-tab-wallet', d.wallet);
      setText('i18n-tab-settings', d.settings);
      setText('top-sub-caption', d.caption);

      const sInput = document.getElementById('store-search-input');
      if (sInput) sInput.placeholder = d.search;
      setText('filter-all', d.filter_all);
      setText('filter-wishlist', d.filter_wishlist);
      setText('filter-stock', d.filter_stock);
      setText('filter-instant', d.filter_instant);
      setText('filter-lowprice', d.filter_lowprice);

      setText('banner-badge-text', d.banner_badge);
      setText('banner-title-text', d.banner_title);
      setText('banner-sub-text', d.banner_sub);
      setText('pwa-banner-title', d.pwa_title);
      setText('pwa-banner-sub', d.pwa_sub);
      setText('pwa-banner-btn', d.pwa_btn);

      setText('title-collections', d.collections);
      setText('label-view-grid', d.view_grid);
      setText('label-view-list', d.view_list);
      setText('btn-back-to-catalogs', d.all_catalogs);
      setText('btn-back-product', d.back);
      const backArrow = isRtl ? '→' : '←';
      setText('icon-back-to-catalogs', backArrow);
      setText('icon-back-product', backArrow);

      setText('detail-category-header', d.product);
      setText('label-desc-title', d.desc);
      setText('label-promo-code-input', d.promo_code_label);
      setText('btn-apply-coupon', d.apply);
      setText('label-total-title', d.total);
      setText('btn-buy-action-label', d.buy_now);
      setText('btn-stars-action-label', d.stars_buy);
      setText('btn-restock-text', d.restock_alert);

      setText('success-view-title', d.order_success);
      setText('success-keys-title', d.delivered_keys);
      setText('success-copy-hint', d.copy_hint);
      setText('btn-success-view-orders', d.view_orders);
      setText('btn-success-continue', d.continue_shopping);
      setText('title-orders-history', d.orders_title);

      setText('label-wallet-balance-title', d.wallet_balance_title);
      setText('label-vip-progress-prefix', d.vip_progress);
      setText('recharge-method-title', d.method_section_title);
      setText('label-method-stars-name', d.stars_title);
      setText('label-method-stars-sub', d.stars_sub);
      setText('label-method-crypto-name', d.crypto_title);
      setText('label-method-crypto-sub', d.crypto_sub);
      setText('label-method-sam-name', d.sam_title);
      setText('label-method-sam-sub', d.sam_sub);
      setText('recharge-amount-title', d.amount_section_title);
      setText('voucher-section-title', d.voucher_section_title);
      setText('voucher-redeem-btn', d.voucher_btn);

      const customInput = document.getElementById('custom-topup-input');
      if (customInput) customInput.placeholder = d.custom_amount_placeholder;
      updateRechargeButtonText();

      setText('label-theme-title', d.theme_section_title);
      setText('label-theme-dark', d.theme_dark);
      setText('label-theme-light', d.theme_light);
      setText('label-install-title', d.install_section_title);
      setText('label-install-desc', d.install_desc);
      setText('btn-install-app', d.install_btn);
      setText('label-currency-title', d.currency_title);
      setText('label-lang-title', d.lang_title);
      setText('label-referral-title', d.referral_title);
      const descBox = document.getElementById('label-referral-desc');
      if (descBox) descBox.innerHTML = d.referral_desc;
      setText('label-ref-stat-count', d.ref_stat_count);
      setText('label-ref-stat-earned', d.ref_stat_earned);
      setText('label-ref-stat-rate', d.ref_stat_rate);
      setText('label-ref-breakdown-title', d.ref_breakdown_title);
      setText('btn-copy-ref-link', d.copy);

      document.querySelectorAll('#language-picker-chips .filter-chip').forEach(el => {
        el.classList.toggle('active', el.id === 'lang-chip-' + lang);
      });

      renderCatalogsGrid();
      if (activeCatalog) {
        const meta = CATALOG_META[activeCatalog];
        const dispTitle = (lang === 'ar' && meta?.arTitle) ? meta.arTitle : (meta?.enTitle || activeCatalog);
        setText('active-collection-title', dispTitle);
        let filtered = allProducts.filter(p => p.category === activeCatalog);
        filtered = filterAndSortProducts(filtered);
        renderProductItems(filtered);
      }
      if (selectedProduct) {
        const rawDesc = (lang === 'ar' && selectedProduct.description_ar)
          ? selectedProduct.description_ar
          : (selectedProduct.description || '');
        const pDescBox = document.getElementById('prod-rich-desc');
        if (pDescBox) pDescBox.innerHTML = formatRichDescription(rawDesc);
        updateDetailPagePrice();
      }
      if (userData?.orders) {
        renderOrders(userData.orders);
      }
      if (userData) {
        renderReferralsBreakdown(userData.referrals_breakdown || [], userData.referrals_total_earned || 0.0, userData.referrals_count || 0);
      }
    }

    // Tab Navigation
    function switchTab(tab) {
      haptic('pop');
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

    // SWR Cache Storage & Fetching
    function loadFromCache() {
      try {
        const catCache = localStorage.getItem('ghstore_catalog_cache');
        if (catCache) {
          const parsed = JSON.parse(catCache);
          allProducts = parsed.products || [];
          categoriesList = parsed.categories || [];
          renderCatalogsGrid();
        }
        const userCache = localStorage.getItem('ghstore_user_cache');
        if (userCache) {
          userData = JSON.parse(userCache);
          updateBalancePills();
        }
      } catch (e) {}
    }

    async function fetchCatalogData() {
      try {
        const res = await fetch('/api/catalog');
        const d = await res.json();
        allProducts = d.products || [];
        categoriesList = d.categories || [];
        try { localStorage.setItem('ghstore_catalog_cache', JSON.stringify(d)); } catch (e) {}
        renderCatalogsGrid();
        if (activeCatalog) {
          openCollection(activeCatalog);
        }
      } catch (e) {
        if (!allProducts.length) {
          document.getElementById('catalogs-grid').innerHTML = '<div style="color: var(--hint); text-align: center; padding: 30px;">فشل تحميل التصنيفات.</div>';
        }
      }
    }

    // Category View Mode: Picture & Title Grid vs Detailed List
    function setCatalogViewMode(mode) {
      haptic('pop');
      currentCatalogViewMode = mode;
      try { localStorage.setItem('ghstore_cat_view', mode); } catch (e) {}

      const btnG = document.getElementById('btn-view-grid');
      const btnL = document.getElementById('btn-view-list');
      if (btnG) btnG.classList.toggle('active', mode === 'grid');
      if (btnL) btnL.classList.toggle('active', mode === 'list');

      renderCatalogsGrid();
    }

    function renderCatalogsGrid() {
      const container = document.getElementById('catalogs-grid');
      if (!container) return;

      const groups = {};
      categoriesList.forEach(c => {
        groups[c] = allProducts.filter(p => p.category === c);
      });

      const d = I18N[currentAppLanguage] || I18N.ar;
      const isGrid = (currentCatalogViewMode === 'grid');

      container.className = `catalogs-grid ${isGrid ? 'grid-layout' : 'list-layout'}`;

      container.innerHTML = Object.keys(groups).map(catName => {
        const items = groups[catName];
        if (!items || !items.length) return '';
        const meta = CATALOG_META[catName] || {
          arTitle: catName,
          enTitle: catName,
          icon: "📦",
          image: "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=600&auto=format&fit=crop&q=80",
          arPreview: "منتجات رقمية",
          enPreview: "Digital goods"
        };
        const minPrice = Math.min(...items.map(p => p.price || 999));
        const sym = items[0]?.sym || '$';
        const displayTitle = (currentAppLanguage === 'ar' && meta.arTitle) ? meta.arTitle : (meta.enTitle || catName);
        const displayPreview = (currentAppLanguage === 'ar' && meta.arPreview) ? meta.arPreview : (meta.enPreview || meta.arPreview);

        if (isGrid) {
          // Visual Card: Picture + Title
          return `
            <div class="catalog-visual-card" style="background-image: url('${meta.image}');" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
              <div class="catalog-visual-overlay"></div>
              <div class="catalog-visual-top">
                <span class="catalog-visual-pill">${items.length} ${d.items_suffix}</span>
              </div>
              <div class="catalog-visual-bottom">
                <div class="catalog-visual-title">${displayTitle}</div>
                <div class="catalog-visual-sub">
                  <span>${d.starts_from} ${minPrice.toFixed(2)}${sym}</span>
                  <span style="font-size: 14px;">${(currentAppLanguage === 'ar') ? '‹' : '›'}</span>
                </div>
              </div>
            </div>
          `;
        }

        // List Card (Alternate View)
        const chevron = (currentAppLanguage === 'ar') ? '‹' : '›';
        return `
          <div class="catalog-list-card" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
            <div class="catalog-left">
              <div class="catalog-icon-box">${meta.icon}</div>
              <div class="catalog-info">
                <div class="catalog-name">${displayTitle}</div>
                <div class="catalog-sub">
                  <span>${items.length} ${d.items_suffix}</span> ·
                  <span style="color: var(--accent); font-weight: 700;">${d.starts_from} ${minPrice.toFixed(2)}${sym}</span>
                </div>
                <div style="font-size: 11px; color: var(--hint); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${displayPreview}
                </div>
              </div>
            </div>
            <span class="chevron-icon">${chevron}</span>
          </div>
        `;
      }).join('');
    }

    function openCollection(catName) {
      haptic('light');
      activeCatalog = catName;
      document.getElementById('catalogs-collection-mode').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'block';
      const meta = CATALOG_META[catName];
      const dispTitle = (currentAppLanguage === 'ar' && meta?.arTitle) ? meta.arTitle : (meta?.enTitle || catName);
      document.getElementById('active-collection-title').innerText = dispTitle;

      let filtered = allProducts.filter(p => p.category === catName);
      filtered = filterAndSortProducts(filtered);
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

    // Quick Filters & Sorting Logic
    function applyCatalogFilter(filterKey) {
      haptic('pop');
      activeCatalogFilter = filterKey;
      document.querySelectorAll('#quick-filters-row .filter-chip').forEach(el => el.classList.remove('active'));
      const activeEl = document.getElementById('filter-' + filterKey);
      if (activeEl) activeEl.classList.add('active');

      if (filterKey === 'all' && !document.getElementById('store-search-input').value.trim()) {
        returnToCollections();
        return;
      }

      document.getElementById('catalogs-collection-mode').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'block';

      let baseList = activeCatalog ? allProducts.filter(p => p.category === activeCatalog) : allProducts;
      const q = (document.getElementById('store-search-input').value || '').trim().toLowerCase();
      if (q) {
        baseList = baseList.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.description_ar || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
      }

      const filtered = filterAndSortProducts(baseList);
      document.getElementById('active-collection-title').innerText = filterKey === 'wishlist'
        ? (currentAppLanguage === 'ar' ? '❤️ المفضلة' : '❤️ Favorites')
        : (currentAppLanguage === 'ar' ? 'النتائج المصفاة' : 'Filtered Results');
      renderProductItems(filtered);
    }

    function filterAndSortProducts(list) {
      let result = [...list];
      if (activeCatalogFilter === 'wishlist') {
        result = result.filter(p => wishlistSet.has(Number(p.id)));
      } else if (activeCatalogFilter === 'stock') {
        result = result.filter(p => p.stock === null || p.stock > 0);
      } else if (activeCatalogFilter === 'instant') {
        result = result.filter(p => p.delivery_type !== 'activation');
      } else if (activeCatalogFilter === 'lowprice') {
        result.sort((a, b) => (a.price || 0) - (b.price || 0));
      }
      return result;
    }

    function handleSearch() {
      const q = (document.getElementById('store-search-input').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('store-clear-btn');

      if (q) {
        clearBtn.style.display = 'block';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
        document.getElementById('products-catalog-mode').style.display = 'block';
        document.getElementById('active-collection-title').innerText = (currentAppLanguage === 'ar') ? `بحث: "${q}"` : `Search: "${q}"`;

        let matched = allProducts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.description_ar || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
        matched = filterAndSortProducts(matched);
        renderProductItems(matched);
      } else {
        clearBtn.style.display = 'none';
        if (activeCatalogFilter === 'all') returnToCollections();
        else applyCatalogFilter(activeCatalogFilter);
      }
    }

    function clearSearch() {
      document.getElementById('store-search-input').value = '';
      returnToCollections();
    }

    function renderProductItems(products) {
      const container = document.getElementById('catalog-products-list');
      if (!container) return;
      if (!products.length) {
        container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--hint);">${currentAppLanguage === 'ar' ? 'لا توجد منتجات مطابقة لهذا الفلتر.' : 'No products found matching this filter.'}</div>`;
        return;
      }
      const d = I18N[currentAppLanguage] || I18N.ar;
      container.innerHTML = products.map(p => {
        const isFav = wishlistSet.has(Number(p.id));
        const isOutOfStock = (p.stock !== null && p.stock <= 0);
        const stockStr = isOutOfStock
          ? (currentAppLanguage === 'ar' ? 'نفد المخزون' : 'Out of Stock')
          : (p.stock ? `${currentAppLanguage === 'ar' ? 'متوفر' : 'In Stock'} (${p.stock})` : (currentAppLanguage === 'ar' ? 'تسليم فوري' : 'Instant Delivery'));
        const deliveryStr = (p.delivery_type === 'activation')
          ? (currentAppLanguage === 'ar' ? 'تفعيل مخصص' : 'Custom Activation')
          : (currentAppLanguage === 'ar' ? 'تسليم تلقائي' : 'Instant Delivery');

        return `
          <div class="product-row" onclick="openProductDetail(${Number(p.id)})">
            <div class="prod-left">
              <div class="prod-icon">${p.emoji || '⚡'}</div>
              <div class="prod-details">
                <div class="prod-title">${p.name}</div>
                <div class="prod-desc">
                  <span style="${isOutOfStock ? 'color: var(--danger); font-weight:700;' : ''}">${stockStr}</span> ·
                  <span>${deliveryStr}</span>
                </div>
              </div>
            </div>
            <div class="prod-price-box">
              <div class="prod-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
              <div style="display: flex; align-items: center; gap: 4px; margin-top: 2px;">
                <button class="wishlist-btn-card" data-pid="${p.id}" onclick="toggleWishlist(${p.id}, event)">${isFav ? '❤️' : '🤍'}</button>
                <div class="prod-tap-hint">${d.view_details}</div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    // DEDICATED IN-APP PRODUCT DETAIL PAGE
    function openProductDetail(productId) {
      haptic('light');
      selectedProduct = allProducts.find(p => Number(p.id) === Number(productId));
      if (!selectedProduct) return;
      selectedQty = 1;
      appliedCoupon = null;
      document.getElementById('coupon-code-input').value = '';
      document.getElementById('coupon-applied-note').style.display = 'none';

      document.getElementById('prod-hero-icon').innerText = selectedProduct.emoji || '⚡';
      document.getElementById('prod-hero-name').innerText = selectedProduct.name;
      document.getElementById('prod-hero-cat').innerText = selectedProduct.category || 'Digital';

      const rawDesc = (currentAppLanguage === 'ar' && selectedProduct.description_ar)
        ? selectedProduct.description_ar
        : (selectedProduct.description || '');
      document.getElementById('prod-rich-desc').innerHTML = formatRichDescription(rawDesc);

      const isInstant = selectedProduct.delivery_type !== 'activation';
      const isOutOfStock = (selectedProduct.stock !== null && selectedProduct.stock <= 0);

      document.getElementById('prod-delivery-badge').innerText = isInstant
        ? (currentAppLanguage === 'ar' ? '⚡ تسليم تلقائي فوري' : '⚡ Instant Automated Delivery')
        : (currentAppLanguage === 'ar' ? '⏳ تفعيل مخصص' : '⏳ Custom Activation');

      document.getElementById('prod-stock-badge').innerText = isOutOfStock
        ? (currentAppLanguage === 'ar' ? '🔴 نفد المخزون' : '🔴 Out of Stock')
        : (selectedProduct.stock ? `${currentAppLanguage === 'ar' ? '🟢 متوفر' : '🟢 In Stock'} (${selectedProduct.stock})` : (currentAppLanguage === 'ar' ? '⚡ تسليم فوري' : '⚡ Instant Delivery'));

      const restockBox = document.getElementById('restock-alert-box');
      const buyBtn = document.getElementById('btn-inapp-purchase');
      const starsBtn = document.getElementById('btn-stars-purchase');

      if (isOutOfStock) {
        restockBox.style.display = 'block';
        buyBtn.style.display = 'none';
        starsBtn.style.display = 'none';
      } else {
        restockBox.style.display = 'none';
        buyBtn.style.display = 'flex';
        starsBtn.style.display = 'flex';
      }

      updateWishlistUI();
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

    // In-App Coupon Validation
    async function applyCheckoutCoupon() {
      const code = (document.getElementById('coupon-code-input').value || '').trim();
      if (!code || !selectedProduct) return;
      haptic('light');
      const unit = selectedProduct.price || 0.0;
      const subtotal = unit * selectedQty;

      try {
        const res = await fetch('/api/coupon/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: code, subtotal: subtotal })
        });
        const d = await res.json();
        if (d.valid) {
          appliedCoupon = d;
          haptic('success');
          const note = document.getElementById('coupon-applied-note');
          note.innerText = d.message;
          note.style.display = 'block';
          updateDetailPagePrice();
        } else {
          appliedCoupon = null;
          showToast(d.error || (currentAppLanguage === 'ar' ? 'كود الخصم غير صالح' : 'Invalid promo code'));
          document.getElementById('coupon-applied-note').style.display = 'none';
          updateDetailPagePrice();
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'فشل التحقق من كود الخصم' : 'Failed to validate promo code');
      }
    }

    function updateDetailPagePrice() {
      if (!selectedProduct) return;
      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      const sym = selectedProduct.sym || '$';

      let bulkPct = 0;
      if (selectedQty >= 10) bulkPct = 15;
      else if (selectedQty >= 5) bulkPct = 7;

      let vipPct = userData?.vip_discount || 0;
      let totalDiscount = Math.max(bulkPct, vipPct);

      let discountText = '';
      if (totalDiscount > 0) {
        const discVal = total * (totalDiscount / 100);
        total = Math.max(0.01, total - discVal);
        discountText = (currentAppLanguage === 'ar') ? `خصم تلقائي: -${totalDiscount}%!` : `Discount: -${totalDiscount}%!`;
      }

      if (appliedCoupon) {
        const cDisc = appliedCoupon.discount || 0.0;
        total = Math.max(0.01, total - cDisc);
        discountText += (currentAppLanguage === 'ar') ? ` (كوبون: -${cDisc.toFixed(2)}${sym})` : ` (Coupon: -${cDisc.toFixed(2)}${sym})`;
      }

      document.getElementById('prod-discount-tag').innerText = discountText;
      document.getElementById('prod-total-price').innerText = `${total.toFixed(2)}${sym}`;
      document.getElementById('btn-price-tag').innerText = `(${total.toFixed(2)}${sym})`;

      const userBalance = userData?.balance || 0.0;
      const alertBox = document.getElementById('insufficient-funds-alert');
      const buyBtn = document.getElementById('btn-inapp-purchase');
      const d = I18N[currentAppLanguage] || I18N.ar;

      if (userBalance < total) {
        alertBox.style.display = 'block';
        alertBox.innerHTML = (currentAppLanguage === 'ar')
          ? `⚠️ الرصيد المتاح غير كافٍ (تحتاج ${total.toFixed(2)}${sym}، رصيدك $${userBalance.toFixed(2)}).`
          : `⚠️ Insufficient balance (Requires ${total.toFixed(2)}${sym}, available $${userBalance.toFixed(2)}).`;
        buyBtn.innerHTML = `<span>${d.topup_to_continue}</span>`;
        buyBtn.onclick = () => switchTab('wallet');
      } else {
        alertBox.style.display = 'none';
        buyBtn.innerHTML = `<span>${d.buy_now}</span> <span>(${total.toFixed(2)}${sym})</span>`;
        buyBtn.onclick = executeProductBuy;
      }
    }

    // 1-Tap Restock Notification Subscribe
    async function triggerInAppRestockSubscribe() {
      if (!selectedProduct || !userId) return;
      haptic('light');
      try {
        const res = await fetch('/api/restock/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, product_id: selectedProduct.id })
        });
        const d = await res.json();
        if (d.status === 'success') {
          haptic('success');
          showToast('🔔 ' + (currentAppLanguage === 'ar' ? d.message : 'Subscribed to restock alerts!'));
        } else {
          showToast(currentAppLanguage === 'ar' ? 'تعذر الاشتراك في التنبيه' : 'Failed to subscribe to alert');
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'خطأ في إرسال طلب التنبيه' : 'Network error subscribing');
      }
    }

    // 1-Tap Product Sharing (Telegram Link & Stories)
    function shareCurrentProduct() {
      if (!selectedProduct) return;
      haptic('light');
      const botUser = userData?.bot_username || 'demo_aiogramshopbot';
      const shareUrl = `https://t.me/${botUser}?start=prod_${selectedProduct.id}_ref_${userId}`;
      const shareText = (currentAppLanguage === 'ar')
        ? `تسوق ${selectedProduct.name} الآن بأفضل سعر على GH Store!`
        : `Shop ${selectedProduct.name} now at best prices on GH Store!`;

      if (tg?.shareToStory) {
        tg.shareToStory({
          media_url: selectedProduct.image_url || 'https://bot.gh-store.me/static/banner.png',
          text: shareText,
          widget_link: { url: shareUrl, name: "🛍️ GH Store" }
        });
        return;
      }

      const tgShareLink = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
      if (tg?.openTelegramLink) tg.openTelegramLink(tgShareLink);
      else window.open(tgShareLink, '_blank');
    }

    // Add to Home Screen (Bot API 8.0)
    function promptAddToHomeScreen() {
      haptic('pop');
      if (tg?.addToHomeScreen) {
        tg.addToHomeScreen();
      } else {
        showToast(currentAppLanguage === 'ar' ? 'انقر على القائمة بالأعلى (⋮) واختر "إضافة إلى الشاشة الرئيسية"' : 'Tap menu (⋮) and select "Add to Home Screen"');
      }
    }

    function checkHomeScreenCapability() {
      if (tg?.checkHomeScreenStatus) {
        tg.checkHomeScreenStatus((status) => {
          const banner = document.getElementById('home-screen-banner');
          if (banner && status === 'missed') {
            banner.style.display = 'flex';
          }
        });
      }
    }

    // IN-APP CHECKOUT (POST /api/buy)
    async function executeProductBuy() {
      if (!selectedProduct || !userId) {
        showToast(currentAppLanguage === 'ar' ? 'يرجى فتح المتجر من داخل تيليجرام' : 'Please open store inside Telegram');
        return;
      }

      const unit = selectedProduct.price || 0.0;
      let total = unit * selectedQty;
      if (total >= 50.0 && tg?.BiometricManager?.isBiometricAvailable) {
        tg.BiometricManager.authenticate({ reason: `Confirm order $${total.toFixed(2)}` }, (success) => {
          if (success) processOrderPlacement();
          else showToast(currentAppLanguage === 'ar' ? 'تم إلغاء التحقق الحيوي' : 'Biometric cancelled');
        });
        return;
      }

      processOrderPlacement();
    }

    async function processOrderPlacement() {
      haptic('light');
      const buyBtn = document.getElementById('btn-inapp-purchase');
      buyBtn.disabled = true;
      buyBtn.innerHTML = `<span>${currentAppLanguage === 'ar' ? '⏳ جاري معالجة الطلب...' : '⏳ Processing Order...'}</span>`;

      const payload = {
        tg_id: userId,
        product_id: selectedProduct.id,
        quantity: selectedQty
      };
      if (appliedCoupon?.code) payload.coupon_code = appliedCoupon.code;

      try {
        const res = await fetch('/api/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await res.json();
        buyBtn.disabled = false;

        if (d.status === 'success') {
          fireConfetti();
          haptic('success');

          if (userData) {
            userData.balance = Math.max(0, userData.balance - d.total_paid);
            updateBalancePills();
            try { localStorage.setItem('ghstore_user_cache', JSON.stringify(userData)); } catch (e) {}
          }

          document.getElementById('success-meta-sub').innerText = (currentAppLanguage === 'ar')
            ? `طلب #${d.order_id} · ${d.product_name} (${d.quantity}×)`
            : `Order #${d.order_id} · ${d.product_name} (${d.quantity}×)`;
          const keysBox = document.getElementById('success-delivered-keys');
          keysBox.innerHTML = renderStructuredCredentials(d.goods);

          document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
          document.getElementById('view-order-success').classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل إتمام الطلب.' : 'Order failed.'));
          updateDetailPagePrice();
        }
      } catch (e) {
        buyBtn.disabled = false;
        haptic('error');
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال. يرجى إعادة المحاولة.' : 'Connection error. Please retry.');
        updateDetailPagePrice();
      }
    }

    // Direct Telegram Stars Invoice (openInvoice)
    async function executeStarsDirectBuy() {
      if (!selectedProduct || !userId) return;
      haptic('light');
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
              showToast(currentAppLanguage === 'ar' ? 'تم الدفع بنجاح عبر نجوم تيليجرام!' : 'Paid successfully with Telegram Stars!');
              switchTab('orders');
            } else if (status === 'failed') {
              showToast(currentAppLanguage === 'ar' ? 'فشلت عملية الدفع بالنجوم' : 'Stars payment failed');
            }
          });
        } else {
          showToast(currentAppLanguage === 'ar' ? 'تعذر فتح فاتورة النجوم' : 'Failed to open Stars invoice');
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'خطأ في شبكة الفواتير' : 'Invoice network error');
      }
    }

    // Recharge Flow
    function selectRechargeMethod(method) {
      haptic('pop');
      selectedRechargeMethod = method;
      ['stars', 'crypto', 'sam'].forEach(m => {
        const card = document.getElementById('method-card-' + m);
        if (card) card.classList.toggle('active', m === method);
      });
      updateRechargeButtonText();
    }

    function selectTopupAmount(amt) {
      haptic('light');
      selectedRechargeAmount = parseFloat(amt);
      const input = document.getElementById('custom-topup-input');
      if (input) input.value = amt.toFixed(2);
      updateAmountChipsUI();
      updateRechargeButtonText();
    }

    function onCustomAmountInput() {
      const input = document.getElementById('custom-topup-input');
      const val = parseFloat(input?.value);
      if (!isNaN(val) && val > 0) {
        selectedRechargeAmount = val;
      }
      updateAmountChipsUI();
      updateRechargeButtonText();
    }

    function updateAmountChipsUI() {
      [1, 5, 10, 25, 50, 100].forEach(a => {
        const chip = document.getElementById('chip-amt-' + a);
        if (chip) chip.classList.toggle('active', Math.abs(selectedRechargeAmount - a) < 0.001);
      });
    }

    function updateRechargeButtonText() {
      const btn = document.getElementById('btn-execute-recharge');
      if (!btn) return;
      let methodName = "نجوم تيليجرام";
      if (selectedRechargeMethod === 'crypto') {
        methodName = (currentAppLanguage === 'ar') ? "العملات الرقمية" : "Crypto";
      } else if (selectedRechargeMethod === 'sam') {
        methodName = (currentAppLanguage === 'ar') ? "سيرياتيل كاش" : "SAM Cash";
      } else {
        methodName = (currentAppLanguage === 'ar') ? "نجوم تيليجرام" : "Telegram Stars";
      }

      const amtStr = selectedRechargeAmount ? selectedRechargeAmount.toFixed(2) : "10.00";
      if (currentAppLanguage === 'ar') {
        btn.innerHTML = `<span>⚡</span> <span>شحن ${amtStr}$ عبر ${methodName}</span>`;
      } else {
        btn.innerHTML = `<span>⚡</span> <span>Recharge $${amtStr} via ${methodName}</span>`;
      }
    }

    async function executeSelectedRecharge() {
      if (!userId) {
        showToast(currentAppLanguage === 'ar' ? 'يرجى فتح المتجر من داخل تيليجرام' : 'Please open store inside Telegram');
        return;
      }
      if (!selectedRechargeAmount || selectedRechargeAmount < 1.0) {
        showToast(currentAppLanguage === 'ar' ? 'الحد الأدنى للشحن هو 1$' : 'Minimum recharge amount is $1');
        return;
      }
      haptic('light');

      const btn = document.getElementById('btn-execute-recharge');
      btn.disabled = true;
      const loadingText = (currentAppLanguage === 'ar') ? '⏳ جاري تجهيز الفاتورة...' : '⏳ Generating invoice...';
      btn.innerHTML = `<span>${loadingText}</span>`;

      try {
        const res = await fetch('/api/invoice/topup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            amount: selectedRechargeAmount,
            method: selectedRechargeMethod
          })
        });
        const d = await res.json();
        btn.disabled = false;
        updateRechargeButtonText();

        if (d.type === 'stars' && d.invoice_link) {
          tg.openInvoice(d.invoice_link, (status) => {
            if (status === 'paid') {
              fireConfetti();
              haptic('success');
              showToast(currentAppLanguage === 'ar' ? `تم شحن +$${selectedRechargeAmount.toFixed(2)} بنجاح!` : `+$${selectedRechargeAmount.toFixed(2)} Credited!`);
              loadUserData();
            } else if (status === 'failed') {
              showToast(currentAppLanguage === 'ar' ? 'فشلت عملية الدفع' : 'Payment failed');
            }
          });
        } else if (d.type === 'url' && d.url) {
          tg.openLink(d.url);
          showToast(currentAppLanguage === 'ar' ? 'تم فتح صفحة الدفع. سيتم شحن الرصيد تلقائياً فور التأكيد!' : 'Payment link opened. Balance credits on confirmation!');
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'تعذر إنشاء فاتورة الشحن' : 'Failed to create invoice'));
        }
      } catch (e) {
        btn.disabled = false;
        updateRechargeButtonText();
        showToast(currentAppLanguage === 'ar' ? 'خطأ في شبكة الشحن' : 'Recharge network error');
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
          showToast(d.message || (currentAppLanguage === 'ar' ? 'تم شحن الكوبون!' : 'Voucher redeemed!'));
          document.getElementById('voucher-code-input').value = '';
          loadUserData();
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'كود الهدية غير صالح' : 'Invalid voucher'));
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'فشلت عملية شحن الكوبون' : 'Failed to redeem voucher');
      }
    }

    // User Profile, Settings & Referral Data Loading
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
        try { localStorage.setItem('ghstore_user_cache', JSON.stringify(d)); } catch (e) {}
        updateBalancePills();

        // Profile Picture
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

        // Profile Display Name & Prominent @username
        const displayName = tgUser?.first_name ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : (d.username ? '@' + d.username : (currentAppLanguage === 'ar' ? 'العميل' : 'Customer'));
        document.getElementById('user-name-title').innerText = displayName;

        const handleBox = document.getElementById('user-handle-title');
        if (d.username) {
          handleBox.innerText = `@${d.username}`;
          handleBox.style.display = 'block';
        } else {
          handleBox.style.display = 'none';
        }

        document.getElementById('user-tg-num').innerText = 'ID: ' + d.telegram_id;

        // Profile VIP Badge: ONLY display if a real discount is applied (>0% and not Standard)
        const vipBox = document.getElementById('user-vip-pill-box');
        const topVipTag = document.getElementById('top-vip-tag');
        const hasVipDiscount = d.vip_discount > 0 && d.vip_tier && d.vip_tier !== 'Standard';

        if (hasVipDiscount) {
          vipBox.innerHTML = `<span class="vip-tag">${d.vip_tier} (${currentAppLanguage === 'ar' ? 'خصم' : 'Discount'} ${d.vip_discount}%)</span>`;
          vipBox.style.display = 'block';
          topVipTag.innerText = d.vip_tier;
          topVipTag.style.display = 'inline-block';
        } else {
          vipBox.innerHTML = '';
          vipBox.style.display = 'none';
          topVipTag.style.display = 'none';
        }

        // VIP Progress Bar
        const spent = d.total_spent || 0.0;
        let nextTarget = 100.0;
        let nextLabel = (currentAppLanguage === 'ar') ? "Silver VIP (خصم 3%)" : "Silver VIP (3% off)";
        if (spent >= 500) {
          nextTarget = 1000.0;
          nextLabel = (currentAppLanguage === 'ar') ? "Platinum VIP (خصم 10%)" : "Platinum VIP (10% off)";
        } else if (spent >= 100) {
          nextTarget = 500.0;
          nextLabel = (currentAppLanguage === 'ar') ? "Gold VIP (خصم 7%)" : "Gold VIP (7% off)";
        }
        const pct = Math.min(100, Math.round((spent / nextTarget) * 100));
        document.getElementById('next-vip-rank').innerText = nextLabel;
        document.getElementById('vip-progress-num').innerText = `${pct}% ($${spent.toFixed(0)} / $${nextTarget.toFixed(0)})`;
        document.getElementById('vip-progress-fill').style.width = `${pct}%`;

        // Referral Stats & Breakdown
        const refLink = `https://t.me/${d.bot_username}?start=${d.referral_code || ''}`;
        document.getElementById('referral-link-display').innerText = refLink;
        document.getElementById('referral-count-val').innerText = d.referrals_count || 0;
        document.getElementById('referral-earned-val').innerText = `$${(d.referrals_total_earned || 0.0).toFixed(2)}`;

        renderReferralsBreakdown(d.referrals_breakdown || [], d.referrals_total_earned || 0.0, d.referrals_count || 0);

        // Currency Chips
        document.querySelectorAll('#currency-picker-chips .filter-chip').forEach(el => {
          el.classList.toggle('active', el.innerText.includes(d.currency_preference));
        });

        // Set Language if user has not set an explicit local override
        if (!localStorage.getItem('ghstore_lang') && d.language) {
          applyLanguage(d.language);
        }

        renderOrders(d.orders || []);
      } catch (e) {
        renderEmptyOrders();
      }
    }

    // Render Referred Friends & Commission Breakdown in Settings
    function renderReferralsBreakdown(breakdown, totalEarned, count) {
      const container = document.getElementById('referrals-breakdown-list');
      if (!container) return;
      const d = I18N[currentAppLanguage] || I18N.ar;

      if (!breakdown || !breakdown.length) {
        container.innerHTML = `
          <div style="text-align: center; padding: 16px; background: var(--input-bg); border-radius: 12px; color: var(--hint); font-size: 12px;">
            ${currentAppLanguage === 'ar' ? 'لم تقم بدعوة أصدقاء بعد. شارك رابطك واكسب 0.2% عمولة أرباح فورية من كل عملية شراء!' : 'No referred friends yet. Share your link and earn 0.2% profit margin commission on every order!'}
          </div>
        `;
        return;
      }

      container.innerHTML = breakdown.map(r => `
        <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <div>
            <div style="font-size: 13px; font-weight: 700; color: var(--text);">${r.user_display}</div>
            <div style="font-size: 11px; color: var(--hint); margin-top: 1px;">
              ${r.registered_at ? r.registered_at + ' · ' : ''}${r.orders_count} ${d.orders_word}
            </div>
          </div>
          <div style="text-align: end;">
            <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); color: var(--success); font-size: 12px; font-weight: 800; padding: 3px 8px; border-radius: 8px;">
              +$${r.earned.toFixed(2)}
            </span>
          </div>
        </div>
      `).join('');
    }

    function updateBalancePills() {
      if (!userData) return;
      document.getElementById('top-balance-str').innerText = userData.display_balance || `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-hero').innerText = `$${userData.balance.toFixed(2)}`;
      document.getElementById('wallet-balance-approx').innerText = userData.currency_preference !== 'USD'
        ? `≈ ${userData.display_balance}`
        : (currentAppLanguage === 'ar' ? 'جاهز للشراء الفوري' : 'Ready for instant purchases');

      const topVipTag = document.getElementById('top-vip-tag');
      if (userData.vip_discount > 0 && userData.vip_tier && userData.vip_tier !== 'Standard') {
        topVipTag.innerText = userData.vip_tier;
        topVipTag.style.display = 'inline-block';
      } else {
        topVipTag.style.display = 'none';
      }
    }

    function renderEmptyOrders() {
      const container = document.getElementById('orders-container-box');
      if (!container) return;
      const d = I18N[currentAppLanguage] || I18N.ar;
      container.innerHTML = `
        <div style="text-align: center; padding: 40px 16px; color: var(--hint);">
          <div style="font-size: 40px; margin-bottom: 8px;">📦</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 4px;">${d.orders_empty_title}</div>
          <p style="font-size: 13px; margin-bottom: 16px;">${d.orders_empty_sub}</p>
          <button class="btn-action-primary" onclick="switchTab('store')" style="width: auto; padding: 0 24px; margin: 0 auto; height: 42px;">${d.browse_store}</button>
        </div>
      `;
    }

    function renderOrders(orders) {
      const container = document.getElementById('orders-container-box');
      if (!container) return;
      if (!orders.length) {
        renderEmptyOrders();
        return;
      }
      const d = I18N[currentAppLanguage] || I18N.ar;
      container.innerHTML = orders.map(o => `
        <div class="inset-card" style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="font-size: 15px;">#${o.id} · ${o.created_at || ''}</strong>
            <span class="pill-badge" style="background: ${o.status.includes('completed') ? 'rgba(16,185,129,0.2); color:#10b981' : o.status.includes('fail') ? 'rgba(239,68,68,0.2); color:#ef4444' : 'rgba(245,158,11,0.2); color:#f59e0b'}; font-size:11px;">${o.status}</span>
          </div>
          <div style="font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 2px;">${o.products}</div>
          <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-bottom: 8px;">${d.total}: ${o.total.toFixed(2)}${o.sym}</div>

          <!-- Timeline Stepper -->
          <div class="timeline-box">
            <div class="timeline-track"></div>
            <div class="timeline-node">
              <div class="node-circle done">✓</div>
              <div class="node-label">${d.step_placed}</div>
            </div>
            <div class="timeline-node">
              <div class="node-circle ${o.status.includes('completed') ? 'done' : 'active'}">${o.status.includes('completed') ? '✓' : '●'}</div>
              <div class="node-label">${d.step_processing}</div>
            </div>
            <div class="timeline-node">
              <div class="node-circle ${o.status.includes('completed') ? 'done' : ''}">${o.status.includes('completed') ? '✓' : '○'}</div>
              <div class="node-label">${d.step_delivered}</div>
            </div>
          </div>

          <!-- Structured Credential Splitter -->
          ${renderStructuredCredentials(o.goods)}

          <div style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px;">
            ${o.warranty_days && !o.warranty_claimed && o.status === 'completed' ? `
              <button class="btn-action-secondary" onclick="claimOrderWarranty(${o.id})">${d.claim_warranty}</button>
            ` : ''}
          </div>
        </div>
      `).join('');
    }

    function copyCredText(text) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(currentAppLanguage === 'ar' ? 'تم النسخ بنجاح!' : 'Copied successfully!');
      });
    }

    function copyReferralLink() {
      const link = document.getElementById('referral-link-display').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast(currentAppLanguage === 'ar' ? 'تم نسخ رابط الإحالة!' : 'Referral link copied!');
      });
    }

    async function selectDisplayCurrency(code) {
      haptic('light');
      document.querySelectorAll('#currency-picker-chips .filter-chip').forEach(el => {
        el.classList.toggle('active', el.innerText.includes(code));
      });
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, currency: code })
        });
        showToast(currentAppLanguage === 'ar' ? `تم تعيين عملة العرض إلى ${code}` : `Display currency set to ${code}`);
        loadUserData();
      }
    }

    async function changeStoreLanguage(code) {
      haptic('pop');
      applyLanguage(code);
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, language: code })
        });
        showToast(code === 'ar' ? 'تم تحديث لغة التطبيق إلى العربية!' : 'App language set to English!');
        loadUserData();
      }
    }

    async function claimOrderWarranty(orderId) {
      haptic('light');
      try {
        const res = await fetch('/api/warranty/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, order_id: orderId })
        });
        const d = await res.json();
        if (d.status === 'success') {
          fireConfetti();
          showToast(currentAppLanguage === 'ar' ? 'تم اعتماد الضمان وتسليم البيانات الجديدة!' : 'Warranty approved & new credentials delivered!');
          loadUserData();
        } else {
          showToast(currentAppLanguage === 'ar' ? 'تم إرسال طلب الضمان لمراجعة الدعم' : 'Warranty claim submitted for review');
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'فشل تقديم طلب الضمان' : 'Failed to submit warranty claim');
      }
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

    // Initial Startup Sequence: Theme -> i18n -> SWR Cache -> Network
    initAppTheme();
    const initialLang = localStorage.getItem('ghstore_lang') || 'ar';
    applyLanguage(initialLang);
    initWishlist();
    loadFromCache();
    fetchCatalogData();
    loadUserData();
    initSSE();
    checkHomeScreenCapability();
  </script>
</body>
</html>
"""
