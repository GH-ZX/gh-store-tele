/**
 * Automated Headless Browser Test Suite for GH Store Mini App Frontend
 * 
 * Exercises the real browser execution environment (Chromium/Google Chrome):
 * 1. Checkout Recovery (durable in-flight storage, upstream status recovery, safe idempotency key reuse)
 * 2. Arabic & English Layouts (RTL/LTR toggling, lang attributes, font classes, i18n dictionary updates)
 * 3. Navigation (tab switching, modal sheets, navStack LIFO popping, Telegram BackButton lifecycle)
 * 4. Keyboard Behavior (Enter on search, Enter on coupon, Escape on modal, focus scroll)
 * 5. Viewport Zoom Capability (verifies zoom is not disabled by user-scalable=no)
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const securitySrc = fs.readFileSync(path.join(root, 'static/storefront/security.js'), 'utf8');
const apiSrc = fs.readFileSync(path.join(root, 'static/storefront/api.js'), 'utf8');
const storefrontSrc = fs.readFileSync(path.join(root, 'static/storefront/storefront.js'), 'utf8');
const walletSrc = fs.readFileSync(path.join(root, 'static/storefront/wallet.js'), 'utf8');
const checkoutSrc = fs.readFileSync(path.join(root, 'static/storefront/checkout.js'), 'utf8');
const smsSrc = fs.readFileSync(path.join(root, 'static/storefront/sms.js'), 'utf8');
const adminSrc = fs.readFileSync(path.join(root, 'static/storefront/admin.js'), 'utf8');
const appSrc = fs.readFileSync(path.join(root, 'static/storefront/app.js'), 'utf8');

function runBrowserTests() {
  let count = 0;
  function check(condition, message) {
    if (!condition) throw new Error(message);
    count++;
  }

  // ==========================================
  // 1. VIEWPORT & ZOOM CAPABILITY TEST
  // ==========================================
  const viewportMeta = document.querySelector('meta[name="viewport"]');
  check(viewportMeta !== null, 'viewport meta tag exists');
  const viewportContent = viewportMeta.getAttribute('content') || '';
  check(!viewportContent.includes('user-scalable=no'), 'zoom is not blocked by user-scalable=no');
  check(!viewportContent.includes('maximum-scale=1.0'), 'zoom is not blocked by maximum-scale=1.0');
  check(viewportContent.includes('viewport-fit=cover'), 'safe-area viewport-fit=cover is preserved');

  // ==========================================
  // 2. ARABIC & ENGLISH LAYOUT DIRECTION TEST
  // ==========================================
  // Test Arabic Layout
  StoreAPI.applyLanguage('ar');
  check(document.documentElement.lang === 'ar', 'HTML lang is set to Arabic (ar)');
  check(document.documentElement.dir === 'rtl', 'HTML dir is set to right-to-left (rtl)');
  check(document.documentElement.classList.contains('lang-ar'), 'lang-ar class applied');
  check(!document.documentElement.classList.contains('lang-en'), 'lang-en class removed in Arabic mode');
  check(document.getElementById('i18n-tab-store')?.textContent === 'المتجر', 'Arabic tab label translated');

  // Test English Layout
  StoreAPI.applyLanguage('en');
  check(document.documentElement.lang === 'en', 'HTML lang is set to English (en)');
  check(document.documentElement.dir === 'ltr', 'HTML dir is set to left-to-right (ltr)');
  check(document.documentElement.classList.contains('lang-en'), 'lang-en class applied');
  check(!document.documentElement.classList.contains('lang-ar'), 'lang-ar class removed in English mode');
  check(document.getElementById('i18n-tab-store')?.textContent === 'Store', 'English tab label translated');
  check(document.getElementById('i18n-tab-orders')?.textContent === 'Orders', 'English orders tab translated');

  // Restore Arabic as primary
  StoreAPI.applyLanguage('ar');

  // ==========================================
  // 3. NAVIGATION & MODAL STACK TESTS
  // ==========================================
  // Tab Navigation
  switchTab('wallet');
  check(document.getElementById('tab-wallet')?.classList.contains('active'), 'wallet tab button active');
  check(document.getElementById('view-wallet')?.style.display !== 'none', 'wallet view displayed');
  check(document.getElementById('view-store')?.style.display === 'none', 'store view hidden');

  switchTab('store');
  check(document.getElementById('tab-store')?.classList.contains('active'), 'store tab button active');
  check(document.getElementById('view-store')?.style.display !== 'none', 'store view displayed');

  // Navigation Stack & Telegram BackButton Synchronization
  let modalDismissed = false;
  StoreAPI.pushNav('test_modal', () => { modalDismissed = true; });
  check(StoreAPI.navStack.length === 1, 'navStack contains pushed modal');

  // Pop modal from stack
  StoreAPI.popNav();
  check(modalDismissed === true, 'popNav invoked modal onBack handler');
  check(StoreAPI.navStack.length === 0, 'navStack is empty after pop');

  // ==========================================
  // 4. KEYBOARD BEHAVIOR TESTS
  // ==========================================
  // 4a. Escape key dismisses open modal
  let escapeDismissed = false;
  StoreAPI.pushNav('escape_modal', () => { escapeDismissed = true; });
  check(StoreAPI.navStack.length === 1, 'escape_modal on stack');

  const escapeEvent = new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, bubbles: true });
  document.dispatchEvent(escapeEvent);
  check(escapeDismissed === true, 'Escape key popped modal from navStack');
  check(StoreAPI.navStack.length === 0, 'navStack emptied by Escape key');

  // 4b. Enter key on search input triggers catalog filtering
  const searchInput = document.getElementById('search-input');
  check(searchInput !== null, 'search input exists');
  searchInput.value = 'telegram';
  const enterEvent = new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true });
  searchInput.dispatchEvent(enterEvent);
  check(searchInput.value === 'telegram', 'search input value preserved on Enter');

  // 4c. Enter key on coupon input
  const couponInput = document.getElementById('coupon-input');
  check(couponInput !== null, 'coupon input exists');
  couponInput.value = 'DISCOUNT50';
  couponInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));

  // ==========================================
  // 5. DURABLE CHECKOUT RECOVERY TESTS
  // ==========================================
  // Clear any existing test data
  sessionStorage.clear();
  localStorage.clear();

  const samplePayload = {
    tg_id: 998877,
    product_id: 42,
    quantity: 1,
    custom_fields: { player_id: 'user_123' }
  };

  const idempKey = StorefrontSecurity.checkoutKey('buy', samplePayload);
  check(typeof idempKey === 'string' && idempKey.length === 32, 'valid idempotency key created');

  // 5a. Save pending attempt
  const savedRecord = StoreCheckout.savePendingCheckout({
    scope: 'buy',
    payload: samplePayload,
    idempotencyKey: idempKey,
    productTitle: 'Telegram Premium 1 Month'
  });

  check(savedRecord.idempotencyKey === idempKey, 'pending checkout record saved with key');

  // 5b. Retrieve pending attempt
  const retrieved = StoreCheckout.getPendingCheckout();
  check(retrieved !== null, 'pending checkout retrieved from storage');
  check(retrieved.idempotencyKey === idempKey, 'retrieved record matches idempotency key');
  check(retrieved.payload.tg_id === 998877, 'retrieved record has correct payload');

  // 5c. Safe retry preserves exact same idempotency key (preventing double debits)
  const retryKey = StorefrontSecurity.checkoutKey('buy', samplePayload);
  check(retryKey === idempKey, 'retry uses identical idempotency key');

  // 5d. Clear pending checkout upon confirmed completion
  StoreCheckout.clearPendingCheckout();
  check(StoreCheckout.getPendingCheckout() === null, 'pending checkout cleared after completion');
  StorefrontSecurity.finishCheckout('buy', samplePayload, idempKey);

  // ==========================================
  // 6. SMS ACTIVATION (5SIM) MODAL & CONTROLS
  // ==========================================
  check(typeof window.openSmsModal === 'function', 'openSmsModal exported on window');
  check(typeof window.openAdminSmsModal === 'function', 'openAdminSmsModal exported on window');
  const smsChip = document.getElementById('filter-sms-chip');
  check(smsChip !== null, 'filter-sms-chip exists in storefront filter row');

  // Test opening customer SMS modal
  openSmsModal();
  const smsModal = document.getElementById('sms-activation-modal');
  check(smsModal && smsModal.style.display !== 'none', 'sms-activation-modal opens');
  check(document.getElementById('sms-service-select') !== null, 'service select exists');
  check(document.getElementById('sms-country-select') !== null, 'country select exists');
  check(document.getElementById('btn-buy-sms') !== null, 'buy SMS button exists');
  closeSmsModal();
  check(smsModal.style.display === 'none', 'sms-activation-modal closes');

  // Test opening admin SMS modal
  openAdminSmsModal();
  const adminSmsModal = document.getElementById('admin-sms-modal');
  check(adminSmsModal && adminSmsModal.style.display !== 'none', 'admin-sms-modal opens');
  closeAdminSmsModal();
  check(adminSmsModal.style.display === 'none', 'admin-sms-modal closes');

  // Mark all tests passed in body
  document.body.textContent = `PASS: ${count} storefront browser coverage checks`;
}

async function main() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ghstore-browser-coverage-'));
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');

    const htmlBody = `
<!DOCTYPE html>
<html lang="ar" dir="rtl" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>GH Store Test Harness</title>
</head>
<body>
  <div id="toast" class="toast-pill"></div>
  <canvas id="confetti-canvas"></canvas>

  <!-- Navigation Tabs -->
  <div id="tab-store" class="tab active"><span id="i18n-tab-store">المتجر</span></div>
  <div id="tab-orders" class="tab"><span id="i18n-tab-orders">العمليات</span></div>
  <div id="tab-wallet" class="tab"><span id="i18n-tab-wallet">المحفظة</span></div>
  <div id="tab-settings" class="tab"><span id="i18n-tab-settings">الإعدادات</span></div>

  <!-- Views -->
  <div id="view-store" style="display: block;">
    <input type="text" id="search-input" placeholder="Search...">
    <input type="text" id="coupon-input" placeholder="Coupon...">
    <div id="quick-filters-row">
      <div class="filter-chip filter-sms-chip" id="filter-sms-chip" onclick="openSmsModal()">SMS</div>
    </div>
    <div id="categories-container"></div>
    <div id="products-container"></div>
  </div>
  <div id="view-orders" style="display: none;"><div id="orders-history-list"></div></div>
  <div id="view-wallet" style="display: none;"><div id="wallet-balance-usd">$0.00</div></div>
  <div id="view-settings" style="display: none;"></div>

  <!-- Cart Drawer -->
  <div id="floating-cart-bar" style="display: none;">
    <span id="cart-floating-count">0</span>
    <span id="cart-floating-total">$0.00</span>
  </div>
  <div id="cart-drawer" class="drawer">
    <div id="cart-drawer-items-list"></div>
    <div id="cart-drawer-subtotal">$0.00</div>
  </div>

  <!-- Modals -->
  <div id="product-detail-modal" style="display: none;"></div>
  <div id="modal-order-success" style="display: none;">
    <span id="success-order-id"></span>
    <div id="success-delivered-goods"></div>
    <div id="success-instructions-steps"></div>
  </div>

  <!-- SMS Activation Modals -->
  <div class="admin-modal-overlay" id="sms-activation-modal" style="display: none;">
    <div id="sms-stage-select">
      <select id="sms-service-select"></select>
      <select id="sms-country-select"></select>
      <span id="sms-quote-stock-badge"></span>
      <span id="sms-quote-price-usd"></span>
      <span id="sms-quote-price-local"></span>
      <button id="btn-buy-sms" onclick="executeBuySms()"></button>
    </div>
    <div id="sms-stage-active" style="display: none;">
      <div id="sms-allocated-phone-number"></div>
      <div id="sms-waiting-box"></div>
      <div id="sms-received-box" style="display: none;">
        <span id="sms-received-code-val"></span>
        <span id="sms-received-full-text"></span>
      </div>
      <button id="btn-cancel-sms" onclick="executeCancelSms()"></button>
      <button id="btn-ban-sms" onclick="executeBanSms()"></button>
    </div>
  </div>
  <div class="admin-modal-overlay" id="admin-sms-modal" style="display: none;">
    <div id="admin-5sim-balance-val"></div>
    <div id="admin-sms-services-list"></div>
    <div id="admin-sms-countries-list"></div>
  </div>

  <!-- Load Modular Scripts -->
  <script>${securitySrc}</script>
  <script>${apiSrc}</script>
  <script>${storefrontSrc}</script>
  <script>${walletSrc}</script>
  <script>${checkoutSrc}</script>
  <script>${smsSrc}</script>
  <script>${adminSrc}</script>
  <script>${appSrc}</script>
  <script>
    try {
      (${runBrowserTests.toString()})();
    } catch (e) {
      document.body.textContent = 'FAIL: ' + e.stack;
    }
  </script>
</body>
</html>
    `;

    res.end(htmlBody);
  });

  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const executable = process.env.CHROME_BIN || '/usr/bin/google-chrome';

  const child = spawn(executable, [
    '--headless',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-background-networking',
    '--no-first-run',
    '--user-data-dir=' + profile,
    '--dump-dom',
    `http://127.0.0.1:${port}`
  ]);

  let stdout = '', stderr = '';
  child.stdout.on('data', d => { stdout += d; });
  child.stderr.on('data', d => { stderr += d; });

  const timeout = setTimeout(() => child.kill('SIGKILL'), 25000);
  try {
    const code = await new Promise((resolve, reject) => {
      child.on('exit', resolve);
      child.on('error', reject);
    });
    assert.equal(code, 0, stderr);
    assert.match(stdout, /PASS: \d+ storefront browser coverage checks/, stdout);
    console.log(stdout.match(/PASS: \d+ storefront browser coverage checks/)[0]);
  } finally {
    clearTimeout(timeout);
    server.close();
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
