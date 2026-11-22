# ROOKIE-FIT-2: 2026 rookies' day-one ratings, redone

**TL;DR**
- **A rookie's starting level now means "how good he is when he plays," not "how much he will play."** It comes from
  rookies who actually played (2009-2025 drafts) with a correction for who gets minutes, plus the scouts' board rank,
  readiness write-ups and, lightly, this season's real games. The class spreads out again (overall 69.8-78.1, was 69.8-75.1).
- **Boozer is the most ready rookie; Lendeborg is now 5th (was 20th), Peterson 8th, Wagler 11th, Burries 20th,
  Dybantsa 24th, Acuff 29th.** History, both impact measures and their first month agree that high-usage freshman
  guards and wings with weak college defense start below average. Their upside (potential) is untouched.
- **A simulated season looks like a real rookie class** (points per game, two 15-a-game rookies, how many barely
  play); the new ratings mainly change who those rookies are. Two gaps remain, reported and not fixed: the best
  simulated rookies score less per minute than real ones, and simulated rookies barely improve from the first half of
  the season to the second (real ones add about 2 points per 36).

_Status: **review**. Claude Opus agent, worktree branch `worktree-agent-a1a01f15e16d6caf4`, 2026-11-22._


## 1. What was wrong and what changed

The first attempt fitted "how good was his first season" with players who barely played pulled toward a bench level.
That mixed ability with playing time (a rookie stuck behind veterans counted as a bad player) and squeezed the whole
class into about five overall points. Now:

1. **The target is ability: impact per 100 possessions when he plays.** First-season Basketball Index LEBRON (offense
   and defense separately; the same scale the game's player value is fitted to), as measured, for the 518 drafted
   college players with 300+ rookie minutes. A short season counts for less (weight = minutes / (minutes + 500)): it
   is noisier, not worse. Box plus-minus was fitted the same way as a second opinion.
2. **Who gets minutes is corrected, not baked in.** Players who play are not a random draw: a second-rounder who gets
   minutes is usually a good one. A second model estimates each player's chance of playing from the same evidence,
   and the impact fit carries a separate term for that selection (the standard two-step correction). The day-one
   ability leaves that term out: it is what he would show if he played, whoever his team is.
3. **Evidence used:** final college season (Barttorvik: box plus-minus split into offense and defense, usage, shooting,
   rebound, assist, steal, block, turnover and free-throw rates, three-point volume and accuracy, height, team strength,
   minutes share), age and age x production, and the scouts' view (draft slot averaged with the public consensus board
   rank; see section 3). Ridge regression, strength chosen by leaving one draft out.
4. **Kept from the first attempt:** college numbers set each rookie's skill shape (the same college-to-skill mapping),
   the rookie step runs last in the builder, analyst claims are applied last, veterans' inputs are byte-identical, and
   physical tools and potential are not touched.

### How well it predicts (drafts the fit never saw: fit 2009-2019, scored on 2020-2025)

Correlation with real first-season impact, rookies who played (1 = perfect, 0 = nothing):

| What predicts it | All who played (186) | 1,000+ minutes (101) | Every draft left out in turn (518) |
|---|---:|---:|---:|
| Draft slot alone, total impact | 0.12 | 0.19 | 0.16 |
| College numbers, total impact | 0.55 | 0.65 | 0.48 |
| College numbers + slot, total impact (used) | **0.56** | **0.67** | **0.49** |
| ... offense only | 0.29 | 0.35 | 0.38 |
| ... defense only | 0.74 | 0.77 | 0.66 |
| Draft slot alone, box plus-minus | 0.22 | 0.22 | 0.21 |
| College + slot, box plus-minus | 0.51 | 0.60 | 0.46 |

- **Draft slot carries a little signal** (more for box plus-minus, as you said), but almost nothing once college
  numbers are known (0.55 -> 0.56). On the 2015-2025 first rounds, a public big-board rank added nothing beyond the
  slot either (the two carry the same information).
- **Defense carries over from college far better than offense.**
- **The correction for who plays matters most for late picks.** Average day-one ability by pick band (impact per 100,
  0 = average NBA player): picks 1-3 -0.86, 4-10 -1.47, 11-20 -1.80, 21-30 -1.87, 31-45 -1.98, 46-60 -2.07. Among late
  second-rounders who did play, the real average was -1.28: they are the good ones, and the correction stops the game
  from treating every late pick as one of them.
- **Calibration:** grouping rookies into tenths by prediction, each tenth's real average is within about 0.2 of the
  prediction for both offense and defense (the top tenth: predicted -0.19, real +0.03).


## 2. Readiness versus upside: the 2026 class

Overall = the card number. "First try" is the committed version (ROOKIE-FIT); "old" is before that.
Day-one ability is impact per 100 possessions (offense / defense); 0 = average NBA player.

