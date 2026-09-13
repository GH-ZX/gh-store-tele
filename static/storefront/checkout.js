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
    const container = document.getElementById('product-game-fields-container');
    if (!container) return;
    const meta = product?.extra_meta || {};
    const fields = meta.custom_fields || [];

    if (!fields || fields.length === 0) {
      container.innerHTML = '';
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';
    let html = '<div class="game-fields-card"><div class="game-fields-header">بيانات الحساب المطلوبة للشحن</div>';
    fields.forEach(f => {
      const fieldKey = api().escapeAttr(f.key || f.id || 'field');
      const label = api().escapeAttr(f.name || f.label || 'المعرف');
      const placeholder = api().escapeAttr(f.placeholder || `أدخل ${label}`);

      html += `<div class="game-input-row">
        <label class="game-input-label">${label}</label>
        <input type="text" class="game-input-control" id="custom-field-${fieldKey}" placeholder="${placeholder}">
      </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
  }

  function getEnteredCustomFields() {
    const custom = {};
    const inputs = document.querySelectorAll('[id^="custom-field-"]');
    inputs.forEach(inp => {
      const key = inp.id.replace('custom-field-', '');
      if (inp.value && inp.value.trim()) {
        custom[key] = inp.value.trim();
      }
    });
    return custom;
  }

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

  // --- Purchase Execution (Instant & Cart) ---
  async function buyNow(product, quantity = 1, extraFields = null) {
    if (!product || !product.id) return;
    const tgId = state().userId || api().getTg()?.initDataUnsafe?.user?.id;
    if (!tgId) {
      api().showToast('يرجى الدخول من داخل تطبيق تيليجرام');
      return;
    }

    const qty = Math.max(1, Number(quantity) || 1);
    const customFields = extraFields || getEnteredCustomFields();

    const payload = {
      tg_id: tgId,
      product_id: Number(product.id),
      quantity: qty,
      custom_fields: customFields,
      coupon_code: state().appliedCoupon?.code || undefined
    };

    const idempotencyKey = security().checkoutKey ? security().checkoutKey('buy', payload) : `buy-${Date.now()}`;

    // Persist to recovery engine BEFORE firing request
    savePendingCheckout({
      scope: 'buy',
      payload,
      idempotencyKey,
      productTitle: product.name_ar || product.name
    });

    api().haptic?.('heavy');
    const buyBtn = document.getElementById('btn-buy-now');
    if (buyBtn) buyBtn.disabled = true;

    try {
      const res = await fetch('/api/buy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (res.ok && data.status === 'ok') {
        api().haptic?.('success');
        api().fireConfetti?.();
        security().finishCheckout?.('buy', payload, idempotencyKey);
        clearPendingCheckout();
        showOrderSuccessView(data.order || data);
      } else {
        api().haptic?.('error');
        api().showToast(data.error || 'فشلت عملية الشراء. تأكد من توفر الرصيد الكافي.');
      }
    } catch (e) {
      api().showToast('انقطع الاتصال بالخادم. سيتم التحقق من طلبك تلقائياً.');
    } finally {
      if (buyBtn) buyBtn.disabled = false;
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
      options: it.options || {}
    }));

    const payload = {
      tg_id: tgId,
      items: lineItems,
      coupon_code: state().appliedCoupon?.code || undefined
    };

    const idempotencyKey = security().checkoutKey ? security().checkoutKey('cart', payload) : `cart-${Date.now()}`;

    savePendingCheckout({
      scope: 'cart',
      payload,
      idempotencyKey,
      itemsCount: items.length
    });

    api().haptic?.('heavy');
    const checkoutBtn = document.getElementById('btn-cart-checkout-submit');
    if (checkoutBtn) checkoutBtn.disabled = true;

    try {
      const res = await fetch('/api/cart/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (res.ok && data.status === 'ok') {
        api().haptic?.('success');
        api().fireConfetti?.();
        security().finishCheckout?.('cart', payload, idempotencyKey);
        clearPendingCheckout();
        clearEntireCart();
        closeCartDrawer();
        showOrderSuccessView(data.order || data);
      } else {
        api().haptic?.('error');
        api().showToast(data.error || 'فشل إتمام سلة المشتريات. تأكد من توفر الرصيد.');
      }
    } catch (e) {
      api().showToast('حدث خطأ بالشبكة. سيتم استعادة السلة تلقائياً.');
    } finally {
      if (checkoutBtn) checkoutBtn.disabled = false;
    }
  }

  // --- Post-Purchase Order Delivery View ---
  function showOrderSuccessView(order) {
    const modal = document.getElementById('modal-order-success');
    if (!modal) return;

    const idEl = document.getElementById('success-order-id');
    if (idEl) idEl.textContent = `#${order.id || ''}`;

    const goodsContainer = document.getElementById('success-delivered-goods');
    if (goodsContainer) {
      const goods = order.delivery_goods || [];
      if (goods.length > 0) {
        goodsContainer.innerHTML = api().renderStructuredCredentials(goods);
      } else {
        goodsContainer.innerHTML = '<div class="alert-box-info">الطلب قيد المعالجة وسيتم تسليم البيانات فوراً خلال دقائق</div>';
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
    api().pushNav('order_success_modal', () => { modal.style.display = 'none'; });
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
