# ROOKIE-FIT: 2026 rookies' starting ratings from college evidence

**TL;DR**
- **Rookies' starting ratings now come from their last college season**, through a fit of how college play turned
  into first-year NBA play for every drafted college player since 2009. Draft slot barely matters to that fit: it
  adds almost nothing once you know a player's college numbers.
- **Lendeborg moves up (28th to 20th of the rookies, 518th to 385th in the league), but not to the top.** The
  evidence says older, very productive seniors are somewhat MORE ready than their draft slot suggests, but a
  24-year-old's college numbers overstate him a bit compared with a 19-year-old's same numbers. Without that age
  discount he would be about 7th of the class.
- **The class is flatter and more honest:** all rookies now sit between 69.8 and 75.1 overall (was 67.4-79.9), the
  productive bigs and two-way college players (Boozer, Graves, Wilson, Onyenso, Mara) rise, and high-usage freshman
  guards drop (Peterson 69th to 326th, Brown, Acuff, Philon). Real rookies are below-average NBA players on
  average, and the game now says so. Veterans' inputs are unchanged.

_Status: **review**. Claude Opus agent, worktree branch `worktree-agent-a7e1308eb189afdd2`, 2026-11-22._


## 1. What the evidence says (drafts 2009-2025)

**Data.** Every drafted college player's final college season (Barttorvik tables; 799 players, drafts 2009-2025)
against his first NBA season: Basketball Index LEBRON split into offense and defense (the same impact scale the
game's player value is fitted to) and Basketball Reference box plus-minus and minutes. A player who missed his
whole first season and then played a real one (Griffin, Embiid, Simmons, Holmgren) is judged on that real season.

**Who gets minutes.** Many rookies barely play, so "how good were the rookies who played" flatters late picks. Every
drafted player counts instead: his rookie impact is pulled toward the level of rookies who barely play, more the
fewer minutes he got (a player who never plays sits at that level: -1.5 LEBRON, -3.7 box plus-minus; it takes 750
minutes to count half). Fits on the selected players only are kept in the bundle for comparison (same signs,
larger sizes).

**College inputs.** Box plus-minus split into offense and defense, usage, true shooting, rebound, assist, steal,
block and turnover rates, free-throw rate, three-point share, volume and accuracy (career, shrunk toward typical),
free-throw accuracy, height, age on draft day, team strength (Barttorvik's adjusted efficiency rating), minutes
share, and age x production (offense and defense). Ridge regression; strength picked by leaving one draft out.

**Checks on drafts the fit never saw** (fit 2009-2019, scored on 2020-2025, 274 players; and every draft left
out in turn):

How well each approach predicts first-season impact (correlation; 1 is perfect, 0 is nothing):

| What predicts it | Drafts the fit never saw (2020-2025) | Same, rookies with 1,000+ minutes only | Every draft left out in turn |
|---|---:|---:|---:|
| Draft slot alone, total impact (LEBRON) | 0.08 | 0.06 | 0.08 |
| College numbers, total impact | 0.49 | 0.65 | 0.41 |
| College numbers + draft slot, total impact (used) | 0.48 | 0.64 | 0.41 |
| College + slot, offense only | 0.27 | 0.34 | 0.31 |
| College + slot, defense only | 0.62 | 0.76 | 0.53 |
| Draft slot alone, box plus-minus | 0.37 | 0.17 | 0.38 |
| College + slot, box plus-minus | 0.54 | 0.54 | 0.51 |

Plain reading: college production is a much better guide to a rookie's first year than where he was picked.
Draft slot has some value for box plus-minus (top picks get the ball and the box score) but almost none for LEBRON
once college numbers are known. Defense carries over from college far better than offense (blocks, steals,
rebounds and size travel; college scoring efficiency less so). First-year impact is hard to predict: even the
best model explains about a quarter of it (two-fifths for rookies who played real minutes).

What real rookies look like (players with 500+ minutes, average first-season LEBRON): picks 1-3 -0.7, picks 4-10
-1.5, 11-20 -1.6, 21-30 -1.6, second round -1.2 to -1.4 (the few second-rounders who play are the good ones).
93% of picks 1-10 reach 500 minutes; 20% of picks 46-60 do. Average NBA player is 0.


**Do older, highly productive seniors arrive more NBA-ready than their draft slot suggests?** Yes, a little,
but less than their college numbers alone suggest. Out-of-sample averages (positive = better than predicted):

| Group | Players | Typical pick | vs draft slot | vs college numbers + slot |
|---|---:|---:|---:|---:|
| Older (22.5+), college box plus-minus 9+ | 45 | 35 | **+0.12** | -0.05 |
| Older (22.5+), less productive | 118 | 44 | +0.02 | -0.01 |
| Younger (under 21), college box plus-minus 9+ | 81 | 9 | **+0.40** | +0.12 |
| Younger (under 21), less productive | 289 | 20 | -0.18 | -0.01 |

(First-season LEBRON, after the minutes adjustment; the box plus-minus version says the same: +0.25 vs slot for
productive seniors, +0.62 for productive young players.)

- Productive seniors beat their draft slot, so teams do discount them a bit too much on day one.
- Productive young players beat their slot by much more: production at 19 is a stronger signal than at 23.
- The fit found that a year of age makes each point of college production worth less (the age x production terms
  are negative for both offense and defense and improve every held-out check slightly). Age on its own adds
  essentially nothing to day-one ability (standardized weight +0.01 for LEBRON, -0.05 for box plus-minus).
  So age mostly belongs in growth room, as asked; this task changes only day-one ability. (Development is the
  development-curve agent's area; nothing here touches potential.)
- For Lendeborg: projected first-season LEBRON -1.29 (offense -1.09, defense -0.18), 18th of 50 by projection.
  Without the age x production terms (the sensitivity run) he would be -0.93, 7th. A typical pick 11 projects
  about -1.4 to -1.5, so the evidence does say he arrives readier than his slot.


## 2. How it reaches the game

1. **College numbers as evidence for specific skills.** The fitted college-to-NBA skill mapping the real 2027-2029
   prospects already use (`data/canonical/real_prospects.json`) turns each rookie's college line into evidence for
   the skills it speaks to: shooting from three-point and free-throw shooting, rebounding from rebound rates, rim
   protection and contests from block rate and height, steals and passing-lane reads from steal rate, passing from
   assist rate and assist-to-turnover, handling and creation from usage, self-created shots and turnovers. 46 of
   the 64 skills get a labelled college evidence entry (source, minutes, how well college predicts that skill),
   weighted like the 2027-2029 prospects. The other 18 stay labelled as estimates.
2. **The level from the translation fit.** Each rookie's projected first-season offense and defense is placed on
   the game's value scale by the same line that links veterans' real 2025-26 LEBRON to the game's value of their
   inputs (274 veterans with 1,000+ minutes; offense 0.87 + 0.79 x real, defense 0.74 + 0.70 x real). One shift
   per side of the ball (all offensive skills together, all defensive skills together; free-throw shooting
   excepted) moves his skills until the game values him at that level. The shift keeps his shape: what he is
   good at relative to his own game still comes from his college numbers. Shifts ranged from -0.46 to +0.18
   (offense) and -0.08 to +0.39 (defense) on the log-odds scale, about -11 to +9 skill points. Every rookie ended
   within 0.03 points per 100 possessions of his target; analyst claims about rookies are then applied last, as
   for every player, and move a few off it slightly.
3. **The four layers stay separate.** Only skills (technique) and involvement change. Physical tools (height,
   length, strength, jumping: the existing listed measurements and draft-combine evidence) and the other
   tendencies are untouched. Involvement (how much of the offense he wants) takes college usage as evidence on
   the measured scale (about a quarter weight; e.g. Peterson 54% -> 50%). Coach usage is not an input here.
4. **Old draft-model traits and the flat rookie penalty are dropped** for rookies with a college season: the
   slot-based traits were not evidence, and the flat "pre-NBA readiness" offset is replaced by the measured one.
5. **Veterans unchanged.** The rookie step runs last in the builder, after every league-wide step, so every
   veteran's 94 inputs are byte-identical (checked: only the 50 rookies differ, on their 64 skills and
   involvement; the tendency scale map is identical). Veterans' displayed ratings can still move by up to 0.05
   because the game ranks everyone against the league, rookies included.
6. **Three rookies keep the previous method** (no usable college season): Karim Lopez and Sergio de Larrea
   (overseas) and Jayden Quaintance (too few college minutes).


## 3. The 2026 class, before and after

Display overall is the number on the player card. Projected rookie impact is first-season LEBRON per 100 possessions (0 = average NBA player).

| Rookie | Pick | Age | College line (team, BPM off/def, usage, TS%, 3P%, FT%) | Projected rookie impact (off / def) | Overall before → after | Rookie rank before → after | League rank before → after |
|---|---:|---:|---|---:|---:|---:|---:|
| Cameron Boozer | 3 | 19 | Duke Fr, +16.0 (+10.2/+5.8), usg 31, TS 65, 3P 37% on 4.3/40, FT 77% | -0.65 (-0.55 / -0.18) | 74.1 → 75.1 | 15 → 1 | 350 → 263 |
| Allen Graves | 19 | 20 | Santa Clara Fr, +14.2 (+8.8/+5.5), usg 22, TS 62, 3P 37% on 4.7/40, FT 73% | -0.59 (-0.69 / +0.00) | 71.2 → 74.7 | 31 → 2 | 543 → 289 |
| Caleb Wilson | 4 | 20 | North Carolina Fr, +12.2 (+6.2/+6.0), usg 29, TS 63, 3P 32% on 1.4/40, FT 71% | -0.84 (-0.83 / -0.05) | 72.7 → 74.2 | 20 → 3 | 424 → 321 |
| Darryn Peterson | 2 | 19 | Kansas Fr, +7.8 (+5.5/+2.2), usg 31, TS 58, 3P 36% on 9.5/40, FT 79% | -1.54 (-0.81 / -0.77) | 79.9 → 74.2 | 1 → 4 | 69 → 326 |
| Ugonna Onyenso | 53 | 22 | Virginia Sr, +13.9 (+2.3/+11.5), usg 15, TS 62, 3P 32% on 2.1/40, FT 68% | -0.93 (-1.31 / +0.38) | 71.7 → 74.0 | 24 → 5 | 503 → 341 |
| Izaiyah Nelson | 51 | 23 | South Florida Sr, +9.2 (+4.3/+5.0), usg 24, TS 61, 3P 25% on 2.0/40, FT 68% | -0.96 (-1.05 / +0.06) | 69.4 → 74.0 | 42 → 6 | 638 → 342 |
| Zuby Ejiofor | 23 | 22 | St. John's Sr, +14.3 (+6.9/+7.4), usg 26, TS 61, 3P 30% on 2.1/40, FT 71% | -1.04 (-1.04 / -0.01) | 70.7 → 73.9 | 34 → 7 | 577 → 347 |
| Aday Mara | 12 | 21 | Michigan Jr, +14.6 (+4.4/+10.2), usg 24, TS 66, 3P 33% on 0.4/40, FT 61% | -0.99 (-1.24 / +0.28) | 74.5 → 73.9 | 11 → 8 | 313 → 348 |
| Maliq Brown | 44 | 22 | Duke Sr, +13.9 (+4.7/+9.2), usg 14, TS 64, 3P 31% on 1.6/40, FT 62% | -1.05 (-1.22 / +0.18) | 68.0 → 73.8 | 49 → 9 | 670 → 355 |
| Sergio de Larrea | 25 | 20 | no college season (kept the earlier method) | — | 73.6 → 73.7 | 16 → 10 | 376 → 361 |
| Dillon Mitchell | 40 | 23 | St. John's Sr, +9.9 (+3.9/+6.0), usg 16, TS 56, 3P 28% on 0.6/40, FT 52% | -1.16 (-1.20 / +0.03) | 68.2 → 73.6 | 47 → 11 | 667 → 369 |
| Tarris Reed Jr. | 26 | 23 | Connecticut Sr, +12.9 (+4.8/+8.1), usg 26, TS 61, 3P 32% on 0.2/40, FT 60% | -1.14 (-1.18 / +0.04) | 72.4 → 73.6 | 22 → 12 | 446 → 371 |
| Joshua Jefferson | 28 | 22 | Iowa St. Sr, +11.2 (+4.6/+6.7), usg 29, TS 56, 3P 32% on 4.1/40, FT 72% | -1.22 (-1.09 / -0.11) | 70.6 → 73.5 | 35 → 13 | 584 → 374 |
| Hannes Steinbach | 14 | 20 | Washington Fr, +8.7 (+5.2/+3.5), usg 24, TS 64, 3P 34% on 2.0/40, FT 74% | -1.17 (-1.02 / -0.18) | 71.5 → 73.5 | 27 → 14 | 517 → 375 |
| Dailyn Swain | 15 | 21 | Texas Jr, +9.4 (+6.1/+3.4), usg 26, TS 63, 3P 31% on 3.2/40, FT 80% | -1.21 (-0.95 / -0.27) | 69.8 → 73.5 | 40 → 15 | 619 → 376 |
| Morez Johnson Jr. | 9 | 20 | Michigan So, +11.4 (+6.1/+5.3), usg 21, TS 68, 3P 34% on 1.4/40, FT 72% | -1.15 (-1.02 / -0.16) | 70.8 → 73.5 | 33 → 16 | 571 → 377 |
| Baba Miller | 36 | 22 | Cincinnati Sr, +9.7 (+2.5/+7.1), usg 22, TS 58, 3P 30% on 2.1/40, FT 63% | -1.20 (-1.26 / +0.09) | 69.0 → 73.5 | 45 → 17 | 654 → 378 |
| Kingston Flemings | 8 | 19 | Houston Fr, +10.3 (+5.9/+4.5), usg 26, TS 56, 3P 36% on 3.6/40, FT 80% | -1.27 (-0.86 / -0.41) | 77.0 → 73.4 | 3 → 18 | 149 → 383 |
| Trevon Brazile | 35 | 23 | Arkansas Sr, +9.3 (+4.7/+4.6), usg 17, TS 62, 3P 35% on 4.7/40, FT 67% | -1.26 (-1.19 / -0.06) | 69.0 → 73.4 | 44 → 19 | 653 → 384 |
| Yaxel Lendeborg | 11 | 24 | Michigan Sr, +15.5 (+9.2/+6.3), usg 20, TS 65, 3P 36% on 6.0/40, FT 78% | -1.29 (-1.09 / -0.18) | 71.5 → 73.4 | 28 → 20 | 518 → 385 |
| Keaton Wagler | 5 | 19 | Illinois Fr, +11.2 (+8.8/+2.3), usg 26, TS 60, 3P 38% on 7.0/40, FT 78% | -1.30 (-0.74 / -0.62) | 76.7 → 73.3 | 6 → 21 | 167 → 389 |
| Henri Veesaar | 52 | 22 | North Carolina Jr, +9.7 (+5.4/+4.2), usg 23, TS 66, 3P 36% on 3.9/40, FT 66% | -1.35 (-1.19 / -0.14) | 71.5 → 73.2 | 26 → 22 | 516 → 395 |
| AJ Dybantsa | 1 | 19 | BYU Fr, +6.2 (+5.9/+0.3), usg 34, TS 60, 3P 33% on 4.9/40, FT 76% | -1.55 (-0.83 / -0.74) | 72.9 → 73.2 | 19 → 23 | 408 → 398 |
| Bruce Thornton | 31 | 23 | Ohio St. Sr, +10.9 (+8.7/+2.2), usg 23, TS 66, 3P 37% on 5.0/40, FT 82% | -1.43 (-0.93 / -0.49) | 71.3 → 73.1 | 30 → 24 | 537 → 402 |
| Brayden Burries | 10 | 21 | Arizona Fr, +10.2 (+6.0/+4.2), usg 22, TS 62, 3P 37% on 6.2/40, FT 78% | -1.42 (-0.96 / -0.45) | 75.8 → 73.1 | 9 → 25 | 223 → 405 |
| Chris Cenac Jr. | 27 | 19 | Houston Fr, +6.3 (+2.1/+4.2), usg 20, TS 55, 3P 33% on 3.9/40, FT 66% | -1.46 (-1.28 / -0.17) | 71.0 → 73.0 | 32 → 26 | 558 → 411 |
| Bryce Hopkins | 49 | 24 | St. John's Sr, +6.6 (+3.7/+2.9), usg 22, TS 56, 3P 33% on 3.4/40, FT 72% | -1.46 (-1.15 / -0.29) | 67.4 → 73.0 | 53 → 27 | 684 → 412 |
| Tobi Lawal | 48 | 23 | Virginia Tech Sr, +2.4 (+0.6/+1.8), usg 20, TS 64, 3P 33% on 2.9/40, FT 68% | -1.45 (-1.23 / -0.23) | 67.7 → 72.9 | 50 → 28 | 675 → 416 |
| Braden Smith | 38 | 23 | Purdue Sr, +8.5 (+6.6/+1.9), usg 26, TS 55, 3P 38% on 5.3/40, FT 82% | -1.53 (-0.96 / -0.57) | 72.4 → 72.9 | 21 → 29 | 443 → 417 |
| Bennett Stirtz | 16 | 23 | Iowa Sr, +7.4 (+6.6/+0.7), usg 26, TS 61, 3P 36% on 7.4/40, FT 80% | -1.55 (-0.94 / -0.59) | 75.1 → 72.9 | 10 → 30 | 272 → 418 |
| Labaron Philon | 22 | 20 | Alabama So, +8.5 (+8.4/+0.1), usg 30, TS 63, 3P 36% on 8.0/40, FT 77% | -1.53 (-0.80 / -0.77) | 76.9 → 72.9 | 4 → 31 | 158 → 419 |
| Koa Peat | 30 | 19 | Arizona Fr, +8.0 (+4.1/+3.9), usg 24, TS 56, 3P 34% on 0.8/40, FT 64% | -1.50 (-1.15 / -0.34) | 70.2 → 72.9 | 38 → 32 | 602 → 420 |
| Felix Okpara | 46 | 22 | Tennessee Sr, +7.4 (+1.7/+5.6), usg 14, TS 62, 3P 32% on 0.5/40, FT 66% | -1.45 (-1.40 / -0.03) | 69.1 → 72.9 | 43 → 33 | 650 → 421 |
| Ebuka Okorie | 17 | 19 | Stanford Fr, +6.9 (+6.8/+0.1), usg 30, TS 59, 3P 35% on 6.5/40, FT 80% | -1.51 (-0.74 / -0.82) | 75.9 → 72.8 | 7 → 34 | 216 → 424 |
| Nick Martinelli | 55 | 22 | Northwestern Sr, +5.9 (+5.7/+0.2), usg 29, TS 60, 3P 35% on 3.7/40, FT 76% | -1.55 (-1.00 / -0.54) | 67.6 → 72.8 | 51 → 35 | 678 → 425 |
| Nate Ament | 13 | 19 | Tennessee Fr, +6.1 (+2.8/+3.4), usg 28, TS 53, 3P 33% on 5.3/40, FT 77% | -1.59 (-1.16 / -0.39) | 71.5 → 72.8 | 29 → 36 | 519 → 426 |
| Otega Oweh | 41 | 23 | Kentucky Sr, +4.8 (+2.9/+1.9), usg 27, TS 55, 3P 34% on 4.6/40, FT 72% | -1.56 (-1.06 / -0.48) | 73.4 → 72.8 | 17 → 37 | 385 → 427 |
| Alex Karaban | 29 | 23 | Connecticut Sr, +8.8 (+5.3/+3.5), usg 18, TS 59, 3P 37% on 6.0/40, FT 82% | -1.57 (-1.19 / -0.35) | 68.5 → 72.8 | 46 → 38 | 662 → 428 |
| Ja'Kobi Gillespie | 42 | 22 | Tennessee Sr, +8.6 (+6.2/+2.4), usg 26, TS 54, 3P 36% on 9.5/40, FT 80% | -1.54 (-0.94 / -0.60) | 72.1 → 72.8 | 23 → 39 | 469 → 429 |
| Jaden Bradley | 50 | 23 | Arizona Sr, +7.6 (+4.2/+3.4), usg 21, TS 57, 3P 36% on 2.2/40, FT 78% | -1.58 (-1.13 / -0.41) | 73.0 → 72.8 | 18 → 40 | 404 → 430 |
| Cameron Carr | 24 | 21 | Baylor So, +6.0 (+4.1/+1.9), usg 24, TS 62, 3P 36% on 7.4/40, FT 78% | -1.60 (-1.09 / -0.50) | 75.9 → 72.7 | 8 → 41 | 217 → 441 |
| Jaron Pierre Jr. | 58 | 24 | SMU Sr, +2.5 (+2.7/-0.2), usg 23, TS 57, 3P 34% on 7.7/40, FT 77% | -1.60 (-1.10 / -0.51) | 70.2 → 72.7 | 37 → 42 | 601 → 442 |
| Emanuel Sharp | 45 | 22 | Houston Sr, +8.7 (+6.4/+2.2), usg 23, TS 58, 3P 37% on 9.6/40, FT 85% | -1.65 (-1.00 / -0.64) | 71.6 → 72.7 | 25 → 43 | 510 → 443 |
| Tyler Bilodeau | 43 | 22 | UCLA Sr, +5.7 (+5.3/+0.4), usg 24, TS 66, 3P 39% on 5.9/40, FT 79% | -1.65 (-1.11 / -0.52) | 68.2 → 72.6 | 48 → 44 | 668 → 449 |
| Christian Anderson | 18 | 20 | Texas Tech So, +8.2 (+7.2/+0.9), usg 25, TS 63, 3P 39% on 8.2/40, FT 78% | -1.62 (-0.86 / -0.78) | 74.3 → 72.6 | 12 → 45 | 320 → 450 |
| Tyler Nickel | 47 | 23 | Vanderbilt Sr, +6.3 (+5.3/+1.0), usg 17, TS 62, 3P 39% on 10.0/40, FT 80% | -1.67 (-1.14 / -0.52) | 67.6 → 72.6 | 52 → 46 | 679 → 452 |
| Meleek Thomas | 34 | 20 | Arkansas Fr, +5.9 (+5.2/+0.7), usg 22, TS 56, 3P 39% on 7.0/40, FT 79% | -1.69 (-1.00 / -0.70) | 74.1 → 72.5 | 14 → 47 | 349 → 457 |
| Mikel Brown Jr. | 6 | 20 | Louisville Fr, +5.0 (+4.1/+0.9), usg 31, TS 58, 3P 34% on 10.4/40, FT 80% | -1.72 (-0.94 / -0.79) | 77.1 → 72.4 | 2 → 48 | 145 → 460 |
| Ryan Conwell | 37 | 22 | Louisville Sr, +5.2 (+4.2/+1.0), usg 28, TS 57, 3P 37% on 12.4/40, FT 82% | -1.78 (-1.04 / -0.74) | 74.3 → 72.3 | 13 → 49 | 322 → 473 |
| Isaiah Evans | 33 | 20 | Duke So, +6.5 (+4.2/+2.3), usg 22, TS 59, 3P 37% on 10.4/40, FT 81% | -1.77 (-1.13 / -0.62) | 69.4 → 72.3 | 41 → 50 | 637 → 474 |
| Darius Acuff Jr. | 7 | 19 | Arkansas Fr, +6.7 (+7.9/-1.2), usg 30, TS 60, 3P 41% on 6.5/40, FT 79% | -1.74 (-0.75 / -1.03) | 76.9 → 72.2 | 5 → 51 | 159 → 482 |
| Karim Lopez | 21 | 19 | no college season (kept the earlier method) | — | 70.5 → 70.3 | 36 → 52 | 587 → 609 |
| Jayden Quaintance | 20 | 19 | no college season (kept the earlier method) | — | 69.9 → 69.8 | 39 → 53 | 615 → 630 |

**Sanity check against the draft and the college numbers.** Teams took Dybantsa, Peterson, Boozer, Wilson,
Wagler, Brown, Acuff and Flemings with the first eight picks. The strongest college box plus-minus seasons in the
class were Boozer (16.0), Lendeborg (15.5), Mara (14.6), Ejiofor (14.3), Graves (14.2), Onyenso and Maliq Brown
(13.9). The new day-one order sits between the two: it follows college production, discounted for age and
adjusted for what carries over (defense more than offense). I did not find a published analyst ranking of
day-one readiness to compare with; the analyst claims already in the game are applied on top. The big moves, in
plain words:
- **Peterson (1st -> 4th of rookies, 69th -> 326th in the league), Brown, Acuff, Philon, Okorie, Flemings, Wagler
  down.** Before, high-usage freshman guards got generous guard skill defaults and a very high involvement, so the
  game valued them like good NBA starters. History says 19-year-old high-usage guards are below-average NBA players
  in year one (their college defense is weak and their offense does not carry over efficiently). Their upside is
  untouched: that is potential, not day-one ability.
- **Graves, Onyenso, Maliq Brown, Nelson, Mitchell, Ejiofor up.** Huge college box plus-minus, mostly from
  defense (blocks, steals, rebounds), and defense is the part of college play that carries over best.
- **Boozer is now the best rookie** (2nd in the country in box plus-minus at 19, the strongest profile in the fit).
- **Dybantsa stays mid-pack** (BYU usage 34%, box plus-minus 6.2, weak defensive numbers).
- **Lendeborg 28th -> 20th.** See the age section.
- **The flat class is the honest expectation, not a bug.** A projection is the average outcome; real rookies
  scatter widely around it (the best 2025 rookie was +0.95, the worst -4.8). If the game should show more spread
  for rookies (for example "how good if he plays a full season", which pulls non-players less toward the floor), that
  is a choice for the user; the fit supports it with `--k 250` (wider spread, same order).


## 4. Last season's rookies (2025 class) as a test

The same method run for the 2025 class as of their draft (fit on drafts 2009-2024 only, so 2025 is unseen),
compared with how those rookies actually played in 2025-26 (first-season LEBRON):

| Rating method (as of draft day) | Correlation with real first season, 500+ minutes (32 rookies) | All 44 with a season |
|---|---:|---:|
| Old method (draft-model traits, flat rookie penalty) | 0.40 | 0.27 |
| College method (this task) | **0.47** | **0.36** |
| Draft slot alone | 0.31 | 0.26 |

The college method rates last season's rookies somewhat better than the old one and than draft slot. Rank order
(Spearman) is mixed: 0.38 vs 0.45 for the old method among the 32 who played, because the college method
compresses the class and puts second-rounders level with lottery picks. Misses worth knowing: Harper (+0.95 real,
projected -1.33) and Knueppel (+0.63, -1.50) were much better; Tre Johnson, Will Riley and Drake Powell (-4.0 to
-4.8) much worse. Caveat: the 2025 rookies keep their real 2025-26 involvement in this test (it is measured, not
estimated), so the test only judges skills and level.

  all with a LEBRON: correlation with real rookie impact  slot-based (old) 0.27  college method 0.355  projection itself 0.348  draft slot 0.261
    Spearman: old 0.312  new 0.265
| Rookie | Pick | Real rookie impact (min) | Projection | Game impact as of draft: old → college method | Overall old → college | Game today (with his NBA season) |
|---|---:|---:|---:|---:|---:|---:|
| Cooper Flagg | 1 | -0.15 (2344) | -0.80 | +1.64 → +0.92 | 76.4 → 74.3 | +2.29 (78.4) |
| Dylan Harper | 2 | +0.95 (1558) | -1.33 | +1.26 → +0.51 | 75.3 → 73.0 | +2.87 (80.1) |
| VJ Edgecombe | 3 | +0.00 (2623) | -1.21 | +0.46 → +0.61 | 72.9 → 73.3 | +2.22 (78.1) |
| Kon Knueppel | 4 | +0.63 (2551) | -1.50 | +0.66 → +0.41 | 73.5 → 72.7 | +2.52 (79.1) |
| Ace Bailey | 5 | -2.45 (1988) | -1.73 | +0.76 → +0.24 | 73.8 → 72.2 | +0.40 (72.7) |
| Tre Johnson | 6 | -4.40 (1443) | -1.97 | +0.32 → +0.10 | 72.5 → 71.8 | -0.06 (71.3) |
| Jeremiah Fears | 7 | -1.47 (2112) | -1.72 | +0.12 → +0.28 | 71.9 → 72.3 | +0.40 (72.7) |
| Egor Dëmin | 8 | -0.89 (1308) | -1.65 | +0.32 → +0.31 | 72.4 → 72.4 | +1.15 (74.9) |
| Collin Murray-Boyles | 9 | +0.62 (1246) | -0.93 | +0.27 → +0.82 | 72.3 → 74.0 | +2.16 (78.0) |
| Khaman Maluach | 10 | -0.59 (411) | -1.06 | +0.21 → +0.80 | 72.1 → 73.9 | +0.26 (72.3) |
| Cedric Coward | 11 | -1.17 (1598) | -1.38 | +0.94 → +0.47 | 74.3 → 72.9 | +2.49 (79.0) |
| Derik Queen | 13 | -0.51 (2023) | -1.41 | -0.06 → +0.50 | 71.3 → 73.0 | +0.90 (74.2) |
| Carter Bryant | 14 | -1.24 (818) | -1.29 | -0.70 → +0.55 | 69.4 → 73.1 | -0.03 (71.4) |
| Walter Clayton Jr. | 18 | -2.68 (1410) | -1.70 | -0.39 → +0.29 | 70.3 → 72.4 | -0.26 (70.7) |
| Kasparas Jakučionis | 20 | -0.76 (945) | -1.79 | -0.17 → +0.22 | 71.0 → 72.2 | +0.94 (74.3) |
| Will Riley | 21 | -4.03 (1633) | -1.80 | -0.55 → +0.19 | 69.9 → 72.1 | -0.58 (69.8) |
| Drake Powell | 22 | -4.80 (1320) | -1.57 | -0.82 → +0.36 | 69.0 → 72.6 | -0.71 (69.4) |
| Asa Newell | 23 | -1.20 (500) | -1.29 | -0.57 → +0.54 | 69.8 → 73.1 | +0.13 (71.9) |
| Nique Clifford | 24 | -1.11 (1882) | -1.39 | -1.10 → +0.51 | 68.2 → 73.0 | -0.43 (70.2) |
| Jase Richardson | 25 | -2.16 (587) | -1.48 | -0.58 → +0.42 | 69.8 → 72.8 | +0.21 (72.1) |
| Danny Wolf | 27 | -0.76 (1187) | -1.44 | -0.46 → +0.45 | 70.1 → 72.9 | +0.49 (73.0) |
| Liam McNeeley | 29 | -0.40 (368) | -2.02 | -1.54 → +0.05 | 66.9 → 71.6 | -0.55 (69.9) |
| Yanic Konan Niederhäuser | 30 | -0.35 (424) | -1.24 | -1.30 → +0.59 | 67.6 → 73.3 | +0.09 (71.8) |
| Rasheer Fleming | 31 | -1.28 (673) | -1.25 | -1.49 → +0.59 | 67.0 → 73.3 | -0.34 (70.5) |
| Sion James | 33 | -0.28 (1843) | -1.49 | -1.50 → +0.43 | 67.0 → 72.8 | -0.16 (71.0) |
| Ryan Kalkbrenner | 34 | -0.50 (1479) | -1.29 | +0.67 → +0.61 | 73.5 → 73.3 | +2.41 (78.7) |
| Johni Broome | 35 | -1.16 (55) | -1.11 | -0.71 → +0.68 | 69.4 → 73.5 | +0.45 (72.9) |
| Adou Thiero | 36 | -1.30 (149) | -1.22 | -1.94 → +0.61 | 65.7 → 73.3 | -0.45 (70.2) |
| Chaz Lanier | 37 | -2.34 (262) | -1.80 | -1.46 → +0.21 | 67.1 → 72.1 | -0.71 (69.4) |
| Kam Jones | 38 | -3.60 (616) | -1.38 | -0.85 → +0.51 | 68.9 → 73.0 | -0.88 (68.8) |
| Alijah Martin | 39 | -1.06 (146) | -1.61 | -1.04 → +0.34 | 68.4 → 72.5 | +0.24 (72.2) |
| Micah Peavy | 40 | -1.33 (913) | -1.28 | -1.36 → +0.57 | 67.4 → 73.2 | -0.32 (70.6) |
| Koby Brea | 41 | -0.73 (84) | -1.68 | -1.44 → +0.29 | 67.2 → 72.4 | +0.27 (72.3) |
| Maxime Raynaud | 42 | -2.33 (1964) | -1.44 | -0.20 → +0.46 | 70.9 → 72.9 | -0.69 (69.4) |
| Jamir Watkins | 43 | -1.39 (1032) | -1.44 | -0.73 → +0.46 | 69.3 → 72.9 | +0.90 (74.2) |
| Brooks Barnhizer | 44 | -2.62 (348) | -1.27 | -2.23 → +0.57 | 64.8 → 73.2 | -1.18 (68.0) |
| Amari Williams | 46 | -1.66 (146) | -1.25 | -1.93 → +0.59 | 65.7 → 73.3 | -1.22 (67.9) |
| Javon Small | 48 | -0.41 (830) | -1.52 | +0.47 → +0.42 | 72.9 → 72.8 | +2.63 (79.4) |
| Tyrese Proctor | 49 | -0.66 (545) | -1.72 | -0.13 → +0.27 | 71.1 → 72.3 | +1.14 (74.9) |
| Kobe Sanders | 50 | -1.80 (1351) | -1.32 | -0.92 → +0.55 | 68.7 → 73.1 | -0.07 (71.3) |
| John Tonje | 53 | -1.03 (42) | -1.68 | -1.52 → +0.31 | 66.9 → 72.4 | -0.14 (71.1) |
| Will Richard | 56 | -0.73 (1377) | -1.58 | -0.80 → +0.37 | 69.1 → 72.6 | +0.71 (73.6) |
| Max Shulga | 57 | -0.83 (36) | -1.39 | -2.25 → +0.51 | 64.7 → 73.0 | -0.90 (68.8) |
| Jahmai Mashack | 59 | -3.69 (673) | -1.36 | -1.61 → +0.51 | 66.7 → 73.0 | -1.51 (67.0) |


## 5. Gates

- **Veterans' inputs: unchanged.** Full rebuild with the repo's builder, compared with the committed file: only the
  50 rookies with a college season differ (their 64 skills and involvement); all 641 others byte-identical; the
  tendency scale map identical. Veterans' displayed ratings can shift by up to 0.05 impact points because the game
  ranks everyone against the whole league, rookies included.
- **Real-stat scorecard** (replay of 2025-26 with real minutes, 1,230 games): **18/18** league measures in range.
  (Rookies do not play in that replay, as expected.)
- **Betting test** (20 runs a game, 1,231 games, 1,018 with market odds), against the last committed numbers from
  the RATINGS-FT-TOV report: seed 1001 Brier .2040 -> .2043, log loss .5980 -> .5985, spread miss 4.16 -> 4.16,
  total miss 5.61 -> 5.60; seed 2001 Brier .1972 -> .1971, log loss .5813 -> .5811, spread 4.00 -> 4.01, total
  5.62 -> 5.70. Unchanged within run-to-run noise (the replay uses real rosters, where rookies play little).
- **Tests:** 7 new (`tests/test_rookie_fit.py`); focused modules (rookie fit, builder, input estimator, imported rookie
  ratings, real prospects, prospect realism / development / rating parity, ratings model) 161 OK, 2 skipped; core
  suite 338 OK, 2 skipped. The full suite was not run.
- **Not run on Azure:** the worker pool was blocked by the permission system (it would copy the Basketball Index
  data off the laptop), so everything ran locally at low priority, one heavy job at a time.
- **Not regenerated:** the E2 report tables (`docs/agents/tasks/e2-input-estimator.md`), built with `--no-report` to
  stay inside this task's files. Running the builder without that flag refreshes them.

**Notes for the coordinator**
- Your starting numbers (Lendeborg 9th of rookies, 145th) did not match what I measured on the committed inputs
  with the card's overall (28th of rookies, 518th; Peterson 1st / 69th). I used the card overall from
  `player_profile.engine_header` throughout; the before/after table is internally consistent.
- The level step reads the game's player-value model from the builder (`ratings_model` private caches, read only;
  no edits to `ratings_model.py`). If the value model is refitted later, rebuild the inputs so the rookies' level
  follows it.
- Open choice for the user: the class is now flat (69.8-75.1) because it shows the expected first season. A wider
  "if he plays" spread is available (`rookie_fit.py --k 250`) if wanted.


## 6. Files and how to refresh

- `scripts/research/rookie_fit.py`: the fit and the 2026 projections -> `data/research/rookie_translation_2026.json`
  (fit, checks, age tables, each 2026 rookie's college line, skill-evidence profile and projection).
  `--backtest-2025` fits on 2009-2024 only and projects the 2025 class (scratch file in `output/rookie-fit/`).
  `--no-interactions` is the sensitivity run without the age x production terms.
- `scripts/research/rookie_fit_check.py`: `snapshot` (display overall / impact / ranks of every rostered player),
  `table` (2026 class before vs after), `backtest` (2025 class as of its draft, old vs college method).
- `src/nba_gm_data/input_estimator.py`: `load_rookie_college`, `estimate_player_inputs(..., college=...)`, the
  projection as family context (`_projection_context`), `apply_rookie_involvement`.
- `scripts/build_player_inputs.py`: uses the college path for 2026 rookies with a college season.
- `tests/test_rookie_fit.py`.

Sources: Barttorvik player and team tables (barttorvik.com, local raw CSVs); Basketball Index LEBRON by season
(fanspo.com BBI role explorer, cached under `data/research/bbi/captures/fanspo_tools/lebron/`); Basketball Reference
advanced tables and draft pages (`data/research/development_evidence.json`).

## Resume state
- Done: everything above. Board row set to review. Committed on the worktree branch, not pushed.
