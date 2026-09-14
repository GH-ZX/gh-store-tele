/**
 * GH Store - Main Application Orchestrator & Compatibility Bootstrap (app.js)
 * 
 * Coordinates:
 * - Module integration (StoreAPI, StorefrontModule, WalletModule, StoreCheckout, AdminModule)
 * - Exposes unified global window API for all inline HTML onclick handlers
 * - Preserves security formatter functions for unit and security suites
 * - Boots Telegram WebApp SDK, safe areas, layout directions (RTL/LTR), and theme
 * - Manages real-time SSE stream, keyboard navigation, and automatic Checkout Recovery
 */

    function formatRichDescription(raw) {
      if (!raw) return `<span style="color: var(--hint)">${(window.currentAppLanguage || 'ar') === 'ar' ? 'لا يوجد وصف إضافي.' : 'No additional description.'}</span>`;
      let text = String(raw).trim();

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
        links.push('<a href="' + escapeAttr(StorefrontSecurity.safeUrl(url)) + '" class="desc-link">' + escapeAttr(label) + '</a>');
        return placeholder;
      });

      text = text.replace(/(https?:\/\/[^\s<"'\)]+)/gi, (url) => {
        const cleanUrl = url.replace(/[.,;]+$/, '');
        const trailing = url.slice(cleanUrl.length);
        const placeholder = '___LINK_' + links.length + '___';
        links.push('<a href="' + escapeAttr(StorefrontSecurity.safeUrl(cleanUrl)) + '" class="desc-link">' + escapeAttr(cleanUrl) + '</a>');
        return placeholder + trailing;
      });

      links.forEach((linkHtml, idx) => {
        text = text.replace('___LINK_' + idx + '___', linkHtml);
      });
      text = text.replace(/\r?\n/g, '<br>');
      text = text.replace(/(<br\s*\/?>){3,}/gi, '<br><br>');

      return StorefrontSecurity.sanitizeRichHtml(text);
    }

    function escapeAttr(str) {
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function escAttr(s) {
      return StorefrontSecurity.escapeHtml(s);
    }

    function instructionStepsHTML(steps) {
      return steps.map((step, idx) => `<div class="instr-step"><span class="instr-step-num">${idx + 1}</span><span class="instr-step-text">${formatRichDescription(step)}</span></div>`).join('');
    }

    function normalizeCredentialItem(raw) {
      if (!raw) return '';
      if (typeof raw === 'object' && raw !== null) {
        return (
          raw.account_data || raw.value || raw.data || raw.credentials || raw.key || raw.code || raw.token ||
          (raw.email && raw.password ? `${raw.email}:${raw.password}` : null) ||
          (raw.username && raw.password ? `${raw.username}:${raw.password}` : null) ||
          JSON.stringify(raw)
        );
      }
      let s = String(raw).trim();
      if (s.startsWith('{') && s.endsWith('}')) {
        try {
          const parsed = JSON.parse(s);
          if (typeof parsed === 'object' && parsed !== null) {
            return normalizeCredentialItem(parsed);
          }
        } catch (e) {}
        const m = s.match(/['"](?:account_data|value|data|credentials|key|code|token)['"]\s*:\s*['"]([^'"]+)['"]/);
        if (m && m[1]) return m[1];
      }
      return s;
    }

    function renderStructuredCredentials(goods) {
      if (!goods || !goods.length) {
        return `<div style="padding: 12px; color: var(--warning); text-align: center;">${(window.currentAppLanguage || 'ar') === 'ar' ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
      }

      const isAr = ((window.currentAppLanguage || 'ar') === 'ar');
      const normalizedGoods = goods.map(g => normalizeCredentialItem(g)).filter(Boolean);

      if (!normalizedGoods.length) {
        return `<div style="padding: 12px; color: var(--warning); text-align: center;">${isAr ? 'جاري التفعيل، سيتم التسليم قريباً.' : 'Activation in progress, delivery shortly.'}</div>`;
      }

      const renderedRows = normalizedGoods.map(rawLine => {
        const line = String(rawLine).trim();

        // 1. If it's an activation / direct subscription link (e.g. Gemini, Google One, Canva, etc.)
        if (line.startsWith('http://') || line.startsWith('https://')) {
          const isGemini = line.toLowerCase().includes('google') || line.toLowerCase().includes('gemini');
          let hostName = 'serviceactivation.google.com';
          try {
            const u = new URL(line);
            hostName = u.hostname || hostName;
          } catch (e) {}

          const badgeText = isGemini
            ? (isAr ? '✨ كود تفعيل اشتراك Gemini Pro المعتمد' : '✨ Gemini Pro Activation Token')
            : (isAr ? '✨ كود تفعيل الاشتراك المباشر' : '✨ Direct Activation Token');

          const activateBtnText = isAr
            ? '⚡ تفعيل حسابك الآن عبر هذا الرابط'
            : '⚡ Activate Your Account using this Token';

          const copyBtnText = isAr
            ? '📋 نسخ رابط التفعيل المباشر'
            : '📋 Copy Direct Activation Link';

          const hintText = isAr
            ? '💡 اضغط على الزر البنفسجي بالأعلى لفتح الرابط وتفعيل حسابك فورياً، أو انسخ الرابط لفتحه في متصفحك.'
            : '💡 Tap the button above to activate your account directly, or copy the token link to open in your browser.';

          return `
            <div class="inset-card" style="margin: 8px 0 14px 0; border: 1px solid rgba(168, 85, 247, 0.45); background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(56, 189, 248, 0.08)); padding: 16px; border-radius: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span class="pill-badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; font-size: 11px; font-weight: 800; padding: 4px 10px;">
                  ${badgeText}
                </span>
                <span style="font-size: 11px; color: var(--hint); font-weight: 700;">1-Tap Token</span>
              </div>

              <!-- Spacious, Elegant URL Container with Domain Header -->
              <div style="background: var(--input-bg); border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 12px; padding: 12px; margin-bottom: 14px; box-shadow: inset 0 2px 6px rgba(0,0,0,0.25);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px dashed var(--border); padding-bottom: 6px; flex-wrap: wrap; gap: 4px;">
                  <span style="font-size: 11px; font-weight: 800; color: var(--accent); font-family: monospace; display: inline-flex; align-items: center; gap: 4px; word-break: break-all;">
                    🌐 ${escapeAttr(hostName)}
                  </span>
                  <span style="font-size: 10px; color: var(--success); font-weight: 700; white-space: nowrap;">
                    ↗ ${isAr ? 'رابط خارجي' : 'External Link'}
                  </span>
                </div>
                <div style="font-family: monospace; font-size: 11px; color: var(--text); word-break: break-all; line-height: 1.6; user-select: all; max-height: 180px; overflow-y: auto; padding: 4px 2px;">
                  ${escapeAttr(line)}
                </div>
              </div>

              <!-- Big Prominent Activation Button -->
              <button type="button" class="btn-action-primary" data-payment-url="${escapeAttr(line)}" onclick="openExternalPaymentUrl(this.dataset.paymentUrl)" style="width: 100%; height: 50px; font-size: 13.5px; font-weight: 800; background: linear-gradient(135deg, #a855f7, #6366f1); border-radius: 12px; box-shadow: 0 4px 16px rgba(168, 85, 247, 0.35); display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 8px; border: none; color: white; cursor: pointer;">
                <span>${activateBtnText}</span>
              </button>

              <!-- Clean Separated Copy Button -->
              <button type="button" class="btn-action-secondary" data-copy="${escapeAttr(line)}" onclick="copyFromBtn(this)" style="width: 100%; height: 40px; font-size: 12px; font-weight: 700; border-radius: 10px; border-color: rgba(168, 85, 247, 0.4); color: var(--text); display: flex; align-items: center; justify-content: center; gap: 6px;">
                <span>${copyBtnText}</span>
              </button>

              <div style="font-size: 10.5px; color: var(--hint); margin-top: 10px; text-align: center; line-height: 1.5;">
                ${hintText}
              </div>
            </div>
          `;
        }

        // 2. Delimiter parsing: pipe '|', slash '/', or colon ':'
        let parts = [];
        if (line.includes(' | ')) { parts = line.split(' | '); }
        else if (line.includes('|')) { parts = line.split('|'); }
        else if (line.includes(' / ')) { parts = line.split(' / '); }
        else if (line.includes(':') && line.split(':').length >= 2) {
          parts = line.split(':');
        }

        if (parts.length >= 2) {
          const rows = parts.map((partRaw, idx) => {
            const part = String(partRaw).trim();
            let label = isAr ? "بيانات" : "Credential";
            if (idx === 0) {
              label = part.includes('@') ? (isAr ? "البريد الإلكتروني" : "Email") : (isAr ? "اسم المستخدم" : "Username");
            } else if (idx === 1) {
              label = isAr ? "كلمة المرور" : "Password";
            } else if (idx === 2) {
              label = part.includes('@') ? (isAr ? "البريد البديل / الاسترداد" : "Recovery Email") : (isAr ? "كود 2FA / الأمان" : "2FA / Security Key");
            } else if (idx === 3) {
              label = isAr ? "رمز الأمان / كلمة سر البديل" : "Security Key / Recovery Pass";
            } else {
              label = isAr ? `معلومة ${idx + 1}` : `Field ${idx + 1}`;
            }

            return `
              <div class="cred-pill-row">
                <div class="cred-meta">
                  <span class="cred-type-tag">${label}</span>
                  <span class="cred-val-text">${escapeAttr(part)}</span>
                </div>
                <button class="btn-copy-mini" data-copy="${escapeAttr(part)}" onclick="copyFromBtn(this)">${isAr ? 'نسخ' : 'Copy'}</button>
              </div>
            `;
          }).join('');

          return `
            <div class="cred-grid">
              ${rows}
            </div>
          `;
        }

        // 3. Fallback: single license key / code
        return `
          <div class="cred-pill-row" style="margin: 6px 0;">
            <div class="cred-meta">
              <span class="cred-type-tag">${isAr ? 'مفتاح / كود التفعيل' : 'License / Key'}</span>
              <span class="cred-val-text">${escapeAttr(line)}</span>
            </div>
            <button class="btn-copy-mini" data-copy="${escapeAttr(line)}" onclick="copyFromBtn(this)">${isAr ? 'نسخ' : 'Copy'}</button>
          </div>
        `;
      }).join('');

      const hasOnlyUrls = normalizedGoods.every(g => g.startsWith('http://') || g.startsWith('https://'));
      const allText = normalizedGoods.join('\n');
      const copyAllBtn = hasOnlyUrls ? '' : `
        <div style="margin-top: 8px;">
          <button class="btn-action-secondary" data-copy="${escapeAttr(allText)}" onclick="copyFromBtn(this)" style="height: 34px; font-size: 11px; width: 100%;">
            <span>📋 ${isAr ? 'نسخ كافة بيانات الحساب' : 'Copy All Account Details'}</span>
          </button>
        </div>
      `;

      return renderedRows + copyAllBtn;
    }

    function openExternalPaymentUrl(url) {
      const cleanUrl = StorefrontSecurity?.safeUrl ? StorefrontSecurity.safeUrl(url) : url;
      if (!cleanUrl) return;
      api().haptic?.('light');
      const tg = api().getTg?.() || window.Telegram?.WebApp;
      if (tg?.openLink) {
        try {
          tg.openLink(cleanUrl);
          return;
        } catch (_) {}
      }
      window.open(cleanUrl, '_blank', 'noopener,noreferrer');
    }

    function copyCredText(text, btn) {
      api().haptic?.('success');
      const targetBtn = btn || (window.event?.currentTarget);
      const originalText = targetBtn ? targetBtn.innerText : null;
      const isAr = ((state().currentAppLanguage || window.currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');

      if (targetBtn) {
        targetBtn.innerText = isAr ? '✅ تم النسخ!' : '✅ Copied!';
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
          api().showToast?.(isAr ? 'تم النسخ بنجاح! 📋' : 'Copied successfully! 📋');
        }).catch(() => fallbackCopy(text));
      } else {
        fallbackCopy(text);
      }
    }

    function fallbackCopy(text) {
      try {
        const isAr = ((state().currentAppLanguage || window.currentAppLanguage || root.localStorage?.getItem('ghstore_lang') || 'ar') === 'ar');
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        api().showToast?.(isAr ? 'تم النسخ بنجاح! 📋' : 'Copied successfully! 📋');
      } catch (_) {}
    }

    function copyFromBtn(btn) {
      if (!btn) return;
      const text = btn.getAttribute('data-copy') || '';
      copyCredText(text, btn);
    }
    const copyCredFromBtn = copyFromBtn;

    function assetUrl(u) {
      if (!u) return '';
      let clean = StorefrontSecurity.safeUrl(u, true);
      if (!clean) return '';
      // These URLs are also used in CSS url('...') inside HTML attributes.
      clean = clean.replace(/['"()\\<>]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
      if (String(u).trim().startsWith('/static/img/')) {
        const v = localStorage.getItem('ghstore_build') || '4';
        return clean + (clean.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(v);
      }
      return clean;
    }

    function thumbImg(src, name) {
      const safe = escAttr(assetUrl(src));
      const nm = escAttr(name);
      return '<img src="' + safe + '" alt="' + nm + '" loading="lazy" data-n="' + nm + '" onerror="window.__thumbErr(this)">';
    }

(function (root) {
  'use strict';

  const api = () => root.StoreAPI || {};
  const state = () => root.StoreAPI?.AppState || {};
  const storefront = () => root.StorefrontModule || {};
  const wallet = () => root.WalletModule || {};
  const checkout = () => root.StoreCheckout || {};
  const admin = () => root.AdminModule || {};
  const sms = () => root.SmsModule || {};

  // --- Tab Navigation ---
  function switchTab(tab) {
    state().activeTab = tab;
    api().haptic?.('selection');

    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });

    ['store', 'orders', 'wallet', 'settings'].forEach(t => {
      const tabBtn = document.getElementById(`tab-${t}`);
      const viewEl = document.getElementById(`view-${t}`);
      const isCurrent = (t === tab);
      if (tabBtn) {
        tabBtn.classList.toggle('active', isCurrent);
        tabBtn.setAttribute('aria-selected', isCurrent ? 'true' : 'false');
      }
      if (viewEl) {
        if (isCurrent) {
          viewEl.classList.add('active');
          viewEl.style.display = 'block';
        } else {
          viewEl.classList.remove('active');
          viewEl.style.display = 'none';
        }
      }
    });
    window.scrollTo({ top: 0, behavior: 'instant' });

    if (tab === 'orders') {
      const isAdmin = !!(state().userData?.is_admin || window.userData?.is_admin);
      const radarHeader = document.getElementById('admin-radar-header-box');
      const attChip = document.getElementById('act-filter-attention');
      const trChip = document.getElementById('act-filter-transfers');
      if (isAdmin) {
        if (radarHeader) radarHeader.style.display = 'block';
        if (attChip) attChip.style.display = 'inline-block';
        if (trChip) trChip.style.display = 'inline-block';
        if (root.loadAdminLiveRadar) root.loadAdminLiveRadar();
        else loadUserOrders();
      } else {
        if (radarHeader) radarHeader.style.display = 'none';
        if (attChip) attChip.style.display = 'none';
        if (trChip) trChip.style.display = 'none';
        loadUserOrders();
      }
    } else if (tab === 'wallet') {
      wallet().renderWalletBalances?.();
    }
  }

  // --- Copy Credential Helper ---
  function copyCredFromBtn(btn) {
    if (!btn) return;
    const val = btn.getAttribute('data-copy') || '';
    if (!val) return;
    navigator.clipboard?.writeText(val);
    api().haptic?.('light');
    api().showToast(api().t('toast-copied', 'تم النسخ بنجاح!'));
  }

  function copyFromBtn(btn) {
    copyCredFromBtn(btn);
  }

  // --- Data Loading & Synchronization ---
  let catalogRequest = null;
  function loadStorefrontData() {
    if (!catalogRequest) {
      catalogRequest = fetchStorefrontData().finally(() => { catalogRequest = null; });
    }
    return catalogRequest;
  }

  async function fetchStorefrontData() {
    try {
      const res = await fetch('/api/catalog');
      if (!res.ok) throw new Error('Catalog HTTP ' + res.status);
      {
        const data = await res.json();
        if (!Array.isArray(data.categories) || !Array.isArray(data.products)) throw new Error('Invalid catalog response');
        state().categoriesList = data.categories || [];
        state().allFolders = data.folders || [];
        state().allProducts = data.products || [];
        if (data.store_logo_url) applyStoreLogo(data.store_logo_url);
        if (data.flash_sale) storefront().initFlashSaleTimer?.(data.flash_sale);
        storefront().renderCatalogsGrid?.(state().categoriesList);
        const productsView = document.getElementById('products-catalog-mode');
        if (productsView && productsView.style.display !== 'none') {
          storefront().refreshVisibleCatalog?.();
        }
        const status = document.getElementById('catalog-load-status');
        if (status) { status.hidden = true; status.replaceChildren(); }
      }
    } catch (e) {
      console.warn('Failed to fetch catalog:', e);
      const isAr = state().currentAppLanguage === 'ar';
      const status = document.getElementById('catalog-load-status');
      if (status) {
        status.hidden = false;
        status.innerHTML = `<p>${isAr ? 'تعذر تحديث المتجر. تحقق من اتصالك وحاول مجدداً.' : 'Could not update the store. Check your connection and try again.'}</p><button type="button" class="btn-action-secondary" onclick="loadStorefrontData()">${isAr ? 'إعادة المحاولة' : 'Retry'}</button>`;
      }
      if (!state().allProducts.length) {
        document.querySelectorAll('#catalogs-grid .skeleton-card-item').forEach(el => el.remove());
        const grid = document.getElementById('catalogs-grid');
        if (grid && !grid.children.length) {
          grid.innerHTML = `
            <div class="empty-state-card" style="grid-column: 1 / -1; text-align: center; padding: 36px 16px; color: var(--hint); border: 1px dashed var(--border); border-radius: 18px; margin-block-end: 20px;">
              <div style="font-size: 32px; margin-bottom: 8px;">📡</div>
              <div style="font-size: 15px; font-weight: 800; color: var(--text); margin-bottom: 4px;">${isAr ? 'تعذر تحميل المنتجات والتصنيفات' : 'Failed to load catalog'}</div>
              <div style="font-size: 13px; margin-bottom: 16px;">${isAr ? 'تأكد من الاتصال بالإنترنت ثم حاول مجدداً.' : 'Check your network connection and try again.'}</div>
              <button type="button" class="btn-action-primary" onclick="loadStorefrontData()" style="max-width: 180px; margin: 0 auto; min-height: 40px; font-size: 13px; font-weight: 700;">${isAr ? 'إعادة المحاولة ↻' : 'Retry ↻'}</button>
            </div>
          `;
        }
      }
    }
  }

  let activeActivityFilter = 'all';

  function filterActivityView(filterKey) {
    activeActivityFilter = filterKey;
    root.activeActivityFilter = filterKey;
    api().haptic?.('selection');
    ['all', 'attention', 'orders', 'recharges', 'transfers', 'vault'].forEach(k => {
      const chip = document.getElementById(`act-filter-${k}`);
      if (chip) chip.classList.toggle('active', k === filterKey);
    });
    const isAdmin = !!(state().userData?.is_admin || window.userData?.is_admin);
    if (isAdmin && root.renderAdminLiveRadar) {
      root.renderAdminLiveRadar();
    } else {
      renderUserActivity();
    }
  }

  function renderUserActivity() {
    const container = document.getElementById('orders-container-box') || document.getElementById('orders-history-list');
    if (!container) return;

    const isAr = (state().currentAppLanguage === 'ar');
    const orders = (state().userOrders || []).map(o => ({ ...o, type: 'order' }));
    const recharges = (state().userRecharges || []).map(r => ({ ...r, type: 'recharge' }));
    let list = [...orders, ...recharges];
    list.sort((a, b) => (b.timestamp || b.id || 0) - (a.timestamp || a.id || 0));

    if (activeActivityFilter === 'orders') {
      list = list.filter(i => i.type === 'order');
    } else if (activeActivityFilter === 'recharges') {
      list = list.filter(i => i.type === 'recharge');
    } else if (activeActivityFilter === 'vault') {
      list = list.filter(i => i.type === 'order' && i.status === 'completed' && ((i.goods && i.goods.length) || (i.delivery_goods && i.delivery_goods.length)));
    }

    if (list.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px 16px; color: var(--hint);">
          <div style="font-size: 38px; margin-bottom: 8px;">📦</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 4px;">
            ${isAr ? 'لا توجد عمليات أو طلبات سابقة' : 'No previous orders or activities'}
          </div>
          <p style="font-size: 13px; margin-bottom: 16px; color: var(--hint);">
            ${isAr ? 'تصفح باقات واشتراكات المتجر واشترِ الآن برصيد محفظتك.' : 'Browse store subscriptions and purchase now with your wallet.'}
          </p>
          <button class="btn-action-primary" onclick="switchTab('store')" style="width: auto; padding: 0 24px; margin: 0 auto; height: 42px; font-size: 13px;">
            ${isAr ? '🛍️ تصفح المتجر' : '🛍️ Browse Store'}
          </button>
        </div>
      `;
      return;
    }

    const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;

    container.innerHTML = list.map(it => {
      if (it.type === 'order') {
        const isCompleted = (it.status === 'completed');
        const isRefunded = (it.status === 'refunded');
        const statusClass = isCompleted ? 'status-completed' : (isRefunded ? 'status-refunded' : 'status-pending');
        const statusLabel = isCompleted ? (isAr ? 'مكتمل ✅' : 'Completed ✅') : (isRefunded ? (isAr ? 'مسترجع ↩️' : 'Refunded ↩️') : (isAr ? 'قيد التجهيز ⏳' : 'In Progress ⏳'));
        const goods = it.goods || it.delivery_goods || [];
        const prodName = it.products || it.product_name || (isAr ? 'منتج رقمي' : 'Digital Product');
        const totalNum = Number(it.total || it.total_sell || 0).toFixed(2);

        return `
          <div class="order-history-card" onclick="openOrderDetail(${it.id})" role="button" tabindex="0" style="background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 14px; margin-bottom: 10px; cursor: pointer;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 12px; font-weight: 800; color: var(--accent);">#${it.id}</span>
              <span class="activity-status-pill ${statusClass}" style="font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 8px;">${statusLabel}</span>
            </div>
            <div style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 4px;">
              🛍️ ${escapeAttr(prodName)}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--hint); margin-bottom: 6px;">
              <span>💰 $${totalNum} USD</span>
              <span>${it.created_at || ''}</span>
            </div>
            ${goods.length ? `
              <div class="order-delivery-credentials-wrap" style="margin-top: 10px;">
                ${renderFn ? renderFn(goods) : ''}
              </div>
            ` : ''}
            <div style="display: flex; justify-content: flex-end; margin-top: 6px;">
              <span style="font-size: 11px; font-weight: 700; color: var(--accent);">${isAr ? 'عرض التفاصيل والبيانات الكاملة ›' : 'View full details & keys ›'}</span>
            </div>
          </div>
        `;
      } else {
        const isPaid = (it.status === 'completed');
        const statusLabel = isPaid ? (isAr ? 'تم الشحن ✅' : 'Completed ✅') : (isAr ? 'قيد المراجعة ⏳' : 'Pending ⏳');
        const statusClass = isPaid ? 'status-completed' : 'status-pending';
        return `
          <div class="order-history-card" style="background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 14px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span style="font-size: 13px; font-weight: 800; color: var(--text);">💳 ${escapeAttr(it.method || 'شحن رصيد')}</span>
              <span class="activity-status-pill ${statusClass}" style="font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 8px;">${statusLabel}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--hint);">
              <span style="font-weight: 800; color: var(--success);">+$${Number(it.amount_usd || 0).toFixed(2)} USD</span>
              <span>${it.created_at || ''}</span>
            </div>
          </div>
        `;
      }
    }).join('');
  }

  // --- User Data, Profile, Referrals, & Admin Overview ---
  function renderUserProfile(d) {
    if (!d) return;
    const isAr = (state().currentAppLanguage === 'ar');
    const tgObj = root.Telegram?.WebApp;
    const tgUser = tgObj?.initDataUnsafe?.user;

    // Profile Picture & Initial
    const topAvatarBox = document.getElementById('top-avatar-box');
    const setAvatarBox = document.getElementById('settings-avatar-box');
    const firstLetter = (tgUser?.first_name || d.first_name || d.username || 'U')[0].toUpperCase();

    const photoUrl = tgUser?.photo_url || d.photo_url;
    const safePhoto = (photoUrl && root.StorefrontSecurity) ? root.StorefrontSecurity.safeUrl(photoUrl, true) : (photoUrl || '');

    if (safePhoto) {
      if (topAvatarBox) {
        topAvatarBox.innerHTML = `
          <img src="${safePhoto}" class="avatar-img" alt="Avatar" onload="this.style.display='block'; if (this.nextElementSibling) this.nextElementSibling.style.display='none';" onerror="this.style.display='none'; if (this.nextElementSibling) this.nextElementSibling.style.display='flex';">
          <div class="avatar-fallback" id="top-avatar-initial" style="display: none;">${firstLetter}</div>
        `;
      }
      if (setAvatarBox) {
        setAvatarBox.innerHTML = `
          <img src="${safePhoto}" class="avatar-img" style="width: 48px; height: 48px;" alt="Avatar" onload="this.style.display='block'; if (this.nextElementSibling) this.nextElementSibling.style.display='none';" onerror="this.style.display='none'; if (this.nextElementSibling) this.nextElementSibling.style.display='flex';">
          <div class="avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px; display: none;">${firstLetter}</div>
        `;
      }
    } else {
      if (topAvatarBox) {
        topAvatarBox.innerHTML = `<div class="avatar-fallback" id="top-avatar-initial">${firstLetter}</div>`;
      }
      if (setAvatarBox) {
        setAvatarBox.innerHTML = `<div class="avatar-fallback" id="settings-avatar-initial" style="width: 48px; height: 48px; font-size: 20px;">${firstLetter}</div>`;
      }
    }

    // Name & Handle
    const defaultRoleTitle = d.is_admin ? (isAr ? 'المسؤول' : 'Admin') : (isAr ? 'العميل' : 'Customer');
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
    if (idNumEl) idNumEl.innerText = 'ID: ' + (d.telegram_id || state().userId || '---');

    // VIP Pill in Profile Header
    const vipBox = document.getElementById('user-vip-pill-box');
    const hasVipDiscount = (Number(d.vip_discount) > 0) && d.vip_tier && d.vip_tier !== 'Standard';
    if (vipBox) {
      if (!d.is_admin && hasVipDiscount) {
        vipBox.innerHTML = `<span class="vip-tag">${d.vip_tier} (${isAr ? 'خصم' : 'Discount'} ${Number(d.vip_discount)}%)</span>`;
        vipBox.style.display = 'block';
      } else {
        vipBox.innerHTML = '';
        vipBox.style.display = 'none';
      }
    }
  }

  function renderUserReferrals(d) {
    if (!d) return;
    const isAr = (state().currentAppLanguage === 'ar');
    const refCard = document.getElementById('user-referral-system-card');
    if (refCard) refCard.style.display = d.is_admin ? 'none' : 'block';

    const botName = d.bot_username || 'gh_store1_bot';
    const refCode = d.referral_code || '';
    const refLink = refCode ? `https://t.me/${botName}?start=${refCode}` : `https://t.me/${botName}`;

    const refEl = document.getElementById('referral-link-display');
    if (refEl) refEl.innerText = refLink;

    const countEl = document.getElementById('referral-count-val');
    if (countEl) countEl.innerText = String(d.referrals_count || 0);

    const earnedEl = document.getElementById('referral-earned-val');
    if (earnedEl) earnedEl.innerText = `$${(d.referrals_total_earned || 0.0).toFixed(2)}`;

    const rateEl = document.getElementById('referral-rate-val');
    if (rateEl) rateEl.innerText = `${d.referral_commission_rate || d.admin_stats?.referral_commission_percent || 0.2}%`;

    const breakdownList = document.getElementById('referrals-breakdown-list');
    if (breakdownList) {
      const items = d.referrals_breakdown || [];
      if (!items.length) {
        breakdownList.innerHTML = `
          <div style="text-align: center; padding: 14px; background: var(--input-bg); border-radius: 10px; color: var(--hint); font-size: 12px;">
            ${isAr ? 'لم تقم بدعوة أصدقاء بعد. شارك رابطك واكسب عمولة فورية من كل عملية شراء!' : 'No referred friends yet. Share your link and earn instant commission on every order!'}
          </div>
        `;
      } else {
        breakdownList.innerHTML = items.map(r => `
          <div style="background: var(--input-bg); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div>
              <div style="font-size: 12px; font-weight: 700; color: var(--text);">${r.user_display || 'User'}</div>
              <div style="font-size: 10px; color: var(--hint); margin-top: 1px;">
                ${r.registered_at ? r.registered_at + ' · ' : ''}${r.orders_count || 0} ${isAr ? 'طلب' : 'orders'}
              </div>
            </div>
            <div style="text-align: end;">
              <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); color: var(--success); font-size: 11px; font-weight: 800; padding: 2px 6px; border-radius: 6px;">
                +$${Number(r.earned || 0).toFixed(2)}
              </span>
            </div>
          </div>
        `).join('');
      }
    }

    const supportUser = d.support_username || 'ahmedghx';
    const supportBtnEl = document.getElementById('label-support-chat-btn');
    if (supportBtnEl) {
      supportBtnEl.innerText = isAr
        ? `التواصل مع خدمة العملاء والدعم (@${supportUser})`
        : `Contact Customer Support (@${supportUser})`;
    }
  }

  function renderAdminControlCenter(d) {
    if (!d) return;
    const isAr = (state().currentAppLanguage === 'ar');
    const adminCenterCard = document.getElementById('admin-control-center-card');
    if (!adminCenterCard) return;

    if (!d.is_admin) {
      adminCenterCard.style.display = 'none';
      return;
    }

    adminCenterCard.style.display = 'block';
    const stats = d.admin_stats || {};

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    setVal('admin-stat-revenue', `$${(stats.total_revenue || 0).toFixed(2)}`);
    setVal('admin-stat-cost', `$${(stats.total_cost || 0).toFixed(2)}`);
    setVal('admin-stat-profit', `$${((stats.total_revenue || 0) - (stats.total_cost || 0)).toFixed(2)}`);
    setVal('admin-stat-balances', `$${(stats.total_user_balances || 0).toFixed(2)}`);

    if (stats.supplier_wallets) {
      const sw = stats.supplier_wallets;
      setVal('admin-bal-batstore', `$${(sw.batstore_usd || 0.0).toFixed(2)}`);
      setVal('admin-bal-prodseller', `$${(sw.prodseller_usd || 0.0).toFixed(2)}`);
      setVal('admin-bal-g2bulk', `$${(sw.g2bulk_usd || 0.0).toFixed(2)}`);
      setVal('admin-bal-sam-usd', `$${(sw.sam_usd || 0.0).toFixed(2)} USD`);
      setVal('admin-bal-sam-syp', `${Math.round(sw.sam_syp || 0.0).toLocaleString()} ${isAr ? 'ل.س' : 'SYP'}`);
      setVal('admin-bal-total-suppliers-pill', `${isAr ? 'إجمالي:' : 'Total:'} $${(sw.total_supplier_usd || 0.0).toFixed(2)}`);

      setVal('admin-wallet-headline-bal', `$${(sw.total_supplier_usd || 0.0).toFixed(2)}`);
      setVal('admin-wallet-batstore', `$${(sw.batstore_usd || 0.0).toFixed(2)}`);
      setVal('admin-wallet-prodseller', `$${(sw.prodseller_usd || 0.0).toFixed(2)}`);
      setVal('admin-wallet-g2bulk', `$${(sw.g2bulk_usd || 0.0).toFixed(2)}`);
      setVal('admin-wallet-sam-usd', `$${(sw.sam_usd || 0.0).toFixed(2)}`);
      setVal('admin-wallet-sam-syp', `${Math.round(sw.sam_syp || 0.0).toLocaleString()} ${isAr ? 'ل.س' : 'SYP'}`);
      setVal('admin-wallet-users-total', `$${(stats.total_user_balances || 0.0).toFixed(2)}`);
    }

    const sypInput = document.getElementById('admin-syp-rate-input');
    if (sypInput && !sypInput.value && stats.syp_usd_rate) sypInput.value = stats.syp_usd_rate;

    const refInput = document.getElementById('admin-ref-rate-input');
    if (refInput && !refInput.value && stats.referral_commission_percent) refInput.value = stats.referral_commission_percent;

    const logoInput = document.getElementById('admin-store-logo-input');
    if (logoInput && !logoInput.value && d.store_logo_url) logoInput.value = d.store_logo_url;
  }

  function renderStoreAnnouncement(d) {
    const heroBanner = document.getElementById('storefront-hero-banner');
    if (!heroBanner) return;
    const annText = (d?.store_announcement || d?.admin_stats?.store_announcement || '').trim();
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

  function applyStoreLogo(url) {
    const rawUrl = (url || state().currentStoreLogo || '').trim();
    state().currentStoreLogo = rawUrl;
    const img = document.getElementById('top-store-logo');
    const fallback = document.getElementById('top-store-fallback');
    const input = document.getElementById('admin-store-logo-input');
    if (input && rawUrl) input.value = rawUrl;

    if (!img) return;

    let cleanUrl = rawUrl;
    if (cleanUrl.endsWith('/gh-store-logo-mark.png') || cleanUrl === 'gh-store-logo-mark.png') {
      cleanUrl = '/static/img/gh-store-logo-mark.png';
    }

    if (cleanUrl) {
      img.onload = () => {
        img.style.display = 'block';
        if (fallback) fallback.style.display = 'none';
      };
      img.onerror = () => {
        img.style.display = 'none';
        if (fallback) fallback.style.display = 'flex';
      };
      img.src = cleanUrl;
    } else {
      img.style.display = 'none';
      if (fallback) fallback.style.display = 'flex';
    }
  }

  function copyUserId() {
    const uid = state().userId || state().userData?.telegram_id;
    if (uid && navigator.clipboard) {
      navigator.clipboard.writeText(String(uid));
      api().haptic?.('light');
      api().showToast?.(state().currentAppLanguage === 'ar' ? 'تم نسخ ID المستخدم!' : 'User ID copied!');
    }
  }

  function copyReferralLink() {
    const linkEl = document.getElementById('referral-link-display');
    const txt = linkEl?.innerText?.trim();
    if (txt && navigator.clipboard) {
      navigator.clipboard.writeText(txt);
      api().haptic?.('light');
      api().showToast?.(state().currentAppLanguage === 'ar' ? 'تم نسخ رابط الدعوة!' : 'Referral link copied!');
    }
  }

  function openCustomerSupportChat() {
    const user = state().userData?.support_username || 'ahmedghx';
    const tg = root.Telegram?.WebApp;
    if (tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/${user}`);
    else window.open(`https://t.me/${user}`, '_blank');
  }

  function openOfficialChannel() {
    const tg = root.Telegram?.WebApp;
    if (tg?.openTelegramLink) tg.openTelegramLink('https://t.me/ghstorex');
    else window.open('https://t.me/ghstorex', '_blank');
  }

  async function loadUserData() {
    try {
      if (api().ensureAuthSession) {
        await api().ensureAuthSession();
      }
      const tgId = state().userId;
      const url = tgId ? `/api/user/me?tg_id=${tgId}` : '/api/user/me';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.error) {
          console.warn('User data response error:', data.error);
          return;
        }
        state().userData = data;
        state().userId = data.telegram_id || data.tg_id || state().userId;
        if (data.orders) state().userOrders = data.orders;
        if (data.recharges) state().userRecharges = data.recharges;

        try { root.localStorage?.setItem('ghstore_user_cache_v3', JSON.stringify(data)); } catch (_) {}

        // 1. Balances across Top Bar, Wallet Tab, and Settings Tab
        wallet().renderWalletBalances(data);

        // 2. User Profile (Display Name, @username, TG ID, Avatar, VIP Discount Pill)
        renderUserProfile(data);

        // 3. Referral Program (Link, Count, Earned, Rate, Breakdown List)
        renderUserReferrals(data);

        // 4. Admin Control Center & Wallets (if user is admin)
        renderAdminControlCenter(data);

        // 5. Store Announcement & Logo
        renderStoreAnnouncement(data);
        if (data.store_logo_url) applyStoreLogo(data.store_logo_url);

        // 6. User Activity & Orders if activeTab === 'orders'
        if (state().activeTab === 'orders') renderUserActivity();

        // 7. Check continuous insufficient balance recovery
        checkPendingBuyResume();
      } else {
        console.warn('Failed to load user data: HTTP', res.status);
      }
    } catch (e) {
      console.warn('Failed to fetch user data:', e);
    }
  }

  async function loadUserOrders() {
    const container = document.getElementById('orders-container-box') || document.getElementById('orders-history-list');
    if (!container) return;
    if (!state().userOrders || !state().userOrders.length) {
      container.innerHTML = '<div class="loading-spinner">جاري تحميل العمليات...</div>';
    }

    try {
      const tgId = state().userId;
      const url = tgId ? `/api/orders?tg_id=${tgId}` : '/api/orders';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        state().userOrders = data.orders || [];
        renderUserActivity();
      } else if (state().userData && state().userData.orders) {
        state().userOrders = state().userData.orders;
        renderUserActivity();
      }
    } catch (_) {
      if (state().userData && state().userData.orders) {
        state().userOrders = state().userData.orders;
        renderUserActivity();
      }
    }
  }

  // --- Real-Time Server Sent Events (SSE) ---
  function initSSE() {
    try {
      const sse = new EventSource('/api/events');
      sse.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          const eventType = ev.event || ev.type;
          if (eventType === 'order_updated') loadUserOrders();
          else if (eventType === 'balance_updated') loadUserData();
          else if (['catalog_synced', 'stock_update'].includes(eventType)) loadStorefrontData();
          else if (eventType === 'rate_update') {
            state().sypRate = Number(ev.syp_rate) > 0 ? Number(ev.syp_rate) : null;
            loadUserData();
          }
        } catch (_) {}
      };
    } catch (_) {}
  }

  // --- Master App Startup Sequence ---
  async function bootApp() {
    // 1. Initialize Telegram platform & viewport
    api().initTelegramPlatform?.();
    api().updateSafeAreaInsets?.();

    // 2. Language & Layout direction setup (RTL vs LTR)
    const savedLang = root.localStorage?.getItem('ghstore_lang') || 'ar';
    api().applyLanguage?.(savedLang);

    // 2.1 Theme setup: synchronize visual toggle with stored or platform theme
    const savedTheme = root.localStorage?.getItem('ghstore_theme') || api().getTg?.()?.colorScheme || 'dark';
    if (root.setAppTheme) {
      root.setAppTheme(savedTheme);
    } else {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }

    // 3. Initialize Keyboard navigation behavior
    api().initKeyboardBehavior?.();

    // Public catalog loading does not depend on the private session handshake.
    loadStorefrontData();

    // 4. Authenticate private account requests.
    if (api().ensureAuthSession) {
      await api().ensureAuthSession();
    }

    // 5. Bind Search Input Keyboard Events (Enter key triggers search)
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          storefront().filterCatalog(searchInput.value);
          searchInput.blur();
        }
      });
      searchInput.addEventListener('input', () => {
        storefront().filterCatalog(searchInput.value);
      });
    }

    // 6. Bind Coupon Input Keyboard Events (Enter key triggers validation)
    const couponInput = document.getElementById('coupon-input');
    if (couponInput) {
      couponInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          checkout().applyCoupon(couponInput.value);
        }
      });
    }

    // 7. Initialize Cart & Flash Sale Timer
    checkout().initCart?.();
    storefront().initFlashSaleTimer?.();

    // 8. Load private data & connect SSE
    loadUserData();
    initSSE();

    // 9. Durable Checkout Recovery on Startup
    checkout().recoverPendingCheckout?.();

    // 10. Deep linking: handle startapp or start_param
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const tg = window.Telegram && window.Telegram.WebApp;
      const startParam = urlParams.get('startapp') || urlParams.get('tgWebAppStartParam') || tg?.initDataUnsafe?.start_param || '';
      if (startParam === 'orders' || startParam.startsWith('ord_')) {
        switchTab('orders');
      }
    } catch (_) {}
  }

  // --- Continuous Insufficient Balance Recovery ---
  function checkPendingBuyResume() {
    try {
      const raw = root.sessionStorage?.getItem('ghstore_pending_buy_resume');
      if (!raw) return;
      const pending = JSON.parse(raw);
      if (!pending || !pending.productId) return;

      // Intent expires after 2 hours
      if (Date.now() - (pending.createdAt || 0) > 2 * 3600 * 1000) {
        root.sessionStorage?.removeItem('ghstore_pending_buy_resume');
        return;
      }

      const userBal = Number(state().userData?.balance || 0);
      const all = state().allProducts || [];
      const prod = all.find(p => Number(p.id) === Number(pending.productId));
      if (!prod) return;

      const currentPrice = Number(prod.sell_price_usd ?? prod.price ?? 0) * (Number(pending.quantity) || 1);
      if (userBal >= currentPrice) {
        root.sessionStorage?.removeItem('ghstore_pending_buy_resume');
        const isAr = (state().currentAppLanguage === 'ar');
        api().showToast?.(isAr ? 'تم شحن الرصيد بنجاح! تفضل بمراجعة وتأكيد طلبك.' : 'Balance topped up! Review and confirm your order.');
        if (root.openProductDetail) {
          root.openProductDetail(prod.id);
          if (pending.quantity && pending.quantity > 1) {
            state().selectedQty = pending.quantity;
            const qEl = document.getElementById('prod-qty-val');
            if (qEl) qEl.innerText = String(pending.quantity);
            if (storefront().updateDetailPagePrice) storefront().updateDetailPagePrice();
          }
          if (pending.customFields && checkout().restoreEnteredCustomFields) {
            checkout().restoreEnteredCustomFields(pending.customFields);
          }
        }
      }
    } catch (_) {}
  }

  // --- Contextual Order Support & Order Details Management ---
  let currentOrderDetailId = null;
  root.currentOrderDetailId = null;

  function openOrderSupport(orderId) {
    const tg = api().getTg();
    const isAr = (state().currentAppLanguage === 'ar');
    const oid = orderId || currentOrderDetailId || '';
    const msg = encodeURIComponent(isAr ? `مرحباً، أود الاستفسار والمساعدة بخصوص طلبي #${oid}` : `Hello, I need assistance regarding my order #${oid}`);
    const supportUrl = `https://t.me/ahmedghx?text=${msg}`;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(supportUrl);
    } else {
      window.open(supportUrl, '_blank', 'noopener');
    }
  }

  function supportCurrentOrderDetail() {
    openOrderSupport(currentOrderDetailId);
  }

  function rateCurrentOrderDetail() {
    const isAr = (state().currentAppLanguage === 'ar');
    api().showToast?.(isAr ? 'شكراً لتقييمك! نسعد بخدمتكم دائماً ⭐' : 'Thank you for your rating! ⭐');
  }

  function showOrderReceiptModal(orderId) {
    const isAr = (state().currentAppLanguage === 'ar');
    const orders = state().userOrders || [];
    const order = orders.find(o => String(o.id) === String(orderId || currentOrderDetailId));
    if (!order) {
      api().showToast?.(isAr ? 'لم يتم العثور على بيانات الإيصال' : 'Receipt data not found');
      return;
    }
    const receiptText = `
══════════════════════════
       GH STORE RECEIPT   
══════════════════════════
Order ID: #${order.id}
Date: ${order.created_at || 'N/A'}
Service: ${order.products || order.product_name || 'Digital Goods'}
Status: ${order.status || 'completed'}
Total Paid: $${Number(order.total || order.total_sell || 0).toFixed(2)} USD
Payment Method: Wallet Balance (USD)
══════════════════════════
    `;
    api().copyTextToClipboard?.(receiptText.trim());
    api().showToast?.(isAr ? 'تم نسخ بيانات الإيصال بالكامل!' : 'Receipt copied to clipboard!');
  }

  function openOrderDetail(orderId) {
    api().haptic?.('light');
    currentOrderDetailId = orderId;
    root.currentOrderDetailId = orderId;

    const isAr = (state().currentAppLanguage === 'ar');
    const orders = state().userOrders || [];
    const order = orders.find(o => String(o.id) === String(orderId)) || { id: orderId };

    const detailView = document.getElementById('view-order-detail');
    if (!detailView) return;

    // Header & Summary
    const idTitle = document.getElementById('order-detail-id-title');
    if (idTitle) idTitle.innerText = `${isAr ? 'طلب' : 'Order'} #${order.id || orderId}`;

    const dateEl = document.getElementById('order-detail-date');
    if (dateEl) dateEl.innerText = order.created_at || new Date().toISOString().split('T')[0];

    const prodTitle = document.getElementById('order-detail-products-title');
    if (prodTitle) prodTitle.innerText = order.products || order.product_name || (isAr ? 'منتج رقمي' : 'Digital Service');

    const totalEl = document.getElementById('order-detail-total-amount');
    if (totalEl) totalEl.innerText = `$${Number(order.total || order.total_sell || 0).toFixed(2)} USD`;

    // Status & Stepper
    const status = order.status || (order.goods && order.goods.length ? 'completed' : 'pending');
    const isCompleted = (status === 'completed');
    const isRefunded = (status === 'refunded' || status === 'failed');
    const isReview = (status === 'requires_manual_review' || status === 'received');

    const badgeEl = document.getElementById('order-detail-status-badge');
    const fillEl = document.getElementById('order-detail-stepper-fill');
    const node1 = document.getElementById('order-step-node-1');
    const node2 = document.getElementById('order-step-node-2');
    const node3 = document.getElementById('order-step-node-3');

    if (isCompleted) {
      if (badgeEl) {
        badgeEl.className = 'pill-badge in-stock';
        badgeEl.innerText = isAr ? 'مكتمل ✅' : 'Completed ✅';
      }
      if (fillEl) fillEl.style.width = '100%';
      if (node1) node1.className = 'order-step-node completed';
      if (node2) node2.className = 'order-step-node completed';
      if (node3) node3.className = 'order-step-node completed';
    } else if (isRefunded) {
      if (badgeEl) {
        badgeEl.className = 'pill-badge stock-out';
        badgeEl.innerText = isAr ? 'ملغى ومسترد ↩️' : 'Refunded ↩️';
      }
      if (fillEl) fillEl.style.width = '33%';
      if (node1) node1.className = 'order-step-node completed';
      if (node2) node2.className = 'order-step-node';
      if (node3) node3.className = 'order-step-node';
    } else if (isReview) {
      if (badgeEl) {
        badgeEl.className = 'pill-badge spec-pill';
        badgeEl.innerText = isAr ? 'بانتظار المراجعة ⏳' : 'Manual Review ⏳';
      }
      if (fillEl) fillEl.style.width = '50%';
      if (node1) node1.className = 'order-step-node completed';
      if (node2) node2.className = 'order-step-node active';
      if (node3) node3.className = 'order-step-node';
    } else {
      // Processing
      if (badgeEl) {
        badgeEl.className = 'pill-badge spec-pill';
        badgeEl.innerText = isAr ? 'قيد التجهيز والتفعيل ⏳' : 'Processing ⏳';
      }
      if (fillEl) fillEl.style.width = '66%';
      if (node1) node1.className = 'order-step-node completed';
      if (node2) node2.className = 'order-step-node completed';
      if (node3) node3.className = 'order-step-node active';
    }

    // Credentials Box
    const goods = order.goods || order.delivery_goods || [];
    const credBox = document.getElementById('order-detail-credentials-box');
    const renderFn = root.renderStructuredCredentials || api().renderStructuredCredentials;
    if (credBox) {
      if (goods && goods.length > 0) {
        credBox.innerHTML = renderFn ? renderFn(goods) : '';
      } else if (isRefunded) {
        credBox.innerHTML = `
          <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-weight: 800; font-size: 13px; color: #ef4444; margin-bottom: 4px;">
              ${isAr ? 'تم استرداد المبلغ بالكامل إلى محفظتك' : 'Order amount was fully refunded to your wallet'}
            </div>
            <div style="font-size: 12px; color: var(--hint); margin-bottom: 12px;">
              ${isAr ? 'إذا كنت بحاجة للمساعدة، يرجى التواصل مع فريق الدعم.' : 'If you need further help, please reach out to support.'}
            </div>
            <button type="button" class="btn-action-secondary" onclick="openOrderSupport('${order.id || orderId}')" style="height: 38px; font-size: 12px; font-weight: 700; width: auto; padding: 0 16px; margin: 0 auto;">
              💬 ${isAr ? 'محادثة الدعم' : 'Contact Support'}
            </button>
          </div>
        `;
      } else {
        credBox.innerHTML = `
          <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 28px; margin-bottom: 6px;">⏳</div>
            <div style="font-weight: 800; font-size: 13px; color: var(--accent); margin-bottom: 4px;">
              ${isAr ? 'جاري تجهيز وتفعيل طلبك الآن' : 'Your order is currently being fulfilled'}
            </div>
            <div style="font-size: 12px; color: var(--hint); line-height: 1.5; margin-bottom: 12px;">
              ${isAr ? 'تم استلام الدفعة وتأكيد الطلب. سيتم إرسال بيانات الاشتراك فور اكتمال التجهيز والتفعيل.' : 'Payment confirmed. Credentials and account details will appear here shortly.'}
            </div>
            <button type="button" class="btn-action-secondary" onclick="openOrderSupport('${order.id || orderId}')" style="height: 38px; font-size: 12px; font-weight: 700; width: auto; padding: 0 16px; margin: 0 auto;">
              💬 ${isAr ? 'استفسار من الدعم' : 'Contact Support'}
            </button>
          </div>
        `;
      }
    }

    // Hide all views, show order-detail
    document.querySelectorAll('.tab-view').forEach(el => {
      el.classList.remove('active');
      el.style.display = 'none';
    });
    detailView.classList.add('active');
    detailView.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'instant' });

    api().pushNav?.('order_detail', closeOrderDetailView);
  }

  let _closingOrderDetail = false;
  function closeOrderDetailView() {
    if (_closingOrderDetail) return;
    _closingOrderDetail = true;
    try {
      api().haptic?.('light');
      currentOrderDetailId = null;
      root.currentOrderDetailId = null;

      document.querySelectorAll('.tab-view').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
      });

      const detailView = document.getElementById('view-order-detail');
      if (detailView) {
        detailView.classList.remove('active');
        detailView.style.display = 'none';
      }

      const ordersView = document.getElementById('view-orders');
      if (ordersView) {
        ordersView.classList.add('active');
        ordersView.style.display = 'block';
      }

      window.scrollTo({ top: 0, behavior: 'instant' });

      if (api().navStack?.length > 0 && api().navStack[api().navStack.length - 1].name === 'order_detail') {
        api().popNav?.();
      }
    } finally {
      _closingOrderDetail = false;
    }
  }

  root.openOrderDetail = openOrderDetail;
  root.closeOrderDetailView = closeOrderDetailView;
  root.openOrderSupport = openOrderSupport;
  root.supportCurrentOrderDetail = supportCurrentOrderDetail;
  root.rateCurrentOrderDetail = rateCurrentOrderDetail;
  root.showOrderReceiptModal = showOrderReceiptModal;
  root.checkPendingBuyResume = checkPendingBuyResume;

  // Attach all functions to window for backward compatibility with inline HTML attributes
  root.formatRichDescription = formatRichDescription;
  root.escapeAttr = escapeAttr;
  root.escAttr = escAttr;
  root.instructionStepsHTML = instructionStepsHTML;
  root.normalizeCredentialItem = normalizeCredentialItem;
  root.renderStructuredCredentials = renderStructuredCredentials;
  root.assetUrl = assetUrl;
  root.thumbImg = thumbImg;

  root.switchTab = switchTab;
  root.applyLanguage = (lang) => api().applyLanguage?.(lang);
  root.openExternalPaymentUrl = openExternalPaymentUrl;
  root.copyCredFromBtn = copyCredFromBtn;
  root.copyFromBtn = copyFromBtn;
  root.copyCredText = copyCredText;
  root.copyCredVal = (val) => copyCredText(val);
  root.loadStorefrontData = loadStorefrontData;
  root.loadUserData = loadUserData;
  root.loadUserOrders = loadUserOrders;
  root.filterActivityView = filterActivityView;
  root.renderUserActivity = renderUserActivity;

  // Storefront Proxies
  root.renderCatalogsGrid = (c) => storefront().renderCatalogsGrid?.(c);
  root.renderCategories = (c) => storefront().renderCatalogsGrid?.(c);
  root.switchCategoryViewMode = (m) => storefront().switchCategoryViewMode?.(m);
  root.setCatalogViewMode = (m) => storefront().setCatalogViewMode?.(m);
  root.selectCategory = (c) => storefront().selectCategory?.(c);
  root.openCollection = (c) => storefront().openCollection?.(c);
  root.returnToCollections = () => storefront().returnToCollections?.();
  root.applyCatalogFilter = (f) => storefront().applyCatalogFilter?.(f);
  root.openServiceVariantsByIndex = (i) => storefront().openServiceVariantsByIndex?.(i);
  root.returnFromVariantsToPrevious = () => storefront().returnFromVariantsToPrevious?.();
  root.openProductDetail = (id) => storefront().openProductDetail?.(id);
  root.openProductDetailPage = (id) => storefront().openProductDetailPage?.(id);
  root.closeProductDetail = () => storefront().closeProductDetail?.();
  root.closeProductDetailPage = () => storefront().closeProductDetailPage?.();
  root.adjustQty = (d) => storefront().adjustQty?.(d);
  root.applyCheckoutCoupon = () => storefront().applyCheckoutCoupon?.();
  root.executeProductBuy = () => storefront().executeProductBuy?.();
  root.openSearchPage = () => storefront().openSearchPage?.();
  root.closeSearchPage = () => storefront().closeSearchPage?.();
  root.handleSearchPageInput = () => storefront().handleSearchPageInput?.();
  root.clearSearchPageInput = () => storefront().clearSearchPageInput?.();
  root.openProductModal = (p) => storefront().openProductDetail?.(p?.id || p);
  root.openProductModalById = (id) => storefront().openProductDetail?.(id);
  root.closeProductModal = () => storefront().closeProductDetail?.();
  root.filterCatalog = (q) => storefront().filterCatalog?.(q);
  root.openReviewsModal = () => storefront().openReviewsModal?.();
  root.closeReviewsModal = () => storefront().closeReviewsModal?.();
  root.openSupportModal = () => storefront().openSupportModal?.();
  root.closeSupportModal = () => storefront().closeSupportModal?.();

  // Wallet Proxies
  root.setCurrencyPreference = (c) => wallet().setCurrencyPreference?.(c);
  root.selectRechargeMethod = (m) => wallet().selectRechargeMethod?.(m);
  root.setShamCurrency = (c) => wallet().setShamCurrency?.(c);
  root.setRechargeAmount = (a) => wallet().setRechargeAmount?.(a);
  root.selectTopupAmount = (a) => wallet().selectTopupAmount?.(a);
  root.onCustomAmountInput = () => wallet().onCustomAmountInput?.();
  root.executeSelectedRecharge = () => wallet().executeSelectedRecharge?.();
  root.submitRechargeRequest = () => wallet().submitRechargeRequest?.();
  root.openInvoicePage = (d) => wallet().openInvoicePage?.(d);
  root.closeInvoicePage = () => wallet().closeInvoicePage?.();
  root.openActiveInvoiceGateway = () => wallet().openActiveInvoiceGateway?.();
  root.checkActiveInvoiceStatus = () => wallet().checkActiveInvoiceStatus?.();
  root.copyActiveInvoiceLink = () => wallet().copyActiveInvoiceLink?.();
  root.copyCryptoAddress = () => wallet().copyCryptoAddress?.();
  root.submitRedeemVoucher = () => wallet().submitRedeemVoucher?.();
  root.submitVoucherRedeem = () => wallet().submitVoucherRedeem?.();
  root.scanVoucherQr = () => wallet().scanVoucherQr?.();
  root.selectDisplayCurrency = (c) => wallet().selectDisplayCurrency?.(c);
  root.setAppTheme = (t) => wallet().setAppTheme?.(t);
  root.setCatalogViewMode = (m) => storefront().switchCategoryViewMode?.(m);
  root.openReceiptModal = (id) => wallet().openReceiptModal?.(id);
  root.closeReceiptPreviewModal = () => wallet().closeReceiptPreviewModal?.();
  root.openVipBenefitsModal = () => wallet().openVipBenefitsModal?.();
  root.closeVipBenefitsModal = () => wallet().closeVipBenefitsModal?.();

  // Checkout Proxies
  root.openCartDrawer = () => checkout().openCartDrawer?.();
  root.closeCartDrawer = () => checkout().closeCartDrawer?.();
  root.addToCartCurrentProduct = () => {
    if (state().selectedProduct) checkout().addToCart?.(state().selectedProduct, state().selectedQty || 1);
  };
  root.changeCartQty = (pid, d) => checkout().changeCartQty?.(pid, d);
  root.removeFromCart = (pid) => checkout().removeFromCart?.(pid);
  root.clearEntireCart = () => checkout().clearEntireCart?.();
  root.executeCartCheckout = () => checkout().executeCartCheckout?.();
  root.buyNow = (p, q, f) => checkout().buyNow?.(p, q, f);
  root.applyCoupon = (c) => checkout().applyCoupon?.(c);

  root.copyUserId = copyUserId;
  root.copyReferralLink = copyReferralLink;
  root.openCustomerSupportChat = openCustomerSupportChat;
  root.openOfficialChannel = openOfficialChannel;
  root.renderUserProfile = renderUserProfile;
  root.renderUserReferrals = renderUserReferrals;
  root.renderAdminControlCenter = renderAdminControlCenter;
  root.renderStoreAnnouncement = renderStoreAnnouncement;
  root.applyStoreLogo = applyStoreLogo;

  // Admin Proxies
  root.openAdminProductModal = (id) => admin().openAdminProductModal?.(id);
  root.closeAdminProductModal = () => admin().closeAdminProductModal?.();
  root.submitAdminProductUpdate = () => admin().submitAdminProductUpdate?.();
  root.onAdminProdCatSelectChange = () => admin().onAdminProdCatSelectChange?.();
  root.onAdminProdFolderSelectChange = () => admin().onAdminProdFolderSelectChange?.();
  root.openAdminCategoryModal = (id) => admin().openAdminCategoryModal?.(id);
  root.closeAdminCategoryModal = () => admin().closeAdminCategoryModal?.();
  root.openAdminCurrentCategoryEditor = () => admin().openAdminCurrentCategoryEditor?.();
  root.submitAdminCategoryUpdate = () => admin().submitAdminCategoryUpdate?.();
  root.openAdminFolderModal = (k, d) => admin().openAdminFolderModal?.(k, d);
  root.closeAdminFolderModal = () => admin().closeAdminFolderModal?.();
  root.openAdminCurrentFolderEditor = () => admin().openAdminCurrentFolderEditor?.();
  root.openAdminCreateFolderModal = () => admin().openAdminCreateFolderModal?.();
  root.submitAdminFolderUpdate = () => admin().submitAdminFolderUpdate?.();
  root.setAdminBalanceAction = (a) => admin().setAdminBalanceAction?.(a);
  root.setAdminBalAmount = (a) => admin().setAdminBalAmount?.(a);
  root.submitAdminAdjustBalance = () => admin().submitAdminAdjustBalance?.();
  root.submitAdminRevokeSessions = (id) => admin().submitAdminRevokeSessions?.(id);
  root.submitAdminUnrevokeSessions = (id) => admin().submitAdminUnrevokeSessions?.(id);
  root.submitAdminUpdateSypRate = () => admin().submitAdminUpdateSypRate?.();
  root.submitAdminUpdateStoreLogo = () => admin().submitAdminUpdateStoreLogo?.();
  root.openAdminStoreSettingsPage = () => admin().openAdminStoreSettingsPage?.();
  root.closeAdminStoreSettingsPage = () => admin().closeAdminStoreSettingsPage?.();
  root.openAdminSuppliersPage = () => admin().openAdminSuppliersPage?.();
  root.closeAdminSuppliersPage = () => admin().closeAdminSuppliersPage?.();
  root.openAdminUsersPage = () => admin().openAdminUsersPage?.();
  root.closeAdminUsersPage = () => admin().closeAdminUsersPage?.();
  root.openAdminStuckOrdersPage = () => admin().openAdminStuckOrdersPage?.();
  root.closeAdminStuckOrdersPage = () => admin().closeAdminStuckOrdersPage?.();
  root.openAdminResellerPricingPage = () => admin().openAdminResellerPricingPage?.();
  root.closeAdminResellerPricingPage = () => admin().closeAdminResellerPricingPage?.();
  root.openAdminConfigPage = () => admin().openAdminConfigPage?.();
  root.closeAdminConfigPage = () => admin().closeAdminConfigPage?.();
  root.openAdminBannerModal = () => admin().openAdminBannerModal?.();
  root.closeAdminBannerModal = () => admin().closeAdminBannerModal?.();
  root.openAdminBalanceModal = (id) => admin().openAdminBalanceModal?.(id);
  root.closeAdminBalanceModal = () => admin().closeAdminBalanceModal?.();
  root.openAdminDiscountModal = (id) => admin().openAdminDiscountModal?.(id);
  root.closeAdminDiscountModal = () => admin().closeAdminDiscountModal?.();
  root.openAdminGiftModal = () => admin().openAdminGiftModal?.();
  root.closeAdminGiftModal = () => admin().closeAdminGiftModal?.();
  root.openAdminMessageModal = (id) => admin().openAdminMessageModal?.(id);
  root.closeAdminMessageModal = () => admin().closeAdminMessageModal?.();
  root.openAdminOrdersModal = () => admin().openAdminOrdersModal?.();
  root.closeAdminOrdersModal = () => admin().closeAdminOrdersModal?.();
  root.openAdminCouponsModal = () => admin().openAdminCouponsModal?.();
  root.closeAdminCouponsModal = () => admin().closeAdminCouponsModal?.();
  root.openFullSqlAdmin = () => admin().openFullSqlAdmin?.();
  root.openAdminPanel = () => admin().openFullSqlAdmin?.();
  root.refreshSupplierBalances = () => { if (root.loadUserData) root.loadUserData(); };

  // SMS Activation Proxies
  root.openSmsModal = () => sms().openSmsModal?.();
  root.closeSmsModal = () => sms().closeSmsModal?.();
  root.onSmsSelectionChange = () => sms().onSmsSelectionChange?.();
  root.executeBuySms = () => sms().executeBuySms?.();
  root.copyAllocatedPhone = () => sms().copyAllocatedPhone?.();
  root.copyReceivedCode = () => sms().copyReceivedCode?.();
  root.executeCancelSms = () => sms().executeCancelSms?.();
  root.executeBanSms = () => sms().executeBanSms?.();
  root.openAdminSmsModal = () => sms().openAdminSmsModal?.();
  root.closeAdminSmsModal = () => sms().closeAdminSmsModal?.();
  root.loadAdminSmsSettings = () => sms().loadAdminSmsSettings?.();
  root.toggleAdminSmsService = (c, e) => sms().toggleAdminSmsService?.(c, e);
  root.toggleAdminSmsCountry = (c, e) => sms().toggleAdminSmsCountry?.(c, e);

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bootApp);
    } else {
      bootApp();
    }
  }

})(typeof window !== 'undefined' ? window : globalThis);
