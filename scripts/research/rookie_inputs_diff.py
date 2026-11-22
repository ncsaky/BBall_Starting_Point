#!/usr/bin/env python3
"""ROOKIE-FIT-2 check: which players' inputs differ between two input files (veterans must be byte-identical).

    python3 scripts/research/rookie_inputs_diff.py data/canonical/player_inputs_2026_27.json.gz output/rookie-fit-2/player_inputs_after.json
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())
    rookies = {p["id"] for p in universe["players"] if str(p.get("draft_year")) == "2026"}
    pa, pb = a["players"], b["players"]
    changed = [pid for pid in set(pa) | set(pb)
               if json.dumps(pa.get(pid), sort_keys=True) != json.dumps(pb.get(pid), sort_keys=True)]
    inputs = Counter(iid for pid in changed for iid in set(pa.get(pid, {}).get("inputs", {})) | set(pb.get(pid, {}).get("inputs", {}))
                     if json.dumps(pa.get(pid, {}).get("inputs", {}).get(iid), sort_keys=True)
                     != json.dumps(pb.get(pid, {}).get("inputs", {}).get(iid), sort_keys=True))
    veterans = [pid for pid in changed if pid not in rookies]
    print(f"players {len(pb)}; changed {len(changed)} (rookies {len(changed) - len(veterans)}, others {len(veterans)})")
    print("others changed:", veterans[:20])
    print("inputs changed (count of players):", dict(sorted(inputs.items())))
    print("top-level keys equal:", {k: a[k] == b[k] for k in a if k != "players"})


if __name__ == "__main__":
    main()
