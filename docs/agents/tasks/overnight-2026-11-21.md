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
