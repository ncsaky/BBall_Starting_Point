# Rating change proposals — 2026-11-02

Research-only recommendations for Dylan Harper, Jeremy Sochan and Luka Dončić. No canonical ratings were edited by this research task. The game uses 0–100 base traits and derives engine OVR/OFF/DEF; player cards then map those summaries to a separate 1–99 presentation scale. The current probe uses baseline `2026-10-30-contract-separation-v10`; the player rating/roster snapshot remains dated July 28. The verified save starts October 20, 2026, but that date does not automatically refresh all roster, health, contract or rating inputs. The later contract import update does not change the July rating evidence or approve the Harper trait proposal. See `DISPLAY_VALUE_TRACE.md` for probe details.

## Decision summary

| Player | Verified new-save player-card OVR / OFF / DEF | Engine OVR / OFF / DEF after runtime rotation | Recommendation | Expected OVR / OFF / DEF direction | Confidence |
|---|---:|---:|---|---|---|
| Dylan Harper | **78.6 / 80.0 / 81.5** | 58.6 / 60.0 / 61.9 | Narrow increase: `passing_reads` 71.1 → 73.1. Leave scoring traits and potential unchanged. | Slight ↑ / slight ↑ / unchanged | Moderate-low |
| Jeremy Sochan | **79.1 / 72.8 / 87.1** | 59.1 / 52.8 / 68.9 | Leave unchanged. Current shooting traits are already modest; weak 2025-26 results do not establish further skill decline or that defense/rebounding are overstated. | ↔ / ↔ / ↔ | Moderate |
| Luka Dončić | **88.6 / 96.0 / 67.5** | 70.8 / 83.4 / 47.5 | Leave underlying traits unchanged. The perceived low OVR is explained substantially by reading an engine value as a displayed rating. | ↔ / ↔ / ↔ | Moderate-high for no change; low for any exact calibration conclusion |

These are the exact values selected from `ratings.overall/offense/defense` by the frontend in the October 20 gameplay-entry disposable new-save action trace, freshly reconfirmed on November 2 after an explicit measurement-free release; probe metadata and full payloads are in `probe_artifacts/player_card_probe_window_release_20261102.json`. No season was simulated. The actual OVRs are rotation-dependent in this new-save state. No projected potential, growth mechanics or OVR formula changes are recommended.

## Dylan Harper

### Verified game values and relevant traits

In the current October 20 disposable new save, engine OVR/OFF/DEF are 58.6/60.0/61.9 and displayed 78.6/80.0/81.5. Saved baseline minutes were 22.1; runtime rotation projected 15.89. Before save rotation, the canonical engine summary was 59.5/60.0/61.9 and card-scale 79.5/80.0/81.5. July 28 current ability is 53.11 and potential 71.91. Relevant traits are `passing_reads=71.07`, `handle_pressure=67.74`, `rim_pressure=56.73`, `shooting_range=52.95`, `release_speed=53.97`, `shot_versatility=53.91`, `foot_speed_lateral_agility=71.06`, and `defensive_effort=69.20`. The July health state is active, no current injury ID, no present health penalty.

### Evidence split by date

**Available by July 28 (2025-26 season):** The official Spurs game notes report 69 games (four starts), 22.6 minutes, 11.8 points, 3.9 assists and 3.4 rebounds per game, on 50.5% field goals and 34.3% from three. He had a 20% usage rate and a productive Spurs playoff run. These support a capable first-year finisher and secondary creator in a moderate role; they do not establish elite shooting or high-volume lead creation.

**Later evidence (published after July 28):** The 2026 sophomore outlook praises his playoff confidence/rim finishing and forecasts a larger role. Treat that as corroboration of promise and forecast, not as information available to the inspected July-source baseline. This later evidence predates the verified October 20 entry date, but keep it labeled separately from the July-start evidence; do not include post-opener evidence. His 15 missed games for calf/ankle issues are season availability evidence, not a healthy-ability trait downgrade.

### Comparable scale check and recommendation

