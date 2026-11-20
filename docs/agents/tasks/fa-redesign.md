# Free agency redesign (one free-agency room)

_Claude Opus agent, own worktree branch, 2026-11-19. Status: **review** (committed on the branch, not pushed or merged)._

**TL;DR**
- **Free agency is now one room of three windows that open together, once per phase:** a sortable, filterable market
  table, an Offer Builder (the player, his price, your salary / years / guarantee, a live cap table, rival bids), and a
  Signing Wire of league moves. The day buttons moved to the top bar, like draft night.
- **The builder shows what the game really uses.** The old screen showed a made-up "interest" number and the market
  ask as "asking price"; neither decided anything. Now it shows the salary he actually signs for from you, the
  retirement limit, and the cap check, all computed by the same rules the Sign button runs.
- **Big finding for you:** a free agent accepts *your* offer based only on his projected minutes (minutes x $0.45M),
  not on his market ask. Brandon Miller asks $28.8M, rivals bid $30.4M, and he signs with you for $13.6M. See Questions.

## Resume state
- Done: inventory, redesign, backend fields, tests, screenshots, this report, board row (`review`). One commit on the
  worktree branch. Not pushed or merged.
- Scratch saves and the screenshot driver: `output/fa-redesign/` (git-ignored). `saves/fa_warm.pristine.json` is a
  Charlotte save on free agency day 1 (copy it over `saves/fa_warm.json` to replay); `saves/fa_resign.pristine.json`
  is the same save in the re-signing window. `shot.cjs` + `steps/offer_flow.cjs` (Playwright, run with
  `NODE_PATH=~/.hermes/hermes-agent/node_modules`; `ACCEPT_DIALOGS=1` lets it sign). `to_fa.py` moves a draft-night
  save to re-signing through the normal app actions.
- Worktree symlinks (`.venv`, Barttorvik raw, universe SQLite, injury evidence, BBI files, settlement output, startup
  movie) were removed before the commit; re-create them (see the task brief) to rerun the screenshots.

## How I reached free agency (no season was played)
The UI batch's draft-night save (Charlotte, 26 June 2027) was finished with the normal "finish draft" action, then
"advance to next event" moved it to the re-signing window (27 June), and "Open Free Agency" opened the market
(1 July, day 1 of 5, 80 free agents, 29 rival bids). In that scratch save five Charlotte players had been moved to free
agency by the UI batch, and no games were played, so "last season" stats are zero. Everything else is the engine's.

## 1. Inventory of the old free-agency screen
Seven windows were cut out of one old page: Free Agency Controls, Free-Agent Market, Selected Free Agent, Live Offers,
Signing Wire, Free Agency Payroll, Free Agency Cap Position, plus a separate negotiation pop-up.

| Window | What it showed | Problems |
|---|---|---|
| Controls | Team logo, "Day N of 5", Trade Room, My Roster, Waivers, Sim FA Day / Sim To End (or exclusive-window buttons, or Advance To Next Phase) | A whole window for a few buttons; unlike draft night, nothing in the top bar |
| Free-Agent Market | Three linked tables: 12 ratings, 8 last-season stats, then Fit / Ask / Move / Leading bid / Interest. Market / Shortlist / My Offers tabs, a hidden filter bar (name, position, minimum OVR), Compare | Very wide; the information that decides a signing was split from the player; "My Offers" was always empty in the app (the app's offers are answered on the spot, so they never become "live"); interest bar had no meaning without the day's bar |
| Selected Free Agent | Name, OVR, five rating bars, Player Card / Build Offer / Shortlist | No price, no bids, no contract facts |
| Live Offers | Rival bids for the selected player (team, salary x years, interest) | Separate from the player and the offer |
| Signing Wire | Last 5 signings | Signings only, five rows |
| Payroll | Four-year payroll share chart | Not connected to any offer |
| Cap Position | Payroll, tax room, hard-cap room | Not connected to any offer |
| Negotiation pop-up | Ask "x 4", salary, years, Guaranteed box, "Interest Breakdown", "Player Interest", four-year cap chart, six-season table | **Rule 4 problems:** the interest numbers were invented in the browser (offer / ask x 70, a made-up security penalty, "Financial room" from the max offer); the "asking price" was the market ask, which does not decide whether he accepts; the cap chart charged the offer to the season that just ended (it started from the old season, not the season the contract starts); the toast after a rejected offer read "Offer offered" |

Actions (all kept): `free_agency_room`, `submit_free_agent_offer` (with `auto_apply`, guarantee, `allow_tax_exceed` in
the re-signing window), `advance_free_agency` (day / to end), `advance_re_signing` (day / open market),
`advance_save` (next phase), `waiver_room` + claims/releases, Trade Room, My Roster, player card ("Build Offer"),
Compare (up to three), shortlist. Permissions: the windows lock when the phase does not allow signings; the market and
builder lock when free agency is over; only your own expiring players during the exclusive window.

What you wrote: "Free agency must be redone UI/UX design wise and card wise and everything, currently it's awful."
The backlog asked for one real screen using the negotiation / player-card language, dense rows and the window chrome.

## 2. What changed
**One room, three windows** (`Free-Agent Market`, `Offer Builder`, `Signing Wire`), replacing the seven windows and
the pop-up. They open side by side, centered, the first time you enter the re-signing window and again when free
agency opens (same "once on entry" rule as draft night and the playoffs; after that your arrangement and closed
windows are kept). The day buttons are in the top bar: Advance Exclusive Day / Open Free Agency, then Sim FA Day /
Sim To End, then Advance To Next Phase. The S E keyboard shortcut still works.

**Free-Agent Market.** Header: day, how many players are shown, a one-line rule reminder, and your cap position for
the season the contract starts (roster, payroll, room under the tax, room under the hard cap, largest legal offer).
Filters always visible: All / Shortlist / Has bids / My offers, name search (live), position (PG..C, dual positions
match either), maximum age, minimum OVR, "Fits our room" (he would sign a guaranteed offer you can legally make),
Reset, Compare. Table in the house style (double header rule, small bold headers, stripes, whole-row hover, sorted
column shaded, headshots bottom-aligned): shortlist star, Player, Pos, Age, OVR bar, OFF, DEF, last season
PTS/REB/AST, Ask (with the daily move), Bids (count + best team + terms), Mood, Fit for us. Every column sorts.
- **Mood** is the best rival bid's interest against the bar he needs *today* to sign it (the engine's own daily bar,
  which drops each day): "Ready to sign" when the bid already clears it, "Weighing bids" otherwise, "No bids",
  or "Your rights" in the exclusive window. The tick on the meter is the bar.
