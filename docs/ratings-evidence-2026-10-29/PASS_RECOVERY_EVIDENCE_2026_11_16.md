# Pass/reception recovery evidence — November 16, 2026

**Retaining possession is not the same as preserving the scoring opportunity.** Evidence supports clean control, awkward-but-retained recovery and genuine loss as different observations. It does **not** supply reliable conditional probabilities for those outcomes. Two historical aggregate constraints were found, useful for accounting/budget checks rather than response calibration.

The [structured ledger](PASS_RECOVERY_EVIDENCE_2026_11_16.json), `pass_recovery_evidence_v1_2026_11_16`, contains ten claims, six constraint records, five controlled comparisons and explicit source/denominator/uncertainty fields. No player grades, passing fields, catalogue dimensions or operational controls are added or changed. October2026 pre-opener remains the target; older evidence is dated context, not current form. Review coverage is selected retained passages and public written sections/tables, not complete new episodes or video inspection.

## Evidence-to-mechanism matrix

Candidate implications below are **our structural inferences**, not fitted coefficients or measured effects. Exact claim IDs, source summaries and correlation groups are in the ledger.

| Claim / exact source | What it supports | Boundary and candidate implication |
|---|---|---|
| PR01 — [PG transcript](transcripts/episode8_transcript.txt), Aug5,2026 **01:28:18–01:28:40** | Broad Luka passing repertoire | No placement/catch denominator. Recognizing a target and delivering the ball remain separate from reception. |
| PR02 — [center transcript](transcripts/episode4_transcript.txt), Sep2,2026 **01:00:07–01:00:35** | Effective Holmgren rolling and catch radius | Reach makes a delivery physically accessible; it does not independently establish control technique or readiness. |
| PR03 — same transcript **01:03:46–01:04:23** | Open shooting distinguished from release-access problems | Time left after recovery can matter even when the ball is secured. Preserve shooting skill separately from available preparation time. |
| PR04 — [Pina, Jan11,2018 §12](https://www.vice.com/en/article/the-outlet-pass-dirk-back-ads-childs-play-and-denvers-enjoyable-mess/) | Retained disruption can erase the next opening | Negative example for “catchable means equally good shot.” Permit reset/no immediate shot; exact delay is unmeasured. |
| PR05 — same article **§11** | Awkward aerial receipt can remain playable | A reachable imperfect lob need not be a turnover. Securing, airborne adjustment and finishing remain distinct. |
| PR06 — [NBA, Jun8,2023](https://www.nba.com/news/finals-film-study-nuggets-heat-game-3), roll/pump-and-go sections | Roll and help-created lob contexts | Selected successes, no all-attempt denominator. Ground-roll short touch is not interchangeable with an aerial finish. |
| PR07 — [NBA metric definitions](https://www.nba.com/stats/help/glossary), Potential AST / Deflections / Passes Made | Definitions summarized in ledger | Shot-conditioned metrics exclude some retained resets. A defensive touch does not by itself establish a loss. Check units and filters before dividing. |
| PR08 — [official Jun5,2025 gamebook](https://statsdmz.nba.com/pdfs/20250605/20250605_INDOKC_book.pdf), p1; PBP Q1 **08:14/08:12/06:02**, Q2 **08:50**, Q4 **10:00/09:58** | Distinct loss labels and actual sequential possession events | Labels do not reveal delivery causality. The Q2 example follows a rebound; Q4 has successive opposite-team losses. Returning possession later does not erase the first turnover. |
| PR09 — [2018 original study](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.02315/full), **Table1; Participants; Table2** | Separate bobble/turnover coding precedent | Youth small-sided games, not NBA rates. Do not import scoring rewards, means or effect sizes as engine coefficients. |
| PR10 — [retained exposure ledger](CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.json), Luka completed/mixed-window entries | Explicit unit/window mismatch | Reject a per-pass loss rate assembled from different filters or seasons. Missing observations remain missing. |

These are not ten independent confirmations. Two retained episodes share a commentary channel; Jokić's2023 source is inherited research; highlights and written examples select notable successes/errors. The study supports a coding distinction, not NBA frequency. No new player-level inference is made from fame, height, total assists or aggregate turnovers.

## What the numbers actually constrain

| Constraint | Population and denominator | Valid use / rejected use |
|---|---|---|
| PC01: IND **25**, OKC **7** team turnovers; player-column sums **24**, **6** | Jun5,2025 IND–OKC, one48-minute regulation game per team; final box p1 | One team event beyond each player sum. Reconcile counts without duplication. Not a league average or pass-error target; no full subtype tally reconstructed. |
| PC02: Luka **255/64 = 3.984375** turnovers per game | Retained raw ESPN2025–26 regular season, LAL,64 games; total-turnover numerator | A matched scorer-attributed seasonal budget only. Do not calculate from rounded4.0×64 or constrain causal passer responsibility to scorer credit. No per-pass denominator. |
| PC03: retained **2,753 passes made**, **3,454 received**, **3,249 touches** | Count-like mixed provider fields, generated Mar11,2026; exact per-field units/coverage unverified | Reject255/2753. Full-season turnovers and these fields do not share a verified window. No conversion to clean/awkward percentages. |
| PC04–05 | Local tracking registry has no observations; study is non-NBA with no matching all-pass denominator | Neither supplies the missing conditional rates. |

PC02 raw games/turnovers were rechecked in [the retained ESPN response](../../data/research/espn_career_raw/3945274.json), using season2026 averages/totals rows. Assists in that row were also checked for lineage, not used as successful-catch counts. Player-specific scorer-charged subtypes cannot exceed the corresponding total; causal responsibility may differ. Repeated controlled roll/lob/pop trials are not that full-season action mixture.

Denominator discipline matters: a released pass attempt, reception, touch, shot, possession and game are different observation units. Potential assists are already conditioned on a subsequent shot; catch-and-shoot percentages are conditioned on attempts. Neither observes all failed deliveries or retained possessions that reset. Bad-pass/lost-ball scorer labels do not identify a clean/awkward receipt split, and lost-ball events can follow rebounds or dribbles. Deflections and recoveries can occur without a possession change; they are not additional turnovers to add to an eventual loss.

## Candidate observation model and comparisons

For a **declared cohort of released passes**, record mutually exclusive observation states: clean retained; awkward live retention (including a teammate recovery); retained stoppage; live loss; dead-ball loss; unresolved at the observation horizon. Resolve or censor the last category explicitly. Declare stable control separately from first touch: an ongoing bobble is not a completed receipt. A later strip after resolved reception or a steal-back is a separate event, rather than retroactively changing an earlier clean receipt or deleting an earlier loss. This is a proposed coding protocol, not a claim that public tracking uses these labels.

Record the delivered trajectory/timing, intended and actual receiver, first-control time, correction movement, ready-to-act time, remaining clock and defender geometry at the actual next action. These distinguish securing the ball from recovering the original position. Receiver skill can help retain an imperfect pass without guaranteeing the original shot; physical reach can expand access without granting perfect control. Defensive recovery can close a window during a gather. A poor next shot should arise from the changed state/choice, rather than an unexplained universal accuracy penalty.

Use matched comparisons, with no percentage ranges prescribed:

1. Vary delivery endpoint/timing at fixed route, skills and starting defense: on target; reachable but awkward; outside the reachable envelope. Do not force every tiny error to cause a turnover.
2. Change receiver technique at fixed geometry, then geometry at fixed technique. This separates S14 from reach, jump and balance.
3. Change interception access or defensive recovery timing separately. Count one actual loss once, while retaining defensive-contact information.
4. Among retained receipts, vary clock/closure opportunity and observe readiness, release contest, reset and no-shot outcomes. Do not treat a recovered pass as automatically ready to shoot.
5. Report ground-roll, lob and perimeter-outlet/pop strata separately, with their released-attempt denominators and losses. Use F03/F04/F06 recognition/execution and S14/S08/S26 according to their [approved meanings](../PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md), rather than adding duplicate general-passing or catch bonuses.

The outcome counts must reconcile to the declared attempts, including unresolved observations. This identity and nonnegative counts are structural checks, not empirical calibration. Useful next evidence would be a small consecutively sampled, independently coded set of attempted passes, including failures/resets, with pressure and readiness observations—not another highlight compilation. No acquisition or coding campaign is launched here.

## Verification and stop point

[Validation](diagnostics/pass_recovery_20261116/validation.json) covers ledger references, registered IDs, arithmetic, retained-source links and eleven local source hashes. The prior milestone11 packet matches its delivery hash; its ratings/catalogue remain unchanged. [Reviewed gamebook facts](diagnostics/pass_recovery_20261116/reviewed_gamebook_facts.json) retain the transcribed counts/locators; they are not a downloaded original-file checksum.

FIBA's manual exceeded the tool size limit; PMC showed an anti-bot page, while the publisher article was accessible. One local copy request for the web-readable gamebook timed out and was not retried. No subscription, full-video review, complete PBP review, backend outcome inspection or simulation is claimed. No production files, saves or shared trackers changed. No human clarification is required.

**Calibration finding:** actual aggregate accounting constraints were found; an empirical conditional clean/awkward/loss calibration rate or response coefficient was **not** found. Stop for coordinator review.