| Rookie | Pick | Age | College fit (off / def) | Readiness notes | This season so far (min, pts per 36, box +/-, what it moved) | Day-one ability | Overall: old → first try → new | Rookie rank | League rank |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| Cameron Boozer | 3 | 19 | +0.37 / +0.07 | ready now | 494 min, 19.3, +2.2 (moved +0.20) | +0.85 (+0.55 / +0.30) | 74.1 → 75.1 → 78.1 | 15 → 1 → 1 | 350 → 263 → 114 |
| Allen Graves | 19 | 20 | -0.15 / +0.45 | some readiness | 257 min, 12.5, +0.4 (moved -0.04) | +0.26 (-0.09 / +0.35) | 71.2 → 74.7 → 76.9 | 31 → 2 → 2 | 543 → 289 → 153 |
| Zuby Ejiofor | 23 | 22 | -1.18 / +0.76 | ready now | 116 min, 14.3, -0.1 (moved +0.02) | -0.20 (-0.99 / +0.79) | 70.7 → 73.9 → 75.6 | 34 → 7 → 3 | 577 → 347 → 223 |
| Caleb Wilson | 4 | 20 | -0.43 / +0.37 | some readiness | 308 min, 22.1, -1.8 (moved -0.26) | -0.32 (-0.41 / +0.09) | 72.7 → 74.2 → 75.5 | 20 → 3 → 4 | 424 → 321 → 237 |
| Yaxel Lendeborg | 11 | 24 | -0.98 / +0.25 | ready now | 506 min, 22.4, +0.6 (moved +0.14) | -0.39 (-0.48 / +0.10) | 71.5 → 73.4 → 75.4 | 28 → 20 → 5 | 518 → 385 → 243 |
| Aday Mara | 12 | 21 | -1.90 / +1.34 | some readiness | 358 min, 16.1, +0.9 (moved +0.27) | -0.29 (-1.58 / +1.30) | 74.5 → 73.9 → 75.3 | 11 → 8 → 6 | 313 → 348 → 251 |
| Izaiyah Nelson | 51 | 23 | -1.21 / +0.83 | unknown | — | -0.38 (-1.21 / +0.83) | 69.4 → 74.0 → 75.2 | 42 → 6 → 7 | 638 → 342 → 263 |
| Darryn Peterson | 2 | 19 | -0.17 / -1.32 | ready now | 521 min, 19.6, +0.4 (moved +0.37) | -0.92 (-0.04 / -0.88) | 79.9 → 74.2 → 75.2 | 1 → 4 → 8 | 69 → 326 → 264 |
| Ugonna Onyenso | 53 | 22 | -2.10 / +1.61 | some readiness | — | -0.49 (-2.10 / +1.61) | 71.7 → 74.0 → 74.8 | 24 → 5 → 9 | 503 → 341 → 291 |
| Hannes Steinbach | 14 | 20 | -1.14 / +0.12 | ready now | 63 min (too few to count) | -0.82 (-0.99 / +0.17) | 71.5 → 73.5 → 74.3 | 27 → 14 → 10 | 517 → 375 → 316 |
| Keaton Wagler | 5 | 19 | -0.18 / -0.85 | ready now | 332 min, 19.2, -1.7 (moved -0.13) | -0.96 (-0.10 / -0.86) | 76.7 → 73.3 → 74.3 | 6 → 21 → 11 | 167 → 389 → 317 |
| Maliq Brown | 44 | 22 | -1.88 / +1.14 | unknown | 1 min (too few to count) | -0.74 (-1.88 / +1.14) | 68.0 → 73.8 → 74.3 | 49 → 9 → 12 | 670 → 355 → 318 |
| Tarris Reed Jr. | 26 | 23 | -1.70 / +0.93 | some readiness | 60 min (too few to count) | -0.77 (-1.70 / +0.93) | 72.4 → 73.6 → 74.2 | 22 → 12 → 13 | 446 → 371 → 331 |
| Joshua Jefferson | 28 | 22 | -1.43 / +0.51 | some readiness | 4 min (too few to count) | -0.92 (-1.43 / +0.51) | 70.6 → 73.5 → 74.1 | 35 → 13 → 14 | 584 → 374 → 342 |
| Dailyn Swain | 15 | 21 | -0.95 / -0.04 | some readiness | 27 min (too few to count) | -0.98 (-0.95 / -0.04) | 69.8 → 73.5 → 74.0 | 40 → 15 → 15 | 619 → 376 → 350 |
| Baba Miller | 36 | 22 | -2.00 / +1.04 | unknown | 107 min, 15.8, -0.8 (moved +0.07) | -0.89 (-1.97 / +1.08) | 69.0 → 73.5 → 73.9 | 45 → 17 → 16 | 654 → 378 → 356 |
| Sergio de Larrea | 25 | 20 | no college season | — | — | earlier method | 73.6 → 73.7 → 73.7 | 16 → 10 → 17 | 376 → 361 → 369 |
| Morez Johnson Jr. | 9 | 20 | -1.14 / +0.20 | ready now | 256 min, 13.2, -5.4 (moved -0.41) | -1.15 (-1.24 / +0.09) | 70.8 → 73.5 → 73.6 | 33 → 16 → 18 | 571 → 377 → 375 |
| Trevon Brazile | 35 | 23 | -1.66 / +0.55 | unknown | 257 min, 12.5, -2.0 (moved -0.06) | -1.17 (-1.54 / +0.37) | 69.0 → 73.4 → 73.4 | 44 → 19 → 19 | 653 → 384 → 384 |
| Brayden Burries | 10 | 21 | -0.89 / -0.59 | ready now | 387 min, 17.9, -1.2 (moved -0.04) | -1.32 (-0.54 / -0.78) | 75.8 → 73.1 → 73.4 | 9 → 25 → 20 | 223 → 405 → 385 |
| Bennett Stirtz | 16 | 23 | -0.90 / -1.06 | ready now | 295 min, 15.1, +1.3 (moved +0.46) | -1.30 (-0.62 / -0.68) | 75.1 → 72.9 → 73.4 | 10 → 30 → 21 | 272 → 418 → 386 |
| Dillon Mitchell | 40 | 23 | -1.71 / +0.67 | project | 2 min (too few to count) | -1.24 (-1.86 / +0.62) | 68.2 → 73.6 → 73.2 | 47 → 11 → 22 | 667 → 369 → 395 |
| Kingston Flemings | 8 | 19 | -0.69 / -0.63 | some readiness | 258 min, 13.0, -3.9 (moved -0.18) | -1.50 (-0.90 / -0.60) | 77.0 → 73.4 → 72.9 | 3 → 18 → 23 | 149 → 383 → 410 |
| AJ Dybantsa | 1 | 19 | -0.25 / -1.08 | some readiness | 443 min, 17.5, -4.1 (moved -0.38) | -1.71 (-0.57 / -1.14) | 72.9 → 73.2 → 72.9 | 19 → 23 → 24 | 408 → 398 → 411 |
| Ebuka Okorie | 17 | 19 | -0.32 / -1.32 | some readiness | 20 min (too few to count) | -1.64 (-0.32 / -1.32) | 75.9 → 72.8 → 72.8 | 7 → 34 → 25 | 216 → 424 → 415 |
| Henri Veesaar | 52 | 22 | -1.72 / +0.21 | some readiness | — | -1.50 (-1.72 / +0.21) | 71.5 → 73.2 → 72.7 | 26 → 22 → 26 | 516 → 395 → 427 |
| Bruce Thornton | 31 | 23 | -0.89 / -0.77 | some readiness | 41 min (too few to count) | -1.66 (-0.89 / -0.77) | 71.3 → 73.1 → 72.6 | 30 → 24 → 27 | 537 → 402 → 432 |
| Labaron Philon | 22 | 20 | -0.47 / -1.25 | some readiness | 75 min (too few to count) | -1.71 (-0.47 / -1.25) | 76.9 → 72.9 → 72.6 | 4 → 31 → 28 | 158 → 419 → 433 |
| Darius Acuff Jr. | 7 | 19 | -0.31 / -1.75 | ready now | 590 min, 24.8, -2.3 (moved -0.16) | -2.02 (-0.04 / -1.98) | 76.9 → 72.2 → 72.1 | 5 → 51 → 29 | 159 → 482 → 471 |
| Meleek Thomas | 34 | 20 | -1.14 / -1.17 | some readiness | 331 min, 19.4, -0.4 (moved +0.33) | -1.98 (-0.96 / -1.01) | 74.1 → 72.5 → 71.9 | 14 → 47 → 30 | 349 → 457 → 483 |
| Braden Smith | 38 | 23 | -1.24 / -0.89 | some readiness | 135 min, 11.5, -0.8 (moved +0.21) | -1.92 (-1.30 / -0.61) | 72.4 → 72.9 → 71.9 | 21 → 29 → 31 | 443 → 417 → 487 |
| Tobi Lawal | 48 | 23 | -2.16 / +0.34 | unknown | 36 min (too few to count) | -1.82 (-2.16 / +0.34) | 67.7 → 72.9 → 71.8 | 50 → 28 → 32 | 675 → 416 → 500 |
| Ja'Kobi Gillespie | 42 | 22 | -1.01 / -1.01 | unknown | 4 min (too few to count) | -2.02 (-1.01 / -1.01) | 72.1 → 72.8 → 71.8 | 23 → 39 → 33 | 469 → 429 → 502 |
| Christian Anderson | 18 | 20 | -0.79 / -1.31 | ready now | 194 min, 13.4, -5.3 (moved -0.19) | -2.09 (-0.85 / -1.24) | 74.3 → 72.6 → 71.7 | 12 → 45 → 34 | 320 → 450 → 506 |
| Cameron Carr | 24 | 21 | -1.43 / -0.60 | some readiness | 37 min (too few to count) | -2.03 (-1.43 / -0.60) | 75.9 → 72.7 → 71.7 | 8 → 41 → 35 | 217 → 441 → 509 |
| Alex Karaban | 29 | 23 | -1.70 / -0.27 | unknown | 82 min (too few to count) | -1.97 (-1.70 / -0.27) | 68.5 → 72.8 → 71.7 | 46 → 38 → 36 | 662 → 428 → 512 |
| Felix Okpara | 46 | 22 | -2.53 / +0.69 | unknown | 5 min (too few to count) | -1.84 (-2.53 / +0.69) | 69.1 → 72.9 → 71.7 | 43 → 33 → 37 | 650 → 421 → 513 |
| Koa Peat | 30 | 19 | -1.67 / -0.39 | some readiness | 42 min (too few to count) | -2.06 (-1.67 / -0.39) | 70.2 → 72.9 → 71.5 | 38 → 32 → 38 | 602 → 420 → 527 |
| Nick Martinelli | 55 | 22 | -1.26 / -0.91 | unknown | 26 min (too few to count) | -2.17 (-1.26 / -0.91) | 67.6 → 72.8 → 71.4 | 51 → 35 → 39 | 678 → 425 → 536 |
| Jaden Bradley | 50 | 23 | -1.76 / -0.36 | unknown | 42 min (too few to count) | -2.12 (-1.76 / -0.36) | 73.0 → 72.8 → 71.4 | 18 → 40 → 40 | 404 → 430 → 538 |
| Chris Cenac Jr. | 27 | 19 | -1.88 / -0.04 | project | 58 min (too few to count) | -2.12 (-2.03 / -0.09) | 71.0 → 73.0 → 71.3 | 32 → 26 → 41 | 558 → 411 → 544 |
| Bryce Hopkins | 49 | 24 | -1.74 / -0.04 | project | 103 min, 13.3, -6.1 (moved -0.17) | -2.15 (-1.90 / -0.25) | 67.4 → 73.0 → 71.3 | 53 → 27 → 42 | 684 → 412 → 545 |
| Mikel Brown Jr. | 6 | 20 | -0.82 / -1.21 | some readiness | 252 min, 18.9, -6.1 (moved -0.42) | -2.45 (-0.92 / -1.53) | 77.1 → 72.4 → 71.0 | 2 → 48 → 43 | 145 → 460 → 562 |
| Tyler Bilodeau | 43 | 22 | -1.61 / -0.69 | unknown | — | -2.31 (-1.61 / -0.69) | 68.2 → 72.6 → 71.0 | 48 → 44 → 44 | 668 → 449 → 563 |
| Nate Ament | 13 | 19 | -1.57 / -0.32 | project | 277 min, 14.9, -5.3 (moved -0.29) | -2.38 (-1.74 / -0.64) | 71.5 → 72.8 → 70.9 | 29 → 36 → 45 | 519 → 426 → 573 |
| Tyler Nickel | 47 | 23 | -1.53 / -0.84 | unknown | — | -2.37 (-1.53 / -0.84) | 67.6 → 72.6 → 70.9 | 52 → 46 → 46 | 679 → 452 → 574 |
| Otega Oweh | 41 | 23 | -1.53 / -0.65 | project | — | -2.38 (-1.68 / -0.70) | 73.4 → 72.8 → 70.9 | 17 → 37 → 47 | 385 → 427 → 575 |
| Emanuel Sharp | 45 | 22 | -1.10 / -1.09 | some readiness | 268 min, 10.2, -6.3 (moved -0.21) | -2.40 (-1.54 / -0.86) | 71.6 → 72.7 → 70.9 | 25 → 43 → 48 | 510 → 443 → 576 |
| Isaiah Evans | 33 | 20 | -1.47 / -0.96 | some readiness | 23 min (too few to count) | -2.43 (-1.47 / -0.96) | 69.4 → 72.3 → 70.8 | 41 → 50 → 49 | 637 → 474 → 584 |
| Ryan Conwell | 37 | 22 | -1.27 / -1.24 | unknown | 226 min, 15.0, -3.2 (moved +0.01) | -2.50 (-1.27 / -1.23) | 74.3 → 72.3 → 70.7 | 13 → 49 → 50 | 322 → 473 → 590 |
| Jaron Pierre Jr. | 58 | 24 | -1.68 / -0.86 | unknown | 99 min (too few to count) | -2.54 (-1.68 / -0.86) | 70.2 → 72.7 → 70.5 | 37 → 42 → 51 | 601 → 442 → 601 |
| Karim Lopez | 21 | 19 | no college season | — | — | earlier method | 70.5 → 70.3 → 70.4 | 36 → 52 → 52 | 587 → 609 → 604 |
| Jayden Quaintance | 20 | 19 | no college season | — | — | earlier method | 69.9 → 69.8 → 69.8 | 39 → 53 → 53 | 615 → 630 → 632 |