On the same canonical trait scale, teammate Stephon Castle has `passing_reads=73.50`, `handle_pressure=63.72`, and `rim_pressure=66.52`; Harper's handle is already higher than Castle's while Harper's passing-read estimate is slightly lower. Harper's 3.9 assists in 22.6 minutes, efficient FG result, and independent positive playoff/sophomore evaluation support a small passing-read correction. The same evidence does not support elevating shooting range/release because the 34.3% three-point season is consistent with Harper's current low-mid 50s shooting traits. It also does not warrant a rim-pressure boost without shot-location/drive evidence.

**Proposal:** `passing_reads` +2.0, from 71.07 to 73.07, with no change to other traits, current ability or potential. This aligns him near (not above) the in-game Castle playmaking comparator and recognizes demonstrated rookie playmaking. Treat as a reviewable proposal, not a confident regrade: 69 games, a 22.6-minute role, and one postseason sample limit precision.

**Expected impact:** Slightly higher engine OVR through creation/IQ blend and slightly higher OFF; DEF unchanged. Display values will also move slightly upward by the fixed transform. Exact increments require recomputing the actual save baseline and must not be read as a formula change.

## Jeremy Sochan

### Verified game values and relevant traits

In the current October 20 disposable new save, engine OVR/OFF/DEF were 59.1/52.8/68.9 and displayed 79.1/72.8/87.1. Saved baseline minutes were 25.0; the active runtime rotation projected 26.84. This is a rotation outcome, not a health effect. An earlier July-start probe assigned 0.0 minutes and displayed OVR 75.3; do not treat that older rotation-specific value as the current entry-point result. Before rotation, canonical engine OVR/OFF/DEF was 56.9/52.8/68.9 and card-scale 76.9/72.8/87.1. July 28 current ability is 52.57 and potential 60.41. Relevant traits: `shooting_range=49.50`, `release_speed=42.88`, `shot_versatility=49.71`, `handle_pressure=48.75`, `passing_reads=60.24`, `defensive_effort=72.62`, `foot_speed_lateral_agility=70.60`, `screen_navigation=71.69`, `rim_deterrence=68.24`, and `offensive_rebounding=76.81`. July health is active with no current injury ID.

### Evidence split by date

**Available by July 28:** In 28 Spurs games before being waived in February 2026, Sochan played 12.8 minutes per game, averaging 4.1 points, 2.6 rebounds and 1.0 assist; he shot 25.7% on 35 threes and did not start. This supports a clear concern about 2025-26 offensive output and role stability. It is a small three-point sample and a narrow Spurs role. NBA G League's official release records 16 additional games with New York after the waiver; the 28-game Spurs row is not a full-season line. In 2024-25 he had a larger Spurs role (54 games, 25.3 minutes, 11.4 points, 6.5 rebounds, 2.4 assists), evidence that the low 2025-26 role is not a stable measure of his entire NBA contribution.

**Later evidence relative to the inspected source:** Portland's roster lists his signing on August 2, after the July 28 canonical start. That date precedes the verified October 20 save start, so the signing is eligible for a properly refreshed entry roster. The inspected canonical roster and contract are still not corrected by changing the save date. This is a roster/contract alignment issue, not evidence for lowering or raising his traits; no later performance claim is used to justify a trait change.

### Comparable scale check and recommendation

The current shooting scale already sits below neutral: release 42.9 and range/versatility around 49.5. That is materially weaker than the game’s Aaron Gordon comparator (release 65, range 67, versatility 48) and is compatible with Sochan's poor recent three-point result. Conversely, his defense and rebounding traits are not extreme relative to specialist examples: game comparator Ausar Thompson has defensive effort/lateral/screen-navigation near 96.7 and offensive rebounding 89.8, well above Sochan's 70–77 range. The 2025-26 role collapse does not establish that Sochan's already-distinct defense, mobility or rebounding traits are inflated.

