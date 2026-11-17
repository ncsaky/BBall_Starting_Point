# Missing measurements, staff budget, draft previews, and social posts

The roster now has verified heights and weights for all 11 players with missing measurements. Future-pick recommendations reuse the same draft class across teams. Extension posts need the player's own simulation evidence, and games missed by themselves cannot support a durability warning.

Brooklyn's staff budget guard was already working. The original test candidate accepted an offer the guard had lowered to fit the budget. The revised test gives Brooklyn less room to spend so it can catch a live strategy that improperly raises the cap.

## Player measurements

The rebuild reads `data/overrides/player_overrides.json`, where other manual player measurements already live. The shipped starting-universe JSON has the same field updates so a fresh checkout or packaged game can use the measurements directly. Heights and weights use published professional listings where available. Nkrumah uses the measured combine values, including barefoot height. The two empty wingspans below had no verified measurement in the sources reviewed.

The original Portsmouth measurement sheets gave Sellers and Cooper different wingspans from an online transcription. The values below come from the sheets.

| Player | Height (in) | Weight (lb) | Wingspan (in) | Sources |
|---|---:|---:|---:|---|
| Tucker DeVries | 79 | 215 | 81 | Height and weight [Maine Celtics roster](https://maine.gleague.nba.com/news/roster-110326). Wingspan [Sports Illustrated pre-draft workout coverage](https://www.si.com/nba/pacers/onsi/pacers-to-host-6-players-for-pre-draft-workouts-thursday-01ksnnzhjqhp). |
| Wyatt Fricks | 81 | 216 | 81.5 | Height and weight [Greensboro Swarm roster](https://greensboro.gleague.nba.com/news/greensboro-swarm-announce-2026-27-training-camp-roster-presented-by-hondajet). Wingspan [Portsmouth Invitational measurement sheet, page 2](https://pbs.twimg.com/media/HGJXHYYW0AAHEJm.jpg?name=orig). |
| Jaylin Sellers | 76 | 205 | 80.5 | Height and weight [NBA G League player profile](https://gleague.nba.com/player/1643637/jaylin-sellers). Wingspan [Portsmouth Invitational measurement sheet, page 1](https://pbs.twimg.com/media/HGJXHXcXcAA89aN.jpg?name=orig). |
| Rashaun Agee | 79 | 210 | 85.5 | Height and weight [Cleveland Charge roster](https://cleveland.gleague.nba.com/news/charge-2026-27-opening-night-roster). Wingspan [Portsmouth Invitational measurement sheet, page 2](https://pbs.twimg.com/media/HGJXHYYW0AAHEJm.jpg?name=orig). |
| Carson Cooper | 82 | 245 | 85 | Height and weight [NBA Grizzlies roster](https://www.nba.com/team/1610612763/lineups-misc). Wingspan [Portsmouth Invitational measurement sheet, page 1](https://pbs.twimg.com/media/HGJXHXcXcAA89aN.jpg?name=orig). |
| Josh Dix | 77 | 210 | 78.5 | Height and weight [NBA player profile](https://www.nba.com/player/1643717/josh-dix). Wingspan [Portsmouth Invitational measurement sheet, page 1](https://pbs.twimg.com/media/HGJXHXcXcAA89aN.jpg?name=orig). |
| Christoph Tilly | 84 | 242 | — | Height and weight [NBA Summer League roster](https://www.nba.com/summer-league/2026/slc/team/1610612760/thunder). |
| Andrew Holifield | 80 | 195 | — | Height and weight [NBA Summer League roster](https://www.nba.com/summer-league/2026/slc/team/1610612760/thunder). |
| Aaron Nkrumah | 77 | 188.8 | 82.25 | All three [2026 NBA Draft Combine results, transcribed by Basket Reference](https://www.basket-reference.com/event-48-NBA.Draft.Combine-2026-imperial.htm). |
| Nimari Burnett | 77 | 202 | 81.5 | Height and weight [Raptors 905 roster](https://raptors905.gleague.nba.com/news/raptors-905-announce-opening-night-roster-4). Wingspan [Portsmouth Invitational measurement sheet, page 2](https://pbs.twimg.com/media/HGJXHYYW0AAHEJm.jpg?name=orig). |
| Mohamed Wague | 82 | 225 | 88 | Height and weight [Utah Jazz signing announcement](https://www.nba.com/jazz/news/utah-jazz-sign-mohamed-wague). Wingspan [SLC Dunk signing coverage](https://www.slcdunk.com/utah-jazz-news/70170/utah-jazz-make-surprise-center-signing-post-nurkic-injury). |

## What changed

- **Roster test.** Restored the original missing-data assertion. Updated the separate Cam Whitmore salary check to the $675,000 game estimate on his Denver two-way deal, recorded in `data/overrides/contracts_2026_10_13.json` in `5e40fef`.
- **Staff test.** The guard from `5b9b8f2` already applies staff hires against the original league budget. The offer cap from `fd8e3ce` reduced the $11.35 million ask to $10.90 million within the $28.11 million budget. That still met the free agent's minimum of 96% of the ask. The test now adds $1 million to an existing non-coach salary, so the capped offer falls below the minimum. The spending and no-hire assertions are unchanged.
- **Draft recommendations.** The temporary draft view had been creating its own cache on first use and losing it with the view. It now shares the existing generated-class cache with the reusable transaction context. The cache still uses year, effective class seed, talent mode, and configuration. Recommendation payloads copy the prospect records they return so a caller cannot change the cached class.
- **Social posts.** The validator checks for the exact health evidence attached to the player in the extension. A durability concern also requires an elevated injury-risk score or a player who is currently unavailable. The test covers six of six games and six of 70 with zero injury risk. The East standings examples use Scottie Barnes because `5e40fef` moved Ingram to the Clippers. The original accept/reject checks still exercise both scenarios.

## Checks

- All four restored tests passed with the final measurements.
- The foundation module passed on the final measurements with 214 tests and 23 skips.
- The core suite passed on the final measurements with 329 tests and three skips.
- Before-and-after draft recommendations matched for Boston and Atlanta at two seeds. The new code built one class per seed and returned the same results after a caller edited a returned prospect.
- Forcing the staff test to use the live budget allowed Brooklyn to spend $29.56 million against its $28.11 million limit. The revised fixture caught the regression.
- The shipped universe differs only in the 31 expected measurement fields.
- The 17 neighboring draft and narrative tests passed.
- Full discovery ran 1,746 tests with three failures and 53 skips. It started with preliminary wingspans and read the corrected values during the rebuild check. The final foundation run passed that check, and two separate rebuilds of the final data were identical.
- The other two discovery failures were `FivePlayerCalibrationTests.test_only_exact_targets_and_reviewed_rim_anchor_change_inputs` and `RatingScaleConsistencyTests.test_reviewed_top_rim_anchor_preserves_other_inputs_and_development`. They compare all player fields in the live universe against historical snapshots. Both passed when rerun against the pre-BUG-B data. The new starting universe changes only the 31 intentional measurement fields. Both tests are outside the assigned scope. The coordinator can pin the historical comparisons to corresponding snapshots and retain the separate check on Wembanyama's later rim-deterrence change from 99.0 to 100.0.

## Resume state

All four quarantines are removed. Both requested checks passed on the final measurements, and the full discovery findings are recorded above. Logs are in `output/bug-b/`. Ready for coordinator review. No commits.
