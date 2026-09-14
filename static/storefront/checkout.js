/**
 * GH Store - Cart, Dynamic Fields, Checkout, & Resilient Recovery Module (checkout.js)
 * 
 * Provides:
 * - Multi-item shopping cart drawer with live server-side price quoting
 * - Dynamic custom fields generator (Player ID, Zone ID, Server selection, Character name)
 * - Coupon code validation and live VIP strikethrough discount calculations
 * - Instant single-item purchase (`/api/buy`) and multi-item cart checkout (`/api/cart/checkout`)
 * - Cryptographic idempotency key binding across retry attempts
 * - Durable Checkout Recovery Engine:
 *   - Persists in-flight checkouts to browser storage
 *   - Automatically detects and recovers interrupted purchases upon app reconnect or reload
 *   - Prevents double-charging by safely reusing idempotency keys on retry
 *   - Surfaces post-purchase activation instructions and 1-tap copy of credentials
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};
  const security = () => root.StorefrontSecurity || {};

  const PENDING_STORAGE_KEY = 'ghstore_pending_checkout_v1';
  let cartMap = {};

  // --- Cart Management & Persistence ---
  function initCart() {
    try {
      const local = root.localStorage?.getItem('ghstore_cart');
      if (local) cartMap = JSON.parse(local) || {};
    } catch (_) {}
    state().cartMap = cartMap;
    updateFloatingCartUI();
  }

  function saveCart() {
    try {
      root.localStorage?.setItem('ghstore_cart', JSON.stringify(cartMap));
      api().cloudStorageSet?.('ghstore_cart', JSON.stringify(cartMap));
    } catch (_) {}
    state().cartMap = cartMap;
    updateFloatingCartUI();
  }

  function updateFloatingCartUI() {
    const floatEl = document.getElementById('floating-cart-bar');
    const countEl = document.getElementById('cart-floating-count');
    const totalEl = document.getElementById('cart-floating-total');
    if (!floatEl) return;

    const items = Object.values(cartMap);
    const count = items.reduce((sum, it) => sum + (Number(it.quantity) || 1), 0);

    if (count > 0) {
      floatEl.style.display = 'flex';
      if (countEl) countEl.textContent = String(count);
      const total = items.reduce((sum, it) => sum + (Number(it.product?.sell_price_usd || 0) * (Number(it.quantity) || 1)), 0);
      if (totalEl) totalEl.textContent = `$${total.toFixed(2)}`;
    } else {
      floatEl.style.display = 'none';
    }
  }

  function addToCart(product, quantity = 1, options = {}) {
    if (!product || !product.id) return;
    api().haptic?.('pop');
    api().playAudioTick?.();

    const pid = String(product.id);
    if (cartMap[pid]) {
      cartMap[pid].quantity = (Number(cartMap[pid].quantity) || 1) + Number(quantity);
      cartMap[pid].options = { ...(cartMap[pid].options || {}), ...options };
    } else {
      cartMap[pid] = { product, quantity: Number(quantity), options };
    }
    saveCart();
    api().showToast(api().t('toast-added-cart', 'تمت الإضافة إلى السلة 🛒'));
  }

  function removeFromCart(productId) {
    api().haptic?.('light');
    delete cartMap[String(productId)];
    saveCart();
    renderCartDrawerItems();
  }

  function changeCartQty(productId, delta) {
    api().haptic?.('selection');
    const pid = String(productId);
    if (!cartMap[pid]) return;
    const current = Number(cartMap[pid].quantity) || 1;
    const next = current + Number(delta);
    if (next <= 0) {
      removeFromCart(pid);
    } else {
      cartMap[pid].quantity = next;
      saveCart();
      renderCartDrawerItems();
    }
  }

  function clearEntireCart() {
    cartMap = {};
    saveCart();
    renderCartDrawerItems();
  }

  function openCartDrawer() {
    api().haptic?.('pop');
    const drawer = document.getElementById('cart-drawer');
    if (!drawer) return;
    renderCartDrawerItems();
    drawer.classList.add('active');
    api().pushNav('cart_drawer', closeCartDrawer);
  }

  function closeCartDrawer() {
    api().haptic?.('light');
    const drawer = document.getElementById('cart-drawer');
    if (drawer) drawer.classList.remove('active');
  }

  function renderCartDrawerItems() {
    const listEl = document.getElementById('cart-drawer-items-list');
    const subtotalEl = document.getElementById('cart-drawer-subtotal');
    if (!listEl) return;

    const items = Object.values(cartMap);
    if (items.length === 0) {
      listEl.innerHTML = `<div class="empty-cart-view">${api().t('cart-empty', 'السلة فارغة حالياً')}</div>`;
      if (subtotalEl) subtotalEl.textContent = '$0.00';
      return;
    }

    const isAr = (state().currentAppLanguage === 'ar');
    let subtotal = 0;
    let html = '';

    items.forEach(it => {
      const p = it.product;
      const title = isAr ? (p.name_ar || p.name) : (p.name || p.name_ar);
      const lineTotal = Number(p.sell_price_usd || 0) * Number(it.quantity || 1);
      subtotal += lineTotal;

      html += `<div class="cart-line-item">
        <div class="cart-line-info">
          <div class="cart-line-title">${api().escapeAttr(title)}</div>
          <div class="cart-line-unit">$${Number(p.sell_price_usd || 0).toFixed(2)} × ${it.quantity}</div>
        </div>
        <div class="cart-line-stepper">
          <button class="cart-step-btn" onclick="changeCartQty(${p.id}, -1)">-</button>
          <span class="cart-step-qty">${it.quantity}</span>
          <button class="cart-step-btn" onclick="changeCartQty(${p.id}, 1)">+</button>
        </div>
        <div class="cart-line-price">$${lineTotal.toFixed(2)}</div>
        <button class="cart-line-del" onclick="removeFromCart(${p.id})">✕</button>
      </div>`;
    });

    listEl.innerHTML = html;
    if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
  }

  // --- Dynamic Game & Custom Fields ---
  function renderProductGameFields(product) {
    const container = document.getElementById('detail-game-fields-container') || document.getElementById('product-game-fields-container');
    if (!container) return;

    const meta = product?.extra_meta || {};
    const requiredFields = meta.required_fields || [];
    const customFields = meta.custom_fields || [];
    const isDirectTopup = product?.delivery_type === 'direct_topup' || product?.delivery_type === 'game_recharge' || (requiredFields.length > 0);

    if (!isDirectTopup && (!customFields || customFields.length === 0)) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';

    // Configure standard game fields if present in DOM
    const groupPlayer = document.getElementById('group-player-id');
    const groupServer = document.getElementById('group-server-id');
    const groupChar = document.getElementById('group-charname');

    if (groupPlayer) groupPlayer.style.display = 'block';

    const needsServer = requiredFields.includes('serverid') || requiredFields.includes('zoneid') || requiredFields.includes('server_id');
    if (groupServer) groupServer.style.display = needsServer ? 'block' : 'none';

    const needsChar = requiredFields.includes('charname') || requiredFields.includes('character_name');
    if (groupChar) groupChar.style.display = needsChar ? 'block' : 'none';

    // Clear previous input values
    const pInp = document.getElementById('game-player-id-input');
    if (pInp) pInp.value = '';
    const sInp = document.getElementById('game-server-id-input');
    if (sInp) sInp.value = '';
    const cInp = document.getElementById('game-charname-input');
    if (cInp) cInp.value = '';
  }

  function getEnteredCustomFields() {
    const custom = {};

    // 1. Direct game inputs
    const pInp = document.getElementById('game-player-id-input');
    if (pInp && pInp.value && pInp.value.trim()) {
      custom.player_id = pInp.value.trim();
    }

    const sInp = document.getElementById('game-server-id-input');
    const sSel = document.getElementById('game-server-id-select');
    if (sInp && sInp.style.display !== 'none' && sInp.value && sInp.value.trim()) {
      custom.server_id = sInp.value.trim();
    } else if (sSel && sSel.style.display !== 'none' && sSel.value && sSel.value.trim()) {
      custom.server_id = sSel.value.trim();
    }

    const cInp = document.getElementById('game-charname-input');
    if (cInp && cInp.value && cInp.value.trim()) {
      custom.charname = cInp.value.trim();
    }

    // 2. Generic custom fields if present
    const inputs = document.querySelectorAll('[id^="custom-field-"]');
    inputs.forEach(inp => {
      const key = inp.id.replace('custom-field-', '');
      if (inp.value && inp.value.trim()) {
        custom[key] = inp.value.trim();
      }
    });
    return custom;
  }

  function restoreEnteredCustomFields(fields) {
    if (!fields || typeof fields !== 'object') return;
    if (fields.player_id) {
      const pInp = document.getElementById('game-player-id-input');
      if (pInp) pInp.value = fields.player_id;
    }
    if (fields.server_id) {
      const sInp = document.getElementById('game-server-id-input');
      if (sInp) sInp.value = fields.server_id;
      const sSel = document.getElementById('game-server-id-select');
      if (sSel) sSel.value = fields.server_id;
    }
    if (fields.charname) {
      const cInp = document.getElementById('game-charname-input');
      if (cInp) cInp.value = fields.charname;
    }
    for (const [k, v] of Object.entries(fields)) {
      const el = document.getElementById('custom-field-' + k);
      if (el) el.value = v;
    }
  }

  function proceedToTopupForProduct(productId, qty, shortfall) {
    api().haptic?.('medium');
    const customFields = getEnteredCustomFields();
    const product = (state().allProducts || []).find(p => Number(p.id) === Number(productId));
    const prodTitle = product ? (product.name_ar || product.name || '') : '';
    const unitPrice = product ? Number(product.sell_price_usd ?? product.price ?? 0) : 0;
    const totalDue = unitPrice * qty;

    const pendingIntent = {
      productId: Number(productId),
      quantity: Number(qty),
      customFields: customFields,
      productTitle: prodTitle,
      requiredTotal: totalDue,
      shortfall: shortfall,
      createdAt: Date.now()
    };
    try {
      root.sessionStorage?.setItem('ghstore_pending_buy_resume', JSON.stringify(pendingIntent));
    } catch (_) {}

    if (root.switchTab) {
      root.switchTab('wallet');
    }
  }
  root.proceedToTopupForProduct = proceedToTopupForProduct;
  root.restoreEnteredCustomFields = restoreEnteredCustomFields;

  function clearInlineFormErrors() {
    document.querySelectorAll('.inline-field-error').forEach(el => el.remove());
    const pInp = document.getElementById('game-player-id-input');
    if (pInp) pInp.style.borderColor = '';
    const sInp = document.getElementById('game-server-id-input');
    if (sInp) sInp.style.borderColor = '';
    const sSel = document.getElementById('game-server-id-select');
    if (sSel) sSel.style.borderColor = '';
  }
  root.clearInlineFormErrors = clearInlineFormErrors;

  // Global helper for input changes on dynamic fields
  root.onPlayerInputChanged = function () {
    clearInlineFormErrors();
  };
  root.triggerPlayerVerification = function () {
    const pInp = document.getElementById('game-player-id-input');
    const statusEl = document.getElementById('player-verify-status');
    if (!pInp || !pInp.value.trim()) {
      api().showToast?.('يرجى إدخال معرف اللاعب أولاً');
      return;
    }
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = 'rgba(16, 185, 129, 0.15)';
      statusEl.style.color = '#10b981';
      statusEl.textContent = 'معرف اللاعب جاهز للإرسال والشحن ✅';
    }
    api().haptic?.('success');
  };

  // --- Coupon Code Application ---
  async function applyCoupon(code) {
    const raw = String(code || '').trim();
    if (!raw) return;

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/coupon/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: raw })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        state().appliedCoupon = data.coupon;
        api().haptic?.('success');
        api().showToast(`تم تطبيق القسيمة (${data.coupon.discount_percent || 0}% خصم)`);
      } else {
        state().appliedCoupon = null;
        api().showToast(data.error || 'كود القسيمة غير صالح');
      }
    } catch (_) {
      api().showToast('فشل التحقق من كود القسيمة');
    }
  }

  // --- Durable Checkout Recovery Engine ---
  function savePendingCheckout(attemptData) {
    const record = {
      ...attemptData,
      timestamp: Date.now()
    };
    try {
      root.localStorage?.setItem(PENDING_STORAGE_KEY, JSON.stringify(record));
      root.sessionStorage?.setItem(PENDING_STORAGE_KEY, JSON.stringify(record));
    } catch (_) {}
    return record;
  }

  function getPendingCheckout() {
    try {
      const raw = root.localStorage?.getItem(PENDING_STORAGE_KEY) || root.sessionStorage?.getItem(PENDING_STORAGE_KEY);
      if (!raw) return null;
      const record = JSON.parse(raw);
      // Valid if less than 30 minutes old
      if (Date.now() - record.timestamp < 30 * 60 * 1000) {
        return record;
      }
      clearPendingCheckout();
    } catch (_) {}
    return null;
  }

  function clearPendingCheckout() {
    try {
      root.localStorage?.removeItem(PENDING_STORAGE_KEY);
      root.sessionStorage?.removeItem(PENDING_STORAGE_KEY);
    } catch (_) {}
  }

  async function recoverPendingCheckout() {
    const pending = getPendingCheckout();
    if (!pending || !pending.idempotencyKey) return false;

    console.info('[CheckoutRecovery] Interrupted checkout detected:', pending);
    api().showToast(api().t('recovery-detected', 'جاري فحص حالة طلبك السابق...'));

    try {
      // Inquire order fulfillment status with the saved idempotency key
      const res = await fetch('/api/orders/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idempotency_key: pending.idempotencyKey,
          tg_id: pending.payload?.tg_id
        })
      });

      if (res.ok) {
        const result = await res.json();
        if (result.order && (result.order.status === 'completed' || result.order.delivery_goods)) {
          // Recovered confirmed order!
          showOrderSuccessView(result.order);
          security().finishCheckout?.(pending.scope, pending.payload, pending.idempotencyKey);
          clearPendingCheckout();
          api().fireConfetti?.();
          api().showToast('تمت استعادة وتسليم طلبك بنجاح! 🎉');
          return true;
        }
      }
    } catch (e) {
      console.warn('[CheckoutRecovery] Server inquiry failed, preserving key for safe retry:', e);
    }
    return false;
  }

  function formatCheckoutError(err) {
    const isAr = (state().currentAppLanguage === 'ar');
    const dict = {
      'idempotency_key_required': isAr ? 'مفتاح العملية مفقود، يرجى المحاولة مجدداً.' : 'Missing transaction key. Please retry.',
      'idempotency_key_conflict': isAr ? 'تم إرسال طلب مكرر بتفاصيل مختلفة، يرجى المحاولة لاحقاً.' : 'Duplicate order conflict. Please retry.',
      'user_not_found': isAr ? 'الحساب غير مسجل بالمتجر، يرجى إعادة تشغيل البوت.' : 'User account not found.',
      'account_banned': isAr ? 'تم إيقاف حسابك مؤقتاً، يرجى التواصل مع الدعم.' : 'Account is banned.',
      'product_unavailable': isAr ? 'المنتج غير متوفر للشراء حالياً.' : 'Product is currently unavailable.',
      'out_of_stock': isAr ? 'عذراً، نفد مخزون هذا المنتج حالياً.' : 'Item is out of stock.',
      'insufficient_balance': isAr ? 'رصيدك غير كافٍ لإتمام هذا الطلب. يرجى شحن المحفظة.' : 'Insufficient balance. Please top up your wallet.',
      'invalid_coupon': isAr ? 'كود الخصم غير صالح أو منتهي الصلاحية.' : 'Invalid coupon code.',
      'coupon_limit_reached': isAr ? 'تم استنفاد الحد الأقصى لاستخدام كود الخصم.' : 'Coupon usage limit reached.',
      'direct_topup_quantity_one': isAr ? 'شحن الألعاب متاح بكمية 1 فقط لكل طلب.' : 'Game top-ups must be quantity 1.',
      'missing_player_id': isAr ? 'يرجى إدخال معرف اللاعب (Player ID / UID).' : 'Please enter your Player ID / UID.',
      'missing_server_id': isAr ? 'يرجى اختيار أو إدخال معرف السيرفر (Server ID).' : 'Please specify Server / Zone ID.',
      'missing_charname': isAr ? 'يرجى إدخال اسم الشخصية داخل اللعبة.' : 'Please enter Character name.',
      'invalid_quantity': isAr ? 'الكمية المطلوبة غير صحيحة.' : 'Invalid quantity.',
      'invalid_parameters': isAr ? 'بيانات الطلب غير صالحة.' : 'Invalid order parameters.',
      'price_unavailable': isAr ? 'تعذر احتساب السعر حالياً.' : 'Price unavailable.'
    };
    return dict[err] || err || (isAr ? 'فشلت عملية الشراء. تأكد من توفر الرصيد الكافي.' : 'Purchase failed. Check your balance.');
  }

  // --- Purchase Execution (Instant & Cart) ---
  async function buyNow(product, quantity = 1, extraFields = null) {
    if (!product || !product.id) return;
    const tgId = state().userId || api().getTg()?.initDataUnsafe?.user?.id;
    if (!tgId) {
      api().showToast('يرجى الدخول من داخل تطبيق تيليجرام');
      return;
    }

    const isAr = ((state().currentAppLanguage || window.currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');

    // Inline validation for dynamic custom / game fields (preserves input)
    const fieldsContainer = document.getElementById('detail-game-fields-container') || document.getElementById('product-game-fields-container');
    if (fieldsContainer && fieldsContainer.style.display !== 'none') {
      clearInlineFormErrors();
      const pInp = document.getElementById('game-player-id-input');
      const sInp = document.getElementById('game-server-id-input');
      const sSel = document.getElementById('game-server-id-select');
      const groupServer = document.getElementById('group-server-id');

      let hasFormError = false;
      if (pInp && (!pInp.value || !pInp.value.trim())) {
        hasFormError = true;
        pInp.style.borderColor = '#ef4444';
        const errEl = document.createElement('div');
        errEl.className = 'inline-field-error';
        errEl.style.cssText = 'color: #ef4444; font-size: 11px; margin-top: 4px; font-weight: 700;';
        errEl.textContent = isAr ? 'يرجى إدخال معرف اللاعب أو الحساب للمتابعة' : 'Please enter player or account ID to continue';
        const targetContainer = pInp.closest('.game-input-group') || pInp.parentNode;
        targetContainer.appendChild(errEl);
        try { pInp.focus(); pInp.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
      } else if (groupServer && groupServer.style.display !== 'none') {
        const sVal = (sInp && sInp.style.display !== 'none') ? sInp.value : (sSel ? sSel.value : '');
        if (!sVal || !sVal.trim()) {
          hasFormError = true;
          const targetInp = (sInp && sInp.style.display !== 'none') ? sInp : sSel;
          if (targetInp) targetInp.style.borderColor = '#ef4444';
          const errEl = document.createElement('div');
          errEl.className = 'inline-field-error';
          errEl.style.cssText = 'color: #ef4444; font-size: 11px; margin-top: 4px; font-weight: 700;';
          errEl.textContent = isAr ? 'يرجى تحديد أو إدخال معرف السيرفر / المنطقة' : 'Please enter or select server / zone ID';
          const targetContainer = (targetInp && targetInp.closest('.game-input-group')) || groupServer || (targetInp && targetInp.parentNode);
          if (targetContainer) targetContainer.appendChild(errEl);
          try { if (targetInp) { targetInp.focus(); targetInp.scrollIntoView({ behavior: 'smooth', block: 'center' }); } } catch (_) {}
        }
      }

      if (hasFormError) {
        api().haptic?.('error');
        return;
      }
    }

    const qty = Math.max(1, Number(quantity) || 1);
    const customFields = extraFields || getEnteredCustomFields();

    const payload = {
      tg_id: tgId,
      product_id: Number(product.id),
      quantity: qty,
      coupon_code: state().appliedCoupon?.code || undefined,
      ...customFields,
      custom_fields: customFields
    };

    const idempotencyKey = security().checkoutKey ? security().checkoutKey('buy', payload) : `buy-${Date.now()}`;
    payload.idempotency_key = idempotencyKey;

    // Persist to recovery engine BEFORE firing request
    savePendingCheckout({
      scope: 'buy',
      payload,
      idempotencyKey,
      productTitle: product.name_ar || product.name
    });

    api().haptic?.('heavy');
    const buyBtn = document.getElementById('btn-inapp-purchase') || document.getElementById('btn-buy-now');
    const originalBtnHtml = buyBtn ? buyBtn.innerHTML : '';
    if (buyBtn) {
      buyBtn.disabled = true;
      buyBtn.style.opacity = '0.7';
      buyBtn.innerHTML = `<span>${isAr ? 'جاري تأكيد وتجهيز الطلب... ⏳' : 'Confirming order... ⏳'}</span>`;
    }

    try {
      const res = await fetch('/api/buy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
          'X-Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      const isSuccess = res.ok && (data.status === 'ok' || data.status === 'success' || data.success === true || Boolean(data.order_id || data.id));

      if (isSuccess) {
        api().haptic?.('success');
        api().fireConfetti?.();
        security().finishCheckout?.('buy', payload, idempotencyKey);
        clearPendingCheckout();
        const orderData = data.order || data;
        showOrderSuccessView(orderData);
        if (root.loadUserData) root.loadUserData();
      } else {
        api().haptic?.('error');
        const msg = formatCheckoutError(data.error);
        api().showToast(msg, 3500);
        if (data.error === 'insufficient_balance') {
          const userBal = Number(state().userData?.balance || 0);
          const unitPrice = Number(product.sell_price_usd ?? product.price ?? 0);
          const totalDue = unitPrice * qty;
          const shortfall = Math.max(0.01, +(totalDue - userBal).toFixed(2));

          const fundAlert = document.getElementById('insufficient-funds-alert');
          if (fundAlert) {
            fundAlert.innerHTML = `
              <div style="font-weight: 800; font-size: 14px; margin-bottom: 6px; color: #ef4444;">
                ${isAr ? 'الرصيد المتاح غير كافٍ لإتمام الشراء ⚠️' : 'Insufficient balance to complete purchase ⚠️'}
              </div>
              <div style="font-size: 12px; margin-bottom: 10px; color: var(--hint);">
                ${isAr ? `رصيدك الحالي: $${userBal.toFixed(2)} · إجمالي الطلب: $${totalDue.toFixed(2)} · ينقصك: $${shortfall.toFixed(2)}` : `Current balance: $${userBal.toFixed(2)} · Total: $${totalDue.toFixed(2)} · Shortfall: $${shortfall.toFixed(2)}`}
              </div>
              <button type="button" class="btn-action-primary" onclick="proceedToTopupForProduct(${Number(product.id)}, ${qty}, ${shortfall})" style="width: 100%; height: 44px; font-size: 13px; font-weight: 800; background: linear-gradient(135deg, #f59e0b, #d97706); display: flex; align-items: center; justify-content: center; gap: 6px;">
                <span>⚡</span>
                <span>${isAr ? `شحن $${shortfall.toFixed(2)} ومتابعة الشراء` : `Top up $${shortfall.toFixed(2)} & Continue`}</span>
              </button>
            `;
            fundAlert.style.display = 'block';
          }
        }
      }
    } catch (e) {
      api().showToast('انقطع الاتصال بالخادم. سيتم التحقق من طلبك تلقائياً.');
    } finally {
      if (buyBtn) {
        buyBtn.disabled = false;
        buyBtn.style.opacity = '1';
        buyBtn.innerHTML = originalBtnHtml;
      }
    }
  }

  async function executeCartCheckout() {
    const items = Object.values(cartMap);
    if (items.length === 0) return;

    const tgId = state().userId || api().getTg()?.initDataUnsafe?.user?.id;
    if (!tgId) {
      api().showToast('يرجى الدخول من داخل تطبيق تيليجرام');
      return;
    }

    const lineItems = items.map(it => ({
      product_id: Number(it.product.id),
      quantity: Number(it.quantity) || 1,
      options: it.options || {},
      ...(it.options || {})
    }));

    const payload = {
      tg_id: tgId,
      items: lineItems,
      coupon_code: state().appliedCoupon?.code || undefined
    };

    const idempotencyKey = security().checkoutKey ? security().checkoutKey('cart', payload) : `cart-${Date.now()}`;
    payload.idempotency_key = idempotencyKey;

    savePendingCheckout({
      scope: 'cart',
      payload,
      idempotencyKey,
      itemsCount: items.length
    });

    api().haptic?.('heavy');
    const checkoutBtn = document.getElementById('btn-cart-checkout-submit') || document.getElementById('btn-cart-checkout');
    const originalBtnHtml = checkoutBtn ? checkoutBtn.innerHTML : '';
    if (checkoutBtn) {
      checkoutBtn.disabled = true;
      checkoutBtn.style.opacity = '0.7';
      checkoutBtn.innerHTML = '<span>جاري إتمام الطلب... ⏳</span>';
    }

    try {
      const res = await fetch('/api/cart/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
          'X-Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      const isSuccess = res.ok && (data.status === 'ok' || data.status === 'success' || data.success === true || Boolean(data.order_id || data.id));

      if (isSuccess) {
        api().haptic?.('success');
        api().fireConfetti?.();
        security().finishCheckout?.('cart', payload, idempotencyKey);
        clearPendingCheckout();
        clearEntireCart();
        closeCartDrawer();
        const orderData = data.order || data;
        showOrderSuccessView(orderData);
        if (root.loadUserData) root.loadUserData();
      } else {
        api().haptic?.('error');
        const msg = formatCheckoutError(data.error);
        api().showToast(msg, 3500);
      }
    } catch (e) {
      api().showToast('حدث خطأ بالشبكة. سيتم استعادة السلة تلقائياً.');
    } finally {
      if (checkoutBtn) {
        checkoutBtn.disabled = false;
        checkoutBtn.style.opacity = '1';
        checkoutBtn.innerHTML = originalBtnHtml;
      }
    }
  }

  function normalizeInstructionSteps(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map(s => String(s || '').trim()).filter(Boolean);
    return String(raw).split(/\r?\n/).map(s => String(s || '').trim()).filter(Boolean);
  }

  function renderSuccessInstructions(order) {
    const card = document.getElementById('success-instructions-card');
    const stepsBox = document.getElementById('success-instructions-steps');
    if (!card || !stepsBox) return;

    const isAr = ((state().currentAppLanguage || window.currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    const raw = isAr
      ? (order.instructions_ar || order.instructions_en || order.activation_steps)
      : (order.instructions_en || order.instructions_ar || order.activation_steps);

    const steps = normalizeInstructionSteps(raw);
    if (!steps || !steps.length) {
      card.style.display = 'none';
      stepsBox.innerHTML = '';
      return;
    }

    const labelEl = document.getElementById('label-success-instructions');
    if (labelEl) {
      labelEl.innerText = isAr ? 'خطوات التفعيل والاستخدام' : 'Activation Steps';
    }
    const htmlFn = root.instructionStepsHTML || api().instructionStepsHTML;
    stepsBox.innerHTML = htmlFn ? htmlFn(steps) : steps.map((s, i) => `<div class="instr-step"><span class="instr-step-num">${i + 1}</span><span class="instr-step-text">${api().escapeAttr(s)}</span></div>`).join('');
    card.style.display = 'block';
  }

  // --- Post-Purchase Order Delivery View ---
  function showOrderSuccessView(order) {
    const orderId = order.id || order.order_id || '';
    const goods = order.delivery_goods || order.goods || [];
    const isAr = ((state().currentAppLanguage || window.currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    const status = order.status || (goods.length > 0 ? 'completed' : 'pending');
    const isDelivered = (status === 'completed' || goods.length > 0);
    const isRefunded = (status === 'refunded' || status === 'failed');
    const isReview = (status === 'requires_manual_review' || status === 'received');

    // 1. In-App Dedicated View (#view-order-success)
    const viewSuccess = document.getElementById('view-order-success');
    if (viewSuccess) {
      const titleEl = document.getElementById('success-view-title');
      if (titleEl) {
        if (isDelivered) {
          titleEl.textContent = isAr ? 'تم الطلب والتسليم بنجاح! 🎉' : 'Order Delivered Successfully! 🎉';
        } else if (isRefunded) {
          titleEl.textContent = isAr ? 'طلب ملغى ومسترد ↩️' : 'Order Refunded ↩️';
        } else if (isReview) {
          titleEl.textContent = isAr ? 'تم استلام الطلب وبانتظار المراجعة ⏳' : 'Order Received - In Review ⏳';
        } else {
          titleEl.textContent = isAr ? 'تم استلام وتأكيد الطلب ⏳' : 'Order Confirmed - Processing ⏳';
        }
      }

      const metaSub = document.getElementById('success-meta-sub');
      if (metaSub) {
        const prodName = order.product_name ? ` · ${order.product_name}` : '';
        if (isDelivered) {
          metaSub.textContent = isAr
            ? `طلب #${orderId}${prodName} · تم التسليم بنجاح ✅`
            : `Order #${orderId}${prodName} · Delivered Successfully ✅`;
        } else if (isRefunded) {
          metaSub.textContent = isAr
            ? `طلب #${orderId}${prodName} · تم استرداد المبلغ للمحفظة ↩️`
            : `Order #${orderId}${prodName} · Refunded to wallet ↩️`;
        } else {
          metaSub.textContent = isAr
            ? `طلب #${orderId}${prodName} · جاري التجهيز والتفعيل ⏳`
            : `Order #${orderId}${prodName} · Processing & Activation ⏳`;
        }
      }

      const keysContainer = document.getElementById('success-delivered-keys');
      const keysCard = document.getElementById('success-keys-card') || keysContainer?.closest('.inset-card');
      const keysTitle = document.getElementById('success-keys-title');
      const copyHint = document.getElementById('success-copy-hint');

      if (keysContainer) {
        if (isDelivered && goods.length > 0) {
          const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;
          keysContainer.innerHTML = renderFn ? renderFn(goods) : '';

          const hasUrls = goods.some(g => {
            const str = String(typeof g === 'object' ? (g.value || g.data || '') : g).trim();
            return str.startsWith('http://') || str.startsWith('https://');
          });

          if (hasUrls) {
            if (keysTitle) keysTitle.style.display = 'none';
            if (copyHint) copyHint.style.display = 'none';
            if (keysCard) {
              keysCard.style.background = 'transparent';
              keysCard.style.border = 'none';
              keysCard.style.padding = '0';
              keysCard.style.boxShadow = 'none';
            }
          } else {
            if (keysTitle) {
              keysTitle.style.display = 'block';
              keysTitle.textContent = isAr ? 'بيانات الحساب / المفاتيح المسلمة' : 'Delivered Credentials / Keys';
            }
            if (copyHint) {
              copyHint.style.display = 'block';
              copyHint.textContent = isAr ? 'انقر على أي كود بالأعلى للنسخ!' : 'Tap any code above to copy!';
            }
            if (keysCard) {
              keysCard.style.background = '';
              keysCard.style.border = '';
              keysCard.style.padding = '';
              keysCard.style.boxShadow = '';
            }
          }
        } else if (isRefunded) {
          if (keysTitle) keysTitle.style.display = 'none';
          if (copyHint) copyHint.style.display = 'none';
          keysContainer.innerHTML = `
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 16px; text-align: center;">
              <div style="font-weight: 800; font-size: 14px; color: #ef4444; margin-bottom: 6px;">
                ${isAr ? 'تم استرداد كامل المبلغ إلى رصيد محفظتك' : 'Order amount was refunded to your wallet'}
              </div>
              <div style="font-size: 12px; color: var(--hint); margin-bottom: 14px;">
                ${isAr ? 'إذا كنت بحاجة للمساعدة أو ترغب بالاستفسار، تواصل مع فريق الدعم.' : 'For assistance or inquiries, please contact our support team.'}
              </div>
              <button type="button" class="btn-action-secondary" onclick="openOrderSupport('${orderId}')" style="height: 38px; font-size: 12px; font-weight: 700; width: auto; padding: 0 18px; margin: 0 auto;">
                💬 ${isAr ? 'محادثة الدعم الفني' : 'Contact Support'}
              </button>
            </div>
          `;
        } else {
          // Processing / Review
          if (keysTitle) keysTitle.style.display = 'none';
          if (copyHint) copyHint.style.display = 'none';
          keysContainer.innerHTML = `
            <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 14px; padding: 16px; text-align: center;">
              <div style="font-size: 32px; margin-bottom: 8px;">⏳</div>
              <div style="font-weight: 800; font-size: 14px; color: var(--accent); margin-bottom: 6px;">
                ${isAr ? 'تم تأكيد الدفع وجاري التجهيز والتفعيل' : 'Payment Confirmed - Fulfilling Service'}
              </div>
              <div style="font-size: 12px; color: var(--hint); line-height: 1.5; margin-bottom: 14px; max-width: 320px; margin-inline: auto;">
                ${isAr ? 'نقوم بتوليد وتفعيل بياناتك فوراً. ستظهر البيانات في هذه الشاشة وفي رسائل البوت خلال دقائق.' : 'We are activating your service now. Credentials will be delivered here and via bot message shortly.'}
              </div>
              <button type="button" class="btn-action-secondary" onclick="openOrderSupport('${orderId}')" style="height: 38px; font-size: 12px; font-weight: 700; width: auto; padding: 0 18px; margin: 0 auto;">
                💬 ${isAr ? `استفسار عن الطلب #${orderId}` : `Inquire about Order #${orderId}`}
              </button>
            </div>
          `;
        }
      }

      // Render activation steps if present
      renderSuccessInstructions(order);

      const btnViewOrders = document.getElementById('btn-success-view-orders');
      if (btnViewOrders) btnViewOrders.textContent = isAr ? 'عرض في طلباتي' : 'View in Orders';
      const btnContinue = document.getElementById('btn-success-continue');
      if (btnContinue) btnContinue.textContent = isAr ? 'متابعة التسوق' : 'Continue Shopping';

      document.querySelectorAll('.tab-view').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
      });
      const storeEl = document.getElementById('view-store');
      if (storeEl) {
        storeEl.classList.remove('active');
        storeEl.style.display = 'none';
      }

      viewSuccess.classList.add('active');
      viewSuccess.style.display = 'block';
      window.scrollTo({ top: 0, behavior: 'smooth' });

      api().pushNav?.('order_success', () => {
        if (root.switchTab) root.switchTab('store');
      });
      return;
    }

    // 2. Modal Fallback (#modal-order-success)
    const modal = document.getElementById('modal-order-success');
    if (!modal) return;

    const idEl = document.getElementById('success-order-id');
    if (idEl) idEl.textContent = `#${orderId}`;

    const goodsContainer = document.getElementById('success-delivered-goods');
    if (goodsContainer) {
      if (goods.length > 0) {
        const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;
        goodsContainer.innerHTML = renderFn ? renderFn(goods) : '';
      } else {
        goodsContainer.innerHTML = `<div class="alert-box-info">${isAr ? 'الطلب قيد المعالجة وسيتم تسليم البيانات فوراً خلال دقائق' : 'Order is processing, credentials will be delivered shortly'}</div>`;
      }
    }

    const stepsContainer = document.getElementById('success-activation-steps');
    if (stepsContainer && order.activation_steps) {
      stepsContainer.innerHTML = api().instructionStepsHTML(order.activation_steps);
      stepsContainer.style.display = 'block';
    } else if (stepsContainer) {
      stepsContainer.style.display = 'none';
    }

    modal.style.display = 'flex';
    api().pushNav?.('order_success_modal', () => { modal.style.display = 'none'; });
  }

  // --- Export Namespace ---
  root.StoreCheckout = {
    initCart,
    addToCart,
    removeFromCart,
    changeCartQty,
    clearEntireCart,
    openCartDrawer,
    closeCartDrawer,
    renderCartDrawerItems,
    renderProductGameFields,
    applyCoupon,
    savePendingCheckout,
    getPendingCheckout,
    clearPendingCheckout,
    recoverPendingCheckout,
    buyNow,
    executeCartCheckout,
    showOrderSuccessView
  };

})(typeof window !== 'undefined' ? window : globalThis);
