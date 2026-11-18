# Trade AI direction (user, 2026-11-19)

Captured from the user's own description. This is the design brief for the trade AI; later tasks refine it.

## Why
The trade-deadline run evaluates about 20,000 trades. The goal is not to make the search faster, but smarter: decide
which trades are worth evaluating at all. To know that, first look at the trades the AI makes today, the way a
person would, and see where they don't make sense.

## Three layers, in order of importance

### 1. Value: the raw worth of the assets each team moves
- Player impact (how good he is), age, contract.
- Draft picks and what each pick is likely worth.

### 2. Context: why this trade makes sense for these two teams
- **Fit on both sides:** how well the player fits the team giving him up, and the team getting him.
- **Role and future:** is he a future core piece for the team, or a depth player who doesn't get minutes?
- **Succession:** if an older player is leaving, is a younger player there to take the role?
- **Tenure:** how long the player has been with the team.
- **Team phase:** contending, close, rebuilding; how old the core players are.
- **Investment:** how much a team recently put into a player, for example trading up to draft him, or a recent
  first-round pick. Teams rarely move assets they just paid a lot for. (The exact assets given up don't need to be
  remembered; the size of the investment and how recent it is do.)

Value plus context together produce **"textbook" trades**: roughly fair value, and a good reason for both teams.
**These are the most important thing to get right and must not be lost.** Refining what a textbook trade is comes
first.

### 3. Front-office personality: why real trades aren't textbook
- Every front office has people with opinions on specific players.
- Some front offices are less savvy than others; real trades have winners and losers.
- This is a small, deliberate layer on top of textbook trades, added after the textbook model is solid.

## How general managers actually work: targets first (user, 2026-11-19, follow-up)
- A front office **starts from a target**. It can be specific (this player) or vague (this kind of player, or a
  range: "a starting-level wing who can shoot", "a backup center under $10M").
- It then looks at its **options** for getting that target: can it be had for a reasonable price, for something that
  makes sense for the team? What are the alternatives?
- **Targets must make sense for the team**: its phase and what it's trying to do. Getting target selection right is
  critical to realism.
- **Wanting a player doesn't mean getting him.** The other team doesn't just give in once the value is met. It has
  targets of its own, possibly on the team making the offer; if it doesn't want anything that team has, it asks for
  more raw value instead.
- This should be both more realistic and faster than brute force: teams only search for what they're looking for.

## Multi-team trades stay
Three-team (and larger) trades must not be lost. Check real-life rates of multi-team versus two-team trades and keep
the engine near them.

## Calibrate against real trades
Study real trades from the 2025-26 and 2026-27 seasons, with their context and how analysts judged them. Example the
user gave: Nique Clifford traded for two second-round picks this season. On raw value that might be close, but
people disliked it: he was a recent first-round pick and Sacramento had traded up to get him.

## Order of work
1. Human-style review of the trades the AI currently makes (from simulated seasons), against real trades.
2. Refine the textbook model (value + context), including investment and tenure.
3. Target-driven search: each front office picks targets (specific or vague) that fit its phase and plan, explores
   the options and alternatives for each, and the other team answers with its own targets or a demand for more value.
   Keep multi-team trades at real-life rates. This is what makes the deadline fast.
4. Front-office personality layer (savvy, player opinions), small and deliberate.
