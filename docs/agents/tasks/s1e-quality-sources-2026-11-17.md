# S1-E: the two quality numbers the AI reads (2026-11-17)

Companion to the detailed cutoff inventory in `s1e-threshold-inventory.md` (Codex, accepted). This note adds the structural finding below.

Read-only sweep (sonnet subagent, reviewed by Claude). Purpose: Stage 1 step E. Before the front office reads
the new ratings, list every place that reads OVR/OFF/DEF and every hard-coded cutoff.

## Key structural finding

There are **two separate quality numbers** in the engine:

1. **Summary OVR/OFF/DEF** (`save.py` `_uncached_player_attribute_summary`). This is a weighted average of the 15
   hidden ratings plus a minutes bonus, clamped 1–99. It drives rotations, minutes buy-in, free-agent priority
   and archiving, released-player salary, awards, trade *wants* text and the player-card header today.
2. **Market on-court value** (`transactions.py` `player_on_court_value`, ~:4200). It is built from game
   *features* (`impact*.42 + usage*.09 + shot_creation*.08 + spacing*.08 + rim_pressure*.06 + passing*.07 +
   defensive_events*.07 + rim_deterrence*.07 + portability*.06 − weak-link penalty`). It drives trade value,
   contract asks, role tiers, superstar floors and value caps.

The trade and contract market therefore does **not** read the summary OVR. Rescaling the summary does not touch
the market cutoffs. Star compression in the market comes through the game features.

## Cutoffs on the summary scale (need percentile re-expression if the summary scale changes)

| Where | What |
|---|---|
| save.py:7767 `public_player_role` | star ≥82, starter ≥74, rotation ≥64 |
| save.py:8430, 8963 | free-agent archive / "meaningful" at 58 / 53 / 50 |
| save.py:8968 `released_free_agent_salary` | 2.25M + minutes·0.5M + (overall−55)·650k (waivers.py:40 and release_planning.py:133 inherit it) |
| save.py:6683–6708 | rotation caps/floors at 75 / 68 / 61 |
| play.py:1272–1345 `coach_minutes_buy_in` | role 76 / 65 / 56, 72, teammate gap +2.5, fit cutoffs on shooting/creation/defense/rebounding |
| play.py:5074 | FA "stronger same position" +2.5 |
| app_actions.py:3113 | projected fit pivot 60 |
| app_actions.py:1096 | "star signed" headline ≥85 |
| trade_wants.py:190–320 | want conditions ≥52/56/55/53/50, comparisons +1 |
| save.py:8140 awards | DPOY defense pivots 70/80, rim deterrence 85/70 |
| dashboard_metrics.py:28 | expected win% divisor 50 |
| extension_analysis.py:111, narrative.py:957 | deltas 4 |
| fantasy_draft.py:~155 | blends engine overall with a reviewed prior overall (scale must match) |

Linear uses (scale-dependent weights): roster_cut_score, ai_roster_retention_score, auto_starting_five,
ai_role_targets, team_rotation_projection, MVP/ROTY scores, FA priority, team identity depth.

## Market cutoffs (on-court value scale; unaffected unless on-court value changes)

transactions.py: superstar floor (on_court ≥79, playoff ≥80); premium anchor 76.5/76 (also :3875,
multi_team_trades.py:249/260); value caps 124/118/112 at on_court 86/82; star floors at 72/66; surplus gates
(<80, ≥74); negative-surplus gates 74/70/66/62; surplus_quality_factor pivot 60. contract_ai.py:960–1000
role tiers (on_court 58/61/64/66; value 78/84/90) drive asking salary. team_planning.py is already
percentile-based. draft.py prospect floors (ability 58/56/57/55, value 68).

## Implication for Stage 1

- The input-derived traits flow into **both** numbers. Fixing star separation at the trait level (BBI evidence,
  and keeping technique separate from volume tendencies) fixes both at once, with no threshold rewrites.
- Replacing the summary with the 94-input profile composite (the original S1-E plan, step 1) would need the
  summary-scale cutoffs above re-expressed. It would still leave the market on its own feature-based value, so
  the card and the market could disagree.
- **Recommendation:** keep the engine's numbers as the source of truth (the card header already shows the AI's
  own numbers). Put the Stage 1 effort into making the input-derived traits right. Revisit the composite only if
  the user wants the card's OVR to be the profile composite.
