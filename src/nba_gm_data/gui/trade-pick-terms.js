(() => {
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const picks = row => row?.payload?.picks || (row?.payload?.assets || []).filter(a=>a.kind==='pick');
  const eligible = pick => pick?.kind==='pick' && pick.terms_editable!==false && !pick.has_conditions && !pick.has_protection;
  const selected = rows => rows.flatMap(owner=>(owner.selected || []).filter(a=>a.kind==='pick').map(pick=>({owner,pick})));
  const primary = (rule,rows) => selected(rows).find(row=>row.pick.id===rule.pick_id);
  const recipient = (row,rows) => rows.find(r=>r.team===(row.owner.receiverFor?.(row.pick) ?? row.owner.recipient));
  const label = pick => `${pick.season} R${pick.round} ${pick.original_team_abbrev || pick.label || ''}`;
  const request = rules => (rules || []).filter(r=>r.enabled!==false).map(r=>({pick_id:r.pick_id,type:r.type,
    ...(r.type==='protected_pick'?{from:Number(r.from),through:Number(r.through),fallback_pick_ids:r.fallback_pick_ids || []}
      :{other_pick_id:r.other_pick_id || '',benefit:r.benefit || 'better'})}));
  function collateral(rule,rows) {
    const row=primary(rule,rows);
    if (!row) return [];
    const reserved=new Set(selected(rows).map(r=>r.pick.id));
    return picks(row.owner).filter(p=>eligible(p) && !reserved.has(p.id) && Number(p.round)===Number(row.pick.round)
      && Number(p.season)>=Number(row.pick.season)
      && !(p.season===row.pick.season && p.original_team_id && p.original_team_id===row.pick.original_team_id));
  }
  function swapChoices(rule,rows) {
    const row=primary(rule,rows);
    if (!row) return [];
    const reserved=new Set(selected(rows).map(r=>r.pick.id));
    return picks(recipient(row,rows)).filter(p=>eligible(p) && !reserved.has(p.id)
      && String(p.season)===String(row.pick.season) && Number(p.round)===Number(row.pick.round));
  }
  function errors(rules,rows) {
    const errors=[], reserved=new Set(selected(rows).map(r=>r.pick.id)), used=new Set();
    for (const rule of rules || []) {
      if (rule.enabled===false) continue;
      const row=primary(rule,rows), prefix=row?label(row.pick):'Draft condition';
      let problem='';
      if (!row || !eligible(row.pick)) problem='Choose an editable selected pick.';
      else if (used.has(rule.pick_id)) problem='This pick already has a condition.';
      else if (rule.type==='protected_pick') {
        const max=Number(row.pick.round)===1?30:60;
        if (!(Number(rule.from)>=1 && Number(rule.through)>=Number(rule.from) && Number(rule.through)<=max)) problem='Choose a valid protected range.';
        else if ((rule.fallback_pick_ids || []).length!==1 || !collateral(rule,rows).some(p=>p.id===rule.fallback_pick_ids[0])) problem='Choose a replacement pick.';
      } else if (rule.type==='pick_swap') {
        if (!recipient(row,rows)) problem='Choose a specific receiving team for a swap.';
        else if (!swapChoices(rule,rows).some(p=>p.id===rule.other_pick_id)) problem='Choose the other same-year, same-round pick.';
      } else problem='Choose a condition type.';
      used.add(rule.pick_id);
      const others=rule.type==='protected_pick'?rule.fallback_pick_ids || []:[rule.other_pick_id].filter(Boolean);
      if (others.some(id=>reserved.has(id))) problem='A pick cannot be committed to two parts of this package.';
      others.forEach(id=>reserved.add(id));
      if (problem) errors.push({key:rule.key,message:`${prefix}: ${problem}`});
    }
    return errors;
  }
  function markup(rows,rules=[]) {
    const choices=selected(rows).filter(r=>eligible(r.pick)), used=new Set(rules.map(r=>r.pick_id));
    const problems=errors(rules,rows);
    const select=(field,value,options,key,aria)=>`<select data-pick-field="${field}" data-pick-key="${esc(key)}" aria-label="${esc(aria)}">${options.map(([id,text,disabled])=>`<option value="${esc(id)}"${String(id)===String(value)?' selected':''}${disabled?' disabled':''}>${esc(text)}</option>`).join('')}</select>`;
    const numbers=(low,high)=>Array.from({length:high-low+1},(_,i)=>[low+i,`#${low+i}`]);
    return `<section class="trade-pick-terms" aria-label="Draft terms"><header><strong>Draft Terms</strong><button type="button" class="ui-command" data-pick-add${choices.some(r=>!used.has(r.pick.id))?'':' disabled'} title="Add a condition to a selected unencumbered pick"><img src="/assets/window-icons/plus.svg" alt="">Add condition</button></header>${rules.map(rule=>{
      const row=primary(rule,rows), other=row?recipient(row,rows):null;
      const max=Number(row?.pick.round)===1?30:60;
      const error=problems.find(e=>e.key===rule.key);
      const fallback=collateral(rule,rows), swaps=swapChoices(rule,rows);
      return `<div class="trade-pick-rule${rule.enabled===false?' is-disabled':''}" data-pick-rule="${esc(rule.key)}"><div class="trade-pick-rule-fields">
        <label class="trade-pick-enabled"><input type="checkbox" data-pick-field="enabled" data-pick-key="${esc(rule.key)}" aria-label="Apply this draft condition"${rule.enabled!==false?' checked':''}></label>
        <label><span>Pick</span>${select('pick_id',rule.pick_id,choices.map(r=>[r.pick.id,`${r.owner.team} · ${label(r.pick)}`,used.has(r.pick.id)&&r.pick.id!==rule.pick_id]),rule.key,'Primary pick')}</label>
        <label><span>Condition</span>${select('type',rule.type,[['protected_pick','Protected range'],['pick_swap','Swap right',!other]],rule.key,'Condition type')}</label>
        ${rule.type==='protected_pick'?`<label class="trade-protected-range"><span>Protected positions</span><div>${select('from',rule.from,numbers(1,max),rule.key,'Protected from position')}<span>through</span>${select('through',rule.through,numbers(Number(rule.from)||1,max),rule.key,'Protected through position')}</div></label><label><span>If protected, convey instead</span>${select('fallback',rule.fallback_pick_ids?.[0] || '',[['','Choose replacement pick'],...fallback.map(p=>[p.id,label(p)])],rule.key,'Replacement pick')}</label>`
          :`<label><span>${esc(other?.team || 'Receiving team')} gets</span>${select('benefit',rule.benefit,[['better','More favorable pick'],['worse','Less favorable pick']],rule.key,'Swap direction')}</label><label><span>Compared with</span>${select('other_pick_id',rule.other_pick_id || '',[['','Choose other pick'],...swaps.map(p=>[p.id,label(p)])],rule.key,'Other swap pick')}</label>`}
        <button type="button" class="ui-command trade-icon-button" data-pick-remove="${esc(rule.key)}" title="Remove condition" aria-label="Remove condition"><img src="/assets/window-icons/x.svg" alt=""></button>
      </div>${error?`<p class="trade-pick-rule-error" role="status">${esc(error.message)}</p>`:''}</div>`;
    }).join('')}</section>`;
  }
  function wire(root,rows,rules,onChange) {
    root.querySelector('[data-pick-add]')?.addEventListener('click',()=>{
      const row=selected(rows).find(r=>eligible(r.pick) && !rules.some(rule=>rule.pick_id===r.pick.id));
      if (!row) return;
      const next=structuredClone(rules), low=Number(row.pick.round)===1?1:31;
      next.push({key:`condition-${Math.max(0,...rules.map(r=>Number(String(r.key).split('-').at(-1))||0))+1}`,pick_id:row.pick.id,type:'protected_pick',from:low,through:low+3,fallback_pick_ids:[],enabled:true});
      onChange(next,{key:next.at(-1).key,field:'pick_id'});
    });
    root.querySelectorAll('[data-pick-remove]').forEach(button=>button.addEventListener('click',()=>{
      const next=rules.filter(r=>r.key!==button.dataset.pickRemove);
      onChange(next,next.length?{key:next[0].key,field:'pick_id'}:{add:true});
    }));
    root.querySelectorAll('[data-pick-field]').forEach(control=>control.addEventListener('change',()=>{
      const next=structuredClone(rules), rule=next.find(r=>r.key===control.dataset.pickKey);
      if (!rule) return;
      const field=control.dataset.pickField;
      if (field==='enabled') rule.enabled=control.checked;
      else if (field==='fallback') rule.fallback_pick_ids=control.value?[control.value]:[];
      else if (['from','through'].includes(field)) { rule[field]=Number(control.value); rule.through=Math.max(rule.from,rule.through); }
      else rule[field]=control.value;
      if (field==='pick_id') {
        const row=primary(rule,rows), low=Number(row?.pick.round)===1?1:31;
        Object.assign(rule,{from:low,through:low+3,fallback_pick_ids:[],other_pick_id:''});
      }
      onChange(next);
    }));
  }
  const prune=(rules,rows)=>(rules || []).filter(r=>primary(r,rows));
  window.TradePickTerms=Object.freeze({markup,wire,request,errors,prune,eligible});
})();
