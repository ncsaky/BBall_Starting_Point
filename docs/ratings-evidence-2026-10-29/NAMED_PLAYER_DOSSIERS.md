# Named-player and contract dossiers

Research-only snapshot, prepared 2026-10-29 and updated with display/runtime findings on 2026-10-30. No production ratings, code, or saves were changed by this research task. The Performance Chat separately updated the contract import baseline to v10; this dossier records that current state while preserving the earlier v9 finding as historical evidence. The canonical rating/roster snapshot still declares a 2026-27 start date of **2026-07-28**, while the user's intended gameplay start is **2026-10-20**, just before the regular season. The user considers offseason podcast evidence broadly current at the October start unless intervening injuries, trades, signings or other material events change context. Changing the intended game date does not update the retained July canonical source. All evidence below remains dated; post-start facts are not treated as known pre-start inputs.

## Reading the repository values

The source inspected for rating traits was `data/canonical/universe_2026_27_offseason.json`, currently `starting_data_version=2026-10-30-contract-separation-v10`; its rating/roster snapshot remains dated July 28. The canonical player traits are on a 0–100 scale. The game’s `player_attribute_summary()` computes a derived `overall` from traits, role, and minutes; it is a different output from the manually supplied OVR column in `data/overrides/league_trait_ratings_2026_06_20.csv`. These values should not be compared as if they were one shared scale.

Health state is separate from healthy ability. At the canonical date, all four players have `availability_status: active` and no `current_injury_id`; consequently the canonical health state applies no current-injury rating reduction. Trait values below are the canonical base profile. Their separate health profiles are confidence-limited risk estimates, not active rating penalties.

| Player | Canonical team / projected minutes | Current ability / potential | Game-derived overall | Health state on 2026-07-28 |
|---|---|---:|---:|---|
| Damian Lillard | POR / 25.5 | Not stored / not stored | 68.5 engine summary | Active; no current injury ID. Profile records a past season-ending lower-leg/foot flag, but not the actual Achilles diagnosis. |
| Dylan Harper | SAS / 22.1 | 53.11 / 71.91 | 59.5 engine summary | Active; no current injury ID or major-prior-injury entry. |
| Jeremy Sochan | POR / 11.0 | 52.57 / 60.41 | 56.9 engine summary | Active; no current injury ID or major-prior-injury entry. |
| Luka Dončić | LAL / 35.5 | Not stored / not stored | 71.3 engine summary | Active; no current injury ID or major-prior-injury entry. |

**Display-scale correction:** The OVR values in this table are raw game-engine summaries, not user-facing player-card ratings. The current October 20 disposable new-save probe found frontend-selected card OVRs of 86.4 (Lillard), 78.6 (Harper), 79.1 (Sochan), and 88.6 (Dončić), after save rotation-minute projection. An earlier July-start probe had different rotation minutes and yielded 86.5/78.6/75.3/88.3. Both are retained and dated in `DISPLAY_VALUE_TRACE.md`; the old Sochan 75.3 was a zero-minute rotation outcome, not the current save value.

The canonical `active_season` is not a clean guarantee that every linked transaction existed on July 28: Sochan is listed on Portland even though NBA.com’s Portland roster lists his signing on **2026-08-02**. See the Sochan date note below.

## Damian Lillard — contract provenance is materially conflated in the canonical contract row

### Dated contract timeline

