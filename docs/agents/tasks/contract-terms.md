# CONTRACT-TERMS: contract history, salary paths and options, option decisions

_Claude (Opus agent), worktree branch `worktree-agent-a467c2ea2e59eaa25`. Status: **in progress** (measurement)._

## TL;DR
- **The Podziemski bug is fixed at the source.** The salary tables the league is built from list only the years a
  contract still has left, so 497 real contracts looked like fresh one- or two-year deals and the extension rules
  refused them. Each real contract's signing season and length is now rebuilt from evidence (the draft, reported
  signings, last season's salary table); where nothing says when a deal was signed, the length is stored as unknown
  and the screen says so. League-wide, players who can extend on day one went from **4 to 116**.
- **Extensions follow the league's rules:** rookie-scale deals in the summer before year four (until the day before
  opening night); other deals of three or more seasons from the second anniversary (third for five- and six-year
  deals), five seasons at most including the current one, first year at most 140% of his salary or the average
  salary. The Set The Roster list and the extension screen now use one rule, so a listed player is never refused.
- **Offers have a shape:** free-agent offers, re-signings and extensions pick a salary path (rising, flat, declining)
  and an option on the last season (none, player, team). Salaries are saved year by year; players value earlier money
  and player options, and the "Will he sign?" box says how the shape changes his answer. AI deals use the real shares.
- **Option decisions are visible:** an Option Decisions card in the offseason checklist (the player's own choice with
  his reason; your team options with Keep / Decline), phone messages, and notable decisions on the league wire.

(Results of the two-season probe and the scorecards: see "Measurements"; filled in when the runs finish.)

## Resume state
- Committed on the branch: part 1 (eb15bb6), parts 2-3 (d34ec3b), browser tests + probe (f82edf6), AI extension
  guards (03ecaec).
- Running on the Azure worker (one at a time): `contract-terms-branch` (two-season probe of this branch,
  output/ct-probe-branch), `contract-terms-base` (same probe on main 5c5f19a from output/contract-terms/basetree,
  output/ct-probe-base), `contract-terms-scorecards` (real-stat 1,230-game replay and odds 20 runs x seeds 1001/2001,
  output/ct-scorecards). Logs in output/contract-terms/azure_*.log.
- GUI server for screenshots: port 8771 from this worktree (save dir output/contract-terms/gui_saves).
- Left: parallel focused tests (waiting for swap), metrics into this report, FA builder and option-card screenshots
  from the probe's copies, board row to review.