Class overall range 69.8-78.1, spread (standard deviation) 1.81. First try 69.8-75.1 (0.85). Old method 67.4-79.9 (2.99).

**The seven you named:**
- **Cameron Boozer (3): most ready, 1st of rookies (114th in the league).** The strongest college season in the class
  at 19, two-way, and his first month (+2.2 box plus-minus on a winning Memphis team) agrees. Potential 87.9 unchanged,
  so his growth room is smaller than Dybantsa's or Peterson's, which matches "ready now, debatable ceiling."
- **Yaxel Lendeborg (11): ready now, 5th of rookies (was 20th).** At 24 his college line (box plus-minus 15.5) is
  discounted a little for age, but the readiness write-ups (both preseason lists called him the most NBA-ready) and his
  first month (19.7 a game, 57% true shooting, +0.6 box plus-minus) lift him. Potential 76.9 (little upside), unchanged.
  See section 5: the simulated Warriors still play him only ~18 minutes.
- **Darryn Peterson (2): 8th of rookies.** College fit says a good scorer but a weak defender; readiness notes say
  ready; his first month (+0.4 box plus-minus on a bad Utah team) moved him up +0.37, one of the largest moves.
  Potential 87.5, unchanged: a top-two future, not a top-two rookie today.
- **Keaton Wagler (5): 11th.** Ready offensive player (near-average offense on day one), poor defense.
- **Brayden Burries (10): 20th.** Readiness write-ups called him ready; his college numbers and first month are
  middling (17.9 points per 36, -1.2 box plus-minus on a 1-16 Milwaukee). Potential 79.3: neither high ceiling nor
  very ready.
