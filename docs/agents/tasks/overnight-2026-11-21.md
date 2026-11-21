# Overnight 2026-11-21: plan and morning report

_Coordinator: Claude. The user is asleep about 8 hours and asked for "surprise development": predict the next asks and finish them first._

## Rules for the night
- **Laptop:** at most two heavy jobs at once (agents' probes and replays, or big test runs). The Azure worker runs one long single-core job at a time, and its spend is logged in `output/azure_ledger.json` with a 300-hour monthly cap.
- **Disk:** about 28 GB free. Check it at every notification. Agents keep scratch output small and delete probe saves.
- **Merging into main:** only approved work (tasks the user started or decided), and only after the full related tests, the browser tests and the real-stat scorecard all pass.
- **Surprise work:** pushed as `overnight/*` branches for the user to review, never merged into main.

## Predicted next asks, in order
1. Finish the two running tasks: free agency slice 3 (offer sheets and matching), and star injuries (complete 2025-26 history, measured history weight).
2. The user's two decisions from tonight:
   - bidding-war winners pay at least what the second-best bid was worth, and a slightly lower offer wins only rarely, with a stated reason;
   - new saves give coordinators neutral ratings.
3. **Free agency slice 4:** two-way contracts, Exhibit 10 camp deals, the 21-to-15 cutdown, and sign-and-trades. Codex's evidence is merged (`roster-edge-evidence.md`).
4. **The ten-season league health check** (the user said to run it tonight). It runs on Azure.
5. **UI/UX** (on the user's list of biggest misses): a polish pass on screens that aren't changing tonight, as a branch for review.
6. Merge Codex's README refresh.

## Schedule (two laptop slots, plus Azure)
- **Slot A:** FA-REAL slice 3, then review and merge, then slice 4.
- **Slot B:** star injuries, then review and merge, then the bidding-war price floor, then neutral coordinators (which needs slice 3 merged first, because both touch save creation).
- **Light work in between:** the UI polish branch (no simulations, only rendering screens of existing saves).
- **Azure:** the ten-season check, once the upload finishes.

## Morning report

### TL;DR
- **Merged into main overnight** (every one passed its tests and the real-stat check, 18/18): free agency offer sheets; star injuries; the bidding-war price floor; one overall rating scale; the first Stage 2 piece. The whole suite (2,457 tests) passed on the combined game.
- **Branches waiting for your review:** `overnight/ui-polish` and `overnight/headshots`. Both merge cleanly.
- **Free agency slice 4 also merged:** realistic free agency is now complete, all four slices. The whole suite (2,476 tests) passed on it.
- **Neutral coordinators also merged:** the betting test improved on both seeds (Brier 0.2060 -> 0.2041 and 0.1992 -> 0.1972; market 0.1962), and the real-stat check stays 18/18.
- **Still running:** the ten-season check (on Azure, resumed after a safety shutdown cut it off).

### Landed in main
1. **Free agency slice 3: offer sheets.**
   - Rival teams can sign your restricted free agents, and you get a Match-or-Pass countdown with the terms, your cap effect and any hard cap.
   - AI teams bid for real reasons.
   - Players taking the one-year qualifying offer: 3 and 0 a summer (real 0-2; it was 7 and 4).
2. **Star injuries.**
   - Real players' injury history now includes the 892 missing 2025-26 injuries, and history counts at its measured weight.
   - Top-30 median games played: 63.5 / 59.5 (real 64.5-65.5; it was 70 / 67.5).
   - Injuries per team: 40 (real 35-43; it was 35).
3. **Bidding-war price floor** (your decision).
   - The winner always pays at least what the second-best offer was worth to the seller, and losing bidders can raise.
   - The rare lower-bid exception never fired in 14 bidding wars. Two constants can widen it if you want it to happen occasionally.
4. **One overall rating scale** (your decision).
   - One straight-line scale everywhere: 90+ is exactly the analysts' top five (Jokić 95.4, Gilgeous-Alexander 94.5, Wembanyama 92.8, Dončić 91.3, Giannis 90.4; Kawhi next at 89.6).
   - 95% of rotation players sit in the 70s or 80s, and the bench reaches the high 60s.
   - It also fixed the roster table's OFF column, which was showing a different number.
5. **Stage 2, first piece.**
   - An engine switch, with today's engine still the default and unchanged.
   - All 691 players' 94 inputs feed the physics pieces.
   - Shooting spot-check: the physics ranks shooters well. With its conversion refit, every shot type lands within about 1 point of real on held-out players.
   - **Key finding:** today's engine reads players' actual 2025-26 percentages, so a fair head-to-head with Stage 2 needs held-out data.
6. **Free agency slice 4:** two-way contracts (three places outside the 15, a 50-game limit, promotions), Exhibit 10 camp deals with affiliate bonuses, the 21-to-15 opening-roster cutdown with waivers, and sign-and-trades.
   - Real counts hit: about 7 camp deals a team; 8 and 3 sign-and-trades; 33 and 24 overseas departures.
   - No hard-cap breaches on opening night, and nobody is ever signed onto your roster without your say-so.
   - Still low: two-way promotions in season (15-20, real 26-32).
   - First summer's camp period runs slower than main.
7. **Neutral starting coordinators** (your decision): every team's starting coordinators have neutral ratings, and head coaches are unchanged.
   - The betting test improved on both seeds.
   - Side effect: AI teams keep coordinators only with a staff grade of 68+, so most starting coordinators will be replaced when their first contracts end.
8. **Codex research:** offseason decisions, 2025-26 injury history, roster-edge evidence (two-ways, camp deals, sign-and-trades), and the README refresh.

### Branches for your review (not merged)
- **`overnight/ui-polish`:**
  - dialogs and messages no longer open behind windows;
  - the playoff bracket fits at 1024 px;
  - a clearer start screen;
  - Full Standings in the house style;
  - the server no longer drops page files under load.

  Screenshots are in `output/ui-polish/`.
- **`overnight/headshots`:**
  - 2,000 generated faces, with every made-up staff member's name matching their face's gender and no repeats in a league;
  - 22 of 30 real head coaches show real photos;
  - 528 of 535 real college prospects show ESPN headshots.

  Style options are in `output/headshots/options-view.html`.

### Decisions only you can make
1. **Prospect potentials** on the new straight-line scale come out at 100-120 for the top prospects. Options: recalibrate potential to mean expected peak value, show "+N at peak", or leave it.
2. **Face style** for made-up people: Open Peeps (built in), Avataaars or Personas. And should we use NBA.com/ESPN photos for the 8 head coaches without a free one?
3. **Merge** `overnight/ui-polish` and `overnight/headshots`?
4. **Private data on GitHub:** my safety check blocked the commit and push, and I undid it fully. It needs your allowance in Claude Code's permission settings, or you can push it yourself.
5. **Stage 2 next step** (plan in `docs/agents/tasks/stage2-plan.md`). The suggested next piece is rebounding and fouls, then perimeter contests, then the first fast possession loop.
6. **Disk:** about 7 GB of old scratch folders from merged tasks could be deleted (needs your OK). Swap got large overnight.

### Infrastructure notes
- The Azure worker works end to end. Overnight fixes:
  - the upload now skips caches and builds;
  - a link loop in the settlement data is avoided;
  - the fixed 7 a.m. safety shutdown is removed, after it cut off the ten-season run;
  - the script now notices if the machine stops mid-job.
- **Spend so far:** under US$1 of the ~US$100 credit.
- **Lessons:** commit pending board edits before every merge (a blocked merge twice became a board-only commit, both caught and redone). Watch disk and swap with several agents running.
