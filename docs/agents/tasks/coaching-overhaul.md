# Coaching / staff overhaul (user request 2026-11-18)

User: coaching is too simple; at least 3 ratings per staff role with actual impact; coaches change over time.

## Current system (audit 2026-11-18, read-only subagent)
- Six roles per team: head coach, offensive coordinator, defensive coordinator, development lead, scouting lead,
  performance lead. Each has 3 skill ratings + 3 shared personality ratings (adaptability, communication, ambition),
  20-96 scale. On paper 3 per role; in practice:
- The sim reads 0-5 "stars" averaged across roles (save.py save_coach_ratings): offense +/-~3 per 100, defense +/-~3.2,
  tempo +/-2 possessions, small matchup minute shifts. Coordinators have no separate effect (averaged into shared stars).
- **Dead or mis-wired**: rotation_trust and player_buy_in stars (computed, unused); playoff_preparation (computed, never
  applied — no playoff coaching effect); the head-coach part of development uses a static real-name reputation table, not
  the save's coach (hiring/firing changes nothing there); staff morale (unused); job_security (static); archetype/style
  tags (display only); two unreconciled real-coach reputation tables (sim.py and staff.py).
- Effects that do work: development lead (growth multiplier ~ +/-12%, focus weights), performance lead (injury odds
  -12%/+8%, fatigue, recovery length), scouting lead (draft board noise and confidence).
- **No change over time**: no age, experience, progression, decline, retirement, reputation drift; the free-agent pool is
  a fixed ladder (best generated head coach grade 76 vs Kerr 93), never refilled.
- GUI text promises effects that are not modeled (buy-in, rotation trust, playoff preparation, morale).
- No tests cover the coach-effect numbers.

## Evidence available
- Basketball Index growth curve: per-head-coach development effect (players' actual minus projected development; 56
  coaches, 231 coach-seasons) -> a real development rating for real coaches.
- Existing real-coach reputation sources (Bleacher Report 2026 ranking, 0-5 star attributes), coach records/experience
  (coaches_espn_2026.json, BRef/NBA staff pages).
- Team performance vs talent expectation (lineup data, xPoints standings) is possible but noisy; use lightly.

## Proposed design (for user review)
Each role gets 3 ratings that each drive one distinct, testable effect (plus personality as tendencies):
- **Head coach**: Rotation management (in-game minutes decisions around the user's rough targets: fatigue, fouls,
  blowouts, hot/cold hands, matchups — project rule 8), Player relations (buy-in/morale -> small performance and
  minutes-acceptance effect, player happiness/re-signing), Game management (in-game adjustments, late-game execution,
  the playoff effect that is currently dead).
- **Offensive coordinator**: Shot quality (shot diet / ORtg), Spacing design (how well shooter-heavy lineups fit),
  Creator usage (how efficiently stars carry high usage).
- **Defensive coordinator**: Coverage design (DRtg), Matchup scheming (hiding weak defenders, targeting), Discipline
  (fouls committed, transition defense).
- **Development lead**: Skill development (technique growth), Young-player growth (prospects/G-League), Veteran
  maintenance (slows skill decline; physical decline stays age-driven). Real head coaches' BBI development effect feeds
  the head coach's share.
- **Scouting lead**: Talent evaluation, Medical/bust risk (ties into the injury overhaul's medicals), International/
  college coverage; also accuracy of the AI's own trade and free-agent evaluations for AI teams.
- **Performance lead**: Injury prevention (per-region hazard), Conditioning (fatigue), Recovery (return timing, rust).
- **Lifecycle**: staff age and experience; ratings drift yearly (younger staff improve, older decline, experience grows
  game management); reputation moves with results vs expectations; retirement; a refilled pool each offseason
  (assistants promoted, coordinators become head-coach candidates); job security moves with results (hot seat).
- Every displayed rating is used by the engine (rule 4); GUI text rewritten to match.

## User decisions (2026-11-18)
- Morale/chemistry system: **later**; player relations starts with minutes acceptance and buy-in/playoff effects.
- Built after the injury overhaul.
- Still open: size of coaching effects (keep current +/-3 per 100 scale, or evidence-calibrated).

## Resume state
Design drafted; awaiting user review.
