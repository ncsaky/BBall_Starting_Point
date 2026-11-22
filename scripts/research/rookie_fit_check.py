#!/usr/bin/env python3
"""ROOKIE-FIT checks: how the game rates rookies (display overall, impact, ranks) and a 2025-class back-test.

  # every rostered player's display overall / impact with the current inputs file -> JSON (before/after tables)
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit_check.py snapshot output/rookie-fit/after.json

  # 2026 class table: before vs after snapshots, with each rookie's college line and projection
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit_check.py table output/rookie-fit/before.json output/rookie-fit/after.json

  # 2025 class back-test: rebuild the 2025 rookies' technique as of their draft (old slot-based method and the
  # college method, from a fit on drafts 2009-2024 only), then compare the game's rating with their real rookie year
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit.py --backtest-2025
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit_check.py backtest output/rookie-fit/rookie_translation_2025_backtest.json
"""
from __future__ import annotations

import copy
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import real_prospects as rp  # noqa: E402
from nba_gm_data import ratings_model  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.impact_value import player_impact  # noqa: E402
from nba_gm_data.input_estimator import DEFINITIONS, InputEstimator, load_rookie_college  # noqa: E402
from nba_gm_data.player_profile import engine_header  # noqa: E402

BUNDLE = ROOT / "data/research/rookie_translation_2026.json"
LEBRON_CSV = ROOT / "data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv"
TECHNIQUE = tuple(iid for iid, d in DEFINITIONS.items() if d["kind"] == "grade")


def snapshot(overrides: dict[str, dict] | None = None) -> list[dict]:
    """Display overall / impact for every rostered player; overrides = {player_id: {input_id: record}}."""
    if overrides:
        key, league = ratings_model._load_inputs_keyed(ROOT)
        patched = dict(league)
        for pid, records in overrides.items():
            patched[pid] = {**league[pid], **records}
        ratings_model._INPUT_CACHE[key] = patched
    ratings_model._FITTED_CACHE.clear()   # league tables refitted on these inputs, as a new save would
    canonical = load_app_canonical(ROOT)
    ratings_model.install_inputs_model(canonical, ROOT)
    rows = []
    for p in canonical["players"]:
        if not p.get("team_abbrev"):
            continue
        head = engine_header(canonical, p["id"])
        imp = player_impact(canonical, p)
        if head and imp:
            rows.append({"id": p["id"], "name": p["name"], "team": p["team_abbrev"], "draft_year": str(p.get("draft_year")),
                         "pick": p.get("draft_position"), "age": p.get("age"), "ovr": head["ovr"], "off": head["off"],
                         "def": head["def"], "impact": round(imp["overall"], 3), "impact_off": round(imp["offense"], 3),
                         "impact_def": round(imp["defense"], 3)})
    rows.sort(key=lambda r: -r["ovr"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    if overrides:
        ratings_model._INPUT_CACHE.pop(key, None)
    return rows


def class_rows(rows: list[dict], year: str) -> dict[str, dict]:
    rookies = [r for r in rows if r["draft_year"] == year]
    for i, r in enumerate(rookies, 1):
        r["class_rank"] = i
    return {r["id"]: r for r in rookies}


def table(before_path: str, after_path: str) -> None:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))["class_2026"]
    before = class_rows(json.loads(Path(before_path).read_text()), "2026")
    after = class_rows(json.loads(Path(after_path).read_text()), "2026")
    print("| Rookie | Pick | Age | College line (team, BPM off/def, usage, TS%, 3P%, FT%) | Projected rookie impact "
          "(off / def) | Overall before → after | Rookie rank before → after | League rank before → after |")
    print("|---|---:|---:|---|---:|---:|---:|---:|")
    for pid, a in sorted(after.items(), key=lambda kv: kv[1]["class_rank"]):
        b = before.get(pid, {})
        e = bundle.get(pid)
        if e:
            c, pr = e["college"], e["projection"]
            line = (f"{c['team']} {c['class']}, {c['bpm']:+.1f} ({c['obpm']:+.1f}/{c['dbpm']:+.1f}), usg {c['usg']:.0f}, "
                    f"TS {c['ts']:.0f}, 3P {100 * c['three_pct']:.0f}% on {c['three_per40']:.1f}/40, FT {100 * c['ft_pct']:.0f}%")
            proj = f"{pr['lebron']:+.2f} ({pr['o']:+.2f} / {pr['d']:+.2f})"
        else:
            line, proj = "no college season (kept the earlier method)", "—"
        print(f"| {a['name']} | {a['pick']} | {a['age']:.0f} | {line} | {proj} | {b.get('ovr', float('nan')):.1f} → "
              f"{a['ovr']:.1f} | {b.get('class_rank', '—')} → {a['class_rank']} | {b.get('rank', '—')} → {a['rank']} |")


