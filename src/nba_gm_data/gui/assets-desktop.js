// Two desktops share dashboard data; only asset valuations need an extra read.
let assetsRead = null;
const ASSETS_CARD_IDS = new Set(['roster','stats','contracts','payroll','picks','league-block','team-block','team-wants']);
function assetsContextKey() {
  return [state.currentSave, state.dashboardRevision, state.multiplayer.league?.revision,
    state.home?.save?.current_date, state.dashboardTeam || userTeam()].join(':');
}
function assetsErrorForContext() {
  return state.assetsErrorKey===assetsContextKey()&&state.assetsErrorDashboard===state.data.dashboard?state.assetsError:'';
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
  }).catch(error=>{
    if(key===assetsContextKey() && dashboard===state.data.dashboard) {
      state.assetsError=error.message;state.assetsErrorKey=key;state.assetsErrorDashboard=dashboard;
    }
    throw error;
  }).finally(()=>{if(assetsRead===request){assetsRead=null;state.assetsLoading=false;}});
  assetsRead=request;
  return request.promise;
}
function loadOpenedAssetsCard(target,id) {
  if(!ASSETS_CARD_IDS.has(id)) return;
  const saved=state.data.assetsDesktop;
  if(!state.currentSave||state.hydrating||state.tutorial||assetsErrorForContext()||
    (assetsRead?.key===assetsContextKey()&&assetsRead.dashboard===state.data.dashboard)||
    (saved?.key===assetsContextKey()&&saved.dashboard===state.data.dashboard))return;
  const currentDashboard=state.data.dashboard;
  const focusedId=document.activeElement?.closest('[data-board-window]')?.dataset.boardWindow;
  const refresh=()=>{
    if(state.view!=='dashboard'||state.data.dashboard!==currentDashboard||!target.isConnected)return;
    refreshAssetsSurface(target);
    if(focusedId&&!state.modal) {
      const frame=target.querySelector(`[data-board-window="${focusedId}"]`);
      if(frame&&!frame.hidden) frame.querySelector('[data-board-move]')?.focus({preventScroll:true});
    }
  };
  loadAssetsDesktop().then(refresh).catch(refresh);
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
  const dash=state.data.dashboard||{};
  const extensionEligible=Boolean(row.extension_eligible && dash.extension_window_open);
  const editable=teamLabel(dash.team||state.dashboardTeam||userTeam())===userTeam();
  if(extensionEligible && editable) return html(`<button type="button" class="extension-eligible-contract extension-contract-button" data-asset-extension="${escapeAttr(row.id)}" title="Negotiate an extension with ${escapeAttr(row.name)}">${money(amount)}</button>`);
  return html(`<span${extensionEligible?' class="extension-eligible-contract" title="Extension eligible"':expires?' class="asset-contract-expiring" title="Contract expires after this season"':''}>${money(amount)}</span>`);
}
function assetExtensionCell(row) {
  const dash=state.data.dashboard||{};
  const editable=teamLabel(dash.team||state.dashboardTeam||userTeam())===userTeam();
  if(!editable) return '<span title="Only your own team can offer extensions">—</span>';
  if(!dash.extension_window_open) return '<span title="The extension window is closed">Closed</span>';
  if(!row.extension_eligible) return '<span title="Not currently eligible for an extension">—</span>';
  return `<button type="button" class="asset-extension-action" data-asset-extension="${escapeAttr(row.id)}" aria-label="Negotiate extension with ${escapeAttr(row.name || 'player')}">Negotiate</button>`;
}
function wireAssetExtensions(root) {
  root.querySelectorAll('[data-asset-extension]').forEach(button=>{
    button.onclick=()=>openExtensionNegotiation(button.dataset.assetExtension);
  });
}
function pickTeamAbbrev(pick) {
  return pick.original_team_abbrev || String(pick.original_team_id || '').replace(/^team_/,'').toUpperCase() || 'NBA';
}
// Visible image bounds fit every mark proportionally into the same bubble.
const PICK_LOGO_BOUNDS = {"ATL":[500,500,20,20,460,460],"BKN":[500,500,20,20,460,460],"BOS":[500,500,20,20,460,460],"CHA":[500,500,11,20,478,460],"CHI":[500,500,19,46,461,408],"CLE":[500,500,20,54,461,392],"DAL":[500,500,20,20,460,460],"DEN":[500,500,20,20,460,460],"DET":[500,500,20,20,460,460],"GSW":[500,500,20,20,460,460],"HOU":[500,500,76,20,347,460],"IND":[500,500,20,36,460,428],"LAC":[500,500,20,20,460,460],"LAL":[500,500,20,111,460,282],"MEM":[500,500,19,32,462,436],"MIA":[500,500,32,20,436,461],"MIL":[500,500,75,20,350,460],"MIN":[500,500,20,20,460,460],"NOP":[500,500,20,161,460,178],"NYK":[500,500,20,62,460,376],"OKC":[500,500,20,117,460,266],"ORL":[500,500,20,83,461,334],"PHI":[500,500,60,20,380,460],"PHX":[500,500,20,58,461,384],"POR":[500,500,41,19,418,461],"SAC":[500,500,49,20,402,461],"SAS":[500,500,60,20,380,460],"TOR":[500,500,20,20,460,460],"UTA":[500,500,20,93,460,313],"WAS":[500,500,20,20,460,460]};
function pickLogoMarkup(team, layer=0, front=false, owner='') {
  const bounds = PICK_LOGO_BOUNDS[team];
  const className=`draft-team-mark${front?' is-swap-front':''}`;
  const badge=owner && owner!==team ? `<span class="draft-asset-owner" title="Owned by ${escapeAttr(owner)}"><img src="${escapeAttr(teamLogoSrc(owner))}" alt="Owned by ${escapeAttr(owner)}" /></span>` : '';
  if (!bounds) return `<span class="${className}" style="z-index:${layer}"><span class="draft-team-logo-crop"><img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}" /></span>${badge}</span>`;
  const [width,height,x,y,visibleWidth,visibleHeight] = bounds;
  const reference=Math.max(visibleWidth,visibleHeight);
  const style = `z-index:${layer};--pick-logo-width-scale:${visibleWidth/reference};--pick-logo-height-scale:${visibleHeight/reference};--pick-image-width:${width/reference};--pick-image-height:${height/reference};--pick-image-left:${-x/reference};--pick-image-top:${-y/reference}`;
  return `<span class="${className}" style="${style}"><span class="draft-team-logo-crop"><img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}" /></span>${badge}</span>`;
}

