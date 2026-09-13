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
      const rate = state().sypRate || 14500;
      const sypVal = Math.round(num * rate);
      return `${sypVal.toLocaleString('en-US')} ل.س`;
    } else if (curr === 'STARS') {
      const starsVal = Math.round(num * 100);
      return `${starsVal} ⭐`;
    }
    return `$${num.toFixed(2)}`;
  }

  // --- Render Wallet Balances & Profile VIP ---
  function renderWalletBalances(userData = null) {
    const data = userData || state().userData;
    if (!data) return;
    state().userData = data;

    const balanceUsd = Number(data.top_up_amount || 0) - Number(data.consume_records || 0);
    const sypRate = state().sypRate || 14500;
    const balanceSyp = Math.round(balanceUsd * sypRate);
    const balanceStars = Math.round(balanceUsd * 100);

    // Update Top App Bar & Wallet Tab displays
    const usdEl = document.getElementById('wallet-balance-usd');
    if (usdEl) usdEl.textContent = `$${balanceUsd.toFixed(2)}`;

    const sypEl = document.getElementById('wallet-balance-syp');
    if (sypEl) sypEl.textContent = `${balanceSyp.toLocaleString('en-US')} ل.س`;

    const starsEl = document.getElementById('wallet-balance-stars');
    if (starsEl) starsEl.textContent = `${balanceStars} ⭐`;

    // Render VIP Tier & Gamified Progress
    renderVipTier(data, balanceUsd);
  }

  function renderVipTier(data, balanceUsd) {
    const spentUsd = Number(data.consume_records || 0);
    let tier = 'Standard';
    let discount = 0;
    let nextThreshold = 50;
    let progress = 0;

    if (spentUsd >= 500) {
      tier = 'Diamond';
      discount = 10;
      nextThreshold = 500;
      progress = 100;
    } else if (spentUsd >= 200) {
      tier = 'Gold';
      discount = 7;
      nextThreshold = 500;
      progress = Math.min(100, Math.round((spentUsd / 500) * 100));
    } else if (spentUsd >= 50) {
      tier = 'Silver';
      discount = 4;
      nextThreshold = 200;
      progress = Math.min(100, Math.round((spentUsd / 200) * 100));
    } else {
      tier = 'Standard';
      discount = 0;
      nextThreshold = 50;
      progress = Math.min(100, Math.round((spentUsd / 50) * 100));
    }

    const tierBadge = document.getElementById('user-vip-badge');
    if (tierBadge) tierBadge.textContent = `VIP: ${tier}`;

    const progressBar = document.getElementById('vip-progress-fill');
    if (progressBar) progressBar.style.width = `${progress}%`;
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
    const input = document.getElementById('recharge-amount-input');
    if (input) input.value = rechargeAmount;
    updateRechargeButtonText();
  }

  function updateRechargeButtonText() {
    const btn = document.getElementById('btn-submit-recharge');
    if (!btn) return;
    const isAr = (state().currentAppLanguage === 'ar');

    let label = isAr ? `شحن ${rechargeAmount}$ عبر ` : `Recharge $${rechargeAmount} via `;
    if (selectedRechargeMethod === 'stars') label += (isAr ? 'تيليجرام ستارز' : 'Telegram Stars');
    else if (selectedRechargeMethod === 'crypto') label += 'USDT (BEP-20)';
    else if (selectedRechargeMethod === 'shamcash') label += `شام كاش (${selectedShamCurrency})`;
    else if (selectedRechargeMethod === 'syriatelcash') label += 'سيريتل كاش';

    btn.textContent = label;
  }

  async function submitRechargeRequest() {
    const input = document.getElementById('recharge-amount-input');
    const amt = parseFloat(input?.value || rechargeAmount);
    if (!amt || amt <= 0) {
      api().showToast('يرجى إدخال مبلغ شحن صحيح');
      return;
    }

    api().haptic?.('heavy');
    const btn = document.getElementById('btn-submit-recharge');
    if (btn) btn.disabled = true;

    try {
      if (selectedRechargeMethod === 'stars') {
        const res = await fetch('/api/wallet/stars/invoice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount_usd: amt })
        });
        const data = await res.json();
        if (data.invoice_link && api().getTg()?.openInvoice) {
          api().getTg().openInvoice(data.invoice_link, (status) => {
            if (status === 'paid') {
              api().haptic?.('success');
              api().fireConfetti?.();
              api().showToast('تم دفع الفاتورة وشحن رصيدك بنجاح!');
              renderWalletBalances();
            }
          });
        } else if (data.invoice_link) {
          root.location.href = data.invoice_link;
        } else {
          api().showToast(data.error || 'فشل توليد رابط نجوم تيليجرام');
        }
      } else if (selectedRechargeMethod === 'shamcash' || selectedRechargeMethod === 'syriatelcash') {
        const res = await fetch('/api/wallet/sam/invoice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount: amt,
            method: selectedRechargeMethod === 'shamcash' ? 'shamcash' : 'syriatel',
            currency: selectedShamCurrency
          })
        });
        const data = await res.json();
        if (data.paymentUrl) {
          const win = root.open(data.paymentUrl, '_blank');
          if (!win) root.location.href = data.paymentUrl;
          api().showToast('جاري فتح صفحة الدفع الآمنة...');
        } else {
          api().showToast(data.error || 'فشل إنشاء فاتورة الدفع الإلكتروني');
        }
      } else if (selectedRechargeMethod === 'crypto') {
        const res = await fetch('/api/wallet/crypto/deposit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount_usd: amt })
        });
        const data = await res.json();
        if (data.address) {
          showCryptoDepositModal(data.address, amt);
        } else {
          api().showToast('فشل الحصول على عنوان الإيداع');
        }
      }
    } catch (e) {
      api().showToast('حدث خطأ أثناء معالجة طلب الشحن');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function showCryptoDepositModal(address, amt) {
    const modal = document.getElementById('modal-crypto-deposit');
    if (!modal) return;
    const addrEl = document.getElementById('crypto-deposit-addr');
    if (addrEl) addrEl.textContent = address;
    modal.style.display = 'flex';
    api().pushNav('crypto_deposit_modal', () => { modal.style.display = 'none'; });
  }

  // --- Gift Vouchers ---
  async function submitRedeemVoucher() {
    const input = document.getElementById('voucher-code-input');
    const code = (input?.value || '').trim();
    if (!code) {
      api().showToast('يرجى إدخال كود القسيمة');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/wallet/voucher/redeem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().fireConfetti?.();
        api().showToast(`تم شحن رصيدك بنجاح بمبلغ $${data.amount_usd}!`);
        if (input) input.value = '';
        renderWalletBalances();
      } else {
        api().showToast(data.error || 'كود القسيمة غير صالح أو تم استخدامه');
      }
    } catch (_) {
      api().showToast('فشل التحقق من القسيمة');
    }
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
    submitRechargeRequest,
    submitRedeemVoucher,
    openReceiptModal,
    closeReceiptPreviewModal,
    openVipBenefitsModal,
    closeVipBenefitsModal
  };

})(typeof window !== 'undefined' ? window : globalThis);