- **Fit for us** is the existing number, now explained on hover (overall plus your depth at his position; it does not
  change whether he signs).
- Keyboard: arrow keys move through rows and select, Enter jumps to the salary box, Space selects; sort headers,
  filters and stars are buttons. Selecting a row updates the builder without rebuilding the table (scroll kept).

**Offer Builder** (player-card panel language): headshot, name, position / age / height, OVR / OFF / DEF, Player Card,
Shortlist; last season line; **What He Wants**: market ask (what rivals bid against), **signs with you from**
(guaranteed and non-guaranteed), longest deal before his projected retirement. **Your Offer**: salary box + slider
(league minimum to your largest legal offer), quick buttons (His price from you / Market ask / League minimum), years
1-5 (arrow keys), Guaranteed / Non-guaranteed (with what that means: each season becomes guaranteed on January 10),
and Options: "None" (the game's free-agent contracts have no options; salary is flat). **Will He Sign?** verdict with
the reason and a meter (your salary as a share of his price). **Cap Position With This Offer**: five seasons from the
contract's first season: payroll, this offer, after, tax room, hard-cap room, updating as you type. **Rival Bids** with
interest against today's bar and who leads. **Your Offers To Him** (signed / declined, with what he needed; declined
offers are read back from the save). Footer: total and the Sign button (asks for confirmation; disabled when the cap
rule would block it).

**Signing Wire**: every recorded league move (signings with terms and total, trades, other moves), newest first,
filters All / Signings / Trades / Ours, and a line "29 live bids on 13 players, 0 ready to sign".

**Engine numbers only (rule 4).** New, additive fields in the `free_agency_room` payload:
`accept_floor_millions` / `accept_floor_offer_millions` (the threshold `manual_save_pool_signing` applies, and the
smallest $0.1M offer that meets it), `safe_years` (`extension_safe_year_limit`), `sign_bar_today`
(`free_agency_accept_threshold`), `signing_blocked_reason` (stretch-release rule), `headshot_url`, `health`; room-level
`signing_season`, `roster_count`, `offer_rules` (minimum, whether the tax may be exceeded, five-year limit, no
options, flat salary, unreviewed-waiver block), `league_moves`, `user_offer_history`. No engine behavior changed.

Removed: the invented interest numbers, the old negotiation pop-up and its cap chart (and one old test of that chart).

## 3. Screenshots
`output/fa-redesign/screenshots/` (git-ignored, in this worktree). Before: `output/fa-redesign/before/fa_before_1440.png`.
- `fa_1440_01_entry.png`: free agency day 1 at 1440 x 900; the three windows open side by side (the Assistant GM
  phone still covers the right edge here).
- `fa_1440_02_selected.png`: Brandon Miller picked with a search and a click; the builder shows his market ask
  ($28.8M), his price from you ($13.6M) and the default offer at his ask.
- `fa_1440_03_offer_ready.png`: offer set to his price, 3 years (chosen with the arrow keys), guaranteed; verdict
  "He signs", cap table updated (2027-28 payroll $140.1M -> $153.7M, tax room $53.7M).
