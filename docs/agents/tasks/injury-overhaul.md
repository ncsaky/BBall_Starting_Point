# Injury engine overhaul (user request 2026-11-18)

User: replace the single injury-risk number with per-body-area tracking; same-area injuries compound; body type, play style,
role, usage/workload and ratings change which injuries happen and how often. Evidence: Basketball Index Injury Tracker
(`data/research/bbi/tools/injury_*.json`, extracted by Codex BBX) plus Codex task INJ (current output vs that evidence).

## Current system (audit 2026-11-18, read-only subagent)
- Per player: a health profile (durability 1-99, injury_prone flag, body-area risk TAGS, major prior injuries), one health
  state (fatigue, one current injury, return date, rust), and injury events. Body area is a plain label with almost no effect.
- Draw: once per scheduled game for the top-11 rotation (8+ projected minutes): base 0.021 x minutes x fatigue x
  (low durability) x (low stamina) x age ramp x 1.22 if prone x performance staff (0.88-1.08), clamped 0.0005-0.19.
  Stamina is the only rating used. Severity is a league-wide quota-weighted pick among 5 bands (not player-specific);
  body area is a quota-weighted pick (x1.55 if tagged). Duration is uniform within the band. "Recurrence" is a flag that
  changes nothing; nothing compounds; prior injuries are only counted league-wide for quotas.
- Effects: out until return date; rust (3/8/16/28/45 by band) -> in-game penalty 0.08 per point, cap 4; small development
  drag while hurt/tired; trade/contract value via transactions.player_health_risk (0-34; ~15 consumers; narrative.py
  duplicates it). No permanent post-injury loss.
- Config `data/overrides/injury_model_config.json` is hand-set ("2K-style sandbox", quotas guessed, never fitted).
- Bug: GUI severity label reads `injury_severity` fields no code writes.
- Perf: simulate_health runs every day (also no-game days), re-reads config, rescans events; cheap per draw.

## Proposed design (for user review)
1. **Body regions** (about 10, matching Basketball Index's regions): ankle, foot, knee, lower leg/Achilles, thigh/hamstring,
   hip/groin, back/core, shoulder/arm, hand/wrist, head/concussion, plus illness/other.
2. **Per-player, per-region state**: injury history (count, recency-weighted), current "vulnerability" that rises after an
   injury there and decays over months, and a player-specific region durability (real players: from BBI per-body-part
   risk and their absence history; generated players: from body type and play style).
3. **Per-game hazard per region** = evidence base rate x age (by region) x workload (minutes, back-to-backs, fatigue) x
   body (height/weight/wingspan; e.g. heavy bigs -> knee/foot/back) x play style (drives/rim pressure/explosiveness ->
   ankle/knee/foot/hamstring; post/rebounding/contact -> back/hand/shoulder) x history (BBI recurrence risk ratios:
   same-region priors raise risk, decaying with time) x medical staff. Rates calibrated so league totals match BBI
   games-missed-per-82 by age/role; no league quotas inside the draw.
4. **Diagnosis and duration**: pick a diagnosis within the region (e.g. ankle sprain vs fracture) and draw days out from
   BBI's real return-day distribution for that diagnosis (25/50/75/90th percentiles). Severity follows from the diagnosis.
5. **Several injuries at once** allowed; availability = latest return date. Optional later: playing through minor injuries
   with a penalty.
6. **Aftermath from evidence**: rust/return ramp from BBI short-term curves (minutes and shooting after return by absence
   length); permanent effects only where BBI long-term data shows them (e.g. major lower-leg injuries -> athletic decline).
7. AI/trade value keeps a derived health-risk summary (0-34 scale) computed from the new state, so the ~15 consumers keep
   working; GUI shows diagnosis + body part (fixes the severity label bug); player card can show an injury history by region.
8. Perf: precompute per-player region hazards once per day (or when ratings/profile change).

## Open decisions for the user
- Permanent rating loss after major injuries (evidence-based) — yes/no.
- Playing through minor injuries (with a penalty) now or later.

## Resume state
Design drafted; awaiting user review. Codex INJ (engine output vs BBI) running in parallel.
