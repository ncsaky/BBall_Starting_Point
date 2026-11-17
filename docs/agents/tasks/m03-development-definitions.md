# M03: What the development numbers actually mean (audit, no formulas changed)

**TL;DR**
1. The GUI shows three different "growth/upside" ideas under overlapping words: (a) "Upside Remaining / Upside" for players, which is a hidden-formula *index* (age, current impact, role), not the player's real potential; (b) "Net growth" lines, which are a *rough estimate* that runs about 3-4x larger than the real rating change; (c) "Now -> Pot" and "Upside" for prospects, which is the scouts' public guess.
2. "OVR remaining" is a wrong unit for (a): it is 0 to 5 of an index (development value / 22 x 5). It is zero for every player 27 or older, and for any 25-26 year old already strong, even where the hidden "potential" field says otherwise (Jalen Williams: potential 73.7 vs ability 69.2, shown 0.0).
3. Fix is labels and tooltips only (Section 4); nothing in the engine needs to change for M03.

Scratch scripts: `output/m03-audit/probe.py`, `probe2.py`. Line numbers below are from this checkout.

## 1. Every development number the GUI shows

| # | GUI label (app.js) | Payload field (app_actions.py) | How the engine makes it |
|---|---|---|---|
| A | **Upside Remaining** ring, dev card header (app.js:4017, 4050-4057; label "x.x OVR remaining") | `upside_remaining` on roster rows (app_actions.py:1512; also 1135, 1907, 3142, 4078, save.py:4466, trade_wants.py:101) | `valuation.development_upside / 22 x 5`, clamped 0-5, one decimal. `development_upside` = `player_development_upside` (transactions.py:4235-4244) |
| B | **Upside** ring on player card (app.js:7504-7507), Player Finder "Upside" column (8888-8890), finder filter "Upside" (8837), negotiation "Upside remaining" bar (7303-7305, "+x OVR") | same `upside_remaining` (card version at app_actions.py:1817) | same as A |
| C | **Net growth**, with "Season" and "<Month>" bars (app.js:4017-4034, 4068-4078) | `dashboardTrends.development.lines[].points[].value` (app_actions.py:2188-2193, 2460-2521) | Chart value = today's OVR minus the sum of monthly estimates; each estimate is `estimated_overall_delta` (app_actions.py:2535-2543) |
| D | **Player Development** line chart, "Monthly Player Development", axis fixed to -5..+5 (app.js:10649, 10929-10960, 10972-10995) | same lines as C; JS subtracts the start value so every line starts at 0 | same as C |
| E | **Now -> Pot** (draft board, app.js:3780-3792), draft table "Now" / "Pot" (5117), asset line "Potential n" (12353) | prospect `now`, `potential` (prospect_cards.py:60-66) | Scouting estimate. `potential` is the *public* number (`scouting_prior`, draft.py:1835-1843) or, below 100% scouting, a noisy midpoint from your scouts (prospect_cards.py:32-40). Hidden true potential is not shown |
| F | **Upside** ring on a *prospect* card, locked below 100% scouting (app.js:7498-7500) | `upside_remaining`, `upside_unlocked` (app_actions.py:1683) | `(scouted potential - scouted now) / 5`, clamped 0-5. Different formula from A/B, same label and same "OVR remaining" unit text |
| G | Fantasy draft **Ceiling** and "+runway" (app.js:4449-4461, 4499), card block "Likely growth / Good-situation runway / Ceiling OVR" (4574-4580) | `ceiling_overall`, `growth_runway`, `growth_outlook` (fantasy_draft.py:231-300) | 3-year estimate from age table, headroom, development value and minutes. Fantasy draft only |
| H | Contract extension chart "Projected OVR" with scenario range (app.js:9236-9244) | `projection` (extension_analysis.py:136) | Seven runs of the real development model with varied minutes and staff; note says "illustrative, not a guarantee" |
| I | Trade bar **Age + upside** (app.js:6351-6352) | `age_upside` (transactions.py:3739-3742) | `age_curve x 0.9 + development_upside x 0.75`, market value points, not OVR |
| J | Staff **Development Lead** (app.js:3844 etc.) | staff grade | Multiplies real monthly growth (health.py:615, `development_multiplier`); not a player number |

Not shown anywhere: the player's `potential` and `current_ability` fields (only 256 of 691 rostered players have them: young or recently drafted), the realization roll (bust/normal/breakout), the per-skill ceiling, and the real monthly skill changes (the "development events").

## 2. Exact definitions

**A/B Upside (players).** Hidden formula (transactions.py:4235): 0 if age is over 26; otherwise `(24 - age) x 2.3` (floored at 0) plus `(68 - impact) x 0.16` (floored at 0), plus 4 for development-priority players, plus 2 if age 23 or under with 18+ minutes; capped 0-22. GUI divides by 22 and multiplies by 5. Scale 0-5 index. Time window: none stated (it is a market-style signal, not "next 3 years"). Visible, but it does not read the player's potential at all, and it is recomputed from current minutes and impact so it can move with roster role. It also feeds trade value (weight 0.75) and AI trade fit.

**C/D Net growth.** Unit is estimated OVR points. Window: the current season's Oct-Jun months only (app_actions.py:2465-2473, 2484-2495); offseason months (Jul-Sep) are processed by the engine (save.py:1796) but never charted. "Season" = last chart point minus first; "<Month>" = last minus previous point. Estimate = sum of that month's skill changes x 0.75, capped at +/-0.65 per month (app_actions.py:2535-2543; the code comment says it was inflated "to keep the +/-5 display envelope"). Then the line is anchored so the final point equals today's OVR. The chart axis is fixed at -5..+5 and clamps beyond that. Real source: `monthly_trait_delta` (health.py:735-806), 15 skills per player per month, each at most +0.36 and at least -0.12, driven by age factor, minutes, staff, injuries/fatigue, focus skills and the hidden per-skill ceiling. Applied to ratings via `ratings_model.apply_development` for the new inputs mode (ratings_model.py:260-274), old mode via `apply_development_events_to_traits`.

