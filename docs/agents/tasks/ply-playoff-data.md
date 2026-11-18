# Playoff translation evidence

The dataset covers the same 679 players as the career-stats file. It has 2,963 regular-season player-seasons and 1,401 playoff player-seasons from 2013–14 through 2025–26. Of those players, 398 logged playoff minutes. All 17 requested stat fields matched Basketball Reference in each of the five playoff spot checks.

The data is in [player_playoff_stats.json](../../../data/research/player_playoff_stats.json). Each player has a `regular.seasons` and a `playoffs.seasons` list under their existing ESPN player ID. An empty list means the sources yielded no games for that player in the phase and date range. A player traded during a season has one combined row with the contributing ESPN team IDs.

## Coverage

| Phase | Players with minutes | Player-seasons | Missing fields | Estimated minutes |
|---|---:|---:|---:|---:|
| Regular season | 572 | 2,963 | 0 | 0 |
| Playoffs | 398 | 1,401 | 0 | 0 |

The file also gives season-by-season counts, source URLs, and retrieval timestamps. All 679 requests for playoff histories succeeded. The regular-season box scores came from the existing raw ESPN cache.

## Basketball Reference spot checks

These are totals from each source. The final column shows how many of the 17 numeric fields in the delivered row agree with Basketball Reference, including minutes. The team also agreed in every check.

| Player | Playoffs | Games | Points | Rebounds | Assists | ESPN minutes estimate | Basketball Reference and delivered minutes | Fields matched |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nikola Jokić | 2023 | 20 | 600 | 269 | 190 | 790.0 | 789 | 17/17 |
| Giannis Antetokounmpo | 2021 | 21 | 634 | 269 | 108 | 800.1 | 800 | 17/17 |
| Jamal Murray | 2023 | 20 | 522 | 113 | 142 | 800.0 | 799 | 17/17 |
| Jalen Brunson | 2024 | 13 | 421 | 43 | 97 | 517.4 | 518 | 17/17 |
| Shai Gilgeous-Alexander | 2025 | 23 | 688 | 123 | 150 | 851.0 | 851 | 17/17 |

Sources for the comparisons are the Basketball Reference playoff totals tables. [2021](https://www.basketball-reference.com/playoffs/NBA_2021_totals.html) · [2023](https://www.basketball-reference.com/playoffs/NBA_2023_totals.html) · [2024](https://www.basketball-reference.com/playoffs/NBA_2024_totals.html) · [2025](https://www.basketball-reference.com/playoffs/NBA_2025_totals.html)

## How the data was collected

- The importer uses the ESPN career stats endpoint with season type `2` for the regular season and `3` for the playoffs. When ESPN sends back its regular-season table with playoffs absent from its available seasons, the importer records an empty playoff history.
- ESPN's career totals omit total minutes. Basketball Reference supplies the published whole-minute totals when normalized names, games and a set of box totals identify one row. The join recognizes Basketball Reference's “Ron Holland” for ESPN's “Ronald Holland II.” Two matched 2022–23 Memphis rows, Tyus Jones and Brandon Clarke, have one made free throw, two free-throw attempts, and one point of disagreement between sources. Their other matching box totals confirmed the minute join. The output retains ESPN's box counts. [2022–23 Basketball Reference regular-season totals](https://www.basketball-reference.com/leagues/NBA_2023_totals.html)
- Basketball Reference had one verified playoff season absent from ESPN's career endpoint. Maxi Kleber played one game for the Lakers in the 2025 playoffs. The importer adds that row from Basketball Reference, and the official NBA box score confirms the appearance and counts. [2025 playoff totals](https://www.basketball-reference.com/playoffs/NBA_2025_totals.html) · [Official NBA box score](https://www.nba.com/game/0042400165/box-score)
- ESPN's totals table omits Seth Curry's one-game Memphis stint in 2013–14 and Thanasis Antetokounmpo's two-game 2023 playoffs. Curry's one-game averages give his counts directly. Thanasis's counting averages are all zero over two games, which gives zero counts. Basketball Reference also reports those totals. [2013–14 regular-season totals](https://www.basketball-reference.com/leagues/NBA_2014_totals.html) · [2023 playoff totals](https://www.basketball-reference.com/playoffs/NBA_2023_totals.html)
- The importer loads only the numeric helpers from the career importer because a normal import would start that script's network requests and writes. Requests are sequential and spaced at least 0.51 seconds apart for ESPN and 4.1 seconds for Basketball Reference. New raw responses are cached under `output/ply/`.

Run from the repository root with `python3 -B scripts/import_player_playoff_stats.py`. Reruns reuse the cache. The cached rerun produced an identical file. Checks across all rows confirmed the season bounds, unique keys, made shots within attempts, and the scoring and rebounding totals. The local comparison log is `output/ply/verification-final.log`.
