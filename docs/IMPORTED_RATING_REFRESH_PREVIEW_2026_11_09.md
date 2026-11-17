# Imported input refresh preview — November 9, 2026

Dry run only. Owned artifacts: this document and `output/imported-rating-refresh-preview-2026-11-09/`. No scouting proposals, production ratings, version bump, career migration, GUI, preview restart or season simulation is authorized or performed. Research's independent player judgments are not inputs to this experiment.

## Source contract and experiment

Read the existing audit at `docs/ratings-evidence-2026-10-29/IMPORTED_INPUT_SOURCE_AUDIT.md`. The skill artifact is generated March 11, 2026, with March 5 public augmentation; its exact strict-provider per-player cutoff is not retained. The career artifact is retrieved October 14, 2026 and contains ESPN **2025–26 regular-season** totals (`seasontype=2`). The released v10 universe combines preserved baseline values with later partial corrections. Neither old source metadata nor a July baseline proves every current trait is stale.

`dry_run.py` joins the original **526-player population** to canonical ESPN IDs, checks normalized names and athlete URLs, and finds **515** positive-game/minute season rows. It refreshes supported fields for the whole matched cohort before computing percentile maps. It never ranks only the five reviewed players. The other eleven rows retain their old fields: this is explicitly a **mixed-window sensitivity experiment**, not a homogeneous final-season reference scale ready for release.

| Input family | Dry-run mapping | Boundaries |
| --- | --- | --- |
| GP, MP | Season games and total minutes | Never copy `2025minutes` or projected `minutes`; neither is current availability |
| PTS/REB/AST/STL/BLK/TOV, FGM/FGA, 3PA/FG3A/FG3M, FTM/FTA | Explicit season total divided by games | Per-game values, not totals or per-75; preserve real numeric zero |
| 3P%/FG3_PCT, FG%/FG_PCT, FT%/FT_PCT | Makes / attempts, fraction scale | Zero/missing denominator does not produce a new observed percentage; leave old field and disclose it as unrefreshed |
| threePAr/3PAr, FTr | 100 × 3PA/FGA or FTA/FGA | Input rate fields use percentage scale; aliases have different old values/provider lineage, so this adopts one declared definition rather than claiming exact upstream reproduction |
| Per-75, usage/impact metrics, play types, touches, deflections, BBallIQ, tracking | Unchanged | No possession denominator, new tracking observations or measured IQ can be recovered from career box totals |
| Role minutes, prior minutes, health, role labels, physical attributes | Unchanged | This pass measures source refresh, not roster/availability policy or role retuning |

A private filesystem root links existing read-only resources and owns its own skill-input JSON. The existing `build_universe` runs on original and refreshed inputs with the full cohort and all current correction stages. Sidecars record field-level old/new values, full-season totals, athlete URL, retrieval date, trait lineage, raw trait sensitivity and final engine/display summaries. The private replacement file retains old artifact metadata intentionally; it is **not** a publishable source package. Provenance must be rewritten field-by-field in a real versioned refresh.

| Player | March GP → final GP | March total MP → final total MP |
| --- | ---: | ---: |
| Anthony Edwards | 52 → 61 | 1817 → 2135.0 |
| Devin Vassell | 48 → 67 | 1441 → 2043.5 |
| Jalen Duren | 50 → 70 | 1383 → 1974.0 |
| Cedric Coward | 49 → 62 | 1263 → 1599.6 |
| Kawhi Leonard | 46 → 65 | 1470 → 2086.5 |

These counts establish changed retained source windows, not a recommendation to increase ratings. Player-season URLs and all mapped rates are in `field-and-base-diff.json`.

## Override order and interpretation

The current importer: initial returning-player trait inference → league CSV quantile calibration → preserved returning baseline → named `players` overrides → new-player/rookie handling → roster alignment using later career evidence → health construction → stamina arithmetic repair → named `post_alignment_players` overrides → v7 imported-skill checks → v8 rotation-profile checks → downstream profiles/markets. The percentile reference uses the original returning-player cohort, excluding newly appended camp/rookie rows.

Named/manual profiles are not removed or adjusted in this dry run. Alignment skips prior manual/rookie/alignment markers; v7/v8 skip reviewed profiles and their own already-applied markers. These protections are not interchangeable: regenerating from initial source versus reapplying a correction to an already-corrected final trait can yield different results. Do not stack raw-refresh deltas on final values, apply a second roster/rookie conversion, or clear markers to force changes. A new CSV quantile endpoint can also invalidate v8's reconciliation with the preserved value; provenance affects whether a correction applies, not just the displayed input date.

