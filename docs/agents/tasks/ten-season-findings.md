# Ten-season league health check: findings (partial, 8 of 10 seasons)

_Run on the Azure worker overnight 2026-11-21: seed 17, Golden State hands-off, code as of the night's start. The run resumed after a safety shutdown and is finishing seasons 9-10. Data: `output/ten-season-partial/league_health.json` (one snapshot per action). Measured at the first regular-season snapshot of each season, rostered players only. "Value" is the engine's own player value (the AI's scale, not the new display scale)._

## TL;DR
- **The league stays believable in the middle.** Talent levels, roster turnover, ages and the rise of drafted players all look healthy over eight seasons.
- **The top flattens.** After Jokić ages, no one reaches his level again. The best young players stop growing at about 22-23 (Wembanyama flat at 74-75 from 22 to 30, Cooper Flagg peaking near 69 at 22). Top values bunch onto a few exact numbers (five of the top 15 at exactly 73.8), the signature of a hidden ceiling.
- **The weakest teams keep getting weaker.** The gap between the best and worst teams' top nine widens every couple of seasons.

## The numbers
| Season | Best | Top 5 avg | Top 10 avg | 30th | 60th | Rotation median | Made-up in top 30 | Made-up in rotations | Avg age | Top-30 age |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-27 | 78.0 | 75.2 | 74.2 | 68.6 | 65.5 | 59.2 | 0 | 0 | 26.2 | 30.2 |
| 2028-29 | 76.8 | 75.2 | 74.0 | 68.2 | 65.5 | 59.6 | 0 | 34 | 26.1 | 28.3 |
| 2030-31 | 75.0 | 74.3 | 73.3 | 67.9 | 65.8 | 59.8 | 4 | 69 | 26.6 | 28.4 |
| 2032-33 | 75.0 | 73.9 | 73.1 | 68.2 | 66.0 | 59.8 | 10 | 109 | 26.4 | 27.2 |
| 2034-35 | 74.2 | 74.0 | 73.8 | 69.1 | 66.0 | 59.6 | 15 | 152 | 26.4 | 27.7 |

**Team spread** (standard deviation of each team's top-nine average):
- best team stays about 65-67;
- worst team falls from 55.8 to 50.1;
- the spread grows from 2.5 to 3.1.

**Development by age** (average change over one season):
- +2.1 at 19, +1.0 at 22, about 0 from 24 to 29;
- -0.7 at 31, -1.5 at 33, -2.7 at 35.

The shape is right. The problem is the top end.

## Likely cause of the flat top (to confirm)
- **What the engine runs on.** It runs on 15 hidden traits derived from the 94 ratings through a quantile map fitted to the old trait table's range (`trait_adapter.fit_adapter`, `ratings_model.install_inputs_model`). See the Stage 2 survey.
- **Why that caps the top.** A quantile map has a fixed top. Once a player is at the top of the old range, improving his 94 ratings can't raise his traits any further.
- **What it explains:**
  - the repeated exact top values;
  - Wembanyama and Flagg plateauing early;
  - the league slowly losing superstar-level players.
- **Why it matters for the rules:** in effect it's the "clipping at 100" that AGENTS.md rule 3 forbids, only hidden. It is also strong evidence for Stage 2, which replaces that mapping with the 94 ratings directly.
- **Possible contributors:**
  - development caps in the 94-input growth model;
  - potential estimates for prospects;
  - the overall summary's clamp.

  A short focused check can separate them: grow one elite young player's inputs by hand and watch his traits and value.

## Parity drift (to investigate)
- The worst team's top nine weakens about 0.7 a season.
- Possible causes:
  - rebuilding teams selling everything while their young players plateau early (the same ceiling);
  - lottery luck not offsetting it;
  - bad teams being unable to sign free agents.
- Next: list the bottom three teams each season, with their records, payroll, draft picks and best young players.

## Other checks
- **Retirements look low:** about 5 a season by the retirement count. League exits (overseas, unsigned) run about 60 a season. Combined turnover looks realistic, but split this way retirements look low.
- **Injury events** run about 1,340 a season (about 45 a team) in this run, which started before the star-injury merge. Today's main gives about 40 (real 35-43).

## Suggested next tasks
1. **Confirm and fix the ceiling.** Small and high-value; this is part of Stage 2's "replace the traits" work.
2. **Investigate parity** (read-only, quick).
3. **Re-run ten seasons** on today's main once the ceiling is fixed. It now includes star injuries, free agency slices 3 and 4, the bidding-war floor and neutral coordinators.
