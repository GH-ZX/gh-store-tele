/**
 * GH Store - Main Application Orchestrator & Compatibility Bootstrap (app.js)
 * 
 * Coordinates:
 * - Module integration (StoreAPI, StorefrontModule, WalletModule, StoreCheckout, AdminModule)
 * - Exposes unified global window API for all inline HTML onclick handlers
 * - Preserves security formatter functions for unit and security suites
 * - Boots Telegram WebApp SDK, safe areas, layout directions (RTL/LTR), and theme
 * - Manages real-time SSE stream, keyboard navigation, and automatic Checkout Recovery
 */

    function formatRichDescription(raw) {
      if (!raw) return `<span style="color: var(--hint)">${(window.currentAppLanguage || 'ar') === 'ar' ? 'لا يوجد وصف إضافي.' : 'No additional description.'}</span>`;
      let text = String(raw).trim();

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
      text = text.replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, '<i>$1</i>');

      text = text.replace(/`([^`]+)`/g, '<code class="desc-inline-code">$1</code>');
      text = text.replace(/^[\s]*[-*•]\s+(.+)$/gim, '<div class="desc-bullet">• $1</div>');

      // Make URLs and markdown links clickable safely via placeholders
      const links = [];
      text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/gi, (m, label, url) => {
        const placeholder = '___LINK_' + links.length + '___';
        links.push('<a href="' + escapeAttr(StorefrontSecurity.safeUrl(url)) + '" class="desc-link">' + escapeAttr(label) + '</a>');
        return placeholder;
      });

      text = text.replace(/(https?:\/\/[^\s<"'\)]+)/gi, (url) => {
        const cleanUrl = url.replace(/[.,;]+$/, '');
        const trailing = url.slice(cleanUrl.length);
        const placeholder = '___LINK_' + links.length + '___';
        links.push('<a href="' + escapeAttr(StorefrontSecurity.safeUrl(cleanUrl)) + '" class="desc-link">' + escapeAttr(cleanUrl) + '</a>');
        return placeholder + trailing;
      });

      links.forEach((linkHtml, idx) => {
        text = text.replace('___LINK_' + idx + '___', linkHtml);
      });
      text = text.replace(/\r?\n/g, '<br>');
      text = text.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');

      return StorefrontSecurity.sanitizeRichHtml(text);
    }

    function escapeAttr(str) {
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function escAttr(s) {
      return StorefrontSecurity.escapeHtml(s);
    }

    function instructionStepsHTML(steps) {
      return steps.map((step, idx) => `<div class="instr-step"><span class="instr-step-num">${idx + 1}</span><span class="instr-step-text">${formatRichDescription(step)}</span></div>`).join('');
    }

    function normalizeCredentialItem(raw) {
      if (!raw) return '';
      if (typeof raw === 'object' && raw !== null) {
        return (
          raw.account_data || raw.value || raw.data || raw.credentials || raw.key || raw.code || raw.token ||
          (raw.email && raw.password ? `${raw.email}:${raw.password}` : null) ||
          (raw.username && raw.password ? `${raw.username}:${raw.password}` : null) ||
          JSON.stringify(raw)
        );
      }
      let s = String(raw).trim();
      if (s.startsWith('{') && s.endsWith('}')) {
        try {
          const parsed = JSON.parse(s);
          if (typeof parsed === 'object' && parsed !== null) {
            return normalizeCredentialItem(parsed);
          }
        } catch (e) {}
        const m = s.match(/['"](?:account_data|value|data|credentials|key|code|token)['"]\s*:\s*['"]([^'"]+)['"]/);
        if (m && m[1]) return m[1];
      }
      return s;
    }

    function renderStructuredCredentials(goods) {
      if (!goods || !goods.length) {
        return `<div style="padding: 12px; color: var(--warning); text-align: center;">${(window.currentAppLanguage || 'ar') === 'ar' ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
      }

      const isAr = ((window.currentAppLanguage || 'ar') === 'ar');
      const normalizedGoods = goods.map(g => normalizeCredentialItem(g)).filter(Boolean);

      if (!normalizedGoods.length) {
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
      const copyAllBtn = hasOnlyUrls ? '' : `
        <div style="margin-top: 8px;">
          <button class="btn-action-secondary" data-copy="${escapeAttr(allText)}" onclick="copyFromBtn(this)" style="height: 34px; font-size: 11px; width: 100%;">
            <span>📋 ${isAr ? 'نسخ كافة بيانات الحساب' : 'Copy All Account Details'}</span>
          </button>
        </div>
      `;

      return renderedRows + copyAllBtn;
    }

    function assetUrl(u) {
      if (!u) return '';
      let clean = StorefrontSecurity.safeUrl(u, true);
      if (!clean) return '';
      // These URLs are also used in CSS url('...') inside HTML attributes.
      clean = clean.replace(/['"()\\<>]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
      if (String(u).trim().startsWith('/static/img/')) {
        const v = localStorage.getItem('ghstore_build') || '4';
        return clean + (clean.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(v);
      }
      return clean;
    }

    function thumbImg(src, name) {
      const safe = escAttr(assetUrl(src));
      const nm = escAttr(name);
      return '<img src="' + safe + '" alt="' + nm + '" loading="lazy" data-n="' + nm + '" onerror="window.__thumbErr(this)">';
    }

(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};
  const storefront = () => root.StorefrontModule || {};
  const wallet = () => root.WalletModule || {};
  const checkout = () => root.StoreCheckout || {};
  const admin = () => root.AdminModule || {};
  const sms = () => root.SmsModule || {};

  // --- Tab Navigation ---
  function switchTab(tab) {
    state().activeTab = tab;
    api().haptic?.('selection');

    ['store', 'orders', 'wallet', 'settings'].forEach(t => {
      const tabBtn = document.getElementById(`tab-${t}`);
      const viewEl = document.getElementById(`view-${t}`);
      if (tabBtn) tabBtn.classList.toggle('active', t === tab);
      if (viewEl) viewEl.style.display = (t === tab) ? 'block' : 'none';
    });

    if (tab === 'orders') loadUserOrders();
    else if (tab === 'wallet') wallet().renderWalletBalances();
  }

  // --- Copy Credential Helper ---
  function copyCredFromBtn(btn) {
    if (!btn) return;
    const val = btn.getAttribute('data-copy') || '';
    if (!val) return;
    navigator.clipboard?.writeText(val);
    api().haptic?.('light');
    api().showToast(api().t('toast-copied', 'تم النسخ بنجاح!'));
  }

  function copyFromBtn(btn) {
    copyCredFromBtn(btn);
  }

  // --- Data Loading & Synchronization ---
  async function loadStorefrontData() {
    try {
      const res = await fetch('/api/catalog');
      if (res.ok) {
        const data = await res.json();
        state().categoriesList = data.categories || [];
        state().allProducts = data.products || [];
        storefront().renderCategories(state().categoriesList);
        storefront().renderStorefrontFolderCards(state().allProducts);
      }
    } catch (e) {
      console.warn('Failed to fetch catalog:', e);
    }
  }

  async function loadUserData() {
    try {
      const res = await fetch('/api/user/me');
      if (res.ok) {
        const data = await res.json();
        state().userData = data;
        state().userId = data.telegram_id || data.tg_id;
        wallet().renderWalletBalances(data);
      }
    } catch (e) {
      console.warn('Failed to fetch user data:', e);
    }
  }

  async function loadUserOrders() {
    const listEl = document.getElementById('orders-history-list');
    if (!listEl) return;
    listEl.innerHTML = '<div class="loading-spinner">جاري تحميل العمليات...</div>';

    try {
      const res = await fetch('/api/orders');
      if (res.ok) {
        const data = await res.json();
        const orders = data.orders || [];
        if (orders.length === 0) {
          listEl.innerHTML = '<div class="empty-state-card">لا توجد عمليات سابقة حتى الآن</div>';
          return;
        }
        const isAr = (state().currentAppLanguage === 'ar');
        listEl.innerHTML = orders.map(o => `
          <div class="order-history-card">
            <div class="order-card-header">
              <span class="order-card-id">#${o.id}</span>
              <span class="order-card-status status-${o.status}">${isAr ? (o.status === 'completed' ? 'مكتمل ✅' : 'قيد المعالجة ⏳') : o.status}</span>
            </div>
            <div class="order-card-total">$${Number(o.total_sell || 0).toFixed(2)}</div>
          </div>
        `).join('');
      }
    } catch (_) {
      listEl.innerHTML = '<div class="empty-state-card">فشل تحميل سجل العمليات</div>';
    }
  }

  // --- Real-Time Server Sent Events (SSE) ---
  function initSSE() {
    try {
      const sse = new EventSource('/api/events');
      sse.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (ev.type === 'order_updated') loadUserOrders();
          else if (ev.type === 'balance_updated') loadUserData();
          else if (ev.type === 'catalog_synced') loadStorefrontData();
        } catch (_) {}
      };
    } catch (_) {}
  }

  // --- Master App Startup Sequence ---
  function bootApp() {
    // 1. Initialize Telegram platform & viewport
    api().initTelegramPlatform?.();
    api().updateSafeAreaInsets?.();

    // 2. Language & Layout direction setup (RTL vs LTR)
    const savedLang = root.localStorage?.getItem('ghstore_lang') || 'ar';
    api().applyLanguage?.(savedLang);

    // 3. Initialize Keyboard navigation behavior
    api().initKeyboardBehavior?.();

    // 4. Bind Search Input Keyboard Events (Enter key triggers search)
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          storefront().filterCatalog(searchInput.value);
          searchInput.blur();
        }
      });
      searchInput.addEventListener('input', () => {
        storefront().filterCatalog(searchInput.value);
      });
    }

    // 5. Bind Coupon Input Keyboard Events (Enter key triggers validation)
    const couponInput = document.getElementById('coupon-input');
    if (couponInput) {
      couponInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          checkout().applyCoupon(couponInput.value);
        }
      });
    }

    // 6. Initialize Cart & Flash Sale Timer
    checkout().initCart?.();
    storefront().initFlashSaleTimer?.();

    // 7. Load Data & Connect SSE
    loadStorefrontData();
    loadUserData();
    initSSE();

    // 8. Durable Checkout Recovery on Startup
    checkout().recoverPendingCheckout?.();
  }

  // Attach all functions to window for backward compatibility with inline HTML attributes
  root.formatRichDescription = formatRichDescription;
  root.escapeAttr = escapeAttr;
  root.escAttr = escAttr;
  root.instructionStepsHTML = instructionStepsHTML;
  root.normalizeCredentialItem = normalizeCredentialItem;
  root.renderStructuredCredentials = renderStructuredCredentials;
  root.assetUrl = assetUrl;
  root.thumbImg = thumbImg;

  root.switchTab = switchTab;
  root.applyLanguage = (lang) => api().applyLanguage?.(lang);
  root.copyCredFromBtn = copyCredFromBtn;
  root.copyFromBtn = copyFromBtn;
  root.loadStorefrontData = loadStorefrontData;
  root.loadUserData = loadUserData;

  // Storefront Proxies
  root.switchCategoryViewMode = (m) => storefront().switchCategoryViewMode?.(m);
  root.selectCategory = (c) => storefront().selectCategory?.(c);
  root.openProductModal = (p) => storefront().openProductModal?.(p);
  root.openProductModalById = (id) => storefront().openProductModalById?.(id);
  root.closeProductModal = () => storefront().closeProductModal?.();
  root.filterCatalog = (q) => storefront().filterCatalog?.(q);
  root.openReviewsModal = () => storefront().openReviewsModal?.();
  root.closeReviewsModal = () => storefront().closeReviewsModal?.();
  root.openSupportModal = () => storefront().openSupportModal?.();
  root.closeSupportModal = () => storefront().closeSupportModal?.();

  // Wallet Proxies
  root.setCurrencyPreference = (c) => wallet().setCurrencyPreference?.(c);
  root.selectRechargeMethod = (m) => wallet().selectRechargeMethod?.(m);
  root.setShamCurrency = (c) => wallet().setShamCurrency?.(c);
  root.setRechargeAmount = (a) => wallet().setRechargeAmount?.(a);
  root.submitRechargeRequest = () => wallet().submitRechargeRequest?.();
  root.submitRedeemVoucher = () => wallet().submitRedeemVoucher?.();
  root.openReceiptModal = (id) => wallet().openReceiptModal?.(id);
  root.closeReceiptPreviewModal = () => wallet().closeReceiptPreviewModal?.();
  root.openVipBenefitsModal = () => wallet().openVipBenefitsModal?.();
  root.closeVipBenefitsModal = () => wallet().closeVipBenefitsModal?.();

  // Checkout Proxies
  root.openCartDrawer = () => checkout().openCartDrawer?.();
  root.closeCartDrawer = () => checkout().closeCartDrawer?.();
  root.addToCartCurrentProduct = () => {
    if (state().selectedProduct) checkout().addToCart?.(state().selectedProduct, state().selectedQty || 1);
  };
  root.changeCartQty = (pid, d) => checkout().changeCartQty?.(pid, d);
  root.removeFromCart = (pid) => checkout().removeFromCart?.(pid);
  root.clearEntireCart = () => checkout().clearEntireCart?.();
  root.executeCartCheckout = () => checkout().executeCartCheckout?.();
  root.buyNow = (p, q, f) => checkout().buyNow?.(p, q, f);
  root.applyCoupon = (c) => checkout().applyCoupon?.(c);

  // Admin Proxies
  root.openAdminProductModal = (id) => admin().openAdminProductModal?.(id);
  root.closeAdminProductModal = () => admin().closeAdminProductModal?.();
  root.submitAdminProductUpdate = () => admin().submitAdminProductUpdate?.();
  root.openAdminCategoryModal = (id) => admin().openAdminCategoryModal?.(id);
  root.closeAdminCategoryModal = () => admin().closeAdminCategoryModal?.();
  root.openAdminFolderModal = (k) => admin().openAdminFolderModal?.(k);
  root.closeAdminFolderModal = () => admin().closeAdminFolderModal?.();
  root.setAdminBalanceAction = (a) => admin().setAdminBalanceAction?.(a);
  root.setAdminBalAmount = (a) => admin().setAdminBalAmount?.(a);
  root.submitAdminAdjustBalance = () => admin().submitAdminAdjustBalance?.();
  root.submitAdminRevokeSessions = (id) => admin().submitAdminRevokeSessions?.(id);
  root.submitAdminUnrevokeSessions = (id) => admin().submitAdminUnrevokeSessions?.(id);
  root.submitAdminUpdateSypRate = () => admin().submitAdminUpdateSypRate?.();
  root.submitAdminUpdateStoreLogo = () => admin().submitAdminUpdateStoreLogo?.();

  // SMS Activation Proxies
  root.openSmsModal = () => sms().openSmsModal?.();
  root.closeSmsModal = () => sms().closeSmsModal?.();
  root.onSmsSelectionChange = () => sms().onSmsSelectionChange?.();
  root.executeBuySms = () => sms().executeBuySms?.();
  root.copyAllocatedPhone = () => sms().copyAllocatedPhone?.();
  root.copyReceivedCode = () => sms().copyReceivedCode?.();
  root.executeCancelSms = () => sms().executeCancelSms?.();
  root.executeBanSms = () => sms().executeBanSms?.();
  root.openAdminSmsModal = () => sms().openAdminSmsModal?.();
  root.closeAdminSmsModal = () => sms().closeAdminSmsModal?.();
  root.loadAdminSmsSettings = () => sms().loadAdminSmsSettings?.();
  root.toggleAdminSmsService = (c, e) => sms().toggleAdminSmsService?.(c, e);
  root.toggleAdminSmsCountry = (c, e) => sms().toggleAdminSmsCountry?.(c, e);

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bootApp);
    } else {
      bootApp();
    }
  }

})(typeof window !== 'undefined' ? window : globalThis);
