from pathlib import Path
import json,gzip,copy
from nba_gm_data.save import player_attribute_summary,player_display_attribute_summary
from nba_gm_data.sim import player_feature_vector,invalidate_sim_cache
R=Path('docs/ratings-evidence-2026-10-29');A=R/'probe_artifacts'
p=A/'next_batch_frozen_20261110.json';z=p.with_suffix('.json.gz')
if p.exists():z.write_bytes(gzip.compress(p.read_bytes()));p.unlink()
c=json.loads(gzip.decompress(z.read_bytes()));s=json.loads((A/'next_batch_snapshot_20261110.json').read_text())
raw="""Desmond Bane|SG|00:52–00:58|Movement/pull-up shooting and passing; pressure/switches reduce separation and finishing|Versatility54.93 below Brown62.10 undercredits repertoire, without requiring stronger handle/rim pressure. Increase.
Franz Wagner|SF|00:51:23–00:56:54|Drive/pass, size, transition and on-ball defense; health and playoff jumper uncertainty|DEF80 exceeds Brown75.8, range70.84 exceeds Barnes58.06 but trails Bane74.25. Hold: broad defense and intermediate shooting are a plausible ordering; small health-sensitive playoff sample cannot dictate shooting.
Scottie Barnes|PF|01:10–01:17:38|Passing, cutting, boards and versatile defense; inconsistent threes and lead scoring ceiling|Passing81.55 above Franz74.40 and range58.06 below him fit a connector. Hold; rim90.32 belongs in shared helper calibration audit.
Luka Doncic|PG|01:27:17–01:37:18|Elite physical creation and passing; settling/rim-access decline, defensive targeting, availability|Passing95 exceeds SGA85.43/Curry82.62 while effort42 trails both. Hold/mechanic issue: relative OVR is not solved by another passing buff.
Stephen Curry|PG|01:11:36–01:25:46|Shooting gravity and transformative offense; age/availability projection|Range99/release98 exceed SGA70/72; effort68.47 below SGA72. Hold/mechanic issue: assess teammate benefit rather than capped shooting or a healthy-skill age penalty.
Shai Gilgeous-Alexander|PG|01:30:53–01:43:34|Controlled creation, rim/FT pressure and positive defense; playoff loading and off-ball/three volume growth|Handle91.25/rim88 exceed Curry84/62; navigation68 below White83.29. Hold: do not import forecast off-ball growth. DEF below Curry is a weighting question, not proof of a missing subskill.
Cooper Flagg|SF|01:03:29–01:15:15|Passing, connective two-way play, touch; inefficient jumper and unproven projected sophomore leap|Passing77.92 above Franz74.40, range56.39 below Barnes58.06. Hold: already advanced young connector; no current-skill increase from forecast.
Derrick White|SG|01:34–01:44|Anticipation, guard rim help and decisions; poor recent shooting, limited inside creation|Rim58 below Castle76.96 conflicts with stronger help-defense account; navigation83.29 above Castle78.38. Hold White; correct Castle shape first. Shooting rebound remains projection.
Cason Wallace|SG|01:08–01:13:30|Elite hands/POA, catch shots, cuts; lead creation and shooting ceiling disputed|Effort97.11/navigation96.01 exceed White85.56/83.29, handle58.24 below Castle63.72. Mechanic referral: shared activity/navigation proxies warrant joint audit, not an isolated rank-based cut.
Austin Reaves|SG|01:23:51–01:34|PnR/isolation, foul drawing, floater, passing; pressure, athletic separation, turnovers and targeting|Versatility51.28 below Bane54.93 despite stronger on-ball account; rim65.92 below Herro85.95 despite explicit driving comparison. Increase repertoire; retain playoff/defense limits.
Tyler Herro|SG|00:25–00:30|Volume jumper and regular-season creation; screen dependence, switching pressure and defensive targeting|Rim85.95 near SGA88 and above Reaves65.92/Garland64.04, handle84.47 also above both. Decrease downhill/pressure creation; preserve shooting. Miami history is not current Milwaukee role.
Paolo Banchero|PF|00:09:56–00:16:19|Physical mismatch/FT creation; erratic jumper, traffic decisions, turnovers and focus/defense|Rim deterrence84.14 above Franz76.92 despite weaker defensive account; passing76.26 above Franz74.40 despite merely okay passing. Rebalance help/reads; retain physical rim pressure.
Jonathan Kuminga|TEAM|02:18:10–02:20|Athletic transition/finishing flashes; shooting, decisions, focus and unstable small sample|Handle58.92/range54.88 below Brown71.85/75.34 prevent lead creation; passing65.62 remains modest. Hold: broad focus concern needs sustained role evidence rather than one opening-week half.
Jaylen Brown|SF|01:21:58–01:30:18|Physical creation, transition, on-ball defense, intermediate growth; turnovers and below-average lead passing/team awareness|Passing74.74 slightly above Franz74.40 and only6.16 below Durant80.90 underdistinguishes score-first wing from connectors. Decrease reads; preserve physical scoring.
Kevin Durant|SF|01:26:30–01:31:24|Efficient scalable shooting/spacing; blitz handling, turnovers and missing organizer|Handle78.60 above Reaves75.17/Garland72.91 conflicts with pressure critique. Reduce handling, preserve shooting; organizer interaction is a separate mechanic.
Stephon Castle|PG|00:14:56–00:22:05|Elite POA assignments, strength, cutting/boards; turnovers, intermediate scoring and weak help/rim disruption|Rim76.96 above White58/Cason61.12 while effort79.44 below both. Move defensive value toward containment, away from helper/rim role.
Darius Garland|PG|00:22:05–00:29:26|Elite handle/change of pace, PnR, passing and on/off-ball threes; size defense, health, FT/rim and playoff pressure limits|Handle72.91 below Reaves75.17/Herro84.47 conflicts with specific handle praise. Increase healthy handle; retain rim64.04 and effort50.98.
Rudy Gobert|C|00:51:38–00:59:07|Elite rim anchor and defensive consistency; very limited playoff scoring/FT offense|Rim99.01 vs Allen96.82 both saturate99; OFF57.5 below Kessler58.2. Hold/mechanic issue: evaluate feeder/screen/spacing context, not fictitious shooting or self-creation.
Walker Kessler|C|00:08:12–00:10:48|Rim/boards, screens/lobs, finishing; slow feet, coverage flexibility, health and limited scoring|Rim97.43 near Allen96.82, navigation68.12 near Allen69.21, handle47.45 below Allen54.38. Hold: narrower scoring/coverage profile is defensible; spacing flashes do not establish a shooter.
Jarrett Allen|C|00:03:08–00:04:48|Reliable rim/boards and complementary finishing; limited offensive upside and matchup flexibility|OFF55.4 below Kessler58.2 with lower rim pressure57.82 vs63.49 but higher handle54.38. Hold/mechanic issue: compare actual finishing with feeders before lifting specialist offense."""
files={'SG':'SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md','SF':'SMALL_FORWARDS_FULL_EXTRACTION.md','PF':'POWER_FORWARD_FULL_EXTRACTION.md','PG':'POINT_GUARDS_FULL_EXTRACTION.md','TEAM':'TEAM_RANKING_FULL_EXTRACTION.md','C':'EPISODE_4_CENTERS_EXTRACTION.md'}
dates={'SG':'2026-08-14','SF':'2026-08-19','PF':'2026-08-28','PG':'2026-08-05','TEAM':'2026-10-07','C':'2026-09-02'}
changes={'Desmond Bane':{'shot_versatility':5},'Austin Reaves':{'shot_versatility':6},'Tyler Herro':{'rim_pressure':-12,'handle_pressure':-5},'Paolo Banchero':{'rim_deterrence':-12,'passing_reads':-4},'Jaylen Brown':{'passing_reads':-6},'Kevin Durant':{'handle_pressure':-6},'Stephon Castle':{'rim_deterrence':-15,'defensive_effort':6},'Darius Garland':{'handle_pressure':6}}
head=f"""# Next rating batch review — 2026-11-10

Twenty additional players screened; eight concrete next implementation candidates. The backend-owned five are excluded. These are provisional scouting recommendations for coordinator review.

## Broad findings

Herro behaves too much like an elite downhill creator relative to Reaves and Garland. Castle receives too much defensive value from helping at the rim rather than containing guards. Brown's reads sit too close to connective forwards. Durant should find pressure harder without losing shooting value. Bane/Reaves need more scoring repertoire; Garland needs better ball control. The other twelve receive comparative holds or mechanic referrals, not an assertion that every current number is accurate.

Prioritize Castle, Herro, Brown and Garland, then Bane/Reaves and Durant. Paolo is lower confidence because physical tools/creation load provide substantial counterevidence; approve its subparts separately. This is eight proposed changes, not a quota for twenty.

## Frozen source and interpretation

Version {s['version']}; starting SHA-256 {s['sha256']}. The [compressed canonical copy](probe_artifacts/next_batch_frozen_20261110.json.gz) freezes the starting state before concurrent backend five-player changes. [Exact20-player traits/provenance](probe_artifacts/next_batch_snapshot_20261110.json), [private runner](probe_artifacts/next_batch_review_20261110.py) and [full recomputations](probe_artifacts/next_batch_recomputations_20261110.json) preserve the comparison. Rebase against later versions before implementation.

Game start is October20,2026. Current data mix March skill inputs, June subjective priors, preserved baseline values and later roster/stat/profile updates; they are not uniformly July. The [source-refresh dry run](../IMPORTED_RATING_REFRESH_PREVIEW_2026_11_09.md) changed no final traits for its five players; this result is not generalized to these twenty.

All tuples below are OVR/OFF/DEF: engine first, then presentation crosswalk. These are fixed-canonical-minute calculations, not observed runtime player-card responses. Saved rotation can change OVR. No save or simulation was used. All scouting is dated, transcript-only, with unidentified turns, resolved aliases and disagreements retained. No podcast rank becomes an OVR target; repeated same-host opinions are not independent evidence. Availability and future promise remain distinct from healthy current skill.

## Evidence table

V=shot versatility, H=handle pressure, P=passing reads, R=rim pressure, E=effort, N=navigation, B=rim deterrence. These are raw traits; all15 exact values are retained in the snapshot.

| Player / stable ID | Engine; presentation | Relevant traits | Dated strengths and weaknesses | Comparison / disposition |
|---|---|---|---|---|
"""
for line in raw.splitlines():
 n,k,t,ev,verdict=line.split('|');b=s['players'][n];tv={a['trait_key']:a['value'] for a in b['traits']}
 e='/'.join(str(b['engine'][a]) for a in ['overall','offense','defense']);d='/'.join(str(b['display'][a]) for a in ['overall','offense','defense'])
 v=', '.join(f'{a}={tv[q]}' for a,q in [('V','shot_versatility'),('H','handle_pressure'),('P','passing_reads'),('R','rim_pressure'),('E','defensive_effort'),('N','screen_navigation'),('B','rim_deterrence')])
 head+=f'| {n}: {b["player"]["id"]} | {e}; **{d}** | {v} | [{dates[k]}, {t}]({files[k]}): {ev}. | {verdict} |\n'
