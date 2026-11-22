#!/usr/bin/env python3
"""Build canonical inputs from local evidence; no simulation or network access.

Run from any directory with PYTHONPATH=src. The generated JSON is a validated
player_model input section. Re-running also refreshes the bounded evidence tables
between markers in the E2 report; hand-written schema/method notes are preserved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

from nba_gm_data.input_estimator import (
    DEFINITIONS, InputEstimator, METHOD_VERSION,
    UNIVERSE_PATH, canonical_json, coverage_counts, estimation_status,
    load_reference_cells, validation_comparison, source_join_audit, rotation_input_spread,
)

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '<!-- E2 generated evidence report -->'
END = '<!-- E2 end generated evidence report -->'
TECHNIQUE_INPUTS = tuple(iid for iid, definition in DEFINITIONS.items()
                         if definition["kind"] == "grade")


def estimate_startup_inputs(estimator: InputEstimator, universe: dict) -> dict:
    section = estimator.estimate_universe(universe)
    for player in universe["players"]:
        if player.get("draft_year") != 2026 or player.get("draft_status") != "drafted":
            continue
        career = estimator.careers.get(str(player.get("espn_player_id") or ""), {})
        if any(row.get("season") and row["season"] < "2026-27" and (row.get("games") or 0) > 0
               for row in career.get("seasons", [])):
            continue
        rookie_inputs = estimator.estimate_player_inputs(player, prospect=True).to_dict()["inputs"]
        inputs = section["players"][player["id"]]["inputs"]
        # Keep the original physical and tendency estimates before the evidence overlays.
        inputs.update({iid: rookie_inputs[iid] for iid in TECHNIQUE_INPUTS})
    return section


def report_tables(universe: dict, section: dict, comparison: dict, elapsed: float,
                  byte_count: int, estimator: InputEstimator) -> str:
    coverage=coverage_counts(section)
    audit=source_join_audit(universe,estimator)
    spread=rotation_input_spread(section,audit)
    names={p['id']:p['name'] for p in universe['players']}
    groups={
        'Physical tools (12)': [k for k in DEFINITIONS if k.startswith('P')],
        'Shooting (9)': [f'S{i:02d}' for i in range(1,10)],
        'Finishing and receiving (6)': [f'S{i:02d}' for i in range(10,16)],
        'Handling and attack recognition (5)': [f'S{i:02d}' for i in range(16,21)],
        'Post craft (3)': [f'S{i:02d}' for i in range(21,24)],
        'Foul craft, routes and screening (5)': [f'S{i:02d}' for i in range(24,29)],
        'Rebounding technique (4)': [f'S{i:02d}' for i in range(29,33)],
        'Defense technique and recognition (14)': [f'S{i:02d}' for i in range(33,47)],
        'Passing recognition (9)': [k for k in DEFINITIONS if k.endswith('.recognition')],
        'Passing execution (9)': [k for k in DEFINITIONS if k.endswith('.execution')],
        'Conditional tendencies (18)': [k for k in DEFINITIONS if k.startswith('T')],
    }
    total=Counter(estimation_status(r) for p in section['players'].values() for r in p['inputs'].values())
    nplayers=len(section['players'])
    matched_skills=sum(1 for p in universe['players'] if _name(p['name']) in estimator.skills)
    matched_stats=sum(1 for p in universe['players'] if _name(p['name']) in estimator.stats)
    matched_career=sum(1 for p in universe['players'] if str(p.get('espn_player_id') or '') in estimator.careers)
    grades=[r['value']['grade'] for p in section['players'].values() for r in p['inputs'].values() if 'grade' in r['value']]
    lines=[BEGIN,'','## Build and coverage','',
        f'- Method: `{METHOD_VERSION}`. Built **{nplayers} × 94 = {nplayers*94:,}** complete records.',
        f'- **{total["estimated"]:,} player-evidence estimates; {total["prior"]:,} explicit priors.**',
        f'- Local joins: {matched_skills} unique skill names, {matched_stats} unique later Crafted names, {matched_career} ESPN IDs. Sources are overlapping, never additive player counts.',
        f'- Build, validation, comparison without packet experts, serialization and write: **{elapsed:.3f} seconds**; canonical JSON {byte_count/1_000_000:.2f} MB.',
        f'- Skill-grade range {min(grades):.3f}–{max(grades):.3f}; exactly 100: {sum(v==100 for v in grades)}; at least 99.9: {sum(v>=99.9 for v in grades)}. No scale-max clipping.',
        '', '| Input family | Player-evidence estimates | Priors | Total |', '|---|---:|---:|---:|']
    for family,ids in groups.items():
        estimated=sum(coverage[i]['estimated'] for i in ids)
        priors=sum(coverage[i]['prior'] for i in ids)
        lines.append(f'| {family} | {estimated:,} | {priors:,} | {estimated+priors:,} |')
    lines.extend(['','## Per-input coverage and hand-reference comparison','',
        f'Newest estimated source cells from **{comparison["reference_players"]} players**, {comparison["reference_cells"]} cells; {comparison["comparable_cells"]} comparable numeric cells. One display-only physical descriptor has no aligned scale and is excluded from numeric agreement. Unknowns do not overwrite earlier estimates. Nov15 uses `proposed_source_input_section`; scenarios, operational profiles and completion suggestions are excluded.',
        '', 'The final estimate includes a 35% adjustment toward sourced expert technique judgments. **This comparison shares expert evidence with the reference; it is not independent validation.** The last two columns rerun the estimator with every packet-expert adjustment disabled, retaining the declared legacy/statistical prior context. No constants were fitted to either comparison. Expert agreement must not be read as accuracy against ground truth. Expert-adjusted bands deliberately retain source disagreement, so they contain the reused hand value by construction; the bands without packet adjustments do not have this guarantee. This is a comparison without those packet adjustments, not a fully held-out test: legacy priors may share related expert/statistical information.',
        '', 'Differences are in each input’s native units: technique grades, FT percentage points, geometry cm or mass kg. Technique comparisons provisionally share the hand packets’ 50/75/90 anchors; FT retains its separately declared conversion-percentage scale. No mixed-unit grand average is reported. “Inside” asks whether the hand midpoint falls inside the estimator’s broad plausibility band, not whether two calibrated confidence intervals overlap. A dash means there is no comparable hand cell.',
        '', '| Input | Name | Estimated | Prior | Hand cells | Mean absolute difference | Inside band | Difference without experts | Inside without experts |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|'])
    for row in comparison['table']:
        iid=row['input_id'];count=row['count'];c=coverage[iid]
        diff=f'{row["mean_absolute_difference"]:.2f}' if count else '—'
        inside=f'{100*row["inside_fraction"]:.1f}%' if count else '—'
        baseline=f'{row["baseline_mean_absolute_difference"]:.2f}' if count else '—'
        base_inside=f'{100*row["baseline_inside_fraction"]:.1f}%' if count else '—'
        lines.append(f'| {iid} | {row["name"]} | {c["estimated"]} | {c["prior"]} | {count} | {diff} | {inside} | {baseline} | {base_inside} |')
    lines.extend(['','## Ten largest technique disagreements','',
        'Sorted within technique grades only; centimeter and kilogram differences are not ranked against grades. Each explanation identifies the evidence limitation rather than treating the hand value as truth.',
        '', '| Player | Input | Estimator | Hand reference | Difference | Explanation |',
        '|---|---|---:|---:|---:|---|'])
    for row in comparison['biggest_disagreements']:
        explanation=row['explanation']
        if 'expert' in explanation:
            gaps={
                'S20':'No tagged attack-choice windows; the conservative position/role prior retains 65% weight despite expert praise of orchestration.',
                'F04.execution':'No typed lob-delivery sample; a broad role prior is retained alongside expert evidence of passing repertoire.',
                'F04.recognition':'No counted available lob reads; general passing praise supplies direction with broad uncertainty.',
                'S09':'No deep-shot mechanics curve; global three-point accuracy cannot identify distance-extension technique.',
                'S41':'Steals and deflections mix anticipation, technique and scheme; expert anticipation evidence adjusts a broad prior.',
                'S33':'No stance/angle success sample separated from physical tools; the expert containment assessment adjusts the role prior.',
                'S02':'Global three-point outcomes and an uncertain live-dribble difficulty prior understate the expert assessment of elite pull-up shooting.',
                'S44':'No responsibility-error counts; the expert assessment of attention adjusts an otherwise broad prior.',
                'S35':'No independent navigation-technique sample; the broad prior retains most weight despite expert praise.',
            }
            explanation=gaps.get(row['input_id'],'The broad baseline retains 65% weight; isolated technique observations are unavailable.')
        lines.append(f'| {names[row["player_id"]]} | {row["input_id"]} {DEFINITIONS[row["input_id"]]["name"]} | {row["estimate"]:.2f} | {row["reference"]:.2f} | {row["absolute_difference"]:.2f} | {explanation} |')
    lines.extend(['','## Observable tendencies and shot locations','',
        'T02 now uses player attempt counts: current completed ESPN 3PA/FGA first, then valid provider attempt-rate fields, then dated observed chart counts when no newer ratio exists. The three-point share shrinks by 100 prior field-goal attempts. Retained 2024–25 aggregate chart bins inform conditional two-point locations for matched players; their totals are reconciled, coordinates use the existing basket-relative feet grid, and two-foot bin/season uncertainty stays broad. The older chart does not count again toward a newer three-point ratio.',
        '', 'LT_06 efficiency and the ambiguous FREQ field are not shot-attempt frequencies. They are not used as observed location counts. Missing two-point subregions retain declared player priors. T01 action and T03 mode tags overlap and omit some alternatives; their estimates are explicitly partial proxies, with pass/reset prior mass preserved. Roll participation supports a broad T11 roll/pop proxy, and ORB% supports a broad T12 crash proxy with an explicit assumed recovery conversion, not a claim that rebounds equal crash attempts.',
        '', '| Tendency | Player-evidence estimates | Priors | Evidence strength |',
        '|---|---:|---:|---|'])
    for iid,label in [('T01','partial action mix'),('T02','attempt-location mix'),('T03','shooting modes'),
                      ('T05','transition frequency'),('T08','possession involvement'),('T09','cutting'),
                      ('T10','off-ball movement tags'),('T11','screen/roll/pop'),('T12','offensive crash'),('T18','contact seeking')]:
        strength=('attempt-count constrained; two-point subregions partly prior' if iid=='T02' else
                  'observed tag/rate with deployment and proxy uncertainty')
        lines.append(f'| {iid} {label} | {coverage[iid]["estimated"]} | {coverage[iid]["prior"]} | {strength} |')
    lines.extend(['','Families without an observed choice denominator (risk, persistence, help, contest choice, pursuit/box-out emphasis and effort allocation) remain wide player-conditioned priors. All probability rows normalize, every input retains a value, and the source/uncertainty record says which parts are observed or inferred.'])
    lines.extend(['','## Adapter feedback: joins and player-specific priors','',
        'Priors now respond weakly to related legacy traits, provider outcomes/workload, defensive deployment and body/age context. Every such record remains `reason: prior`, with low confidence and broad bands. `legacy_trait_prior` identifies the legacy contribution; those effective summaries are not relabeled as technique measurements. Direct statistical estimates are untouched by prior conditioning. No adapter rankings or simulation results enter these rules.',
        '', f'The audit cohort contains **{audit["rotation_players"]} players** with at least 1,000 minutes in any retained 2025–26 skill snapshot, later Crafted snapshot, or unique completed ESPN regular-season row. Taking the maximum selects the audit cohort only; source denominators are never summed. The report does not rely on a skill join to qualify a missing-skill player.',
        '', '| High-minute player with missing skill row | Retained minutes | Skill snapshot | Later Crafted snapshot | ESPN ID |',
        '|---|---:|---|---|---|'])
    if audit['unmatched_skills']:
        for row in audit['unmatched_skills']:
            lines.append(f'| {row["name"]} | {row["minutes"]:.1f} | missing | {"joined" if row["stats_joined"] else "missing"} | {"joined" if row["career_joined"] else "missing"} |')
    else:
        lines.append('| None | — | all joined | — | — |')
    lines.append('')
    lines.append('High-minute players missing the later Crafted snapshot: '+(', '.join(row['name'] for row in audit['unmatched_stats']) or 'none')+'.')
    # Explicitly requested identity check, not a named ranking or estimator rule.
    wemb=next((row for row in audit['players'] if row['name']=='Victor Wembanyama'),None)
    if wemb:
        inputs=section['players'][wemb['player_id']]['inputs']
        lines.extend(['',f'**Wembanyama check:** skill snapshot {"joined" if wemb["skill_joined"] else "missing"}; later Crafted snapshot {"joined" if wemb["stats_joined"] else "missing"}; ESPN ID {"joined" if wemb["career_joined"] else "missing"}. His record did not fail a name/accent join. The earlier near-50 passing and shooting numbers came from the reference scale and conservative estimates, while release speed was a flat prior. No named-player override has been added.',
            '', '| Requested player input | Value | Evidence label |', '|---|---:|---|'])
        for iid in ('S01','S02','S03','S07','S08','S09','F01.recognition','F01.execution'):
            r=inputs[iid]
            lines.append(f'| {iid} {DEFINITIONS[iid]["name"]} | {r["value"]["grade"]:.3f} | {estimation_status(r)} |')
    flags=[r for r in spread if r['near_zero']]
    lines.extend(['','## Rotation-player spread: all 94 inputs','',
        'Population standard deviation across the audit cohort, in native units. Distribution families show every outcome separately; there is no arbitrary scalar coding of outcomes. A flag marks any component below 1 grade point, 0.5 cm/kg, or 0.01 probability. These are review flags only: no rating is changed to pass a spread threshold, and no jitter is introduced.',
        '', f'**{len(flags)} input families have a near-zero component.** '+('Review: '+', '.join(r['input_id'] for r in flags)+'.' if flags else 'None of the approved families is flat at these declared thresholds.'),
        '', '| Input | Name | Players | Standard deviation (unit or outcome) | Near-zero components |',
        '|---|---|---:|---|---|'])
    for row in spread:
        deviations='; '.join(f'{key.removeprefix("reference_opportunity/")}: {sd:.4f}' for key,sd in row['standard_deviations'].items())
        flagged=', '.join(key.removeprefix('reference_opportunity/') for key in row['near_zero']) or '—'
        lines.append(f'| {row["input_id"]} | {row["name"]} | {row["count"]} | {deviations} | {flagged} |')
    lines.extend(['',END])
    return '\n'.join(lines)


def _name(name):
    # Reuse estimator join convention; do not introduce a second match policy.
    from nba_gm_data.input_estimator import _normalize
    return _normalize(name)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--report',type=Path,default=None)
    parser.add_argument('--no-report',action='store_true')
    parser.add_argument('--no-bbi',action='store_true',help='Skip the Basketball Index evidence overlay')
    parser.add_argument('--no-analysts',action='store_true',help='Skip the attributed analyst-claim evidence')
    args=parser.parse_args()
    root=args.root.resolve()
    output=args.output or root/'data/canonical/player_inputs_2026_27.json'
    report=args.report or root/'docs/agents/tasks/e2-input-estimator.md'
    started=time.perf_counter()
    universe=json.loads((root/UNIVERSE_PATH).read_text())
    estimator=InputEstimator.from_local(root)
    section=estimate_startup_inputs(estimator,universe)
    bbi_summary=None
    if not args.no_bbi and (root/'data/research/bbi/normalized.json').exists() and (root/'data/research/bbi/bbi_input_mapping.json').exists():
        # Player-specific Basketball Index evidence (Leaderboards Values captures) blended over the estimate.
        from nba_gm_data.bbi_evidence import apply_overlay, apply_measured_tendencies
        bbi_summary=apply_overlay(section,root)
        bbi_summary.update(apply_measured_tendencies(section,root))
        # Foul drawing and handle security per chance: free throws and turnovers against what an average player
        # earns or commits from the same drives, shots, passes and touches (RATINGS-FT-TOV, 2026-11-21).
        from nba_gm_data.foul_security_evidence import apply_foul_security_evidence
        bbi_summary.update(apply_foul_security_evidence(section,root,universe))
    # Measured dunk rates (public Basketball-Reference shooting data) for dunk execution, net of body size.
    from nba_gm_data.public_shot_evidence import apply_dunk_evidence
    bbi_summary=(bbi_summary or {})|apply_dunk_evidence(section,root,universe)
    # Strength and jump capacity: NBA Draft Combine tests (age-adjusted) blended with in-game proxies by reliability.
    from nba_gm_data.physical_evidence import apply_physical_evidence
    bbi_summary|=apply_physical_evidence(section,root,universe)
    # Attributed analyst claims last: where analysts and the measures disagree, analysts lead (user priority, 2026-11-19).
    if not args.no_analysts:
        from nba_gm_data.analyst_evidence import apply_analyst_evidence
        analyst=apply_analyst_evidence(section,root)
        analyst.pop('analyst_changes')
        bbi_summary|=analyst
    baseline=estimate_startup_inputs(InputEstimator.from_local(root,use_expert=False),universe)
    comparison=validation_comparison(section,load_reference_cells(root),baseline)
    payload=canonical_json(section)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(payload,encoding='utf-8')
    # Git tracks only the compressed copy (~4.5 MB vs ~92 MB); mtime=0 keeps it byte-reproducible.
    import gzip
    with open(str(output)+'.gz','wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=9,mtime=0,filename='') as gz:
        gz.write(payload.encode('utf-8'))
    elapsed=time.perf_counter()-started
    byte_count=len(payload.encode('utf-8'))
    if not args.no_report:
        text=report.read_text() if report.exists() else '# E2 input estimator\n'
        generated=report_tables(universe,section,comparison,elapsed,byte_count,estimator)
        if BEGIN in text and END in text:
            text=text[:text.index(BEGIN)]+generated+text[text.index(END)+len(END):]
        else:
            text=text.rstrip()+'\n\n'+generated+'\n'
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(text,encoding='utf-8')
    print(f'Wrote {len(section["players"])} players × 94 inputs to {output}')
    if bbi_summary:
        print(f'BBI overlay: {bbi_summary}')
    print(f'{byte_count:,} bytes; build and comparison {elapsed:.3f}s; {comparison["reference_players"]} reference players')


if __name__=='__main__':
    main()
