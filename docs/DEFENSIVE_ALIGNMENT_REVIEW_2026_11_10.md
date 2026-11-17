# Defensive alignment review — November 10, 2026

Historical pre-implementation evidence. The subsequent user-approved [implemented correction](DEFENSIVE_ALIGNMENT_CORRECTION_2026_11_10.md) supersedes this report's production status and legacy-version recommendation: development careers are disposable, so no compatibility framework was added. The experiment results below remain the recorded before/control evidence.

**Status: working isolated prototypes and downstream checks; no production defensive formula is installed.** The investigation confirms genuine high-end rim saturation and a mismatch between headline DEF and gameplay concepts. Neither tested replacement is calibrated well enough to ship. The shared-card alternative also changes established careers despite their archived traits. Production remains the five-player v11 calibration, including its earlier eleven trait targets. No additional player edits, GUI changes, market-policy changes, development changes or dependencies were introduced.

Evidence is retained in `output/defensive-alignment-2026-11-10/`. Its read-only `summarize.py` consolidates the existing experiments into `review-summary.json`, asserting the key comparisons. All **99 recorded backend/canonical/archive/override files** still match their pre-experiment hashes. The later mistaken settlement continuation did not implement a defensive correction; its settlement measurements are unrelated to this review.

## What is wrong, and what is merely a different definition

The inspected production paths are `traits.py:build_traits_for_player`, `save.py:_uncached_player_attribute_summary`, `sim.py:player_feature_vector`, `defensive_anchor_score`, `defensive_feature_summary_from_values`, and `spatial.py:player_spatial_profile`. Trade valuation, roster retention and fresh contract contexts were exercised separately.

1. **Input correlation:** inferred effort uses deflections, steal rate and CraftedDPM; agility and navigation reuse nearly the same deflection/steal/versatility/impact inputs with different weights and role adjustments. Scheme IQ also uses CraftedDPM, alongside IQ/passing proxies. Rim inference is primarily block rate and height, with smaller impact support. Subsequent subjective calibration, preservation and scouting overlays can replace those inferred values. These are correlated proxies with uncertainty, not independent measurements of containment, navigation and help. The shared sources alone do not establish that gameplay counts a skill three times.
2. **Card definition:** engine DEF equally averages raw effort, scheme IQ, navigation and rim. Agility contributes through athleticism instead. DEF enters engine OVR with weight .22 before the enabled role-skill blend; displayed values then use the existing nonlinear display transform. A high displayed DEF therefore is not a direct reading of the gameplay rim channel, and changing DEF can change OVR and retention.
3. **Real scalar saturation:** gameplay rim is `clamp(r + .18 * max(0, r - 68)^1.18, 1, 99)`. Gobert, Kessler and Allen have different raw rim values but all become **99** on this channel. This erases a real distinction.
4. **Spatial defense remains distinct:** restricted-area spatial contests still use raw rim, size, scheme and effort. Baseline restricted values are Gobert **92.63**, Kessler **92.00**, Allen **88.19**. It would be incorrect to conclude that all three are identical throughout gameplay, or to replace their spatial behavior with one universal DEF number.
5. **The existing gameplay rollup is not a card-quality scale.** Activity is `.42*effort + .36*agility + .22*navigation`; three inputs of 70 produce 70. Weak-link targeting is `clamp(50 + .55*max(0,48-activity)^1.15,1,99)`. Thus integrity, `clamp(100-weak_link,1,99)`, is **50 for every activity of at least 48**. It represents absence of a targeting penalty, not mediocre defensive skill. Player anchor is `.45*rim + .30*activity + .15*impact + .10*integrity`. The tested player rollup averages activity, rim, anchor and integrity, yielding effective weights `.325 activity + .3625 rim + .0375 impact + .275 integrity`. Copying this into cards mixes a neutral targeting term and general impact into a purported defensive skill scale. Team anchor aggregation also differs from this single-player calculation.

## Executed alternatives

`prototype.py` temporarily replaces functions inside a context manager and restores them on exit. It is not imported by production or the preview. All alternatives leave raw traits and spatial formulas unchanged; the channel-only alternatives replace only the rounded gameplay rim scalar.