- **AJ Dybantsa (1): 24th.** BYU usage 34% with weak defensive numbers; first month 16.5 a game but 50% true shooting
  and -4.1 box plus-minus (moved him -0.38). The fit says a high-usage freshman wing like this starts about where Cade
  Cunningham, Jalen Green or Brandon Miller started (all -1.4 to -3.3 in year one). Potential 87.5 unchanged: the
  pick was for the future.
- **Darius Acuff Jr. (7): 29th.** Near-average offense on day one (third in the class, behind Boozer and level with Peterson) but
  the weakest defensive projection in the first round. His 25.4 a game is volume on a 2-14 Sacramento (33% usage,
  51% true shooting, -2.3 box plus-minus); that context explains the gap between his scoring and his rating.

Both measures agree on these: ranking the class by the box plus-minus fit instead puts Dybantsa 14th, Peterson 17th
and Acuff 27th. Bigs with big college defensive numbers (Graves, Ejiofor, Mara, Nelson, Onyenso, Maliq Brown) rate
high because college defense is the part that carries over best, and the game values defense on the same impact scale.


## 3. Scouting, analyst and draft-ranking evidence

`data/research/rookie_scouting_2026.json` (built by `scripts/research/rookie_scouting.py`), gathered 2026-11-22 from
public pages only, polite pacing, with source, author, date and link for every entry:
- **Seven final pre-draft big boards:** Rookie Scale consensus (locked June 23), ESPN (Jeremy Woo, top 100), The
  Ringer (J. Kyle Mann), ClutchPoints (Brett Siegel), NBC Sports (Raphielle Johnson), On SI (Derek Parker, top 40),
  The Athletic (Sam Vecenie, top 10 via a Bleacher Report summary; the full board is paywalled). Skipped: Tankathon
  (now shows 2027), CBS (blocked), Bleacher Report, NBADraft.net, No Ceilings, Basketball Index (not reached).
