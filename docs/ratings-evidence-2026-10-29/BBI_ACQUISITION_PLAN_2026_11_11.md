# BBI acquisition plan — November 11, 2026

**Purpose: maximize useful league-wide input evidence from one possible month, not collect a small star sample or every column indiscriminately.** No purchase, account access or paid player-data acquisition has occurred. This task checked public documentation and a metric dictionary only; the four-row historical demo from the prior task is reused as feasibility evidence.

**The demo is2019–20, not last season.** Its actual scope includes2018–19 and2019–20 Lakers, despite a November11,2026 interface update label. Our primary acquisition target is completed **2025–26 regular season**, followed by **2024–25**, with **2023–24** useful for stability, age/role changes and interrupted seasons. The game's target is October immediately before2026–27. Projected2026–27 talent is a forecast, and actual2026–27 games are post-start evidence; neither belongs silently in the opening baseline.

Recommendation remains **yes to one targeted $5 month if the user chooses**, with early access/transfer checks and a league-wide capture plan. The likely benefit is substantially better skill/context evidence across both offense and defense. It is not a verified ability to download a complete database or automatically replace every rating. [Public package](https://www.bball-index.com/data-tools-package/)

Backend owns [the player-ratings blueprint](../PLAYER_RATINGS_BLUEPRINT_2026_11_11.md), schema design and code. This plan supplies evidence to that work;114 requested metrics are not114 proposed game traits. No production ratings, contracts, saves, growth mechanics, simulations or UI change is included.

## 1. What is actually verified

| Public evidence | Verified result | Still unverified |
|---|---|---|
| [Package](https://www.bball-index.com/data-tools-package/) and [Skills page](https://www.bball-index.com/skills-application/) | Membership advertises full covered seasons/metrics; skills filtering by season/role/team/minutes. | Exact field-by-season completeness, account access, export, IDs and sample metadata for completed2025–26/2024–25. “Every season” is not proof every metric exists in every year. |
| [Leaderboards](https://www.bball-index.com/leaderboards-tool/) | Documents values, grades, percentiles and subset comparisons. | No public skills CSV/XLSX export promise found in the inspected pages/search. Absence of a promise does not establish absence of a feature. |
| [Skills demo](https://bball-index.shinyapps.io/SkillsDemo/) | Prior public browser query returned actual historical defensive values, minutes and roles; four rows preserved. | It does not verify current skill rows or full-league access. Its selector years2019/2020 correspond to table seasons2018–19/2019–20; confirm season conventions during capture. |
| [Public glossary](https://www.bball-index.com/glossary/) → [published sheet](https://docs.google.com/spreadsheets/d/e/2PACX-1vTqxPLTuFQwWBFof7XlhHBYidVupesU81LllfS1G8uBTeHfpbByEbh1bM0Ih1aUU4XDCcHTKKLSuITT/pubhtml/sheet?headers=false&gid=263593269) |222 relevant metric labels cataloged;25 targeted definitions checked across skill/context families, plus earlier defensive checks. Names/categories retained, not a player dataset. | Numerical encoding, provider model/version, raw event denominators, exact sample reliability and full historical availability. |
| [Passing guide](https://www.bball-index.com/a-guide-to-passing-stats/) | Explains passing components, stabilization and opportunity. | No proof a general passing composite measures pressure handling or every kind of read. |
| [Offensive Talent introduction](https://www.bball-index.com/offensive-talent-introduction/) | Describes a provider model combining underlying skills and role context. | A total talent grade is not an independent input to add to every constituent skill. Current coefficient/formula access is not promised. |
| [2018 defensive/rebounding explanation](https://www.bball-index.com/explaining-defensive-rebounding-talent-grades/) | Historical methodology explicitly mixes tracking, sample adjustment and some on/off evidence. | **Legacy description**, not proof the current formula is unchanged. “Talent” does not guarantee independence from impact. |
| Free LEBRON/lineups/rotation surfaces | Previously checked: impact interface/CSV control, lineup query UI and rotation loading page. | No current player export was acquired. A LEBRON export control does not establish a skills export. Impact and minutes cannot substitute for independent skill channels. |

Public-field statuses in the manifest mean **documented labels**, with selected definitions checked—not paid data acquired. The actual demo is historical. Export and event-level opportunities remain questions to resolve with exposed account features or provider clarification, not hidden endpoints.

## 2. Acquisition manifests and priority

The [machine-readable acquisition manifest](BBI_ACQUISITION_MANIFEST_2026_11_11.json) lists **114 named requests across13 skill/context groups**, their public categories, working evidence type, required sample information, overlap warnings and intended basketball questions. It separates essential P1 fields, supporting P2 history/uncertainty and optional P3 validation. This is a useful-field request set, not a target to maximize column count. If a provider-supported full bundle is the only exposed download, preserve it once and extract the useful subset; unused columns do not count as success.

### P1 — essential league-wide skill and context coverage

Exact provider names are preserved in the JSON, including spelling variants. The table below identifies the minimum distinct questions each batch must answer. Each group should cover **all exposed NBA player-season rows**, not just the feasibility cohort.

| Group | Named examples to request | Distinction / evidence type and sample needs |
|---|---|---|
| Shooting accuracy/difficulty/creation | `3PT %`, `3PT FGA Per 75 Possessions`, `3PT Shot Making`, `3PT Shot Quality`, `3PT Shot Creation`, `3PT Functional Versatility` | Observed accuracy/volume versus modeled difficulty, self-creation and shot mix. Need attempts, distance/openness definitions and representation. A difficult-shot model is not a direct release-time measurement. |
| Catch/pull-up/deep/midrange | `C&S 3PT FG%`, `C&S 3PT Shot Making`, `3PT Pull Up FG%`, `3PT Pull Up Shot Making`, `Deep 3PT Shot Making`, `Midrange Shot Making`, stabilized context percentages | Separate shooting contexts and sample stability. Need attempts by type; low pull-up volume is not proof a player cannot pull up. Deep attempts show use as well as ability. |
| Finishing versus rim access | `Rim FG%`, `Rim Shot Attempts Per 75 Possessions`, `% of Shots at Rim Unassisted`, `Rim Shot Creation`, `Rim Shot Making`, `Rim Shot Quality`, `Drives Per 75 Possessions` | Getting there versus finishing, assisted opportunity versus self-created pressure. Need rim attempts/drives/possessions and shot-location definition. Total finishing model overlaps submetrics. |
| Foul/contact/post/intermediate | `Drive Foul Drawn Rate`, `Contact Finish Rate`, `Floater Shot Making`, `Paint Touches Per 75 Possessions`, `Post Up Draw Foul Rate`, `Stable Post Up PPP` | Contact Finish uses fouled2pt attempts, not all contact attempts. Post production depends on opportunity/matchups. Need fouled attempts, drives, post possessions, floater samples and foul definitions. |
| Handling/passing/creation contexts | `Passing Creation Volume`, `Passing Creation Quality`, `Passing Efficiency`, `Passing Versatility`, `Potential Assists Per 100 Passes`, `Turnovers Per 100 Touches`, lost-ball/bad-pass variants, `Isolation Turnover Rate` | Observational turnovers versus provider estimates of pass quality/read variety. Need touches, passes, potential assists and turnover/action samples. **Direct pressure-tagged handling is not confirmed**; do not call every turnover handling failure. |
| Screening/rolling | `Screen Assists Per 75 Possessions`, `Screening Talent`, `Roll Man Poss Per 75 Possessions`, `Roll Man Impact Per 75 Possessions` | Screening model versus action use and roll/pop/slip scoring production. Need screens/actions, roll opportunities and scoring samples; a per75 production label is not an intrinsic skill coefficient. |
| Off-ball movement | `Cuts Per 75 Possessions`, `Cut FG%`, `Off-Ball Screen Possessions Per 75 Possessions`, `Off-Ball Screen eFG%`, `Movement Attack Rate`, movement distance/speed ratings | Execution and use are separate. Published movement ratings compare offense within role; do not turn them into raw speed or cardio. Need cut/off-screen opportunities and distance/time context. |
| OREB | Chance rate, adjusted success, contested share, crashing/conversion estimates, talent total and putback production | Chance creation versus conversion, with team scheme and deferrals. Need chances, contested/deferred opportunities and putback attempts. Model crashing ability is not necessarily desired crash behavior. |
| DREB / box-out context | Defensive chance rate, adjusted success, contested share, crashing/conversion estimates and talent total | Securing rebounds and getting into position differ. **Box-out counts/opportunities/technique are not confirmed** in the inspected catalog. Rebound totals alone cannot supply them; need chance/deferred samples. |
| Rim success/prevention/opportunity | Expected-adjusted contest result, contest volume/stabilized variants, deterrence share/rate, block-on-contest rate and screener rim defense | Keep successful contests separate from avoidance and opportunity. Need defended makes/attempts and on-court/rim exposure; no block+height+role bonus substituted for these channels. Overall rim composite is an overlap check. |
| Containment/navigation/pursuit | `Perimeter Isolation Defense`, `Ball Screen Navigation`, `Off-Ball Chaser Defense`, `Screener Mobile Defense` | Documented provider estimates, not timed physical tests. Need opponent/action/sample context. Direct contact resistance/recovery speed remains unconfirmed. |
| Help/disruptions/work | `Help Defensive Activity`, `Help Effectiveness Rating`, help total, deflections, passing-lane/pickpocket estimates, distance/foul context | Help volume versus success, plus event production and duty. Role-adjusted feet traveled is context, not intrinsic stamina; help IQ does not follow from offensive passing IQ. Need help events and exposure. |
| Deployment/coverage context | Matchup difficulty, positional/role versatility and P&R/DHO/off-ball coverage aggression/versatility; role labels from player rows | Assignments and schemes, not skill grants. **Opponent-ID/time/shares are requested but unverified**. Need minutes/possessions and definition/version; do not confuse aggression with effectiveness. |

All groups should retain available minutes and enough identity/season/context to interpret the evidence. Request games and actual event denominators where available, but do not promise them: a rate or stabilized value is not a raw sample count. If denominators are absent, record that explicitly and use minutes/available exposure only as weaker reliability context. Do not fabricate event counts by multiplying a per75 rate by minutes without actual possessions.

### P2 — supporting history and uncertainty

After the two core seasons are safely preserved, acquire the same useful groups for **2023–24** where covered, preferably league-wide by the same exposed method. An earlier uninjured season can be especially useful for return-from-injury players, but preserve its date rather than quietly making it current ability. A rookie's missing earlier NBA row is expected, not zero skill. Retain birthdate/age if exposed, team changes/stints, minutes, games and injury/role annotations from dated existing sources; provider medical or durability detail is not assumed.

Capture raw values and provider grades/percentiles as **different representations** if useful. Prefer values and samples first. Grades/percentiles aid comparison but depend on the selected population, season and filters. Never convert podcast rank, season percentile or provider letter grade directly into game OVR. Record grade population and stabilization/version information if exposed; otherwise mark unknown.

A completed season fetched now may be retrospectively modeled with later formula updates. Record retrieval date and provider as-of/version separately from season. It can be useful retrospective evidence without pretending that exact published grade existed on October20. Keep2026–27 projections and early-season results out of the opening-state dataset.

### P3 — optional validation, after useful skill coverage

LEBRON/O-LEBRON/D-LEBRON/WAR, overall offensive/defensive talent and optimization, stabilized lineup data, teammate/opponent context and minutes can test whether a profile makes basketball sense. Keep constituent overlap explicit: a provider total is not another independent vote after its components are used. Age curves are forecasts/priors, not imported growth mechanics. Matched historical playoff samples may contextualize retained playoff scouting, but small matchup-dependent runs do not automatically set a universal playoff trait.

Do not spend the month collecting attractive lineup/impact charts while missing basic shot-context, passing, rebound-opportunity and screen/help evidence. Free tools can supply some validation later; core skill access is the main reason to consider a month.

## 3. From a small feasibility check to broad coverage

### Before purchase / account access

Public evidence supports the likely value, while transfer and sample access are unresolved. A human can decide whether that uncertainty is acceptable for one month or ask the provider the two focused questions at the end. No message is sent and no purchase/login is attempted by this task.

### First authorized session: verify, then expand

1. Human activates/logs into the intended monthly package if desired; no credentials need be sent here. Confirm the account exposes completed2025–26 and2024–25 regular seasons, not just projections/current games. Confirm ending-year selector conventions and default sample/minute filters.
2. Use the12-player feasibility cohort in the manifest across both seasons: scorer/shooter, passer, guard defender, helper, anchor, traded player, low-minute case and rookie. Missing earlier rookie data should be explained. Check field values, units, grades, names/IDs, total-versus-stint rows and sample columns. This cohort is a format/access check, **not the final acquisition population**.
3. Check the actual permitted transfer method: exposed download/export; otherwise table copy with headers and pagination, or an allowed visible read-only capture. Confirm all rows can be retained without hidden state, reverse-engineered endpoints or paywall bypass. An export button elsewhere is not evidence this table exports.
4. Expand immediately to full-league P1 batches by family/season. Clear star/team/default-minute filters and include low-minute players where exposed. Use a pagination manifest so a first page cannot be mistaken for full coverage. Preserve each batch before moving on. Prioritize completed2025–26 across distinct core channels, then2024–25, rather than every field for12 names.
5. Close missing families and historical gaps, then P2/P3 if useful. Access limitations reduce the promised scope; they do not justify repeatedly retrying a failed query or silently calling partial tables complete.

Illustrative one-month use: first session establishes feasibility and begins league-wide capture; next focused sessions complete both core seasons; subsequent sessions add third-year context, reconcile IDs/samples and review coverage. Finish local preservation/QA before access expires. This is a work order, not an automation, a commitment to wait a month, or authorization to acquire paid data now.

### Export alternatives and fallbacks

* **Exposed CSV/XLSX/download:** preserve original bytes, filters and source/version; normalize a copy. Confirm whether export includes all filtered rows or only the displayed page.
* **Permitted table copy:** retain headers, all pages and displayed total; copy small family batches for the whole league. Save exact values/representation, not screenshots alone when machine-readable copy exists. Review a few cells against the source and distinguish missing, blank and zero.
* **Permitted visible read-only table capture:** same provenance/pagination requirements; acquire only what access exposes. No hidden JSON, authentication workarounds, unpublished endpoints or scripted rate-limit retries. If support for league-wide retention is unclear, resolve that narrowly rather than assume it.
* **No practical full-league transfer:** capture the broadest permitted high-value family coverage first, record limitations and ask for an exposed export option if the user wants to contact the provider. Do not spend the month manually transcribing114 metrics for a few stars and label it transformative league coverage.
* **Access gap or no purchase:** use existing official/ESPN box evidence, retained skill inputs, targeted public reports and trusted scouting to build broad priors with uncertainty. Public NBA dashboards were unavailable in prior bounded requests; do not launch another request campaign. BBI is additive evidence, not a condition for all calibration work.

## 4. Local preservation and provenance

The [preservation schema](BBI_PRESERVATION_SCHEMA_2026_11_11.json) specifies planned raw/metadata/normalized/coverage/scouting folders **inside this research folder**, with no production importer. No empty paid-data folders were created as if acquisition had begun.

Each raw batch needs a unique ID, source URL, provider, retrieved UTC, provider as-of or unknown, raw and normalized season label, competition type, selected metrics, value/grade/percentile mode, all filters/default minimum minutes, displayed/captured counts, pagination, capture method and SHA-256. Retain original raw names, team labels, units and text. Store normalized long-form records keyed by player/season/type/metric, pointing back to the exact batch/row/cell.

Keep provider IDs when exposed. If absent, preserve that absence and build an explicit NBA/ESPN/canonical crosswalk using name plus age/team/season context; review ambiguity, not just stripped-name equality. A canonical team-prefixed ID is identity, not proof of historical team. Preserve team stints and totals separately; do not add a season total to its component stints. Record missing reasons such as not yet NBA, unavailable metric, filtered, unknown or no eligible attempts.

Separate observation/rate, stabilized estimate, provider model, contextual label and forecast in every metric's dictionary. “Values” can still mean a modeled score. Preserve percent versus percentage-point encoding, per75/per100 denominators and sign direction; do not infer standardized units from a number near zero. Definitions and versions can differ across years. Never normalize percentages by100 without checking the displayed convention.

QA is documentary/data-integrity work: row counts, duplicates, missingness, units, joins and source-cell spot checks. This plan calls for no tests/game simulations, backend reconstruction, production import or formula change.

## 5. Trusted scouting as usable evidence

Retained podcasts are substantive scouting evidence, not merely unverified filler until a tracking metric appears. An explicit, concrete assessment can support a directional correction or provisional range with peers and counterevidence. It does not need an impossible isolated causal measurement before it is useful.

For each claim preserve source/publication date, timestamp interval and supported speaker identity (otherwise unidentified/local turns). Record the **explicit assessment** separately from a **reasonable implication**, with reasoning. Keep disagreements, counterexamples, role/health context and forecasts. Numerical magnitudes are transparent calibration judgments on the chosen game scale, not measurements falsely attributed to a podcast or a provider.

| Retained example | Explicit assessment | Reasonable implication and calibration use | Limits / counterevidence |
|---|---|---|---|
| Castle, Aug5 PG00:18:37–00:22:05 | Strong physical POA defense; weaker secondary rim/help/disruption. | Support stronger containment than help/rim relative to same-scale guard peers, even if exact screen/help tracking is missing. | Fouls, Wembanyama/team support and small matchup samples; does not justify every defensive tool improving. |
| White, Aug14 SG01:34–01:44 | Anticipation/positioning, guard help blocks and defensive work are praised. | Support a valuable navigation/help profile; guard blocks do not imply center anchoring. | Keep current shooting/offense concerns separate. Exact navigation/help range is a judgment, not an inferred number from rank. |
| Barnes, Aug28 PF01:10:00–01:17:38 | Guards/wings, hands, help/rim versatility. | Support broad defensive suitability rather than a single position label; use anchor/wing peers to calibrate a range. | Full-time anchor equivalence is not established; scoring/three-point ceiling concerns remain separate. |
| Harper, Aug5 PG00:29:26–00:39:09 | Size, pace, paint finishing/decisions are praised; larger role and superstar ceiling forecast. | Present finishing/creation can be supported now; passing growth and future usage stay forecast unless demonstrated. | Do not turn predictions into present skill or potential-mechanic changes. |

Use the existing extractions and [cross-video claim index](CROSS_VIDEO_CLAIM_INDEX.md), not a wholesale re-extraction. Repeated speakers/underlying stats are not independent corroboration. Caption ambiguity can hold a narrow claim without discarding a clear surrounding assessment. Expert disagreement should widen/qualify a range or define a contrast to inspect, not force artificial consensus.

BBI may corroborate, challenge or contextualize scouting. It does not automatically overrule it. For example, a low-event helper may still make excellent positional decisions, and low usage can hide passing talent. Where tracking is missing, use an explicit scouting-derived range and confidence; where source and scouting conflict, preserve both and investigate the particular channel rather than alter unrelated ratings.

## 6. Measurable success and stopping rules

Success is useful coverage and distinct channels, not downloaded-column volume:

* **Population:** goal≥95% of eligible canonical NBA veterans joined for each completed core season, with100% of unmatched/missing cases reason-coded. This is a proposed operational target, not an access promise. Also report every provider row and all low-minute/rookie/free-agent/traded-player strata. Players with no prior NBA season belong in a separate prospect lane, not the missing-veteran denominator.
* **Channels:** attempt all13 P1 groups league-wide. Publish per-field and per-family coverage, separating observed inputs, provider models, sample availability and unknown units. A total composite alone does not count as several independent subchannels. Start with complete core-family coverage before adding optional duplicates.
* **Reliability:** retain opportunity/sample context where exposed, historical seasons, stabilization flags and missing reasons. A missing count is a visible gap, not a silently verified sample. Report descriptive≥500-minute and<500-minute strata without excluding the latter from acquisition or imposing a talent floor.
* **Reproducibility:** every normalized value links to raw capture/filter/season/representation and hash; pilot and a stratified source-cell review reconcile. No silent totals/stints duplication or percent/grade mixing.
* **Practical impact:** backend can replace repeated block/height/impact/role proxies with better distinct evidence across broad player populations and calibrate source/scouting ranges. Capture does not itself prove a new rating system is accurate or approve an import.

Stop buying/collecting when the useful families and history are locally preserved with honest gaps; do not renew merely to chase redundant impact charts. A subscription cannot establish causal player skill independent of teammates, exact cognitive/physical tools, true effort/motivation/cardio, injury prognosis, future potential or every playoff matchup. Nor does it guarantee that all role-lab counterfactuals are observed or that all metrics are independent. Those limits permit useful broad calibration; they do not require hand-reviewing every player forever.

## 7. Real unresolved human steps/questions

No answer is needed to continue the backend's current definitions/reconstruction work. Before any paid acquisition:

1. **Human choice:** authorize/activate one month if desired; this plan does not buy or sign in. No credentials need be shared in chat.
2. **If not answered by the exposed account UI, ask the provider:** “Does the $5 package expose the full NBA player pool for completed2025–26 and2024–25 in Player Skills/Leaderboards, including the listed skill/context families, and which historical/event sample fields are missing?”
3. **If transfer remains unclear:** “Which exposed download or permitted table-copy method retains all filtered player rows and raw values, with IDs/season/team/minutes and any event denominators? Does it include all pages or only the displayed page?”

These are the actual access/coverage questions. No provider message is sent. There is no need to decide114 game ratings, every player's role, projected growth or future commercial release policy to carry out this acquisition plan.