**Recommendation:** Leave all existing traits, current ability and potential unchanged for now. Do not make the broad user-suggested downward adjustment: available evidence identifies a shooting/role concern that the existing profile already expresses. A further shooting decline needs a larger or more representative shooting sample, while a lower overall would also reduce the defensive/rebounding value that current evidence does not refute. Revisit the `shooting_range` or `shot_versatility` component only if a multi-season or role-adjusted sample confirms sustained inability to provide spacing; do not lower `release_speed` from accuracy results alone.

**Expected impact:** No change to OVR/OFF/DEF. If future evidence supports only a shooting-trait decrease, OFF and OVR would fall slightly while DEF would remain nearly unchanged; that is not recommended from this evidence alone.

## Luka Dončić

### Verified game values and relevant traits

In the current October 20 disposable new save, engine OVR/OFF/DEF were 70.8/83.4/47.5 and displayed 88.6/96.0/67.5. Saved baseline minutes were 30.0; active runtime rotation projected 31.87. An earlier July-start probe projected 30.4 and displayed 88.3 OVR. Before rotation, canonical engine OVR/OFF/DEF was 71.3/83.4/47.5 and card-scale 88.9/96.0/67.5. Current ability/potential fields are not stored. Relevant traits include `shooting_range=84.60`, `release_speed=79.03`, `shot_versatility=68.54`, `handle_pressure=88.86`, `passing_reads=95.00`, `rim_pressure=82.85`, `playoff_translation=84.00`, `portability=66.08`; defense is represented lower (`defensive_effort=42`, lateral agility 32, screen navigation 36, rim deterrence 42). July health state is active, with no current injury ID and no injury-driven player-card multiplier.

### Evidence split by date

**Available by July 28:** His completed 2025-26 season produced 33.5 points per game, the scoring title, fourth in MVP voting and first-team All-NBA recognition. That strongly supports elite current offensive output. It does not on its own establish elite defense, every shooting subskill or a particular overall formula weight.

**Later evidence:** No post-July result is used for the proposal. If a later save includes an injury or fatigue state, that save's effective availability must be evaluated separately from this July healthy-ability snapshot. The current player-card action separates health risk from the three headline rating fields.

### Comparable scale check and recommendation

The current trait mix already represents elite creation: handle 88.9 and passing 95 are near the top of the internal scale, while range 84.6 and rim pressure 82.9 are also high. On the same data, Trae Young has 91 handle/93 passing but low defensive traits, and Jalen Brunson has 87.7 handle/83.9 passing with higher release/range traits. Luka's 84 playoff translation is below the in-game SGA 88 but above the example Brunson 79.8; no single peer proves an adjustment. The display crosswalk is decisive for the perceived mismatch: the 71.3 engine overall becomes 88.9 card OVR, and 83.4 offense becomes 96.0 card OFF.

**Recommendation:** Leave all underlying Luka traits unchanged. Do not raise traits solely to reconcile the former mistaken 71.3-as-card-OVR reading. A review of the OVR weighting could be a separate calibration project, but this task explicitly does not alter the OVR formula, and the high OFF / 96.0 displayed offensive rating is already consistent with the cited scoring season. Defense remains an intentional component weakness rather than a reason to depress offensive traits.

**Expected impact:** No change to OVR/OFF/DEF. If an independent, broader season-by-season review later supports a trait change, it should target that evidenced component; no direction is recommended now.

## Decision boundary

The intended game start is October 20, 2026, just before the regular season. The user considers offseason podcast claims broadly current for that start unless a dated injury, trade, signing or other material event changes the context. The proposal's underlying game snapshot and verified save still use a July 28 canonical rating/roster source; this is a data-alignment gap, not an unresolved choice about the intended game start. All claims remain source-dated, and post-start evidence is not represented as known before the opener. No prospect-system growth, potential mechanic, injury model or OVR formula change is proposed. The Harper +2 passing-read proposal remains unapproved; the Sochan and Luka recommendations are to leave ratings unchanged on the current record. Exact current card values and rotation projections are captured in `DISPLAY_VALUE_TRACE.md` and `probe_artifacts/player_card_probe_window_release_20261102.json`.
