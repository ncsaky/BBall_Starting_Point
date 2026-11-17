# 2026 Offseason Data Update

## Snapshot

New games now begin on **July 28, 2026**, in the **2026 offseason**, with the
active season set to **2026-27**. This replaces the original 2025-26 preseason
starting universe for newly created saves.

The update changes real-world state, not the reviewed gameplay ratings:

- Current NBA team assignments and roster status
- Player age, birthdate, height, weight, position, and experience
- Completed 2026 draft results and drafted-player onboarding
- Publicly available 2026-27 and future contract salaries
- Future first- and second-round pick ownership from 2027 through 2033
- Official 2026-27 salary-cap, tax, and apron baselines
- The new-save date, phase, schedule season, contract season, and live draft year

Returning players retain their previous engine trait values by normalized name.
The build records this preservation report in canonical metadata.

## Source Hierarchy

### Official NBA Sources

Official sources are authoritative for league identity and completed moves:

- [NBA team roster pages](https://www.nba.com/teams): current team, roster
  membership, age, birthdate, position, height, weight, experience, and
  acquisition context for all 30 teams.
- [2026 NBA Draft results](https://www.nba.com/news/2026-nba-draft-order):
  completed draft order and draft-night transaction text.
- [2026 NBA Draft prospects](https://www.nba.com/draft/2026/prospects):
  physical and biographical supplementation for drafted rookies.
- [2026 offseason deals](https://www.nba.com/news/nba-offseason-deals-2026):
  completed signings, extensions, waivers, and trades.
- [2026 offseason trade tracker](https://www.nba.com/news/2026-offseason-trade-tracker):
  player and draft-asset trade cross-checking.
- [2026-27 NBA salary cap](https://www.nba.com/news/nba-salary-cap-2026-27-season):
  official cap, tax, and apron levels.

Only completed moves reflected by the official roster snapshot are assigned to
teams. Reported, pending, or on-hold transactions are not treated as completed.

### Public Secondary Sources

The NBA does not publish one complete machine-readable ledger for every annual
salary and every future pick condition. Two public secondary sources fill those
specific gaps:

- [Basketball Reference player contracts](https://www.basketball-reference.com/contracts/players.html):
  annual contract salaries and remaining terms.
- [Spotrac future draft picks](https://www.spotrac.com/nba/draft/future/):
  owner-side first- and second-round pick records and available protection text.

Current official-roster players missing from the public salary table receive a
clearly marked gameplay estimate. Rookie estimates use draft slot; other current
players use a one-year minimum-scale estimate. Unresolved non-roster contracts
remain `research_pending` rather than being presented as verified facts.

## Reproducible Refresh

The game does not need the internet at runtime. Refresh the checked-in research
snapshot, then rebuild canonical output:

```bash
PYTHONPATH=src python3 scripts/update_2026_offseason_snapshot.py
PYTHONPATH=src python3 -m nba_gm_data.cli build --root . --out data/canonical
```

The refresh script writes:

- `data/research/nba_official_rosters_2026_07_28.json`
- `data/research/nba_official_draft_2026.json`
- `data/research/contracts_public_players_2027.json`
- `data/research/future_picks_spotrac_2027_plus.json`

The canonical build writes:

- `data/canonical/universe_2026_27_offseason.json`
- `data/canonical/universe_2026_27_offseason.sqlite`
- `data/canonical/coverage_report.json`

## Build Audit

The July 28 snapshot currently produces:

- 30 teams
- 640 player records
- 588 official roster/camp rows
- 60 completed 2026 draft selections
- 60 prospects in the next playable 2027 class
- 420 unique future picks: one R1 and one R2 origin record per team for
  2027-2033, with current ownership annotations
- 640 contract records
- 526 returning players with all 7,890 prior engine trait values preserved

The larger player count includes current NBA roster/camp players plus retained
free-agent and historical gameplay records. It is intentionally not a claim that
640 players are simultaneously on standard NBA contracts.

## Deliberate Boundaries

- **Ratings:** no returning-player ratings were recalibrated in this update.
- **Staff:** gameplay staff remain the existing fictional simulation layer.
- **Schedule:** until an official complete 2026-27 schedule source is ingested,
  the game generates the 2026-27 schedule deterministically from the established
  schedule template.
- **Existing saves:** old save files are not silently migrated. New saves use the
  July 2026 universe; existing saves continue from their own persisted history.
- **Unsigned players:** official roster pages can contain camp, two-way, or
  otherwise unsigned-status players. Roster status and contract confidence are
  kept separate so missing salary data does not become invented certainty.
- **Pick protections:** owner-side source text is preserved where available.
  The game normalizes it into its structured protection/swap system and keeps
  unresolved terms auditable.

## Verification

Focused tests cover:

- The new epoch and offseason phase
- Landmark roster moves and 2026 rookies
- Exact returning-player trait preservation
- Contract and future-pick counts
- Unique pick identities
- Current 2027 draft-class routing
- Completed historical startup injuries
- New-save schedule generation

Run all tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
