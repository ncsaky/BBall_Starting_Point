# Starting-Roster Versions

New games use `2026-10-23-forward-tuning-v5`. Established games keep the starting dataset recorded in their save. Updating or rebuilding the application does not automatically rerate those careers, remove earned development, move players, or rewrite their contracts.

The versioned snapshots and their registry are under `data/canonical/baselines/`. Each released starting version must retain its immutable snapshot when a later version is published. Unrecognized versions fail explicitly rather than silently adopting the latest ratings. Older unversioned saves use the existing hash/legacy-version mapping.

## Roster V2

This version corrects a limited set of imported-roster input inconsistencies:

- Recent 2022-2025 draftees use bounded NBA-role priors where their older inferred profiles are weak. This is not a uniform overall bonus or a minimum for every draft slot.
- Missing play-type measurements are distinguished from measured or manually authored zero traits. Manual overrides remain authoritative, and established non-shooters retain their shooting weaknesses.
- Prior NBA workload uses the two seasons before the game starts, with the older season downweighted. A short injury season does not discard the preceding sample. Future statistics are excluded.
- Recent players receive age- and opportunity-limited remaining-upside metadata. The existing development, realization, health and aging rules remain unchanged.

The already-calibrated 2026 rookie traits are unchanged. Strong existing profiles are preserved. Ratings-derived asset and market tables are rebuilt so this is an engine-data correction, not a cosmetic display change. Identities, contracts, draft-pick ownership/protections, and existing injuries/return dates are preserved.

`src/nba_gm_data/roster_alignment.py` contains the input policy. The canonical metadata's `roster_alignment_report` and individual traits' `components.roster_alignment` record the prior, adjustment, reason, and supporting career sample. These are modeled priors, not measured NBA skill grades.

The position-insensitive overall formula has not changed. Its treatment of some specialists remains a separate issue. This correction also does not establish that every future class or the league's long-term talent distribution is perfectly calibrated.

## Player Tuning V3

V3 builds on V2 and corrects only Kyrie Irving, Dereck Lively II, Collin Murray-Boyles and Keyonte George. The targeted scouting overrides run after the general alignment so they cannot change other traits' alignment priors. Supporting URLs are retained in each corrected trait's `components.manual_calibration`. The rationale and limits are documented in `docs/PLAYER_RATING_CALIBRATION.md`.

The V2 archive remains immutable. Prospect development, future draft generation, contracts, pick terms and existing injuries are not changed. This is a new-game baseline, not a forced correction to an established career.

## Talent V4

V4 additionally opts into versioned skill diversity, role-aware overall/simulation value and generated per-trait career capacity. Imported traits retain the V3 corrections exactly. Earlier careers do not silently adopt the new generation, valuation or plateau rules. See `docs/TALENT_MODEL_V2.md` and `scripts/verify_talent_balance.py` for scope and verification.

## Forward Tuning V5

V5 retains V4's model and changes only Aaron Gordon's and Julius Randle's underlying profiles. See `docs/FORWARD_RATING_CALIBRATION.md` for evidence, tradeoffs and limits. Prospect generation, development, all other player traits, medical state, contracts and pick terms are unchanged. Dependent team needs and markets are rebuilt. V4 careers remain pinned to V4, including earned development.

`tests/test_forward_tuning.py` checks exact scope, downstream simulation and AI valuation, old-career preservation, new-game pick terms, deterministic builds and seeded game replay. `scripts/verify_forward_tuning.py --publish` verifies scope and preservation before writing the immutable V5 archive and canonical outputs. Evidence is under `output/forward-tuning-2026-10-23/`.

## Verification

`scripts/verify_roster_alignment.py` creates disposable comparison saves, checks a normalized old-save week for identical outcomes, measures controlled recent-player development, and runs checkpointed full-game careers. Audit artifacts live under `output/roster-alignment-2026-10-23/`. They are not playable saves or release packages.

To see the corrected starting roster, create a new game with the updated development build. Continuing an older save intentionally retains its previous baseline. No automatic or opt-in migration is included in this change.
