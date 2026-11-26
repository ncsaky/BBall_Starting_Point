# Involvement (T08): should the model carry a player's own scoring share separately? (RATINGS-FIVE-INPUTS)

**Recommendation: no new input now.** The evidence says the split between scoring himself and creating for teammates
is already carried by an existing input (the action mix T01), and a separate "scoring share" input would add almost
nothing that holds up from one season to the next. Nothing was changed; this note is for the user's decision.

## The question
S2-USAGE found that Stage 2 gives high-creation players (Nolan Traoré, Jaren Jackson Jr., DeMar DeRozan, Brandon
Ingram, Zion Williamson, Anthony Davis) too many of their own shots and low-usage finishers too few. Involvement (T08)
is built from Basketball Index's **true usage**, which counts the possessions a player finishes himself *and* the ones he
creates for teammates. Should the model split it into "finishes himself" and "creates for others"?

## What T08 is today
- T08 matches true usage at r .97 across 376 rotation players (500+ minutes in 2025-26), spread .91 as wide. It is
  exactly what it claims to be: how much of the offense runs through him. That matches the approved definition
  ("tendency to seek touches/initiations").
- Plain usage rate (shots, free-throw trips and turnovers only) is a different thing: it matches true usage at only
  .885. A player's own share of his involvement (usage / true usage) averages .675, with a spread of .091 between
  players, and it is a stable habit: .861 from 2024-25 to 2025-26 among players with 1,000+ minutes both seasons.

## Is the split missing from the inputs? Mostly not.
Predicting each player's real 2025-26 usage rate (336 players with three seasons of data):

| Inputs used | Match with real usage (r) |
|---|---|
| Involvement (T08) alone | .88 |
| Involvement + the action mix (T01 shoot / pass / drive / post) — **what the model has now** | **.956** |
| + a scoring-share input built from 2023-24 and 2024-25 only (a fair, out-of-season test) | .958 |
| + a scoring-share input that includes 2025-26 itself (partly the answer key) | .966 |

The action mix already says who shoots and who passes on a touch (T01's pass share alone explains the own-scoring share at
r −.80, and the whole mix at .89). A new input measured the same way would add .002 out of season. The 2.1-point gap
S2-USAGE saw with *real* usage (points miss 9.0% → 7.1%) is mostly season-to-season change and team context (who else is
on the floor, the coach's role), which no player input can carry.

## If the user still wants it
A new tendency ("scoring share of involvement": the share of his involved possessions he finishes himself, measured as
Basketball Index usage rate / true usage, season-weighted like the other measured tendencies) would bring the model to 95
inputs, which the product rules forbid without the user's approval. Today's engine would not read it, so its scorecards
would not move; Stage 2's usage rule would multiply involvement by it.

## Where the remaining usage miss lives instead
- **Team context:** usage is shared among the five on the floor. A creator next to other creators (Traoré beside
  ball-dominant guards) finishes fewer of his own plays than his habits alone imply. That belongs to the coach-usage
  layer and to how Stage 2 shares the ball within a lineup.
- **The shot-location fix in this task** moves rim attempts away from several of the over-used bigs (Jackson Jr.,
  Davis, Porziņģis, Nurkić) and toward under-used finishers (Murray-Boyles, Payton II, Tyson, Larsson), which changes
  their make chances and free throws, though not the usage rule itself.
