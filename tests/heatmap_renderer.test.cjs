const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const test=require('node:test');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
function fixture() {
  const scope={escapeHtml:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;'),escapeAttr:value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;')};
  vm.createContext(scope);
  vm.runInContext(source.slice(source.indexOf('function spatialEfficiencyColor('),source.indexOf('function seasonIdentityRadar(')),scope);
  return scope;
}
function profile() {
  return {seed:'fixed',zones:[{key:'rim'}],shot_chart:{basis:'projected',regions:[
    {id:1,label:'Rim',delta_pp:.8,suppression_delta_pp:-1.2,fg_pct:60.8,league_fg_pct:60},
    {id:12,label:'Center three',delta_pp:2.77,suppression_delta_pp:-.12,fg_pct:40.77,league_fg_pct:38},
  ],cells:[[52.5,250,1,.02,.03,.02],[80,250,1,.01,.02,.02],[340,250,12,.005,.002,.004]]}};
}
test('the colour scale runs red to neutral to blue on the league-relative score and saturates at the ends',()=>{
  const s=fixture();
  const colors=[-1,-.6,-.2,0,.2,.6,1].map(score=>s.spatialEfficiencyColor(score));
  assert.equal(new Set(colors).size,colors.length);
  assert.equal(s.spatialEfficiencyColor(0),'#b6bfc7');
  assert.equal(s.spatialEfficiencyColor(-100),s.spatialEfficiencyColor(-1));
  assert.equal(s.spatialEfficiencyColor(100),s.spatialEfficiencyColor(1));
  assert.equal(s.spatialEfficiencyColor(NaN),s.spatialEfficiencyColor(0));
  // A lighter wash of the same colour for whole-region fills.
  assert.notEqual(s.spatialEfficiencyColor(1,.45),s.spatialEfficiencyColor(1));
});
test('colour is relative to the league in that region: the typical value is neutral and the spread sets full colour',()=>{
  const s=fixture();
  const typical=vm.runInContext('SPATIAL_LEAGUE_REFERENCE.team.offense.mid[0]',s);
  assert.equal(typeof typical,'number');
  assert.equal(s.spatialRelativeScore(typical,1,'offense','team'),0);
  assert.equal(s.spatialRelativeScore(typical+100,1,'offense','team'),1);
  assert.equal(s.spatialRelativeScore(typical-100,1,'offense','team'),-1);
  assert.equal(s.spatialRelativeScore(null,1,'offense','team'),null);
  // Teams bunch together more than players, so the same gap is a stronger colour for a team.
  assert.ok(s.spatialRelativeScore(typical+1,1,'offense','team')>s.spatialRelativeScore(typical+1,1,'offense','player'));
});
test('hex area grows with volume up to four times the league average hex, then caps',()=>{
  const s=fixture();
  const a=s.spatialHexRadius(.001,.001),b=s.spatialHexRadius(.004,.001);
  assert.ok(Math.abs(b*b/(a*a)-4)<1e-9);
  assert.equal(s.spatialHexRadius(100,.001),s.spatialHexRadius(.004,.001));
  assert.equal(s.spatialHexRadius(0,.001),0);
});
test('fine cells pool into a few coarse hexes, and only spots with at least league-average volume are drawn',()=>{
  const s=fixture(),p=profile(),before=JSON.stringify(p);
  const markup=s.spatialHeatmapRegions(p,'offense');
  assert.equal(JSON.stringify(p),before);
  // Two rim cells pool into one hex; the low-volume three-point cell is below the league average hex and is not drawn.
  assert.equal((markup.match(/class="spatial-court-hex"/g)||[]).length,1);
  assert.equal((markup.match(/class="spatial-region-fill"/g)||[]).length,2);
  assert.equal((markup.match(/class="spatial-region-hit"/g)||[]).length,2);
  assert.match(markup,/Rim: 85\.7% of shots \(league 90\.9%\) · Projected FG 60\.8%, league 60\.0% · FG vs league: \+0\.8 pts \(typical player \+2\.9\)/);
  assert.match(markup,/pointer-events="none"/);
  assert.doesNotMatch(markup,/spatial-region-outline|<polygon[^>]+tabindex/);
});
test('region shapes match the engine regions: rings split by angle around the rim, corner threes as strips',()=>{
  const s=fixture();
  assert.match(s.spatialRegionGeometry(1),/^M132\.5 250\.0A80 80 0 1 1/);
  assert.match(s.spatialRegionGeometry(10),/^M-10 -10H142V30H-10Z$/);
  assert.match(s.spatialRegionGeometry(14),/^M-10 470H142V510H-10Z$/);
  assert.equal(s.spatialRegionGeometry(15),'');
});
test('team maps add an overall offense view; defense tabs read Overall, On-ball, Off-ball; legend is relative',()=>{
  const s=fixture(),p=profile();
  p.entity_type='team';p.shot_chart.views=['scoring','playmaking','defense','onball','help'];
  p.shot_chart.cells=p.shot_chart.cells.map(cell=>[...cell,.01,.01,.01]);
  p.shot_chart.regions=p.shot_chart.regions.map(region=>({...region,playmaking_delta_pp:.5,onball_delta_pp:-.6,help_delta_pp:-.6}));
  const markup=s.spatialHeatmapMarkup(p,{compact:true});
  const tabs=[...markup.matchAll(/data-court-tab="([^"]+)"[^>]*>([^<]+)</g)].map(match=>`${match[1]}:${match[2]}`);
  assert.deepEqual(tabs,['offense_total:Overall','offense:Scoring','playmaking:Playmaking','defense:Overall','onball:On-ball','help:Off-ball']);
  assert.match(markup,/<span class="spatial-court-group-label">Offense<\/span>/);
  assert.match(markup,/FG vs league, with playmaking: \+1\.3 pts/);
  assert.match(markup,/<em>Worse<\/em>[\s\S]*<em>Better<\/em>/);
  assert.doesNotMatch(markup,/Help<|On his man|On the ball/);
  delete p.entity_type;
  // Round 9: players get the Overall offense view too (his shooting plus his lift on teammates).
  assert.match(s.spatialHeatmapMarkup(p,{compact:true}),/data-court-tab="offense_total"/);
});
test('missing references are not displayed as average performance',()=>{
  const s=fixture(),p=profile();p.shot_chart.basis='unavailable';
  assert.equal(s.spatialHeatmapRegions(p,'offense'),'');
  assert.match(s.spatialHeatmapMarkup(p),/Shot reference unavailable/);
  p.shot_chart.basis='projected';p.shot_chart.regions[0].delta_pp=null;
  const markup=s.spatialHeatmapRegions(p,'offense');
  assert.match(markup,/Comparison unavailable/);
  assert.doesNotMatch(markup,/NaN|undefined/);
});
test('names are escaped and chart construction is deterministic',()=>{
  const s=fixture(),p=profile();p.shot_chart.regions[0].label='Rim <script>"';
  const markup=s.spatialHeatmapMarkup(p);
  assert.doesNotMatch(markup,/<script>/);
  assert.match(markup,/&lt;script>/);
  p.seed='another';
  assert.equal(s.spatialHeatmapRegions(p,'offense'),s.spatialHeatmapRegions({...p,seed:'first'},'offense'));
});
