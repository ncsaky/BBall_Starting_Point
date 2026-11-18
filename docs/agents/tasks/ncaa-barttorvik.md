# NCAA college data from Barttorvik (T-Rank)

Owner: Claude (coordinator). Status: **data captured; prospect model not started.** Started 2026-11-19.

## Why
Basketball Index's NCAA app does not recognise the user's account, so college data comes from Barttorvik instead.
It's the evidence the prospect generator lacks (see `prospect-realism.md`, section 6): it would let skills be set from
college production instead of a draft-slot profile. It also sizes scouting misses and the top-3 star gap from real
college-to-NBA pairs, and separates young risers from finished seniors.

## What was captured (local only, never committed)
- `data/research/barttorvik/raw/players_<season>.csv`, seasons 2008-2026 (season = spring year; 2026 = 2025-26).
  Source: `https://barttorvik.com/getadvstats.php?year=<season>&csv=1`, downloaded 2026-11-19 with the user's
  approval (19 requests, 3 s apart, about 37 MB total). Git-ignored via `.gitignore`. Derived numbers may be committed.
- 90,739 player-seasons (about 4,600-5,000 per season). 909 distinct drafted players (about 48 per draft;
  players drafted from overseas or the G League are not in college data), 228 of them lottery picks.

## Columns
Loader and column map: `scripts/research/barttorvik.py` (`load(season)`, `load_all()`). The CSV has no header row;
names were matched against the site's player finder. Highlights:
- identity: name, team, conference, class year, height, birth date, hometown, Barttorvik player id
- **eventual NBA draft pick** on every college season of a drafted player (blank = undrafted)
- recruiting rating (0-100, blank if unranked)
- role label (e.g. "Scoring PG", "Wing F", "Stretch 4", "C"; blank in 2008)
- tempo-free rates: minutes %, usage, offensive/defensive rating, eFG%, TS%, offensive/defensive rebound %,
  assist %, turnover %, block %, steal %, free-throw rate, fouls committed per 40
- shooting by zone: dunks, close twos ("rim"), far twos ("mid"), threes and free throws, makes/attempts and the share
  of makes that were assisted
- impact: box plus-minus (two versions, each split into offense and defense), points over replacement (offense and
  defense), stops
- per-game box: minutes, points, rebounds, assists, steals, blocks
- columns 72-77 not identified yet

## Next (not started)
1. Pair each drafted player's final college seasons with NBA outcomes: Basketball Index talent and impact by season
   (local captures), the game's own ratings for current players, and year-4 tiers as in `prospect-realism.md`.
2. Fit college profile -> NBA entry inputs (shooting from FT% / 3P% / 3P rate, creation from usage and unassisted
   rim/mid makes, passing from assist %, rim protection from block %, rebounding, age and size).
3. Generator: draw prospects from real college profiles (resampled or fitted), so classes carry real skill mixes,
   and size the scouting miss from the college-to-NBA residuals. Consider the 2026-27 college season (2027 file) as
   the next real draft class.
4. Good fit for an overnight agent or a Fable 5.2 design pass (see MORNING_REPORT_2026_11_19.md).

## Resume state
Data captured and mapped (2026-11-19). Nothing in the engine uses it yet.
