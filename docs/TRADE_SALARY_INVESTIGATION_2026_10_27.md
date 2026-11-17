# Trade Salary Regression Investigation

## Finding

The six previously reported failing assertions did not prove six broken salary rules. The integration test mixed an old saved career with the latest starting roster. `canonical_with_save` correctly selects the historical starting universe for established careers through `baseline_for_save`.

The test chose Denver's first non-traded player from today's universe: `player_den-emanuel-miller`. That player does not exist in the saved career's historical universe. Giving that absent player a $500M salary therefore did not raise Denver's live payroll. This invalidated the stale-current-payroll, prepared-context and three future-year cases. Similarly, deleting Dunn's contract from the latest universe did not delete it from the historical universe actually used for the career.

The fixture now selects the same preserved baseline as the saved career before choosing players or modifying contracts. All six original assertions pass with their salary expectations unchanged. Historical saves continue using their original roster; no salary threshold, matching rule or roster-preservation behavior was relaxed.

## Separate Production Bug

After correcting the fixture, its missing-data case reached a genuine error: `apply_trade_to_state` attempted to load canonical data before the existing guarded salary checker, so a missing/corrupt file raised an exception rather than returning a blocked trade.

The application boundary now returns `not_applied_salary_legality` with `manual_review_required` when starting payroll data cannot be loaded. Salary validation also blocks safely if the preserved starting-roster archive cannot be read. These paths do not execute the trade or consume the offer. File-level tests verify identical bytes and modification times after rejection. Unexpected programming errors outside the data-loading/overlay failure cases are not broadly swallowed.

## Verification

142 tests pass across salary application, independent salary boundaries, transaction application/atomicity, trade calendar and discretion, July reviews, team planning, roster-space sales, release planning, waivers, protection and daily/bulk simulation consistency.

The new standalone boundary fixture does not depend on changing imported rosters or an archived audit save. It verifies:

- Rejection of worsened current payroll overages without changing source data or save state.
- Rechecks in all three supported future payroll years.
- Missing/corrupt canonical data blocks file application without writing.
- Missing preserved-roster data blocks without mutating the save.
- Legal salary-reducing trades can still execute despite an existing overage.
- Unresolved current traded salary stays blocked.
- A valid trade applies once and a repeat does nothing.

The existing historical integration tests additionally cover direct file application, app application, candidate application, incoming-offer acceptance, unchanged rejection files, latest save overrides over prepared stale context, and the existing unknown-future-salary skip policy.

Command:

```sh
env PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest test_trade_salary_application test_trade_salary_boundaries test_transaction_application_audit test_trade_calendar test_trade_discretion test_summer_trade_reviews test_team_planning test_roster_space test_release_planning test_waivers test_contract_protection test_simulation_consistency
```

This is a check of the game's existing financial rules, not certification of complete NBA CBA compliance or a full repository test run. No long career reruns were necessary. No player ratings, development, UI design, playable saves or retained market evidence were deleted or recalibrated. The development server was restarted with the user's approval.
