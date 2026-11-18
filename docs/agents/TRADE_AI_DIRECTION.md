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

## Calibrate against real trades
Study real trades from the 2025-26 and 2026-27 seasons, with their context and how analysts judged them. Example the
user gave: Nique Clifford traded for two second-round picks this season. On raw value that might be close, but
people disliked it: he was a recent first-round pick and Sacramento had traded up to get him.

## Order of work
1. Human-style review of the trades the AI currently makes (from simulated seasons), against real trades.
2. Refine the textbook model (value + context), including investment and tenure.
3. Smarter search: generate candidate trades from team needs and context instead of brute force (this is what
   makes the deadline fast).
4. Front-office personality layer (savvy, player opinions), small and deliberate.
