"""Prespecified source/control contrasts; never selected by observed ordering."""
from .fixtures import overlay,ACTORS,IDS


def sensitivities(p):
    for actor in ('turner','towns','holmgren'):
        for value in (40,85):
            yield actor+'_unknown_receiving_'+str(value),actor,overlay(p,'unknown_receiving_'+str(value),{actor:{'S14':value}}),{}
    for actor,key,ends,kw in [('holmgren','S08',(35,60),{'coverage':'stay'}),('towns','S01',(82,95),{}),('turner','S26',(60,85),{'coverage':'stay'})]:
        for value in ends:
            yield actor+'_'+key+'_'+str(value),actor,overlay(p,'source_range_'+str(value),{actor:{key:value}},kind='source_range'),kw
    # Shared motion shifts both offense and defense; do not label it a measured
    # athlete-only speed effect or simultaneously maximize all player abilities.
    for name,values in [('slow',(2.5,5.5,2.2)),('fast',(3.5,6.5,2.8))]:
        changes={a:dict(zip(('P05','P06','P07'),values)) for a in ('turner','towns','holmgren','jokic','curry','white','castle','barnes','wemb')}
        yield 'common_motion_'+name,'turner',overlay(p,'common_motion_'+name,changes),{}
    for value in (50,85):
        yield 'holmgren_closeout_'+str(value),'holmgren',overlay(p,'closeout_'+str(value),{'wemb':{'S40':value}}),{'coverage':'stay'}


def export_inputs(p):
    return {'source_packet_sha256':p.get('final_packet_sha256',None),'original_screen_pop_packet_sha256':'161b9d9e0761699e9f2358a0a020494b62aca0580639926ae40c42ad86ba7ee2',
        'source_documents':p['source_documents'],'operational_documents':{pid:v.to_dict() for pid,v in p['views'].items()},
        'completion_ledger':p['completion_ledger'],'overrides':p['overrides'],
        'synthetic_reference_id':IDS['nonspacing'],'synthetic_reference_policy':'all synthetic, not a named source grade',
        'H1_control_prerequisites':['P01 stored cm','P02 stored cm'],'H1_rule':'P01+70+0.5*(P02-P01); hypothetical standing reach, not measured; no extra body bonus',
        'roles':'four source actors: offense+interaction+pop screener only; full interior/coverage/post roles not asserted'}
