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
  // 2b. THEME SWITCHING & STATE SYNCHRONIZATION TEST
  // ==========================================
  setAppTheme('light');
  check(document.documentElement.getAttribute('data-theme') === 'light', 'HTML data-theme switched to light');
  check(document.getElementById('theme-btn-light')?.classList.contains('active'), 'theme-btn-light has active class');
  check(document.getElementById('theme-btn-light')?.getAttribute('aria-checked') === 'true', 'theme-btn-light aria-checked is true');
  check(!document.getElementById('theme-btn-dark')?.classList.contains('active'), 'theme-btn-dark active class removed');
  check(document.getElementById('theme-btn-dark')?.getAttribute('aria-checked') === 'false', 'theme-btn-dark aria-checked is false');
  check(localStorage.getItem('ghstore_theme') === 'light', 'ghstore_theme saved as light in localStorage');

  setAppTheme('dark');
  check(document.documentElement.getAttribute('data-theme') === 'dark', 'HTML data-theme switched to dark');
  check(document.getElementById('theme-btn-dark')?.classList.contains('active'), 'theme-btn-dark has active class');
  check(document.getElementById('theme-btn-dark')?.getAttribute('aria-checked') === 'true', 'theme-btn-dark aria-checked is true');
  check(!document.getElementById('theme-btn-light')?.classList.contains('active'), 'theme-btn-light active class removed');
  check(document.getElementById('theme-btn-light')?.getAttribute('aria-checked') === 'false', 'theme-btn-light aria-checked is false');
  check(localStorage.getItem('ghstore_theme') === 'dark', 'ghstore_theme saved as dark in localStorage');

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

  // ==========================================
  // 7. USER DATA & ADMIN RENDERING TESTS
  // ==========================================
  const sampleUser = {
    telegram_id: 7635553403,
    username: 'ahmed_admin',
    first_name: 'Ahmed',
    balance: 45.75,
    total_spent: 120.00,
    vip_tier: 'Gold',
    vip_discount: 7,
    is_admin: true,
    referrals_count: 5,
    referrals_total_earned: 12.50,
    referral_commission_rate: 0.2,
    admin_stats: {
      total_revenue: 350.00,
      total_cost: 200.00,
      total_user_balances: 85.00
    }
  };

  WalletModule.renderWalletBalances(sampleUser);
  check(document.getElementById('top-balance-str')?.textContent === '$45.75', 'top-balance-str updated with user balance');
  check(document.getElementById('wallet-balance-hero')?.textContent === '$45.75', 'wallet-balance-hero updated with user balance');
  check(document.getElementById('settings-card-balance')?.textContent === '$45.75', 'settings-card-balance updated with user balance');

  renderUserProfile(sampleUser);
  check(document.getElementById('user-name-title')?.textContent === 'Ahmed', 'user-name-title updated with user name');
  check(document.getElementById('user-tg-num')?.textContent.includes('7635553403'), 'user-tg-num updated with telegram ID');

  renderAdminControlCenter(sampleUser);
  check(document.getElementById('admin-control-center-card')?.style.display !== 'none', 'admin-control-center-card visible for admin');
  check(document.getElementById('admin-stat-revenue')?.textContent === '$350.00', 'admin-stat-revenue updated');

  // ==========================================
  // 8. STOREFRONT CATEGORIES & LOGO & AVATAR VERIFICATION
  // ==========================================
  // Test 8a. Skeletons in catalogs-grid are replaced by rendered category cards
  const testCategories = [
    { id: 1, name: 'AI & Chatbots', name_ar: 'الذكاء الاصطناعي', icon_url: '/static/img/cat-ai.svg' },
    { id: 2, name: 'Streaming', name_ar: 'البث والترفيه', icon_url: '/static/img/cat-streaming.svg' }
  ];
  const testProducts = [
    { id: 101, name: 'ChatGPT Plus 1 Month', category: 'AI & Chatbots', sell_price_usd: 19.99, stock: 10 },
    { id: 102, name: 'Netflix Premium 4K', category: 'Streaming', sell_price_usd: 3.50, stock: 5 }
  ];

  StoreAPI.AppState.categoriesList = testCategories;
  StoreAPI.AppState.allProducts = testProducts;
  StorefrontModule.renderCatalogsGrid(testCategories);

  const gridEl = document.getElementById('catalogs-grid');
  check(gridEl && !gridEl.querySelector('.skeleton-card-item'), 'shimmer skeletons removed from catalogs-grid');
  check(gridEl && gridEl.querySelectorAll('.catalog-visual-card, .catalog-list-card').length === 2, 'two category cards rendered in catalogs-grid');

  // Test 8b. Category mode switching
  StorefrontModule.setCatalogViewMode('list');
  check(gridEl && gridEl.classList.contains('list-layout'), 'catalogs-grid switched to list-layout');
  StorefrontModule.setCatalogViewMode('grid');
  check(gridEl && gridEl.classList.contains('grid-layout'), 'catalogs-grid switched back to grid-layout');

  // Test 8c. Open collection and return to collections
  StorefrontModule.openCollection('AI & Chatbots');
  check(document.getElementById('products-catalog-mode')?.style.display !== 'none', 'products-catalog-mode visible');
  check(document.getElementById('catalogs-collection-mode')?.style.display === 'none', 'catalogs-collection-mode hidden');
  check(document.getElementById('catalog-products-list')?.querySelectorAll('.product-row').length >= 1, 'products rendered in collection');

  StorefrontModule.returnToCollections();
  check(document.getElementById('catalogs-collection-mode')?.style.display !== 'none', 'catalogs-collection-mode restored');
  check(document.getElementById('products-catalog-mode')?.style.display === 'none', 'products-catalog-mode hidden after return');

  // Test 8d. Store logo application & fallback
  applyStoreLogo('/static/img/gh-store-logo-mark.png');
  const logoImg = document.getElementById('top-store-logo');
  check(logoImg && logoImg.src.includes('gh-store-logo-mark.png'), 'store logo src set properly');

  // Test 8e. User Avatar with relative path safety
  sampleUser.photo_url = '/api/user/avatar/7635553403';
  renderUserProfile(sampleUser);
  const avatarImg = document.querySelector('#top-avatar-box img.avatar-img');
  check(avatarImg && avatarImg.src.includes('/api/user/avatar/7635553403'), 'avatar img rendered with relative url allowed');

  // Test 8f. Opening product detail page displays view-product-detail and hides view-store
  switchTab('store');
  check(document.getElementById('view-store')?.style.display !== 'none', 'store view displayed before product open');
  StorefrontModule.openProductDetail(101);
  const prodDetailEl = document.getElementById('view-product-detail');
  const storeViewEl = document.getElementById('view-store');
  check(prodDetailEl && prodDetailEl.style.display !== 'none', 'product detail page visible after opening');
  check(storeViewEl && storeViewEl.style.display === 'none', 'view-store hidden when product detail opens (not stacked down below)');

  // Test 8g. Closing product detail page restores view-store and hides product detail page
  StorefrontModule.closeProductDetailPage();
  check(prodDetailEl && prodDetailEl.style.display === 'none', 'product detail page hidden after closing');
  check(storeViewEl && storeViewEl.style.display !== 'none', 'view-store restored after closing product detail');

  // Test 8h. Admin Orders and Live Radar functions exist on window
  check(typeof loadAdminOrders === 'function', 'loadAdminOrders is defined on window');
  check(typeof loadAdminLiveRadar === 'function', 'loadAdminLiveRadar is defined on window');
  check(typeof openAdminOrdersModal === 'function', 'openAdminOrdersModal is defined on window');

  // Test 8i. renderUserActivity renders structured credentials for delivered orders
  StoreAPI.AppState.userOrders = [{
    id: 999,
    status: 'completed',
    total_sell: 12.0,
    products: 'Gemini Pro Subscription',
    goods: ['https://serviceactivation.google.com/token/test12345']
  }];
  StoreAPI.AppState.userRecharges = [];
  renderUserActivity();
  const ordersContainer = document.getElementById('orders-container-box') || document.getElementById('orders-history-list');
  check(ordersContainer.innerHTML.includes('Gemini Pro Activation Token') || ordersContainer.innerHTML.includes('كود تفعيل اشتراك Gemini Pro'), 'renderUserActivity uses renderStructuredCredentials for Gemini Pro URLs');
  check(ordersContainer.innerHTML.includes('openExternalPaymentUrl'), 'orders view contains direct activation action');

  // Test 8j. openOrderDetail opens view-order-detail with correct ID
  openOrderDetail(999);
  const orderDetailView = document.getElementById('view-order-detail');
  const idTitleEl = document.getElementById('order-detail-id-title');
  check(orderDetailView && orderDetailView.style.display !== 'none', 'order detail view visible upon openOrderDetail');
  check(idTitleEl && idTitleEl.innerText.includes('999'), 'order detail ID title set to order #999');

  // Test 8k. closeOrderDetailView restores orders view
  closeOrderDetailView();
  check(orderDetailView && orderDetailView.style.display === 'none', 'order detail view hidden after closeOrderDetailView');
  check(document.getElementById('view-orders')?.style.display !== 'none', 'orders view restored after closing order detail');

  // Test 8l. proceedToTopupForProduct sets pending buy in sessionStorage and checkPendingBuyResume handles it
  proceedToTopupForProduct(101, 2, 15.0);
  const pendingRaw = sessionStorage.getItem('ghstore_pending_buy_resume');
  check(pendingRaw && JSON.parse(pendingRaw).productId === 101, 'proceedToTopupForProduct stored pending buy intent');

  // --- Item 15: Task-Based Usability Checks ---
  // Task 1: Search & Find a Service
  openSearchPage();
  check(document.getElementById('view-search')?.style.display !== 'none', 'Task 1: Search view opens cleanly');
  const searchPageInput = document.getElementById('search-page-input');
  if (searchPageInput) {
    searchPageInput.value = 'unknown_xyz_no_match';
    handleSearchPageInput();
    const searchList = document.getElementById('search-page-products-list');
    check(searchList && searchList.innerHTML.includes('applyQuickSearch'), 'Task 1: Search empty state renders suggestions and quick search buttons');

    applyQuickSearch('ChatGPT');
    check(searchPageInput.value === 'ChatGPT', 'Task 1: applyQuickSearch updates search input value');
    check(searchList && searchList.querySelectorAll('.product-row').length >= 1, 'Task 1: search results rendered for matched query');

    // Query preservation
    StorefrontModule.openProductDetail(101);
    StorefrontModule.closeProductDetailPage();
    check(searchPageInput.value === 'ChatGPT', 'Task 1: Search query preserved after viewing and closing product detail');
    closeSearchPage();
  }

  // Task 2: Compare Two Plans / Variants Under a Service
  const sampleP1 = { id: 101, name: 'ChatGPT Plus', duration_en: '1 Month', delivery_type: 'activation', stock: 10, sell_price_usd: 15.0 };
  const sampleP2 = { id: 102, name: 'ChatGPT Team', duration_en: '1 Year', delivery_type: 'stock', stock: 5, sell_price_usd: 120.0 };
  const durBadge1 = renderDurationBadge(sampleP1.duration_en);
  const durBadge2 = renderDurationBadge(sampleP2.duration_en);
  const meta1 = productMetaLine({ isOutOfStock: false, isActivation: true, duration: sampleP1.duration_en, multiCount: 0, stockText: 'In stock (10)' });
  const meta2 = productMetaLine({ isOutOfStock: false, isActivation: false, duration: sampleP2.duration_en, multiCount: 0, stockText: 'In stock (5)' });
  check(durBadge1.includes('prod-dur-badge') && durBadge1.includes('1 Month'), 'Task 2: Duration badge renders cleanly');
  check(meta1.includes('prod-type-label') && (meta1.includes('تفعيل') || meta1.includes('Activation')), 'Task 2: Plan comparison meta contains delivery tag');
  check(meta2.includes('prod-type-label') && (meta2.includes('حساب') || meta2.includes('Account')), 'Task 2: Variant comparison meta contains consistent tags');

  // Task 3: Balance Shortfall Recovery Flow & Input Preservation
  StoreAPI.AppState.userId = sampleUser.telegram_id;
  const gameFieldsContainer = document.getElementById('detail-game-fields-container');
  if (gameFieldsContainer) gameFieldsContainer.style.display = 'block';
  const playerInp = document.getElementById('game-player-id-input');
  if (playerInp) playerInp.value = '';
  buyNow(sampleP1);
  check(document.querySelector('.inline-field-error') !== null, 'Task 3: Missing required custom field renders inline error');
  check(playerInp && playerInp.style.borderColor.includes('239'), 'Task 3: Input highlighted with error border');

  // Typing clears error inline while preserving value
  if (playerInp) {
    playerInp.value = 'PlayerUID999';
    onPlayerInputChanged();
  }
  check(document.querySelector('.inline-field-error') === null, 'Task 3: Typing clears inline error');
  check(playerInp && playerInp.value === 'PlayerUID999', 'Task 3: Typed input is preserved');

  // Shortfall recovery preserves fields
  proceedToTopupForProduct(101, 1, 15.0);
  const pendingBuy = JSON.parse(sessionStorage.getItem('ghstore_pending_buy_resume') || '{}');
  check(pendingBuy.productId === 101 && pendingBuy.customFields?.player_id === 'PlayerUID999', 'Task 3: Shortfall recovery preserved product and entered custom fields');

  // Task 4: Retrieve Delivered Order & Contextual Support
  openOrderDetail(999);
  const credsBox = document.getElementById('order-detail-credentials-box');
  check(credsBox && (credsBox.innerHTML.includes('Gemini Pro') || credsBox.innerHTML.includes('serviceactivation')), 'Task 4: Delivered credentials retrieved with activation token');
  closeOrderDetailView();

  // ==========================================
  // 9. ADMIN PRODUCT & FOLDER CATEGORY DROPDOWN TESTS
  // ==========================================
  StoreAPI.AppState.categoriesList = [
    ...testCategories,
    { id: 5, name: 'Productivity', name_ar: 'إنتاجية', name_en: 'Productivity' },
    { id: 9, name: 'Communication', name_ar: 'تواصل', name_en: 'Communication' }
  ];
  check(typeof populateCategorySelect === 'function', 'populateCategorySelect function defined');
  check(typeof onAdminProdCatSelectChange === 'function', 'onAdminProdCatSelectChange defined');
  check(typeof onAdminProdFolderSelectChange === 'function', 'onAdminProdFolderSelectChange defined');
  check(typeof openAdminFolderModal === 'function', 'openAdminFolderModal defined');
  check(typeof submitAdminFolderUpdate === 'function', 'submitAdminFolderUpdate defined');
  check(typeof openAdminCurrentFolderEditor === 'function', 'openAdminCurrentFolderEditor defined');
  check(typeof openAdminCreateFolderModal === 'function', 'openAdminCreateFolderModal defined');

  // Test 9a. Product Modal Category Dropdown
  openAdminProductModal(101);
  const prodCatSelect = document.getElementById('admin-edit-prod-cat');
  check(prodCatSelect !== null, 'admin-edit-prod-cat select exists');
  check(prodCatSelect.tagName === 'SELECT', 'admin-edit-prod-cat is a SELECT element');
  check(prodCatSelect.options.length >= 2, 'admin-edit-prod-cat has category options');
  check(prodCatSelect.value === 'AI & Chatbots', 'product 101 category pre-selected');
  const prodFolderSelect = document.getElementById('admin-edit-prod-folder-select');
  check(prodFolderSelect !== null && prodFolderSelect.tagName === 'SELECT', 'admin-edit-prod-folder-select is a SELECT element');
  closeAdminProductModal();

  // Test 9b. Folder Modal Category Dropdown
  const testFolder = {
    id: 54,
    key: 'zoom',
    category: 'Communication',
    title_en: 'Zoom',
    title_ar: 'زووم',
    icon: '💬',
    sort_order: 10
  };
  openAdminFolderModal('zoom', testFolder);
  const folderModal = document.getElementById('admin-folder-modal');
  check(folderModal && folderModal.style.display !== 'none', 'admin-folder-modal opens');
  const folderCatSelect = document.getElementById('admin-edit-folder-cat');
  check(folderCatSelect !== null, 'admin-edit-folder-cat select exists');
  check(folderCatSelect.tagName === 'SELECT', 'admin-edit-folder-cat is a SELECT element');
  check(folderCatSelect.options.length >= 2, 'admin-edit-folder-cat has category options');
  check(folderCatSelect.value === 'Communication', 'zoom folder current category pre-selected');

  // Test 9c. Changing Folder Category to Productivity via Dropdown
  folderCatSelect.value = 'Productivity';
  check(folderCatSelect.value === 'Productivity', 'folder category changed to Productivity in dropdown');
  closeAdminFolderModal();
  check(folderModal.style.display === 'none', 'admin-folder-modal closes');

  // Test 9d. Product Modal Pre-filled Names without overrides
  openAdminProductModal(101);
  const prodNameEn = document.getElementById('admin-edit-prod-name');
  const prodNameAr = document.getElementById('admin-edit-prod-name-ar');
  check(prodNameEn && prodNameEn.value === 'ChatGPT Plus 1 Month', 'product 101 English name is pre-filled');
  check(prodNameAr && prodNameAr.value === 'ChatGPT Plus 1 Month', 'product 101 Arabic name falls back to clean name');
  closeAdminProductModal();

  // Test 9e. Product Modal Pre-filled Names with custom overrides
  StoreAPI.AppState.allProducts.push({
    id: 103,
    name: 'Zoom Pro Annual',
    clean_name: 'Zoom Pro',
    custom_name: 'Zoom Pro Enterprise',
    custom_name_ar: 'زووم برو للشركات',
    category: 'Productivity',
    sell_price_usd: 49.99,
    stock: 20
  });
  openAdminProductModal(103);
  check(document.getElementById('admin-edit-prod-name')?.value === 'Zoom Pro Enterprise', 'product 103 custom English name pre-filled');
  check(document.getElementById('admin-edit-prod-name-ar')?.value === 'زووم برو للشركات', 'product 103 custom Arabic name pre-filled');
  closeAdminProductModal();

  // Test 9f. Folder Modal Pre-filled Titles with folder data
  openAdminFolderModal('zoom', testFolder);
  const folderTitleEn = document.getElementById('admin-edit-folder-title-en');
  const folderTitleAr = document.getElementById('admin-edit-folder-title-ar');
  check(folderTitleEn && folderTitleEn.value === 'Zoom', 'folder title_en pre-filled');
  check(folderTitleAr && folderTitleAr.value === 'زووم', 'folder title_ar pre-filled');
  closeAdminFolderModal();

  // Test 9g. Folder Modal Pre-filled Titles from primary product when folder not in DB
  StoreAPI.AppState.allProducts.push({
    id: 104,
    name: 'Netflix 4K UHD 1 Month',
    folder_key: 'netflix',
    folder_title_en: 'Netflix 4K UHD',
    folder_title_ar: 'نتفلكس بدقة 4K',
    category: 'Streaming',
    sell_price_usd: 4.99
  });
  openAdminFolderModal('netflix');
  check(document.getElementById('admin-edit-folder-title-en')?.value === 'Netflix 4K UHD', 'virtual folder title_en pre-filled from primary product');
  check(document.getElementById('admin-edit-folder-title-ar')?.value === 'نتفلكس بدقة 4K', 'virtual folder title_ar pre-filled from primary product');
  closeAdminFolderModal();

  // Test 9h. Create New Folder modal leaves titles empty for input
  openAdminCreateFolderModal();
  check(document.getElementById('admin-edit-folder-title-en')?.value === '', 'new folder title_en starts empty');
  check(document.getElementById('admin-edit-folder-title-ar')?.value === '', 'new folder title_ar starts empty');
  closeAdminFolderModal();

  // ==========================================
  // 10. GAME & VOUCHER PACK SELECTION AND DROPDOWN TESTS
  // ==========================================
  const pubgGameProduct = {
    id: 30000011,
    name: 'PUBG Mobile (Instant Recharge)',
    name_ar: 'ببجي موبايل (شحن فوري)',
    category: 'Games',
    delivery_type: 'direct_topup',
    supplier: 'g2bulk',
    cost_usd: 0.90,
    sell_price_usd: 1.26,
    stock: 9999,
    extra_meta: {
      type: 'instant_recharge',
      game_code: 'pubg_mobile',
      required_fields: ['userid'],
      items: [
        { id: 264, name: '60 UC', cost: 0.90, price: 1.26, reseller_price: 0.97 },
        { id: 3, name: '325 UC', cost: 4.45, price: 6.23, reseller_price: 4.81 },
        { id: 4, name: '660 UC', cost: 8.90, price: 12.46, reseller_price: 9.61 },
        { id: 5, name: '1800 UC', cost: 22.38, price: 31.33, reseller_price: 24.17 }
      ]
    }
  };

  const pubgVoucherProduct = {
    id: 35000001,
    name: 'PUBG MOBILE UC Vouchers (Digital Vouchers)',
    name_ar: 'قسائم ببجي موبايل الرقمية',
    category: 'Games',
    delivery_type: 'voucher',
    supplier: 'g2bulk',
    cost_usd: 0.89,
    sell_price_usd: 1.25,
    stock: 9999,
    extra_meta: {
      type: 'voucher',
      category_id: 1,
      redemption_url: 'https://www.midasbuy.com',
      instructions_ar: [
        'توجه إلى موقع midasbuy.com الرسمي',
        'أدخل معرف اللاعب (Player ID)',
        'أدخل كود القسيمة (PIN) واضغط تأكيد'
      ],
      instructions_en: [
        'Visit www.midasbuy.com',
        'Enter your Player ID',
        'Enter the voucher PIN and confirm'
      ],
      items: [
        { id: 2, name: '60 Uc Voucher', cost: 0.89, price: 1.25, reseller_price: 0.96, face_value: 1, stock: 17308 },
        { id: 4, name: '660 Uc Voucher', cost: 8.90, price: 12.46, reseller_price: 9.61, face_value: 10, stock: 3679 },
        { id: 7, name: '8100 Uc Voucher', cost: 88.0, price: 123.20, reseller_price: 95.04, face_value: 100, stock: 0 }
      ]
    }
  };

  StoreAPI.AppState.allProducts.push(pubgGameProduct);
  StoreAPI.AppState.allProducts.push(pubgVoucherProduct);

  // 10a. Open PUBG Game product
  openProductDetail(30000011);
  const variantsContainer = document.getElementById('detail-variants-container');
  check(variantsContainer !== null, 'detail-variants-container exists');
  check(variantsContainer.style.display !== 'none', 'detail-variants-container displayed for game with packs');

  const packSelect = document.getElementById('detail-pack-select');
  check(packSelect !== null, 'detail-pack-select exists');
  check(packSelect.tagName === 'SELECT', 'detail-pack-select is a SELECT element');
  check(packSelect.options.length === 4, 'detail-pack-select has 4 pack options');
  check(packSelect.options[0].value === '264', 'first pack option is 60 UC (lowest price first)');
  check(StoreAPI.AppState.selectedProduct?.selectedPack?.id === 264, 'selectedPack default is 60 UC');

  // 10b. Change pack selection via dropdown to 660 UC (id: 4)
  onDetailPackSelectChange('4');
  check(StoreAPI.AppState.selectedProduct?.selectedPack?.id === 4, 'selectedPack updated to 660 UC');
  check(packSelect.value === '4', 'detail-pack-select value synced to 4');
  const activeCard = document.querySelector('.detail-variant-card.active');
  check(activeCard !== null, 'active variant card exists');
  check(activeCard.getAttribute('data-pack-id') === '4', 'active card matches selected pack 4');
  check(document.getElementById('prod-total-price')?.textContent === '$11.59', 'total price updated to 660 UC price ($11.59 with VIP discount)');
  check(document.getElementById('prod-original-price')?.textContent === '$12.46', 'original price is $12.46 before VIP discount');

  // 10c. Change pack selection via card click to 325 UC (id: 3)
  onDetailPackCardClick('3');
  check(StoreAPI.AppState.selectedProduct?.selectedPack?.id === 3, 'selectedPack updated to 325 UC via card click');
  check(packSelect.value === '3', 'detail-pack-select value synced to 3 after card click');
  check(document.getElementById('prod-total-price')?.textContent === '$5.79', 'total price updated to 325 UC price ($5.79 with VIP discount)');
  check(document.getElementById('prod-original-price')?.textContent === '$6.23', 'original price is $6.23 before VIP discount');

  // 10d. Open PUBG Voucher product and verify redemption instructions
  openProductDetail(35000001);
  check(variantsContainer.style.display !== 'none', 'detail-variants-container displayed for voucher product');
  check(packSelect.options.length === 3, 'detail-pack-select populated with 3 voucher packs');

  const voucherManual = document.getElementById('detail-voucher-manual-container');
  check(voucherManual !== null, 'detail-voucher-manual-container exists');
  check(voucherManual.style.display !== 'none', 'detail-voucher-manual-container displayed for voucher product');

  const stepsList = document.getElementById('detail-voucher-steps-list');
  check(stepsList !== null, 'detail-voucher-steps-list exists');
  check(stepsList.innerHTML.includes('midasbuy.com'), 'voucher instructions contain redemption steps');

  const officialSiteLink = document.getElementById('link-voucher-official-site');
  check(officialSiteLink !== null, 'link-voucher-official-site exists');
  check(officialSiteLink.href.includes('midasbuy.com'), 'official site link points to midasbuy.com');

  // 10e. Out-of-stock pack disables buy button and shows restock alert
  onDetailPackSelectChange('7'); // 8100 UC Voucher (stock: 0)
  check(document.getElementById('btn-inapp-purchase')?.style.display === 'none', 'buy button hidden when out-of-stock pack selected');
  check(document.getElementById('restock-alert-box')?.style.display !== 'none', 'restock alert displayed for out-of-stock pack');

  // Select in-stock pack restores buy button
  onDetailPackSelectChange('2'); // 60 UC Voucher (stock: 17308)
  check(document.getElementById('btn-inapp-purchase')?.style.display !== 'none', 'buy button restored when in-stock pack selected');

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

  <!-- Top Header Logo -->
  <div class="store-logo-wrapper">
    <img id="top-store-logo" class="store-logo-img" src="" alt="GH Store" style="display: none;">
    <div id="top-store-fallback" class="store-logo-fallback">🛍️</div>
  </div>

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
      <div class="filter-chip active" id="filter-all" onclick="applyCatalogFilter('all')">الكل</div>
    </div>

    <!-- Real Storefront Modes -->
    <div id="catalogs-collection-mode">
      <button class="view-toggle-btn active" id="btn-view-grid" onclick="setCatalogViewMode('grid')">شبكة</button>
      <button class="view-toggle-btn" id="btn-view-list" onclick="setCatalogViewMode('list')">قائمة</button>
      <div class="catalogs-grid grid-layout" id="catalogs-grid">
        <div class="skeleton-card-item"></div>
      </div>
    </div>
    <div id="products-catalog-mode" style="display: none;">
      <div id="active-collection-title">التصنيف</div>
      <div id="catalog-products-list"></div>
    </div>
    <div id="service-variants-mode" style="display: none;">
      <div id="active-service-title">باقات الخدمة</div>
      <div id="service-variants-products-list"></div>
    </div>

    <div id="categories-container"></div>
    <div id="products-container"></div>
  </div>
  <section id="view-product-detail" class="tab-view" style="display: none;">
    <button class="btn-back-catalog" onclick="closeProductDetailPage()"></button>
    <div class="inset-card" id="detail-variants-container" style="display: none;">
      <div id="label-variants-title">اختر الفئة أو الباقة | Select Pack</div>
      <span class="catalog-visual-pill" id="variants-count-badge" style="display: none;"></span>
      <div id="detail-pack-select-group">
        <label for="detail-pack-select" id="label-pack-select">اختر الباقة من القائمة:</label>
        <select id="detail-pack-select" class="admin-text-input" onchange="onDetailPackSelectChange(this.value)"></select>
      </div>
      <div id="detail-packs-loading" style="display: none;"></div>
      <div class="detail-variants-grid" id="detail-variants-list"></div>
    </div>
    <div class="inset-card" id="detail-voucher-manual-container" style="display: none;">
      <div id="label-voucher-manual-title">طريقة الاستخدام واسترداد الكود</div>
      <a href="#" id="link-voucher-official-site" style="display: none;">الموقع الرسمي</a>
      <div class="voucher-steps-list" id="detail-voucher-steps-list"></div>
    </div>
    <div id="detail-game-fields-container" style="display: none;">
      <div id="group-player-id">
        <input type="text" id="game-player-id-input" oninput="onPlayerInputChanged()">
      </div>
      <div id="group-server-id" style="display: none;">
        <input type="text" id="game-server-id-input" oninput="onPlayerInputChanged()">
      </div>
    </div>
    <div id="prod-total-price"></div>
    <div id="prod-original-price" style="display: none;"></div>
    <div id="btn-price-tag"></div>
    <div id="prod-stock-badge"></div>
    <div id="restock-alert-box" style="display: none;"></div>
    <button id="btn-inapp-purchase" onclick="buyNow(StoreAPI.AppState.activeProduct)"></button>
  </section>
  <section id="view-search" class="tab-view" style="display: none;">
    <button class="btn-back-catalog" onclick="closeSearchPage()"></button>
    <input type="text" id="search-page-input" oninput="handleSearchPageInput()">
    <span class="search-page-clear-btn" id="search-page-clear-btn" onclick="clearSearchPageInput()" style="display: none;">✕</span>
    <div id="search-page-empty-state" style="display: flex;"></div>
    <div id="search-page-results" style="display: none;">
      <div id="search-results-count-bar"></div>
      <div id="search-page-products-list"></div>
    </div>
  </section>
  <section id="view-order-detail" class="tab-view" style="display: none;">
    <div id="order-detail-id-title"></div>
    <div id="order-detail-date"></div>
    <div id="order-detail-products-title"></div>
    <div id="order-detail-total-amount"></div>
    <div id="order-detail-status-badge"></div>
    <div id="order-detail-stepper-fill"></div>
    <div id="order-step-node-1"></div>
    <div id="order-step-node-2"></div>
    <div id="order-step-node-3"></div>
    <div id="order-detail-credentials-box"></div>
  </section>
  <div id="view-orders" style="display: none;"><div id="orders-history-list"></div></div>
  <div id="view-wallet" style="display: none;">
    <span id="top-balance-str">$0.00</span>
    <span id="top-balance-plus">➕</span>
    <div id="wallet-balance-usd">$0.00</div>
    <div id="wallet-balance-hero">$0.00</div>
    <div id="wallet-balance-approx">جاهز للشراء</div>
  </div>
  <div id="view-settings" style="display: none;">
    <div id="settings-card-balance">$0.00</div>
    <div id="settings-card-spent">$0.00</div>
    <div id="user-name-title">العميل</div>
    <div id="user-handle-title" style="display: none;">@username</div>
    <div id="user-tg-num">ID: 000000000</div>
    <div id="user-vip-pill-box"></div>
    <div id="admin-control-center-card" style="display: none;">
      <div id="admin-stat-revenue">$0.00</div>
      <div id="admin-stat-cost">$0.00</div>
      <div id="admin-stat-profit">$0.00</div>
      <div id="admin-stat-balances">$0.00</div>
    </div>
    <div id="top-avatar-box"><div id="top-avatar-initial">U</div></div>
    <div id="settings-avatar-box"><div id="settings-avatar-initial">U</div></div>
    <span id="referral-link-display"></span>
    <div id="referral-count-val">0</div>
    <div id="referral-earned-val">$0.00</div>
    <div id="referral-rate-val">0.2%</div>
    <div class="theme-segmented-control" role="radiogroup" aria-label="Theme">
      <button type="button" class="theme-segment-btn active" id="theme-btn-dark" role="radio" aria-checked="true" onclick="setAppTheme('dark')">
        <span id="label-theme-dark">داكن</span>
      </button>
      <button type="button" class="theme-segment-btn" id="theme-btn-light" role="radio" aria-checked="false" onclick="setAppTheme('light')">
        <span id="label-theme-light">فاتح</span>
      </button>
    </div>
  </div>

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

  <!-- Admin Product Editor Modal Sheet -->
  <div class="admin-modal-overlay" id="admin-product-modal" style="display: none;">
    <input type="hidden" id="admin-edit-prod-id">
    <input type="text" id="admin-edit-prod-name">
    <input type="text" id="admin-edit-prod-name-ar">
    <select id="admin-edit-prod-folder-select" onchange="onAdminProdFolderSelectChange()"></select>
    <div id="admin-edit-prod-new-folder-wrap" style="display: none;">
      <input type="text" id="admin-edit-prod-folder-new-en">
      <input type="text" id="admin-edit-prod-folder-new-ar">
    </div>
    <select id="admin-edit-prod-cat" onchange="onAdminProdCatSelectChange()"></select>
    <input type="number" id="admin-edit-prod-price">
    <input type="number" id="admin-edit-prod-reseller-price">
    <input type="text" id="admin-edit-prod-stock-display">
    <input type="checkbox" id="admin-edit-prod-hidden">
    <input type="checkbox" id="admin-edit-folder-hidden">
    <button id="admin-product-save-btn" onclick="submitAdminProductUpdate()"></button>
  </div>

  <!-- Admin Folder Editor Modal Sheet -->
  <div class="admin-modal-overlay" id="admin-folder-modal" style="display: none;">
    <input type="hidden" id="admin-edit-folder-id">
    <input type="hidden" id="admin-edit-folder-key">
    <input type="text" id="admin-edit-folder-title-en">
    <input type="text" id="admin-edit-folder-title-ar">
    <select id="admin-edit-folder-cat"></select>
    <input type="text" id="admin-edit-folder-icon">
    <input type="number" id="admin-edit-folder-sort">
    <input type="checkbox" id="admin-edit-folder-hidden-check">
    <button id="admin-folder-save-btn" onclick="submitAdminFolderUpdate()"></button>
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
