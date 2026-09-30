/* Deliberately isolated design studies; only the review harness can invoke them. */
document.addEventListener('interface-preview-ready', ({detail:{fixture}}) => {
  const params=new URLSearchParams(location.search);
  const screen=params.get('dense');
  if (!screen) return;
  const supported=['roster','player','trade-builder','trade-finder','free-agency','negotiation','draft','playoffs','staff'];
  if (!supported.includes(screen)) return;
  // Player sizing has graduated into the shared renderer, not a second mockup.
  if(screen==='player') { document.body.dataset.conceptReady=screen;return; }
  const e=escapeHtml, n=v=>v==null?'—':Number(v).toFixed(1), m=v=>v==null?'—':money(v);
  const dash=fixture.data.dashboard, roster=rosterRows(dash), user=fixture.data.tradeUser, other=fixture.data.tradePartner;
  const market=fixture.data.freeagency, player=fixture.player, staff=fixture.data.staff.team_report.gameplay_staff_slots || [];
  const prospects=draftBoardRows(fixture.data.draft.draft_board), years=Object.keys(dash.cap_by_year).sort().slice(0,4);
  const name=p=>p.name||p.label||'—', r=p=>p.display_ratings||p.ratings||{}, id=p=>p.id||p.player_id;
  const logo=t=>`<span class="density-logo"><img src="${e(teamLogoSrc(teamLabel(t)))}" alt="">${e(teamLabel(t))}</span>`;
  const btn=(label,route,key='')=>`<button type="button" class="density-action" data-study-route="${route}">${label}${key?`<span class="shortcut-hint">${key}</span>`:''}</button>`;
  const table=(heads,rows,widths=[])=>`<table class="density-table" data-local-sort>${widths.length?`<colgroup>${widths.map(w=>`<col style="width:${w}%">`).join('')}</colgroup>`:''}<thead><tr>${heads.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(c=>`<tr>${c.map(v=>`<td title="${escapeAttr(String(v??'').replace(/<[^>]*>/g,''))}">${v??'—'}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const person=p=>`<button type="button" data-study-player="${e(id(p)||'')}">${e(name(p))}</button>`;
  const mini=v=>`<span class="density-mini"><i><b style="${performanceBarStyle(Number(v||0))}"></b></i>${v==null?'—':Math.round(v)}</span>`;
  const bars=items=>`<div class="density-bars">${items.map(([label,value])=>`<div class="density-bar"><span>${e(label)}</span><i><b style="${performanceBarStyle(Number(value||0))}"></b></i><strong>${n(value)}</strong></div>`).join('')}</div>`;
  const stats=items=>`<div class="density-statline">${items.map(([label,value])=>`<div><span>${e(label)}</span><strong>${value}</strong></div>`).join('')}</div>`;
  const card=(title,body,x,y,w,h,action='',cls='')=>`<section class="density-card ${cls}" style="grid-column:${x}/span ${w};grid-row:${y}/span ${h}"><header><h2>${title}</h2>${action}</header><div class="density-body">${body}</div></section>`;
  const wire=(fixture.home.league_events?.events||fixture.home.league_events||[]);
  const news=Array.isArray(wire)?wire.slice(0,8):[];
  const newsTable=()=>table(['Date','Transaction'],news.map(x=>[e(x.date||''),e(x.summary||x.text||x.description||x.headline||x.kind||'')]),[16,84]);
  const capBars=(caps=dash.cap_by_year,players=roster)=>{
    const entries=Object.entries(caps).slice(0,4),max=Math.max(...entries.flatMap(([,c])=>[c.salary_total_millions||0,c.hard_cap_millions||0]))*1.08;
    const colors=['#789aaf','#879e90','#a99d80','#7c879b','#a09096','#688a8b'];
    return `<div class="density-cap">${entries.map(([year,c])=>{
      const payroll=Number(c.salary_total_millions||0),segments=players.map((p,i)=>({name:name(p),salary:Number(p.salary_by_year?.[year]||0),color:colors[i%colors.length]})).filter(p=>p.salary>0);
      const covered=segments.reduce((sum,p)=>sum+p.salary,0),denominator=Math.max(covered,payroll,1);
      if(payroll>covered)segments.push({name:'Other commitments',salary:payroll-covered,color:'#6d7680'});
      return `<div class="density-cap-year"><span>${shortSeasonLabel(year)}</span><div class="density-cap-rail"><div class="density-cap-stack" style="height:${payroll/max*100}%">${segments.map(p=>`<i style="height:${p.salary/denominator*100}%;background:${p.color}" title="${e(p.name)} ${m(p.salary)}"></i>`).join('')}</div><em style="bottom:${c.tax_line_millions/max*100}%" title="Tax ${m(c.tax_line_millions)}"></em><em class="hard" style="bottom:${c.hard_cap_millions/max*100}%" title="Hard cap ${m(c.hard_cap_millions)}"></em></div><small>${m(payroll)}</small></div>`;
    }).join('')}</div>`;
  };
  const capTable=(caps=dash.cap_by_year)=>table(['Year','Payroll','Tax room','Hard room'],Object.entries(caps).slice(0,4).map(([y,c])=>[shortSeasonLabel(y),m(c.salary_total_millions),m(c.tax_space_millions),m(c.hard_cap_space_millions)]),[17,27,28,28]);
  const projectedCap=(caps,sends,receives)=>Object.fromEntries(Object.entries(caps).map(([year,c])=>{const delta=receives.reduce((s,p)=>s+Number(p.salary_by_year?.[year]||0),0)-sends.reduce((s,p)=>s+Number(p.salary_by_year?.[year]||0),0);return [year,{...c,salary_total_millions:c.salary_total_millions+delta,tax_space_millions:c.tax_space_millions-delta,hard_cap_space_millions:c.hard_cap_space_millions-delta}];}));
  const pickTable=(p=user)=>table(['Pick','Value'],(p.assets||[]).filter(x=>x.kind!=='player').map(x=>[e(x.label),n(x.trade_value)]),[80,20]);
  const briefPlayers=(players,kind='stats')=>table(['Player','Age','Pos','OVR','Off','Def',kind==='value'?'Value':'MPG'],players.map(p=>[person(p),Math.floor(p.age),p.position,mini(r(p).overall),mini(r(p).offense??r(p).creation),mini(r(p).defense),n(kind==='value'?p.trade_value:(p.minutes_projection??p.mpg))]),[32,7,8,13,13,13,14]);
  const rosterTable=(players,withValue=false)=>{
    const fields=['overall','shooting','creation','passing','defense','rebounding','rim_deterrence','athleticism','portability'];
    const heads=['Player','Age','Pos',...(withValue?['Value']:[]),'OVR','Shot','Cre','Pass','Def','Reb','Rim','Ath','Port','GP','MPG','PTS','REB','AST','STL','BLK','Risk','Up',...years.map(shortSeasonLabel)];
    return table(heads,players.map(p=>[person(p),p.age,p.position,...(withValue?[n((user.assets.find(a=>id(a)===id(p))||p).trade_value)]:[]),...fields.map(k=>n(r(p)[k])),p.gp_display||p.games||'—',n(p.minutes_projection||p.mpg),n(p.points_per_game||p.ppg),n(p.rebounds_per_game||p.rpg),n(p.assists_per_game||p.apg),n(p.steals_per_game),n(p.blocks_per_game),n(p.health_risk),n(p.upside_remaining),...years.map(y=>{const cell=assetContractCell(p,y,years);return cell.__html||cell;})]),[12,3,4,...Array(heads.length-3).fill(81/(heads.length-3))]);
  };
  const rotationRating=key=>roster.reduce((sum,p)=>sum+Number(r(p)[key]||0)*Number(p.minutes_projection||0),0)/Math.max(1,roster.reduce((sum,p)=>sum+Number(p.minutes_projection||0),0));
  const shape=()=>`<div class="density-radars">${fantasyPlayerRadar('Offense',[['Shooting',rotationRating('shooting')],['Spacing',rotationRating('range')],['Creation',rotationRating('creation')],['Passing',rotationRating('passing')],['Rim pressure',rotationRating('rim_pressure')],['Portability',rotationRating('portability')]],'offense')}${fantasyPlayerRadar('Defense',[['Defense',rotationRating('defense')],['Rim protect',rotationRating('rim_deterrence')],['Rebound',rotationRating('rebounding')],['Effort',rotationRating('def_effort')],['Navigation',rotationRating('screen_nav')],['Athleticism',rotationRating('athleticism')]],'defense')}</div>`;
  const positional=()=>table(['Position','Players','Minutes','OVR'],['PG','SG','SF','PF','C'].map(pos=>{const rows=roster.filter(p=>p.position?.split('/')[0]===pos);return [pos,rows.length,rows.reduce((v,p)=>v+Number(p.minutes_projection||0),0),n(averageNumber(rows.map(p=>r(p).overall)))];}));
  const expiring=()=>table(['Player','Age','Salary'],roster.filter(p=>Number(p.salary_by_year?.[years[0]])&&!Number(p.salary_by_year?.[years[1]])).map(p=>[person(p),p.age,m(p.salary_by_year[years[0]])]),[60,12,28]);
  const staffTable=(rows=staff)=>table(['Name','Role','Grade','Contract'],rows.map(s=>[e(s.name),e({head_coach:'HC',defensive_coordinator:'Defense',offensive_coordinator:'Offense',development_lead:'Development',scouting_lead:'Scouting',performance_lead:'Performance'}[s.slot]||s.slot),mini(s.grade),`${m(s.contract?.annual_salary_millions||s.asking_salary_millions)} × ${s.contract?.years_remaining||s.asking_years}`]),[33,24,23,20]);
  const valueBar=assets=>{const parts=tradeValuePiecesFromAssets(assets),total=assets.reduce((s,a)=>s+Number(a.trade_value||0),0);const chunks=[['Players',assets.filter(a=>a.kind==='player').reduce((s,a)=>s+Number(a.trade_value||0),0),'#66a384'],['Picks',assets.filter(a=>a.kind==='pick').reduce((s,a)=>s+Number(a.trade_value||0),0),'#cfb963'],['Swaps',assets.filter(a=>a.kind==='pick_swap').reduce((s,a)=>s+Number(a.trade_value||0),0),'#7b9fcb']];return `<div class="density-value"><span>Package value ${n(total)}</span><div class="density-value-track">${chunks.map(([,v,c])=>`<i style="width:${Math.max(0,v)/Math.max(1,total)*100}%;background:${c}"></i>`).join('')}</div><div class="density-legend">${chunks.map(([l,,c])=>`<span><i style="background:${c}"></i>${l}</span>`).join('')}</div></div>`;};
  const packageView=(assets)=>`<div class="density-package">${assets.map(p=>`<div>${person(p)}<span>${m(p.salary_by_year?.[years[0]])}</span></div>`).join('')}${valueBar(assets)}</div>`;
  const quality=()=>bars([['Overall',dash.team_identity.metrics.overall],['Offense',dash.team_identity.metrics.offense],['Defense',dash.team_identity.metrics.defense],['Depth',dash.team_identity.metrics.depth]]);
  const prospectTable=()=>table(['Prospect','Pos','Age','Now','Potential','Fit','Range','Scouted'],prospects.map(p=>[person(p),p.position,p.age,n(p.now),n(p.potential),n(p.fit),`${p.prospect.rank_range?.low||p.rank}–${p.prospect.rank_range?.high||p.rank}`,mini(p.scoutedPct)]),[25,9,6,10,10,10,12,18]);
  const availability=()=>table(['Player','Status','GP'],roster.filter(p=>isPlayerInjured(p.health)||Number(p.health_risk)>3).map(p=>[person(p),e(p.health?.label||'Available'),p.gp_display||'—']),[48,32,20]);
  const trendRows=()=>table(['Player','Season Δ','MPG','Upside'],roster.map(p=>[person(p),n(p.development_delta||p.overall_delta||0),n(p.minutes_projection),n(p.upside_remaining)]),[45,20,15,20]);
  const topSix=briefPlayers(roster.slice(0,6));
  let cards=[],title='',actions='';
  if(screen==='roster') {
    title='Roster';actions=btn('Trade builder','trade-builder','G T');
    cards=[card('Ratings · season production · contracts',rosterTable(roster),1,1,12,7),card('Team shape',shape(),1,8,4,5),card('Position coverage',positional(),5,8,3,3),card('Health & availability',availability(),5,11,3,2),card('Four-year payroll',capBars(),8,8,3,5),card('Team signals',quality(),11,8,2,5)];
  } else if(screen==='player') {
    title=player.name;actions=btn('Roster','roster')+btn('Trade builder','trade-builder','G T');
    cards=[card('Player',stats([['OVR',n(player.ratings.overall)],['Age',player.age],['Risk',n(player.health_risk)],['Upside',n(player.upside_remaining)]]),1,1,3,2),
      card('Complete ratings',`<div class="approved-rating-rail">${playerCardRatingRows(player.ratings).map(([l,v,k])=>playerCardRatingBar(l,v,k,player)).join('')}</div>`,1,3,3,10),
      card('Court influence',spatialHeatmapMarkup(player.spatial_profile),4,1,6,4,'','density-court'),
      card('Offensive / defensive shape',`<div class="density-radars">${fantasyPlayerRadar('Offense',[['Shot',player.ratings.shooting],['Creation',player.ratings.creation],['Pass',player.ratings.passing],['Rim',player.ratings.rim_pressure],['Range',player.ratings.range],['Handle',player.ratings.handle]],'offense')}${fantasyPlayerRadar('Defense',[['Defense',player.ratings.defense],['Effort',player.ratings.def_effort],['Rim',player.ratings.rim_deterrence],['Rebound',player.ratings.rebounding],['Athleticism',player.ratings.athleticism],['Navigation',player.ratings.screen_nav]],'defense')}</div>`,4,5,6,4),
      card('Latest season',table(['GP','MPG','PTS','REB','AST','STL','BLK','TO','FTA','FT%'],[[player.season.games,...['mpg','ppg','rpg','apg','spg','bpg','topg','fta_per_game','ft_pct'].map(k=>n(player.season[k]))]]),4,9,6,1),
      card('Last 30 games · Game score',approvedGameScoreChart(player),4,10,6,3),card('Payroll share',approvedCapShareChart(player),10,1,3,5),card('Six-season salary',approvedSalaryLedger(player),10,6,3,3),card('Last five games',approvedRecentGames(player),10,9,3,4)];
  } else if(screen==='trade-builder') {
    title='Trade builder';actions=btn('Trade finder','trade-finder','G B');
    const outgoing=user.assets.filter(a=>a.kind==='player').slice(1,3),incoming=other.assets.filter(a=>a.kind==='player').slice(1,2);
    const myCap=projectedCap(user.cap_by_year,outgoing,incoming),theirCap=projectedCap(other.cap_by_year,incoming,outgoing);
    cards=[card(`${logo(user.team)} Player assets`,briefPlayers(user.assets.filter(a=>a.kind==='player'),'value'),1,1,3,8),card('My draft assets',pickTable(),1,9,3,4),
      card('Miami sends',packageView(outgoing),4,1,3,4),card('Boston sends',packageView(incoming),7,1,3,4,btn('Change team','player-finder')),
      card('Four-year impact · Miami',capBars(myCap,[...user.assets.filter(a=>a.kind==='player'&&!outgoing.includes(a)),...incoming])+capTable(myCap),4,5,3,7,'','density-cap-combined'),card('Four-year impact · Boston',capBars(theirCap,[...other.assets.filter(a=>a.kind==='player'&&!incoming.includes(a)),...outgoing])+capTable(theirCap),7,5,3,7,'','density-cap-combined'),
      card('Legality',`<p class="density-note">Not evaluated</p>`,4,12,6,1,btn('Evaluate package','trade-builder')),
      card(`${logo(other.team)} Player assets`,briefPlayers(other.assets.filter(a=>a.kind==='player'),'value'),10,1,3,8),card('Boston draft assets',pickTable(other),10,9,3,4)];
  } else if(screen==='trade-finder') {
    title='Trade finder';actions=btn('Builder','trade-builder','G T');
    cards=[card('Assets to shop',briefPlayers(user.assets.filter(a=>a.kind==='player'),'value'),1,1,4,7,btn('Edit package','trade-builder')),card('Available returns · sample',briefPlayers(other.assets.filter(a=>a.kind==='player'),'value'),5,1,8,7,btn('Inspect package','trade-builder')),
      card('My pick inventory',pickTable(),1,8,4,5),card('My roster coverage',positional(),5,8,3,5),card('Current cap capacity',capBars(),8,8,3,5),card('Team needs',quality(),11,8,2,5)];
  } else if(screen==='free-agency'||screen==='negotiation') {
    title=screen==='free-agency'?'Free agency':'Contract negotiation'; actions=btn('Roster','roster')+btn('Trade room','trade-builder','G T');
    const selected=market.candidates[0],offers=market.candidates.slice(0,6).map(p=>[person(p),p.highest_offer?logo(p.highest_offer.team_abbrev):'—',m(p.highest_offer?.aav_millions),mini(p.highest_offer?.interest_score)]);
    const offerAav=Math.min(selected.ask_millions,market.cap.max_offer_aav_millions),offerYears=selected.ask_years||4;
    const salaryByYear=Object.fromEntries(years.map((year,i)=>[year,i<offerYears?offerAav:0]));
    const offeredCap=projectedCap(dash.cap_by_year,[],[{salary_by_year:salaryByYear}]);
    const salaryLedger=table(['Season','Salary','Payroll','Tax room','Hard room'],Array.from({length:6},(_,i)=>{
      const start=Number(years[0].slice(0,4))+i,year=`${start}-${String(start+1).slice(-2)}`,cap=offeredCap[year];
      return [year,m(i<offerYears?offerAav:0),m(cap?.salary_total_millions),m(cap?.tax_space_millions),m(cap?.hard_cap_space_millions)];
    }));
    const marketRows=table(['Player','Age','Pos','OVR','Shot','Create','Pass','Def','Reb','Rim','MPG','PTS','REB','AST','Ask','Move','Bid'],market.candidates.map(p=>[person(p),p.age,p.position,...['overall','shooting','creation','passing','defense','rebounding','rim_deterrence'].map(k=>n(r(p)[k])),n(p.mpg),n(p.ppg),n(p.rpg),n(p.apg),m(p.ask_millions),m(p.ask_change_millions),m(p.highest_offer?.aav_millions)]),[15,...Array(16).fill(85/16)]);
    if(screen==='free-agency') cards=[card('Player market',marketRows,1,1,9,8,btn('Market','free-agency')+btn('Shortlist','free-agency')+btn('My offers','free-agency')+btn('Compare','comparison')),
      card(e(selected.name),bars([['Shooting',r(selected).shooting],['Creation',r(selected).creation],['Defense',r(selected).defense],['Fit',selected.team_fit_score]]),10,1,3,4,btn('Build offer','negotiation')),
      card('Live offers',table(['Player','Team','Offer','Interest'],offers,[40,16,20,24]),10,5,3,3),card('Four-year cap',capBars(),10,8,3,5),
      card('Expiring contracts',expiring(),1,9,3,4),card('Roster coverage',positional(),4,9,3,4),card('League transactions',newsTable(),7,9,3,4)];
    else cards=[card('Complete ratings',bars(Object.entries(r(selected)).filter(([k])=>k!=='overall').map(([k,v])=>[rowLabel(k),v])),1,1,3,12),card(e(selected.name),stats([['Asking AAV',m(selected.ask_millions)],['Offer AAV',m(Math.min(selected.ask_millions,market.cap.max_offer_aav_millions||32))],['Years',selected.ask_years||4],['Fit',n(selected.team_fit_score)]]),4,1,6,2),
      card('Interest breakdown · sample',bars([['Offer versus ask',92],['Team fit',selected.team_fit_score],['Financial room',70],['Market competition',65]]),4,3,3,5),card('Competing offers · sample',table(['Team','AAV','Years','Interest'],offers.slice(0,3).map((o,i)=>[logo(['BOS','NYK','DEN'][i]),m(selected.ask_millions-i),3,mini(80-i*8)])),7,3,3,5),
      card('Offer cap impact',capBars(offeredCap),10,1,3,7),card('Six-season salary & team position',salaryLedger,4,8,6,5,btn('Submit offer','negotiation')),card('Health & upside',bars([['Health risk',selected.health_risk],['Upside',selected.upside_remaining],['Trade value',selected.trade_value]]),10,8,3,5)];
  } else if(screen==='draft') {
    title='Draft';actions=btn('Sim current pick','draft','S E')+btn('Sim to my pick','draft','S P')+btn('Roster','roster');
    const selected=prospects[0];
    cards=[card('Prospect board',prospectTable(),1,1,8,8,btn('Compare','comparison')),card('Draft order',table(['Pick','Team','Status'],(fixture.data.draft.upcoming_order||[]).map((p,i)=>[p.pick||i+1,logo(p.team||p.owner_team||p.owner_team_id),'Upcoming']),[15,60,25]),9,1,4,6),
      card(e(selected.name),bars([['Now',selected.now],['Potential',selected.potential],['Floor',selected.floor],['Ceiling',selected.ceiling],['Fit',selected.fit],['Scouted',selected.scoutedPct]]),9,7,4,6,btn('Player card','player')),
      card('My draft capital',pickTable(),1,9,3,4),card('Rotation coverage',positional(),4,9,3,4),card('Rookie payroll room',capTable(),7,9,2,4)];
  } else if(screen==='playoffs') {
    title='Playoffs';actions=btn('One game / series','playoffs','S E')+btn('Finish round','playoffs','S R')+btn('Roster','roster');
    cards=[card('Bracket',`<div class="playoff-command-center density-bracket">${playoffBracket(state.data.playoffs.series)}</div>`,1,1,8,8),card('My rotation',topSix,9,1,4,4,btn('Box score','box-score')),card('My team shape',shape(),9,5,4,4),
      card('Playoff leaders · sample',table(['Player','Team','GP','MPG','PTS','REB','AST'],fixture.data.playerFinder.rows.slice(0,8).map(p=>[person(p),logo(p.team_abbrev),p.games||'—',n(p.mpg||p.minutes_per_game),n(p.ppg||p.points_per_game),n(p.rpg||p.rebounds_per_game),n(p.apg||p.assists_per_game)]),[32,13,7,12,12,12,12]),1,9,5,4),card('Health & availability',availability(),6,9,3,4),card('Coaching staff',staffTable(),9,9,4,4)];
  } else if(screen==='staff') {
    title='Coaching staff';actions=btn('Roster','roster');
    cards=[card('Assigned staff',staffTable(),1,1,8,4),card('Budget',stats([['Spent',m(fixture.data.staff.team_report.budget.annual_spend_millions)],['Budget',m(fixture.data.staff.team_report.budget.annual_budget_millions)],['Available',m(fixture.data.staff.team_report.budget.available_millions)],['Roles',staff.length]]),9,1,4,3),
      card('Staff market',staffTable(fixture.data.staff.market.candidates),1,5,8,8,btn('Negotiate','staff-negotiation')),card('Coaching effects',bars(staff[0].effect_rows.map(x=>[x.label,x.bar_value])),9,4,4,4),card('Morale & job security',table(['Staff','Morale','Security'],staff.map(s=>[e(s.name),mini(s.morale),mini(s.job_security)]),[44,28,28]),9,8,4,5)];
  }
  closeAllModals();
  document.getElementById('app').inert=false;
  document.getElementById('roomNavigation')?.remove();
  els.content.innerHTML=`<div class="density-screen"><header class="density-top">${btn('This season','dashboard','G H')}${logo(user.team)}<h1>${e(title)}</h1><time>${screen.includes('agency')?'Day 3 of 5':e(fixture.home.save.current_date)}</time>${actions}${btn('Settings','settings','G ,')}</header><div class="density-grid">${cards.join('')}</div><footer class="density-wire"><span>League wire</span><p>${e(news[0]?.description||news[0]?.text||news[0]?.headline||'Trade and signing updates')}</p>${btn('View all','league-wire','G N')}</footer></div>`;
  document.body.classList.add('density-preview');
  els.content.addEventListener('click',event=>{
    const route=event.target.closest('[data-study-route]');
    if(route){const target=route.dataset.studyRoute;const next=new URLSearchParams({ 'ui-review':target,skin:params.get('skin')||'carbon'});if(supported.includes(target))next.set('dense',target);location.search=next.toString();}
    const p=event.target.closest('[data-study-player]');if(p)dashboardPlayerCard(p.dataset.studyPlayer);
  });
  GameInterface.enhance(els.content);
  document.body.dataset.conceptReady=screen;
});