Raw sensitivity already demonstrates the risk of direct delta application. Duren's missing `threePAr` becomes measured zero attempts/FGA. That adds a low component to the **portability proxy**, moving its raw value **45.64 → 30.81**, despite no new portability observation. It is not evidence to downgrade his actual portability by 14.83. The current preservation/override pipeline must be evaluated separately from this raw inference effect. Kawhi's raw shooting range moves **61.01 → 64.69**, while Edwards moves only **72.67 → 72.84**. Neither implies a manually approved final rating change.

## Release blockers and minimal future implementation

The retained data cannot regenerate a complete homogeneous full-season skill model: eleven original-cohort joins are unresolved, strict-provider lineage/cut dates are missing, and advanced/tracking/per-possession fields have incompatible or unknown windows. Missingness is not zero. Box totals alone do not supersede named scouting corrections for defense, handle, movement, IQ or portability. There is no support for blanket +1.5 adjustments in this task.

A future approved implementation should:

1. Declare a new baseline version after v10, with field/provider/season/split/units and retrieval provenance. Resolve alias and zero-attempt semantics explicitly; label missing/proxy fields instead of upgrading their confidence.
2. Choose and record a league-wide source-window/reference-population policy before replacing percentile inputs. Resolve unmatched players or explicitly freeze their reference treatment; do not silently use a five-player distribution.
3. Specify which baseline-preservation entries the measured update supersedes. Retain named corrections unless their actual evidentiary basis is superseded, and audit ordering/reconciliation before permitting final changes.
4. Adopt only for new saves through the existing versioned baseline mechanism. Existing careers keep their stored baseline/model and trait development; no silent migration or simulated career rewrite.
5. Verify deterministic rebuild/idempotence, missing-vs-zero and percent-vs-fraction cases, rate denominators, stable ID/name joins, unchanged named corrections, cohort/order stability, old-career load preservation and explicit changed/unchanged trait/summary diffs. Full-season collection/ratings implementation requires a separate decision.

## Completed result and read-only gate

Both private full-cohort canonical builds completed. The fresh original-input build reproduces the stored canonical's **all 15 numerical traits and every engine/display summary field** for each of the five players. Thus this comparison is anchored to the current output, not an assumed historical baseline.

| Player | Engine OVR before → refreshed | Display OVR before → refreshed | Final numerical traits changed |
| --- | ---: | ---: | ---: |
| Anthony Edwards | 78.3 → 78.3 | 93.8 → 93.8 | 0/15 |
| Devin Vassell | 67.5 → 67.5 | 86.0 → 86.0 | 0/15 |
| Jalen Duren | 67.1 → 67.1 | 85.7 → 85.7 | 0/15 |
| Cedric Coward | 55.5 → 55.5 | 75.5 → 75.5 | 0/15 |
| Kawhi Leonard | 79.3 → 79.3 | 94.5 → 94.5 | 0/15 |

All summary categories, not only OVR, match before/refreshed. Original player role-minute projections are retained. The engine/display transform and availability are untouched. These OVR figures are diagnostic outputs of the existing model, not independently validated scouting judgments.

`field-and-base-diff.json` enumerates all 15 raw traits per player, including unchanged ones and original final-trait lineage. `pipeline-comparison.json` contains complete before/refreshed numerical trait and engine/display dictionaries. `stored-baseline-comparison.json` verifies agreement with production's stored numeric output. Final metadata/confidence equality is **not** asserted: new raw components/field presence can change lineage even when preservation restores the same number. The experiment is not an idempotence certification of a new baseline; that remains a future release gate.

The measured-input replacement alone produces **no numerical final correction** for these five players through the unchanged pipeline. This is not proof that refreshed statistics have no basketball value. Baseline preservation intentionally supersedes raw inference, while the existing later evidence passes already consume the same retained career totals. A useful new version must explicitly decide which preserved entries to supersede and how to handle the unsupported/mixed-window inputs. No such production policy was invented here.

Two canonical calculations took **37.09 s / 15.66 s** including reads and initialization. They are modest bounded import calculations, not simulations or evidence of a speedup. No broad profiling or browser work ran. Before/after SHA-256 manifests match for **833 production canonical/source/code files**. Production inputs, the loaded preview and existing careers remain unchanged. The private root's symlinks are read-only inputs to the importer; its replacement skill JSON and all generated artifacts live only under this task's output folder.

Reproduce sequentially with a **fresh** output directory:

```sh
PYTHONPATH=src .venv/bin/python \
  output/imported-rating-refresh-preview-2026-11-09/dry_run.py \
  --output output/imported-rating-refresh-preview-2026-11-09/replay
```

The runner refuses to overwrite an existing private-root calculation. It requires no external requests or new dependencies. The preserved `hashes-before.json`, `hashes-after.json` and `verification.json` record the completed read-only gate. This handoff stops at the dry run; it does not apply manual +1.5 proposals or start a production refresh.
