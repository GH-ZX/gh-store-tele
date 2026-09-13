/* Shared, dependency-free boundaries for untrusted catalog content and checkout retries. */
(function (root) {
  'use strict';
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  function safeUrl(value, allowRelative = false) {
    const raw = String(value ?? '').trim();
    if (!raw || /[\u0000-\u001f\u007f]/.test(raw)) return '';
    if (!allowRelative && !/^https?:\/\//i.test(raw)) return '';
    try {
      const url = new URL(raw, root.location?.href || 'https://invalid.local/');
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
      return url.href;
    } catch (_) { return ''; }
  }

  // Rebuild safe elements instead of removing known-bad attributes. No supplier
  // styles, IDs, forms, images, SVG/MathML or event handlers reach the live DOM.
  function sanitizeRichHtml(value) {
    const source = document.createElement('template');
    source.innerHTML = String(value ?? '');
    const output = document.createElement('div');
    const allowed = new Set(['B', 'STRONG', 'I', 'EM', 'U', 'S', 'BR', 'P', 'DIV', 'SPAN', 'UL', 'OL', 'LI', 'CODE', 'PRE', 'BLOCKQUOTE', 'A']);
    const discard = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'TEMPLATE', 'NOSCRIPT', 'SVG', 'MATH', 'FORM', 'INPUT', 'BUTTON', 'TEXTAREA', 'SELECT', 'LINK', 'META', 'BASE']);
    const classes = new Set(['desc-heading', 'desc-bullet', 'desc-inline-code', 'desc-link']);
    function append(node, parent) {
      if (node.nodeType === 3) { parent.appendChild(document.createTextNode(node.data)); return; }
      if (node.nodeType !== 1 || discard.has(node.tagName) || node.namespaceURI !== 'http://www.w3.org/1999/xhtml') return;
      let target = parent;
      if (allowed.has(node.tagName)) {
        target = document.createElement(node.tagName.toLowerCase());
        if (classes.has(node.getAttribute('class'))) target.className = node.getAttribute('class');
        if (node.tagName === 'A') {
          const href = safeUrl(node.getAttribute('href'));
          if (href) {
            target.setAttribute('href', href);
            target.setAttribute('target', '_blank');
            target.setAttribute('rel', 'noopener noreferrer');
          }
        }
        parent.appendChild(target);
      }
      for (const child of node.childNodes) append(child, target);
    }
    for (const child of source.content.childNodes) append(child, output);
    return output.innerHTML;
  }

  function canonical(value) {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
    return JSON.stringify(value);
  }

  const attempts = new Map();
  function checkoutKey(scope, payload) {
    const storageKey = 'ghstore_checkout_v1:' + scope + ':' + payload.tg_id;
    const fingerprint = canonical(payload);
    let attempt = attempts.get(storageKey);
    try { attempt = JSON.parse(root.sessionStorage.getItem(storageKey)) || attempt; } catch (_) {}
    if (!attempt || attempt.fingerprint !== fingerprint) {
      const bytes = new Uint8Array(16);
      root.crypto.getRandomValues(bytes);
      attempt = { fingerprint, key: Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('') };
    }
    attempts.set(storageKey, attempt);
    try { root.sessionStorage.setItem(storageKey, JSON.stringify(attempt)); } catch (_) {}
    return attempt.key;
  }

  function finishCheckout(scope, payload, key) {
    const storageKey = 'ghstore_checkout_v1:' + scope + ':' + payload.tg_id;
    // A late response must never clear a newer attempt for a changed payload.
    let attempt = attempts.get(storageKey);
    try { attempt = JSON.parse(root.sessionStorage.getItem(storageKey)) || attempt; } catch (_) {}
    if (attempt?.key !== key) return;
    attempts.delete(storageKey);
    try { root.sessionStorage.removeItem(storageKey); } catch (_) {}
  }

  root.StorefrontSecurity = { escapeHtml, safeUrl, sanitizeRichHtml, checkoutKey, finishCheckout };
})(typeof window !== 'undefined' ? window : globalThis);