| Mode | Definition for raw rim r, bounded to 1–100 | Limitation |
|---|---|---|
| Legacy | Existing clipped nonlinear bonus above 68 | Flattens the elite tail at 99 |
| Linear | `1 + (r-1)*98/99` | Strictly increasing 1–99, but changes the entire scale, including low values |
| Smooth | `r - (max(0,r-68)/32)^2` | Strictly increasing 1–99 and smooth at 68; removes the old bonus across the whole upper range, not just the clipped tail |
| Shared card | Smooth rim plus existing gameplay player rollup substituted for engine DEF | Demonstrates the definition/scale problem; substantial uncalibrated card, OVR and retention changes |

The curves are mathematical controls, not independently supported basketball calibrations. Monotonicity and smoothness do not establish correct strength or positional balance.

Sample coverage includes guards, wings/helpers and centers. Card columns below are **actual v11 `player_card` actions**, rather than private summary estimates; game rim columns use the common fixed canonical input.

| Player / coverage | Raw rim | Legacy game rim | Smooth game rim | Actual card DEF legacy → shared |
|---|---:|---:|---:|---:|
| Derrick White / guard help | 58.00 | 58.000 | 58.000 | 92.5 → 83.9 |
| Stephon Castle / guard | 76.96 | 79.353 | 76.882 | 92.9 → 87.8 |
| Stephen Curry / guard control | 36.09 | 36.090 | 36.090 | 83.8 → 72.0 |
| Luka Dončić / guard control | 42.00 | 42.000 | 42.000 | 67.5 → 61.5 |
| Kawhi Leonard / wing | 74.25 | 75.815 | 74.212 | 97.5 → 90.8 |
| Scottie Barnes / helper | 90.32 | 97.346 | 89.833 | 96.0 → 92.7 |
| Cooper Flagg / helper | 88.41 | 94.732 | 88.003 | 95.4 → 91.6 |
| Rudy Gobert / rim anchor | 99.01 | 99.000 | 98.071 | 97.5 → 93.5 |
| Walker Kessler / rim anchor | 97.43 | 99.000 | 96.584 | 95.5 → 91.6 |
| Jarrett Allen / rim anchor | 96.82 | 99.000 | 96.009 | 96.0 → 91.8 |
| Jalen Duren / center | 90.00 | 96.908 | 89.527 | 88.8 → 88.4 |

Smooth alone leaves card DEF unchanged, so it does not resolve misleading headline interpretation. Shared-card actual v11 OVR moves Kawhi **94.7 → 92.2**, White **87.1 → 84.9**, Gobert **88.4 → 86.2**, Duren **85.1 → 85.0**. These changes are not evidence that those new rankings are correct.

## Gameplay and roster consequences

There are **96 bounded games**: three matchups × eight seeds (17/29/41/53/67/79/83/97) × four modes. The healthy input rosters and source-minute projections are held fixed; coach matchup minute nudges are disabled only inside this diagnostic harness. No production rotations are changed. This isolates feature effects but is not a normal career or rotation-policy test.

| Matchup | Legacy mean points | Linear mean points | Smooth / shared-card mean points |
|---|---:|---:|---:|
| TOR–HOU | 107.625–115.625 | 109.875–116.375 | 109.625–116.250 |
| DET–BOS | 106.625–110.750 | 107.125–111.750 | 107.125–111.750 |
| MIN–GSW | 111.875–113.125 | 112.250–113.375 | 112.125–113.375 |

Smooth and shared-card have **identical complete game records** in this fixed-roster harness: cards do not directly alter these game inputs. This does not prove identical dynamic career outcomes, because roster forecasts/retention can consume changed OVR. Baseline → smooth team blocks include TOR **5.50 → 5.50**, HOU **5.75 → 6.00**, BOS **5.375 → 4.75**; MIN stays **4.625**. Rebounds also shift slightly (TOR **38.625 → 38.125**, MIN **43.50 → 43.75**). All players' upper rim channels change together; these small samples and shared RNG draw paths cannot establish an individual causal ranking or calibrated scoring distribution. Boxes include rim attempts but not rim makes; two-point percentage must not be described as paint accuracy.

Private fixed-context retention scores under shared-card move White **84.9 → 82.1**, Kawhi **90.0 → 86.5**, Gobert **83.0 → 80.2**, Duren **81.26625 → 81.06625**. Actual cut decisions were not simulated. The changes demonstrate an economic/roster consequence of card formulas, not merely a cosmetic display adjustment.

## Trade, free agency, extensions and negotiation

Fresh transaction valuations and contract profiles were rebuilt for every mode; stale stored asks are not used as evidence of economic neutrality. Trade prices consume gameplay features and contract/age/health/scarcity inputs, while forecasts and roles can consume OVR.

