---
name: telegram-mini-apps
description: Authoritative engineering guide, best practices, and API reference for building high-performance Telegram Mini Apps (TMA) across Bot API 6.0 through 8.0+. Covers WebApp SDK lifecycle, native UI (MainButton, SecondaryButton, BackButton, SettingsButton), fullscreen and orientation locks, safe area insets, theme synchronization, cryptographic HMAC-SHA256 initData backend validation, haptic feedback, biometric manager, cloud storage, payment invoices (Stars & fiat), and common mobile WebView gotchas.
---

# Telegram Mini Apps (TMA) - Engineering Guide & Reference

This skill provides comprehensive architectural patterns, code recipes, and best practices for building production-grade Telegram Mini Apps (TMAs) running inside Telegram on iOS, Android, macOS, Windows, and Web.

---

## 1. SDK Integration & Lifecycle

### 1.1 Script Loading
Place the official Telegram WebApp script in the `<head>` of your HTML before all other scripts:
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```
Once loaded, the singleton `window.Telegram.WebApp` (often aliased to `window.Telegram?.WebApp` or `tg`) becomes globally available.

### 1.2 Essential Initialization Sequence
Always call `ready()` as soon as initial DOM rendering completes, followed by `expand()` to maximize vertical screen real estate:

```javascript
const tg = window.Telegram?.WebApp;

document.addEventListener('DOMContentLoaded', () => {
  if (tg) {
    // 1. Inform Telegram the app has rendered to dismiss the splash/loading screen
    tg.ready();

    // 2. Expand to maximum available height
    tg.expand();

    // 3. Optional Bot API 7.7+: prevent accidental pull-down gestures from closing the app
    if (tg.isVersionAtLeast && tg.isVersionAtLeast('7.7')) {
      tg.disableVerticalSwipes();
    }

    // 4. Sync header and background colors with app theme
    syncThemeColors();
  }
});
```

### 1.3 Platform Detection & Capability Gating
```javascript
const platform = tg?.platform || 'unknown'; 
// Values: 'ios', 'android', 'tdesktop', 'macos', 'weba', 'webk', 'unknown'

const isMobile = ['ios', 'android'].includes(platform);

// Always check Bot API feature version before calling newer methods:
if (tg?.isVersionAtLeast && tg.isVersionAtLeast('8.0')) {
  // Safe to call Bot API 8.0 methods
  tg.requestFullscreen?.();
}
```

---

## 2. Safe Area Insets, Fullscreen & Viewport (Bot API 8.0+)

### 2.1 Safe Area Insets (Notches, Dynamic Island & Nav Bars)
Telegram provides both system-level safe areas and content-level safe areas:
- `tg.safeAreaInset`: `{ top, bottom, left, right }`
- `tg.contentSafeAreaInset`: `{ top, bottom, left, right }`

These are automatically mapped to native CSS variables:
```css
:root {
  /* Use Telegram CSS variables with fallback to browser env() */
  --safe-top: var(--tg-content-safe-area-inset-top, var(--tg-safe-area-inset-top, env(safe-area-inset-top, 0px)));
  --safe-bottom: var(--tg-content-safe-area-inset-bottom, var(--tg-safe-area-inset-bottom, env(safe-area-inset-bottom, 0px)));
}

body {
  padding-top: var(--safe-top);
  padding-bottom: calc(var(--safe-bottom) + 12px);
  min-height: var(--tg-viewport-stable-height, 100vh);
  overscroll-behavior-y: none; /* Crucial: stops pull-to-refresh bounce */
}
```

Listen for dynamic changes (e.g. device rotation or keyboard popup):
```javascript
tg.onEvent('safeAreaChanged', () => {
  console.log('New safe area:', tg.safeAreaInset);
});
tg.onEvent('contentSafeAreaChanged', () => {
  console.log('New content safe area:', tg.contentSafeAreaInset);
});
```

### 2.2 Fullscreen Mode (Bot API 8.0+)
```javascript
function enterFullscreen() {
  if (tg?.requestFullscreen) {
    tg.onEvent('fullscreenFailed', ({ error }) => {
      console.warn('Fullscreen failed:', error); // UNSUPPORTED | ALREADY_FULLSCREEN
    });
    tg.onEvent('fullscreenChanged', () => {
      console.log('Is fullscreen:', tg.isFullscreen);
    });
    tg.requestFullscreen();
  }
}
```

### 2.3 Orientation Lock (Bot API 8.0+)
```javascript
// Lock to current orientation (portrait or landscape)
tg.lockOrientation?.();

