# Offline defensive-role experiment

Not imported by `src/`, not installed in the server, and not a coaching or
rotation engine. Production DEF/OVR and player inputs remain unchanged.

```sh
PYTHONPATH=src:.:tests .venv/bin/python -m unittest test_defensive_role_prototype -v
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_role_prototype.py --output /tmp/defensive-roles-new
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_role_prototype.py --trial-inputs experiments/defensive_roles/castle_research_sensitivity.json --output /tmp/defensive-roles-castle-new
```

Output directories must be new. The JSON contains all current canonical
players' six scores, input coverage/source confidence, limitations, reasons,
primary/secondary suggestions, current-engine reference, sensitivity tests,
five-player contexts and same-identity replacement controls. `scores.md` is a
16-player readable selection. `--observations` accepts a name-keyed object
with `jobs` and `note`; those fields cannot change scores. Imported source
role labels are explicitly not independently verified assignment shares.

`castle_research_sensitivity.json` reproduces an older **held** research
candidate, not an approved correction. It changes only private inputs; the
runner never writes canonical data, saves, engine modules or UI.

Each role score is a declared weighted trait blend with a disclosed critical
channel cap. Missing traits use prior35 and confidence0. These are unvalidated
proxy estimates; source confidence is inherited metadata, not a probability
that a role grade is accurate. Current inputs do not independently measure
containment, contact strength, help timing or recovery range. An uncertain
player can have a score, but cannot acquire measured-role status from it.

`assign` exactly optimizes a declared reference objective over one-percent
responsibility units. Five players each get one unit; opponent demands total
five. Jobs are exclusive bookkeeping buckets over time, not a claim all
basketball tasks are independent or mutually exclusive on a possession.
Every body can attempt every job; one optional soft wing-size mismatch
hypothesis is separate from base skill. Rim already incorporates effective
size and receives no additional height factor. There are no position bans.

`summarize` reports a usage mean and a demand-capped coverage index separately
from production DEF. Both are experimental grade bookkeeping, not expected
points prevented. Sheltering supplies no skill credit; excess supply to an
easy role cannot substitute for an uncovered job. These rules prevent max-role
and duplicate-credit artifacts but do not establish a calibrated defense model.

See `docs/DEFENSIVE_ROLE_PROTOTYPE_2026_11_11.md` for results, rejected design
choices, the held-input experiment, source limitations and production gates.
