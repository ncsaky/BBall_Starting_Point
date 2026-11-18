# Career save size

**Box scores and their game logs take up most of the space.** The copied career had reached July 3, 2036, with ten completed playing seasons. It used **650 MiB** on disk and took about **82 MiB** to ZIP. The normal exporter rejected it at the **512 MiB expanded limit**. A separate **128 MiB ZIP limit** also applies.

**I’d keep every box score and make full exports work first.** A bounded, streamed export and import can keep the career intact. To make ordinary saves faster, separate the backup work from the export decision. If the priority is a smaller file to share, offer a second export with two seasons of detailed games and the rest of the career summarized.

**Career totals are already stored.** The player’s career stat strip, old team records, and past award winners can survive a smaller export. Older box scores and some injury and player-card detail would need to come from a full copy of the career.

## Options for the decision

Sizes are **expanded / ZIP, in MiB**. Ten-season sizes are measured and twenty-season sizes are projections. The current caps are **512 / 128** and both must pass.

| Option | 10 seasons | 20 seasons | What the player loses | Implementation size |
|---|---:|---:|---|---|
| Full export with higher limits | 650 / 82 | ~1,297 / 163 | Nothing. A 2 GiB expanded and 256 MiB ZIP budget would cover this projection. | Small for limit changes alone. Medium for streaming import/export and verifying both GUI and CLI round trips. |
| Keep only the latest copy of each record | 593 / 72 | ~1,181 / 144 | No current career history. An older recovery snapshot must hold its own copy. Still exceeds the 512 MiB limit at ten seasons. | Medium. Stop repeat inserts, rebuild compactly and test interrupted saves. |
| Compress each latest record separately | 346 / 159 | ~684 / 321 | Nothing. Compressing each row strips out repetition that the existing ZIP would otherwise use. This version fails the ZIP limit even at ten seasons. | Medium. Update payload encoding, readers, validation and recovery. |
| Keep detailed games for two seasons plus all existing season totals | 245 / 25 | ~399 / 38 | Old individual boxes and game-by-game splits. Sparse player cards and old injury-minute details need replacements to preserve what they show. | Medium to large. Write compact snapshots, preserve recent lookups, and handle older box requests in the UI. |
| Compact share export alongside an optional full archive | 163 / 18 portable | ~214 / 22 portable | On the compact copy, the same older game details plus older monthly development notes and inbox headlines. The full archive retains those details. | Large. Two export flavors, a consistent optional attachment, and round-trip and recovery tests. |

The full archive can start as a separate complete career export. With only the latest version of each record it is about **593 / 72** at ten seasons and **1,181 / 144** at twenty. Reattaching an older-history-only file would require a versioned link to the exact career and a way to reject mismatched archives. The portable-only variants fit both caps in this projection. The local save only gets faster if its storage or backup process also changes.

For the projections, I rebuilt the older eight seasons of each variant separately, including their indexes, and used a year’s share of that size for each additional season. The full baseline also adds the observed average cost of older versions and the original page layout. The JSON adds about 3.14 MiB per year from season-attributed history, with ZIP growth estimated using its observed compression ratio. Holding the same workload, the eight-season expanded baseline is about **521 MiB**. The writer mix, future JSON growth, and recovery overhead can change the actual cutoff. The two-season variants hold the recent game detail window fixed.

The two detail-cutting estimates include the existing JSON and its career totals, scores, schedules, injuries, deals, awards and other live state. The prototypes remove history rows only. They do not add a substitute for older injury-minute charts or sparse player-card game logs. Before shipping that option, either keep a slim per-injury snapshot and a player’s last 30 games outside the window, or clearly show that the detail is unavailable. If old playoff season tables are part of the product decision, capture playoff totals by season before removing boxes. The present rollover snapshot carries regular-season player totals and playoff brackets. The checkpoint’s playoff stat counters are cumulative, with game IDs from multiple years.

For local save speed, `write_save` preserves a complete previous backup before publishing each new save. The backup copies SQLite, validates the copy, hashes both files and ZIPs them. `validate_save_components` caches a successful check for an unchanged file and revision. On a cache miss it runs SQLite’s `quick_check`, checks visible counts and validates JSON across committed rows. In the audit process that check alone took about 6 seconds. The writer also inventories visible keys when recording a new checkpoint. Raising export limits leaves that work in place. A separate local improvement could retain a recoverable previous revision with a checked checkpoint and avoid copying and recompressing the entire career on every save. That is a medium-to-large change that needs interrupted-write and restore tests. The import limit change also needs the HTTP upload ceiling and the current in-memory ZIP and base64 paths reviewed together.

## What takes up space

