// Published wants use backend matching; this file only edits and presents them.
const WANT_LABELS = {overall:'OVR',offense:'OFF',defense:'DEF',height_inches:'Height (in)',age:'Age',
  upside_remaining:'Upside',health_risk:'Injury risk',salary_millions:'Salary ($M)',contract_years:'Contract years',
  shooting:'Shooting',creation:'Creation',spacing:'Spacing',passing:'Passing',rebounding:'Rebounding',
  rim_deterrence:'Rim protection',athleticism:'Athleticism',release:'Release',range:'Range',handle:'Handle',
  rim_pressure:'Rim pressure',def_effort:'Defensive effort',screen_nav:'Screen navigation',
  lateral_agility:'Lateral agility',stamina:'Stamina',iq:'IQ'};

function wantDescription(want, roster=[]) {
  if(want.kind==='picks') {
    const years=want.draft_years?.length?` (${want.draft_years[0]}–${want.draft_years.at(-1)})`:'';
    return `${want.quality==='premium'?'Premium ':''}R${want.round} picks · next ${want.from}–${want.through} drafts${years} · ${want.protection==='unprotected'?'unprotected':want.protection==='light'?'top-4 or less protected':'any protection'}`;
  }
  const target=want.target_name || roster.find(row=>row.id===want.target_player_id)?.name || 'former roster player';
  const prefix=want.kind==='upgrade'?`Upgrade over ${target}${want.active===false?' · inactive':''}`:(want.positions||[]).join('/') || 'Players';
  const criteria=(want.conditions||[]).map(c=>`${WANT_LABELS[c.field] || c.field} ${c.op} ${c.value}`).join(' · ');
  return `${prefix}${criteria?` · ${criteria}`:''}`;
}

function teamWantsCurrent(fallback) {
  const team=state.wantsTeam || teamLabel(fallback?.team || state.dashboardTeam || userTeam());
  const cached=state.wantsRead;
  if(cached?.save===state.currentSave && cached.team===team) return cached.payload;
  if(team===teamLabel(fallback?.team || '')) return fallback?.wants;
  return null;
}

function teamWantsMarkup(assets) {
  const team=state.wantsTeam || teamLabel(assets?.team || state.dashboardTeam || userTeam());
  const payload=teamWantsCurrent(assets), editable=team===userTeam();
  return `<div class="team-wants-toolbar"><select data-wants-team aria-label="Team wants">${(state.teams||[]).map(t=>`<option value="${escapeAttr(t.abbrev)}" ${t.abbrev===team?'selected':''}>${escapeHtml(t.abbrev)}</option>`).join('')}</select>${editable?`<button type="button" class="ui-command wants-command" data-want-add ${payload?.entries?.length>=6?'disabled':''}><img src="/assets/window-icons/plus.svg" alt=""> Add</button>`:''}</div><div class="team-wants-list">${payload?(payload.entries||[]).map((want,index)=>`<div class="team-want-row ${want.active===false?'is-inactive':''}"><span class="team-want-priority">${index+1}</span><span class="team-want-description" title="${escapeAttr(want.reason || wantDescription(want,payload.roster))}">${escapeHtml(wantDescription(want,payload.roster))}</span>${editable?`<div class="team-want-actions"><button type="button" class="ui-command wants-command" data-want-move="${index}" data-step="-1" title="Higher priority" aria-label="Move want ${index+1} up" ${index===0?'disabled':''}>↑</button><button type="button" class="ui-command wants-command" data-want-move="${index}" data-step="1" title="Lower priority" aria-label="Move want ${index+1} down" ${index===payload.entries.length-1?'disabled':''}>↓</button><button type="button" class="ui-command wants-command" data-want-edit="${index}" title="Edit want" aria-label="Edit want ${index+1}">Edit</button><button type="button" class="ui-command wants-command" data-want-remove="${index}" title="Remove want" aria-label="Remove want ${index+1}"><img src="/assets/window-icons/x.svg" alt=""></button></div>`:''}</div>`).join('') || `<div class="team-wants-empty">${editable?'No published wants.':'No current wants.'}</div>`:'<div class="team-wants-empty" role="status">Loading wants…</div>'}</div>`;
}

async function readTeamWants(team=state.wantsTeam || userTeam()) {
  const save=state.currentSave;
  const payload=await action('team_wants',{...savePayload(),team});
  if(state.currentSave!==save)return null;
  state.wantsRead={save,team,payload};
  return payload;
}