// Restore automatic rotation
tg.unlockOrientation?.();
```

### 2.4 Viewport Height vs Viewport Stable Height
- `tg.viewportHeight` updates continuously during user dragging gestures/animations.
- `tg.viewportStableHeight` updates **only after gesture completion**.
- **Rule of thumb**: Never bind layout calculations directly to `viewportHeight` as it causes stuttering. Use `viewportStableHeight` or CSS variable `var(--tg-viewport-stable-height)`.

---

## 3. Theme Synchronization & Dynamic Colors

Telegram supplies real-time palette tokens matching the user's active client theme (Light, Dark, Custom Tint).

### 3.1 CSS Variables Provided by Telegram
```css
body {
  background-color: var(--tg-theme-bg-color, #ffffff);
  color: var(--tg-theme-text-color, #1c1c1e);
}

.hint-text {
  color: var(--tg-theme-hint-color, #8e8e93);
}

.action-btn {
  background-color: var(--tg-theme-button-color, #2481cc);
  color: var(--tg-theme-button-text-color, #ffffff);
}

.secondary-card {
  background-color: var(--tg-theme-secondary-bg-color, #f2f2f7);
}
```

### 3.2 Dynamic Theme Listener & Header Styling
```javascript
function applyTheme() {
  const theme = tg.themeParams;
  const isDark = tg.colorScheme === 'dark';

  // Customize Telegram client window chrome
  if (tg.setHeaderColor) {
    tg.setHeaderColor(theme.bg_color || (isDark ? '#18222d' : '#ffffff'));
  }
  if (tg.setBackgroundColor) {
    tg.setBackgroundColor(theme.bg_color || (isDark ? '#0f172a' : '#f8fafc'));
  }
  if (tg.setBottomBarColor) {
    tg.setBottomBarColor(theme.secondary_bg_color || (isDark ? '#1e293b' : '#ffffff'));
  }
}

// Attach listener
tg.onEvent('themeChanged', applyTheme);
applyTheme();
```

---

## 4. Native UI Controls: BottomButtons & Navigation

Telegram provides native header and bottom buttons that feel seamless and native to mobile users.

### 4.1 MainButton & SecondaryButton (`BottomButton`)
Bot API 7.10+ unifies `MainButton` and `SecondaryButton` under the `BottomButton` interface.

```javascript
// Configure Main Button
tg.MainButton.setText("CHECKOUT ($25.00)")
  .show()
  .enable();

tg.MainButton.onClick(handleCheckout);

function handleCheckout() {
  // Display native loading spinner on the button
  tg.MainButton.showProgress(false); // false disables button while active
  
  // Call your API...
  fetch('/api/order', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      tg.MainButton.hideProgress();
      tg.HapticFeedback?.notificationOccurred('success');
    })
    .catch(() => {
      tg.MainButton.hideProgress();
      tg.HapticFeedback?.notificationOccurred('error');
    });
}

// Configure Secondary Button (Bot API 7.10+)
if (tg.SecondaryButton) {
  tg.SecondaryButton.setParams({
    text: "CANCEL",
    position: "left", // 'left' | 'right' | 'top' | 'bottom'
    is_visible: true,
    is_active: true
  });
  tg.SecondaryButton.onClick(() => {
    tg.MainButton.hide();
    tg.SecondaryButton.hide();
  });
}

// ALWAYS clean up listeners when navigating away / unmounting:
function cleanupButtons() {
  tg.MainButton.offClick(handleCheckout);
  tg.MainButton.hide();
  tg.SecondaryButton?.hide();
}
```

### 4.2 Native BackButton
Use Telegram's native header BackButton for in-app navigation instead of custom screen back buttons:

```javascript
function updateBackButton(currentScreen) {
  if (currentScreen === 'home') {
    tg.BackButton.hide();
  } else {
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
      navigateToPreviousScreen();
    });
  }
}
```

### 4.3 Native SettingsButton
```javascript
if (tg.SettingsButton) {
  tg.SettingsButton.show();
  tg.SettingsButton.onClick(() => {
    openSettingsModal();
  });
}
```

---

## 5. Mobile WebView Critical Gotcha: Modals vs `window.prompt()`

> **CRITICAL WARNING FOR TELEGRAM WEBVIEWS (iOS & Android)**:  
> Standard JavaScript browser popups (`window.prompt`, `window.alert`, `window.confirm`) are **completely blocked or return null immediately** in Telegram WebViews on iOS and Android! Never use them in production TMAs.

### 5.1 Telegram Native Popups (`tg.showPopup`)
Use `tg.showPopup()`, `tg.showAlert()`, or `tg.showConfirm()`:

```javascript
// Native Alert
tg.showAlert("Your order has been placed successfully!");

// Native Confirm
tg.showConfirm("Are you sure you want to cancel this subscription?", (ok) => {
  if (ok) {
    cancelSubscription();
  }
});

// Rich Custom Native Popup
tg.showPopup({
  title: "Confirm Refund",
  message: "Do you want to refund $15.00 to this customer's wallet?",
  buttons: [
    { id: "refund", type: "destructive", text: "Refund Funds" },
    { id: "cancel", type: "cancel" }
  ]
}, (buttonId) => {
  if (buttonId === "refund") {
    executeRefund();
  }
});
```

### 5.2 In-App Custom Bottom Sheets (For complex inputs like balance, discounts, forms)
When collecting text, numeric amounts, or selections, always render an in-app HTML modal sheet with CSS slide-up animations and preset chips:

```html
<div class="admin-modal-overlay" id="custom-modal" style="display: none;">
  <div class="admin-modal-sheet">
    <h3>Adjust User Balance</h3>
    <input type="number" id="amt-input" placeholder="0.00" inputmode="decimal">
    <div class="chips">
      <button onclick="setAmount(10)">+$10</button>
      <button onclick="setAmount(25)">+$25</button>
      <button onclick="setAmount(50)">+$50</button>
    </div>
    <button onclick="submitModal()">Confirm</button>
  </div>
</div>
```

---

## 6. Haptic Feedback

Telegram provides rich native tactile feedback via `tg.HapticFeedback`. Use it to give users tactile confirmation:

| Action / Event | Recommended Haptic Call |
|---|---|
| Tab switch, segmented control, radio selection | `tg.HapticFeedback.selectionChanged()` |
| Button tap, card click, chip toggle | `tg.HapticFeedback.impactOccurred('light')` |
| Primary action confirmation, swipe gesture | `tg.HapticFeedback.impactOccurred('medium')` |
| Destructive action, delete, ban | `tg.HapticFeedback.impactOccurred('heavy')` or `'rigid'` |
| Success toast, completed payment, confetti | `tg.HapticFeedback.notificationOccurred('success')` |
| Validation error, failed payment | `tg.HapticFeedback.notificationOccurred('error')` |
| Insufficient funds, warning notice | `tg.HapticFeedback.notificationOccurred('warning')` |

```javascript
function haptic(type = 'light') {
  try {
    if (!window.Telegram?.WebApp?.HapticFeedback) return;
    const h = window.Telegram.WebApp.HapticFeedback;
    if (['light', 'medium', 'heavy', 'rigid', 'soft'].includes(type)) {
      h.impactOccurred(type);
    } else if (['error', 'success', 'warning'].includes(type)) {
      h.notificationOccurred(type);
    } else if (type === 'selection') {
      h.selectionChanged();
    }
  } catch (e) {
    // Ignore unsupported environments silently
  }
}
```

---

## 7. Backend Cryptographic Validation (`initData`)

Never trust client-side data (`initDataUnsafe`). Send `tg.initData` to your backend and verify the cryptographic signature using HMAC-SHA256 with the bot token.

### 7.1 Python / FastAPI Validation Implementation
```python
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """
    Cryptographically validate Telegram WebApp initData string using HMAC-SHA256.
    
    1. Parse query string into key-value pairs.
    2. Extract 'hash'.
    3. Generate secret_key = HMAC_SHA256(bot_token, "WebAppData").
    4. Build data_check_string = sorted key=value pairs joined with '\n'.
    5. Compare HMAC_SHA256(data_check_string, secret_key).hexdigest() == hash.
    6. Verify auth_date is within max_age_seconds to prevent replay attacks.
    """
    if not init_data:
        raise ValueError("Missing init_data")

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    parsed.pop("signature", None) # Remove third-party signature if present

    if not received_hash:
        raise ValueError("Missing hash parameter")

    # Verify auth_date freshness
    auth_date = int(parsed.get("auth_date", 0))
    if max_age_seconds > 0 and (time.time() - auth_date) > max_age_seconds:
        raise ValueError("init_data has expired")

    # Create data_check_string: alphabetical sort of key=value pairs separated by \n
    check_items = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(check_items)

    # Calculate HMAC secret key
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    # Calculate expected hash
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid init_data signature")

    # Deserialize complex nested objects (e.g. 'user')
    result = dict(parsed)
    if "user" in result:
        result["user"] = json.loads(result["user"])

    return result
```

---

## 8. Payments, Invoices & Monetization

### 8.1 Telegram Stars (XTR) & In-App Purchases
To accept Telegram Stars in a Mini App:
1. Backend creates an invoice link using Bot API `createInvoiceLink` with `currency="XTR"`.
2. Frontend opens invoice via `tg.openInvoice()`:

```javascript
async function payWithStars(amountUsd) {
  const res = await fetch('/api/stars/create-invoice', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_usd: amountUsd, init_data: tg.initData })
  });
  const data = await res.json();
  
  if (data.invoice_link) {
    tg.openInvoice(data.invoice_link, (status) => {
      if (status === 'paid') {
        haptic('success');
        showToast("Payment Successful!");
        reloadBalance();
      } else if (status === 'failed') {
        haptic('error');
        showToast("Payment Failed");
      } else if (status === 'cancelled') {
        showToast("Payment Cancelled");
      }
    });
  }
}
```

### 8.2 External Payments (Crypto / Gateways)
When directing users to crypto checkout (e.g. KryptoExpress, ShamCash, Stripe):
- Use `tg.openLink(url)` which opens the external URL in the user's default browser or in-app browser sheet without closing the Mini App.
- Never use standard `window.open()` or `location.href` which can terminate or unmount the Mini App context.

---

## 9. CloudStorage & DeviceStorage (Bot API 6.9+ / 9.0+)

Telegram provides cloud-synced storage across all devices of the user, as well as local persistent device storage.

### 9.1 Telegram CloudStorage (Synced across user devices)
- Up to 1024 keys per user.
- Max 4096 characters per value.

```javascript
// Store item
tg.CloudStorage?.setItem('selected_lang', 'ar', (err, stored) => {
  if (!err && stored) console.log('Saved to Telegram Cloud!');
});

