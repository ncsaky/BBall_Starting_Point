// Two desktops share dashboard data; only asset valuations need an extra read.
let assetsRead = null;
let assetsBlockTimer = 0;
let assetsBlockRemaining = 8000;
function assetsContextKey() {
  return [state.currentSave, state.dashboardRevision, state.multiplayer.league?.revision,
    state.home?.save?.current_date, state.dashboardTeam || userTeam()].join(':');
}
async function loadAssetsDesktop() {
  const key=assetsContextKey(), dashboard=state.data.dashboard;
  if(state.data.assetsDesktop?.key===key && state.data.assetsDesktop.dashboard===dashboard) return;
  if(assetsRead?.key===key && assetsRead.dashboard===dashboard) return assetsRead.promise;
  const request={key,dashboard};
  state.assetsError='';
  state.assetsLoading=true;
  request.promise=action('team_assets',{...savePayload(),team:state.dashboardTeam||userTeam()}).then(payload=>{
    if(key!==assetsContextKey() || dashboard!==state.data.dashboard) return;
    state.data.assetsDesktop={key,dashboard,payload};
    if(teamLabel(payload.team)===userTeam()) state.data.tradeUser=payload;
  }).catch(error=>{if(key===assetsContextKey()) state.assetsError=error.message;throw error;}).finally(()=>{if(assetsRead===request){assetsRead=null;state.assetsLoading=false;}});
  assetsRead=request;
  return request.promise;
}
async function openTeamRosterCard(team = userTeam()) {
  closeAllModals();
  state.view='dashboard';
  const target=teamLabel(team || userTeam());
  if(target!==teamLabel(state.dashboardTeam||userTeam())) await switchDashboardTeam(target);
  else {
    await ensureViewData(true);
    renderDashboard();
  }
  window.CardBoard?.open('roster');
}
function assetContractCell(row,season,seasons) {
  const amount=Number(row.salary_by_year?.[season]||0);
  if(!amount) return '—';
  const expires=season===seasons[0] && !Object.entries(row.salary_by_year||{}).some(([year,value])=>year>season&&Number(value)>0);
  return html(`<span${expires?' class="asset-contract-expiring" title="Contract expires after this season"':''}>${money(amount)}</span>`);
}
function pickTeamAbbrev(pick) {
  return pick.original_team_abbrev || String(pick.original_team_id || '').replace(/^team_/,'').toUpperCase() || 'NBA';
}
function draftAssetGlyph(pick, compact=false, inert=false) {
  const isSwap=pick.kind==='pick_swap';
  const teams=(isSwap ? pick.original_team_abbrevs : [pickTeamAbbrev(pick)]).filter(Boolean).slice(0,2);
  const condition=pick.protection_summary || pick.condition_summary || (isSwap ? pick.label : '');
  const title=pick.label || `${pick.season || ''} R${pick.round || ''}`;
  const tag=inert?'span':'button';
  return `<${tag}${inert?'':' type="button"'} class="draft-asset-glyph${isSwap?' is-swap':''}${compact?' is-compact':''}" title="${escapeAttr(condition || title)}" aria-label="${escapeAttr(title)}">
    <span class="draft-asset-logos">${teams.map(team=>`<span><img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}" /></span>`).join('')}</span>
    ${isSwap?'<b class="draft-asset-swap" aria-hidden="true">⇄</b>':''}
    ${condition&&!isSwap?'<b class="draft-asset-condition" aria-hidden="true">*</b>':''}
    <span class="draft-asset-tooltip">${escapeHtml(condition || title)}</span>
  </${tag}>`;
}
function draftAssetsBoard(picks) {
  const seasonStart=Number(String(state.home?.save?.season||'').match(/^(\d{4})/)?.[1]);
  const firstDraftYear=Number.isFinite(seasonStart)&&seasonStart>1900
    ? seasonStart+1
    : Math.min(...picks.map(p=>Number(String(p.season||'').slice(0,4))).filter(year=>Number.isFinite(year)&&year>1900));
  const start=Number.isFinite(firstDraftYear)?firstDraftYear:new Date().getFullYear();
  const years=Array.from({length:7},(_,index)=>String(start+index));
  return `<div class="draft-assets-board"><div class="draft-assets-corner">Round</div>${years.map(y=>`<strong>${escapeHtml(shortSeasonLabel(y))}</strong>`).join('')}
    ${[1,2].map(round=>`<b>R${round}</b>${years.map(year=>`<div class="draft-assets-cell">${picks.filter(p=>String(p.season||'')===year&&Number(p.round||0)===round).map(p=>draftAssetGlyph(p)).join('')||'<span>—</span>'}</div>`).join('')}`).join('')}</div>`;
}
function assetsTradeTools(legal) {
  return `<div class="assets-trade-tools">
    <button type="button" data-assets-trade="builder" ${legal?'':'disabled'}><strong>Trade builder</strong>${gameArtwork('trade-builder','trade-launch-art')}</button>
    <button type="button" data-assets-trade="finder" ${legal?'':'disabled'}><strong>Trade finder</strong>${gameArtwork('trade-finder','trade-launch-art')}</button>
  </div>`;
}
function compactRatingBar(value) {
  return `<span class="linked-rating assets-rating-bar"><span>${draftMetric(value)}</span><i><b style="${performanceBarStyle(Number(value||0))}"></b></i></span>`;
}
function compactBlockContract(value, terms, activeSeason=state.home?.save?.season) {
  if(terms?.length) return terms.map(term=>`${money(term.salary/1_000_000)} × ${term.years}`).join(', ');
  const salaries=String(value||'').split('/').filter(part=>!activeSeason||!part.match(/\d{4}-\d{2}/)||part.match(/\d{4}-\d{2}/)[0]>=activeSeason).map(part=>part.match(/\$([\d.]+)M/i)?.[1]).filter(Boolean);
  if(!salaries.length)return '—';
  const runs=[];
  salaries.forEach(salary=>{
    const last=runs[runs.length-1];
    if(last)last.years+=1;
    else runs.push({salary,years:1});
  });
  return runs.map(run=>`$${run.salary}M × ${run.years}`).join(', ');
}

// Every section receives the same ordered rows and shares a single scroll surface.
function linkedRosterTables(rows, groups, scope, sort) {
  const fields = groups.flatMap(group=>group.fields);
  const field = fields.find(item=>item.key===sort.key);
  const ordered = [...rows].sort((a,b)=>{
    const av=field?.value(a), bv=field?.value(b);
    const compared=typeof av==='number'&&typeof bv==='number'?av-bv:String(av??'').localeCompare(String(bv??''),undefined,{numeric:true});
    return compared*(sort.direction==='asc'?1:-1)||String(a.id).localeCompare(String(b.id));
  });
  return `<div class="linked-roster-scroll" data-linked-scope="${scope}"><div class="linked-roster-tables">${groups.map(group=>`<section class="linked-roster-group ${group.className||''}">${scope==='assets'?'':`<h4>${group.title}</h4>`}<table><colgroup>${group.fields.map(f=>`<col${f.width?` style="width:${f.width}px"`:''}>`).join('')}</colgroup><thead><tr>${group.fields.map(f=>`<th aria-sort="${sort.key===f.key?(sort.direction==='asc'?'ascending':'descending'):'none'}"><button type="button" data-linked-sort="${f.key}">${f.label}${sort.key===f.key?(sort.direction==='asc'?' ↑':' ↓'):''}</button></th>`).join('')}</tr></thead><tbody>${ordered.map(p=>`<tr data-linked-player="${escapeAttr(p.id)}"${scope==='market'?` data-fa-select="${escapeAttr(p.id)}"`:''} class="${isPlayerInjured(p.health)?'injured':''}${scope==='market'&&String(state.selectedFreeAgent)===String(p.id)?' is-selected':''}">${group.fields.map(f=>`<td>${f.cell?f.cell(p):escapeHtml(f.value(p)??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table></section>`).join('')}</div></div>`;
}
function wireLinkedRoster(root, onSort) {
  root?.querySelectorAll('[data-linked-sort]').forEach(button=>button.onclick=()=>onSort(button.dataset.linkedSort));
  root?.querySelectorAll('[data-linked-player]').forEach(row=>{
    const highlight=active=>root.querySelectorAll('[data-linked-player]').forEach(other=>other.classList.toggle('is-linked-hover',active&&other.dataset.linkedPlayer===row.dataset.linkedPlayer));
    row.onmouseenter=()=>highlight(true); row.onmouseleave=()=>highlight(false);
  });
}
function assetsRosterMarkup(rows,seasons) {
  const identity=[
    {key:'name',label:'Player',width:138,value:p=>p.name,cell:p=>formatCell(summaryPlayerNameCell(p,true))},
    {key:'age',label:'Age',width:28,value:p=>Math.floor(p.age)},
    {key:'position',label:'Pos',width:28,value:p=>compactPos(p.position)},
    {key:'trade_value',label:'Value',width:65,value:p=>Number(p.trade_value||0),cell:p=>p.trade_value==null?'—':draftMetric(p.trade_value)},
  ];
  const ratings=[['OVR','overall'],['OFF','offense'],['DEF','defense'],['Shot','shooting'],['Cre','creation'],['Pass','passing'],['Reb','rebounding'],['Rim','rim_deterrence'],['Ath','athleticism'],['Range','range']].map(([label,key],i)=>({label,key,width:i<3?72:([5,9].includes(i)?38:39),value:p=>Number(key==='offense'?(p.ratings?.offense??((Number(rating(p,'shooting'))+Number(rating(p,'creation'))+Number(rating(p,'passing')))/3)):rating(p,key)),cell:p=>i<3?compactRatingBar(key==='offense'?(p.ratings?.offense??((Number(rating(p,'shooting'))+Number(rating(p,'creation'))+Number(rating(p,'passing')))/3)):rating(p,key)):draftMetric(rating(p,key))}));
  const stats=[{key:'games',label:'GP',value:p=>Number(p.games||0),cell:p=>escapeHtml(p.gp_display||p.games||0)},{key:'mpg',label:'MPG',value:p=>Number(mpgFromRow(p)),cell:p=>draftMetric(mpgFromRow(p))},...['points','rebounds','assists','steals','blocks','turnovers'].map((key,i)=>({key,label:['PTS','REB','AST','STL','BLK','TO'][i],value:p=>Number(statNumber(p,key)),cell:p=>statNumber(p,key)}))];
  const contracts=[{key:'health_risk',label:'Risk',width:34,value:p=>Number(p.health_risk||0),cell:p=>draftMetric(p.health_risk)},{key:'upside_remaining',label:'Up',width:34,value:p=>Number(p.upside_remaining||0),cell:p=>draftMetric(p.upside_remaining)},...seasons.map(season=>({key:season,label:shortSeasonLabel(season),width:48,value:p=>Number(p.salary_by_year?.[season]||0),cell:p=>formatCell(assetContractCell(p,season,seasons))}))];
  return linkedRosterTables(rows,[{title:'Ratings',className:'linked-ratings',fields:[...identity,...ratings]},{title:'Season stats',className:'linked-stats',fields:stats},{title:'Contracts',className:'linked-contracts',fields:contracts}],'assets',state.assetsRosterSort||{key:'trade_value',direction:'desc'});
}
function teamBlockMarkup(payload, editable, seasons=[]) {
  const ids=payload?.team_block_player_ids||[], pickIds=payload?.team_block_pick_ids||[], players=payload?.players||[], picks=payload?.picks||[], team=teamLabel(payload?.team||state.dashboardTeam||userTeam());
  const entries=[...ids.map(id=>({id,kind:'player'})),...pickIds.map(id=>({id,kind:'pick'}))];
  const rows=Array.from({length:6},(_,index)=>{
    const entry=entries[index], player=entry?.kind==='player'?players.find(p=>p.id===entry.id):null, pick=entry?.kind==='pick'?picks.find(p=>p.id===entry.id):null;
    const playerCell=player?`<span class="team-block-player"><button type="button" data-dashboard-player-card="${escapeAttr(player.id)}">${escapeHtml(player.name)}</button><button type="button" data-block-remove="${escapeAttr(player.id)}" aria-label="Remove ${escapeAttr(player.name)} from trade block" ${editable?'':'disabled'}>×</button></span>`:pick?`<span class="team-block-player" title="${escapeAttr(pick.label)}"><span>${escapeHtml(`${pick.season} R${pick.round} ${pick.original_team_abbrev || ''}`)}</span><button type="button" data-block-remove="${escapeAttr(pick.id)}" data-block-kind="pick" aria-label="Remove ${escapeAttr(pick.label)} from trade block" ${editable?'':'disabled'}>×</button></span>`:`<span class="team-block-add-pair"><select data-block-add aria-label="Add player to trade block slot ${index+1}" ${editable?'':'disabled'}><option value="">+ Player</option>${players.filter(p=>!ids.includes(p.id)).map(p=>`<option value="${escapeAttr(p.id)}">${escapeHtml(p.name)}</option>`).join('')}</select><select data-block-add data-block-kind="pick" aria-label="Add draft pick to trade block slot ${index+1}" ${editable?'':'disabled'}><option value="">+ Pick</option>${picks.filter(p=>!pickIds.includes(p.id)).map(p=>`<option value="${escapeAttr(p.id)}">${escapeHtml(p.label)}</option>`).join('')}</select></span>`;
    const ratingValue=key=>player?.ratings?.[key]??(key==='offense'?player?.ratings?.overall:undefined);
    const contract=compactBlockContract(player?.contract,player?.contract_terms);
    return `<div class="assets-block-row team-block-row"><span class="assets-block-team">${teamLogoSrc(team)?`<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}" />`:escapeHtml(team)}</span>${playerCell}<span>${player?Math.floor(Number(player.age)||0):'—'}</span><span>${escapeHtml(player?.position||'—')}</span>${['overall','offense','defense'].map(key=>`<span>${player?compactRatingBar(ratingValue(key)):'—'}</span>`).join('')}<span title="${escapeAttr(player?.contract||'No contract')}">${escapeHtml(contract)}</span>${player||pick?`<button type="button" class="block-find-trade" data-block-find-trade="${escapeAttr(entry.id)}" data-block-kind="${entry.kind}" data-block-team="${escapeAttr(team)}" title="Find trades for ${escapeAttr(player?.name || pick?.label)}" aria-label="Find trades for ${escapeAttr(player?.name || pick?.label)}">Find</button>`:'<span></span>'}</div>`;
  }).join('');
  return `<div class="assets-block-table team-block-table"><div class="assets-block-head"><span>Team</span><span>Player</span><span>Age</span><span>Pos</span><span>OVR</span><span>OFF</span><span>DEF</span><span>Contract</span><span>Trade</span></div>${rows}</div>`;
}
async function updateTeamBlock(playerId, remove=false, kind='player') {
  const payload=state.data.assetsDesktop?.payload;
  if(!payload||!playerId)return;
  const ids=payload[kind==='pick'?'team_block_pick_ids':'team_block_player_ids']||[];
  const next=remove?ids.filter(id=>id!==playerId):[...ids,playerId];
  try {
    const result=await action('set_team_block',{...savePayload(),team:state.dashboardTeam||userTeam(),player_ids:kind==='player'?next:payload.team_block_player_ids||[],pick_ids:kind==='pick'?next:payload.team_block_pick_ids||[]});
    if(result.status!=='updated')throw new Error(result.reason||'Could not update trade block.');
    payload.team_block_player_ids=result.team_block_player_ids;
    payload.team_block_pick_ids=result.team_block_pick_ids;
    refreshAssetsSurface();
  } catch(error) {showToast(error.message,true);refreshAssetsSurface();}
}
function refreshAssetsSurface() {
  if(state.view==='dashboard') renderDashboard();
}
function leagueBlockGroups(rows) {
  const top=[...rows].sort((a,b)=>Number(b.overall||0)-Number(a.overall||0)).slice(0,6);
  const groups=[{label:'Top league targets',rows:top}];
  const byTeam=new Map();
  rows.forEach(row=>{const key=row.team_abbrev||'NBA';if(!byTeam.has(key))byTeam.set(key,[]);byTeam.get(key).push(row);});
  [...byTeam.keys()].sort().forEach(team=>groups.push({label:team,rows:byTeam.get(team).slice(0,6)}));
  return groups;
}
function leagueBlockMarkup(rows) {
  const groups=leagueBlockGroups(rows), index=((Number(state.assetsBlockIndex)||0)%Math.max(1,groups.length)+groups.length)%Math.max(1,groups.length), group=groups[index]||{label:'League',rows:[]};
  const entries=group.rows.map(row=>`<div class="assets-block-row">
    <span class="assets-block-team"><img src="${escapeAttr(teamLogoSrc(row.team_abbrev))}" alt="${escapeAttr(row.team_abbrev)}" /></span>
    <button type="button" data-dashboard-player-card="${escapeAttr(row.player_id)}">${escapeHtml(row.name||'Unknown')}</button>
    <span>${Math.floor(Number(row.age)||0)||'—'}</span><span>${escapeHtml(row.position||'—')}</span>
    <span>${compactRatingBar(row.overall)}</span><span>${compactRatingBar(row.offense)}</span><span>${compactRatingBar(row.defense)}</span>
    <span title="${escapeAttr(row.contract||'No contract')}">${escapeHtml(compactBlockContract(row.contract,row.contract_terms))}</span>
    <button type="button" class="block-find-trade" data-block-find-trade="${escapeAttr(row.player_id)}" data-block-team="${escapeAttr(row.team_abbrev)}" title="Find trades for ${escapeAttr(row.name)}" aria-label="Find trades for ${escapeAttr(row.name)}">Find</button>
  </div>`).join('');
  return `<div class="assets-block-caption"><span>${escapeHtml(group.label)}</span><div class="assets-block-nav"><button type="button" data-assets-block-nav="-1" aria-label="Previous players on the block">‹</button><button type="button" data-assets-block-nav="1" aria-label="Next players on the block">›</button></div><b>${index+1}/${groups.length}</b></div>
    <div class="assets-block-table"><div class="assets-block-head"><span>Team</span><span>Player</span><span>Age</span><span>Pos</span><span>OVR</span><span>OFF</span><span>DEF</span><span>Contract</span><span>Trade</span></div>${entries||'<p class="assets-empty">No players are currently on the block.</p>'}</div>`;
}
function wireLeagueBlockControls(root) {
  root?.querySelectorAll('[data-block-find-trade]').forEach(button=>button.onclick=async()=>{
    try {
      state.tradePartner=button.dataset.blockTeam;
      state.selectedFrom=[];
      state.selectedTo=[];
      state.tradeResults=[];
      await openTradeRoomModal('finder', {targetTeam:button.dataset.blockTeam,targetPlayerId:button.dataset.blockKind!=='pick'?button.dataset.blockFindTrade:undefined,targetPickId:button.dataset.blockKind==='pick'?button.dataset.blockFindTrade:undefined});
      await runTradeSearch();
    } catch(error) {showToast(error.message,true);}
  });
  root?.querySelectorAll('[data-assets-block-nav]').forEach(button=>button.onclick=()=>{
    const rows=state.data.assetsDesktop?.payload?.league_block||[];
    const count=leagueBlockGroups(rows).length;
    if(!count)return;
    state.assetsBlockIndex=(Number(state.assetsBlockIndex||0)+Number(button.dataset.assetsBlockNav)+count)%count;
    assetsBlockRemaining=8000;
    const body=root.querySelector('[data-assets-block-body]');
    if(body){body.innerHTML=leagueBlockMarkup(rows);wireDashboardPlayerCards(body);wireLeagueBlockControls(root);}
  });
}
function startAssetsBlockRotation() {
  clearInterval(assetsBlockTimer);
  assetsBlockRemaining=8000;
  const rows=state.data.assetsDesktop?.payload?.league_block||[];
  if(!rows.length || state.view!=='dashboard') return;
  let previous=performance.now();
  assetsBlockTimer=setInterval(()=>{
    const now=performance.now(),elapsed=now-previous;previous=now;
    if(state.view!=='dashboard'){clearInterval(assetsBlockTimer);return;}
    if(state.modal||document.hidden)return;
    const windowCard=els.content.querySelector('[data-board-window="league-block"]');
    if(windowCard&&(windowCard.hidden||windowCard.classList.contains('is-minimized')))return;
    assetsBlockRemaining=Math.max(0,assetsBlockRemaining-elapsed);
    if(assetsBlockRemaining===0){
      state.assetsBlockIndex=(Number(state.assetsBlockIndex)||0)+1;
      const body=els.content.querySelector('[data-assets-block-body]');
      if(body){body.innerHTML=leagueBlockMarkup(rows);wireDashboardPlayerCards(body);wireLeagueBlockControls(els.content);}
      assetsBlockRemaining=8000;
    }
    const ring=els.content.querySelector('[data-block-countdown]');
    if(ring){ring.style.strokeDashoffset=String(100*(1-assetsBlockRemaining/8000));ring.parentElement.setAttribute('aria-label',`Next league block in ${Math.ceil(assetsBlockRemaining/1000)} seconds`);}
  },100);
}
function assetsDesktopCards() {
  const dash=state.data.dashboard||{},seasons=contractSeasons(rosterRows(dash)).slice(0,4),saved=state.data.assetsDesktop;
  const payload=saved?.key===assetsContextKey()&&saved.dashboard===dash?saved.payload:null;
  const values=new Map((payload?.players||[]).map(p=>[p.id,p]));
  const rows=rosterRows(dash).map(p=>({...p,trade_value:values.get(p.id)?.trade_value})).sort((a,b)=>(b.trade_value??-1)-(a.trade_value??-1));
  const editable=teamLabel(dash.team||state.dashboardTeam||userTeam())===userTeam();
  const legal=editable&&(dash.legal_actions||[]).some(a=>['trades','draft_trades'].includes(a));
  const panel=(title,body,cls,buttons='',artwork='')=>`<section class="season-command-panel assets-${cls}">${title?seasonPanelHeader(title,buttons,artwork):''}<div class="assets-panel-body">${body}</div></section>`;
  const roster=assetsRosterMarkup(rows,seasons);
  const picks=[...(payload?.picks||[]),...(payload?.pick_swaps||[])];
  return {rows,seasons,markup:`<div class="assets-grid">
      ${panel('',roster,'roster')}
      ${panel('Four-Year Payroll Share',summaryContractChart(rows,seasons,dash),'payroll','','payroll')}
      ${panel('Draft assets',payload?draftAssetsBoard(picks):`<p class="assets-empty">${state.assetsError?escapeHtml(state.assetsError):'Loading draft assets…'}</p>${state.assetsError?'<button type="button" data-assets-retry>Retry</button>':''}`,'picks')}
      ${panel('League block',payload?`<div data-assets-block-body>${leagueBlockMarkup(payload.league_block||[])}</div>`:'<p class="assets-empty">Loading league block…</p>','block',`<svg class="block-countdown" viewBox="0 0 24 24" role="img" aria-label="Next league block in 8 seconds"><circle class="block-countdown-track" cx="12" cy="12" r="9"/><circle data-block-countdown cx="12" cy="12" r="9" pathLength="100"/></svg>`)}
      <div class="assets-trade-launchers">${assetsTradeTools(legal)}</div>
      ${panel('Team block',teamBlockMarkup(payload,editable,seasons),'team-block')}
    </div>`};
}
function wireAssetsCards(root, rows, seasons) {
  wireDashboardPlayerCards(root);
  wireLeagueBlockControls(root);
  const wireRoster=()=>wireLinkedRoster(root.querySelector('.assets-roster'),key=>{
    const prior=state.assetsRosterSort||{key:'trade_value',direction:'desc'};
    state.assetsRosterSort={key,direction:prior.key===key&&prior.direction==='desc'?'asc':'desc'};
    const body=root.querySelector('.assets-roster .assets-panel-body');
    const scroll=body.querySelector('.linked-roster-scroll')?.scrollTop||0;
    body.innerHTML=assetsRosterMarkup(rows,seasons);body.querySelector('.linked-roster-scroll').scrollTop=scroll;
    wireDashboardPlayerCards(body);wireRoster();
  });
  wireRoster();
  root.querySelectorAll('[data-block-add]').forEach(select=>select.onchange=()=>updateTeamBlock(select.value,false,select.dataset.blockKind||'player'));
  root.querySelectorAll('[data-block-remove]').forEach(button=>button.onclick=()=>updateTeamBlock(button.dataset.blockRemove,true,button.dataset.blockKind||'player'));
  root.querySelectorAll('[data-assets-trade]').forEach(b=>b.onclick=()=>openTradeRoomModal(b.dataset.assetsTrade));
  root.querySelector('[data-assets-retry]')?.addEventListener('click',()=>loadAssetsDesktop().then(refreshAssetsSurface).catch(refreshAssetsSurface));
}
function mountDashboardCardBoard(target) {
  if(!window.CardBoard) return;
  const dashboard=target.querySelector('.season-command-dashboard');
  if(!dashboard) return;
  const {rows,seasons,markup}=assetsDesktopCards();
  const seed=document.createElement('div');
  seed.className='assets-desktop card-board-assets-seed';
  seed.innerHTML=markup;
  dashboard.append(seed);
  window.CardBoard.mount(target,{save:state.currentSave,assetsRoot:seed});
  dashboard.querySelectorAll('.card-board-body.assets-desktop').forEach(root=>wireAssetsCards(root.parentElement,rows,seasons));
  startAssetsBlockRotation();
  const saved=state.data.assetsDesktop;
  if(!state.currentSave||state.hydrating||state.assetsError||state.assetsLoading||
    (saved?.key===assetsContextKey()&&saved.dashboard===state.data.dashboard))return;
  const currentDashboard=state.data.dashboard;
  loadAssetsDesktop().then(()=>{
    if(state.view==='dashboard'&&state.data.dashboard===currentDashboard&&target.isConnected)renderDashboard();
  }).catch(()=>{
    if(state.view==='dashboard'&&state.data.dashboard===currentDashboard&&target.isConnected)renderDashboard();
  });
}
