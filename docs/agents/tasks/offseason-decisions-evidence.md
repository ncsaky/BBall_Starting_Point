# NBA offseason decisions, 2023–2026

## Resume state

Research for the free-agency calendar and restricted free-agency work. This is the Codex worktree on `codex/offseason-decisions-evidence`. The shared board is in the main checkout. The worktree contains research only.

Player options, qualifying offers, and team options are saved. Rookie extensions, offer sheets, and early terminations and same-team returns remain. Commit each decision separately. Hoops Rumors has four years of decision trackers and signing trackers. NBA.com provides a second check on signing destinations. Basketball Reference has prior-season performance and Spotrac has prior-season payroll. The 2026 game values are available as a comparison, while using them to predict older summers would give the fit information that teams did not have.

## 1. Player options

A player option lets the player add one more year at a salary already in his contract. Declining it can clear the way for a new deal with the same team or elsewhere.

| Decision summer | Kept option | Declined | Declined and stayed | Correct when that summer was held out | Majority baseline |
|---|---:|---:|---:|---:|---:|
| 2023 | 13 | 9 | 4 | 15/22 | 9/22 |
| 2024 | 12 | 15 | 7 | 14/27 | 12/27 |
| 2025 | 10 | 10 | 8 | 12/20 | 10/20 |
| 2026 | 10 | 11 | 9 | 10/21 | 10/21 |

Compare the option with what similar players earned on new deals. The threshold selected on the other three summers ranged from 80% to 110% of the option salary. In two folds the fit also used a lower threshold for players 30 and older. Those rules got **51 of 90** decisions right versus **41 of 90** for the training summers' most common choice. They were about even on the 2026 test. The observed price gap is a useful input for negotiations, but these data give little support for a single automatic percentage.

The price estimate uses the median annual salary, as a share of the cap, of the nine nearest unrestricted signings in the eligible comparison years. Similarity is based on age, games, minutes, the player's estimated total contribution above a replacement player, and his contribution per possession. A player is never his own comparison. The fit uses prior-season box scores, and historical salaries from three other summers at test time. The saved game rating is a 2026 comparison. Games played measure availability and include absences for reasons other than injury. Named injuries are recorded where verified. The comparison prices omit guarantees and the certainty of a longer offer. [Prior-season box score example](https://www.basketball-reference.com/leagues/NBA_2026_advanced.html) · [Free-agent contract tracker example](https://transactions.hoopsrumors.com/widget/free-agent-signings/2026/)

Bruce Brown left Denver's $6.8 million option in 2023 and secured a much larger contract in Indiana. Kyrie Irving gave up a $43 million Dallas option while recovering from a torn knee ligament and agreed to three years and $119 million with Dallas. Lonzo Ball sat out the prior season and kept his $21.4 million Chicago option in 2024. In that same summer Richaun Holmes gave up his option in an extension with Washington. Opt-ins that facilitate a trade, including Kristaps Porziņģis in 2023, are counted as opt-ins. [2023 option decisions](https://www.hoopsrumors.com/2023/04/nba-player-option-decisions-for-2023-24.html) · [2024 option decisions](https://www.hoopsrumors.com/2024/04/nba-player-option-decisions-for-2024-25.html) · [Irving agreement](https://www.hoopsrumors.com/2025/06/kyrie-irving-to-decline-option-re-sign-with-mavs-on-three-year-deal.html) · [2026 option decisions](https://www.hoopsrumors.com/2026/04/nba-player-option-decisions-for-2026-27.html)

## 3. Qualifying offers

A qualifying offer is a one-year contract the player can accept. It also lets his old team match a signed offer from another team. A two-way contract splits time between the NBA and its developmental league.

| Summer | Standard contracts, sent / known candidates | Two-way contracts, sent / tracker candidates | Standard decisions correct | Majority baseline |
|---|---:|---:|---:|---:|
| 2023 | 13/27 | 32/45 | 18/27 | 14/27 |
| 2024 | 11/27 | 17/56 | 20/27 | 16/27 |
| 2025 | 10/18 | 27/53 | 13/18 | 8/18 |
| 2026 | 13/28 | 18/46 | 23/28 | 15/28 |