The database file was **604.22 MiB**, and the JSON was **46.06 MiB**. The eight database collections account for **391.84 MiB of stored JSON text** inside SQLite, including older versions. The rest is largely the five indexes (**98.59 MiB**) and the row keys, page overhead and unused space in the records table (about **113.69 MiB** together). The SQLite file averaged **60.42 MiB per completed playing season** at this point. The tables below separate the payloads from shared file overhead and show the JSON separately so the numbers can be added without double counting.

The **193.18 MiB of full boxes** contains **101.09 MiB of player lines**, **34.25 MiB of team lines**, and **50.94 MiB of plus/minus tracking**. The tracking includes **41.02 MiB of modeled lineup stretches** with score changes. The normal writer does not persist a shot-by-shot or possession-by-possession feed. `possessions` in a box is a number, and the measured boxes have zero stored `scoring_events`. Dropping play-by-play after a set number of seasons saves **0 MiB** here. Dropping just the old modeled lineup stretches would save roughly **4.1 MiB of payload per affected season** before page effects. That would keep displayed player plus/minus and ordinary boxes, but remove the lineup intervals from the box response and from analysis. I found the tracking field in the box-score response and no corresponding browser renderer.

**Older copies of transactions are real disk usage.** The checkpoint contains 26,621 transaction rows for 4,855 visible records. The 21,766 older versions take **32.01 MiB of payload**. Some paths read archived transactions back into the save for draft checks. The archive writer will insert eligible rows it receives at the new revision, even if their contents match an earlier copy. A latest-only rebuild with the same indexes reclaimed **57.77 MiB** across payload, pages and indexes. Do this as a verified snapshot rebuild or checkpoint maintenance step. The previous manifest must still have its corresponding history if a save stops partway through.

### SQLite payload by season (MiB)

| Collection | 2026–27 | 2027–28 | 2028–29 | 2029–30 | 2030–31 | 2031–32 | 2032–33 | 2033–34 | 2034–35 | 2035–36 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `game_results` | 19.16 | 19.17 | 19.34 | 19.06 | 19.42 | 19.40 | 19.47 | 19.43 | 19.40 | 19.33 | 193.18 |
| `player_game_logs` | 8.90 | 8.93 | 9.00 | 8.95 | 9.09 | 9.07 | 9.06 | 9.16 | 9.16 | 9.21 | 90.52 |
| `development_events` | 4.49 | 5.80 | 5.68 | 5.95 | 6.01 | 6.29 | 6.41 | 6.57 | 6.73 | 0.50 | 54.43 |
| `transaction_logs` | 3.71 | 5.27 | 6.59 | 6.09 | 4.65 | 4.86 | 3.49 | 2.91 | 1.72 | — | 39.30 |
| `team_game_logs` | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | — | 8.53 |
| `news_items` | 0.23 | 0.25 | 0.28 | 0.30 | 0.27 | 0.32 | 0.29 | 0.30 | 0.28 | — | 2.52 |
| `league_events` | 0.10 | 0.20 | 0.29 | 0.30 | 0.30 | 0.34 | 0.32 | 0.32 | 0.30 | — | 2.46 |
| `social_feed` | 0.05 | 0.09 | 0.11 | 0.11 | 0.12 | 0.13 | 0.11 | 0.11 | 0.07 | — | 0.90 |
| **Total** | 37.59 | 40.66 | 42.24 | 41.70 | 40.81 | 41.36 | 40.09 | 39.75 | 38.61 | 29.04 | 391.84 |

Games account for **292.23 MiB** across full boxes, player game logs and team game logs, about **75%** of the stored record text. Game dates came from the JSON score index, with the playoff game ID’s year as a fallback for the 867 date-less summaries. Other records use an explicit season where present, then the July-to-June date window. The DB `season` column sometimes contains a day or month string and was not grouped verbatim. The transaction column includes superseded rows. Its visible payload by season is 0.38, 0.60, 0.84, 0.89, 0.80, 1.00, 0.90, 1.02, 0.86 and 0.00 MiB, totaling 7.29 MiB. All other collections had one stored revision per visible record. The 2035–36 column is low because rollover had not yet moved its current team logs and most narrative, development and transaction rows out of the save JSON.

### Save JSON by season (MiB)