**Existing thresholds matter.** Castle's game rim moves **79.353 → 76.882**, crossing the existing 78 rim-scarcity threshold and removing six scarcity points. His final stored player value remains capped at 99 in this source, which does not mean the lost component is irrelevant. Kawhi's current v11 **75.815** is already below 78; this prototype does not cause a new scarcity-category loss for him. Baseline → smooth player values include Kawhi **78.40 → 78.28**, Duren **80.21 → 79.33**, Gobert **71.59 → 71.48**. White stays **82.30**.

The controlled trade fixture gives participants identical known $25M contracts and cheap surrounding rosters, retains ownership and explicit core commitments, and evaluates Kawhi/Duren/Gobert against Curry or Pat Spencer. All **18 reports** (six pairs × three modes) are financially legal. All six bilateral participant decision pairs remain unchanged across modes, and none is approved by both sides. Kawhi-for-Curry remains rejected by TOR despite positive net value because of its core commitment. Kawhi-for-Spencer and Gobert-for-Spencer retain premium-return rejection; Curry's side rejects Duren/Gobert returns under its premium safeguard. This verifies concrete guards in this sample, not all possible trade or pick-investment thresholds. No trade was settled.

The first exploratory financial fixture removed selected contracts and produced **11 manual-review results in every mode**. Its asks/scores are retained in the mode files, but it cannot establish legal signing acceptance. Original-contract extension checks also correctly stop: nine players are outside their extension window and two have original terms shorter than three years, in every mode.

`financial_fixed.py` addresses that gap with **known, guaranteed, expiring $1.9M contracts**, original ownership, an HOU destination roster of 14, and the same facts/cap state across three modes. These are controlled projected-FA/eligible-extension counterfactuals, not claims about the players' real contracts. All **33 opening FA offers are legal**. Public negotiation functions run up to three rounds, including money, years/security, role promises, fit, winning context and player/team score gates; no signing/extension is applied to a save.

| Player | FA ask $M, legacy → smooth | Opening bid $M | Negotiation consequence |
|---|---:|---:|---|
| Castle | 29.686 → 28.680 | 24.638 → 24.251 | Four-year featured-role FA accepts in round 1; extension accepted AAV 23.960 → 23.148 |
| Duren | 27.062 → 26.831 | 20.565 → 20.389 | Opening player rejection in both; four-year FA accepts in round 2 at 22.877 → 22.682; extension accepts at 21.306 → 21.124 |
| Kawhi | 45.731 → 45.601 | 37.527 → 37.420 | Two-year featured-role FA accepts; extension walks away in both |
| Gobert | 22.887 → 22.867 | 17.545 → 17.530 | Two-year featured-role FA accepts; extension walks away in both |
| Curry | 31.857 → 33.840 | 25.421 → 27.003 | One-year FA/extension accept at changed prices despite his unchanged rim channel |
| Luka | 43.790 → 43.790 | 33.127 → 33.127 | Opening accept → player-reject; later four-year agreement moves 33.127 in round 1 → 36.163 in round 2 |

Luka's first player score crosses **68.0069 → 67.9892**, with the same team score **81.2200**. His reasons retain below-minimum salary, clear role, fit and winning context. This small threshold movement has a concrete negotiation-price effect. Curry's rise is a nonlocal contract-comparison/cohort effect, not a direct defensive upgrade; a league-wide formula can change another player's terms without changing that player's rim channel. All final FA and extension accept/walk-away outcomes remain the same in this eleven-player controlled sample, but accepted money and negotiation paths do not. Accepted terms above are fully guaranteed. Smooth and shared-card asks/bids/accepted terms coincide in this fixture; that does not establish global economic equivalence.

## Legacy compatibility, tests and runtime limits

Actual `player_card` dispatches were run on disposable restored v11 and archived v10 careers, with normal save revision invalidation between modes. The first exploratory card read reused an existing read context and is retained under `exploratory-stale-read-cache/`, excluded from results. Corrected actions use fresh revisions; the runner also asserts that leaving the prototype restores Kawhi's original card.

**Archived inputs do not freeze global Python formulas.** The shared-card prototype changes v10 Kawhi DEF **98.2 → 94.5**, OVR **95.0 → 92.8**; v10 White DEF **92.5 → 83.9**, OVR **87.0 → 84.8**. Existing `baseline_for_save` preserves source versions, and talent/offense have model gates, but the inspected defense paths have no corresponding formula-version gate. A global substitution would violate existing-career behavior preservation.