For standard contracts, offer it to players who logged **about 1,000 minutes** the previous year. Three folds chose 1,000 and the other chose 500. The rule got **74 of 100** decisions right against **53 of 100** for the training summers' most common response. Raising the threshold for bigger offers or high prior payroll, or adding a box-score contribution shortcut, did not win a fold. Indiana tendered Isaiah Jackson after his Achilles injury. Check what the team would owe if the player accepts and allow exceptions for injured rotation players. [2023 qualifying offers](https://www.hoopsrumors.com/2023/06/2023-nba-qualifying-offer-recap.html) · [2024](https://www.hoopsrumors.com/2024/06/2024-nba-qualifying-offer-recap.html) · [2025](https://www.hoopsrumors.com/2025/06/2025-nba-qualifying-offer-recap.html) · [2026](https://www.hoopsrumors.com/2026/06/2026-nba-qualifying-offer-recap.html)

NBA playing time was weak for two-way decisions. The tested rules got 39/55, 27/52 and 20/44 right for 2024–26. In 2024 the fitted rule predicted no offers. In 2025 and 2026 it used 250 minutes and identified about half or fewer of both classes on average. The 2023 no-offer list may include players who failed the old roster-day requirement, so its holdout cannot give a fair score. Overseas rights retained without a new roster decision are included in counts and excluded from fitting. [2017 agreement](https://cosmic-s3.imgix.net/3c7a0a50-8e11-11e9-875d-3d44e94ae33f-2017-NBA-NBPA-Collective-Bargaining-Agreement.pdf) · [2023 agreement](https://nbpa.com/cba/)

| Summer | Same-team deal reported in June / July or later / date unknown | Signed outside offer, matched / passed | Accepted, standard / two-way | Offer withdrawn / rights renounced |
|---|---:|---:|---:|---:|
| 2023 | 6 / 8 / 16 | 2 / 0 | 1 / 1 | 4 / 1 |
| 2024 | 5 / 7 / 9 | 0 / 0 | 1 / 1 | 5 / 3 |
| 2025 | 6 / 5 / 12 | 0 / 1 | 2 / 4 | 4 / 2 |
| 2026 | 4 / 6 / 8 | 2 / 1 | 0 / 3 | 2 / 1 |

June counts use public agreement dates. The player often formally signed in July. An offer withdrawal and a renunciation can both appear on one row, and the player may still sign later. San Antonio withdrew Sandro Mamukelashvili's offer and re-signed him in 2024. Brooklyn's Trendon Watford took his one-year offer that summer, an acceptance missed in the earlier free-agency report. Jalen Duren negotiated a long-term return in October 2026. [RealGM 2024 register](https://basketball.realgm.com/nba/transactions/league/2025) · [Watford acceptance](https://www.hoopsrumors.com/2024/07/nets-trendon-watford-signs-qualifying-offer.html) · [Duren agreement](https://www.hoopsrumors.com/2026/10/jalen-duren-to-re-sign-with-pistons-on-five-year-deal.html)

The candidate lists are a public tracker census. Teams do not have to report every unissued offer or unsuccessful negotiation. Some two-way signing dates are missing. Of the 100 standard candidates, 32 lack an amount and another four have only a minimum-based lower bound. Payroll is Spotrac's prior-season active payroll. Those gaps limit what the fits say about offer size and the team's exact room on the decision date. [Qualifying-offer amounts](https://www.hoopsrumors.com/2026/05/hoops-rumors-glossary-qualifying-offer-3.html) · [Spotrac payroll example](https://www.spotrac.com/nba/cap/_/year/2025)

## 2. Team options

A team option lets the club add a year at an agreed price. The first-round rookie contract's third- and fourth-year options get decided in the fall, about a year before the option salary is paid. The table groups by decision year. Waivers that cancelled a live option are counted in the declined column and flagged in the data. An earlier waiver or third-year decline that already ended the contract removes any later decision.

| Decision year | Standard exercised / declined | Rookie year three exercised / declined | Rookie year four exercised / declined | Standard calls correct | Rookie calls correct |
|---|---:|---:|---:|---:|---:|
| 2023 | 12 / 9 | 29 / 1 | 24 / 5 | 15/21 | 48/59 |
| 2024 | 10 / 15 | 29 / 1 | 22 / 7 | 14/25 | 45/59 |
| 2025 | 15 / 18 | 29 / 1 | 23 / 6 | 14/33 | 45/59 |
| 2026 | 26 / 26 | 29 / 1 | 19 / 10 | 33/52 | 54/59 |

**Standard deals.** Three folds exercised when the estimated market was at least 1.2–1.5 times the option or when the team could still cut some salary after exercising. One fold chose 500 minutes. The fits got **76/131** correct versus **68/131** for the baseline. Some teams declined cheap options to sign a longer deal. Oklahoma City did that with Isaiah Joe and Aaron Wiggins in 2024. Keeping a lightly guaranteed option can preserve a choice through camp. Keeping a player via a new deal, and keeping him on the last year of his current deal, solve different needs. [2023 team options](https://www.hoopsrumors.com/2023/04/nba-team-option-decisions-for-2023-24.html) · [2024](https://www.hoopsrumors.com/2024/04/nba-team-option-decisions-for-2024-25.html) · [2025](https://www.hoopsrumors.com/2025/04/nba-team-option-decisions-for-2025-26.html) · [2026](https://www.hoopsrumors.com/2026/05/nba-team-option-decisions-for-2026-27.html)

**First-round deals.** Teams picked up **116 of 120** third years. For fourth years, the tests selected 700–1,000 prior minutes with a replacement-level box score in three folds, and 1,000 minutes alone in the fourth. The rule got **192/236** right, against **204/236** for exercising all options. It was better at finding declines, since always exercising finds none. For the live decisions that remained after excluding waivers, it got 45/54, 45/58, 45/54, and 49/55. A poor prior year is a reason to review a fourth-year salary. It is a noisy reason to cut someone automatically. For example, Oklahoma City picked up Chet Holmgren's third-year option after the foot injury that cost him his first season. Memphis declined Jake LaRavia's fourth year despite recent rotation minutes. The yearly counts include only the events in the decision recaps and omit options already lost in a previous year's waiver or decline. [Fall 2023](https://www.hoopsrumors.com/2023/11/recap-of-2024-25-rookie-scale-option-decisions.html) · [Fall 2024](https://www.hoopsrumors.com/2024/11/recap-of-2025-26-rookie-scale-option-decisions.html) · [Fall 2025](https://www.hoopsrumors.com/2025/11/recap-of-2026-27-rookie-scale-option-decisions.html) · [Fall 2026](https://www.hoopsrumors.com/2026/11/recap-of-2027-28-rookie-scale-option-decisions.html)

## 4. Rookie-scale extensions

A rookie-scale extension adds years to a first-round pick's original deal before the last season starts. The new pay begins the next year. Without an extension, the player has to finish the contract and receive a qualifying offer to become restricted.

| Fall deadline | Extended | Finished window without extension | Waived before deadline | Restricted next summer among unextended | Correct vs. baseline |
|---|---:|---:|---:|---:|---:|
| 2023 | 14 | 13 | 0 | 5 | 17/27 vs. 13/27 |
| 2024 | 11 | 13 | 0 | 7 | 18/24 vs. 13/24 |
| 2025 | 9 | 12 | 1 | 6 | 13/21 vs. 12/21 |
| 2026 | 7 | 14 | 2 | Pending summer 2027 | 20/21 vs. 14/21 |

The rule chose players with a strong prior season, usually at least **1.0 in Basketball Reference's estimate of total contribution above a replacement player**. The 2024 fold chose 0.5. It got **68/93** decisions right, versus **52/93** for the baseline. The fit tests whether a deal happened. It does not separate a team that didn't make an offer from a player who declined one. Tyrese Maxey's 2023 wait helped Philadelphia preserve spending room for the following summer. Jonathan Kuminga's 2024 wait gave the sides another year to establish his price. [2023 extension recap](https://www.hoopsrumors.com/2023/10/2023-nba-rookie-scale-extension-recap.html) · [2024](https://www.hoopsrumors.com/2024/10/2024-nba-rookie-scale-extension-recap.html) · [2025](https://www.hoopsrumors.com/2025/10/2025-nba-rookie-scale-extension-recap.html) · [2026](https://www.hoopsrumors.com/2026/10/2026-nba-rookie-scale-extension-recap.html)

The data record the full reported value, length and average annual pay as a share of the first extension-year cap. The maximum extensions started at a base 25% of the cap, with eligibility to rise as high as 30% for awards where the deal allowed it. There were 3, 4, 3 and 1 base maximum deals in the four years. Payton Pritchard's four years and $30 million averaged 5.3% of the 2024 cap. Christian Braun's five years and $125 million averaged 15.2% of the 2026 cap, with a reported first salary of 13.1%. Brandin Podziemski's five years and $110 million averaged 12.6% of the projected 2027 cap. The average includes reported incentives where the total includes them. Exact first-year amounts and guarantees are missing where the public source only gave a total. [2023 agreement, Article II](https://nbpa.com/cba/) · [NBA 2026 cap](https://www.nba.com/news/nba-salary-cap-2026-27-season) · [Basketball Reference salary ledger](https://www.basketball-reference.com/contracts/players.html)
