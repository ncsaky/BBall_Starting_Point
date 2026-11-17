# First bounded NerdSesh extraction — for method review

## Scope and provenance

This checkpoint retains the original selected-passage extracts from two accessible English auto-caption tracks: [the June 12, 2026 draft big board](https://youtu.be/xZMVSPmcQKE?si=WVlsAYb_YicOVmuH) and [the October 7, 2026 NBA team rankings](https://youtu.be/J6STkjbVuUg?si=qgUBq12e0nHk7pBj). The original entries below remain selected passages, not full-episode reviews. A later full ranked-prospect-discussion extraction of the retained draft-board captions is in `DRAFT_BIG_BOARD_FULL_EXTRACTION.md`; that review also does not cover uncaptioned audiovisual content. The two VTT files used here are in `captions/`; one other source VTT was retrieved during inventory, then discarded without analysis. The retained files were retrieved from YouTube with `yt-dlp` 2026.03.17; no video was downloaded or listened to. All statements below are paraphrases of captions, not independently verified basketball facts.

YouTube's auto captions provide timestamps and occasional `>>` turn markers, but not speaker diarization. The videos introduce Carson and Logan; the team-ranking episode also introduces guest Tyler / Hoop Venue. The captions do not reliably identify which named person makes each later claim. Rows therefore use “unidentified speaker”; where a caption turn marker helps distinguish adjacent statements, “next local turn” means only the next marked turn in that excerpt. It is not a persistent identity, and no mapping to a named person or speaker across the episode is claimed. Captions contain recognition errors and overlapping rolling text; timestamps should be used to review the source before any later synthesis. No long transcript passages are reproduced here.

## Video 1: 2026 NBA Draft Big Board

**Source date and scope:** Published 2026-06-12; evaluates the 2026 draft prospect class. This is pre-draft projection, not an NBA-performance rating.

| Time | Attribution | Paraphrased claim and reason | Evidence type / uncertainty |
|---|---|---|---|
| 02:23:26–02:23:46 | Unidentified speaker; a local `>>` turn marker follows | One speaker sees AJ Dybantsa and Darryn Peterson as having more refinement/upside, while Cameron Boozer may be the more immediately impactful, versatile, well-rounded player. | Future ceiling versus early contribution; qualitative opinion. No identity is assigned. |
| 02:23:50–02:24:35 | Unidentified speaker (next local turn) | Says they moved Boozer to #2. The stated reason is greater confidence in his immediate impact and concern that Peterson's freshman season raised questions about health, lingering hamstring problems, expected playmaking and two-point scoring. The speaker says Peterson may be closer to his high-school version if the injuries explain the season. | Explicit personal ranking (#2) and a mix of observed freshman-season results and projection. The injury explanation is presented as a possibility, not established causation. |
| 02:35:25–02:36:21 | Unidentified speaker; local turn changes are marked in the captions | One speaker acknowledges that Peterson's inconsistent season and reliance on high-school evidence make the evaluation uncomfortable, but keeps him at #2 on the strength of projected on-ball/off-ball scoring and creation, including an MVP-level ceiling. The next speaker says the reservations are real but slight. | Explicit competing #2 ranking. Ceiling is a high-variance forecast; the stated evidence includes both high-school projection and a disappointing freshman season. No identity is tracked across this episode. |
| 02:36:36–02:37:08 | Unidentified speaker (local turn) | The discussion frames Peterson, Boozer and AJ as unusually strong prospects: likely top-seven picks and potential #1 overall prospects in many classes, while noting Peterson's freshman season was disappointing relative to expectation and Boozer met expectations. | Broad class-relative judgment, not a trait measurement or a stable league rating. |

**Disagreement recorded:** Boozer versus Peterson at #2. The disagreement is not simply “better player”: the speakers weight immediate impact/floor differently from star upside and lead-guard scoring creation. They agree the top group is unusually strong. The captions also show explicit caution about Peterson's lingering hamstring issues and uncertainty about whether his freshman performance reflects health; they do not establish a long-term injury prognosis.

**Current ability versus ceiling:** References to freshman playmaking, two-point scoring and health concern current/recent performance. “Perfect modern guard,” MVP-level talent, scoring ceiling and high-school translation are projections. Keep these as separate evidence fields.

## Video 2: Top 10 NBA Teams

**Source date and scope:** Published 2026-10-07; preseason team ranking discussion for the 2026–27 season. The ranking is a team-level forecast, not an individual player ranking.

| Time | Attribution | Paraphrased claim and reason | Evidence type / uncertainty |
|---|---|---|---|
| 01:40:30–01:41:18 | Unidentified speaker (local turn) | In the Denver discussion, the speaker argues that Aaron Gordon is essential: a play-finisher and shooter who adds transition pressure, mismatch attacks, offensive rebounds, tertiary handling/playmaking and versatile defense. They object to Denver being as low as #14 on the referenced board. | Player-role and trait claims used to support a team ranking. Rank attribution belongs to the speaker's board; it is not a consensus rank. The transcript does not provide a numerical player grade. |
| 01:41:20–01:42:05 | Unidentified speaker; local turn change marked by `>>` | Another speaker says Denver is unlikely to win the title and compares its odds with other teams in that tier. The exchange weighs Denver's complementary roster and Gordon's value against stronger opponents, including San Antonio. | Team-context judgment with disagreement about team ceiling. Not evidence that Gordon alone determines the ranking. No identity is tracked across the episode. |
| 01:42:02–01:42:10 | Unidentified speaker turns | The conversation invokes Dylan Harper in the question of whether San Antonio can stop Denver and vice versa. | Matchup speculation, not an isolated player-skill evaluation. No supported numerical inference. |

**Disagreement recorded:** One speaker considers Denver's #14 placement too low because Gordon makes the core function better; another is skeptical of its championship odds in a difficult tier. This shows why role value and team prediction must be recorded separately.

**Caption-to-video provenance check (October 7 episode):** The retained file is `J6STkjbVuUg.en.vtt`; its video ID matches the supplied URL, and `yt-dlp` metadata records the title “Ranking The Top 10 NBA Teams: Will Spurs, Thunder or Knicks win it all? 76ers overrated?” and publication date 2026-10-07. The opening caption introduces the episode as a top-10 team ranking with a guest. Captions from 01:39–01:42 remain in a continuous Denver/Nuggets discussion (depth, defense, Murray, Gordon, Jokic, and the San Antonio matchup). The #14 remark is therefore from this correctly matched episode, not evidence of a caption file attached to a different video. The Oct 2 episode `ZaA4usLpBWI` is explicitly titled a teams #20–11 ranking; its full retained captions and final recap include Denver at #14 on one host's board and #9 on the other. The Oct 7 Denver discussion refers to #14 and to “last episode.” This supports the rank as a legitimate cross-episode reference, not a caption-source mismatch. The exact speaker/list identity in the Oct 7 passage remains unresolved; do not assign persistent identities across episodes or treat #14 as a consensus ranking.

**Current ability versus ceiling:** The Gordon discussion is about his present complementary role and playoff contribution. Denver's title probability is a team forecast. The Harper reference is matchup speculation. No injury issue is raised in these selected segments.

## Tentative evidence-to-trait mapping for review

This is a semantic mapping proposal only; it does not propose numeric changes.

| Caption claim category | Existing trait semantics it may inform | Confidence / guardrail |
|---|---|---|
| Prospect scoring creation and lead-guard ceiling | `handle_pressure`, `rim_pressure`, `shot_versatility`; `passing_reads` only when playmaking is explicitly supported | Low-to-medium from opinion alone. Separate present skill from projection and corroborate with film/stat evidence before any rating proposal. |
| Injury-limited performance / lingering hamstring concern | Health, availability and confidence metadata; not a permanent skill trait by itself | High confidence that the speakers raised health as a concern; low confidence about diagnosis, chronicity or cause. Do not turn injury discussion into a healthy-ability downgrade. |
| Boozer's described versatility and immediate impact | Role/portability and the named skills only where explicitly evidenced | Low-to-medium. Broad praise is not itself a rating; find concrete evidence before mapping to individual traits. |
| Gordon's shooting, finishing, transition play, offensive rebounding and secondary handling | Candidate concepts: `shooting_range`/`release_speed`, `rim_pressure`, `offensive_rebounding`, `handle_pressure`/`passing_reads` | Medium as a list of described roles, low as a numeric estimate. The speakers make a team-context argument; corroborate each trait independently. |
| Gordon's versatile defense | Defensive-role traits such as `defensive_effort`, `scheme_iq`, `foot_speed_lateral_agility` only if backed by specific evidence | Low from this broad caption claim. Do not infer every defensive subskill from “versatile defender.” |

Podcast rank positions must remain source claims, not be translated directly into OVR. Team placement, player role, current ability, ceiling, availability and uncertainty should remain distinct fields. Each substantive claim in a later broad pass should have its own source timestamp and corroboration state.

## Repository calibration context inspected read-only

- `src/nba_gm_data/schema.py` declares `CANONICAL_SEASON = 2026-27` and `CANONICAL_START_DATE = 2026-07-28`.
- `data/canonical/universe_2026_27_offseason.json` identifies the active baseline as `starting_data_version: 2026-10-27-interior-offense-v9`.
- The baseline registry shows prior imported-skill v7 and imported-tail v6 layers. The canonical trait-rating data and `data/overrides/league_trait_ratings_2026_06_20.csv` use values on a 0–100 scale; OVR/OFF/DEF/REB are composites, not podcast ranks.
- A separate `universe_2025_26_preseason` starts 2025-10-01 and points to rating source `src_league_trait_ratings_2026_06_20`. The repository therefore contains multiple plausible season snapshots.

**User's October-start policy (updated 2026-11-02):** The intended game start is 2026-10-20, just before the regular season. The user considers the offseason podcast evaluations broadly current at that start unless an intervening injury, trade, signing or other material event changes the context. Keep every claim dated and check for such events. The retained canonical ratings/roster source still says 2026-07-28; this is a data-alignment gap, not an open choice about the intended game start. Preserve that provenance until a separately authorized implementation updates it.

## Method status after review corrections

The extraction is a selected-passage sample, not an episode-wide review. Attribution is limited to “unidentified speaker” and excerpt-local turn order when captions show a turn marker; those labels do not imply persistent speaker tracking. The Denver #14 provenance check is documented above, with the exact board referent left unresolved. The October start/evidence policy is recorded above; the July 28 canonical source mismatch remains. Named-player and contract dossiers are in `NAMED_PLAYER_DOSSIERS.md`; remaining source coverage and gaps are in `COVERAGE_AND_GAPS.md`. No game code, production ratings, contracts, saves, or backlog files were changed.
