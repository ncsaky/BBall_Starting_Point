"""Can a player's ratings predict his real offensive and defensive role? (playtest 2026-11-22)

Veterans carry real primary roles; drafted rookies only have placeholders from their position. This fits role
profiles on veterans' derived traits (plus height) and measures, on veterans held out of the fit, how often the
nearest profile (or the k nearest veterans) picks the real role, against the position placeholder rule."""
from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.ingest import rookie_def_role, rookie_off_role  # noqa: E402
from nba_gm_data.ratings_model import _trait_values, install_inputs_model  # noqa: E402


def main() -> None:
    canon = load_app_canonical(ROOT)
    install_inputs_model(canon, ROOT)
    traits = _trait_values(canon)
    keys = sorted({k for v in traits.values() for k in v})
    vets = [p for p in canon["players"] if p.get("team_id") and p.get("primary_off_role") and p.get("primary_def_role")
            and str(p.get("draft_year") or "0").isdigit() and int(p.get("draft_year") or 0) < 2026 and p["id"] in traits]
    feats = keys + ["height_inches"]

    def vec(p):
        t = traits[p["id"]]
        return [float(t.get(k, 50.0)) for k in keys] + [float(p.get("height_inches") or 78)]

    X = [vec(p) for p in vets]
    mean = [sum(col) / len(col) for col in zip(*X)]
    sd = [max(1e-6, math.sqrt(sum((x - m) ** 2 for x in col) / len(col))) for col, m in zip(zip(*X), mean)]
    Z = [[(x - m) / s for x, m, s in zip(row, mean, sd)] for row in X]
    # Shape, not level: each player's trait z-scores minus his own average trait z-score, so a raw rookie is compared
    # by what he is relatively good at. Height (last column) stays absolute, weighted by HEIGHT_WEIGHT.
    HEIGHT_WEIGHT = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    SHAPE = "--level" not in sys.argv

    def shape(z):
        if not SHAPE:
            return z
        body = z[:-1]
        avg = sum(body) / len(body)
        body = [v - avg for v in body]
        if "--cosine" in sys.argv:  # direction of strengths only: a flatter (raw) profile still points the same way
            norm = math.sqrt(sum(v * v for v in body)) or 1.0
            body = [v / norm * math.sqrt(len(body)) for v in body]
        return body + [z[-1] * HEIGHT_WEIGHT]
    Z = [shape(z) for z in Z]

    def dist(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b))

    out = {"features": feats, "veterans": len(vets)}
    rng = random.Random(7)
    order = list(range(len(vets)))
    rng.shuffle(order)
    folds = [order[i::5] for i in range(5)]
    for side, field, rule in (("offense", "primary_off_role", rookie_off_role), ("defense", "primary_def_role", rookie_def_role)):
        y = [p[field] for p in vets]
        res = {"placeholder": 0, "centroid": 0, **{f"knn{k}": 0 for k in (5, 9, 15, 25)}}
        for fold in folds:
            held = set(fold)
            train = [i for i in range(len(vets)) if i not in held]
            cents = {}
            for role in set(y[i] for i in train):
                rows = [Z[i] for i in train if y[i] == role]
                cents[role] = [sum(c) / len(rows) for c in zip(*rows)]
            for i in fold:
                res["placeholder"] += rule(vets[i].get("position") or "") == y[i]
                res["centroid"] += min(cents, key=lambda r: dist(Z[i], cents[r])) == y[i]
                near = sorted(train, key=lambda j: dist(Z[i], Z[j]))
                for k in (5, 9, 15, 25):
                    votes = Counter()
                    for j in near[:k]:
                        votes[y[j]] += 1.0 / (1.0 + dist(Z[i], Z[j]))
                    res[f"knn{k}"] += votes.most_common(1)[0][0] == y[i]
        n = len(vets)
        out[side] = {name: round(v / n, 3) for name, v in res.items()}
        out[side]["most_common_share"] = round(Counter(y).most_common(1)[0][1] / n, 3)
    rookies = [p for p in canon["players"] if p.get("team_id") and str(p.get("draft_year") or "").isdigit()
               and int(p["draft_year"]) >= 2026 and p["id"] in traits]
    for side, field in (("offense", "primary_off_role"), ("defense", "primary_def_role")):
        counts = Counter()
        for p in rookies:
            z = shape([(x - m) / s for x, m, s in zip(vec(p), mean, sd)])
            near = sorted(range(len(vets)), key=lambda j: dist(z, Z[j]))[:15]
            votes = Counter()
            for j in near:
                votes[vets[j][field]] += 1.0 / (1.0 + dist(z, Z[j]))
            counts[votes.most_common(1)[0][0]] += 1
        out[side]["rookie_roles_k15"] = dict(counts.most_common())
    out["veteran_role_shares"] = {f: dict(Counter(p[f] for p in vets).most_common()) for f in ("primary_off_role", "primary_def_role")}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
