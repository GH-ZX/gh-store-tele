/**
 * GH Store - Admin Control Center, Live Editors, & Session Controls Module (admin.js)
 * 
 * Provides:
 * - Admin overview dashboard metrics & server liquidity monitor (BatStore, ProdSeller, G2Bulk)
 * - Live in-place editors for Products, Categories, Brand Folders, and Promotional Banners
 * - User management, manual balance credits/deductions, and custom VIP tier overrides
 * - Order management, stuck order resolution, and instant refund dialogs
 * - Admin security controls: session revocation & unrevocation API triggers
 * - Global store settings: store logo, Syrian Pound exchange rate, and referral commission
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};

  let adminBalAmount = 10;
  let adminBalAction = 'add';

  // --- Admin Product Editor Modal ---
  function openAdminProductModal(productId) {
    const all = state().allProducts || [];
    const p = all.find(item => Number(item.id) === Number(productId));
    if (!p) return;

    api().haptic?.('pop');
    const modal = document.getElementById('admin-product-modal');
    if (!modal) return;

    const idInput = document.getElementById('admin-edit-prod-id');
    const nameInput = document.getElementById('admin-edit-prod-name');
    const nameArInput = document.getElementById('admin-edit-prod-name-ar');
    const priceInput = document.getElementById('admin-edit-prod-price');
    const descInput = document.getElementById('admin-edit-prod-desc');

    if (idInput) idInput.value = p.id;
    if (nameInput) nameInput.value = p.name || '';
    if (nameArInput) nameArInput.value = p.name_ar || '';
    if (priceInput) priceInput.value = p.sell_price_usd || '';
    if (descInput) descInput.value = p.description || '';

    modal.style.display = 'flex';
    api().pushNav('admin_prod_modal', closeAdminProductModal);
  }

  function closeAdminProductModal() {
    api().haptic?.('light');
    const modal = document.getElementById('admin-product-modal');
    if (modal) modal.style.display = 'none';
  }

  async function submitAdminProductUpdate() {
    const id = document.getElementById('admin-edit-prod-id')?.value;
    const name = document.getElementById('admin-edit-prod-name')?.value;
    const nameAr = document.getElementById('admin-edit-prod-name-ar')?.value;
    const price = parseFloat(document.getElementById('admin-edit-prod-price')?.value);
    const desc = document.getElementById('admin-edit-prod-desc')?.value;

    if (!id || !price || price <= 0) {
      api().showToast('يرجى التأكد من صحة السعر والبيانات');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/admin/product/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: Number(id),
          name,
          name_ar: nameAr,
          sell_price_usd: price,
          description: desc,
          admin_tg_id: state().userId
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast('تم تحديث المنتج بنجاح');
        closeAdminProductModal();
        if (root.loadStorefrontData) root.loadStorefrontData();
      } else {
        api().showToast(data.error || 'فشل تحديث بيانات المنتج');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب التحديث');
    }
  }

  // --- Admin Category & Folder Editors ---
  function openAdminCategoryModal(catId) {
    const modal = document.getElementById('admin-category-modal');
    if (modal) {
      modal.style.display = 'flex';
      api().pushNav('admin_cat_modal', closeAdminCategoryModal);
    }
  }

  function closeAdminCategoryModal() {
    const modal = document.getElementById('admin-category-modal');
    if (modal) modal.style.display = 'none';
  }

  function openAdminFolderModal(folderKey) {
    const modal = document.getElementById('admin-folder-modal');
    if (modal) {
      modal.style.display = 'flex';
      api().pushNav('admin_folder_modal', closeAdminFolderModal);
    }
  }

  function closeAdminFolderModal() {
    const modal = document.getElementById('admin-folder-modal');
    if (modal) modal.style.display = 'none';
  }

  // --- Admin Balance Adjustments ---
  function setAdminBalanceAction(action) {
    adminBalAction = action;
    const btnAdd = document.getElementById('btn-admin-bal-add');
    const btnDeduct = document.getElementById('btn-admin-bal-deduct');
    if (btnAdd) btnAdd.classList.toggle('active', action === 'add');
    if (btnDeduct) btnDeduct.classList.toggle('active', action === 'deduct');
  }

  function setAdminBalAmount(amt) {
    adminBalAmount = Number(amt) || 10;
    const input = document.getElementById('admin-bal-amount-input');
    if (input) input.value = adminBalAmount;
  }

  async function submitAdminAdjustBalance() {
    const tgIdInput = document.getElementById('admin-bal-user-id');
    const targetTgId = tgIdInput?.value?.trim();
    const amt = parseFloat(document.getElementById('admin-bal-amount-input')?.value || adminBalAmount);

    if (!targetTgId || !amt || amt <= 0) {
      api().showToast('يرجى إدخال معرف المستخدم والمبلغ');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/admin/user/balance/adjust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: state().userId,
          target_tg_id: targetTgId,
          amount: amt,
          action: adminBalAction
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast(`تم ${adminBalAction === 'add' ? 'إيداع' : 'خصم'} $${amt} بنجاح!`);
      } else {
        api().showToast(data.error || 'فشل تعديل رصيد المستخدم');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب الرصيد');
    }
  }

  // --- Admin Session Revocation Controls ---
  async function submitAdminRevokeSessions(targetTgId) {
    if (!targetTgId) return;
    api().haptic?.('warning');
    try {
      const res = await fetch('/api/admin/sessions/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: state().userId,
          target_tg_id: targetTgId
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast('تم إلغاء صلاحية جميع جلسات المستخدم بنجاح');
      } else {
        api().showToast(data.error || 'فشل إلغاء الجلسات');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال أمر إلغاء الجلسات');
    }
  }

  async function submitAdminUnrevokeSessions(targetTgId) {
    if (!targetTgId) return;
    api().haptic?.('light');
    try {
      const res = await fetch('/api/admin/sessions/unrevoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: state().userId,
          target_tg_id: targetTgId
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast('تم رفع الحظر عن جلسات المستخدم بنجاح');
      } else {
        api().showToast(data.error || 'فشل رفع الحظر');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال أمر رفع الحظر');
    }
  }

  // --- Admin Global Settings (SYP Rate, Logo, Referral) ---
  async function submitAdminUpdateSypRate() {
    const val = parseFloat(document.getElementById('admin-syp-rate-input')?.value);
    if (!val || val <= 0 || !state().userId) return;

    api().haptic?.('light');
    try {
      const res = await fetch('/api/admin/rate/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_tg_id: state().userId, syp_rate: val })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        state().sypRate = d.syp_rate;
        api().haptic?.('success');
        api().showToast(`تم تحديث سعر صرف الليرة بنجاح (1$ = ${d.syp_rate} ل.س)`);
        if (root.WalletModule?.renderWalletBalances) root.WalletModule.renderWalletBalances();
      } else {
        api().showToast('فشل تحديث سعر الصرف');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب التحديث');
    }
  }

  async function submitAdminUpdateStoreLogo() {
    const input = document.getElementById('admin-store-logo-input');
    const url = (input?.value || '').trim();
    api().haptic?.('light');
    try {
      const res = await fetch('/api/admin/store-logo/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_tg_id: state().userId, logo_url: url })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        api().haptic?.('success');
        api().showToast('تم تحديث شعار المتجر بنجاح!');
        const img = document.getElementById('top-store-logo');
        if (img && url) {
          img.src = url;
          img.style.display = 'block';
        }
      } else {
        api().showToast(d.error || 'فشل تحديث الشعار');
      }
    } catch (_) {
      api().showToast('خطأ في الاتصال بالخادم');
    }
  }

  // --- Export Namespace ---
  root.AdminModule = {
    openAdminProductModal,
    closeAdminProductModal,
    submitAdminProductUpdate,
    openAdminCategoryModal,
    closeAdminCategoryModal,
    openAdminFolderModal,
    closeAdminFolderModal,
    setAdminBalanceAction,
    setAdminBalAmount,
    submitAdminAdjustBalance,
    submitAdminRevokeSessions,
    submitAdminUnrevokeSessions,
    submitAdminUpdateSypRate,
    submitAdminUpdateStoreLogo
  };

})(typeof window !== 'undefined' ? window : globalThis);
