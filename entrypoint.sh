#!/bin/bash
set -e

APP_PID=""
CF_PID=""
SUPERVISOR_PID=""

cleanup() {
    echo "[entrypoint] Received termination signal. Shutting down..."
    if [ -f /tmp/cloudflared.pid ]; then
        local pid
        pid=$(cat /tmp/cloudflared.pid 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
        rm -f /tmp/cloudflared.pid
    fi
    if [ -n "$SUPERVISOR_PID" ] && kill -0 "$SUPERVISOR_PID" 2>/dev/null; then
        kill -TERM "$SUPERVISOR_PID" 2>/dev/null || true
    fi
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        kill -TERM "$APP_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

start_cloudflared() {
    cloudflared --no-autoupdate --metrics 127.0.0.1:20241 tunnel --no-autoupdate run \
        --protocol http2 \
        --token "$TUNNEL_TOKEN" &
    CF_PID=$!
    echo "$CF_PID" > /tmp/cloudflared.pid
}

# Supervise cloudflared: active health monitoring with auto-recovery
if [ -n "$TUNNEL_TOKEN" ]; then
    echo "[entrypoint] Starting Cloudflare Tunnel in all-in-one container..."
    (
        start_cloudflared
        fail_count=0
        
        while true; do
            sleep 15

            # 1. Process liveness check
            if [ -z "$CF_PID" ] || ! kill -0 "$CF_PID" 2>/dev/null; then
                echo "[entrypoint] Cloudflare Tunnel process died. Restarting..."
                start_cloudflared
                fail_count=0
                continue
            fi

            # 2. Readiness check against cloudflared's metrics endpoint
            # Returns 200 with readyConnections > 0 when edge tunnels are healthy
            if curl -s -f -m 5 http://127.0.0.1:20241/ready 2>/dev/null | grep -q '"readyConnections": *[1-9]'; then
                fail_count=0
            else
                fail_count=$((fail_count + 1))
                echo "[entrypoint] Cloudflare Tunnel readiness check failed ($fail_count/3)..."
                if [ "$fail_count" -ge 3 ]; then
                    echo "[entrypoint] Cloudflare Tunnel has had no active edge connections for 45s. Forcing restart..."
                    kill -TERM "$CF_PID" 2>/dev/null || true
                    sleep 2
                    if kill -0 "$CF_PID" 2>/dev/null; then
                        kill -9 "$CF_PID" 2>/dev/null || true
                    fi
                    start_cloudflared
                    fail_count=0
                fi
            fi
        done
    ) &
    SUPERVISOR_PID=$!
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

wait "$APP_PID"
EXIT_CODE=$?

cleanup
exit $EXIT_CODE
