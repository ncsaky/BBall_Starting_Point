---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/draft
  - gameplay/scouting
  - project/nba-gm
---

# Draft Lottery And Scouting

## Responsibility

[draft.py](../../../src/nba_gm_data/draft.py) owns draft-class records, future class generation, scouted views, team boards, selection scoring, rookie contracts/onboarding, and draft-trade support. [save.py](../../../src/nba_gm_data/save.py) owns the live lottery and draft state, exact pick order, protection/swap resolution, advancement, and persistence.

## Two Prospect Sources

- The 2026 class is researched and attached to the initial data foundation.
- Future classes are generated deterministically with variable archetypes, ages, positions, heights, trait profiles, potential, floors, and ceilings.

Generated prospects must use the same trait vocabulary and plausible distributions as the calibrated NBA player pool. Otherwise development and simulation would put rookies in a different numerical universe.

## Scouting Fog

The true prospect record is not identical to what every team sees. Scouted Now, Potential, Floor, and Ceiling incorporate:

- prospect uncertainty;
- scouting staff quality and specialties;
- team-specific board context;
- deterministic noise for reproducibility.

One shared scout-display helper should power board, picker, and report screens so the same team does not see contradictory estimates before the draft. After selection, the dashboard shows actual engine/display ratings rather than the pre-draft estimate.

## Lottery

Lottery generation uses weighted odds and a random seed stored with the save. An omitted interactive seed should produce fresh draws across saves; an explicit seed remains reproducible.

Protection and swap obligations resolve against the lottery result before the final owner order is persisted and displayed. Odds may show original team plus ownership/protection context, while reveal rows must show final resolved owners.

The lottery reveal, draft summary, asset list, and live queue all need one saved order. Rebuilding draft state from stale baseline owners was the source of earlier mismatches.

## AI Selection

AI selection balances:

- best player available;
- team positional and skill needs;
- timeline and expected role;
- scouting confidence;
- roster redundancy;
- prospect tier and uncertainty;
- controlled seed-based variance.

Top picks are more stable; lottery picks have moderate variance; late firsts and seconds can vary more among comparable tiers. A redundant small offense-first guard is penalized for a team with an elite primary creator unless the talent gap is large enough to justify best player available.

## Draft Pick Value Curve

Pick value is steep at the top, especially #1, then gradually compresses. Late-first and early-second picks should be neighbors, but #1 cannot be acquired from #6 with only a future second. Draft-class quality and available prospect tiers affect context, yet top move-ups normally require future first-round value or a major player/prospect.

The curve has two common failure modes:

- too flat at the top, creating cheap dramatic move-ups;
- too discontinuous at the first/second boundary, overvaluing #30 relative to #31.

Tests should cover monotonic local comparisons and package-level move-up requirements.

## Draft-Night Trade Market

Before AI selections, a pick-centered market can run:

- buyers trade up for a high-fit at-risk prospect;
- sellers move down when no prospect separates or several are interchangeable;
- multiple offers for one pick resolve to the best accepted package;
- user-owned picks are excluded from autonomous trades;
- one pick cannot be traded twice in the same draft;
- breaking-news UI aggregates trades between visible pauses;
- single-pick, sim-to-user, and full-draft flows all use the same hook.

Activity is intentionally concentrated in the top 25 and bounded to avoid chaotic drafts.

## Rookie Onboarding

Drafted players receive rookie-scale contracts and are added to the active save. Initial rotation baselines use draft slot, current ability, potential, and team depth so a strong rookie does not enter at zero minutes. Current and previous-year rookies are protected from automatic cutdown logic.

## Invariants

1. Every live slot has one exact pick ID and owner.
2. Reveal, summary, assets, and selection queue agree.
3. A selected prospect cannot be selected again.
4. A traded current pick changes only that pick.
5. Scouted views are consistent for the same team/save.
6. Same-seed classes and decisions are reproducible.
7. Top-tier prospects remain relatively stable while same-tier later picks can vary.
8. Rookie contracts and roster onboarding are applied once.

## Source And Configuration

- [Draft module](../../../src/nba_gm_data/draft.py)
- [Draft model v1](../../../data/overrides/draft_model_config.json)
- [Save lottery/draft orchestration](../../../src/nba_gm_data/save.py)

## Related Notes

- [[Systems/Pick Obligations and Swaps]]
- [[Systems/Ratings and Traits]]
- [[Architecture/Determinism and Identity]]
