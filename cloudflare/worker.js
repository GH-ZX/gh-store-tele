export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === "/health" || url.pathname === "/status") {
      return new Response(
        JSON.stringify({
          status: "healthy",
          service: env.SERVICE_NAME || "gh-store-bot",
          domain: "bot.gh-store.me",
          backend_configured: Boolean(env.BACKEND_URL && env.BACKEND_URL.trim()),
          timestamp: new Date().toISOString()
        }, null, 2),
        {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store"
          }
        }
      );
    }

    const backendUrl = env.BACKEND_URL ? env.BACKEND_URL.trim().replace(/\/+$/, "") : null;

    // If backend origin is configured, proxy request to the backend bot server
    if (backendUrl) {
      try {
        const targetUrl = new URL(url.pathname + url.search, backendUrl);
        const headers = new Headers(request.headers);
        headers.set("X-Forwarded-Host", url.host);
        headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

        const init = {
          method: request.method,
          headers: headers,
          redirect: "follow"
        };

        if (request.method !== "GET" && request.method !== "HEAD") {
          init.body = request.body;
        }

        const response = await fetch(targetUrl.toString(), init);
        const newHeaders = new Headers(response.headers);
        newHeaders.set("X-Edge-Gateway", "gh-store-bot");
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: newHeaders
        });
      } catch (err) {
        console.error("Backend proxy error:", err);
        return new Response(
          JSON.stringify({
            error: "Bad Gateway",
            message: "Failed to forward request to bot backend",
            details: err.message
          }),
          { status: 502, headers: { "Content-Type": "application/json" } }
        );
      }
    }

    // If backend is not configured yet, gracefully answer webhooks so Telegram / payment callbacks don't fail
    if (request.method === "POST") {
      if (url.pathname === "/" || url.pathname === "/webhook") {
        return new Response(
          JSON.stringify({
            ok: true,
            status: "queued_at_edge",
            notice: "bot.gh-store.me Cloudflare Worker is active. Set BACKEND_URL secret to forward updates to your bot server."
          }),
          { headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.pathname === "/samwebhook" || url.pathname === "/ventebot") {
        return new Response(
          JSON.stringify({ status: "ok" }),
          { headers: { "Content-Type": "application/json" } }
        );
      }
    }

    // Default info landing page
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>GH Store Bot Edge Gateway</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; max-width: 540px; width: 100%; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    h1 { margin-top: 0; font-size: 22px; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
    .badge { display: inline-block; background: #059669; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 16px; }
    p { line-height: 1.6; color: #94a3b8; font-size: 14px; }
    code { background: #0f172a; color: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
    .endpoint { margin: 12px 0; padding: 10px; background: #0f172a; border-radius: 6px; border-left: 3px solid #38bdf8; font-size: 13px; word-break: break-all; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">Active & Ready</div>
    <h1>🤖 GH Store Bot Edge Gateway</h1>
    <p>This Cloudflare Worker is running on <b>bot.gh-store.me</b>.</p>
    <p>It handles incoming Telegram webhooks and payment callbacks, and forwards them to your bot backend service.</p>
    <div class="endpoint"><b>Public Hostname:</b> https://bot.gh-store.me</div>
    <div class="endpoint"><b>Health Check:</b> <a href="/health" style="color: #38bdf8">https://bot.gh-store.me/health</a></div>
    <p style="margin-top: 20px;">To connect your bot container or server, set the <code>BACKEND_URL</code> environment variable or secret in Cloudflare Dashboard or via Wrangler:</p>
    <div class="endpoint"><code>wrangler secret put BACKEND_URL</code></div>
  </div>
</body>
</html>`;

    return new Response(html, {
      headers: { "Content-Type": "text/html; charset=utf-8" }
    });
  }
};