async function saveTeamWants(entries, revision) {
  const save=state.currentSave;
  const payload=await action('set_team_wants',{...savePayload(),team:userTeam(),entries,revision});
  if(save!==state.currentSave)throw new Error('The previous save was updated; the active save has changed.');
  state.wantsRead={save:state.currentSave,team:userTeam(),payload};
  state.wantsTeam=userTeam();
  state.data.assetsDesktop=null;
  await loadAssetsDesktop();
  refreshAssetsSurface();
  return payload;
}

function wireTeamWants(root, assets) {
  const surface=root.matches?.('.assets-wants')?root:root.querySelector('.assets-wants');
  if(!surface)return;
  const redraw=()=>{surface.querySelector('.assets-panel-body').innerHTML=teamWantsMarkup(assets);wireTeamWants(surface,assets);window.CardBoard?.fitContent?.('team-wants');};
  surface.querySelector('[data-wants-team]')?.addEventListener('change',async event=>{
    state.wantsTeam=event.target.value;
    try {await readTeamWants(state.wantsTeam);redraw();} catch(error){showToast(error.message,true);}
  });
  surface.querySelector('[data-want-add]')?.addEventListener('click',()=>openWantEditor().catch(error=>showToast(error.message,true)));
  surface.querySelectorAll('[data-want-edit]').forEach(button=>button.onclick=()=>openWantEditor(Number(button.dataset.wantEdit)).catch(error=>showToast(error.message,true)));
  surface.querySelectorAll('[data-want-remove],[data-want-move]').forEach(button=>button.onclick=async()=>{
    try {
      const payload=teamWantsCurrent(assets), rows=structuredClone(payload.entries);
      if(button.dataset.wantRemove!==undefined) rows.splice(Number(button.dataset.wantRemove),1);
      else {const i=Number(button.dataset.wantMove), j=i+Number(button.dataset.step);[rows[i],rows[j]]=[rows[j],rows[i]];}
      await saveTeamWants(rows,payload.revision);
    }catch(error){showToast(error.message,true);}
  });
  if(!teamWantsCurrent(assets) && !state.wantsReading) {
    state.wantsReading=true;
    readTeamWants(state.wantsTeam || userTeam()).then(()=>{if(surface.isConnected)redraw();}).catch(error=>showToast(error.message,true)).finally(()=>{state.wantsReading=false;});
  }
}

function wantPreset(kind, payload) {
  const base={id:`want_${globalThis.crypto?.randomUUID?.() || Date.now()}`,kind:'player',positions:[],conditions:[]};
  if(kind.startsWith('suggestion:'))return {...structuredClone(payload.suggestions[Number(kind.split(':')[1])]),id:base.id};
  if(kind==='picks')return {id:base.id,kind:'picks',round:1,from:1,through:3,protection:'any',quality:'any'};
  if(kind==='upgrade')return {...base,kind:'upgrade',target_player_id:payload.roster?.[0]?.id || ''};
  if(kind==='youth')base.conditions=[{field:'age',op:'<=',value:23},{field:'overall',op:'>=',value:75},{field:'upside_remaining',op:'>=',value:1}];
  if(kind==='rotation')base.conditions=[{field:'overall',op:'>=',value:78}];
  return base;
}

async function openWantEditor(index=null) {
  const save=state.currentSave;
  const payload=await readTeamWants(userTeam());
  if(!payload || save!==state.currentSave)return;
  state.wantEditor={payload,index,draft:structuredClone(index===null?wantPreset('player',payload):payload.entries[index])};
  renderWantEditor();
}

function renderWantEditor() {
  state.modal={kind:'teamWants',title:state.wantEditor.index===null?'Add Team Want':'Edit Team Want',body:wantEditorMarkup()};
  renderModal();
}