| Date / season | Finding |
|---|---|
| July 2022 | Lillard signed a Portland extension that was later traded with him to Milwaukee. The old extension had two years remaining in summer 2025, worth about $112.6 million, one year of which was an option year. |
| July 1–6, 2025 | Milwaukee waived Lillard after his April 2025 left Achilles rupture and stretched the **gross remaining guaranteed Milwaukee obligation** (reported as $112.6 million, rounded by NBA.com to $113 million) over five cap years, 2025-26 through 2029-30. This is Milwaukee dead salary from the waived contract; it is not Lillard’s new Portland contract. [AP](https://apnews.com/article/nba-free-agency-bucks-pacers-978b8bd4076ca59d7bb8c3dddd25003e), [NBA.com](https://www.nba.com/news/bucks-waive-damian-lillard?lctg=5ed4cd31c0cd4110c421d01e) |
| July 19, 2025 | Portland announced his return on a three-year deal reported at $42 million. The reported structure is two guaranteed years plus a 2027-28 player option and a no-trade clause. The 2027-28 option was not yet exercisable at the canonical 2026-07-28 start date. [NBA.com](https://www.nba.com/news/damian-lillard-to-return-to-trail-blazers), [The Washington Post](https://www.washingtonpost.com/sports/2025/07/17/damian-lillard-trail-blazers/), [OPB](https://www.opb.org/article/2025/07/17/damian-lillard-return-to-portland/) |
| 2025-26 | Lillard did not play because he was rehabbing the Achilles; Portland’s 2026-27 game notes record no games in 2025-26. The old Milwaukee waived obligation continued separately. [NBA.com season review](https://www.nba.com/news/season-review-2025-26), [Portland game notes](https://www.nba.com/gamenotes/blazers.pdf) |
| 2026-27, canonical start | Portland’s active salary is **$13,398,800**. The separate Milwaukee stretched amount is about **$22,516,603** gross for this cap year. As of 2026-07-28, Lillard is in the guaranteed second year of Portland’s new deal, with the $14,104,000 2027-28 player option still pending. Contract salary data: [Basketball-Reference Portland payroll](https://www.basketball-reference.com/contracts/POR.html); a local pre-aggregation source scrape is `data/research/contracts_public_players_2026.json`, retrieved 2026-04-21. |
| By 2026-10-29 (post-start evidence) | Portland’s game notes list Lillard as active in its first three regular-season games. This confirms return-to-play by October; it does not rewrite the July 28 health snapshot. [NBA.com Portland game notes](https://www.nba.com/gamenotes/blazers.pdf) |

The new Portland signing also produced a reported set-off against Milwaukee’s waived-contract obligation. This changes the former club’s net cash/cap accounting; it does not turn Milwaukee’s dead salary into Lillard’s Portland salary. The gross $112.6 million five-year figure and the exact net offset should remain separately labeled. I did not find an authoritative public ledger that settles every set-off allocation in the canonical contract row.

### Historical v9 finding and current v10 state

The earlier v9 canonical entry `contract_player-por-damian-lillard` had `original_contract_years: 4` and years 2026-27 through 2029-30 at **$35,915,403 / $36,620,603 / $22,516,603 / $22,516,603**, with guarantee status unknown. Those first two numbers equal:

- Portland’s new active salary: $13,398,800 (2026-27) and $14,104,000 (2027-28 player option), **plus**
- a $22,516,603-per-year Milwaukee stretched amount.

That v9 row combined the active Portland contract with the prior team's waived-contract accounting. Current v10 records the Portland active contract as a three-season 2025-26 through 2027-28 deal (two seasons remain at the 2026-27 game start) and a separate Milwaukee gross stretch obligation. The new-save player-card salary schedule contains only the Portland terms; new-save payroll contains one gross Milwaukee ledger entry. `CONTRACT_IMPORT_FINDING.md` documents both versions and the remaining reload, idempotency and existing-career review cases. This contract correction came from the separate Performance Chat; no contract correction was made by this research task.

### Ability, health and uncertainty

Canonical base traits include release 90, range 92, shot versatility 84, handle 82, passing reads 78, lateral agility 40, defensive effort 42 and stamina 58. The game-derived overall is 68.5, with derived shooting 88.7, creation 75.5 and defense 45.4. The June 20 subjective source CSV has OVR 80 / OFF 82 / DEF 42; that is a separately sourced prior, not the game’s derived overall.

The real left Achilles injury is well documented, but the July 28 canonical health state is active with no current injury ID. Its profile’s note is imprecise (“raw OutForSeason flag”) and body-area tags do not explicitly name the Achilles. Do not apply a present-day Achilles reduction to the July 28 healthy base without a distinct, dated injury-state decision. The 2025-26 absence is injury-adjusted availability evidence; the shooting and playmaking traits are healthy-skill estimates. Age 36 and a recent major Achilles rupture remain substantial uncertainty for post-return workload and performance.

## Dylan Harper — proposed upward correction has meaningful evidence, but remains a calibration question

**User hypothesis:** current OVR may be too low. This is a research question, not a pre-approved buff.

**Existing canonical values:** game-derived overall 59.5; current ability 53.11; potential 71.91. Key traits: release 54.0, range 53.0, shot versatility 53.9, rim pressure 56.7, handle 67.7, passing reads 71.1, lateral agility 71.1, defensive effort 69.2 and playoff translation 57.5. Active on July 28 with no active injury ID. His generated health profile is only 0.38 confidence and records no major-prior-injury entry.

**Supporting evidence, as of the completed 2025-26 season:** The Spurs’ official game notes report 69 games (four starts), 22.6 minutes, 11.8 points, 3.9 assists and 3.4 rebounds per game, with 50.5% field-goal and 34.3% three-point shooting. His usage was about 20%; these are productive rookie results with efficient finishing, but a modest role rather than star-level volume. The same official notes report 14.1 points, 5.6 rebounds and 2.7 assists during the Spurs’ Finals run, plus 15 missed regular-season games for a left calf strain, right ankle soreness and right calf contusion. [Spurs 2025-26 game notes](https://www.nba.com/gamenotes/spurs.pdf?tid=1706240441020)

NBA.com’s 2026 sophomore outlook describes Harper’s rookie season as strong, highlights his playoff confidence and rim shotmaking, and expects his role/minutes to grow. That is affirmative counterweight to a low current estimate, but it is forward-looking analysis rather than a measured new trait value. [NBA.com sophomore outlook](https://www.nba.com/news/2026-sophomores-expectations-2026-27)

**Assessment:** The evidence supports reviewing whether current-ability/overall calibration gives too little credit to his first-year finishing, playmaking and playoff contribution. It does not yet support a numerical increase to shooting traits: his moderate three-point percentage and the existing 53-ish range/release/versatility values are directionally plausible. His 71.91 potential already separates substantial future upside from present ability. July 28 health state has no active modifier; the 2025-26 missed games belong in dated availability history, not as a permanent healthy-skill downgrade. Uncertainty: one NBA season, limited role, missed time, and real sophomore growth still unknown at the July snapshot.

## Jeremy Sochan — recent role supports a component-level concern; broad “overrated” is not established

**User hypothesis:** Sochan may be overrated. This is not automatically accepted.

**Existing canonical values:** game-derived overall 56.9; current ability 52.57; potential 60.41. Traits include release 42.9, range 49.5, shot versatility 49.7, handle 48.8, passing reads 60.2, lateral agility 70.6, defensive effort 72.6, rim deterrence 68.2, screen navigation 71.7 and offensive rebounding 76.8. The profile thus represents limited shooting with strong defensive/rebounding components, rather than a uniformly high all-around rating. His July 28 health state is active with no injury ID; risk profile has only 0.38 confidence and no major-prior-injury entry.

**Supporting evidence for the concern:** San Antonio’s official season notes say Sochan was waived on February 11, 2026. Before that he played 28 games at 12.8 minutes per game and averaged 4.1 points, 2.6 rebounds and 1.0 assist; he shot 25.7% on 35 three-point attempts. He did not start. [Spurs 2025-26 game notes](https://www.nba.com/gamenotes/spurs.pdf?tid=1767956415755)

**Counterevidence and context:** The official NBA G League release records 16 additional 2025-26 regular-season games with New York after San Antonio, so the 28-game Spurs line is not his entire season. His earlier 2024-25 Spurs season was materially larger: 54 games and 11.4 points, 6.5 rebounds and 2.4 assists in 25.3 minutes; this was a different season and should not mask the 2025-26 rotation collapse. NBA sources describe that 2025-26 stint as 28 Spurs games plus 16 Knicks games. [NBA G League official release](https://aguacaliente.gleague.nba.com/news/texas-legends-select-nba-champion-jeremy-sochan-with-first-pick-in-2026-nba-g-league-draft), [NBA stats page](https://www.nba.com/stats/player/1631110/?Season=2024-25&SeasonType=Regular+Season)

The low 2025-26 minutes and weak three-point result support skepticism about present offensive shooting and role reliability. They do not by themselves show that defensive effort, mobility, screen navigation or rebounding are overrated. The current engine summary is 56.9, with the clearest positive traits in those defensive/rebounding areas; there is no case here for a broad downward move. Uncertainty: the reduced Spurs role appears coach/rotation-driven in the cited evidence, while the small 28-game sample and midseason team change complicate attribution.

**Snapshot-date problem:** The canonical July 28 universe lists Sochan on Portland at 11 projected minutes with a one-year $2,449,421 contract. NBA.com’s Portland roster records him as signed **August 2, 2026**, after the canonical start date. [NBA.com Portland roster](https://www.nba.com/team/1610612757/blazers) His July 28 team/contract should not be represented as Portland without an explicit rule for post-start transactions.

## Luka Dončić — dominant recent offense; the apparent “OVR” mismatch needs a scale crosswalk

**User hypothesis:** Luka may be underrated. Current evidence supports checking the display/calibration, not an automatic increase.

**Existing canonical values:** game-derived overall 71.3; current ability and potential are not stored for him. Traits include range 84.6, release 79.0, shot versatility 68.5, rim pressure 82.8, handle 88.9, passing reads 95.0, portability 66.1 and playoff translation 84.0. Counterbalancing traits include lateral agility 32.0, defensive effort 42.0, screen navigation 36.0 and rim deterrence 42.0. His July 28 health state is active with no current injury ID. The health profile is a generic, low-confidence (0.38) risk estimate, not a current injury reduction.

**Supporting evidence:** The NBA’s 2025-26 season review credits Dončić with the scoring title at 33.5 points per game, fourth place in MVP voting and a first-team All-NBA selection. These facts strongly support elite current offensive value as of the July 2026 start snapshot, since the season ended before that date. [NBA 2025-26 season review](https://www.nba.com/news/season-review-2025-26)

**Counterevidence / interpretation:** His canonical offensive traits are already strong, including 95 passing, 88.9 handle, 82.8 rim pressure and 84 playoff translation. The profile also explicitly keeps defense and mobility lower. The CSV prior’s OVR 91 / OFF 89 / DEF 45 comes from the June 20 subjective rating prior; it is not the same field or formula as the game-derived 71.3. Without a calibration crosswalk between those two outputs, “71.3 versus 91” cannot by itself prove under-rating. No new injury penalty is represented on July 28; if assessing a different save/date with active injury status, compare its effective rating separately from this healthy base.

**Assessment:** The season evidence backs the claim that Dončić should remain an elite offensive player; it does not show that every trait or the whole game-derived overall is low. The strongest next diagnostic is to validate the display-scale relationship and confirm that his elite creation/scoring role is sufficiently represented in the engine’s derived overall. Do not use injury-adjusted effective OVR as a proxy for healthy ability. Uncertainty: the NBA evidence is one completed season and a single scoring metric does not resolve defense, portability, or the game’s different role-weighting formula.

## Decisions intentionally left open

- Which baseline is authoritative when `2026-07-28` startup metadata conflicts with August/October facts already embedded in the canonical universe?
- Should upcoming-player evaluation treat in-game `overall`, roster-alignment `current_ability`, `potential`, and the June subjective OVR prior as separate measures with an explicit crosswalk?
- Are the four players’ current health profiles sufficient, especially Lillard’s generic injury history and the low-confidence generic profiles for Harper, Sochan and Dončić?
- No player rating or contract value is proposed for mutation in this research checkpoint.
