# Offline defensive-input reconstruction

Read-only experiments, never imported by production. No canonical, save,
coach, rotation, GUI, growth or economic rebuild is performed.

```sh
PYTHONPATH=src:.:tests .venv/bin/python -m unittest test_defensive_input_reconstruction -v
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_input_reconstruction.py --reference output/defensive-input-reconstruction-2026-11-11/run1/fixed_reference.json --output /tmp/defensive-inputs-new
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_defensive_input_experiment.py --reference output/defensive-input-reconstruction-2026-11-11/run1/fixed_reference.json --rows output/defensive-input-reconstruction-2026-11-11/audited/evaluated_source_rows.json --output /tmp/defensive-inputs-timing-new.json
```

Use a fresh output directory. The checked-in experiment's reference is frozen
from the original 526-row source, identified by SHA. Omitting `--reference`
creates a new experiment reference; that is a deliberate version fork, NOT
an annual or per-roster recalibration policy. Reuse the reference to evaluate
new players, subsets, outliers, different membership and repeated imports.

The runner replays the actual five-trait pipeline for all 691 current players
without constructing markets or a full new universe. It observes real
pre-clamp arguments during subjective calibration and asserts exact current
values, components, source metadata and confidence. It also keeps explicit
unrecoverable historical latent values; current100 is never reversed to108.

`stages.csv` contains all 3,455 trait rows through the stages, including current,
pure range-only, fixed-reference A and evidence-separating B experiments.
`players.json` contains raw fields, source contributions, full current
components, stage traces, reviewed override status, sample limitations,
neutral-impact/no-role attribution counterfactuals and B weight sensitivity.
`summary.json` contains distributions by role/size/position/sample, structural
source overlap, source/tie coverage, rank changes, review-hold conflicts and
existing prospect-conversion scale comparisons. No new prospect is generated.

A is deliberately a contrast: the existing proxy equations, role boosts and
questionable evidence remain. B does NOT recycle steals/impact into effort,
feet and screen technique. It reports event and protection proxies plus a
separate general-impact context; unidentifiable skills are unknown. Its
85%block/15%height protection hypothesis is unvalidated, not points prevented.
The fixed mapping and headroom are deterministic modeling examples, not
validated skill anchors. Absolute recorded overrides are reapplied, and
research HOLD conflicts are reported rather than silently erased.

No complete candidate is accepted for production. See
`docs/DEFENSIVE_INPUT_RECONSTRUCTION_2026_11_11.md` for blocking evidence and
the concrete next integration gate. Roles remain experimental.
