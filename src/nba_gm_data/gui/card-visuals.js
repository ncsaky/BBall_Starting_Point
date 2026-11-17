/* Card-specific vector icons shared by the gallery and window switcher. */
(() => {
  const ink='#344d61', blue='#497fa8', pale='#dbe8f2', green='#60966d', gold='#ba9250', gray='#b9c5ce', line='#c5cfd7';
  const escape=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
  const rect=(x,y,w,h,fill='#eef2f5',stroke='none',radius=0)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}"/>`;
  const path=(d,fill='none',stroke=ink,width=1.6)=>`<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;
  const circle=(x,y,r,fill='none',stroke=ink,width=1.5)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`;
  const text=(x,y,value,size=7,color=ink,anchor='start',weight=400)=>`<text x="${x}" y="${y}" font-family="Arial,sans-serif" font-size="${size}" fill="${color}" text-anchor="${anchor}" font-weight="${weight}">${escape(value)}</text>`;
  const person=(x,y,s=1)=>`<g transform="translate(${x} ${y}) scale(${s})">${circle(0,0,3.4,pale)}${path('M-6 12v-4c0-5 12-5 12 0v4z',pale)}</g>`;
  const bars=(x,y,width=12)=>[0,1,2].map((n)=>rect(x,y+n*6,width,2.5,gray)+rect(x,y+n*6,width*(.8-n*.2),2.5,blue)).join('');
  const sheet=()=>rect(7,4,20,27,'#f8fafb',ink,2)+path('M12 10h10M12 15h10M12 20h6', 'none',gray);
  const jersey=()=>path('M12 5l-6 3 3 8 4-2v15h14V14l4 2 3-8-6-3c-2 6-12 6-14 0z',pale);
  const trophy=()=>path('M10 5h14v8c0 10-14 10-14 0z', '#ede0bd',gold)+path('M10 8H5v4c0 5 5 6 8 6M24 8h5v4c0 5-5 6-8 6M17 22v6M11 29h12','none',gold,1.8);
  const radar=(fill=pale)=>path('M17 4l13 10-5 16H9L4 14z','none',gray)+path('M17 4v26M4 14l21 16M30 14L9 30','none',gray,.7)+path('M17 8l10 8-5 10-10 2-6-12z',fill,blue,1.4);
  const motifs={
    identity:()=>rect(3,6,28,23,pale,ink,1)+path('M17 6v23M3 11h7v13H3M31 11h-7v13h7')+circle(17,17.5,5),
    signals:()=>bars(5,8,23)+path('M25 27l4-4 4 4M29 23v8','none',green),
    morale:()=>person(9,12,.8)+person(25,12,.8)+path('M17 6c-6-7-12 2 0 9 12-7 6-16 0-9z','#e9c4c8','#ab6870',1.2),
    factors:()=>[0,1,2,3].map((n)=>rect(4,6+n*7,26,3,gray)+rect(4,6+n*7,16-n*2,3,n%2?green:blue)+path(`M${12+n*4} ${4+n*7}v7`,'none',ink,1)).join(''),
    offense:()=>radar()+circle(27,27,5,'#eee0c9',gold)+path('M22 27h10M27 22v10','none',gold,.8),
    defense:()=>radar()+path('M22 19l8 3v5c0 5-8 7-8 7s-8-2-8-7v-5z',pale,ink,1.2),
    standings:()=>[0,1,2].map((n)=>text(5,10+n*10,n+1,7,ink,'middle',700)+rect(10,5+n*10,20,6,n===0?pale:'#eef2f5',line,1)+path(`M13 ${8+n*10}h${13-n*3}`,'none',n===0?blue:gray,2)).join(''),
    week:()=>rect(4,6,26,25,'#f7fafc',ink,2)+rect(4,6,26,7,pale)+path('M4 13h26M11 3v6M23 3v6')+[0,1,2,3,4,5].map(n=>circle(10+n%3*7,19+Math.floor(n/3)*7,1.6,n===4?blue:gray,'none')).join(''),
    opponent:()=>person(8,10,.85)+person(26,10,.85)+text(17,27,'VS',6,blue,'middle',700),
    minutes:()=>circle(11,19,10,pale)+path('M11 12v7l5 3M8 5h6M11 5v4')+bars(24,11,8),
    development:()=>person(7,10,.7)+circle(26,9,5,'none',green,2)+path('M16 20h16M16 26h16M24 17v12','none',gray,2)+path('M24 20h7M24 26h4','none',green,3),
    efficiency:()=>path('M5 5v26h26','none',gray)+path('M5 13h26M5 22h26M13 5v26M22 5v26','none',line,.6)+path('M7 23l6-7 6 4 9-13','none',green,2)+[ [7,23],[13,16],[19,20],[28,7] ].map(([x,y])=>circle(x,y,1.8,green,'#f8fafb',.7)).join(''),
    prospects:()=>sheet()+circle(25,23,6,pale,blue)+path('M29 28l5 5','none',blue,2)+person(16,11,.5),
    'award-mvp':()=>trophy()+path('M17 8l1.4 3 3.3.4-2.4 2.3.5 3.3-2.8-1.6-2.8 1.6.5-3.3-2.4-2.3 3.3-.4z',gold,'none'),
    'award-dpoy':()=>trophy()+path('M17 9l5 2v4c0 4-5 6-5 6s-5-2-5-6v-4z',pale,blue,1.2),
    'award-roty':()=>trophy()+text(17,17,'R',9,gold,'middle',700),
    staff:()=>rect(4,5,19,26,'#f8fafb',ink,2)+rect(9,3,9,5,pale,ink,1)+person(15,14,.65)+path('M26 13l6 2-3 5 3 11h-6l2-11-4-5z',pale,blue,1.2),
    roster:()=>[0,1,2].map(n=>person(7,5+n*10,.45)+rect(15,5+n*10,16,3,gray)+rect(15,5+n*10,12-n*2,3,blue)).join(''),
    stats:()=>sheet()+rect(11,24,3,4,gray)+rect(16,20,3,8,blue)+rect(21,15,3,13,green),
    contracts:()=>sheet()+text(15,15,'$',11,green,'middle',700)+path('M20 27l10-15 3 2-10 15-5 3z','#ede0bd',gold,1.2),
    payroll:()=>path('M4 30h27','none',ink)+[0,1,2,3].map(n=>rect(5+n*7,8+n*3,4,21-n*3,gray)+rect(5+n*7,8+n*3,4,9,'#b85b53')).join('')+path('M4 13h27','none',gold,1),
    picks:()=>rect(4,5,27,25,'#f8fafb',ink,2)+path('M4 12h27M12 12v18M21 12v18M4 21h27','none',gray,1)+circle(16,17,3,pale,blue)+circle(26,26,3,'#ede0bd',gold),
    'team-block':()=>jersey()+path('M5 24h8l-3-3M13 24l-3 3','none',blue,1.8),
    'league-block':()=>circle(17,17,13,pale)+path('M4 17h26M17 4c-10 9-10 17 0 26M17 4c10 9 10 17 0 26','none',blue,1)+path('M22 28h11l-3-3M33 28l-3 3','none',ink,1.8),
    'league-wire':()=>rect(3,5,28,23,'#f8fafb',ink,2)+path('M8 11h18M16 16h10M16 21h10','none',gray,2)+rect(7,15,6,7,pale,blue,1)+path('M10 28l-3 4v-4',pale),
    transactions:()=>path('M5 11h24l-5-5M29 23H5l5 5','none',blue,2)+circle(17,17,5,pale,ink,1),
    bracket:()=>path('M3 7h7v7h7v6h8M3 21h7v-7M3 28h7v-7M17 20v8h8M25 20v8h7','none',blue,2)+[ [3,7],[3,21],[3,28],[32,24] ].map(([x,y])=>circle(x,y,2,pale,ink,1)).join(''),
    controls:()=>circle(17,17,13,pale)+path('M14 10l10 7-10 7z',blue,'none'),
    lottery:()=>circle(17,17,13,pale)+circle(17,17,8,'#f8fafb',blue)+text(17,21,'1',12,blue,'middle',700),
    player:()=>person(11,10,1)+bars(23,10,10)+circle(27,29,4,'none',green),
    market:()=>person(10,11,.9)+circle(27,22,8,'#e1eddf',green)+text(27,26,'$',10,green,'middle',700),
    offers:()=>rect(3,7,28,22,'#f8fafb',ink,2)+path('M3 7l14 12L31 7','none',blue,1.5)+circle(27,27,6,'#e1eddf',green)+text(27,30,'$',8,green,'middle',700),
    checklist:()=>sheet()+path('M10 10l2 2 3-4M10 19l2 2 3-4','none',green,1.8),
  };
  const descriptions={identity:'Court influence',signals:'Team strengths',morale:'Confidence & chemistry',factors:'Efficiency indicators',offense:'Offensive profile',defense:'Defensive profile',standings:'Conference rankings',week:'Schedule & results',opponent:'Matchup & rotation',minutes:'Rotation & fatigue',development:'Growth & upside',efficiency:'Season rating trends',prospects:'Scouting board',staff:'Grades & contracts',roster:'Complete player ratings',stats:'Season production',contracts:'Salary, risk & upside',payroll:'Cap & tax outlook',picks:'Draft capital', 'team-block':'Your trade assets','league-block':'League trade targets','league-wire':'Transactions & news',transactions:'Draft-night trades',bracket:'Playoff matchups',controls:'Phase decisions',lottery:'Draft lottery',player:'Player profile',checklist:'Required decisions'};
  function kindFor(id) {
    if (motifs[id]) return id;
    if (id.startsWith('player-card-')) return 'player';
    if (id.includes('staff_retention') || id.includes('cutdown')) return 'checklist';
    if (id.endsWith('-control')) return 'controls';
    if (id.endsWith('-bracket')) return 'bracket';
    if (id.endsWith('-lottery')) return 'lottery';
    if (id.endsWith('-payroll') || id.endsWith('-cap')) return 'payroll';
    if (id.endsWith('-wire') || id.endsWith('-ticker')) return 'league-wire';
    if (id.endsWith('-trades')) return 'transactions';
    if (id.endsWith('-offers')) return 'offers';
    if (id.endsWith('-market')) return 'market';
    if (id.startsWith('phase-fantasy_draft-') && id.endsWith('-board')) return 'roster';
    if (id.endsWith('-selected')) return 'player';
    if (id.endsWith('-roster')) return 'roster';
    if (id.endsWith('-leaders')) return 'stats';
    if (id.endsWith('-order')) return 'picks';
    if (id.endsWith('-summary')) return 'standings';
    if (id.endsWith('-board')) return 'prospects';
    return 'signals';
  }
  function icon(id) {
    const kind=kindFor(id);
    return `<svg viewBox="0 0 40 40" focusable="false" aria-hidden="true"><rect x="1" y="1" width="38" height="38" rx="8" fill="#f8fafb" stroke="#c7d2da"/><g transform="translate(3 3)">${motifs[kind]()}</g></svg>`;
  }
  window.CardVisuals=Object.freeze({icon,kindFor,description:id=>id.endsWith('-order')?'Selection order':id.endsWith('-summary')?'Draft recap':kindFor(id)==='offers'?'Incoming proposals':kindFor(id)==='market'?'Free-agent availability':descriptions[kindFor(id)] || 'Award contenders'});
})();
