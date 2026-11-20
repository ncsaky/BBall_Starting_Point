"""Draft-night check without a season: new saves moved to the 2027 draft date, whole draft simulated with AI trades.

For each seed: the number of draft-night trades, and for each trade whether the buyer drafted the prospect it traded
up for, his consensus rank and the pick. The season is skipped (records 0-0, preseason rosters), so the draft order
comes from projected standings; this checks the draft machinery, not a season's results.

usage: PYTHONPATH=src python scripts/research/draft_night_trades_check.py SAVE_DIR [seed ...]
"""
import re
import sys
import time
from pathlib import Path

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import create_league_save, load_save, write_save

save_dir = Path(sys.argv[1])
seeds = [int(s) for s in sys.argv[2:]] or [17, 23, 31]
save_dir.mkdir(parents=True, exist_ok=True)
canonical = load_app_canonical(Path("."))
totals = {"trades": 0, "got_target": 0}
for seed in seeds:
    path = save_dir / f"trades_{seed}.json"
    save = create_league_save(Path("."), canonical, "GSW", path, seed=seed)
    save["state"].update(current_date="2027-06-26", phase="draft", legal_actions=["trades", "draft_picks"])
    write_save(path, save)
    payload = {"save_path": str(path), "team": "GSW", "year": "2027", "seed": seed}
    started = time.time()
    dispatch_app_action("draft_room", payload, save_dir=save_dir)
    dispatch_app_action("draft_sim_all", payload, save_dir=save_dir)
    seconds = time.time() - started
    done = load_save(path)
    pending = done["draft_state"]["draft"]["pending_draft_selections"]
    by_pick = {int(p["selection"]["overall_pick"]): p for p in pending}
    reasons = [log.get("trade_reasons") for log in done.get("transaction_logs", [])
               if log.get("transaction_type") == "trade" and (log.get("trade_reasons") or {}).get("target_key") == "draft_prospect"]
    print(f"seed {seed}: {len(reasons)} draft-night trades, draft took {seconds:.0f} s")
    for reason in reasons:
        text = reason.get("text") or ""
        match = re.search(r"traded up to pick (\d+) for (.+?), number (\d+) on its draft board", text)
        if not match:
            print("   ", text)
            continue
        pick, target, board_rank = int(match.group(1)), match.group(2), int(match.group(3))
        taken = by_pick.get(pick) or {}
        drafted = (taken.get("prospect") or {}).get("name")
        got = drafted == target
        totals["trades"] += 1
        totals["got_target"] += got
        print(f"    pick {pick}: wanted {target} (its board #{board_rank}); drafted {drafted}"
              f" {'(target)' if got else '(not the target)'} | {(taken.get('decision') or {}).get('notes')}")
print("total", totals)
