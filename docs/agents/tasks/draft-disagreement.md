# How much draft boards disagree

**TL;DR.** Scouts now give more weight to the kinds of players their staff values when coverage is thin. Better staffs still estimate current ability and potential more accurately.\
In the separate generated draft, the typical gap doubled from three to six spots in the second round. The NBA gap was nine. Four of the first five picks stayed within four spots of consensus.\
Across the four game drafts, eight of 40 consensus top-ten prospects slid at least five spots, up from five. Large reaches averaged lower true talent in each pick range.

## Where teams used to disagree

I rebuilt the June boards for all 30 teams using the same four drafts as the earlier study. I removed one influence at a time and rebuilt the boards. The figures below are the typical spread in **grade points**, measured as the average standard deviation across the teams for each prospect. The columns use the prospects' starting public ranks so the same players are compared in every run. The effects can overlap. [Original draft study](draft-decisions-evidence.md)

| What went into the old scouts' grades | Public ranks 1–5 | 6–14 | 15–30 | 31–60 |
|---|---:|---:|---:|---:|
| Everything | 2.25 | 2.84 | 4.31 | 4.47 |
| Removed estimation error | 1.85 | 2.10 | 1.88 | 1.63 |
| Gave teams equal coverage of each prospect | 2.25 | 2.81 | 4.20 | 4.40 |
| Gave every prospect the same coverage | 4.37 | 4.37 | 4.19 | 3.65 |
| Gave every staff the same preferences | 1.21 | 1.85 | 3.94 | 4.24 |
| Gave every staff the same skill | 2.20 | 2.63 | 3.91 | 4.12 |

Estimation error explained most of the old late-board spread. For ranks 31–60, removing it lowered the spread from 4.23 to 1.03 points in 2026, and from 4.62/4.51/4.50 to 2.08/1.66/1.76 in the three generated classes. Giving prospects equal coverage took away the top prospects' advantage of being watched much more. Teams usually watched about 100% of the top five by June and 49% of ranks 31–60. Differences in how much two teams watched the *same* prospect explained relatively little.

I also ranked the same available players for every general manager at a representative pick in each range. Removing the rebuilding or contending adjustment moved the typical spread by at most 0.16 draft spots across the four ranges. Removing roster need moved it by at most 0.11 spots. These comparisons measure how the rankings differ between teams. An individual close decision can still swing on fit.

## What changed

Staff preferences now affect the talent grade based on the traits the staff sees. A staff that values shooting can rank a strong shooter higher. The preference has more influence where coverage is thinner, and the ability estimates keep their own uncertainty. A top-five pick also carries an extra cost of 1.5 grade points for each spot beyond a two-spot reach. The four drafts' grade spreads rose from 2.25 / 2.84 / 4.31 / 4.47 points to **2.54 / 4.12 / 8.30 / 10.19**. When I removed staff preferences from the revised model, the late spread dropped from 10.19 to 4.24. With estimation error removed it was 8.91. The rankings are seeded and still use the same reports month to month as new information arrives.

I fitted to the 2012–2021 NBA results and the 2031 and 2032 generated classes, using the same seeds and rosters as the first study. The search tested five levels of added coverage-related upside error, five strengths of staff preference, and six reach penalties over several tolerances. The score emphasizes pick gaps and reach rates, with a quarter assigned to top-ten slides and falls out of the lottery. The initial fit without the extra top-five cost produced three ten-spot reaches in the first five picks of the 2033 check. I added the early-pick cost and refitted using the original training split. The final choice keeps the original estimation-error scale, uses a stronger preference term, and charges 0.40 grade points per point of pick value beyond a six-point tolerance. With the new model, zero general reach cost scored 0.61 at best on the training split versus 0.52 for the chosen setting. The earlier model scored 1.09. Lower scores mean a closer fit.

## Draft results

Each cell gives the **median absolute gap in spots**, followed by the share of picks that reached **five / ten spots** ahead of the board. Game comparisons use the league consensus for their version of the board. The NBA figures come from the historical public boards. [Draft evidence data](../../../data/research/draft_decisions_evidence.json)

| Picks | Game 2031–32 before | Game 2031–32 after | NBA 2012–21 | Game 2033 before | Game 2033 after | NBA 2022–25 |
|---|---:|---:|---:|---:|---:|---:|
| 1–5 | 0 · 11% / 0% | 1 · 0% / 0% | 1 · 12% / 0% | 0 · 20% / 0% | 0 · 20% / 0% | 0.5 · 0% / 0% |
| 6–14 | 2 · 6% / 0% | 2 · 22% / 17% | 3 · 29% / 21% | 1 · 13% / 0% | 5.5 · 38% / 25% | 3 · 28% / 14% |
| 15–30 | 3 · 13% / 0% | 7 · 32% / 23% | 6 · 37% / 25% | 3.5 · 19% / 0% | 5 · 31% / 6% | 6.5 · 36% / 23% |
| Second round | 4 · 13% / 3% | 8 · 20% / 12% | 10 · 44% / 32% | 3 · 7% / 3% | 6 · 20% / 13% | 9 · 42% / 29% |

| Among consensus top-ten prospects | Game 2031–32 before | Game 2031–32 after | NBA 2012–21 | Game 2033 before | Game 2033 after | NBA 2022–25 |
|---|---:|---:|---:|---:|---:|---:|
| Slid five or more spots | 4/20 | 4/20 | 14/100 | 1/10 | 3/10 | 7/40 |
| Went after pick 14 | 1/20 | 2/20 | 9/100 | 0/10 | 1/10 | 4/40 |

