"""Read-only league-wide defensive input replay and construction experiments.

No full universe/economic rebuild: only the existing trait pipeline is replayed
in privately owned memory. Current production source/data are never written.
"""
from __future__ import annotations
import argparse,csv,hashlib,inspect,json,math,resource,statistics,sys,time,tracemalloc
from collections import Counter,defaultdict
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import ingest as ig,traits as tr
from nba_gm_data.imported_skill_calibration import calibrate_imported_skills
from nba_gm_data.rotation_profile_calibration import calibrate_rotation_profiles
from nba_gm_data.five_player_calibration import apply_calibration
from nba_gm_data.roster_alignment import align_imported_roster
from nba_gm_data.schema import to_plain
from nba_gm_data.utils import percentile_maps,normalize_name
from experiments.defensive_inputs.model import (VERSION,KEYS,FIELDS,finite,infer,freeze_reference,
    fixed_lookup,experiment,reapply_overrides,source_overlap,tail_scale)


def distribution(values):
    xs=sorted(float(v) for v in values if v is not None)
    if not xs:return {'n':0}
    def q(p):
        pos=(len(xs)-1)*p;i=int(pos);j=min(i+1,len(xs)-1)
        return xs[i]+(xs[j]-xs[i])*(pos-i)
    return {'n':len(xs),'min':xs[0],'p10':q(.1),'median':q(.5),'p90':q(.9),'p95':q(.95),
        'max':xs[-1],'zero':sum(v==0 for v in xs),'hundred':sum(v==100 for v in xs),
        'above_100':sum(v>100 for v in xs),'at_least_95':sum(v>=95 for v in xs),
        'unique_exact':len(set(xs)),'unique_rounded_2dp':len({round(v,2) for v in xs}),
        'largest_exact_tie':max(Counter(xs).values())}


