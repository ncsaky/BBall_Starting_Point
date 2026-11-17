# Stage 1 design: new player ratings drive the current engine

_Owner: Claude Code. 2026-11-16. Implements roadmap S1.1–S1.5 (`ENGINE_ROADMAP.md`). Respects the approved map's rule (`PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`): one authoritative player model, and any old-engine adapter is transitional and never separately editable._

## Core idea

The **94 inputs are the only stored truth** about a player's basketball ability. The old engine's 15 ratings (`traits`) become a **pure function of the inputs**, computed by an adapter. They stay under the hood, so every existing consumer keeps working unchanged: the sim, health, draft, trades, contracts, narrative and about 15 other modules.

```
evidence ──► estimator ──► 94 inputs (stored, shown on card)
                              │
                              ├──► adapter ──► 15 hidden ratings ──► existing engine, AI, everything
                              └──► derived summaries ──► OVR / OFF / DEF / role fits (shown)
development ──► changes inputs (never the hidden ratings directly)
```

## Components

### A. Inputs for everyone (Codex task E2)
- `src/nba_gm_data/input_estimator.py` produces `data/canonical/player_inputs_2026_27.json`: 691 players by 94 inputs, each with value, uncertainty, status (`estimated` or `prior`) and sources. It also has a prospect variant.
- Loaded into the canonical universe at build time. Saves keep inputs in the existing dormant `player_performance_inputs` section (`player_model.py`).

### B. Adapter: inputs to the 15 hidden ratings (Claude)
- New `src/nba_gm_data/trait_adapter.py`. For each hidden rating, a **declared, readable formula** over named inputs: weights plus the input families involved. Example: `release_speed` comes from the shooting-preparation and release inputs. `rim_deterrence` comes from rim-contest technique, verticality, length and positioning.
- **Scale matching:** each derived rating is quantile-mapped to the current league distribution of that rating. The old engine's tuning stays valid, while *which* player sits where comes from the new evidence. This is engine plumbing (the engine adapting to the ratings), not ratings bent to fit the engine.
- The weights are written down and reviewable. They are not fitted to sim outcomes.
- The adapter runs in exactly two places: universe build, and whenever a player's inputs change (development, injuries' long-term effects, draft generation).

### C. Development writes to inputs (Claude)
- Today, development events hold `trait_deltas` that `save.py:apply_development_events_to_traits` adds to the old ratings.
- Stage 1 keeps the existing growth model (who grows and by how much is unchanged). Each hidden-rating change is spread onto that rating's contributing inputs in proportion to the adapter weights. The hidden ratings are then recomputed.
- The card always shows the developed inputs, and the engine always uses ratings derived from them.
- Proper per-skill aging curves (athleticism declines while skills grow, and so on) come later (roadmap E8).

### D. Displayed ratings and the new player card (Claude, GUI)
- Replace the card's current bars with the full input set, grouped into four layers: **Technique & recognition**, **Physical tools**, **Tendencies**, **Coach usage/deployment**.
- Every value shows its uncertainty and source status (estimated or prior).
- OVR/OFF/DEF/role fits are derived from inputs and capabilities. **No clipping at 100**: the scale has headroom, so elite players separate.
- The hidden 15 are no longer shown anywhere.
- Today's scale problem to fix (measured 2026-11-16): the league top 10 sit between 77.7 and 81.0, Gilgeous-Alexander's DEF is 60.8, Knueppel is 60.4 overall, Harper 59.9.
- Old rating-pin tests (`test_imported_rookie_ratings`, `test_player_tuning`, `test_roster_alignment` and others) get rewritten with relative expectations for the new scale.

### E. Front-office AI on the new ratings (Claude, with Codex for bounded pieces)

**Finding (2026-11-16):** in inputs mode the AI already reads input-derived traits. But its OVR/OFF/DEF comes from `save.py:_uncached_player_attribute_summary`, a separate formula over the 15 traits. That formula clamps to 1–99 and adds a minutes bonus, and it is called about 75 times across `play.py`, `save.py`, `app_actions.py`, fantasy draft, extensions, release planning, prospect cards, waivers, transactions and trade wants. The new card header uses the profile's 50+15z scale instead, so card and AI would show different OVRs.

**Plan:**
1. In inputs mode, `player_attribute_summary` returns overall/offense/defense from `player_profile`, on the single unclipped display scale. Subratings follow the same approach.
2. Inventory every threshold that reads these values (superstar cutoffs, max-contract and extension triggers, trade-value breakpoints, draft and fantasy boards, waivers).
3. Re-express each threshold as a league percentile, so it carries over to the new scale.
4. Re-check the market: no collapse in superstar value, sensible contracts, trades still happen, and five-season activity distributions look comparable to legacy.
- Trade value, contract value, extensions, free agency and draft boards switch from the old summary values to the new derived OVR/OFF/DEF, role fit and age/upside.
- Re-check the market afterward: no superstar-value collapses, sensible contracts, trades still happen.

### F. Prospects
- `draft.py` generation produces inputs through the estimator's prospect variant. Then the adapter produces their hidden ratings. Same pipeline as veterans.

## Gates (must pass before Stage 1 becomes the default)

1. Betting-odds scorecard (`validate-season-probabilities`): no worse than the old ratings (Brier score and log loss).
2. Real-stat scorecard (`scripts/calibration_report.py`): no more league metrics out of band than the old engine (12 of 18 in band today). Player-level misses don't get worse for high-minute players.
3. Core tests green, with the rating-pin tests rewritten.
4. Three-season smoke run: development changes inputs, cards and hidden ratings stay in agreement, no NaN or out-of-range values.
5. User review of the new card, and of ratings for about 20 players the user knows well.

## Build order

1. Tests trustworthy, plus a fast core suite (in progress).
2. E2 estimator (Codex) in parallel with B, the adapter. Build B first against the 32 hand-researched players, then the full estimator output.
3. C, development to inputs.
4. Gates 1–2 on the old scorecards. Fix the adapter if they regress.
5. D, the new card. E, front-office AI.
6. F, prospects. Then gates 3–5, then default switch.

## Basketball Index timing

Subscribe after step 2 lands: the estimator exists, and the capture/import pipeline has been tested on free pages. Capture **everything** the paid membership exposes (all seasons, all metric families, all players, both values and percentiles) for personal use within the site's terms. The data then feeds the estimator as an additional evidence source.
