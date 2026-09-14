/**
 * GH Store - Wallet, Top-Up Rails, Multi-Currency, & Receipts Module (wallet.js)
 * 
 * Provides:
 * - Real-time wallet balances rendering (USD, Syrian Pounds, Telegram Stars)
 * - Multi-currency preferences & dynamic exchange rate formatting
 * - Payment rails orchestration:
 *   1. Telegram Stars Invoicing (native WebApp openInvoice)
 *   2. Crypto BEP-20 (USDT) address display & 1-tap copy
 *   3. ShamCash & Syriatel Cash payment invoices with USD/SYP currency toggles
 * - VIP Gamified tier progression bar (Standard, Silver, Gold, Diamond)
 * - Gift voucher redemption & in-app receipt PDF rendering engine
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};

  let selectedRechargeMethod = 'shamcash';
  let selectedShamCurrency = 'USD';
  let rechargeAmount = 10;

  // --- Currency Preference & Money Formatting ---
  function setCurrencyPreference(curr) {
    api().haptic?.('selection');
    state().currentCurrency = curr || 'USD';
    try {
      root.localStorage?.setItem('ghstore_currency', curr);
      api().cloudStorageSet?.('ghstore_currency', curr);
    } catch (_) {}
    renderWalletBalances();
  }

  function formatMoney(amountUsd, targetCurrency = null) {
    const curr = targetCurrency || state().currentCurrency || 'USD';
    const num = Number(amountUsd || 0);

    if (curr === 'SYP') {
      const rate = Number(state().sypRate);
      if (!Number.isFinite(rate) || rate <= 0) return `$${num.toFixed(2)} USD`;
      const sypVal = Math.round(num * rate);
      return `${sypVal.toLocaleString('en-US')} ل.س`;
    } else if (curr === 'STARS') {
      const rate = Number(state().starsUsdRate);
      if (!Number.isFinite(rate) || rate <= 0) return `$${num.toFixed(2)} USD`;
      const starsVal = Math.round(num / rate);
      return `${starsVal} ⭐`;
    }
    return `$${num.toFixed(2)}`;
  }

  // --- Render Wallet Balances & Profile VIP ---
  function renderWalletBalances(userData = null) {
    const data = userData || state().userData;
    if (!data) return;
    state().userData = data;

    const balanceUsd = typeof data.balance === 'number'
      ? data.balance
      : (data.balance !== undefined
          ? Number(data.balance)
          : (Number(data.top_up_amount || 0) - Number(data.consume_records || 0)));
    const sypRate = Number(data.syp_rate);
    state().sypRate = Number.isFinite(sypRate) && sypRate > 0 ? sypRate : null;
    const balanceSyp = state().sypRate ? Math.round(balanceUsd * state().sypRate) : null;
    state().starsUsdRate = Number(data.stars_usd_rate) > 0 ? Number(data.stars_usd_rate) : null;
    const balanceStars = state().starsUsdRate ? Math.round(balanceUsd / state().starsUsdRate) : null;
    const isAr = (state().currentAppLanguage === 'ar');
    const balDisplay = `$${balanceUsd.toFixed(2)}`;

    // 1. Top App Bar Balance & Plus Button
    const topBalEl = document.getElementById('top-balance-str');
    if (topBalEl) topBalEl.textContent = balDisplay;
    const plusBtn = document.getElementById('top-balance-plus');
    if (plusBtn) plusBtn.style.display = data.is_admin ? 'none' : 'inline-block';

    // 2. Wallet Tab Hero & Approximate Displays
    const heroBalEl = document.getElementById('wallet-balance-hero');
    if (heroBalEl) heroBalEl.textContent = balDisplay;
    const approxEl = document.getElementById('wallet-balance-approx');
    if (approxEl) {
      approxEl.hidden = balanceSyp === null;
      approxEl.textContent = balanceSyp === null ? '' : isAr
        ? `≈ ${balanceSyp.toLocaleString('en-US')} ل.س · جاهز للشراء`
        : `≈ ${balanceSyp.toLocaleString('en-US')} SYP · Ready`;
    }

    // 3. Settings View Financial Card
    const finCard = document.getElementById('settings-finance-card');
    if (finCard) finCard.style.display = 'grid';
    const cardBal = document.getElementById('settings-card-balance');
    if (cardBal) cardBal.textContent = balDisplay;
    const spentUsd = Number(data.total_spent || data.consume_records || 0);
    const cardSpent = document.getElementById('settings-card-spent');
    if (cardSpent) cardSpent.textContent = `$${spentUsd.toFixed(2)}`;

    // 4. Admin vs User Wallet Section Views
    const userWalletSection = document.getElementById('wallet-user-recharge-section');
    const adminWalletSection = document.getElementById('wallet-admin-management-section');
    if (data.is_admin) {
      if (userWalletSection) userWalletSection.style.display = 'none';
      if (adminWalletSection) adminWalletSection.style.display = 'block';
      const tabLabel = document.getElementById('i18n-tab-wallet');
      if (tabLabel) tabLabel.textContent = isAr ? 'الخزينة والأرصدة' : 'Reserves & Users';
    } else {
      if (userWalletSection) userWalletSection.style.display = 'block';
      if (adminWalletSection) adminWalletSection.style.display = 'none';
      const tabLabel = document.getElementById('i18n-tab-wallet');
      if (tabLabel) tabLabel.textContent = isAr ? 'المحفظة' : 'Wallet';
    }

    // 5. Test/Legacy compatibility elements
    const usdEl = document.getElementById('wallet-balance-usd');
    if (usdEl) usdEl.textContent = balDisplay;
    const sypEl = document.getElementById('wallet-balance-syp');
    if (sypEl) sypEl.textContent = balanceSyp === null ? '—' : `${balanceSyp.toLocaleString('en-US')} ل.س`;
    const starsEl = document.getElementById('wallet-balance-stars');
    if (starsEl) starsEl.textContent = balanceStars === null ? '—' : `${balanceStars} ⭐`;

    // Render VIP Tier & Gamified Progress
    renderVipTier(data, balanceUsd);
  }

  function renderVipTier(data, balanceUsd) {
    // Current tier comes from the server. Do not invent future discount thresholds.
    const tier = data.vip_tier || '';
    const progress = document.getElementById('wallet-vip-progress-card');
    if (progress) progress.hidden = true;
    const tierBadge = document.getElementById('user-vip-badge');
    if (tierBadge) tierBadge.textContent = `VIP: ${tier}`;
  }

  // --- Top-Up / Recharge Logic ---
  function selectRechargeMethod(method) {
    api().haptic?.('pop');
    selectedRechargeMethod = method;

    ['stars', 'crypto', 'shamcash', 'syriatelcash'].forEach(m => {
      const card = document.getElementById(`method-card-${m}`);
      if (card) card.classList.toggle('active', m === method);
    });

    const shamBox = document.getElementById('shamcash-currency-box');
    if (shamBox) {
      shamBox.style.display = (method === 'shamcash') ? 'flex' : 'none';
    }

    updateRechargeButtonText();
  }

  function setShamCurrency(curr) {
    api().haptic?.('light');
    selectedShamCurrency = curr;

    const btnUsd = document.getElementById('btn-sham-curr-usd');
    const btnSyp = document.getElementById('btn-sham-curr-syp');
    if (btnUsd) btnUsd.classList.toggle('active', curr === 'USD');
    if (btnSyp) btnSyp.classList.toggle('active', curr === 'SYP');

    updateRechargeButtonText();
  }

  function setRechargeAmount(amt) {
    api().haptic?.('light');
    rechargeAmount = Number(amt) || 10;
    const input = document.getElementById('custom-topup-input') || document.getElementById('recharge-amount-input');
    if (input) input.value = rechargeAmount.toFixed(2);
    [1, 5, 10, 25, 50, 100].forEach(a => {
      const chip = document.getElementById(`chip-amt-${a}`);
      if (chip) chip.classList.toggle('active', a === rechargeAmount);
    });
    updateRechargeButtonText();
  }

  function selectTopupAmount(amt) {
    setRechargeAmount(amt);
  }

  function onCustomAmountInput() {
    const input = document.getElementById('custom-topup-input');
    const val = parseFloat(input?.value);
    if (!isNaN(val) && val > 0) {
      rechargeAmount = val;
      [1, 5, 10, 25, 50, 100].forEach(a => {
        const chip = document.getElementById(`chip-amt-${a}`);
        if (chip) chip.classList.toggle('active', Math.abs(a - rechargeAmount) < 0.01);
      });
      updateRechargeButtonText();
    }
  }

  function updateRechargeButtonText() {
    const btn = document.getElementById('btn-execute-recharge') || document.getElementById('btn-submit-recharge');
    const textEl = document.getElementById('recharge-btn-text');
    const isAr = (state().currentAppLanguage === 'ar');

    let methodLabel = '';
    if (selectedRechargeMethod === 'stars') methodLabel = isAr ? 'نجوم تيليجرام ⭐' : 'Telegram Stars ⭐';
    else if (selectedRechargeMethod === 'crypto') methodLabel = 'USDT (BEP-20)';
    else if (selectedRechargeMethod === 'shamcash') methodLabel = isAr ? `شام كاش (${selectedShamCurrency})` : `Sham Cash (${selectedShamCurrency})`;
    else if (selectedRechargeMethod === 'syriatelcash') methodLabel = isAr ? 'سيريتل كاش' : 'Syriatel Cash';

    const label = isAr ? `شحن ${rechargeAmount.toFixed(2)}$ عبر ${methodLabel}` : `Recharge $${rechargeAmount.toFixed(2)} via ${methodLabel}`;
    if (textEl) textEl.textContent = label;
    else if (btn) btn.textContent = label;
  }

  let activeInvoiceData = null;

  async function executeSelectedRecharge() {
    const customInp = document.getElementById('custom-topup-input');
    const amt = parseFloat(customInp?.value || rechargeAmount);
    if (!amt || amt <= 0) {
      api().showToast('يرجى إدخال مبلغ شحن صحيح');
      return;
    }

    const btn = document.getElementById('btn-execute-recharge') || document.getElementById('btn-submit-recharge');
    const textEl = document.getElementById('recharge-btn-text');
    if (btn) btn.disabled = true;
    if (textEl) textEl.textContent = (state().currentAppLanguage === 'ar') ? 'جاري تجهيز الفاتورة...' : 'Generating invoice...';
    api().haptic?.('heavy');

    try {
      const res = await fetch('/api/invoice/topup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tg_id: state().userId,
          amount: amt,
          method: selectedRechargeMethod,
          currency: (selectedRechargeMethod === 'shamcash') ? selectedShamCurrency : ((selectedRechargeMethod === 'syriatelcash') ? 'SYP' : 'USD')
        })
      });
      const data = await res.json();
      if (btn) btn.disabled = false;
      updateRechargeButtonText();

      if (data.type === 'stars' && data.invoice_link) {
        if (api().getTg()?.openInvoice) {
          api().getTg().openInvoice(data.invoice_link, (status) => {
            if (status === 'paid') {
              api().haptic?.('success');
              api().fireConfetti?.();
              api().showToast(state().currentAppLanguage === 'ar' ? `تم شحن +$${amt.toFixed(2)} بنجاح!` : `+$${amt.toFixed(2)} Credited!`);
              if (root.loadUserData) root.loadUserData();
            } else if (status === 'failed') {
              api().showToast(state().currentAppLanguage === 'ar' ? 'فشلت عملية الدفع' : 'Payment failed');
            }
          });
        } else {
          root.open(data.invoice_link, '_blank');
        }
      } else if (data.type === 'url' || data.type === 'crypto' || data.status === 'ok') {
        openInvoicePage(data);
      } else {
        api().showToast(data.error || 'تعذر إنشاء فاتورة الشحن');
      }
    } catch (e) {
      if (btn) btn.disabled = false;
      updateRechargeButtonText();
      api().showToast('خطأ في الاتصال أثناء الشحن');
    }
  }

  function submitRechargeRequest() {
    return executeSelectedRecharge();
  }

  function openInvoicePage(invoiceData) {
    activeInvoiceData = invoiceData;
    api().haptic?.('pop');

    document.querySelectorAll('.tab-view').forEach(el => el.style.display = 'none');
    const view = document.getElementById('view-invoice');
    if (view) view.style.display = 'block';
    window.scrollTo(0, 0);

    const invId = invoiceData.invoice_id ? `#INV-${invoiceData.invoice_id}` : '#INV-TOPUP';
    const idEl = document.getElementById('invoice-id-display');
    if (idEl) idEl.innerText = invId;

    const nameEl = document.getElementById('invoice-method-name');
    const subEl = document.getElementById('invoice-method-sub');
    const prov = invoiceData.provider || selectedRechargeMethod;
    const isAr = (state().currentAppLanguage === 'ar');

    if (prov === 'shamcash') {
      if (nameEl) nameEl.innerText = isAr ? 'شام كاش' : 'Sham Cash';
      if (subEl) subEl.innerText = isAr ? 'دفع مباشر وفوري عبر بنك شام كاش' : 'Direct payment via Sham Cash';
    } else if (prov === 'syriatelcash') {
      if (nameEl) nameEl.innerText = isAr ? 'سيرياتيل كاش' : 'Syriatel Cash';
      if (subEl) subEl.innerText = isAr ? 'دفع بالليرة السورية (SYP)' : 'Direct payment in SYP';
    } else {
      if (nameEl) nameEl.innerText = 'USDT (BEP-20)';
      if (subEl) subEl.innerText = 'BNB Smart Chain (BEP-20)';
    }

    const usdEl = document.getElementById('invoice-amount-usd');
    const localEl = document.getElementById('invoice-amount-local');
    const amt = Number(invoiceData.amount || rechargeAmount || 10);
    if (usdEl) usdEl.innerText = `$${amt.toFixed(2)} USD`;

    if (invoiceData.invoice_amount && invoiceData.currency === 'SYP') {
      if (localEl) {
        localEl.innerText = `≈ ${Number(invoiceData.invoice_amount).toLocaleString()} ${isAr ? 'ل.س' : 'SYP'}`;
        localEl.style.display = 'block';
      }
    } else {
      if (localEl) localEl.style.display = 'none';
    }

    const bep20Box = document.getElementById('invoice-crypto-bep20-box');
    const addrEl = document.getElementById('invoice-crypto-address');
    if (invoiceData.address) {
      if (addrEl) addrEl.innerText = invoiceData.address;
      if (bep20Box) bep20Box.style.display = 'block';
    } else {
      if (bep20Box) bep20Box.style.display = 'none';
    }

    const samTxnBox = document.getElementById('invoice-sam-txn-box');
    if (samTxnBox) {
      samTxnBox.style.display = (prov === 'shamcash' || prov === 'syriatelcash') ? 'block' : 'none';
    }

    api().pushNav('invoice_view', closeInvoicePage);
  }

  function closeInvoicePage() {
    api().haptic?.('light');
    const view = document.getElementById('view-invoice');
    if (view) view.style.display = 'none';
    const walletView = document.getElementById('view-wallet');
    if (walletView) walletView.style.display = 'block';
    if (api().navStack.length > 0 && api().navStack[api().navStack.length - 1].name === 'invoice_view') {
      api().popNav();
    }
  }

  function openActiveInvoiceGateway() {
    if (activeInvoiceData?.url) {
      api().haptic?.('pop');
      if (api().getTg()?.openLink) api().getTg().openLink(activeInvoiceData.url);
      else root.open(activeInvoiceData.url, '_blank');
    } else {
      api().showToast('لا يوجد رابط دفع متاح');
    }
  }

  async function checkActiveInvoiceStatus() {
    if (!activeInvoiceData?.invoice_id && !activeInvoiceData?.id) {
      api().showToast('لا توجد فاتورة نشطة للتحقق منها');
      return;
    }
    const invId = activeInvoiceData.invoice_id || activeInvoiceData.id;
    const prov = activeInvoiceData.provider || selectedRechargeMethod;
    const txnRef = (document.getElementById('invoice-sam-txn-input')?.value || '').trim();

    api().haptic?.('medium');
    const btn = document.getElementById('btn-check-invoice-status');
    if (btn) btn.disabled = true;
    api().showToast('جاري التحقق من حالة الفاتورة...');

    try {
      const res = await fetch('/api/invoice/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tg_id: state().userId,
          invoice_id: String(invId),
          method: prov,
          transaction_ref: txnRef
        })
      });
      const d = await res.json();
      if (btn) btn.disabled = false;

      if (d.paid || d.status === 'paid' || d.status === 'completed') {
        api().haptic?.('success');
        api().fireConfetti?.();
        api().showToast('تم تأكيد الدفع وشحن الرصيد بنجاح! ✅');
        closeInvoicePage();
        if (root.loadUserData) root.loadUserData();
      } else {
        api().showToast(d.message || 'لم يتم تأكيد وصول الدفع بعد، يرجى الانتظار دقيقة.');
      }
    } catch (_) {
      if (btn) btn.disabled = false;
      api().showToast('خطأ أثناء التحقق من الفاتورة');
    }
  }

  function copyActiveInvoiceLink() {
    const url = activeInvoiceData?.url || '';
    if (url) {
      navigator.clipboard?.writeText(url);
      api().haptic?.('light');
      api().showToast('تم نسخ رابط الدفع!');
    }
  }

  function copyCryptoAddress() {
    const addr = document.getElementById('invoice-crypto-address')?.innerText || activeInvoiceData?.address || '';
    if (addr) {
      navigator.clipboard?.writeText(addr);
      api().haptic?.('light');
      api().showToast('تم نسخ عنوان المحفظة!');
    }
  }

  // --- Gift Vouchers ---
  async function submitVoucherRedeem() {
    const input = document.getElementById('voucher-code-input');
    const code = (input?.value || '').trim();
    if (!code) {
      api().showToast('يرجى إدخال كود القسيمة');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/voucher/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tg_id: state().userId, code })
      });
      const data = await res.json();
      if (data.status === 'success' || data.status === 'ok') {
        api().haptic?.('success');
        api().fireConfetti?.();
        api().showToast(`تم شحن رصيدك بنجاح بمبلغ $${data.amount}!`);
        if (input) input.value = '';
        if (root.loadUserData) root.loadUserData();
      } else {
        api().showToast(data.error || 'كود القسيمة غير صالح أو تم استخدامه مسبقاً');
      }
    } catch (_) {
      api().showToast('فشل التحقق من القسيمة');
    }
  }

  const submitRedeemVoucher = submitVoucherRedeem;

  function scanVoucherQr() {
    const tg = api().getTg();
    if (tg?.showScanQrPopup) {
      tg.showScanQrPopup({ text: 'امسح رمز QR لقسيمة الهدية' }, (text) => {
        if (text) {
          const input = document.getElementById('voucher-code-input');
          if (input) input.value = text.trim().toUpperCase();
          tg.closeScanQrPopup();
          submitVoucherRedeem();
        }
        return true;
      });
    } else {
      api().showToast('ميزة مسح QR متاحة داخل تطبيق تيليجرام');
    }
  }

  // --- Currency & Theme Controls ---
  async function selectDisplayCurrency(code) {
    api().haptic?.('light');
    setCurrencyPreference(code);
    document.querySelectorAll('#currency-picker-chips .filter-chip').forEach(el => {
      el.classList.toggle('active', el.textContent.includes(code));
    });
    if (state().userId) {
      try {
        await fetch('/api/user/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tg_id: state().userId, currency: code })
        });
      } catch (_) {}
    }
  }

  function setAppTheme(theme) {
    api().haptic?.('light');
    document.documentElement.setAttribute('data-theme', theme);
    try {
      root.localStorage?.setItem('ghstore_theme', theme);
      api().cloudStorageSet?.('ghstore_theme', theme);
    } catch (_) {}
    document.querySelectorAll('#theme-picker-chips .filter-chip').forEach(el => {
      el.classList.toggle('active', el.id === `btn-theme-${theme}`);
    });
  }

  // --- Official Receipt Modal ---
  function openReceiptModal(orderId) {
    api().haptic?.('light');
    const modal = document.getElementById('modal-receipt-preview');
    if (!modal) return;
    modal.style.display = 'flex';
    api().pushNav('receipt_modal', closeReceiptPreviewModal);
  }

  function closeReceiptPreviewModal() {
    const modal = document.getElementById('modal-receipt-preview');
    if (modal) modal.style.display = 'none';
  }

  function openVipBenefitsModal() {
    api().haptic?.('pop');
    const modal = document.getElementById('modal-vip-benefits');
    if (modal) {
      modal.style.display = 'flex';
      api().pushNav('vip_modal', closeVipBenefitsModal);
    }
  }

  function closeVipBenefitsModal() {
    const modal = document.getElementById('modal-vip-benefits');
    if (modal) modal.style.display = 'none';
  }

  // --- Export Namespace ---
  root.WalletModule = {
    setCurrencyPreference,
    formatMoney,
    renderWalletBalances,
    selectRechargeMethod,
    setShamCurrency,
    setRechargeAmount,
    selectTopupAmount,
    onCustomAmountInput,
    updateRechargeButtonText,
    executeSelectedRecharge,
    submitRechargeRequest,
    openInvoicePage,
    closeInvoicePage,
    openActiveInvoiceGateway,
    checkActiveInvoiceStatus,
    copyActiveInvoiceLink,
    copyCryptoAddress,
    submitVoucherRedeem,
    submitRedeemVoucher,
    scanVoucherQr,
    selectDisplayCurrency,
    setAppTheme,
    openReceiptModal,
    closeReceiptPreviewModal,
    openVipBenefitsModal,
    closeVipBenefitsModal
  };

  root.renderWalletBalances = renderWalletBalances;

})(typeof window !== 'undefined' ? window : globalThis);