The separate comparison improved its overall score from 1.16 to 0.78. The one top-five reach in 2033 was one pick out of five, both before and after. Picks six through 14 strayed farther than in the NBA check, and large reaches were still scarce from pick 15 onward. All generated classes here had 60 eligible prospects. In the later NBA drafts, 27 of 113 second-round picks went to someone outside the public top 60 or missing from the composite. Among the 86 picks of public top-60 players, the typical gap was seven spots and 24% / 10% were five- / ten-spot reaches. That is closer to the game's six spots and 20% / 13% on the separate class.

| Picks | Rebuilt 2026 game before | Rebuilt 2026 game after |
|---|---:|---:|
| 1–5 | 1 · 0% / 0% | 1 · 0% / 0% |
| 6–14 | 2 · 11% / 11% | 8 · 56% / 44% |
| 15–30 | 2 · 19% / 6% | 9 · 25% / 19% |
| Second round | 2 · 13% / 0% | 5.5 · 27% / 13% |

In the rebuilt 2026 draft, one of ten top-ten prospects slid at least five spots and fell out of the lottery. Both counts were zero before. This is the archived prospect class run on game teams and rosters. The separate rookie-ratings work was outside this comparison.

Three fresh generated classes, 2034–2036, checked the revision after the 2033 test exposed the top-five problem. Across those drafts the typical gap stayed at one spot in the top five, grew from four to 6.5 at picks 15–30, and grew from four to six in round two. One of 15 top-five picks reached five spots, down from two. Eight of 30 top-ten prospects slid five or more spots, and five went after pick 14. Both rates were above the later NBA sample.

## Did reaches work out?

Across the 237 game picks, a player chosen five or more spots early averaged less true talent than a player chosen within four spots of his board ranking in every pick range. True talent uses the game's actual current ability, potential, floor and ceiling with the standard risk adjustments. It is a check on draft choices before player development. The NBA numbers measure actual value over replacement through year four. [Four-year NBA outcome comparison](draft-decisions-evidence.md#what-happened-by-year-four)

| Pick range | Game true talent, reach / within four before | Game true talent, reach / within four after | NBA 2012–21 four-year value, reach / within four |
|---|---:|---:|---:|
| 1–5 | 66.7 / 74.2 | 68.4 / 73.1 | 0.77 / 4.12 |
| 6–14 | 64.5 / 69.0 | 60.2 / 69.0 | 1.17 / 1.89 |
| 15–30 | 57.2 / 62.2 | 55.0 / 60.9 | 0.84 / 0.85 |
| Second round | 45.8 / 48.0 | 46.9 / 47.1 | 0.07 / 0.48 |

The direction held in each range in 2033. The only revised top-five reach was slightly better than the best consensus prospect still available on that specific turn. From pick six on, reaches averaged 9.3 to 13.3 grade points below the best consensus player left when the team picked, across all four drafts.

## The user's scouts

Toronto's June board matched the reports the AI used for the same team and month across all four classes. The board entries include the same rank, grade and coverage values. In the 2026 run Toronto agreed with the consensus on Cameron Boozer, AJ Dybantsa, Darryn Peterson and Caleb Wilson in the first four spots, with full coverage. Toronto ranked Koa Peat fifth versus tenth on the consensus, with 78% coverage. The draft tests also check what the user's player cards show, the effects of skill on coverage and error, and that a team acquiring a pick makes its own choice.

I kept Toronto's lead, preferences and seeded reads fixed and changed the staff's skills from 50 to 85. Across all four classes, average coverage rose from 52% to 83%. The stronger staff's average current-ability error was 1.0 points versus 2.8. Its average full-potential error was 4.1 points versus 7.7, and the advantage held in each class. The stronger preference term increased grade errors against a neutral true-talent grade for both staffs. The stronger staff still averaged a 3.2-point miss versus 6.0 for the weaker one.

## Speed

I timed three cold scouting builds and three selection-only drafts for each of the four classes. The table gives the median of the four class medians. The scouting update builds the April reports for all 30 teams.

| Work timed | Before | After |
|---|---:|---:|
| Monthly scouting build | 99 ms | 80 ms |
| Selection-only draft | 140 ms | 118 ms |
| Full draft room | 29.17 s | 29.63 s |

The draft-room figure is the median of three runs from the same copied 2029 Toronto lottery save. Each run applied 59 picks and returned nine draft-trade notices. The ranges were 28.12–30.64 seconds before and 28.79–33.30 after. The 0.46-second median increase was smaller than the variation between repeats.

## Verification

The real-stat replay matched every printed measurement from the old version and stayed at **18 of 18** targets in range over 1,230 games. The core suite ran 351 tests with no failures and one skip. The skip is an older trade-salary suite whose archived fixture is missing. The original draft evidence and the final training search both reproduced byte for byte.

All 38 draft tests and 32 other board, app and lifecycle checks passed. The draft-year test now finds the shared scripts folder using the same import pattern as the audit tests. The 13 duplicate-pick tests build their own disposable save and draft.

## Reproduce the probes

The main comparison uses a selection-only draft with fixed owners. The live timing includes the draft room's normal trades, signings and save writes. Use the source at `4e348eb` on the Python import path for the before comparison. The original evidence script's default action still rebuilds the historical file.

```sh
mkdir -p output/draft-disagreement
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --disagreement --output output/draft-disagreement/verified-after.json
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --fit-disagreement --output output/draft-disagreement/verified-fit.json
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --time-live-draft --output output/draft-disagreement/live-after.json
```

## Resume state

Ready for review on the draft disagreement branch, which starts at `4e348eb`. The settlement fixture is linked from the main checkout. Raw measurements are in `output/draft-disagreement/`.
