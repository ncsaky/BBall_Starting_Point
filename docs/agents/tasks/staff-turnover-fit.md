# AI staff turnover

## TL;DR

- The old rules put most neutral coordinators below the renewal bar and counted losing streaks against the assistants as well as the head coach.
- The NBA evidence points to about two head-coach firings in season and three in summer. For assistants, the biggest signal is whether the head coach changed.
- The game has two assistant slots. The comparison uses the proportion of the old bench that left, alongside the real-world counts.

## Scope and old rules

This work covers AI head coaches, offensive and defensive coordinators, and reviews of the three modeled support roles. The six employed slots do not include a general manager or president. Front-office profiles set team AI behavior and carry no executive employment or firing process.

| Decision | Before the fit |
|---|---|
| Calendar and limits | Staff bundle on month changes, February 5, and during training camp, offseason, lottery, draft, re-signing and free agency. Processing allows 8 recommendations per bundle and one firing or direct hire per team/slot/season, with a permanent hire allowed after an interim. Permanent head-coach firing ceilings were 3 in season and 6 cumulatively for the season by summer. The summer recommendation mix aimed for 4 head-coach reviews minus prior firings. The executor skipped the human team. |
| Record and injury context | Estimated win percentage was .25 + contention ceiling ÷ 170, bounded .25–.72. After 20 games, a .12 miss added pressure and a .06 miss added head-coach pressure. Both required fewer than 18 projected minutes currently injured. Skid lookback was 17 games. |
| Shared firing score | Threshold 28 on February 5, September 1, October 1 and in summer phases, 36 otherwise. Interim +32, expired deal +22, grade below 56 +8 and .85 per point below 56, grade below 72 +.20 per point below 72, non-interim grade 86+ −5.5. Security 72+ subtracted up to 7 at .28 per point and security 48 or lower added up to 7 at .32 per point. Underperformance added 8 plus .10 per pressure point above 65. Pressure 76+ added 5. Contenders added 3, rebuilders/developers added 4 for development and scouting, and calendar checkpoints added 3. Non-head slots took −6. A previously fired slot now held by an interim added 9. |
| Head-coach firing score | Underperformance added 9, a .06 miss added 5.5, and 8 losses over at least 12 recent games added .85 per loss, capped at 13, with the injury guard. Ten recent losses added 1.15 per loss, capped at 18, with the same guard. The seasonal review added 8 for missing expectations, below .42 winning percentage, or grade below 72. A second seasonal bonus of 9 applied with fewer than 4 firings/reviews and a miss, below .44 winning percentage, or grade below 74. Ordinary reviews added 5 with fewer than 2 firings/reviews and a .12 miss or 9 recent losses. A grade-82+ head coach lost 8 firing points if a weak coordinator was present and the team had 8 recent losses. With no candidate, firing alone needed another 12 points. |
| Coordinator firing score | Eight losses over at least 12 recent games added 12 if the assistant trailed the head coach by more than 7 and the injury guard cleared. The weaker coordinator picked up another 7 for underperformance or 7 recent losses if their grade was at most 72 and more than 6 below the head coach. |
| Support-staff firing score | Seasonal reviews added 13 for below-target development and 12 each for poor draft return or at least 170 injury games missed. Development needed at least 12 events and positive trait gains below max(1.2, .075 × events). Poor draft return meant every tracked top-20 rookie was below 45 current ability and 66 potential. |
| Market and offers | Considered the first 18 per role. Current grade ≤68 with market grade ≥82 added 10 to firing pressure. A market grade ≥88 with a 7-point upgrade added 8. Current grade ≤76 and an available grade ≥82 with a 6-point upgrade added 5.5. Required an upgrade of 7 for permanent heads or 5 otherwise, eased to 3 for an 82+ candidate replacing a grade ≤68. Candidates could ask up to 108% of the recommendation budget. Ranked by upgrade plus .12 × salary headroom capped at 8, with ±1.5 seeded noise on the recommendation score. Negotiation separately required the authoritative budget, a hiring score ≥−1.5, and 100% of ask or 96% for free agents. A 7-point gain to grade 80+ received a better-replacement reason. |
| Contract expiry | Strong grade was 76 for coaches and coordinators, 72 for support. The stable-fit floor was 68 for all roles, with no missed team expectation or unresolved failure. After 30 games, falling more than .10 short of the strategy forecast vetoed retaining a coach/coordinator below 88. A role-specific failure vetoed retention below 82. The offer aimed for the greater of 103.5% of old pay and 97% of the market contract, with budget exceptions only for grade 88+ and room for 96% of old pay. Renewal lasted 2 years or 3 at grade 78+. |
| Career exits and market supply | Separately seeded aging and retirement apply every year. The pool refills to at least 20 head-coach candidates and 16 per other role. A coordinator can enter the head-coach market, preserving their person identity. |

Sources and real-world targets are in [NBA staff turnover evidence](staff-turnover-evidence.md) and [the underlying data](../../../data/research/staff_turnover_evidence.json).

## Resume state

The old rules have been traced. The full two-season baseline uses a detached copy of the starting commit and opening staff snapshots, with the Azure run queued behind an existing job.