function nestedSwapArrows(width) {
  return `<svg class="draft-asset-swap" width="${width}" height="14" viewBox="0 0 ${width} 14" aria-hidden="true" focusable="false"><path d="M1 3.5H${width-1}m-4-3 4 3-4 3M${width-1} 10.5H1m4-3-4 3 4 3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>`;
}
function nestedSwapMarkup(node) {
  if (node.type==='pick') return {width:20, html:pickLogoMarkup(node.team_abbrev,0,false,node.owner_abbrev || '')};
  const left=nestedSwapMarkup(node.left), right=nestedSwapMarkup(node.right);
  const separated=node.left.type==='swap' || node.right.type==='swap';
  const width=left.width + right.width + (separated ? 8 : -8);
  const leftFront=node.benefit==='better';
  return {width,html:`<span class="draft-nested-swap"><span class="draft-nested-pair${separated?' has-nested-input':''}"><span class="draft-nested-half${leftFront?' is-front':''}">${left.html}</span><span class="draft-nested-half${leftFront?'':' is-front'}">${right.html}</span></span>${nestedSwapArrows(width)}</span>`};
}

function draftAssetGlyph(pick, compact=false, inert=false, extended=false) {
  const forfeited=pick.status==='forfeited';
  if (forfeited && !extended) return '';
  const presentation=pick.pick_presentation || {};
  const isSwap=pick.kind==='pick_swap' || Boolean(presentation.is_swap);
  const swapTeams=pick.original_team_abbrevs || (pick.original_team_ids || []).map(id=>String(id).replace(/^team_/,'').toUpperCase());
  const presentedTeams=pick.kind==='pick_swap' && !pick.display_only ? presentation.asset_team_abbrevs : presentation.team_abbrevs;
  const teams=[...new Set((presentedTeams?.length ? presentedTeams : isSwap ? (swapTeams.length ? swapTeams : [pickTeamAbbrev(pick)]) : [pickTeamAbbrev(pick)]).filter(Boolean))];
  const frontTeam=presentation.front_team_abbrev;
  const rawCondition=String(pick.condition_summary || pick.protection_summary || pick.protections || (isSwap ? pick.label : '') || '').trim();
  const condition=/^[A-Z]{2,4}$/.test(rawCondition) || /^unprotected[.\s]*$/i.test(rawCondition) ? '' : rawCondition;
  const title=pick.label || `${pick.season || ''} R${pick.round || ''}`;
  const tooltip=(condition && !title.toLowerCase().includes(condition.toLowerCase()) ? `${title}; ${condition}` : title).replace(/;?\s*unprotected(?:[.;]\s*no additional conditions\.?)?/ig,'').trim();
  const owner=pick.current_owner_team_abbrev || String(pick.current_owner_team_id || '').replace(/^team_/,'').toUpperCase();
  const iconOwners=isSwap ? presentation.pair_icon_owners && Object.keys(presentation.pair_icon_owners).length ? presentation.pair_icon_owners : presentation.team_owners || {} : {[pickTeamAbbrev(pick)]:owner};
  const viewedTeam=teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam());
  // Extended inclusion describes where an item was listed, not ownership.
  // Owned collateral and less-favourable entitlements remain fully visible.
  const hasOwnedOutcome=owner===viewedTeam || (isSwap && Object.values(iconOwners).includes(viewedTeam));
  const contextOnly=forfeited || Boolean(pick.is_additional && owner && !hasOwnedOutcome);
  const presentationProtection=pick.kind==='pick_swap' && !pick.display_only ? presentation.asset_has_protection : presentation.has_protection;
  const hasProtection=Boolean(pick.has_protection || presentationProtection || /\b(?:top[- ]\d+\s+protected|picks?\s+\d+[-–]\d+\s+protected)\b/i.test(pick.protection_summary || pick.protections || ''));
  if (forfeited) inert=true;
  const tag=inert?'span':'button';
  const swapWidth=20 + Math.max(0,teams.length-1)*12;
  const nested=presentation.nested_entitlement?.tree;
  const nestedMarkup=nested ? nestedSwapMarkup(nested).html : null;
  return `<${tag}${inert?'':' type="button"'} class="draft-asset-glyph${isSwap?' is-swap':''}${nested?' is-nested':''}${compact?' is-compact':''}${extended?' is-extended':''}${extended&&contextOnly?' is-additional':''}" data-draft-asset-tooltip="${escapeAttr(tooltip)}" aria-label="${escapeAttr(tooltip)}">
    <span class="draft-asset-logos">${nestedMarkup || teams.map((team,index)=>pickLogoMarkup(team, isSwap ? team===frontTeam ? teams.length+1 : teams.length-index : 0, isSwap && team===frontTeam, (isSwap ? iconOwners[team] : '') || '')).join('')}${hasProtection?'<b class="draft-asset-condition" aria-hidden="true"><svg viewBox="0 0 10 10" width="5" height="5" focusable="false"><path d="M5 1v8M1.54 3l6.92 4M1.54 7l6.92-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg></b>':''}</span>
    ${isSwap&&!nested?`<svg class="draft-asset-swap" width="${swapWidth}" height="14" viewBox="0 0 ${swapWidth} 14" aria-hidden="true" focusable="false"><path d="M1 3.5H${swapWidth-1}m-4-3 4 3-4 3M${swapWidth-1} 10.5H1m4-3-4 3 4 3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>`:''}
  </${tag}>`;
}
// Keep condition details outside the clipped and scaled card body.
let draftAssetTooltip;
function hideDraftAssetTooltip() {
  if (draftAssetTooltip) draftAssetTooltip.hidden = true;
}
function showDraftAssetTooltip(glyph) {
  if (!draftAssetTooltip) {
    draftAssetTooltip = document.createElement('div');
    draftAssetTooltip.id = 'draftAssetConditionTooltip';
    draftAssetTooltip.className = 'draft-asset-condition-tooltip';
    draftAssetTooltip.setAttribute('role', 'tooltip');
    document.body.append(draftAssetTooltip);
  }
  draftAssetTooltip.textContent = glyph.dataset.draftAssetTooltip;
  draftAssetTooltip.hidden = false;
  glyph.setAttribute('aria-describedby', draftAssetTooltip.id);
  const bounds = glyph.getBoundingClientRect();
  const width = draftAssetTooltip.offsetWidth, height = draftAssetTooltip.offsetHeight;
  draftAssetTooltip.style.left = `${Math.max(8, Math.min(window.innerWidth - width - 8, bounds.left + bounds.width / 2 - width / 2))}px`;
  draftAssetTooltip.style.top = `${bounds.top >= height + 12 ? bounds.top - height - 7 : Math.min(window.innerHeight - height - 8, bounds.bottom + 7)}px`;
}
document.addEventListener('pointerover', event => {
  const glyph = event.target.closest('[data-draft-asset-tooltip]');
  if (glyph) showDraftAssetTooltip(glyph);
});
document.addEventListener('pointerout', event => {
  const glyph = event.target.closest('[data-draft-asset-tooltip]');
  if (glyph && !glyph.contains(event.relatedTarget)) hideDraftAssetTooltip();
});
document.addEventListener('focusin', event => {
  const glyph = event.target.closest('[data-draft-asset-tooltip]');
  if (glyph) showDraftAssetTooltip(glyph);
});
document.addEventListener('focusout', event => {
  if (event.target.closest('[data-draft-asset-tooltip]')) hideDraftAssetTooltip();
});
document.addEventListener('scroll', hideDraftAssetTooltip, true);
document.addEventListener('keydown', event => { if (event.key === 'Escape') hideDraftAssetTooltip(); });
window.addEventListener('resize', hideDraftAssetTooltip);

function draftAssetsBoard(picks, extended=false) {
  const seasonStart=Number(String(state.home?.save?.season||'').match(/^(\d{4})/)?.[1]);
  const firstDraftYear=Number.isFinite(seasonStart)&&seasonStart>1900
    ? seasonStart+1
    : Math.min(...picks.map(p=>Number(String(p.season||'').slice(0,4))).filter(year=>Number.isFinite(year)&&year>1900));
  const start=Number.isFinite(firstDraftYear)?firstDraftYear:new Date().getFullYear();
  const years=Array.from({length:7},(_,index)=>String(start+index));
  return `<div class="draft-assets-board${extended?' is-extended':''}"><div class="draft-assets-corner">Round</div>${years.map(y=>`<strong>${escapeHtml(shortSeasonLabel(y))}</strong>`).join('')}
    ${[1,2].map(round=>`<b>R${round}</b>${years.map(year=>`<div class="draft-assets-cell">${picks.filter(p=>String(p.season||'')===year&&Number(p.round||0)===round).map(p=>draftAssetGlyph(p,false,false,extended)).join('')||'<span>—</span>'}</div>`).join('')}`).join('')}</div>`;
}
function setDraftAssetsCardExpanded(expanded, card) {
  if (!card) return;
  card.dataset.draftAssetsExtended=String(expanded);
  const body=card.querySelector('.assets-panel-body');
  const saved=state.data.assetsDesktop;
  if (!body || saved?.key!==assetsContextKey() || saved.dashboard!==state.data.dashboard) return;
  const payload=saved.payload;
  hideDraftAssetTooltip();
  body.innerHTML=draftAssetsBoard(expanded ? payload.extended_draft_assets || payload.draft_assets || [...(payload.picks||[]),...(payload.pick_swaps||[])] : payload.draft_assets || [...(payload.picks||[]),...(payload.pick_swaps||[])],expanded);
}
function assetsTradeTools(legal) {
  return `<div class="assets-trade-tools">
    <button type="button" data-assets-trade="builder" ${legal?'':'disabled'}><strong>Trade builder</strong>${gameArtwork('trade-builder','trade-launch-art')}</button>
    <button type="button" data-assets-trade="finder" ${legal?'':'disabled'}><strong>Trade finder</strong>${gameArtwork('trade-finder','trade-launch-art')}</button>
  </div>`;
}
// Player OVR/OFF/DEF: the one rating bar every table uses (scale and look in app.js playerRatingBarStyle).
function compactRatingBar(value) {
  return `<span class="linked-rating assets-rating-bar player-rating-bar"><span>${draftMetric(value)}</span><i><b style="${playerRatingBarStyle(value)}"></b></i></span>`;
}
// Coach effects and other 0-100 values keep the plain scale.
function effectRatingBar(value) {
  return `<span class="linked-rating assets-rating-bar"><span>${draftMetric(value)}</span><i><b style="${performanceBarStyle(Number(value||0))}"></b></i></span>`;
}
function blockValueBar(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const score = clampNumber(Number(value), 0, 100);
  const amount = Number(value).toFixed(1);
  return `<span class="block-value-meter" role="img" aria-label="Value ${amount} out of 100" title="Value ${amount}"><b aria-hidden="true">${amount}</b><span class="block-value-bar" aria-hidden="true"><i style="width:${score}%;background:hsl(${score * 1.2},45%,42%)"></i></span></span>`;
}
function blockTableStyle(rows) {
  const contractWidth = Math.max(100, ...rows.map(row => compactBlockContract(row.contract,row.contract_terms).length * 5.5 + 8));
  return `--block-contract-width:${contractWidth}px;min-width:${526 + contractWidth}px`;
}
function compactBlockContract(value, terms, activeSeason=state.home?.save?.season) {
  if(terms?.length) return terms.map(term=>`${money(term.salary/1_000_000)} × ${term.years}`).join(', ');
  const salaries=String(value||'').split('/').filter(part=>!activeSeason||!part.match(/\d{4}-\d{2}/)||part.match(/\d{4}-\d{2}/)[0]>=activeSeason).map(part=>part.match(/\$([\d.]+)M/i)?.[1]).filter(Boolean);
  if(!salaries.length)return String(value||'—');
  const runs=[];
  salaries.forEach(salary=>{
    const last=runs[runs.length-1];
    if(last)last.years+=1;
    else runs.push({salary,years:1});
  });
  return runs.map(run=>`$${run.salary}M × ${run.years}`).join(', ');
}

// Grouped roster sections share one player order and scroll surface.
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
function assetsRosterGroups(seasons) {
  const player={key:'name',label:'Player',width:178,value:p=>p.name,cell:p=>formatCell(summaryPlayerNameCell(p,true,true))};
  const compactPlayer={...player,width:162};
  const identity=[
    player,
    {key:'age',label:'Age',width:28,value:p=>Math.floor(p.age)},
    {key:'position',label:'Pos',width:28,value:p=>compactPos(p.position)},
    {key:'trade_value',label:'Value',width:65,value:p=>Number(p.trade_value||0),cell:p=>p.trade_value==null?'—':draftMetric(p.trade_value)},
  ];
  // OFF comes from the server like OVR and DEF (one display scale; OVERALL-SCALE, 2026-11-21). rating() reads the row's
  // display ratings first and only averages subratings when no OFF was sent. Reading p.ratings.offense first skipped the
  // roster rows' display_ratings and showed a three-subrating average under the OFF label.
  const ratings=[['OVR','overall'],['OFF','offense'],['DEF','defense'],['Shot','shooting'],['Cre','creation'],['Pass','passing'],['Reb','rebounding'],['Rim','rim_deterrence'],['Ath','athleticism'],['Range','range']].map(([label,key],i)=>({label,key,width:i<3?80:([5,9].includes(i)?38:39),value:p=>Number(key==='offense'?(p.ratings?.offense??rating(p,'offense')):rating(p,key)),cell:p=>i<3?compactRatingBar(key==='offense'?(p.ratings?.offense??rating(p,'offense')):rating(p,key)):draftMetric(rating(p,key))}));
  const stats=[compactPlayer,{key:'games',label:'GP',value:p=>Number(p.games||0),cell:p=>escapeHtml(p.gp_display||p.games||0)},{key:'mpg',label:'MPG',value:p=>Number(mpgFromRow(p)),cell:p=>draftMetric(mpgFromRow(p))},...['points','rebounds','assists','steals','blocks','turnovers'].map((key,i)=>({key,label:['PTS','REB','AST','STL','BLK','TO'][i],value:p=>Number(statNumber(p,key)),cell:p=>statNumber(p,key)}))];
  const contracts=[compactPlayer,{key:'health_risk',label:'Risk',width:44,value:p=>Number(p.health_risk||0),cell:p=>playerEvidenceRing('Health risk',p.health_risk,10,Number(p.health_risk)>=7?'#e04d55':Number(p.health_risk)>=4?'#bd5b5d':'#8e6263','/10')},{key:'upside_remaining',label:'Upside',width:44,value:p=>Number(p.upside_remaining||0),cell:p=>playerEvidenceRing('Upside remaining',p.upside_remaining,5,playerUpsideColor(Number(p.upside_remaining||0)),' OVR')},...seasons.map(season=>({key:season,label:shortSeasonLabel(season),width:48,value:p=>Number(p.salary_by_year?.[season]||0),cell:p=>formatCell(assetContractCell(p,season,seasons))}))];
  return [
    {id:'roster',className:'linked-ratings',fields:[...identity,...ratings]},
    {id:'stats',className:'linked-stats',fields:stats},
    {id:'contracts',className:'linked-contracts',fields:contracts},
  ];
}
function assetsRosterSort(id) {
  state.assetsRosterSortByCard ||= {};
  if(id==='roster'&&!state.assetsRosterSortByCard.roster) state.assetsRosterSortByCard.roster=state.assetsRosterSort||{key:'trade_value',direction:'desc'};
  return state.assetsRosterSortByCard[id]||(state.assetsRosterSortByCard[id]={key:'name',direction:'asc'});
}
function assetsRosterMarkup(rows,group,sort) {
  return linkedRosterTables(rows,[group],'assets',sort);
}
function simulationStatsPlayerRows(snapshot) {
  if(Array.isArray(snapshot)) return snapshot;
  for(const key of ['players','rows','roster','player_stats','players_by_id']) {
    if(Array.isArray(snapshot?.[key])) return snapshot[key];
    if(snapshot?.[key]&&typeof snapshot[key]==='object') return Object.entries(snapshot[key]).map(([id,row])=>({...row,id:row.id||row.player_id||id}));
  }
  return [];
}
function mergeSimulationStatsRow(player, update, teamGames) {
  const row={...player,...update,id:player.id};
  const totals=update.totals||update.season_totals||update.statistics?.totals||update.stats?.totals||null;
  const values=update.stats&&typeof update.stats==='object'?{...update.stats,...update}:update;
  const read=(source,keys)=>{
    for(const key of keys) if(source?.[key]!==undefined&&source?.[key]!==null&&source[key]!=='') return Number(source[key]);
    return null;
  };
  const games=read(values,['games','gp','games_played','gamesPlayed','gp_total']) ?? read(totals,['games','gp','games_played','gamesPlayed']);
  if(games!==null&&Number.isFinite(games)) {
    row.games=games;
    row.gp_display=update.gp_display||update.games_display||(teamGames?`${games}/${teamGames}`:String(games));
  }
  const totalMinutes=read(totals,['minutes','minutes_played','total_minutes','minutes_total']) ?? read(update,['total_minutes','minutes_total','minutes_played']);
  const mpg=read(values,['mpg','display_mpg','season_minutes_per_game','minutes_per_game']);
  if(mpg!==null&&Number.isFinite(mpg)) {
    row.mpg=mpg; row.display_mpg=mpg; row.season_minutes_per_game=mpg;
  } else if(totalMinutes!==null&&games>0) {
    row.mpg=totalMinutes/games; row.display_mpg=totalMinutes/games; row.season_minutes_per_game=totalMinutes/games;
  }
  const statKeys={points:['points_per_game','points_pg','ppg'],rebounds:['rebounds_per_game','rebounds_pg','rpg'],assists:['assists_per_game','assists_pg','apg'],steals:['steals_per_game','steals_pg','spg'],blocks:['blocks_per_game','blocks_pg','bpg'],turnovers:['turnovers_per_game','turnovers_pg','topg']};
  for(const [stat,aliases] of Object.entries(statKeys)) {
    const direct=read(values,aliases);
    const total=read(totals,[stat,`total_${stat}`,`${stat}_total`]) ?? read(update,[`total_${stat}`,`${stat}_total`]);
    const candidate=direct ?? (!totals?read(values,[stat]):null);
    if(candidate!==null&&Number.isFinite(candidate)) row[`${stat}_per_game`]=candidate;
    else if(total!==null&&games>0) row[`${stat}_per_game`]=total/games;
  }
  return row;
}
function updateDashboardStatsDuringSimulation(snapshot) {
  const updates=simulationStatsPlayerRows(snapshot);
  if(!updates.length||!state.data.dashboard) return false;
  const dash=state.data.dashboard;
  const current=rosterRows(dash);
  const teamGames=Number(snapshot?.team_games||snapshot?.team_games_played||snapshot?.current_team_games||snapshot?.games_played||snapshot?.games||0)||null;
  const updatesById=new Map(updates.map(row=>[String(row.player_id||row.id||row.player?.id||''),row]).filter(([id])=>id));
  if(!updatesById.size) return false;
  let changedIds=[];
  const rows=current.map(player=>{
    const update=updatesById.get(String(player.id||player.player_id||''));
    if(!update) return player;
    const next=mergeSimulationStatsRow(player,update,teamGames);
    const fields=['games','gp_display','mpg','display_mpg','points_per_game','rebounds_per_game','assists_per_game','steals_per_game','blocks_per_game','turnovers_per_game'];
    if(fields.some(key=>next[key]!==player[key])) changedIds.push(String(player.id||player.player_id));
    return next;
  });
  if(!changedIds.length) return true;
  const playerKey=Array.isArray(dash.players)?'players':Array.isArray(dash.roster)?'roster':Array.isArray(dash.rotation)?'rotation':Array.isArray(dash.rows)?'rows':'players';
  state.data.dashboard={...dash,[playerKey]:rows};
  if(state.data.statusDashboard===dash) state.data.statusDashboard=state.data.dashboard;
  const card=document.querySelector('[data-board-window="stats"] .assets-stats');
  const body=card?.querySelector('.assets-panel-body');
  if(!body) return true;
  const scroll=body.querySelector('.linked-roster-scroll')?.scrollTop||0;
  const {rows:displayRows,seasons}=assetsDesktopCards();
  const group=assetsRosterGroups(seasons).find(item=>item.id==='stats');
  body.innerHTML=assetsRosterMarkup(displayRows,group,assetsRosterSort('stats'));
  const tableScroll=body.querySelector('.linked-roster-scroll');
  if(tableScroll) tableScroll.scrollTop=scroll;
  wireAssetsCards(card,displayRows,seasons);
  for(const id of changedIds) {
    const row=body.querySelector(`[data-linked-player="${CSS.escape(id)}"]`);
    row?.classList.add('simulation-live-stat-updated');
    if(row) setTimeout(()=>row.classList.remove('simulation-live-stat-updated'),850);
  }
  return true;
}
window.updateDashboardStatsDuringSimulation=updateDashboardStatsDuringSimulation;
function compactPickEntitlementLabel(pick) {
  const presentation=pick.pick_presentation || {};
  const prefix=`${pick.season} R${pick.round}`;
  const describe=node=>node.type==='pick' ? node.team_abbrev : `${node.benefit==='better'?'Best':'Worst'}(${describe(node.left)}/${describe(node.right)})`;
  if (presentation.nested_entitlement?.tree) return `${prefix} · ${describe(presentation.nested_entitlement.tree)}`;
  if (presentation.is_swap) {
    const teams=(presentation.team_abbrevs || []).join('/');
    if (presentation.asset_rank) {
      const rank=presentation.asset_rank, size=presentation.asset_pool_size;
      const position=rank*2>=size+1 ? size-rank+1 : rank;
      const suffix=position%100>=11&&position%100<=13?'th':({1:'st',2:'nd',3:'rd'}[position%10]||'th');
      const outcome=rank===1?'Best':rank===size?'Worst':`${position}${suffix}${rank*2>=size+1?'Worst':'Best'}`;
      return `${prefix} · ${outcome}(${teams})`;
    }
    const outcome=String(presentation.label || '').match(/receives (?:the )?([^.;]+?) of /i)?.[1] || '';
    const rank=outcome.replace(/more favourable|most favourable/i,'Best').replace(/less favourable|least favourable/i,'Worst').replace(/favourable/ig,'').trim();
    // Definite ranked outcomes retain their rank/count; complex conditional
    // comparisons keep an honest short label and the complete hover text.
    const plainRank=/^(Best|Worst|\d+ (?:most|least)|(?:second|third|fourth|fifth) (?:most|least))$/i.test(rank);
    return `${prefix} · ${plainRank?`${rank}(${teams})`:`Conditional swap (${teams})`}`;
  }
  const protection=String(pick.protection_summary || '').trim();
  return `${prefix} · ${pick.original_team_abbrev || ''}${protection && !/^unprotected/i.test(protection)?` · ${protection}`:''}`;
}

function teamBlockPickIcon(pick) {
  const tree=pick.pick_presentation?.nested_entitlement?.tree;
  const depth=node=>node.type==='pick'?0:1+Math.max(depth(node.left),depth(node.right));
  const height=tree ? (20 + depth(tree)*12.8)*.75 : pick.pick_presentation?.is_swap || pick.kind==='pick_swap' ? 32.8 : 20;
  const scale=Math.min(1,22/height);
  return `<span class="team-block-pick-art" style="zoom:${scale}">${draftAssetGlyph(pick,false,true)}</span>`;
}

function teamBlockMarkup(payload, editable, seasons=[]) {
  const ids=payload?.team_block_player_ids||[], pickIds=payload?.team_block_pick_ids||[], players=payload?.players||[], picks=payload?.picks||[], team=teamLabel(payload?.team||state.dashboardTeam||userTeam());
  const entries=[...ids.map(id=>({id,kind:'player'})),...pickIds.map(id=>({id,kind:'pick'}))];
  const rows=Array.from({length:6},(_,index)=>{
    const entry=entries[index], player=entry?.kind==='player'?players.find(p=>p.id===entry.id):null, pick=entry?.kind==='pick'?picks.find(p=>p.id===entry.id):null;
    if (pick) {
      const label=pick.label || `${pick.season} R${pick.round} ${pick.original_team_abbrev || ''}`;
      const shortLabel=compactPickEntitlementLabel(pick);
      return `<div class="assets-block-row team-block-row is-pick-row"><span class="assets-block-team team-block-pick-icon">${teamBlockPickIcon(pick)}</span><span class="team-block-pick-description" title="${escapeAttr(label)}"><span>${escapeHtml(shortLabel)}</span><button type="button" data-block-remove="${escapeAttr(pick.id)}" data-block-kind="pick" aria-label="Remove ${escapeAttr(label)} from trade block" ${editable?'':'disabled'}>×</button></span><span class="assets-block-value">${blockValueBar(pick.trade_value)}</span><button type="button" class="block-find-trade" data-block-find-trade="${escapeAttr(entry.id)}" data-block-kind="pick" data-block-team="${escapeAttr(team)}" title="Find trades for ${escapeAttr(label)}" aria-label="Find trades for ${escapeAttr(label)}">Find</button></div>`;
    }
    const playerCell=player?`<span class="team-block-player"><button type="button" data-dashboard-player-card="${escapeAttr(player.id)}">${playerNameWithInjuryMarkup(player)}</button><button type="button" data-block-remove="${escapeAttr(player.id)}" aria-label="Remove ${escapeAttr(player.name)} from trade block" ${editable?'':'disabled'}>×</button></span>`:pick?`<span class="team-block-player" title="${escapeAttr(pick.label)}"><span>${escapeHtml(`${pick.season} R${pick.round} ${pick.original_team_abbrev || ''}`)}</span><button type="button" data-block-remove="${escapeAttr(pick.id)}" data-block-kind="pick" aria-label="Remove ${escapeAttr(pick.label)} from trade block" ${editable?'':'disabled'}>×</button></span>`:`<span class="team-block-add-pair"><select data-block-add aria-label="Add player to trade block slot ${index+1}" ${editable?'':'disabled'}><option value="">+ Player</option>${players.filter(p=>!ids.includes(p.id)).map(p=>`<option value="${escapeAttr(p.id)}">${escapeHtml(p.name)}</option>`).join('')}</select><select data-block-add data-block-kind="pick" aria-label="Add draft pick to trade block slot ${index+1}" ${editable?'':'disabled'}><option value="">+ Pick</option>${picks.filter(p=>!pickIds.includes(p.id)).map(p=>`<option value="${escapeAttr(p.id)}">${escapeHtml(p.label)}</option>`).join('')}</select></span>`;
    if (!player) return `<div class="assets-block-row team-block-row is-empty-row">${playerCell}<span class="assets-block-value"></span><span></span></div>`;
    const ratingValue=key=>player?.ratings?.[key]??(key==='offense'?averageNumber([player?.ratings?.shooting,player?.ratings?.creation,player?.ratings?.passing].filter(value=>value!=null),0):undefined);
    const contract=compactBlockContract(player?.contract,player?.contract_terms);
    const teamImage=player
      ? playerHeadshotMarkup(player,'roster-player-headshot')
      : teamLogoSrc(team)?`<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}" />`:escapeHtml(team);
    return `<div class="assets-block-row team-block-row"><span class="assets-block-team">${teamImage}</span>${playerCell}<span>${player?Math.floor(Number(player.age)||0):'—'}</span><span>${escapeHtml(player?.position||'—')}</span>${['overall','offense','defense'].map(key=>`<span>${player?compactRatingBar(ratingValue(key)):'—'}</span>`).join('')}<span title="${escapeAttr(player?.contract||'No contract')}">${escapeHtml(contract)}</span><span class="assets-block-value">${blockValueBar(player?.trade_value ?? pick?.trade_value)}</span>${player||pick?`<button type="button" class="block-find-trade" data-block-find-trade="${escapeAttr(entry.id)}" data-block-kind="${entry.kind}" data-block-team="${escapeAttr(team)}" title="Find trades for ${escapeAttr(player?.name || pick?.label)}" aria-label="Find trades for ${escapeAttr(player?.name || pick?.label)}">Find</button>`:'<span></span>'}</div>`;
  }).join('');
  return `<div class="assets-block-table team-block-table" style="${blockTableStyle(players.filter(player=>ids.includes(player.id)))}"><div class="assets-block-head"><span>Team</span><span>Player</span><span>Age</span><span>Pos</span><span>OVR</span><span>OFF</span><span>DEF</span><span>Contract</span><span class="assets-block-value-heading">Value</span><span>Trade</span></div>${rows}</div>`;
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
function refreshAssetsSurface(target = null) {
  if(state.view!=='dashboard') return;
  if(!target?.isConnected) { renderDashboard(); return; }
  const {rows,seasons,markup}=assetsDesktopCards();
  const seed=document.createElement('div');
  seed.innerHTML=markup;
  const classes={roster:'roster',stats:'stats',contracts:'contracts',payroll:'payroll',picks:'picks','league-block':'block','team-block':'team-block','team-wants':'wants'};
  for(const [id,cls] of Object.entries(classes)) {
    const card=target.querySelector(`[data-board-window="${id}"] .assets-${cls}`);
    const body=card?.querySelector('.assets-panel-body');
    const replacement=seed.querySelector(`.assets-${cls} .assets-panel-body`);
    if(!body||!replacement) continue;
    const scroll=body.querySelector('.linked-roster-scroll')?.scrollTop||0;
    body.replaceChildren(...replacement.childNodes);
    if (id==='picks') setDraftAssetsCardExpanded(card.dataset.draftAssetsExtended==='true',card);
    const tableScroll=body.querySelector('.linked-roster-scroll');
    if(tableScroll) tableScroll.scrollTop=scroll;
    wireAssetsCards(card.parentElement,rows,seasons);
  }
}
function leagueBlockGroups(rows) {
  const top=[...rows].sort((a,b)=>Number(b.overall||0)-Number(a.overall||0)).slice(0,6);
  const groups=[{label:'Top league targets',rows:top}];
  const byTeam=new Map();
  rows.forEach(row=>{const key=row.team_abbrev||'NBA';if(!byTeam.has(key))byTeam.set(key,[]);byTeam.get(key).push(row);});
  [...byTeam.keys()].sort().forEach(team=>groups.push({label:team,team_abbrev:team,rows:byTeam.get(team).slice(0,6)}));
  return groups;
}
function leagueBlockMarkup(rows) {
  const groups=leagueBlockGroups(rows), index=((Number(state.assetsBlockIndex)||0)%Math.max(1,groups.length)+groups.length)%Math.max(1,groups.length), group=groups[index]||{label:'League',rows:[]};
  const entries=group.rows.map(row=>`<div class="assets-block-row">
    <span class="assets-block-team league-block-portrait">${playerHeadshotMarkup(row,'roster-player-headshot')}${!group.team_abbrev?`<img class="league-block-team-badge" src="${escapeAttr(teamLogoSrc(row.team_abbrev))}" alt="${escapeAttr(row.team_abbrev)}" />`:''}</span>
    <button type="button" data-dashboard-player-card="${escapeAttr(row.player_id)}">${playerNameWithInjuryMarkup(row)}</button>
    <span>${Math.floor(Number(row.age)||0)||'—'}</span><span>${escapeHtml(row.position||'—')}</span>
    <span>${compactRatingBar(row.overall)}</span><span>${compactRatingBar(row.offense)}</span><span>${compactRatingBar(row.defense)}</span>
    <span title="${escapeAttr(row.contract||'No contract')}">${escapeHtml(compactBlockContract(row.contract,row.contract_terms))}</span>
    <span class="assets-block-value">${blockValueBar(row.trade_value)}</span>
    <button type="button" class="block-find-trade" data-block-find-trade="${escapeAttr(row.player_id)}" data-block-team="${escapeAttr(row.team_abbrev)}" title="Find trades for ${escapeAttr(row.name)}" aria-label="Find trades for ${escapeAttr(row.name)}">Find</button>
  </div>`).join('');
  return `<div class="assets-block-caption"><span class="league-block-group-label">${group.team_abbrev?`<img src="${escapeAttr(teamLogoSrc(group.team_abbrev))}" alt="${escapeAttr(group.team_abbrev)}" title="${escapeAttr(group.team_abbrev)}" />`:escapeHtml(group.label)}</span><div class="assets-block-nav"><button type="button" data-assets-block-nav="-1" aria-label="Previous players on the block">‹</button><button type="button" data-assets-block-nav="1" aria-label="Next players on the block">›</button></div><b>${index+1}/${groups.length}</b></div>
    <div class="assets-block-table" style="${blockTableStyle(rows)}"><div class="assets-block-head"><span>Team</span><span>Player</span><span>Age</span><span>Pos</span><span>OVR</span><span>OFF</span><span>DEF</span><span>Contract</span><span class="assets-block-value-heading">Value</span><span>Trade</span></div>${entries||'<p class="assets-empty">No players are currently on the block.</p>'}</div>`;
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
    const body=root.querySelector('[data-assets-block-body]');
    if(body){body.innerHTML=leagueBlockMarkup(rows);wireDashboardPlayerCards(body);wireLeagueBlockControls(root);}
  });
}
function assetsDesktopCards() {
  const dash=state.data.dashboard||{},seasons=contractSeasons(rosterRows(dash)).slice(0,4),saved=state.data.assetsDesktop;
  const payload=saved?.key===assetsContextKey()&&saved.dashboard===dash?saved.payload:null;
  const values=new Map((payload?.players||[]).map(p=>[p.id,p]));
  const rows=rosterRows(dash).map(p=>({...p,trade_value:values.get(p.id)?.trade_value,health_risk:values.get(p.id)?.health_risk ?? p.health_risk,upside_remaining:values.get(p.id)?.upside_remaining ?? p.upside_remaining})).sort((a,b)=>(b.trade_value??-1)-(a.trade_value??-1));
  const editable=teamLabel(dash.team||state.dashboardTeam||userTeam())===userTeam();
  const legal=editable&&(dash.legal_actions||[]).some(a=>['trades','draft_trades'].includes(a));
  const message=assetsErrorForContext();
  const error=message?`<p class="assets-empty" role="alert">${escapeHtml(message)}</p><button type="button" data-assets-retry>Retry</button>`:'';
  const panel=(title,body,cls,buttons='',artwork='')=>`<section class="season-command-panel assets-${cls}">${title?seasonPanelHeader(title,buttons,artwork):''}<div class="assets-panel-body">${error}${body}</div></section>`;
  const groups=assetsRosterGroups(seasons);
  const roster=assetsRosterMarkup(rows,groups[0],assetsRosterSort('roster'));
  const stats=assetsRosterMarkup(rows,groups[1],assetsRosterSort('stats'));
  const contracts=assetsRosterMarkup(rows,groups[2],assetsRosterSort('contracts'));
  const picks=payload?.draft_assets || [...(payload?.picks||[]),...(payload?.pick_swaps||[])];
  return {rows,seasons,markup:`<div class="assets-grid">
      ${panel('',roster,'roster')}
      ${panel('',stats,'stats')}
      ${panel('',contracts,'contracts')}
      ${panel('',summaryContractChart(rows,seasons,dash),'payroll')}
      ${panel('',payload?draftAssetsBoard(picks):error?'':'<p class="assets-empty">Loading draft assets…</p>','picks')}
      ${panel('',payload?`<div data-assets-block-body>${leagueBlockMarkup(payload.league_block||[])}</div>`:error?'':'<p class="assets-empty">Loading league block…</p>','block')}
      <div class="assets-trade-launchers">${assetsTradeTools(legal)}</div>
      ${panel('',payload?teamBlockMarkup(payload,editable,seasons):error?'':'<p class="assets-empty">Loading team block…</p>','team-block')}
      ${panel('',typeof teamWantsMarkup==='function'?teamWantsMarkup(payload):'','wants')}
    </div>`};
}
function wireAssetsCards(root, rows, seasons) {
  if(typeof wireTeamWants==='function')wireTeamWants(root,state.data.assetsDesktop?.payload);
  wireDashboardPlayerCards(root);
  wireAssetExtensions(root);
  wireLeagueBlockControls(root);
  const rosterCard=root.matches?.('.assets-roster,.assets-stats,.assets-contracts')?root:root.querySelector('.assets-roster,.assets-stats,.assets-contracts');
  if(rosterCard){
    const id=rosterCard.classList.contains('assets-roster')?'roster':rosterCard.classList.contains('assets-stats')?'stats':'contracts';
    const group=assetsRosterGroups(seasons).find(item=>item.id===id);
    const body=rosterCard.querySelector('.assets-panel-body');
    const wireRoster=()=>wireLinkedRoster(rosterCard,key=>{
      const prior=assetsRosterSort(id);
      const sort={key,direction:prior.key===key&&prior.direction==='desc'?'asc':'desc'};
      state.assetsRosterSortByCard[id]=sort;
      if(id==='roster')state.assetsRosterSort=sort;
      const scroll=body.querySelector('.linked-roster-scroll')?.scrollTop||0;
      body.innerHTML=assetsRosterMarkup(rows,group,sort);
      body.querySelector('.linked-roster-scroll').scrollTop=scroll;
      wireDashboardPlayerCards(body);wireAssetExtensions(body);wireRoster();
    });
    wireRoster();
  }
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
  const seasonal = seasonalClipboardCards(dashboard);
  const viewedTeam=teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam());
  const editable=!state.hydrating && viewedTeam===userTeam();
  const tradeDisabled=!editable||!["trades","draft_trades"].some(action=>clipboardLegalActions().has(action));
  window.CardBoard.mount(target,{save:state.currentSave,assetsRoot:seed,extraCards:[...seasonal,...clipboardPlayerCardWindows()],captureLayoutCards:ids=>structuredClone(state.clipboardPlayerCards.filter(entry=>entry.saveId===String(state.currentSave || "") && ids.includes(entry.id))),restoreLayoutCards:entries=>{
    const restored=[];
    for (const entry of entries) {
      if (entry.saveId!==String(state.currentSave || "") || !entry.id || !entry.body) continue;
      const existing=state.clipboardPlayerCards.find(item=>item.id===entry.id);
      if (existing) Object.assign(existing,structuredClone(entry));
      else state.clipboardPlayerCards.push(structuredClone(entry));
      state.clipboardPlayerCardSequence=Math.max(state.clipboardPlayerCardSequence,Number(entry.id.replace('player-card-','')) || 0);
      restored.push(entry.id);
    }
    return clipboardPlayerCardWindows().filter(card=>restored.includes(card.id));
  },onVisibilityChange:(id,visible)=>{const entry=state.clipboardPlayerCards.find(item=>item.id===id);if(entry) entry.windowOpen=visible;},onLayoutRestored:wirePlayerGameScoreCharts,onOpen:id=>loadOpenedAssetsCard(target,id),onExpandedChange:(id,expanded,card)=>id==="picks"?setDraftAssetsCardExpanded(expanded,card):id==="development"?setDevelopmentCardExpanded(expanded,card):id==="standings"?setStandingsCardExpanded(expanded,card):id==="week"?setWeekCardExpanded(expanded,card):id==="prospects"?setProspectsCardExpanded(expanded,card):id==="staff"?setStaffCardExpanded(expanded,card):id==="league-wire"?setLeagueWireCardExpanded(expanded,card):undefined,onTradeMenuAction:action=>action==="offers"?openTradeOffersModal():action==="market"?openTradeMarketBoard():openTradeRoomModal(action),lockedCards:clipboardLockedCards(),entryLayout:typeof clipboardEntryLayout==="function"?clipboardEntryLayout():null,phaseCommands:clipboardPhaseCommands(),toolbarActions:{simulationDisabled:!editable,tradeDisabled,offerCount:Number(state.data.dashboardOffers?.offers?.length||0)},phaseContext:(state.hydrating || !state.home) ? null : dashboardPhaseKind()==="playoffs" ? `${state.home?.save?.season || ""}:postseason-v2:playoffs` : dashboardPhaseKind()==="draft" && ["odds","reveal"].includes(state.draftPresentationStage) ? `${state.home?.save?.season || ""}:lottery-v2:draft` : `${state.home?.save?.season || ""}:${state.home?.save?.phase || ""}:${dashboardPhaseKind()}`});
  dashboard.querySelectorAll('.card-board-body.assets-desktop').forEach(root=>wireAssetsCards(root.parentElement,rows,seasons));
}