def replay(root):
    raw=ig.load_json(root,ig.RAW_PLAYER_INPUT)
    draft=ig.load_optional_json(root,ig.OFFICIAL_DRAFT_2026_FILE) or {}
    prospects=ig.load_optional_json(root,ig.DRAFT_PROSPECTS_FILE) or {}
    base,new,roster_report=ig.apply_official_roster_snapshot(raw['players'],ig.load_optional_json(root,ig.OFFICIAL_ROSTERS_2026_FILE) or {},draft,prospects)
    rows=[*base,*new]
    players=ig.build_players(rows,ig.load_optional_json(root,ig.PLAYER_OVERRIDES_FILE) or {},ig.load_player_external_metadata(root))
    maps=percentile_maps(base,tr.PERCENTILE_FIELDS)
    ts=[];initial={}; stages={}; phase_times={}
    def capture(name,traits):
        stages[name]={(t.player_id,t.trait_key):t.value for t in traits if t.trait_key in KEYS}
    start=time.perf_counter()
    for i,row in enumerate(rows):
        player=players[i]
        built=tr.build_traits_for_player(row,i,player.id,maps,legacy_stamina=True)
        ts.extend(built)
        initial[player.id]=infer(row,lambda f,i=i:maps.get(f,{}).get(i))
        for t in built:
            if t.trait_key in KEYS:assert initial[player.id][t.trait_key]['capped']==t.value,(player.name,t.trait_key)
    phase_times['initial_inference']=time.perf_counter()-start
    capture('initial_capped',ts)
    n=len(base);ret=[t for t in ts if t.player_id in {p.id for p in players[:n]}]
    new_ids={p.id for p in players[n:]};nt=[t for t in ts if t.player_id in new_ids]
    calibration_trace=defaultdict(list)
    # Observe real pre-clamp arguments, preserving every original return value.
    real_clamp=tr.clamp
    lines,line_start=inspect.getsourcelines(tr.apply_league_trait_calibration)
    locations={line_start+i:('trait_blend' if 'clamp(calibrated)' in s else 'composite_nudge')
               for i,s in enumerate(lines) if 'clamp(calibrated)' in s or 'clamp(before + nudge)' in s}
    def observed_clamp(value,*args,**kwargs):
        f=sys._getframe(1)
        if f.f_code is tr.apply_league_trait_calibration.__code__ and f.f_lineno in locations:
            d=f.f_locals
            calibration_trace[d['player_id'],d['trait_key']].append({
                'phase':locations[f.f_lineno],'column':d.get('column'),'preclip':value,
                'postclip':real_clamp(value,*args,**kwargs),'target':d.get('target'),
                'weight':d.get('trait_weight') if locations[f.f_lineno]=='trait_blend' else None,
                'before':d.get('previous') if locations[f.f_lineno]=='trait_blend' else d.get('before'),
                'nudge':d.get('nudge') if locations[f.f_lineno]=='composite_nudge' else None})
        return real_clamp(value,*args,**kwargs)
    start=time.perf_counter()
    with patch.object(tr,'clamp',observed_clamp):
        ret,calibration_report=tr.apply_league_trait_calibration(ret,players[:n],tr.load_league_trait_ratings(root/ig.LEAGUE_TRAIT_RATINGS_FILE))
    phase_times['subjective_calibration_observed']=time.perf_counter()-start
    capture('subjective_calibration',ret+nt)
    baseline=ig.roster_rating_baseline(root)
    start=time.perf_counter()
    ret,preservation=ig.preserve_returning_trait_values(ret,players[:n],baseline)
    nt,_=ig.preserve_returning_trait_values(nt,players[n:],baseline)
    phase_times['preservation']=time.perf_counter()-start
    capture('preservation',ret+nt)
    overrides=ig.load_optional_json(root,ig.TRAIT_OVERRIDES_FILE) or {}
    ret=ig.apply_trait_overrides(ret,players[:n],overrides)
    capture('manual_returning',ret+nt)
    from nba_gm_data import draft as draft_module
    conversion_trace={}
    original_rookie=ig.rookie_trait_records
    original_conversion=draft_module.nba_trait_values_from_prospect
    def observed_rookie(player,prospect,draft_traits=None):
        def observed_conversion(*args,**kwargs):
            values=original_conversion(*args,**kwargs)
            conversion_trace[player['id']]={k:values[k] for k in KEYS}
            return values
        with patch.object(draft_module,'nba_trait_values_from_prospect',observed_conversion):
            return original_rookie(player,prospect,draft_traits)
    with patch.object(ig,'rookie_trait_records',observed_rookie):
        newplayers,nt,rookie_report=ig.imported_rookie_ratings(players[n:],nt,prospects,draft)
    players=[*players[:n],*newplayers]
    capture('rookie_conversion',ret+nt)
    nt=ig.apply_trait_overrides(nt,newplayers,overrides)
    ts=ret+nt;capture('manual_new',ts)
    career=ig.load_optional_json(root,Path('data/research/player_career_stats.json')) or {}
    start=time.perf_counter()
    players,ts,alignment=align_imported_roster(players,ts,career,2026);capture('roster_alignment',ts)
    ts,_=tr.repair_preserved_stamina(ts);capture('stamina_repair_no_defense_change',ts)
    ts=ig.apply_trait_overrides(ts,players,{'players':overrides.get('post_alignment_players',[])});capture('post_alignment_manual',ts)
    ts,skill_report=calibrate_imported_skills(players,ts,career,2026);capture('skill_evidence_v7',ts)
    ts,rotation_report=calibrate_rotation_profiles(players,ts,career,2026);capture('rotation_profile_v8',ts)
    ts=apply_calibration(players,ts,ig.load_optional_json(root,Path('data/overrides/five_player_calibration_v11.json')));capture('scouting_v11',ts)
    phase_times['later_trait_layers']=time.perf_counter()-start
    return players,rows,ts,initial,stages,calibration_trace,phase_times,{
        'base_source_players':len(base),'new_roster_rows':len(new),'subjective_calibration':calibration_report,
        'rookie_prebound_conversion':conversion_trace,
        'preservation':preservation,'rookie_conversion':rookie_report,'alignment':alignment,
        'skill_evidence':skill_report,'rotation_profile':rotation_report}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reference',type=Path,help='Reuse a previously frozen reference JSON; default freezes current source ONCE for this experiment')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=Path.cwd();start=time.perf_counter()
    canonical=json.loads((root/'data/canonical/universe_2026_27_offseason.json').read_text())
    source_bytes=(root/ig.RAW_PLAYER_INPUT).read_bytes();source_sha=hashlib.sha256(source_bytes).hexdigest()
    source=json.loads(source_bytes)
    reference=json.loads(args.reference.read_text()) if args.reference else freeze_reference(source['players'],source_sha)
    (args.output/'fixed_reference.json').write_text(json.dumps(reference,indent=2)+'\n')
    players,rows,traits,initial,stages,caltrace,times,reports=replay(root)
    existing={(t['player_id'],t['trait_key']):t for t in canonical['traits'] if t['trait_key'] in KEYS}
    rebuilt={(t.player_id,t.trait_key):t for t in traits if t.trait_key in KEYS}
    mismatches=[{'id':k[0],'trait':k[1],'replayed':t.value,'canonical':existing.get(k,{}).get('value')} for k,t in rebuilt.items() if k not in existing or t.value!=existing[k]['value']]
    assert set(rebuilt)==set(existing)
    assert not mismatches,mismatches[:20]
    metadata_mismatches=[{'id':k[0],'trait':k[1]} for k,t in rebuilt.items()
        if t.components!=existing[k]['components'] or t.confidence!=existing[k]['confidence']
        or t.source_ids!=existing[k]['source_ids'] or t.source_kind!=existing[k]['source_kind']]
    current_players={p['id']:p for p in canonical['players']}
    output=[];flat=[];stage_names=list(stages);weights=[];reapplied=Counter();held=Counter();candidate_times=[]
    original_names={normalize_name(p.get('name')) for p in source['players']}
    original_by_name={normalize_name(p.get('name')):p for p in source['players']}
    original_maps=percentile_maps(source['players'],tr.PERCENTILE_FIELDS)
    original_inference={normalize_name(row.get('name')):infer(row,lambda f,i=i:original_maps.get(f,{}).get(i))
                        for i,row in enumerate(source['players'])}
    for player,row in zip(players,rows):
        current={k:existing[player.id,k]['value'] for k in KEYS}
        reviewed={k for k in KEYS if any(marker in existing[player.id,k]['components'] for marker in ('manual_calibration','five_player_scouting_v11'))}
        start_one=time.perf_counter();exp=experiment(row,reference);candidate_times.append(time.perf_counter()-start_one)
        # Only actual March model rows have a defensible raw numeric source.
        has_source=normalize_name(row.get('name')) in original_names
        original_row=original_by_name.get(normalize_name(row.get('name')),{})
        range_only={k:tail_scale(initial[player.id][k]['preclip']) if has_source else None for k in KEYS}
        range_final,_=reapply_overrides(range_only,current,reviewed)
        a={k:exp['A_fixed_reference'][k] if has_source else None for k in KEYS}
        a_out,a_status=reapply_overrides(a,current,reviewed)
        b={k:exp['B_rim_hypothesis'] if k=='rim_deterrence' and has_source else None for k in KEYS}
        b_out,b_status=reapply_overrides(b,current,reviewed)
        p=current_players[player.id]
        record={'player_id':player.id,'name':p['name'],'position':p.get('position'),'height_inches':p.get('height_inches'),
            'source_role':row.get('primaryDefRole'),'source_available':has_source,'sample_context':exp['sample'],
            'raw_source':{f:row.get(f) for f in FIELDS},'source_augmentation':row.get('augment'),
            'original_March_source_fields':{f:original_row.get(f) for f in FIELDS},
            'roster_overlay_changes':{f:{'before':original_row.get(f),'after':row.get(f)}
                for f in (*FIELDS,'position','primaryOffRole','primaryDefRole','minutes')
                if has_source and (finite(original_row.get(f))!=finite(row.get(f)) if f in FIELDS else original_row.get(f)!=row.get(f))},
            'pre_roster_initial':original_inference.get(normalize_name(row.get('name'))),
            'initial':initial[player.id],'current':current,'reviewed_override_traits':sorted(reviewed),
            'range_only_replay':range_final,
            'range_only_limit':'Pure numeric-range diagnostic inherits ordinal/cohort source ranks; NOT the proposed stable reference mapping.',
            'A_pre_override':a,'A_final':a_out,'A_status':a_status,'B_pre_override':b,'B_final':b_out,'B_status':b_status,
            'B_channels':exp['B_channels'],'lineage':{}}
        for key in KEYS:
            t=existing[player.id,key]; comp=t['components'];keypair=(player.id,key)
            lineage={'replayed_stages':{n:stages[n][keypair] for n in stage_names},
                'subjective_preclip_trace':caltrace.get(keypair,[]),'current_components':comp,
                'rookie_conversion_prebound':reports['rookie_prebound_conversion'].get(player.id,{}).get(key),
                'current_notes':t.get('notes'),'last_verified':t.get('last_verified'),
                'source_ids':t['source_ids'],'source_kind':t['source_kind'],'confidence':t['confidence'],
                'unrecoverable':['Preserved historical latent preclip not stored; current raw replay is not proof of historical unclipped value.'] if comp.get('2026_roster_refresh') else []}
            if not has_source:lineage['unrecoverable'].append('No original March raw model row: initial newcomer fallback/rookie priors are NOT new NBA observations.')
            record['lineage'][key]=lineage
            reapplied[key]+=key in reviewed;held[key]+=b_status[key].startswith('held')
            flat.append({'player_id':player.id,'name':p['name'],'position':p.get('position'),'height':p.get('height_inches'),
                'source_role':row.get('primaryDefRole'),'raw_source_available':has_source,'trait':key,
                'initial_preclip':initial[player.id][key]['preclip'],
                **{n:stages[n][keypair] for n in stage_names},'current':current[key],
                'range_only_replay':range_final[key],
                'A_pre_override':a[key],'A_final':a_out[key],'B_pre_override':b[key],'B_final':b_out[key],
                'reviewed_override':key in reviewed,'A_status':a_status[key],'B_status':b_status[key]})
        if has_source:
            weights.append({k:initial[player.id][k]['normalized_source_weights'] for k in KEYS})
            neutral=infer(row,lambda f:50. if f=='CraftedDPM' else fixed_lookup(reference,f,row.get(f)))
            record['attribution_counterfactuals']={k:{
                'A_preclip':exp['A_uncapped'][k]['preclip'],
                'same_evidence_without_role_bonus':exp['A_uncapped'][k]['preclip']-exp['A_uncapped'][k]['role_bonus'],
                'CraftedDPM_held_neutral_50_preclip':neutral[k]['preclip'],
            } for k in KEYS}
            block=fixed_lookup(reference,'BLKpct',row.get('BLKpct'))
            height=fixed_lookup(reference,'HeightSocks',row.get('HeightSocks'))
            record['B_block_weight_sensitivity']={str(w):tail_scale(w*block+(1-w)*height) if block is not None and height is not None else None for w in (.7,.85,1.)}
        output.append(record)
    stats={}
    for key in KEYS:
        stats[key]={'current':distribution(p['current'][key] for p in output),
            'initial_preclip_all':distribution(p['initial'][key]['preclip'] for p in output),
            'initial_preclip_original_source_only':distribution(p['initial'][key]['preclip'] for p in output if p['source_available']),
            'A_final':distribution(p['A_final'][key] for p in output),'B_final':distribution(p['B_final'][key] for p in output),
            'range_only_replay':distribution(p['range_only_replay'][key] for p in output),
            'A_mean_abs_change':statistics.fmean(abs(p['A_final'][key]-p['current'][key]) for p in output),
            'B_mean_abs_change':statistics.fmean(abs(p['B_final'][key]-p['current'][key]) for p in output),
            'by_replay_stage':{n:distribution(v for (_,k),v in st.items() if k==key) for n,st in stages.items()}}
    grouped={}
    groupers={'position':lambda p:p['position'] or 'unknown','source_role':lambda p:p['source_role'] or 'unknown',
        'height_band':lambda p:'unknown' if p['height_inches'] is None else '<77' if p['height_inches']<77 else '77–81' if p['height_inches']<82 else '82+',
        'source_GP_band':lambda p:'unknown' if p['sample_context']['GP'] is None else '<20' if p['sample_context']['GP']<20 else '20–49' if p['sample_context']['GP']<50 else '50+'}
    for group,get in groupers.items():
        partitions=defaultdict(list)
        for p in output:partitions[get(p)].append(p)
        grouped[group]={label:{'n':len(ps),**{k:{lane:distribution(p[lane][k] for p in ps) for lane in ('current','A_final','B_final')} for k in KEYS}} for label,ps in partitions.items()}
    overlap={a:{b:statistics.fmean(source_overlap(w)[a][b] for w in weights) for b in KEYS} for a in KEYS}
    field_uses={f:sum(any(f in w[k] for k in KEYS) for w in weights) for f in FIELDS}
    # Pre-clamp dependency allocation into current activity/rim blend. Rim's
    # nonlinear response and later overrides mean this is NOT final DEF effect.
    mix={'defensive_effort':.252,'foot_speed_lateral_agility':.216,'screen_navigation':.132,'rim_deterrence':.4,'scheme_iq':0}
    attribution={f:statistics.fmean(sum(mix[k]*w[k].get(f,0) for k in KEYS) for w in weights) for f in FIELDS}
    dependence={'mean_shared_source_weight_overlap':overlap,'source_present_players':field_uses,
        'mean_preclip_linear_activity_rim_dependency':attribution,
        'warning':'Exact structural weights before clipping/nonlinearity/calibration, not causal impact or independent skill evidence.'}
    with (args.output/'stages.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    (args.output/'players.json').write_text(json.dumps(output,indent=2)+'\n')
    # Broad untouched extremes and scalar endpoint detail, not a three-name patch.
    extremes={k:{'lowest_current':sorted(output,key=lambda p:p['current'][k])[:5],
                  'highest_A_unreviewed':sorted((p for p in output if k not in p['reviewed_override_traits']),key=lambda p:-p['A_final'][k])[:5]} for k in KEYS}
    extremes={k:{label:[{'name':p['name'],'current':p['current'][k],'A':p['A_final'][k],'B':p['B_final'][k]} for p in ps] for label,ps in groups.items()} for k,groups in extremes.items()}
    # Rank inversions count only identified source cohort; overrides can create
    # legitimate constraints/ties. Do not present any new order as validated.
    rank={}
    for key in KEYS:
        ps=[p for p in output if p['source_available']]
        lanes={}
        for lane in ('A_final','B_final'):
            inversions=tie_splits=new_ties=0
            for i,p in enumerate(ps):
                for q in ps[i+1:]:
                    old=p['current'][key]-q['current'][key];new=p[lane][key]-q[lane][key]
                    inversions+=old*new<0;tie_splits+=old==0 and new!=0;new_ties+=old!=0 and new==0
            lanes[lane]={'pairwise_rank_inversions':inversions,'current_ties_split':tie_splits,'new_ties_from_distinct_current':new_ties,'pairs':len(ps)*(len(ps)-1)//2}
        rank[key]=lanes
    # Stability evaluations use the exact SAME frozen reference, never refit it.
    originals=[r for r in rows if normalize_name(r.get('name')) in original_names]
    evaluated_fields=(*FIELDS,'name','primaryOffRole','primaryDefRole','position','GP','MP','minutes','2025minutes')
    (args.output/'evaluated_source_rows.json').write_text(json.dumps([{f:r.get(f) for f in evaluated_fields} for r in originals],indent=2)+'\n')
    baseline_scores=[experiment(row,reference) for row in originals]
    reversed_scores=list(reversed([experiment(row,reference) for row in reversed(originals)]))
    assert baseline_scores==reversed_scores
    subset=[experiment(row,reference) for row in originals[::3]];assert subset==baseline_scores[::3]
    extreme={**originals[0],**{f:1e6 for f in FIELDS},'name':'Synthetic outlier'}
    experiment(extreme,reference)
    assert [experiment(row,reference) for row in originals]==baseline_scores
    stats_source={f:{'present':sum(finite(row.get(f)) is not None for row in source['players']),
        'distribution':distribution(finite(row.get(f)) for row in source['players']),
        'tied_raw_groups':sum(n>1 for n in Counter(finite(row.get(f)) for row in source['players'] if finite(row.get(f)) is not None).values())} for f in FIELDS}
    old_maps=percentile_maps(source['players'],FIELDS)
    for f in FIELDS:
        groups=defaultdict(list)
        for i,row in enumerate(source['players']):
            v=finite(row.get(f))
            if v is not None:groups[v].append(old_maps[f][i])
        tied={v:xs for v,xs in groups.items() if len(xs)>1}
        worst=max(tied,key=lambda v:max(tied[v])-min(tied[v])) if tied else None
        stats_source[f].update({'tied_input_players':sum(len(xs) for xs in tied.values()),
            'worst_current_ordinal_tie_spread':max(tied[worst])-min(tied[worst]) if worst is not None else 0,
            'worst_tied_raw_value':worst})
    from nba_gm_data.draft import rookie_trait_records
    draft_traits=defaultdict(list)
    for t in canonical['draft_prospect_traits']:draft_traits[t['prospect_id']].append(t)
    projected=[]
    for p in canonical['draft_prospects']:
        records=rookie_trait_records({'id':p['id'],'position':p['position'],'source_ids':p['source_ids']},p,draft_traits[p['id']])
        projected.append({'id':p['id'],'name':p['name'],'position':p['position'],
            'draft_year':p['draft_year'],'values':{t['trait_key']:t['value'] for t in records if t['trait_key'] in KEYS}})
    (args.output/'existing_prospect_conversion.json').write_text(json.dumps(projected,indent=2)+'\n')
    generated_comparison={k:distribution(p['values'][k] for p in projected) for k in KEYS}
    conflicts=[]
    held_names={'Rudy Gobert','Scottie Barnes','Evan Mobley','Stephen Curry','Luka Dončić','Nick Richards','Isaiah Stewart','Clint Capela','Jay Huff','Brook Lopez','Myles Turner'}
    for p in output:
        if p['name'] in held_names:
            conflicts.append({'name':p['name'],'current':p['current'],
                'A_delta':{k:p['A_final'][k]-p['current'][k] for k in KEYS},
                'B_delta':{k:p['B_final'][k]-p['current'][k] for k in KEYS},
                'meaning':'Research HOLD/no justified replacement: offline counterfactual, NOT permission to erase reviewed judgment.'})
    summary={'version':VERSION,'players':len(output),'trait_rows':len(flat),'replayed_canonical_values_equal':True,
        'replayed_current_metadata_mismatches':metadata_mismatches,
        'source_row_count':len(source['players']),'original_source_matched_players':sum(p['source_available'] for p in output),
        'source_sha256':source_sha,'reference_sha256':hashlib.sha256((args.output/'fixed_reference.json').read_bytes()).hexdigest(),
        'stats':stats,'groups':grouped,'dependency':dependence,'source_coverage':stats_source,
        'reviewed_overrides_reapplied':dict(reapplied),'B_held_counts':dict(held),'extremes':extremes,'rank_changes':rank,
        'research_hold_conflicts':conflicts,
        'generated_scale_comparison':{'existing_prospects_converted':len(projected),'distributions':generated_comparison,
            'warning':'Existing pure conversion only, no new class/development. Imported fixed-reference channels and generated talent/archetype/ability anchors are not calibrated to one another.'},
        'roster_input_overlay':{'changed_fields':dict(Counter(f for p in output for f in p['roster_overlay_changes'])),
            'post_overlay_field_coverage':{f:sum(finite(row.get(f)) is not None for row in originals) for f in FIELDS},
            'preclip_changes_from_original_input_context':{k:sum(p['source_available'] and abs(p['pre_roster_initial'][k]['preclip']-p['initial'][k]['preclip'])>1e-9 for p in output) for k in KEYS},
            'note':'Official identity/physical overlay changes input heights/positions and thus percentile context BEFORE inference. Frozen candidate reference still uses original March source; differences are explicit, not new ability observations.'},
        'stability':{'repeat':True,'reordered_rows':True,'subset_membership':True,'outlier_added_without_refit':True,
            'current_percentile_tie_policy':'ordinal stable-sort; identical raw inputs can get distinct percentiles based on row order',
            'candidate_tie_policy':'same fixed-reference raw value -> same grade, with tail headroom'},
        'timing':{'phases_seconds':times,'candidate_per_player_total_seconds':sum(candidate_times),
            'total_offline_seconds_before_output_summary':time.perf_counter()-start},
        'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'decision':'Not accepted for production. A repairs headroom, not evidence. B separates channels but missing independent skill/rim opportunity evidence blocks a full five-trait candidate.',
        'pipeline_reports':reports}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('players','trait_rows','replayed_canonical_values_equal','original_source_matched_players','reviewed_overrides_reapplied','timing','peak_rss_bytes','decision')},indent=2))

if __name__=='__main__':main()