// Retrieve item
tg.CloudStorage?.getItem('selected_lang', (err, val) => {
  if (!err && val) setLanguage(val);
});
```

---

## 10. Bot API 8.0+ Advanced Features

### 10.1 Home Screen Shortcut Pinning
Prompt mobile users to install the Mini App directly to their home screen:

```javascript
function checkAndPromptHomeScreen() {
  if (tg?.checkHomeScreenStatus) {
    tg.checkHomeScreenStatus((status) => {
      // 'unsupported' | 'unknown' | 'added' | 'missed'
      if (status === 'missed') {
        showHomeScreenBanner();
      }
    });
  }
}

function installShortcut() {
  tg?.addToHomeScreen?.();
}
```

### 10.2 Native QR Scanner
```javascript
function scanBarcode() {
  if (tg?.showScanQrPopup) {
    tg.showScanQrPopup({ text: "Scan payment or voucher QR code" }, (text) => {
      handleVoucherCode(text);
      return true; // Return true to close scanner popup
    });
  }
}
```

### 10.3 Native File Downloads
```javascript
if (tg?.downloadFile) {
  tg.downloadFile({
    url: "https://example.com/receipt.pdf",
    file_name: "receipt-1049.pdf"
  }, (accepted) => {
    if (accepted) console.log('Download started');
  });
}
```

---

## 11. Production Checklist & Performance Rules

1. **Disable Overscroll Bounce**: Always add `overscroll-behavior-y: none;` on `<html>` and `<body>` to prevent rubber-band bounce.
2. **Disable User Select on UI**: Use `user-select: none; -webkit-user-select: none;` on buttons, headers, and tabs to avoid accidental text highlighting on long presses.
3. **Touch Action Manipulation**: Add `touch-action: manipulation;` on buttons to remove the 300ms tap delay on iOS.
4. **Transparent Tap Highlight**: Add `-webkit-tap-highlight-color: transparent;` to eliminate grey boxes on tapped elements in WebKit.
5. **Virtual Keyboard Layout**: Never rely on `100vh` or `window.innerHeight` for bottom buttons; use `var(--tg-viewport-stable-height)` and padding with `var(--tg-content-safe-area-inset-bottom)`.
6. **Graceful Degradation**: Always wrap Telegram WebApp calls in optional chaining (`tg?.HapticFeedback?.impactOccurred?.('light')`) so the app can be developed, previewed, and tested in standard browsers without crashing.
