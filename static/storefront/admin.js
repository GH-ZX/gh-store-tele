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

  // --- Category & Folder Selection Helpers ---
  function populateCategorySelect(selectEl, selectedCategory) {
    if (!selectEl) return;
    const cats = state().categoriesList || [];
    const isAr = (state().currentAppLanguage === 'ar');
    const seen = new Set();
    const options = [];

    cats.forEach(c => {
      const val = c.name;
      if (!val || seen.has(val)) return;
      seen.add(val);
      const title = isAr ? (c.name_ar || c.name) : (c.name_en || c.name);
      const icon = c.icon ? `${c.icon} ` : '';
      options.push({ value: val, label: `${icon}${title}` });
    });

    const allProds = state().allProducts || [];
    allProds.forEach(p => {
      const val = p.category || p.category_name;
      if (val && !seen.has(val)) {
        seen.add(val);
        options.push({ value: val, label: `📁 ${val}` });
      }
    });

    if (selectedCategory && !seen.has(selectedCategory)) {
      seen.add(selectedCategory);
      options.push({ value: selectedCategory, label: `📁 ${selectedCategory}` });
    }

    selectEl.innerHTML = options.map(opt => `
      <option value="${escAttr(opt.value)}" ${opt.value === selectedCategory ? 'selected' : ''}>
        ${escAttr(opt.label)}
      </option>
    `).join('');

    if (selectedCategory) {
      selectEl.value = selectedCategory;
    }
  }

  function updateAdminProductFolderOptions(selectedCategory, currentFolder) {
    const selectEl = document.getElementById('admin-edit-prod-folder-select');
    if (!selectEl) return;
    const isAr = (state().currentAppLanguage === 'ar');
    const options = [
      { value: '', label: isAr ? '-- بدون مجلد (منتج مستقل) --' : '-- No Folder (Standalone) --' }
    ];

    const seen = new Set();
    const allFolders = state().allFolders || [];
    allFolders.filter(f => f.category === selectedCategory).forEach(f => {
      const val = f.title_en || f.key;
      if (val && !seen.has(val)) {
        seen.add(val);
        const title = isAr ? (f.title_ar || f.title_en) : (f.title_en || f.title_ar);
        options.push({ value: val, label: `${f.icon || '📁'} ${title}` });
      }
    });

    const allProds = state().allProducts || [];
    allProds.filter(p => (p.category === selectedCategory || p.category_name === selectedCategory) && p.custom_group).forEach(p => {
      const val = p.custom_group;
      if (val && !seen.has(val)) {
        seen.add(val);
        const title = isAr ? (p.custom_group_ar || p.custom_group) : p.custom_group;
        options.push({ value: val, label: `📁 ${title}` });
      }
    });

    options.push({ value: '__NEW__', label: isAr ? '➕ إنشاء مجلد جديد...' : '➕ Create New Folder...' });

    selectEl.innerHTML = options.map(opt => `
      <option value="${escAttr(opt.value)}" ${opt.value === currentFolder ? 'selected' : ''}>
        ${escAttr(opt.label)}
      </option>
    `).join('');

    if (currentFolder && seen.has(currentFolder)) {
      selectEl.value = currentFolder;
    } else {
      selectEl.value = currentFolder || '';
    }

    onAdminProdFolderSelectChange();
  }

  function onAdminProdCatSelectChange() {
    const cat = document.getElementById('admin-edit-prod-cat')?.value || '';
    updateAdminProductFolderOptions(cat, '');
  }

  function onAdminProdFolderSelectChange() {
    const val = document.getElementById('admin-edit-prod-folder-select')?.value;
    const wrap = document.getElementById('admin-edit-prod-new-folder-wrap');
    if (wrap) {
      wrap.style.display = (val === '__NEW__' ? 'block' : 'none');
    }
  }

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
    const resellerPriceInput = document.getElementById('admin-edit-prod-reseller-price');
    const stockDisplay = document.getElementById('admin-edit-prod-stock-display');
    const hiddenCheck = document.getElementById('admin-edit-prod-hidden');
    const folderHiddenCheck = document.getElementById('admin-edit-folder-hidden');
    const catSelect = document.getElementById('admin-edit-prod-cat');

    const defaultNameEn = p.custom_name || p.variant_title_en || p.clean_name || p.name || '';
    const defaultNameAr = p.custom_name_ar || p.variant_title_ar || p.name_ar || defaultNameEn || '';

    if (idInput) idInput.value = p.id;
    if (nameInput) nameInput.value = defaultNameEn;
    if (nameArInput) nameArInput.value = defaultNameAr;
    if (priceInput) priceInput.value = p.sell_price_usd ?? p.price ?? '';
    if (resellerPriceInput) resellerPriceInput.value = p.reseller_price_usd ?? '';
    if (stockDisplay) {
      const isAr = state().currentAppLanguage === 'ar';
      stockDisplay.value = (p.stock !== null && p.stock !== undefined) ? `${p.stock} (${isAr ? 'قطعة' : 'in stock'})` : (isAr ? 'متوفر' : 'In stock');
    }
    if (hiddenCheck) hiddenCheck.checked = !!p.hidden;
    if (folderHiddenCheck) folderHiddenCheck.checked = false;

    // Populate category dropdown
    const currentCat = p.category || p.category_name || '';
    populateCategorySelect(catSelect, currentCat);

    // Populate folder dropdown for this category
    const currentFolder = p.custom_group || p.folder_title_en || '';
    updateAdminProductFolderOptions(currentCat, currentFolder);

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
    const name = document.getElementById('admin-edit-prod-name')?.value?.trim();
    const nameAr = document.getElementById('admin-edit-prod-name-ar')?.value?.trim();
    const price = parseFloat(document.getElementById('admin-edit-prod-price')?.value);
    const resellerPriceRaw = document.getElementById('admin-edit-prod-reseller-price')?.value;
    const resellerPrice = (resellerPriceRaw !== '' && resellerPriceRaw !== null && !isNaN(parseFloat(resellerPriceRaw))) ? parseFloat(resellerPriceRaw) : null;
    const catSelect = document.getElementById('admin-edit-prod-cat');
    const category = catSelect?.value?.trim();
    const folderSelect = document.getElementById('admin-edit-prod-folder-select');
    let customGroup = folderSelect?.value?.trim() || null;
    let customGroupAr = null;
    if (customGroup === '__NEW__') {
      customGroup = document.getElementById('admin-edit-prod-folder-new-en')?.value?.trim() || null;
      customGroupAr = document.getElementById('admin-edit-prod-folder-new-ar')?.value?.trim() || customGroup;
    }
    const isHidden = !!document.getElementById('admin-edit-prod-hidden')?.checked;
    const hideEntireFolder = !!document.getElementById('admin-edit-folder-hidden')?.checked;

    if (!id || isNaN(price) || price <= 0) {
      api().showToast(state().currentAppLanguage === 'ar' ? 'يرجى التأكد من صحة السعر والبيانات' : 'Please check price and data');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/admin/product/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: Number(id),
          custom_name: name,
          custom_name_ar: nameAr || name,
          category: category,
          custom_group: customGroup,
          custom_group_ar: customGroupAr,
          sell_price_usd: price,
          reseller_price_usd: resellerPrice,
          hidden: isHidden,
          hide_entire_folder: hideEntireFolder,
          admin_tg_id: state().userId
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast(state().currentAppLanguage === 'ar' ? 'تم تحديث المنتج بنجاح' : 'Product updated successfully');
        closeAdminProductModal();
        if (root.loadStorefrontData) root.loadStorefrontData();
      } else {
        api().showToast(data.error || 'فشل تحديث بيانات المنتج');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب التحديث');
    }
  }

  // --- Admin Folder Editor Modal ---
  function openAdminFolderModal(folderKey, folderData) {
    api().haptic?.('pop');
    const modal = document.getElementById('admin-folder-modal');
    if (!modal) return;

    let folder = folderData || null;
    const allFolders = state().allFolders || [];
    const allProds = state().allProducts || [];

    if (!folder && folderKey) {
      const matchKey = String(folderKey).toLowerCase().trim();
      folder = allFolders.find(f => {
        const k = (f.key || '').toLowerCase().trim();
        const te = (f.title_en || '').toLowerCase().trim();
        const ta = (f.title_ar || '').toLowerCase().trim();
        const fid = String(f.id || '').trim();
        return k === matchKey || fid === matchKey || te === matchKey || ta === matchKey;
      });
    }

    let primaryProd = null;
    if (folderKey) {
      const matchKey = String(folderKey).toLowerCase().trim();
      primaryProd = allProds.find(p => {
        const fk = (p.folder_key || '').toLowerCase().trim();
        const cg = (p.custom_group || '').toLowerCase().trim();
        const fte = (p.folder_title_en || '').toLowerCase().trim();
        const fta = (p.folder_title_ar || '').toLowerCase().trim();
        return fk === matchKey || cg === matchKey || fte === matchKey || fta === matchKey;
      }) || allProds.find(p => {
        const pn = (p.name || '').toLowerCase().trim();
        const cn = (p.clean_name || '').toLowerCase().trim();
        return pn.includes(matchKey) || cn.includes(matchKey);
      });
    }

    const isNewCreation = (folderData && folderData.id === '' && folderData.key === '' && !folderKey);
    const key = isNewCreation ? '' : (folder?.key || folderData?.key || primaryProd?.folder_key || folderKey || '');
    const id = folder?.id || folderData?.id || '';
    const titleEn = isNewCreation
      ? (folderData?.title_en || '')
      : (folder?.title_en || folder?.folder_title_en || folder?.title || folderData?.title_en || folderData?.folder_title_en || folderData?.title || primaryProd?.folder_title_en || primaryProd?.custom_group || primaryProd?.clean_name || primaryProd?.name || key || '');
    const titleAr = isNewCreation
      ? (folderData?.title_ar || '')
      : (folder?.title_ar || folder?.folder_title_ar || folderData?.title_ar || folderData?.folder_title_ar || primaryProd?.folder_title_ar || primaryProd?.custom_group_ar || primaryProd?.variant_title_ar || primaryProd?.custom_name_ar || titleEn || '');
    const category = folder?.category || folderData?.category || primaryProd?.category || state().activeCatalog || '';
    const icon = folder?.icon || folderData?.icon || primaryProd?.folder_icon || primaryProd?.emoji || '📁';
    const sort = folder?.sort_order ?? folder?.priority ?? folderData?.sort_order ?? folderData?.priority ?? 50;
    const isHidden = !!(folder?.hidden || folderData?.hidden || primaryProd?.folder_hidden || primaryProd?.hidden);

    const idInput = document.getElementById('admin-edit-folder-id');
    const keyInput = document.getElementById('admin-edit-folder-key');
    const titleEnInput = document.getElementById('admin-edit-folder-title-en');
    const titleArInput = document.getElementById('admin-edit-folder-title-ar');
    const iconInput = document.getElementById('admin-edit-folder-icon');
    const sortInput = document.getElementById('admin-edit-folder-sort');
    const hiddenCheck = document.getElementById('admin-edit-folder-hidden-check');
    const catSelect = document.getElementById('admin-edit-folder-cat');

    if (idInput) idInput.value = id;
    if (keyInput) keyInput.value = key;
    if (titleEnInput) titleEnInput.value = titleEn;
    if (titleArInput) titleArInput.value = titleAr;
    if (iconInput) iconInput.value = icon;
    if (sortInput) sortInput.value = sort;
    if (hiddenCheck) hiddenCheck.checked = isHidden;

    populateCategorySelect(catSelect, category);

    modal.style.display = 'flex';
    api().pushNav('admin_folder_modal', closeAdminFolderModal);
  }

  function closeAdminFolderModal() {
    api().haptic?.('light');
    const modal = document.getElementById('admin-folder-modal');
    if (modal) modal.style.display = 'none';
  }

  function openAdminCurrentFolderEditor() {
    const key = (typeof activeVariantFamilyKey !== 'undefined' && activeVariantFamilyKey)
      ? activeVariantFamilyKey
      : (root.activeVariantFamilyKey || window.activeVariantFamilyKey || '');
    openAdminFolderModal(key);
  }

  function openAdminCreateFolderModal() {
    const activeCat = state().activeCatalog || '';
    openAdminFolderModal('', {
      id: '',
      key: '',
      title_en: '',
      title_ar: '',
      category: activeCat,
      icon: '📁',
      sort_order: 50,
      hidden: false
    });
  }

  async function submitAdminFolderUpdate() {
    const id = document.getElementById('admin-edit-folder-id')?.value;
    const key = document.getElementById('admin-edit-folder-key')?.value?.trim();
    const titleEn = document.getElementById('admin-edit-folder-title-en')?.value?.trim();
    const titleAr = document.getElementById('admin-edit-folder-title-ar')?.value?.trim();
    const catSelect = document.getElementById('admin-edit-folder-cat');
    const category = catSelect?.value?.trim();
    const icon = document.getElementById('admin-edit-folder-icon')?.value?.trim();
    const sort = parseInt(document.getElementById('admin-edit-folder-sort')?.value || '50', 10);
    const isHidden = !!document.getElementById('admin-edit-folder-hidden-check')?.checked;

    if (!titleEn) {
      api().showToast(state().currentAppLanguage === 'ar' ? 'يرجى إدخال اسم المجلد' : 'Please enter folder title');
      return;
    }

    const folderKey = key || titleEn.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');

    api().haptic?.('medium');
    try {
      const endpoint = (!id && !key) ? '/api/admin/folder/create' : '/api/admin/folder/update';
      const payload = {
        admin_tg_id: state().userId,
        folder_id: id ? Number(id) : null,
        key: folderKey,
        category: category,
        title_en: titleEn,
        title_ar: titleAr || titleEn,
        icon: icon || '📁',
        sort_order: isNaN(sort) ? 50 : sort,
        hidden: isHidden
      };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast(state().currentAppLanguage === 'ar' ? 'تم حفظ بيانات المجلد بنجاح' : 'Folder saved successfully');
        closeAdminFolderModal();
        if (root.loadStorefrontData) root.loadStorefrontData();
      } else {
        api().showToast(data.error || 'فشل حفظ بيانات المجلد');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب حفظ المجلد');
    }
  }

  // --- Admin Category Editor Modal ---
  function openAdminCategoryModal(catId) {
    const cats = state().categoriesList || [];
    const cat = cats.find(c => String(c.id) === String(catId) || c.name === catId);
    if (!cat) return;

    api().haptic?.('pop');
    const modal = document.getElementById('admin-category-modal');
    if (!modal) return;

    const idInput = document.getElementById('admin-edit-cat-id');
    const arInput = document.getElementById('admin-edit-cat-ar');
    const enInput = document.getElementById('admin-edit-cat-en');
    const prodInput = document.getElementById('admin-edit-cat-prod');
    const imgInput = document.getElementById('admin-edit-cat-img');
    const prevArInput = document.getElementById('admin-edit-cat-prev-ar');
    const prevEnInput = document.getElementById('admin-edit-cat-prev-en');
    const sortInput = document.getElementById('admin-edit-cat-sort');
    const hiddenCheck = document.getElementById('admin-edit-cat-hidden');

    if (idInput) idInput.value = cat.id || '';
    if (arInput) arInput.value = cat.name_ar || cat.name || '';
    if (enInput) enInput.value = cat.name_en || cat.name || '';
    if (prodInput) prodInput.value = cat.product_category || cat.name || '';
    if (imgInput) imgInput.value = cat.image_url || '';
    if (prevArInput) prevArInput.value = cat.preview_ar || '';
    if (prevEnInput) prevEnInput.value = cat.preview_en || '';
    if (sortInput) sortInput.value = cat.sort_order ?? 1;
    if (hiddenCheck) hiddenCheck.checked = !!cat.hidden;

    modal.style.display = 'flex';
    api().pushNav('admin_cat_modal', closeAdminCategoryModal);
  }

  function closeAdminCategoryModal() {
    api().haptic?.('light');
    const modal = document.getElementById('admin-category-modal');
    if (modal) modal.style.display = 'none';
  }

  function openAdminCurrentCategoryEditor() {
    const activeCat = state().activeCatalog;
    if (!activeCat) return;
    const cats = state().categoriesList || [];
    const cat = cats.find(c => c.name === activeCat || String(c.id) === String(activeCat));
    if (cat) {
      openAdminCategoryModal(cat.id);
    }
  }

  async function submitAdminCategoryUpdate() {
    const id = document.getElementById('admin-edit-cat-id')?.value;
    const nameAr = document.getElementById('admin-edit-cat-ar')?.value?.trim();
    const nameEn = document.getElementById('admin-edit-cat-en')?.value?.trim();
    const prodCat = document.getElementById('admin-edit-cat-prod')?.value?.trim();
    const imgUrl = document.getElementById('admin-edit-cat-img')?.value?.trim();
    const prevAr = document.getElementById('admin-edit-cat-prev-ar')?.value?.trim();
    const prevEn = document.getElementById('admin-edit-cat-prev-en')?.value?.trim();
    const sort = parseInt(document.getElementById('admin-edit-cat-sort')?.value || '1', 10);
    const isHidden = !!document.getElementById('admin-edit-cat-hidden')?.checked;

    if (!id || !nameEn) {
      api().showToast('يرجى التأكد من إدخال اسم التصنيف');
      return;
    }

    api().haptic?.('medium');
    try {
      const res = await fetch('/api/admin/category/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category_id: Number(id),
          admin_tg_id: state().userId,
          name_ar: nameAr,
          name_en: nameEn,
          product_category: prodCat,
          image_url: imgUrl,
          preview_ar: prevAr,
          preview_en: prevEn,
          sort_order: isNaN(sort) ? 1 : sort,
          hidden: isHidden
        })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        api().haptic?.('success');
        api().showToast('تم تحديث التصنيف بنجاح');
        closeAdminCategoryModal();
        if (root.loadStorefrontData) root.loadStorefrontData();
      } else {
        api().showToast(data.error || 'فشل تحديث بيانات التصنيف');
      }
    } catch (_) {
      api().showToast('خطأ في إرسال طلب التحديث');
    }
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
        if (root.applyStoreLogo) {
          root.applyStoreLogo(url);
        } else {
          const img = document.getElementById('top-store-logo');
          if (img && url) {
            img.src = url;
            img.style.display = 'block';
          }
        }
      } else {
        api().showToast(d.error || 'فشل تحديث الشعار');
      }
    } catch (_) {
      api().showToast('خطأ في الاتصال بالخادم');
    }
  }

  // --- Admin Navigation & Views ---
  function openAdminStoreSettingsPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-store-settings');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_store_settings', closeAdminStoreSettingsPage);
  }

  function closeAdminStoreSettingsPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function openAdminSuppliersPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-suppliers');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_suppliers', closeAdminSuppliersPage);
  }

  function closeAdminSuppliersPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function openAdminUsersPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-users');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_users', closeAdminUsersPage);
  }

  function closeAdminUsersPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function openAdminStuckOrdersPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-stuck');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_stuck', closeAdminStuckOrdersPage);
  }

  function closeAdminStuckOrdersPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function openAdminResellerPricingPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-reseller-pricing');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_reseller_pricing', closeAdminResellerPricingPage);
  }

  function closeAdminResellerPricingPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function openAdminConfigPage() {
    api().haptic?.('pop');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const view = document.getElementById('view-admin-config');
    if (view) {
      view.classList.add('active');
      view.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('admin_config', closeAdminConfigPage);
  }

  function closeAdminConfigPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const setView = document.getElementById('view-settings');
    if (setView) {
      setView.classList.add('active');
      setView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  // --- Admin Modals ---
  function openAdminBannerModal() {
    api().haptic?.('pop');
    const m = document.getElementById('admin-banner-modal');
    if (m) m.style.display = 'flex';
    api().pushNav?.('admin_banner', closeAdminBannerModal);
  }

  function closeAdminBannerModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-banner-modal');
    if (m) m.style.display = 'none';
  }

  function openAdminBalanceModal(tgId) {
    api().haptic?.('pop');
    const m = document.getElementById('admin-balance-modal');
    if (m) m.style.display = 'flex';
    const inp = document.getElementById('admin-bal-user-id');
    if (inp && tgId) inp.value = tgId;
    api().pushNav?.('admin_balance', closeAdminBalanceModal);
  }

  function closeAdminBalanceModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-balance-modal');
    if (m) m.style.display = 'none';
  }

  function openAdminDiscountModal(tgId) {
    api().haptic?.('pop');
    const m = document.getElementById('admin-discount-modal');
    if (m) m.style.display = 'flex';
    const inp = document.getElementById('admin-disc-user-id');
    if (inp && tgId) inp.value = tgId;
    api().pushNav?.('admin_discount', closeAdminDiscountModal);
  }

  function closeAdminDiscountModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-discount-modal');
    if (m) m.style.display = 'none';
  }

  function openAdminGiftModal() {
    api().haptic?.('pop');
    const m = document.getElementById('admin-gift-modal');
    if (m) m.style.display = 'flex';
    api().pushNav?.('admin_gift', closeAdminGiftModal);
  }

  function closeAdminGiftModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-gift-modal');
    if (m) m.style.display = 'none';
  }

  function openAdminMessageModal(tgId) {
    api().haptic?.('pop');
    const m = document.getElementById('admin-message-user-modal');
    if (m) m.style.display = 'flex';
    const inp = document.getElementById('admin-msg-user-id');
    if (inp && tgId) inp.value = tgId;
    api().pushNav?.('admin_msg', closeAdminMessageModal);
  }

  function closeAdminMessageModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-message-user-modal');
    if (m) m.style.display = 'none';
  }

  let currentAdminOrdersFilter = 'all';

  function openAdminOrdersModal() {
    api().haptic?.('pop');
    const m = document.getElementById('admin-orders-modal');
    if (m) m.style.display = 'flex';
    api().pushNav?.('admin_orders', closeAdminOrdersModal);
    loadAdminOrders('all');
  }

  function closeAdminOrdersModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-orders-modal');
    if (m) m.style.display = 'none';
  }

  async function loadAdminOrders(status = 'all') {
    currentAdminOrdersFilter = status;
    api().haptic?.('selection');
    ['all', 'pending', 'completed', 'refunded'].forEach(t => {
      const btn = document.getElementById('admin-ord-tab-' + t);
      if (btn) btn.classList.toggle('active', (status === 'all' && t === 'all') || (status === 'pending_fulfillment' && t === 'pending') || (status === t));
    });
    const container = document.getElementById('admin-orders-results-list');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--hint);">جاري تحميل الطلبات...</div>';

    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    const isAr = ((state().currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    try {
      const res = await fetch(`/api/admin/orders?tg_id=${tgId}&status=${encodeURIComponent(status)}`);
      const d = await res.json();
      const orders = d.orders || [];
      if (!orders.length) {
        container.innerHTML = `<div style="text-align:center; padding:24px; color:var(--hint);">${isAr ? 'لا توجد طلبات مطابقة.' : 'No matching orders found.'}</div>`;
        return;
      }
      const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;

      container.innerHTML = orders.map(o => {
        const isCompleted = (o.status === 'completed');
        const isRefunded = (o.status === 'refunded');
        const isPending = (o.status === 'pending_fulfillment' || o.status === 'pending');
        const statusClass = isCompleted ? 'status-completed' : (isRefunded ? 'status-refunded' : 'status-pending');
        const statusLabel = isCompleted ? (isAr ? 'مكتمل ✅' : 'Completed ✅') : (isRefunded ? (isAr ? 'مسترد ↩️' : 'Refunded ↩️') : (isPending ? (isAr ? 'قيد التنفيذ ⏳' : 'In Progress ⏳') : o.status));
        const goods = o.goods || [];

        return `
          <div class="order-admin-card" style="background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-weight:800; font-size:13px; color:var(--accent);">#${o.id} · <span style="font-size:12px; color:var(--text);">${api().escapeAttr(o.username ? '@' + o.username : 'ID: ' + o.telegram_id)}</span></span>
              <span class="activity-status-pill ${statusClass}" style="font-size:10px; font-weight:700; padding:2px 8px; border-radius:6px;">
                ${statusLabel}
              </span>
            </div>
            <div style="font-size:13px; font-weight:700; color:var(--text); margin-bottom:6px;">🛍️ ${api().escapeAttr(o.products)}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--hint); background:var(--input-bg); padding:6px 10px; border-radius:8px; border:1px solid var(--border); margin-bottom:6px;">
              <span>${isAr ? 'المبيع:' : 'Sell:'} <strong style="color:var(--text);">$${Number(o.total_sell || 0).toFixed(2)}</strong></span>
              <span>${isAr ? 'التكلفة:' : 'Cost:'} $${Number(o.cost_usd || 0).toFixed(2)}</span>
              <span>${isAr ? 'الربح:' : 'Profit:'} <strong style="color:var(--success);">+$${Number(o.profit_usd || 0).toFixed(2)}</strong></span>
            </div>
            <div style="font-size:10.5px; color:var(--hint); margin-bottom:${goods.length ? '8px' : '0'}; display:flex; justify-content:space-between;">
              <span>${o.created_at || ''}</span>
              ${o.customer_reference ? `<span style="font-family:monospace;">ref: ${api().escapeAttr(o.customer_reference)}</span>` : ''}
            </div>
            ${goods.length ? `
              <div style="margin-top:6px;">
                ${renderFn ? renderFn(goods) : ''}
              </div>
            ` : ''}
            ${isPending ? `
              <div style="display:flex; gap:6px; margin-top:8px; border-top:1px dashed var(--border); padding-top:8px;">
                <button class="btn-action-primary" onclick="adminUpdateOrderStatus(${o.id}, 'completed')" style="flex:1; height:34px; font-size:11px; padding:0;">
                  ${isAr ? 'اعتماد واكتمال ✅' : 'Complete ✅'}
                </button>
                <button class="btn-action-warning" onclick="adminUpdateOrderStatus(${o.id}, 'refunded')" style="flex:1; height:34px; font-size:11px; padding:0;">
                  ${isAr ? 'استرداد ↩️' : 'Refund ↩️'}
                </button>
              </div>
            ` : ''}
          </div>
        `;
      }).join('');
    } catch (e) {
      container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--danger);">${isAr ? 'خطأ في جلب الطلبات. تحقق من الاتصال.' : 'Error fetching orders.'}</div>`;
    }
  }

  async function adminUpdateOrderStatus(orderId, newStatus) {
    api().haptic?.('medium');
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    const isAr = ((state().currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    try {
      const res = await fetch('/api/admin/orders/update-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_tg_id: tgId, order_id: orderId, status: newStatus })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        api().haptic?.('success');
        api().showToast(isAr ? 'تم تحديث حالة الطلب بنجاح' : 'Order status updated successfully');
        loadAdminOrders(currentAdminOrdersFilter);
      } else {
        api().showToast(d.error || (isAr ? 'فشل تحديث حالة الطلب' : 'Failed to update order status'));
      }
    } catch (e) {
      api().showToast(isAr ? 'خطأ في الاتصال بالخادم' : 'Connection error');
    }
  }

  // --- Live Activity Radar ---
  let adminLiveActivities = [];

  async function loadAdminLiveRadar(showToastOnDone = false) {
    const isAdmin = !!(state().userData?.is_admin || window.userData?.is_admin);
    if (!isAdmin) return;
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    const isAr = ((state().currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');

    try {
      const res = await fetch(`/api/admin/live-activity?tg_id=${tgId}&limit=60`);
      const d = await res.json();
      if (d.status === 'ok') {
        adminLiveActivities = d.activities || [];
        const attentionBadge = document.getElementById('admin-radar-attention-badge');
        if (attentionBadge) {
          if (d.needs_attention_count > 0) {
            attentionBadge.innerText = isAr ? `⚠️ ${d.needs_attention_count} بحاجة اعتماد` : `⚠️ ${d.needs_attention_count} Need Approval`;
            attentionBadge.style.display = 'inline-block';
          } else {
            attentionBadge.style.display = 'none';
          }
        }
        renderAdminLiveRadar();
        if (showToastOnDone) {
          api().showToast(isAr ? '✅ تم تحديث الرادار المباشر' : '✅ Live radar refreshed');
        }
      }
    } catch (e) {
      console.warn("Live radar error:", e);
    }
  }

  function renderAdminLiveRadar() {
    const container = document.getElementById('orders-container-box') || document.getElementById('orders-history-list');
    if (!container) return;
    const isAr = ((state().currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    const activeFilter = root.activeActivityFilter || 'all';

    let list = [...adminLiveActivities];
    if (activeFilter === 'attention') {
      list = list.filter(a => a.needs_attention);
    } else if (activeFilter === 'recharges') {
      list = list.filter(a => a.type === 'recharge');
    } else if (activeFilter === 'orders') {
      list = list.filter(a => a.type === 'order');
    } else if (activeFilter === 'transfers') {
      list = list.filter(a => a.type === 'admin_transfer');
    } else if (activeFilter === 'vault') {
      list = list.filter(a => a.type === 'order' && a.goods && a.goods.length);
    }

    if (!list.length) {
      container.innerHTML = `
        <div style="text-align: center; padding: 36px 16px; color: var(--hint); background: var(--input-bg); border-radius: 14px; border: 1px solid var(--border);">
          <div style="font-size: 28px; margin-bottom: 8px;">📡</div>
          <div style="font-size: 14px; font-weight: 700; color: var(--text);">${isAr ? 'لا توجد عمليات في هذا التصنيف حالياً' : 'No activities in this filter'}</div>
          <div style="font-size: 12px; margin-top: 4px;">${isAr ? 'ستظهر أي عمليات شراء أو شحن جديدة فور إجرائها في المتجر.' : 'New orders and recharges will appear here in real time.'}</div>
        </div>
      `;
      return;
    }

    const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;

    container.innerHTML = list.map(item => {
      const isOrder = (item.type === 'order');
      const isCompleted = (item.status === 'completed');
      const isPending = (item.status === 'pending' || item.status === 'pending_fulfillment');

      const statusColor = isCompleted ? '#10b981' : (isPending ? '#f59e0b' : '#ef4444');
      const statusBg = isCompleted ? 'rgba(16,185,129,0.18)' : (isPending ? 'rgba(245,158,11,0.18)' : 'rgba(239,68,68,0.18)');
      const statusText = isCompleted ? (isAr ? 'مكتمل ✅' : 'Completed ✅') : (isPending ? (isAr ? 'قيد المعالجة ⏳' : 'Pending ⏳') : (isAr ? 'فشل / منتهي ❌' : 'Failed ❌'));

      const userTag = item.username ? `@${item.username}` : `مستخدم`;
      const tgIdStr = item.telegram_id || '';
      const goods = item.goods || [];

      return `
        <div class="inset-card" style="margin-bottom: 12px; border-color: ${item.needs_attention ? 'rgba(239,68,68,0.45)' : 'var(--border)'}; background: ${item.needs_attention ? 'linear-gradient(135deg, rgba(239,68,68,0.06), var(--card))' : 'var(--card)'};">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 15px;">${isOrder ? '🛍️' : '💳'}</span>
              <strong style="font-size: 13px; color: var(--text);">${api().escapeAttr(item.title)}</strong>
            </div>
            <span class="pill-badge" style="background: ${statusBg}; color: ${statusColor}; font-size: 11px;">
              ${statusText}
            </span>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 8px;">
            <div>
              <span style="font-weight: 700; color: var(--accent);">${api().escapeAttr(userTag)}</span>
              <span style="font-family: monospace; color: var(--hint); margin-inline-start: 4px;">(ID: ${tgIdStr})</span>
            </div>
            <span style="font-size: 11px; color: var(--hint);">${item.created_at || ''}</span>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; font-size: 13px;">
            <span style="color: var(--hint); font-size: 11px;">${isOrder ? (isAr ? 'قيمة الطلب' : 'Order Total') : (isAr ? 'المبلغ المدفوع' : 'Paid Amount')}</span>
            <div style="text-align: right;">
              <strong style="font-size: 15px; color: var(--text);">$${Number(item.amount_usd || item.total_usd || 0.0).toFixed(2)} USD</strong>
              ${item.local_amount && item.currency !== 'USD' ? `
                <div style="font-size: 11px; color: var(--warning); font-weight: 700;">≈ ${Math.round(item.local_amount).toLocaleString()} ${item.currency === 'XTR' ? '⭐' : 'ل.س'}</div>
              ` : ''}
            </div>
          </div>

          ${goods.length ? `
            <div style="margin-top: 10px;">
              ${renderFn ? renderFn(goods) : ''}
            </div>
          ` : ''}

          ${!isOrder && item.needs_attention ? `
            <div style="margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 10px;">
              <button class="btn-action-primary" onclick="adminApproveRechargeAction('${item.id}', ${item.telegram_id}, ${item.amount_usd})" style="width: 100%; height: 42px; background: linear-gradient(135deg, #10b981, #059669); font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; gap: 6px;">
                <span>✅ ${isAr ? 'اعتماد وإيداع الرصيد للعميل' : 'Approve & Credit Balance'} (+$${Number(item.amount_usd || 0).toFixed(2)})</span>
              </button>
            </div>
          ` : ''}

          ${isOrder && item.needs_attention ? `
            <div style="margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 10px; display: flex; gap: 8px;">
              <button class="btn-action-warning" onclick="adminUpdateOrderStatus(${item.raw_id}, 'refunded')" style="flex: 1; height: 38px; font-size: 12px;">
                <span>↩️ ${isAr ? 'استرداد الرصيد' : 'Refund Order'}</span>
              </button>
              <button class="btn-action-secondary" onclick="openAdminOrdersModal()" style="flex: 1; height: 38px; font-size: 12px;">
                <span>🔍 ${isAr ? 'فحص في الطلبات' : 'Inspect Order'}</span>
              </button>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  async function adminApproveRechargeAction(rechargeId, targetTgId, amountUsd) {
    api().haptic?.('medium');
    const isAr = ((state().currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
    if (!confirm(isAr ? `هل أنت متأكد من رغبتك في اعتماد شحن رصيد العميل (${targetTgId}) بمبلغ $${Number(amountUsd).toFixed(2)} USD وإرسال إشعار فوري له؟` : `Approve recharge of $${Number(amountUsd).toFixed(2)} USD for user ${targetTgId}?`)) {
      return;
    }

    api().showToast(isAr ? 'جاري اعتماد الشحن وإيداع الرصيد...' : 'Approving recharge...');
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    try {
      const res = await fetch('/api/admin/recharge/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_tg_id: tgId,
          recharge_id: rechargeId,
          telegram_id: targetTgId,
          amount_usd: amountUsd
        })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        api().haptic?.('success');
        api().showToast(isAr ? `✅ تم اعتماد الشحن وإيداع $${Number(d.credited_amount || amountUsd).toFixed(2)} للعميل بنجاح!` : `✅ Recharge of $${Number(d.credited_amount || amountUsd).toFixed(2)} approved!`);
        loadAdminLiveRadar();
      } else {
        api().showToast(d.error || (isAr ? 'فشل اعتماد الشحن' : 'Failed to approve recharge'));
      }
    } catch (e) {
      api().showToast(isAr ? 'خطأ في الاتصال أثناء اعتماد الشحن' : 'Connection error');
    }
  }

  // --- Admin Coupons Management ---
  function openAdminCouponsModal() {
    api().haptic?.('pop');
    const m = document.getElementById('admin-coupons-modal');
    if (m) m.style.display = 'flex';
    api().pushNav?.('admin_coupons', closeAdminCouponsModal);
    loadAdminCoupons();
  }

  function closeAdminCouponsModal() {
    api().haptic?.('light');
    const m = document.getElementById('admin-coupons-modal');
    if (m) m.style.display = 'none';
  }

  async function loadAdminCoupons() {
    const container = document.getElementById('admin-coupons-list');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center; padding:10px; color:var(--hint);">تحميل الكوبونات...</div>';
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    try {
      const res = await fetch(`/api/admin/coupons?tg_id=${tgId}`);
      const d = await res.json();
      if (!d.coupons || !d.coupons.length) {
        container.innerHTML = '<div style="text-align:center; padding:10px; color:var(--hint);">لا توجد كوبونات مسجلة.</div>';
        return;
      }
      container.innerHTML = d.coupons.map(c => `
        <div style="background:var(--card); border:1px solid var(--border); border-radius:8px; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong style="font-family:monospace; font-size:13px; color:var(--accent);">${api().escapeAttr(c.code)}</strong>
            <div style="font-size:11px; color:var(--hint);">
              ${c.type === 'percent' ? c.value + '%' : '$' + c.value} · الاستخدام: ${c.usage_count}/${c.usage_limit || '∞'}
            </div>
          </div>
          <button class="admin-edit-badge-btn" style="color:${c.is_active ? '#ef4444' : '#10b981'};" onclick="submitToggleCoupon(${c.id})">
            ${c.is_active ? 'تعطيل' : 'تفعيل'}
          </button>
        </div>
      `).join('');
    } catch (e) {
      container.innerHTML = '<div style="text-align:center; color:var(--danger);">خطأ في جلب الكوبونات.</div>';
    }
  }

  async function submitAdminCreateCoupon() {
    const code = (document.getElementById('admin-new-coupon-code')?.value || '').trim();
    const val = parseFloat(document.getElementById('admin-new-coupon-val')?.value || 0);
    const type = document.getElementById('admin-new-coupon-type')?.value;
    const limit = parseInt(document.getElementById('admin-new-coupon-limit')?.value || 100);
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    if (!code || val <= 0) {
      api().showToast('يرجى إدخال كود صحيح وقيمة صالحة');
      return;
    }
    try {
      const res = await fetch('/api/admin/coupons/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_tg_id: tgId, code: code, value: val, type: type, usage_limit: limit })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        api().haptic?.('success');
        api().showToast(`تم إنشاء الكود ${d.coupon.code} بنجاح!`);
        document.getElementById('admin-new-coupon-code').value = '';
        document.getElementById('admin-new-coupon-val').value = '';
        loadAdminCoupons();
      } else {
        api().showToast(d.error || 'فشل إنشاء الكوبون');
      }
    } catch (e) {
      api().showToast('فشل إنشاء الكوبون');
    }
  }

  async function submitToggleCoupon(couponId) {
    const tgId = state().userId || state().userData?.telegram_id || state().userData?.tg_id;
    try {
      const res = await fetch('/api/admin/coupons/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_tg_id: tgId, coupon_id: couponId })
      });
      const d = await res.json();
      if (d.status === 'ok') {
        api().haptic?.('light');
        api().showToast(d.is_active ? 'تم تفعيل الكوبون' : 'تم تعطيل الكوبون');
        loadAdminCoupons();
      }
    } catch (e) {
      api().showToast('فشل تحديث الكوبون');
    }
  }

  function openFullSqlAdmin() {
    const tg = root.Telegram?.WebApp;
    if (tg?.openLink) tg.openLink(window.location.origin + '/admin');
    else window.open('/admin', '_blank');
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
    openAdminCurrentFolderEditor,
    openAdminCreateFolderModal,
    submitAdminFolderUpdate,
    openAdminCurrentCategoryEditor,
    submitAdminCategoryUpdate,
    onAdminProdCatSelectChange,
    onAdminProdFolderSelectChange,
    populateCategorySelect,
    setAdminBalanceAction,
    setAdminBalAmount,
    submitAdminAdjustBalance,
    submitAdminRevokeSessions,
    submitAdminUnrevokeSessions,
    submitAdminUpdateSypRate,
    submitAdminUpdateStoreLogo,
    openAdminStoreSettingsPage,
    closeAdminStoreSettingsPage,
    openAdminSuppliersPage,
    closeAdminSuppliersPage,
    openAdminUsersPage,
    closeAdminUsersPage,
    openAdminStuckOrdersPage,
    closeAdminStuckOrdersPage,
    openAdminResellerPricingPage,
    closeAdminResellerPricingPage,
    openAdminConfigPage,
    closeAdminConfigPage,
    openAdminBannerModal,
    closeAdminBannerModal,
    openAdminBalanceModal,
    closeAdminBalanceModal,
    openAdminDiscountModal,
    closeAdminDiscountModal,
    openAdminGiftModal,
    closeAdminGiftModal,
    openAdminMessageModal,
    closeAdminMessageModal,
    openAdminOrdersModal,
    closeAdminOrdersModal,
    loadAdminOrders,
    adminUpdateOrderStatus,
    loadAdminLiveRadar,
    renderAdminLiveRadar,
    adminApproveRechargeAction,
    openAdminCouponsModal,
    closeAdminCouponsModal,
    loadAdminCoupons,
    submitAdminCreateCoupon,
    submitToggleCoupon,
    openFullSqlAdmin
  };

  // Direct window bindings for inline HTML attribute callbacks
  root.openAdminOrdersModal = openAdminOrdersModal;
  root.closeAdminOrdersModal = closeAdminOrdersModal;
  root.loadAdminOrders = loadAdminOrders;
  root.adminUpdateOrderStatus = adminUpdateOrderStatus;
  root.loadAdminLiveRadar = loadAdminLiveRadar;
  root.renderAdminLiveRadar = renderAdminLiveRadar;
  root.adminApproveRechargeAction = adminApproveRechargeAction;
  root.openAdminCouponsModal = openAdminCouponsModal;
  root.closeAdminCouponsModal = closeAdminCouponsModal;
  root.loadAdminCoupons = loadAdminCoupons;
  root.submitAdminCreateCoupon = submitAdminCreateCoupon;
  root.submitToggleCoupon = submitToggleCoupon;
  root.openAdminProductModal = openAdminProductModal;
  root.closeAdminProductModal = closeAdminProductModal;
  root.submitAdminProductUpdate = submitAdminProductUpdate;
  root.openAdminCategoryModal = openAdminCategoryModal;
  root.closeAdminCategoryModal = closeAdminCategoryModal;
  root.openAdminFolderModal = openAdminFolderModal;
  root.closeAdminFolderModal = closeAdminFolderModal;
  root.openAdminCurrentFolderEditor = openAdminCurrentFolderEditor;
  root.openAdminCreateFolderModal = openAdminCreateFolderModal;
  root.submitAdminFolderUpdate = submitAdminFolderUpdate;
  root.openAdminCurrentCategoryEditor = openAdminCurrentCategoryEditor;
  root.submitAdminCategoryUpdate = submitAdminCategoryUpdate;
  root.onAdminProdCatSelectChange = onAdminProdCatSelectChange;
  root.onAdminProdFolderSelectChange = onAdminProdFolderSelectChange;
  root.populateCategorySelect = populateCategorySelect;
  root.setAdminBalanceAction = setAdminBalanceAction;
  root.setAdminBalAmount = setAdminBalAmount;
  root.submitAdminAdjustBalance = submitAdminAdjustBalance;
  root.submitAdminRevokeSessions = submitAdminRevokeSessions;
  root.submitAdminUnrevokeSessions = submitAdminUnrevokeSessions;
  root.submitAdminUpdateSypRate = submitAdminUpdateSypRate;
  root.submitAdminUpdateStoreLogo = submitAdminUpdateStoreLogo;
  root.openAdminStoreSettingsPage = openAdminStoreSettingsPage;
  root.closeAdminStoreSettingsPage = closeAdminStoreSettingsPage;
  root.openAdminSuppliersPage = openAdminSuppliersPage;
  root.closeAdminSuppliersPage = closeAdminSuppliersPage;
  root.openAdminUsersPage = openAdminUsersPage;
  root.closeAdminUsersPage = closeAdminUsersPage;
  root.openAdminStuckOrdersPage = openAdminStuckOrdersPage;
  root.closeAdminStuckOrdersPage = closeAdminStuckOrdersPage;
  root.openAdminResellerPricingPage = openAdminResellerPricingPage;
  root.closeAdminResellerPricingPage = closeAdminResellerPricingPage;
  root.openAdminConfigPage = openAdminConfigPage;
  root.closeAdminConfigPage = closeAdminConfigPage;
  root.openAdminBannerModal = openAdminBannerModal;
  root.closeAdminBannerModal = closeAdminBannerModal;
  root.openAdminBalanceModal = openAdminBalanceModal;
  root.closeAdminBalanceModal = closeAdminBalanceModal;
  root.openAdminDiscountModal = openAdminDiscountModal;
  root.closeAdminDiscountModal = closeAdminDiscountModal;
  root.openAdminGiftModal = openAdminGiftModal;
  root.closeAdminGiftModal = closeAdminGiftModal;
  root.openAdminMessageModal = openAdminMessageModal;
  root.closeAdminMessageModal = closeAdminMessageModal;
  root.openFullSqlAdmin = openFullSqlAdmin;

})(typeof window !== 'undefined' ? window : globalThis);