**E Pot (prospects).** Scouts' public estimate on the same display scale as OVR. Wide error when scouting is low.

**F Upside (prospects).** `(Pot - Now) / 5`, so a 25-point gap shows the maximum 5.0.

**Same word, different thing.**
- "Potential" (E, scouts) vs player `potential` field (true hidden, raw engine scale, drives `upside_multiplier` and per-skill ceilings in health.py:809-828 and talent.py:93-110) vs "development upside" (A/B, 0-22 market index). Three different quantities.
- "Upside" for a drafted player (A) and the same ring for a prospect (F) use different formulas, and the prospect ring is hidden until 100% scouting while the player ring is always visible.
- Raw `potential - current_ability` is on a different scale than displayed OVR (Flagg: raw 64.2 ability but 72.2 shown), so nobody can reconcile "86 potential" with the 72 on the card.

## 3. Examples (this save, start of 2026-27, seed 1)

| Player | Age / role | Shown OVR | Upside ring (A/B) and why | Net growth, season (C), est. vs real |
|---|---|---|---|---|
| Cooper Flagg (young riser) | 19, 33.7 mpg | 72.2 | **3.1**: dev value 13.5/22 x 5. (24-19) x 2.3 = 11.5, +2 for minutes, +impact term. Hidden potential 86.2 vs ability 64.2 | Estimate hits the 0.65 cap every month: **+5.9** over 9 months. Real change after 3 months of engine growth: 72.2 -> 72.7 (+0.5), so the estimate for those months (+1.95) is about 4x too high |
| Jalen Williams (late riser) | 25, 29.1 mpg | 75.2 | **0.0**: age term is 0, and impact is above 68. Hidden potential 73.7 vs ability 69.2 (a 4.5 raw gap) is ignored | +1.2 (small positive months) |
| Anthony Edwards / Jalen Brunson (prime) | 25 / 30 | 78.4 / 73.4 | **0.0** / **0.0** | +1.8 / +0.5 |
| Stephen Curry (older decliner) | 38, 31.3 mpg | 77.8 | **0.0**, and it cannot go negative, so decline is not shown here at all | Hits the -0.65 cap every month: **-5.9**. Real after 3 months: 77.8 -> 77.5 (-0.3), estimate -1.95 |
| Kevin Durant | 38 | 73.3 | 0.0 | -5.9 est.; real 3 months 73.3 -> 73.1 (-0.2) |
| Prospect example (draft board) | n/a | Now 55, Pot 80 | F: (80-55)/5 = **5.0**, "5.0 OVR remaining" only after 100% scouting | not applicable |

Reading: Net growth saturates for anyone very young or old, so every old star looks the same (-5.9) and every top rookie the same (+5.9). The real engine moves far less in these months.

## 4. Inconsistencies and proposed label set (labels and tooltips only)

Problems:
1. "OVR remaining" and "+x OVR" claim a rating-point meaning that A/B do not have (5.0 max means an index, and 0 for everyone 27+).
2. Same "Upside" ring has two formulas (players vs prospects), and prospects hide it while players do not.
3. "Net growth" is an inflated estimate shown with one decimal as if exact; Season and Month bars share the -5..+5 scale, which hides small real moves.
4. Season window quietly excludes Jul-Sep; the card says only "Season".
5. "Potential" means three things (Section 2). Players never display potential at all, yet the user's notes ask for "potential vs upside".
6. Trade "Age + upside" bar is market value, but sits next to OVR-style numbers.
7. Player Finder column "Upside" (0-5, not OVR) sits beside OVR/OFF/DEF bars.
8. Finder filter and sort expose a number whose formula is hidden from the user.

Proposed labels and one-line tooltips:
- **Growth runway** (replaces "Upside Remaining" / "Upside" for players): "A 0-5 estimate of how much room this player has to improve, based on age, role and current level. It does not predict an exact rating."
- **Prospect upside** (replaces F, same ring, keeps the lock): "Gap between your scouts' estimate of the prospect's potential and current level, scaled to 0-5. Unlocks at 100% scouting."
- **Scouted potential ("Pot")** (E): "Your scouts' best guess at this prospect's best realistic level. Not the true hidden rating."
- **Season trend** (replaces "Net growth"): "Estimated change in overall since October. A rough guide: real changes are usually smaller."
- **This month** (replaces the month label in the metric): "Estimated change in overall during the latest month."
- **Development trend chart** title: "Estimated overall change this season (Oct-Jun)". Axis note: "Shows estimates, capped at +/-5."
- **Ceiling / Good-situation runway** (G, fantasy draft only): keep, but tooltip "Three-year best-case estimate. Not guaranteed."
- **Age + upside** (I): rename "Age and growth value", tooltip "Market value from age and room to grow. Not an overall rating."
- Remove the "OVR" suffix on A/B and in negotiation bars ("+1.2 OVR"); show the index plain (for example "3.1 / 5").

Optional engine-adjacent follow-ups (need a separate decision, not part of M03): make the season estimate use the real before/after OVR instead of the 0.75 x cap; add a player "potential" display that matches what the engine uses (rule 4 in AGENTS.md); let Growth runway read the hidden potential gap (it currently ignores it).

## 5. Open questions for the user
- Should veterans show a "decline watch" number, or is a flat 0.0 acceptable once growth runway ends?
- Do you want real potential visible on rostered players you own (as a scouted estimate) so "potential vs upside" can be compared as in your notes?
