# Damian Lillard contract import finding — updated 2026-11-02

## Finding

The local import source and transformation explain the apparent Portland-active-salary plus Milwaukee-dead-salary aggregation. Basketball-Reference's fetched research file contains duplicate team-tagged Damian Lillard rows whose salary schedules are already an aggregate: its Portland-tagged 2026-27 value is exactly Portland's new active salary plus Milwaukee's separate stretched salary. The importer selects the row matching Lillard's canonical current team (POR) and copies the source salary seasons as the canonical player's active contract. It does **not** add the MIL row to the POR row during `build_contracts()`; the aggregate is already present in each source row.

In the earlier v9 clean new save, I found no Lillard-specific Milwaukee dead-salary obligation seeded in the save ledger. That defect was a **misassigned aggregate**: Portland's active Lillard contract was overstated, while Milwaukee's separate obligation was omitted from Milwaukee team payroll. It was not double-counted in that save; adding Milwaukee's obligation without first correcting Portland's active schedule would have created a double count.

## Current v10 state verified in a new save

The current baseline is `2026-10-30-contract-separation-v10`. A later provenance resolution is present in `data/overrides/contract_import_resolutions.json` and `src/nba_gm_data/contract_imports.py`. It signature-checks the duplicated aggregate Basketball-Reference rows, excludes them from active matching, then imports a sourced Portland component contract and a separate Milwaukee gross waived/stretch obligation. The current one-save probe created exactly one MIL Lillard obligation; the player-card action lists only $13,398,800 (2026-27) and $14,104,000 (2027-28 player option), while payroll reports Portland waived salary $0 and Milwaukee waived salary $22.52m in each remaining season through 2029-30. The obligation's set-off amount, net salary and net cap charge remain null/unknown. See `probe_artifacts/player_card_probe_window_release_20261102.json` for raw action and payroll payloads.

This current-state correction was made in the separate Performance Chat, not by this research task. This report does not claim reload/idempotency tests or existing-career migration were verified. The checklist below is now a review and regression checklist for that correction and any future migration; unchecked items remain open.

## Original v9 source and transformation chain

- `scripts/update_2026_offseason_snapshot.py:345` scrapes Basketball-Reference's `player-contracts` table and records a team tag and season salary cells. This source shape has one Lillard row tagged MIL and another tagged POR; both repeat the same four aggregate annual salary values. The parser does not classify an old-team waived obligation separately from a current active contract.
- `data/research/player_contracts_bref_2026_10_13.json` preserves both Lillard source records. Each carries $35,915,403 for 2026-27, $36,620,603 for 2027-28, then $22,516,603 for 2028-29 and 2029-30. The MIL row has $90,066,412 `remaining_guaranteed`; the POR row has $13,398,800. These copied aggregate schedules cannot both be interpreted as active salary contracts.
- `src/nba_gm_data/ingest.py:1755` `build_contracts()` matches first on normalized player name plus canonical team. For Lillard's POR canonical player, it chooses the POR-tagged record and copies its season salary values into one `contract_player-por-damian-lillard` contract. There is no separation into team salary and former-team waived/dead obligation at this boundary.
- In `data/canonical/universe_2026_27_offseason.json`, that single contract is assigned to POR, signed season 2026-27, four seasons, with `35,915,403 / 36,620,603 / 22,516,603 / 22,516,603`. Contract guarantee and option fields are null; the original row therefore also loses important team/term semantics.
- A distinct pre-aggregation research source, `data/research/contracts_public_players_2026.json` (Hoopshype scrape dated 2026-04-21), gives the component amounts: POR $13,398,800 for 2026-27, $14,104,000 for 2027-28 (player option), and no POR 2028-29/2029-30 active salary; MIL $22,516,603 in each year 2025-26 through 2029-30. For the two overlapping years, the Basketball-Reference combined values equal the sum: $13,398,800 + $22,516,603 = $35,915,403 and $14,104,000 + $22,516,603 = $36,620,603.
- Runtime `player_salary_table()` reads the single active player contract. `team_cap_summary()` sums active player contracts for the player's assigned team and separately sums `save.waived_salary_obligations`. In the v9 result, POR charged $35.9m / $36.6m as Lillard salary, MIL had no Lillard dead-salary entry, and the later $22.5m values were attributed to POR even though they belong to Milwaukee's gross stretched obligation.

## Guarantees, option, and unresolved set-off

The intended distinct records at the July 28, 2026 start are:

| Record | Team | 2026-27 | 2027-28 | 2028-29 | 2029-30 | Notes |
|---|---|---:|---:|---:|---:|---|
| Portland active contract | POR | $13,398,800 | $14,104,000 | — | — | Original term: 3 seasons signed in 2025 (2025-26, 2026-27, 2027-28). At 2026-27 game start: 2 scheduled seasons remain; 2026-27 is guaranteed, 2027-28 is a player option. |
| Milwaukee waived/stretched obligation (gross) | MIL | $22,516,603 | $22,516,603 | $22,516,603 | $22,516,603 | Former contract's remaining gross guarantee was stretched across 5 cap seasons, 2025-26 through 2029-30. At 2026-27 game start: 4 annual installments remain. Do not call those four installments the original player-contract duration. |

