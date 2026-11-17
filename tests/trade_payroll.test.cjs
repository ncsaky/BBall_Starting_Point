const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
const runtime=()=>{
  const scope={escapeHtml:value=>String(value),escapeAttr:value=>String(value),shortSeasonLabel:value=>value,money:value=>`$${Number(value).toFixed(1)}M`,clampNumber:(value,min,max)=>Math.max(min,Math.min(max,value))};
  vm.createContext(scope);
  vm.runInContext(source.slice(source.indexOf('function salaryHorizonChart('),source.indexOf('function playerHeadshotMarkup(')),scope);
  return scope;
};
test('ordinary payroll cards keep their original automatic tax-aware scale and contract tooltips',()=>{
  const s=runtime();
  const html=s.salaryHorizonChart({seasons:['2026-27'],rows:[{id:'p',name:'Player',salary_by_year:{'2026-27':100}}],capByYear:{'2026-27':{salary_total_millions:100,tax_line_millions:200,hard_cap_millions:240}}});
  assert.ok(html.includes(`height:${100/(240*1.06)*100}%`));
  assert.match(html,/\$100.0M · Player/);
  assert.match(html,/Tax<\/span><span>Hard cap/);
  assert.equal((html.match(/class="salary-horizon-year"/g)||[]).length,4);
});
test('before and after comparisons share one explicit scale and stable player colors',()=>{
  const s=runtime(),options={seasons:['2026-27'],scaleMaximum:400,colorPlayerIds:['a','b','c']};
  const before=s.salaryHorizonChart({...options,rows:[{id:'b',name:'Kept',salary_by_year:{'2026-27':100}}]});
  const after=s.salaryHorizonChart({...options,rows:[{id:'a',name:'Incoming',salary_by_year:{'2026-27':40}},{id:'b',name:'Kept',salary_by_year:{'2026-27':100}}]});
  assert.match(before,/height:25%/);assert.match(after,/height:35%/);
  for(const html of [before,after])assert.match(html,/salary-segment-1[^>]*height:[^"]+" title="\$100.0M · Kept"/);
});
