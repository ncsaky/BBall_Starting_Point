---
type: data
status: current
reviewed: 2026-07-10
tags:
  - data/provenance
  - architecture/data
  - project/nba-gm
---

# Data Provenance And Trust

## Philosophy

The canonical metadata describes the foundation as “public/cited, rotation-first, confidence-aware.” This means:

- public evidence is preferred over hidden/manual guesses;
- rotation-relevant players receive the deepest data effort first;
- missing or uncertain data is represented explicitly;
- raw inputs are evidence, not canonical truth;
- manual overrides are visible and reviewable rather than buried in code.

## Source Classes

The repository includes research/cache material from sources such as:

- ESPN schedules, box scores, coaches, and draft information;
- Basketball Reference staff and contract information;
- NBA.com team and staff information;
- Spotrac future-pick/contract context;
- odds and tracking-derived inputs;
- manual full-league ratings and gameplay calibration files.

At the reviewed snapshot, canonical output registers 37 source records with trust level, path/URL, retrieval context, and notes.

## Trust Is Field-Specific

A source can be authoritative for one fact and weak for another. Examples:

- Team roster listings are useful for membership but not necessarily future salary detail.
- Public contracts may omit uncertainty around options or guarantees.
- Box scores are strong evidence for historical stats but not direct truth for a player's future latent trait.
- A human ratings CSV is a useful prior for ranking basketball ability but is subjective and full-health by design.

Trust should therefore attach to records/fields and transformation purpose, not merely to a website name.

## Research Caches

Build-time research is cached under `data/research/` so canonical rebuilds do not depend on live network availability or shifting pages. This improves reproducibility and allows the exact evidence used in one build to be inspected later.

The tradeoff is staleness. Cache retrieval date and source metadata need to be visible so a later updater knows whether a “missing” player is genuinely absent or merely newer than the snapshot.

## Coverage Issues

Canonical output includes explicit coverage issues rather than silently inventing all missing data. At this snapshot, 179 coverage issues remain. Missing-data playtests have repeatedly found heights and contract fields, demonstrating that coverage auditing should be a normal build output and GUI/admin view.

## Manual Overrides

Overrides correct known gaps or impose intentional gameplay judgments. They should include:

- the player/staff/pick identity;
- the corrected field/value;
- effective date or season where relevant;
- reason/source note;
- distinction between factual correction and gameplay tuning.

Without that distinction, future maintainers cannot know whether to replace an override when new source data arrives.

## Reproducibility Checklist

1. Keep source snapshots or research cache entries.
2. Record source metadata and retrieval context.
3. Version transformation/config files.
4. Keep matching audit output, especially aliases and unmatched rows.
5. Build canonical data deterministically.
6. Test known public anchors and known uncertainty.
7. Never fetch live web data during normal gameplay.

## Ethical And Product Boundary

Public real-world names and statistics seed a private simulation. Narrative prompts must not treat a model's memorized real-world reputation as current sim truth. The game should distinguish sourced data, simulated outcomes, and generated opinion in both code and presentation.

## Source Anchors

- [Research directory](../../../data/research)
- [Overrides directory](../../../data/overrides)
- [Canonical source registry in output](../../../data/canonical/universe_2025_26_preseason.json)
- [Research module](../../../src/nba_gm_data/research.py)

## Related Notes

- [[Data/Canonical Build Pipeline]]
- [[Data/Overrides and Model Configuration]]
- [[Systems/Narrative Engine]]
