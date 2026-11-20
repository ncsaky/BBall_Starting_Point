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
    if (id.endsWith('-injuries')) return 'injuries';
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
  // Gallery previews: a small, static drawing of each card's real layout (title bar, then the card's own table,
  // bars, chart or bracket). Representative only; no live data, so they never render half-loaded or clipped.
  const red='#c4585f', stripe='#eef1f3', dark='#172228';
  const W=160, H=100;
  const text_=(x,y,w,color=gray,h=2.4)=>rect(x,y,w,h,color,'none',1);
  const avatar=(x,y,r=3.2)=>circle(x,y,r,pale,'#9fb3c3',.7);
  const bar=(x,y,w,fill,color=blue,track=dark,h=2.6)=>rect(x,y,w,h,track)+rect(x,y,Math.max(1,w*fill),h,color);
  const seq=(n,fn)=>Array.from({length:n},(_,i)=>fn(i)).join('');
  const wave=[.82,.64,.9,.47,.71,.56,.38,.66,.52,.44];
  function rows(count,{top=17,h=10,avatar:withAvatar=true,nameX=withAvatar?16:7,cells=()=>''}={}) {
    return text_(6,top-5,24,'#7d8a95',1.8)+path(`M4 ${top-1.5}h152M4 ${top-.3}h152`,'none',line,.6)
      +seq(count,i=>{const y=top+i*h;return rect(4,y,152,h,i%2?stripe:'#fff')+(withAvatar?avatar(10,y+h/2,3):'')+text_(nameX,y+h/2-1.2,26-(i%3)*4,ink)+cells(i,y,h);});
  }
  const tableKinds={
    standings:()=>rows(8,{avatar:false,nameX:22,cells:(i,y)=>text_(6,y+3.5,4,ink)+circle(16,y+5,2.6,pale,blue,.6)+text_(110,y+3.8,12,'#7d8a95')+text_(128,y+3.8,10,'#7d8a95')+text_(144,y+3.8,8,'#7d8a95')}),
    minutes:()=>rows(8,{cells:(i,y)=>text_(56,y+3.8,8,'#7d8a95')+rect(76,y+4,38,1.6,'#c8d1d8')+circle(76+38*wave[i],y+4.8,2,ink,'none')+seq(5,k=>rect(124+k*6,y+4,4.6,2,k<(5-i%4)?(k>2?gold:green):'#c8d1d8'))}),
    roster:()=>rows(8,{cells:(i,y)=>seq(3,k=>bar(62+k*30,y+4,22,wave[(i+k*3)%10],k===2?green:blue))}),
    stats:()=>rows(8,{cells:(i,y)=>seq(6,k=>text_(64+k*15,y+3.8,9,k===1?ink:'#7d8a95'))+rect(78,17,15,80,'rgba(118,156,190,.18)')}),
    contracts:()=>rows(8,{cells:(i,y)=>seq(4,k=>text_(64+k*23,y+3.8,i>4-k?0:15,k===3-(i%3)?gold:'#7d8a95'))}),
    prospects:()=>rows(8,{avatar:false,nameX:24,cells:(i,y)=>text_(6,y+3.6,5,ink,2.8)+circle(18,y+5,2.8,pale,blue,.6)+text_(64,y+3.8,14,'#7d8a95')+bar(118,y+3.7,32,.95-i*.08,i>5?gold:blue)}),
    injuries:()=>rows(7,{cells:(i,y)=>seq(3,k=>bar(56+k*24,y+4,17,wave[(i+k)%10],blue))+text_(132,y+3.6,3,red,3)+text_(137,y+3.8,14,'#7d8a95')}),
    checklist:()=>rows(7,{cells:(i,y)=>text_(60,y+3.8,14,'#7d8a95')+text_(80,y+3.8,14,'#7d8a95')+seq(3,k=>rect(112+k*13,y+2,12.4,6,i<2&&k===1?red:k===0&&i>=2?'#d7eadc':'#edf0f3','#8d99a5',.5))}),
    market:()=>rows(8,{cells:(i,y)=>bar(60,y+4,26,wave[i],blue)+text_(96,y+3.8,14,green)+text_(118,y+3.8,10,'#7d8a95')+rect(136,y+2,16,6,'#edf0f3','#8d99a5',.5)}),
    order:()=>seq(8,i=>{const y=14+i*10.5;return rect(4,y,152,10,i===2?'#dce8f2':i%2?stripe:'#fff')+text_(8,y+3.8,5,ink)+circle(22,y+5,3.2,pale,blue,.6)+text_(30,y+2.2,i<2?40:26,i<2?ink:gray)+text_(30,y+6,18,'#9aa6b0',1.6)+(i===2?text_(140,y+3.8,10,blue):'');}),
    'league-wire':()=>seq(5,i=>{const y=15+i*16.5;return rect(4,y,152,15,i%2?stripe:'#fff')+rect(8,y+2.5,10,10,pale,'#9fb3c3',.6)+text_(22,y+3.5,90-i*9,ink)+text_(22,y+8.5,120-i*6,'#9aa6b0',1.8);}),
    staff:()=>rows(6,{h:13,cells:(i,y)=>bar(70,y+5,38,wave[i+2],wave[i+2]>.6?blue:gold)+text_(116,y+5,30,'#7d8a95')}),
  };
  const previews={
    ...tableKinds,
    bracket:()=>{const box=(x,y)=>rect(x,y,22,12,'#fff','#9aa6b0',2)+text_(x+3,y+3,12,ink,1.8)+text_(x+3,y+7.5,10,gray,1.8);
      return seq(4,i=>box(6,16+i*20)+box(132,16+i*20))+seq(2,i=>box(34,26+i*40)+box(104,26+i*40))+box(62,46)+box(80,46)
        +path('M28 22h3v20h3M28 42h3M28 62h3v20h3M28 82h3M56 32h3v20h3M56 72h3v-20M132 22h-3v20h-3M132 42h-3M132 62h-3v20h-3M132 82h-3M104 32h-3v20h-3M104 72h-3v-20','none',gray,.8);},
    lottery:()=>seq(14,i=>{const x=8+(i%4)*37,y=16+Math.floor(i/4)*20;return rect(x,y,34,16,i<4?'#dce8f2':'#fff','#b7c2cb',1.5)+circle(x+7,y+8,4.5,i<4?blue:pale,'none')+text_(x+14,y+6.8,14,ink);}),
    offense:()=>{const pts=(s)=>[0,1,2,3,4].map(k=>{const a=-Math.PI/2+k*2*Math.PI/5,r=36*s[k];return `${80+r*Math.cos(a)},${57+r*Math.sin(a)}`;}).join(' ');
      return `<polygon points="${pts([1,1,1,1,1])}" fill="#f5f8fa" stroke="${gray}"/><polygon points="${pts([.66,.66,.66,.66,.66])}" fill="none" stroke="${line}"/><polygon points="${pts([.9,.62,.78,.5,.84])}" fill="rgba(73,127,168,.32)" stroke="${blue}" stroke-width="1.4"/>`;},
    identity:()=>rect(20,14,120,80,'#f4efe4','#b9a98a',1)+path('M80 14v80M20 54h120','none','#c9b996',.8)+circle(80,54,10,'none','#c9b996',.8)+path('M20 34h22v40H20M140 34h-22v40h22','none','#c9b996',.8)+seq(6,i=>circle(34+i*18,30+(i%3)*22,5,i%2?'rgba(73,127,168,.45)':'rgba(96,150,109,.45)','none')),
    signals:()=>seq(3,i=>text_(10,24+i*24,26,ink,3)+bar(44,23.5+i*24,82,[.78,.52,.64][i],[gold,red,blue][i],'#dde3e8',4)+text_(132,24+i*24,16,'#7d8a95',3)),
    factors:()=>seq(4,i=>text_(10,20+i*19,24,ink,3)+bar(42,19.5+i*19,96,[.7,.45,.6,.55][i],i%2?green:blue,'#dde3e8',4)+path(`M${42+96*.55} ${16+i*19}v10`,'none',ink,.8)),
    morale:()=>rows(7,{cells:(i,y)=>bar(64,y+4,58,wave[i],wave[i]>.55?green:gold,'#dde3e8')}),
    week:()=>seq(7,i=>text_(10+i*21,15,10,'#7d8a95',2))+seq(28,i=>{const x=6+(i%7)*21,y=20+Math.floor(i/7)*19;return rect(x,y,20,18,'#fff',line,0)+(i%3===1?circle(x+10,y+9,3,i%2?green:red,'none'):'');}),
    opponent:()=>circle(44,30,12,pale,blue,1)+circle(116,30,12,'#f3e3e3',red,1)+text_(74,29,12,ink,3)+rows(4,{top:52,h:10,cells:(i,y)=>bar(70,y+4,40,wave[i])+bar(116,y+4,34,wave[i+3],red)}),
    development:()=>rows(7,{cells:(i,y)=>text_(64,y+3.8,10,'#7d8a95')+path(`M86 ${y+7}l4-4 4 4`,'none',green,1.2)+bar(100,y+4,46,wave[i],green,'#dde3e8')}),
    efficiency:()=>path('M10 92V16M10 92h144','none',gray,.8)+seq(4,i=>path(`M10 ${30+i*16}h144`,'none',line,.5))+path('M14 70 32 62 50 66 68 48 86 54 104 40 122 44 140 30 152 34','none',green,1.8)+path('M14 76 32 74 50 70 68 72 86 64 104 66 122 58 140 60 152 54','none',blue,1.2),
    award:()=>seq(4,i=>{const y=16+i*20;return rect(4,y,152,18,i%2?stripe:'#fff')+text_(9,y+7.5,5,ink,3)+avatar(24,y+9,5.5)+text_(34,y+7.5,60-i*6,ink,3)+text_(132,y+7.5,14,i<2?green:'#7d8a95',3);}),
    payroll:()=>path('M10 92h144','none',ink,.8)+seq(4,i=>{const x=22+i*34,h=[70,62,48,34][i];return rect(x,92-h,20,h,'#c8d1d8')+rect(x,92-h*.55,20,h*.55,blue);})+path('M10 30h144','none',red,1)+text_(12,24,26,red,2),
    picks:()=>seq(2,r=>text_(8,18+r*42,22,ink,2.6)+seq(7,i=>rect(8+i*21,24+r*42,18,22,i%3===2?'#f7f9fa':'#fff','#b7c2cb',1.5)+circle(17+i*21,32+r*42,4,i%3===2?'#eee':pale,i%3===2?gray:blue,.6)+text_(11+i*21,40+r*42,12,'#7d8a95',1.8))),
    blocks:()=>rows(6,{h:12,cells:(i,y)=>text_(62,y+4.5,18,'#7d8a95')+bar(88,y+4.5,40,wave[i])+rect(134,y+2,18,7,'#edf0f3','#8d99a5',.5)}),
    wants:()=>seq(6,i=>{const y=16+i*13;return rect(8,y,8,8,i<2?blue:'#fff','#8d99a5',.8)+text_(22,y+3,70-i*6,ink,2.4)+text_(100,y+3,30,'#9aa6b0',2.2);}),
    player:()=>rect(8,16,44,54,pale,'#9fb3c3',1)+circle(30,34,10,'#c3d3e0','none')+path('M14 70c2-14 30-14 32 0','#c3d3e0','none')+text_(8,76,40,ink,3)+text_(8,82,28,'#9aa6b0',2)+seq(7,i=>text_(62,19+i*11,22,'#7d8a95',2.2)+bar(88,19+i*11,62,wave[i],wave[i]>.7?blue:wave[i]>.5?'#7fa9c8':gold)),
    trades:()=>seq(4,i=>{const y=16+i*20;return rect(4,y,152,18,i%2?stripe:'#fff')+circle(14,y+9,5,pale,blue,.6)+path(`M24 ${y+6}h24l-3-3M48 ${y+12}H24l3 3`,'none',blue,1.1)+circle(56,y+9,5,'#f3e3e3',red,.6)+text_(66,y+5,74-i*8,ink)+text_(66,y+10,50,'#9aa6b0',1.8);}),
    offers:()=>seq(4,i=>{const y=16+i*20;return rect(4,y,152,18,i%2?stripe:'#fff')+rect(9,y+4,16,11,'#fff',ink,.8)+path(`M9 ${y+4}l8 6 8-6`,'none',ink,.8)+text_(32,y+5,66,ink)+text_(32,y+10,44,'#9aa6b0',1.8)+rect(128,y+4,22,10,'#e1eddf',green,.6);}),
    controls:()=>seq(3,i=>rect(10+i*48,40,42,18,i===0?'#dce8f2':'#edf0f3','#8d99a5',1.5)+text_(18+i*48,48,26,ink)),
    builder:()=>rect(6,16,70,78,'#fff',line)+rect(84,16,70,78,'#fff',line)+seq(4,i=>avatar(14,26+i*16,4)+text_(22,25+i*16,40,ink)+avatar(92,26+i*16,4)+text_(100,25+i*16,40,ink))+path('M74 55h12l-3-3M86 60H74l3 3','none',blue,1.2),
  };
  const previewKind=(id)=>{
    if (id.startsWith('award-')) return 'award';
    if (id === 'defense') return 'offense';
    if (['team-block','league-block'].includes(id)) return 'blocks';
    if (id === 'team-wants') return 'wants';
    if (id.startsWith('trade-')) return 'builder';
    if (id.includes('staff_retention')) return 'staff';
    if (id.endsWith('-injuries')) return 'injuries';
    if (id.endsWith('-order')) return 'order';
    if (id.endsWith('-summary') || id.endsWith('-leaders')) return 'stats';
    if (id.endsWith('-wire') || id.endsWith('-ticker')) return 'league-wire';
    if (id.endsWith('-trades')) return 'trades';
    const kind=kindFor(id);
    if (kind === 'transactions') return 'trades';
    return previews[kind] ? kind : 'roster';
  };
  function preview(id) {
    const kind=previewKind(id);
    return `<svg class="card-visual-preview" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" focusable="false" aria-hidden="true"><rect x=".5" y=".5" width="${W-1}" height="${H-1}" rx="2" fill="#fff" stroke="#9fb0bd"/><rect x="1" y="1" width="${W-2}" height="8" fill="#c7d7e5"/>${rect(4,3.6,30,1.8,'#55697a')}${seq(3,i=>rect(W-9-i*7,3,5,3,'#eef3f7','#8ea2b2',.4))}<g>${previews[kind]()}</g></svg>`;
  }
  motifs.injuries=()=>rect(4,6,26,24,'#f8fafb',ink,2)+path('M17 11v14M10 18h14','none',red,3.2);
  descriptions.injuries='Injured & returning players';
  window.CardVisuals=Object.freeze({icon,preview,previewKind,kindFor,description:id=>id==='team-wants'?'Your trade wants':id.startsWith('trade-')?'Trade tools':id.endsWith('-order')?'Selection order':id.endsWith('-summary')?'Draft recap':kindFor(id)==='offers'?'Incoming proposals':kindFor(id)==='market'?'Free-agent availability':descriptions[kindFor(id)] || 'Award contenders'});
})();
