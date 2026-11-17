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
    {id:2,label:'Wing',delta_pp:2.77,suppression_delta_pp:-.12,fg_pct:40.77,league_fg_pct:38},
  ],cells:[[52.5,250,1,.002,.003,.002],[80,250,2,.001,.002,.002]]}};
}
test('the fixed continuous scale distinguishes modest advantages from average and disadvantages',()=>{
  const s=fixture();
  const colors=[-3,-1.68,-.5,0,.5,.8,2.77,3].map(s.spatialEfficiencyColor);
  assert.equal(new Set(colors).size,colors.length);
  assert.equal(s.spatialEfficiencyColor(0),'#a8b3bd');
  assert.equal(s.spatialEfficiencyColor(-100),s.spatialEfficiencyColor(-8));
  assert.equal(s.spatialEfficiencyColor(100),s.spatialEfficiencyColor(8));
  assert.equal(s.spatialEfficiencyColor(NaN),s.spatialEfficiencyColor(0));
});
test('hex area is proportional to density between explicit floor and saturation caps',()=>{
  const s=fixture();
  const a=s.spatialHexRadius(.0005,.002),b=s.spatialHexRadius(.002,.002);
  assert.equal(b*b/(a*a),4);
  assert.equal(s.spatialHexRadius(100,.002),12);
  assert.equal(s.spatialHexRadius(0,.002),1.8);
  assert.ok(s.spatialHexRadius(.0018,.002)<s.spatialHexRadius(.0022,.002));
});
test('region values and density remain untouched; cells have no individual hover targets',()=>{
  const s=fixture(),p=profile(),before=JSON.stringify(p);
  const markup=s.spatialHeatmapMarkup(p,{compact:true});
  assert.equal(JSON.stringify(p),before);
  assert.equal((markup.match(/class="spatial-region-hit"/g)||[]).length,4);
  assert.match(markup,/Projected FG 60.8%, league 60.0%; \+0.8 pp vs league/);
  assert.match(markup,/Modeled defensive suppression; -1.2 pp vs league/);
  assert.match(markup,/pointer-events="none"/);
  assert.doesNotMatch(markup,/spatial-region-outline|<polygon[^>]+tabindex/);
  assert.match(markup,/Fixed continuous color scale: -8 to \+8/);
  assert.equal((markup.match(/class="spatial-key-stop"/g)||[]).length,10);
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
test('names are escaped, chart construction is deterministic, and no player-specific normalization is used',()=>{
  const s=fixture(),p=profile();p.shot_chart.regions[0].label='Rim <script>"';
  const markup=s.spatialHeatmapMarkup(p);
  assert.doesNotMatch(markup,/<script>/);
  assert.match(markup,/&lt;script>/);
  p.seed='another';
  assert.equal(s.spatialHeatmapRegions(p,'offense'),s.spatialHeatmapRegions({...p,seed:'first'},'offense'));
  const first=s.spatialHeatmapRegions(p,'offense');
  p.shot_chart.regions[1].delta_pp=100;
  const second=s.spatialHeatmapRegions(p,'offense');
  const firstFill=html=>html.match(/class="spatial-court-hex"[^>]+fill="([^"]+)"/)[1];
  assert.equal(firstFill(first),firstFill(second));
});