| Collection | 2026–27 | 2027–28 | 2028–29 | 2029–30 | 2030–31 | 2031–32 | 2032–33 | 2033–34 | 2034–35 | 2035–36 | Other¹ | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `season_history` | 0.85 | 0.86 | 0.86 | 0.85 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | — | 0.00 | 7.71 |
| `development_events` | — | — | — | — | — | — | — | — | — | 6.15 | 0.59 | 6.74 |
| `generated_traits` | 0.58 | 0.58 | 0.57 | 0.57 | 0.57 | 0.57 | 0.57 | 0.58 | 0.58 | 0.58 | 0.00 | 5.74 |
| `injury_events` | 0.32 | 0.32 | 0.32 | 0.32 | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 | 0.00 | 3.26 |
| `season_schedules` | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.00 | 2.72 |
| `waiver_wire` | 0.12 | 0.14 | 0.19 | 0.27 | 0.14 | 0.34 | 0.27 | 0.27 | 0.27 | 0.30 | 0.00 | 2.32 |
| `game_result_summaries` | 0.22 | 0.22 | 0.22 | 0.21 | 0.22 | 0.22 | 0.22 | 0.22 | 0.22 | 0.21 | 0.00 | 2.15 |
| `playoff_player_stats` | 0.15 | 0.15 | 0.16 | 0.14 | 0.16 | 0.17 | 0.17 | 0.16 | 0.16 | 0.16 | 0.18 | 1.76 |
| `transaction_logs` | — | — | — | — | — | — | — | — | 0.12 | 1.06 | 0.10 | 1.29 |
| `waived_salary_obligations` | 0.05 | 0.06 | 0.08 | 0.12 | 0.06 | 0.14 | 0.11 | 0.12 | 0.11 | 0.12 | 0.00 | 0.97 |
| `team_game_logs` | — | — | — | — | — | — | — | — | — | 0.95 | 0.00 | 0.95 |
| `pending_staff_negotiations` | — | 0.01 | 0.14 | 0.11 | 0.17 | 0.08 | 0.12 | 0.07 | 0.13 | 0.06 | 0.00 | 0.90 |
| `player_season_stats` | — | — | — | — | — | — | — | — | — | 0.79 | — | 0.79 |
| `contract_overrides` | — | — | — | — | — | — | — | — | — | — | 0.69 | 0.69 |
| `draft_state` | — | — | — | — | — | — | — | — | — | — | 0.64 | 0.64 |
| `incoming_rookies` | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.00 | 0.63 |
| `generated_players` | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.00 | 0.58 |
| `award_preseason_baselines` | 0.05 | 0.05 | 0.05 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 | 0.00 | 0.55 |
| `rookie_contracts` | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.00 | 0.46 |
| `development_trait_totals` | — | — | — | — | — | — | — | — | — | — | 0.44 | 0.44 |
| `health_states` | — | — | — | — | — | — | — | — | — | — | 0.43 | 0.43 |
| `league_events` | — | — | — | — | — | — | — | — | 0.04 | 0.33 | 0.04 | 0.41 |
| `news_items` | — | — | — | — | — | — | — | — | 0.02 | 0.30 | 0.01 | 0.33 |
| `draft_rights` | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.00 | 0.30 |
| `draft_orders` | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.00 | 0.28 |
| `social_feed` | — | — | — | — | — | — | — | — | 0.05 | 0.12 | 0.02 | 0.19 |
| `game_results` | — | — | — | — | — | — | — | — | — | — | 0.15 | 0.15 |
| `player_game_logs` | — | — | — | — | — | — | — | — | — | — | 0.00 | 0.00 |
| `Other sections` | 0.10 | 0.06 | 0.05 | 0.07 | 0.06 | 0.07 | 0.07 | 0.07 | 0.07 | 0.53 | 1.55 | 2.69 |
| **Total** | 2.93 | 2.94 | 3.14 | 3.22 | 3.12 | 3.31 | 3.27 | 3.22 | 3.51 | 12.55 | 4.85 | 46.06 |

¹ Other includes undated state, rows assigned outside the ten played seasons, and collection overhead. The active season column also carries current aggregate state such as team records. Cumulative playoff stats are assigned by game ID where possible, with the shared counters under Other. Rookie records are assigned to their draft class, under the season ending in that draft year. The last draft class is smaller because it was still processing. Within `season_history`, **7.09 MiB** is player season stats, **0.29 MiB** playoff state, and **0.25 MiB** draft order. This checkpoint uses the legacy traits model. Careers storing the newer 94-input player model can have a different JSON footprint. [The byte-level inventory](../../../output/sav/measurements.json) lists every top-level field and the box-score subfields.

## Which screens and rules read the history

