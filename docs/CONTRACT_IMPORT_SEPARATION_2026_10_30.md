# New-career contract separation — October 30, 2026

New careers on **2026-10-30-contract-separation-v10** separate Damian Lillard's Portland active contract from Milwaukee's former-team gross stretch reserve. Existing careers remain pinned to their previous immutable baseline; no load-time migration or automatic repair is provided.

| Component | 2026–27 | 2027–28 | 2028–29 | 2029–30 |
| --- | ---: | ---: | ---: | ---: |
| POR active salary | $13,398,800, guaranteed | $14,104,000, pending player option | — | — |
| MIL gross planning reserve | $22,516,603 | $22,516,603 | $22,516,603 | $22,516,603 |

Portland's original signed term is three seasons, 2025–26 through 2027–28; two scheduled seasons remain at entry. Milwaukee's original stretch schedule has five installments, 2025–26 through 2029–30; four remain at entry. The original waived contract duration is **unknown**, not five years. Milwaukee set-off and net charges are **unknown/unverified**, not zero. The existing financial model uses the explicitly disclosed gross reserve conservatively; `unverified_waived_reserve_millions` exposes that assumption. No set-off formula or no-trade protection was inferred.

## Evidence and import boundary

The read-only research finding is [CONTRACT_IMPORT_FINDING.md](ratings-evidence-2026-10-29/CONTRACT_IMPORT_FINDING.md). The retained Basketball-Reference artifact has MIL and POR rows repeating the same aggregate annual schedule. It was already aggregated at source; the importer did not add the two rows together. The retained HoopsHype component rows reconcile exactly: $13,398,800 + $22,516,603 = $35,915,403, and $14,104,000 + $22,516,603 = $36,620,603.