- **Readiness lists:** ESPN's post-summer-league rookie ranking (Zach Kram, July 17) and SI's preseason Rookie of the
  Year ranking (Blake Silverman, Oct 3); both call Lendeborg the most NBA-ready.
- **Readiness tier for each rookie** (ready now / some readiness / project / unknown) with a one-line paraphrase and
  links: 11 ready now, 22 some, 6 projects, 14 unknown (mostly second-rounders with no write-up).
- **NBA.com Kia Rookie Ladders** Oct 28 - Nov 18 (Nov 18: Lendeborg, Boozer, Acuff, Peterson, Dybantsa, Wilson, Mara,
  Wagler, Meleek Thomas, Burries). Used as a check only: ladders rank counting stats in role.
- Spot-checked against the live ESPN board and the Nov 18 ladder; the tiers are paraphrases made for this file.

**How they enter:** (a) the scouts' rank is the average (on a log scale) of the draft slot and the consensus board
rank, used where the fit uses draft slot; (b) a readiness nudge of +0.20 for "ready now" (0.15 offense, 0.05 defense)
and -0.20 for "project", well inside the fit's own error (about 1.1). No history exists to fit the nudge, so it is
deliberately small. Each rookie's skills carry a labelled evidence note listing the parts.


## 4. This season's real games (small sample, light weight)

Basketball Reference rookie, advanced and team pages fetched 2026-11-22 (one page every 6 seconds; paths allowed
by their robots file). Box plus-minus already adjusts for team strength. A rookie's offensive and defensive box
plus-minus is put on the impact scale by a line fitted on rookies 2015-16 to 2025-26 (247 with 1,000+ minutes), and
blended in with weight minutes / (minutes + 1,500), so 500 minutes count for a quarter and 100 minutes for 6%.
Under 100 minutes counts for nothing. His usage so far also nudges his involvement (a tendency, not a skill) with
weight minutes / (minutes + 1,000).