The reported background is that Milwaukee waived and stretched the former contract, while Portland later signed Lillard to a distinct three-year/$42 million deal with two guaranteed years and a 2027-28 player option. See [Associated Press reporting on the Milwaukee waiver](https://apnews.com/article/nba-free-agency-bucks-pacers-978b8bd4076ca59d7bb8c3dddd25003e), [NBA.com on the waiver/stretch](https://www.nba.com/news/bucks-waive-damian-lillard?lctg=5ed4cd31c0cd4110c421d01e), and [NBA.com on his Portland return](https://www.nba.com/news/damian-lillard-to-return-to-trail-blazers). The Portland option must remain an option, not a guaranteed year. The gross Milwaukee obligation is separate from the Portland active contract. Milwaukee's net cost may be affected by set-off from Lillard's Portland earnings; this review does not establish the exact season-by-season offset. Keep that amount unknown rather than deriving it from the aggregate source, a guarantee field, or unverified reporting.

## Implementation-ready review checklist

### Source and canonical records

- [x] At import, preserve source identity/team tags and classify the matching duplicate source rows as a resolved aggregate before active matching.
- [x] Treat the Basketball-Reference duplicate Lillard MIL/POR schedules as aggregate source rows; neither is imported as a full active-team schedule, and the duplicated schedules are not summed together.
- [x] Use the provenance resolution to separate Portland active terms from Milwaukee's former-team obligation. Keep other unresolved aggregate rows out of guessed current-team contracts.
- [x] Portland active terms: original signed term is 3 seasons (2025-26 through 2027-28), not 4. At the game's 2026-27 start, two scheduled years remain: $13,398,800 guaranteed for 2026-27 and $14,104,000 for 2027-28 as a player option. There is no Portland active salary in 2028-29 or 2029-30 under this contract.
- [x] Milwaukee obligation: the new-save ledger stores five original gross installments, 2025-26 through 2029-30, at $22,516,603 each. At game start, four installments remain. The former contract's original term is not inferred from its five-year cap-stretch schedule.
- [x] Guarantees/options are season-specific: the Portland 2026-27 guarantee and 2027-28 player-option status are present. They are supported by component source/reporting, not inferred from the aggregate salary row.
- [x] Contract protections: the resolution does not infer a no-trade clause. Retain `unknown/unverified` unless authoritative contract-level evidence supports the operative protection and terms.
- [x] Set-off is modeled separately from the gross Milwaukee obligation. The current v10 record has null `setoff_amount`, `net_salary` and net charge; do not replace these unknowns with $0 or describe $22,516,603 as the verified net charge.

### Runtime, new-save, reload and existing-career behavior

- [x] Player salary cards read only the active Portland player contract for Lillard. In the captured new-save payroll, Portland's waived salary is $0 and Milwaukee's gross former-team ledger is charged once for 2026-27 through 2029-30.
- [x] New-save initialization creates one Milwaukee obligation from canonical provenance using a deterministic ID derived from resolution/team/season range. The captured save has exactly one record. **Separate repeated-initialization and retry idempotency tests remain open below.**
- [ ] Save serialization/reload round-trips the obligation's team, gross annual schedule, source reference, known/unknown set-off status and term semantics without converting the obligation back into an active player contract.
- [ ] Reopening an existing career must never re-seed the startup obligation over an already persisted one. Missing obligation state in an old save must not be treated as proof that the user never modified Lillard's contract history.
- [ ] Existing-career migration policy must preserve player/team trades, negotiated extensions, waivers/buyouts, option decisions, cap holds and all other user-created history. Do not silently rewrite the player's active contract from the latest canonical snapshot.
- [ ] Only consider automatic repair for a demonstrably untouched save whose stored canonical hash/version and contract provenance identify the faulty imported baseline and which has no Lillard-related player/team contract mutations or option decisions. Otherwise leave the existing career unchanged and offer a separately reviewed migration/repair path; preserve a pre-migration backup and make the repair idempotent.
- [ ] If a new save is created from a future canonical source that already has the corrected separation, initialize from that source once. Reload and player-card reads must not mutate the ledger.

### Regression tests

- [ ] Import fixture with same-name MIL/POR source rows and repeated aggregate schedule: result is classified as aggregate/ambiguous, never two current active salaries and never a sum of duplicate rows.
- [ ] Provenance-resolved fixture: POR active schedule is 2026-27 $13,398,800 and 2027-28 $14,104,000 player option only; MIL gross stretch is a distinct $22,516,603 per season, 2025-26 through 2029-30.
- [ ] Original-term versus remaining-term assertions: Portland original 3-year deal, two scheduled years remaining at 2026-27 start; Milwaukee five stretched cap installments in total, four remaining at that start. Do not infer the original waived contract duration from its stretch schedule.
- [ ] Guarantee, option and protection assertions: POR guarantee and PO retain exact term flags; unsupported protections remain unknown; no-trade protection does not become a verified flag by guess.
- [ ] Set-off absent: gross MIL obligation persists; net amount remains explicitly unknown; no silent zero or guessed offset is materialized.
- [ ] New-save initialization twice (including retry/reopen path) produces exactly one dead-obligation record and one charge per relevant season.
- [ ] Save reload preserves record ID, team ownership, gross schedule, provenance and unknown-offset state; a read-only card/payroll query does not seed another record.
- [ ] POR player card lists only active POR salary terms; POR payroll counts active salary once; MIL payroll counts the gross former-team ledger once; there is no duplicate aggregate across ledgers.
- [ ] Existing-career fixtures with a trade, negotiated extension, exercised/declined option, waiver, or later contract override remain byte/meaningfully unchanged by default. Only the explicitly eligible untouched-baseline fixture can be repaired, and repeated migration is idempotent.

The original faulty boundary was the source scraper/`build_contracts()` handoff accepting a team-tagged aggregate schedule as if it were that team's active player contract. The correction is provenance-aware import and canonical/new-save obligation modeling, not a Damian-name gameplay special case. The v10 correction is present in the current baseline, but this research task did not implement or modify it. Existing-career migration and the unchecked regression cases remain open; no existing-career repair was performed by this research task.
