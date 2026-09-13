/**
 * GH Store - 5sim Virtual Numbers & SMS Activation Module (sms.js)
 * 
 * Provides:
 * - Customer SMS modal: service picker, country picker, price quote & live availability
 * - Number purchase with atomic balance debit
 * - Interactive countdown timer (15 min) & live polling for incoming SMS code
 * - Instant code copy & haptic notifications
 * - Instant cancellation and refund if code does not arrive
 * - Number ban reporting with auto-refund
 * - Admin controls: toggle active services, toggle active countries, check 5sim balance
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};

  let currentSmsOrder = null;
  let smsPollTimer = null;
  let smsCountdownTimer = null;
  let currentQuote = null;

  // --- Customer SMS Activation Modal ---
  async function openSmsModal() {
    api().haptic?.('medium');
    const modal = document.getElementById('sms-activation-modal');
    if (!modal) return;

    modal.style.display = 'flex';
    api().pushNav?.('sms_modal', closeSmsModal);

    // Reset view to stage select unless an active order is in progress
    if (!currentSmsOrder || currentSmsOrder.completed) {
      setSmsStage('select');
      await loadSmsServicesAndCountries();
    } else {
      setSmsStage('active');
    }
  }

  function closeSmsModal() {
    api().haptic?.('light');
    const modal = document.getElementById('sms-activation-modal');
    if (modal) modal.style.display = 'none';
  }

  function setSmsStage(stage) {
    const selectStage = document.getElementById('sms-stage-select');
    const activeStage = document.getElementById('sms-stage-active');
    if (stage === 'select') {
      if (selectStage) selectStage.style.display = 'flex';
      if (activeStage) activeStage.style.display = 'none';
    } else {
      if (selectStage) selectStage.style.display = 'none';
      if (activeStage) activeStage.style.display = 'flex';
    }
  }

  async function loadSmsServicesAndCountries() {
    const svcSelect = document.getElementById('sms-service-select');
    const ctrySelect = document.getElementById('sms-country-select');

    if (svcSelect) {
      svcSelect.innerHTML = '<option value="">-- جاري تحميل الخدمات... --</option>';
      svcSelect.disabled = true;
    }
    if (ctrySelect) {
      ctrySelect.innerHTML = '<option value="">-- جاري تحميل الدول... --</option>';
      ctrySelect.disabled = true;
    }

    try {
      const [resSvcs, resCtries] = await Promise.all([
        fetch('/api/sms/services').then(r => r.json()),
        fetch('/api/sms/countries').then(r => r.json())
      ]);

      const isAr = ((window.currentAppLanguage || 'ar') === 'ar');

      if (svcSelect && resSvcs.status === 'ok') {
        let opts = '';
        resSvcs.services.forEach(s => {
          const name = isAr ? (s.name_ar || s.name_en) : s.name_en;
          const icon = s.icon || '📱';
          opts += `<option value="${s.code}">${icon} ${name}</option>`;
        });
        svcSelect.innerHTML = opts;
        svcSelect.disabled = false;
      }

      if (ctrySelect && resCtries.status === 'ok') {
        let opts = '';
        resCtries.countries.forEach(c => {
          const name = isAr ? (c.name_ar || c.name_en) : c.name_en;
          const flag = c.flag_emoji || '🌐';
          opts += `<option value="${c.code}">${flag} ${name}</option>`;
        });
        ctrySelect.innerHTML = opts;
        ctrySelect.disabled = false;
      }

      // Fetch quote for first selection
      await onSmsSelectionChange();
    } catch (e) {
      api().showToast?.('فشل تحميل قائمة خدمات وأرقام SMS');
    }
  }

  async function onSmsSelectionChange() {
    const svcSelect = document.getElementById('sms-service-select');
    const ctrySelect = document.getElementById('sms-country-select');
    const buyBtn = document.getElementById('btn-buy-sms');
    const stockBadge = document.getElementById('sms-quote-stock-badge');
    const priceUsd = document.getElementById('sms-quote-price-usd');
    const priceLocal = document.getElementById('sms-quote-price-local');

    if (!svcSelect || !ctrySelect) return;
    const service = svcSelect.value;
    const country = ctrySelect.value;

    if (!service || !country) {
      if (buyBtn) buyBtn.disabled = true;
      return;
    }

    if (stockBadge) {
      stockBadge.textContent = 'جاري فحص التوفر...';
      stockBadge.style.background = 'rgba(56,189,248,0.15)';
      stockBadge.style.color = 'var(--accent)';
    }
    if (buyBtn) buyBtn.disabled = true;

    try {
      const res = await fetch(`/api/sms/quote?service=${encodeURIComponent(service)}&country=${encodeURIComponent(country)}`);
      const quote = await res.json();
      currentQuote = quote;

      if (quote.status === 'ok' && quote.available) {
        if (stockBadge) {
          stockBadge.textContent = `متوفر (${quote.stock_count} رقم)`;
          stockBadge.style.background = 'rgba(34,197,94,0.15)';
          stockBadge.style.color = '#22c55e';
        }
        if (priceUsd) {
          priceUsd.textContent = `$${quote.sell_price_usd.toFixed(2)}`;
        }
        if (priceLocal && root.StoreAPI?.formatPrice) {
          priceLocal.textContent = root.StoreAPI.formatPrice(quote.sell_price_usd);
        }
        if (buyBtn) buyBtn.disabled = false;
      } else {
        if (stockBadge) {
          stockBadge.textContent = 'غير متوفر حالياً';
          stockBadge.style.background = 'rgba(239,68,68,0.15)';
          stockBadge.style.color = 'var(--danger)';
        }
        if (priceUsd) priceUsd.textContent = '--';
        if (priceLocal) priceLocal.textContent = '';
        if (buyBtn) buyBtn.disabled = true;
      }
    } catch (_) {
      if (stockBadge) {
        stockBadge.textContent = 'تعذر فحص السعر';
        stockBadge.style.background = 'rgba(239,68,68,0.15)';
        stockBadge.style.color = 'var(--danger)';
      }
      if (buyBtn) buyBtn.disabled = true;
    }
  }

  async function executeBuySms() {
    const svcSelect = document.getElementById('sms-service-select');
    const ctrySelect = document.getElementById('sms-country-select');
    const buyBtn = document.getElementById('btn-buy-sms');

    if (!svcSelect || !ctrySelect || !currentQuote || !currentQuote.available) return;

    const service = svcSelect.value;
    const country = ctrySelect.value;
    const requiredUsd = currentQuote.sell_price_usd;

    // Check balance
    const userBal = parseFloat(state().balance || 0);
    if (userBal < requiredUsd) {
      api().haptic?.('error');
      api().showToast?.(`رصيدك الحالي ($${userBal.toFixed(2)}) غير كافٍ. المطلوب: $${requiredUsd.toFixed(2)}`);
      return;
    }

    if (buyBtn) {
      buyBtn.disabled = true;
      buyBtn.innerHTML = '<span>جاري طلب الرقم وتفعيله... ⏳</span>';
    }
    api().haptic?.('medium');

    try {
      const res = await fetch('/api/sms/buy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tg_id: state().userId,
          service,
          country,
          operator: 'any'
        })
      });
      const data = await res.json();

      if (data.status === 'ok') {
        api().haptic?.('success');
        currentSmsOrder = data;

        // Deduct balance locally
        state().balance = Math.max(0, userBal - requiredUsd);
        if (root.StoreAPI?.updateHeaderBalance) {
          root.StoreAPI.updateHeaderBalance();
        }

        // Switch to active view
        setSmsStage('active');

        // Populate phone display
        const phoneEl = document.getElementById('sms-allocated-phone-number');
        if (phoneEl) phoneEl.textContent = data.phone;

        // Reset waiting vs received displays
        const waitBox = document.getElementById('sms-waiting-box');
        const recvBox = document.getElementById('sms-received-box');
        const cancelBtn = document.getElementById('btn-cancel-sms');
        const banBtn = document.getElementById('btn-ban-sms');
        if (waitBox) waitBox.style.display = 'flex';
        if (recvBox) recvBox.style.display = 'none';
        if (cancelBtn) cancelBtn.style.display = 'block';
        if (banBtn) banBtn.style.display = 'block';

        // Start countdown and polling
        startSmsCountdown(data.expires_in_seconds || 900);
        startSmsPolling(data.activation_id);
      } else {
        api().haptic?.('error');
        api().showToast?.(data.error || 'فشل شراء الرقم');
        if (buyBtn) {
          buyBtn.disabled = false;
          buyBtn.innerHTML = '<span>⚡ تفعيل الرقم وشراء الخدمة الآن</span>';
        }
      }
    } catch (e) {
      api().haptic?.('error');
      api().showToast?.('خطأ في الاتصال بالخادم');
      if (buyBtn) {
        buyBtn.disabled = false;
        buyBtn.innerHTML = '<span>⚡ تفعيل الرقم وشراء الخدمة الآن</span>';
      }
    }
  }

  function startSmsCountdown(totalSeconds) {
    if (smsCountdownTimer) clearInterval(smsCountdownTimer);

    let remaining = totalSeconds;
    const timerEl = document.getElementById('sms-countdown-timer');

    function renderTime() {
      const mins = Math.floor(remaining / 60);
      const secs = remaining % 60;
      if (timerEl) {
        timerEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
      }
    }

    renderTime();
    smsCountdownTimer = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        clearInterval(smsCountdownTimer);
        smsCountdownTimer = null;
        if (timerEl) timerEl.textContent = '00:00';
      } else {
        renderTime();
      }
    }, 1000);
  }

  function startSmsPolling(activationId) {
    if (smsPollTimer) clearInterval(smsPollTimer);

    smsPollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/sms/order/${encodeURIComponent(activationId)}`);
        const status = await res.json();

        // 1. Code received
        if (status.status === 'finished' || status.sms_code) {
          clearInterval(smsPollTimer);
          smsPollTimer = null;
          if (smsCountdownTimer) clearInterval(smsCountdownTimer);

          api().haptic?.('success');

          const waitBox = document.getElementById('sms-waiting-box');
          const recvBox = document.getElementById('sms-received-box');
          const codeVal = document.getElementById('sms-received-code-val');
          const fullText = document.getElementById('sms-received-full-text');
          const cancelBtn = document.getElementById('btn-cancel-sms');
          const banBtn = document.getElementById('btn-ban-sms');

          if (waitBox) waitBox.style.display = 'none';
          if (recvBox) recvBox.style.display = 'flex';
          if (codeVal) codeVal.textContent = status.sms_code;
          if (fullText) fullText.textContent = status.sms_text || '';
          if (cancelBtn) cancelBtn.style.display = 'none';
          if (banBtn) banBtn.style.display = 'none';

          if (currentSmsOrder) {
            currentSmsOrder.completed = true;
            currentSmsOrder.sms_code = status.sms_code;
          }

          api().showToast?.('🎉 وصل كود التفعيل بنجاح!');
          return;
        }

        // 2. Canceled or Timed out
        if (status.status === 'canceled' || status.status === 'timeout' || status.refunded) {
          clearInterval(smsPollTimer);
          smsPollTimer = null;
          if (smsCountdownTimer) clearInterval(smsCountdownTimer);

          api().haptic?.('warning');
          api().showToast?.('انتهت صلاحية الرقم وتم استرداد الرصيد إلى محفظتك');

          // Refresh user balance from server
          if (root.loadStorefrontData) root.loadStorefrontData();

          currentSmsOrder = null;
          setSmsStage('select');
        }
      } catch (_) {
        // network retry
      }
    }, 3500);
  }

  function copyAllocatedPhone() {
    const phoneEl = document.getElementById('sms-allocated-phone-number');
    const text = phoneEl ? phoneEl.textContent.trim() : '';
    if (!text) return;

    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
    } else {
      const input = document.createElement('input');
      input.value = text;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
    }

    api().haptic?.('light');
    const hint = document.getElementById('sms-copy-hint');
    if (hint) {
      hint.textContent = '✔ تم نسخ الرقم بنجاح!';
      setTimeout(() => {
        if (hint) hint.textContent = 'اضغط لنسخ الرقم وضعه في التطبيق المطلوب';
      }, 2500);
    }
    api().showToast?.('تم نسخ الرقم');
  }

  function copyReceivedCode() {
    const codeEl = document.getElementById('sms-received-code-val');
    const text = codeEl ? codeEl.textContent.trim() : '';
    if (!text) return;

    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
    } else {
      const input = document.createElement('input');
      input.value = text;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
    }

    api().haptic?.('success');
    api().showToast?.('تم نسخ كود التفعيل');
  }

  async function executeCancelSms() {
    if (!currentSmsOrder || !currentSmsOrder.activation_id) return;

    api().haptic?.('medium');
    const cancelBtn = document.getElementById('btn-cancel-sms');
    if (cancelBtn) cancelBtn.disabled = true;

    try {
      const res = await fetch(`/api/sms/order/${encodeURIComponent(currentSmsOrder.activation_id)}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tg_id: state().userId })
      });
      const data = await res.json();

      if (data.status === 'ok' || data.status === 'already_canceled') {
        if (smsPollTimer) clearInterval(smsPollTimer);
        if (smsCountdownTimer) clearInterval(smsCountdownTimer);

        api().haptic?.('success');
        api().showToast?.(`تم إلغاء الرقم واسترداد $${(data.refunded_usd || currentSmsOrder.sell_price_usd || 0).toFixed(2)} إلى محفظتك بنجاح`);

        // Refresh balance
        if (root.loadStorefrontData) root.loadStorefrontData();

        currentSmsOrder = null;
        setSmsStage('select');
      } else {
        api().showToast?.(data.error || 'تعذر إلغاء الرقم');
        if (cancelBtn) cancelBtn.disabled = false;
      }
    } catch (_) {
      api().showToast?.('خطأ أثناء إلغاء الرقم');
      if (cancelBtn) cancelBtn.disabled = false;
    }
  }

  async function executeBanSms() {
    if (!currentSmsOrder || !currentSmsOrder.activation_id) return;

    api().haptic?.('medium');
    const banBtn = document.getElementById('btn-ban-sms');
    if (banBtn) banBtn.disabled = true;

    try {
      const res = await fetch(`/api/sms/order/${encodeURIComponent(currentSmsOrder.activation_id)}/ban`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tg_id: state().userId })
      });
      const data = await res.json();

      if (data.status === 'ok') {
        if (smsPollTimer) clearInterval(smsPollTimer);
        if (smsCountdownTimer) clearInterval(smsCountdownTimer);

        api().haptic?.('success');
        api().showToast?.(`تم حظر الرقم واسترداد $${(data.refunded_usd || currentSmsOrder.sell_price_usd || 0).toFixed(2)} إلى محفظتك`);

        // Refresh balance
        if (root.loadStorefrontData) root.loadStorefrontData();

        currentSmsOrder = null;
        setSmsStage('select');
      } else {
        api().showToast?.(data.error || 'تعذر الإبلاغ عن حظر الرقم');
        if (banBtn) banBtn.disabled = false;
      }
    } catch (_) {
      api().showToast?.('خطأ أثناء الإبلاغ عن حظر الرقم');
      if (banBtn) banBtn.disabled = false;
    }
  }

  // --- Admin SMS Controls ---
  async function openAdminSmsModal() {
    api().haptic?.('medium');
    const modal = document.getElementById('admin-sms-modal');
    if (!modal) return;

    modal.style.display = 'flex';
    api().pushNav?.('admin_sms_modal', closeAdminSmsModal);
    await loadAdminSmsSettings();
  }

  function closeAdminSmsModal() {
    api().haptic?.('light');
    const modal = document.getElementById('admin-sms-modal');
    if (modal) modal.style.display = 'none';
  }

  async function loadAdminSmsSettings() {
    const balVal = document.getElementById('admin-5sim-balance-val');
    const svcsList = document.getElementById('admin-sms-services-list');
    const ctriesList = document.getElementById('admin-sms-countries-list');

    if (balVal) balVal.textContent = 'جاري الفحص...';
    if (svcsList) svcsList.innerHTML = '<div style="color: var(--hint); font-size: 12px;">جاري تحميل الخدمات...</div>';
    if (ctriesList) ctriesList.innerHTML = '<div style="color: var(--hint); font-size: 12px;">جاري تحميل المناطق...</div>';

    try {
      const res = await fetch('/api/admin/sms/settings', {
        headers: { 'X-Telegram-User-Id': String(state().userId || 0) }
      });
      const data = await res.json();

      if (data.status === 'ok') {
        if (balVal) {
          const balRub = data.balance?.balance_rub || 0;
          const balUsd = data.balance?.balance_usd || 0;
          balVal.textContent = `${balRub.toFixed(1)} RUB (~$${balUsd.toFixed(2)})`;
        }

        // Services
        if (svcsList && data.services) {
          let sHtml = '';
          data.services.forEach(s => {
            const checked = s.is_enabled ? 'checked' : '';
            sHtml += `
              <div style="display: flex; justify-content: space-between; align-items: center; background: var(--input-bg); padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border);">
                <div>
                  <span style="font-weight: 700; font-size: 13px;">${s.name_ar || s.name_en}</span>
                  <span style="font-size: 11px; color: var(--hint); margin-inline-start: 6px;">(${s.code})</span>
                </div>
                <label class="switch-toggle" style="position: relative; display: inline-block; width: 38px; height: 22px;">
                  <input type="checkbox" ${checked} onchange="toggleAdminSmsService('${s.code}', this.checked)">
                  <span class="slider-round"></span>
                </label>
              </div>`;
          });
          svcsList.innerHTML = sHtml;
        }

        // Countries
        if (ctriesList && data.countries) {
          let cHtml = '';
          data.countries.forEach(c => {
            const checked = c.is_enabled ? 'checked' : '';
            cHtml += `
              <div style="display: flex; justify-content: space-between; align-items: center; background: var(--input-bg); padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border);">
                <div>
                  <span style="margin-inline-end: 6px;">${c.flag || '🌐'}</span>
                  <span style="font-weight: 700; font-size: 13px;">${c.name_ar || c.name_en}</span>
                  <span style="font-size: 11px; color: var(--hint); margin-inline-start: 6px;">(${c.code})</span>
                </div>
                <label class="switch-toggle" style="position: relative; display: inline-block; width: 38px; height: 22px;">
                  <input type="checkbox" ${checked} onchange="toggleAdminSmsCountry('${c.code}', this.checked)">
                  <span class="slider-round"></span>
                </label>
              </div>`;
          });
          ctriesList.innerHTML = cHtml;
        }
      }
    } catch (_) {
      api().showToast?.('فشل تحميل إعدادات أرقام 5sim للمشرف');
    }
  }

  async function toggleAdminSmsService(serviceCode, isEnabled) {
    api().haptic?.('light');
    try {
      const res = await fetch('/api/admin/sms/services/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: state().userId,
          service_code: serviceCode,
          is_enabled: isEnabled
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().showToast?.(`تم ${isEnabled ? 'تفعيل' : 'تعطيل'} خدمة ${serviceCode}`);
      } else {
        api().showToast?.(data.error || 'فشل تعديل حالة الخدمة');
      }
    } catch (_) {
      api().showToast?.('خطأ أثناء تعديل حالة الخدمة');
    }
  }

  async function toggleAdminSmsCountry(countryCode, isEnabled) {
    api().haptic?.('light');
    try {
      const res = await fetch('/api/admin/sms/countries/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: state().userId,
          country_code: countryCode,
          is_enabled: isEnabled
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().showToast?.(`تم ${isEnabled ? 'تفعيل' : 'تعطيل'} منطقة ${countryCode}`);
      } else {
        api().showToast?.(data.error || 'فشل تعديل حالة المنطقة');
      }
    } catch (_) {
      api().showToast?.('خطأ أثناء تعديل حالة المنطقة');
    }
  }

  // --- Export Namespace ---
  root.SmsModule = {
    openSmsModal,
    closeSmsModal,
    loadSmsServicesAndCountries,
    onSmsSelectionChange,
    executeBuySms,
    copyAllocatedPhone,
    copyReceivedCode,
    executeCancelSms,
    executeBanSms,
    openAdminSmsModal,
    closeAdminSmsModal,
    loadAdminSmsSettings,
    toggleAdminSmsService,
    toggleAdminSmsCountry
  };

})(typeof window !== 'undefined' ? window : globalThis);
