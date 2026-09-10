#!/bin/bash
set -e

CF_PID=""
APP_PID=""

cleanup() {
    echo "[entrypoint] Received termination signal. Shutting down..."
    if [ -n "$CF_PID" ] && kill -0 "$CF_PID" 2>/dev/null; then
        kill -TERM "$CF_PID" 2>/dev/null
    fi
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        kill -TERM "$APP_PID" 2>/dev/null
    fi
    wait 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start cloudflared if TUNNEL_TOKEN is provided
if [ -n "$TUNNEL_TOKEN" ]; then
    echo "[entrypoint] Starting Cloudflare Tunnel in all-in-one container..."
    cloudflared --no-autoupdate tunnel --no-autoupdate run --protocol http2 --token "$TUNNEL_TOKEN" &
    CF_PID=$!
else
    echo "[entrypoint] TUNNEL_TOKEN not set; skipping Cloudflare Tunnel."
fi

# Run the command passed as arguments, or default to python -u run.py
if [ $# -gt 0 ]; then
    echo "[entrypoint] Starting: $*"
    "$@" &
    APP_PID=$!
else
    echo "[entrypoint] Starting GH Store Bot (python -u run.py)..."
    python -u run.py &
    APP_PID=$!
fi

# Supervise cloudflared: restart on transient failure, never kill bot on tunnel blip.
if [ -n "$TUNNEL_TOKEN" ]; then
    (
    while true; do
        if ! kill -0 "$CF_PID" 2>/dev/null; then
            echo "[entrypoint] Restarting Cloudflare Tunnel..."
            cloudflared --no-autoupdate tunnel --no-autoupdate run --protocol http2 --token "$TUNNEL_TOKEN" &
            CF_PID=$!
        fi
        sleep 15
    done
    ) &
fi

wait "$APP_PID"
EXIT_CODE=$?

cleanup
exit $EXIT_CODE
