# Targeted Player Calibration, October 23, 2026

## Scope and Evidence Standard

New-game version: `2026-10-23-player-tuning-v3`, layered on the immutable V2 baseline. Only four named players' traits change. Medical profiles, existing injuries, return dates, identities, contracts, draft terms, future classes and development rules remain unchanged. Existing saves stay pinned to their previous baseline.

These are model judgments, not scientifically measured 0-100 skills. The evidence supports direction and player identity more strongly than the exact chosen integer. NBA performance through 2025-26, pre-start scouting and reported roles inform the changes; later reporting is corroboration about that completed season, not permission to import 2026-27 performances or transactions. No Reddit comment or another game's overall is used as the calibration target.

The narrow overrides run after general alignment and medical construction, before ratings-dependent asset/contract-market tables. This prevents a new defensive grade from changing other alignment priors, or a stamina correction from silently raising inferred durability. Corrected traits retain notes, confidence, previous value and supporting URLs in `components.manual_calibration`.

## Kyrie Irving

The V2 inputs included neutral 50 shooting/range/rim-pressure estimates, 50 offensive rebounding and 7.51 portability despite a demonstrated NBA shot-creation career. A missed season should widen uncertainty, not replace established skill with generic defaults.

[NBA injury reporting](https://www.nba.com/news/kyrie-irving-wont-return-2025-26-season) confirms his missed season. [ESPN's career table](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/6442/stats?seasontype=2) supplies the multi-year performance context. [Grant Afseth's original reporting](https://dallassportsjournal.com/mavericks-luka-doncic-out-with-wrist/) includes coaches' and teammates' assessments of his shooting, handle, finishing and off-ball partnership. A short hot-shooting stretch in that article is not treated as his sustainable shooting percentage.

Restore strong shooting, elite handling/shot versatility, credible secondary creation and fit. Retain below-average defense, limited screen navigation, conservative post-injury mobility, low offensive rebounding and his existing medical risk. Do not assume peak athleticism or guaranteed rehabilitation success.

## Dereck Lively II

[NBA injury reporting](https://www.nba.com/news/mavericks-dereck-lively-out-season-foot-surgery) documents seven appearances before surgery. [ESPN career statistics](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/4683688/stats?seasontype=2), the [Mavericks' media guide](https://cdn.nba.com/teams/uploads/sites/1610612742/2025/09/2024-25-Dallas-Mavericks-Media-Guide-2_compressed.pdf) and [Josh Bowe's season analysis](https://www.mavsmoneyball.com/2025/5/21/24432892/dereck-livelys-sophomore-season-was-only-a-disappointment-because-of-high-expectations) support established lob finishing, interior defense and connective passing. Bowe also identifies foul trouble, inconsistent possessions and a restricted/rusty return. Those cautions matter.

Improve vertical finishing, conditioning, interior shot repertoire and usable mobility. Keep his extremely limited shooting and handling. Reduce tiny-sample rebound/rim-protection extremes and the overly certain scheme-IQ estimate instead of boosting an already high defense composite. No invented jumper or guard-style screen-chasing skill.

His overall remains modest because the unchanged composite gives shooting/creation identical weights across positions and omits a direct rebounding component. That is a separate valuation problem, not a reason to falsify his underlying shooting to manufacture an 80 overall. His existing medical profile is preserved; the older generic medical-history coverage is not claimed to be complete.

## Collin Murray-Boyles

[Kai Gammage's Sportsnet scouting](https://www.sportsnet.ca/nba/article/prospect-of-interest-how-does-collin-murray-boyles-fit-with-raptors/) identifies strength, agility, length and defensive versatility while noting size limitations. [Louis Zatzman's NBA-season analysis](https://raptorsrepublic.com/2026/01/20/collin-murray-boyles-and-jamal-shead-revolutionize-the-raptors-future/) describes defensive anticipation, disruption and strong rotation-player impact. [No Ceilings' playoff film analysis](https://www.noceilingsnba.com/p/2026-nba-playoffs-dylan-harper-vj) independently explains show/recover, blitz and small-ball switching value, including matchup reasons to retain a seven-foot center elsewhere on the roster.

Raise defensive motor, recognition, navigation and mobility. Raise help deterrence modestly, not to giant rim-anchor levels. Offensive traits stay exact. On/off evidence is contextual support, not a one-to-one conversion into a trait rating; team and matchup effects remain confounders.

## Keyonte George

[Ryan Miller's KSL reporting](https://www.ksl.com/article/51394225) describes defensive shortcomings and loss of the starting role, while also reporting improved offensive decision-making. The [xRAPM table](https://xrapm.com/) dated April 12, 2026 places him at its defensive zero percentile; lower defensive values are better in that metric. [CBS analysis](https://www.cbssports.com/nba/news/grading-nba-rookie-extensions-wembanyama-george-thompson-podziemski-wallace-miller/) corroborates severe defensive concerns. No extension terms from that later article are imported here.

Lower defensive consistency, navigation, coverage recognition and rim deterrence. Preserve his shooting, passing, creation, stamina and lateral tools. Bad defensive execution is not evidence that he cannot score or move. `scheme_iq` is shared with some offensive/IQ calculations, so those derived values can move even though his offensive traits do not; this model coupling is explicitly retained, not hidden.

## Verification

`tests/test_player_tuning.py` checks exact scope against V2, preservation of health/finances/prospects, traceable evidence, old-career pinning with earned development, new-game app actions, and downstream simulation-feature changes. `scripts/verify_player_tuning.py` publishes the immutable archive and canonical outputs only after scope checks, verifies existing save/archive hashes, and records neutral-24-minute before/after grades.

Reproduce the data check with `PYTHONPATH=src:scripts python scripts/verify_player_tuning.py`. `--publish` writes the checked baseline; it is not a save migration. Existing archive contents cannot be overwritten with a different candidate. Evidence and league-floor endpoint accounting are under `output/player-tuning-2026-10-23/`.
