# Playtest guide: what's new and what to look at

_Updated 2026-11-21. Everything below is in the main game. Start a **new save**; old saves don't get the new systems._

## How to start

**1. Open Terminal and go to the game folder:**
```bash
cd ~/Documents/BBall_data/BBall_Starting_Point
```

**2. Start the game.** This opens it in your browser at http://127.0.0.1:8765:
```bash
PYTHONPATH=src .venv/bin/python -m nba_gm_data.app_server --root . --open
```

**3. Choose New Save.** Saves made before a merge don't get the new systems.

**To stop the game:** click the Terminal window and press Control-C. Your save is kept.

**After Claude merges something:** you don't need to download anything, since merges land straight in this folder. Just stop the game (Control-C) and start it again with step 2. The new code only takes effect after a restart.

**If the browser says it can't connect:** the game isn't running. Run step 2 again. If Terminal says the address is already in use, an old copy is still running. Close that Terminal window, or start on another port by adding `--port 8766` to the end of step 2.

**What to cover:** a good first pass is one full season through the trade deadline, then the playoffs and the whole new offseason, into the next preseason. The offseason changed the most, so give it the most attention.

## What's new, and what to check

### Players and ratings
- **The player card** shows the game's real value on the overall, offense and defense numbers. Jokić, Gilgeous-Alexander and Wembanyama are near the top. *Check:* does the top 20 feel right?
- **Ratings follow analysts first, impact data second.** Dunks, shot types, strength and jumping come from real data.
- **Recent ratings fixes:**
  - Defensive rebounding now credits the real rebounders (Jokić, Wembanyama, Gobert, Zubac).
  - Strength no longer punishes long arms.
  - Team-defense reads are checked against film. Kuminga keeps his one-on-one defense but rates lower on rotations and focus.
- **Screen assists** are a stat in box scores and the league leaders.
- **Prospect cards** show "Scouts' upside estimate". True potential stays hidden until a player signs.

### Games, minutes and health
- **Minutes look real.** Stars play about 34–36. Blowouts rest starters, and injured players' minutes go to the right backups. Each coach has a "ride the stars" tendency.
- **Injuries:**
  - They happen mid-game, and players come back rusty on a minutes limit.
  - Lengths follow real data: about 4 in 10 injuries cost a single game.
  - A new career opens with **the real 2026-27 opening-night injuries**, and nobody else starts hurt.
  - *Check:* does the injury report look like a real NBA team's?
- **Rest:**
  - AI teams rest stars on back-to-backs, against weak or elite opponents, and once seeds are locked, each time with a reason. Teams rest less on national TV games (the "TV" tag on the calendar).
  - Your team has a "Coach rests players" switch (off by default), and a zZ "rest for N games" button beside each player's minutes.
- **Fatigue** builds with minutes actually played and fades with rest days.

### Trades
- **Front offices have personalities** based on their real reputations: savvy, patience, urgency, favorite players and loyalty. Sacramento overpays for veterans; Oklahoma City hoards picks.
  - Each team page has a **Front Office** button with your assistant GM's read, which gets sharper the more you deal with that team.
- **Negotiations run over several days with several teams.**
  - Teams counter each other and you, for up to 4 rounds.
  - Good players whose teams have a reason to sell get **shopped**, which can start a **bidding war**.
  - A team whose patience runs out makes a **take-it-or-leave-it** final offer.
- **The Trade Market board** shows who's available, who's interested and how far talks have gone. Your assistant GM texts you about notable players being shopped.
- **Trades follow the real calendar:** busy draft nights, the first days of free agency (from June 30), late summer, and the deadline.
- **Newly signed players can't be traded until their real date:** December 15, January 15 after a big Bird raise, or three months.
- *Check:*
  - Do trades make sense, and does each one state a believable reason?
  - Is the deadline busy enough (real: 23–28 trades in deadline week)?
  - Do counters and final offers in the trade window feel like a real negotiation?

### The offseason (new: four stops in the real order)
1. **Decide who to keep** (from June 17, with the draft on June 22–24 in the middle). One checklist, sorted by deadline:
   - **Player and team options:** keep him, or decline.
   - **Qualifying offers** to young players (send, max offer, no offer, withdraw).
   - **Your own free agents,** with Bird rights shown plainly.
   - **Cap holds,** with a Renounce button and a before/after preview.
2. **Make offers** (from June 30). The free-agency room shows how each offer would be paid for: Bird rights, cap room, the mid-level, the bi-annual or the minimum. It also shows what that locks in, for example "hard-capped at the first apron".
3. **Signing day.** A recap of who you signed, who left and where, and what's still open.
4. **Set the roster** (October). Cut from up to 21 players to 15. Rookie-scale extensions close the day before opening night, and rookie options come due in early November.

**The money rules are real:**
- exact cap and tax lines;
- true max and minimum salaries;
- raises that grow year by year;
- exceptions as real budgets;
- hard caps triggered by specific moves.

**AI teams make the same decisions.** Players opt out when the market pays more. Teams send qualifying offers to young players who played real minutes. About half of free agents return to their own team, as in real life. Stars stay with teams that hold their rights.

*Check:* does the summer feel like a real NBA offseason, and does each stop make sense without reading anything?

### Draft
- **Two boards:** Consensus, and Your board (your scouts, talent only, updated monthly), plus "Fit for us".
- **AI teams** pick from their own scouts' boards plus team needs, each pick with a reason.

### Screens
- **One table style** everywhere. Every window has its own icon.
- **A year-end recap** after the Finals and a **preseason outlook** at the start of each season; reopen both from Settings.
- **Awards:** Finals MVP, Sixth Man, Most Improved and All-NBA, using the 65-game rule.

## Known gaps (don't spend time on these)
- **Simulation speed:** a simulated month takes about 30–37 seconds, and the offseason takes a little longer to play through than before.
- **Offer sheets are coming next.** Until then, a restricted free agent negotiates only with his own team, and too many take the one-year qualifying offer.
- **Not built yet:** two-way contracts, camp (Exhibit 10) deals and sign-and-trades.
- **Games played:** the very best players still play a few more games than real ones. A fix is being tested.
- **Browsers:** some screens are only checked in Chrome at desktop sizes.

## How to send feedback
Note what felt wrong and roughly when (date in the game, team, player). Screenshots help. The most useful feedback is anything that doesn't feel like real basketball.
