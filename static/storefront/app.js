// Automatically attach cryptographic Telegram initData to every API call
(function() {
  const _origFetch = window.fetch;
  window.fetch = function(url, options) {
    const opts = options ? { ...options } : {};
    const tgObj = window.Telegram?.WebApp;
    if (tgObj?.initData) {
      if (!opts.headers) {
        opts.headers = { 'X-Telegram-Init-Data': tgObj.initData };
      } else if (typeof Headers !== 'undefined' && opts.headers instanceof Headers) {
        if (!opts.headers.has('X-Telegram-Init-Data')) {
          opts.headers.set('X-Telegram-Init-Data', tgObj.initData);
        }
      } else if (Array.isArray(opts.headers)) {
        opts.headers.push(['X-Telegram-Init-Data', tgObj.initData]);
      } else {
        opts.headers = { ...opts.headers, 'X-Telegram-Init-Data': tgObj.initData };
      }
    }
    return _origFetch.call(this, url, opts);
  };
})();

const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.isVersionAtLeast && tg.isVersionAtLeast('7.7')) {
        try { tg.disableVerticalSwipes?.(); } catch (e) {}
      }
      if (tg.isVersionAtLeast && tg.isVersionAtLeast('8.0')) {
        try { tg.requestFullscreen?.(); } catch (e) {}
      }
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      if (tg.SettingsButton) {
        try {
          tg.SettingsButton.show();
          tg.SettingsButton.onClick(() => switchTab('settings'));
        } catch (e) {}
      }
    }

    function cloudStorageSet(key, value) {
      try {
        if (tg?.CloudStorage?.setItem) {
          tg.CloudStorage.setItem(key, String(value), (err) => {
            if (err) console.debug('CloudStorage set error:', err);
          });
        }
      } catch (e) {}
    }

    function cloudStorageGet(key, callback) {
      try {
        if (tg?.CloudStorage?.getItem) {
          tg.CloudStorage.getItem(key, (err, val) => {
            if (!err && val !== undefined && val !== null && val !== '') {
              callback(val);
            }
          });
        }
      } catch (e) {}
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
        tg.onEvent('fullscreenFailed', ({ error }) => {
          console.debug('Fullscreen failed:', error);
        });
        tg.onEvent('viewportChanged', updateSafeAreaInsets);

        // Bot API 8.0 Lifecycle Events: activated / deactivated
        tg.onEvent('deactivated', () => {
          // App minimized: close SSE stream and pause background intervals
          if (window._sseSource) {
            try { window._sseSource.close(); } catch (e) {}
          }
          clearInterval(flashSaleTimerInterval);
        });
        tg.onEvent('activated', () => {
          // App restored: reconnect real-time stock/price stream and refresh
          initSSE();
          if (typeof loadUserData === 'function') loadUserData();
          if (typeof fetchCatalogData === 'function') fetchCatalogData();
        });
      }

      // Bot API 8.0: Lock portrait orientation for consistent mobile commerce layout
      if (tg.isVersionAtLeast && tg.isVersionAtLeast('8.0')) {
        try { tg.lockOrientation?.(); } catch (e) {}
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
          } else if (type === 'selection') {
            tg.HapticFeedback.selectionChanged?.();
          } else if (['light', 'medium', 'heavy', 'rigid', 'soft'].includes(type)) {
            tg.HapticFeedback.impactOccurred(type);
          } else {
            tg.HapticFeedback.impactOccurred('light');
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
                const cloudCart = JSON.parse(val) || {};
                if (Object.keys(cartMap).length === 0 && Object.keys(cloudCart).length > 0) {
                  cartMap = cloudCart;
                  updateFloatingCartUI();
                  renderCartDrawerItems();
                }
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
      syncCartToBackend();
    }

    let syncCartTimer = null;
    function syncCartToBackend() {
      if (!userId) return;
      clearTimeout(syncCartTimer);
      syncCartTimer = setTimeout(async () => {
        try {
          const items = Object.values(cartMap).map(it => ({ id: it.id, name: it.clean_name || it.name, price: it.price, quantity: it.quantity }));
          await fetch('/api/cart/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tg_id: userId, items: items })
          });
        } catch (e) {}
      }, 1200);
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
          totalEl.innerText = formatPrice(totalPrice);
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
      if (tg?.MainButton) {
        tg.MainButton.offClick(executeCartCheckout);
        tg.MainButton.hide();
      }
      if (tg?.SecondaryButton) {
        tg.SecondaryButton.offClick(clearEntireCart);
        tg.SecondaryButton.hide();
      }
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
                  <div class="cart-item-price">${formatPrice(it.price)} × ${it.quantity} = <strong>${formatPrice(itemTotal)}</strong></div>
                </div>
              </div>
              <div style="display: flex; align-items: center;">
                <div class="cart-stepper">
                  <button onclick="changeCartQty(${it.id}, -1)">–</button>
                  <span>${it.quantity}</span>
                  <button onclick="changeCartQty(${it.id}, 1)">+</button>
                </div>
                <button class="cart-del-btn" onclick="removeCartItem(${it.id})" title="${currentAppLanguage === 'ar' ? 'حذف' : 'Remove'}">✕</button>
              </div>
            </div>
          `;
        }).join('');
      }

      const discRow = document.getElementById('cart-summary-disc-row');
      const discEl = document.getElementById('cart-summary-discount');
      const subEl = document.getElementById('cart-summary-subtotal');
      const totEl = document.getElementById('cart-summary-total');
      const checkBtn = document.getElementById('btn-cart-checkout');
      if (subEl) subEl.innerText = formatPrice(subtotal);
      if (totEl) totEl.innerText = formatPrice(subtotal);
      if (checkBtn) { checkBtn.disabled = true; }
      refreshCartQuote(items, subtotal, sym);
    }

    // AUTHORITATIVE CART QUOTE (stale responses ignored)
    let cartQuoteSeq = 0;
    async function refreshCartQuote(items, subtotal, sym) {
      const seq = ++cartQuoteSeq;
      const discRow = document.getElementById('cart-summary-disc-row');
      const discEl = document.getElementById('cart-summary-discount');
      const totEl = document.getElementById('cart-summary-total');
      const checkBtn = document.getElementById('btn-cart-checkout');
      const d = I18N[currentAppLanguage] || I18N.ar;
      let quote = null;
      try {
        const res = await fetch('/api/price-quote', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            items: items.map(it => ({ product_id: it.id, quantity: it.quantity }))
          })
        });
        const payload = await res.json();
        if (seq !== cartQuoteSeq) return;
        if (!res.ok || payload.error) {
          if (totEl) totEl.innerText = d.quote_failed_note;
          if (checkBtn) { checkBtn.disabled = true; checkBtn.onclick = null; }
          return;
        }
        quote = payload;
      } catch (e) {
        if (seq !== cartQuoteSeq) return;
        if (totEl) totEl.innerText = d.quote_failed_note;
        if (checkBtn) { checkBtn.disabled = true; checkBtn.onclick = null; }
        return;
      }
      const finalTotal = quote.total;
      const saved = Math.max(0, subtotal - finalTotal);
      if (discRow && discEl) {
        if (saved > 0.005) {
          discRow.style.display = 'flex';
          discEl.innerText = `-${formatPrice(saved)}` + (quote.discount_limited ? ' · ' + d.quote_limited_note : '');
        } else if (quote.discount_limited) {
          discRow.style.display = 'flex';
          discEl.innerText = d.quote_limited_note;
        } else {
          discRow.style.display = 'none';
        }
      }
      if (totEl) totEl.innerText = formatPrice(finalTotal);
      const userBal = userData?.balance || 0.0;
      if (checkBtn) {
        checkBtn.disabled = false;
        if (userBal < finalTotal) {
          checkBtn.innerHTML = `<span>${currentAppLanguage === 'ar' ? 'شحن الرصيد للمتابعة' : 'Top up to continue'} ($${userBal.toFixed(2)})</span>`;
          checkBtn.onclick = () => { closeCartDrawer(); switchTab('wallet'); };
        } else {
          checkBtn.innerHTML = `<span>${currentAppLanguage === 'ar' ? `تأكيد شراء السلة (${items.length} منتجات)` : `Confirm cart (${items.length} items)`} • ${formatPrice(finalTotal)}</span>`;
          checkBtn.onclick = executeCartCheckout;
        }
      }
      if (tg?.MainButton && items.length > 0) {
        tg.MainButton.offClick(executeCartCheckout);
        if (userBal < finalTotal) {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? `شحن الرصيد للمتابعة ($${userBal.toFixed(2)})` : `Top up balance ($${userBal.toFixed(2)})`)
            .show()
            .enable();
          tg.MainButton.onClick(() => { closeCartDrawer(); switchTab('wallet'); });
        } else {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? `شراء السلة (${items.length}) • ${formatPrice(finalTotal)}` : `Checkout (${items.length}) • ${formatPrice(finalTotal)}`)
            .show()
            .enable();
          tg.MainButton.onClick(executeCartCheckout);
        }
      }
      if (tg?.SecondaryButton && items.length > 0) {
        tg.SecondaryButton.offClick(clearEntireCart);
        tg.SecondaryButton.setParams({
          text: currentAppLanguage === 'ar' ? 'إفراغ السلة' : 'Clear Cart',
          position: 'left',
          is_visible: true,
          is_active: true
        });
        tg.SecondaryButton.onClick(clearEntireCart);
      }
    }

    async function executeCartCheckout() {
      const items = Object.values(cartMap);
      if (!items.length || !userId) return;
      haptic('light');

      const btn = document.getElementById('btn-cart-checkout');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>${currentAppLanguage === 'ar' ? 'جاري معالجة السلة...' : 'Processing cart...'}</span>`;
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
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل إتمام شراء السلة' : 'Failed to complete cart purchase'));
          renderCartDrawerItems();
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        if (tg?.MainButton) tg.MainButton.hideProgress();
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال أثناء شراء السلة' : 'Network error during cart checkout');
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

    // Immediate Zero-Latency Pre-fill from Telegram WebApp Context
    if (tgUser) {
      try {
        const initial = (tgUser.first_name || 'U')[0].toUpperCase();
        const topInit = document.getElementById('top-avatar-initial');
        const setInit = document.getElementById('settings-avatar-initial');
        if (tgUser.photo_url) {
          const imgTag = `<img src="${tgUser.photo_url}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%; display: block;" alt="Avatar">`;
          if (topInit) topInit.innerHTML = imgTag;
          if (setInit) setInit.innerHTML = imgTag;
        } else {
          if (topInit) topInit.innerText = initial;
          if (setInit) setInit.innerText = initial;
        }
        const nameEl = document.getElementById('user-name-title');
        const handleEl = document.getElementById('user-handle-title');
        const idEl = document.getElementById('user-tg-num');
        const fullName = `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim();
        const defaultTitle = (currentAppLanguage === 'ar') ? 'العميل' : 'Customer';
        const dispName = fullName || (tgUser.username ? '@' + tgUser.username : (userId ? `ID: ${userId}` : defaultTitle));
        if (nameEl) nameEl.innerText = dispName;
        if (handleEl) {
          if (tgUser.username) {
            handleEl.innerText = `@${tgUser.username.replace(/^@/, '')}`;
            handleEl.style.display = 'block';
          } else {
            handleEl.style.display = 'none';
          }
        }
        if (idEl && userId) {
          idEl.innerText = 'ID: ' + userId;
        }
      } catch (e) {
        console.error('Error in startup tgUser resolution:', e);
      }
    } else if (userId) {
      try {
        const idEl = document.getElementById('user-tg-num');
        if (idEl) idEl.innerText = 'ID: ' + userId;
        const nameEl = document.getElementById('user-name-title');
        if (nameEl) nameEl.innerText = `User ${userId}`;
      } catch (e) {}
    }

    // Appearance / Theme Switcher
    function setAppTheme(theme) {
      haptic('pop');
      document.documentElement.setAttribute('data-theme', theme);
      try { localStorage.setItem('ghstore_theme', theme); } catch (e) {}
      cloudStorageSet('ghstore_theme', theme);

      document.querySelectorAll('.theme-segment-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById('theme-btn-' + theme);
      if (activeBtn) activeBtn.classList.add('active');

      const isLight = (theme === 'light');
      const bgCol = isLight ? '#f8fafc' : '#090e1a';
      try {
        if (tg?.setHeaderColor) tg.setHeaderColor(bgCol);
        if (tg?.setBackgroundColor) tg.setBackgroundColor(bgCol);
        if (tg?.setBottomBarColor) tg.setBottomBarColor(bgCol);
      } catch (e) {}
    }

    function initAppTheme() {
      const savedTheme = localStorage.getItem('ghstore_theme') || (tg?.colorScheme === 'light' ? 'light' : 'dark');
      setAppTheme(savedTheme);
      cloudStorageGet('ghstore_theme', (theme) => {
        if (theme && ['dark', 'light'].includes(theme) && theme !== savedTheme) {
          setAppTheme(theme);
        }
      });
      if (tg?.onEvent) {
        tg.onEvent('themeChanged', () => {
          if (!localStorage.getItem('ghstore_theme')) {
            const autoTheme = tg.colorScheme === 'light' ? 'light' : 'dark';
            setAppTheme(autoTheme);
          }
        });
      }
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
        image: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&auto=format&fit=crop&q=85",
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
      if (!raw) return `<span style="color: var(--hint)">${currentAppLanguage === 'ar' ? 'لا يوجد وصف إضافي.' : 'No additional description.'}</span>`;
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
      text = text.replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, '<i>$1</i>');

      text = text.replace(/`([^`]+)`/g, '<code class="desc-inline-code">$1</code>');
      text = text.replace(/^[\s]*[-*•]\s+(.+)$/gim, '<div class="desc-bullet">• $1</div>');

      // Make URLs and markdown links clickable safely via placeholders
      const links = [];
      text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/gi, (m, label, url) => {
        const placeholder = '___LINK_' + links.length + '___';
        links.push('<a href="' + url + '" target="_blank" rel="noopener noreferrer" class="desc-link" onclick="handleDescLink(event, \'' + url + '\')">' + label + '</a>');
        return placeholder;
      });

      text = text.replace(/(https?:\/\/[^\s<"'\)]+)/gi, (url) => {
        const cleanUrl = url.replace(/[.,;]+$/, '');
        const trailing = url.slice(cleanUrl.length);
        const placeholder = '___LINK_' + links.length + '___';
        links.push('<a href="' + cleanUrl + '" target="_blank" rel="noopener noreferrer" class="desc-link" onclick="handleDescLink(event, \'' + cleanUrl + '\')">' + cleanUrl + '</a>');
        return placeholder + trailing;
      });

      links.forEach((linkHtml, idx) => {
        text = text.replace('___LINK_' + idx + '___', linkHtml);
      });
      text = text.replace(/\r?\n/g, '<br>');
      text = text.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');


      return text;
    }


    function handleDescLink(e, url) {
      if (tg?.openLink) {
        e.preventDefault();
        try { tg.openLink(url); } catch (err) { window.open(url, '_blank'); }
      }
    }
    // Structured Credential Splitter
    function renderStructuredCredentials(goods) {
      if (!goods || !goods.length) {
        return `<div style="padding: 12px; color: var(--warning); text-align: center;">${currentAppLanguage === 'ar' ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
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
                <button class="btn-copy-mini" onclick="copyCredText('${part.trim().replace(/'/g, "\\\\'")}', this)">${currentAppLanguage === 'ar' ? 'نسخ' : 'Copy'}</button>
            `;
          }).join('');

          return `
            <div class="cred-grid">
              ${rows}
              <div style="text-align: left; margin-top: 2px;">
                <button class="btn-copy-mini" style="font-size: 10px;" onclick="copyCredText('${line.replace(/'/g, "\\\\'")}', this)">${currentAppLanguage === 'ar' ? 'نسخ السطر كاملاً' : 'Copy Full Line'}</button>
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
            <button class="btn-copy-mini" onclick="copyCredText('${line.replace(/'/g, "\\\\'")}', this)">${currentAppLanguage === 'ar' ? 'نسخ' : 'Copy'}</button>
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
        filter_instant: "تسليم مباشر",
        filter_lowprice: "الأقل سعراً",
        banner_badge: "تحديثات المتجر",
        banner_title: "اشتراكات كلود وجيميني متوفرة الآن",
        banner_sub: "تسليم تلقائي للمفاتيح والحسابات على مدار الساعة",
        pwa_title: "أضف التطبيق للشاشة الرئيسية",
        pwa_sub: "لوصول مباشر وسريع دون فتح تيليجرام",
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
        instant_delivery: "تسليم تلقائي",
        custom_activation: "تفعيل مخصص",
        warranty_30d: "ضمان 30 يوم",
        in_stock: "متوفر",
        out_of_stock: "نفد المخزون",
        desc: "الوصف",
        promo_code_label: "كود الخصم",
        apply: "تطبيق",
        total: "السعر الإجمالي",
        insufficient_balance: "الرصيد المتاح غير كافٍ لهذا الطلب.",
        topup_to_continue: "شحن الرصيد للمتابعة",
        buy_now: "شراء",
        stars_buy: "الدفع عبر نجوم تيليجرام",
        restock_alert: "نبهني فور التوفر",
        order_success: "تم الطلب بنجاح!",
        delivered_keys: "بيانات الحساب / المفاتيح المسلمة",
        copy_hint: "انقر على أي كود بالأعلى للنسخ!",
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
        wallet_ready: "جاهز للشراء",
        vip_progress: "التقدم نحو رتبة",
        method_section_title: "1. اختر وسيلة الشحن",
        stars_title: "نجوم تيليجرام",
        stars_sub: "دفع عبر Apple Pay أو Google Pay أو النجوم",
        crypto_title: "USDT (BEP-20)",
        crypto_sub: "دفع مباشر وسريع عبر شبكة BEP20",
        shamcash_title: "شام كاش",
        shamcash_sub: "دفع مباشر وسريع عبر بنك شام كاش",
        syriatelcash_title: "سيرياتيل كاش",
        syriatelcash_sub: "دفع مباشر بالليرة السورية",
        amount_section_title: "2. اختر المبلغ أو حدد مخصصاً",
        custom_amount_placeholder: "أدخل المبلغ ($)... e.g. 15",
        voucher_section_title: "شحن عبر كرت هدية",
        voucher_btn: "شحن الكرت",
        theme_section_title: "المظهر",
        theme_dark: "الوضع الداكن",
        theme_light: "الوضع الفاتح",
        install_section_title: "تثبيت التطبيق",
        install_desc: "أضف أيقونة متجر GH Store إلى شاشة هاتفك الرئيسية لتصفح العروض بسهولة!",
        install_btn: "إضافة إلى الشاشة الرئيسية",
        currency_title: "عملة العرض المفضلة",
        lang_title: "اللغة",
        settings_balance: "الرصيد المتاح",
        settings_spent: "إجمالي المشتريات",
        copy_id: "نسخ ID",
        support_section_title: "الدعم وقنوات المتجر",
        support_chat_btn: "التواصل مع خدمة العملاء والدعم",
        official_channel_btn: "قناة العروض والتحديثات الرسمية",
        curr_usd_opt: "الدولار (USD)",
        curr_syp_opt: "الليرة السورية (SYP)",
        admin_sup_s1: "سيرفر 1 (بات ستور)",
        admin_sup_s2: "سيرفر 2 (برود سيلر)",
        admin_sup_sam: "محفظة SAM",
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
        sheet_copy_btn: "نسخ رابط الفاتورة المباشر",
        admin_center: "لوحة تحكم المشرف",
        admin_verified: "مسؤول معتمد",
        stat_revenue: "إجمالي المبيعات",
        stat_cost: "تكلفة المورد",
        stat_profit: "إجمالي الربح (قبل الرسوم)",
        stat_balances: "أرصدة العملاء الحالية",
        stat_users: "عدد المستخدمين",
        stat_orders: "إجمالي الطلبات",
        supplier_wallets: "احتياطي الموردين",
        refresh: "تحديث",
        admin_orders_title: "مراقبة طلبات المتجر المباشرة",
        admin_coupons_title: "إدارة كوبونات الخصم",
        tab_all: "الكل",
        tab_pending: "قيد التنفيذ",
        tab_completed: "مكتمل",
        tab_refunded: "مسترد",
        no_matching_orders: "لا توجد طلبات مطابقة.",
        amount_label: "المبلغ",
        cost_label: "التكلفة",
        profit_label: "الربح الإجمالي",
        confirm_delivery: "تأكيد التسليم",
        refund_to_customer: "استرداد المبلغ للعميل",
        refund_confirm_msg: "هل أنت متأكد من استرداد قيمة الطلب إلى رصيد العميل؟",
        refund_done: "تم استرداد المبلغ بنجاح!",
        order_updated: "تم تحديث حالة الطلب!",
        manual_sale_title: "بيع يدوي مدفوع خارج المتجر",
        manual_sale_btn: "تسليم بيع يدوي مدفوع",
        recipient_label: "وجهة التسليم",
        deliver_self: "لحسابي",
        deliver_other: "لعميل آخر",
        customer_tg_id: "معرف تيليجرام للعميل",
        qty_label: "الكمية",
        sale_total: "الإجمالي بالسعر الرسمي",
        external_paid_label: "تأكيد استلام المبلغ خارج المتجر",
        external_paid_note: "لا يتم خصم أي مبلغ من رصيد محفظة العميل. سيُسجل البيع بإيراد حقيقي.",
        confirm_sale: "تأكيد البيع المدفوع",
        cancel: "إلغاء",
        processing_sale: "جاري تنفيذ البيع...",
        sale_success_self: "تم تسجيل البيع واستلام المنتج بنجاح!",
        external_paid_done: "مدفوع خارج المتجر",
        suppliers_drawer: "إدارة ومفاتيح الموردين والسيرفرات",
        one_time_setup: "إعدادات التهيئة ومفاتيح الربط",
        orders_history_btn: "مراقبة الطلبات والاسترداد",
        users_manage_btn: "إدارة المستخدمين والأرصدة",
        coupons_manage_btn: "إدارة وإنشاء الكوبونات",
        sqladmin_btn: "لوحة SQLAdmin الكاملة",
        stuck_orders_btn: "متابعة الطلبات والعمليات المعلقة",
        syp_rate_title: "سعر صرف الليرة السورية مقابل الدولار",
        referral_rate_title: "نسبة عمولة الإحالة من أرباح الهامش",
        logo_url_title: "رابط شعار المتجر",
        margin_rate_title: "نسبة هامش الربح العام على المنتجات",
        stars_rate_title: "قيمة النجمة الواحدة مقابل الدولار",
        broadcast_banner_title: "شريط الإعلانات العام في المتجر",
        force_sync_btn: "مزامنة الكتالوج والأسعار من المورد فورياً",
        autorefund_title: "نظام الاسترداد التلقائي",
        store_settings_title: "إعدادات وتشغيل المتجر",
        store_settings_drawer: "إعدادات وتشغيل المتجر",
        back_to_settings: "العودة للإعدادات",
        sec_hdr_currencies: "العملات وأسعار الصرف",
        sec_hdr_pricing: "التسعير وهوامش الأرباح",
        sec_hdr_branding: "هوية المتجر والإعلانات",
        sec_hdr_operations: "أدوات التشغيل والمزامنة",
        admin_syp_rate_desc: "مربوط بقاعدة البيانات ويتم تطبيقه فورياً على الشحن بالليرة السورية",
        admin_stars_rate_desc: "افتراضياً: 0.01$ للنجمة الواحدة (100 نجمة = 1$)",
        save_stars_rate: "حفظ سعر النجوم",
        admin_margin_rate_desc: "تحدد نسبة ربح المتجر التلقائية على أسعار المورد لجميع المنتجات",
        update_margin: "تحديث الهامش",
        admin_ref_rate_desc: "النسبة التي يحصل عليها العميل من أرباح مشتريات أصدقائه",
        admin_logo_url_desc: "يظهر في أعلى المتجر بجانب الاسم (يدعم PNG و SVG و WebP)",
        save_logo: "حفظ الشعار",
        admin_broadcast_banner_desc: "يظهر أعلى الصفحة لجميع الزوار (اتركه فارغاً لإخفائه)",
        publish_announcement: "نشر الإعلان",
        admin_autorefund_desc: "استرداد الطلبات المعلقة فوراً لحساب العميل عند التعثر",
        update: "تحديث",
        quote_limited_note: "تم تقليص الخصم عند تكلفة المورد حتى لا يسبب خسارة.",
        quote_failed_note: "تعذر حساب السعر النهائي. يرجى إعادة المحاولة.",
        price_unavailable_note: "هذا المنتج غير متاح حالياً بهذا السعر."
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
        instant_delivery: "Automated Delivery",
        custom_activation: "Custom Activation",
        warranty_30d: "30 Days Warranty",
        in_stock: "In Stock",
        out_of_stock: "Out of Stock",
        desc: "Description",
        promo_code_label: "Promo Code",
        apply: "Apply",
        total: "Total Price",
        insufficient_balance: "Insufficient balance for this order.",
        topup_to_continue: "Top Up Balance to Continue",
        buy_now: "Buy",
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
        wallet_ready: "Ready for purchase",
        vip_progress: "Progress to",
        method_section_title: "1. Select Payment Method",
        stars_title: "Telegram Stars",
        stars_sub: "Instant payment via Apple Pay, Google Pay or Stars",
        crypto_title: "USDT (BEP-20 / BNB Chain)",
        crypto_sub: "Instant payment via BEP-20 (Binance Smart Chain)",
        shamcash_title: "Sham Cash",
        shamcash_sub: "Direct payment via Sham Cash wallet",
        syriatelcash_title: "Syriatel Cash",
        syriatelcash_sub: "Direct payment in Syrian Pounds (SYP only)",
        amount_section_title: "2. Choose Amount or Enter Custom",
        custom_amount_placeholder: "Enter amount ($)... e.g. 15",
        voucher_section_title: "Redeem Gift Voucher",
        voucher_btn: "Redeem Voucher",
        theme_section_title: "Appearance",
        theme_dark: "Dark Mode",
        theme_light: "Light Mode",
        install_section_title: "Install App",
        install_desc: "Add GH Store to your phone home screen for instant access!",
        install_btn: "Add to Home Screen",
        currency_title: "Preferred Display Currency",
        lang_title: "Language",
        settings_balance: "Available Balance",
        settings_spent: "Total Purchases",
        copy_id: "Copy ID",
        support_section_title: "Support & Official Channels",
        support_chat_btn: "Contact Customer Support",
        official_channel_btn: "Official Announcements Channel",
        curr_usd_opt: "US Dollar (USD)",
        curr_syp_opt: "Syrian Pound (SYP)",
        admin_sup_s1: "Server 1 (BatStore)",
        admin_sup_s2: "Server 2 (ProdSeller)",
        admin_sup_sam: "SAM Wallet",
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
        sheet_copy_btn: "Copy Direct Payment Link",
        admin_center: "Admin Control Center",
        admin_verified: "Verified Admin",
        stat_revenue: "Total Sales",
        stat_cost: "Supplier Cost",
        stat_profit: "Gross Profit (before fees)",
        stat_balances: "Current Customer Balances",
        stat_users: "Users",
        stat_orders: "Total Orders",
        supplier_wallets: "Supplier Wallets",
        refresh: "Refresh",
        admin_orders_title: "Live Store Orders",
        admin_coupons_title: "Discount Coupons",
        tab_all: "All",
        tab_pending: "Pending",
        tab_completed: "Completed",
        tab_refunded: "Refunded",
        no_matching_orders: "No matching orders.",
        amount_label: "Amount",
        cost_label: "Cost",
        profit_label: "Gross profit",
        confirm_delivery: "Confirm delivery",
        refund_to_customer: "Refund to customer",
        refund_confirm_msg: "Refund this order to the customer wallet balance?",
        refund_done: "Refunded successfully!",
        order_updated: "Order updated!",
        manual_sale_title: "Manual Externally Paid Sale",
        manual_sale_btn: "Deliver paid manual sale",
        recipient_label: "Recipient",
        deliver_self: "Deliver to my account (admin)",
        deliver_other: "Sell to another customer",
        customer_tg_id: "Customer Telegram ID",
        qty_label: "Quantity",
        sale_total: "Regular-price total",
        external_paid_label: "Confirm payment received outside the store",
        external_paid_note: "No wallet balance is debited. The sale is recorded with real revenue.",
        confirm_sale: "Confirm paid sale",
        cancel: "Cancel",
        processing_sale: "Processing sale...",
        sale_success_self: "Sale recorded and product received!",
        external_paid_done: "Paid externally",
        quote_limited_note: "Discount was capped at supplier cost to avoid a loss.",
        quote_failed_note: "Could not compute the final price. Please retry.",
        price_unavailable_note: "This product is currently unavailable at this price.",
        suppliers_drawer: "Suppliers & Servers Control",
        one_time_setup: "Initial System Setup",
        orders_history_btn: "Orders & Refunds Radar",
        users_manage_btn: "Manage Users & Balances",
        coupons_manage_btn: "Manage Discount Coupons",
        sqladmin_btn: "Full SQLAdmin Panel",
        stuck_orders_btn: "Pending & Stuck Orders",
        syp_rate_title: "SYP / USD Exchange Rate",
        referral_rate_title: "Referral Margin Commission (%)",
        logo_url_title: "Store Brand Logo URL",
        margin_rate_title: "Global Profit Margin (%)",
        stars_rate_title: "Telegram Stars / USD Rate",
        broadcast_banner_title: "Broadcast Announcement Banner",
        force_sync_btn: "Force Sync Catalog from Supplier",
        autorefund_title: "Automated Refunds Engine",
        store_settings_title: "Store Operations & Rates",
        store_settings_drawer: "Store Rates & Operations",
        back_to_settings: "Back to Settings",
        sec_hdr_currencies: "Currencies & Exchange Rates",
        sec_hdr_pricing: "Pricing & Profit Margins",
        sec_hdr_branding: "Store Branding & Announcements",
        sec_hdr_operations: "Operations & Synchronization",
        admin_syp_rate_desc: "Database-backed and applied instantly to Syrian Pound top-ups",
        admin_stars_rate_desc: "Default: $0.01 per star (100 stars = $1.00)",
        save_stars_rate: "Save Stars Rate",
        admin_margin_rate_desc: "Sets the store default profit margin over supplier wholesale prices",
        update_margin: "Update Margin",
        admin_ref_rate_desc: "Percentage earned by referrer from friend purchase profit margin",
        admin_logo_url_desc: "Shown in store header next to brand name (PNG, SVG, WebP)",
        save_logo: "Save Logo",
        admin_broadcast_banner_desc: "Broadcast banner shown to all customers (leave empty to hide)",
        publish_announcement: "Publish Announcement",
        admin_autorefund_desc: "Instantly refunds failed or unfulfilled orders back to customer wallet",
        update: "Update"
      }
    };

    function applyLanguage(lang) {
      currentAppLanguage = lang;
      try { localStorage.setItem('ghstore_lang', lang); } catch (e) {}
      cloudStorageSet('ghstore_lang', lang);
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
      updateManualSaleTotal();
      if (userData?.is_admin) renderAdminStatsLabels();
      setText('admin-orders-modal-title', d.admin_orders_title);
      setText('admin-coupons-modal-title', d.admin_coupons_title);
      setText('admin-ord-tab-all', d.tab_all);
      setText('admin-ord-tab-pending', d.tab_pending);
      setText('admin-ord-tab-completed', d.tab_completed);
      setText('admin-ord-tab-refunded', d.tab_refunded);
      const ordersModal = document.getElementById('admin-orders-modal');
      if (ordersModal && ordersModal.style.display === 'flex') loadAdminOrders('all');
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
      setText('admin-center-title', d.admin_center);
      setText('admin-verified-badge', d.admin_verified);
      setText('label-theme-dark', d.theme_dark);
      setText('label-theme-light', d.theme_light);
      setText('admin-supplier-reserves-label', d.supplier_wallets);
      setText('btn-suppliers-drawer-label', d.suppliers_drawer);
      setText('admin-syp-rate-title', d.syp_rate_title);
      setText('admin-ref-rate-title', d.referral_rate_title);
      setText('admin-logo-url-title', d.logo_url_title);
      setText('label-install-title', d.install_section_title);
      setText('label-install-desc', d.install_desc);
      setText('btn-install-app', d.install_btn);
      setText('settings-label-balance', d.settings_balance);
      setText('settings-label-spent', d.settings_spent);
      setText('btn-copy-user-id', d.copy_id);
      setText('label-support-section-title', d.support_section_title);
      setText('label-support-chat-btn', d.support_chat_btn);
      setText('label-official-channel-btn', d.official_channel_btn);
      setText('lbl-curr-usd-opt', d.curr_usd_opt);
      setText('lbl-curr-syp-opt', d.curr_syp_opt);
      setText('admin-sup-s1-title', d.admin_sup_s1);
      setText('admin-sup-details-link', isRtl ? 'تفاصيل ←' : 'Details →');
      setText('admin-sup-s1-sub', isRtl ? 'رصيد المورد 1' : 'Supplier 1 Balance');
      setText('admin-prodseller-tier', isRtl ? 'برونزية' : 'Bronze');
      setText('admin-sup-s2-title', d.admin_sup_s2);
      setText('admin-sup-sam-title', d.admin_sup_sam);
      setText('label-currency-title', d.currency_title);
      setText('label-lang-title', d.lang_title);
      setText('btn-force-sync-label', d.force_sync_btn);
      setText('admin-autorefund-title', d.autorefund_title);
      setText('btn-stuck-orders-label', d.stuck_orders_btn);
      setText('btn-admin-users-drawer', d.users_manage_btn);
      setText('btn-admin-orders-drawer', d.orders_history_btn);
      setText('btn-admin-coupons-drawer', d.coupons_manage_btn);
      setText('btn-admin-sqladmin-drawer', d.sqladmin_btn);
      setText('btn-admin-onetime-label', d.one_time_setup);
      setText('store-settings-header-title', d.store_settings_title);
      setText('btn-back-store-settings-label', d.back_to_settings);
      setText('sec-hdr-currencies', d.sec_hdr_currencies);
      setText('sec-hdr-pricing', d.sec_hdr_pricing);
      setText('sec-hdr-branding', d.sec_hdr_branding);
      setText('sec-hdr-operations', d.sec_hdr_operations);
      setText('admin-syp-rate-desc', d.admin_syp_rate_desc);
      setText('admin-stars-rate-desc', d.admin_stars_rate_desc);
      setText('admin-stars-rate-btn', d.save_stars_rate);
      setText('admin-margin-rate-desc', d.admin_margin_rate_desc);
      setText('btn-margin-update', d.update_margin);
      setText('admin-ref-rate-desc', d.admin_ref_rate_desc);
      setText('admin-logo-url-desc', d.admin_logo_url_desc);
      setText('btn-logo-update', d.save_logo);
      setText('admin-broadcast-banner-desc', d.admin_broadcast_banner_desc);
      setText('btn-announcement-update', d.publish_announcement);
      setText('admin-trending-tags-title', isRtl ? 'العلامات الأكثر بحثاً في المتجر (Trending Search Tags)' : 'Trending Search Tags');
      setText('admin-trending-tags-desc', isRtl ? 'افصل بين الكلمات بفاصلة (اتركه فارغاً للاعتماد على أكثر المنتجات طلباً تلقائياً)' : 'Comma-separated tags (leave empty to derive automatically from top products)');
      setText('btn-trending-tags-update', isRtl ? 'حفظ العلامات' : 'Save Tags');
      setText('admin-autorefund-desc', d.admin_autorefund_desc);
      setText('btn-syp-rate-update', d.update);
      setText('btn-ref-rate-update', d.update);
      setText('btn-store-settings-drawer-label', d.store_settings_drawer);
      setText('admin-stat-label-revenue', d.stat_revenue);
      setText('admin-stat-label-cost', d.stat_cost);
      setText('admin-stat-label-profit', d.stat_profit);
      setText('admin-stat-label-balances', d.stat_balances);
      setText('admin-stat-label-users', d.stat_users);
      setText('admin-stat-label-orders', d.stat_orders);
      setText('admin-detail-gift-label', d.manual_sale_title);
      setText('admin-gift-modal-title', d.manual_sale_title);
      setText('admin-gift-recipient-label', d.recipient_label);
      setText('gift-type-self', d.deliver_self);
      setText('gift-type-user', d.deliver_other);
      setText('admin-gift-tgid-label', d.customer_tg_id);
      setText('admin-gift-qty-label', d.qty_label);
      setText('admin-gift-total-label', d.sale_total);
      setText('admin-gift-paid-label', d.external_paid_label);
      setText('admin-gift-paid-note', d.external_paid_note);
      setText('admin-gift-cancel-btn', d.cancel);
      setText('admin-gift-confirm-label', d.confirm_sale);
      updateManualSaleTotal();
      if (userData?.is_admin) renderAdminStatsLabels();

      const langSelect = document.getElementById('language-select-dropdown');
      if (langSelect) langSelect.value = lang;

      // Activity / Orders Filter Chips
      setText('act-filter-all', d.tab_all || (isRtl ? 'الكل' : 'All'));
      setText('act-filter-vault', isRtl ? '🔐 خزنة المفاتيح' : '🔐 Key Vault');
      setText('act-filter-orders', isRtl ? 'مشتريات المنتجات' : 'Orders');
      setText('act-filter-recharges', isRtl ? 'عمليات الشحن' : 'Top-ups');
      setText('act-filter-attention', isRtl ? 'المعلقة والفاشلة' : 'Pending & Failed');

      // Quick Filters on Storefront
      setText('lbl-filter-all', d.filter_all || (isRtl ? 'الكل' : 'All'));
      setText('label-filter-wishlist', d.filter_wishlist || (isRtl ? 'المفضلة' : 'Favorites'));
      setText('lbl-filter-stock', d.filter_stock || (isRtl ? 'متوفر فقط' : 'In Stock'));
      setText('lbl-filter-instant', d.filter_instant || (isRtl ? 'تسليم فوري' : 'Instant'));
      setText('lbl-filter-lowprice', d.filter_lowprice || (isRtl ? 'الأقل سعراً' : 'Lowest Price'));
      setText('lbl-trending', isRtl ? 'الأكثر بحثاً:' : 'Trending:');

      // View Toggle Labels
      setText('label-view-grid', d.view_grid || (isRtl ? 'شبكة' : 'Grid'));
      setText('label-view-list', d.view_list || (isRtl ? 'قائمة' : 'List'));

      // Dedicated Order Detail View
      setText('btn-back-order-detail-label', isRtl ? 'العودة للعمليات' : 'Back to Activity');
      setText('order-detail-top-title', isRtl ? 'تفاصيل الطلب' : 'Order Details');
      setText('order-detail-total-label', isRtl ? 'إجمالي القيمة:' : 'Total Amount:');
      setText('order-detail-keys-label', isRtl ? 'بيانات التفعيل والحساب:' : 'Delivered Account & License Keys:');
      setText('order-detail-btn-preview-label', isRtl ? 'معاينة الإيصال المعتمد' : 'View Official Receipt');
      setText('order-detail-btn-pdf-label', isRtl ? 'تنزيل ملف PDF' : 'Download PDF');
      setText('order-detail-btn-rate-label', isRtl ? '⭐ تقييم' : '⭐ Rate');
      setText('order-detail-btn-support-label', isRtl ? '💬 فتح تذكرة دعم' : '💬 Support Ticket');

      // Dedicated Invoice View
      setText('btn-back-invoice', isRtl ? 'العودة للمحفظة' : 'Back to Wallet');
      setText('invoice-header-title', isRtl ? 'فاتورة شحن الرصيد' : 'Top-Up Invoice');
      setText('invoice-amount-due-label', isRtl ? 'المبلغ المطلوب سداده' : 'Amount Due');
      setText('invoice-crypto-title', isRtl ? 'عنوان الإيداع المباشر (USDT BEP-20)' : 'Direct Deposit Address (USDT BEP-20)');
      setText('invoice-crypto-copy-btn-label', isRtl ? '📋 نسخ عنوان المحفظة' : '📋 Copy Wallet Address');
      setText('invoice-crypto-warning', isRtl ? '⚠️ أرسل USDT حصراً عبر شبكة BNB Smart Chain (BEP20) لتفادي فقدان الأموال.' : '⚠️ Send USDT strictly via BNB Smart Chain (BEP20) network to avoid loss of funds.');
      setText('invoice-btn-gateway-label', isRtl ? '🌐 فتح بوابة الدفع المباشرة' : '🌐 Open Payment Gateway');
      setText('label-check-invoice', isRtl ? '🔄 التحقق من وصول الدفع وتحديث الرصيد' : '🔄 Check Payment & Update Balance');
      setText('invoice-copy-link-label', isRtl ? '📋 نسخ الرابط' : '📋 Copy Link');
      setText('invoice-return-wallet-label', isRtl ? '✕ العودة للمحفظة' : '✕ Back to Wallet');

      // Admin Live Radar Mode Switchers & Header
      const btnLiveRadar = document.getElementById('btn-mode-live-radar');
      if (btnLiveRadar) btnLiveRadar.innerHTML = `<span>${isRtl ? 'رادار العمليات المباشر' : 'Live Operations Radar'}</span>`;
      const btnMyOrders = document.getElementById('btn-mode-my-orders');
      if (btnMyOrders) btnMyOrders.innerHTML = `<span>${isRtl ? 'طلباتي الشخصية' : 'My Personal Orders'}</span>`;
      setText('admin-radar-title', isRtl ? 'بث مباشر لعمليات المتجر' : 'Live Store Operations Radar');
      setText('admin-radar-refresh-btn-label', isRtl ? 'تحديث حي' : 'Live Refresh');
      setText('admin-radar-desc', isRtl ? 'متابعة حية وفورية لكافة طلبات الشراء وعمليات الشحن في البوت، مع إمكانية اعتماد الشحن المعلق أو الفاشل فورياً.' : 'Real-time live monitoring of all customer purchases and top-ups, with instant manual approval tools.');

      // Admin Users Management Subview
      setText('admin-users-back-label', isRtl ? 'العودة للإعدادات' : 'Back to Settings');
      setText('admin-users-page-title', isRtl ? 'إدارة المستخدمين والأرصدة' : 'Manage Users & Balances');
      setText('admin-ufilter-all', isRtl ? 'الكل' : 'All');
      setText('admin-ufilter-balance', isRtl ? 'لديهم رصيد' : 'Has Balance');
      setText('admin-ufilter-vip', isRtl ? 'VIP فقط' : 'VIP Only');
      setText('admin-ufilter-banned', isRtl ? 'المحظورون فقط' : 'Banned');
      const uSearchInput = document.getElementById('admin-user-search-input');
      if (uSearchInput) uSearchInput.placeholder = isRtl ? 'ابحث برقم ID أو اسم المستخدم @username...' : 'Search by Telegram ID or @username...';

      // Admin Stuck Orders Subview
      setText('admin-stuck-back-label', isRtl ? 'العودة للإعدادات' : 'Back to Settings');
      setText('admin-stuck-page-title', isRtl ? 'الطلبات والعمليات المعلقة' : 'Pending & Stuck Operations');
      setText('admin-stuck-box-title', isRtl ? 'مركز متابعة العمليات العالقة والمبالغ المعلقة' : 'Pending Operations & Stuck Balances Center');
      setText('admin-stuck-box-desc', isRtl ? 'تظهر هنا الطلبات قيد التفعيل والمبالغ المعلقة التي تحتاج لمتابعة أو استرداد يدوي للعملاء.' : 'Shows unfulfilled orders and pending deposits requiring manual review or refund.');

      // Admin One-Time Config Subview
      setText('admin-config-back-label', isRtl ? 'العودة للإعدادات' : 'Back to Settings');
      setText('admin-config-page-title', isRtl ? 'إعدادات التهيئة لمرة واحدة' : 'One-Time System Configuration');
      setText('admin-config-banner-title', isRtl ? '⚙️ إعدادات ومفاتيح الربط الأساسية (One-Time Config)' : '⚙️ Core System & API Keys (One-Time Config)');
      setText('admin-config-banner-desc', isRtl ? 'الحقول مقفلة ومحمية تلقائياً لمنع أي تعديل بالخطأ. اضغط على أيقونة القلم ✏️ بجانب أي إعداد لفتح التعديل عليه وحفظه.' : 'Fields are locked to prevent accidental changes. Tap the pencil ✏️ to unlock and update.');

      // Admin Store Reserves & Liquidity in Wallet
      setText('admin-reserves-title', isRtl ? 'الخزينة واحتياطي الموردين' : 'Store Reserves & Supplier Liquidity');
      setText('admin-reserves-sub', isRtl ? 'لوحة السيولة والتحكم المالي للمتجر' : 'Financial Liquidity & Operations Dashboard');
      setText('admin-reserves-sec-title', isRtl ? 'أرصدة محافظ الموردين والسيولة' : 'Supplier Wallets & Reserves');
      setText('admin-reserves-s1-title', isRtl ? 'رصيد BatStore' : 'BatStore Balance');
      setText('admin-reserves-s1-sub', isRtl ? 'تجهيز الحسابات' : 'Fulfillment Service');
      setText('admin-reserves-sam-title', isRtl ? 'محفظة SAM (USD)' : 'SAM Wallet (USD)');
      setText('admin-reserves-users-label', isRtl ? 'إجمالي أرصدة العملاء الحالية' : 'Total Customer Balances');
      setText('admin-reserves-refresh-label', isRtl ? '🔄 تحديث الأرصدة' : '🔄 Refresh Reserves');
      setText('admin-reserves-actions-title', isRtl ? 'إجراءات الإدارة السريعة' : 'Quick Admin Actions');
      setText('admin-reserves-btn-user', isRtl ? 'تعديل أو إيداع رصيد لأي عميل' : 'Adjust or Deposit Balance for User');
      setText('admin-reserves-btn-config', isRtl ? 'إعدادات المتجر وأسعار الصرف' : 'Store Settings & Exchange Rates');
      setText('admin-reserves-btn-sqladmin', isRtl ? 'الانتقال إلى لوحة SQLAdmin الكاملة' : 'Open Full SQLAdmin Panel');
      setText('admin-demands-title', isRtl ? '🔍 طلبات المنتجات غير المتوفرة (Search Demands)' : '🔍 Top Customer Search Demands (Unstocked)');

      // Currency Picker Labels
      setText('curr-chip-usd', isRtl ? 'الدولار (USD)' : 'US Dollar (USD)');

      // Admin Modal Labels
      setText('admin-bal-lbl-add', isRtl ? 'إضافة رصيد' : 'Add Balance');
      setText('admin-bal-lbl-deduct', isRtl ? 'خصم رصيد' : 'Deduct Balance');
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
      renderUnifiedActivity();
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

      if (tab === 'orders') {
        if (userData?.is_admin) {
          const switcher = document.getElementById('admin-activity-mode-switcher');
          if (switcher) switcher.style.display = 'block';
          if (adminActivityMode === 'radar') {
            switchAdminActivityMode('radar');
          } else {
            switchAdminActivityMode('my_orders');
          }
        } else {
          const switcher = document.getElementById('admin-activity-mode-switcher');
          if (switcher) switcher.style.display = 'none';
          renderUnifiedActivity();
        }
      } else if (tab === 'wallet' || tab === 'settings') {
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

    // Deep Link & Launch Parameter Router (startapp / start_param)
    let _startParamProcessed = false;
    function handleStartParam() {
      if (_startParamProcessed) return;
      const rawParam = (
        tg?.initDataUnsafe?.start_param ||
        urlParams.get('startapp') ||
        urlParams.get('start_param') ||
        urlParams.get('tgWebAppStartParam') ||
        ''
      ).trim();
      if (!rawParam) return;

      if (rawParam.startsWith('prod_') || rawParam.startsWith('p_') || rawParam.startsWith('item_')) {
        if (!allProducts || !allProducts.length) return;
        _startParamProcessed = true;
        const pid = Number(rawParam.replace(/^(prod_|p_|item_)/, ''));
        if (pid && allProducts.some(p => Number(p.id) === pid)) {
          setTimeout(() => openProductDetail(pid), 180);
          return;
        }
      } else if (rawParam.startsWith('cat_') || rawParam.startsWith('c_')) {
        _startParamProcessed = true;
        const catName = decodeURIComponent(rawParam.replace(/^(cat_|c_)/, ''));
        if (catName) {
          setTimeout(() => openCollection(catName), 180);
          return;
        }
      } else if (rawParam === 'wallet' || rawParam === 'recharge' || rawParam === 'topup') {
        _startParamProcessed = true;
        switchTab('wallet');
        return;
      } else if (rawParam === 'cart') {
        _startParamProcessed = true;
        setTimeout(() => openCartDrawer(), 180);
        return;
      } else if (rawParam.startsWith('voucher_') || rawParam.startsWith('v_')) {
        _startParamProcessed = true;
        const code = rawParam.replace(/^(voucher_|v_)/, '').toUpperCase();
        switchTab('wallet');
        setTimeout(() => {
          const inp = document.getElementById('voucher-code-input');
          if (inp) {
            inp.value = code;
            inp.scrollIntoView({ behavior: 'smooth' });
          }
        }, 200);
        return;
      } else if (rawParam.startsWith('ref_') || rawParam.startsWith('r_')) {
        _startParamProcessed = true;
        const refCode = rawParam.replace(/^(ref_|r_)/, '');
        try {
          localStorage.setItem('ghstore_referrer_code', refCode);
          cloudStorageSet('ghstore_referrer_code', refCode);
        } catch (e) {}
        return;
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
          handleStartParam();
        }
        const userCache = localStorage.getItem('ghstore_user_cache');
        if (userCache) {
          userData = JSON.parse(userCache);
          updateBalancePills();
        }
      } catch (e) {}
    }
    function renderDynamicBanners(banners) {
      if (!banners || !banners.length) return;
      const b = banners[0];
      const title = (currentAppLanguage === 'ar' && b.title_ar) ? b.title_ar : (b.title_en || b.title_ar);
      const sub = (currentAppLanguage === 'ar' && b.subtitle_ar) ? b.subtitle_ar : (b.subtitle_en || b.subtitle_ar);
      const badge = (currentAppLanguage === 'ar' && b.badge_ar) ? b.badge_ar : (b.badge_en || b.badge_ar);

      const titleEl = document.getElementById('banner-title-text');
      const subEl = document.getElementById('banner-sub-text');
      const badgeEl = document.getElementById('banner-badge-text');

      if (titleEl && title) titleEl.innerText = title;
      if (subEl && sub) subEl.innerText = sub;
      if (badgeEl && badge) badgeEl.innerText = badge;

      const container = document.getElementById('hero-banner-container');
      if (container) {
        if (b.product_id) {
          container.style.cursor = 'pointer';
          container.onclick = () => openProductDetail(b.product_id);
        } else if (b.target_category) {
          container.style.cursor = 'pointer';
          container.onclick = () => openCollection(b.target_category);
        }
      }
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
        if (d.flash_sale) initFlashSaleTimer(d.flash_sale);
        if (d.banners && d.banners.length) renderDynamicBanners(d.banners);
        initTrendingSearches();
        if (activeCatalog) {
          openCollection(activeCatalog);
        }
        handleStartParam();
      } catch (e) {
        if (!allProducts.length) {
        document.getElementById('catalogs-grid').innerHTML = `<div style="color: var(--hint); text-align: center; padding: 30px;">${currentAppLanguage === 'ar' ? 'فشل تحميل التصنيفات.' : 'Failed to load categories.'}</div>`;
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
          ? `<button class="admin-edit-badge-btn" onclick="openAdminCategoryEditor(${catId}, event)">${currentAppLanguage === 'ar' ? 'تعديل' : 'Edit'}</button>`
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
      document.getElementById('service-variants-mode').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'none';
      document.getElementById('catalogs-collection-mode').style.display = 'block';
      activeVariantFamilyKey = null;
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
    let logSearchTimer = null;
    function handleSearch() {
      const rawQ = (document.getElementById('store-search-input').value || '').trim().toLowerCase();
      const clearBtn = document.getElementById('store-clear-btn');
      const autoBox = document.getElementById('search-autocomplete-dropdown');

      // Autocomplete Suggestions Dropdown
      if (rawQ.length >= 2 && autoBox) {
        const suggestions = allProducts.filter(p => {
          const nameStr = ((p.clean_name || '') + ' ' + (p.name || '')).toLowerCase();
          return nameStr.includes(rawQ);
        }).slice(0, 5);
        if (suggestions.length) {
          autoBox.innerHTML = suggestions.map(p => {
            const { origPrice, finalPrice, hasDiscount, discPct } = calculateProductPrices(p);
            const priceHtml = hasDiscount
              ? `<div style="display:flex; align-items:baseline; gap:4px;"><span style="color:var(--accent); font-weight:800;">${formatPrice(finalPrice)}</span><span style="font-size:10px; text-decoration:line-through; color:var(--hint);">${formatPrice(origPrice)}</span><span class="prod-discount-badge" style="font-size:9px;">-${discPct}%</span></div>`
              : `<span style="color:var(--accent); font-weight:800;">${formatPrice(origPrice)}</span>`;
            return `
              <div class="search-autocomplete-item" onclick="selectSearchAutocomplete(${p.id})">
                <div class="search-item-left">
                  <div style="min-width: 0;">
                    <div class="search-item-name">${p.clean_name || p.name}</div>
                    <div class="search-item-cat">${p.category || 'Digital'}</div>
                  </div>
                </div>
                <div class="search-item-price">${priceHtml}</div>
              </div>
            `;
          }).join('');
          autoBox.style.display = 'block';
        } else {
          autoBox.style.display = 'none';
        }
      } else if (autoBox) {
        autoBox.style.display = 'none';
      }

      if (rawQ) {
        clearTimeout(logSearchTimer);
        logSearchTimer = setTimeout(() => {
          fetch('/api/search/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: rawQ })
          }).catch(() => {});
        }, 1500);

        clearBtn.style.display = 'block';
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

    function selectSearchAutocomplete(productId) {
      haptic('medium');
      const autoBox = document.getElementById('search-autocomplete-dropdown');
      if (autoBox) autoBox.style.display = 'none';
      openProductDetail(productId);
    }

    function clearSearch() {
      const autoBox = document.getElementById('search-autocomplete-dropdown');
      if (autoBox) autoBox.style.display = 'none';
      document.getElementById('store-search-input').value = '';
      returnToCollections();
    }

    // Real-Time Currency Preference & Formatter
    function getCurrentCurrencyPref() {
      return userData?.currency_preference || localStorage.getItem('ghstore_curr_pref') || 'USD';
    }

    function getSypRate() {
      return Number(userData?.syp_rate || userData?.admin_stats?.syp_usd_rate || 14500);
    }

    function formatPrice(amountUsd) {
      if (amountUsd === null || amountUsd === undefined || isNaN(amountUsd)) return 'N/A';
      const pref = getCurrentCurrencyPref();
      const num = Number(amountUsd);
      if (pref === 'SYP') {
        const syp = Math.round(num * getSypRate());
        return `${syp.toLocaleString()} ${currentAppLanguage === 'ar' ? 'ل.س' : 'SYP'}`;
      }
      return `$${num.toFixed(2)}`;
    }

    function formatBalance(amountUsd) {
      if (amountUsd === null || amountUsd === undefined || isNaN(amountUsd)) return '$0.00';
      const pref = getCurrentCurrencyPref();
      const num = Number(amountUsd);
      if (pref === 'SYP') {
        const syp = Math.round(num * getSypRate());
        return `${syp.toLocaleString()} ${currentAppLanguage === 'ar' ? 'ل.س' : 'SYP'}`;
      }
      return `$${num.toFixed(2)}`;
    }

    function getDualCurrencyPreview(amountUsd) {
      return '';
    }
    // Navigation State & Index-based Registry for Dedicated Variants Page
    let activeVariantFamilyKey = null;
    let _serviceFamilyRegistry = [];

    function getProductFamilyKey(p) {
      if (!p) return 'Other';
      if (p.custom_group) return p.custom_group;
      const raw = (p.custom_name || p.clean_name || p.name || '').trim();
      const lower = raw.toLowerCase();
      const brands = [
        ['chatgpt', 'ChatGPT Plus'],
        ['claude', 'Claude API & Pro'],
        ['gemini', 'Google Gemini Advanced'],
        ['netflix', 'Netflix Premium'],
        ['canva', 'Canva Pro'],
        ['spotify', 'Spotify Premium'],
        ['tradingview', 'TradingView'],
        ['coursera', 'Coursera Plus'],
        ['duolingo', 'Duolingo Super'],
        ['peacock', 'Peacock TV'],
        ['windows 11', 'Windows 11 Pro'],
        ['windows 10', 'Windows 10 Pro'],
        ['office 365', 'Microsoft 365'],
        ['microsoft 365', 'Microsoft 365'],
        ['capcut', 'CapCut Pro'],
        ['nordvpn', 'NordVPN'],
        ['expressvpn', 'ExpressVPN'],
        ['elevenlabs', 'ElevenLabs AI'],
        ['gamma', 'Gamma AI'],
        ['framer', 'Framer AI'],
        ['figma', 'Figma Pro'],
        ['apple tv', 'Apple TV+'],
        ['shahid', 'Shahid VIP']
      ];
      for (const [kw, family] of brands) {
        if (lower.includes(kw)) return family;
      }
      return p.clean_name || p.name;
    }

    function getUserDiscountPercent() {
      if (userData?.vip_discount !== undefined && userData?.vip_discount !== null) {
        return Number(userData.vip_discount);
      }
      try {
        const cached = JSON.parse(localStorage.getItem('ghstore_user_cache') || '{}');
        return Number(cached.vip_discount || 0);
      } catch (e) {
        return 0;
      }
    }
    function calculateProductPrices(product) {
      const origPrice = Number(product?.price || 0.0);
      const costUsd = Number(product?.cost_usd || 0.0);
      const discPct = getUserDiscountPercent();

      let finalPrice = origPrice;
      let hasDiscount = false;

      if (discPct > 0) {
        const rawDiscounted = Math.round((origPrice * (1 - discPct / 100)) * 100) / 100;
        finalPrice = costUsd > 0 ? Math.max(costUsd, rawDiscounted) : rawDiscounted;
        hasDiscount = (finalPrice < origPrice);
      }

      const profitUsd = Math.max(0, Math.round((finalPrice - costUsd) * 100) / 100);
      const marginPct = costUsd > 0 ? Math.round(((finalPrice - costUsd) / costUsd) * 100) : 0;

      return {
        origPrice,
        finalPrice,
        hasDiscount,
        discPct,
        costUsd,
        profitUsd,
        marginPct
      };
    }

    function renderPriceBoxHTML(product, isMulti, favSvg, tapHint) {
      const { origPrice, finalPrice, hasDiscount, discPct, costUsd, profitUsd } = calculateProductPrices(product);
      const isAdmin = !!(userData && userData.is_admin);
      const d = I18N[currentAppLanguage] || I18N.ar;
      const startsPrefix = isMulti ? `<span style="font-size: 10px; color: var(--hint); font-weight: 600;">${d.starts_from || 'من'} </span>` : '';

      let priceRow = '';
      if (hasDiscount) {
        priceRow = `
          <div class="prod-price-row-wrap">
            ${startsPrefix}
            <span class="prod-price">${formatPrice(finalPrice)}</span>
            <span class="prod-price-original">${formatPrice(origPrice)}</span>
            <span class="prod-discount-badge">-${discPct}%</span>
          </div>
        `;
      } else {
        priceRow = `<div class="prod-price">${startsPrefix}${formatPrice(origPrice)}</div>`;
      }

      let adminCostRow = '';
      if (isAdmin && costUsd > 0) {
        const costLbl = (currentAppLanguage === 'ar') ? 'مورد' : 'Cost';
        const profLbl = (currentAppLanguage === 'ar') ? 'ربح' : 'Profit';
        adminCostRow = `
          <div class="prod-admin-cost">
            <span>${costLbl}: ${formatPrice(costUsd)}</span>
            <span>· ${profLbl}: +${formatPrice(profitUsd)}</span>
          </div>
        `;
      }

      return `
        <div class="prod-price-box">
          ${priceRow}
          ${adminCostRow}
          <div style="display: flex; align-items: center; gap: 4px; margin-top: 2px;">
            ${favSvg ? `<button class="fav-btn-action" data-pid="${product.id}" onclick="toggleWishlist(${product.id}, event)">${favSvg}</button>` : ''}
            <div class="prod-tap-hint">${tapHint}</div>
          </div>
        </div>
      `;
    }

    function findAlternateServerProduct(product) {
      if (!product || !allProducts || !allProducts.length) return null;
      const clean = (product.clean_name || product.name || '').trim().toLowerCase();
      if (!clean) return null;
      return allProducts.find(p => {
        if (p.id === product.id) return false;
        if (p.supplier === product.supplier) return false;
        if (p.stock !== null && Number(p.stock) <= 0) return false;
        const pClean = (p.clean_name || p.name || '').trim().toLowerCase();
        return pClean.includes(clean) || clean.includes(pClean);
      });
    }

    function checkProductEffectiveStock(product) {
      if (!product) {
        return { isOutOfStock: true, effectiveStock: 0, isFailoverAvailable: false, alternateProduct: null };
      }
      const directInStock = (product.stock === null || Number(product.stock) > 0);
      if (directInStock) {
        return {
          isOutOfStock: false,
          effectiveStock: product.stock,
          isFailoverAvailable: false,
          alternateProduct: null
        };
      }

      // Direct item has stock <= 0, check if alternate server has duplicate offering in stock
      const alternate = findAlternateServerProduct(product);
      if (alternate) {
        return {
          isOutOfStock: false,
          effectiveStock: alternate.stock,
          isFailoverAvailable: true,
          alternateProduct: alternate
        };
      }

      // Out of stock on BOTH servers
      return {
        isOutOfStock: true,
        effectiveStock: 0,
        isFailoverAvailable: false,
        alternateProduct: null
      };
    }

    // Category Products Listing: Groups multi-variant products into clean family cards
    function renderProductItems(products) {
      const container = document.getElementById('catalog-products-list');
      if (!container) return;
      if (!products.length) {
        container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--hint);">${currentAppLanguage === 'ar' ? 'لا توجد منتجات مطابقة لهذا الفلتر.' : 'No products found matching this filter.'}</div>`;
        return;
      }
      const d = I18N[currentAppLanguage] || I18N.ar;
      const isAdmin = !!(userData && userData.is_admin);

      // Group by family within category
      const familyMap = new Map();
      products.forEach(p => {
        const famKey = (p.category || 'Other') + ':::' + getProductFamilyKey(p);
        if (!familyMap.has(famKey)) {
          familyMap.set(famKey, []);
        }
        familyMap.get(famKey).push(p);
      });

      _serviceFamilyRegistry = [];
      let regIdx = 0;
      let html = '';
      for (const [famKey, items] of familyMap.entries()) {
        // Prioritize in-stock offerings from either server first
        items.sort((a, b) => {
          const aStock = checkProductEffectiveStock(a);
          const bStock = checkProductEffectiveStock(b);
          if (aStock.isOutOfStock !== bStock.isOutOfStock) {
            return aStock.isOutOfStock ? 1 : -1;
          }
          return (a.price || 0) - (b.price || 0);
        });
        const primary = items[0];
        const isMulti = items.length > 1;
        const currentIdx = regIdx++;
        const groupTitle = isMulti ? getProductFamilyKey(primary) : (primary.custom_name || primary.name || primary.clean_name);
        _serviceFamilyRegistry.push({
          famKey: famKey,
          title: groupTitle,
          items: items
        });
        const isFav = wishlistSet.has(Number(primary.id));
        const anyInStock = items.some(it => !checkProductEffectiveStock(it).isOutOfStock);
        const isOutOfStock = !anyInStock;

        const stockBadge = isOutOfStock
          ? `<span class="spec-pill stock-out">${d.out_of_stock}</span>`
          : `<span class="spec-pill in-stock">${primary.stock ? `${d.in_stock} (${primary.stock})` : d.in_stock}</span>`;
        const isActivation = (primary.delivery_type === 'activation');
        const deliveryBadge = isActivation
          ? `<span class="spec-pill delivery-activation">${currentAppLanguage === 'ar' ? 'تفعيل مخصص' : 'Activation'}</span>`
          : `<span class="spec-pill delivery-instant">${currentAppLanguage === 'ar' ? 'تسليم فوري' : 'Instant'}</span>`;

        const multiBadge = isMulti
          ? `<span class="spec-pill in-stock" style="background: rgba(56,189,248,0.15); color: var(--accent); font-weight: 800;">${items.length} ${currentAppLanguage === 'ar' ? 'خيارات وباقات متوفرة' : 'Options Available'}</span>`
          : '';

        const durText = (currentAppLanguage === 'ar' ? primary.duration_ar : primary.duration_en) || null;
        const warText = (currentAppLanguage === 'ar' ? primary.warranty_ar : primary.warranty_en) || null;
        const durPill = (!isMulti && durText) ? `<span class="spec-pill duration">${durText}</span>` : '';
        const warPill = (!isMulti && warText && !warText.includes('بدون') && !warText.includes('No')) ? `<span class="spec-pill warranty">${warText}</span>` : '';

        const favSvg = `
          <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="18" height="18">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
        `;

        const displayTitle = isMulti
          ? getProductFamilyKey(primary)
          : (primary.custom_name || primary.name || primary.clean_name);

        const adminEditBtn = isAdmin
          ? `<button class="admin-edit-badge-btn" onclick="openAdminProductEditor(${primary.id}, event)">${currentAppLanguage === 'ar' ? 'تعديل' : 'Edit'}</button>`
          : '';

        const priceDisplay = isMulti
          ? `<span style="font-size: 10px; color: var(--hint); font-weight: 600;">${d.starts_from || (currentAppLanguage === 'ar' ? 'يبدأ من' : 'From')}</span> ${formatPrice(primary.price)}`
          : formatPrice(primary.price);

        const clickAction = isMulti
          ? `openServiceVariantsByIndex(${currentIdx})`
          : `openProductDetail(${Number(primary.id)})`;

        html += `
          <div class="product-row" onclick="${clickAction}">
            <div class="prod-left">
              <div style="display:flex; align-items:center;">
                <span class="prod-title">${displayTitle}</span>
                ${adminEditBtn}
              </div>
              <div class="prod-specs-row">
                ${stockBadge}
                ${deliveryBadge}
                ${multiBadge}
                ${durPill}
                ${warPill}
              </div>
            </div>
            ${renderPriceBoxHTML(primary, isMulti, favSvg, isMulti ? (currentAppLanguage === 'ar' ? 'عرض الباقات ‹' : 'Options ›') : d.view_details)}
          </div>
        `;
      }
      container.innerHTML = html;
    }

    // Dedicated Page Subview Showing All Variants (Same format as products page)
    function openServiceVariantsByIndex(idx) {
      haptic('light');
      const entry = _serviceFamilyRegistry[idx];
      if (!entry) return;
      activeVariantFamilyKey = entry.famKey;

      const titleEl = document.getElementById('active-service-title');
      if (titleEl) titleEl.innerText = entry.title || 'باقات الخدمة';

      const backLabelEl = document.getElementById('btn-back-variants');
      if (backLabelEl) {
        backLabelEl.innerText = (currentAppLanguage === 'ar')
          ? (activeCatalog ? 'الرجوع للتصنيف' : 'الرجوع للبحث')
          : (activeCatalog ? 'Back to Category' : 'Back to Search');
      }
      const backArrow = (currentAppLanguage === 'ar') ? '→' : '←';
      const arrowEl = document.getElementById('icon-back-variants');
      if (arrowEl) arrowEl.innerText = backArrow;

      // Switch modes
      document.getElementById('catalogs-collection-mode').style.display = 'none';
      document.getElementById('products-catalog-mode').style.display = 'none';
      document.getElementById('service-variants-mode').style.display = 'block';
      window.scrollTo(0, 0);

      const siblings = entry.items.slice().sort((a, b) => (a.price || 0) - (b.price || 0));
      const container = document.getElementById('service-variants-products-list');
      if (container) {
        const d = I18N[currentAppLanguage] || I18N.ar;
        const isAdmin = !!(userData && userData.is_admin);

        container.innerHTML = siblings.map(p => {
          const isFav = wishlistSet.has(Number(p.id));
          const stockInfo = checkProductEffectiveStock(p);
          const isOutOfStock = stockInfo.isOutOfStock;

          const stockBadge = isOutOfStock
            ? `<span class="spec-pill stock-out">${d.out_of_stock}</span>`
            : `<span class="spec-pill in-stock">${p.stock ? `${d.in_stock} (${p.stock})` : (stockInfo.isFailoverAvailable ? `${d.in_stock} (بديل)` : d.in_stock)}</span>`;

          const isActivation = (p.delivery_type === 'activation');
          const deliveryBadge = isActivation
            ? `<span class="spec-pill delivery-activation">${currentAppLanguage === 'ar' ? 'تفعيل مخصص' : 'Activation'}</span>`
            : `<span class="spec-pill delivery-instant">${currentAppLanguage === 'ar' ? 'تسليم فوري' : 'Instant'}</span>`;

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

          const displayTitle = p.custom_name || p.name;
          const adminEditBtn = isAdmin
            ? `<button class="admin-edit-badge-btn" onclick="openAdminProductEditor(${p.id}, event)">${currentAppLanguage === 'ar' ? 'تعديل' : 'Edit'}</button>`
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
                  ${deliveryBadge}
                  ${durPill}
                  ${warPill}
                  ${typPill}
                </div>
              </div>
              ${renderPriceBoxHTML(p, false, favSvg, d.view_details)}
            </div>
          `;
        }).join('');
      }

      pushNav('service_variants', returnFromVariantsToPrevious);
    }

    function openServiceVariantsPage(famKey, famTitle) {
      const idx = _serviceFamilyRegistry.findIndex(e => e.famKey === famKey);
      if (idx !== -1) {
        openServiceVariantsByIndex(idx);
      }
    }

    function returnFromVariantsToPrevious() {
      haptic('light');
      activeVariantFamilyKey = null;
      document.getElementById('service-variants-mode').style.display = 'none';

      if (activeCatalog) {
        document.getElementById('products-catalog-mode').style.display = 'block';
      } else if (document.getElementById('store-search-input').value.trim()) {
        document.getElementById('products-catalog-mode').style.display = 'block';
      } else {
        document.getElementById('catalogs-collection-mode').style.display = 'block';
      }

      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'service_variants') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }
    // DEDICATED IN-APP PRODUCT DETAIL PAGE
    function openProductDetail(productId) {
      haptic('light');
      selectedProduct = allProducts.find(p => Number(p.id) === Number(productId));
      if (!selectedProduct) return;
      selectedQty = 1;
      appliedCoupon = null;
      const d = I18N[currentAppLanguage] || I18N.en || I18N.ar;

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
        const stockInfo = checkProductEffectiveStock(selectedProduct);
        const isOutOfStock = stockInfo.isOutOfStock;

        setTxt('prod-delivery-badge', isInstant
          ? (currentAppLanguage === 'ar' ? 'تسليم تلقائي' : 'Automated Delivery')
          : (currentAppLanguage === 'ar' ? 'تفعيل مخصص' : 'Custom Activation'));

        let stockText = d.in_stock;
        if (isOutOfStock) {
          stockText = d.out_of_stock;
        } else if (stockInfo.isFailoverAvailable) {
          stockText = (currentAppLanguage === 'ar') ? 'متوفر (سيرفر بديل)' : 'In Stock (Alternate Server)';
        } else if (selectedProduct.stock) {
          stockText = `${d.in_stock} (${selectedProduct.stock})`;
        } else {
          stockText = d.instant_delivery;
        }
        setTxt('prod-stock-badge', stockText);
        const stockBadgeEl = document.getElementById('prod-stock-badge');
        if (stockBadgeEl) {
          stockBadgeEl.className = isOutOfStock ? 'pill-badge spec-pill stock-out' : 'pill-badge in-stock';
        }

        // Admin detail edit and gift buttons
        const adminDetailEdit = document.getElementById('admin-detail-edit-container');
        if (adminDetailEdit) {
          adminDetailEdit.style.display = (userData && userData.is_admin) ? 'block' : 'none';
        }
        const adminDetailGift = document.getElementById('admin-detail-gift-container');
        if (adminDetailGift) {
          adminDetailGift.style.display = (userData && userData.is_admin) ? 'block' : 'none';
        }

        // Multi-Supplier Server Badge in Product Detail
        const serverBadgeEl = document.getElementById('prod-server-badge');
        if (serverBadgeEl) {
          if (selectedProduct.supplier === 'prodseller') {
            serverBadgeEl.innerText = (currentAppLanguage === 'ar') ? 'سيرفر 2 (ProdSeller)' : 'Server 2 (ProdSeller)';
            serverBadgeEl.style.display = 'inline-block';
            serverBadgeEl.style.background = 'rgba(16, 185, 129, 0.15)';
            serverBadgeEl.style.color = '#10b981';
          } else if (selectedProduct.supplier === 'batstore' || selectedProduct.server_badge) {
            serverBadgeEl.innerText = (currentAppLanguage === 'ar') ? 'سيرفر 1 (BatStore)' : 'Server 1 (BatStore)';
            serverBadgeEl.style.display = 'inline-block';
            serverBadgeEl.style.background = 'rgba(56, 189, 248, 0.15)';
            serverBadgeEl.style.color = 'var(--accent)';
          } else {
            serverBadgeEl.style.display = 'none';
          }
        }

        const editBtn = document.getElementById('admin-detail-edit-btn');
        if (editBtn) editBtn.innerText = (currentAppLanguage === 'ar') ? 'تعديل بيانات المنتج كمسؤول' : 'Edit Product as Admin';

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

        if (isOutOfStock) {
          if (restockBox) restockBox.style.display = 'block';
          if (buyBtn) buyBtn.style.display = 'none';
        } else {
          if (restockBox) restockBox.style.display = 'none';
          if (buyBtn) buyBtn.style.display = 'flex';
        }

        updateWishlistUI();
        updateDetailPagePrice();
        renderProductDetailVariants();
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
      const varContainer = document.getElementById('detail-variants-container');
      if (varContainer) varContainer.style.display = 'none';
      const detailView = document.getElementById('view-product-detail');
      if (detailView) detailView.classList.remove('active');
      const storeView = document.getElementById('view-store');
      if (storeView) storeView.classList.add('active');

      if (activeVariantFamilyKey) {
        document.getElementById('service-variants-mode').style.display = 'block';
        document.getElementById('products-catalog-mode').style.display = 'none';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
      } else if (activeCatalog) {
        document.getElementById('products-catalog-mode').style.display = 'block';
        document.getElementById('service-variants-mode').style.display = 'none';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
      } else if (document.getElementById('store-search-input').value.trim()) {
        document.getElementById('products-catalog-mode').style.display = 'block';
        document.getElementById('service-variants-mode').style.display = 'none';
        document.getElementById('catalogs-collection-mode').style.display = 'none';
      } else {
        document.getElementById('catalogs-collection-mode').style.display = 'block';
        document.getElementById('products-catalog-mode').style.display = 'none';
        document.getElementById('service-variants-mode').style.display = 'none';
      }

      if (tg?.MainButton) {
        tg.MainButton.offClick(executeProductBuy);
        tg.MainButton.offClick(goToWalletFromMainBtn);
        tg.MainButton.offClick(triggerInAppRestockSubscribe);
        tg.MainButton.hide();
      }
      if (tg?.SecondaryButton) {
        tg.SecondaryButton.offClick(addToCartCurrentProduct);
        tg.SecondaryButton.hide();
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

    // AUTHORITATIVE PRICE UPDATER (POST /api/price-quote; never exposes supplier cost)
    let detailQuoteSeq = 0;
    async function updateDetailPagePrice() {
      if (!selectedProduct) return;
      const unit = selectedProduct.price || 0.0;
      const sym = selectedProduct.sym || '$';
      const d = I18N[currentAppLanguage] || I18N.ar;
      const buyBtn = document.getElementById('btn-inapp-purchase');
      const buyLabel = document.getElementById('btn-buy-action-label');
      const priceTag = document.getElementById('btn-price-tag');
      const totalTag = document.getElementById('prod-total-price');
      const discTag = document.getElementById('prod-discount-tag');
      const alertBox = document.getElementById('insufficient-funds-alert');

      // Instant local estimate; the authoritative quote below overwrites it.
      const estimate = unit * selectedQty;
      if (totalTag) totalTag.innerText = `${estimate.toFixed(2)}${sym}`;
      if (priceTag) priceTag.innerText = `(${estimate.toFixed(2)}${sym})`;
      if (buyBtn) buyBtn.disabled = true;

      const seq = ++detailQuoteSeq;
      let quote = null;
      try {
        const res = await fetch('/api/price-quote', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            items: [{ product_id: selectedProduct.id, quantity: selectedQty }],
            coupon_code: appliedCoupon?.code || undefined
          })
        });
        const payload = await res.json();
        if (seq !== detailQuoteSeq) return; // stale async result
        if (!res.ok || payload.error) {
          quote = { total: unit * selectedQty, discount_limited: false };
        } else {
          quote = payload;
        }
      } catch (e) {
        if (seq !== detailQuoteSeq) return;
        quote = { total: unit * selectedQty, discount_limited: false };
      }

      const total = quote.total;
      const origTotal = unit * selectedQty;
      const origTag = document.getElementById('prod-original-price');
      const liveDiscBadge = document.getElementById('prod-live-discount-badge');
      const adminPricingBox = document.getElementById('admin-detail-pricing-box');

      // Live customer discount calculation
      if (total < origTotal && origTag && liveDiscBadge) {
        origTag.style.display = 'inline';
        origTag.innerText = formatPrice(origTotal);
        liveDiscBadge.style.display = 'inline-block';
        const effectivePct = Math.round(((origTotal - total) / origTotal) * 100);
        liveDiscBadge.innerText = `-${effectivePct}%`;
      } else {
        if (origTag) origTag.style.display = 'none';
        if (liveDiscBadge) liveDiscBadge.style.display = 'none';
      }

      // Admin live wholesale cost and margin breakdown
      if (adminPricingBox) {
        const costUsd = Number(selectedProduct.cost_usd || 0.0);
        const isAdmin = !!(userData && userData.is_admin);
        if (isAdmin && costUsd > 0) {
          adminPricingBox.style.display = 'block';
          const setVal = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt; };
          const totalCost = costUsd * selectedQty;
          const totalProfit = Math.max(0, total - totalCost);
          setVal('admin-detail-cost-val', formatPrice(totalCost));
          setVal('admin-detail-sell-val', formatPrice(origTotal));
          setVal('admin-detail-profit-val', `+${formatPrice(totalProfit)}`);
        } else {
          adminPricingBox.style.display = 'none';
        }
      }

      let discountText = '';
      if (quote.discount_limited) discountText = d.quote_limited_note;
      else if (appliedCoupon?.code) discountText = (currentAppLanguage === 'ar') ? `(كوبون: ${appliedCoupon.code})` : `(Coupon: ${appliedCoupon.code})`;
      if (discTag) discTag.innerText = discountText;
      if (totalTag) totalTag.innerText = formatPrice(total);
      const dualTag = document.getElementById('prod-total-dual-price');
      if (dualTag) dualTag.innerHTML = getDualCurrencyPreview(total);
      if (priceTag) { priceTag.innerText = `(${formatPrice(total)})`; priceTag.style.display = 'inline'; }

      const userBalance = userData?.balance || 0.0;
      if (userBalance < total) {
        const shortage = Math.max(0.01, +(total - userBalance).toFixed(2));
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.innerHTML = `
            <div style="margin-bottom: 8px;">
              ${(currentAppLanguage === 'ar')
                ? `الرصيد المتاح غير كافٍ (تحتاج ${total.toFixed(2)}${sym}، رصيدك $${userBalance.toFixed(2)}).`
                : `Insufficient balance (Requires ${total.toFixed(2)}${sym}, available $${userBalance.toFixed(2)}).`}
            </div>
            <div style="display: flex; gap: 6px; justify-content: center; flex-wrap: wrap;">
              <button type="button" onclick="quickTopupShortageStars(${shortage})" class="btn-action-warning" style="height: 32px; padding: 0 12px; font-size: 11px; font-weight: 800; background: linear-gradient(135deg, #f59e0b, #d97706); border: none; color: #fff; border-radius: 8px;">
                ${(currentAppLanguage === 'ar') ? `شحن النقص بالنجوم ($${shortage.toFixed(2)})` : `Top up exact $${shortage.toFixed(2)} via Stars`}
              </button>
              <button type="button" onclick="quickTopupShortageWallet(${shortage})" class="btn-action-secondary" style="height: 32px; padding: 0 10px; font-size: 11px; font-weight: 700;">
                ${(currentAppLanguage === 'ar') ? 'خيارات شحن أخرى' : 'Other Payment Rails'}
              </button>
            </div>
          `;
        }
        if (buyLabel) buyLabel.innerText = d.topup_to_continue;
        if (priceTag) priceTag.style.display = 'none';
        if (buyBtn) { buyBtn.disabled = false; buyBtn.onclick = () => quickTopupShortageWallet(shortage); }
      } else {
        if (alertBox) alertBox.style.display = 'none';
        if (buyLabel) buyLabel.innerText = d.buy_now;
        if (buyBtn) { buyBtn.disabled = false; buyBtn.onclick = executeProductBuy; }
      }

      if (tg?.MainButton) {
        tg.MainButton.offClick(executeProductBuy);
        tg.MainButton.offClick(goToWalletFromMainBtn);
        tg.MainButton.offClick(triggerInAppRestockSubscribe);
        if (userBalance < total) {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? `شحن الرصيد للمتابعة ($${userBalance.toFixed(2)})` : `Top up balance ($${userBalance.toFixed(2)})`)
            .show()
            .enable();
          tg.MainButton.onClick(goToWalletFromMainBtn);
        } else {
          tg.MainButton.setText(currentAppLanguage === 'ar' ? `شراء الآن • ${formatPrice(total)}` : `Buy Now • ${formatPrice(total)}`)
            .show()
            .enable();
          tg.MainButton.onClick(executeProductBuy);
        }
      }
      if (tg?.SecondaryButton) {
        tg.SecondaryButton.offClick(addToCartCurrentProduct);
        if (!isOutOfStock) {
          tg.SecondaryButton.setParams({
            text: currentAppLanguage === 'ar' ? 'إضافة إلى السلة 🛒' : 'Add to Cart 🛒',
            position: 'left',
            is_visible: true,
            is_active: true
          });
          tg.SecondaryButton.onClick(addToCartCurrentProduct);
        } else {
          tg.SecondaryButton.hide();
        }
      }
    }

    function goToWalletFromMainBtn() {
      closeProductDetailPage();
      switchTab('wallet');
    }

    async function quickTopupShortageStars(amountUsd) {
      if (!userId || !amountUsd) return;
      haptic('medium');
      try {
        const res = await fetch('/api/invoice/topup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, amount: amountUsd, method: 'stars' })
        });
        const d = await res.json();
        if (d.status === 'ok' && d.invoice_link) {
          if (tg?.openInvoice) {
            tg.openInvoice(d.invoice_link, (status) => {
              if (status === 'paid') {
                fireConfetti();
                haptic('success');
                showToast(currentAppLanguage === 'ar' ? '✅ تم شحن الرصيد بنجاح!' : 'Balance topped up successfully!');
                loadUserData().then(() => updateDetailPagePrice());
              }
            });
          } else {
            window.open(d.invoice_link, '_blank');
          }
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'تعذر إنشاء فاتورة النجوم' : 'Failed to create Stars invoice');
      }
    }

    function quickTopupShortageWallet(amountUsd) {
      haptic('light');
      closeProductDetailPage();
      selectedRechargeAmount = amountUsd;
      const customInput = document.getElementById('custom-topup-input');
      if (customInput) customInput.value = amountUsd.toFixed(2);
      switchTab('wallet');
    }

    // ==============================================
    // 🧾 OFFICIAL IN-APP RECEIPT MODAL & PDF ENGINE
    // ==============================================
    let currentReceiptModalType = 'order';
    let currentReceiptModalId = null;

    function closeReceiptPreviewModal() {
      haptic('light');
      const modal = document.getElementById('modal-receipt-preview');
      if (modal) modal.style.display = 'none';
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'receipt_modal') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function downloadCurrentModalPdf() {
      if (currentReceiptModalType === 'recharge' && currentReceiptModalId) {
        downloadRechargeReceipt(currentReceiptModalId);
      } else if (currentReceiptModalId) {
        downloadOrderReceipt(currentReceiptModalId);
      }
    }

    function showOrderReceiptModal(orderId) {
      haptic('pop');
      currentReceiptModalType = 'order';
      currentReceiptModalId = Number(orderId);
      const order = (userData?.orders || []).find(o => Number(o.id) === currentReceiptModalId);
      if (!order) return;

      const isAr = (currentAppLanguage === 'ar');
      const titleEl = document.getElementById('receipt-modal-title');
      if (titleEl) titleEl.innerText = isAr ? 'إيصال الشراء الرسمي' : 'Official Purchase Receipt';
      const btnDl = document.getElementById('btn-download-pdf-label');
      if (btnDl) btnDl.innerText = isAr ? '⬇️ تنزيل ملف PDF' : '⬇️ Download PDF Receipt';
      const btnCl = document.getElementById('btn-close-receipt-modal-label');
      if (btnCl) btnCl.innerText = isAr ? 'إغلاق' : 'Close';

      const body = document.getElementById('receipt-modal-body');
      if (body) {
        body.innerHTML = `
          <div class="receipt-paper-box">
            <div class="receipt-paper-header">
              <div class="receipt-paper-brand">GH STORE</div>
              <div class="receipt-paper-sub">${isAr ? 'إيصال شراء وضمان معتمد' : 'OFFICIAL PURCHASE INVOICE & RECEIPT'}</div>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'رقم الإيصال:' : 'Invoice #:'}</span>
              <span class="receipt-row-val">GH-${order.id}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'تاريخ الشراء:' : 'Issue Date:'}</span>
              <span class="receipt-row-val">${order.created_at || 'Confirmed'}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'الخدمة / المنتج:' : 'Product:'}</span>
              <span class="receipt-row-val" style="font-family:inherit; font-size:12px;">${order.products || 'Digital License'}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'حالة الطلب:' : 'Status:'}</span>
              <span class="receipt-row-val" style="color:var(--success); font-family:inherit;">${order.status === 'completed' ? (isAr ? 'مكتمل ومفعل' : 'Completed') : order.status}</span>
            </div>

            <div class="receipt-amount-banner">
              <div style="font-size:11px; color:var(--hint); margin-bottom:2px;">${isAr ? 'المبلغ الإجمالي المدفوع' : 'Total Amount Paid'}</div>
              <div class="receipt-amount-num">$${Number(order.total || 0).toFixed(2)} USD</div>
            </div>

            <div style="margin: 10px 0;">
              <div style="font-size:11px; color:var(--hint); font-weight:700; margin-bottom:6px;">${isAr ? 'البيانات والمفاتيح المسلمة:' : 'Delivered Credentials & Keys:'}</div>
              ${renderStructuredCredentials(order.goods)}
            </div>

            <div class="receipt-audit-badge">
              <span>🛡️</span>
              <span>${isAr ? `ضمان كامل واستبدال فوري لمدة ${order.warranty_days || 30} يوم.` : `Full ${order.warranty_days || 30}-day replacement warranty included.`}</span>
            </div>
          </div>
        `;
      }

      const modal = document.getElementById('modal-receipt-preview');
      if (modal) modal.style.display = 'flex';
      pushNav('receipt_modal', closeReceiptPreviewModal);
    }

    function showRechargeReceiptModal(recharge) {
      haptic('pop');
      currentReceiptModalType = 'recharge';
      currentReceiptModalId = recharge.id || recharge.invoice_id;

      const isAr = (currentAppLanguage === 'ar');
      const titleEl = document.getElementById('receipt-modal-title');
      if (titleEl) titleEl.innerText = isAr ? 'إيصال شحن الرصيد المعتمد' : 'Official Top-Up Receipt';
      const btnDl = document.getElementById('btn-download-pdf-label');
      if (btnDl) btnDl.innerText = isAr ? '⬇️ تنزيل إيصال PDF' : '⬇️ Download PDF Receipt';
      const btnCl = document.getElementById('btn-close-receipt-modal-label');
      if (btnCl) btnCl.innerText = isAr ? 'إغلاق' : 'Close';

      const localPart = (recharge.currency === 'SYP' && recharge.invoice_amount)
        ? `<div style="font-size:12px; color:var(--text); font-weight:700; margin-top:2px;">≈ ${Number(recharge.invoice_amount).toLocaleString()} ل.س</div>`
        : '';

      const isManual = Boolean(recharge.approved_by_admin);
      const auditText = isManual
        ? (isAr ? 'تمت مراجعة العملية والاعتماد والإيداع اليدوي من قبل إدارة المتجر.' : 'Transaction reviewed & manually approved by Store Administration.')
        : (isAr ? 'تم التحقق والإيداع التلقائي الفوري عبر بوابة الدفع الإلكترونية.' : 'Verified & credited automatically via Payment Gateway confirmation.');

      const body = document.getElementById('receipt-modal-body');
      if (body) {
        body.innerHTML = `
          <div class="receipt-paper-box">
            <div class="receipt-paper-header">
              <div class="receipt-paper-brand">GH STORE</div>
              <div class="receipt-paper-sub" style="color:var(--success);">${isAr ? 'إشعار شحن محفظة معتمد' : 'OFFICIAL WALLET DEPOSIT CONFIRMATION'}</div>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'رقم الإيصال:' : 'Receipt #:'}</span>
              <span class="receipt-row-val">GH-TOPUP-${String(recharge.id || recharge.invoice_id).replace(/^SAM-|^STR-|^CRY-/, '')}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'تاريخ العملية:' : 'Deposit Date:'}</span>
              <span class="receipt-row-val">${recharge.created_at || 'Confirmed'}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'وسيلة الشحن:' : 'Payment Method:'}</span>
              <span class="receipt-row-val" style="font-family:inherit;">${recharge.methodTitle || recharge.provider || 'Wallet Top-up'}</span>
            </div>
            <div class="receipt-row">
              <span class="receipt-row-label">${isAr ? 'مرجع الفاتورة:' : 'Reference ID:'}</span>
              <span class="receipt-row-val" style="font-size:11px;">${recharge.invoice_id || 'Direct'}</span>
            </div>

            <div class="receipt-amount-banner" style="background:rgba(16,185,129,0.08); border-color:rgba(16,185,129,0.3);">
              <div style="font-size:11px; color:var(--hint); margin-bottom:2px;">${isAr ? 'المبلغ المودع في الرصيد' : 'Amount Credited to Wallet'}</div>
              <div class="receipt-amount-num recharge-green">+$${Number(recharge.amount || 0).toFixed(2)} USD</div>
              ${localPart}
            </div>

            <div class="receipt-audit-badge">
              <span>${isManual ? '🛡️' : '⚡'}</span>
              <span>${auditText}</span>
            </div>

            <div style="margin-top:12px; font-size:11px; color:var(--hint); text-align:center;">
              ${isAr ? 'الرصيد متاح حالياً وجاهز للاستخدام الفوري في جميع مشتريات المتجر.' : 'Funds are secured and ready for immediate use across all store services.'}
            </div>
          </div>
        `;
      }

      const modal = document.getElementById('modal-receipt-preview');
      if (modal) modal.style.display = 'flex';
      pushNav('receipt_modal', closeReceiptPreviewModal);
    }

    function downloadOrderReceipt(orderId) {
      haptic('medium');
      const isAr = (currentAppLanguage === 'ar');
      const pdfUrl = `${window.location.origin}/api/orders/${orderId}/receipt.pdf?tg_id=${userId}`;
      const fileName = `GHStore_Order_${orderId}.pdf`;

      if (tg?.downloadFile) {
        tg.downloadFile({ url: pdfUrl, file_name: fileName }, (accepted) => {
          if (accepted) {
            haptic('success');
            showToast(isAr ? 'جاري تنزيل ملف PDF... 🧾' : 'Downloading PDF receipt... 🧾');
          }
        });
      } else {
        const a = document.createElement('a');
        a.href = pdfUrl;
        a.download = fileName;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast(isAr ? 'تم بدء تنزيل ملف PDF! 🧾' : 'PDF download started! 🧾');
      }
    }

    function downloadRechargeReceipt(rechargeId) {
      haptic('medium');
      const isAr = (currentAppLanguage === 'ar');
      const cleanId = String(rechargeId).replace(/^rec_/, '').replace(/#/g, '');
      const pdfUrl = `${window.location.origin}/api/recharges/${cleanId}/receipt.pdf?tg_id=${userId}`;
      const fileName = `GHStore_Recharge_${cleanId}.pdf`;

      if (tg?.downloadFile) {
        tg.downloadFile({ url: pdfUrl, file_name: fileName }, (accepted) => {
          if (accepted) {
            haptic('success');
            showToast(isAr ? 'جاري تنزيل ملف PDF... 🧾' : 'Downloading PDF receipt... 🧾');
          }
        });
      } else {
        const a = document.createElement('a');
        a.href = pdfUrl;
        a.download = fileName;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast(isAr ? 'تم بدء تنزيل ملف PDF! 🧾' : 'PDF download started! 🧾');
      }
    }

    // In-App Support Ticket Modal Handlers
    function openSupportTicketModal(orderId = null) {
      haptic('light');
      const ordInput = document.getElementById('ticket-order-id');
      if (ordInput) ordInput.value = orderId || '';
      const msgInput = document.getElementById('ticket-message-input');
      if (msgInput) msgInput.value = '';
      const modal = document.getElementById('customer-support-ticket-modal');
      if (modal) modal.style.display = 'flex';
      pushNav('support_ticket', closeSupportTicketModal);
    }

    function closeSupportTicketModal() {
      haptic('light');
      const modal = document.getElementById('customer-support-ticket-modal');
      if (modal) modal.style.display = 'none';
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'support_ticket') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    async function submitCustomerSupportTicket() {
      if (!userId) return;
      haptic('medium');
      const orderId = document.getElementById('ticket-order-id')?.value || null;
      const subject = document.getElementById('ticket-subject-select')?.value || 'General Inquiry';
      const msg = (document.getElementById('ticket-message-input')?.value || '').trim();
      if (!msg || msg.length < 3) {
        showToast(currentAppLanguage === 'ar' ? 'يرجى كتابة نص الرسالة' : 'Please enter message text');
        return;
      }
      const btn = document.getElementById('btn-submit-support-ticket');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>${currentAppLanguage === 'ar' ? 'جاري الإرسال...' : 'Sending...'}</span>`;
      }
      try {
        const res = await fetch('/api/support/ticket', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, order_id: orderId, subject: subject, message: msg })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;
        if (d.status === 'success') {
          closeSupportTicketModal();
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? `✅ تم إرسال تذكرتك بنجاح (#${d.ticket_id})!` : `Ticket #${d.ticket_id} submitted!`);
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل إرسال التذكرة' : 'Ticket failed'));
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال' : 'Connection error');
      }
    }

    // Dynamic Trending Searches & Real-Time Sync
    async function initTrendingSearches() {
      try {
        const res = await fetch('/api/search/trending');
        const d = await res.json();
        if (d.trending && d.trending.length) {
          const bar = document.getElementById('trending-searches-bar');
          if (bar) {
            const label = currentAppLanguage === 'ar' ? '🔥 الأكثر بحثاً:' : '🔥 Trending:';
            bar.innerHTML = `<span class="trending-label">${label}</span>` +
              d.trending.map(t => `<span class="trending-chip" onclick="applySearchQuery('${t}')">⚡ ${t}</span>`).join('');
          }
        }
      } catch (e) {}
    }

    // Live Flash Sale Countdown Timer
    let flashSaleTimerInterval = null;
    function initFlashSaleTimer(flash) {
      if (!flash || !flash.enabled || !flash.end_timestamp) {
        const b = document.getElementById('flash-sale-banner');
        if (b) b.style.display = 'none';
        return;
      }
      const banner = document.getElementById('flash-sale-banner');
      const badge = document.getElementById('flash-sale-badge');
      const timer = document.getElementById('flash-countdown-timer');
      if (!banner || !timer) return;

      const title = (currentAppLanguage === 'ar') ? (flash.title_ar || '🔥 عروض فلاش محدودة') : (flash.title_en || '🔥 Limited Flash Sale');
      if (badge) badge.innerText = `${title} (-${flash.percent}%)`;
      banner.style.display = 'flex';

      clearInterval(flashSaleTimerInterval);
      const update = () => {
        const now = Math.floor(Date.now() / 1000);
        const remaining = Math.max(0, flash.end_timestamp - now);
        if (remaining <= 0) {
          banner.style.display = 'none';
          clearInterval(flashSaleTimerInterval);
          return;
        }
        const hrs = String(Math.floor(remaining / 3600)).padStart(2, '0');
        const mins = String(Math.floor((remaining % 3600) / 60)).padStart(2, '0');
        const secs = String(remaining % 60).padStart(2, '0');
        timer.innerText = `${hrs}:${mins}:${secs}`;
      };
      update();
      flashSaleTimerInterval = setInterval(update, 1000);
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
      const botUser = userData?.bot_username || 'GHStoreBot';
      const shareUrl = `https://t.me/${botUser}/app?startapp=prod_${selectedProduct.id}_ref_${userId}`;
      const shareText = (currentAppLanguage === 'ar')
        ? `🔥 تسوق ${selectedProduct.clean_name || selectedProduct.name} الآن بأفضل سعر على GH Store!`
        : `🔥 Shop ${selectedProduct.clean_name || selectedProduct.name} now at best prices on GH Store!`;

      // Bot API 8.0 Native Prepared Inline Message Share (direct chat picker)
      if (tg?.shareMessage && tg.isVersionAtLeast && tg.isVersionAtLeast('8.0') && userId) {
        fetch('/api/share/prepare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_id: selectedProduct.id, tg_id: userId })
        })
        .then(r => r.json())
        .then(d => {
          if (d.status === 'ok' && d.prepared_message_id) {
            tg.shareMessage(d.prepared_message_id, (sent) => {
              if (sent) {
                haptic('success');
                showToast(currentAppLanguage === 'ar' ? 'تمت المشاركة بنجاح! 🚀' : 'Shared successfully! 🚀');
              }
            });
          } else {
            fallbackStoryOrLinkShare(shareUrl, shareText);
          }
        })
        .catch(() => fallbackStoryOrLinkShare(shareUrl, shareText));
        return;
      }

      fallbackStoryOrLinkShare(shareUrl, shareText);
    }

    function fallbackStoryOrLinkShare(shareUrl, shareText) {
      if (tg?.shareToStory) {
        try {
          tg.shareToStory({
            media_url: selectedProduct.image_url || 'https://bot.gh-store.me/static/banner.png',
            text: shareText,
            widget_link: { url: shareUrl, name: "GH Store" }
          });
          return;
        } catch (e) {}
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
        methodName = "USDT (BEP-20)";
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
          if (tg?.openInvoice) {
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
          } else {
            window.open(d.invoice_link, '_blank');
          }
        } else if ((d.type === 'url' || d.type === 'crypto' || d.status === 'ok') && (d.url || d.address)) {
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
        if (nameEl) nameEl.innerText = (currentAppLanguage === 'ar') ? 'شام كاش' : 'Sham Cash';
        if (subEl) subEl.innerText = (currentAppLanguage === 'ar') ? 'دفع مباشر وفوري عبر بنك شام كاش' : 'Direct payment via Sham Cash';
      } else if (prov === 'syriatelcash') {
        if (iconBox) iconBox.innerHTML = '<img src="https://www.syriatel.sy/assets/img/logo.png" class="method-brand-img" alt="Syriatel Cash">';
        if (nameEl) nameEl.innerText = (currentAppLanguage === 'ar') ? 'سيرياتيل كاش' : 'Syriatel Cash';
        if (subEl) subEl.innerText = (currentAppLanguage === 'ar') ? 'دفع بالليرة السورية (SYP)' : 'Direct payment in SYP';
      } else {
        if (iconBox) iconBox.innerHTML = '<div style="width:34px; height:34px; border-radius:50%; background:#26a17b; display:flex; align-items:center; justify-content:center; color:white; font-weight:800; font-size:16px; flex-shrink:0;">₮</div>';
        if (nameEl) nameEl.innerText = 'USDT (BEP-20)';
        if (subEl) subEl.innerText = (currentAppLanguage === 'ar') ? 'شبكة بينانس سمارت تشين (BEP-20)' : 'Binance Smart Chain (BEP-20)';
      }

      // 4. Populate Amounts
      const usdEl = document.getElementById('invoice-amount-usd');
      const localEl = document.getElementById('invoice-amount-local');
      const amt = Number(invoiceData.amount || selectedRechargeAmount || 10);
      if (usdEl) usdEl.innerText = `$${amt.toFixed(2)} USD`;

      if (invoiceData.invoice_amount && invoiceData.currency === 'SYP') {
        if (localEl) {
          localEl.innerText = `≈ ${Number(invoiceData.invoice_amount).toLocaleString()} ${currentAppLanguage === 'ar' ? 'ل.س' : 'SYP'}`;
          localEl.style.display = 'block';
        }
      } else {
        if (localEl) localEl.style.display = 'none';
      }

      // Populate Crypto BEP-20 Address Box if present
      const bep20Box = document.getElementById('invoice-crypto-bep20-box');
      const addrEl = document.getElementById('invoice-crypto-address');
      if (invoiceData.address) {
        if (addrEl) addrEl.innerText = invoiceData.address;
        if (bep20Box) bep20Box.style.display = 'block';
      } else {
        if (bep20Box) bep20Box.style.display = 'none';
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
    function copyCryptoAddress() {
      haptic('light');
      const addrEl = document.getElementById('invoice-crypto-address');
      const addr = addrEl ? addrEl.innerText.trim() : '';
      if (!addr) return;
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(addr);
      }
      showToast((currentAppLanguage === 'ar') ? '✅ تم نسخ عنوان المحفظة (BEP-20)!' : '✅ BEP-20 Wallet Address Copied!');
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

    function scanVoucherQr() {
      haptic('light');
      if (tg?.showScanQrPopup) {
        tg.showScanQrPopup({ text: currentAppLanguage === 'ar' ? 'امسح رمز الاستجابة السريعة (QR) لكوبون الهدية' : 'Scan digital voucher QR code' }, (qrText) => {
          if (!qrText) return false;
          const cleaned = qrText.trim().toUpperCase();
          const inp = document.getElementById('voucher-code-input');
          if (inp) inp.value = cleaned;
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? 'تم مسح الكود بنجاح!' : 'QR Code scanned!');
          return true;
        });
      } else {
        showToast(currentAppLanguage === 'ar' ? 'مسح QR غير مدعوم في هذا الإصدار من تيليجرام' : 'QR Scanner not supported on this Telegram client');
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
      const isAr = (currentAppLanguage === 'ar');
      if (container && !cachedAdminUsersList.length) {
        container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--hint);">${isAr ? 'جاري البحث في قاعدة البيانات...' : 'Searching database...'}</div>`;
      }
      try {
        const res = await fetch(`/api/admin/users?tg_id=${userId}&query=${encodeURIComponent(q)}`);
        const d = await res.json();
        cachedAdminUsersList = d.users || [];
        renderAdminUsersCards();
      } catch (e) {
        if (container) container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--danger);">${isAr ? 'خطأ في جلب المستخدمين.' : 'Error fetching users.'}</div>`;
      }
    }

    function renderAdminUsersCards() {
      const container = document.getElementById('admin-users-results-list');
      if (!container) return;
      const isAr = (currentAppLanguage === 'ar');

      let filtered = [...cachedAdminUsersList];
      if (activeAdminUserFilter === 'balance') {
        filtered = filtered.filter(u => u.balance > 0);
      } else if (activeAdminUserFilter === 'vip') {
        filtered = filtered.filter(u => (u.vip_discount > 0 || u.custom_discount_pct > 0));
      } else if (activeAdminUserFilter === 'banned') {
        filtered = filtered.filter(u => u.is_banned);
      }

      if (!filtered.length) {
        container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--hint);">${isAr ? 'لا يوجد مستخدمين مطابقين لهذا الفلتر.' : 'No users match this filter.'}</div>`;
        return;
      }

      container.innerHTML = filtered.map(u => {
        const initial = (u.username || 'U')[0].toUpperCase();
        const vipLabel = (u.custom_discount_pct !== null && u.custom_discount_pct !== undefined)
          ? `${u.custom_discount_pct}% ${isAr ? 'مخصص' : 'Custom'}`
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
                    <button class="btn-copy-mini" style="font-size: 9px; padding: 1px 6px;" onclick="copyCredText('${u.telegram_id}')">${isAr ? 'نسخ ID' : 'Copy ID'}</button>
                    ${u.registered_at ? `<span style="font-size: 10px; color: var(--hint);">· ${u.registered_at}</span>` : ''}
                  </div>
                </div>
              </div>

              <!-- ONLY SHOW BADGE IF BANNED (NO ACTIVE BADGE SPAM) -->
              ${u.is_banned ? `
                <span class="pill-badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; font-size: 11px; flex-shrink: 0;">
                  🚫 ${isAr ? 'محظور' : 'Banned'}
                </span>
              ` : ''}
            </div>

            <!-- Metrics Row (Balance, Spent, VIP Tier) -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 8px 10px; margin-bottom: 12px; text-align: center;">
              <div>
                <div style="font-size: 10px; color: var(--hint);">${isAr ? 'الرصيد المتاح' : 'Available Balance'}</div>
                <div style="font-size: 14px; font-weight: 800; color: ${u.balance > 0 ? 'var(--accent)' : 'var(--text)'};">
                  $${u.balance.toFixed(2)}
                </div>
              </div>
              <div>
                <div style="font-size: 10px; color: var(--hint);">${isAr ? 'المشتريات' : 'Total Purchases'}</div>
                <div style="font-size: 14px; font-weight: 800; color: var(--text);">
                  $${u.total_spent.toFixed(2)}
                </div>
              </div>
              <div>
                <div style="font-size: 10px; color: var(--hint);">${isAr ? 'الرتبة / الخصم' : 'VIP Tier / Discount'}</div>
                <div style="font-size: 12px; font-weight: 700; color: ${u.vip_discount > 0 ? 'var(--warning)' : 'var(--hint)'}; margin-top: 2px;">
                  ${vipLabel}
                </div>
              </div>
            </div>

            <!-- Quick Options & Settings UX Grid (High Usability) -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 6px;">
              <button class="btn-action-primary" onclick="openAdminBalanceModal(${u.telegram_id}, '${u.username || ''}', ${u.balance})" style="height: 38px; font-size: 12px;">
                💰 ${isAr ? 'تعديل الرصيد' : 'Adjust Balance'}
              </button>
              <button class="btn-action-secondary" onclick="openAdminDiscountModal(${u.telegram_id}, '${u.username || ''}', ${u.custom_discount_pct !== null && u.custom_discount_pct !== undefined ? u.custom_discount_pct : u.vip_discount})" style="height: 38px; font-size: 12px;">
                🏷️ ${isAr ? 'تخصيص خصم %' : 'Set Discount %'}
              </button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;">
              <button class="btn-action-secondary" onclick="openAdminMessageModal(${u.telegram_id}, '${u.username || ''}')" style="height: 36px; font-size: 11px;">
                💬 ${isAr ? 'مراسلة المستخدم' : 'Message User'}
              </button>
              <button class="btn-action-secondary" style="height: 36px; font-size: 11px; color: ${u.is_banned ? '#10b981' : '#ef4444'};" onclick="submitToggleBan(${u.telegram_id})">
                ${u.is_banned ? (isAr ? '✅ فك الحظر' : '✅ Unban') : (isAr ? '🚫 حظر الحساب' : '🚫 Ban Account')}
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
        submitBtn.innerText = act === 'add' ? (currentAppLanguage === 'ar' ? 'تأكيد إضافة الرصيد (+)' : 'Confirm Add Balance (+)') : (currentAppLanguage === 'ar' ? 'تأكيد خصم الرصيد (-)' : 'Confirm Deduct Balance (-)');
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
          lastBalanceAuditId = d.audit_id;
          const msg = (currentAppLanguage === 'ar')
            ? `تم تعديل الرصيد بنجاح! الرصيد الجديد: $${d.new_balance.toFixed(2)}`
            : `Balance updated successfully! New balance: $${d.new_balance.toFixed(2)}`;
          showToast(msg);
          closeAdminBalanceModal();
          executeAdminUserSearch();
          loadUserData();
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل تعديل الرصيد' : 'Failed to update balance'));
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال بالخادم' : 'Server connection error');
      }
    }

    let lastBalanceAuditId = null;
    async function adminRollbackLastBalanceAction() {
      if (!lastBalanceAuditId || !userId) return;
      haptic('medium');
      showToast(currentAppLanguage === 'ar' ? 'جاري التراجع عن العملية...' : 'Rolling back adjustment...');
      try {
        const res = await fetch('/api/admin/audit/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, audit_id: lastBalanceAuditId })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? `✅ تم التراجع عن العملية! الرصيد: $${d.new_balance.toFixed(2)}` : `✅ Rolled back! Balance: $${d.new_balance.toFixed(2)}`);
          lastBalanceAuditId = null;
          executeAdminUserSearch();
          loadUserData();
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل التراجع' : 'Rollback failed'));
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال' : 'Connection error');
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
      const lang18 = I18N[currentAppLanguage] || I18N.ar;
      container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--hint);">...</div>';
      try {
        const res = await fetch(`/api/admin/orders?tg_id=${userId}&status=${encodeURIComponent(status)}`);
        const d = await res.json();
        if (!d.orders || !d.orders.length) {
          container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--hint);">${lang18.no_matching_orders}</div>`;
          return;
        }
        container.innerHTML = d.orders.map(o => {
          const profit = (o.gross_profit ?? o.margin ?? 0);
          const profitColor = profit < 0 ? 'var(--danger)' : 'var(--success)';
          const orderWord = currentAppLanguage === 'ar' ? 'طلب' : 'Order';
          return `
          <div style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:14px;">${orderWord} #${o.id} · ${o.username || 'tg:' + o.telegram_id}</strong>
              <span class="pill-badge" style="background:${o.status === 'completed' ? 'rgba(16,185,129,0.2); color:#10b981' : o.status === 'refunded' ? 'rgba(239,68,68,0.2); color:#ef4444' : 'rgba(245,158,11,0.2); color:#f59e0b'}; font-size:10px;">
                ${o.status}
              </span>
            </div>
            <div style="font-size:13px; font-weight:700; margin:4px 0;">${o.products}</div>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--hint);">
              <span>${lang18.amount_label}: <strong style="color:var(--text);">$${o.total_sell.toFixed(2)}</strong></span>
              <span>${lang18.cost_label}: $${o.cost_usd.toFixed(2)}</span>
              <span>${lang18.profit_label}: <strong style="color:${profitColor};">$${profit.toFixed(2)}</strong></span>
            </div>
            ${o.goods && o.goods.length ? `
              <div style="background:var(--input-bg); border-radius:6px; padding:6px; margin-top:6px; font-family:monospace; font-size:11px; word-break:break-all;">
                ${o.goods.slice(0, 2).join('<br>')}
              </div>
            ` : ''}
            <div style="display:flex; gap:6px; margin-top:8px;">
              ${o.status !== 'completed' ? `<button class="admin-edit-badge-btn" onclick="submitAdminOrderStatus(${o.id}, 'completed')">${lang18.confirm_delivery}</button>` : ''}
              ${o.status !== 'refunded' ? `<button class="admin-edit-badge-btn" style="color:#ef4444;" onclick="submitAdminOrderStatus(${o.id}, 'refunded')">${lang18.refund_to_customer}</button>` : ''}
            </div>
          </div>
        `;
        }).join('');
      } catch (e) {
        container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--danger);">فشل جلب الطلبات.</div>';
      }
    }

    // Native refund confirmation (window.confirm is blocked in Telegram WebViews)
    function confirmAdminRefund(callback) {
      const msg = (I18N[currentAppLanguage] || I18N.ar).refund_confirm_msg;
      if (tg?.showConfirm) {
        try {
          tg.showConfirm(msg, (ok) => { if (ok) callback(); });
          return;
        } catch (e) {}
      }
      if (tg?.showPopup) {
        try {
          tg.showPopup({ message: msg, buttons: [{ id: 'ok', type: 'destructive', text: 'OK' }, { id: 'cancel', type: 'cancel' }] }, (btnId) => { if (btnId === 'ok') callback(); });
          return;
        } catch (e) {}
      }
      callback();
    }

    async function submitAdminOrderStatus(orderId, newStatus) {
      const lang18 = I18N[currentAppLanguage] || I18N.ar;
      const run = async () => {
        try {
          const res = await fetch('/api/admin/orders/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_tg_id: userId, order_id: orderId, new_status: newStatus })
          });
          const d = await res.json();
          if (d.status === 'ok') {
            showToast(newStatus === 'refunded' ? lang18.refund_done : lang18.order_updated);
            loadAdminOrders('all');
          }
        } catch (e) {
          showToast(currentAppLanguage === 'ar' ? 'فشل تحديث الطلب' : 'Failed to update order');
        }
      };
      if (newStatus === 'refunded') confirmAdminRefund(run);
      else run();
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
      const isAr = (currentAppLanguage === 'ar');
      container.innerHTML = `<div style="text-align:center; padding:10px; color:var(--hint);">${isAr ? 'تحميل الكوبونات...' : 'Loading coupons...'}</div>`;
      try {
        const res = await fetch(`/api/admin/coupons?tg_id=${userId}`);
        const d = await res.json();
        if (!d.coupons || !d.coupons.length) {
          container.innerHTML = `<div style="text-align:center; padding:10px; color:var(--hint);">${isAr ? 'لا توجد كوبونات مسجلة.' : 'No registered coupons.'}</div>`;
          return;
        }
        container.innerHTML = d.coupons.map(c => `
          <div style="background:var(--card); border:1px solid var(--border); border-radius:8px; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="font-family:monospace; font-size:13px; color:var(--accent);">${c.code}</strong>
              <div style="font-size:11px; color:var(--hint);">
                ${c.type === 'percent' ? c.value + '%' : '$' + c.value} · ${isAr ? 'الاستخدام:' : 'Usage:'} ${c.usage_count}/${c.usage_limit || '∞'}
              </div>
            </div>
            <button class="admin-edit-badge-btn" style="color:${c.is_active ? '#ef4444' : '#10b981'};" onclick="submitToggleCoupon(${c.id})">
              ${c.is_active ? (isAr ? 'تعطيل' : 'Disable') : (isAr ? 'تفعيل' : 'Enable')}
            </button>
          </div>
        `).join('');
      } catch (e) {
        container.innerHTML = `<div style="text-align:center; color:var(--danger);">${isAr ? 'خطأ في جلب الكوبونات.' : 'Error fetching coupons.'}</div>`;
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

    async function submitAdminUpdateTrendingTags() {
      const val = (document.getElementById('admin-trending-tags-input')?.value || '').trim();
      haptic('light');
      try {
        const res = await fetch('/api/admin/trending-tags/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, tags: val })
        });
        const d = await res.json();
        if (d.status === 'ok') {
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? 'تم حفظ العلامات الأكثر بحثاً بنجاح!' : 'Trending search tags saved!');
          loadTrendingSearches();
        } else {
          showToast(currentAppLanguage === 'ar' ? 'فشل حفظ العلامات' : 'Failed to save tags');
        }
      } catch (e) {
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال بالخادم' : 'Server connection error');
      }
    }

    async function loadTrendingSearches() {
      const bar = document.getElementById('trending-searches-bar');
      const container = document.getElementById('trending-chips-container');
      if (!bar || !container) return;
      try {
        const res = await fetch('/api/search/trending');
        const d = await res.json();
        const tags = d.trending || [];
        if (tags.length > 0) {
          container.innerHTML = tags.map(tag => `
            <span class="trending-chip" onclick="applySearchQuery('${tag.replace(/'/g, "\\\\'")}')">⚡ ${tag}</span>
          `).join('');
          bar.style.display = 'flex';
        } else {
          bar.style.display = 'none';
        }
      } catch (e) {
        bar.style.display = 'none';
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
    // Admin Manual Externally Paid Sale Handlers
    function openAdminGiftModal() {
      if (!selectedProduct) return;
      haptic('light');
      const titleEl = document.getElementById('admin-gift-prod-title');
      if (titleEl) titleEl.innerText = selectedProduct.clean_name || selectedProduct.name;
      const qtyInput = document.getElementById('gift-qty');
      if (qtyInput) qtyInput.value = '1';
      const paidCheck = document.getElementById('manual-sale-paid-check');
      if (paidCheck) paidCheck.checked = false;
      selectGiftTargetType('self');
      updateManualSaleTotal();
      const modal = document.getElementById('admin-gift-modal');
      if (modal) modal.classList.add('active');
    }

    function closeAdminGiftModal() {
      haptic('light');
      const modal = document.getElementById('admin-gift-modal');
      if (modal) modal.classList.remove('active');
    }

    let currentGiftTargetType = 'self';
    function selectGiftTargetType(type) {
      haptic('light');
      currentGiftTargetType = type;
      const btnSelf = document.getElementById('gift-type-self');
      const btnUser = document.getElementById('gift-type-user');
      if (btnSelf) btnSelf.classList.toggle('active', type === 'self');
      if (btnUser) btnUser.classList.toggle('active', type === 'user');
      const userRow = document.getElementById('gift-user-row');
      if (userRow) userRow.style.display = (type === 'user') ? 'block' : 'none';
    }

    function manualSaleBusyLabel() {
      const d = I18N[currentAppLanguage] || I18N.ar;
      return `<span>${d.processing_sale}</span>`;
    }

    async function submitAdminManualSale() {
      if (!selectedProduct) return;
      haptic('medium');
      const d18 = I18N[currentAppLanguage] || I18N.ar;
      const btn = document.getElementById('btn-submit-free-order');
      const confirmLabel = document.getElementById('admin-gift-confirm-label');
      const prevLabel = confirmLabel ? confirmLabel.innerText : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = manualSaleBusyLabel();
      }
      const restoreBtn = () => {
        if (btn) {
          btn.disabled = false;
          if (confirmLabel) confirmLabel.innerText = prevLabel || d18.confirm_sale;
          else btn.innerHTML = `<span>${prevLabel || d18.confirm_sale}</span>`;
        }
      };

      const qty = Math.max(1, Math.min(10, parseInt(document.getElementById('gift-qty')?.value || '1', 10) || 1));
      let targetTgId = userId;
      if (currentGiftTargetType === 'user') {
        const rawTarget = document.getElementById('gift-target-id')?.value?.trim();
        if (!rawTarget) {
          showToast(currentAppLanguage === 'ar' ? 'يرجى إدخال معرف تيليجرام للعميل' : 'Enter the customer Telegram ID');
          restoreBtn();
          return;
        }
        targetTgId = parseInt(rawTarget, 10);
      }
      if (!document.getElementById('manual-sale-paid-check')?.checked) {
        showToast(d18.external_paid_label);
        restoreBtn();
        return;
      }

      try {
        const res = await fetch('/api/admin/manual-sale', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            product_id: selectedProduct.id,
            quantity: qty,
            target_tg_id: targetTgId,
            payment_confirmed: true
          })
        });
        const d = await res.json();
        restoreBtn();

        if (d.status === 'success') {
          closeAdminGiftModal();
          fireConfetti();
          haptic('success');
          showToast(currentGiftTargetType === 'self'
            ? `✅ ${d18.sale_success_self} ($${(d.total_sell || 0).toFixed(2)} · ${d18.external_paid_done})`
            : `✅ #${d.order_id} · $${(d.total_sell || 0).toFixed(2)} · ${d18.external_paid_done} (${targetTgId})`);

          if (currentGiftTargetType === 'self' && d.goods && d.goods.length > 0) {
            document.getElementById('success-meta-sub').innerText = `#${d.order_id} · $${(d.total_sell || 0).toFixed(2)} · ${d18.external_paid_done}`;
            const keysBox = document.getElementById('success-delivered-keys');
            if (keysBox) keysBox.innerHTML = renderStructuredCredentials(d.goods);
            document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
            const successView = document.getElementById('view-order-success');
            if (successView) successView.classList.add('active');
          }
          loadUserData();
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل تنفيذ البيع' : 'Sale failed'));
        }
      } catch (e) {
        restoreBtn();
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال بالخادم أثناء البيع' : 'Connection error during sale');
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
      const isAr = (currentAppLanguage === 'ar');
      if (container) container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--hint);">${isAr ? 'جاري فحص العمليات والطلبات العالقة...' : 'Checking pending & stuck operations...'}</div>`;
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
          if (container) container.innerHTML = `<div style="text-align:center; padding:40px 16px; color:var(--success); font-weight:700;">${isAr ? '✅ ممتاز! لا توجد أي طلبات أو مبالغ معلقة حالياً.' : '✅ Great! No stuck orders or pending funds.'}</div>`;
          return;
        }

        if (container) {
          container.innerHTML = orders.map(o => `
            <div class="inset-card" style="margin-bottom: 12px; padding: 14px; border-color: rgba(245,158,11,0.4);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                  <strong style="font-size: 14px; color: var(--text);">${isAr ? 'طلب' : 'Order'} #${o.id} · ${o.username ? '@' + o.username : 'User ' + o.telegram_id}</strong>
                  <div style="font-size: 11px; color: var(--hint); font-family: monospace; margin-top: 2px;">ID: ${o.telegram_id} · ${o.created_at}</div>
                </div>
                <span class="pill-badge" style="background: rgba(245,158,11,0.2); color: #f59e0b; font-size: 10px;">
                  ${isAr ? '⏳ معلق / قيد التفعيل' : '⏳ Pending / Processing'}
                </span>
              </div>

              <div style="font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 6px;">${o.products}</div>
              <div style="font-size: 14px; color: var(--accent); font-weight: 800; margin-bottom: 12px;">${isAr ? 'المبلغ المعلق:' : 'Pending Amount:'} $${o.total_sell.toFixed(2)} USD</div>

              <div style="display: flex; gap: 8px;">
                <button class="btn-action-primary" onclick="executeAdminRefundStuck(${o.id}, ${o.total_sell})" style="flex: 2; height: 38px; font-size: 12px; background: linear-gradient(135deg, #ef4444, #dc2626);">
                  ${isAr ? `💸 استرداد الرصيد للعميل ($${o.total_sell.toFixed(2)})` : `💸 Refund Customer ($${o.total_sell.toFixed(2)})`}
                </button>
                <button class="btn-action-secondary" onclick="openAdminMessageModal(${o.telegram_id}, '${o.username || ''}')" style="flex: 1; height: 38px; font-size: 12px;">
                  ${isAr ? '💬 مراسلة' : '💬 Message'}
                </button>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        if (container) container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--danger);">${isAr ? 'خطأ في جلب العمليات المعلقة.' : 'Error fetching pending operations.'}</div>`;
      }
    }

    async function executeAdminRefundStuck(orderId, amount) {
      haptic('medium');
      const isAr = (currentAppLanguage === 'ar');
      const msg = isAr ? `هل أنت متأكد من رغبتك في استرداد مبلغ $${amount.toFixed(2)} لحساب العميل فورياً؟` : `Are you sure you want to refund $${amount.toFixed(2)} to customer immediately?`;
      const run = async () => {
        try {
          const res = await fetch('/api/admin/stuck-orders/refund', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_tg_id: userId, order_id: orderId })
          });
          const d = await res.json();
          if (d.status === 'ok') {
            showToast('تم استرداد المبلغ بنجاح!');
            loadAdminStuckOrders();
            loadAdminLiveRadar();
          } else {
            showToast(d.error || 'فشل الاسترداد');
          }
        } catch (e) {
          showToast('خطأ في الاتصال أثناء الاسترداد');
        }
      };

      if (tg?.showConfirm) {
        tg.showConfirm(msg, (ok) => { if (ok) run(); });
      } else if (tg?.showPopup) {
        tg.showPopup({ message: msg, buttons: [{ id: 'ok', type: 'destructive', text: 'استرداد' }, { id: 'cancel', type: 'cancel' }] }, (b) => { if (b === 'ok') run(); });
      } else {
        run();
      }
    }
    async function refreshSupplierBalances(showUserToast = true) {
      if (showUserToast) {
        haptic('light');
        showToast((currentAppLanguage === 'ar') ? 'جاري تحديث أرصدة محافظ الموردين...' : 'Updating supplier balances...');
      }
      try {
        const res = await fetch(`/api/user-data?tg_id=${userId}&refresh_wallets=true`);
        const d = await res.json();
        if (d && d.admin_stats && d.admin_stats.supplier_wallets) {
          const sw = d.admin_stats.supplier_wallets;
          const setText = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
          setText('admin-bal-batstore', `$${Number(sw.batstore_usd || 0).toFixed(2)}`);
          setText('admin-bal-prodseller', `$${Number(sw.prodseller_usd || 0).toFixed(2)}`);
          setText('admin-bal-sam-usd', `$${Number(sw.sam_usd || 0).toFixed(2)} USD`);
          setText('admin-bal-sam-syp', `${Math.round(Number(sw.sam_syp || 0)).toLocaleString()} ل.س`);
          setText('admin-bal-total-suppliers-pill', `إجمالي: $${Number(sw.total_supplier_usd || 0).toFixed(2)}`);
          setText('sup-card-bat-bal', `$${Number(sw.batstore_usd || 0).toFixed(2)} USD`);
          setText('sup-card-prod-bal', `$${Number(sw.prodseller_usd || 0).toFixed(2)} USDT`);
          setText('suppliers-view-total-bal', `$${Number(sw.total_supplier_usd || 0).toFixed(2)} USD`);
          if (showUserToast) showToast((currentAppLanguage === 'ar') ? '✅ تم تحديث الأرصدة بنجاح' : '✅ Balances updated');
        }
      } catch (e) {
        if (showUserToast) showToast((currentAppLanguage === 'ar') ? 'تعذر التحديث' : 'Update failed');
      }
    }


    // Admin Stats Numbers (gross profit before fees; negatives shown honestly)
    function renderAdminStatsLabels() {
      const s = userData?.admin_stats;
      if (!s) return;
      const setText = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
      setText('admin-stat-revenue', `$${(s.total_revenue || 0).toFixed(2)}`);
      setText('admin-stat-cost', `$${(s.total_cost || 0).toFixed(2)}`);
      const profit = (s.gross_profit || 0);
      const profitEl = document.getElementById('admin-stat-profit');
      if (profitEl) {
        profitEl.innerText = `$${profit.toFixed(2)}`;
        profitEl.style.color = profit < 0 ? '#ef4444' : '#10b981';
      }
      setText('admin-stat-balances', `$${(s.total_users_balance || 0).toFixed(2)}`);
      setText('admin-stat-users', String(s.total_users_count || 0));
      setText('admin-stat-orders', String(s.total_orders_count || 0));
    }

    // Manual Sale Live Total (regular list price × quantity, no discounts)
    function updateManualSaleTotal() {
      const qty = Math.max(1, Math.min(10, parseInt(document.getElementById('gift-qty')?.value || '1', 10) || 1));
      const unit = selectedProduct?.price || 0;
      const total = (unit * qty).toFixed(2);
      const el = document.getElementById('admin-gift-total-val');
      if (el) el.innerText = `$${total}`;
    }


    function toggleProdSellerKeyVisibility() {
      const el = document.getElementById('admin-prodseller-key-input');
      if (el) {
        el.type = (el.type === 'password') ? 'text' : 'password';
      }
    }

    async function testProdSellerKeyLive() {
      haptic('light');
      const keyInput = document.getElementById('admin-prodseller-key-input');
      const statusEl = document.getElementById('admin-prodseller-test-status');
      const keyVal = keyInput?.value?.trim() || '';

      if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.style.color = 'var(--hint)';
        statusEl.innerText = (currentAppLanguage === 'ar') ? '⏳ جاري فحص المفتاح والرصيد مع سيرفر ProdSeller...' : 'Testing key with ProdSeller...';
      }

      try {
        const res = await fetch('/api/admin/prodseller/test-balance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, api_key: keyVal })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          if (statusEl) {
            statusEl.style.color = '#ef4444';
            statusEl.innerText = `خطأ: ${d.error || d.message || 'المفتاح غير صالح'}`;
          }
          showToast(d.error || 'فشل الفحص');
          return;
        }

        const bal = Number(d.balance || 0.0).toFixed(2);
        const mem = d.membership || 'bronze';
        const user = d.username ? `@${d.username}` : '';
        if (statusEl) {
          statusEl.style.color = '#10b981';
          statusEl.innerText = `المفتاح فعال. الرصيد: $${bal} · العضوية: ${mem} ${user}`;
        }
        const prodBalEl = document.getElementById('admin-bal-prodseller');
        if (prodBalEl) prodBalEl.innerText = `$${bal}`;
        const prodTierEl = document.getElementById('admin-prodseller-tier');
        if (prodTierEl) prodTierEl.innerText = mem;
        showToast((currentAppLanguage === 'ar') ? `رصيد سيرفر 2: $${bal}` : `ProdSeller balance: $${bal}`);
      } catch (e) {
        if (statusEl) {
          statusEl.style.color = '#ef4444';
          statusEl.innerText = `خطأ في الاتصال: ${e.message}`;
        }
      }
    }

    async function saveSupplierSettings() {
      haptic('medium');
      const keyInput = document.getElementById('admin-prodseller-key-input');
      const strategySelect = document.getElementById('admin-supplier-routing-select');
      const keyVal = keyInput?.value?.trim() || '';
      const strategyVal = strategySelect?.value || 'auto_cheapest';

      showToast((currentAppLanguage === 'ar') ? 'جاري حفظ إعدادات الموردين...' : 'Saving supplier settings...');
      try {
        const res = await fetch('/api/admin/supplier/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            prodseller_api_key: keyVal,
            routing_strategy: strategyVal
          })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          showToast(d.error || 'فشل الحفظ');
          return;
        }
        showToast((currentAppLanguage === 'ar') ? 'تم حفظ إعدادات الموردين بنجاح' : 'Supplier settings saved');
        await refreshSupplierBalances();
      } catch (e) {
        showToast(e.message);
      }
    }

    async function syncAllSupplierCatalogs() {
      haptic('medium');
      const btn = document.getElementById('btn-sync-suppliers');
      if (btn) {
        btn.disabled = true;
        btn.innerText = (currentAppLanguage === 'ar') ? 'جاري المزامنة...' : 'Syncing...';
      }
      showToast((currentAppLanguage === 'ar') ? 'جاري جلب ومزامنة المنتجات من جميع الموردين...' : 'Syncing all supplier catalogs...');
      try {
        const res = await fetch('/api/admin/supplier/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          showToast(d.error || 'فشلت المزامنة');
          return;
        }
        const b = d.result?.batstore || {};
        const p = d.result?.prodseller || {};
        const tot = d.result?.total_products || 0;
        showToast((currentAppLanguage === 'ar')
          ? `تمت المزامنة بنجاح: BatStore (${b.created || 0}+/${b.updated || 0}) · ProdSeller (${p.created || 0}+/${p.updated || 0}) · الإجمالي: ${tot}`
          : `Sync complete: Total ${tot}`);
        await fetchCatalogData();
      } catch (e) {
        showToast(e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerText = (currentAppLanguage === 'ar') ? 'مزامنة كافة الموردين' : 'Sync All Suppliers';
        }
      }
    }
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

        // Re-render active collection or search with live personal discount
        if (activeCatalog) {
          let filtered = allProducts.filter(p => p.category === activeCatalog);
          filtered = filterAndSortProducts(filtered);
          renderProductItems(filtered);
        }
        // Check & Render Admin Control Center in Settings
        // 1. Check & Render Admin Control Center in Settings
        const adminCenterCard = document.getElementById('admin-control-center-card');
        if (adminCenterCard) {
          if (d.is_admin) {
            adminCenterCard.style.display = 'block';
            if (d.admin_stats) {
              renderAdminStatsLabels();
            }
            loadAdminSearchDemands();
              const sypInput = document.getElementById('admin-syp-rate-input');
              if (sypInput && !sypInput.value && d.admin_stats?.syp_usd_rate) sypInput.value = d.admin_stats.syp_usd_rate;

              const refInput = document.getElementById('admin-ref-rate-input');
              if (refInput && !refInput.value && d.admin_stats?.referral_commission_percent) refInput.value = d.admin_stats.referral_commission_percent;

              const logoInput = document.getElementById('admin-store-logo-input');
              if (logoInput && !logoInput.value && d.store_logo_url) logoInput.value = d.store_logo_url;

              const marginInput = document.getElementById('admin-margin-input');
              if (marginInput && !marginInput.value && d.admin_stats?.global_margin_percent) {
                marginInput.value = d.admin_stats.global_margin_percent;
              }

              const starsRateInput = document.getElementById('admin-stars-rate-input');
              if (starsRateInput && !starsRateInput.value && d.admin_stats?.stars_to_usd_rate) {
                starsRateInput.value = d.admin_stats.stars_to_usd_rate;
              }

              const announceInput = document.getElementById('admin-announcement-input');
              if (announceInput && !announceInput.value && (d.store_announcement || d.admin_stats?.store_announcement)) {
                announceInput.value = d.store_announcement || d.admin_stats?.store_announcement;
              }
              const trendInput = document.getElementById('admin-trending-tags-input');
              if (trendInput && !trendInput.value && (d.store_trending_tags || d.admin_stats?.store_trending_tags)) {
                trendInput.value = d.store_trending_tags || d.admin_stats?.store_trending_tags;
              }
              if (d.admin_stats?.supplier_wallets) {
                const sw = d.admin_stats.supplier_wallets;
                const batEl = document.getElementById('admin-bal-batstore');
                const prodEl = document.getElementById('admin-bal-prodseller');
                const samUsdEl = document.getElementById('admin-bal-sam-usd');
                const samSypEl = document.getElementById('admin-bal-sam-syp');
                const totalPill = document.getElementById('admin-bal-total-suppliers-pill');
                if (batEl) batEl.innerText = `$${(sw.batstore_usd || 0.0).toFixed(2)}`;
                if (prodEl) prodEl.innerText = `$${(sw.prodseller_usd || 0.0).toFixed(2)}`;
                if (samUsdEl) samUsdEl.innerText = `$${(sw.sam_usd || 0.0).toFixed(2)} USD`;
                if (samSypEl) samSypEl.innerText = `${Math.round(sw.sam_syp || 0.0).toLocaleString()} ${currentAppLanguage === 'ar' ? 'ل.س' : 'SYP'}`;
                if (totalPill) totalPill.innerText = `${currentAppLanguage === 'ar' ? 'إجمالي:' : 'Total:'} $${(sw.total_supplier_usd || 0.0).toFixed(2)}`;
              }
              const routingSelect = document.getElementById('admin-supplier-routing-select');
              if (routingSelect && d.admin_stats?.supplier_routing_strategy) {
                routingSelect.value = d.admin_stats.supplier_routing_strategy;
              }
              isAutoRefundEnabled = !!d.admin_stats?.autorefund_enabled;
              updateAutoRefundBtnUI();
          } else {
            adminCenterCard.style.display = 'none';
          }
        }

        // 2. Configure Dedicated Admin Wallet View (Supplier Reserves vs Customer Recharge)
        const userWalletSection = document.getElementById('wallet-user-recharge-section');
        const adminWalletSection = document.getElementById('wallet-admin-management-section');
        if (d.is_admin) {
          if (userWalletSection) userWalletSection.style.display = 'none';
          if (adminWalletSection) {
            adminWalletSection.style.display = 'block';
            if (d.admin_stats && d.admin_stats.supplier_wallets) {
              const sw = d.admin_stats.supplier_wallets;
              const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
              setVal('admin-wallet-headline-bal', `$${(sw.batstore_usd || 0.0).toFixed(2)}`);
              setVal('admin-wallet-batstore', `$${(sw.batstore_usd || 0.0).toFixed(2)}`);
              setVal('admin-wallet-sam-usd', `$${(sw.sam_usd || 0.0).toFixed(2)} USD`);
              setVal('admin-wallet-sam-syp', `${Math.round(sw.sam_syp || 0.0).toLocaleString()} ل.س`);
              setVal('admin-wallet-users-total', `$${(d.admin_stats.total_users_balance || 0.0).toFixed(2)}`);
            }
          }
        } else {
          if (userWalletSection) userWalletSection.style.display = 'block';
          if (adminWalletSection) adminWalletSection.style.display = 'none';
        }

        // 3. Hide Referrals & VIP for Admins
        const refCard = document.getElementById('user-referral-system-card');
        if (refCard) refCard.style.display = d.is_admin ? 'none' : 'block';

        const adminGiftBtn = document.getElementById('admin-detail-gift-container');
        if (adminGiftBtn) adminGiftBtn.style.display = d.is_admin ? 'block' : 'none';

        // Dynamic Store Announcement Hero Banner (Only shown when configured by admin!)
        const heroBanner = document.getElementById('storefront-hero-banner');
        if (heroBanner) {
          const annText = (d.store_announcement || '').trim();
          if (annText) {
            const titleEl = document.getElementById('banner-title-text');
            const subEl = document.getElementById('banner-sub-text');
            if (titleEl) titleEl.innerText = annText;
            if (subEl) subEl.style.display = 'none';
            heroBanner.style.display = 'block';
          } else {
            heroBanner.style.display = 'none';
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
        const defaultRoleTitle = d.is_admin ? ((currentAppLanguage === 'ar') ? 'المسؤول' : 'Admin') : ((currentAppLanguage === 'ar') ? 'العميل' : 'Customer');
        const tgFullName = tgUser?.first_name ? `${tgUser.first_name} ${tgUser.last_name || ''}`.trim() : '';
        const effectiveName = tgFullName || (d.first_name ? `${d.first_name} ${d.last_name || ''}`.trim() : '');
        const displayName = effectiveName || (d.username ? '@' + d.username.replace(/^@/, '') : (d.telegram_id ? `ID: ${d.telegram_id}` : defaultRoleTitle));
        const nameEl = document.getElementById('user-name-title');
        if (nameEl) nameEl.innerText = displayName;

        const handleBox = document.getElementById('user-handle-title');
        const effectiveHandle = tgUser?.username || d.username;
        if (handleBox) {
          if (effectiveHandle) {
            handleBox.innerText = `@${effectiveHandle.replace(/^@/, '')}`;
            handleBox.style.display = 'block';
          } else {
            handleBox.style.display = 'none';
          }
        }

        const idNumEl = document.getElementById('user-tg-num');
        if (idNumEl) idNumEl.innerText = 'ID: ' + (d.telegram_id || userId);

        // Profile VIP Badge: ONLY display if a real discount is applied (>0% and not Standard)
        const vipBox = document.getElementById('user-vip-pill-box');
        const topVipTag = document.getElementById('top-vip-tag');
        const hasVipDiscount = d.vip_discount > 0 && d.vip_tier && d.vip_tier !== 'Standard';

        if (!d.is_admin && hasVipDiscount) {
          vipBox.innerHTML = `<span class="vip-tag">${d.vip_tier} (${currentAppLanguage === 'ar' ? 'خصم' : 'Discount'} ${d.vip_discount}%)</span>`;
          vipBox.style.display = 'block';
          topVipTag.innerText = d.vip_tier;
          topVipTag.style.display = 'inline-block';
        } else {
          vipBox.innerHTML = '';
          vipBox.style.display = 'none';
          topVipTag.style.display = 'none';
        }

        // VIP Progress Bar & Gamification
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
        const remainingSpend = Math.max(0, nextTarget - spent);
        const promptText = (remainingSpend > 0)
          ? ((currentAppLanguage === 'ar') ? `أنفق $${remainingSpend.toFixed(0)} إضافية للترقية إلى ${nextLabel}!` : `Spend $${remainingSpend.toFixed(0)} more to unlock ${nextLabel}!`)
          : ((currentAppLanguage === 'ar') ? 'تم الوصول لأعلى رتبة VIP! 🏆' : 'Top VIP Rank Reached! 🏆');

        const rankEl = document.getElementById('next-vip-rank');
        if (rankEl) rankEl.innerText = nextLabel;
        const progNumEl = document.getElementById('vip-progress-num');
        if (progNumEl) progNumEl.innerText = `${pct}% ($${spent.toFixed(0)} / $${nextTarget.toFixed(0)})`;
        const fillEl = document.getElementById('vip-progress-fill');
        if (fillEl) fillEl.style.width = `${pct}%`;

        const vipPromptEl = document.getElementById('vip-gamify-prompt');
        if (vipPromptEl) {
          vipPromptEl.innerText = promptText;
          vipPromptEl.style.display = 'block';
        }

        const setNode = (id, reached) => { const el = document.getElementById(id); if (el) el.classList.toggle('reached', reached); };
        setNode('vip-node-std', true);
        setNode('vip-node-sil', spent >= 100);
        setNode('vip-node-gld', spent >= 500);
        setNode('vip-node-plt', spent >= 1000);
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
      const pref = getCurrentCurrencyPref();
      const balDisplay = formatBalance(userData.balance || 0);

      const topBalEl = document.getElementById('top-balance-str');
      if (topBalEl) topBalEl.innerText = balDisplay;

      const heroBalEl = document.getElementById('wallet-balance-hero');
      if (heroBalEl) heroBalEl.innerText = balDisplay;

      const approxEl = document.getElementById('wallet-balance-approx');
      if (approxEl) {
        approxEl.innerText = (pref === 'SYP')
          ? `≈ $${Number(userData.balance || 0).toFixed(2)} USD`
          : (currentAppLanguage === 'ar' ? 'جاهز للشراء الفوري' : 'Ready for instant purchases');
      }

      const cardBal = document.getElementById('settings-card-balance');
      if (cardBal) cardBal.innerText = balDisplay;

      const cardSpent = document.getElementById('settings-card-spent');
      if (cardSpent) cardSpent.innerText = formatBalance(userData.total_spent || 0);
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

    function togglePasswordVisibility(inputId) {
      const el = document.getElementById(inputId);
      if (el) {
        el.type = (el.type === 'password') ? 'text' : 'password';
      }
    }

    function openAdminSuppliersPage() {
      haptic('pop');
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const view = document.getElementById('view-admin-suppliers');
      if (view) view.classList.add('active');
      window.scrollTo(0, 0);
      pushNav('admin_suppliers', closeAdminSuppliersPage);
    }

    function closeAdminSuppliersPage() {
      haptic('light');
      const view = document.getElementById('view-admin-suppliers');
      if (view) view.classList.remove('active');
      const setView = document.getElementById('view-settings');
      if (setView) setView.classList.add('active');
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_suppliers') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function openAdminStoreSettingsPage() {
      haptic('pop');
      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const view = document.getElementById('view-admin-store-settings');
      if (view) view.classList.add('active');
      window.scrollTo(0, 0);
      pushNav('admin_store_settings', closeAdminStoreSettingsPage);
      loadAdminStoreSettingsValues();
    }

    function closeAdminStoreSettingsPage() {
      haptic('light');
      const view = document.getElementById('view-admin-store-settings');
      if (view) view.classList.remove('active');
      const setView = document.getElementById('view-settings');
      if (setView) setView.classList.add('active');
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'admin_store_settings') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function loadAdminStoreSettingsValues() {
      const s = userData?.admin_stats;
      if (!s) return;
      const sypInp = document.getElementById('admin-syp-rate-input');
      if (sypInp && s.syp_usd_rate) sypInp.value = s.syp_usd_rate;
      const starsInp = document.getElementById('admin-stars-rate-input');
      if (starsInp && s.stars_to_usd_rate) starsInp.value = s.stars_to_usd_rate;
      const marginInp = document.getElementById('admin-margin-input');
      if (marginInp && s.global_margin_percent) marginInp.value = s.global_margin_percent;
      const refInp = document.getElementById('admin-ref-rate-input');
      if (refInp && s.referral_commission_percent) refInp.value = s.referral_commission_percent;
      const logoInp = document.getElementById('admin-store-logo-input');
      if (logoInp && userData?.store_logo_url) logoInp.value = userData.store_logo_url;
      const annInp = document.getElementById('admin-announcement-input');
      if (annInp && s.store_announcement) annInp.value = s.store_announcement;
      isAutoRefundEnabled = !!s.autorefund_enabled;
      updateAutoRefundBtnUI();
    }

    async function loadAdminSuppliersDetails() {
      try {
        const res = await fetch(`/api/admin/supplier/details?tg_id=${userId}`);
        const d = await res.json();
        if (!res.ok || d.error) return;

        // Server 1 BatStore
        const bat = d.batstore || {};
        const batCountEl = document.getElementById('sup-card-bat-count');
        if (batCountEl) batCountEl.innerText = `${bat.product_count || 0} منتج مرتبط`;
        const batSyncEl = document.getElementById('sup-card-bat-sync');
        if (batSyncEl) batSyncEl.checked = !!bat.sync_enabled;
        const batKeyState = document.getElementById('sup-card-bat-key-state');
        if (batKeyState) batKeyState.innerText = bat.api_key_configured ? `محفوظ (${bat.api_key_masked})` : 'غير مهيأ';

        // Server 2 ProdSeller
        const prod = d.prodseller || {};
        const prodCountEl = document.getElementById('sup-card-prod-count');
        if (prodCountEl) prodCountEl.innerText = `${prod.product_count || 0} منتج مرتبط`;
        const prodSyncEl = document.getElementById('sup-card-prod-sync');
        if (prodSyncEl) prodSyncEl.checked = !!prod.sync_enabled;
        const prodKeyState = document.getElementById('sup-card-prod-key-state');
        if (prodKeyState) prodKeyState.innerText = prod.api_key_configured ? `محفوظ (${prod.api_key_masked})` : 'غير مهيأ';

        // Routing & Failover
        const routingEl = document.getElementById('sup-page-routing-select');
        if (routingEl && d.routing_strategy) routingEl.value = d.routing_strategy;
        const failoverEl = document.getElementById('sup-page-failover');
        if (failoverEl) failoverEl.checked = (d.auto_failover !== false);

        // Update live balances
        await refreshSupplierBalances(false);
      } catch (e) {
        console.error('Failed to load supplier details:', e);
      }
    }

    async function testBatStoreKeyLive() {
      haptic('light');
      const keyVal = document.getElementById('sup-card-bat-key')?.value?.trim() || '';
      const statusEl = document.getElementById('sup-card-bat-status');
      const btn = document.getElementById('btn-test-batstore');
      if (btn) btn.disabled = true;

      if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.style.color = 'var(--hint)';
        statusEl.innerText = 'جاري الاتصال بسيرفر BatStore وفحص الرصيد...';
      }

      try {
        const res = await fetch('/api/admin/batstore/test-balance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, api_key: keyVal })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          if (statusEl) {
            statusEl.style.color = '#ef4444';
            statusEl.innerText = `خطأ في الاتصال: ${d.error || 'المفتاح غير صالح'}`;
          }
          showToast(d.error || 'فشل فحص سيرفر 1');
          return;
        }

        const bal = Number(d.balance || 0.0).toFixed(2);
        if (statusEl) {
          statusEl.style.color = '#10b981';
          statusEl.innerText = `سيرفر 1 متصل بنجاح: الرصيد $${bal} USD · المستخدم: ${d.username || 'Reseller'}`;
        }
        const balEl = document.getElementById('sup-card-bat-bal');
        if (balEl) balEl.innerText = `$${bal} USD`;
        showToast(`رصيد سيرفر 1: $${bal}`);
      } catch (e) {
        if (statusEl) {
          statusEl.style.color = '#ef4444';
          statusEl.innerText = `خطأ: ${e.message}`;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function testProdSellerKeyLiveInSuppliersPage() {
      haptic('light');
      const keyVal = document.getElementById('sup-card-prod-key')?.value?.trim() || '';
      const statusEl = document.getElementById('sup-card-prod-status');
      const btn = document.getElementById('btn-test-prodseller');
      if (btn) btn.disabled = true;

      if (statusEl) {
        statusEl.style.display = 'block';
        statusEl.style.color = 'var(--hint)';
        statusEl.innerText = 'جاري الاتصال بسيرفر ProdSeller وفحص الرصيد...';
      }

      try {
        const res = await fetch('/api/admin/prodseller/test-balance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId, api_key: keyVal })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          if (statusEl) {
            statusEl.style.color = '#ef4444';
            statusEl.innerText = `خطأ في الاتصال: ${d.error || 'المفتاح غير صالح'}`;
          }
          showToast(d.error || 'فشل فحص سيرفر 2');
          return;
        }

        const bal = Number(d.balance || 0.0).toFixed(2);
        const mem = d.membership || 'bronze';
        const user = d.username ? `@${d.username}` : '';
        if (statusEl) {
          statusEl.style.color = '#10b981';
          statusEl.innerText = `سيرفر 2 متصل بنجاح: الرصيد $${bal} USDT · العضوية: ${mem} ${user}`;
        }
        const balEl = document.getElementById('sup-card-prod-bal');
        if (balEl) balEl.innerText = `$${bal} USDT`;
        const tierEl = document.getElementById('sup-card-prod-tier');
        if (tierEl) tierEl.innerText = `عضوية: ${mem} ${user}`;
        showToast(`رصيد سيرفر 2: $${bal}`);
      } catch (e) {
        if (statusEl) {
          statusEl.style.color = '#ef4444';
          statusEl.innerText = `خطأ: ${e.message}`;
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function saveSuppliersPageSettings() {
      haptic('medium');
      const batKey = document.getElementById('sup-card-bat-key')?.value?.trim() || '';
      const prodKey = document.getElementById('sup-card-prod-key')?.value?.trim() || '';
      const strategy = document.getElementById('sup-page-routing-select')?.value || 'auto_cheapest';
      const batSync = document.getElementById('sup-card-bat-sync')?.checked;
      const prodSync = document.getElementById('sup-card-prod-sync')?.checked;
      const failover = document.getElementById('sup-page-failover')?.checked;

      showToast('جاري حفظ إعدادات السيرفرين...');
      try {
        const res = await fetch('/api/admin/supplier/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            admin_tg_id: userId,
            batstore_api_key: batKey,
            prodseller_api_key: prodKey,
            routing_strategy: strategy,
            batstore_sync_enabled: batSync,
            prodseller_sync_enabled: prodSync,
            auto_failover: failover
          })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          showToast(d.error || 'فشل الحفظ');
          return;
        }
        showToast('تم حفظ كافة إعدادات ومفاتيح السيرفرين بنجاح');
        await loadAdminSuppliersDetails();
      } catch (e) {
        showToast(e.message);
      }
    }

    async function syncAllSupplierCatalogsInSuppliersPage() {
      haptic('medium');
      const btn = document.getElementById('btn-sup-page-sync');
      if (btn) {
        btn.disabled = true;
        btn.innerText = 'جاري مزامنة المنتجات من السيرفرين...';
      }
      showToast('جاري جلب ومزامنة المنتجات من كلا الموردين...');
      try {
        const res = await fetch('/api/admin/supplier/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_tg_id: userId })
        });
        const d = await res.json();
        if (!res.ok || d.error) {
          showToast(d.error || 'فشلت المزامنة');
          return;
        }
        const b = d.result?.batstore || {};
        const p = d.result?.prodseller || {};
        const tot = d.result?.total_products || 0;
        showToast(`تمت المزامنة بنجاح: BatStore (${b.created || 0}+/${b.updated || 0}) · ProdSeller (${p.created || 0}+/${p.updated || 0}) · الإجمالي: ${tot}`);
        await fetchCatalogData();
        await loadAdminSuppliersDetails();
      } catch (e) {
        showToast(e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerText = 'مزامنة وتحديث كافة المنتجات من كلا الموردين الآن';
        }
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
      ['all', 'attention', 'orders', 'recharges', 'vault'].forEach(f => {
        const btn = document.getElementById('act-filter-' + f);
        if (btn) btn.classList.toggle('active', f === filterKey);
      });
      if (userData?.is_admin && adminActivityMode === 'radar') {
        renderAdminLiveRadar();
      } else {
        renderUnifiedActivity();
      }
    }

    let adminActivityMode = 'radar';
    let adminLiveActivities = [];

    function switchAdminActivityMode(mode) {
      haptic('pop');
      adminActivityMode = mode;
      document.getElementById('btn-mode-live-radar')?.classList.toggle('active', mode === 'radar');
      document.getElementById('btn-mode-my-orders')?.classList.toggle('active', mode === 'my_orders');
      const radarHeader = document.getElementById('admin-radar-header-box');
      const attentionChip = document.getElementById('act-filter-attention');
      const titleOrders = document.getElementById('title-orders-history');

      if (mode === 'radar') {
        if (radarHeader) radarHeader.style.display = 'block';
        if (attentionChip) attentionChip.style.display = 'inline-block';
        if (titleOrders) titleOrders.innerText = (currentAppLanguage === 'ar') ? 'رادار العمليات المباشرة للعملاء' : 'Live Customer Operations Radar';
        loadAdminLiveRadar();
      } else {
        if (radarHeader) radarHeader.style.display = 'none';
        if (attentionChip) attentionChip.style.display = 'none';
        if (titleOrders) titleOrders.innerText = (currentAppLanguage === 'ar') ? 'طلباتي وسجل عملياتي' : 'My Orders & Activity';
        renderUnifiedActivity();
      }
    }

    async function loadAdminLiveRadar(showToastOnDone = false) {
      if (!userData?.is_admin) return;
      try {
        const res = await fetch(`/api/admin/live-activity?tg_id=${userId}&limit=60`);
        const d = await res.json();
        if (d.status === 'ok') {
          adminLiveActivities = d.activities || [];
          const attentionBadge = document.getElementById('admin-radar-attention-badge');
          if (attentionBadge) {
            if (d.needs_attention_count > 0) {
              attentionBadge.innerText = `⚠️ ${d.needs_attention_count} بحاجة اعتماد`;
              attentionBadge.style.display = 'inline-block';
            } else {
              attentionBadge.style.display = 'none';
            }
          }
          renderAdminLiveRadar();
          if (showToastOnDone) {
            showToast(currentAppLanguage === 'ar' ? '✅ تم تحديث الرادار المباشر' : '✅ Live radar refreshed');
          }
        }
      } catch (e) {
        console.error("Live radar error:", e);
      }
    }
    async function loadAdminSearchDemands() {
      if (!userData?.is_admin) return;
      const box = document.getElementById('admin-demands-list');
      if (!box) return;
      try {
        const res = await fetch(`/api/admin/search/demands?tg_id=${userId}`);
        const d = await res.json();
        const demands = d.demands || [];
        if (!demands.length) {
          box.innerHTML = `<span style="font-size: 11px; color: var(--hint);">${currentAppLanguage === 'ar' ? 'لا توجد طلبات بحث مسجلة حالياً.' : 'No zero-result searches recorded yet.'}</span>`;
          return;
        }
        box.innerHTML = demands.map(it => `
          <span class="pill-badge" style="background: var(--card); border: 1px solid var(--border); font-size: 11px; padding: 4px 8px;">
            ${it.query} <strong style="color: var(--accent); margin-inline-start: 4px;">(${it.searches})</strong>
          </span>
        `).join('');
      } catch (e) {
        box.innerHTML = `<span style="font-size: 11px; color: var(--danger);">${currentAppLanguage === 'ar' ? 'فشل تحميل الطلبات' : 'Failed to load demands'}</span>`;
      }
    }


    function renderAdminLiveRadar() {
      const container = document.getElementById('orders-container-box');
      if (!container) return;

      let list = [...adminLiveActivities];
      if (activeActivityFilter === 'attention') {
        list = list.filter(a => a.needs_attention);
      } else if (activeActivityFilter === 'recharges') {
        list = list.filter(a => a.type === 'recharge');
      } else if (activeActivityFilter === 'orders') {
        list = list.filter(a => a.type === 'order');
      }

      const isAr = (currentAppLanguage === 'ar');
      if (!list.length) {
        container.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--hint); background: var(--input-bg); border-radius: 14px; border: 1px solid var(--border);">
            <div style="font-size: 28px; margin-bottom: 8px;">📡</div>
            <div style="font-size: 14px; font-weight: 700; color: var(--text);">${isAr ? 'لا توجد عمليات في هذا التصنيف حالياً' : 'No operations in this category yet'}</div>
            <div style="font-size: 12px; margin-top: 4px;">${isAr ? 'ستظهر أي عمليات شراء أو شحن جديدة فور إجرائها في المتجر.' : 'New customer orders or top-ups will appear here in real time.'}</div>
          </div>
        `;
        return;
      }

      container.innerHTML = list.map(item => {
        const isOrder = (item.type === 'order');
        const isCompleted = (item.status === 'completed');
        const isPending = (item.status === 'pending' || item.status === 'pending_fulfillment');

        const statusColor = isCompleted ? '#10b981' : (isPending ? '#f59e0b' : '#ef4444');
        const statusBg = isCompleted ? 'rgba(16,185,129,0.18)' : (isPending ? 'rgba(245,158,11,0.18)' : 'rgba(239,68,68,0.18)');
        const statusText = isCompleted ? (isAr ? 'مكتمل ✅' : 'Completed ✅') : (isPending ? (isAr ? 'بانتظار التحويل / التفعيل ⏳' : 'Pending Activation ⏳') : (isAr ? 'فشل / منتهي ❌' : 'Failed / Expired ❌'));

        const userTag = item.username ? `@${item.username}` : (isAr ? `مستخدم` : `User`);
        const tgIdStr = item.telegram_id || '';

        return `
          <div class="inset-card" style="margin-bottom: 12px; border-color: ${item.needs_attention ? 'rgba(239,68,68,0.45)' : 'var(--border)'}; background: ${item.needs_attention ? 'linear-gradient(135deg, rgba(239,68,68,0.06), var(--card))' : 'var(--card)'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 15px;">${isOrder ? '🛍️' : '💳'}</span>
                <strong style="font-size: 13px; color: var(--text);">${item.title}</strong>
              </div>
              <span class="pill-badge" style="background: ${statusBg}; color: ${statusColor}; font-size: 11px;">
                ${statusText}
              </span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 8px;">
              <div>
                <span style="font-weight: 700; color: var(--accent);">${userTag}</span>
                <span style="font-family: monospace; color: var(--hint); margin-inline-start: 4px;">(ID: ${tgIdStr})</span>
              </div>
              <span style="font-size: 11px; color: var(--hint);">${item.created_at || ''}</span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; font-size: 13px;">
              <span style="color: var(--hint); font-size: 11px;">${isOrder ? (isAr ? 'قيمة الطلب' : 'Order Total') : (isAr ? 'المبلغ المدفوع' : 'Amount Paid')}</span>
              <div style="text-align: right;">
                <strong style="font-size: 15px; color: var(--text);">$${(item.amount_usd || item.total_usd || 0.0).toFixed(2)} USD</strong>
                ${item.local_amount && item.currency !== 'USD' ? `
                  <div style="font-size: 11px; color: var(--warning); font-weight: 700;">≈ ${Math.round(item.local_amount).toLocaleString()} ${item.currency === 'XTR' ? '⭐' : (isAr ? 'ل.س' : 'SYP')}</div>
                ` : ''}
              </div>
            </div>

            ${!isOrder && item.needs_attention ? `
              <div style="margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 10px;">
                <button class="btn-action-primary" onclick="adminApproveRechargeAction('${item.id}', ${item.telegram_id}, ${item.amount_usd})" style="width: 100%; height: 42px; background: linear-gradient(135deg, #10b981, #059669); font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; gap: 6px;">
                  <span>${isAr ? `✅ اعتماد وإيداع الرصيد للعميل (+$${(item.amount_usd || 0).toFixed(2)})` : `✅ Approve & Credit Balance (+$${(item.amount_usd || 0).toFixed(2)})`}</span>
                </button>
              </div>
            ` : ''}

            ${isOrder && item.needs_attention ? `
              <div style="margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 10px; display: flex; gap: 8px;">
                <button class="btn-action-warning" onclick="executeAdminRefundStuck(${item.raw_id}, ${item.total_usd})" style="flex: 1; height: 38px; font-size: 12px;">
                  <span>${isAr ? '↩️ استرداد الرصيد' : '↩️ Refund Balance'}</span>
                </button>
                <button class="btn-action-secondary" onclick="openAdminOrdersModal()" style="flex: 1; height: 38px; font-size: 12px;">
                  <span>${isAr ? '🔍 فحص في المورد' : '🔍 Inspect Supplier'}</span>
                </button>
              </div>
            ` : ''}
          </div>
        `;
      }).join('');
    }

    async function adminApproveRechargeAction(rechargeId, targetTgId, amountUsd) {
      haptic('medium');
      const isAr = (currentAppLanguage === 'ar');
      const msg = isAr ? `هل أنت متأكد من اعتماد وإيداع الرصيد (+$${Number(amountUsd || 0).toFixed(2)} USD) للعميل (${targetTgId})؟` : `Are you sure you want to approve and credit (+$${Number(amountUsd || 0).toFixed(2)} USD) to customer (${targetTgId})?`;
      const run = async () => {
        showToast(isAr ? 'جاري اعتماد الشحن وإيداع الرصيد...' : 'Approving and crediting deposit...');
        try {
          const res = await fetch('/api/admin/recharge/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              admin_tg_id: userId,
              recharge_id: rechargeId,
              telegram_id: targetTgId,
              amount_usd: amountUsd
            })
          });
          const d = await res.json();
          if (d.status === 'ok') {
            fireConfetti();
            haptic('success');
            showToast(`✅ تم اعتماد الشحن وإيداع $${d.credited_amount.toFixed(2)} للعميل بنجاح!`);
            loadAdminLiveRadar();
          } else {
            showToast(d.error || 'فشل اعتماد الشحن');
          }
        } catch (e) {
          showToast('خطأ في الاتصال أثناء اعتماد الشحن');
        }
      };

      if (tg?.showConfirm) {
        tg.showConfirm(msg, (ok) => { if (ok) run(); });
      } else if (tg?.showPopup) {
        tg.showPopup({ message: msg, buttons: [{ id: 'ok', type: 'destructive', text: 'اعتماد الشحن' }, { id: 'cancel', type: 'cancel' }] }, (b) => { if (b === 'ok') run(); });
      } else {
        run();
      }
    }

    function openExternalPaymentUrl(url) {
      haptic('light');
      if (tg?.openLink) tg.openLink(url);
      else window.open(url, '_blank');
    }
    let currentOrderDetailId = null;
    let expandedActivityItems = new Set();

    function toggleActivityItem(itemId) {
      haptic('selection');
      const el = document.getElementById('activity-item-' + itemId);
      if (!el) return;
      if (expandedActivityItems.has(itemId)) {
        expandedActivityItems.delete(itemId);
        el.classList.remove('expanded');
      } else {
        expandedActivityItems.add(itemId);
        el.classList.add('expanded');
      }
    }

    function openOrderDetailView(orderId) {
      haptic('pop');
      currentOrderDetailId = Number(orderId);
      const order = (userData?.orders || []).find(o => Number(o.id) === currentOrderDetailId);
      if (!order) return;

      const idEl = document.getElementById('order-detail-id-title');
      if (idEl) idEl.innerText = `طلب #${order.id}`;

      const dateEl = document.getElementById('order-detail-date');
      if (dateEl) dateEl.innerText = order.created_at || '';

      const prodEl = document.getElementById('order-detail-products-title');
      if (prodEl) prodEl.innerText = order.products || 'Digital Product';

      const totalEl = document.getElementById('order-detail-total-amount');
      if (totalEl) totalEl.innerText = `$${Number(order.total || 0).toFixed(2)} USD`;

      const badgeEl = document.getElementById('order-detail-status-badge');
      if (badgeEl) {
        if (order.status === 'completed') {
          badgeEl.className = 'pill-badge status-completed';
          badgeEl.style.background = 'rgba(16, 185, 129, 0.2)';
          badgeEl.style.color = '#10b981';
          badgeEl.innerText = (currentAppLanguage === 'ar') ? 'مكتمل ومفعل' : 'Completed';
        } else if (order.status === 'refunded') {
          badgeEl.className = 'pill-badge status-refunded';
          badgeEl.style.background = 'rgba(239, 68, 68, 0.2)';
          badgeEl.style.color = '#ef4444';
          badgeEl.innerText = (currentAppLanguage === 'ar') ? 'مسترجع' : 'Refunded';
        } else {
          badgeEl.className = 'pill-badge status-pending';
          badgeEl.style.background = 'rgba(245, 158, 11, 0.2)';
          badgeEl.style.color = '#f59e0b';
          badgeEl.innerText = (currentAppLanguage === 'ar') ? 'قيد التنفيذ' : 'Processing';
        }
      }

      const fillEl = document.getElementById('order-detail-stepper-fill');
      const circle2 = document.getElementById('order-step-circle-2');
      const circle3 = document.getElementById('order-step-circle-3');
      const node2 = document.getElementById('order-step-node-2');
      const node3 = document.getElementById('order-step-node-3');

      if (order.status === 'completed') {
        if (fillEl) { fillEl.style.width = '100%'; fillEl.style.background = 'var(--accent)'; }
        if (node2) node2.className = 'order-step-node completed';
        if (circle2) circle2.innerText = '✓';
        if (node3) node3.className = 'order-step-node completed';
        if (circle3) circle3.innerText = '✓';
      } else if (order.status === 'refunded') {
        if (fillEl) { fillEl.style.width = '50%'; fillEl.style.background = '#ef4444'; }
        if (node2) node2.className = 'order-step-node active';
        if (circle2) circle2.innerText = '↩️';
        if (node3) node3.className = 'order-step-node';
        if (circle3) circle3.innerText = '3';
      } else {
        if (fillEl) { fillEl.style.width = '50%'; fillEl.style.background = 'var(--accent)'; }
        if (node2) node2.className = 'order-step-node active';
        if (circle2) circle2.innerText = '⏳';
        if (node3) node3.className = 'order-step-node';
        if (circle3) circle3.innerText = '3';
      }

      const credBox = document.getElementById('order-detail-credentials-box');
      if (credBox) {
        credBox.innerHTML = renderStructuredCredentials(order.goods);
      }

      const warBadge = document.getElementById('order-detail-warranty-badge');
      if (warBadge) {
        if (order.warranty_days) {
          warBadge.innerText = (currentAppLanguage === 'ar') ? `🛡️ ضمان ${order.warranty_days} يوم` : `🛡️ ${order.warranty_days}d Warranty`;
          warBadge.style.display = 'inline-block';
        } else {
          warBadge.style.display = 'none';
        }
      }

      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      const detailSection = document.getElementById('view-order-detail');
      if (detailSection) detailSection.classList.add('active');

      pushNav('order_detail', closeOrderDetailView);
    }

    function closeOrderDetailView() {
      haptic('light');
      currentOrderDetailId = null;
      const detailSection = document.getElementById('view-order-detail');
      if (detailSection) detailSection.classList.remove('active');
      const ordersView = document.getElementById('view-orders');
      if (ordersView) ordersView.classList.add('active');

      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'order_detail') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function downloadCurrentOrderDetailPdf() {
      if (currentOrderDetailId) downloadOrderReceipt(currentOrderDetailId);
    }

    function rateCurrentOrderDetail() {
      if (currentOrderDetailId) openReviewModal(currentOrderDetailId);
    }

    function supportCurrentOrderDetail() {
      if (currentOrderDetailId) openSupportTicketModal(currentOrderDetailId);
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
      } else if (activeActivityFilter === 'vault') {
        combined = combined.filter(it => it.type === 'order' && it.status === 'completed' && it.goods && it.goods.length > 0);
      }
      if (!combined.length) {
        renderEmptyOrders();
        return;
      }

      const d = I18N[currentAppLanguage] || I18N.ar;

      container.innerHTML = combined.map((it, idx) => {
        const itemDomId = it.type === 'order' ? 'ord_' + it.id : 'rec_' + it.id;
        const isExpanded = expandedActivityItems.has(itemDomId);

        if (it.type === 'order') {
          let statusClass = 'status-completed';
          let statusLabel = (currentAppLanguage === 'ar') ? 'مكتمل' : 'Completed';

          if (it.status === 'completed') {
            statusClass = 'status-completed';
            statusLabel = (currentAppLanguage === 'ar') ? 'مكتمل' : 'Completed';
          } else if (it.status === 'refunded') {
            statusClass = 'status-refunded';
            statusLabel = (currentAppLanguage === 'ar') ? 'مسترجع' : 'Refunded';
          } else if (it.status === 'pending_supplier_recharge') {
            statusClass = 'status-pending';
            statusLabel = (currentAppLanguage === 'ar') ? 'قيد التجهيز' : 'Processing';
          } else {
            statusClass = 'status-pending';
            statusLabel = (currentAppLanguage === 'ar') ? 'قيد التنفيذ' : 'In Progress';
          }

          const stepperFillWidth = it.status === 'completed' ? '100%' : (it.status.includes('pending') ? '50%' : '100%');
          const stepperFillColor = it.status === 'refunded' ? '#ef4444' : 'var(--accent)';
          const node2Class = it.status === 'completed' ? 'completed' : (it.status.includes('pending') ? 'active' : (it.status === 'refunded' ? 'active' : ''));
          const node2Icon = it.status === 'completed' ? '✓' : (it.status === 'refunded' ? '↩️' : '⏳');

          return `
            <div class="activity-notif-item ${isExpanded ? 'expanded' : ''}" id="activity-item-${itemDomId}">
              <!-- Compact Notification Header -->
              <div class="activity-notif-header" onclick="toggleActivityItem('${itemDomId}')">
                <div class="activity-notif-badge ${statusClass}">
                  <span>🛍️</span>
                  <span class="status-dot ${statusClass}"></span>
                </div>
                <div class="activity-notif-info">
                  <div class="activity-notif-title-row">
                    <span class="activity-notif-title">${(currentAppLanguage === 'ar' ? 'طلب' : 'Order')} #${it.id} · ${it.products || (currentAppLanguage === 'ar' ? 'منتج رقمي' : 'Digital Service')}</span>
                    <span class="activity-notif-amount amount-blue">${it.total.toFixed(2)}${it.sym}</span>
                  </div>
                  <div class="activity-notif-meta-row">
                    <span class="activity-notif-time">${it.created_at || ''}</span>
                    <span class="activity-status-pill ${statusClass}">${statusLabel}</span>
                  </div>
                </div>
                <div class="activity-notif-arrow">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
                  </svg>
                </div>
              </div>

              <!-- Smooth Expandable Body -->
              <div class="activity-notif-body">
                <!-- 3-Step Timeline Stepper -->
                <div class="order-stepper-track" style="margin: 10px 0 14px 0;">
                  <div class="order-stepper-line">
                    <div class="order-stepper-line-fill" style="width: ${stepperFillWidth}; background: ${stepperFillColor};"></div>
                  </div>
                  <div class="order-step-node completed">
                    <div class="order-step-circle">✓</div>
                    <div class="order-step-label">${d.step_placed}</div>
                  </div>
                  <div class="order-step-node ${node2Class}">
                    <div class="order-step-circle">${node2Icon}</div>
                    <div class="order-step-label">${it.status === 'refunded' ? (currentAppLanguage === 'ar' ? 'مسترجع' : 'Refunded') : d.step_processing}</div>
                  </div>
                  <div class="order-step-node ${it.status === 'completed' ? 'completed' : ''}">
                    <div class="order-step-circle">${it.status === 'completed' ? '✓' : '3'}</div>
                    <div class="order-step-label">${d.step_delivered}</div>
                  </div>
                </div>

                <!-- Structured Delivered Credentials -->
                ${renderStructuredCredentials(it.goods)}

                <!-- Action Pills -->
                <div style="display: flex; gap: 6px; align-items: center; margin-top: 10px; flex-wrap: wrap;">
                  ${it.warranty_days ? `
                    <span class="pill-badge" style="background: rgba(56,189,248,0.15); color: var(--accent); font-size: 11px;">🛡️ ${currentAppLanguage === 'ar' ? `ضمان ${it.warranty_days} يوم` : `${it.warranty_days}d Warranty`}</span>
                  ` : ''}
                  ${it.status === 'completed' ? `
                    <button class="btn-action-secondary" onclick="showOrderReceiptModal(${it.id})" style="height: 34px; font-size: 11px; padding: 0 10px;">🧾 ${currentAppLanguage === 'ar' ? 'عرض الإيصال' : 'View Receipt'}</button>
                    <button id="btn-rate-order-${it.id}" class="btn-action-secondary" onclick="openReviewModal(${it.id})" style="height: 34px; font-size: 11px; padding: 0 10px;">⭐ ${currentAppLanguage === 'ar' ? 'تقييم' : 'Rate'}</button>
                    <button class="btn-action-secondary" onclick="downloadOrderReceipt(${it.id})" style="height: 34px; font-size: 11px; padding: 0 10px;">⬇️ PDF</button>
                  ` : ''}
                </div>

                <!-- Prominent Enter Order Page Action -->
                <button class="btn-enter-page" onclick="openOrderDetailView(${it.id})">
                  <span>${currentAppLanguage === 'ar' ? '🔍 عرض تفاصيل الطلب كاملة' : '🔍 View Full Order Details'}</span>
                  <span style="font-size: 14px;">${currentAppLanguage === 'ar' ? '‹' : '›'}</span>
                </button>
              </div>
            </div>
          `;
        }

        // Recharge Notification Item
        const isPaid = (it.status === 'completed');
        const isPending = (it.status === 'pending');
        let statusClass = isPaid ? 'status-completed' : (isPending ? 'status-pending' : 'status-failed');
        let statusLabel = isPaid ? (currentAppLanguage === 'ar' ? 'تم الشحن' : 'Completed') : (isPending ? (currentAppLanguage === 'ar' ? 'بانتظار الدفع' : 'Pending') : (currentAppLanguage === 'ar' ? 'ملغية' : 'Cancelled'));

        let methodLogo = '💳';
        let methodTitle = (currentAppLanguage === 'ar') ? 'شحن رصيد' : 'Wallet Top-up';
        if (it.method === 'shamcash') {
          methodLogo = '<img src="https://shamcash.sy/_next/static/media/logo.5be69def.svg" style="width:20px; height:20px; object-fit:contain;" alt="ShamCash">';
          methodTitle = (currentAppLanguage === 'ar') ? 'شام كاش' : 'Sham Cash';
        } else if (it.method === 'syriatelcash') {
          methodLogo = '<img src="https://www.syriatel.sy/assets/img/logo.png" style="width:20px; height:20px; object-fit:contain;" alt="Syriatel">';
          methodTitle = (currentAppLanguage === 'ar') ? 'سيرياتيل كاش' : 'Syriatel Cash';
        } else if (it.method === 'stars') {
          methodLogo = '⭐';
          methodTitle = (currentAppLanguage === 'ar') ? 'نجوم تيليجرام' : 'Telegram Stars';
        } else if (it.method === 'crypto') {
          methodLogo = '🪙';
          methodTitle = (currentAppLanguage === 'ar') ? 'العملات الرقمية' : 'Crypto (USDT)';
        }

        const localPart = (it.currency === 'SYP' && it.invoice_amount)
          ? ` <span style="font-size:11px; color:var(--hint);">(≈ ${Math.round(it.invoice_amount).toLocaleString()} ل.س)</span>`
          : '';

        const invoiceParamStr = JSON.stringify({
          invoice_id: it.invoice_id || '',
          url: it.payment_url || '',
          provider: it.method || 'shamcash',
          amount: it.amount_usd || 0.0,
          invoice_amount: it.invoice_amount || 0,
          currency: it.currency || 'USD'
        }).replace(/"/g, '&quot;');

        return `
          <div class="activity-notif-item ${isExpanded ? 'expanded' : ''}" id="activity-item-${itemDomId}">
            <!-- Compact Notification Header -->
            <div class="activity-notif-header" onclick="toggleActivityItem('${itemDomId}')">
              <div class="activity-notif-badge ${statusClass}">
                <span>${methodLogo}</span>
                <span class="status-dot ${statusClass}"></span>
              </div>
              <div class="activity-notif-info">
                <div class="activity-notif-title-row">
                  <span class="activity-notif-title">${methodTitle}</span>
                  <span class="activity-notif-amount amount-green">+$${it.amount_usd.toFixed(2)}</span>
                </div>
                <div class="activity-notif-meta-row">
                  <span class="activity-notif-time">${it.created_at || ''}</span>
                  <span class="activity-status-pill ${statusClass}">${statusLabel}</span>
                </div>
              </div>
              <div class="activity-notif-arrow">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                  <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
                </svg>
              </div>
            </div>

            <!-- Expandable Body -->
            <div class="activity-notif-body">
              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin: 6px 0;">
                <span>${(currentAppLanguage === 'ar') ? 'المبلغ المستلم:' : 'Amount Received:'} <strong style="color:var(--success); font-size:15px;">+$${it.amount_usd.toFixed(2)} USD</strong>${localPart}</span>
                <span style="font-size: 11px; color: var(--hint); font-family: monospace;">${it.invoice_id ? '#' + it.invoice_id.substring(0, 12) : ''}</span>
              </div>

              ${isPending ? `
                <div style="display: flex; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);">
                  ${it.payment_url ? `
                    <button class="btn-action-primary" onclick="openExternalPaymentUrl('${it.payment_url}')" style="flex: 1; height: 36px; font-size: 11px;">
                      ${(currentAppLanguage === 'ar') ? '🌐 إتمام الدفع' : '🌐 Pay Online'}
                    </button>
                  ` : ''}
                  <button class="btn-action-secondary" onclick="openInvoicePage(${invoiceParamStr})" style="flex: 1; height: 36px; font-size: 11px;">
                    ${(currentAppLanguage === 'ar') ? '🔄 فحص الفاتورة' : '🔄 Check Status'}
                  </button>
                </div>
              ` : ''}

              <!-- Succeeded Recharges show Official Deposit Voucher, Pending show Invoice & Pay -->
              ${isPaid ? `
                <button class="btn-enter-page" onclick="showRechargeReceiptModal(${invoiceParamStr})">
                  <span>${currentAppLanguage === 'ar' ? '🧾 عرض إيصال الشحن الرسمي المعتمد' : '🧾 View Official Top-Up Receipt'}</span>
                  <span style="font-size: 14px;">${currentAppLanguage === 'ar' ? '‹' : '›'}</span>
                </button>
              ` : `
                <button class="btn-enter-page" onclick="openInvoicePage(${invoiceParamStr})">
                  <span>${currentAppLanguage === 'ar' ? '🔄 متابعة الدفع وفحص الفاتورة' : '🔄 Complete Payment / Check Status'}</span>
                  <span style="font-size: 14px;">${currentAppLanguage === 'ar' ? '‹' : '›'}</span>
                </button>
              `}
            </div>
          </div>
        `;
      }).join('');
    }
    function copyCredText(text, btn) {
      haptic('success');
      const targetBtn = btn || (window.event?.currentTarget);
      const originalText = targetBtn ? targetBtn.innerText : null;
      if (targetBtn) {
        targetBtn.innerText = (currentAppLanguage === 'ar') ? '✅ تم النسخ!' : '✅ Copied!';
        targetBtn.classList.add('copied');
        setTimeout(() => {
          if (targetBtn && originalText) {
            targetBtn.innerText = originalText;
            targetBtn.classList.remove('copied');
          }
        }, 1800);
      }
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

    // Customer 5-Star Review Modal Handlers
    let currentReviewRating = 5;
    function openReviewModal(orderId) {
      haptic('light');
      const orderInput = document.getElementById('review-order-id');
      if (orderInput) orderInput.value = orderId;
      setReviewStar(5);
      const commentInput = document.getElementById('review-comment-input');
      if (commentInput) commentInput.value = '';
      const modal = document.getElementById('customer-review-modal');
      if (modal) modal.style.display = 'flex';
      pushNav('customer_review', closeReviewModal);
    }

    function closeReviewModal() {
      haptic('light');
      const modal = document.getElementById('customer-review-modal');
      if (modal) modal.style.display = 'none';
      if (navStack.length > 0 && navStack[navStack.length - 1].name === 'customer_review') {
        navStack.pop();
        if (navStack.length === 0 && tg?.BackButton) tg.BackButton.hide();
      }
    }

    function setReviewStar(rating) {
      haptic('light');
      currentReviewRating = Math.max(1, Math.min(5, rating));
      for (let i = 1; i <= 5; i++) {
        const el = document.getElementById('star-' + i);
        if (el) el.classList.toggle('active', i <= currentReviewRating);
      }
    }

    async function submitCustomerReview() {
      if (!userId) return;
      haptic('medium');
      const orderId = parseInt(document.getElementById('review-order-id')?.value || '0', 10);
      const text = (document.getElementById('review-comment-input')?.value || '').trim();
      const btn = document.getElementById('btn-submit-customer-review');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>${currentAppLanguage === 'ar' ? 'جاري الإرسال...' : 'Submitting...'}</span>`;
      }

      try {
        const res = await fetch('/api/reviews/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tg_id: userId,
            rating: currentReviewRating,
            text: text,
            order_id: orderId || undefined
          })
        });
        const d = await res.json();
        if (btn) btn.disabled = false;
        if (d.status === 'success') {
          closeReviewModal();
          fireConfetti();
          haptic('success');
          showToast(currentAppLanguage === 'ar' ? 'شكراً لتقييمك! ✨' : 'Thank you for your review! ✨');
          const rateBtn = document.getElementById(`btn-rate-order-${orderId}`);
          if (rateBtn) {
            rateBtn.innerText = currentAppLanguage === 'ar' ? '✅ تم التقييم' : '✅ Reviewed';
            rateBtn.disabled = true;
          }
        } else {
          showToast(d.error || (currentAppLanguage === 'ar' ? 'فشل إرسال التقييم' : 'Review failed'));
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        showToast(currentAppLanguage === 'ar' ? 'خطأ في الاتصال' : 'Connection error');
      }
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
      if (userData) {
        userData.currency_preference = code;
      }
      try { localStorage.setItem('ghstore_curr_pref', code); } catch (e) {}
      updateBalancePills();
      updateFloatingCartUI();
      renderCatalogsGrid();
      if (activeCatalog) {
        let filtered = allProducts.filter(p => p.category === activeCatalog);
        filtered = filterAndSortProducts(filtered);
        renderProductItems(filtered);
      }
      if (selectedProduct) {
        updateDetailPagePrice();
      }
      renderCartDrawerItems();
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, currency: code })
        });
        showToast(currentAppLanguage === 'ar' ? `تم تعيين عملة العرض إلى ${code === 'SYP' ? 'الليرة السورية' : 'الدولار'}` : `Display currency set to ${code}`);
        loadUserData();
      }
    }

    function initCurrency() {
      const savedCurr = localStorage.getItem('ghstore_curr_pref') || 'USD';
      const btnUsd = document.getElementById('curr-chip-usd');
      const btnSyp = document.getElementById('curr-chip-syp');
      if (btnUsd) btnUsd.classList.toggle('active', savedCurr === 'USD');
      if (btnSyp) btnSyp.classList.toggle('active', savedCurr === 'SYP');
    }

    async function changeStoreLanguage(code) {
      haptic('pop');
      applyLanguage(code);
      const sel = document.getElementById('language-select-dropdown');
      if (sel) sel.value = code;
      const isAr = (code === 'ar');
      const langNames = { ar: 'العربية', en: 'English', de: 'Deutsch', es: 'Español', fr: 'Français', it: 'Italiano', zh: '中文' };
      const msg = isAr ? `تم تعيين لغة التطبيق إلى ${langNames[code] || code}!` : `App language set to ${langNames[code] || code}!`;
      showToast(msg);
      if (userId) {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: userId, language: code })
        });
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
    initCurrency();
    const tgLang = tg?.initDataUnsafe?.user?.language_code;
    const detectedLang = tgLang && I18N[tgLang] ? tgLang : (tgLang === 'ar' ? 'ar' : 'en');
    const initialLang = localStorage.getItem('ghstore_lang') || detectedLang;
    applyLanguage(initialLang);
    cloudStorageGet('ghstore_lang', (storedLang) => {
      if (storedLang && storedLang !== currentAppLanguage && I18N[storedLang]) {
        applyLanguage(storedLang);
      }
    });
    initWishlist();
    initCart();
    loadFromCache();
    fetchCatalogData();
    loadTrendingSearches();
    loadUserData();
    initSSE();
    checkHomeScreenCapability();
    handleStartParam();