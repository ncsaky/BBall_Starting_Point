"""Tables comparing real and generated draft classes (reads output/prospect-realism/*.json).

    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_report.py [generated.json]
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict

from prospect_realism import OUT, PICK_RANGES, TIER_NAMES, minutes_role, q, read_draft_csv, tier_for_rank

RANGES = [r[0] for r in PICK_RANGES]
SIDES = ("overall", "offense", "defense")


def fmt(values: list[float], digits: int = 1) -> str:
    if not values:
        return "–"
    lo, mid, hi = q(values, .1, .5, .9)
    return f"{mid:.{digits}f} ({lo:.{digits}f}–{hi:.{digits}f})"


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "–"


def class_sizes() -> dict[int, Counter]:
    sizes: dict[int, Counter] = defaultdict(Counter)
    for row in read_draft_csv():
        from prospect_realism import pick_range
        sizes[int(row["draft_year"])][pick_range(row["pick"])] += 1
    return sizes


def real_entry(real: dict, mode: str, year: int) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for p in real["game"][mode]["players"]:
        if p["draft_year"] == year and p["range"] in RANGES:
            out[p["range"]].append(p)
    return out


def generated_by_range(gen: dict, mode: str) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in gen[mode]["rows"]:
        out[r["range"]].append(r)
    return out


def entry_table(real: dict, gen: dict | None, mode: str) -> str:
    rows = []
    real_by = real_entry(real, mode, 2026)
    gen_by = generated_by_range(gen, mode) if gen else {}
    for rng in RANGES:
        r, g = real_by.get(rng, []), gen_by.get(rng, [])
        rows.append([rng, "real 2026", len(r), fmt([p["age"] for p in r]), fmt([p["overall"] for p in r]),
                     fmt([p["offense"] for p in r]), fmt([p["defense"] for p in r]),
                     fmt([p["league_rank"] for p in r], 0)])
        if g:
            rows.append(["", "generated", len(g), fmt([p["age"] for p in g]), fmt([p["overall"] for p in g]),
                         fmt([p["offense"] for p in g]), fmt([p["defense"] for p in g]),
                         fmt([p["league_rank"] for p in g], 0)])
    return table(["Picks", "Source", "N", "Age", "OVR", "OFF", "DEF", "League rank"], rows)


def path_table(real: dict, gen: dict | None, mode: str) -> str:
    """Median OVR after k seasons. Real: cross-section of the 2026..2022 classes (survivors only)."""
    rows = []
    gen_by = generated_by_range(gen, mode) if gen else {}
    for rng in RANGES:
        cells = []
        for k, year in enumerate((2026, 2025, 2024, 2023, 2022)):
            players = real_entry(real, mode, year).get(rng, [])
            cells.append(f"{st.median([p['overall'] for p in players]):.1f} (n={len(players)})" if players else "–")
        rows.append([rng, "real (survivors)", *cells])
        g = gen_by.get(rng, [])
        if g and g[0].get("history"):
            cells = []
            for k in range(5):
                vals = [r["history"][k]["overall"] for r in g if len(r["history"]) > k]
                survivors = [r["history"][k]["overall"] for r in g if len(r["history"]) > k and r["ranks"][k] <= 450]
                cells.append(f"{st.median(vals):.1f} / {st.median(survivors):.1f}" if survivors else f"{st.median(vals):.1f}")
            rows.append(["", "generated all / top-450", *cells])
    return table(["Picks", "Source", "Entry", "After 1", "After 2", "After 3", "After 4"], rows)


def real_tiers(real: dict, mode: str, year: int, sizes: dict[int, Counter]) -> dict[str, Counter]:
    out = defaultdict(Counter)
    for p in real["game"][mode]["players"]:
        if p["draft_year"] == year and p["range"] in RANGES:
            out[p["range"]][tier_for_rank(p["league_rank"])] += 1
    for rng in RANGES:
        missing = sizes.get(year, Counter()).get(rng, 0) - sum(out[rng].values())
        out[rng]["out"] += max(0, missing)
    return out


def tiers_table(real: dict, gen: dict | None, mode: str, seasons: int = 4) -> str:
    sizes = class_sizes()
    rows = []
    gen_by = generated_by_range(gen, mode) if gen else {}
    for rng in RANGES:
        for label, year in (("real 2022 (after 4)", 2022), ("real 2023 (after 3)", 2023)):
            c = real_tiers(real, mode, year, sizes)[rng]
            n = sum(c.values())
            rows.append([rng if label.startswith("real 2022") else "", label, n, *[pct(c[t], n) for t in TIER_NAMES]])
        g = [r for r in gen_by.get(rng, []) if len(r.get("ranks", [])) > seasons]
        if g:
            c = Counter(tier_for_rank(r["ranks"][seasons]) for r in g)
            rows.append(["", f"generated (after {seasons})", len(g), *[pct(c[t], len(g)) for t in TIER_NAMES]])
            c = Counter(tier_for_rank(r["ranks"][0]) for r in g)
            rows.append(["", "generated (entry)", len(g), *[pct(c[t], len(g)) for t in TIER_NAMES]])
    return table(["Picks", "Source", "N", "Star (top 25)", "Starter (26–150)", "Rotation (151–300)",
                  "Bench (301–450)", "Out (450+ or gone)"], rows)


def bbi_table(real: dict) -> str:
    """Year-4 role from Basketball Index minutes and offensive talent rank, 2015-2022 classes."""
    rows = []
    picks = real["bbi"]["picks"]
    for rng in RANGES:
        group = [p for p in picks if p["range"] == rng and p["draft_year"] <= 2021]
        n = len(group)
        role = Counter(minutes_role((p["history"][3] or {}).get("minutes")) for p in group)
        top25 = sum(1 for p in group if (p["history"][3] or {}).get("rank") and p["history"][3]["rank"] <= 25)
        top100 = sum(1 for p in group if (p["history"][3] or {}).get("rank") and p["history"][3]["rank"] <= 100)
        vorp = [p["career_vorp"] for p in group if p["career_vorp"] is not None]
        big = sum(1 for p in group if (p["career_vorp"] or 0) >= 15)
        rows.append([rng, n, pct(role["starter"], n), pct(role["rotation"], n), pct(role["bench"], n), pct(role["out"], n),
                     pct(top25, n), pct(top100, n), pct(big, n)])
    return table(["Picks", "N (2015–21)", "Yr-4 starter minutes (2,000+)", "Rotation (1,000–1,999)", "Bench",
                  "No yr-4 NBA season", "Yr-4 offense top 25", "Yr-4 offense top 100", "Career VORP 15+"], rows)


def growth_table(real: dict, gen: dict | None, mode: str) -> str:
    """League-percentile change over three seasons for players still in the league at the end.

    Basketball Index: offensive talent rank, rookie season to season 4 (2015-2022 classes, players with both).
    Generated: overall rank among the opening league, after season 1 to after season 4, kept if ranked in the
    top 450 after season 4."""
    seasons = real["bbi"]["seasons"]
    rows = []
    gen_by = generated_by_range(gen, mode) if gen else {}
    for rng in RANGES:
        changes = []
        for p in real["bbi"]["picks"]:
            h = p["history"]
            if p["range"] == rng and h[0] and h[3] and h[0].get("rank") and h[3].get("rank"):
                changes.append((1 - h[3]["rank"] / seasons[h[3]["season"]]["count"])
                               - (1 - h[0]["rank"] / seasons[h[0]["season"]]["count"]))
        g = [r for r in gen_by.get(rng, []) if len(r.get("ranks", [])) > 4 and r["ranks"][4] <= 450]
        gen_changes = [(r["ranks"][1] - r["ranks"][4]) / 691 for r in g]
        rows.append([rng, len(changes), fmt([100 * c for c in changes], 0), len(g), fmt([100 * c for c in gen_changes], 0)])
    return table(["Picks", "BBI N", "BBI change (pct points)", "Generated N", "Generated change (pct points)"], rows)


def bbi_class_variation(real: dict) -> str:
    rows = []
    picks = real["bbi"]["picks"]
    for year in range(2015, 2022):
        group = [p for p in picks if p["draft_year"] == year]
        role = Counter(minutes_role((p["history"][3] or {}).get("minutes")) for p in group)
        top100 = sum(1 for p in group if (p["history"][3] or {}).get("rank") and p["history"][3]["rank"] <= 100)
        big = sum(1 for p in group if (p["career_vorp"] or 0) >= 15)
        rows.append([year, len(group), role["starter"], role["starter"] + role["rotation"], top100, big])
    return table(["Class", "Picks", "Yr-4 starters", "Yr-4 starters + rotation", "Yr-4 offense top 100", "Career VORP 15+"], rows)


def gen_class_variation(gen: dict, mode: str, seasons: int = 4) -> str:
    rows = []
    groups = defaultdict(list)
    for r in gen[mode]["rows"]:
        groups[(r["year"], r["seed"])].append(r)
    for (year, seed), group in sorted(groups.items()):
        if len(group[0].get("ranks", [])) <= seasons:
            continue
        tiers = Counter(tier_for_rank(r["ranks"][seasons]) for r in group)
        entry = Counter(tier_for_rank(r["ranks"][0]) for r in group)
        rows.append([f"{year} seed {seed}", len(group), entry["star"] + entry["starter"], tiers["star"],
                     tiers["star"] + tiers["starter"], tiers["star"] + tiers["starter"] + tiers["rotation"],
                     f"{st.median(r['overall'] for r in group[:14]):.1f}"])
    return table(["Class", "N", "Entry top-150", "Yr-4 stars", "Yr-4 top-150", "Yr-4 top-300", "Lottery entry OVR median"], rows)


def mix_table(real: dict, gen: dict | None) -> str:
    rows = []
    real_pos = Counter()
    for p in real["game"]["inputs"]["players"]:
        if p["draft_year"] and p["draft_year"] >= 2022 and p["range"] in RANGES:
            real_pos[str(p["position"]).split("/")[0]] += 1
    gen_pos = Counter(str(r["position"]).split("/")[0] for r in gen["inputs"]["rows"]) if gen else Counter()
    rn, gn = sum(real_pos.values()), sum(gen_pos.values())
    for pos in ("PG", "SG", "SF", "PF", "C"):
        rows.append([pos, pct(real_pos[pos], rn), pct(gen_pos[pos], gn)])
    return table(["Primary position", "Real draftees 2022–26 in league", "Generated"], rows)


def groups_table(real: dict, gen: dict | None) -> str:
    keys = ("shooting", "finishing", "creation", "playmaking", "rebounding", "defense", "athletic_tools",
            "strength_tools", "height_cm")
    rows = []
    for label, players in (("real 2026 class", [p for p in real["game"]["inputs"]["players"] if p["draft_year"] == 2026]),
                           ("real 2022 class (after 4)", [p for p in real["game"]["inputs"]["players"] if p["draft_year"] == 2022]),
                           ("real veterans 27+", [p for p in real["game"]["inputs"]["players"] if p["age"] >= 27])):
        rows.append([label, len(players), *[fmt([p["groups"][k] for p in players if p.get("groups") and p["groups"].get(k) is not None]) for k in keys]])
    if gen:
        g = gen["inputs"]["rows"]
        rows.append(["generated entry", len(g), *[fmt([r["groups"][k] for r in g if r["groups"].get(k) is not None]) for k in keys]])
        after = [r for r in g if r.get("groups_after")]
        if after:
            rows.append(["generated after 4", len(after), *[fmt([r["groups_after"][k] for r in after if r["groups_after"].get(k) is not None]) for k in keys]])
    return table(["Group", "N", *keys], rows)


def main() -> None:
    real = json.loads((OUT / "real.json").read_text())
    name = sys.argv[1] if len(sys.argv) > 1 else "generated.json"
    gen = json.loads((OUT / name).read_text()) if (OUT / name).exists() else None
    for mode in ("inputs", "legacy"):
        if gen and mode not in gen:
            continue
        print(f"\n## {mode}: entry by pick range (median, 10th–90th)\n")
        print(entry_table(real, gen, mode))
        print(f"\n## {mode}: OVR path by seasons in league\n")
        print(path_table(real, gen, mode))
        print(f"\n## {mode}: league-rank tiers\n")
        print(tiers_table(real, gen, mode))
        print(f"\n## {mode}: growth over three seasons (league percentile points, survivors)\n")
        print(growth_table(real, gen, mode))
        if gen:
            print(f"\n## {mode}: generated class-to-class variation\n")
            print(gen_class_variation(gen, mode))
    print("\n## Basketball Index year-4 outcomes (2015–2021 classes)\n")
    print(bbi_table(real))
    print("\n## Basketball Index class-to-class variation\n")
    print(bbi_class_variation(real))
    print("\n## Position mix\n")
    print(mix_table(real, gen))
    print("\n## 94-input groups (inputs mode)\n")
    print(groups_table(real, gen))


if __name__ == "__main__":
    main()