function wantEditorMarkup() {
  const {draft:w,payload}=state.wantEditor;
  const option=(value,label,selected)=>`<option value="${escapeAttr(value)}" ${selected?'selected':''}>${escapeHtml(label)}</option>`;
  const pick=w.kind==='picks';
  return `<form class="want-editor" data-want-form><label>Profile<select data-want-preset>${[['player','Player profile'],['youth','Young upside'],['rotation','Rotation help'],['upgrade','Upgrade a player'],['picks','Draft capital']].map(([key,label])=>option(key,label,key===w.kind)).join('')}${(payload.suggestions||[]).map((row,i)=>option(`suggestion:${i}`,`Suggested: ${wantDescription(row,payload.roster)}`,false)).join('')}</select></label>
    ${pick?`<div class="want-pick-fields"><label>Round<select data-want-prop="round">${[1,2].map(n=>option(n,`Round ${n}`,w.round===n)).join('')}</select></label><label>From draft<select data-want-prop="from">${Array.from({length:7},(_,i)=>option(i+1,`Next ${i+1}`,w.from===i+1)).join('')}</select></label><label>Through draft<select data-want-prop="through">${Array.from({length:7},(_,i)=>option(i+1,`Next ${i+1}`,w.through===i+1)).join('')}</select></label><label>Protection<select data-want-prop="protection">${[['any','Any'],['light','Top-4 or less'],['unprotected','Unprotected only']].map(([key,label])=>option(key,label,w.protection===key)).join('')}</select></label><label>Quality<select data-want-prop="quality">${[['any','Any'],['premium','Premium']].map(([key,label])=>option(key,label,w.quality===key)).join('')}</select></label></div>`:`${w.kind==='upgrade'?`<label>Upgrade over<select data-want-prop="target_player_id">${!payload.roster.some(p=>p.id===w.target_player_id)?option(w.target_player_id,'Former roster player · inactive',true):''}${payload.roster.map(p=>option(p.id,`${p.name} · ${p.position || ''}`,w.target_player_id===p.id)).join('')}</select></label>`:''}<fieldset class="want-positions"><legend>Positions</legend>${['PG','SG','SF','PF','C'].map(pos=>`<label><input type="checkbox" data-want-position="${pos}" ${(w.positions||[]).includes(pos)?'checked':''}>${pos}</label>`).join('')}</fieldset><div class="want-conditions">${(w.conditions||[]).map((c,i)=>`<div class="want-condition" data-want-condition="${i}"><select data-condition-field aria-label="Condition ${i+1} attribute">${Object.entries(WANT_LABELS).map(([key,label])=>option(key,label,c.field===key)).join('')}</select><select data-condition-op aria-label="Condition ${i+1} comparison">${['>=','>','<=','<','='].map(op=>option(op,op,c.op===op)).join('')}</select><input type="number" data-condition-value aria-label="Condition ${i+1} value" value="${escapeAttr(c.value)}" step="0.1" required><button type="button" class="ui-command wants-command" data-condition-remove="${i}" aria-label="Remove condition ${i+1}" title="Remove condition"><img src="/assets/window-icons/x.svg" alt=""></button></div>`).join('')}</div><button type="button" class="ui-command wants-command" data-condition-add ${(w.conditions||[]).length>=8?'disabled':''}><img src="/assets/window-icons/plus.svg" alt="">Condition</button>`}
    <div class="want-editor-footer"><span role="alert" data-want-error></span><button type="submit" class="ui-command wants-command">Publish</button></div></form>`;
}

function wireWantModal(root) {
  const form=root.querySelector('[data-want-form]');
  if(form) {
    const {draft,payload}=state.wantEditor;
    form.querySelector('[data-want-preset]').onchange=e=>{state.wantEditor.draft=wantPreset(e.target.value,payload);renderWantEditor();};
    form.querySelectorAll('[data-want-prop]').forEach(input=>input.onchange=()=>{draft[input.dataset.wantProp]=['round','from','through'].includes(input.dataset.wantProp)?Number(input.value):input.value;});
    form.querySelectorAll('[data-want-position]').forEach(input=>input.onchange=()=>{draft.positions=[...form.querySelectorAll('[data-want-position]:checked')].map(el=>el.dataset.wantPosition);});
    form.querySelectorAll('[data-want-condition]').forEach(row=>{
      const c=draft.conditions[Number(row.dataset.wantCondition)];
      row.querySelector('[data-condition-field]').onchange=e=>{c.field=e.target.value;};
      row.querySelector('[data-condition-op]').onchange=e=>{c.op=e.target.value;};
      row.querySelector('[data-condition-value]').oninput=e=>{c.value=e.target.value===''?null:Number(e.target.value);};
    });
    form.querySelector('[data-condition-add]')?.addEventListener('click',()=>{draft.conditions.push({field:'overall',op:'>=',value:75});renderWantEditor();});
    form.querySelectorAll('[data-condition-remove]').forEach(button=>button.onclick=()=>{draft.conditions.splice(Number(button.dataset.conditionRemove),1);renderWantEditor();});
    form.onsubmit=async event=>{
      event.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
      try {const rows=structuredClone(payload.entries);if(state.wantEditor.index===null)rows.push(draft);else rows[state.wantEditor.index]=draft;await saveTeamWants(rows,payload.revision);closeModal();}
      catch(error){form.querySelector('[data-want-error]').textContent=error.message;button.disabled=false;}
    };
  }
  root.querySelector('[data-wants-keep]')?.addEventListener('click',()=>dismissWantReminder(false));
  root.querySelector('[data-wants-review]')?.addEventListener('click',()=>dismissWantReminder(true));
}

