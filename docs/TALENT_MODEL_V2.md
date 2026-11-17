# Talent Diversity and Role Value

## Version Boundary

New-game baseline `2026-10-23-talent-v4` opts into `meta.talent_model_version = 2`. Earlier archives do not contain that flag and keep the previous overall/impact formulas and future-class generation. New generated prospects carry `src_talent_balance_v2` provenance through scouting, onboarding, signings and save reload. Per-trait career-capacity records remain attached to the generated trait, not recalculated from the player's improved rating.

All existing imported player traits are identical to V3, including the Irving, Lively, Murray-Boyles and George corrections. Medical profiles, contracts and pick terms are unchanged. No save migration, league-wide annual normalization, forced retirements or increased injury rates is included.

## Present Ability and Profile Shape

Procedural classes keep the same class-strength, depth, top-end, identity, physical and medical draws. Skill-shape draws use a separate stable stream. The October 26 rare-upside follow-up modestly widens the potential tail for newly generated V2 classes only; it does not change entry skills, legacy generation or already saved classes. See [the supply screen and its limits](RARE_UPSIDE_SUPPLY_2026_10_26.md). Archetype-correlated strengths and one or two likely weaknesses replace uniformly mild profiles; some players remain relatively complete. Traditional rim-running centers usually retain poor shooting, guards usually retain little rim protection, and offensive/defensive limitations vary rather than following a universal team/pick penalty.

The V2 conversion allows genuine sub-25 weaknesses instead of imposing the legacy 25 minimum. Sharp shooting, screen-defense and rim-protection mappings avoid excessive smoothing from unrelated attributes. High NBA readiness raises usable strengths, not severe weaknesses. There is no slot-specific overall target or automatic starter grade for every lottery pick.

Potential no longer directly raises present shooting/creation/playoff traits, or the immediate minutes projection. A team can still prioritize a high-upside player's development; allocation of opportunity is a management decision, not evidence of current polished skill. Existing draft-slot playing-time priors otherwise remain in place.

## Persistent Career Capacity

Generated trait records include entry ability, potential, entry skill and an aptitude estimate informed by the profile, motor and feel. Combined with the existing save-seeded realization, these produce stable, different per-skill ceilings. A bad outcome can plateau after little improvement; a successful high-upside player can retain generous headroom in good skills while never fixing a major hole.

Successful high-upside careers receive bounded additional learning support in stronger skills. This is selective, not a universal growth multiplier. The October 26 forward calibration adds learning runway through the twenties and capacity-directed catch-up for unusually raw, successful high-upside profiles. Only that raw catch-up case can exceed the original .36 monthly cap, with a worst-case .81 bound; ordinary, disappointing and legacy profiles retain their previous bounds and rates. Real opportunity, staff, age, fatigue and injury interruption continue to affect realized growth. The additional runway stops at age 30. Aging coefficients and retirement rules are unchanged; revised role values can indirectly change retention, playing time and retirement decisions. Noise cannot accumulate positive growth beyond a plateau, but a ceiling is not a minimum and does not prevent decline. See [the forward calibration and paired evidence](PROSPECT_LEARNING_2026_10_26.md).

Ceilings use a bounded cache of primitive inputs. Trades and reloads do not reroll them. Extension projections pass the same capacity records and role model into the existing monthly rules rather than drawing an incompatible curve.

## Specialist Value and AI Consumers

The role summary includes rebounding and changes the relevance of the six existing composites: shooting, creation, defense, athleticism, IQ and rebounding. Centers are not expected to contribute like lead guards. A limited premium recognizes the strongest two role-relevant composites rather than rewarding an arbitrary single raw attribute. A uniform skill profile receives no position-only bonus.

This is not solely a display edit. `sim.player_impact_score` uses the shared role calculation, which flows through projected usage, player/team simulation features and transaction valuations. `transactions.build_player_asset_valuations` consumes those features; `contract_ai.build_player_contract_market_profiles` consumes those valuations. Rotation, cutdown and retention consumers use the revised `save.player_attribute_summary`. No existing contract is rewritten to a newly estimated price.

The remaining formulas still contain contextual approximations and historical priors. A modest role summary cannot certify optimal lineup decisions or solve every specialist evaluation. In particular, raw draft current-ability/potential estimates and rookie-value protections still matter to AI valuations and are not secretly replaced with display overall.

## Measurement and Evidence

The census observer records both the active-model fixed-24-minute overall and the legacy fixed-24-minute overall. A better headline cannot thereby be mistaken for more underlying talent or a lower inflation rate. Draft outcomes include the entire controlled class, not only roster survivors; actual-career censuses separately retain roster membership, age year, draft year, transactions, health and retirement records.

Research supports heterogeneous careers, not a single guaranteed development curve: [Vaci et al.'s NBA aging analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC6690864/) models individual development/decline and compensating skills; [Berkeley's draft study](https://sportsanalytics.studentorg.berkeley.edu/articles/decoding-the-draft.html) distinguishes contribution by draft position; [its second-round analysis](https://sportsanalytics.studentorg.berkeley.edu/articles/trash-or-treasure.html) emphasizes career participation and differing outcomes. Those observations motivate the model. They do not establish our exact coefficients or turn a selected OVR threshold into an empirical bust definition.

## Reproduction

- `PYTHONPATH=src:scripts python scripts/verify_talent_balance.py survey` builds a candidate and isolated starting saves. It refuses to overwrite existing survey saves.
- `... probe` compares legacy, new shape/readiness without plateaus, and the complete model across the same six class/seed contexts over 18 controlled years.
- `... soak --seed 17 --seasons 2` and seed 29 use real app actions, required decisions and short-lived action workers to bound memory. Each worker finishes an action and persists its audit checkpoint before exiting; the next reload continues the same career. `... validate --seasons 2` independently validates the resulting seasons, draft slots, development months, health coverage, retirement identities and model propagation through signings/reloads.
- `... prepare_replay`, `... replay --label before/after` and `... partition` compare an old V3 career across frozen/new runtimes and a V4 career advanced daily versus weekly across a month boundary.
- The bounded full-sweep launcher is `output/talent-balance-2026-10-23/check_suite_isolated.py`; `... classify` records known/reproduced failures and rejects unclassified failed methods. The authorization fixture pins a known-positive V3 market; the talent tests separately exercise an actual V4 trade-finder offer.
- `... publish` requires the verified candidate to equal a fresh deterministic build, completed career/propagation checks and classified regression results, while preserving old archives/playable save hashes. This gate does not mean the whole repository suite is green.

Artifacts are under `output/talent-balance-2026-10-23/`. Rejected prototypes remain there separately and are not published versions. Long-run equilibrium still requires longer actual league careers; healthy fixed-opportunity probes are mechanism diagnostics, not forecasts of NBA outcome rates.