def table3(old_path: str, first_path: str, new_path: str) -> None:
    """ROOKIE-FIT-2: the 2026 class under the old method, the first attempt and the new ability level."""
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))["class_2026"]
    snaps = [class_rows(json.loads(Path(p).read_text()), "2026") for p in (old_path, first_path, new_path)]
    old, first, new = snaps
    print("| Rookie | Pick | Age | College fit (off / def) | Readiness | This season so far (min, per 36 pts, box +/-) "
          "| Day-one ability (off / def) | Overall: old → first try → new | Rookie rank | League rank |")
    print("|---|---:|---:|---:|---|---|---:|---:|---:|---:|")
    for pid, a in sorted(new.items(), key=lambda kv: kv[1]["class_rank"]):
        e = bundle.get(pid)
        if e:
            parts, pr = e["projection_parts"], e["projection"]
            fit = f"{parts['college_fit']['o']:+.2f} / {parts['college_fit']['d']:+.2f}"
            tier = parts["readiness"]["tier"].replace("_", " ")
            g = parts["early_games"]
            games = (f"{g['minutes']:.0f} min, {g['pts_per36']:.1f}, {g['bpm']:+.1f} (moved {g['o'] + g['d']:+.2f})"
                     if g.get("minutes") else "—")
            proj = f"{pr['lebron']:+.2f} ({pr['o']:+.2f} / {pr['d']:+.2f})"
        else:
            fit, tier, games, proj = "no college season", "—", "—", "earlier method"
        ovr = " → ".join(f"{s[pid]['ovr']:.1f}" if pid in s else "—" for s in snaps)
        rk = " → ".join(str(s[pid]["class_rank"]) if pid in s else "—" for s in snaps)
        lg = " → ".join(str(s[pid]["rank"]) if pid in s else "—" for s in snaps)
        print(f"| {a['name']} | {a['pick']} | {a['age']:.0f} | {fit} | {tier} | {games} | {proj} | {ovr} | {rk} | {lg} |")
    ovrs = [r["ovr"] for r in new.values()]
    print(f"\nnew class overall range {min(ovrs):.1f}-{max(ovrs):.1f}, sd {statistics.pstdev(ovrs):.2f}; first try "
          f"{min(r['ovr'] for r in first.values()):.1f}-{max(r['ovr'] for r in first.values()):.1f}, sd "
          f"{statistics.pstdev([r['ovr'] for r in first.values()]):.2f}; old {min(r['ovr'] for r in old.values()):.1f}-"
          f"{max(r['ovr'] for r in old.values()):.1f}, sd {statistics.pstdev([r['ovr'] for r in old.values()]):.2f}")


def rookie_lebron(season: str) -> dict[str, dict]:
    out = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["Season"] == season:
                out[rp.name_key(row["Player"])] = row
    dev = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]["seasons"]
    minutes = {rp.name_key(r[2]): r[4] for r in dev if str(r[0]) == season}
    return {k: {"lebron": float(v["LEBRON"]), "o": float(v["O-LEBRON"]), "d": float(v["D-LEBRON"]),
                "minutes": minutes.get(k, 0)} for k, v in out.items()}


def corr(xs, ys):
    return round(statistics.correlation(xs, ys), 3) if len(xs) > 2 else None