Public reporting supports the distinct [Portland three-year agreement](https://www.nba.com/news/damian-lillard-to-return-to-trail-blazers) and [Milwaukee waiver](https://www.nba.com/news/bucks-waive-damian-lillard). Exact annual components and the option flag come from the retained salary artifact; this work does not establish an exact net Milwaukee charge.

`data/overrides/contract_import_resolutions.json` retains source IDs, retrieval metadata, exact aggregate rows, exact component rows, artifact paths and evidence links. `contract_imports.resolve_contract_imports` checks the known aggregate signature before matching active contracts, preserves its rows as aggregate evidence, and appends the separately sourced active component. The ingestion boundary also verifies the retained component rows. A changed or duplicated source signature fails closed for review. This is one explicit evidence resolution; it does not guess at other ambiguous contracts. No player-name condition was added to runtime financial or trade logic.

The canonical universe now has a separate `waived_salary_obligations` collection, serialized in JSON and SQLite. New-save creation copies its remaining rows once into the existing save ledger, before runtime planning. IDs derive deterministically from evidence, former team and stretch range. Repeated initialization cannot double the reserve, overwrite amended relief, or resurrect a deliberately removed obligation. Player trades and fantasy allocation move the active agreement through existing ownership logic; Milwaukee's ledger remains Milwaukee's.

## Career isolation and data scope

Only new creation invokes obligation initialization. Reads, repairs and settlements do not seed this import. Existing baseline archives are byte-identical to their pre-edit hashes. The registry adds only v10; all prior version/hash mappings and the legacy fallback are unchanged. Old fixtures with a trade, extension, exercised/declined option override or waiver produce the same defaults, active contracts and real player-card responses against the new application input, without rewriting their files.

Underlying teams, players, traits, roster slots, health profiles/states, injury/development events, picks, staff, front-office/team profiles, draft classes/prospects/traits and scouting reports are unchanged. Exactly one active contract changes. This full canonical rebuild also regenerates derived valuations, market profiles/preferences, extension/free-agent candidates, strategic states, trade-block entries, draft-board fits and coverage under the **existing current builders**; these collections are not claimed byte-identical to the earlier generated v9 artifact. No model, rating, roster, market-policy, rotation or RNG algorithm was changed to obtain those outputs. Older careers continue using their old baseline.

Changed data/baseline files, exhaustively:

- `data/overrides/contract_import_resolutions.json` — new evidence resolution.
- `data/canonical/universe_2026_27_offseason.json` — rebuilt v10 universe.
- `data/canonical/universe_2026_27_offseason.sqlite` — matching universe and separate ledger table.
- `data/canonical/baselines/2026-10-30-contract-separation-v10.json.gz` — new immutable archive.
- `data/canonical/baselines/registry.json` — one additional version mapping.

Backend changes are limited to `contract_imports.py`, `ingest.py`, `schema.py`, `storage.py`, the creation hook in `save.py`, and the version constant in `roster_alignment.py`. Added evidence capture: `scripts/capture_contract_separation.py`. Tests: new `tests/test_contract_import_separation.py` and a debt-aware assertion update in `tests/test_contract_protection.py`. Research-owned files and shared GUI files were not edited. Completed settlement/performance and pre-opening-start code remains intact.

## Financial and regression verification

Evidence root: `output/lillard-contract-separation/`. `reference/src/`, `canonical-before.json`, `registry-before.json` and `pre-edit.json` preserve the pre-edit backend/data identity. `before/` and `after/` contain disposable real `create_save`/`player_card` captures. In the seed-17 Portland career, 2026–27 team payroll changes as follows:

| Team | Before | After |
| --- | ---: | ---: |
| POR | $216,759,719 | $194,243,116 |
| MIL | $163,578,961 | $186,095,564 |
| Combined | $380,338,680 | $380,338,680 |

The same $22,516,603 shift holds for each remaining stretch season; neither team has a Lillard charge in 2030–31 under this agreement. The card lists $13.4m / $14.1m and no subsequent active salary. Query/reload repetition preserves the file and single ledger entry. SQLite contract/ledger content matches JSON, and the new archive exactly matches the published universe. `publication.json` and `data-verification.json` record those checks.

**59 unique focused tests pass** across contract import (11), new-career entry (8), protection (17), block-term presentation (2), salary application (11) and settlement materialization (10). Coverage includes source drift/duplicate refusal, guarantees/options, deterministic/idempotent seeding, reserve expiry, real cards/caps, old-career preservation, a fully applied bilateral ownership transfer, actual fantasy completion, fresh/stale/sequential settlements, protected terms/swaps, human rotations and unchanged bilateral/full-fallback behavior. Startup action tests advance only the first two game dates; no season study was launched.

The initial 58-test run found one existing action test whose two seed subtests assumed the entire initial debt ledger was empty. The corrected test now asserts the imported debt remains exact and one waiver is added; duplicate actions must preserve the entire resulting ledger. That test passes in `regression-correction.txt`. An added fantasy probe initially guessed an unsanitized filename; it was corrected to use the actual create response path and passes in `fantasy-verification.txt`. The other 57 original tests passed in `regression.txt`. `tests.json` records these runs explicitly.

There is no existing player-option exercise/decline action engine. Tests preserve the pending flag and use the model's existing explicit contract overrides for exercised/declined states, then execute the real offseason expiry transition with unrelated AI signing/retirement isolated. They do not claim to implement or verify a nonexistent option-decision workflow. The current financial model continues to count a pending scheduled option in budget forecasts. No option policy was added here.

Reproduce sequentially from the repository root:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_contract_import_separation test_new_career_start test_contract_protection \
  test_block_contract_terms test_trade_salary_application test_settlement_materialization -v

# Refuses an existing destination; setup/card/cap capture only, no simulation.
PYTHONPATH=src .venv/bin/python scripts/capture_contract_separation.py \
  --canonical data/canonical/universe_2026_27_offseason.json \
  --output output/contract-separation-repro-current

# Rebuild into a disposable directory, never over an archived baseline.
PYTHONPATH=src .venv/bin/python -m nba_gm_data.cli build --root . \
  --out output/contract-separation-repro-build --quiet
```

The verified isolated preview is **http://127.0.0.1:8794/**, using `output/lillard-contract-separation/preview-saves/contract_verified.json`. `preview.json` records the actual process, backend hashes, baseline version and real HTTP card/POR/MIL cap assertions. Existing previews and playable saves were left alone. No performance measurement hold was imposed on the UI or research chats.
