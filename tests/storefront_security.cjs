// Run with: node tests/storefront_security.cjs (requires Chrome/Chromium).
// Exercises the real browser parser and actual storefront rendering functions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const app = fs.readFileSync(path.join(root, 'static/storefront/app.js'), 'utf8');
const security = fs.readFileSync(path.join(root, 'static/storefront/security.js'), 'utf8');
const names = ['formatRichDescription', 'escapeAttr', 'escAttr', 'instructionStepsHTML', 'normalizeCredentialItem', 'renderStructuredCredentials', 'assetUrl', 'thumbImg'];
const functions = names.map(name => {
  const start = app.indexOf('    function ' + name + '(');
  assert.ok(start >= 0, name);
  const end = app.indexOf('\n    }', start) + '\n    }'.length;
  return app.slice(start, end);
}).join('\n');

function browserTests() {
  const { safeUrl, sanitizeRichHtml, escapeHtml, checkoutKey, finishCheckout } = StorefrontSecurity;
  let count = 0;
  function check(condition, message) { if (!condition) throw new Error(message); count++; }
  const attack = `<img src=x onerror="window.pwned=1"><svg onload="window.pwned=1"></svg>`;
  const payloads = [
    attack,
    `<script>window.pwned=1</script><b onclick="window.pwned=1">Bold</b>`,
    `<a href="javascript:window.pwned=1">click</a>`,
    `<a href="java&#x09;script:window.pwned=1">click</a>`,
    `<a href="data:text/html,attack">click</a>`,
    `<math><mtext><table><mglyph><style><!--</style><img title="--><img src=x onerror='window.pwned=1'>">`,
    `<form id=location><input name=href><button formaction="javascript:alert(1)">click</button></form>`,
    `<a href="https://example.com/' onclick='window.pwned=1">quoted link</a>`,
    `[click](https://example.com/"onclick="window.pwned=1)`,
    `&lt;img src=x onerror=window.pwned=1&gt;`,
    `<div style="position:fixed;inset:0" id="btn-buy" data-copy="secret">content</div>`,
    `<iframe srcdoc="<script>window.pwned=1</script>"></iframe>`,
  ];
  for (const payload of payloads) {
    for (const render of [sanitizeRichHtml, formatRichDescription, x => instructionStepsHTML([x])]) {
      const box = document.createElement('div');
      box.innerHTML = render(payload);
      document.body.appendChild(box);
      check(!box.querySelector('script,style,img,svg,math,iframe,form,input,button,object,embed'), 'active content leaked: ' + payload);
      for (const node of box.querySelectorAll('*')) {
        check(!Array.from(node.attributes).some(a => /^on/i.test(a.name)), 'event attribute leaked');
        if (node.hasAttribute('href')) check(/^https?:/.test(node.href), 'unsafe navigation');
      }
      box.remove();
    }
  }
  const rich = document.createElement('div');
  rich.innerHTML = formatRichDescription('### عنوان\n**Bold**\n- Item\n[Help](https://example.com/help)');
  check(rich.querySelector('b')?.textContent === 'Bold', 'bold formatting preserved');
  check(rich.querySelector('.desc-heading')?.textContent === 'عنوان', 'Arabic heading preserved');
  check(rich.querySelector('a')?.getAttribute('rel') === 'noopener noreferrer', 'safe link rel');
  check(rich.querySelector('a')?.href === 'https://example.com/help', 'markdown URL preserved');
  check(safeUrl('javascript:alert(1)') === '', 'reject script URLs');
  check(safeUrl('https://user:pass@example.com') === '', 'reject credential URLs');
  check(safeUrl('java\nscript:alert(1)', true) === '', 'reject embedded control characters');
  check(safeUrl('/static/img/cat.svg', true).endsWith('/static/img/cat.svg'), 'local image allowed');
  check(escapeHtml(`'"<&>`) === '&#39;&quot;&lt;&amp;&gt;', 'complete attribute escaping');

  const thumb = document.createElement('div');
  thumb.innerHTML = thumbImg(`https://example.com/x'\");background:red;/*`, attack);
  check(thumb.querySelectorAll('img').length === 1, 'thumbnail markup cannot inject elements');
  check(thumb.firstChild.alt === attack, 'thumbnail alt is literal text');
  check(!/["'<>\\()]/.test(assetUrl(`https://example.com/x'\");color:red`)), 'CSS URL quotes encoded');
  const creds = document.createElement('div');
  creds.innerHTML = renderStructuredCredentials([`https://example.com/activate?token=';window.pwned=1;//`]);
  check(!creds.innerHTML.includes("openExternalPaymentUrl('"), 'delivery links never interpolate into JS');
  check(!window.pwned, 'payload did not execute');

  sessionStorage.clear();
  const p = { tg_id: 42, product_id: 9, quantity: 1 };
  const key = checkoutKey('buy', p);
  check(/^[a-f0-9]{32}$/.test(key), 'cryptographic idempotency key');
  check(key === checkoutKey('buy', { quantity: 1, product_id: 9, tg_id: 42 }), 'equivalent payload reuses key');
  check(key === checkoutKey('buy', p), 'network/409 retry reuses key');
  check(key !== checkoutKey('cart', p), 'cart and instant scopes differ');
  check(key !== checkoutKey('buy', { ...p, tg_id: 43 }), 'users isolated');
  const changed = { ...p, quantity: 2 };
  const changedKey = checkoutKey('buy', changed);
  check(key !== changedKey, 'payload change creates new attempt');
  finishCheckout('buy', p, key);
  check(changedKey === checkoutKey('buy', changed), 'late response preserves newer attempt');
  // Reload helper to discard in-memory state while retaining browser storage.
  const script = document.createElement('script');
  script.textContent = window.helperSource;
  document.head.appendChild(script);
  check(changedKey === StorefrontSecurity.checkoutKey('buy', changed), 'reload preserves uncertain request');
  StorefrontSecurity.finishCheckout('buy', changed, changedKey);
  check(changedKey !== StorefrontSecurity.checkoutKey('buy', changed), 'confirmed result permits new purchase');
  document.body.textContent = `PASS: ${count} storefront security checks`;
}

async function main() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ghstore-security-browser-'));
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    const script = `${security}\nconst currentAppLanguage='ar';\n${functions}\nwindow.helperSource=${JSON.stringify(security)};\ntry { (${browserTests.toString()})(); } catch(e) { document.body.textContent='FAIL: '+e.stack; }`;
    res.end('<!doctype html><html><head></head><body><script>' + script.replace(/<\/script/gi, '<\\/script') + '</script></body></html>');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const executable = process.env.CHROME_BIN || '/usr/bin/google-chrome';
  const child = spawn(executable, ['--headless', '--no-sandbox', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--user-data-dir=' + profile, '--dump-dom', `http://127.0.0.1:${server.address().port}`]);
  let stdout = '', stderr = '';
  child.stdout.on('data', data => { stdout += data; });
  child.stderr.on('data', data => { stderr += data; });
  const timeout = setTimeout(() => child.kill('SIGKILL'), 25000);
  try {
    const code = await new Promise((resolve, reject) => { child.on('exit', resolve); child.on('error', reject); });
    assert.equal(code, 0, stderr);
    assert.match(stdout, /<body>PASS: \d+ storefront security checks<\/body>/, stdout);
    console.log(stdout.match(/PASS: \d+ storefront security checks/)[0]);
  } finally {
    clearTimeout(timeout);
    server.close();
    fs.rmSync(profile, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