| Rookie | Team (record, net rating) | Minutes (games) | Points per 36 | True shooting | Usage | Box +/- | Ability moved (off / def) | Weight |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Darius Acuff Jr. | SAC (2-14, -12.4) | 590 (16) | 24.8 | 0.513 | 33% | -2.3 | -0.16 (+0.11 / -0.27) | 28% |
| Darryn Peterson | UTA (3-14, -7.4) | 521 (17) | 19.6 | 0.520 | 25% | +0.4 | +0.37 (-0.02 / +0.39) | 26% |
| Yaxel Lendeborg | GSW (8-8, -0.9) | 506 (16) | 22.4 | 0.574 | 27% | +0.6 | +0.14 (+0.34 / -0.20) | 25% |
| Cameron Boozer | MEM (12-5, +9.1) | 494 (16) | 19.3 | 0.551 | 24% | +2.2 | +0.20 (+0.03 / +0.17) | 25% |
| AJ Dybantsa | WAS (6-11, -6.6) | 443 (13) | 17.5 | 0.498 | 24% | -4.1 | -0.38 (-0.32 / -0.06) | 23% |
| Brayden Burries | MIL (1-16, -12.4) | 387 (17) | 17.9 | 0.559 | 21% | -1.2 | -0.04 (+0.20 / -0.24) | 20% |
| Aday Mara | OKC (10-6, +4.6) | 358 (16) | 16.1 | 0.653 | 18% | +0.9 | +0.27 (+0.31 / -0.04) | 19% |
| Keaton Wagler | LAC (4-11, -6.5) | 332 (15) | 19.2 | 0.557 | 24% | -1.7 | -0.13 (-0.07 / -0.07) | 18% |
| Meleek Thomas | CLE (9-8, +2.4) | 331 (14) | 19.4 | 0.584 | 22% | -0.4 | +0.33 (+0.18 / +0.15) | 18% |
| Caleb Wilson | CHI (4-11, -7.8) | 308 (10) | 22.1 | 0.525 | 27% | -1.8 | -0.26 (+0.02 / -0.28) | 17% |
| Bennett Stirtz | OKC (10-6, +4.6) | 295 (16) | 15.1 | 0.651 | 15% | +1.3 | +0.46 (+0.12 / +0.33) | 16% |
| Nate Ament | MIL (1-16, -12.4) | 277 (15) | 14.9 | 0.572 | 17% | -5.3 | -0.29 (-0.02 / -0.27) | 16% |
| Emanuel Sharp | SAC (2-14, -12.4) | 268 (16) | 10.2 | 0.480 | 14% | -6.3 | -0.21 (-0.44 / +0.23) | 15% |
| Kingston Flemings | ATL (10-6, +2.7) | 258 (12) | 13.0 | 0.590 | 16% | -3.9 | -0.18 (-0.21 / +0.03) | 15% |
| Trevon Brazile | DEN (9-5, +1.5) | 257 (14) | 12.5 | 0.639 | 14% | -2.0 | -0.06 (+0.12 / -0.18) | 15% |
| Allen Graves | TOR (6-10, +0.2) | 257 (16) | 12.5 | 0.564 | 14% | +0.4 | -0.04 (+0.06 / -0.10) | 15% |
| Morez Johnson Jr. | DAL (9-7, -0.2) | 256 (15) | 13.2 | 0.476 | 19% | -5.4 | -0.41 (-0.25 / -0.16) | 15% |
| Mikel Brown Jr. | BRK (3-12, -8.0) | 252 (11) | 18.9 | 0.500 | 26% | -6.1 | -0.42 (-0.10 / -0.32) | 14% |
| Ryan Conwell | MIA (9-6, +0.6) | 226 (13) | 15.0 | 0.555 | 17% | -3.2 | +0.01 (+0.00 / +0.01) | 13% |
| Christian Anderson | CHO (4-11, -11.0) | 194 (14) | 13.4 | 0.473 | 22% | -5.3 | -0.19 (-0.22 / +0.02) | 12% |
| Braden Smith | IND (5-11, -3.6) | 135 (10) | 11.5 | 0.541 | 16% | -0.8 | +0.21 (-0.06 / +0.27) | 8% |
| Zuby Ejiofor | ATL (10-6, +2.7) | 116 (10) | 14.3 | 0.648 | 14% | -0.1 | +0.02 (+0.04 / -0.03) | 7% |
| Baba Miller | LAC (4-11, -6.5) | 107 (13) | 15.8 | 0.673 | 18% | -0.8 | +0.07 (+0.03 / +0.04) | 7% |
| Bryce Hopkins | DEN (9-5, +1.5) | 103 (8) | 13.3 | 0.659 | 14% | -6.1 | -0.17 (-0.01 / -0.17) | 6% |

**Far from their real start, and why:**
- **Acuff** (rated 29th; 25.4 a game): volume on the league's worst team. His efficiency and box plus-minus support
  a below-average day-one level; team context explains the points.
- **Dybantsa** (24th; 16.5 a game): same story, less extreme; his first month lowered him.
- **Lendeborg** (5th; 19.7 a game on a .500 Warriors team): the rating agrees he is ready, but in simulation Golden
  State has ten players rated above him and gives him ~18 minutes, not 31.6. The rating is not the cause; it is the
  depth chart (and possibly real injuries the simulation does not have). Flag for the user.
