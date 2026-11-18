# Prospect realism: generated draft classes and how they grow

_Branch `claude/prospect-realism` (Claude, overnight 2026-11-18/19). Status: **review**. Not pushed._

**TL;DR**
- In the new 94-input ratings, generated draftees used to never become stars or even starters: by year 4, 0% stars and 0-7% starters at every pick range, because development lost most of its size on the way into the 94 inputs and every rookie had the same low involvement. Now top-10 picks become starters 50-64% of the time, and busts, late bloomers and strong/weak drafts all show up, close to real draft classes.
- Generated classes now look like real ones at the draft: real ages by pick (19 at the top, 22 in round two), a real position mix (centers 17%, was 9%), levels and upside anchored to the real 2026 class, and scouting misses both ways.
- Open: the older (legacy) ratings now make too many young stars from picks 4-30. They do the same to the **real** 2026 rookies, so it is a legacy-scale problem, not a generator one. Top-3 picks in the new ratings still become stars less often than real ones (7% vs about 20-33%).

## 1. What changed (plain language)

1. **Development keeps its size in the new ratings** (`ratings_model.py`). A growth step of one point on a hidden rating used to be *split* across the 5-10 inputs behind it, so a typical input moved about a fifth of a point. Now each input moves by the average step of the ratings that use it, scaled so a one-point gain moves the card overall as much as in the legacy ratings (+0.90 both; was about +0.5). Effect on everyone in the new ratings, healthy one-year forecast:

   | Age | Players | Legacy ratings | New ratings, before | New ratings, after |
   | --- | ---: | --- | --- | --- |
   | 19–22 | 137 | +1.4 | +0.7 | +1.1 |
   | 23–26 | 308 | +0.1 | +0.1 | +0.2 |
   | 27–30 | 148 | −0.5 | −0.3 | −0.4 |
   | 31–33 | 55 | −1.7 | −1.0 | −1.5 |
   | 34–40 | 42 | −3.5 | −1.8 | −3.1 |

   So the new ratings now grow young players and age veterans at about the size the legacy model was tuned for (DEV-TUNE).
2. **Physical tools develop** (speed, agility, strength, balance, vertical, conditioning, recovery). Before, stamina never moved and foot speed barely did in the new ratings, so veterans never lost burst. Height, wingspan, reach and weight stay fixed.
3. **Involvement follows skill.** Real draftees' true usage rises a median +3 to +7 points from year 1 to year 4 (Basketball Index leaderboards, 2013-2022 classes; top-3 picks 35% → 41%). The involvement input now moves 0.0093 per grade point of offensive skill (league cross-section, 567 players with measured usage, r = 0.74), within 5-65%. It falls when skills fade.
4. **Season draw re-measured** (coordinator request). With the compression removed, the 94-input season draw at 0.47 gave −52%..+46% (500+ minutes) and −62%..+52% (1,500+) of the starting spread. **0.28** gives −32%..+28% and −39%..+32%, the same bands main had at 0.47 before this change (targets about −41..+31 and −36..+29). Legacy (0.36) is unchanged.
5. **Generator** (`draft.py`):
   - Slot profile anchored to the real 2026 class as the game rates it: current ability ~62/58 at picks 1/3, 54 at 10, 52 at 20, 51 at 30, 44-47 in round two; public potential 88 → 46. Ages follow real rookie-season ages (2015-2022 classes): 19 / 20 / 20 / 21 / 22 by pick range. Younger at a slot = less now, more upside.
   - Strong and weak drafts: top-end and depth strength shift level and upside (lottery entry median moves 49-55 across classes; year-4 starters per class 6-21).
   - Positions come from the archetype with a realistic split (e.g., stretch bigs are PF 60% / C 40%).
   - **Scouting misses**: true potential = the public board ± 6 (career-capacity model), on top of the old hidden upside tail. The board, the AI and the prospect card still show only the public number (rule 4).
6. **Involvement at entry** (`input_estimator.py`): generated rookies took the same ~25% involvement at every pick. It now comes from the same real-player neighbors as their skills (top picks ~30%, second-rounders ~22%; real rookies 35/28/27/26/24%).
7. **Drafted prospects grow like real young players** (`health.py`): they now get the same youth growth and good/bad seasons as real young players, once they play real minutes (Basketball Index: early gains are tied to opportunity). Before, generated prospects got none of the youth curve and 16% of the season swings, so they grew more slowly and more predictably than real rookies of the same age.

