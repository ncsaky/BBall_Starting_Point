# INJURY-NAMES: injury names agree with how long players are out

Progress: 7/7 - done, ready for review

## Summary (plain language)

- An injury now picks its **name first, then a length from that injury's own real records**, so the two agree.
- A simulated season costs about the **same number of injuries and games** as before (season one: injuries up 1%, games
  lost down 0.6%). By the third season games lost are about 6% lower, because the strange very long absences no longer
  carry over.
- Side effect to know about: **ACL and Achilles tears happen more often** (about 6 a season, was about 4), so slightly
  more players take a permanent decline after an injury (about 15 per 1,600 injuries, was 12). No ratings data changed.

## What was wrong (both suspected causes confirmed, plus two)

1. A record cut off by the end of a season took the typical length of longer cases **anywhere in the same body part**.
   Most knee injuries are minor, so an ACL tear in a season's last week became a couple of weeks.
2. The length came from the whole body part and the name from a **broad length bucket**, so a long draw could be called
   a contusion.
3. The top 2.5% of each body part's curve stretched evenly up to the **longest absence on record** (knee: 601 days).
4. "Games missed" was always days divided by two, **even across a summer**, so a long absence reported up to 300 games.

## What changed

- Each diagnosis has its own share of injuries and its own lengths. A cut-off record now counts toward longer cases of
  the **same** diagnosis only.
- Each kind of diagnosis has limits: knocks, soreness and "ankle injury" type names at most 20 games, illness 15,
  sprains and strains 50, other tears at least 10, surgery at least 7, and ACL tears and Achilles ruptures at least 180
  days of the basketball calendar (most of a season). Nothing lasts past 381 days. A diagnosis with fewer than 3 cases
  that have a recorded return uses the same kind of injury in the same area of the body. Limits live in
  `scripts/build_injury_model.py` (`KIND_DAYS`).
- An absence that runs into a later season reports the games the player can actually miss.
- News reads naturally: "with an ankle injury", "with back spasms", "recovering from knee surgery". No more
  "(unspecified)".
- Season-start injuries are named to fit their length.
- `data/canonical/injury_model_v2.json` rebuilt with the build script (it reproduced the old file exactly before the
  change). Injury rates are unchanged apart from the small automatic re-fit that goes with the new lengths.

## Games shown, before and after (typical, with 5th to 95th percentile)

| Injury | Before | After |
|---|---|---|
| ACL tear | 107 (6 to 282) | 89 (45 to 132) |
| Achilles tendon rupture | 110 (1 to 147) | 91 (57 to 105) |
| Meniscus tear | 36 (15 to 257) | 45 (18 to 114) |
| Knee surgery | 26 (1 to 239) | 45 (13 to 108) |
| Foot fracture | 43 (16 to 185) | 43 (18 to 90) |
| Hand fracture | 18 (7 to 30) | 18 (10 to 30) |
| Ankle sprain | 2 (longest 185) | 2 (longest 47) |
| Back contusion | 2 (longest 204) | 1 (longest 7) |
| Shin contusion | 4 (longest 60) | 2 (longest 11) |
| Unspecified ankle injury | 1 (longest 184) | 1 (longest 20) |

## Season totals, before and after

Ten seeded runs of three seasons back to back (injuries only, fixed rosters), same seeds on both versions.

| Per season | Season 1 | Season 2 | Season 3 |
|---|---|---|---|
| Injuries | 1,585 to 1,598 | 1,568 to 1,618 | 1,581 to 1,652 |
| Games missed | 6,470 to 6,433 | 7,484 to 7,099 | 7,831 to 7,342 |
| 40+ game injuries | 43.8 to 35.5 | 47.1 to 36.8 | 50.6 to 37.0 |
| ... of those with a minor-sounding name | 14.5 to 0 | 16 to 0 | 19.6 to 0 |
| Serious name, under 5 games | 3.8 to 0 | 4.4 to 0 | 4.2 to 0.1 |
| ACL and Achilles tears | 4.4 to 5.6 | 4.4 to 5.8 | 3.4 to 6.6 |
| Back after November 1 of the next season | 18.2 to 14.4 | 20.9 to 14.9 | 21.0 to 17.4 |
| Longest games figure shown | 263 to 131 | 266 to 128 | 271 to 127 |

**Against real records** (complete public injury reports, 2023-24 to 2025-26): counting only the first 40 games of each
absence, an injury costs 5.02 games in real life, 5.19 in the old model and 5.04 now (first 60 games: 5.53 real, 5.75
old, 5.48 now). The mix of short and long absences still matches the records, as closely as before or closer.

**Tears:** the new rate is the injury tracker's own share; the old one was low because cut-off tears were being turned
into short injuries. A rough name search of the complete records finds 2, 14 and 6 new ACL and Achilles tears in the
three seasons.

## Still true

- About 14 players a season are still out past November 1 of the next season, and about 9 do not return until the
  following calendar year. These are now surgeries and major tears with lengths from real records.
- A few surgery names can still run into the next season (wrist surgery especially), because that is what their small
  real samples show.

## Checks

- New tests: `tests/test_injury_names.py`. Updated: `tests/test_injury_anchor.py` (checks the drawn mix against the real
  records), `tests/test_injuries_2.py` (new file layout). All injury test modules and the related save tests pass.
- Full suite on the Azure pool: 2,624 Python tests, 35 skipped, 15 failures or errors. All 15 fail the same way on the
  unchanged parent commit `9ec8eaad` (packaging, two screen-style checks, thin-sample rating and experimental-engine
  tests), so none come from this change. The browser tests were not part of the run.
- Not run: the betting-odds test and the real-stat scorecard (season-one games missed are essentially unchanged).
- Not checked by eye in the browser.
- Old saves keep their existing injuries; only new draws use the new model.

Measure again with:

```bash
PYTHONPATH=src .venv/bin/python scripts/research/injury_diagnosis_check.py --draws 100000 --seasons 10 --years 3 --labels
```

Raw before/after output: `output/injury-names/`.

## Resume state

Code, model, report and full test run done on branch `claude/loving-chatelet-4c6b58`. Ready for review and merge.
