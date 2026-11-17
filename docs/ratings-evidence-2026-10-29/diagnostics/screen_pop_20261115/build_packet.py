"""Bounded research artifact builder; no engine imports, saves or simulations."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
RESEARCH = ROOT / 'docs/ratings-evidence-2026-10-29'
DIAG = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.player_model import PlayerInputs, validate_input_section

VERSION = 'screen_pop_research_v1_2026_11_15'
SCALE = 'research_technique_reference_v0_2026_11_13'
INPUT = 'player_performance_inputs_v1'
REG = 'player_performance_registry_v1'
FROZEN = 'docs/ratings-evidence-2026-10-29/EXPANDED_ACTION_COHORT_2026_11_14.json'
CANON = 'data/canonical/universe_2026_27_offseason.json'
MAP = 'docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md'

def read(path):
    return json.loads((ROOT / path).read_text())

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

frozen = read(FROZEN)
assert sha(FROZEN) == 'e61a71e7b1225f83c0e357386b98a08ce2a449c310e99f5846b80b00a32755d2'
canonical = read(CANON)
defs = {d['id']: d for d in definition_registry()['inputs']}
assert len(defs) == 94
IDs = [
    'player_mil-myles-turner', 'player_nyk-karl-anthony-towns',
    'player_okc-chet-holmgren', 'player_cha-naz-reid',
    'player_lac-brook-lopez', 'player_gsw-al-horford',
    'player_den-nikola-jokic', 'player_sas-victor-wembanyama',
]
canon_players = {p['id']: p for p in canonical['players']}
inherited = frozen['proposed_source_input_section']['players']

sources = {
    'CE': {'path': 'transcripts/episode4_transcript.txt', 'published_on': '2026-09-02', 'video_id': 'CbartUy6cMY', 'kind': 'user-retained timestamped transcript; targeted passages only this pass'},
    'T30': {'path': 'transcripts/episode3_transcript.txt', 'published_on': '2026-09-30', 'kind': 'user-retained timestamped transcript; targeted passages only this pass'},
    'T20': {'path': 'captions/ZaA4usLpBWI.en.vtt', 'published_on': '2026-10-02', 'video_id': 'ZaA4usLpBWI', 'kind': 'retained auto-captions; targeted passages only this pass'},
    'T10': {'path': 'captions/J6STkjbVuUg.en.vtt', 'published_on': '2026-10-07', 'video_id': 'J6STkjbVuUg', 'kind': 'retained auto-captions; targeted passages only this pass'},
    'TURNER_HISTORY': {'url': 'https://www.si.com/nba/2016/12/07/myles-turner-indiana-pacers-nate-mcmillan-the-craft', 'published_on': '2016-12-07', 'author': 'Rob Mahoney', 'kind': 'original reporting with player/coach explanations; written text reviewed, embedded media not reviewed', 'locator': 'offense section: screen precision, vision window, passing-lane adjustment', 'temporal_limit': 'Ten-year-old developmental evidence, not proof of unchanged current execution or body/conditioning.'},
    'HORFORD_HISTORY': {'url': 'https://www.celticsblog.com/2023/3/30/23657210/diversify-your-bigs-how-rob-williams-and-al-horford-dictate-boston-celtics-offense', 'published_on': '2023-03-30', 'author': 'Michael Spooner', 'kind': 'original analyst interpretation of selected actions; written text reviewed, embedded media not reviewed', 'locator': 'Al on without Rob; Both Rob and Al on', 'temporal_limit': 'Historical Boston role; older current player and changed team. No 2026 timed release/route measurement.'},
    'JOKIC_HISTORY': {'url': 'https://www.nba.com/news/finals-film-study-nuggets-heat-game-3', 'published_on': '2023-06-08', 'kind': 'inherited selected historical written analysis; inherited records preserved', 'temporal_limit': 'Not a current screening/receiving rate; no new estimates from this lookup.'},
}

# Summaries live once, here. New record evidence points to these claim IDs.
claims = [
    {'id': 'SP01', 'player_id': IDs[0], 'source': 'T10', 'window': '03:15:00–03:20:00', 'present_evidence': 'Indiana loses Turner shooting; he supplied rim protection but poor drop coverage. The same passage credits more speed than Zubac.', 'limits': 'Spacing does not establish screen contact, release speed, hands or pop choice. Poor drop is not a measured slow-physicals grade.', 'shared_group': 'turner_2026_spacing'},
    {'id': 'SP02', 'player_id': IDs[0], 'source': 'TURNER_HISTORY', 'window': 'offense section, paragraphs beginning Change came / In the meantime', 'present_evidence': 'Historical reporting separates screen angle/legal stop, reading help and relocating into a changing passing window; missed contact and endurance caveats remain.', 'limits': 'Historical development, not measured 2026 execution; modern spacing supports role continuity only. Current S27, strength and release remain unknown.', 'shared_group': 'turner_historical_screen_route'},
    {'id': 'SP03', 'player_id': IDs[1], 'source': 'CE', 'window': '01:20:36–01:22:06;01:24:35–01:25:00', 'present_evidence': 'Towns praised as elite shooter, specifically catch-and-shoot and deep contested makes, with hub/passing growth.', 'limits': 'Run sustainability disputed; playoff peak may regress. No isolated reference-mode denominator, preparation time, pop read or legal-screen sample.', 'shared_group': 'towns_center_shooting'},
    {'id': 'SP04', 'player_id': IDs[1], 'source': 'T10', 'window': '03:25:17–03:32:25', 'present_evidence': 'Hub offense credited, but regular-to-playoff jumper and team catch-shoot improvement flagged as regression risk.', 'limits': 'Speaker statistics unverified; team catch-shoot change is not Towns individual mode accuracy. Weight-loss concern is not measured force.', 'shared_group': 'towns_team_regression'},
    {'id': 'SP05', 'player_id': IDs[2], 'source': 'CE', 'window': '01:00:07–01:00:35;01:01:20–01:02:25;01:03:46–01:05:05', 'present_evidence': 'Holmgren a fluid roller and useful three-point big; slow/low release and contested-shot access criticized in Spurs matchup, despite earlier effective rounds.', 'limits': 'Catch radius is geometry, not independent hands technique. Neither wing physicality nor offensive collapse diagnoses screen quality. Low release is not a new release-height measurement.', 'shared_group': 'holmgren_shooting_access'},
    {'id': 'SP06', 'player_id': IDs[3], 'source': 'T30', 'window': '00:41:08–00:42:10 (named shooter list 00:41:42–00:41:55)', 'present_evidence': 'Captioned Nas Reed appears among Charlotte shooters in an expected three-heavy offense.', 'limits': 'Resolved to canonical Naz Reid by name and team context; broad role evidence only. No catch split, speed, range-extension, route or screening observation; weak team creation may limit opportunities.', 'shared_group': 'reid_team_spacing'},
    {'id': 'SP07', 'player_id': IDs[4], 'source': 'T30', 'window': '00:16:10–00:16:16;00:19:06–00:19:32;00:26:44–00:26:55', 'present_evidence': 'Lopez explicitly included in available shooting, with a perimeter-heavy diet and sharply criticized mobility/rim-pressure context.', 'limits': 'Volume is deployment, not accuracy; rhetorical immobility is not m/s. Size and one historical screen example cannot establish current S27.', 'shared_group': 'lopez_team_spacing'},
    {'id': 'SP08', 'player_id': IDs[5], 'source': 'T20', 'window': '01:28:34–01:29:24;01:34:50–01:35:00', 'present_evidence': 'Horford described as solid/serviceable with shooting and offensive feel, permitting several frontcourt combinations.', 'limits': 'Rotational and older-player context. No timed release or named pop observation in this window; team strength praise cannot become measured strength.', 'shared_group': 'horford_current_fit'},
    {'id': 'SP09', 'player_id': IDs[5], 'source': 'T10', 'window': '00:39:25–00:39:37', 'present_evidence': 'Historical Boston comparison credits Horford catch-and-go decision making rather than an ignorable stationary nonshooter.', 'limits': 'Historical referent within a 2026 discussion, not a fresh 2026 possession sample. Normal catch/use does not certify difficult-pass reception.', 'shared_group': 'horford_catch_go'},
    {'id': 'SP10', 'player_id': IDs[5], 'source': 'HORFORD_HISTORY', 'window': 'Al on without Rob; Both Rob and Al on', 'present_evidence': 'Analyst distinguishes shooting routes, popping after screens, occasional trap-punishing short rolls and post-catch choices.', 'limits': '2023 selected actions; observed Boston preference is not invariant T11. Age/team change prevent a precise 2026 release or contact grade.', 'shared_group': 'horford_historical_route'},
    {'id': 'SP11', 'player_id': IDs[6], 'source': 'CE', 'window': '01:32:23–01:35:07;01:36:54–01:38:45', 'present_evidence': 'Historic offense and weak-support carrying argument, countered by a poor Minnesota series and Gobert matchup.', 'limits': 'Does not isolate reference catch three, range extension or pop route; preserve existing historical screen/receiving estimates without inventing current shooting.', 'shared_group': 'jokic_inherited_context'},
    {'id': 'SP12', 'player_id': IDs[7], 'source': 'CE', 'window': '01:35:07–01:36:54;01:38:45–01:45:37', 'present_evidence': 'Strong offense and extraordinary rim threat, but finishing/polish and space-switching limitations; substantial further-growth language.', 'limits': 'Paint gravity is not proof of pop threat. Preserve tentative inherited S01; projection and height do not establish hands, screening or route reads.', 'shared_group': 'wembanyama_inherited_context'},
]
claim_by_id = {c['id']: c for c in claims}
source_paths = [FROZEN, CANON, MAP, 'src/nba_gm_data/player_model.py', 'src/nba_gm_data/player_model_registry.py', 'docs/ratings-evidence-2026-10-29/SOURCE_INDEX.md', 'docs/ratings-evidence-2026-10-29/transcripts/TRANSCRIPT_MANIFEST.md']
source_paths += ['docs/ratings-evidence-2026-10-29/' + s['path'] for s in sources.values() if 'path' in s]
source_hashes = {p: sha(p) for p in source_paths}

def unknown(k):
    return {'status': 'unknown', 'value': None, 'evidence': [], 'reason': f'{k}: no supported player-specific input established in this bounded packet.', 'uncertainty': {'confidence': 'unknown', 'notes': 'No generic grade or distribution is implied. Any future completion must be separately labeled a control.'}}

base = {'version': INPUT, 'registry_version': REG, 'players': {}}
origins = {}
cohort = []
for pid in IDs:
    cp = canon_players[pid]
    cohort.append({'player_id': pid, 'name': cp['name'], 'team_abbrev_in_snapshot': cp['team_abbrev'], 'espn_player_id': cp.get('espn_player_id'), 'snapshot_source': CANON, 'identity_is_snapshot_not_live_roster_verification': True})
    if pid in inherited:
        base['players'][pid] = deepcopy(inherited[pid])
        for k, rec in inherited[pid]['inputs'].items():
            if rec['status'] != 'unknown': origins[(pid, k)] = {'kind': 'inherited_supported', 'packet': FROZEN, 'packet_version': frozen['packet_version'], 'section': 'proposed_source_input_section', 'record_sha256': hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    else:
        base['players'][pid] = {'version': INPUT, 'registry_version': REG, 'player_id': pid, 'inputs': {k: unknown(k) for k in defs}}
proposed = deepcopy(base)
new_estimates = []

def add_grade(pid, k, bounds, refs, explanation, caveat):
    assert proposed['players'][pid]['inputs'][k]['status'] == 'unknown'
    assert defs[k]['kind'] == 'grade'
    value = {'grade': sum(bounds) / 2, 'scale': SCALE}
    evidence = []
    for ref in refs:
        c = claim_by_id[ref]
        s = sources[c['source']]
        evidence.append({'source': s.get('path', s.get('url')), 'method': 'dated source assessment plus explicit provisional technique inference', 'as_of': s['published_on'], 'shared_evidence_id': c['shared_group'], 'notes': f"{ref}; {c['window']}; full claim and limits in source ledger."})
    record = {'status': 'estimated', 'value': value, 'evidence': evidence, 'uncertainty': {'confidence': 'low', 'notes': f'Provisional range {bounds[0]}–{bounds[1]}, not statistical CI. {explanation} {caveat}'}}
    proposed['players'][pid]['inputs'][k] = record
    entry = {'player_id': pid, 'name': canon_players[pid]['name'], 'design_id': k, 'origin': 'new_scouting_estimate', 'range': bounds, 'reference': value, 'evidence_claim_ids': refs, 'inference': explanation, 'counterevidence': caveat, 'confidence': 'low magnitude; source direction separately documented', 'record': record}
    new_estimates.append(entry)
    origins[(pid, k)] = {'kind': 'new_scouting_estimate', 'evidence_claim_ids': refs}

add_grade(IDs[0], 'S26', [60,85], ['SP02','SP01'], 'Window-maintenance relocation hypothesis, not sprint speed or moving-shot accuracy.', 'Historical technique with current spacing continuity; no current route-timing sample.')
add_grade(IDs[0], 'S28', [60,85], ['SP02','SP01'], 'Broad screen-follow-up reading hypothesis; shares evidence with S26, not an independent measured bonus.', 'Historical instruction and described behavior do not isolate present recognition from handler/coaching. S27 remains unknown.')
add_grade(IDs[1], 'S01', [82,95], ['SP03','SP04'], 'Explicit catch-three assessment supports strong-to-exceptional reference execution.', 'Peak playoff variance and absent isolated denominators preclude precise probability or every-context superiority.')
add_grade(IDs[1], 'S09', [75,93], ['SP03'], 'Broad mechanics-extension hypothesis from deep shooting assessment, not another universal accuracy bonus.', 'Distance is qualitative; no meters or separation of shot quality, release height and extension technique.')
add_grade(IDs[2], 'S01', [65,85], ['SP05'], 'Useful reference catch-shot hypothesis from three-point-big assessment.', 'Mixed-mode and matchup evidence; catch-only accuracy not measured. Preparation is separately constrained.')
add_grade(IDs[2], 'S08', [35,60], ['SP05'], 'Below-strong preparation-speed hypothesis from explicit slow-release concern.', 'No milliseconds; low release height is not this grade. Open shots and earlier rounds remain counterevidence; do not penalize both S01 and S08 for the same contest difficulty.')
add_grade(IDs[3], 'S01', [65,85], ['SP06'], 'Tentative reference catch-shooting hypothesis from explicit shooter-role inclusion.', 'Thin collective role praise, not a mode split; range broad and low confidence. No route or screen competence inferred.')
add_grade(IDs[4], 'S01', [65,84], ['SP07'], 'Tentative reference catch-shooting hypothesis from affirmative shooting assessment.', 'Perimeter frequency alone is insufficient; positive shooting remark is the support. No exact shooting probability or moving-release grade.')
add_grade(IDs[5], 'S01', [65,86], ['SP08','SP10'], 'Current rotational spacing supports a useful catch-shot hypothesis, with historical context.', 'Historical peak is not copied into current ability; no current catch-only denominator or exact probability.')
add_grade(IDs[5], 'S14', [65,85], ['SP09','SP08'], 'Broad ordinary-pass catch-and-use hypothesis from catch-and-go role.', 'No difficult-pass sample; decision evidence is correlated with S20 and cannot count as a second full post-catch decision bonus.')
add_grade(IDs[5], 'S20', [72,90], ['SP09','SP08'], 'Post-catch attack/reset recognition hypothesis from explicit decision-making and current offensive feel.', 'Not a passing-family grade or screen-read substitute; historical Boston comparison and team context confound magnitude.')
add_grade(IDs[5], 'S26', [65,88], ['SP10','SP08'], 'Shooting-route arrival/timing hypothesis with historical specific actions and current role continuity.', 'Current physical speed and preparation remain unknown; historical routes do not establish current route-success rate.')
add_grade(IDs[5], 'S28', [65,88], ['SP10','SP08'], 'Broad follow-up selection hypothesis across pop and trap short-roll contexts.', 'Historical coach/deployment confounds; shares evidence with route grade. No innate pop probability, no independently measured present S27.')

# Newly reported conversions only for players without inherited profiles.
for pid in IDs:
    if pid in inherited:
        continue
    cp = canon_players[pid]
    for k, field, unit, factor in [('P01','height_inches','cm',2.54),('P02','wingspan_inches','cm',2.54),('P04','weight_lbs','kg',0.45359237)]:
        if cp.get(field) is None:
            continue
        record = {'status': 'estimated', 'value': {'measurements': [{'metric': field, 'value': round(cp[field] * factor, 6), 'unit': unit, 'protocol': 'Canonical reported value; original measurement date, footwear and protocol unknown; unit conversion only.'}]}, 'evidence': [{'source': CANON, 'method': 'exact reported-unit conversion only; no new physical testing', 'as_of': '2026-11-15', 'shared_evidence_id': 'canonical_reported_physical_tools', 'notes': 'Extraction date, not physical measurement date. Raw field and value preserved in new-estimate ledger.'}], 'uncertainty': {'confidence': 'medium', 'notes': 'Reported snapshot, not verified test. Conversion decimals add no precision; mass is not strength and reach remains unknown.'}}
        proposed['players'][pid]['inputs'][k] = record
        new_estimates.append({'player_id': pid, 'name': cp['name'], 'design_id': k, 'origin': 'new_reported_conversion', 'raw_field': field, 'raw_value': cp[field], 'conversion_factor': factor, 'unit': unit, 'record': record})
        origins[(pid,k)] = {'kind': 'new_reported_conversion', 'source': CANON, 'raw_field': field}

# Fixed approved-map dependencies. Deliberately NOT read from the changing backend.
dependencies = {
    'C01': {'ids': ['S01','S04','S08','S09','P09'], 'meaning': 'reference catch-shot response; not route generation'},
    'C13': {'ids': ['S14','P02','P09'], 'meaning': 'pass securing/use, conditional on delivery'},
    'C17': {'ids': ['S25','S26','P05','P06','P07','P09'], 'meaning': 'full approved off-ball family; S25 cutting is outside the narrow shooting-relocation envelope'},
    'C18': {'ids': ['S27','S28','P01','P02','P03','P04','P08','P09'], 'meaning': 'screen placement/contact/legality and follow-up opportunities'},
    'C19': {'ids': ['S28','P01','P02','P03','P05','P09'], 'derived_dependencies': ['C17','C18'], 'meaning': 'prospective roll/pop/slip availability; actual scoring and receiving remain separate'},
    'C33_CONTEXT': {'ids': ['T11','S28','S20','T01','T02','T03'], 'meaning': 'screen follow-up and shot policy subset; full C33 has other contexts. Choices are not shooting skill.'},
}
core_ids = sorted(set(dependencies['C01']['ids'] + dependencies['C13']['ids'] + dependencies['C18']['ids'] + dependencies['C19']['ids'] + ['S26','P06','P07','T11']))
choice_ids = ['S20','T01','T02','T03']
passing_ids = [f'F{i:02d}.{stage}' for i in range(1,10) for stage in ['recognition','execution']]
readiness = []
ledger = []
for pid in IDs:
    inp = proposed['players'][pid]['inputs']
    missing = [k for k in core_ids if inp[k]['status'] == 'unknown']
    readiness.append({'player_id': pid, 'name': canon_players[pid]['name'], 'fixed_prospective_core_ids': core_ids, 'core_supported': [k for k in core_ids if k not in missing], 'core_unknown': missing, 'choice_context_unknown': [k for k in choice_ids if inp[k]['status']=='unknown'], 'all_known_inputs': [k for k in defs if inp[k]['status']!='unknown'], 'status': 'source profile schema-valid; prospective pop action incomplete without separately declared controls; actual interface not verified'})
    for k,d in defs.items():
        ledger.append({'player_id': pid, 'name': canon_players[pid]['name'], 'design_id': k, 'label': d['name'], 'base_status': base['players'][pid]['inputs'][k]['status'], 'proposed_status': inp[k]['status'], 'origin': origins.get((pid,k), {'kind': 'source_unknown'}), 'prospective_core_dependency': k in core_ids, 'choice_context_dependency': k in choice_ids, 'passing_pair_retained': k in passing_ids, 'actual_compiled_consumer_verified_this_task': False, 'record_pointer': f'/proposed_source_input_section/players/{pid}/inputs/{k}'})

counts = {'players': 8, 'inputs_per_player': 94, 'records_per_layer': 752, 'inherited_supported_records': sum(r['status']!='unknown' for p in base['players'].values() for r in p['inputs'].values()), 'new_scouting_ranges': sum(e['origin']=='new_scouting_estimate' for e in new_estimates), 'new_reported_conversions': sum(e['origin']=='new_reported_conversion' for e in new_estimates), 'proposed_known_records': sum(r['status']!='unknown' for p in proposed['players'].values() for r in p['inputs'].values()), 'prospective_core_ids_per_actor': len(core_ids), 'prospective_core_supported_cells': sum(len(r['core_supported']) for r in readiness), 'source_claims': len(claims), 'operational_completions': 0}
counts['proposed_unknown_records'] = 752-counts['proposed_known_records']
counts['prospective_core_unknown_cells'] = 8*len(core_ids)-counts['prospective_core_supported_cells']

packet = {
    'packet_version': VERSION, 'input_version': INPUT, 'registry_version': REG,
    'production_import_authorized': False,
    'date_policy': {'target': 'October 2026 immediately before regular-season opener', 'canonical_file_meta_start_date': canonical['meta'].get('canonical_start_date'), 'canonical_file_starting_data_version': canonical['meta'].get('starting_data_version'), 'interpretation': 'July metadata is retained provenance, not a reversal of the user-approved October target. No date or roster mutation. Historical sources explicitly dated; no post-start performances or growth projection used as current skill.', 'health': 'healthy ability separate from dated availability; no new medical or transaction audit'},
    'technique_scale': {'id': SCALE, 'anchors': {'50': 'functional reference','75': 'strong reference','90': 'exceptional reference'}, 'meaning': 'broad provisional raw decomposition hypotheses; not production OVR, calibrated probability, percentile or statistical CI'},
    'cohort': cohort, 'counts': counts,
    'inheritance': {'packet': FROZEN, 'packet_version': frozen['packet_version'], 'sha256': source_hashes[FROZEN], 'source_section': 'proposed_source_input_section', 'policy': 'All94 source records copied exactly for Turner/Jokic/Wembanyama. New estimates fill unknowns only; no old operational controls imported. Five other actors start94 explicit unknowns.'},
    'base_source_input_section': base, 'proposed_source_input_section': proposed,
    'new_estimates': new_estimates,
    'source_ledger_path': 'diagnostics/screen_pop_20261115/source_ledger.json',
    'readiness_ledger_path': 'diagnostics/screen_pop_20261115/readiness_ledger.json',
    'fixed_approved_map_dependencies': dependencies, 'readiness': readiness,
    'operational_input_section': None, 'operational_completions': [],
    'experimental_completion_suggestions': [
        {'kind': 'not_player_estimates', 'suggestion': 'First compare supplied reference catches under common declared preparation/reception/geometry controls where unknown; do not label this a full pop-route test.'},
        {'kind': 'not_player_estimates', 'suggestion': 'For a future route test, hold handler, defender, start, physical controls and called follow-up fixed; separately vary unknown screening, route, receiving and release assumptions. No common values supplied by this packet.'},
        {'kind': 'not_innate_tendency', 'suggestion': 'Use separate called-roll and called-pop strata before any T11 mix. All eight T11 distributions remain unknown. Label any mixture a coaching scenario, not observed deployment.'},
    ],
    'proposed_source_corrections': [], 'human_questions_required': [],
    'independence': {'milestone10_outcomes_inspected': False, 'backend_implementation_inspected': False, 'schema_and_registry_only': True, 'profile_compilations': 0, 'simulations': 0, 'production_or_save_writes': 0},
    'source_hashes': source_hashes,
    'validation_scope': 'Existing source schema,94-ID completeness, passing-pair preservation, units/types/ranges, provenance and source preservation; not actual pop compilation or runtime correctness.',
}
dump(RESEARCH/'SCREEN_POP_INPUTS_2026_11_15.json',packet)
dump(DIAG/'source_ledger.json', {'packet_version': VERSION, 'sources': sources, 'claims': claims, 'coverage': 'Targeted source windows only this pass; prior full-extraction coverage is inherited, not claimed as new audiovisual review.', 'speaker_policy': 'unidentified/local turns; no persistent cross-episode identity assignment', 'lookup_log': {'search_rounds': 2, 'broad_acquisition': False, 'failed': [{'url': 'https://api-hub.nba.com/news/film-study-damian-lillard-bucks-2023','status':'461 on open; no retry; snippet example not used for numerical screening grade'}], 'limited': [{'url': 'https://www.nba.com/pacers/news/turner-shooting-at-both-record-volume-and-efficiency','status': 'search snippet only; body no readable lines; exact publication date not established; no new estimate depends on it'}, {'url': 'https://www.nba.com/warriors/videos/horford-pick-and-pop-three-film-study','status': 'title only, no audiovisual content reviewed; no grade or event date taken from title'}], 'rejected': 'Paywalled Patreon/current post-start content, unrelated defensive-screen results and social comments not used. No subscriptions, repeated blocked requests or video downloads.'}})
dump(DIAG/'readiness_ledger.json', {'packet_version':VERSION, 'basis':MAP, 'prospective_only':True, 'rows':ledger})

# Schema validation is permitted; import no adapter/engine and never put inputs in a save.
validate_input_section(base)
validate_input_section(proposed)
for pid in IDs:
    assert set(base['players'][pid]['inputs']) == set(defs)
    assert set(proposed['players'][pid]['inputs']) == set(defs)
    assert PlayerInputs(proposed['players'][pid]).to_dict() == proposed['players'][pid]
    assert set(k for k in proposed['players'][pid]['inputs'] if k.startswith('F')) == set(passing_ids)
    if pid in inherited:
        assert base['players'][pid] == inherited[pid]
        for k,rec in inherited[pid]['inputs'].items():
            if rec['status'] != 'unknown': assert proposed['players'][pid]['inputs'][k] == rec
    assert proposed['players'][pid]['inputs']['T11']['status'] == 'unknown'
for e in new_estimates:
    if e['origin'] == 'new_scouting_estimate':
        assert 0 <= e['range'][0] <= e['reference']['grade'] <= e['range'][1] <=100
        assert all(ref in claim_by_id for ref in e['evidence_claim_ids'])
        assert base['players'][e['player_id']]['inputs'][e['design_id']]['status'] == 'unknown'
for s in sources.values():
    if 'path' in s: assert (RESEARCH/s['path']).exists()
checks = {p: sha(p)==h for p,h in source_hashes.items()}
assert all(checks.values())
validation = {'packet_version':VERSION, 'status':'PASS', 'counts':counts, 'layers_schema_validated':['base_source_input_section','proposed_source_input_section'], 'player_roundtrips':8, 'all_94_ids_each':True, 'stable_ids_unique_in_canonical':True, 'inherited_profiles_exact_in_base':3, 'inherited_supported_records_exact_in_proposed':counts['inherited_supported_records'], 'passing_fields_per_actor':18, 'all_passing_records_preserved_from_base':all(base['players'][pid]['inputs'][k]==proposed['players'][pid]['inputs'][k] for pid in IDs for k in passing_ids), 'all_T11_unknown':True, 'new_grades_only_fill_unknowns':True, 'range_and_scale_checks':True, 'physical_units_and_conversions_schema_valid':True, 'source_hash_checks':checks, 'local_sources_present':True, 'profile_compilations':0, 'simulations':0, 'production_or_save_writes':0, 'actual_pop_consumer_verified':False}
assert validation['all_passing_records_preserved_from_base']
dump(DIAG/'validation.json',validation)
print(json.dumps({'status':'PASS','counts':counts,'validation':str(DIAG.relative_to(ROOT)/'validation.json')}))