| Data | What reads it and what to preserve |
|---|---|
| Full boxes (`game_results`) | The browser box-score modal and CLI `box-score` request a full game by ID, including archived games. Recent player-card rows, results, and playoff series offer ways to open boxes in the browser. Calendar, score lookups and playoff progression can use score summaries. Live games also use the full result as they record stats, play-in outcomes, and highlights. Once a season closes, the reason to retain those old boxes is game-level lookup and analysis. Keep the recent/current boxes for active views. |
| Player game logs (`player_game_logs`) | The player card reads up to 30 across seasons for its form chart and last-game table. A sparse player can reach farther back than two seasons. The award race reconstructs prior-week candidate ranks from **current-season** logs. The team efficiency panel’s injury events currently scan all archived player logs to recover the games before an injury, replacement minutes, and the return date. Season totals cannot recover these. |
| Team game logs (`team_game_logs`) | Live opponent scouting, team stats and weekly efficiencies, prior-week award ranks, coach evaluation, and recent narrative and lifecycle calculations query the current JSON. `materialize_game_summaries` uses the dates when archiving. The old database rows have no dedicated production reader. The social screen indirectly loads them through the full-history loader, and audits can load them too. |
| Development (`development_events`) | The player and team development charts and staff evaluation read recent or current events. Ratings are rebuilt from cumulative `development_trait_totals` plus current rows. Archived monthly explanations and staff/health context are useful for audits. Normal career advancement does not need the old individual rows to rebuild ratings. Preserve the cumulative totals exactly and avoid reapplying archived deltas when importing a slim save. |
| Transactions (`transaction_logs`) | Current rows inform trade eligibility (recent trades, signings and waiver claims), AI trade context, player-card team arrival and staff timeline. Draft application explicitly reads historical transactions for draft selection consumption and also uses saved draft rights, picks and rookie contracts. There is a missing-staff-counter rebuild on load using archived deals and league events. Keep each visible deal, or prove that compact facts reproduce those checks before dropping detail. |
| League activity (`league_events`) | League Activity, transaction and signing feeds can load old archived events, filter and sort before limiting the display. Older events can appear in sparse filtered views even if the default page is recent. The staff-counter rebuild reads them too. |
| News (`news_items`) | The home inbox, CLI briefing, narrative and season review read a current or recent slice in JSON. Archived news has no dedicated screen reader that I found. The social screen’s generic history load still reads those rows, and audit tools can request them. Keep current headlines and the small recent tail. |
| Social posts (`social_feed`) | The historical Social modal loads history, filters by team, then returns the latest matching posts. An old post can still appear for a sparse team. The modal currently hydrates all eight kinds and can write rewritten social posts. A targeted reader would reduce the load without dropping old data. |
| Season totals, awards and standings (JSON) | The career strip reads `season_history.player_season_stats`; dashboard comparisons use the previous season totals, and multiplayer dynasty scoring reads past team wins and losses plus its championship ledger. Current league leaders and regular-season awards use `player_season_stats` and team records, playoff leaders and Finals MVP use `playoff_player_stats`, and old award results sit in `season_history.awards`. Waiver priority can consult prior standings. No dedicated all-time single-game record screen reading old boxes was found. Old boxes are the source for future single-game records or retrospective splits. |
| Remaining JSON | Current rosters, generated identities and ratings, player health, plans, salary and waiver obligations, draft orders and picks are working state. Player injury histories and health risk use injury rows. Scheduled games are usually selected by the active season; departure history, draft cohorts and old season snapshots have their own readers and should be left intact in a size-only change. |

Read paths checked in `history_store.py` (archiving, validation and hydration), `save.py` (calendar, boxes, awards, rollover and backups), `app_actions.py` (player card, leader races and injury timeline), `draft.py` (consumption), `transactions.py` (eligibility), `career_stats.py` and `multiplayer.py` (career records), and `save_recovery.py` / `app_server.py` (transfer limits). Generic validation and backups touch the whole database regardless of which features need a row. A read by the Social screen’s generic loader does not establish a product need for each row it reads.

## Measurement and handoff

The checkpoint was copied before inspection. At revision 373 it had 13,157 archived boxes, 230,994 player game logs and nine rollover summaries. The current year’s 1,230 regular-season games and postseason were already complete, with that year’s totals still in live state. The original portable-export code rejected the copy as expected. The compressed sizes in the table come from test ZIPs of the JSON and SQLite members using the exporter’s default compression. The tiny backup manifest is excluded. The databases were rebuilt with the original indexes, and SQLite integrity and visible counts were checked. Record compression was byte-for-byte reversible in the prototype. The variants are sizing runs, and were not imported into the game. There are no game code changes.

Run from the repo root with the copied input only:

```sh
PYTHONPATH=src .venv/bin/python scripts/research/save_size_audit.py output/sav/checkpoint.fDrY5w/mature17.json > output/sav/measurements.json
```

### Resume state

SAV is ready for review. The copy, byte measurements and audit script are available for the coordinator. The product choice is whether to offer a compact share export alongside a full career export. No retention rule has been enabled.
