# Feedback for E2 from the adapter check (Claude, 2026-11-16)

I ran `trait_adapter.py` (the Stage 1 bridge) on your current `player_inputs_2026_27.json` for all 691 players and compared the derived legacy traits with today's traits. Your output format works as-is. Thank you for the stable contract.

## What's working
Where players have their own evidence, the derived traits track the current ones and often improve on them. Rank correlations: rim deterrence 0.64, shooting range 0.60, offensive rebounding 0.60, release speed 0.55, passing reads 0.52. Example: Knueppel's release speed goes from 64 to 94, which is plausible.

## The problem: flat priors erase distinctions
86% of records are priors. Where a trait leans on prior-heavy inputs, the derived trait barely correlates with today's:

| Trait | Rank correlation |
|---|---|
| defensive_effort | 0.06 |
| stamina_cardio | 0.05 |
| foot_speed_lateral_agility | 0.08 |
| screen_navigation | 0.09 |

Defensive effort derives to **56.0 for SGA, Wembanyama, Curry and Gobert alike**: the same prior. Shipping that would make players *more* alike, which is the opposite of the project's goal.

## Requested changes (please fold into E2 before marking review)
1. **Player-specific priors.** When there is no direct evidence for an input, build the prior from that player's related evidence, with appropriately wide uncertainty and labeled as a prior:
   - Old traits as *weak* evidence, e.g. `defensive_effort`, `foot_speed_lateral_agility`, `screen_navigation`, `stamina_cardio`, `scheme_iq`. Keep it explicitly sourced as `legacy_trait_prior` and never presented as a measurement.
   - Box-score and play-type stats, minutes and workload, and the defensive role and position mix.
   - Height, weight and wingspan for the physical families.

   Shrink toward position or role, but don't collapse to it. Two starters at the same position with very different old trait values should not get identical priors.
2. **Check Wembanyama.** He derives about 50 on shooting, release and passing, which suggests his stats row didn't join (name or accent?). Please report any high-minute players (over 1,000 minutes) whose skill rows failed to join.
3. Add a summary to your report: for each input, the standard deviation of values across players with at least 1,000 minutes. Any input with near-zero spread across real rotation players is a red flag.

4. **Shot-location tendency (T02) is a prior for all 691 players**, but it is directly observable: three-point attempt rate, rim and close attempts, and play-type mix (Crafted `threePAr`, `3PAp75`, `LT_06`/close-shot data; ESPN 3PA/FGA). Please estimate T02 per player from those, and likewise any tendency with observable frequency data (T01 drive/shoot/pass mix, T03 catch versus pull-up, T09 cutting, T11 roll/pop where play-type data exists, T12 offensive crashing).
   **Why it matters:** with the new ratings switched on, the real-stats scorecard shows three-point attempts per 36 error tripling (0.52 to 1.65), because shot volume currently carries no player-specific information.

**Scorecard baseline** (real 2025-26 stats, 1,230 simulated games, 150 high-minute players; average error per 36 minutes):

| Stat | Old traits | New inputs (your current output) |
|---|---|---|
| Points | 2.9 | 4.1 |
| Field-goal attempts | 1.96 | 2.59 |
| Three-point attempts | 0.52 | 1.65 |
| Assists | 1.11 | 0.96 |

League-level metrics are unchanged (12 of 18 in band either way). The goal is for your revised output to beat the old-traits column.

The adapter reads your records unchanged. No schema change is needed for any of this.
