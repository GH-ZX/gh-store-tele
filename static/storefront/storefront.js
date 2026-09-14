/**
 * GH Store - Catalog, Categories, Search, & Product Detail Module (storefront.js)
 * 
 * Provides:
 * - Dynamic category rendering with grid/list mode toggle on #catalogs-grid
 * - Brand folder grouping with in-stock priority partitioning
 * - Dedicated variants page subview for family collections (#service-variants-mode)
 * - Dedicated product detail page (#view-product-detail)
 * - Alias-powered smart search with autocomplete chips and dedicated search page (#view-search)
 * - Quantity steppers, live discount strikethrough, coupon verification, and game player inputs
 * - Flash sale countdown timer and reviews / support modals
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};
  const checkout = () => root.StoreCheckout || {};
  const sec = () => root.StorefrontSecurity || {};

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

  let _serviceFamilyRegistry = [];
  let activeVariantFamilyKey = null;
  let wishlistSet = new Set();
  let selectedProduct = null;
  let selectedQty = 1;
  let activeCatalog = null;
  let activeCatalogFilter = 'all';

  // Load wishlist from storage
  try {
    const rawWish = root.localStorage?.getItem('ghstore_wishlist');
    if (rawWish) wishlistSet = new Set(JSON.parse(rawWish));
  } catch (_) {}

  // --- Category View Mode: Grid vs List ---
  let currentCatalogViewMode = 'grid';
  try {
    currentCatalogViewMode = root.localStorage?.getItem('ghstore_cat_view') || 'grid';
  } catch (_) {}

  function setCatalogViewMode(mode) {
    currentCatalogViewMode = mode;
    try { root.localStorage?.setItem('ghstore_cat_view', mode); } catch (_) {}
    api().haptic?.('light');

    const btnG = document.getElementById('btn-view-grid');
    const btnL = document.getElementById('btn-view-list');
    if (btnG) btnG.classList.toggle('active', mode === 'grid');
    if (btnL) btnL.classList.toggle('active', mode === 'list');

    renderCatalogsGrid();
  }

  function switchCategoryViewMode(mode) {
    setCatalogViewMode(mode);
  }

  // --- Price & Currency Helpers ---
  function getAppCurrencyPref() {
    return state().userData?.currency_preference || root.localStorage?.getItem('ghstore_curr_pref') || 'USD';
  }

  function getSypRate() {
    return Number(state().userData?.syp_rate || state().userData?.admin_stats?.syp_usd_rate || 0);
  }

  function formatPrice(amountUsd) {
    if (amountUsd === null || amountUsd === undefined || isNaN(amountUsd)) return 'N/A';
    const pref = getAppCurrencyPref();
    const num = Number(amountUsd);
    const rate = getSypRate();
    const isAr = (state().currentAppLanguage === 'ar');
    if (pref === 'SYP' && rate > 0) {
      const syp = Math.round(num * rate);
      return `${syp.toLocaleString()} ${isAr ? 'ل.س' : 'SYP'}`;
    }
    return `$${num.toFixed(2)}`;
  }

  function stripEmojis(s) {
    return String(s || '').replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}\u{2190}-\u{21FF}]/gu, '').replace(/\s{2,}/g, ' ').trim();
  }

  function escAttr(s) {
    return sec().escapeHtml ? sec().escapeHtml(s) : String(s || '').replace(/"/g, '&quot;');
  }

  function thumbImg(src, name) {
    const safeSrc = sec().safeUrl ? sec().safeUrl(src, true) : (src || '');
    const cleanSafe = safeSrc ? escAttr(safeSrc) : '/static/img/product-placeholder.svg';
    const nm = escAttr(name || 'Product');
    return `<img src="${cleanSafe}" alt="${nm}" loading="lazy" data-n="${nm}" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='inline-flex';"><span class="prod-thumb-letter" style="display:none;">${(name || 'GH').trim().charAt(0).toUpperCase()}</span>`;
  }

  function productThumb(p) {
    const raw = (p && (p.display_image || p.image_url)) || '/static/img/product-placeholder.svg';
    return raw;
  }

  function calculateProductPrices(product) {
    const u = state().userData;
    const origPrice = Number(product.sell_price_usd || product.price || 0);
    const costUsd = Number(product.cost_price_usd || product.cost_usd || product.original_price || 0);

    const isReseller = !!(u && (u.is_reseller || u.role === 'reseller'));
    if (isReseller && u.reseller_margin_percent !== undefined) {
      const mPct = Number(u.reseller_margin_percent) || 0;
      const resPrice = Math.round(costUsd * (1 + mPct / 100) * 100) / 100;
      const profitUsd = Math.max(0, Math.round((resPrice - costUsd) * 100) / 100);
      return {
        origPrice,
        finalPrice: resPrice,
        hasDiscount: (resPrice < origPrice),
        discPct: origPrice > 0 ? Math.round(((origPrice - resPrice) / origPrice) * 100) : 0,
        costUsd,
        profitUsd,
        marginPct: mPct,
        isReseller: true
      };
    }

    const vipDiscount = Number(u?.vip_discount || 0);
    let finalPrice = origPrice;
    let hasDiscount = false;

    if (vipDiscount > 0) {
      const rawDiscounted = Math.round((origPrice * (1 - vipDiscount / 100)) * 100) / 100;
      finalPrice = costUsd > 0 ? Math.max(costUsd, rawDiscounted) : rawDiscounted;
      hasDiscount = (finalPrice < origPrice);
    }

    const profitUsd = Math.max(0, Math.round((finalPrice - costUsd) * 100) / 100);
    const marginPct = costUsd > 0 ? Math.round(((finalPrice - costUsd) / costUsd) * 100) : 0;

    return {
      origPrice,
      finalPrice,
      hasDiscount,
      discPct: vipDiscount,
      costUsd,
      profitUsd,
      marginPct,
      isReseller: false
    };
  }

  function checkProductEffectiveStock(product) {
    if (!product) return { isOutOfStock: true, effectiveStock: 0 };
    const stock = (product.stock !== null && product.stock !== undefined) ? Number(product.stock) : 999;
    return {
      isOutOfStock: stock <= 0,
      effectiveStock: stock
    };
  }

  function getProductFamilyKey(p) {
    if (!p) return 'Other';
    if (p.custom_group) return p.custom_group;
    if (p.folder_title_en) return p.folder_title_en;
    const raw = (p.custom_name || p.clean_name || p.name || '').trim();
    const lower = raw.toLowerCase();
    const brands = [
      ['chatgpt', 'ChatGPT Plus'],
      ['claude', 'Claude API & Pro'],
      ['gemini', 'Google Gemini'],
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
      ['nordvpn', 'NordVPN Premium']
    ];
    for (const [kw, name] of brands) {
      if (lower.includes(kw)) return name;
    }
    return raw || 'Other';
  }

  function renderDurationBadge(dur) {
    if (!dur) return '';
    return `<span class="prod-dur-badge">${escAttr(dur)}</span>`;
  }

  function productMetaLine(o) {
    const isAr = (state().currentAppLanguage === 'ar');
    if (o.isOutOfStock) {
      const lbl = isAr ? 'نفد المخزون' : 'Out of stock';
      return `<div class="prod-meta oos"><i class="dot"></i><span>${lbl}</span></div>`;
    }
    const stock = o.stockText || (isAr ? 'متوفر' : 'In stock');
    if (o.isActivation) {
      const delivery = isAr ? 'تفعيل مخصص' : 'Activation';
      return `<div class="prod-meta"><i class="dot"></i><span>${escAttr(stock)}</span><span class="sep">·</span><span>${delivery}</span></div>`;
    }
    return `<div class="prod-meta"><i class="dot"></i><span>${escAttr(stock)}</span></div>`;
  }

  function renderPriceBoxHTML(product, isMulti, favSvg, tapHint) {
    const { origPrice, finalPrice, hasDiscount, discPct } = calculateProductPrices(product);
    const isAr = (state().currentAppLanguage === 'ar');
    const startsPrefix = isMulti ? `<span style="font-size: 10px; color: var(--hint); font-weight: 600;">${isAr ? 'من ' : 'From '}</span>` : '';

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

    return `
      <div class="prod-price-box">
        ${priceRow}
        <div class="prod-action-row">
          ${favSvg ? `<button class="fav-btn-action" data-pid="${Number(product.id)}" onclick="event.stopPropagation(); toggleProductWishlist(${Number(product.id)})">${favSvg}</button>` : ''}
          <div class="prod-tap-hint">${tapHint || (isAr ? 'عرض' : 'View')}</div>
        </div>
      </div>
    `;
  }

  function renderAdminProductBar(product) {
    const u = state().userData;
    if (!u || !u.is_admin) return '';
    const { costUsd, profitUsd } = calculateProductPrices(product);
    const isAr = (state().currentAppLanguage === 'ar');
    const costLbl = isAr ? 'المورد' : 'Cost';
    const profLbl = isAr ? 'الربح' : 'Profit';
    const editLbl = isAr ? 'تعديل' : 'Edit';

    return `
      <div class="prod-admin-footer" onclick="event.stopPropagation()">
        <div class="prod-admin-metrics">
          <span class="cost-metric">${costLbl}: <b>${formatPrice(costUsd)}</b></span>
          <span class="sep">·</span>
          <span class="prof-metric">${profLbl}: <b>+${formatPrice(profitUsd)}</b></span>
        </div>
        <button class="prod-admin-edit-action" onclick="openAdminProductModal(${Number(product.id)})">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          <span>${editLbl}</span>
        </button>
      </div>
    `;
  }

  // --- Dynamic Categories Rendering (Eliminates Shimmer Skeletons Forever) ---
  function renderCatalogsGrid(categories = null) {
    const cats = categories || state().categoriesList || [];
    state().categoriesList = cats;
    const allProds = state().allProducts || [];

    const container = document.getElementById('catalogs-grid');
    const testContainer = document.getElementById('categories-container');

    if (!container && !testContainer) return;

    const isGrid = (currentCatalogViewMode === 'grid');
    const isAr = (state().currentAppLanguage === 'ar');
    const isAdmin = !!(state().userData && state().userData.is_admin);

    if (container) {
      container.className = `catalogs-grid ${isGrid ? 'grid-layout' : 'list-layout'}`;
    }

    // Toggle button UI synchronization
    const btnG = document.getElementById('btn-view-grid');
    const btnL = document.getElementById('btn-view-list');
    if (btnG) btnG.classList.toggle('active', isGrid);
    if (btnL) btnL.classList.toggle('active', !isGrid);

    if (!cats || cats.length === 0) {
      const emptyHtml = `<div class="empty-state-card" style="text-align: center; padding: 40px 16px; color: var(--hint);">${isAr ? 'لا توجد تصنيفات متاحة حالياً' : 'No categories available currently'}</div>`;
      if (container) container.innerHTML = emptyHtml;
      if (testContainer) testContainer.innerHTML = emptyHtml;
      return;
    }

    const cardsHtml = cats.map(catItem => {
      const catName = (typeof catItem === 'object' && catItem.name) ? catItem.name : String(catItem);
      const catId = (typeof catItem === 'object' && catItem.id) ? catItem.id : null;
      const items = allProds.filter(p => p.category === catName || p.category_name === catName || String(p.category_id) === String(catId));
      const isEmpty = (!items || !items.length);

      let displayTitle = catName;
      let displayPreview = '';
      let imageUrl = '/static/img/cat-other.svg';

      if (typeof catItem === 'object') {
        const tEn = catItem.name_en || catItem.name || catName;
        const tAr = catItem.name_ar || tEn;
        displayTitle = stripEmojis(isAr ? tAr : tEn) || catName;
        displayPreview = (isAr && catItem.preview_ar) ? catItem.preview_ar : (catItem.preview_en || '');
        imageUrl = (catItem.image_url || catItem.icon_url || '/static/img/cat-other.svg');
      }

      const minPrice = isEmpty ? 0 : Math.min(...items.map(p => Number(p.sell_price_usd || p.price || 999)));
      const itemsSuffix = isAr ? 'منتج' : 'items';
      const startsFrom = isAr ? 'من' : 'Starts from';
      const soonPill = isEmpty
        ? `<span class="catalog-visual-pill" style="background: rgba(245,158,11,0.25); color: #fbbf24;">${isAr ? 'قريباً' : 'Soon'}</span>`
        : `<span class="catalog-visual-pill">${items.length} ${itemsSuffix}</span>`;

      const adminEditBtn = (isAdmin && catId)
        ? `<button class="admin-edit-badge-btn" onclick="event.stopPropagation(); openAdminCategoryEditor(${catId}, event)">${isAr ? 'تعديل' : 'Edit'}</button>`
        : '';

      const safeImg = sec().safeUrl ? sec().safeUrl(imageUrl, true) : imageUrl;

      if (isGrid) {
        return `
          <div class="catalog-visual-card${isEmpty ? ' is-empty' : ''}" style="background-image: url('${safeImg}');" data-category="${escAttr(catName)}" onclick="openCollection(this.dataset.category)">
            <div class="catalog-visual-overlay"></div>
            <div class="catalog-visual-top">
              ${soonPill}
              ${adminEditBtn}
            </div>
            <div class="catalog-visual-bottom">
              <div class="catalog-visual-title">${escAttr(displayTitle)}</div>
              <div class="catalog-visual-sub">
                ${isEmpty
                  ? `<span>${isAr ? 'منتجات جديدة قريباً' : 'New products soon'}</span>`
                  : `<span>${startsFrom} ${formatPrice(minPrice)}</span>`}
                <span style="font-size: 15px; font-weight: 800;">${isAr ? '‹' : '›'}</span>
              </div>
            </div>
          </div>
        `;
      }

      // List layout
      const chevron = isAr ? '‹' : '›';
      return `
        <div class="catalog-list-card${isEmpty ? ' is-empty' : ''}" data-category="${escAttr(catName)}" onclick="openCollection(this.dataset.category)">
          <div class="catalog-left">
            <div class="catalog-thumb"><img src="${safeImg}" alt="" loading="lazy" onerror="this.style.display='none'"></div>
            <div class="catalog-info">
              <div style="display:flex; align-items:center;">
                <span class="catalog-name">${escAttr(displayTitle)}</span>
                ${adminEditBtn}
              </div>
              <div class="catalog-sub">
                ${isEmpty
                  ? `<span style="color: #fbbf24; font-weight: 700;">${isAr ? 'قريباً' : 'Soon'}</span>`
                  : `<span>${items.length} ${itemsSuffix}</span> · <span style="color: var(--accent); font-weight: 700;">${startsFrom} ${formatPrice(minPrice)}</span>`}
              </div>
              <div style="font-size: 11px; color: var(--hint); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${escAttr(displayPreview)}
              </div>
            </div>
          </div>
          <span class="chevron-icon">${chevron}</span>
        </div>
      `;
    }).join('');

    if (container) container.innerHTML = cardsHtml;
    if (testContainer) testContainer.innerHTML = cardsHtml;
  }

  function renderCategories(categories, activeCatId = null) {
    renderCatalogsGrid(categories);
  }

  // --- Collection View & Back Navigation ---
  function openCollection(catName) {
    api().haptic?.('light');
    activeCatalog = catName;
    state().activeCatalog = catName;

    const sCats = document.getElementById('catalogs-collection-mode');
    if (sCats) sCats.style.display = 'none';

    const sProds = document.getElementById('products-catalog-mode');
    if (sProds) sProds.style.display = 'block';

    const isAr = (state().currentAppLanguage === 'ar');
    const cats = state().categoriesList || [];
    let catObj = cats.find(c => (typeof c === 'object' ? (c.name === catName || c.name_en === catName || c.name_ar === catName) : c === catName));
    let dispTitle = catName;
    if (catObj && typeof catObj === 'object') {
      const tEn = catObj.name_en || catObj.name || catName;
      const tAr = catObj.name_ar || tEn;
      dispTitle = stripEmojis(isAr ? tAr : tEn) || catName;
    }

    const titleEl = document.getElementById('active-collection-title');
    if (titleEl) titleEl.innerText = dispTitle;

    const all = state().allProducts || [];
    let filtered = all.filter(p => p.category === catName || p.category_name === catName || String(p.category_id) === String(catName));
    filtered = filterAndSortProducts(filtered);
    renderProductItems(filtered);

    const catAdminBar = document.getElementById('admin-category-actions-bar');
    if (catAdminBar) {
      catAdminBar.style.display = (state().userData && state().userData.is_admin) ? 'flex' : 'none';
    }

    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('collection', returnToCollections);
  }

  function selectCategory(catId) {
    const cats = state().categoriesList || [];
    const cat = cats.find(c => String(c.id) === String(catId) || c.name === catId);
    openCollection(cat ? (cat.name || cat.id) : catId);
  }

  let _closingCollection = false;
  function returnToCollections() {
    if (_closingCollection) return;
    _closingCollection = true;
    try {
      api().haptic?.('light');
      activeCatalog = null;
      state().activeCatalog = null;

      const sVariants = document.getElementById('service-variants-mode');
      if (sVariants) sVariants.style.display = 'none';

      const sProds = document.getElementById('products-catalog-mode');
      if (sProds) sProds.style.display = 'none';

      const sCats = document.getElementById('catalogs-collection-mode');
      if (sCats) sCats.style.display = 'block';

      activeVariantFamilyKey = null;
      window.scrollTo({ top: 0, behavior: 'instant' });

      if (api().navStack?.length > 0 && api().navStack[api().navStack.length - 1].name === 'collection') {
        api().popNav?.();
      }
    } finally {
      _closingCollection = false;
    }
  }

  // --- Filtering & Sorting In-Stock Priority ---
  function filterAndSortProducts(list) {
    let result = [...list];
    if (activeCatalogFilter === 'wishlist') {
      result = result.filter(p => wishlistSet.has(Number(p.id)));
    } else if (activeCatalogFilter === 'stock') {
      result = result.filter(p => !checkProductEffectiveStock(p).isOutOfStock);
    }

    // In-Stock Priority Partitioning: In-stock items ALWAYS at the top, out-of-stock sink to bottom
    result.sort((a, b) => {
      const aOut = checkProductEffectiveStock(a).isOutOfStock ? 1 : 0;
      const bOut = checkProductEffectiveStock(b).isOutOfStock ? 1 : 0;
      if (aOut !== bOut) return aOut - bOut;
      if (activeCatalogFilter === 'lowprice') {
        return (Number(a.sell_price_usd || a.price || 0)) - (Number(b.sell_price_usd || b.price || 0));
      }
      return 0;
    });

    return result;
  }

  function applyCatalogFilter(filterKey) {
    api().haptic?.('pop');
    activeCatalogFilter = filterKey;
    state().activeCatalogFilter = filterKey;

    document.querySelectorAll('#quick-filters-row .filter-chip').forEach(el => el.classList.remove('active'));
    const activeEl = document.getElementById('filter-' + filterKey);
    if (activeEl) activeEl.classList.add('active');

    if (filterKey === 'all' && !activeCatalog) {
      returnToCollections();
      return;
    }

    const sCats = document.getElementById('catalogs-collection-mode');
    if (sCats) sCats.style.display = 'none';

    const sProds = document.getElementById('products-catalog-mode');
    if (sProds) sProds.style.display = 'block';

    const all = state().allProducts || [];
    let baseList = activeCatalog ? all.filter(p => p.category === activeCatalog || p.category_name === activeCatalog) : all;
    const filtered = filterAndSortProducts(baseList);

    const isAr = (state().currentAppLanguage === 'ar');
    const titleEl = document.getElementById('active-collection-title');
    if (titleEl) {
      titleEl.innerText = filterKey === 'wishlist'
        ? (isAr ? 'المفضلة' : 'Favorites')
        : (isAr ? 'النتائج المصفاة' : 'Filtered Results');
    }

    renderProductItems(filtered);
  }

  // --- Folder Cards & Products Listing ---
  function renderProductItems(products) {
    const container = document.getElementById('catalog-products-list');
    const testContainer = document.getElementById('products-container');
    if (!container && !testContainer) return;

    const isAr = (state().currentAppLanguage === 'ar');
    if (!products || !products.length) {
      const emptyHtml = `<div style="text-align: center; padding: 40px 16px; color: var(--hint);">${isAr ? 'لا توجد منتجات مطابقة لهذا الفلتر.' : 'No products found matching this filter.'}</div>`;
      if (container) container.innerHTML = emptyHtml;
      if (testContainer) testContainer.innerHTML = emptyHtml;
      return;
    }

    // Group by folder/family
    const familyMap = new Map();
    products.forEach(p => {
      const famKey = p.folder_key || getProductFamilyKey(p) || 'Other';
      if (!familyMap.has(famKey)) familyMap.set(famKey, []);
      familyMap.get(famKey).push(p);
    });

    _serviceFamilyRegistry = [];
    let regIdx = 0;
    let html = '';

    const sortByDurationThenPrice = (a, b) => {
      const dw = (Number(a.duration_weight || 100) - Number(b.duration_weight || 100));
      if (dw !== 0) return dw;
      return (Number(a.sell_price_usd || a.price || 0)) - (Number(b.sell_price_usd || b.price || 0));
    };

    for (const [famKey, items] of familyMap.entries()) {
      items.sort((a, b) => {
        const aStock = checkProductEffectiveStock(a);
        const bStock = checkProductEffectiveStock(b);
        if (aStock.isOutOfStock !== bStock.isOutOfStock) return aStock.isOutOfStock ? 1 : -1;
        return sortByDurationThenPrice(a, b);
      });

      const primary = items[0];
      const isMulti = items.length > 1;
      const currentIdx = regIdx++;

      const folderTitle = isAr
        ? (primary.custom_group_ar || primary.folder_title_ar || primary.custom_group || primary.folder_title_en || getProductFamilyKey(primary))
        : (primary.custom_group || primary.folder_title_en || primary.folder_title_ar || getProductFamilyKey(primary));

      const groupTitle = isMulti
        ? folderTitle
        : (isAr
          ? (primary.custom_name_ar || primary.variant_title_ar || primary.custom_name || primary.clean_name || primary.name)
          : (primary.custom_name || primary.variant_title_en || primary.clean_name || primary.name));

      _serviceFamilyRegistry.push({
        famKey: famKey,
        title: groupTitle,
        items: items
      });

      const isFav = wishlistSet.has(Number(primary.id));
      const anyInStock = items.some(it => !checkProductEffectiveStock(it).isOutOfStock);
      const isOutOfStock = !anyInStock;
      const isActivation = (primary.delivery_type === 'activation');
      const durText = (isAr ? primary.duration_ar : primary.duration_en) || null;
      const stockText = (!isOutOfStock && primary.stock) ? `${isAr ? 'متوفر' : 'In stock'} (${primary.stock})` : ((!isOutOfStock) ? (isAr ? 'متوفر' : 'In stock') : '');
      const metaLine = productMetaLine({
        isOutOfStock,
        isActivation,
        duration: (!isMulti ? durText : null),
        multiCount: (isMulti ? items.length : 0),
        stockText
      });

      const favSvg = `
        <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="18" height="18">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
      `;

      if (isMulti) {
        const folderIcon = primary.folder_icon || primary.emoji || '📁';
        const isIconUrl = /^https?:\/\//.test(String(folderIcon)) || String(folderIcon).startsWith('/');
        const thumbHtml = isIconUrl ? thumbImg(folderIcon, folderTitle) : `<span class="folder-thumb-emoji">${escAttr(folderIcon)}</span>`;
        const planBadge = `📁 ${items.length} ${isAr ? 'باقات متوفرة' : 'Plans Available'}`;
        const chevronArrow = isAr ? '‹' : '›';
        html += `
          <div class="product-row folder-card-row" onclick="openServiceVariantsByIndex(${currentIdx})">
            <div class="prod-row-top">
              <div class="prod-thumb folder-thumb">${thumbHtml}</div>
              <div class="prod-left">
                <div class="prod-title-wrap">
                  <span class="prod-title folder-title" title="${escAttr(folderTitle)}">${escAttr(folderTitle)}</span>
                  <span class="prod-options-badge">${planBadge}</span>
                </div>
              </div>
              <div class="folder-chevron-action">
                <span class="folder-chevron-arrow">${chevronArrow}</span>
              </div>
            </div>
            ${renderAdminProductBar(primary)}
          </div>
        `;
      } else {
        const displayTitle = groupTitle;
        const thumb = productThumb(primary);
        html += `
          <div class="product-row" onclick="openProductDetail(${Number(primary.id)})">
            <div class="prod-row-top">
              <div class="prod-thumb">${thumbImg(thumb, displayTitle)}</div>
              <div class="prod-left">
                <div class="prod-title-wrap">
                  <span class="prod-title" title="${escAttr(displayTitle)}">${escAttr(displayTitle)}</span>
                  ${renderDurationBadge(durText)}
                </div>
                ${metaLine}
              </div>
              ${renderPriceBoxHTML(primary, false, favSvg, isAr ? 'عرض' : 'View')}
            </div>
            ${renderAdminProductBar(primary)}
          </div>
        `;
      }
    }

    if (container) container.innerHTML = html;
    if (testContainer) testContainer.innerHTML = html;
  }

  function renderStorefrontFolderCards(products) {
    renderProductItems(products);
  }

  // --- Dedicated Variants Page ---
  function openServiceVariantsByIndex(idx) {
    api().haptic?.('light');
    const entry = _serviceFamilyRegistry[idx];
    if (!entry) return;
    activeVariantFamilyKey = entry.famKey;

    const isAr = (state().currentAppLanguage === 'ar');
    const _fPrimary = entry.items[0] || {};
    const folderTitle = isAr
      ? (_fPrimary.folder_title_ar || _fPrimary.folder_title_en || entry.title)
      : (_fPrimary.folder_title_en || _fPrimary.folder_title_ar || entry.title);

    const titleEl = document.getElementById('active-service-title');
    if (titleEl) titleEl.innerText = folderTitle || (isAr ? 'باقات الخدمة' : 'Service Plans');

    const sProds = document.getElementById('products-catalog-mode');
    if (sProds) sProds.style.display = 'none';
    const sCats = document.getElementById('catalogs-collection-mode');
    if (sCats) sCats.style.display = 'none';

    const sVariants = document.getElementById('service-variants-mode');
    if (sVariants) sVariants.style.display = 'block';

    const vList = document.getElementById('service-variants-products-list');
    if (vList) {
      vList.innerHTML = entry.items.map(p => {
        const isFav = wishlistSet.has(Number(p.id));
        const stockInfo = checkProductEffectiveStock(p);
        const isOutOfStock = stockInfo.isOutOfStock;
        const isActivation = (p.delivery_type === 'activation');
        const durText = (isAr ? p.duration_ar : p.duration_en) || null;
        const stockText = (!isOutOfStock && p.stock) ? `${isAr ? 'متوفر' : 'In stock'} (${p.stock})` : ((!isOutOfStock) ? (isAr ? 'متوفر' : 'In stock') : '');
        const metaLine = productMetaLine({ isOutOfStock, isActivation, duration: durText, multiCount: 0, stockText });
        const favSvg = `
          <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="18" height="18">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
        `;
        const displayTitle = isAr
          ? (p.variant_title_ar || p.custom_name_ar || p.variant_title_en || p.custom_name || p.clean_name || p.name)
          : (p.variant_title_en || p.custom_name || p.variant_title_ar || p.clean_name || p.name);
        const thumb = productThumb(p);

        return `
          <div class="product-row" onclick="openProductDetail(${Number(p.id)})">
            <div class="prod-row-top">
              <div class="prod-thumb">${thumbImg(thumb, displayTitle)}</div>
              <div class="prod-left">
                <div class="prod-title-wrap">
                  <span class="prod-title" title="${escAttr(displayTitle)}">${escAttr(displayTitle)}</span>
                  ${renderDurationBadge(durText)}
                </div>
                ${metaLine}
              </div>
              ${renderPriceBoxHTML(p, false, favSvg, isAr ? 'عرض' : 'View')}
            </div>
            ${renderAdminProductBar(p)}
          </div>
        `;
      }).join('');
    }

    window.scrollTo({ top: 0, behavior: 'instant' });
    api().pushNav?.('service_variants', returnFromVariantsToPrevious);
  }

  let _closingVariants = false;
  function returnFromVariantsToPrevious() {
    if (_closingVariants) return;
    _closingVariants = true;
    try {
      api().haptic?.('light');
      activeVariantFamilyKey = null;
      const sVariants = document.getElementById('service-variants-mode');
      if (sVariants) sVariants.style.display = 'none';

      if (activeCatalog) {
        const sProds = document.getElementById('products-catalog-mode');
        if (sProds) sProds.style.display = 'block';
      } else {
        const sCats = document.getElementById('catalogs-collection-mode');
        if (sCats) sCats.style.display = 'block';
      }
      window.scrollTo({ top: 0, behavior: 'instant' });

      if (api().navStack?.length > 0 && api().navStack[api().navStack.length - 1].name === 'service_variants') {
        api().popNav?.();
      }
    } finally {
      _closingVariants = false;
    }
  }

  // --- Dedicated Product Detail View ---
  let lastActiveViewId = 'view-store';
  let _closingProductDetail = false;

  function openProductDetail(productId) {
    api().haptic?.('light');
    const all = state().allProducts || [];
    selectedProduct = all.find(p => Number(p.id) === Number(productId));
    if (!selectedProduct) return;

    state().selectedProduct = selectedProduct;
    selectedQty = 1;
    state().selectedQty = 1;

    const isAr = (state().currentAppLanguage === 'ar');
    const displayTitle = isAr
      ? (selectedProduct.custom_name_ar || selectedProduct.variant_title_ar || selectedProduct.custom_name || selectedProduct.clean_name || selectedProduct.name)
      : (selectedProduct.custom_name || selectedProduct.variant_title_en || selectedProduct.clean_name || selectedProduct.name);

    const nameEl = document.getElementById('prod-hero-name');
    if (nameEl) nameEl.innerText = displayTitle;

    const catEl = document.getElementById('prod-hero-cat');
    if (catEl) catEl.innerText = selectedProduct.category || selectedProduct.category_name || (isAr ? 'حساب رقمي' : 'Digital Service');

    const catHeader = document.getElementById('detail-category-header');
    if (catHeader) catHeader.innerText = selectedProduct.category || selectedProduct.category_name || (isAr ? 'المنتج' : 'Product');

    const heroImg = document.getElementById('prod-hero-img');
    if (heroImg) {
      const t = productThumb(selectedProduct);
      heroImg.src = t;
      heroImg.style.display = 'block';
    }

    // Rich description
    const rawDesc = (isAr && selectedProduct.description_ar) ? selectedProduct.description_ar : (selectedProduct.description || '');
    const descBox = document.getElementById('prod-rich-desc');
    if (descBox) {
      descBox.innerHTML = sec().sanitizeRichHtml ? sec().sanitizeRichHtml(rawDesc) : rawDesc;
    }

    // Spec Badges
    const isInstant = selectedProduct.delivery_type !== 'activation';
    const stockInfo = checkProductEffectiveStock(selectedProduct);
    const isOutOfStock = stockInfo.isOutOfStock;

    const delBadge = document.getElementById('prod-delivery-badge');
    if (delBadge) {
      delBadge.innerText = isInstant ? (isAr ? 'تسليم تلقائي ⚡' : 'Instant Delivery ⚡') : (isAr ? 'تفعيل مخصص ⏳' : 'Custom Activation ⏳');
      delBadge.style.display = 'inline-block';
    }

    const stockBadge = document.getElementById('prod-stock-badge');
    if (stockBadge) {
      stockBadge.innerText = isOutOfStock
        ? (isAr ? 'نفد المخزون' : 'Out of Stock')
        : (selectedProduct.stock ? `${isAr ? 'متوفر' : 'In Stock'} (${selectedProduct.stock})` : (isAr ? 'متوفر' : 'In Stock'));
      stockBadge.className = isOutOfStock ? 'pill-badge spec-pill stock-out' : 'pill-badge in-stock';
    }

    // Spec Badges (duration, warranty, type)
    const durVal = isAr ? selectedProduct.duration_ar : selectedProduct.duration_en;
    const durEl = document.getElementById('prod-dur-badge');
    if (durEl) {
      if (durVal) { durEl.innerText = durVal; durEl.style.display = 'inline-block'; }
      else durEl.style.display = 'none';
    }

    const warVal = isAr ? selectedProduct.warranty_ar : selectedProduct.warranty_en;
    const warEl = document.getElementById('prod-war-badge');
    if (warEl) {
      if (warVal) { warEl.innerText = warVal; warEl.style.display = 'inline-block'; }
      else warEl.style.display = 'none';
    }

    const typVal = isAr ? selectedProduct.type_ar : selectedProduct.type_en;
    const typEl = document.getElementById('prod-typ-badge');
    if (typEl) {
      if (typVal) { typEl.innerText = typVal; typEl.style.display = 'inline-block'; }
      else typEl.style.display = 'none';
    }

    // Admin detail buttons
    const adminEdit = document.getElementById('admin-detail-edit-container');
    if (adminEdit) adminEdit.style.display = (state().userData && state().userData.is_admin) ? 'block' : 'none';
    const adminGift = document.getElementById('admin-detail-gift-container');
    if (adminGift) adminGift.style.display = (state().userData && state().userData.is_admin) ? 'block' : 'none';

    // Quantity reset
    const qtyVal = document.getElementById('prod-qty-val');
    if (qtyVal) qtyVal.innerText = '1';

    // Pricing update
    updateDetailPagePrice();

    // Render dynamic game fields if product requires them
    if (checkout().renderProductGameFields) {
      checkout().renderProductGameFields(selectedProduct);
    }
    const fundsAlert = document.getElementById('insufficient-funds-alert');
    if (fundsAlert) fundsAlert.style.display = 'none';

    // Out of Stock & Buttons
    const restockBox = document.getElementById('restock-alert-box');
    const buyBtn = document.getElementById('btn-inapp-purchase');
    if (isOutOfStock) {
      if (restockBox) restockBox.style.display = 'block';
      if (buyBtn) buyBtn.style.display = 'none';
    } else {
      if (restockBox) restockBox.style.display = 'none';
      if (buyBtn) buyBtn.style.display = 'flex';
    }

    // Wishlist UI sync
    const wishBtn = document.getElementById('btn-detail-wishlist');
    if (wishBtn) {
      const isFav = wishlistSet.has(Number(selectedProduct.id));
      const svg = wishBtn.querySelector('.fav-icon-svg');
      if (svg) svg.classList.toggle('active', isFav);
    }

    // Remember previous active view
    const currentActive = document.querySelector('.tab-view.active') || Array.from(document.querySelectorAll('.tab-view')).find(el => el.style.display === 'block');
    if (currentActive && currentActive.id !== 'view-product-detail') {
      lastActiveViewId = currentActive.id;
    }

    // Switch view: Hide all views and show view-product-detail ONLY
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const storeEl = document.getElementById('view-store');
    if (storeEl) {
      storeEl.classList.remove('active');
      storeEl.style.display = 'none';
    }

    const detailView = document.getElementById('view-product-detail');
    if (detailView) {
      detailView.classList.add('active');
      detailView.style.display = 'block';
    }

    window.scrollTo({ top: 0, behavior: 'instant' });

    api().pushNav?.('product_detail', closeProductDetailPage);
  }

  function openProductDetailPage(productId) {
    openProductDetail(productId);
  }

  function openProductModal(product) {
    if (product) openProductDetail(product.id || product);
  }

  function openProductModalById(productId) {
    openProductDetail(productId);
  }

  function closeProductDetailPage() {
    if (_closingProductDetail) return;
    _closingProductDetail = true;
    try {
      api().haptic?.('light');
      selectedProduct = null;
      state().selectedProduct = null;

      document.querySelectorAll('.tab-view').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
      });

      const detailView = document.getElementById('view-product-detail');
      if (detailView) {
        detailView.classList.remove('active');
        detailView.style.display = 'none';
      }

      if (lastActiveViewId && lastActiveViewId !== 'view-product-detail' && lastActiveViewId !== 'view-store') {
        const prevEl = document.getElementById(lastActiveViewId);
        if (prevEl) {
          prevEl.classList.add('active');
          prevEl.style.display = 'block';
        }
      } else {
        const storeView = document.getElementById('view-store');
        if (storeView) {
          storeView.classList.add('active');
          storeView.style.display = 'block';
        }

        if (activeVariantFamilyKey) {
          const sVariants = document.getElementById('service-variants-mode');
          if (sVariants) sVariants.style.display = 'block';
          const sProds = document.getElementById('products-catalog-mode');
          if (sProds) sProds.style.display = 'none';
          const sCats = document.getElementById('catalogs-collection-mode');
          if (sCats) sCats.style.display = 'none';
        } else if (activeCatalog) {
          const sProds = document.getElementById('products-catalog-mode');
          if (sProds) sProds.style.display = 'block';
          const sVariants = document.getElementById('service-variants-mode');
          if (sVariants) sVariants.style.display = 'none';
          const sCats = document.getElementById('catalogs-collection-mode');
          if (sCats) sCats.style.display = 'none';
        } else {
          const sCats = document.getElementById('catalogs-collection-mode');
          if (sCats) sCats.style.display = 'block';
          const sProds = document.getElementById('products-catalog-mode');
          if (sProds) sProds.style.display = 'none';
          const sVariants = document.getElementById('service-variants-mode');
          if (sVariants) sVariants.style.display = 'none';
        }
      }

      window.scrollTo({ top: 0, behavior: 'instant' });

      if (api().navStack?.length > 0 && api().navStack[api().navStack.length - 1].name === 'product_detail') {
        api().popNav?.();
      }
    } finally {
      _closingProductDetail = false;
    }
  }

  function closeProductDetail() {
    closeProductDetailPage();
  }

  function closeProductModal() {
    closeProductDetailPage();
  }

  function adjustQty(delta) {
    if (!selectedProduct) return;
    const current = Number(selectedQty) || 1;
    const next = Math.max(1, current + Number(delta));
    selectedQty = next;
    state().selectedQty = next;

    const qtyVal = document.getElementById('prod-qty-val');
    if (qtyVal) qtyVal.innerText = String(next);

    updateDetailPagePrice();
  }

  function updateDetailPagePrice() {
    if (!selectedProduct) return;
    const { origPrice, finalPrice, hasDiscount, discPct } = calculateProductPrices(selectedProduct);
    const qty = Number(selectedQty) || 1;
    const totFinal = finalPrice * qty;
    const totOrig = origPrice * qty;

    const totEl = document.getElementById('prod-total-price');
    if (totEl) totEl.innerText = formatPrice(totFinal);

    const btnPrice = document.getElementById('btn-price-tag');
    if (btnPrice) btnPrice.innerText = `(${formatPrice(totFinal)})`;

    const origEl = document.getElementById('prod-original-price');
    const badgeEl = document.getElementById('prod-live-discount-badge');
    if (hasDiscount) {
      if (origEl) { origEl.innerText = formatPrice(totOrig); origEl.style.display = 'inline-block'; }
      if (badgeEl) { badgeEl.innerText = `-${discPct}%`; badgeEl.style.display = 'inline-block'; }
    } else {
      if (origEl) origEl.style.display = 'none';
      if (badgeEl) badgeEl.style.display = 'none';
    }

    const adminPricingBox = document.getElementById('admin-detail-pricing-box');
    if (adminPricingBox) {
      const isAdmin = !!(state().userData && state().userData.is_admin);
      adminPricingBox.style.display = isAdmin ? 'block' : 'none';
      if (isAdmin) {
        const costVal = Number(selectedProduct.cost_usd || selectedProduct.wholesale_price || 0) * qty;
        const sellVal = totFinal;
        const profitVal = sellVal - costVal;
        const costEl = document.getElementById('admin-detail-cost-val');
        if (costEl) costEl.innerText = formatPrice(costVal);
        const sellEl = document.getElementById('admin-detail-sell-val');
        if (sellEl) sellEl.innerText = formatPrice(sellVal);
        const profitEl = document.getElementById('admin-detail-profit-val');
        if (profitEl) {
          profitEl.innerText = `${profitVal >= 0 ? '+' : ''}${formatPrice(profitVal)}`;
          profitEl.style.color = profitVal >= 0 ? '#10b981' : '#ef4444';
        }
      }
    }
  }

  function applyCheckoutCoupon() {
    const input = document.getElementById('coupon-code-input');
    const code = (input?.value || '').trim();
    if (!code) return;
    checkout().applyCoupon?.(code);
  }

  function executeProductBuy() {
    if (!selectedProduct) return;
    api().haptic?.('medium');
    checkout().buyNow?.(selectedProduct, selectedQty);
  }

  // --- Dedicated Search Page ---
  function openSearchPage() {
    api().haptic?.('light');
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    const storeEl = document.getElementById('view-store');
    if (storeEl) {
      storeEl.classList.remove('active');
      storeEl.style.display = 'none';
    }

    const searchView = document.getElementById('view-search');
    if (searchView) {
      searchView.classList.add('active');
      searchView.style.display = 'block';
    }
    window.scrollTo({ top: 0, behavior: 'instant' });

    const isAr = (state().currentAppLanguage === 'ar');
    const arrowEl = document.getElementById('search-page-back-icon');
    if (arrowEl) arrowEl.innerText = isAr ? '→' : '←';
    const backLabel = document.getElementById('btn-back-search');
    if (backLabel) backLabel.innerText = isAr ? 'رجوع' : 'Back';

    const inp = document.getElementById('search-page-input');
    if (inp) {
      setTimeout(() => { try { inp.focus(); } catch (_) {} }, 100);
    }

    api().pushNav?.('search_page', closeSearchPage);
  }

  let _closingSearch = false;
  function closeSearchPage() {
    if (_closingSearch) return;
    _closingSearch = true;
    try {
      api().haptic?.('light');
      const inp = document.getElementById('search-page-input');
      if (inp) { inp.value = ''; try { inp.blur(); } catch (_) {} }

      document.querySelectorAll('.tab-view').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
      });

      const searchView = document.getElementById('view-search');
      if (searchView) {
        searchView.classList.remove('active');
        searchView.style.display = 'none';
      }

      const prevTab = state().activeTab || 'store';
      const tabView = document.getElementById('view-' + prevTab) || document.getElementById('view-store');
      if (tabView) {
        tabView.classList.add('active');
        tabView.style.display = 'block';
      }
      window.scrollTo({ top: 0, behavior: 'instant' });

      if (api().navStack?.length > 0 && api().navStack[api().navStack.length - 1].name === 'search_page') {
        api().popNav?.();
      }
    } finally {
      _closingSearch = false;
    }
  }

  function clearSearchPageInput() {
    api().haptic?.('light');
    const inp = document.getElementById('search-page-input');
    if (inp) inp.value = '';
    handleSearchPageInput();
  }

  function handleSearchPageInput() {
    const inp = document.getElementById('search-page-input');
    const rawQ = (inp?.value || '').trim().toLowerCase();
    const clearBtn = document.getElementById('search-page-clear-btn');
    const emptyState = document.getElementById('search-page-empty-state');
    const resultsBox = document.getElementById('search-page-results');
    const listContainer = document.getElementById('search-page-products-list');
    const isAr = (state().currentAppLanguage === 'ar');

    if (!rawQ) {
      if (clearBtn) clearBtn.style.display = 'none';
      if (emptyState) emptyState.style.display = 'flex';
      if (resultsBox) resultsBox.style.display = 'none';
      return;
    }

    if (clearBtn) clearBtn.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';
    if (resultsBox) resultsBox.style.display = 'block';

    let queryTokens = [rawQ];
    for (const [k, aliases] of Object.entries(SEARCH_ALIASES)) {
      if (rawQ.includes(k) || k.includes(rawQ)) {
        queryTokens.push(...aliases);
      }
    }

    const all = state().allProducts || [];
    let matched = all.filter(p => {
      const nameStr = ((p.clean_name || '') + ' ' + (p.name || '') + ' ' + (p.custom_name || '') + ' ' + (p.custom_name_ar || '')).toLowerCase();
      const descStr = ((p.description || '') + ' ' + (p.description_ar || '')).toLowerCase();
      const catStr = (p.category || p.category_name || '').toLowerCase();
      return queryTokens.some(tok => nameStr.includes(tok) || descStr.includes(tok) || catStr.includes(tok));
    });

    matched = filterAndSortProducts(matched);

    const countBar = document.getElementById('search-results-count-bar');
    if (countBar) {
      countBar.innerText = isAr ? `${matched.length} منتج مطابق للبحث` : `${matched.length} product(s) found`;
    }

    if (!matched.length) {
      if (listContainer) {
        listContainer.innerHTML = `
          <div style="text-align: center; padding: 40px 20px; color: var(--hint);">
            <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
            <div style="font-size: 14px; font-weight: 700; color: var(--text);">${isAr ? 'لا توجد نتائج مطابقة' : 'No matching results'}</div>
          </div>
        `;
      }
      return;
    }

    if (listContainer) {
      listContainer.innerHTML = matched.map(p => {
        const isFav = wishlistSet.has(Number(p.id));
        const stockInfo = checkProductEffectiveStock(p);
        const isOutOfStock = stockInfo.isOutOfStock;
        const isActivation = (p.delivery_type === 'activation');
        const durText = (isAr ? p.duration_ar : p.duration_en) || null;
        const stockText = (!isOutOfStock && p.stock) ? `${isAr ? 'متوفر' : 'In stock'} (${p.stock})` : ((!isOutOfStock) ? (isAr ? 'متوفر' : 'In stock') : '');
        const metaLine = productMetaLine({ isOutOfStock, isActivation, duration: durText, multiCount: 0, stockText });
        const favSvg = `
          <svg class="fav-icon-svg ${isFav ? 'active' : ''}" viewBox="0 0 24 24" width="18" height="18">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
        `;
        const displayTitle = isAr ? (p.custom_name_ar || p.name) : (p.custom_name || p.name);
        const thumb = productThumb(p);

        return `
          <div class="product-row" onclick="openProductDetail(${Number(p.id)})">
            <div class="prod-row-top">
              <div class="prod-thumb">${thumbImg(thumb, displayTitle)}</div>
              <div class="prod-left">
                <div class="prod-title-wrap">
                  <span class="prod-title" title="${escAttr(displayTitle)}">${escAttr(displayTitle)}</span>
                  ${renderDurationBadge(durText)}
                </div>
                ${metaLine}
              </div>
              ${renderPriceBoxHTML(p, false, favSvg, isAr ? 'عرض' : 'View')}
            </div>
            ${renderAdminProductBar(p)}
          </div>
        `;
      }).join('');
    }
  }

  function filterCatalog(query) {
    openSearchPage();
    const inp = document.getElementById('search-page-input');
    if (inp) {
      inp.value = query || '';
      handleSearchPageInput();
    }
  }

  function toggleProductWishlist(productId) {
    api().haptic?.('light');
    const pid = Number(productId);
    if (wishlistSet.has(pid)) wishlistSet.delete(pid);
    else wishlistSet.add(pid);
    try { root.localStorage?.setItem('ghstore_wishlist', JSON.stringify(Array.from(wishlistSet))); } catch (_) {}
    if (activeCatalog) openCollection(activeCatalog);
  }

  function toggleCurrentProductWishlist() {
    if (selectedProduct) toggleProductWishlist(selectedProduct.id);
  }

  function shareCurrentProduct() {
    if (!selectedProduct) return;
    const bot = state().userData?.bot_username || 'gh_store1_bot';
    const link = `https://t.me/${bot}?startapp=p_${selectedProduct.id}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(link);
      api().showToast(state().currentAppLanguage === 'ar' ? 'تم نسخ رابط المنتج!' : 'Product link copied!');
    }
  }

  // --- Flash Sale Countdown Timer ---
  let flashSaleInterval = null;
  function initFlashSaleTimer(saleData = null) {
    const banner = document.getElementById('flash-sale-banner');
    const timerEl = document.getElementById('flash-countdown-timer');
    if (!banner || !timerEl) return;

    if (!saleData || !saleData.enabled) {
      banner.style.display = 'none';
      return;
    }

    banner.style.display = 'flex';
    const endTs = Number(saleData.end_timestamp || 0) * 1000;
    if (flashSaleInterval) clearInterval(flashSaleInterval);

    const update = () => {
      const diff = Math.max(0, Math.floor((endTs - Date.now()) / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      timerEl.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
      if (diff <= 0 && flashSaleInterval) clearInterval(flashSaleInterval);
    };
    update();
    flashSaleInterval = setInterval(update, 1000);
  }

  // --- Reviews & Support Modals ---
  function openReviewsModal() {
    api().haptic?.('light');
    const m = document.getElementById('customer-review-modal') || document.getElementById('modal-customer-reviews');
    if (m) {
      m.style.display = 'flex';
      api().pushNav('reviews_modal', closeReviewsModal);
    }
  }

  function closeReviewsModal() {
    const m = document.getElementById('customer-review-modal') || document.getElementById('modal-customer-reviews');
    if (m) m.style.display = 'none';
  }

  function openSupportModal() {
    api().haptic?.('light');
    const m = document.getElementById('modal-support-ticket');
    if (m) {
      m.style.display = 'flex';
      api().pushNav('support_modal', closeSupportModal);
    }
  }

  function closeSupportModal() {
    const m = document.getElementById('modal-support-ticket');
    if (m) m.style.display = 'none';
  }

  // --- Export Namespace ---
  const Module = {
    SEARCH_ALIASES,
    setCatalogViewMode,
    switchCategoryViewMode,
    renderCatalogsGrid,
    renderCategories,
    openCollection,
    selectCategory,
    returnToCollections,
    applyCatalogFilter,
    renderProductItems,
    renderStorefrontFolderCards,
    openServiceVariantsByIndex,
    returnFromVariantsToPrevious,
    openProductDetail,
    openProductDetailPage,
    openProductModal,
    openProductModalById,
    closeProductDetail,
    closeProductDetailPage,
    closeProductModal,
    adjustQty,
    updateDetailPagePrice,
    applyCheckoutCoupon,
    executeProductBuy,
    openSearchPage,
    closeSearchPage,
    handleSearchPageInput,
    clearSearchPageInput,
    filterCatalog,
    toggleProductWishlist,
    toggleCurrentProductWishlist,
    shareCurrentProduct,
    initFlashSaleTimer,
    openReviewsModal,
    closeReviewsModal,
    openSupportModal,
    closeSupportModal,
    formatPrice,
    calculateProductPrices,
    checkProductEffectiveStock,
    getProductFamilyKey
  };

  root.StorefrontModule = Module;

  // Bind directly on window for template inline onclick handlers
  root.setCatalogViewMode = setCatalogViewMode;
  root.switchCategoryViewMode = switchCategoryViewMode;
  root.openCollection = openCollection;
  root.selectCategory = selectCategory;
  root.returnToCollections = returnToCollections;
  root.applyCatalogFilter = applyCatalogFilter;
  root.openServiceVariantsByIndex = openServiceVariantsByIndex;
  root.returnFromVariantsToPrevious = returnFromVariantsToPrevious;
  root.openProductDetail = openProductDetail;
  root.openProductDetailPage = openProductDetailPage;
  root.openProductModal = openProductModal;
  root.openProductModalById = openProductModalById;
  root.closeProductDetail = closeProductDetail;
  root.closeProductDetailPage = closeProductDetailPage;
  root.closeProductModal = closeProductModal;
  root.adjustQty = adjustQty;
  root.applyCheckoutCoupon = applyCheckoutCoupon;
  root.executeProductBuy = executeProductBuy;
  root.openSearchPage = openSearchPage;
  root.closeSearchPage = closeSearchPage;
  root.handleSearchPageInput = handleSearchPageInput;
  root.clearSearchPageInput = clearSearchPageInput;
  root.toggleCurrentProductWishlist = toggleCurrentProductWishlist;
  root.shareCurrentProduct = shareCurrentProduct;

})(typeof window !== 'undefined' ? window : globalThis);
