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
_(Filled in as work lands.)_

### Landed in main (tests, browser tests and the real-stat scorecard passed before each push)
- **Star injuries:** 2025-26 history completed. The top 30's median games fell from 70/67.5 to 63.5/59.5 (real 64.5-65.5). Injuries per team rose from 35 to 40 (real 35-43). 1,081 tests.
- **Free agency slice 3, offer sheets:** Match or Pass, AI sheets with reasons. Qualifying offers taken fell from 7/4 to 3/0 a summer (real 0-2). 1,379 tests.
- **Codex research:** roster-edge evidence (feeds slice 4). Codex README refresh pending.

### Branches for review (not merged)
- `overnight/ui-polish`: 13 fixes. Dialogs and messages no longer open behind windows; the playoff bracket fits at 1024 px; a clearer start screen; Full Standings in the house style; the server no longer drops page files under load. It merges cleanly with main. Screenshots are in `output/ui-polish/`.

- `overnight/headshots`: 2,000 generated faces; every made-up staff member's name matches the face's gender; no repeats within a league. 22 of 30 real head coaches have real (freely licensed) photos, and 528 of 535 real college prospects have ESPN headshots. Merges cleanly. Style samples are in `output/headshots/options.html`; before/after screenshots are in `output/headshots/`. Decisions: face style (Open Peeps built in, Avataaars or Personas available), and whether to use NBA.com or ESPN photos for the 8 coaches without a free one.

### Infrastructure
- **Azure worker:** working end to end (core tests passed there in about 8.5 minutes). The upload is fixed: it skipped caches and builds, and avoided a link loop in the settlement data.