The forced shared-card harness matches Oct 30–Nov 1 bulk/daily/midpoint export-restore runs: identical meaningful-state digest and all **16 ordered events**. **The monkeypatch remains active across reload. This proves partition determinism only; it does not prove persisted formula-version compatibility or an installed new model.**

All **six prototype tests pass**: monotonic/bounded alternatives and smooth join; old saturation versus distinct new tail; normalized activity weights; neutral integrity scale; unchanged raw/offensive features under the channel-only patch; function restoration. The recorded test log has one unclosed-input-file `ResourceWarning`; it is a harness warning, not a failed assertion. No broad production suite was rerun for unchanged production code.

With tracemalloc enabled, median 100 warm attribute calls are **6.68 ms legacy**, **6.64 ms smooth**, **8.54 ms shared-card**. Traced live/peak bytes are **9,504/11,568**, **9,496/11,560**, **13,800/20,768** respectively. All three private roots release before diagnostic GC. These are tiny warm-input measurements with prototype/patch overhead, not end-to-end latency or long-lived server RSS evidence. The four mode runner durations (47.90/45.79/36.69/38.01 seconds) include games, repeated market construction and warm-up differences; they are not a speed comparison. No additional simulation campaign is required to consolidate this review.

## Smallest justified next correction and the decision still needed

**Address the saturated rim response first with a narrowly scoped, versioned high-tail correction.** Preserve the current low/mid response and existing 78 scarcity classification while testing a monotone upper shoulder that distinguishes elite anchors. Neither executed whole-scale curve meets that narrower scope: linear changes low values; smooth removes bonuses well below the clipped tail. Selecting the shoulder/anchor magnitudes still requires basketball calibration; the evidence does not select a defensible replacement automatically.

Headline DEF needs an explicit skill meaning on the existing display scale. It should share authoritative raw components with gameplay while retaining the distinction between perimeter activity, help/rim effects and neutral weak-link targeting. **Do not install the current `defense_total` as card DEF, or lower individual traits solely to fix a headline.** The exact decision is to approve a new-career-only defensive model with calibrated high-tail rim anchors and a defined skill-scale DEF aggregation; no universal positional ordering or percentage reduction is established here.

A bounded integration would first persist a default-legacy defense formula version and propagate it through feature/card, valuation/contract/retention and read/forecast cache ownership. Existing and unversioned careers must retain old arithmetic. Then implement only the selected rim shoulder and separately calibrated card aggregation, retaining the old reference, and repeat the existing card/game/trade/legal-negotiation checks plus normal versioned daily/bulk/reload actions. Test scarcity boundaries, premium/core and pick-investment consequences on fresh contexts before release. This is a prerequisite and verification plan, not an implemented version framework or authorization to expand into role taxonomy/state redesign.

Research's `ratings-evidence-2026-10-29/NEXT_RATING_BATCH_DECISION_SHEET.md` queues six independent offensive subparts and holds Castle/Paolo defensive proposals for the shared correction. **None of that batch is implemented here.** The defensive problem remains open at this isolated-prototype milestone; the tested global replacements are withheld for specific scale and legacy-compatibility reasons.

## Reproduction and current preview

Consolidation only, without new simulations or changing evidence:

```sh
.venv/bin/python output/defensive-alignment-2026-11-10/summarize.py
PYTHONPATH=src:output/defensive-alignment-2026-11-10 \
  .venv/bin/python -m unittest discover \
  -s output/defensive-alignment-2026-11-10 -p test_prototype.py -v
```

The retained runners are `run.py`, `financial_fixed.py`, `trades.py`, `actions.py` and `memory.py`. To reproduce experiments, first copy them into a fresh output directory; change `memory.py`'s explicit output path, and give `actions.py` fresh career directories. Use `PYTHONPATH=src:scripts:NEW_DIRECTORY`, then run those files serially during a coordinated quiet window. They overwrite their local JSON evidence or require nonexistent directories; do not rerun them over the retained artifacts. `run.py` also requires the frozen v11 inputs; its recorded hashes make subsequent source/data drift explicit.

The current integrated preview is **http://127.0.0.1:8796/** (PID **84101**, HTTP 200 confirmed read-only). It runs v11 and prior production corrections, **not this prototype**. It was not restarted for this review; no save action was sent, and active previews/playable careers and shared frontend files were preserved. Stop at this milestone.