All 94 inputs are kept; nothing clips at 100 beyond the existing 0-100 grade schema; real players' ratings are not touched (only how development is routed).

## 2. Real vs generated (new 94-input ratings, 15 classes × 3 seeds)

Real evidence: the game's own ratings of real draftees (2026 class at entry; 2022 class after 4 seasons; 2023 after 3; top-10 picks 2019-2023), Basketball Index talent and minutes for the 2015-2021 classes, and the Basketball-Reference draft list (who never played). "Star" = top 25 in the league by card overall at neutral minutes, "starter" = top 150, "out" = below 450th or gone.

**Entry by pick range** (median card overall, league rank):

| Picks | Real 2026 class | Generated before | Generated after |
| --- | --- | --- | --- |
| 1-3 | 54.7 (rank 254) | 49.5 (448) | 53.9 (290) |
| 4-10 | 56.6 (200) | 49.0 (476) | 52.3 (351) |
| 11-20 | 50.9 (395) | 48.0 (521) | 49.6 (443) |
| 21-30 | 49.9 (434) | 47.6 (540) | 49.1 (466) |
| 31-60 | 45.5 (582) | 45.5 (582) | 46.0 (573) |

Basketball Index rookie-season offense percentile: picks 1-3 at the 72nd, every other range ~30-36th, so the top three should stand out more than they do (in both the real and generated game ratings).

**Year 4** (star / starter or better / out):

| Picks | Real evidence | Generated before | Generated after |
| --- | --- | --- | --- |
| 1-3 | 20% / 73% / 7% (2019-23 top-3, n=15); BBI offense top-25: 33% | 0 / 7 / 24% | 7 / 64 / 4% |
| 4-10 | 6% / 29% / 23% (2019-23, n=35); BBI starter minutes 27% | 0 / 7 / 34% | 3 / 50 / 6% |
| 11-20 | 5% / 10% / 40-50% (2022-23); BBI starter minutes 17%, no yr-4 season 14% | 0 / 0 / 57% | 1 / 30 / 21% |
| 21-30 | 0% / 0-10% / 30-60%; BBI 11% / 19% | 0 / 0 / 67% | 0 / 16 / 38% |
| 31-60 | 0% / 4-7% / 68%; BBI no yr-4 season 59% | 0 / 0.2 / 80% | 0 / 2 / 76% |

**Growth, rookie year to year 4** (league percentile points, players still in the league; median and 10th-90th):

| Picks | Basketball Index (includes measurement noise) | Generated before | Generated after |
| --- | --- | --- | --- |
| 1-3 | +13 (−14 to +43) | +13 (+4 to +20) | +12 (+5 to +26) |
| 4-10 | +15 (−14 to +58) | +9 (+2 to +16) | +13 (−2 to +32) |
| 11-20 | +20 (−15 to +59) | +6 (+2 to +11) | +12 (−3 to +31) |
| 21-30 | +11 (−13 to +57) | +4 (0 to +8) | +11 (−3 to +24) |
| 31-60 | +17 (−17 to +46) | +3 (0 to +8) | +7 (−3 to +21) |

The generated spread is narrower than Basketball Index's on purpose: the season draw is held at two-thirds of BBI's year-to-year spread (user decision), because part of BBI's spread is measurement noise.

**Position mix** (real draftees 2022-26 / before / after): PG 18 / 26 / 16%, SG 22 / 20 / 24%, SF 26 / 28 / 22%, PF 18 / 16 / 20%, C 16 / 9 / 17%.

**Classes vary**: year-4 starters per generated class 6-21 (real 2022 class: 10; BBI 2015-21 starter-minutes players per class 3-10, starters + rotation 17-28).

**Input groups** (median grade): generated entry and year-4 shooting 46.5 → 47.3, creation 46.8 → 49.2, playmaking 51.4 → 53.5, athletic tools 54.5 → 54.9 (90th pct 57 → 60); real 2026 class at entry: shooting 47.9, creation 46.0, athletic 53.6; real 2022 class after 4: creation 51.1, athletic 54.1.

