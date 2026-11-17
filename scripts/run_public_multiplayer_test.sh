#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${NBA_GM_PORT:-$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')}"
SAVE_DIR="${NBA_GM_MULTIPLAYER_SAVE_DIR:-$ROOT/saves}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is required for the temporary public URL."
  echo "Install it once with: brew install cloudflared"
  exit 1
fi

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [[ -n "${TUNNEL_PID:-}" ]]; then
    kill "$TUNNEL_PID" 2>/dev/null || true
    wait "$TUNNEL_PID" 2>/dev/null || true
  fi
  if [[ -n "${TUNNEL_LOG:-}" ]]; then
    rm -f "$TUNNEL_LOG"
  fi
}
trap cleanup EXIT INT TERM

# Discover the exact public origin before starting the API. Never allow all
# tunnel domains or trust a client-supplied forwarded Host/Origin header.
TUNNEL_LOG="$(mktemp -t nba-gm-tunnel.XXXXXX)"
cloudflared tunnel --url "http://127.0.0.1:$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
PUBLIC_ORIGIN=""
for _ in {1..120}; do
  PUBLIC_ORIGIN="$(sed -n 's/.*\(https:\/\/[-a-z0-9]*\.trycloudflare\.com\).*/\1/p' "$TUNNEL_LOG" | head -n 1)"
  if [[ -n "$PUBLIC_ORIGIN" ]]; then
    break
  fi
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    cat "$TUNNEL_LOG"
    exit 1
  fi
  sleep 0.25
done
if [[ -z "$PUBLIC_ORIGIN" ]]; then
  cat "$TUNNEL_LOG"
  echo "The tunnel did not supply an exact public URL."
  exit 1
fi

cd "$ROOT"
PYTHONPATH="$ROOT/src" python3 -m nba_gm_data.app_server \
  --root "$ROOT" \
  --save-dir "$SAVE_DIR" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --allowed-origin "$PUBLIC_ORIGIN" \
  --public-multiplayer-only &
SERVER_PID=$!

for _ in {1..40}; do
  if curl --silent --fail "http://127.0.0.1:$PORT/api/session" >/dev/null; then
    SERVER_READY=1
    break
  fi
  sleep 0.25
done

if ! kill -0 "$SERVER_PID" 2>/dev/null || [[ "${SERVER_READY:-0}" != 1 ]]; then
  echo "The NBA GM server failed to start."
  exit 1
fi

echo
echo "Temporary public multiplayer test: $PUBLIC_ORIGIN"
echo "Share this URL with friends. Press Ctrl-C to stop."
echo
wait "$TUNNEL_PID"
