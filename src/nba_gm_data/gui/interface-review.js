// Review mode uses production renderers with a frozen, explicitly illustrative
// fixture. It never connects a control to a live save or a mutation endpoint.
if (new URLSearchParams(location.search).has('ui-review')) {
  document.addEventListener('DOMContentLoaded', async () => {
    const screen = new URLSearchParams(location.search).get('ui-review') || 'dashboard';
    try {
      const fixture = await fetch('/interface-fixture.json').then(r => r.json());
      document.title = `Preview: ${screen} - NBA GM`;
      const staticFetch = window.fetch.bind(window);
      window.fetch = (input, options) => {
        const url = new URL(input instanceof Request ? input.url : input, location.href);
        if (url.pathname.startsWith('/api/')) return Promise.reject(new Error('Preview only: live API calls are disabled.'));
        return staticFetch(input, options);
      };
      state.currentSave = 'interface-review';
      state.home = fixture.home;
      state.home.save.pending_counts = {};
      state.home.save.phase = 'regular_season';
      state.data = fixture.data;
      state.teams = fixture.teams;
      state.dashboardTeam = userTeam();
      state.tradePartner = 'BOS';
      state.hydrating = false;
      state.data.dashboard.legal_actions = ['trades', 'extensions'];
      state.data.calendar = state.data.dashboardCalendar;
      state.data.standings = state.data.dashboardStandings;
      state.data.offers = state.data.dashboardOffers;
      state.data.events = state.home.league_events;
      const teamFromId = value => String(value || '').replace(/^team_/, '').toUpperCase();
      for (const payload of [state.data.tradeUser, state.data.tradePartner]) {
        for (const pick of payload?.picks || []) {
          const original = String(pick.label || '').match(/R[12]\s+([A-Z]{2,3})\b/)?.[1] || teamFromId(pick.original_team_id) || teamLabel(payload.team);
          pick.original_team_abbrev = original;
          pick.original_team_id ||= `team_${original.toLowerCase()}`;
          pick.protection_summary ||= /protect|condition|convey/i.test(pick.label || '') ? pick.label : '';
        }
        for (const swap of payload?.pick_swaps || []) {
          swap.original_team_abbrevs ||= [...String(swap.label || '').matchAll(/\b([A-Z]{2,3})\b/g)].map(match => match[1]).filter(value => state.teams.includes(value)).slice(-2);
          swap.condition_summary ||= swap.label;
        }
      }
      state.data.tradeUser.league_block ||= state.data.playerFinder.rows.filter(row => row.team_abbrev && row.team_abbrev !== userTeam()).slice(0,36).map((row,index) => ({
        player_id:row.id || row.player_id,name:row.name,team_abbrev:row.team_abbrev,team_id:`team_${String(row.team_abbrev).toLowerCase()}`,
        age:row.age,height:row.height,position:row.position,overall:rating(row,'overall'),offense:rating(row,'offense'),defense:rating(row,'defense'),
        contract:compactSalaryYears(row.salary_by_year),block_score:90-index,
      }));
      const player = fixture.player;
      const candidate = state.data.freeagency.candidates[0];
      state.selectedFreeAgent = candidate?.id;
      const detailFor = id => {
        if (id === player.player_id) return player;
        const row = state.data.playerFinder.rows.find(r => r.id === id || r.player_id === id) || state.data.freeagency.candidates.find(r => r.id === id);
        return {...player, player_id:id, name:row?.name || player.name, ratings:row?.display_ratings || row?.ratings || player.ratings, position:row?.position || player.position, age:row?.age || player.age};
      };
      action = async (name, payload = {}) => {
        const responses = {
          team_dashboard: state.data.dashboard,
          team_assets: payload.team === 'BOS' ? state.data.tradePartner : state.data.tradeUser,
          player_finder: state.data.playerFinder,
          player_card: detailFor(payload.player_id),
          box_score: fixture.box,
          morale: state.data.dashboardMorale,
          user_trade_offers: state.data.dashboardOffers,
          staff_room: state.data.staff,
          free_agency_room: state.data.freeagency,
          draft_room: state.data.draft,
          standings: state.data.dashboardStandings,
          league_leaders: state.data.leagueLeaders,
          league_traits: state.data.leagueTraits,
          league_events: state.home.league_events,
          set_rotation_minutes: {status:'updated',dashboard:state.data.dashboard},
          social_feed: state.data.social || {},
        };
        if (name in responses) return responses[name];
        showToast('Preview only. No save was changed.');
        throw new Error('This action is available in the game.');
      };
      const showModal = (kind,title,body,other={}) => {state.modal={kind,title,body,...other};renderModal();};
      const phase = value => {state.home.save.phase=value;state.view='dashboard';render();};

      // Phase fixture keeps the same roster and currency context across screens.
      const market=state.data.freeagency;
      market.state={status:'active',day:3,day_count:5};
      market.phase='free_agency';
      market.cap.max_offer_aav_millions=32;
      market.candidates.forEach((p,i)=>{
        p.ask_change_millions=i%3===0?-1.2:i%5===0?.6:0;
        if(i<5){p.offer_count=2;p.highest_offer={team_abbrev:['BOS','NYK','DEN','ATL','DAL'][i],aav_millions:p.ask_millions*.95,years:3,interest_score:74-i*5};}
      });
      const series=[];
      [['East',['BOS','ORL','CLE','IND','NYK','ATL','MIL','MIA']],['West',['OKC','SAC','DEN','LAL','MIN','HOU','MEM','GSW']]].forEach(([conference,teams])=>{
        for(let i=0;i<4;i++) series.push({id:`${conference}-${i}`,conference,round:'first_round',teams:teams.slice(i*2,i*2+2),score:i%2?[2,2]:[3,1],status:'in_progress',game_ids:fixture.box?[fixture.box.game_id]:[]});
      });
      state.data.playoffs={phase:'playoffs',round:'first_round',status:'in_progress',current_date:'2027-04-26',series};
      state.data.playoffLeaders={leaders:state.data.playerFinder.rows.slice(0,9).map(r=>({player:{name:r.name},team_abbrev:r.team_abbrev,points_per_game:r.points_per_game}))};
      state.data.draft.state={...state.data.draft.state,status:'in_progress',total_picks:60};
      state.data.draft.presentation_stage='draft';
      state.data.draft.current_selection.selection ||= state.data.draft.current_selection.pick;
      state.data.draft.current_selection.team ||= state.data.draft.board_context_team;
      if(!(state.data.draft.lottery?.odds || []).length) {
        state.data.draft.lottery={odds:state.teams.slice(0,14).map((team,i)=>({team,seed:i+1,odds:[.14,.14,.14,.125,.105,.09,.075,.06,.045,.03,.02,.015,.01,.005][i]})),reveal:state.teams.slice(0,14).map((team,i)=>({owner_team:team,original_team:team,pick:i+1,starting_seed:i+1,movement:0}))};
      }
      render();
      if(screen==='startup'){state.currentSave='';state.saves=[];render();}
      if(screen==='player') await dashboardPlayerCard(player.player_id);
      if(screen==='development') openTeamDevelopmentModal();
      if(screen==='player-finder') await openPlayerFinderModal();
      if(screen==='trade-builder' || screen==='trade-finder') {
        state.selectedFrom = [state.data.tradeUser.assets.find(a=>a.kind==='player')].filter(Boolean);
        state.selectedTo = [state.data.tradePartner.assets.find(a=>a.kind==='player')].filter(Boolean);
        await openTradeRoomModal(screen==='trade-finder'?'finder':'builder');
      }
      if(screen==='trade-offers') await openTradeOffersModal();
      if(screen==='settings') openSettingsModal();
      if(screen==='commands') GameInterface.openPalette();
      if(screen==='shortcuts') GameInterface.openPalette(true);
      if(screen==='standings') openStandingsModal();
      if(screen==='league-wire') openLeagueEventsModal();
      if(screen==='box-score' && fixture.box) await openBoxScore(fixture.box.game_id);
      if(['calendar','staff','league','social'].includes(screen)) {state.view=screen;render();}
      if(screen==='staff-negotiation') {
        const member=marketCandidates(state.data.staff.market)[0];
        if(member) openDashboardStaffNegotiation(member.id);
      }
      if(screen==='free-agency') phase('free_agency');
      if(screen==='re-signing'){market.phase='re_signing';market.re_signing={day:1,day_count:2};phase('re_signing');}
      if(screen==='negotiation'){phase('free_agency');await openFreeAgentNegotiation(candidate.id);}
      if(screen==='comparison'){phase('free_agency');state.freeAgentCompareIds=market.candidates.slice(0,3).map(p=>p.id);openFreeAgentComparison();}
      if(screen==='extension'){
        const c={player_id:player.player_id,name:player.name,eligible:true,safe_years:4,preferred_years:3,max_aav_by_years:{3:48},projected_aav_millions:42,cap_projection:Object.entries(player.cap_by_year||{}).map(([season,v])=>({season,...v}))};
        const room={candidates:[c],team:userTeam(),date:'2027-07-01'};
        showModal('contractExtension','Contract Extension',extensionNegotiationBody(room,c.player_id,null,player),{room,selectedPlayerId:c.player_id,detail:player});
      }
      if(screen==='playoffs') phase('playoffs');
      if(screen==='draft') phase('draft');
      if(screen==='prospects'){state.view='draft';render();}
      if(screen==='lottery-odds'){state.data.draft.presentation_stage='odds';phase('draft_lottery');}
      if(screen==='lottery-reveal'){state.data.draft.presentation_stage='reveal';phase('draft_lottery');}
      if(screen==='draft-summary'){
        const board=draftBoardRows(state.data.draft.draft_board);
        state.data.draft.state.status='completed';state.data.draft.current_selection={};
        state.data.draft.draft_timeline=board.map((p,i)=>({overall_pick:i+1,pick:i+1,team:state.teams[i%30],prospect_name:p.name,prospect:p,round:i<30?1:2,status:'selected'}));phase('draft');
      }
      if(screen==='fantasy-draft'){
        const available=state.data.playerFinder.rows.slice(0,120).map(p=>({...p,player_id:p.id || p.player_id,ratings:p.display_ratings||p.ratings,is_watchlisted:false}));
        state.data.fantasyDraft={status:'in_progress',current_team:state.teams[0],viewer_team:state.data.dashboard.team,pick_number:11,total_picks:450,round:1,available_players:available,viewer_roster:[],watchlist:available.slice(1,5),draft_order:state.teams,recent_picks:[],is_viewer_turn:false};
        state.selectedFantasyPlayer=available[0]?.player_id;phase('fantasy_draft');
      }
      if(screen==='cutdown'){state.home.save.pending_counts={cutdowns:1};render();}
      if(screen==='staff-retention'){
        const member=(state.data.staff.team_report.gameplay_staff_slots||[])[0]||{};
        state.data.staffRetention={status:'required',window:{slot:member.slot,team_abbrev:userTeam()},staff:member,staff_grade:member.grade,budget:{annual_budget_millions:37,current_spend_millions:24},max_offer_millions:12,ask_millions:8,ask_years:3,market:{candidates:marketCandidates(state.data.staff.market).slice(0,8)}};
        state.home.save.pending_counts={staff:1};render();
      }
      stopDashboardRotatorClock();
      const skin = new URLSearchParams(location.search).get('skin');
      if (['carbon','silver'].includes(skin)) {
        document.body.dataset.reviewSkin=skin;
        const sheet=document.createElement('link');sheet.rel='stylesheet';sheet.href='/design-studies.css';document.head.append(sheet);
        await new Promise(resolve=>{sheet.onload=resolve;sheet.onerror=resolve;});
      }
      document.dispatchEvent(new CustomEvent('interface-preview-ready',{detail:{screen,fixture}}));
      GameInterface.enhance();
      await document.fonts.ready;
      await Promise.all([...document.images].map(i=>i.complete?null:new Promise(resolve=>{i.onload=resolve;i.onerror=resolve;})));
      document.body.dataset.reviewReady=screen;
    } catch(error) {
      document.body.dataset.reviewError=error.message;
      console.error(error);
    }
  });
}