## 3. Legacy ratings (still the default for new saves)

| Picks | Year-4 star / starter / out, real 2022 class in legacy | Generated before | Generated after |
| --- | --- | --- | --- |
| 1-3 | 33 / 100 / 0% | 16 / 76 / 7% | 40 / 91 / 0% |
| 4-10 | 0 / 57 / 14% | 2 / 51 / 2% | 33 / 84 / 0% |
| 11-20 | 10 / 40 / 20% | 0 / 23 / 13% | 13 / 62 / 2% |
| 21-30 | 0 / 20 / 30% | 0 / 7 / 25% | 5 / 47 / 3% |
| 31-60 | 0 / 4 / 61% | 0 / 1 / 52% | 0 / 8 / 30% |

The legacy ratings are now **too generous** to generated picks 4-30. The same development driver does the same to the real 2026 rookies in legacy (all three top-3 picks, 2 of 7 picks 4-10 and 2 of 10 picks 11-20 become top-25 within four years; all ten picks 21-30 reach the top 150). Legacy rates rookies far above Basketball Index's rookie-season evidence (picks 4-10 at about rank 150-200 vs BBI's ~34th percentile), so faster prospect growth pushes them past real outcomes. A legacy-only fix tried here (lower readiness boost) helped legacy but cost the new ratings, so it is not included. Options for the coordinator: accept (legacy is being retired), or lower legacy rookie levels for real and generated alike with its own evidence.

## 4. Tests

- `tests/test_prospect_realism.py` (10 tests, ~35 s): same seed → identical class; ages by pick; position mix bands; level and upside fall with pick but overlap; scouting misses both ways; strong and weak drafts; four seasons of development in the new ratings: tiers follow pick order, year-4 tiers within evidence bands (wide for the 4-class sample; `PROSPECT_REALISM_FULL=1` runs the 15-class check with tight bands), clear regressions and big jumps both happen, development deterministic.
- `tests/test_ratings_model.py`: new routing (each input moves by its share of all ratings using it; uniform gain moves all inputs equally), physical capacities develop but body dimensions do not, involvement follows skill and respects its bounds.
- Updated on purpose: `test_prospect_learning` pinned monthly references recaptured (prospects get full season draws when playing; 94-input draw 0.28) and two learning comparisons use expected (noise-free) deltas; `test_prospect_public_potential` allows a true potential below the public board.
- Focused run (draft, prospects, development, ratings model, estimator, talent, health): see the final report for the result. Core tests: see final report.
- Not run: both scorecards. Opening-day scorecards are unaffected (no opening rating changes); the routing and season-draw changes only act after development runs, so an aged-roster scorecard check is still needed before making the new ratings the default.

## 5. Caveats

- Real samples in game units are small (3 top-3 picks per class). Basketball Index's outcome measure here is offensive talent (its defensive/overall series cover mostly current players).
- The real 2026 class's game ratings are themselves estimates (PRO-2). Generated levels are anchored to them, so a PRO-2 change should be followed by a re-run.
- Generated rookies still carry generator archetype names as their role (e.g. "lead_creator"), not Basketball Index role names.
- The measurement holds the league fixed (no other players develop) and sets minutes from league rank each July instead of simulating coaches.

## 6. What NCAA data would add

College production and age-adjusted stats per prospect would let the generator set each skill from evidence (free-throw and three-point shooting, steal/block rates, assist and usage rates) instead of a slot profile; real college-to-NBA pairs would size the scouting miss and the top-3 gap directly; combine measurements would ground physical tools; and multi-year college growth would separate young risers from finished seniors.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/research/prospect_realism.py real          # needs output/prospect-realism/real_drafts_2013_2023.csv (local)
PYTHONPATH=src .venv/bin/python scripts/research/prospect_realism.py generated --out generated_after.json
PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_report.py generated_after.json
PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_routing.py
PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_veterans.py
```

Row-level outputs, the Basketball-Reference list and the season-draw measurement copy are in the ignored `output/prospect-realism/`.

## Resume state

Done: measurement, routing fix, generator, involvement, prospect growth, merge of the coordinator's development review, season draw re-measured (0.28), tests. Remaining for the coordinator: review, scorecards on aged rosters, decision on legacy over-generosity and the top-3 gap.
