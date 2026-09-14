/**
 * GH Store - Shared API, Auth, i18n, & Platform Core Module (api.js)
 * 
 * Provides:
 * - Session token management & fetch auto-interceptor (Authorization, X-Session-Token, X-Telegram-Init-Data)
 * - Telegram WebApp SDK bindings (haptics, safe area insets, cloud storage, orientation lock)
 * - Synthesized zero-asset audio micro-clicks & canvas confetti engine
 * - Navigation stack with native Telegram BackButton synchronization
 * - SWR caching client & toast notification system
 * - Complete i18n translation dictionary & layout switcher (Arabic RTL vs English LTR)
 * - Global keyboard navigation handlers (Escape to close modals, Enter for inputs)
 * - Safe HTML/Markdown text formatters and credential sanitizers
 */
(function (root) {
  'use strict';

  // --- Session Token Management ---
  let appSessionToken = '';
  try {
    const urlParams = typeof root.location !== 'undefined' ? new URLSearchParams(root.location.search) : null;
    const urlTok = urlParams?.get('auth_token') || urlParams?.get('session_token') || urlParams?.get('token');
    const urlTgId = Number(urlParams?.get('tg_id') || 0);
    const tgUser = root.Telegram?.WebApp?.initDataUnsafe?.user;
    const effectiveTgId = tgUser?.id || urlTgId;

    // Detect user change from cache
    const cachedUserId = root.localStorage?.getItem('ghstore_user_id');
    if (effectiveTgId && cachedUserId && String(cachedUserId) !== String(effectiveTgId)) {
      root.localStorage?.removeItem('ghstore_session_token');
      root.sessionStorage?.removeItem('ghstore_session_token');
      root.localStorage?.removeItem('ghstore_user_cache_v3');
    }
    if (effectiveTgId) {
      root.localStorage?.setItem('ghstore_user_id', String(effectiveTgId));
    }

    if (urlTok) {
      appSessionToken = urlTok;
      root.localStorage?.setItem('ghstore_session_token', urlTok);
      root.sessionStorage?.setItem('ghstore_session_token', urlTok);
    } else {
      appSessionToken = root.localStorage?.getItem('ghstore_session_token') || root.sessionStorage?.getItem('ghstore_session_token') || '';
    }
  } catch (_) {}

  function getSessionToken() {
    return appSessionToken;
  }

  function setSessionToken(token) {
    appSessionToken = token || '';
    try {
      if (token) {
        root.localStorage?.setItem('ghstore_session_token', token);
        root.sessionStorage?.setItem('ghstore_session_token', token);
      } else {
        root.localStorage?.removeItem('ghstore_session_token');
        root.sessionStorage?.removeItem('ghstore_session_token');
      }
    } catch (_) {}
  }

  function clearSessionToken() {
    setSessionToken('');
  }

  let authSessionPromise = null;
  let authenticatedToken = '';

  function ensureAuthSession() {
    if (getSessionToken() && getSessionToken() === authenticatedToken) {
      return Promise.resolve({ status: 'ok', token: authenticatedToken, tg_id: AppState.userId });
    }
    if (!authSessionPromise) {
      authSessionPromise = exchangeAuthSession().finally(() => { authSessionPromise = null; });
    }
    return authSessionPromise;
  }

  async function exchangeAuthSession() {
    const tgObj = getTg();
    const currentToken = getSessionToken();
    const initData = tgObj?.initData || '';

    // If we have either initData or currentToken/urlToken, handshake with /api/auth/session
    if (initData || currentToken) {
      try {
        const fetchFn = root._origFetch || root.fetch;
        const res = await fetchFn('/api/auth/session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(initData ? { 'X-Telegram-Init-Data': initData } : {}),
            ...(currentToken ? { 'Authorization': 'Bearer ' + currentToken, 'X-Session-Token': currentToken } : {})
          },
          body: JSON.stringify({
            init_data: initData,
            auth_token: currentToken
          })
        });
        if (res.ok) {
          const d = await res.json();
          if (d.status === 'ok' && d.token) {
            setSessionToken(d.token);
            authenticatedToken = d.token;
            if (d.tg_id) AppState.userId = Number(d.tg_id);
            return d;
          }
        }
      } catch (e) {
        console.debug('Auth session exchange error:', e);
      }
    }
    return null;
  }

  // --- Auto-Interception on window.fetch ---
  if (typeof root.fetch === 'function' && !root._ghstoreFetchIntercepted) {
    const _origFetch = root.fetch;
    root._origFetch = _origFetch;
    root.fetch = function (url, options) {
      const opts = options ? { ...options } : {};
      let requestUrl;
      try {
        requestUrl = new URL(typeof url === 'string' || url instanceof URL ? url : url.url, root.location?.href || 'https://invalid.local');
      } catch (_) {
        return _origFetch.call(this, url, opts);
      }

      if (root.location && requestUrl.origin === root.location.origin && requestUrl.pathname.startsWith('/api/')) {
        const tgObj = root.Telegram?.WebApp;
        const currentToken = getSessionToken();

        if (typeof Headers !== 'undefined' && opts.headers instanceof Headers) {
          if (currentToken && !opts.headers.has('Authorization')) {
            opts.headers.set('Authorization', 'Bearer ' + currentToken);
            opts.headers.set('X-Session-Token', currentToken);
          }
          if (tgObj?.initData && !opts.headers.has('X-Telegram-Init-Data')) {
            opts.headers.set('X-Telegram-Init-Data', tgObj.initData);
          }
        } else if (Array.isArray(opts.headers)) {
          if (currentToken) {
            opts.headers.push(['Authorization', 'Bearer ' + currentToken]);
            opts.headers.push(['X-Session-Token', currentToken]);
          }
          if (tgObj?.initData) {
            opts.headers.push(['X-Telegram-Init-Data', tgObj.initData]);
          }
        } else {
          opts.headers = opts.headers || {};
          if (currentToken) {
            opts.headers['Authorization'] = 'Bearer ' + currentToken;
            opts.headers['X-Session-Token'] = currentToken;
          }
          if (tgObj?.initData) {
            opts.headers['X-Telegram-Init-Data'] = tgObj.initData;
          }
        }
      }
      return _origFetch.call(this, url, opts);
    };
    root._ghstoreFetchIntercepted = true;
  }

  // --- Telegram WebApp SDK Bindings ---
  function getTg() {
    return root.Telegram?.WebApp || null;
  }

  function syncTelegramTheme() {
    const tg = getTg();
    if (!tg) return;
    const storedTheme = root.localStorage?.getItem('ghstore_theme');
    const activeTheme = storedTheme || (tg.colorScheme === 'light' ? 'light' : 'dark');
    if (root.setAppTheme) {
      root.setAppTheme(activeTheme);
    } else {
      const isDark = (activeTheme === 'dark');
      try {
        if (tg.setHeaderColor) {
          tg.setHeaderColor(isDark ? '#090e1a' : '#f8fafc');
        }
        if (tg.setBackgroundColor) {
          tg.setBackgroundColor(isDark ? '#090e1a' : '#f8fafc');
        }
        if (tg.setBottomBarColor) {
          tg.setBottomBarColor(isDark ? '#151d30' : '#ffffff');
        }
      } catch (_) {}
    }
  }

  function initTelegramPlatform() {
    const tg = getTg();
    if (!tg) return;
    try { tg.ready?.(); } catch (_) {}
    try { tg.expand?.(); } catch (_) {}
    if (tg.isVersionAtLeast?.('7.7')) {
      try { tg.disableVerticalSwipes?.(); } catch (_) {}
    }
    if (tg.enableClosingConfirmation) {
      try { tg.enableClosingConfirmation(); } catch (_) {}
    }
    if (tg.BackButton) {
      try { tg.BackButton.hide(); } catch (_) {}
    }
    if (tg.SettingsButton) {
      try {
        tg.SettingsButton.show();
        tg.SettingsButton.onClick(() => {
          if (root.switchTab) root.switchTab('settings');
        });
      } catch (_) {}
    }

    // Sync chrome colors with Telegram theme
    syncTelegramTheme();

    // Safe area, theme, and viewport listeners
    try {
      tg.onEvent?.('safeAreaChanged', updateSafeAreaInsets);
      tg.onEvent?.('contentSafeAreaChanged', updateSafeAreaInsets);
      tg.onEvent?.('themeChanged', syncTelegramTheme);
      tg.onEvent?.('viewportChanged', ({ isStateStable }) => {
        if (isStateStable && tg.viewportStableHeight) {
          document.documentElement.style.setProperty('--viewport-height', tg.viewportStableHeight + 'px');
          document.documentElement.style.setProperty('--tg-viewport-stable-height', tg.viewportStableHeight + 'px');
        }
        updateSafeAreaInsets();
      });
    } catch (_) {}
  }

  function updateSafeAreaInsets() {
    const tg = getTg();
    let top = 0;
    let bottom = 0;
    if (tg) {
      if (tg.isFullscreen) {
        if (tg.contentSafeAreaInset?.top) top = tg.contentSafeAreaInset.top;
        else if (tg.safeAreaInset?.top) top = tg.safeAreaInset.top;
      }
      if (tg.safeAreaInset?.bottom) bottom = Math.max(bottom, tg.safeAreaInset.bottom);
      if (tg.contentSafeAreaInset?.bottom) bottom = Math.max(bottom, tg.contentSafeAreaInset.bottom);
    }
    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.style.setProperty('--safe-top', top + 'px');
      document.documentElement.style.setProperty('--tma-safe-top', top + 'px');
      document.documentElement.style.setProperty('--safe-bottom', bottom + 'px');
      document.documentElement.style.setProperty('--tma-safe-bottom', bottom + 'px');
    }
  }

  function haptic(type = 'light') {
    const tg = getTg();
    if (!tg?.HapticFeedback) return;
    try {
      if (['light', 'medium', 'heavy', 'rigid', 'soft'].includes(type)) {
        tg.HapticFeedback.impactOccurred(type);
      } else if (['error', 'success', 'warning'].includes(type)) {
        tg.HapticFeedback.notificationOccurred(type);
      } else if (type === 'pop' || type === 'selection') {
        tg.HapticFeedback.selectionChanged();
      }
    } catch (_) {}
  }

  function cloudStorageSet(key, value) {
    const tg = getTg();
    try {
      if (tg?.CloudStorage?.setItem) {
        tg.CloudStorage.setItem(key, String(value), (err) => {
          if (err) console.debug('CloudStorage set error:', err);
        });
      }
    } catch (_) {}
  }

  function cloudStorageGet(key, callback) {
    const tg = getTg();
    try {
      if (tg?.CloudStorage?.getItem) {
        tg.CloudStorage.getItem(key, (err, val) => {
          if (!err && val !== undefined && val !== null && val !== '') {
            callback(val);
          }
        });
      }
    } catch (_) {}
  }

  // --- Synthesized Web Audio Micro-Clicks ---
  let audioCtx = null;
  function initAudio() {
    if (audioCtx) return;
    try {
      const AudioContext = root.AudioContext || root.webkitAudioContext;
      if (AudioContext) audioCtx = new AudioContext();
    } catch (_) {}
  }

  function playAudioTick() {
    if (!audioCtx) initAudio();
    if (!audioCtx) return;
    try {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, audioCtx.currentTime + 0.03);
      gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.03);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.03);
    } catch (_) {}
  }

  function playAudioPop() {
    if (!audioCtx) initAudio();
    if (!audioCtx) return;
    try {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(320, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(80, audioCtx.currentTime + 0.07);
      gain.gain.setValueAtTime(0.06, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.07);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.07);
    } catch (_) {}
  }

  function playAudioChime() {
    if (!audioCtx) initAudio();
    if (!audioCtx) return;
    try {
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime + i * 0.04);
        gain.gain.setValueAtTime(0.05, audioCtx.currentTime + i * 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + i * 0.04 + 0.18);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(audioCtx.currentTime + i * 0.04);
        osc.stop(audioCtx.currentTime + i * 0.04 + 0.18);
      });
    } catch (_) {}
  }

  // --- Confetti Animation ---
  function fireConfetti() {
    const canvas = document.getElementById('confetti-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = root.innerWidth || 360;
    canvas.height = root.innerHeight || 640;
    canvas.style.display = 'block';

    const colors = ['#38bdf8', '#34d399', '#f43f5e', '#fbbf24', '#a855f7'];
    const particles = [];
    for (let i = 0; i < 60; i++) {
      particles.push({
        x: canvas.width / 2,
        y: canvas.height / 2,
        vx: (Math.random() - 0.5) * 12,
        vy: (Math.random() - 0.5) * 12 - 4,
        size: Math.random() * 6 + 3,
        color: colors[Math.floor(Math.random() * colors.length)],
        life: 1,
        decay: Math.random() * 0.02 + 0.015
      });
    }

    function render() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      let alive = false;
      for (const p of particles) {
        if (p.life > 0) {
          alive = true;
          p.x += p.vx;
          p.y += p.vy;
          p.vy += 0.25; // gravity
          p.life -= p.decay;
          ctx.globalAlpha = Math.max(0, p.life);
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      if (alive) {
        requestAnimationFrame(render);
      } else {
        canvas.style.display = 'none';
      }
    }
    render();
  }

  // --- Toast Notification ---
  let toastTimeout = null;
  function showToast(msg, duration = 2500) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove('show', 'visible');
    // Trigger reflow to restart css animation if already shown
    void toast.offsetWidth;
    toast.classList.add('show', 'visible');
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      toast.classList.remove('show', 'visible');
    }, duration);
  }

  // --- Centralized Navigation Stack ---
  const navStack = [];

  function pushNav(name, onBack) {
    navStack.push({ name, onBack });
    const tg = getTg();
    if (tg?.BackButton) {
      try {
        tg.BackButton.show();
        tg.BackButton.onClick(handleNativeBack);
      } catch (_) {}
    }
  }

  function popNav() {
    if (navStack.length === 0) return null;
    const item = navStack.pop();
    if (typeof item.onBack === 'function') {
      try { item.onBack(); } catch (e) { console.error('Error in nav onBack:', e); }
    }
    const tg = getTg();
    if (navStack.length === 0 && tg?.BackButton) {
      try { tg.BackButton.hide(); } catch (_) {}
    }
    return item;
  }

  function handleNativeBack() {
    haptic('light');
    popNav();
  }

  // --- SWR Cache Storage ---
  function swrSet(key, data) {
    try {
      root.localStorage?.setItem('swr_' + key, JSON.stringify({ data, time: Date.now() }));
    } catch (_) {}
  }

  function swrGet(key, maxAgeMs = 120000) {
    try {
      const raw = root.localStorage?.getItem('swr_' + key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Date.now() - parsed.time < maxAgeMs) {
        return parsed.data;
      }
    } catch (_) {}
    return null;
  }

  // --- Shared Reactive State Store ---
  let initialUserId = null;
  try {
    const urlP = typeof root.location !== 'undefined' ? new URLSearchParams(root.location.search) : null;
    const tg = root.Telegram?.WebApp;
    initialUserId = Number(tg?.initDataUnsafe?.user?.id || urlP?.get('tg_id') || 0) || null;
  } catch (_) {}

  const AppState = {
    userId: initialUserId,
    userData: null,
    currentAppLanguage: 'ar',
    activeTab: 'store',
    currentCurrency: 'USD',
    sypRate: null,
    starsUsdRate: null,
    categoriesList: [],
    allProducts: [],
    selectedProduct: null,
    selectedQty: 1,
    wishlistSet: new Set(),
    appliedCoupon: null,
    cartMap: {},
    currentStoreLogo: ''
  };

  // --- Translation Dictionary (i18n) ---
  const i18nDict = {
    ar: {
      'tab-store': 'المتجر',
      'tab-orders': 'العمليات',
      'tab-wallet': 'المحفظة',
      'tab-settings': 'الإعدادات',
      'quick-all': 'الكل',
      'quick-in-stock': 'متوفر فوراً',
      'quick-subscriptions': 'اشتراكات',
      'quick-games': 'ألعاب وشحن',
      'quick-software': 'برامج ومفاتيح',
      'search-placeholder': 'ابحث عن الخدمات والباقات...',
      'btn-buy': 'شراء فوري',
      'btn-add-cart': 'أضف للسلة',
      'btn-view-all': 'عرض جميع الباقات',
      'cart-drawer-title': 'سلة المشتريات',
      'cart-total': 'المجموع الكلي:',
      'cart-checkout-btn': 'إتمام الطلب والدفع',
      'cart-empty': 'السلة فارغة حالياً',
      'wallet-title': 'محفظة الحساب',
      'wallet-balance': 'الرصيد المتاح:',
      'wallet-recharge': 'شحن الرصيد',
      'wallet-method-stars': 'تيليجرام ستارز ⭐',
      'wallet-method-crypto': 'عملات رقمية (USDT)',
      'wallet-method-shamcash': 'شام كاش',
      'wallet-method-syriatel': 'سيريتل كاش',
      'orders-title': 'سجل العمليات والطلبات',
      'order-status-completed': 'مكتمل ✅',
      'order-status-pending': 'قيد المعالجة ⏳',
      'order-status-failed': 'ملغى ومسترد ↩️',
      'order-copy-keys': 'نسخ البيانات',
      'order-support': 'طلب مساعدة',
      'settings-title': 'إعدادات الحساب',
      'settings-lang': 'اللغة / Language',
      'settings-currency': 'العملة المفضلة',
      'settings-theme': 'المظهر',
      'theme-dark': 'داكن 🌙',
      'theme-light': 'فاتح ☀️',
      'btn-copy': 'نسخ',
      'toast-copied': 'تم النسخ بنجاح!',
      'recovery-detected': 'تم رصد عملية شراء قيد المتابعة. جاري الاستعادة...'
    },
    en: {
      'tab-store': 'Store',
      'tab-orders': 'Orders',
      'tab-wallet': 'Wallet',
      'tab-settings': 'Settings',
      'quick-all': 'All',
      'quick-in-stock': 'In Stock',
      'quick-subscriptions': 'Subscriptions',
      'quick-games': 'Games & Top-up',
      'quick-software': 'Software & Keys',
      'search-placeholder': 'Search services and plans...',
      'btn-buy': 'Buy Now',
      'btn-add-cart': 'Add to Cart',
      'btn-view-all': 'View all variants',
      'cart-drawer-title': 'Shopping Cart',
      'cart-total': 'Total:',
      'cart-checkout-btn': 'Checkout & Pay',
      'cart-empty': 'Your cart is empty',
      'wallet-title': 'Account Wallet',
      'wallet-balance': 'Available Balance:',
      'wallet-recharge': 'Top-up Balance',
      'wallet-method-stars': 'Telegram Stars ⭐',
      'wallet-method-crypto': 'Crypto (USDT)',
      'wallet-method-shamcash': 'Sham Cash',
      'wallet-method-syriatel': 'Syriatel Cash',
      'orders-title': 'Order History',
      'order-status-completed': 'Completed ✅',
      'order-status-pending': 'Processing ⏳',
      'order-status-failed': 'Cancelled & Refunded ↩️',
      'order-copy-keys': 'Copy Credentials',
      'order-support': 'Get Support',
      'settings-title': 'Account Settings',
      'settings-lang': 'Language / اللغة',
      'settings-currency': 'Preferred Currency',
      'settings-theme': 'Appearance',
      'theme-dark': 'Dark 🌙',
      'theme-light': 'Light ☀️',
      'btn-copy': 'Copy',
      'toast-copied': 'Copied successfully!',
      'recovery-detected': 'Pending purchase detected. Recovering...'
    }
  };

  function t(key, fallback = '') {
    const lang = AppState.currentAppLanguage || 'ar';
    return i18nDict[lang]?.[key] || i18nDict['ar']?.[key] || fallback || key;
  }

  // --- Language & Layout Direction Switcher ---
  function applyLanguage(lang) {
    const valid = (lang === 'en') ? 'en' : 'ar';
    AppState.currentAppLanguage = valid;
    try {
      root.localStorage?.setItem('ghstore_lang', valid);
      cloudStorageSet('ghstore_lang', valid);
    } catch (_) {}

    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.lang = valid;
      document.documentElement.dir = (valid === 'ar') ? 'rtl' : 'ltr';

      if (valid === 'en') {
        document.documentElement.classList.add('lang-en');
        document.documentElement.classList.remove('lang-ar');
      } else {
        document.documentElement.classList.add('lang-ar');
        document.documentElement.classList.remove('lang-en');
      }

      // Update Tab Labels
      ['store', 'orders', 'wallet', 'settings'].forEach(tab => {
        const el = document.getElementById(`i18n-tab-${tab}`);
        if (el) el.textContent = t(`tab-${tab}`);
      });

      // Update Search Bar Placeholder
      const search = document.getElementById('search-input');
      if (search) search.placeholder = t('search-placeholder');

      // Update All [data-i18n] elements
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const k = el.getAttribute('data-i18n');
        if (k && i18nDict[valid]?.[k]) {
          el.textContent = i18nDict[valid][k];
        }
      });
    }
  }

  // --- Keyboard Behavior & Focus Management ---
  function initKeyboardBehavior() {
    if (typeof document === 'undefined') return;

    // 1. Global Escape key listener: closes topmost modal in navStack
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' || e.keyCode === 27) {
        if (navStack.length > 0) {
          e.preventDefault();
          popNav();
        }
      }
    });

    // 2. Mobile keyboard handling: toggle body.keyboard-open and scroll focused input smoothly into view
    document.addEventListener('focusin', (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) {
        if (document.body) document.body.classList.add('keyboard-open');
        setTimeout(() => {
          try {
            e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          } catch (_) {}
        }, 280);
      }
    });

    document.addEventListener('focusout', (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) {
        setTimeout(() => {
          const activeTag = document.activeElement?.tagName;
          if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag)) {
            if (document.body) document.body.classList.remove('keyboard-open');
          }
        }, 120);
      }
    });

    // 3. Visual Viewport resize listener for soft-keyboard detection
    if (typeof window !== 'undefined' && window.visualViewport) {
      window.visualViewport.addEventListener('resize', () => {
        const isKeyboardOpen = window.visualViewport.height < (window.innerHeight * 0.75);
        if (document.body) document.body.classList.toggle('keyboard-open', isKeyboardOpen);
      });
    }
  }

  if (typeof document !== 'undefined') {
    initKeyboardBehavior();
  }
  function escapeAttr(str) {
    if (root.StorefrontSecurity?.escapeHtml) {
      return root.StorefrontSecurity.escapeHtml(str);
    }
    return String(str ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  const escAttr = escapeAttr;

  function assetUrl(url) {
    const raw = String(url ?? '').trim();
    if (!raw) return '';
    if (root.StorefrontSecurity?.safeUrl) {
      const safe = root.StorefrontSecurity.safeUrl(raw, true);
      return safe.replace(/["'<>\\()]/g, encodeURIComponent);
    }
    return raw.replace(/["'<>\\()]/g, encodeURIComponent);
  }

  function thumbImg(url, altText) {
    const safeSrc = assetUrl(url);
    const safeAlt = escapeAttr(altText || '');
    if (!safeSrc) return '';
    return `<img src="${safeSrc}" alt="${safeAlt}" loading="lazy" class="catalog-thumb-img">`;
  }

  function formatRichDescription(raw) {
    if (!raw) return '';
    if (root.StorefrontSecurity?.sanitizeRichHtml) {
      // Parse markdown-like headings, bold, bullet points
      let formatted = String(raw)
        .replace(/^### (.*$)/gim, '<div class="desc-heading">$1</div>')
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
        .replace(/\[(.*?)\]\((https?:\/\/.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="desc-link">$1</a>')
        .replace(/^- (.*$)/gim, '<div class="desc-bullet">• $1</div>')
        .replace(/\n/g, '<br>');
      return root.StorefrontSecurity.sanitizeRichHtml(formatted);
    }
    return escapeAttr(raw);
  }

  function instructionStepsHTML(steps) {
    if (!Array.isArray(steps) || steps.length === 0) return '';
    return steps.map((step, idx) => {
      const safe = formatRichDescription(step);
      return `<div class="instruction-step-item"><span class="step-num">${idx + 1}</span><div class="step-text">${safe}</div></div>`;
    }).join('');
  }

  function normalizeCredentialItem(raw) {
    if (!raw) return '';
    return String(raw).trim();
  }

  function renderStructuredCredentials(goods) {
    if (!goods || !goods.length) {
      const isAr = (AppState.currentAppLanguage === 'ar');
      return `<div style="padding: 12px; color: var(--warning); text-align: center;">${isAr ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
    }

    const isAr = (AppState.currentAppLanguage === 'ar');
    const normalizedGoods = goods.map(g => normalizeCredentialItem(g)).filter(Boolean);

    if (!normalizedGoods.length) {
      const isAr = (AppState.currentAppLanguage === 'ar');
      return `<div style="padding: 12px; color: var(--warning); text-align: center;">${isAr ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
    }

    const renderedRows = normalizedGoods.map(rawLine => {
      const line = String(rawLine).trim();

      // 1. If it's an activation / direct subscription link (e.g. Gemini, Google One, Canva, etc.)
      if (line.startsWith('http://') || line.startsWith('https://')) {
        const isGemini = line.toLowerCase().includes('google') || line.toLowerCase().includes('gemini');
        let hostName = 'serviceactivation.google.com';
        try {
          const u = new URL(line);
          hostName = u.hostname || hostName;
        } catch (e) {}

        const badgeText = isGemini
          ? (isAr ? '✨ كود تفعيل اشتراك Gemini Pro المعتمد' : '✨ Gemini Pro Activation Token')
          : (isAr ? '✨ كود تفعيل الاشتراك المباشر' : '✨ Direct Activation Token');

        const activateBtnText = isAr
          ? '⚡ تفعيل حسابك الآن عبر هذا الرابط'
          : '⚡ Activate Your Account using this Token';

        const copyBtnText = isAr
          ? '📋 نسخ رابط التفعيل المباشر'
          : '📋 Copy Direct Activation Link';

        const hintText = isAr
          ? '💡 اضغط على الزر البنفسجي بالأعلى لفتح الرابط وتفعيل حسابك فورياً، أو انسخ الرابط لفتحه في متصفحك.'
          : '💡 Tap the button above to activate your account directly, or copy the token link to open in your browser.';

        return `
          <div class="inset-card" style="margin: 8px 0 14px 0; border: 1px solid rgba(168, 85, 247, 0.45); background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(56, 189, 248, 0.08)); padding: 16px; border-radius: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <span class="pill-badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; font-size: 11px; font-weight: 800; padding: 4px 10px;">
                ${badgeText}
              </span>
              <span style="font-size: 11px; color: var(--hint); font-weight: 700;">1-Tap Token</span>
            </div>

            <!-- Spacious, Elegant URL Container with Domain Header -->
            <div style="background: var(--input-bg); border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 12px; padding: 12px; margin-bottom: 14px; box-shadow: inset 0 2px 6px rgba(0,0,0,0.25);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px dashed var(--border); padding-bottom: 6px; flex-wrap: wrap; gap: 4px;">
                <span style="font-size: 11px; font-weight: 800; color: var(--accent); font-family: monospace; display: inline-flex; align-items: center; gap: 4px; word-break: break-all;">
                  🌐 ${escapeAttr(hostName)}
                </span>
                <span style="font-size: 10px; color: var(--success); font-weight: 700; white-space: nowrap;">
                  ↗ ${isAr ? 'رابط خارجي' : 'External Link'}
                </span>
              </div>
              <div style="font-family: monospace; font-size: 11px; color: var(--text); word-break: break-all; line-height: 1.6; user-select: all; max-height: 180px; overflow-y: auto; padding: 4px 2px;">
                ${escapeAttr(line)}
              </div>
            </div>

            <!-- Big Prominent Activation Button -->
            <button type="button" class="btn-action-primary" data-payment-url="${escapeAttr(line)}" onclick="openExternalPaymentUrl(this.dataset.paymentUrl)" style="width: 100%; height: 50px; font-size: 13.5px; font-weight: 800; background: linear-gradient(135deg, #a855f7, #6366f1); border-radius: 12px; box-shadow: 0 4px 16px rgba(168, 85, 247, 0.35); display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 8px; border: none; color: white; cursor: pointer;">
              <span>${activateBtnText}</span>
            </button>

            <!-- Clean Separated Copy Button -->
            <button type="button" class="btn-action-secondary" data-copy="${escapeAttr(line)}" onclick="copyFromBtn(this)" style="width: 100%; height: 40px; font-size: 12px; font-weight: 700; border-radius: 10px; border-color: rgba(168, 85, 247, 0.4); color: var(--text); display: flex; align-items: center; justify-content: center; gap: 6px;">
              <span>${copyBtnText}</span>
            </button>

            <div style="font-size: 10.5px; color: var(--hint); margin-top: 10px; text-align: center; line-height: 1.5;">
              ${hintText}
            </div>
          </div>
        `;
      }

      // 2. Delimiter parsing: pipe '|', slash '/', or colon ':'
      let parts = [];
      if (line.includes(' | ')) { parts = line.split(' | '); }
      else if (line.includes('|')) { parts = line.split('|'); }
      else if (line.includes(' / ')) { parts = line.split(' / '); }
      else if (line.includes(':') && line.split(':').length >= 2) {
        parts = line.split(':');
      }

      if (parts.length >= 2) {
        const rows = parts.map((partRaw, idx) => {
          const part = String(partRaw).trim();
          let label = isAr ? "بيانات" : "Credential";
          if (idx === 0) {
            label = part.includes('@') ? (isAr ? "البريد الإلكتروني" : "Email") : (isAr ? "اسم المستخدم" : "Username");
          } else if (idx === 1) {
            label = isAr ? "كلمة المرور" : "Password";
          } else if (idx === 2) {
            label = part.includes('@') ? (isAr ? "البريد البديل / الاسترداد" : "Recovery Email") : (isAr ? "كود 2FA / الأمان" : "2FA / Security Key");
          } else if (idx === 3) {
            label = isAr ? "رمز الأمان / كلمة سر البديل" : "Security Key / Recovery Pass";
          } else {
            label = isAr ? `معلومة ${idx + 1}` : `Field ${idx + 1}`;
          }

          return `
            <div class="cred-pill-row">
              <div class="cred-meta">
                <span class="cred-type-tag">${label}</span>
                <span class="cred-val-text">${escapeAttr(part)}</span>
              </div>
              <button class="btn-copy-mini" data-copy="${escapeAttr(part)}" onclick="copyFromBtn(this)">${isAr ? 'نسخ' : 'Copy'}</button>
            </div>
          `;
        }).join('');

        return `
          <div class="cred-grid">
            ${rows}
          </div>
        `;
      }

      // 3. Fallback: single license key / code
      return `
        <div class="cred-pill-row" style="margin: 6px 0;">
          <div class="cred-meta">
            <span class="cred-type-tag">${isAr ? 'مفتاح / كود التفعيل' : 'License / Key'}</span>
            <span class="cred-val-text">${escapeAttr(line)}</span>
          </div>
          <button class="btn-copy-mini" data-copy="${escapeAttr(line)}" onclick="copyFromBtn(this)">${isAr ? 'نسخ' : 'Copy'}</button>
        </div>
      `;
    }).join('');

    const hasOnlyUrls = normalizedGoods.every(g => g.startsWith('http://') || g.startsWith('https://'));
    const allText = normalizedGoods.join('\n');
    const copyAllBtn = (hasOnlyUrls || normalizedGoods.length <= 1) ? '' : `
      <div style="margin-top: 8px;">
        <button class="btn-action-secondary" data-copy="${escapeAttr(allText)}" onclick="copyFromBtn(this)" style="height: 34px; font-size: 11px; width: 100%;">
          <span>📋 ${isAr ? 'نسخ كافة بيانات الحساب' : 'Copy All Account Details'}</span>
        </button>
      </div>
    `;

    return renderedRows + copyAllBtn;
  }

  function copyCredVal(val) {
    const text = String(val ?? '').trim();
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(() => {});
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
    }
    haptic('selection');
    showToast(t('toast-copied', 'تم النسخ بنجاح! 📋'));
  }
  root.copyCredVal = copyCredVal;

  // --- Export Namespace ---
  root.StoreAPI = {
    getSessionToken,
    setSessionToken,
    clearSessionToken,
    ensureAuthSession,
    getTg,
    initTelegramPlatform,
    updateSafeAreaInsets,
    haptic,
    cloudStorageSet,
    cloudStorageGet,
    playAudioTick,
    playAudioPop,
    playAudioChime,
    fireConfetti,
    showToast,
    copyCredVal,
    navStack,
    pushNav,
    popNav,
    handleNativeBack,
    swrSet,
    swrGet,
    AppState,
    i18nDict,
    t,
    applyLanguage,
    initKeyboardBehavior,
    escapeAttr,
    escAttr,
    assetUrl,
    thumbImg,
    formatRichDescription,
    instructionStepsHTML,
    normalizeCredentialItem,
    renderStructuredCredentials,
    syncTelegramTheme
  };
  root.syncTelegramTheme = syncTelegramTheme;

})(typeof window !== 'undefined' ? window : globalThis);
