# OVERNIGHT-EXTENSIONS: an honest contract-extension page, plus free-agency polish

**TL;DR**
- The contract-extension page no longer shows made-up "interest" bars. It shows the salary he will actually sign for, his market ask, the longest deal he will take, a live "Will he sign?" answer with the real reason, and a season-by-season cap table with the luxury tax.
- The Assistant GM phone now tucks into the corner while it would cover an open window. The signing wire no longer shows moves dated in the future. "Fits our room" now also needs an open roster spot.
- Checked in the running app: I built an extension for Michael Porter Jr., watched the cap table update and signed him. The page also opens much faster (about 1.5 s instead of about 10 s).

Branch: `overnight/honest-extensions` (not merged). Status: review.

## Resume state
- Done: all three items, tests, screenshots, this report, board row. Commits on the worktree branch, then the branch is pushed as `overnight/honest-extensions`.
- Scratch material (git-ignored) is in `output/honest-extensions/`: `saves/` (Brooklyn preseason save, Charlotte re-signing save), `bkn.pristine.json` and `cha_fa.pristine.json` (copy over `saves/` to replay), screenshot drivers `shot.cjs` (extension) and `fa_shot.cjs` (free agency). Run them with `NODE_PATH=~/.hermes/hermes-agent/node_modules` against a server on port 8787.

## 1. Contract extension page
**Before:** "Player Ask", an offer box, and an "Interest Breakdown" with four bars. Two were invented in the browser ("Team direction 64" was a constant; "Player timeline" was 100 minus age x 1.4) and none of them decided anything. "Four-Year Cap Impact" was a bar chart that stopped after four seasons, so a five-year extension ran off the end. A declined offer said only "wants a stronger offer" and showed an interest score.

