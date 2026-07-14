---
type: quality
status: current
reviewed: 2026-07-10
tags:
  - quality/risk
  - quality/technical-debt
  - project/nba-gm
---

# Risk Register And Technical Debt

Scores are qualitative: impact and likelihood from 1 (low) to 5 (high). This is a living prioritization tool, not a declaration that the project is unsafe to use privately.

| Risk | Impact | Likelihood | Evidence | Next control |
|---|---:|---:|---|---|
| Save corruption/no atomic recovery | 5 | 2 | Large JSON mutations and long operations | temp-write + fsync + atomic rename + backups |
| Save schema drift | 5 | 4 | Opportunistic defaults/migrations in read paths | explicit schema version and migration chain |
| GUI/CLI behavior divergence | 4 | 4 | CLI orchestration not fully extracted | action parity matrix and shared application services |
| GUI layout regression | 3 | 5 | repeated overlap/gap playtest fixes | grid refactor and screenshot tests |
| Integration hubs too large | 4 | 4 | `play.py`, `save.py`, `transactions.py` | extract by lifecycle capability with characterization tests |
| Duplicate authority for derived state | 5 | 3 | past pick/order/label/rotation bugs | authority/invalidation docs and validators |
| Full-suite runtime slows feedback | 3 | 5 | historical 8+ minute suite before later growth | timing harness, fixtures, caches, test split |
| AI calibration overfits named examples | 4 | 3 | many player/package-specific playtests | distribution and multi-seed benchmark suites |
| Incomplete CBA rules surprise users | 4 | 3 | v1 practical cap/transaction configs | visible rules guide and staged CBA roadmap |
| Canonical data staleness | 3 | 4 | manual missing heights/contracts found in play | build manifest, freshness audit, update workflow |
| Narrative validator complexity | 3 | 4 | many semantic one-off guards | typed fact claims or constrained rendering grammar |
| Local server exposed beyond loopback | 5 | 1 current / 4 hosted | no auth, local assumptions | enforce loopback; add auth before remote hosting |
| iOS packaging feasibility | 4 | 3 | proposal only; large Python/data runtime | early simulator spike before GUI parity completion |
| Asset licensing/distribution | 4 | 3 | large NBA highlight video and logos | document rights; use user-supplied/licensed assets for release |
| One giant test module | 2 | 5 | 5,000+ lines | split by domain with shared fixtures |

## Highest-Priority Structural Debt

### Explicit Save Schema And Validation

Save dictionaries are flexible but high-risk domains need typed validators. Start with pick obligations, draft state, contracts, and roster ownership. This also enables robust migration.

### Shared Application Services

Move workflow sequencing out of terminal prompts so CLI, GUI, and future native clients execute the same action functions.

### GUI Layout Primitives

Define named grid areas, track variables, card size tokens, and responsive breakpoints. Remove structural negative margins/absolute offsets.

### Scenario Fixture Library

Reusable save builders for deadline, lottery, draft, free agency, playoffs, rollover, injury, and pick-obligation cases will reduce test runtime and duplication.

## Calibration Debt

- Ratings prior has unmatched meaningful players.
- Future prospect distributions need multi-year validation against the calibrated league.
- Award and stat leader tuning requires multi-seed dashboards, not single examples.
- Trade values need benchmark tiers and market-wide conservation tests.
- Staff churn/extension volumes need seasonal distribution reports.

## Product Debt

- GUI parity is incomplete across every CLI path.
- Responsive/mobile UX is not ready.
- Press conferences are disabled pending pacing/quality decisions.
- Onboarding and in-app rules explanation need work for nontechnical friends.
- Save import/export and packaged releases need end-to-end testing.

## Debt Management Rule

Do not “clean up” broad integration modules during unrelated feature work. Create a characterization test, define the ownership boundary, extract one capability, and compare behavior. Unscoped refactoring in this project can alter a league several phases later.

## Related Notes

- [[Roadmap/Next Development Phases]]
- [[Roadmap/Release Readiness]]
- [[History/Failure Museum]]

