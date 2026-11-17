# League draft-asset edge-case audit

Scope: all 30 teams in the 2026-10-13 starting-data snapshot, 420 underlying future picks, 17 protection obligations and 68 swap/allocation comparisons. This is a source/data audit, not a simulated draft or trade test. Existing save ownership was not changed.

All obligation subject and fallback IDs exist in the canonical pick table. Every current protected obligation has one fallback. The source records 50 normalization notes; these include ordinary protection substitutions as well as complex allocations.

## Remaining gaps

| Case | Concrete example | Current handling / remaining gap |
|---|---|---|
| Protected nested inputs | 2027 OKC/DEN/LAC/TOR; 2029 MIN/UTA/CLE/CHA/PHX | Protections resolve before comparisons. The nested graphic only supports unprotected single-slot chains; these need a visible conditional branch rather than a misleading unconditional tree. |
| Ranked pools: several outcomes | 2029 HOU/PHX/DAL: HOU receives two most favourable; BKN receives least | Labels support quantities. Updated: each trade asset has a guaranteed rank and uses expected ranked-outcome valuation; trading it preserves that rank. See ranked_pick_valuation.md. |
| Rank is not original pick identity | 2027 R2 HOU/IND/MIA/OKC: PHI/NOP/NYK/MIA receive ranked slots | Icon ownership represents entitlements, but a physical original-team icon can imply a fixed identity. A ranked-slot treatment should distinguish outcome rank from eventual original pick. |
| Claims on the remainder | 2031 R2 MIA/IND/MEM; 2032 R2 MEM/PHI/UTA | Pool lookups follow current owners in general; explicit remainder references were added for downstream one-slot comparisons attached to recognized nested chains. They are not yet a universal output-reference model for every allocation. |
| Noncontiguous allocation | 2029 POR/BOS/MIL | Source median-of-three clause is deliberately approximated: WAS receives worse of BOS/MIL; POR keeps own plus better BOS/MIL. Exact middle plus both extremes needs a distinct ranked-slot representation. |
| Protection rollover and round conversion | 2028 PHI R1; 2030 GSW R1 | Replaced by a single explicit same-round fallback. The current engine requires matching rounds and does not represent changing protection ranges over several years or first-to-second conversion. |
| Conveyance-dependent recipient | 2027 LAL R2; 2029 DEN and MIN R2 | Alternative recipients tied to a different pick conveying are removed by starting-data normalization. No general cross-year/cross-round decision-tree graphic exists. |
| Narrow selection carve-out | 2027 NOP/POR R2; 2031 HOU/ATL R2 | Conditional picks 56–60 transfers were removed. Would need an explicit numeric condition and named recipient for every branch. |
| Forfeited picks | IND 2029 R1; LAC 2030–2033 R1 | Nontradeable status exists. They need an unmistakable forfeited/unavailable visual if shown as context; a protection asterisk is not appropriate. |
| Unspecified year | DET second to LAC; NOP second/swap to MEM | Omitted rather than inventing an asset. Cannot become selectable until year/round/underlying assets are identifiable. |

## Recommended sequence

1. Give each ranked or remainder outcome one explicit entitlement ID with rank, quantity, dependencies and owner; retain physical picks as resolution leaves.
2. Value the entitlement outcome directly, without adding child rights or counting every possible leaf as owned.
3. Add visual formats for conditional branches, remainder outputs and forfeitures.
4. Extend trade-builder creation only after these formats and ownership rules are shared with trade finder and draft resolution.

## Team coverage

| Team | Original future picks | Currently assigned picks in snapshot | Related obligations |
|---|---:|---:|---:|
| ATL | 14 | 11 | 6 |
| BKN | 14 | 32 | 7 |
| BOS | 14 | 14 | 10 |
| CHA | 14 | 30 | 11 |
| CHI | 14 | 19 | 7 |
| CLE | 14 | 5 | 9 |
| DAL | 14 | 7 | 8 |
| DEN | 14 | 9 | 5 |
| DET | 14 | 17 | 4 |
| GSW | 14 | 8 | 5 |
| HOU | 14 | 10 | 11 |
| IND | 14 | 14 | 13 |
| LAC | 14 | 15 | 6 |
| LAL | 14 | 6 | 5 |
| MEM | 14 | 22 | 12 |
| MIA | 14 | 5 | 12 |
| MIL | 14 | 11 | 9 |
| MIN | 14 | 4 | 11 |
| NOP | 14 | 12 | 10 |
| NYK | 14 | 16 | 8 |
| OKC | 14 | 28 | 16 |
| ORL | 14 | 12 | 5 |
| PHI | 14 | 16 | 13 |
| PHX | 14 | 7 | 18 |
| POR | 14 | 17 | 9 |
| SAC | 14 | 9 | 1 |
| SAS | 14 | 19 | 5 |
| TOR | 14 | 8 | 2 |
| UTA | 14 | 20 | 14 |
| WAS | 14 | 17 | 15 |
