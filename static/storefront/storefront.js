/**
 * GH Store - Catalog, Categories, Search, & Product Detail Module (storefront.js)
 * 
 * Provides:
 * - Dynamic category rendering with grid/list mode toggle
 * - Brand folder grouping with in-stock priority partitioning
 * - Dedicated variants page subview for family collections
 * - Alias-powered smart search with autocomplete chips
 * - Product detail sheet with spec badges, live discounts, and warranty info
 * - Flash sale countdown timer and reviews / support modals
 */
(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};

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

  // --- Category View Mode: Grid vs List ---
  let currentCatalogViewMode = 'grid';
  try {
    currentCatalogViewMode = root.localStorage?.getItem('ghstore_cat_view') || 'grid';
  } catch (_) {}

  function switchCategoryViewMode(mode) {
    currentCatalogViewMode = mode;
    try { root.localStorage?.setItem('ghstore_cat_view', mode); } catch (_) {}
    api().haptic?.('light');
    renderCategories(state().categoriesList);
  }

  // --- Dynamic Categories Rendering ---
  function renderCategories(categories, activeCatId = null) {
    state().categoriesList = categories || [];
    const container = document.getElementById('categories-container');
    if (!container) return;

    if (!categories || categories.length === 0) {
      container.innerHTML = '<div class="empty-state-card">لا توجد تصنيفات متاحة حالياً</div>';
      return;
    }

    const isAr = (state().currentAppLanguage === 'ar');
    let html = `<div class="cat-mode-header">
      <div class="cat-mode-title">${isAr ? 'التصنيفات الرئيسية' : 'Categories'}</div>
      <div class="cat-mode-toggles">
        <button class="cat-toggle-btn ${currentCatalogViewMode === 'grid' ? 'active' : ''}" onclick="switchCategoryViewMode('grid')">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M3 3h8v8H3zm10 0h8v8h-8zM3 13h8v8H3zm10 0h8v8h-8z"/></svg>
        </button>
        <button class="cat-toggle-btn ${currentCatalogViewMode === 'list' ? 'active' : ''}" onclick="switchCategoryViewMode('list')">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M3 4h18v2H3zm0 7h18v2H3zm0 7h18v2H3z"/></svg>
        </button>
      </div>
    </div>`;

    if (currentCatalogViewMode === 'grid') {
      html += '<div class="categories-grid-cards">';
      categories.forEach(cat => {
        const title = isAr ? (cat.name_ar || cat.name) : (cat.name || cat.name_ar);
        const icon = cat.icon_url ? api().thumbImg(cat.icon_url, title) : '📦';
        const isActive = (activeCatId && String(cat.id) === String(activeCatId));
        html += `<div class="cat-grid-card ${isActive ? 'active' : ''}" onclick="selectCategory('${cat.id}')">
          <div class="cat-card-icon">${icon}</div>
          <div class="cat-card-name">${api().escapeAttr(title)}</div>
        </div>`;
      });
      html += '</div>';
    } else {
      html += '<div class="categories-list-rows">';
      categories.forEach(cat => {
        const title = isAr ? (cat.name_ar || cat.name) : (cat.name || cat.name_ar);
        const icon = cat.icon_url ? api().thumbImg(cat.icon_url, title) : '📦';
        html += `<div class="cat-list-row" onclick="selectCategory('${cat.id}')">
          <div class="cat-row-icon">${icon}</div>
          <div class="cat-row-info">
            <div class="cat-row-title">${api().escapeAttr(title)}</div>
            <div class="cat-row-sub">${cat.products_count || 0} ${isAr ? 'منتج متوفر' : 'products available'}</div>
          </div>
          <div class="cat-row-arrow">❯</div>
        </div>`;
      });
      html += '</div>';
    }

    container.innerHTML = html;
  }

  function selectCategory(catId) {
    api().haptic?.('selection');
    const all = state().allProducts || [];
    const filtered = all.filter(p => String(p.category_id) === String(catId));
    renderStorefrontFolderCards(filtered.length > 0 ? filtered : all);
  }

  // --- Folder Cards & In-Stock Priority Partitioning ---
  function renderStorefrontFolderCards(products) {
    const listEl = document.getElementById('products-container');
    if (!listEl) return;

    if (!products || products.length === 0) {
      listEl.innerHTML = '<div class="empty-state-card">لا توجد منتجات مطابقة في هذا التصنيف</div>';
      return;
    }

    // In-Stock Partitioning: In-stock items ALWAYS at the top, out-of-stock sink to bottom
    const inStock = [];
    const outOfStock = [];
    products.forEach(p => {
      const stock = (p.stock !== null && p.stock !== undefined) ? Number(p.stock) : 999;
      if (stock > 0) inStock.push(p);
      else outOfStock.push(p);
    });

    const sorted = [...inStock, ...outOfStock];
    const isAr = (state().currentAppLanguage === 'ar');

    let html = '<div class="products-folder-grid">';
    sorted.forEach(p => {
      const title = isAr ? (p.name_ar || p.name) : (p.name || p.name_ar);
      const stock = (p.stock !== null && p.stock !== undefined) ? Number(p.stock) : 999;
      const isOos = (stock <= 0);
      const thumb = p.image_url ? api().thumbImg(p.image_url, title) : `<div class="prod-thumb-placeholder">GH</div>`;
      const priceStr = `$${Number(p.sell_price_usd || 0).toFixed(2)}`;

      html += `<div class="product-card-item ${isOos ? 'oos-card' : ''}" onclick="openProductModalById(${p.id})">
        <div class="prod-card-thumb-wrap">
          ${thumb}
          ${isOos ? '<span class="badge-oos">نفذت الكمية</span>' : '<span class="badge-instock">متوفر</span>'}
        </div>
        <div class="prod-card-content">
          <div class="prod-card-title">${api().escapeAttr(title)}</div>
          <div class="prod-card-meta">
            <div class="prod-card-price">${priceStr}</div>
            <button class="btn-quick-view" onclick="event.stopPropagation(); openProductModalById(${p.id})">
              ${isAr ? 'طلب' : 'View'}
            </button>
          </div>
        </div>
      </div>`;
    });
    html += '</div>';

    listEl.innerHTML = html;
  }

  // --- Smart Search with Alias Expansion & Filters ---
  function filterCatalog(query) {
    const raw = String(query || '').trim().toLowerCase();
    const all = state().allProducts || [];
    if (!raw) {
      renderStorefrontFolderCards(all);
      return;
    }

    const tokens = raw.split(/\s+/).filter(Boolean);
    const expandedTokens = new Set(tokens);
    for (const [alias, targets] of Object.entries(SEARCH_ALIASES)) {
      if (raw.includes(alias)) {
        targets.forEach(t => expandedTokens.add(t));
      }
    }

    const filtered = all.filter(p => {
      const name = (p.name || '').toLowerCase();
      const nameAr = (p.name_ar || '').toLowerCase();
      const cat = (p.category_name || '').toLowerCase();
      const desc = (p.description || '').toLowerCase();
      const text = `${name} ${nameAr} ${cat} ${desc}`;

      return Array.from(expandedTokens).some(tok => text.includes(tok));
    });

    renderStorefrontFolderCards(filtered);
  }

  // --- Product Detail Modal ---
  function openProductModalById(productId) {
    const all = state().allProducts || [];
    const prod = all.find(p => Number(p.id) === Number(productId));
    if (prod) openProductModal(prod);
  }

  function openProductModal(product) {
    state().selectedProduct = product;
    state().selectedQty = 1;
    api().haptic?.('pop');

    const modal = document.getElementById('product-detail-modal');
    if (!modal) return;

    const isAr = (state().currentAppLanguage === 'ar');
    const title = isAr ? (product.name_ar || product.name) : (product.name || product.name_ar);

    // Populate Fields
    const titleEl = document.getElementById('detail-product-title');
    if (titleEl) titleEl.textContent = title;

    const priceEl = document.getElementById('detail-product-price');
    if (priceEl) priceEl.textContent = `$${Number(product.sell_price_usd || 0).toFixed(2)}`;

    const descEl = document.getElementById('detail-product-desc');
    if (descEl) {
      descEl.innerHTML = api().formatRichDescription(product.description || '');
    }

    const imgEl = document.getElementById('detail-product-img');
    if (imgEl) {
      imgEl.src = product.image_url ? api().assetUrl(product.image_url) : '';
      imgEl.style.display = product.image_url ? 'block' : 'none';
    }

    // Spec Badges
    const badgeContainer = document.getElementById('detail-spec-badges');
    if (badgeContainer) {
      const deliveryBadge = (product.delivery_type === 'stock') ? 'تسليم فوري ⚡' : 'شحن رقمي ⏳';
      const warrantyBadge = product.warranty_days ? `ضمان ${product.warranty_days} يوم 🛡️` : 'ضمان متجر GH 🛡️';
      badgeContainer.innerHTML = `
        <span class="spec-pill">${deliveryBadge}</span>
        <span class="spec-pill">${warrantyBadge}</span>
        <span class="spec-pill supplier-pill">${product.supplier || 'BatStore'}</span>
      `;
    }

    modal.style.display = 'flex';
    modal.classList.add('active');

    api().pushNav('product_modal', closeProductModal);
  }

  function closeProductModal() {
    api().haptic?.('light');
    const modal = document.getElementById('product-detail-modal');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('active');
    }
    state().selectedProduct = null;
  }

  // --- Flash Sale Live Timer ---
  let flashSaleInterval = null;
  function initFlashSaleTimer(seconds = 3600 * 4) {
    let remaining = seconds;
    const timerEl = document.getElementById('flash-sale-timer');
    if (!timerEl) return;

    if (flashSaleInterval) clearInterval(flashSaleInterval);
    flashSaleInterval = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      const h = Math.floor(remaining / 3600);
      const m = Math.floor((remaining % 3600) / 60);
      const s = remaining % 60;
      timerEl.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
      if (remaining <= 0) clearInterval(flashSaleInterval);
    }, 1000);
  }

  // --- Reviews Modal ---
  function openReviewsModal() {
    api().haptic?.('light');
    const m = document.getElementById('modal-customer-reviews');
    if (m) {
      m.style.display = 'flex';
      api().pushNav('reviews_modal', closeReviewsModal);
    }
  }

  function closeReviewsModal() {
    const m = document.getElementById('modal-customer-reviews');
    if (m) m.style.display = 'none';
  }

  // --- Support Ticket Modal ---
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
  root.StorefrontModule = {
    SEARCH_ALIASES,
    switchCategoryViewMode,
    renderCategories,
    selectCategory,
    renderStorefrontFolderCards,
    filterCatalog,
    openProductModal,
    openProductModalById,
    closeProductModal,
    initFlashSaleTimer,
    openReviewsModal,
    closeReviewsModal,
    openSupportModal,
    closeSupportModal
  };

})(typeof window !== 'undefined' ? window : globalThis);