def backtest(bundle_path: str) -> None:
    """2025 rookies rated as of their draft: old (slot-based traits) vs college method, against the real rookie year."""
    est = InputEstimator.from_local(ROOT)
    college = load_rookie_college(ROOT, path=Path(bundle_path))
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    old, new = {}, {}
    for pid, entry in college.items():
        player = copy.deepcopy(players[pid])
        a = est.estimate_player_inputs(player, prospect=True).to_dict()["inputs"]
        b = est.estimate_player_inputs(player, prospect=True, college=entry).to_dict()["inputs"]
        old[pid] = {iid: a[iid] for iid in TECHNIQUE}
        new[pid] = {iid: b[iid] for iid in TECHNIQUE}
    # The college method's level step, exactly as the builder runs it for the 2026 class.
    from scripts.build_player_inputs import level_rookies
    _, league = ratings_model._load_inputs_keyed(ROOT)
    section = {"players": {pid: {"inputs": {**records, **new.get(pid, {})}} for pid, records in league.items()}}
    level = level_rookies(section, college, ROOT)
    print("level step:", json.dumps(level))
    new = {pid: {iid: section["players"][pid]["inputs"][iid] for iid in TECHNIQUE} for pid in college}
    ratings_model._INPUT_CACHE.clear()
    real = rookie_lebron("2026")
    now = {r["id"]: r for r in snapshot()}
    results = {"old": {r["id"]: r for r in snapshot(old)}, "new": {r["id"]: r for r in snapshot(new)}}
    rows = []
    for pid, entry in college.items():
        k = rp.name_key(entry["name"])
        if k not in real or pid not in now:
            continue
        rows.append({"name": entry["name"], "pick": players[pid].get("draft_position"), "real": real[k]["lebron"],
                     "minutes": real[k]["minutes"], "projection": entry["projection"]["lebron"],
                     "old": results["old"][pid]["impact"], "new": results["new"][pid]["impact"],
                     "old_ovr": results["old"][pid]["ovr"], "new_ovr": results["new"][pid]["ovr"],
                     "now": now[pid]["impact"], "now_ovr": now[pid]["ovr"]})
    played = [r for r in rows if r["minutes"] >= 500]
    print(f"2025 rookies with a college season: {len(college)}; with a real rookie year in the data: {len(rows)}; "
          f"500+ minutes: {len(played)}")
    for label, sel in (("500+ minutes", played), ("all with a LEBRON", rows)):
        real_v = [r["real"] for r in sel]
        print(f"  {label}: correlation with real rookie impact  slot-based (old) {corr([r['old'] for r in sel], real_v)}"
              f"  college method {corr([r['new'] for r in sel], real_v)}  projection itself "
              f"{corr([r['projection'] for r in sel], real_v)}  draft slot {corr([-__import__('math').log(r['pick'] or 60) for r in sel], real_v)}")
        print(f"    Spearman: old {round(rp.spearman([r['old'] for r in sel], real_v), 3)}  new "
              f"{round(rp.spearman([r['new'] for r in sel], real_v), 3)}")
    print("| Rookie | Pick | Real rookie impact (min) | Projection | Game impact as of draft: old → college method | "
          "Overall old → college | Game today (with his NBA season) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for r in sorted(rows, key=lambda r: r["pick"] or 99):
        print(f"| {r['name']} | {r['pick']} | {r['real']:+.2f} ({r['minutes']:.0f}) | {r['projection']:+.2f} | "
              f"{r['old']:+.2f} → {r['new']:+.2f} | {r['old_ovr']:.1f} → {r['new_ovr']:.1f} | {r['now']:+.2f} ({r['now_ovr']:.1f}) |")
    Path(ROOT / "output/rookie-fit/backtest_2025.json").write_text(json.dumps(rows, indent=1))


def main() -> None:
    command = sys.argv[1]
    if command == "snapshot":
        Path(sys.argv[2]).write_text(json.dumps(snapshot(), indent=0))
    elif command == "table":
        table(sys.argv[2], sys.argv[3])
    elif command == "table3":
        table3(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "backtest":
        backtest(sys.argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