- **Meleek Thomas** (33rd; 23.6 minutes, 12.7 a game, near-average box plus-minus on a winning Cleveland): better start
  than his rating; moved up +0.33.
- **Bennett Stirtz** (21st; +1.3 box plus-minus on a good Oklahoma City): moved up +0.46, the largest move.


## 5. Simulated rookie season against real rookie classes

Two full simulated 2026-27 regular seasons (seeds 17 and 18, new saves, AI front offices on, the user's team set to
New York so its minutes plan does not touch a lottery rookie), against every drafted rookie class 2015-16 to 2025-26
from Basketball Reference (646 picks; a pick who never played counts as zero). The game's class has 53 rookies (the
other picks are unsigned or stashed), which slightly lowers its share of "barely played".

| Rookie class | Simulated (2 seasons) | Real (11 classes) |
|---|---:|---:|
| Minutes: middle / top tenth | 855 / 1,699 | 502 / 1,841 |
| Minutes per game if he played: middle / top tenth | 13.0 / 27.1 | 15.0 / 27.7 |
| Points per game: middle / top quarter / top tenth | 5.1 / 8.3 / 12.1 | 4.2 / 7.9 / 12.1 |
| Rookies averaging 15+ a game, per class | 2 and 2 | 2.5 on average (0-4) |
| Share averaging 10+ a game | 15% | 14% |
| Share playing 1,500+ minutes | 15% | 18% |
| Share barely playing (under 300 minutes) | 29% | 41% |
| Points per 36 (500+ minutes): bottom tenth / middle / top tenth | 12.9 / 16.0 / 18.8 | 9.6 / 13.7 / 19.0 |
| Rebounds per 36: middle / top tenth | 5.9 / 7.8 | 5.5 / 9.7 |
| Assists per 36: middle / top tenth | 3.5 / 5.0 | 2.5 / 5.7 |
| True shooting: middle | .569 | .535 |

**Against the first try** (same seed 17, committed inputs): its simulated class also looked roughly real in total
(one 15-a-game rookie, 19% at 10+, 21% at 1,500+ minutes, weakest regulars 13.5 per 36). So the class-wide numbers
are set mostly by the engine and the coaches; the new ratings change WHO plays and produces (minutes a game, first
try -> new: Graves 17.0 -> 22.5, Lendeborg 14.8 -> 18.8, Ejiofor 8.4 -> 11.4, Peterson 26.5 -> 27.5; Koa Peat 22.1
-> 18.0, Christian Anderson 21.5 -> 17.0, Thornton 18.3 -> 16.7; Dybantsa, Acuff, Boozer, Mara about the same) and
bring the top end closer to real (two 15-a-game rookies instead of one; 10+ share 15% instead of 19%).

Simulated season leaders (seed 17): Wagler 17.4 a game (33 minutes), Peterson 15.4, Wilson 14.8, Boozer 13.7, Acuff
13.4, Brown 10.3, Mara 10.7, Dybantsa 12.1 in 44 games.

**What looks real:** how many rookies matter (two 15-a-game rookies a class, 15% at 10+), the spread of points per
game, and that the top picks play big minutes (Boozer, Wilson, Peterson, Wagler, Acuff 25-33 minutes).

**What does not (engine and usage, not ratings; reported, not fixed):**
- The simulated rookie class is too even per minute: the weakest regulars score 13 per 36 (real 10) and shoot .569
  (real .535), while the best score less than their real counterparts (Wilson 15 per 36 vs 22 real, Boozer 16 vs 19,
  Lendeborg 14 vs 22). Their involvement already matches their real usage; the engine spreads shots more evenly
  across a roster than real teams do.
- Against this season's real start (same date, mean of both seeds): minutes are close for Peterson, Boozer, Wilson,
  Mara, Flemings, Brown and Ejiofor; Wagler plays 33 in simulation vs 22 real (bench in Los Angeles); Lendeborg,
  Meleek Thomas, Stirtz, Ament and Conwell play far less in simulation than real (deep simulated rotations).

### In-season growth

