"""Telegram Mini App (TMA) Mobile-First Storefront.

Features:
- Admin Control Center: Financial overview, live exchange rate manager (SYP to USD), referral commission manager, user search with live balance adjustment & ban controls, live orders manager with refunds, and coupon manager.
- Live Inline Product & Category Editing: Admins can edit product names, prices, categories, stock, and category visuals/titles live directly in the storefront with instant DB sync.
- Clean Product Rows: Completely removed emojis and repetitive 'Instant Delivery' labels from product cards.
- Stock Priority Sorting: In-stock products always appear first in every catalog and filtered view.
- Vector SVG Favorites: Replaced emoji hearts with sleek, animated vector SVG outline/fill heart icons.
- Syriatel Cash SYP Denomination: Highlights that Syriatel Cash receives Syrian Pounds (SYP only) and displays converted live approximate SYP amounts.
- Fixed Product Exploration Navigation: Preserves stable DOM structure in buy buttons, eliminates null reference crashes, and enables native Telegram BackButton support.
- Separated Customer-Facing Payment Methods: Sham Cash, Syriatel Cash, Crypto, and Telegram Stars with ZERO backend/API names exposed.
- External Browser Payment Sheet: Allows customers to open invoice URLs directly in their mobile browser or copy direct payment links.
- Category Cards: Picture & Title Visual Grid by default, with instant toggle to List view.
- Profile & Settings: Hides VIP badge if Standard (0%), shows only if real discount applied; prominently displays @username.
- SWR (Stale-While-Revalidate) instant 0ms launch cache via localStorage.
- Dark & Light Mode Appearance Toggle with persistent storage and Telegram theme syncing.
- Full Bidirectional Arabic & English i18n Overhaul (RTL/LTR, dynamic catalog & product re-rendering, directional arrows).
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
      --safe-top: 0px;
      --safe-bottom: env(safe-area-inset-bottom, 16px);
      --safe-left: 0px;
      --safe-right: 0px;
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
      overscroll-behavior-y: none;
      touch-action: manipulation;
      transition: background-color 0.25s, color 0.25s;
    }

    /* Sleek Top Navigation Bar (Telegram Native Chrome Harmony) */
    .top-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      background: var(--header-bg);
      border-bottom: 1px solid var(--border);
      padding-top: max(var(--safe-top, 0px), env(safe-area-inset-top, 0px), 10px);
      padding-bottom: 10px;
      padding-left: max(var(--safe-left, 0px), 16px);
      padding-right: max(var(--safe-right, 0px), 16px);
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 52px;
      transition: background-color 0.25s, border-color 0.25s;
    }
    .header-brand {
      display: flex;
      align-items: center;
      gap: 9px;
      cursor: pointer;
    }
    .store-logo-wrapper {
      width: 32px;
      height: 32px;
      border-radius: 9px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid var(--border);
      flex-shrink: 0;
    }
    .store-logo-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .store-logo-fallback {
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .store-brand-info {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .store-title {
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -0.3px;
      color: var(--text);
    }
    .vip-tag {
      background: rgba(245, 158, 11, 0.18);
      color: var(--warning);
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
    }
    .header-right-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .header-balance-pill {
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 20px;
      padding: 5px 11px;
      display: flex;
      align-items: center;
      gap: 5px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
      color: var(--accent);
      transition: transform 0.15s, background-color 0.2s;
    }
    .header-balance-pill:active { transform: scale(0.96); }
    .bal-pill-plus { font-size: 10px; opacity: 0.85; }
    .header-user-badge {
      cursor: pointer;
      display: flex;
      align-items: center;
    }
    .avatar-img {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      object-fit: cover;
      border: 1.5px solid var(--accent);
    }
    .avatar-fallback {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #6366f1);
      color: white;
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Floating Cart Badge Capsule */
    .floating-cart-badge {
      position: fixed;
      bottom: calc(var(--nav-height) + var(--safe-bottom) + 14px);
      left: 16px;
      z-index: 90;
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: #ffffff;
      padding: 9px 15px;
      border-radius: 28px;
      display: flex;
      align-items: center;
      gap: 7px;
      cursor: pointer;
      box-shadow: 0 8px 24px rgba(2, 132, 199, 0.45);
      font-size: 13px;
      font-weight: 800;
      transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s;
      animation: cartPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    [dir="ltr"] .floating-cart-badge { left: auto; right: 16px; }
    .floating-cart-badge:active { transform: scale(0.94); }
    .cart-badge-sep { opacity: 0.6; font-size: 11px; }
    @keyframes cartPop { from { transform: scale(0.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }

    /* Trending Searches Bar */
    .trending-searches-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      padding: 2px 0 8px 0;
      scrollbar-width: none;
    }
    .trending-searches-bar::-webkit-scrollbar { display: none; }
    .trending-label {
      font-size: 11px;
      font-weight: 700;
      color: var(--hint);
      white-space: nowrap;
    }
    .trending-chip {
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 14px;
      padding: 3px 9px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.15s, border-color 0.15s;
    }
    .trending-chip:active { background: rgba(56, 189, 248, 0.15); border-color: var(--accent); }

    /* Cart Drawer Items */
    .cart-item-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .cart-item-left {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      min-width: 0;
    }
    .cart-item-icon {
      font-size: 20px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .cart-item-name {
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .cart-item-price {
      font-size: 12px;
      color: var(--accent);
      font-weight: 700;
    }
    .cart-stepper {
      display: flex;
      align-items: center;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .cart-stepper button {
      background: transparent;
      border: none;
      color: var(--text);
      padding: 4px 8px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }
    .cart-stepper span {
      padding: 0 6px;
      font-size: 12px;
      font-weight: 800;
      color: var(--accent);
      font-family: monospace;
    }
    .cart-del-btn {
      background: transparent;
      border: none;
      color: #ef4444;
      font-size: 14px;
      cursor: pointer;
      padding: 4px;
      margin-left: 6px;
    }
    [dir="ltr"] .cart-del-btn { margin-left: 0; margin-right: 6px; }

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
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s;
    }
    .filter-chip.active {
      background: rgba(56, 189, 248, 0.18);
      color: var(--accent);
      border-color: var(--accent);
    }

    /* Vector SVG Favorite Icon Styling */
    .fav-btn-action {
      background: transparent;
      border: none;
      cursor: pointer;
      padding: 5px;
      line-height: 1;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background-color 0.15s;
    }
    .fav-btn-action:active { background: rgba(239, 68, 68, 0.15); }
    .fav-icon-svg {
      fill: none;
      stroke: var(--hint);
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
      transition: all 0.22s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .fav-icon-svg.active {
      fill: #ef4444;
      stroke: #ef4444;
      filter: drop-shadow(0 0 6px rgba(239, 68, 68, 0.45));
      transform: scale(1.12);
    }

    /* Structured Spec Pills in Product Cards (No Emojis) */
    .prod-specs-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 5px;
      margin-top: 5px;
    }
    .spec-pill {
      display: inline-flex;
      align-items: center;
      font-size: 10.5px;
      font-weight: 700;
      padding: 2.5px 8px;
      border-radius: 6px;
      white-space: nowrap;
      line-height: 1.25;
      letter-spacing: -0.1px;
    }
    .spec-pill.in-stock {
      background: rgba(16, 185, 129, 0.12);
      color: #10b981;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .spec-pill.stock-out {
      background: rgba(239, 68, 68, 0.12);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .spec-pill.duration {
      background: rgba(56, 189, 248, 0.12);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.28);
    }
    .spec-pill.warranty {
      background: rgba(16, 185, 129, 0.12);
      color: #10b981;
      border: 1px solid rgba(16, 185, 129, 0.28);
    }
    .spec-pill.warranty-none {
      background: rgba(239, 68, 68, 0.12);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.28);
    }
    .spec-pill.type {
      background: rgba(168, 85, 247, 0.12);
      color: #c084fc;
      border: 1px solid rgba(168, 85, 247, 0.28);
    }

    /* Admin Inline Edit Badge Buttons */
    .admin-edit-badge-btn {
      background: rgba(56, 189, 248, 0.18);
      border: 1px solid rgba(56, 189, 248, 0.4);
      color: var(--accent);
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
      cursor: pointer;
      margin-inline-start: 6px;
      transition: background 0.15s;
    }
    .admin-edit-badge-btn:active { background: rgba(56, 189, 248, 0.35); }

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

    /* Picture & Title Visual Grid Layout */
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
      background: linear-gradient(180deg, rgba(9, 14, 26, 0.2) 0%, rgba(9, 14, 26, 0.5) 45%, rgba(9, 14, 26, 0.94) 100%);
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
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.95);
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

    /* Product Row Item (Clean, No Emojis, No Box Icon) */
    .product-row {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 16px;
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
      flex-direction: column;
      flex: 1;
      overflow: hidden;
    }
    .prod-title {
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 1px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: var(--text);
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

    /* IN-APP DEDICATED PRODUCT DETAIL PAGE (Clean Hero, No Emojis) */
    .page-hero {
      text-align: center;
      padding: 24px 16px 18px 16px;
      background: radial-gradient(circle at center, rgba(56, 189, 248, 0.12), transparent 70%);
      border-radius: 18px;
      margin-bottom: 14px;
      position: relative;
    }
    .hero-name {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.3px;
      margin-bottom: 6px;
      color: var(--text);
    }
    .hero-cat {
      font-size: 12px;
      color: var(--accent);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
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
      gap: 6px;
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

    /* RECHARGE METHODS (Zero backend API names exposed) */
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
    .method-icon {
      font-size: 26px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .method-brand-img {
      width: 32px;
      height: 32px;
      object-fit: contain;
      flex-shrink: 0;
      display: block;
      border-radius: 6px;
    }
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

    /* Skeleton Loaders & Shimmer */
    .skeleton-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-bottom: 16px;
    }
    .skeleton-box {
      height: 130px;
      border-radius: 18px;
      background: var(--card);
      border: 1px solid var(--border);
      position: relative;
      overflow: hidden;
    }
    .skeleton-box::after {
      content: '';
      position: absolute;
      inset: 0;
      transform: translateX(-100%);
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
      animation: shimmer 1.4s infinite;
    }
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

    /* Admin Management Drawers & Styles */
    .admin-stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-bottom: 12px;
    }
    .admin-stat-card {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
      text-align: center;
    }
    .admin-stat-num {
      font-size: 18px;
      font-weight: 800;
      color: var(--accent);
      margin-top: 2px;
    }
    .admin-stat-label {
      font-size: 11px;
      color: var(--hint);
      font-weight: 600;
    }
    .admin-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.78);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      z-index: 220;
      display: none;
      align-items: flex-end;
      justify-content: center;
    }
    .admin-modal-sheet {
      width: 100%;
      max-width: 500px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px 24px 0 0;
      padding: 20px;
      max-height: 85vh;
      overflow-y: auto;
      box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.6);
      animation: slideUp 0.22s ease-out;
    }
    .admin-input-row {
      display: flex;
      flex-direction: column;
      gap: 4px;
      margin-bottom: 12px;
    }
    .admin-input-label {
      font-size: 11px;
      color: var(--hint);
      font-weight: 700;
    }
    .admin-text-input {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 13px;
      color: var(--text);
      outline: none;
    }
    .admin-text-input:focus { border-color: var(--accent); }
  </style>
</head>
<body>
  <canvas id="confetti-canvas"></canvas>
  <div class="toast-pill" id="toast">تم النسخ!</div>

  <!-- ADMIN PRODUCT EDITOR MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-product-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">تعديل بيانات المنتج كمسؤول</h3>
        <button class="circle-icon-btn" onclick="closeAdminProductModal()">✕</button>
      </div>
      <input type="hidden" id="admin-edit-prod-id">
      <div class="admin-input-row">
        <label class="admin-input-label">الاسم المخصص المعروض (Custom Display Title)</label>
        <input type="text" class="admin-text-input" id="admin-edit-prod-name" placeholder="e.g. Gemini Activation">
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">التصنيف (Category)</label>
        <input type="text" class="admin-text-input" id="admin-edit-prod-cat" placeholder="AI & Chatbots">
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="admin-input-row">
          <label class="admin-input-label">سعر البيع بالدولار (Sell Price USD)</label>
          <input type="number" step="any" class="admin-text-input" id="admin-edit-prod-price">
        </div>
        <div class="admin-input-row">
          <label class="admin-input-label">المخزون (Stock - فارغ للتسليم الآلي)</label>
          <input type="number" class="admin-text-input" id="admin-edit-prod-stock" placeholder="فارغ = آلي">
        </div>
      </div>
      <div style="display: flex; align-items: center; justify-content: space-between; margin: 10px 0 16px 0; background: var(--input-bg); padding: 10px 14px; border-radius: 10px;">
        <span style="font-size: 13px; font-weight: 700;">إخفاء المنتج من المتجر (Hidden)</span>
        <input type="checkbox" id="admin-edit-prod-hidden" style="width: 18px; height: 18px; accent-color: var(--accent);">
      </div>
      <button class="btn-action-primary" onclick="submitAdminProductUpdate()">حفظ التعديلات في قاعدة البيانات</button>
    </div>
  </div>

  <!-- ADMIN CATEGORY EDITOR MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-category-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">تعديل التصنيف كمسؤول</h3>
        <button class="circle-icon-btn" onclick="closeAdminCategoryModal()">✕</button>
      </div>
      <input type="hidden" id="admin-edit-cat-id">
      <div class="admin-input-row">
        <label class="admin-input-label">الاسم بالعربية (Arabic Title)</label>
        <input type="text" class="admin-text-input" id="admin-edit-cat-ar" placeholder="الذكاء الاصطناعي">
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">الاسم بالإنجليزية (English Title)</label>
        <input type="text" class="admin-text-input" id="admin-edit-cat-en" placeholder="AI & Chatbots">
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">رابط صورة التصنيف (Image URL)</label>
        <input type="text" class="admin-text-input" id="admin-edit-cat-img" placeholder="https://...">
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">الوصف المختصر بالعربية</label>
        <input type="text" class="admin-text-input" id="admin-edit-cat-prev-ar" placeholder="كلود · شات جي بي تي">
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">الوصف المختصر بالإنجليزية</label>
        <input type="text" class="admin-text-input" id="admin-edit-cat-prev-en" placeholder="Claude · ChatGPT">
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="admin-input-row">
          <label class="admin-input-label">ترتيب العرض (Sort Order)</label>
          <input type="number" class="admin-text-input" id="admin-edit-cat-sort" value="1">
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; background: var(--input-bg); padding: 6px 12px; border-radius: 10px; margin-top: 18px;">
          <span style="font-size: 11px; font-weight: 700;">إخفاء التصنيف</span>
          <input type="checkbox" id="admin-edit-cat-hidden" style="width: 16px; height: 16px; accent-color: var(--accent);">
        </div>
      </div>
      <button class="btn-action-primary" onclick="submitAdminCategoryUpdate()" style="margin-top: 10px;">حفظ بيانات التصنيف في قاعدة البيانات</button>
    </div>
  </div>

  <!-- ADMIN SEND MESSAGE TO USER MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-message-user-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">💬 إرسال إشعار للمستخدم</h3>
        <button class="circle-icon-btn" onclick="closeAdminMessageModal()">✕</button>
      </div>
      <input type="hidden" id="admin-msg-target-tgid">
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 14px; font-weight: 700; color: var(--text);" id="admin-msg-target-name">@username</div>
        <div style="font-size: 11px; color: var(--hint); font-family: monospace;" id="admin-msg-target-id">ID: 00000000</div>
      </div>
      <div class="admin-input-row">
        <label class="admin-input-label">نص الرسالة / الإشعار المرسل من البوت</label>
        <textarea class="admin-text-input" id="admin-msg-text-input" rows="4" placeholder="اكتب رسالتك للمستخدم هنا... (سيتم إرسالها فورياً عبر رسالة خاصة من البوت)"></textarea>
      </div>
      <div style="display: flex; gap: 8px; margin-top: 14px;">
        <button class="btn-action-secondary" onclick="closeAdminMessageModal()" style="flex: 1; height: 44px;">إلغاء</button>
        <button class="btn-action-primary" id="btn-submit-send-user-msg" onclick="submitAdminSendMessage()" style="flex: 2; height: 44px;">إرسال الرسالة 🚀</button>
      </div>
    </div>
  </div>

  <!-- ADMIN ORDERS MONITOR MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-orders-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">مراقبة طلبات المتجر المباشرة</h3>
        <button class="circle-icon-btn" onclick="closeAdminOrdersModal()">✕</button>
      </div>
      <div style="display: flex; gap: 6px; margin-bottom: 12px; overflow-x: auto;">
        <button class="filter-chip active" id="admin-ord-tab-all" onclick="loadAdminOrders('all')">الكل</button>
        <button class="filter-chip" id="admin-ord-tab-pending" onclick="loadAdminOrders('pending_fulfillment')">قيد التنفيذ</button>
        <button class="filter-chip" id="admin-ord-tab-completed" onclick="loadAdminOrders('completed')">مكتمل</button>
        <button class="filter-chip" id="admin-ord-tab-refunded" onclick="loadAdminOrders('refunded')">مسترد</button>
      </div>
      <div id="admin-orders-results-list" style="display: flex; flex-direction: column; gap: 8px; max-height: 55vh; overflow-y: auto;"></div>
    </div>
  </div>

  <!-- ADMIN COUPONS MANAGER MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-coupons-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">إدارة كوبونات الخصم</h3>
        <button class="circle-icon-btn" onclick="closeAdminCouponsModal()">✕</button>
      </div>
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 8px;">إنشاء كود خصم جديد</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 6px;">
          <input type="text" class="admin-text-input" id="admin-new-coupon-code" placeholder="CODE (e.g. VIP20)" style="text-transform: uppercase;">
          <input type="number" step="any" class="admin-text-input" id="admin-new-coupon-val" placeholder="القيمة (e.g. 20)">
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px;">
          <select class="admin-text-input" id="admin-new-coupon-type">
            <option value="percent">نسبة مئوية (%)</option>
            <option value="currency">مبلغ ثابت ($)</option>
          </select>
          <input type="number" class="admin-text-input" id="admin-new-coupon-limit" placeholder="حد الاستخدام (100)">
        </div>
        <button class="btn-action-primary" onclick="submitAdminCreateCoupon()" style="height: 40px; font-size: 13px;">حفظ وتفعيل الكود</button>
      </div>
      <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">الكوبونات الحالية في النظام</div>
      <div id="admin-coupons-list" style="display: flex; flex-direction: column; gap: 6px; max-height: 35vh; overflow-y: auto;"></div>
    </div>
  </div>

  <!-- ADMIN USER BALANCE ADJUSTMENT MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-balance-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">💰 تعديل رصيد المستخدم</h3>
        <button class="circle-icon-btn" onclick="closeAdminBalanceModal()">✕</button>
      </div>
      <input type="hidden" id="admin-bal-target-tgid">
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 14px; font-weight: 700;" id="admin-bal-user-name">@username</div>
        <div style="font-size: 11px; color: var(--hint); font-family: monospace; margin-top: 2px;" id="admin-bal-user-id">ID: 000000</div>
        <div style="font-size: 12px; margin-top: 6px; border-top: 1px solid var(--border); padding-top: 6px;">
          الرصيد الحالي: <strong style="color: var(--accent); font-size: 14px;" id="admin-bal-user-curr">$0.00</strong>
        </div>
      </div>

      <!-- Action Type Toggle -->
      <div class="theme-segmented-control" style="margin-bottom: 12px;">
        <div class="theme-segment-btn active" id="admin-bal-btn-add" onclick="setAdminBalanceAction('add')">
          <span>➕</span> <span>إضافة رصيد (Add)</span>
        </div>
        <div class="theme-segment-btn" id="admin-bal-btn-deduct" onclick="setAdminBalanceAction('deduct')">
          <span>➖</span> <span>خصم رصيد (Deduct)</span>
        </div>
      </div>

      <!-- Preset Amount Chips -->
      <div class="quick-amounts-grid" style="margin-bottom: 10px;">
        <div class="quick-amount-chip" onclick="setAdminBalAmount(5)">$5</div>
        <div class="quick-amount-chip active" id="admin-bal-chip-10" onclick="setAdminBalAmount(10)">$10</div>
        <div class="quick-amount-chip" onclick="setAdminBalAmount(25)">$25</div>
        <div class="quick-amount-chip" onclick="setAdminBalAmount(50)">$50</div>
        <div class="quick-amount-chip" onclick="setAdminBalAmount(100)">$100</div>
        <div class="quick-amount-chip" onclick="setAdminBalAmount(250)">$250</div>
      </div>

      <!-- Custom Amount Input -->
      <div class="custom-amount-box" style="margin-bottom: 16px;">
        <span style="font-size: 16px; font-weight: 800; color: var(--accent);">$</span>
        <input type="number" id="admin-bal-amount-input" step="any" placeholder="10.00" value="10.00">
        <span style="font-size: 12px; color: var(--hint);">USD</span>
      </div>

      <button class="btn-action-primary" id="btn-submit-adjust-balance" onclick="submitAdminAdjustBalance()">
        تأكيد إضافة الرصيد (+)
      </button>
    </div>
  </div>

  <!-- ADMIN USER CUSTOM DISCOUNT MODAL SHEET -->
  <div class="admin-modal-overlay" id="admin-discount-modal">
    <div class="admin-modal-sheet">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="font-size: 17px; font-weight: 800;">🏷️ تخصيص نسبة خصم VIP</h3>
        <button class="circle-icon-btn" onclick="closeAdminDiscountModal()">✕</button>
      </div>
      <input type="hidden" id="admin-disc-target-tgid">
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 14px; font-weight: 700;" id="admin-disc-user-name">@username</div>
        <div style="font-size: 11px; color: var(--hint); font-family: monospace; margin-top: 2px;" id="admin-disc-user-id">ID: 000000</div>
      </div>

      <div class="quick-amounts-grid" style="margin-bottom: 10px;">
        <div class="quick-amount-chip" onclick="setAdminDiscVal(3)">3%</div>
        <div class="quick-amount-chip" onclick="setAdminDiscVal(5)">5%</div>
        <div class="quick-amount-chip" onclick="setAdminDiscVal(7)">7%</div>
        <div class="quick-amount-chip" onclick="setAdminDiscVal(10)">10%</div>
        <div class="quick-amount-chip" onclick="setAdminDiscVal(15)">15%</div>
        <div class="quick-amount-chip" onclick="setAdminDiscVal(20)">20%</div>
      </div>

      <div class="admin-input-row" style="margin-bottom: 16px;">
        <label class="admin-input-label">نسبة الخصم المخصصة لهذا المستخدم (0-100)%</label>
        <input type="number" step="any" class="admin-text-input" id="admin-disc-input" placeholder="e.g. 15">
      </div>

      <div style="display: flex; gap: 8px;">
        <button class="btn-action-secondary" onclick="clearAdminDiscount()" style="flex: 1; height: 44px;">إلغاء الخصم</button>
        <button class="btn-action-primary" onclick="submitAdminDiscount()" style="flex: 2; height: 44px;">حفظ الخصم</button>
      </div>
    </div>
  </div>

  <!-- MULTI-ITEM CART DRAWER MODAL SHEET -->
  <div class="admin-modal-overlay" id="cart-drawer-sheet">
    <div class="admin-modal-sheet" style="max-height: 85vh; display: flex; flex-direction: column;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 20px;">🛒</span>
          <h3 style="font-size: 17px; font-weight: 800;" id="cart-drawer-title">سلة المشتريات</h3>
          <span class="pill-badge" id="cart-drawer-count-badge" style="background: rgba(56,189,248,0.2); color: var(--accent);">0</span>
        </div>
        <button class="circle-icon-btn" onclick="closeCartDrawer()">✕</button>
      </div>

      <div id="cart-drawer-items-list" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; max-height: 40vh;">
        <!-- Dynamic Cart Items -->
      </div>

      <div id="cart-empty-message" style="text-align: center; padding: 24px 0; color: var(--hint); display: none;">
        السلة فارغة حالياً. تصفح المنتجات وأضف ما ترغب به!
      </div>

      <!-- Cart Summary & Checkout Box -->
      <div id="cart-checkout-box" style="border-top: 1px solid var(--border); padding-top: 12px;">
        <div style="display: flex; justify-content: space-between; font-size: 13px; color: var(--hint); margin-bottom: 4px;">
          <span id="cart-summary-subtotal-label">المجموع الجزئي:</span>
          <span id="cart-summary-subtotal">$0.00</span>
        </div>
        <div id="cart-summary-disc-row" style="display: none; justify-content: space-between; font-size: 13px; color: var(--success); margin-bottom: 4px;">
          <span id="cart-summary-disc-label">خصم الرتبة:</span>
          <span id="cart-summary-discount">-$0.00</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 800; margin-bottom: 12px;">
          <span id="cart-summary-total-label">الإجمالي النهائي:</span>
          <span style="color: var(--accent);" id="cart-summary-total">$0.00</span>
        </div>

        <div style="display: flex; gap: 8px;">
          <button class="btn-action-secondary" onclick="clearEntireCart()" style="flex: 1; height: 46px;" id="cart-btn-clear">إفراغ</button>
          <button class="btn-action-primary" id="btn-cart-checkout" onclick="executeCartCheckout()" style="flex: 3; height: 46px;">
            <span id="cart-btn-checkout-label">تأكيد شراء السلة</span>
          </button>
        </div>
      </div>
    </div>
  </div>


  <!-- Top Sleek Navigation Bar (Native Chrome Space) -->
  <header class="top-header">
    <div class="header-brand" onclick="switchTab('store')">
      <div class="store-logo-wrapper">
        <img id="top-store-logo" class="store-logo-img" src="" alt="GH Store" style="display: none;" onerror="this.style.display='none'; document.getElementById('top-store-fallback').style.display='flex';">
        <div id="top-store-fallback" class="store-logo-fallback">🛍️</div>
      </div>
      <div class="store-brand-info">
        <span class="store-title">GH Store</span>
        <span class="vip-tag" id="top-vip-tag" style="display: none;">VIP</span>
      </div>
    </div>
    <div class="header-right-actions">
      <div class="header-balance-pill" onclick="switchTab('wallet')" title="المحفظة">
        <span class="bal-pill-amount" id="top-balance-str">$0.00</span>
        <span class="bal-pill-plus">➕</span>
      </div>
      <div class="header-user-badge" onclick="switchTab('settings')" title="الإعدادات">
        <div id="top-avatar-box">
          <div class="avatar-fallback" id="top-avatar-initial">U</div>
        </div>
      </div>
    </div>
  </header>

  <!-- TAB 1: STORE VIEW -->
  <main id="view-store" class="tab-view active">
    <!-- Home Screen Pin Banner (Bot API 8.0) -->
    <div class="pwa-banner" id="home-screen-banner" style="display: none;">
      <div style="font-size: 13px;">
        <strong id="pwa-banner-title">أضف التطبيق للشاشة الرئيسية</strong>
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

    <!-- Trending Searches Bar -->
    <div class="trending-searches-bar" id="trending-searches-bar">
      <span class="trending-label">🔥 الأكثر بحثاً:</span>
      <span class="trending-chip" onclick="applySearchQuery('ChatGPT')">🤖 ChatGPT</span>
      <span class="trending-chip" onclick="applySearchQuery('Claude')">⚡ Claude</span>
      <span class="trending-chip" onclick="applySearchQuery('Gemini')">🧠 Gemini</span>
      <span class="trending-chip" onclick="applySearchQuery('Peacock')">🍿 Peacock</span>
      <span class="trending-chip" onclick="applySearchQuery('Windows')">💻 Windows</span>
      <span class="trending-chip" onclick="applySearchQuery('Canva')">🎨 Canva</span>
    </div>
    <!-- Quick Filters & Sorting -->
    <div class="filter-chips-row" id="quick-filters-row">
      <div class="filter-chip active" id="filter-all" onclick="applyCatalogFilter('all')">الكل</div>
      <div class="filter-chip" id="filter-wishlist" onclick="applyCatalogFilter('wishlist')">
        <svg class="fav-icon-svg active" viewBox="0 0 24 24" width="14" height="14" style="filter:none;"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
        <span id="label-filter-wishlist">المفضلة</span>
      </div>
      <div class="filter-chip" id="filter-stock" onclick="applyCatalogFilter('stock')">متوفر فقط</div>
      <div class="filter-chip" id="filter-instant" onclick="applyCatalogFilter('instant')">تسليم فوري</div>
      <div class="filter-chip" id="filter-lowprice" onclick="applyCatalogFilter('lowprice')">الأقل سعراً</div>
    </div>

    <!-- Promotional Hero Banner -->
    <div class="hero-banner">
      <div class="banner-badge" id="banner-badge-text">تحديثات المتجر</div>
      <div class="banner-title" id="banner-title-text">اشتراكات كلود وجيميني متوفرة فورياً</div>
      <div class="banner-sub" id="banner-sub-text">تسليم تلقائي فوري للمفاتيح والحسابات على مدار الساعة</div>
    </div>

    <!-- Mode A: Catalogs Cards (Homepage Collections with Grid/List Toggle) -->
    <div id="catalogs-collection-mode">
      <div class="section-header-flex">
        <div class="section-title" id="title-collections">التصنيفات المميزة</div>
        <div class="view-toggle-capsule">
          <button class="view-toggle-btn active" id="btn-view-grid" onclick="setCatalogViewMode('grid')">
            <span id="label-view-grid">شبكة</span>
          </button>
          <button class="view-toggle-btn" id="btn-view-list" onclick="setCatalogViewMode('list')">
            <span id="label-view-list">قائمة</span>
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
  <!-- Floating Cart Capsule Badge -->
  <div class="floating-cart-badge" id="floating-cart-badge" onclick="openCartDrawer()" style="display: none;">
    <span class="cart-badge-icon">🛒</span>
    <span class="cart-badge-count" id="cart-badge-count">0</span>
    <span class="cart-badge-sep">·</span>
    <span class="cart-badge-total" id="cart-badge-total">$0.00</span>
  </div>


  <!-- DEDICATED IN-APP PRODUCT DETAIL PAGE (Clean Hero, No Emojis) -->
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
        <button class="circle-icon-btn" id="btn-detail-wishlist" onclick="toggleCurrentProductWishlist()" title="المفضلة">
          <svg class="fav-icon-svg" viewBox="0 0 24 24" width="18" height="18"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
        </button>
        <button class="circle-icon-btn" onclick="shareCurrentProduct()" title="مشاركة">↗️</button>
      </div>
      <h2 class="hero-name" id="prod-hero-name">اسم المنتج</h2>
      <div class="hero-cat" id="prod-hero-cat">حساب رقمي</div>
    </div>

    <!-- Structured Spec Badges in Product Detail -->
    <div class="badges-flex" id="detail-badges-box">
      <div class="pill-badge" id="prod-delivery-badge">تسليم تلقائي فوري</div>
      <div class="pill-badge" id="prod-stock-badge">متوفر</div>
      <div class="pill-badge" id="prod-dur-badge" style="display: none;"></div>
      <div class="pill-badge" id="prod-war-badge" style="display: none;"></div>
      <div class="pill-badge" id="prod-typ-badge" style="display: none;"></div>
    </div>

    <!-- Admin Quick Edit Button on Product Detail (Only for Admins) -->
    <div id="admin-detail-edit-container" style="display: none; margin-bottom: 10px;">
      <button class="btn-action-secondary" onclick="openAdminProductEditor(selectedProduct?.id)" style="width: 100%; height: 40px;">
        تعديل بيانات المنتج كمسؤول (Admin Edit)
      </button>
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
        الرصيد المتاح غير كافٍ لهذا الطلب.
      </div>

      <!-- Out-of-Stock Restock Alert Button -->
      <div id="restock-alert-box" style="display: none; margin-bottom: 10px;">
        <button class="btn-action-warning" onclick="triggerInAppRestockSubscribe()">
          <span id="btn-restock-text">نبهني فور التوفر</span>
        </button>
      </div>

      <!-- In-App Purchase & Add to Cart Buttons Row -->
      <div style="display: flex; gap: 8px; margin-bottom: 8px;" id="product-action-buttons-row">
        <button class="btn-action-primary" id="btn-inapp-purchase" onclick="executeProductBuy()" style="flex: 2;">
          <span id="btn-buy-action-label">شراء فوري</span>
          <span id="btn-price-tag">($0.00)</span>
        </button>
        <button class="btn-action-secondary" id="btn-add-to-cart" onclick="addToCartCurrentProduct()" style="flex: 1; height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;" title="إضافة للسلة">
          <span style="font-size: 16px;">🛒</span>
          <span id="btn-add-cart-text" style="font-size: 11px; font-weight: 700;">أضف للسلة</span>
        </button>
      </div>
      <button class="btn-stars-checkout" id="btn-stars-purchase" onclick="executeStarsDirectBuy()">
        <span id="btn-stars-action-label">الدفع عبر نجوم تيليجرام</span>
      </button>
    </div>
  </section>

  <!-- IN-APP ORDER SUCCESS VIEW -->
  <section id="view-order-success" class="tab-view">
    <div style="text-align: center; padding: 24px 0 16px 0;">
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
      <button class="btn-action-secondary" id="btn-success-view-orders" onclick="switchTab('orders')" style="flex: 1; height: 48px;">عرض في طلباتي</button>
      <button class="btn-action-primary" id="btn-success-continue" onclick="switchTab('store')" style="flex: 1; height: 48px;">متابعة التسوق</button>
    </div>
  </section>
  <!-- DEDICATED IN-APP INVOICE VIEW -->
  <section id="view-invoice" class="tab-view">
    <div class="subview-header">
      <button class="btn-back-catalog" onclick="closeInvoicePage()">
        <span id="icon-back-invoice">→</span>
        <span id="btn-back-invoice">العودة للمحفظة</span>
      </button>
      <span style="font-size: 13px; color: var(--accent); font-weight: 700;">فاتورة شحن الرصيد</span>
    </div>

    <!-- Invoice Card Container -->
    <div class="inset-card" style="margin-top: 10px; border-color: rgba(56, 189, 248, 0.35);">
      <!-- Status Badge & ID -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <span class="pill-badge" id="invoice-status-badge" style="background: rgba(245, 158, 11, 0.18); color: #f59e0b; font-size: 12px; padding: 4px 10px; display: inline-flex; align-items: center; gap: 6px;">
          <span style="width: 8px; height: 8px; border-radius: 50%; background: #f59e0b; display: inline-block;"></span>
          <span id="invoice-status-text">بانتظار التحويل / الدفع</span>
        </span>
        <span style="font-size: 12px; color: var(--hint); font-family: monospace;" id="invoice-id-display">#INV-0000</span>
      </div>

      <!-- Payment Method Row -->
      <div style="display: flex; align-items: center; gap: 12px; background: var(--input-bg); border: 1px solid var(--border); border-radius: 14px; padding: 12px; margin-bottom: 14px;">
        <div id="invoice-method-icon-box" style="width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          💳
        </div>
        <div>
          <div style="font-size: 15px; font-weight: 800; color: var(--text);" id="invoice-method-name">وسيلة الدفع</div>
          <div style="font-size: 11px; color: var(--hint);" id="invoice-method-sub">دفع مباشر وسريع</div>
        </div>
      </div>

      <!-- Amount Box -->
      <div style="text-align: center; padding: 18px; background: rgba(56, 189, 248, 0.08); border: 1px dashed rgba(56, 189, 248, 0.35); border-radius: 16px; margin-bottom: 16px;">
        <div style="font-size: 12px; color: var(--hint); margin-bottom: 4px;">المبلغ المطلوب سداده</div>
        <div style="font-size: 28px; font-weight: 800; color: var(--accent);" id="invoice-amount-usd">$10.00</div>
        <div style="font-size: 13px; color: var(--text); font-weight: 700; margin-top: 3px;" id="invoice-amount-local"></div>
      </div>

      <!-- Instructions Note -->
      <div style="font-size: 12px; color: var(--hint); line-height: 1.6; margin-bottom: 18px;" id="invoice-instructions-text">
        انقر على <b>فتح بوابة الدفع</b> للمتابعة في صفحة السداد الرسمية. بعد إتمام التحويل، اضغط على زر <b>التحقق من وصول الدفع</b> بالأسفل لتحديث رصيدك فورياً.
      </div>

      <!-- Action Buttons Stack -->
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <!-- 1. Open Payment Gateway -->
        <button class="btn-action-primary" id="btn-open-payment-gateway" onclick="openActiveInvoiceGateway()" style="height: 48px;">
          <span>🌐 فتح بوابة الدفع المباشرة</span>
        </button>

        <!-- 2. Check Payment Status Button -->
        <button class="btn-action-warning" id="btn-check-invoice-status" onclick="checkActiveInvoiceStatus()" style="height: 48px; background: linear-gradient(135deg, #10b981, #059669); color: white;">
          <span id="label-check-invoice">🔄 التحقق من وصول الدفع وتحديث الرصيد</span>
        </button>

        <!-- 3. Secondary Actions -->
        <div style="display: flex; gap: 8px;">
          <button class="btn-action-secondary" onclick="copyActiveInvoiceLink()" style="flex: 1; height: 42px; font-size: 12px;">
            <span>📋 نسخ الرابط</span>
          </button>
          <button class="btn-action-secondary" onclick="closeInvoicePage()" style="flex: 1; height: 42px; font-size: 12px;">
            <span>✕ العودة للمحفظة</span>
          </button>
        </div>
      </div>
    </div>
  </section>

  <!-- DEDICATED IN-APP ADMIN USERS MANAGEMENT VIEW -->
  <section id="view-admin-users" class="tab-view">
    <div class="subview-header">
      <button class="btn-back-catalog" onclick="closeAdminUsersPage()">
        <span>→</span>
        <span>العودة للإعدادات</span>
      </button>
      <span style="font-size: 13px; color: var(--accent); font-weight: 700;">إدارة المستخدمين والأرصدة</span>
    </div>

    <!-- Search & Quick Filters Bar -->
    <div class="inset-card" style="margin-top: 10px; padding: 12px; margin-bottom: 12px;">
      <div class="search-box" style="margin-bottom: 8px;">
        <span class="search-icon">🔍</span>
        <input type="text" id="admin-user-search-input" placeholder="ابحث برقم ID أو اسم المستخدم @username..." oninput="debounceAdminUserSearch()">
        <span class="clear-search" id="admin-user-clear-btn" onclick="clearAdminUserSearch()" style="display: none;">✕</span>
      </div>
      <div class="filter-chips-row" id="admin-user-filter-chips">
        <div class="filter-chip active" id="admin-ufilter-all" onclick="setAdminUserFilter('all')">الكل</div>
        <div class="filter-chip" id="admin-ufilter-balance" onclick="setAdminUserFilter('balance')">💰 لديهم رصيد</div>
        <div class="filter-chip" id="admin-ufilter-vip" onclick="setAdminUserFilter('vip')">🎖️ VIP فقط</div>
        <div class="filter-chip" id="admin-ufilter-banned" onclick="setAdminUserFilter('banned')">🚫 المحظورون فقط</div>
      </div>
    </div>

    <!-- Users List Container -->
    <div id="admin-users-results-list" style="display: flex; flex-direction: column; gap: 10px;">
      <div style="text-align: center; padding: 30px; color: var(--hint);">جاري جلب قائمة المستخدمين...</div>
    </div>
  </section>

  <!-- DEDICATED IN-APP STUCK ORDERS & MONEY MANAGEMENT VIEW -->
  <section id="view-admin-stuck" class="tab-view">
    <div class="subview-header">
      <button class="btn-back-catalog" onclick="closeAdminStuckOrdersPage()">
        <span>→</span>
        <span>العودة للإعدادات</span>
      </button>
      <span style="font-size: 13px; color: #f59e0b; font-weight: 700;">الطلبات والعمليات المعلقة</span>
    </div>

    <div class="inset-card" style="margin-top: 10px; padding: 12px; margin-bottom: 12px; background: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.3);">
      <div style="font-size: 12px; font-weight: 700; color: #f59e0b; margin-bottom: 4px;">⚠️ مركز متابعة العمليات العالقة والمبالغ المعلقة</div>
      <div style="font-size: 11px; color: var(--hint); line-height: 1.5;">
        تظهر هنا الطلبات قيد التفعيل والمبالغ المعلقة التي تحتاج لمتابعة أو استرداد يدوي للعملاء.
      </div>
    </div>

    <!-- Stuck Orders List Container -->
    <div id="admin-stuck-orders-list" style="display: flex; flex-direction: column; gap: 10px;">
      <div style="text-align: center; padding: 30px; color: var(--hint);">جاري تحميل العمليات المعلقة...</div>
    </div>
  </section>

  <!-- DEDICATED IN-APP ONE-TIME CONFIGURATION VIEW -->
  <section id="view-admin-config" class="tab-view">
    <div class="subview-header">
      <button class="btn-back-catalog" onclick="closeAdminConfigPage()">
        <span>→</span>
        <span>العودة للإعدادات</span>
      </button>
      <span style="font-size: 13px; color: var(--accent); font-weight: 700;">إعدادات التهيئة لمرة واحدة</span>
    </div>

    <!-- Explanatory Banner -->
    <div class="inset-card" style="margin-top: 10px; padding: 14px; margin-bottom: 12px; background: rgba(56, 189, 248, 0.08); border-color: rgba(56, 189, 248, 0.3);">
      <div style="font-size: 13px; font-weight: 800; color: var(--accent); margin-bottom: 4px;">
        ⚙️ إعدادات ومفاتيح الربط الأساسية (One-Time Config)
      </div>
      <div style="font-size: 11px; color: var(--hint); line-height: 1.5;">
        الحقول مقفلة ومحمية تلقائياً لمنع أي تعديل بالخطأ. اضغط على أيقونة القلم <b>✏️</b> بجانب أي إعداد لفتح التعديل عليه وحفظه.
      </div>
    </div>

    <!-- Config Items List -->
    <div id="admin-config-items-list" style="display: flex; flex-direction: column; gap: 10px;">
      <div style="text-align: center; padding: 30px; color: var(--hint);">جاري تحميل الإعدادات...</div>
    </div>
  </section>


  <!-- TAB 2: PROCESSES & ACTIVITY VIEW (ORDERS & RECHARGES) -->
  <main id="view-orders" class="tab-view">
    <div class="section-title" id="title-orders-history">العمليات والسجل</div>
    <div class="filter-chips-row" id="activity-filter-row" style="margin-bottom: 14px;">
      <div class="filter-chip active" id="act-filter-all" onclick="filterActivityView('all')">الكل (All)</div>
      <div class="filter-chip" id="act-filter-orders" onclick="filterActivityView('orders')">🛍️ مشتريات المنتجات</div>
      <div class="filter-chip" id="act-filter-recharges" onclick="filterActivityView('recharges')">💳 شحن الرصيد</div>
    </div>
    <div id="orders-container-box">
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    </div>
  </main>

  <!-- TAB 3: WALLET VIEW (4 USER-FACING RECHARGE METHODS) -->
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

    <!-- Step 1: Choose Payment Method (4 Distinct Options, Zero API Names) -->
    <div class="section-title" id="recharge-method-title">1. اختر وسيلة الشحن</div>
    <div class="recharge-methods-grid">
      <!-- 1. Telegram Stars -->
      <div class="recharge-method-card active" id="method-card-stars" onclick="selectRechargeMethod('stars')">
        <div class="method-card-left">
          <span class="method-icon">⭐</span>
          <div>
            <div class="method-name" id="label-method-stars-name">نجوم تيليجرام (Telegram Stars)</div>
            <div class="method-sub" id="label-method-stars-sub">دفع فوري عبر Apple Pay أو Google Pay أو النجوم</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>

      <!-- 2. Cryptocurrency -->
      <div class="recharge-method-card" id="method-card-crypto" onclick="selectRechargeMethod('crypto')">
        <div class="method-card-left">
          <span class="method-icon">🪙</span>
          <div>
            <div class="method-name" id="label-method-crypto-name">العملات الرقمية (Crypto)</div>
            <div class="method-sub" id="label-method-crypto-sub">USDT (TRC20/BEP20), Bitcoin, Solana, TON</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>

      <!-- 3. Sham Cash -->
      <div class="recharge-method-card" id="method-card-shamcash" onclick="selectRechargeMethod('shamcash')">
        <div class="method-card-left">
          <img src="https://shamcash.sy/_next/static/media/logo.5be69def.svg" class="method-brand-img" alt="Sham Cash" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
          <span class="method-icon" style="display: none;">💳</span>
          <div>
            <div class="method-name" id="label-method-shamcash-name">شام كاش (Sham Cash)</div>
            <div class="method-sub" id="label-method-shamcash-sub">دفع مباشر وسريع عبر بنك شام كاش</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>

      <!-- 4. Syriatel Cash (SYP only) -->
      <div class="recharge-method-card" id="method-card-syriatelcash" onclick="selectRechargeMethod('syriatelcash')">
        <div class="method-card-left">
          <img src="https://www.syriatel.sy/assets/img/logo.png" class="method-brand-img" alt="Syriatel Cash" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
          <span class="method-icon" style="display: none;">📱</span>
          <div>
            <div class="method-name" id="label-method-syriatelcash-name">سيرياتيل كاش (Syriatel Cash)</div>
            <div class="method-sub" id="label-method-syriatelcash-sub">دفع مباشر بالليرة السورية (SYP فقط)</div>
          </div>
        </div>
        <div class="method-radio-check">✓</div>
      </div>
    </div>
    <!-- ShamCash Currency Toggle (USD vs SYP) -->
    <div id="shamcash-currency-box" style="display: none; background: var(--input-bg); border: 1px solid var(--border); border-radius: 14px; padding: 12px; margin-bottom: 12px;">
      <div style="font-size: 12px; font-weight: 700; color: var(--hint); margin-bottom: 8px;" id="label-sham-curr-title">عملة السداد في شام كاش (Payment Currency):</div>
      <div style="display: flex; gap: 8px;">
        <button class="filter-chip active" id="btn-sham-curr-usd" onclick="setShamCurrency('USD')" style="flex: 1; text-align: center; height: 38px;">
          💵 بالدولار (USD)
        </button>
        <button class="filter-chip" id="btn-sham-curr-syp" onclick="setShamCurrency('SYP')" style="flex: 1; text-align: center; height: 38px; display: inline-flex; align-items: center; justify-content: center; gap: 6px;">
          <svg class="syria-flag-svg" viewBox="0 0 30 20" width="18" height="12" style="border-radius: 2px; vertical-align: middle; display: inline-block; box-shadow: 0 0 1px rgba(0,0,0,0.5); flex-shrink: 0;" xmlns="http://www.w3.org/2000/svg">
            <rect width="30" height="6.67" y="0" fill="#007A3D"/>
            <rect width="30" height="6.67" y="6.67" fill="#FFFFFF"/>
            <rect width="30" height="6.67" y="13.33" fill="#000000"/>
            <polygon points="8.5,7.7 9.1,9.2 10.7,9.2 9.4,10.2 9.9,11.7 8.5,10.7 7.1,11.7 7.6,10.2 6.3,9.2 7.9,9.2" fill="#CE1126"/>
            <polygon points="15,7.7 15.6,9.2 17.2,9.2 15.9,10.2 16.4,11.7 15,10.7 13.6,11.7 14.1,10.2 12.8,9.2 14.4,9.2" fill="#CE1126"/>
            <polygon points="21.5,7.7 22.1,9.2 23.7,9.2 22.4,10.2 22.9,11.7 21.5,10.7 20.1,11.7 20.6,10.2 19.3,9.2 20.9,9.2" fill="#CE1126"/>
          </svg>
          <span>بالليرة السورية (SYP)</span>
        </button>
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
      <span id="recharge-btn-text">شحن 10.00$ عبر نجوم تيليجرام</span>
    </button>

    <!-- Redeem Gift Voucher -->
    <div class="section-title" id="voucher-section-title" style="margin-top: 24px;">شحن عبر كرت هدية (Voucher)</div>
    <div class="inset-card" style="display: flex; gap: 8px; padding: 10px;">
      <input type="text" id="voucher-code-input" placeholder="GH-XXXX-YYYY" style="flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; font-family: monospace; text-transform: uppercase;">
      <button class="btn-action-secondary" id="voucher-redeem-btn" onclick="submitVoucherRedeem()" style="padding: 6px 14px;">شحن</button>
    </div>
  </main>

  <!-- TAB 4: SETTINGS VIEW (PROFILE, ADMIN CONTROL CENTER, THEME, LANGUAGE, REFERRALS) -->
  <main id="view-settings" class="tab-view">
    <!-- User Profile Header -->
    <div class="inset-card" style="display: flex; align-items: center; gap: 14px;">
      <div id="settings-avatar-box">
        <div class="avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">U</div>
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: 17px; font-weight: 800;" id="user-name-title">العميل</div>
        <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-top: 1px; display: none;" id="user-handle-title">@username</div>
        <div style="display: flex; align-items: center; gap: 6px; margin-top: 3px;">
          <span style="font-size: 11px; color: var(--hint); font-family: monospace;" id="user-tg-num">ID: 000000000</span>
          <button onclick="copyUserId()" class="btn-copy-mini" style="padding: 1px 6px; font-size: 9px;">نسخ ID</button>
        </div>
        <!-- VIP badge is displayed ONLY if user has a real discount applied (>0%) -->
        <div style="margin-top: 5px; display: none;" id="user-vip-pill-box"></div>
      </div>
    </div>

    <!-- User Financial Overview (Balance & Spent) -->
    <div class="inset-card" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 12px; margin-top: -2px;">
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center;">
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 2px;">الرصيد المتاح</div>
        <div style="font-size: 18px; font-weight: 800; color: var(--accent);" id="settings-card-balance">$0.00</div>
      </div>
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center;">
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 2px;">إجمالي المشتريات</div>
        <div style="font-size: 18px; font-weight: 800; color: var(--text);" id="settings-card-spent">$0.00</div>
      </div>
    </div>

    <!-- ============================================== -->
    <!-- 👑 ADMIN CONTROL CENTER (Visible ONLY to Admins) -->
    <!-- ============================================== -->
    <div class="inset-card" id="admin-control-center-card" style="display: none; border-color: rgba(56, 189, 248, 0.4); background: linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(99, 102, 241, 0.08));">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div style="font-size: 15px; font-weight: 800; color: var(--accent);">👑 لوحة تحكم المشرف (Admin Center)</div>
        <span class="pill-badge" style="background: rgba(16, 185, 129, 0.2); color: var(--success); font-size: 10px;">مسؤول معتمد</span>
      </div>

      <!-- Financial Store Health Overview -->
      <div class="admin-stats-grid">
        <div class="admin-stat-card">
          <div class="admin-stat-label">إجمالي المبيعات</div>
          <div class="admin-stat-num" id="admin-stat-revenue">$0.00</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-label">أرصدة العملاء الحالية</div>
          <div class="admin-stat-num" id="admin-stat-balances" style="color: #38bdf8;">$0.00</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-label">عدد المستخدمين</div>
          <div class="admin-stat-num" id="admin-stat-users" style="color: #f59e0b;">0</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-label">إجمالي الطلبات</div>
          <div class="admin-stat-num" id="admin-stat-orders" style="color: #c084fc;">0</div>
        </div>
      </div>

      <!-- Live Exchange Rate & Currency Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">💱 سعر صرف الليرة السورية مقابل الدولار (SYP / USD)</div>
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px;">مربوط بقاعدة البيانات ويتم تطبيقه فورياً على الشحن بالليرة السورية</div>
        <div style="display: flex; gap: 8px;">
          <input type="number" class="admin-text-input" id="admin-syp-rate-input" placeholder="e.g. 15000" style="flex: 1; font-family: monospace; font-weight: 700;">
          <button class="btn-action-primary" onclick="submitAdminUpdateSypRate()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">تحديث</button>
        </div>
      </div>

      <!-- Referral Commission Rate Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">🎁 نسبة عمولة الإحالة من أرباح الهامش (%)</div>
        <div style="display: flex; gap: 8px;">
          <input type="number" step="any" class="admin-text-input" id="admin-ref-rate-input" placeholder="0.2" style="flex: 1; font-family: monospace; font-weight: 700;">
          <button class="btn-action-primary" onclick="submitAdminUpdateReferralRate()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">تحديث</button>
        </div>
      </div>
      <!-- Store Brand Logo Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">🖼️ رابط شعار المتجر (Store Logo URL)</div>
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px;">يظهر في أعلى المتجر بجانب الاسم (يدعم PNG و SVG و WebP)</div>
        <div style="display: flex; gap: 8px;">
          <input type="text" class="admin-text-input" id="admin-store-logo-input" placeholder="https://example.com/logo.png" style="flex: 1; font-size: 12px;">
          <button class="btn-action-primary" onclick="submitAdminUpdateStoreLogo()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">حفظ الشعار</button>
        </div>
      </div>
      <!-- Global Profit Margin Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">📈 نسبة هامش الربح العام على المنتجات (%)</div>
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px;">تحدد نسبة ربح المتجر التلقائية على أسعار المورد لجميع المنتجات</div>
        <div style="display: flex; gap: 8px;">
          <input type="number" step="any" class="admin-text-input" id="admin-margin-input" placeholder="20" style="flex: 1; font-family: monospace; font-weight: 700;">
          <button class="btn-action-primary" onclick="submitAdminUpdateMargin()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">تحديث الهامش</button>
        </div>
      </div>

      <!-- Telegram Stars Rate Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">⭐ قيمة النجمة الواحدة مقابل الدولار (Stars / USD Rate)</div>
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px;">افتراضياً: 0.01$ للنجمة الواحدة (100 نجمة = 1$)</div>
        <div style="display: flex; gap: 8px;">
          <input type="number" step="any" class="admin-text-input" id="admin-stars-rate-input" placeholder="0.01" style="flex: 1; font-family: monospace; font-weight: 700;">
          <button class="btn-action-primary" onclick="submitAdminUpdateStarsRate()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">حفظ سعر النجوم</button>
        </div>
      </div>

      <!-- Broadcast Announcement Banner Manager -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">📢 شريط الإعلانات العام في المتجر (Broadcast Banner)</div>
        <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px;">يظهر أعلى الصفحة لجميع الزوار (اتركه فارغاً لإخفائه)</div>
        <div style="display: flex; gap: 8px;">
          <input type="text" class="admin-text-input" id="admin-announcement-input" placeholder="خصم خاص بمناسبة العطلة..." style="flex: 1; font-size: 12px;">
          <button class="btn-action-primary" onclick="submitAdminUpdateAnnouncement()" style="height: 38px; width: auto; padding: 0 16px; font-size: 12px;">نشر الإعلان</button>
        </div>
      </div>

      <!-- Force Supplier Catalog Sync -->
      <div style="margin-bottom: 14px;">
        <button class="btn-action-primary" id="btn-force-sync-catalog" onclick="submitAdminCatalogSync()" style="width: 100%; height: 44px; background: linear-gradient(135deg, #6366f1, #4f46e5); font-size: 13px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 8px;">
          <span>🔄 مزامنة الكتالوج والأسعار من المورد فورياً</span>
        </button>
      </div>

      <!-- Auto-Refund Master Setting -->
      <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div style="font-size: 12px; font-weight: 700;">🔄 نظام الاسترداد التلقائي (Auto-Refund)</div>
          <div style="font-size: 10px; color: var(--hint); margin-top: 2px;">عند التعطيل، يتم استرداد الطلبات المعلقة يدوياً فقط</div>
        </div>
        <button class="admin-edit-badge-btn" id="admin-autorefund-toggle-btn" onclick="submitAdminToggleAutoRefund()" style="font-size: 11px; padding: 5px 12px; color: #f59e0b;">
          معطل (يدوي)
        </button>
      </div>

      <!-- Stuck Orders Center Button -->
      <div style="margin-bottom: 12px;">
        <button class="btn-action-warning" onclick="openAdminStuckOrdersPage()" style="width: 100%; height: 44px; font-size: 13px; background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.4); color: #f59e0b; display: flex; align-items: center; justify-content: center; gap: 8px;">
          <span>⚠️ متابعة الطلبات والعمليات المعلقة (Stuck Orders)</span>
        </button>
      </div>


      <!-- Quick Admin Management Navigation Drawers -->
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px;">
        <button class="btn-action-secondary" onclick="openAdminUsersPage()" style="height: 44px; font-size: 12px;">
          👥 إدارة المستخدمين والأرصدة
        </button>
        <button class="btn-action-secondary" onclick="openAdminOrdersModal()" style="height: 44px; font-size: 12px;">
          📦 مراقبة الطلبات والاسترداد
        </button>
        <button class="btn-action-secondary" onclick="openAdminCouponsModal()" style="height: 44px; font-size: 12px;">
          🏷️ إدارة وإنشاء الكوبونات
        </button>
        <button class="btn-action-secondary" onclick="openFullSqlAdmin()" style="height: 44px; font-size: 12px;">
          🔗 لوحة SQLAdmin الكاملة
        </button>
      </div>
      <!-- Master One-Time System Config Page Button -->
      <div style="margin-top: 8px;">
        <button class="btn-action-primary" onclick="openAdminConfigPage()" style="width: 100%; height: 42px; font-size: 12px; background: linear-gradient(135deg, #0284c7, #2563eb); display: flex; align-items: center; justify-content: center; gap: 6px;">
          <span>⚙️ إعدادات التهيئة ومفاتيح الربط لمرة واحدة (One-Time Setup)</span>
        </button>
      </div>
    </div>

    <!-- Appearance: Dark / Light Mode Toggle -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-theme-title">المظهر / Appearance</div>
      <div class="theme-segmented-control">
        <div class="theme-segment-btn active" id="theme-btn-dark" onclick="setAppTheme('dark')">
          <span id="label-theme-dark">داكن (Dark)</span>
        </div>
        <div class="theme-segment-btn" id="theme-btn-light" onclick="setAppTheme('light')">
          <span id="label-theme-light">فاتح (Light)</span>
        </div>
      </div>
    </div>

    <!-- Install PWA Button -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-install-title">تثبيت التطبيق</div>
      <div style="font-size: 12px; color: var(--hint); margin-bottom: 8px;" id="label-install-desc">
        أضف أيقونة متجر GH Store إلى شاشة هاتفك الرئيسية لتصفح العروض فورياً!
      </div>
      <button class="btn-action-secondary" id="btn-install-app" onclick="promptAddToHomeScreen()" style="width: 100%; height: 42px;">
        إضافة إلى الشاشة الرئيسية
      </button>
    </div>

    <!-- Currency Picker (USD & SYP Only) -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-currency-title">عملة العرض المفضلة (Display Currency)</div>
      <div class="theme-segmented-control" id="currency-picker-chips" style="margin-top: 6px;">
        <div class="theme-segment-btn active" id="curr-chip-usd" onclick="selectDisplayCurrency('USD')">
          <span>💵 الدولار (USD $)</span>
        </div>
        <div class="theme-segment-btn" id="curr-chip-syp" onclick="selectDisplayCurrency('SYP')">
          <svg class="syria-flag-svg" viewBox="0 0 30 20" width="18" height="12" style="border-radius: 2px; vertical-align: middle; display: inline-block; box-shadow: 0 0 1px rgba(0,0,0,0.5); flex-shrink: 0;" xmlns="http://www.w3.org/2000/svg">
            <rect width="30" height="6.67" y="0" fill="#007A3D"/>
            <rect width="30" height="6.67" y="6.67" fill="#FFFFFF"/>
            <rect width="30" height="6.67" y="13.33" fill="#000000"/>
            <polygon points="8.5,7.7 9.1,9.2 10.7,9.2 9.4,10.2 9.9,11.7 8.5,10.7 7.1,11.7 7.6,10.2 6.3,9.2 7.9,9.2" fill="#CE1126"/>
            <polygon points="15,7.7 15.6,9.2 17.2,9.2 15.9,10.2 16.4,11.7 15,10.7 13.6,11.7 14.1,10.2 12.8,9.2 14.4,9.2" fill="#CE1126"/>
            <polygon points="21.5,7.7 22.1,9.2 23.7,9.2 22.4,10.2 22.9,11.7 21.5,10.7 20.1,11.7 20.6,10.2 19.3,9.2 20.9,9.2" fill="#CE1126"/>
          </svg>
          <span>الليرة السورية (SYP ل.س)</span>
        </div>
      </div>
    </div>

    <!-- Language Selector Dropdown -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-lang-title">اللغة / Language</div>
      <div style="margin-top: 6px;">
        <select class="admin-text-input" id="language-select-dropdown" onchange="changeStoreLanguage(this.value)" style="width: 100%; height: 44px; font-size: 14px; font-weight: 700; background: var(--input-bg); border-color: var(--border); color: var(--text); border-radius: 12px; padding: 0 12px; outline: none;">
          <option value="ar">🇸🇦 العربية (Arabic)</option>
          <option value="en">🇬🇧 English</option>
          <option value="de">🇩🇪 Deutsch</option>
          <option value="es">🇪🇸 Español</option>
          <option value="fr">🇫🇷 Français</option>
          <option value="it">🇮🇹 Italiano</option>
          <option value="zh">🇨🇳 中文 (Chinese)</option>
        </select>
      </div>
    </div>
    <!-- Referral Program (Comprehensive Details & Breakdown) -->
    <div class="inset-card">
      <div class="section-title" style="margin-top: 0;" id="label-referral-title">برنامج الإحالة والأرباح</div>
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
        سجل الأصدقاء المدعوين والأرباح
      </div>
      <div id="referrals-breakdown-list" style="display: flex; flex-direction: column; gap: 6px;"></div>
    </div>
    <!-- Direct Customer Support & Official Channels -->
    <div class="inset-card" style="display: flex; flex-direction: column; gap: 8px;">
      <div class="section-title" style="margin-top: 0;">الدعم وقنوات المتجر</div>
      <button class="btn-action-secondary" onclick="openCustomerSupportChat()" style="height: 42px; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 8px;">
        <span>💬 التواصل مع خدمة العملاء والدعم</span>
      </button>
      <button class="btn-action-secondary" onclick="openOfficialChannel()" style="height: 42px; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 8px;">
        <span>📢 قناة العروض والتحديثات الرسمية</span>
      </button>
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
      <span class="liquid-tab-label" id="i18n-tab-orders">العمليات</span>
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
      if (tg.isVersionAtLeast && tg.isVersionAtLeast('7.7')) {
        try { tg.disableVerticalSwipes?.(); } catch (e) {}
      }
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      if (tg.SettingsButton) {
        try {
          tg.SettingsButton.show();
          tg.SettingsButton.onClick(() => switchTab('settings'));
        } catch (e) {}
      }
    }

    function updateSafeAreaInsets() {
      const t = getTg();
      let top = 0;
      let bottom = 0;
      let left = 0;
      let right = 0;

      if (t?.contentSafeAreaInset) {
        top = Math.max(top, t.contentSafeAreaInset.top || 0);
        bottom = Math.max(bottom, t.contentSafeAreaInset.bottom || 0);
        left = Math.max(left, t.contentSafeAreaInset.left || 0);
        right = Math.max(right, t.contentSafeAreaInset.right || 0);
      }
      if (t?.safeAreaInset) {
        top = Math.max(top, t.safeAreaInset.top || 0);
        bottom = Math.max(bottom, t.safeAreaInset.bottom || 0);
        left = Math.max(left, t.safeAreaInset.left || 0);
        right = Math.max(right, t.safeAreaInset.right || 0);
      }

      // In case client is in fullscreen, ensure generous top clearance to avoid notch / 3-dots collision
      if (t?.isFullscreen) {
        top = Math.max(top, 54);
      }

      if (top > 0) document.documentElement.style.setProperty('--safe-top', `${top}px`);
      if (bottom > 0) document.documentElement.style.setProperty('--safe-bottom', `${bottom}px`);
      if (left > 0) document.documentElement.style.setProperty('--safe-left', `${left}px`);
      if (right > 0) document.documentElement.style.setProperty('--safe-right', `${right}px`);
    }

    if (tg) {
      updateSafeAreaInsets();
      if (tg.onEvent) {
        tg.onEvent('safeAreaChanged', updateSafeAreaInsets);
        tg.onEvent('contentSafeAreaChanged', updateSafeAreaInsets);
        tg.onEvent('fullscreenChanged', updateSafeAreaInsets);
        tg.onEvent('viewportChanged', updateSafeAreaInsets);
      }
    }

    // Centralized Navigation Stack for Native Telegram BackButton
    const navStack = [];

    function getTg() {
      return window.Telegram?.WebApp || tg;
    }

    function pushNav(name, onBack) {
      navStack.push({ name, onBack });
      const t = getTg();
      if (t?.BackButton) {
        t.BackButton.show();
        t.BackButton.offClick(handleNativeBack);
        t.BackButton.onClick(handleNativeBack);
      }
    }

    function popNav() {
      if (navStack.length > 0) {
        const item = navStack.pop();
        if (typeof item.onBack === 'function') {
          item.onBack();
        }
      }
      const t = getTg();
      if (navStack.length === 0 && t?.BackButton) {
        t.BackButton.hide();
        t.BackButton.offClick(handleNativeBack);
      }
    }
    function handleNativeBack() {
      haptic('selection');
      popNav();
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

    let cartMap = {};
    let currentStoreLogo = '';

    const SEARCH_ALIASES = {
      'شات': ['chatgpt', 'gpt', 'openai'],
      'جي بي تي': ['chatgpt', 'gpt'],
      'ذكاء': ['ai', 'chatgpt', 'claude', 'gemini'],
      'كلود': ['claude', 'anthropic'],
      'جيميني': ['gemini', 'google'],
      'ويندوز': ['windows', 'microsoft'],
      'اوفيس': ['office', 'microsoft 365', 'family'],
      'بي كوك': ['peacock'],
      'بيكوك': ['peacock'],
      'كانفا': ['canva'],
      'يوتيوب': ['youtube'],
      'سبوتيفاي': ['spotify'],
      'نتفلكس': ['netflix'],
      'في بي ان': ['vpn', 'nordvpn']
    };

    function applyStoreLogo(url) {
      currentStoreLogo = url || '';
      const img = document.getElementById('top-store-logo');
      const fallback = document.getElementById('top-store-fallback');
      const input = document.getElementById('admin-store-logo-input');
      if (input && url) input.value = url;
      if (img && fallback) {
        if (url && url.trim()) {
          img.src = url.trim();
          img.style.display = 'block';
          fallback.style.display = 'none';
        } else {
          img.style.display = 'none';
          fallback.style.display = 'flex';
        }
      }
    }

    async function submitAdminUpdateStoreLogo() {
      const input = document.getElementById('admin-store-logo-input');
      const url = (input?.value || '').trim();
      haptic('light');
      try {
        const res = await fetch('/api/admin/store-logo/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, logo_url: url })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? 'تم تحديث شعار المتجر بنجاح!' : 'Store logo updated successfully!');
          applyStoreLogo(url);
        } else {
          showToast(d.error || 'فشل تحديث الشعار');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    // Cart Management & Cross-Device CloudStorage
    function initCart() {
      try {
        const local = localStorage.getItem('ghstore_cart');
        if (local) cartMap = JSON.parse(local) || {};
      } catch (e) {}
      try {
        if (tg?.CloudStorage) {
          tg.CloudStorage.getItem('ghstore_cart', (err, val) => {
            if (!err && val) {
              try {
                cartMap = JSON.parse(val) || {};
                updateFloatingCartUI();
              } catch (e) {}
            }
          });
        }
      } catch (e) {}
      updateFloatingCartUI();
    }

    function saveCart() {
      try { localStorage.setItem('ghstore_cart', JSON.stringify(cartMap)); } catch (e) {}
      try {
        if (tg?.CloudStorage) {
          tg.CloudStorage.setItem('ghstore_cart', JSON.stringify(cartMap), () => {});
        }
      } catch (e) {}
      updateFloatingCartUI();
    }

    function updateFloatingCartUI() {
      const items = Object.values(cartMap);
      const totalQty = items.reduce((acc, it) => acc + (it.quantity || 1), 0);
      const totalPrice = items.reduce((acc, it) => acc + ((it.price || 0) * (it.quantity || 1)), 0);
      const sym = items[0]?.sym || '$';

      const badge = document.getElementById('floating-cart-badge');
      const countEl = document.getElementById('cart-badge-count');
      const totalEl = document.getElementById('cart-badge-total');
      if (badge && countEl && totalEl) {
        if (totalQty > 0 && activeTab === 'store') {
          badge.style.display = 'flex';
          countEl.innerText = totalQty;
          totalEl.innerText = `${totalPrice.toFixed(2)}${sym}`;
        } else {
          badge.style.display = 'none';
        }
      }
    }

    function addToCartCurrentProduct() {
      if (!selectedProduct) return;
      haptic('pop');
      const pid = selectedProduct.id;
      const qty = selectedQty || 1;
      const existing = cartMap[pid];
      if (existing) {
        existing.quantity = Math.min(20, existing.quantity + qty);
      } else {
        cartMap[pid] = {
          id: pid,
          name: selectedProduct.name,
          clean_name: selectedProduct.clean_name || selectedProduct.name,
          price: selectedProduct.price,
          sym: selectedProduct.sym || '$',
          emoji: selectedProduct.emoji || '⚡',
          quantity: qty
        };
      }
      saveCart();
      showToast(currentAppLanguage === 'ar' ? `🛒 تمت إضافة ${selectedProduct.clean_name || selectedProduct.name} للسلة` : `🛒 Added ${selectedProduct.clean_name || selectedProduct.name} to Cart`);
      closeProductDetailPage();
    }

    function openCartDrawer() {
      haptic('pop');
      renderCartDrawerItems();
      const sheet = document.getElementById('cart-drawer-sheet');
      if (sheet) sheet.style.display = 'flex';
      pushNav('cart_drawer', closeCartDrawer);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
    }

    function closeCartDrawer() {
      const sheet = document.getElementById('cart-drawer-sheet');
      if (sheet) sheet.style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'cart_drawer') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function changeCartQty(pid, delta) {
      haptic('light');
      if (!cartMap[pid]) return;
      cartMap[pid].quantity += delta;
      if (cartMap[pid].quantity <= 0) {
        delete cartMap[pid];
      }
      saveCart();
      renderCartDrawerItems();
    }

    function removeCartItem(pid) {
      haptic('pop');
      delete cartMap[pid];
      saveCart();
      renderCartDrawerItems();
    }

    function clearEntireCart() {
      haptic('pop');
      cartMap = {};
      saveCart();
      renderCartDrawerItems();
    }

    function renderCartDrawerItems() {
      const items = Object.values(cartMap);
      const list = document.getElementById('cart-drawer-items-list');
      const emptyMsg = document.getElementById('cart-empty-message');
      const box = document.getElementById('cart-checkout-box');
      const countBadge = document.getElementById('cart-drawer-count-badge');
      if (countBadge) countBadge.innerText = items.length;

      if (!items.length) {
        if (list) list.innerHTML = '';
        if (emptyMsg) emptyMsg.style.display = 'block';
        if (box) box.style.display = 'none';
        return;
      }
      if (emptyMsg) emptyMsg.style.display = 'none';
      if (box) box.style.display = 'block';

      const sym = items[0]?.sym || '$';
      let subtotal = 0.0;
      if (list) {
        list.innerHTML = items.map(it => {
          const itemTotal = (it.price || 0) * (it.quantity || 1);
          subtotal += itemTotal;
          return `
            <div class="cart-item-card">
              <div class="cart-item-left">
                <span class="cart-item-icon">${it.emoji || '⚡'}</span>
                <div style="min-width: 0;">
                  <div class="cart-item-name">${it.clean_name || it.name}</div>
                  <div class="cart-item-price">${it.price.toFixed(2)}${sym} × ${it.quantity} = <strong>${itemTotal.toFixed(2)}${sym}</strong></div>
                </div>
              </div>
              <div style="display: flex; align-items: center;">
                <div class="cart-stepper">
                  <button onclick="changeCartQty(${it.id}, -1)">–</button>
                  <span>${it.quantity}</span>
                  <button onclick="changeCartQty(${it.id}, 1)">+</button>
                </div>
                <button class="cart-del-btn" onclick="removeCartItem(${it.id})" title="حذف">✕</button>
              </div>
            </div>
          `;
        }).join('');
      }

      const discRow = document.getElementById('cart-summary-disc-row');
      const discEl = document.getElementById('cart-summary-discount');
      const subEl = document.getElementById('cart-summary-subtotal');
      const totEl = document.getElementById('cart-summary-total');

      const vipDiscPct = userData?.vip_discount || 0;
      let discVal = 0.0;
      if (vipDiscPct > 0) {
        discVal = subtotal * (vipDiscPct / 100);
      }
      const finalTotal = Math.max(0.01, subtotal - discVal);

      if (subEl) subEl.innerText = `${subtotal.toFixed(2)}${sym}`;
      if (discRow && discEl) {
        if (discVal > 0) {
          discRow.style.display = 'flex';
          discEl.innerText = `-${discVal.toFixed(2)}${sym} (${vipDiscPct}%)`;
        } else {
          discRow.style.display = 'none';
        }
      }
      if (totEl) totEl.innerText = `${finalTotal.toFixed(2)}${sym}`;

      const checkBtn = document.getElementById('btn-cart-checkout');
      const userBal = userData?.balance || 0.0;
      if (checkBtn) {
        if (userBal < finalTotal) {
          checkBtn.innerHTML = `<span>شحن الرصيد للمتابعة ($${userBal.toFixed(2)})</span>`;
          checkBtn.onclick = () => { closeCartDrawer(); switchTab('wallet'); };
        } else {
          checkBtn.innerHTML = `<span>تأكيد شراء السلة (${items.length} منتجات) • ${finalTotal.toFixed(2)}${sym}</span>`;
          checkBtn.onclick = executeCartCheckout;
        }
      }
    }

    async function executeCartCheckout() {
      const items = Object.values(cartMap);
      if (!items.length || !userId) return;
      haptic('light');

      const btn = document.getElementById('btn-cart-checkout');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>جاري معالجة السلة...</span>`;
      }
      if (tg?.MainButton) tg.MainButton.showProgress(false);

      const payload = {
        tg_id: userId,
        items: items.map(it => ({ product_id: it.id, quantity: it.quantity }))
      };

      try {
        const res = await fetch('/api/cart/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (btn) btn.disabled = false;
        if (tg?.MainButton) tg.MainButton.hideProgress();

        if (d.status === 'success') {
          fireConfetti();
          haptic('success');
          cartMap = {};
          saveCart();
          closeCartDrawer();
          loadUserData();

          document.getElementById('success-meta-sub').innerText = (currentAppLanguage === 'ar')
            ? `طلب #${d.order_id} · تم شراء ${d.items_count} منتجات بنجاح`
            : `Order #${d.order_id} · ${d.items_count} items purchased successfully`;
          const keysBox = document.getElementById('success-delivered-keys');
          if (keysBox) keysBox.innerHTML = renderStructuredCredentials(d.goods);

          document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
          const successView = document.getElementById('view-order-success');
          if (successView) successView.classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || 'فشل إتمام شراء السلة');
          renderCartDrawerItems();
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        if (tg?.MainButton) tg.MainButton.hideProgress();
        showToast('خطأ في الاتصال أثناء شراء السلة');
      }
    }
    // Recharge Flow State
    let selectedRechargeMethod = 'stars';
    let selectedRechargeAmount = 10.0;
    let activeInvoiceUrl = null;

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

      try {
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
      } catch (e) {}
    }

    function saveWishlist() {
      const arr = Array.from(wishlistSet);
      try { localStorage.setItem('ghstore_wishlist', JSON.stringify(arr)); } catch (e) {}
      try {
        if (tg?.CloudStorage) {
          tg.CloudStorage.setItem('ghstore_wishlist', JSON.stringify(arr), () => {});
        }
      } catch (e) {}
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
        showToast(currentAppLanguage === 'ar' ? 'تمت الإضافة للمفضلة!' : 'Added to favorites!');
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
        const isFav = wishlistSet.has(Number(selectedProduct.id));
        btn.innerHTML = `
          <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="20" height="20">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
        `;
      }
      document.querySelectorAll('.fav-btn-action').forEach(b => {
        const pid = Number(b.dataset.pid);
        const isFav = wishlistSet.has(pid);
        const svg = b.querySelector('.fav-icon-svg');
        if (svg) svg.classList.toggle('active', isFav);
      });
    }

    // Default Fallback Category Metadata
    const DEFAULT_CATALOG_META = {
      "AI & Chatbots": {
        arTitle: "الذكاء الاصطناعي",
        enTitle: "AI & Chatbots",
        icon: "🤖",
        image: "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&auto=format&fit=crop&q=85",
        arPreview: "كلود · شات جي بي تي · جيميني · جروك",
        enPreview: "Claude · ChatGPT · Gemini · Grok"
      },
      "Streaming & Entertainment": {
        arTitle: "البث والترفيه",
        enTitle: "Streaming & Media",
        icon: "🎬",
        image: "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&auto=format&fit=crop&q=85",
        arPreview: "نتفلكس · بيكوك · شاهد · أبل تي في",
        enPreview: "Netflix · Peacock · Shahid · Apple TV"
      },
      "VPN & Security": {
        arTitle: "الحماية والـ VPN",
        enTitle: "VPN & Security",
        icon: "🛡️",
        image: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&auto=format&fit=crop&q=85",
        arPreview: "نورد في بي ان · سيرف شارك · بروتون",
        enPreview: "NordVPN · Surfshark · Proton VPN"
      },
      "Design & Creative": {
        arTitle: "التصميم والإبداع",
        enTitle: "Design & Creative",
        icon: "🎨",
        image: "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?w=800&auto=format&fit=crop&q=85",
        arPreview: "كانفا · أدوبي · فيجما · فريمر",
        enPreview: "Canva · Adobe · Figma · Framer"
      },
      "Productivity": {
        arTitle: "الإنتاجية والأدوات",
        enTitle: "Productivity & Tools",
        icon: "📝",
        image: "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=800&auto=format&fit=crop&q=85",
        arPreview: "نوشن · كاب كات · أوفيس",
        enPreview: "Notion · CapCut · MS Office 365"
      },
      "Office & Productivity": {
        arTitle: "برامج الأوفيس والأعمال",
        enTitle: "Office & Business",
        icon: "💼",
        image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=85",
        arPreview: "مايكروسوفت 365 · إكسيل · وورد",
        enPreview: "Microsoft 365 · Word · Excel"
      },
      "Accounts & Email": {
        arTitle: "الحسابات والبريد الإلكتروني",
        enTitle: "Accounts & Email",
        icon: "📧",
        image: "https://images.unsplash.com/photo-1596526131083-e8c633c948d2?w=800&auto=format&fit=crop&q=85",
        arPreview: "جي ميل قديم · بريد أعمال موثق",
        enPreview: "Aged Gmail · Business Mail"
      },
      "Education": {
        arTitle: "التعليم والمنصات الدراسية",
        enTitle: "Education & Learning",
        icon: "🎓",
        image: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&auto=format&fit=crop&q=85",
        arPreview: "كورسيرا · كويزلت · أوتوديسك",
        enPreview: "Coursera · Quizlet · Autodesk"
      },
      "Communication": {
        arTitle: "برامج التواصل والمحادثات",
        enTitle: "Communication",
        icon: "💬",
        image: "https://images.unsplash.com/photo-1516251193007-45ef944ab0c6?w=800&auto=format&fit=crop&q=85",
        arPreview: "زوم برو · ميرو · مكالمات فيديو",
        enPreview: "Zoom Pro · Miro · Team Chats"
      },
      "Social Media": {
        arTitle: "وسائل التواصل الاجتماعي",
        enTitle: "Social Media",
        icon: "📱",
        image: "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&auto=format&fit=crop&q=85",
        arPreview: "سناب شات بلس · قنوات موثقة",
        enPreview: "Snapchat+ · Social Boost"
      },
      "Software Keys": {
        arTitle: "مفاتيح وتراخيص البرامج",
        enTitle: "Software Licenses",
        icon: "🔑",
        image: "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&auto=format&fit=crop&q=85",
        arPreview: "ويندوز 10/11 برو · جيت برينز",
        enPreview: "Windows 10/11 Pro · JetBrains"
      },
      "Other": {
        arTitle: "منتجات رقمية متنوعة",
        enTitle: "Digital Subscriptions",
        icon: "📦",
        image: "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=800&auto=format&fit=crop&q=85",
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

      // 1. Direct Telegram custom emoji tag resolution: extract standard UTF-8 emoji
      text = text.replace(/<tg-emoji[^>]*>(.*?)<\/tg-emoji>/gis, '$1');
      text = text.replace(/<tg-emoji[^>]*\/>/gi, '');

      // 2. Eradicate any leaked TGemoji / TG_EMOJI placeholder artifacts
      text = text.replace(/_*TG_?EMOJI_\d+_*/gi, '');
      text = text.replace(/\bTG_?emoji\d+\b/gi, '');
      text = text.replace(/<u>\s*<\/u>/gi, '');

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


      return text;
    }

    // Structured Credential Splitter
    function renderStructuredCredentials(goods) {
      if (!goods || !goods.length) {
        return '<div style="padding: 12px; color: var(--warning); text-align: center;">جاري التفعيل، سيتم التسليم قريباً.</div>';
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
            if (idx === 0) label = part.includes('@') ? (currentAppLanguage === 'ar' ? "البريد / المستخدم" : "Email / User") : (currentAppLanguage === 'ar' ? "اسم المستخدم" : "Username");
            else if (idx === 1) label = (currentAppLanguage === 'ar') ? "كلمة المرور" : "Password";
            else if (idx === 2) label = (currentAppLanguage === 'ar') ? "كود 2FA / الأمان" : "2FA / Security Key";
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
                <button class="btn-copy-mini" style="font-size: 10px;" onclick="copyCredText('${line.replace(/'/g, "\\\\'")}')">${currentAppLanguage === 'ar' ? 'نسخ السطر كاملاً' : 'Copy Full Line'}</button>
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
        orders: "العمليات",
        wallet: "المحفظة",
        settings: "الإعدادات",
        caption: "المتجر الرقمي المعتمد",
        search: "ابحث عن كلود، جيميني، نتفلكس، في بي ان...",
        filter_all: "الكل",
        filter_wishlist: "المفضلة",
        filter_stock: "متوفر فقط",
        filter_instant: "تسليم فوري",
        filter_lowprice: "الأقل سعراً",
        banner_badge: "تحديثات المتجر",
        banner_title: "اشتراكات كلود وجيميني متوفرة فورياً",
        banner_sub: "تسليم تلقائي فوري للمفاتيح والحسابات على مدار الساعة",
        pwa_title: "أضف التطبيق للشاشة الرئيسية",
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
        instant_delivery: "تسليم تلقائي فوري",
        custom_activation: "تفعيل مخصص",
        warranty_30d: "ضمان 30 يوم",
        in_stock: "متوفر",
        out_of_stock: "نفد المخزون",
        desc: "الوصف",
        promo_code_label: "كود الخصم / Promo Code",
        apply: "تطبيق",
        total: "السعر الإجمالي",
        insufficient_balance: "الرصيد المتاح غير كافٍ لهذا الطلب.",
        topup_to_continue: "شحن الرصيد للمتابعة",
        buy_now: "شراء فوري",
        stars_buy: "الدفع عبر نجوم تيليجرام",
        restock_alert: "نبهني فور التوفر",
        order_success: "تم الطلب بنجاح!",
        delivered_keys: "بيانات الحساب / المفاتيح المسلمة",
        copy_hint: "انقر على أي كود بالأعلى للنسخ الفوري!",
        view_orders: "عرض في طلباتي",
        continue_shopping: "متابعة التسوق",
        orders_title: "العمليات والسجل",
        orders_empty_title: "لا توجد عمليات أو طلبات بعد",
        orders_empty_sub: "تصفح التصنيفات واطلب الحسابات والمفاتيح بضغطة واحدة!",
        browse_store: "تصفح المتجر",
        step_placed: "تم الطلب",
        step_processing: "قيد المعالجة",
        step_delivered: "تم التسليم",
        claim_warranty: "طلب تعويض الضمان",
        wallet_balance_title: "الرصيد المتاح للشراء",
        wallet_ready: "جاهز للشراء الفوري",
        vip_progress: "التقدم نحو رتبة",
        method_section_title: "1. اختر وسيلة الشحن",
        stars_title: "نجوم تيليجرام (Telegram Stars)",
        stars_sub: "دفع فوري عبر Apple Pay أو Google Pay أو النجوم",
        crypto_title: "العملات الرقمية (Crypto)",
        crypto_sub: "USDT (TRC20/BEP20), Bitcoin, Solana, TON",
        shamcash_title: "شام كاش (Sham Cash)",
        shamcash_sub: "دفع مباشر وسريع عبر بنك شام كاش",
        syriatelcash_title: "سيرياتيل كاش (Syriatel Cash)",
        syriatelcash_sub: "دفع مباشر بالليرة السورية (SYP فقط)",
        amount_section_title: "2. اختر المبلغ أو حدد مخصصاً",
        custom_amount_placeholder: "أدخل المبلغ ($)... e.g. 15",
        voucher_section_title: "شحن عبر كرت هدية (Voucher)",
        voucher_btn: "شحن الكرت",
        theme_section_title: "المظهر / Appearance",
        theme_dark: "داكن (Dark)",
        theme_light: "فاتح (Light)",
        install_section_title: "تثبيت التطبيق",
        install_desc: "أضف أيقونة متجر GH Store إلى شاشة هاتفك الرئيسية لتصفح العروض فورياً!",
        install_btn: "إضافة إلى الشاشة الرئيسية",
        currency_title: "عملة العرض المفضلة",
        lang_title: "اللغة / Language",
        referral_title: "برنامج الإحالة والأرباح",
        referral_desc: "شارك رابط الإحالة الخاص بك واحصل على <strong>0.2% عمولة أرباح</strong> مباشرة من هامش كل عملية شراء يقوم بها أصدقاؤك!",
        ref_stat_count: "المدعوون",
        ref_stat_earned: "إجمالي الأرباح",
        ref_stat_rate: "نسبة العمولة",
        ref_breakdown_title: "سجل الأصدقاء المدعوين والأرباح",
        copy: "نسخ",
        orders_word: "طلب",
        sheet_payment_title: "إتمام عملية الشحن",
        sheet_payment_desc: "تم إنشاء فاتورة الشحن بنجاح. يمكنك المتابعة في المتصفح الخارجي لإتمام الدفع، أو نسخ رابط الفاتورة المباشر:",
        sheet_open_btn: "فتح صفحة الدفع في المتصفح",
        sheet_copy_btn: "نسخ رابط الفاتورة المباشر"
      },
      en: {
        store: "Store",
        orders: "Activity",
        wallet: "Wallet",
        settings: "Settings",
        caption: "Verified Digital Reseller",
        search: "Search Claude, Gemini, Netflix, VPN...",
        filter_all: "All",
        filter_wishlist: "Favorites",
        filter_stock: "In Stock",
        filter_instant: "Instant Delivery",
        filter_lowprice: "Lowest Price",
        banner_badge: "STORE UPDATES",
        banner_title: "Instant Claude & Gemini Accounts Ready",
        banner_sub: "Automated 24/7 key & account delivery with instant activation",
        pwa_title: "Add App to Home Screen",
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
        instant_delivery: "Instant Automated Delivery",
        custom_activation: "Custom Activation",
        warranty_30d: "30 Days Warranty",
        in_stock: "In Stock",
        out_of_stock: "Out of Stock",
        desc: "Description",
        promo_code_label: "Promo Code / Coupon",
        apply: "Apply",
        total: "Total Price",
        insufficient_balance: "Insufficient balance for this order.",
        topup_to_continue: "Top Up Balance to Continue",
        buy_now: "Instant Buy",
        stars_buy: "Pay with Telegram Stars",
        restock_alert: "Notify When Available (Restock Alert)",
        order_success: "Order Successful!",
        delivered_keys: "Delivered Credentials / Keys",
        copy_hint: "Tap any code above to copy instantly!",
        view_orders: "View in Orders",
        continue_shopping: "Continue Shopping",
        orders_title: "Processes & Activity",
        orders_empty_title: "No activity or orders yet",
        orders_empty_sub: "Browse catalogs and order accounts & keys in 1 tap!",
        browse_store: "Browse Store",
        step_placed: "Placed",
        step_processing: "Processing",
        step_delivered: "Delivered",
        claim_warranty: "Claim Warranty",
        wallet_balance_title: "Available Balance",
        wallet_ready: "Ready for instant purchase",
        vip_progress: "Progress to",
        method_section_title: "1. Select Payment Method",
        stars_title: "Telegram Stars",
        stars_sub: "Instant payment via Apple Pay, Google Pay or Stars",
        crypto_title: "Cryptocurrency (Crypto)",
        crypto_sub: "USDT (TRC20/BEP20), Bitcoin, Solana, TON",
        shamcash_title: "Sham Cash",
        shamcash_sub: "Direct payment via Sham Cash wallet",
        syriatelcash_title: "Syriatel Cash",
        syriatelcash_sub: "Direct payment in Syrian Pounds (SYP only)",
        amount_section_title: "2. Choose Amount or Enter Custom",
        custom_amount_placeholder: "Enter amount ($)... e.g. 15",
        voucher_section_title: "Redeem Gift Card (Voucher)",
        voucher_btn: "Redeem Card",
        theme_section_title: "Theme & Appearance",
        theme_dark: "Dark Mode",
        theme_light: "Light Mode",
        install_section_title: "Install App",
        install_desc: "Add GH Store to your phone home screen for instant access!",
        install_btn: "Add to Home Screen",
        currency_title: "Preferred Display Currency",
        lang_title: "Language",
        referral_title: "Referral Program & Earnings",
        referral_desc: "Share your referral link and earn <strong>0.2% profit margin commission</strong> on every purchase made by friends!",
        ref_stat_count: "Invited",
        ref_stat_earned: "Total Earned",
        ref_stat_rate: "Commission",
        ref_breakdown_title: "Referred Friends & Earnings Breakdown",
        copy: "Copy",
        orders_word: "orders",
        sheet_payment_title: "Complete Payment",
        sheet_payment_desc: "Invoice created successfully. You can proceed in your mobile browser or copy the direct payment link:",
        sheet_open_btn: "Open Payment Page in Browser",
        sheet_copy_btn: "Copy Direct Payment Link"
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
      setText('label-filter-wishlist', d.filter_wishlist);
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
      setText('label-method-shamcash-name', d.shamcash_title);
      setText('label-method-shamcash-sub', d.shamcash_sub);
      setText('label-method-syriatelcash-name', d.syriatelcash_title);
      setText('label-method-syriatelcash-sub', d.syriatelcash_sub);
      setText('recharge-amount-title', d.amount_section_title);
      setText('voucher-section-title', d.voucher_section_title);
      setText('voucher-redeem-btn', d.voucher_btn);

      // Payment Sheet modal labels
      setText('sheet-payment-title', d.sheet_payment_title);
      setText('sheet-payment-desc', d.sheet_payment_desc);
      setText('sheet-label-open', d.sheet_open_btn);
      setText('sheet-label-copy', d.sheet_copy_btn);

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
        let catObj = categoriesList.find(c => (typeof c === 'object' ? c.name : c) === activeCatalog);
        let dispTitle = activeCatalog;
        if (catObj && typeof catObj === 'object') {
          dispTitle = (lang === 'ar' ? catObj.name_ar : catObj.name_en) || activeCatalog;
        } else if (DEFAULT_CATALOG_META[activeCatalog]) {
          dispTitle = (lang === 'ar' ? DEFAULT_CATALOG_META[activeCatalog].arTitle : DEFAULT_CATALOG_META[activeCatalog].enTitle) || activeCatalog;
        }
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
      if (tab === 'wallet') {
        updateRechargeButtonText();
      }
      if (tg?.MainButton && !selectedProduct) {
        tg.MainButton.hide();
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
      if (!allProducts.length) {
        const grid = document.getElementById('catalogs-grid');
        if (grid) {
          grid.innerHTML = `
            <div class="skeleton-grid">
              <div class="skeleton-box"></div>
              <div class="skeleton-box"></div>
              <div class="skeleton-box"></div>
              <div class="skeleton-box"></div>
            </div>
          `;
        }
      }
      try {
        const res = await fetch('/api/catalog');
        const d = await res.json();
        allProducts = d.products || [];
        categoriesList = d.categories || [];
        try { localStorage.setItem('ghstore_catalog_cache', JSON.stringify(d)); } catch (e) {}
        if (d.store_logo_url) applyStoreLogo(d.store_logo_url);
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

    // DYNAMIC DATABASE-DRIVEN CATEGORIES RENDERING
    function renderCatalogsGrid() {
      const container = document.getElementById('catalogs-grid');
      if (!container) return;

      const d = I18N[currentAppLanguage] || I18N.ar;
      const isGrid = (currentCatalogViewMode === 'grid');
      const isAdmin = !!(userData && userData.is_admin);

      container.className = `catalogs-grid ${isGrid ? 'grid-layout' : 'list-layout'}`;

      container.innerHTML = categoriesList.map(catItem => {
        const catName = (typeof catItem === 'object' && catItem.name) ? catItem.name : String(catItem);
        const catId = (typeof catItem === 'object' && catItem.id) ? catItem.id : null;
        const items = allProducts.filter(p => p.category === catName);
        if (!items || !items.length) return '';

        let displayTitle = catName;
        let displayPreview = '';
        let imageUrl = '';
        let icon = '📦';

        if (typeof catItem === 'object' && catItem.image_url) {
          displayTitle = (currentAppLanguage === 'ar' && catItem.name_ar) ? catItem.name_ar : (catItem.name_en || catName);
          displayPreview = (currentAppLanguage === 'ar' && catItem.preview_ar) ? catItem.preview_ar : (catItem.preview_en || '');
          imageUrl = catItem.image_url;
          icon = catItem.icon || '📦';
        } else {
          const fallback = DEFAULT_CATALOG_META[catName] || {};
          displayTitle = (currentAppLanguage === 'ar' && fallback.arTitle) ? fallback.arTitle : (fallback.enTitle || catName);
          displayPreview = (currentAppLanguage === 'ar' && fallback.arPreview) ? fallback.arPreview : (fallback.enPreview || '');
          imageUrl = fallback.image || 'https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=800&auto=format&fit=crop&q=85';
          icon = fallback.icon || '📦';
        }

        const minPrice = Math.min(...items.map(p => p.price || 999));
        const sym = items[0]?.sym || '$';

        const adminEditBtn = (isAdmin && catId)
          ? `<button class="admin-edit-badge-btn" onclick="openAdminCategoryEditor(${catId}, event)">تعديل</button>`
          : '';

        if (isGrid) {
          return `
            <div class="catalog-visual-card" style="background-image: url('${imageUrl}');" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
              <div class="catalog-visual-overlay"></div>
              <div class="catalog-visual-top">
                <span class="catalog-visual-pill">${items.length} ${d.items_suffix}</span>
                ${adminEditBtn}
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

        const chevron = (currentAppLanguage === 'ar') ? '‹' : '›';
        return `
          <div class="catalog-list-card" onclick="openCollection('${catName.replace(/'/g, "\\\\'")}')">
            <div class="catalog-left">
              <div class="catalog-icon-box">${icon}</div>
              <div class="catalog-info">
                <div style="display:flex; align-items:center;">
                  <span class="catalog-name">${displayTitle}</span>
                  ${adminEditBtn}
                </div>
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

      let catObj = categoriesList.find(c => (typeof c === 'object' ? c.name : c) === catName);
      let dispTitle = catName;
      if (catObj && typeof catObj === 'object') {
        dispTitle = (currentAppLanguage === 'ar' ? catObj.name_ar : catObj.name_en) || catName;
      } else if (DEFAULT_CATALOG_META[catName]) {
        dispTitle = (currentAppLanguage === 'ar' ? DEFAULT_CATALOG_META[catName].arTitle : DEFAULT_CATALOG_META[catName].enTitle) || catName;
      }
      document.getElementById('active-collection-title').innerText = dispTitle;

      let filtered = allProducts.filter(p => p.category === catName);
      filtered = filterAndSortProducts(filtered);
      renderProductItems(filtered);

      pushNav('collection', returnToCollections);
    }

    function returnToCollections() {
      haptic('light');
      activeCatalog = null;
      document.getElementById('store-search-input').value = '';
      document.getElementById('store-clear-btn').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'none';
      document.getElementById('catalogs-collection-mode').style.display = 'block';

      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'collection') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    // Quick Filters & Sorting Logic (IN-STOCK PARTITIONING: Available first, Out-of-Stock last)
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
          (p.clean_name || p.name).toLowerCase().includes(q) ||
          p.name.toLowerCase().includes(q) ||
          (p.description || '').toLowerCase().includes(q) ||
          (p.description_ar || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
      }

      const filtered = filterAndSortProducts(baseList);
      document.getElementById('active-collection-title').innerText = filterKey === 'wishlist'
        ? (currentAppLanguage === 'ar' ? 'المفضلة' : 'Favorites')
        : (currentAppLanguage === 'ar' ? 'النتائج المصفاة' : 'Filtered Results');
      renderProductItems(filtered);

      if (tg?.BackButton) {
        tg.BackButton.show();
        tg.BackButton.onClick(returnToCollections);
      }
    }

    function filterAndSortProducts(list) {
      let result = [...list];
      if (activeCatalogFilter === 'wishlist') {
        result = result.filter(p => wishlistSet.has(Number(p.id)));
      } else if (activeCatalogFilter === 'stock') {
        result = result.filter(p => p.stock === null || p.stock > 0);
      } else if (activeCatalogFilter === 'instant') {
        result = result.filter(p => p.delivery_type !== 'activation');
      }

      // Priority sort: In-stock items ALWAYS at the top, out-of-stock items sink to the very end!
      result.sort((a, b) => {
        const aOut = (a.stock !== null && a.stock <= 0) ? 1 : 0;
        const bOut = (b.stock !== null && b.stock <= 0) ? 1 : 0;
        if (aOut !== bOut) return aOut - bOut;
        if (activeCatalogFilter === 'lowprice') {
          return (a.price || 0) - (b.price || 0);
        }
        return 0;
      });

      return result;
    }

    function applySearchQuery(term) {
      haptic('light');
      const input = document.getElementById('store-search-input');
      if (input) {
        input.value = term;
        handleSearch();
      }
    }

    function handleSearch() {
      const rawQ = (document.getElementById('store-search-input').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('store-clear-btn');

      if (rawQ) {
        clearBtn.style.display = 'block';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
        document.getElementById('products-catalog-mode').style.display = 'block';
        document.getElementById('active-collection-title').innerText = (currentAppLanguage === 'ar') ? `نتائج البحث: "${rawQ}"` : `Search: "${rawQ}"`;

        let queryTokens = [rawQ];
        for (const [k, aliases] of Object.entries(SEARCH_ALIASES)) {
          if (rawQ.includes(k) || k.includes(rawQ)) {
            queryTokens.push(...aliases);
          }
        }

        let matched = allProducts.filter(p => {
          const nameStr = ((p.clean_name || '') + ' ' + (p.name || '')).toLowerCase();
          const descStr = ((p.description || '') + ' ' + (p.description_ar || '')).toLowerCase();
          const catStr = (p.category || '').toLowerCase();
          return queryTokens.some(tok => nameStr.includes(tok) || descStr.includes(tok) || catStr.includes(tok));
        });

        matched = filterAndSortProducts(matched);
        renderProductItems(matched);

        pushNav('search_results', returnToCollections);
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

    // Clean Product Rows: NO EMOJIS, Clean Title + Structured Spec Badges + Admin Edit Button
    function renderProductItems(products) {
      const container = document.getElementById('catalog-products-list');
      if (!container) return;
      if (!products.length) {
        container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--hint);">${currentAppLanguage === 'ar' ? 'لا توجد منتجات مطابقة لهذا الفلتر.' : 'No products found matching this filter.'}</div>`;
        return;
      }
      const d = I18N[currentAppLanguage] || I18N.ar;
      const isAdmin = !!(userData && userData.is_admin);

      container.innerHTML = products.map(p => {
        const isFav = wishlistSet.has(Number(p.id));
        const isOutOfStock = (p.stock !== null && p.stock <= 0);

        // 1. Clean Stock Badge (No emojis)
        const stockBadge = isOutOfStock
          ? `<span class="spec-pill stock-out">${d.out_of_stock}</span>`
          : `<span class="spec-pill in-stock">${p.stock ? `${d.in_stock} (${p.stock})` : d.in_stock}</span>`;

        // 2. Structured Spec Pills (No emojis)
        const durText = (currentAppLanguage === 'ar' ? p.duration_ar : p.duration_en) || null;
        const warText = (currentAppLanguage === 'ar' ? p.warranty_ar : p.warranty_en) || null;
        const typText = (currentAppLanguage === 'ar' ? p.type_ar : p.type_en) || null;

        const durPill = durText ? `<span class="spec-pill duration">${durText}</span>` : '';
        const isNoWar = warText && (warText.includes('بدون') || warText.includes('No'));
        const warPill = warText ? `<span class="spec-pill ${isNoWar ? 'warranty-none' : 'warranty'}">${warText}</span>` : '';
        const typPill = typText ? `<span class="spec-pill type">${typText}</span>` : '';

        const favSvg = `
          <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="18" height="18">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
        `;

        const displayTitle = p.clean_name || p.name;
        const adminEditBtn = isAdmin
          ? `<button class="admin-edit-badge-btn" onclick="openAdminProductEditor(${p.id}, event)">تعديل</button>`
          : '';

        return `
          <div class="product-row" onclick="openProductDetail(${Number(p.id)})">
            <div class="prod-left">
              <div style="display:flex; align-items:center;">
                <span class="prod-title">${displayTitle}</span>
                ${adminEditBtn}
              </div>
              <div class="prod-specs-row">
                ${stockBadge}
                ${durPill}
                ${warPill}
                ${typPill}
              </div>
            </div>
            <div class="prod-price-box">
              <div class="prod-price">${p.price ? p.price.toFixed(2) + p.sym : 'N/A'}</div>
              <div style="display: flex; align-items: center; gap: 4px; margin-top: 2px;">
                <button class="fav-btn-action" data-pid="${p.id}" onclick="toggleWishlist(${p.id}, event)">
                  ${favSvg}
                </button>
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

      try {
        const couponInput = document.getElementById('coupon-code-input');
        if (couponInput) couponInput.value = '';
        const couponNote = document.getElementById('coupon-applied-note');
        if (couponNote) couponNote.style.display = 'none';

        const setTxt = (id, txt) => {
          const el = document.getElementById(id);
          if (el) el.innerText = txt;
        };

        const displayTitle = selectedProduct.clean_name || selectedProduct.name;
        setTxt('prod-hero-name', displayTitle);
        setTxt('prod-hero-cat', selectedProduct.category || 'Digital');
        setTxt('prod-qty-val', '1');

        const rawDesc = (currentAppLanguage === 'ar' && selectedProduct.description_ar)
          ? selectedProduct.description_ar
          : (selectedProduct.description || '');
        const descBox = document.getElementById('prod-rich-desc');
        if (descBox) descBox.innerHTML = formatRichDescription(rawDesc);

        const isInstant = selectedProduct.delivery_type !== 'activation';
        const isOutOfStock = (selectedProduct.stock !== null && selectedProduct.stock <= 0);

        setTxt('prod-delivery-badge', isInstant
          ? (currentAppLanguage === 'ar' ? 'تسليم تلقائي فوري' : 'Instant Automated Delivery')
          : (currentAppLanguage === 'ar' ? 'تفعيل مخصص' : 'Custom Activation'));

        setTxt('prod-stock-badge', isOutOfStock
          ? (currentAppLanguage === 'ar' ? 'نفد المخزون' : 'Out of Stock')
          : (selectedProduct.stock ? `${currentAppLanguage === 'ar' ? 'متوفر' : 'In Stock'} (${selectedProduct.stock})` : (currentAppLanguage === 'ar' ? 'تسليم فوري' : 'Instant Delivery')));

        // Admin detail edit button
        const adminDetailEdit = document.getElementById('admin-detail-edit-container');
        if (adminDetailEdit) {
          adminDetailEdit.style.display = (userData && userData.is_admin) ? 'block' : 'none';
        }

        // Spec badges in product detail
        const durEl = document.getElementById('prod-dur-badge');
        const durVal = (currentAppLanguage === 'ar' ? selectedProduct.duration_ar : selectedProduct.duration_en);
        if (durEl) {
          if (durVal) { durEl.innerText = durVal; durEl.style.display = 'inline-block'; }
          else durEl.style.display = 'none';
        }

        const warEl = document.getElementById('prod-war-badge');
        const warVal = (currentAppLanguage === 'ar' ? selectedProduct.warranty_ar : selectedProduct.warranty_en);
        if (warEl) {
          if (warVal) { warEl.innerText = warVal; warEl.style.display = 'inline-block'; }
          else warEl.style.display = 'none';
        }

        const typEl = document.getElementById('prod-typ-badge');
        const typVal = (currentAppLanguage === 'ar' ? selectedProduct.type_ar : selectedProduct.type_en);
        if (typEl) {
          if (typVal) { typEl.innerText = typVal; typEl.style.display = 'inline-block'; }
          else typEl.style.display = 'none';
        }

        const restockBox = document.getElementById('restock-alert-box');
        const buyBtn = document.getElementById('btn-inapp-purchase');
        const starsBtn = document.getElementById('btn-stars-purchase');

        if (isOutOfStock) {
          if (restockBox) restockBox.style.display = 'block';
          if (buyBtn) buyBtn.style.display = 'none';
          if (starsBtn) starsBtn.style.display = 'none';
        } else {
          if (restockBox) restockBox.style.display = 'none';
          if (buyBtn) buyBtn.style.display = 'flex';
          if (starsBtn) starsBtn.style.display = 'flex';
        }

        updateWishlistUI();
        updateDetailPagePrice();
      } catch (err) {
        console.error("Setup product detail error:", err);
      }

      pushNav('product_detail', closeProductDetailPage);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
      if (tg?.enableClosingConfirmation) tg.enableClosingConfirmation();

      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const detailView = document.getElementById('view-product-detail');
      if (detailView) detailView.classList.add('active');
    }

    function closeProductDetailPage() {
      haptic('light');
      selectedProduct = null;
      const detailView = document.getElementById('view-product-detail');
      if (detailView) detailView.classList.remove('active');
      const storeView = document.getElementById('view-store');
      if (storeView) storeView.classList.add('active');

      if (tg?.MainButton) {
        tg.MainButton.offClick(executeProductBuy);
        tg.MainButton.offClick(goToWalletFromMainBtn);
        tg.MainButton.offClick(triggerInAppRestockSubscribe);
        tg.MainButton.hide();
      }

      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (tg?.disableClosingConfirmation) tg.disableClosingConfirmation();

      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'product_detail') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function adjustQty(delta) {
      haptic('light');
      selectedQty = Math.max(1, Math.min(10, selectedQty + delta));
      const qVal = document.getElementById('prod-qty-val');
      if (qVal) qVal.innerText = selectedQty;
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
          if (note) {
            note.innerText = d.message;
            note.style.display = 'block';
          }
          updateDetailPagePrice();
        } else {
          appliedCoupon = null;
          showToast(d.error || (currentAppLanguage === 'ar' ? 'كود الخصم غير صالح' : 'Invalid promo code'));
          const note = document.getElementById('coupon-applied-note');
          if (note) note.style.display = 'none';
          updateDetailPagePrice();
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'فشل التحقق من كود الخصم' : 'Failed to validate promo code');
      }
    }

    // SAFE PRICE UPDATER
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

      const discTag = document.getElementById('prod-discount-tag');
      if (discTag) discTag.innerText = discountText;

      const totalTag = document.getElementById('prod-total-price');
      if (totalTag) totalTag.innerText = `${total.toFixed(2)}${sym}`;

      const priceTag = document.getElementById('btn-price-tag');
      if (priceTag) priceTag.innerText = `(${total.toFixed(2)}${sym})`;

      const userBalance = userData?.balance || 0.0;
      const alertBox = document.getElementById('insufficient-funds-alert');
      const buyBtn = document.getElementById('btn-inapp-purchase');
      const buyLabel = document.getElementById('btn-buy-action-label');
      const d = I18N[currentAppLanguage] || I18N.ar;

      if (userBalance < total) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.innerHTML = (currentAppLanguage === 'ar')
            ? `الرصيد المتاح غير كافٍ (تحتاج ${total.toFixed(2)}${sym}، رصيدك $${userBalance.toFixed(2)}).`
            : `Insufficient balance (Requires ${total.toFixed(2)}${sym}, available $${userBalance.toFixed(2)}).`;
        }
        if (buyLabel) buyLabel.innerText = d.topup_to_continue;
        if (priceTag) priceTag.style.display = 'none';
        if (buyBtn) buyBtn.onclick = () => switchTab('wallet');
      } else {
        if (alertBox) alertBox.style.display = 'none';
        if (buyLabel) buyLabel.innerText = d.buy_now;
        if (priceTag) priceTag.style.display = 'inline';
        if (buyBtn) buyBtn.onclick = executeProductBuy;
      }

      if (tg?.MainButton && selectedProduct) {
        tg.MainButton.offClick(executeProductBuy);
        tg.MainButton.offClick(goToWalletFromMainBtn);
        tg.MainButton.offClick(triggerInAppRestockSubscribe);

        const isOutOfStock = (selectedProduct.stock !== null && selectedProduct.stock <= 0);
        if (isOutOfStock) {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? 'تنبيه عند التوفر 🔔' : 'Notify on Restock 🔔')
            .setParams({ color: '#f59e0b', text_color: '#ffffff', is_visible: true, is_active: true });
          tg.MainButton.onClick(triggerInAppRestockSubscribe);
        } else if (userBalance < total) {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? `شحن الرصيد للمتابعة ($${userBalance.toFixed(2)})` : `Top Up to Continue ($${userBalance.toFixed(2)})`)
            .setParams({ color: '#f59e0b', text_color: '#ffffff', is_visible: true, is_active: true });
          tg.MainButton.onClick(goToWalletFromMainBtn);
        } else {
          tg.MainButton.setText(`${d.buy_now} • $${total.toFixed(2)}`)
            .setParams({ has_shine_effect: true, color: '#2481cc', text_color: '#ffffff', is_visible: true, is_active: true });
          tg.MainButton.onClick(executeProductBuy);
        }
      }
    }

    function goToWalletFromMainBtn() {
      closeProductDetailPage();
      switchTab('wallet');
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
        ? `تسوق ${selectedProduct.clean_name || selectedProduct.name} الآن بأفضل سعر على GH Store!`
        : `Shop ${selectedProduct.clean_name || selectedProduct.name} now at best prices on GH Store!`;

      if (tg?.shareToStory) {
        tg.shareToStory({
          media_url: selectedProduct.image_url || 'https://bot.gh-store.me/static/banner.png',
          text: shareText,
          widget_link: { url: shareUrl, name: "GH Store" }
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
      if (tg?.MainButton) tg.MainButton.showProgress(false);
      const buyBtn = document.getElementById('btn-inapp-purchase');
      if (buyBtn) {
        buyBtn.disabled = true;
        buyBtn.innerHTML = `<span>${currentAppLanguage === 'ar' ? 'جاري معالجة الطلب...' : 'Processing Order...'}</span>`;
      }

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
        if (buyBtn) buyBtn.disabled = false;
        if (tg?.MainButton) tg.MainButton.hideProgress();

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
          if (keysBox) keysBox.innerHTML = renderStructuredCredentials(d.goods);

          if (tg?.MainButton) {
            tg.MainButton.offClick(executeProductBuy);
            tg.MainButton.offClick(goToWalletFromMainBtn);
            tg.MainButton.offClick(triggerInAppRestockSubscribe);
            tg.MainButton.hide();
          }
          document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
          const successView = document.getElementById('view-order-success');
          if (successView) successView.classList.add('active');
        } else {
          haptic('error');
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل إتمام الطلب.' : 'Order failed.'));
          updateDetailPagePrice();
        }
      } catch (e) {
        if (buyBtn) buyBtn.disabled = false;
        if (tg?.MainButton) tg.MainButton.hideProgress();
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

    // ==========================================
    // HARDENED RECHARGE / TOP-UP FLOW LOGIC
    // ==========================================
    let selectedShamCurrency = 'USD';

    function setShamCurrency(curr) {
      haptic('light');
      selectedShamCurrency = curr;
      const btnUsd = document.getElementById('btn-sham-curr-usd');
      const btnSyp = document.getElementById('btn-sham-curr-syp');
      if (btnUsd) btnUsd.classList.toggle('active', curr === 'USD');
      if (btnSyp) btnSyp.classList.toggle('active', curr === 'SYP');
      updateRechargeButtonText();
    }

    function selectRechargeMethod(method) {
      haptic('pop');
      selectedRechargeMethod = method;
      ['stars', 'crypto', 'shamcash', 'syriatelcash'].forEach(m => {
        const card = document.getElementById('method-card-' + m);
        if (card) card.classList.toggle('active', m === method);
      });
      const shamBox = document.getElementById('shamcash-currency-box');
      if (shamBox) {
        shamBox.style.display = (method === 'shamcash') ? 'block' : 'none';
      }
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
      } else if (selectedRechargeMethod === 'shamcash') {
        methodName = (currentAppLanguage === 'ar') ? "شام كاش" : "Sham Cash";
      } else if (selectedRechargeMethod === 'syriatelcash') {
        methodName = (currentAppLanguage === 'ar') ? "سيرياتيل كاش" : "Syriatel Cash";
      } else {
        methodName = (currentAppLanguage === 'ar') ? "نجوم تيليجرام" : "Telegram Stars";
      }

      const amtStr = selectedRechargeAmount ? selectedRechargeAmount.toFixed(2) : "10.00";
      const sypRate = (userData && userData.admin_stats && userData.admin_stats.syp_usd_rate) ? userData.admin_stats.syp_usd_rate : 392.0;

      if (selectedRechargeMethod === 'syriatelcash') {
        const sypEst = Math.round(selectedRechargeAmount * sypRate);
        if (currentAppLanguage === 'ar') {
          btn.innerHTML = `<span>شحن ${amtStr}$ (≈ ${sypEst.toLocaleString()} ل.س) عبر سيرياتيل كاش</span>`;
        } else {
          btn.innerHTML = `<span>Recharge $${amtStr} (≈ ${sypEst.toLocaleString()} SYP) via Syriatel Cash</span>`;
        }
      } else if (selectedRechargeMethod === 'shamcash') {
        if (selectedShamCurrency === 'SYP') {
          const sypEst = Math.round(selectedRechargeAmount * sypRate);
          if (currentAppLanguage === 'ar') {
            btn.innerHTML = `<span>شحن ${amtStr}$ (≈ ${sypEst.toLocaleString()} ل.س) عبر شام كاش</span>`;
          } else {
            btn.innerHTML = `<span>Recharge $${amtStr} (≈ ${sypEst.toLocaleString()} SYP) via Sham Cash</span>`;
          }
        } else {
          if (currentAppLanguage === 'ar') {
            btn.innerHTML = `<span>شحن ${amtStr}$ عبر شام كاش (بالدولار)</span>`;
          } else {
            btn.innerHTML = `<span>Recharge $${amtStr} via Sham Cash (USD)</span>`;
          }
        }
      } else {
        if (currentAppLanguage === 'ar') {
          btn.innerHTML = `<span>شحن ${amtStr}$ عبر ${methodName}</span>`;
        } else {
          btn.innerHTML = `<span>Recharge $${amtStr} via ${methodName}</span>`;
        }
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
      if (btn) {
        btn.disabled = true;
        const loadingText = (currentAppLanguage === 'ar') ? 'جاري تجهيز الفاتورة...' : 'Generating invoice...';
        btn.innerHTML = `<span>${loadingText}</span>`;
      }

      try {
        const res = await fetch('/api/invoice/topup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            amount: selectedRechargeAmount,
            method: selectedRechargeMethod,
            currency: (selectedRechargeMethod === 'shamcash') ? selectedShamCurrency : ((selectedRechargeMethod === 'syriatelcash') ? 'SYP' : 'USD')
          })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;

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
          openInvoicePage(d);
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'تعذر إنشاء فاتورة الشحن' : 'Failed to create invoice'));
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        updateRechargeButtonText();
        showToast(currentAppLanguage === 'ar' ? 'خطأ في شبكة الشحن' : 'Recharge network error');
      }
    }

    let currentInvoiceData = null;

    function openInvoicePage(invoiceData) {
      currentInvoiceData = invoiceData;
      activeInvoiceUrl = invoiceData.url || '';
      haptic('pop');

      // 1. Populate Invoice Meta
      const invId = invoiceData.invoice_id ? `#INV-${invoiceData.invoice_id}` : '#INV-TOPUP';
      const idEl = document.getElementById('invoice-id-display');
      if (idEl) idEl.innerText = invId;

      // 2. Populate Status Badge
      const statusBadge = document.getElementById('invoice-status-badge');
      const statusText = document.getElementById('invoice-status-text');
      if (statusBadge) {
        statusBadge.style.background = 'rgba(245, 158, 11, 0.18)';
        statusBadge.style.color = '#f59e0b';
      }
      if (statusText) statusText.innerText = (currentAppLanguage === 'ar') ? 'بانتظار التحويل / الدفع' : 'Pending Payment';

      // 3. Populate Method Icon and Title
      const iconBox = document.getElementById('invoice-method-icon-box');
      const nameEl = document.getElementById('invoice-method-name');
      const subEl = document.getElementById('invoice-method-sub');
      const prov = invoiceData.provider || selectedRechargeMethod;

      if (prov === 'shamcash') {
        if (iconBox) iconBox.innerHTML = '<img src="https://shamcash.sy/_next/static/media/logo.5be69def.svg" class="method-brand-img" alt="Sham Cash">';
        if (nameEl) nameEl.innerText = (currentAppLanguage === 'ar') ? 'شام كاش (Sham Cash)' : 'Sham Cash';
        if (subEl) subEl.innerText = (currentAppLanguage === 'ar') ? 'دفع مباشر وفوري عبر بنك شام كاش' : 'Direct payment via Sham Cash';
      } else if (prov === 'syriatelcash') {
        if (iconBox) iconBox.innerHTML = '<img src="https://www.syriatel.sy/assets/img/logo.png" class="method-brand-img" alt="Syriatel Cash">';
        if (nameEl) nameEl.innerText = (currentAppLanguage === 'ar') ? 'سيرياتيل كاش (Syriatel Cash)' : 'Syriatel Cash';
        if (subEl) subEl.innerText = (currentAppLanguage === 'ar') ? 'دفع بالليرة السورية (SYP)' : 'Direct payment in SYP';
      } else {
        if (iconBox) iconBox.innerHTML = '<span style="font-size: 24px;">🪙</span>';
        if (nameEl) nameEl.innerText = (currentAppLanguage === 'ar') ? 'العملات الرقمية (Crypto)' : 'Cryptocurrency';
        if (subEl) subEl.innerText = 'USDT, Bitcoin, Solana, TON';
      }

      // 4. Populate Amounts
      const usdEl = document.getElementById('invoice-amount-usd');
      const localEl = document.getElementById('invoice-amount-local');
      const amt = Number(invoiceData.amount || selectedRechargeAmount || 10);
      if (usdEl) usdEl.innerText = `$${amt.toFixed(2)} USD`;

      if (invoiceData.invoice_amount && invoiceData.currency === 'SYP') {
        if (localEl) {
          localEl.innerText = `≈ ${Number(invoiceData.invoice_amount).toLocaleString()} ل.س`;
          localEl.style.display = 'block';
        }
      } else {
        if (localEl) localEl.style.display = 'none';
      }

      // 5. Reset Check Status Button
      const checkBtn = document.getElementById('btn-check-invoice-status');
      const checkLabel = document.getElementById('label-check-invoice');
      if (checkBtn) checkBtn.disabled = false;
      if (checkLabel) checkLabel.innerText = (currentAppLanguage === 'ar') ? '🔄 التحقق من وصول الدفع وتحديث الرصيد' : '🔄 Check Payment Status & Refresh';

      // 6. Navigate to Invoice Page
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const invoiceView = document.getElementById('view-invoice');
      if (invoiceView) invoiceView.classList.add('active');

      pushNav('invoice', closeInvoicePage);

      // Auto-open link if supported
      if (invoiceData.url && tg?.openLink) {
        try { tg.openLink(invoiceData.url); } catch (e) {}
      }
    }

    function closeInvoicePage() {
      haptic('light');
      const invoiceView = document.getElementById('view-invoice');
      if (invoiceView) invoiceView.classList.remove('active');
      const walletView = document.getElementById('view-wallet');
      if (walletView) walletView.classList.add('active');

      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'invoice') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function openActiveInvoiceGateway() {
      if (!activeInvoiceUrl) return;
      haptic('light');
      if (tg?.openLink) {
        tg.openLink(activeInvoiceUrl);
      } else {
        window.open(activeInvoiceUrl, '_blank');
      }
    }

    function copyActiveInvoiceLink() {
      if (!activeInvoiceUrl) return;
      copyCredText(activeInvoiceUrl);
    }

    async function checkActiveInvoiceStatus() {
      if (!currentInvoiceData || !userId) return;
      haptic('light');
      const btn = document.getElementById('btn-check-invoice-status');
      const label = document.getElementById('label-check-invoice');
      if (btn) btn.disabled = true;
      if (label) label.innerText = (currentAppLanguage === 'ar') ? 'جاري التحقق من الفاتورة والرصيد...' : 'Checking payment status...';

      try {
        const res = await fetch('/api/invoice/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            invoice_id: currentInvoiceData.invoice_id,
            method: currentInvoiceData.provider || selectedRechargeMethod
          })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;

        if (d.is_paid || d.status === 'paid') {
          fireConfetti();
          haptic('success');
          const statusBadge = document.getElementById('invoice-status-badge');
          const statusText = document.getElementById('invoice-status-text');
          if (statusBadge) {
            statusBadge.style.background = 'rgba(16, 185, 129, 0.2)';
            statusBadge.style.color = '#10b981';
          }
          if (statusText) statusText.innerText = (currentAppLanguage === 'ar') ? '✅ تم استلام الدفع بنجاح!' : '✅ Payment Confirmed!';
          if (label) label.innerText = (currentAppLanguage === 'ar') ? '✅ تم تأكيد الدفع وإضافة الرصيد!' : '✅ Payment Confirmed!';
          showToast(d.message || (currentAppLanguage === 'ar' ? 'تم تأكيد الدفع وإضافة الرصيد بنجاح! 🎉' : 'Payment confirmed! Balance updated.'));
          loadUserData();
        } else {
          haptic('warning');
          if (label) label.innerText = (currentAppLanguage === 'ar') ? '🔄 إعادة فحص حالة الدفع' : '🔄 Check Again';
          showToast(currentAppLanguage === 'ar' ? 'الفاتورة بانتظار التحويل، لم يصل الدفع بعد. يرجى إتمام التحويل والمحاولة ثانية.' : 'Payment not confirmed yet. Please complete transfer and check again.');
          loadUserData();
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        if (label) label.innerText = (currentAppLanguage === 'ar') ? '🔄 إعادة المحاولة' : '🔄 Retry Check';
        showToast(currentAppLanguage === 'ar' ? 'تعذر التحقق من الفاتورة حالياً' : 'Network error checking invoice');
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

    // ==============================================
    // 👑 ADMIN CONTROL CENTER MODALS & API FUNCTIONS
    // ==============================================
    async function submitAdminUpdateSypRate() {
      const val = parseFloat(document.getElementById('admin-syp-rate-input')?.value);
      if (!val || val <= 0 || !userId) return;
      haptic('light');
      try {
        const res = await fetch('/api/admin/rate/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, syp_rate: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(`تم تحديث سعر صرف الليرة بنجاح (1$ = ${d.syp_rate} ل.س)`);
          loadUserData();
        } else {
          showToast('فشل تحديث سعر الصرف');
        }
      } catch (e) {
        showToast('خطأ في إرسال طلب التحديث');
      }
    }

    async function submitAdminUpdateReferralRate() {
      const val = parseFloat(document.getElementById('admin-ref-rate-input')?.value);
      if (val === undefined || val === null || isNaN(val) || !userId) return;
      haptic('light');
      try {
        const res = await fetch('/api/admin/referral-rate/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, referral_rate: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(`تم تعيين نسبة عمولة الإحالة: ${d.referral_rate}%`);
          loadUserData();
        }
      } catch (e) {
        showToast('فشل تحديث نسبة العمولة');
      }
    }

    // Admin Users Dedicated Page View
    let activeAdminUserFilter = 'all';
    let cachedAdminUsersList = [];
    let adminUserSearchTimer = null;

    function openAdminUsersPage() {
      haptic('pop');
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const view = document.getElementById('view-admin-users');
      if (view) view.classList.add('active');
      pushNav('admin_users', closeAdminUsersPage);
      executeAdminUserSearch();
    }

    function closeAdminUsersPage() {
      haptic('light');
      const view = document.getElementById('view-admin-users');
      if (view) view.classList.remove('active');
      const setView = document.getElementById('view-settings');
      if (setView) setView.classList.add('active');
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_users') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function setAdminUserFilter(filterKey) {
      haptic('light');
      activeAdminUserFilter = filterKey;
      ['all', 'balance', 'vip', 'banned'].forEach(f => {
        const btn = document.getElementById('admin-ufilter-' + f);
        if (btn) btn.classList.toggle('active', f === filterKey);
      });
      renderAdminUsersCards();
    }

    function debounceAdminUserSearch() {
      clearTimeout(adminUserSearchTimer);
      const q = (document.getElementById('admin-user-search-input')?.value || '').trim();
      const clearBtn = document.getElementById('admin-user-clear-btn');
      if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';
      adminUserSearchTimer = setTimeout(() => {
        executeAdminUserSearch();
      }, 350);
    }

    function clearAdminUserSearch() {
      const input = document.getElementById('admin-user-search-input');
      if (input) input.value = '';
      const clearBtn = document.getElementById('admin-user-clear-btn');
      if (clearBtn) clearBtn.style.display = 'none';
      executeAdminUserSearch();
    }

    async function executeAdminUserSearch() {
      const q = (document.getElementById('admin-user-search-input')?.value || '').trim();
      const container = document.getElementById('admin-users-results-list');
      if (container && !cachedAdminUsersList.length) {
        container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--hint);">جاري البحث في قاعدة البيانات...</div>';
      }
      try {
        const res = await fetch(`/api/admin/users?tg_id=${userId}&query=${encodeURIComponent(q)}`);
        const d = await res.json();
        cachedAdminUsersList = d.users || [];
        renderAdminUsersCards();
      } catch (e) {
        if (container) container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--danger);">خطأ في جلب المستخدمين.</div>';
      }
    }

    function renderAdminUsersCards() {
      const container = document.getElementById('admin-users-results-list');
      if (!container) return;

      let filtered = [...cachedAdminUsersList];
      if (activeAdminUserFilter === 'balance') {
        filtered = filtered.filter(u => u.balance > 0);
      } else if (activeAdminUserFilter === 'vip') {
        filtered = filtered.filter(u => (u.vip_discount > 0 || u.custom_discount_pct > 0));
      } else if (activeAdminUserFilter === 'banned') {
        filtered = filtered.filter(u => u.is_banned);
      }

      if (!filtered.length) {
        container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--hint);">لا يوجد مستخدمين مطابقين لهذا الفلتر.</div>';
        return;
      }

      container.innerHTML = filtered.map(u => {
        const initial = (u.username || 'U')[0].toUpperCase();
        const vipLabel = (u.custom_discount_pct !== null && u.custom_discount_pct !== undefined)
          ? `${u.custom_discount_pct}% مخصص`
          : (u.vip_discount > 0 ? `${u.vip_tier} (${u.vip_discount}%)` : 'Standard');

        return `
          <div class="inset-card" style="margin-bottom: 12px; padding: 14px; position: relative;">
            <!-- Top User Row: Avatar + Name + @username + Status badge ONLY if banned -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
              <div style="display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1;">
                <div class="avatar-fallback" style="width: 38px; height: 38px; font-size: 16px; flex-shrink: 0; background: linear-gradient(135deg, #0284c7, #6366f1);">
                  ${initial}
                </div>
                <div style="min-width: 0;">
                  <div style="font-size: 14px; font-weight: 800; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${u.username ? '@' + u.username : 'User #' + u.id}
                  </div>
                  <div style="display: flex; align-items: center; gap: 6px; margin-top: 1px; flex-wrap: wrap;">
                    <span style="font-size: 11px; color: var(--hint); font-family: monospace;">ID: ${u.telegram_id}</span>
                    <button class="btn-copy-mini" style="font-size: 9px; padding: 1px 6px;" onclick="copyCredText('${u.telegram_id}')">نسخ ID</button>
                    ${u.registered_at ? `<span style="font-size: 10px; color: var(--hint);">· ${u.registered_at}</span>` : ''}
                  </div>
                </div>
              </div>

              <!-- ONLY SHOW BADGE IF BANNED (NO ACTIVE BADGE SPAM) -->
              ${u.is_banned ? `
                <span class="pill-badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; font-size: 11px; flex-shrink: 0;">
                  🚫 محظور
                </span>
              ` : ''}
            </div>

            <!-- Metrics Row (Balance, Spent, VIP Tier) -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 8px 10px; margin-bottom: 12px; text-align: center;">
              <div>
                <div style="font-size: 10px; color: var(--hint);">الرصيد المتاح</div>
                <div style="font-size: 14px; font-weight: 800; color: ${u.balance > 0 ? 'var(--accent)' : 'var(--text)'};">
                  $${u.balance.toFixed(2)}
                </div>
              </div>
              <div>
                <div style="font-size: 10px; color: var(--hint);">المشتريات</div>
                <div style="font-size: 14px; font-weight: 800; color: var(--text);">
                  $${u.total_spent.toFixed(2)}
                </div>
              </div>
              <div>
                <div style="font-size: 10px; color: var(--hint);">الرتبة / الخصم</div>
                <div style="font-size: 12px; font-weight: 700; color: ${u.vip_discount > 0 ? 'var(--warning)' : 'var(--hint)'}; margin-top: 2px;">
                  ${vipLabel}
                </div>
              </div>
            </div>

            <!-- Quick Options & Settings UX Grid (High Usability) -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 6px;">
              <button class="btn-action-primary" onclick="openAdminBalanceModal(${u.telegram_id}, '${u.username || ''}', ${u.balance})" style="height: 38px; font-size: 12px;">
                💰 تعديل الرصيد
              </button>
              <button class="btn-action-secondary" onclick="openAdminDiscountModal(${u.telegram_id}, '${u.username || ''}', ${u.custom_discount_pct !== null && u.custom_discount_pct !== undefined ? u.custom_discount_pct : u.vip_discount})" style="height: 38px; font-size: 12px;">
                🏷️ تخصيص خصم %
              </button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;">
              <button class="btn-action-secondary" onclick="openAdminMessageModal(${u.telegram_id}, '${u.username || ''}')" style="height: 36px; font-size: 11px;">
                💬 مراسلة المستخدم
              </button>
              <button class="btn-action-secondary" style="height: 36px; font-size: 11px; color: ${u.is_banned ? '#10b981' : '#ef4444'};" onclick="submitToggleBan(${u.telegram_id})">
                ${u.is_banned ? '✅ فك الحظر' : '🚫 حظر الحساب'}
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // Admin Direct Message Modal
    function openAdminMessageModal(targetTgId, username) {
      haptic('pop');
      document.getElementById('admin-msg-target-tgid').value = targetTgId;
      document.getElementById('admin-msg-target-name').innerText = username ? '@' + username : `User (${targetTgId})`;
      document.getElementById('admin-msg-target-id').innerText = `ID: ${targetTgId}`;
      document.getElementById('admin-msg-text-input').value = '';
      document.getElementById('admin-message-user-modal').style.display = 'flex';
      pushNav('admin_msg_user', closeAdminMessageModal);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
    }

    function closeAdminMessageModal() {
      document.getElementById('admin-message-user-modal').style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_msg_user') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function submitAdminSendMessage() {
      const targetTgId = parseInt(document.getElementById('admin-msg-target-tgid')?.value);
      const msg = (document.getElementById('admin-msg-text-input')?.value || '').trim();
      if (!targetTgId || !msg) {
        showToast('يرجى كتابة نص الرسالة');
        return;
      }
      haptic('light');
      const btn = document.getElementById('btn-submit-send-user-msg');
      if (btn) btn.disabled = true;
      try {
        const res = await fetch('/api/admin/users/send-message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, target_tg_id: targetTgId, message: msg })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;
        if (d.status === 'ok') {
          haptic('success');
          showToast('تم إرسال الرسالة بنجاح للمستخدم!');
          closeAdminMessageModal();
        } else {
          showToast(d.error || 'فشل إرسال الرسالة');
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        showToast('خطأ في الاتصال أثناء الإرسال');
      }
    }

    let adminBalAction = 'add';

    function openAdminBalanceModal(targetTgId, username, currBal) {
      haptic('pop');
      document.getElementById('admin-bal-target-tgid').value = targetTgId;
      document.getElementById('admin-bal-user-name').innerText = username ? '@' + username : `User (${targetTgId})`;
      document.getElementById('admin-bal-user-id').innerText = `ID: ${targetTgId}`;
      document.getElementById('admin-bal-user-curr').innerText = `$${parseFloat(currBal || 0).toFixed(2)}`;
      document.getElementById('admin-bal-amount-input').value = '10.00';
      setAdminBalanceAction('add');
      document.getElementById('admin-balance-modal').style.display = 'flex';
      pushNav('admin_balance', closeAdminBalanceModal);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
    }

    function closeAdminBalanceModal() {
      document.getElementById('admin-balance-modal').style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_balance') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function setAdminBalanceAction(act) {
      haptic('light');
      adminBalAction = act;
      document.getElementById('admin-bal-btn-add').classList.toggle('active', act === 'add');
      document.getElementById('admin-bal-btn-deduct').classList.toggle('active', act === 'deduct');
      const submitBtn = document.getElementById('btn-submit-adjust-balance');
      if (submitBtn) {
        submitBtn.innerText = act === 'add' ? 'تأكيد إضافة الرصيد (+)' : 'تأكيد خصم الرصيد (-)';
      }
    }

    function setAdminBalAmount(amt) {
      haptic('light');
      document.getElementById('admin-bal-amount-input').value = amt.toFixed(2);
    }

    async function submitAdminAdjustBalance() {
      const targetTgId = parseInt(document.getElementById('admin-bal-target-tgid')?.value);
      const amt = parseFloat(document.getElementById('admin-bal-amount-input')?.value);
      if (!targetTgId || isNaN(amt) || amt <= 0) {
        showToast('يرجى إدخال مبلغ صحيح');
        return;
      }
      haptic('light');
      const btn = document.getElementById('btn-submit-adjust-balance');
      if (btn) btn.disabled = true;

      try {
        const res = await fetch('/api/admin/users/adjust-balance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            target_tg_id: targetTgId,
            amount: amt,
            action: adminBalAction
          })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;

        if (d.status === 'ok') {
          haptic('success');
          showToast(`تم تعديل الرصيد بنجاح! الرصيد الجديد: $${d.new_balance.toFixed(2)}`);
          closeAdminBalanceModal();
          executeAdminUserSearch();
          loadUserData();
        } else {
          showToast(d.error || 'فشل تعديل الرصيد');
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    // Admin Custom Discount Modal
    function openAdminDiscountModal(targetTgId, username, currentDisc) {
      haptic('pop');
      document.getElementById('admin-disc-target-tgid').value = targetTgId;
      document.getElementById('admin-disc-user-name').innerText = username ? '@' + username : `User (${targetTgId})`;
      document.getElementById('admin-disc-user-id').innerText = `ID: ${targetTgId}`;
      document.getElementById('admin-disc-input').value = (currentDisc !== null && currentDisc !== undefined) ? currentDisc : '';
      document.getElementById('admin-discount-modal').style.display = 'flex';
      pushNav('admin_discount', closeAdminDiscountModal);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
    }

    function closeAdminDiscountModal() {
      document.getElementById('admin-discount-modal').style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_discount') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }
    function setAdminDiscVal(val) {
      haptic('light');
      document.getElementById('admin-disc-input').value = val;
    }

    async function submitAdminDiscount() {
      const targetTgId = parseInt(document.getElementById('admin-disc-target-tgid')?.value);
      const discVal = parseFloat(document.getElementById('admin-disc-input')?.value);
      if (!targetTgId || isNaN(discVal) || discVal < 0 || discVal > 100) {
        showToast('يرجى إدخال نسبة خصم صحيحة بين 0 و 100');
        return;
      }
      haptic('light');
      try {
        const res = await fetch('/api/admin/users/set-discount', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, target_tg_id: targetTgId, discount_pct: discVal })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast('تم حفظ نسبة الخصم بنجاح!');
          closeAdminDiscountModal();
          executeAdminUserSearch();
        }
      } catch (e) {
        showToast('فشل حفظ نسبة الخصم');
      }
    }

    async function clearAdminDiscount() {
      const targetTgId = parseInt(document.getElementById('admin-disc-target-tgid')?.value);
      if (!targetTgId) return;
      haptic('light');
      try {
        const res = await fetch('/api/admin/users/set-discount', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, target_tg_id: targetTgId, discount_pct: null })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast('تم إلغاء الخصم المخصص');
          closeAdminDiscountModal();
          executeAdminUserSearch();
        }
      } catch (e) {
        showToast('فشل إلغاء الخصم');
      }
    }

    async function submitToggleBan(targetTgId) {
      try {
        const res = await fetch('/api/admin/users/toggle-ban', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, target_tg_id: targetTgId })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast(d.is_banned ? 'تم حظر المستخدم' : 'تم فك حظر المستخدم');
          executeAdminUserSearch();
        }
      } catch (e) {
        showToast('فشل تحديث حالة الحظر');
      }
    }


    // Admin Orders Modal
    function openAdminOrdersModal() {
      haptic('pop');
      document.getElementById('admin-orders-modal').style.display = 'flex';
      pushNav('admin_orders', closeAdminOrdersModal);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
      loadAdminOrders('all');
    }
    function closeAdminOrdersModal() {
      document.getElementById('admin-orders-modal').style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_orders') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function loadAdminOrders(status) {
      ['all', 'pending', 'completed', 'refunded'].forEach(t => {
        const btn = document.getElementById('admin-ord-tab-' + t);
        if (btn) btn.classList.toggle('active', (status === 'all' && t === 'all') || (status === 'pending_fulfillment' && t === 'pending') || (status === t));
      });
      const container = document.getElementById('admin-orders-results-list');
      container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--hint);">جاري تحميل الطلبات...</div>';
      try {
        const res = await fetch(`/api/admin/orders?tg_id=${userId}&status=${encodeURIComponent(status)}`);
        const d = await res.json();
        if (!d.orders || !d.orders.length) {
          container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--hint);">لا توجد طلبات مطابقة.</div>';
          return;
        }
        container.innerHTML = d.orders.map(o => `
          <div style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:14px;">طلب #${o.id} · ${o.username || 'tg:' + o.telegram_id}</strong>
              <span class="pill-badge" style="background:${o.status === 'completed' ? 'rgba(16,185,129,0.2); color:#10b981' : o.status === 'refunded' ? 'rgba(239,68,68,0.2); color:#ef4444' : 'rgba(245,158,11,0.2); color:#f59e0b'}; font-size:10px;">
                ${o.status}
              </span>
            </div>
            <div style="font-size:13px; font-weight:700; margin:4px 0;">${o.products}</div>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--hint);">
              <span>المبلغ: <strong style="color:var(--text);">$${o.total_sell.toFixed(2)}</strong></span>
              <span>التكلفة: $${o.cost_usd.toFixed(2)}</span>
              <span>ربح الهامش: <strong style="color:var(--success);">+$${o.margin.toFixed(2)}</strong></span>
            </div>
            ${o.goods && o.goods.length ? `
              <div style="background:var(--input-bg); border-radius:6px; padding:6px; margin-top:6px; font-family:monospace; font-size:11px; word-break:break-all;">
                ${o.goods.slice(0, 2).join('<br>')}
              </div>
            ` : ''}
            <div style="display:flex; gap:6px; margin-top:8px;">
              ${o.status !== 'completed' ? `<button class="admin-edit-badge-btn" onclick="submitAdminOrderStatus(${o.id}, 'completed')">تأكيد التسليم</button>` : ''}
              ${o.status !== 'refunded' ? `<button class="admin-edit-badge-btn" style="color:#ef4444;" onclick="submitAdminOrderStatus(${o.id}, 'refunded')">استرداد المبلغ للعميل</button>` : ''}
            </div>
          </div>
        `).join('');
      } catch (e) {
        container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--danger);">فشل جلب الطلبات.</div>';
      }
    }

    async function submitAdminOrderStatus(orderId, newStatus) {
      if (newStatus === 'refunded' && !confirm('هل أنت متأكد من استرداد قيمة الطلب إلى رصيد العميل؟')) return;
      try {
        const res = await fetch('/api/admin/orders/update-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, order_id: orderId, new_status: newStatus })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast(newStatus === 'refunded' ? 'تم استرداد المبلغ بنجاح!' : 'تم تحديث حالة الطلب!');
          loadAdminOrders('all');
        }
      } catch (e) {
        showToast('فشل تحديث الطلب');
      }
    }

    // Admin Coupons Modal
    function openAdminCouponsModal() {
      haptic('pop');
      document.getElementById('admin-coupons-modal').style.display = 'flex';
      pushNav('admin_coupons', closeAdminCouponsModal);
      if (tg?.disableVerticalSwipes) tg.disableVerticalSwipes();
      loadAdminCoupons();
    }
    function closeAdminCouponsModal() {
      document.getElementById('admin-coupons-modal').style.display = 'none';
      if (tg?.enableVerticalSwipes) tg.enableVerticalSwipes();
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_coupons') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function loadAdminCoupons() {
      const container = document.getElementById('admin-coupons-list');
      container.innerHTML = '<div style="text-align:center; padding:10px; color:var(--hint);">تحميل الكوبونات...</div>';
      try {
        const res = await fetch(`/api/admin/coupons?tg_id=${userId}`);
        const d = await res.json();
        if (!d.coupons || !d.coupons.length) {
          container.innerHTML = '<div style="text-align:center; padding:10px; color:var(--hint);">لا توجد كوبونات مسجلة.</div>';
          return;
        }
        container.innerHTML = d.coupons.map(c => `
          <div style="background:var(--card); border:1px solid var(--border); border-radius:8px; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="font-family:monospace; font-size:13px; color:var(--accent);">${c.code}</strong>
              <div style="font-size:11px; color:var(--hint);">
                ${c.type === 'percent' ? c.value + '%' : '$' + c.value} · الاستخدام: ${c.usage_count}/${c.usage_limit || '∞'}
              </div>
            </div>
            <button class="admin-edit-badge-btn" style="color:${c.is_active ? '#ef4444' : '#10b981'};" onclick="submitToggleCoupon(${c.id})">
              ${c.is_active ? 'تعطيل' : 'تفعيل'}
            </button>
          </div>
        `).join('');
      } catch (e) {
        container.innerHTML = '<div style="text-align:center; color:var(--danger);">خطأ في جلب الكوبونات.</div>';
      }
    }

    async function submitAdminCreateCoupon() {
      const code = (document.getElementById('admin-new-coupon-code')?.value || '').trim();
      const val = parseFloat(document.getElementById('admin-new-coupon-val')?.value || 0);
      const type = document.getElementById('admin-new-coupon-type')?.value;
      const limit = parseInt(document.getElementById('admin-new-coupon-limit')?.value || 100);
      if (!code || val <= 0) {
        showToast('يرجى إدخال كود صحيح وقيمة صالحة');
        return;
      }
      try {
        const res = await fetch('/api/admin/coupons/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, code: code, value: val, type: type, usage_limit: limit })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast(`تم إنشاء الكود ${d.coupon.code} بنجاح!`);
          document.getElementById('admin-new-coupon-code').value = '';
          document.getElementById('admin-new-coupon-val').value = '';
          loadAdminCoupons();
        }
      } catch (e) {
        showToast('فشل إنشاء الكوبون');
      }
    }

    async function submitToggleCoupon(couponId) {
      try {
        const res = await fetch('/api/admin/coupons/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, coupon_id: couponId })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast(d.is_active ? 'تم تفعيل الكوبون' : 'تم تعطيل الكوبون');
          loadAdminCoupons();
        }
      } catch (e) {
        showToast('فشل تحديث الكوبون');
      }
    }

    // Live Product Editor Modal
    function openAdminProductEditor(productId, e) {
      if (e) e.stopPropagation();
      const prod = allProducts.find(p => Number(p.id) === Number(productId));
      if (!prod) return;
      haptic('pop');
      document.getElementById('admin-edit-prod-id').value = prod.id;
      document.getElementById('admin-edit-prod-name').value = prod.clean_name || '';
      document.getElementById('admin-edit-prod-cat').value = prod.category || '';
      document.getElementById('admin-edit-prod-price').value = prod.price || '';
      document.getElementById('admin-edit-prod-stock').value = (prod.stock !== null && prod.stock !== undefined) ? prod.stock : '';
      document.getElementById('admin-edit-prod-hidden').checked = !!prod.hidden;
      document.getElementById('admin-product-modal').style.display = 'flex';
    }
    function closeAdminProductModal() {
      document.getElementById('admin-product-modal').style.display = 'none';
    }

    async function submitAdminProductUpdate() {
      const pid = parseInt(document.getElementById('admin-edit-prod-id')?.value);
      if (!pid) return;
      const customName = document.getElementById('admin-edit-prod-name')?.value;
      const cat = document.getElementById('admin-edit-prod-cat')?.value;
      const price = parseFloat(document.getElementById('admin-edit-prod-price')?.value);
      const stockStr = document.getElementById('admin-edit-prod-stock')?.value;
      const hidden = document.getElementById('admin-edit-prod-hidden')?.checked;

      haptic('light');
      try {
        const res = await fetch('/api/admin/product/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            product_id: pid,
            custom_name: customName,
            category: cat,
            sell_price_usd: isNaN(price) ? null : price,
            stock: stockStr === '' ? null : parseInt(stockStr),
            hidden: hidden
          })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast('تم تحديث بيانات المنتج بنجاح!');
          closeAdminProductModal();
          await fetchCatalogData();
        } else {
          showToast('فشل تحديث المنتج');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    // Live Category Editor Modal
    function openAdminCategoryEditor(categoryId, catName, e) {
      if (e) e.stopPropagation();
      let cat = categoriesList.find(c => (typeof c === 'object' ? c.id : null) === categoryId);
      if (!cat) {
        cat = categoriesList.find(c => (typeof c === 'object' ? c.name : c) === catName);
      }
      haptic('pop');
      document.getElementById('admin-edit-cat-id').value = (cat && typeof cat === 'object') ? cat.id : categoryId;
      document.getElementById('admin-edit-cat-ar').value = (cat && typeof cat === 'object') ? (cat.name_ar || '') : (catName || '');
      document.getElementById('admin-edit-cat-en').value = (cat && typeof cat === 'object') ? (cat.name_en || '') : (catName || '');
      document.getElementById('admin-edit-cat-img').value = (cat && typeof cat === 'object') ? (cat.image_url || '') : '';
      document.getElementById('admin-edit-cat-prev-ar').value = (cat && typeof cat === 'object') ? (cat.preview_ar || '') : '';
      document.getElementById('admin-edit-cat-prev-en').value = (cat && typeof cat === 'object') ? (cat.preview_en || '') : '';
      document.getElementById('admin-edit-cat-sort').value = (cat && typeof cat === 'object') ? (cat.sort_order || 1) : 1;
      document.getElementById('admin-edit-cat-hidden').checked = (cat && typeof cat === 'object') ? !!cat.hidden : false;
      document.getElementById('admin-category-modal').style.display = 'flex';
    }
    function closeAdminCategoryModal() {
      document.getElementById('admin-category-modal').style.display = 'none';
    }

    async function submitAdminCategoryUpdate() {
      const cid = parseInt(document.getElementById('admin-edit-cat-id')?.value);
      if (!cid) return;
      const nameAr = document.getElementById('admin-edit-cat-ar')?.value;
      const nameEn = document.getElementById('admin-edit-cat-en')?.value;
      const img = document.getElementById('admin-edit-cat-img')?.value;
      const prevAr = document.getElementById('admin-edit-cat-prev-ar')?.value;
      const prevEn = document.getElementById('admin-edit-cat-prev-en')?.value;
      const sort = parseInt(document.getElementById('admin-edit-cat-sort')?.value || 1);
      const hidden = document.getElementById('admin-edit-cat-hidden')?.checked;

      haptic('light');
      try {
        const res = await fetch('/api/admin/category/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            category_id: cid,
            name_ar: nameAr,
            name_en: nameEn,
            image_url: img,
            preview_ar: prevAr,
            preview_en: prevEn,
            sort_order: sort,
            hidden: hidden
          })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          showToast('تم تحديث بيانات التصنيف بنجاح!');
          closeAdminCategoryModal();
          await fetchCatalogData();
        } else {
          showToast('فشل تحديث التصنيف');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    function openFullSqlAdmin() {
      haptic('light');
      if (tg?.openLink) {
        tg.openLink('https://bot.gh-store.me/admin');
      } else {
        window.open('/admin', '_blank');
      }
    }

    function copyUserId() {
      if (!userId) return;
      copyCredText(String(userId));
    }

    function openCustomerSupportChat() {
      haptic('light');
      const botUser = userData?.bot_username || 'demo_aiogramshopbot';
      const link = `https://t.me/${botUser}?start=support`;
      if (tg?.openTelegramLink) tg.openTelegramLink(link);
      else window.open(link, '_blank');
    }

    function openOfficialChannel() {
      haptic('light');
      const botUser = userData?.bot_username || 'demo_aiogramshopbot';
      const link = `https://t.me/${botUser}`;
      if (tg?.openTelegramLink) tg.openTelegramLink(link);
      else window.open(link, '_blank');
    }

    async function submitAdminUpdateMargin() {
      const val = parseFloat(document.getElementById('admin-margin-input')?.value || 20);
      haptic('light');
      try {
        const res = await fetch('/api/admin/margin/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, margin_percent: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? `تم تحديث نسبة الهامش إلى ${d.margin_percent}% بنجاح!` : `Margin updated to ${d.margin_percent}%!`);
        } else {
          showToast('فشل تحديث نسبة الهامش');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    async function submitAdminUpdateStarsRate() {
      const val = parseFloat(document.getElementById('admin-stars-rate-input')?.value || 0.01);
      haptic('light');
      try {
        const res = await fetch('/api/admin/stars-rate/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, stars_rate: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? `تم تحديث سعر النجوم إلى $${d.stars_rate} بنجاح!` : `Stars rate updated to $${d.stars_rate}!`);
        } else {
          showToast('فشل تحديث سعر النجوم');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    async function submitAdminUpdateAnnouncement() {
      const val = (document.getElementById('admin-announcement-input')?.value || '').trim();
      haptic('light');
      try {
        const res = await fetch('/api/admin/announcement/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, announcement: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? 'تم تحديث شريط الإعلانات العام بنجاح!' : 'Announcement updated successfully!');
        } else {
          showToast('فشل نشر الإعلان');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم');
      }
    }

    async function submitAdminCatalogSync() {
      const btn = document.getElementById('btn-force-sync-catalog');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ جاري مزامنة الكتالوج من المورد...</span>`;
      }
      haptic('light');
      try {
        const res = await fetch('/api/admin/catalog/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId })
        });
        const d = await res.json();
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<span>🔄 مزامنة الكتالوج والأسعار من المورد فورياً</span>`;
        }
        if (d.status === 'ok') {
          fireConfetti();
          haptic('success');
          showToast(d.message || 'تمت مزامنة الكتالوج بنجاح!');
          await fetchCatalogData();
        } else {
          showToast('فشلت المزامنة من المورد');
        }
      } catch (e) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<span>🔄 مزامنة الكتالوج والأسعار من المورد فورياً</span>`;
        }
        showToast('خطأ في الاتصال أثناء المزامنة');
      }
    }

    // Admin Auto-Refund Toggle & Stuck Orders Management
    let isAutoRefundEnabled = false;

    async function submitAdminToggleAutoRefund() {
      haptic('light');
      try {
        const res = await fetch('/api/admin/autorefund/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          isAutoRefundEnabled = d.autorefund_enabled;
          updateAutoRefundBtnUI();
          showToast(isAutoRefundEnabled ? 'تم تفعيل نظام الاسترداد التلقائي!' : 'تم تعطيل الاسترداد التلقائي (الوضع اليدوي نشط)');
        }
      } catch (e) {
        showToast('فشل تبديل إعداد الاسترداد');
      }
    }

    function updateAutoRefundBtnUI() {
      const btn = document.getElementById('admin-autorefund-toggle-btn');
      if (btn) {
        btn.innerText = isAutoRefundEnabled ? 'مفعل تلقائياً' : 'معطل (يدوي)';
        btn.style.color = isAutoRefundEnabled ? '#10b981' : '#f59e0b';
      }
    }

    function openAdminStuckOrdersPage() {
      haptic('pop');
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const view = document.getElementById('view-admin-stuck');
      if (view) view.classList.add('active');
      pushNav('admin_stuck', closeAdminStuckOrdersPage);
      loadAdminStuckOrders();
    }

    function closeAdminStuckOrdersPage() {
      haptic('light');
      const view = document.getElementById('view-admin-stuck');
      if (view) view.classList.remove('active');
      const setView = document.getElementById('view-settings');
      if (setView) setView.classList.add('active');
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_stuck') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function loadAdminStuckOrders() {
      const container = document.getElementById('admin-stuck-orders-list');
      if (container) container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--hint);">جاري فحص العمليات والطلبات العالقة...</div>';
      try {
        const res = await fetch(`/api/admin/stuck-orders?tg_id=${userId}`);
        const d = await res.json();
        const orders = d.stuck_orders || [];
        const countBadge = document.getElementById('admin-stuck-count-badge');
        if (countBadge) {
          countBadge.innerText = orders.length;
          countBadge.style.display = orders.length > 0 ? 'inline-block' : 'none';
        }

        if (!orders.length) {
          if (container) container.innerHTML = '<div style="text-align:center; padding:40px 16px; color:var(--success); font-weight:700;">✅ ممتاز! لا توجد أي طلبات أو مبالغ معلقة حالياً.</div>';
          return;
        }

        if (container) {
          container.innerHTML = orders.map(o => `
            <div class="inset-card" style="margin-bottom: 12px; padding: 14px; border-color: rgba(245,158,11,0.4);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                  <strong style="font-size: 14px; color: var(--text);">طلب #${o.id} · ${o.username ? '@' + o.username : 'User ' + o.telegram_id}</strong>
                  <div style="font-size: 11px; color: var(--hint); font-family: monospace; margin-top: 2px;">ID: ${o.telegram_id} · ${o.created_at}</div>
                </div>
                <span class="pill-badge" style="background: rgba(245,158,11,0.2); color: #f59e0b; font-size: 10px;">
                  ⏳ معلق / قيد التفعيل
                </span>
              </div>

              <div style="font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 6px;">${o.products}</div>
              <div style="font-size: 14px; color: var(--accent); font-weight: 800; margin-bottom: 12px;">المبلغ المعلق: $${o.total_sell.toFixed(2)} USD</div>

              <div style="display: flex; gap: 8px;">
                <button class="btn-action-primary" onclick="executeAdminRefundStuck(${o.id}, ${o.total_sell})" style="flex: 2; height: 38px; font-size: 12px; background: linear-gradient(135deg, #ef4444, #dc2626);">
                  💸 استرداد الرصيد للعميل ($${o.total_sell.toFixed(2)})
                </button>
                <button class="btn-action-secondary" onclick="openAdminMessageModal(${o.telegram_id}, '${o.username || ''}')" style="flex: 1; height: 38px; font-size: 12px;">
                  💬 مراسلة
                </button>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        if (container) container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--danger);">خطأ في جلب العمليات المعلقة.</div>';
      }
    }

    async function executeAdminRefundStuck(orderId, amount) {
      if (!confirm(`هل أنت متأكد من رغبتك في استرداد مبلغ $${amount.toFixed(2)} لحساب العميل فورياً؟`)) return;
      haptic('medium');
      try {
        const res = await fetch('/api/admin/stuck-orders/refund', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, order_id: orderId })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          fireConfetti();
          haptic('success');
          showToast(`تم استرداد مبلغ $${d.refunded_amount.toFixed(2)} لحساب العميل بنجاح!`);
          loadAdminStuckOrders();
          loadUserData();
        } else {
          showToast(d.error || 'فشل الاسترداد');
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم أثناء الاسترداد');
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
        if (d.store_logo_url) applyStoreLogo(d.store_logo_url);
        updateBalancePills();

        // Check & Render Admin Control Center in Settings
        const adminCenterCard = document.getElementById('admin-control-center-card');
        if (adminCenterCard) {
          if (d.is_admin) {
            adminCenterCard.style.display = 'block';
            if (d.admin_stats) {
              const setText = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
              setText('admin-stat-revenue', `$${d.admin_stats.total_revenue.toFixed(2)}`);
              setText('admin-stat-balances', `$${d.admin_stats.total_users_balance.toFixed(2)}`);
              setText('admin-stat-users', String(d.admin_stats.total_users_count));
              setText('admin-stat-orders', String(d.admin_stats.total_orders_count));

              const sypInput = document.getElementById('admin-syp-rate-input');
              if (sypInput && !sypInput.value) sypInput.value = d.admin_stats.syp_usd_rate || 15000;

              const refInput = document.getElementById('admin-ref-rate-input');
              if (refInput && !refInput.value) refInput.value = d.admin_stats.referral_commission_percent || 0.2;
            }
              const logoInput = document.getElementById('admin-store-logo-input');
              if (logoInput && !logoInput.value && d.store_logo_url) logoInput.value = d.store_logo_url;
              const marginInput = document.getElementById('admin-margin-input');
              if (marginInput && !marginInput.value && d.admin_stats.global_margin_percent) {
                marginInput.value = d.admin_stats.global_margin_percent;
              }

              const starsRateInput = document.getElementById('admin-stars-rate-input');
              if (starsRateInput && !starsRateInput.value && d.admin_stats.stars_to_usd_rate) {
                starsRateInput.value = d.admin_stats.stars_to_usd_rate;
              }

              const announceInput = document.getElementById('admin-announcement-input');
              if (announceInput && !announceInput.value && d.admin_stats.store_announcement) {
                announceInput.value = d.admin_stats.store_announcement;
              }
          } else {
            adminCenterCard.style.display = 'none';
              if (d.admin_stats) {
                isAutoRefundEnabled = !!d.admin_stats.autorefund_enabled;
                updateAutoRefundBtnUI();
              }
          }
        }

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

        renderUnifiedActivity();
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

      const cardBal = document.getElementById('settings-card-balance');
      const cardSpent = document.getElementById('settings-card-spent');
      if (cardBal) cardBal.innerText = `$${userData.balance.toFixed(2)}`;
      if (cardSpent) cardSpent.innerText = `$${(userData.total_spent || 0).toFixed(2)}`;

      const topVipTag = document.getElementById('top-vip-tag');
      if (userData.vip_discount > 0 && userData.vip_tier && userData.vip_tier !== 'Standard') {
        topVipTag.innerText = userData.vip_tier;
        topVipTag.style.display = 'inline-block';
      } else {
        topVipTag.style.display = 'none';
      }
    }

    // One-Time Admin Config with Pen Button Edit / Lock Mechanism
    let cachedAdminConfigs = [];
    let activeEditingKey = null;

    function openAdminConfigPage() {
      haptic('pop');
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const view = document.getElementById('view-admin-config');
      if (view) view.classList.add('active');
      pushNav('admin_config', closeAdminConfigPage);
      loadAdminConfigs();
    }

    function closeAdminConfigPage() {
      haptic('light');
      activeEditingKey = null;
      const view = document.getElementById('view-admin-config');
      if (view) view.classList.remove('active');
      const setView = document.getElementById('view-settings');
      if (setView) setView.classList.add('active');
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_config') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function loadAdminConfigs() {
      const container = document.getElementById('admin-config-items-list');
      if (container && !cachedAdminConfigs.length) {
        container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--hint);">جاري تحميل الإعدادات من الخادم...</div>';
      }
      try {
        const res = await fetch(`/api/admin/config/all?tg_id=${userId}`);
        const d = await res.json();
        cachedAdminConfigs = d.configs || [];
        renderAdminConfigCards();
      } catch (e) {
        if (container) container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--danger);">خطأ في جلب الإعدادات.</div>';
      }
    }

    function renderAdminConfigCards() {
      const container = document.getElementById('admin-config-items-list');
      if (!container) return;

      if (!cachedAdminConfigs.length) {
        container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--hint);">لا توجد إعدادات مسجلة.</div>';
        return;
      }

      container.innerHTML = cachedAdminConfigs.map(c => {
        const isEditing = (activeEditingKey === c.key);
        const inputType = c.secret && !isEditing ? 'password' : 'text';

        return `
          <div class="inset-card" style="margin-bottom: 10px; padding: 12px; border-color: ${isEditing ? 'var(--accent)' : 'var(--border)'}; transition: border-color 0.2s;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <strong style="font-family: monospace; font-size: 13px; color: var(--accent);">${c.key}</strong>
              <span class="pill-badge" style="font-size: 10px; background: rgba(255,255,255,0.06);">
                ${c.secret ? '🔒 سري' : '⚙️ نظام'}
              </span>
            </div>
            <div style="font-size: 11px; color: var(--hint); margin-bottom: 8px; line-height: 1.4;">
              ${c.desc || 'إعداد نظام'}
            </div>

            <!-- Input Row with Pen Button -->
            <div style="display: flex; gap: 8px; align-items: center;">
              <input type="${inputType}"
                     class="admin-text-input"
                     id="cfg-input-${c.key}"
                     value="${c.value || ''}"
                     ${isEditing ? '' : 'readonly'}
                     style="flex: 1; font-family: monospace; font-size: 13px; background: var(--input-bg); border-color: ${isEditing ? 'var(--accent)' : 'var(--border)'}; color: var(--text); opacity: ${isEditing ? '1' : '0.85'}; outline: none;"
                     placeholder="غير محدد (فارغ)">

              <div id="cfg-actions-${c.key}" style="display: flex; gap: 4px;">
                ${isEditing ? `
                  <button class="btn-action-primary" onclick="submitSaveConfigKey('${c.key}')" style="height: 36px; padding: 0 12px; font-size: 11px; background: #10b981;">
                    💾 حفظ
                  </button>
                  <button class="circle-icon-btn" onclick="cancelConfigEditMode('${c.key}')" title="إلغاء">
                    ✕
                  </button>
                ` : `
                  <button class="circle-icon-btn" onclick="enableConfigEditMode('${c.key}')" title="تعديل الإعداد (انقر على القلم)">
                    ✏️
                  </button>
                `}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function enableConfigEditMode(key) {
      haptic('light');
      activeEditingKey = key;
      renderAdminConfigCards();
      setTimeout(() => {
        const inp = document.getElementById('cfg-input-' + key);
        if (inp) {
          inp.focus();
          inp.select();
        }
      }, 50);
    }

    function cancelConfigEditMode(key) {
      haptic('light');
      activeEditingKey = null;
      renderAdminConfigCards();
    }

    async function submitSaveConfigKey(key) {
      const inp = document.getElementById('cfg-input-' + key);
      const newVal = inp ? inp.value.trim() : '';
      haptic('medium');

      const actionBox = document.getElementById('cfg-actions-' + key);
      if (actionBox) actionBox.innerHTML = '<span style="font-size:11px; color:var(--hint);">جاري الحفظ...</span>';

      try {
        const res = await fetch('/api/admin/config/set', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, key: key, value: newVal })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(`تم حفظ الإعداد ${key} بنجاح!`);
          activeEditingKey = null;
          const target = cachedAdminConfigs.find(c => c.key === key);
          if (target) target.value = newVal;
          renderAdminConfigCards();
        } else {
          showToast('فشل حفظ الإعداد');
          renderAdminConfigCards();
        }
      } catch (e) {
        showToast('خطأ في الاتصال بالخادم أثناء الحفظ');
        renderAdminConfigCards();
      }
    }

    function renderEmptyOrders() {
      const container = document.getElementById('orders-container-box');
      if (!container) return;
      const d = I18N[currentAppLanguage] || I18N.ar;
      container.innerHTML = `
        <div style="text-align: center; padding: 40px 16px; color: var(--hint);">
          <div style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 4px;">${d.orders_empty_title}</div>
          <p style="font-size: 13px; margin-bottom: 16px;">${d.orders_empty_sub}</p>
          <button class="btn-action-primary" onclick="switchTab('store')" style="width: auto; padding: 0 24px; margin: 0 auto; height: 42px;">${d.browse_store}</button>
        </div>
      `;
    }

    let activeActivityFilter = 'all';

    function filterActivityView(filterKey) {
      haptic('pop');
      activeActivityFilter = filterKey;
      ['all', 'orders', 'recharges'].forEach(f => {
        const btn = document.getElementById('act-filter-' + f);
        if (btn) btn.classList.toggle('active', f === filterKey);
      });
      renderUnifiedActivity();
    }

    function openExternalPaymentUrl(url) {
      haptic('light');
      if (tg?.openLink) tg.openLink(url);
      else window.open(url, '_blank');
    }

    function renderUnifiedActivity() {
      const container = document.getElementById('orders-container-box');
      if (!container) return;

      const rawOrders = (userData?.orders || []).map(o => ({ ...o, type: 'order' }));
      const rawRecharges = (userData?.recharges || []).map(r => ({ ...r, type: 'recharge' }));

      let combined = [...rawOrders, ...rawRecharges];
      combined.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));

      if (activeActivityFilter === 'orders') {
        combined = combined.filter(it => it.type === 'order');
      } else if (activeActivityFilter === 'recharges') {
        combined = combined.filter(it => it.type === 'recharge');
      }

      if (!combined.length) {
        renderEmptyOrders();
        return;
      }

      const d = I18N[currentAppLanguage] || I18N.ar;

      container.innerHTML = combined.map(it => {
        if (it.type === 'order') {
          return `
            <div class="inset-card" style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-size: 14px;">🛍️</span>
                  <strong style="font-size: 14px;">طلب #${it.id} · ${it.created_at || ''}</strong>
                </div>
                <span class="pill-badge" style="background: ${it.status === 'completed' ? 'rgba(16,185,129,0.2); color:#10b981' : it.status === 'refunded' ? 'rgba(239,68,68,0.2); color:#ef4444' : 'rgba(245,158,11,0.2); color:#f59e0b'}; font-size:11px;">
                  ${it.status === 'completed' ? 'مكتمل' : (it.status === 'refunded' ? 'مسترجع' : it.status)}
                </span>
              </div>
              <div style="font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 2px;">${it.products}</div>
              <div style="font-size: 13px; color: var(--accent); font-weight: 700; margin-bottom: 8px;">${d.total}: ${it.total.toFixed(2)}${it.sym}</div>

              <!-- Timeline Stepper -->
              <div class="timeline-box">
                <div class="timeline-track"></div>
                <div class="timeline-node">
                  <div class="node-circle done">✓</div>
                  <div class="node-label">${d.step_placed}</div>
                </div>
                <div class="timeline-node">
                  <div class="node-circle ${it.status.includes('completed') ? 'done' : 'active'}">${it.status.includes('completed') ? '✓' : '●'}</div>
                  <div class="node-label">${d.step_processing}</div>
                </div>
                <div class="timeline-node">
                  <div class="node-circle ${it.status.includes('completed') ? 'done' : ''}">${it.status.includes('completed') ? '✓' : '○'}</div>
                  <div class="node-label">${d.step_delivered}</div>
                </div>
              </div>

              <!-- Structured Credentials -->
              ${renderStructuredCredentials(it.goods)}

              <div style="display: flex; gap: 8px; align-items: center; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px; flex-wrap: wrap;">
                ${it.warranty_days ? `
                  <span class="pill-badge" style="background: rgba(56,189,248,0.15); color: var(--accent); font-size: 11px;">🛡️ ${currentAppLanguage === 'ar' ? `ضمان ${it.warranty_days} يوم` : `${it.warranty_days}d Warranty`}</span>
                ` : ''}
                ${it.warranty_days && !it.warranty_claimed && it.status === 'completed' ? `
                  <button class="btn-action-secondary" onclick="claimOrderWarranty(${it.id})" style="height: 36px; font-size: 11px; padding: 0 12px;">${d.claim_warranty}</button>
                ` : ''}
                <button class="btn-action-secondary" onclick="openOrderSupport(${it.id})" style="flex: 1; height: 36px; font-size: 11px; min-width: 140px;">💬 ${currentAppLanguage === 'ar' ? 'تواصل مع الدعم' : 'Contact Support'}</button>
              </div>
            </div>
          `;
        }

        // Render Recharge Transaction Card
        const isPaid = (it.status === 'completed');
        const isPending = (it.status === 'pending');

        let methodLogo = '💳';
        let methodTitle = 'شحن رصيد';
        if (it.method === 'shamcash') {
          methodLogo = '<img src="https://shamcash.sy/_next/static/media/logo.5be69def.svg" style="width:20px; height:20px; object-fit:contain;" alt="ShamCash">';
          methodTitle = 'شام كاش (Sham Cash)';
        } else if (it.method === 'syriatelcash') {
          methodLogo = '<img src="https://www.syriatel.sy/assets/img/logo.png" style="width:20px; height:20px; object-fit:contain;" alt="Syriatel">';
          methodTitle = 'سيرياتيل كاش (Syriatel Cash)';
        } else if (it.method === 'stars') {
          methodLogo = '⭐';
          methodTitle = 'نجوم تيليجرام (Telegram Stars)';
        } else if (it.method === 'crypto') {
          methodLogo = '🪙';
          methodTitle = 'العملات الرقمية (Crypto)';
        }

        const localPart = (it.currency === 'SYP' && it.invoice_amount)
          ? ` <span style="font-size:11px; color:var(--hint);">(≈ ${Math.round(it.invoice_amount).toLocaleString()} ل.س)</span>`
          : '';

        return `
          <div class="inset-card" style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: flex; align-items: center;">${methodLogo}</span>
                <strong style="font-size: 13px;">${methodTitle}</strong>
              </div>
              <span class="pill-badge" style="background: ${isPaid ? 'rgba(16,185,129,0.2); color:#10b981' : isPending ? 'rgba(245,158,11,0.2); color:#f59e0b' : 'rgba(239,68,68,0.2); color:#ef4444'}; font-size:11px;">
                ${isPaid ? '✅ تم الشحن بنجاح' : (isPending ? '⏳ بانتظار الدفع' : '❌ ملغية / منتهية')}
              </span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 6px;">
              <span>المبلغ: <strong style="color:var(--success); font-size:15px;">+$${it.amount_usd.toFixed(2)}</strong>${localPart}</span>
              <span style="font-size: 11px; color: var(--hint); font-family: monospace;">${it.invoice_id ? '#' + it.invoice_id.substring(0, 12) : ''}</span>
            </div>

            <div style="font-size: 11px; color: var(--hint);">${it.created_at || ''}</div>

            ${isPending ? `
              <div style="display: flex; gap: 8px; margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px;">
                ${it.payment_url ? `
                  <button class="btn-action-primary" onclick="openExternalPaymentUrl('${it.payment_url}')" style="flex: 1; height: 36px; font-size: 11px;">
                    🌐 إتمام الدفع
                  </button>
                ` : ''}
                <button class="btn-action-secondary" onclick="openInvoicePage({ invoice_id: '${it.invoice_id}', url: '${it.payment_url || ''}', provider: '${it.method}', amount: ${it.amount_usd}, invoice_amount: ${it.invoice_amount || 0}, currency: '${it.currency}' })" style="flex: 1; height: 36px; font-size: 11px;">
                  🔄 فحص الفاتورة
                </button>
              </div>
            ` : ''}
          </div>
        `;
      }).join('');
    }
    function copyCredText(text) {
      haptic('success');
      if (navigator?.clipboard?.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          showToast(currentAppLanguage === 'ar' ? 'تم النسخ بنجاح!' : 'Copied successfully!');
        }).catch(() => fallbackCopy(text));
      } else {
        fallbackCopy(text);
      }
    }

    function fallbackCopy(text) {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast(currentAppLanguage === 'ar' ? 'تم النسخ بنجاح!' : 'Copied successfully!');
    }

    function openOrderSupport(orderId) {
      haptic('light');
      const botUser = userData?.bot_username || 'demo_aiogramshopbot';
      const link = `https://t.me/${botUser}?start=support_order_${orderId}`;
      if (tg?.openTelegramLink) tg.openTelegramLink(link);
      else window.open(link, '_blank');
    }

    function copyReferralLink() {
      const link = document.getElementById('referral-link-display').innerText;
      navigator.clipboard.writeText(link).then(() => {
        showToast(currentAppLanguage === 'ar' ? 'تم نسخ رابط الإحالة!' : 'Referral link copied!');
      });
    }

    async function selectDisplayCurrency(code) {
      haptic('light');
      const btnUsd = document.getElementById('curr-chip-usd');
      const btnSyp = document.getElementById('curr-chip-syp');
      if (btnUsd) btnUsd.classList.toggle('active', code === 'USD');
      if (btnSyp) btnSyp.classList.toggle('active', code === 'SYP');
      if (userData) userData.currency_preference = code;
      updateBalancePills();
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
      const sel = document.getElementById('language-select-dropdown');
      if (sel) sel.value = code;
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, language: code })
        });
        const langNames = { ar: 'العربية', en: 'English', de: 'Deutsch', es: 'Español', fr: 'Français', it: 'Italiano', zh: '中文' };
        showToast(`تم تعيين لغة التطبيق إلى ${langNames[code] || code}!`);
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
    initCart();
    loadFromCache();
    initSSE();
    checkHomeScreenCapability();
  </script>
</body>
</html>
"""