head+="\n## Eight proposed corrections: actual private production-function results\n\nConfidence: medium on direction, low–medium on exact size; Paolo low–medium overall. Targets are explicit estimates, not statistically identified optima. A reasonable review band is target ±2 trait points for each listed subpart; only preferred targets are recomputed. All other traits/minutes/health/profile anchors remain fixed.\n\n| Player | Exact targets and deltas | Engine after; presentation after | Measured cross-category effects |\n|---|---|---|---|\n"
out={}
for n,ds in changes.items():
 u=copy.deepcopy(c);b=s['players'][n];pid=b['player']['id'];p=next(p for p in u['players'] if p['id']==pid);targets={}
 for t in u['traits']:
  if t['player_id']==pid and t['trait_key'] in ds:t['value']=round(t['value']+ds[t['trait_key']],2);targets[t['trait_key']]=t['value']
 e=player_attribute_summary(u,pid);d=player_display_attribute_summary(u,pid);f=player_feature_vector(u,p).features
 diff={k:{'before':b['features'].get(k),'after':v} for k,v in f.items() if b['features'].get(k)!=v}
 out[n]={'deltas':ds,'targets':targets,'engine':e,'display':d,'changed_features':diff}
 spill=[]
 for k in ['impact','usage','scoring_usage','passing','defensive_events','rim_deterrence','assisted_finishing']:
  if k in diff:spill.append(f'{k}: {diff[k]["before"]}→{diff[k]["after"]}')
 for k in ['rebounding','block','steal']:
  if b['engine'][k]!=e[k]:spill.append(f'engine {k}: {b["engine"][k]}→{e[k]}')
 head+=f'| {n} | '+ '; '.join(f'{k} {ds[k]:+g} → {v}' for k,v in targets.items())+' | '+'/'.join(str(e[k]) for k in ['overall','offense','defense'])+'; **'+'/'.join(str(d[k]) for k in ['overall','offense','defense'])+'** | '+'; '.join(spill)+' |\n'
 invalidate_sim_cache(u)
(A/'next_batch_recomputations_20261110.json').write_text(json.dumps(out,indent=2))
(R/'NEXT_RATING_BATCH_REVIEW.md').write_text(head)
print('records',len(raw.splitlines()),'shortlist',len(out),s['sha256'])
