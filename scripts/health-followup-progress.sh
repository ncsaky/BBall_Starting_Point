#!/bin/sh
set -eu
RUN="$HOME/.cache/nba-gm-audits/health-followup-2026-10-26/runtime/output/health-followup-2026-10-26"
case "${1:-status}" in
    stop) touch "$RUN/STOP"; printf 'Stop requested; the current action can finish and checkpoint.\n'; exit 0 ;;
    status) ;;
    *) printf 'Use alone for progress, or add stop.\n'; exit 2 ;;
esac
exec python3 - "$RUN" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
status = json.loads((root / "status.json").read_text())
run = json.loads((root / "career-17/run.json").read_text())
job = status["jobs"]["17"]
print(f"Final-season follow-up: {status['status']} | seed 17: {job['status']}")
print(f"Date: {run['endpoint']} -> {run['target']} | {run['complete_seasons']}/10 seasons complete")
print(f"Limit: 90 minutes, then safe checkpoint stopping | reason: {status.get('stop_reason') or 'none'}")
print("The other three ten-season careers are already complete; they are not being rerun.")
PY