**What actually decides an extension** (the Submit button's rule, `submit_extension_offer_action`):
- **His price from you** starts from his market ask (the contract model's projected salary). His flexibility with your team then lowers it. Flexibility is 38 + 0.18 x team fit, plus a fixed personal swing of -15 to +15, kept between 8 and 92. He takes 1.02 - flexibility/260 of his ask. Without a guarantee he asks the same premium free agents ask (Porter: +20%).
- The **term** may not run past his projected retirement (1 to 5 years).
- The **salary** must be at least $1.8M and fit under the **hard cap in every season** the extension covers. It may go over the tax.
- He signs when the offer reaches his price.

The price math now lives in one shared helper (`extension_offer_terms`). Both the page and the Submit button use it, so they cannot drift apart. Submit makes exactly the same decisions as before (a test checks it against the old code).

**New page.** It is built from the free-agency Offer Builder pieces and still sits inside the player card:
- **What He Wants:** market ask (x preferred years), "Signs with you from" (guaranteed, and without a guarantee, with the share of his ask), and the longest deal with the season it starts.
- **Your Offer:** a salary box and slider, from $1.8M up to the hard-cap limit for the chosen term. Quick buttons: His price from you / Market ask / Minimum. Years 1-5 as radio buttons; terms past his retirement are disabled and say why. Guaranteed / Non-guaranteed. "Options: none" (the game's extensions have none, and the salary is flat).
- **Will He Sign?** sits next to the button, so it is always in view. It shows a verdict with the reason, for example "He signs an extension with you from $19.3M a season. You are $1.8M short." It also covers "He plans to retire after 3 seasons…", "Blocked by the hard cap…", and "Extensions are closed until the next window" or "Only players whose original contract ran three or more seasons can extend". There is a meter showing your offer as a share of his price.
- **Cap Position With This Extension:** one row per season, from this season to the end of his longest possible deal. Columns: payroll, his current deal, the extension, payroll after, tax room, hard-cap room, and **Tax / payout**. Tax / payout is the luxury-tax bill the game charges if payroll ends over the line (repeat taxpayers pay their higher rates). Otherwise it is your share of the tax payout, using today's league payrolls. When the offer pushes you over, the tooltip says what payout share you give up. Seasons where contracts are not all set yet carry an asterisk.
- **Analysis tabs** (kept, all engine numbers): Ability projection, Comparable contracts, Succession. The old "If he leaves" box became a fourth tab.
- Footer: offer summary and **Sign for $X × N** (or "Make Offer" when he would decline). A declined offer now says what he needed (`needed_millions`, additive).
- Keyboard: Tab order runs salary box → slider → quick buttons → years → guarantee → Sign. Arrow keys move inside the radio groups and skip disabled terms. Enter in the salary box submits.

**Payload** (`extension_room`, all fields additive): `market_ask_millions`, `flexibility`, `ask_share`, `security_premium_pct`, `accept_line_millions`, `accept_offer_millions`, `cap_table` (per season: payroll, his salary, tax line, hard cap, rooms, `tax_rule` with the bracket and rates the game charges, `payout_share_if_under_millions`), `eligibility_reason`. Room-level `offer_rules`. Existing actions and permissions are unchanged.

**Speed:** the page used to build every free agent's likely suitors, which extensions never use. It now builds only the extension projections (`with_extension_context`, which the contract module provides for this purpose). The payload is byte-for-byte identical in a check. Opening one player: about 10 s → 1.5 s. Whole roster: 15.7 s → 6.5 s.

## 2. Polish
- **Assistant GM phone.** While its normal footprint overlaps any open window, it tucks: smaller, partly past the right edge, and lowered so only the top peeks up (sender, message count, close button). Hovering it or tabbing into it brings it back to full size. Everything else works as before: texts, dismiss, Escape, and draft-night and simulation alerts. At 1440 x 900 and 1024 x 768 it no longer covers the Offer Builder, the Signing Wire or the extension page.
- **Future-dated wire moves: real, and found the cause.** In a real flow I took a draft-night save through the draft into re-signing (27 June 2027). The game applies the AI teams' offseason moves right then, but dates them 1 July (re-signings, retirements) and 3 July (signings). The wire listed "07/03" moves on 27 June, and the old display also dropped the year. **Display fix:** a move the game has already applied never shows a date after today. It shows today, and the tooltip says "Already done; recorded for 2027-07-03". Moves from another year now show the year (07/03/26). The engine dates are unchanged (that code belongs to another task; see section 5).
- **"Fits our room" counts roster spots.** He must sign a guaranteed offer you can afford *and* you need an open spot under the 15-man season roster (rosters are cut to 15 before opening night). The Roster chip now reads "13 / 15" and turns red when full. The filter's tooltip explains the rule. The free-agency payload gained `as_of_date` and `offer_rules.season_roster_maximum` (additive).

## 3. Screenshots
All in `output/honest-extensions/screenshots/` (git-ignored, in this worktree):
- `ext_1440_00_board_phone.png`: Brooklyn preseason board; the phone tucked.
- `ext_1440_01_open.png`: extension page for Michael Porter Jr. Market ask $21.6M; signs with you from $19.3M (89% of his ask), $23.1M without a guarantee; 5 years; starts 2027-28.
- `ext_1440_02_short.png`: $17.5M typed, 2 years chosen with the arrow key; "He turns this down … You are $1.8M short"; meter at 91%.
- `ext_1440_03_ready.png`: "His price from you" → $19.3M × 2; "He signs"; cap table 2027-28 payroll $119.3M → $138.6M, tax room +$68.8M, payout share $1.0M.
- `ext_1440_04_signed.png`: after Sign: "Extension signed: Michael Porter Jr. signed a 2-year extension: $19.3M a season, $38.6M total". The save shows 2027-28 and 2028-29 at $19.3M with the news item "BKN extends Michael Porter Jr. to $19.3M x 2."
- `ext_1024_00` to `ext_1024_03`: the same at 1024 x 768.
- `fa_1440_room.png`, `fa_1024_room.png`: free-agency room in the re-signing window. Wire dates show 06/27 with the tooltip; Roster 13 / 15; the phone peeks without covering the builder.
- `fa_1440_fits_filter.png`, `fa_1024_fits_filter.png`: "Fits our room" switched on.

Sideways page scroll: 0 px in every run, and nothing inside the extension page scrolls sideways.

## 4. Checks
- New `tests/test_extension_builder_payload.py` (6 tests):
  - the shared price rule equals the original Submit math for many asks, roles, seeds and players;
  - the price shown is the smallest $0.1M offer Submit accepts, and one step lower is refused;
  - plain-language eligibility reasons;
  - on a real Brooklyn save: Submit at price - $0.1M is rejected (and reports the price as needed), and Submit at the price is applied with the right seasons;
  - the cap table's tax bill equals `trade_tax.luxury_tax_bill`, and its payout share equals `pool_share_if_under`;
  - the browser verdict (the real JavaScript, run in Node) matches Submit on a grid of salaries, terms and guarantees.
- New `tests/honest_extensions.test.cjs` (6): preview verdicts and limits, the cap table and tax math, no invented interest on the page, wire dates, roster-spot filter, phone tuck.
- `node --test tests/*.test.cjs`: 289 pass. The tuck timer is guarded so the phone's existing tests, which run without a timer, still pass.
- GUI guards `tests.test_gui_concept71`, `tests.test_gui_concept74`: OK.
- Extension and contract tests: `test_ai_extension_identity`, `test_block_contract_terms`, `test_free_agency_room_payload`, `test_free_agency_bids`: OK. `test_contract_import_separation` and `test_contract_protection` (28) are OK when run with `tests` on the import path. They import sibling test modules, so they fail to import with plain `-m unittest tests.x`; that is not new.
- `bash scripts/run_core_tests.sh`: 337 tests OK (2 skipped).
- Extension-window tests in `test_foundation` (`test_extension_window_starts_with_two_active_contract_seasons_remaining`, `test_dashboard_extension_controls_follow_current_date_not_stale_legal_actions`): OK (one of them skips in this environment). The big app-action test that also calls the extension room was already marked skip ("needs review").
- Not run: the two scorecards (no engine behaviour changed) and the full suite.

## 5. Found along the way (not changed)
- **Two tax lines.** The signing rules and the cap display measure "tax room" to one line ($200.4M in 2026-27, `save.cap_lines_for_season`). The luxury-tax bill and payout use another ($207.4M, `transactions.cap_lines_for_season` via `trade_tax`). The cap table shows both honestly and says so in a note, but they should be one number. (The TRADE-TAXPOOL row already lists "tax-line mismatch" as a follow-up.)
- **Offseason AI moves are dated ahead.** `save.py` records AI re-signings and retirements for 1 July and AI signings for 3 July (`strategic_free_agent_signings`, `maybe_add_major_free_agent_news`). The game applies them when the re-signing window opens on 27 June. The wire now shows them honestly, but the News feed and other event lists still carry the later dates. A one-line engine fix (use the save's date) belongs to the free-agency engine owner.
- **Extension price vs market:** the extension price comes from a deterministic per-player swing plus team fit (team fit is not set for extension candidates, so everyone gets the neutral 50). It is engine behaviour, now shown plainly. Whether extensions should follow the market the way rival bids do is a design question.
- The injury body-map figure in the player-card header hangs slightly into the panel below it (visible over "Cap Position" on the extension page). The card header is not part of this task.
- The local test server occasionally boots the page without home data on a fast reload (one run showed "Basketball | Season" in the top bar and a script-order error). It does not reproduce on retry; the earlier free-agency task saw the same.
- The startup video returns 404 from the worktree server (it is a symlink to the main checkout); unrelated.

## 6. Questions for you
1. Should the game have one tax line? Right now the signing rules use $200.4M and the tax bill uses $207.4M in 2026-27.
2. Should extension prices follow the market (team fit, winning, role) instead of the fixed per-player swing?
3. The phone's tuck is a peek (top strip only) whenever it would cover a window. Is that too hidden, or would you prefer it to move to the left corner instead?
