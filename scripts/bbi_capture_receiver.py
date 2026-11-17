#!/usr/bin/env python3
"""Local receiver for Basketball Index (Fanspo-hosted) player report-card captures.

The capture loop runs inside the user's signed-in browser tab and POSTs each rendered report card here, so
large page data never has to pass through the chat. Each capture is stored gzipped and untouched under
data/research/bbi/captures/fanspo_profiles/<season>/<player-slug>-<nba-id>.json.gz, with a JSONL log.

Personal-use archive of pages the paid membership displays; see docs/agents/tasks/bbi-capture-plan.md.

    PYTHONPATH=src .venv/bin/python scripts/bbi_capture_receiver.py [--port 8799]
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/bbi/captures/fanspo_profiles"
LOG = OUT / "capture_log.jsonl"
SAFE = re.compile(r"[^a-z0-9.\-]+")
ALLOWED_ORIGINS = ("https://fanspo.com", "https://www.fanspo.com")


RX_PAGE = """<!doctype html><meta charset="utf-8"><title>BBI capture receiver</title>
<body style="font:14px system-ui;padding:16px"><h3>Basketball Index capture receiver</h3>
<p>Keep this tab open while capturing. Saved: <b id="n">0</b> &middot; last: <span id="l">-</span></p>
<script>
let n = 0;
window.addEventListener("message", async (event) => {
  if (!/^https:\\/\\/(www\\.)?fanspo\\.com$/.test(event.origin)) return;
  const data = event.data;
  if (!data || data.kind !== "bbi-profile") return;
  const r = await fetch("/save", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  const out = await r.json();
  n += 1; document.getElementById("n").textContent = n; document.getElementById("l").textContent = out.saved;
  (event.source || window.parent).postMessage({kind: "bbi-saved", id: data.nba_id, season: data.season, rows: out.rows}, event.origin);
});
</script></body>"""


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        origin = self.headers.get("Origin") or ""
        self.send_header("Access-Control-Allow-Origin", origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0])
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self) -> None:  # noqa: N802 (http.server naming)
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/rx"):
            # Relay page: the capture tab hands each report card to this window via postMessage (accepted
            # only from fanspo.com), and this same-origin page saves it with a normal POST.
            body = RX_PAGE.encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return
        counts = {p.name: len(list(p.glob("*.json.gz"))) for p in sorted(OUT.glob("*")) if p.is_dir()}
        body = json.dumps({"ok": True, "captured": counts}).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if (self.headers.get("Origin") or "") not in (*ALLOWED_ORIGINS, f"http://127.0.0.1:{self.server.server_port}"):
            self.send_response(403)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 20_000_000:
            self.send_response(413)
            self.end_headers()
            return
        payload = json.loads(self.rfile.read(length))
        season = SAFE.sub("-", str(payload.get("season", "unknown")).lower())
        slug = SAFE.sub("-", f"{payload.get('slug', 'player')}-{payload.get('nba_id', 'x')}".lower())
        folder = OUT / season
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{slug}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        rows = len(payload.get("rows") or [])
        locked = sum(1 for r in payload.get("rows") or [] if "MEMBERS" in (str(r.get("value")), str(r.get("percentile"))))
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "season": season, "file": path.name,
                                  "rows": rows, "locked": locked, "url": payload.get("url")}) + "\n")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"saved": path.name, "rows": rows}).encode())

    def log_message(self, *args) -> None:  # keep the console quiet; the JSONL log is the record
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"BBI capture receiver on http://127.0.0.1:{args.port} -> {OUT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