- `fa_1440_04_signed.png`: after Sign (confirmation accepted): toast, roster 13 -> 14, payroll $153.7M, largest offer
  now $53.7M, the wire's "Ours" filter shows "Brandon Miller CHA $13.6M x 3, $40.8M total".
- `fa_1024_reduced.png`: 1024 x 768 with reduced motion: same three windows, smaller; the Signing Wire sits past the
  right edge (the board scrolls sideways, the page does not).
- `fa_resigning_1440.png`: the exclusive re-signing window (your two expiring players, "Your rights", top-bar buttons
  Advance Exclusive Day / Open Free Agency, room up to the hard cap).

## 4. Checks
- `node --test tests/*.test.cjs`: 268 pass, including 7 new in `tests/free_agency_room.test.cjs` (cap check against
  the engine rule, verdict from his price / guarantee / retirement, cap table starts at the signing season with a flat
  salary, offer draft defaults, mood and filters and sorting, one-row entry layout applied once, three windows and the
  top-bar commands, no invented interest left). One old test of the removed pop-up chart was deleted from
  `tests/ui_product_audit.test.cjs`.
- New `tests/test_free_agency_room_payload.py` (5): the price shown equals the threshold `manual_save_pool_signing`
  uses for every role and guarantee (one $0.1M step below is refused, the shown price is accepted); rounding never
  shows a price a hair under the threshold; the browser's cap verdict matches `signing_cap_check` on 112 cases (runs
  the real JavaScript under Node).
- GUI guards `tests.test_gui_concept71`, `tests.test_gui_concept74`, free-agency tests (`test_free_agency_bids`,
  `test_released_fa_opportunity`, `test_contract_protection`): OK. the re-signing test in `tests.test_player_lifecycle`: OK. The app-action payload test in `tests.test_foundation` (which calls `free_agency_room`) is skipped in this environment, so the payload was checked through the running app instead.
- `bash scripts/run_core_tests.sh`: 337 tests OK (2 skipped).
- Running app (port 8784, scratch save folder, headless Chromium): entry layout, keyboard row selection (arrows, Enter
  to the salary box), sort, live search (focus kept), quick salary buttons, typing over the limit (clamped to the
  largest legal offer, tax room shows $+0.0M), years with arrow keys, guarantee toggle, and a real signing. Page
  sideways scroll: 0 px in every run. Tab order: market (filters, sort headers, the selected row only), then the
  builder.
- Note for whoever reruns: the local test server sometimes drops some of the browser's parallel connections at
  startup; the screenshot driver now reloads until the app boots.

## 5. Not checked
- A real season into free agency (only the moved scratch save; its "last season" stats are zero).
- The standalone free-agents page outside the card board (the app now routes it to the board; the page still renders
  the same three panels with its own buttons, but I did not screenshot it).
- Very small "phone" widths (under ~700 px), which the app does not really support.
- The two scorecards (no engine change).

## 6. Found along the way (not changed)
- **Your offers and rival bids use different rules.** Rival teams' bids are judged by interest (salary against his
  market ask, years, fit, winning, role) and he signs once a bid clears the day's bar. Your offer from the app is
  judged on the spot, only against his projected minutes x $0.45M (+8-20% without a guarantee). So stars come cheap
  (Miller $13.6M vs a $28.8M ask) and low-ask role players cost more than their ask (Kevin Porter Jr. asks $7.8M but
  needs $13.5M from you). The new screen shows this honestly; the rule itself is an engine question.
- The "My Offers" market tab could never show anything in the app, because app offers are answered at once (only the
  text menu creates waiting bids). It now lists players you have made offers to, including declined ones.
- The Assistant GM phone overlay covers the right edge of the Offer Builder and Signing Wire at 1440 x 900 until it is
  dismissed (existing overlay; also noted by the UI batch).
- The scratch save's wire shows AI signings dated 3 July while the save is on 1 July (and even during re-signing):
  probably left over from how the UI batch built the draft-night save; not checked in a real career.
- The contract-extension page still shows an invented "Team direction 64" and similar interest bars (not free agency;
  not changed).

## 7. Questions for you
1. Should your offers follow the same rule as rival bids (interest against his market ask, settled at the end of the
   day, so you can lose a player to a better bid)? That is an engine change for a separate task. Until then the
   builder shows the current rule plainly.
2. The room opens again when free agency starts after the re-signing window (a new phase), resetting your window
   arrangement once. Keep, or keep the re-signing arrangement?
3. Market columns: I kept last season's PTS/REB/AST and dropped the other nine ratings and stats from the table (the
   builder and player card have them). Want any back as columns?
4. "Fits our room" uses the guaranteed price. Should it also count roster spots (rosters may run over 15 until camp)?