async function maybeShowWantReminder() {
  if(!state.currentSave || state.view!=='dashboard' || state.hydrating || state.simulationRunning || state.draftPlaybackRunning || state.modal || state.tutorial || state.wantsReminderReading)return;
  state.wantsReminderReading=true;
  try {
    const payload=await readTeamWants(userTeam());
    if(!payload?.reminder?.length || state.modal || state.simulationRunning || state.draftPlaybackRunning)return;
    if(state.wantsReminderShown===`${state.currentSave}:${payload.reminder_token}`)return;
    state.wantsReminderShown=`${state.currentSave}:${payload.reminder_token}`;
    state.wantReminder={...payload,saveId:state.currentSave};
    state.modal={kind:'teamWants',title:'Acquisitions Match Your Wants',body:`<section class="want-reminder"><ul>${payload.reminder.map(row=>`<li>${escapeHtml(row.name)}${row.matches.some(m=>m.status==='exact')?'':' · near match'}</li>`).join('')}</ul><div><button type="button" class="ui-command wants-command" data-wants-review>Review Wants</button><button type="button" class="ui-command wants-command" data-wants-keep>Keep</button></div></section>`};
    renderModal();
  }catch(error){console.warn('Wants reminder:',error.message);}finally{state.wantsReminderReading=false;}
}

async function dismissWantReminder(review) {
  try {
    const payload=state.wantReminder;
    if(!payload || payload.saveId!==state.currentSave)return;
    await action('acknowledge_team_wants',{...savePayload(),team:userTeam(),revision:payload.revision,reminder_token:payload.reminder_token});
    state.wantReminder=null;
    closeModal();
    if(review){state.wantsTeam=userTeam();await readTeamWants();state.view='dashboard';renderDashboard();window.CardBoard?.open('team-wants');}
  }catch(error){showToast(error.message,true);}
}

function acknowledgeClosedWantReminder() {
  if(state.modal?.kind!=='teamWants' || !state.wantReminder || state.modal.title!=='Acquisitions Match Your Wants')return;
  const payload=state.wantReminder;state.wantReminder=null;
  if(payload.saveId!==state.currentSave)return;
  action('acknowledge_team_wants',{...savePayload(),team:userTeam(),revision:payload.revision,reminder_token:payload.reminder_token}).catch(error=>showToast(error.message,true));
}

function tradeWantsStrip(payload) {
  const wants=payload?.wants;
  if(!wants?.entries?.length)return '';
  return `<div class="trade-wants-strip"><strong>${escapeHtml(teamLabel(payload.team))} wants</strong><span>${wants.entries.filter(w=>w.active!==false).map(w=>escapeHtml(wantDescription(w,wants.roster))).join(' / ')}</span></div>`;
}

function tradeWantsOfferSummary(candidate) {
  const matches=candidate?.wants_matches || [];
  if(!matches.length)return '';
  const teams=[...new Set(matches.map(row=>row.team_id))];
  return `<div class="trade-wants-strip">${teams.map(team=>{
    const rows=matches.filter(row=>row.team_id===team);
    const exact=new Set(rows.filter(row=>row.status==='exact').map(row=>row.asset_id)).size;
    const near=new Set(rows.filter(row=>row.status==='near' && !rows.some(m=>m.asset_id===row.asset_id && m.status==='exact')).map(row=>row.asset_id)).size;
    return `<span>${escapeHtml(teamLabel(team))}: ${exact?`${exact} want match${exact===1?'':'es'}`:''}${exact&&near?' · ':''}${near?`${near} near match${near===1?'':'es'}`:''}</span>`;
  }).join('')}</div>`;
}