- **Real** (last season's rookies, real box scores, 25 with 300+ minutes in each half, split Jan 31): points per 36
  +2.4 from the first half to the second (median), assists +0.7, rebounds flat, minutes per game +0.2 (median).
- **Simulated** (same split, both seeds): points per 36 -0.1 and +0.1, assists +0.3 and +0.1, rebounds -0.2 and
  +0.4, minutes per game +0.9 and +2.0. Card overall rises steadily, about +0.12 a month (class average 72.8 in
  October to 73.4-73.6 in April; median rookie +0.4 to +0.5).
- **Reading:** the game does grow rookies through the season, but too little for it to show in their scoring. Real
  rookies' second-half jump is partly a bigger role and partly skill; the game's monthly growth for a 19-22-year-old
  is about a quarter of what Basketball Index shows (see `dev-growth-vs-bbi.md`). That is development tuning, outside
  this task.


## 6. Last season's class as a test (fit without 2025, rated as of draft day)

| Method | Correlation with real first season, 500+ minutes (32) | Rank agreement (same 32) | All 44 with a season |
|---|---:|---:|---:|
| Old method (draft-model traits) | 0.40 | 0.45 | 0.27 |
| First try (ROOKIE-FIT) | 0.47 | 0.38 | 0.36 |
| **New (ability)** | **0.54** | **0.53** | **0.40** |
| Draft slot alone | 0.31 | — | 0.26 |

The new method rates last season's rookies better than both earlier ones on every count. Misses that remain:
Harper (+0.95 real, projected -0.99) and Knueppel (+0.63, -1.49) were much better; Tre Johnson (-4.4) and Ace Bailey
(-2.5) worse. The 2025 class spread on the card: 69.6-76.4 (old method 2.8 spread, new 1.4; real rookies vary more
than any forecast can).


## 7. Gates

- **Veterans' inputs byte-identical:** a full rebuild differs from the committed file only for the 50 rookies with a
  college season (their 64 skills and involvement). Lopez, de Larrea and Quaintance (no college season) keep the
  earlier method.
- **Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- **Betting test** (20 runs a game, 1,231 games, 1,018 with market odds), against the same runs on the last commit:

  | | Seed 1001 last commit | this branch | Seed 2001 last commit | this branch |
  |---|---:|---:|---:|---:|
  | Brier (market .1962) | .2043 | .2043 | .1971 | .1972 |
  | Log loss (market .5740) | .5985 | .5985 | .5811 | .5813 |
  | Spread miss vs market (points) | 4.164 | 4.164 | 4.008 | 3.998 |
  | Total miss vs market (points) | 5.603 | 5.626 | 5.699 | 5.758 |

  Picking winners and spreads unchanged; totals 0.02-0.06 points further from the market. Rookies do not play in this
  replay of 2025-26; the small change comes from the game rescaling everyone's ratings against a league that now
  includes the re-rated rookies.
- **Tests:** focused set (`run_tests_parallel.py --workers 2 --match "rookie|input|estimator|prospect|draft|rating"`,
  163 modules, 1,887 tests): all pass except (a) 11 errors from reference files that exist only in the main checkout's
  `output/` (copied in and rerun: all pass) and 2 from the Windows packaging test needing a local startup video (not
  related), and (b) one failure, `test_foundation ... test_repeated_same_day_ai_roster_cut_upserts_one_transaction`
  ("claimed" instead of "cleared" on waivers), which fails the same way on the committed inputs, so it predates this
  change. Core suite (`run_core_tests.sh`): 338 OK, 2 skipped. `tests/test_rookie_fit.py`: 11 OK (5 new).


## 8. Decisions and notes for the user

- **Rank order versus draft order.** The evidence (two impact measures, 17 drafts, held-out checks, the 2025 test and
  this season's first month) puts Dybantsa 24th and Acuff 29th of rookies on day one. If you want the card to track
  draft order more, that would be a taste choice, not something the evidence supports; their growth room is where the
  game should show their status.
- **Lendeborg's minutes in simulation** come from Golden State's depth chart, not his rating (5th of rookies).
- **Potential is on the old scale** (e.g. Lendeborg 76.9 against a card overall of 75.4; many second-rounders have a
  potential below their card overall). Unchanged here as asked, but the two numbers are not comparable; worth a look
  with the development work.
- **Out of scope, observed:** (1) AI drafting (`draft.gm_rows`) uses scouts' current and potential grades from the
  prospect generator, not this fit; future classes' day-one spread should be checked against this one (class spread of
  about 0.8 impact points, late picks around -2). (2) In-season and multi-season growth is weaker than real (section 5).
  (3) The simulation's rookie scoring is too even across a roster (section 5).


## 9. Files and how to refresh

- `scripts/research/rookie_fit2.py`: the ability fit and the 2026 blend -> `data/research/rookie_translation_2026.json`
  (method `rookie_translation_v2`: fit, checks, each rookie's parts). `--quick` skips the checks; `--backtest-2025`.
- `scripts/research/rookie_scouting.py` -> `data/research/rookie_scouting_2026.json`.
- `scripts/research/rookie_real_lines.py` -> `data/research/rookie_real_lines.json` (pages saved under
  `output/rookie-fit-2/bbref/`; a past season's rookies page shows CAREER totals, so season numbers come from the
  totals pages).
- `scripts/research/rookie_season_probe.py` (one simulated season, rookies recorded every step) and
  `rookie_season_compare.py` (against real classes, this season's start and growth).
- `scripts/research/rookie_fit_check.py table3` (the class table), `backtest`; `rookie_inputs_diff.py`.
- `src/nba_gm_data/input_estimator.py` (v2 label, evidence parts, involvement from this season's usage),
  `scripts/build_player_inputs.py` (level note lists the parts), `tests/test_rookie_fit.py`.
- Refresh after new games: fetch the 2027 pages again, run `rookie_real_lines.py`, `rookie_fit2.py`, then the builder.

## Resume state
- All steps done; see gates. Board row set to review. Committed on the worktree branch, not pushed.
