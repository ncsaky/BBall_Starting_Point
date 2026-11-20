# Free-agent prices below the starter tier

- Rotation and depth free agents with no researched price now ask for a share of the salary cap based on what they bring on the court.
- On 15 held-out contracts in those tiers, the average miss fell to $2.62 million from $3.03 million with the minutes rule and $4.78 million with the old market formula.
- Both offseason runs signed the same players. Four teams finished over the hard-cap line in both runs.

## Fit and held-out results

- Matched 84 new free-agent contracts and re-signings to the game (36 from 2025, 48 from 2026). Excluded 25 extensions. Salaries are the reported total divided by contract years, then divided by that signing year's official salary cap.
- Used the game's on-court value in the 94-input ratings mode, the game's contract role tier, age, estimated years of service and signed contract length. On-court value avoids using the existing contract's surplus to predict its replacement. The evidence uses the current game snapshot with October 2026 opening rosters for both summers, with age and service moved back a year for 2025. This is a player-held-out comparison on a later snapshot, so historical ratings and role changes can affect the results.
- Used a weighted regression of the log of salary share, with a penalty of 2 on each coefficient except the intercept. A clear 2026 row gets weight 1. A 2025 row gets half weight for weaker evidence. The uncertainty flag cuts either weight to a quarter. Depth and rotation share a role group because the evidence has one depth contract. The other groups are regular starters and the higher-priced group of specialists, high-end starters and stars.
- For a live ask, the game prices a two-year reference deal, uses its existing age and salary rule to estimate likely years and prices that term. The scale moves with the cap. Ask movements, AI bids and the user offer check use the same first-year salary bounds once the fit applies. The minimum uses years of service from the game's existing estimator and rounds up to the next $0.1 million. The maximum calls the game's experience-based rule and rounds down. [NBA–NBPA agreement, Article I and Exhibit C](https://imgix.cosmicjs.com/25da5eb0-15eb-11ee-b5b3-fbd321202bdf-Final-2023-NBA-Collective-Bargaining-Agreement-6-28-23.pdf) · [NBA 2022–23 base cap](https://pr.nba.com/nba-salary-cap-2022-23-season/)
- Skipped league-wide cap room. The source gives qualitative notes for two summers, without usable per-team cap room measured before bidding. A single number per summer would mix its effect with differences in coverage and signing mix.

Players were assigned to five groups by a stable hash of their names. Repeated players stayed in the same group. Each score predicts one group with a fit on the other four. The validation groups also informed the choice of penalty. The shipped coefficients use all 84. Errors below give every observed contract equal weight.

| Price rule | Rotation and depth average miss ($M) | Rotation and depth average miss (cap points) | Rotation and depth root mean squared miss ($M) | All 84 average miss ($M) |
|---|---:|---:|---:|---:|
| Fitted ask, game-estimated term | 2.62 | 1.65 | 3.64 | 6.91 |
| Minutes × $0.48M | 3.03 | 1.91 | 3.81 | 6.81 |
| Existing ask formula | 4.78 | 3.02 | 5.44 | 6.99 |
| Existing contract-market profile with comparable salaries | 3.66 | 2.30 | 4.51 | 6.67 |
| Fitted ask, actual signed term supplied | 2.46 | 1.55 | 3.07 | 6.18 |

The actual-term row benefits from knowing what the player signed. The first row is the playable test. It wins against both old rules for the tiers it replaces. On all 84, applying the fit across the board raises the average miss against the minutes rule and the comparable-salary profile. Regular starters, elite specialists and the star-priced tiers retain their prior ask path. Existing research rows still take precedence.

## Fifteen held-out deals

All prices are millions per year. A player's two summers appear separately when both deals are in the evidence.

| Summer | Player | Game tier | Real | Fitted | Minutes | Existing formula |
|---|---|---|---:|---:|---:|---:|
| 2025 | Chris Paul | Rotation | 3.60 | 6.3 | 6.8 | 8.6 |
| 2025 | Clint Capela | Rotation | 7.17 | 7.9 | 5.8 | 12.5 |
| 2025 | Dorian Finney-Smith | Depth | 13.25 | 6.2 | 8.3 | 3.5 |
| 2025 | Gary Trent Jr. | Rotation | 3.75 | 5.7 | 10.1 | 10.0 |
| 2025 | Guerschon Yabusele | Rotation | 6.00 | 7.2 | 6.3 | 11.5 |
| 2025 | Kevon Looney | Rotation | 8.00 | 9.7 | 6.7 | 11.8 |
| 2025 | Luke Kennard | Rotation | 11.00 | 7.1 | 10.1 | 11.6 |
| 2025 | Taurean Prince | Rotation | 3.55 | 5.6 | 10.0 | 5.9 |
| 2025 | Tre Mann | Rotation | 8.00 | 5.7 | 7.0 | 10.9 |
| 2025 | Tyus Jones | Rotation | 7.00 | 6.7 | 7.5 | 9.3 |
| 2026 | Gary Trent Jr. | Rotation | 16.00 | 6.1 | 10.1 | 10.0 |
| 2026 | Luke Kennard | Rotation | 6.50 | 7.6 | 10.1 | 11.6 |
| 2026 | Ousmane Dieng | Rotation | 5.83 | 6.9 | 7.2 | 15.5 |
| 2026 | Quinten Post | Rotation | 10.00 | 12.7 | 8.3 | 16.0 |
| 2026 | Robert Williams III | Rotation | 14.67 | 14.1 | 8.1 | 15.8 |

## Offseason replay

A fresh Golden State career with seed 17 and the 94-input ratings ran through the 2026–27 season and draft. Both July 2027 markets started from the same June 27 save, after the computer teams' exclusive re-signings. The control used the old asks. The human team placed no bids.

| Market result | Old | Fitted |
|---|---:|---:|
| Opening free agents | 391 | 391 |
| Opening asks from existing research | 340 | 340 |
| Median ask for the 51 eligible players | $1.8M | $6.1M |
| Open-market deals | 35 | 35 |
| Exclusive computer re-signings | 11 | 11 |
| Automatic roster-repair deals | 51 | 51 |
| Opening free agents still unsigned | 305 | 305 |
| Teams with actual salary-cap room | 1 | 1 |
| Teams over the hard-cap line | 4 | 4 |

The 51 fitted quotes changed in both directions. Forty-nine rose, one fell and one stayed flat. No player in this group drew an AI bid under either price rule. Five later joined teams through automatic roster repair at its fixed $2.25M salary. The signed deals, unsigned pool and all 30 team payrolls were identical. The eight asks in the existing star-priced tiers and all deals in those tiers matched as well. For example, Cason Wallace signed with Memphis at $27.5M per year in both runs. The replay validates the new asks against live save data. The new bid-path test covers how a fitted ask reaches a bid when a player does draw interest.

### Signed salary by tier

Each entry shows count, median and range in millions per year. The simulated sample includes open-market deals and exclusive computer re-signings. The 51 fixed-price roster repairs are counted above. Tiers in both columns come from the game. The tracked real deals favor announced, higher-value contracts, so their counts and lower tail are incomplete. Both samples had zero deals in the game's franchise-anchor and All-Star core tiers.

| Game tier | Reported 2025–26 deals | 2027 old | 2027 fitted |
|---|---|---|---|
| Veteran star | 5 · 14.00 (3.90–40.75) | 1 · 15.10 (15.10–15.10) | 1 · 15.10 (15.10–15.10) |
| High-end starter | 11 · 25.00 (11.00–46.25) | 6 · 20.11 (14.60–30.27) | 6 · 20.11 (14.60–30.27) |
| Elite specialist | 3 · 20.00 (9.33–39.67) | 2 · 23.90 (14.00–33.80) | 2 · 23.90 (14.00–33.80) |
| Starter | 50 · 9.00 (3.90–53.00) | 15 · 14.20 (9.10–31.13) | 15 · 14.20 (9.10–31.13) |
| Rotation | 14 · 7.08 (3.55–16.00) | 20 · 5.35 (2.70–13.24) | 20 · 5.35 (2.70–13.24) |
| Depth | 1 · 13.25 (13.25–13.25) | 2 · 4.04 (3.80–4.28) | 2 · 4.04 (3.80–4.28) |

### Cap room after free agency

July 5, after the game filled out short rosters. Dollar amounts are millions. The salary cap was $170.70M and the hard-cap line was $229.40M. Negative room means the team was over that line.

| Team | Cap room, both runs | Hard-cap room, both runs |
|---|---:|---:|
| ATL | -16.26 | +42.44 |
| BKN | -26.47 | +32.23 |
| BOS | -52.05 | +6.65 |
| CHA | -33.47 | +25.23 |
| CHI | -23.43 | +35.27 |
| CLE | -62.74 | -4.04 |
| DAL | -26.63 | +32.07 |
| DEN | -45.45 | +13.25 |
| DET | -36.70 | +22.00 |
| GSW | +39.62 | +98.32 |
| HOU | -34.75 | +23.95 |
| IND | -34.27 | +24.43 |
| LAC | -24.85 | +33.85 |
| LAL | -41.67 | +17.03 |
| MEM | -23.45 | +35.25 |
| MIA | -36.51 | +22.19 |
| MIL | -13.31 | +45.39 |
| MIN | -47.01 | +11.69 |
| NOP | -26.51 | +32.19 |
| NYK | -54.88 | +3.82 |
| OKC | -71.12 | -12.42 |
| ORL | -62.74 | -4.04 |
| PHI | -40.75 | +17.95 |
| PHX | -31.38 | +27.32 |
| POR | -36.40 | +22.30 |
| SAC | -22.75 | +35.95 |
| SAS | -58.92 | -0.22 |
| TOR | -35.15 | +23.55 |
| UTA | -32.55 | +26.15 |
| WAS | -34.79 | +23.91 |

Oklahoma City was already $12.42M over the line at the June checkpoint. Cleveland, Orlando and San Antonio crossed it in both runs when the existing roster-repair routine added contracts after the market. Their payrolls immediately before repair were $224.44M, $224.44M and $225.12M. Repair added $9.00M, $9.00M and $4.50M respectively. The zero-overage acceptance check therefore fails on the existing roster-repair path.

## Verification

- 50 focused tests passed, including price response, legal starting-salary bounds, a fitted AI bid and the user offer screen's signing floor.
- On a copy of the opening save, the offer screen showed John Konchar's $10.0M ask and a $13.0M signing floor for three guaranteed years. The offer action rejected $12.9M and recorded the deal at $13.0M.
- `bash scripts/run_core_tests.sh` passed with 338 tests run and two skips.
- Rebuild the coefficients with `PYTHONPATH=src .venv/bin/python scripts/research/fit_free_agent_salary.py --write-fit`. The career checkpoint, July and September save pairs, and raw comparison tables are in `output/fa-prices/` in this worktree.

## What's left

- Restricted free-agent offer sheets and matching rights are out of scope.
- The existing automatic roster-repair path in `save.py` needs a hard-cap policy decision. It makes fixed-price signings when teams are short of players and can take payroll over the line. The game's rules for team-level exceptions and later contract-year minima are separate from the fitted opening ask.
- The browser's salary slider still shows the old league-wide minimum and a team-room ceiling. The ask and calculated signing floor come from the same engine decision, which now uses experience-based limits for fitted players. The slider's labels and upper-bound preview would need browser changes.
- The real sample includes only one player the game grades as depth. The 51 live quotes tested here mostly raised old minimum-level asks, and none produced a negotiated signing. More low-end contracts and a later-season market with more unresearched rotation players would test how these quotes hold up.
