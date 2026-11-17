#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-status}
case "$MODE" in
    status|stop) ;;
    *) printf 'Use this command alone for progress, or add stop.\n'; exit 2 ;;
esac
cd "$ROOT"
LOCAL_ROOT="$HOME/.cache/nba-gm-audits/market-lifecycle-2026-10-25/runtime"
if [ -f "$LOCAL_ROOT/local-runtime.json" ]; then
    exec env PYTHONPATH="$LOCAL_ROOT/src:$LOCAL_ROOT/scripts" \
        "$HOME/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12" -B \
        "$LOCAL_ROOT/scripts/overnight_market_health.py" "$MODE"
fi
exec env PYTHONPATH="$ROOT/src:$ROOT/scripts" \
    "$ROOT/.cache/macos-beta-build/arm64/venv/bin/python" -B \
    "$ROOT/scripts/overnight_market_health.py" "$MODE"
