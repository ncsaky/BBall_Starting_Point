/* Original vector drawings, rasterized and processed locally. No generated imagery. */
const study = {style:'dots',surface:'silver',edition:2027};
const subjects = [
  ['shooting','Shooting','Player-card archetype / shooting and spacing categories'],
  ['rebounding','Rebounding','Team identity / interior play / rebounding category'],
  ['vision','Court vision','Mental ratings / coaching / lineup fit'],
  ['builder','Trade builder','Assets page / exchanging packages'],
  ['finder','Trade finder','Assets page / inspecting the market'],
  ['prospects','The next class','Draft and scouting / reusable every season'],
];
const descriptions={
  dots:['01 / Dot press','Variable-size ink dots. Most tactile at medium sizes; especially good for action photography and basketball category images.'],
  stencil:['02 / Cut print','Flat ink shapes and carved shadows. The clearest treatment for small tool illustrations and compressed dashboard placements.'],
  pixels:['03 / Dithered pixels','A deliberately coarse four-tone bitmap. The most game-like option; stronger personality, but less natural beside fine analytical charts.'],
};
const path=(d,fill='#ccd5d9',stroke='',width=2)=>`<path d="${d}" fill="${fill}"${stroke?` stroke="${stroke}" stroke-width="${width}" stroke-linejoin="round" stroke-linecap="round"`:''}/>`;
const line=(x1,y1,x2,y2,color='#899ca8',width=2)=>`<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${color}" stroke-width="${width}"/>`;
const circle=(x,y,r,fill,stroke='',width=2)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke||'none'}" stroke-width="${width}"/>`;
const rect=(x,y,w,h,fill,stroke='',sw=2)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="${stroke||'none'}" stroke-width="${sw}"/>`;
const inkText=(x,y,text,size=24,fill='#d5e0e4')=>`<text x="${x}" y="${y}" font-family="monospace" font-size="${size}" fill="${fill}" text-anchor="middle">${text}</text>`;
function ball(x,y,r){return circle(x,y,r,'#e97c43')+path(`M${x-r} ${y}H${x+r} M${x} ${y-r}V${y+r} M${x-r*.72} ${y-r*.7}Q${x+r*.42} ${y} ${x-r*.72} ${y+r*.7} M${x+r*.72} ${y-r*.7}Q${x-r*.42} ${y} ${x+r*.72} ${y+r*.7}`,'none','#352b28',1.7);}
function hoop(){return rect(499,42,93,64,'none','#718895',3)+rect(522,66,38,30,'none','#94a7b1',2)+path('M493 107H563 M502 111L511 141H547L558 111 M504 114L544 137 M518 111L553 123 M514 139L551 112 M503 124L525 111','none','#bcc9ce',2)+line(590,107,608,342,'#536a77',4);}
function jersey(x,y,scale=1,number='7'){
  return `<g transform="translate(${x} ${y}) scale(${scale})">${path('M22 0L44 12Q60 21 77 12L98 0L129 23L111 68L95 60L101 166L18 166L24 60L8 68L-10 23Z','#a5b5c0')}${path('M22 0L32 24L25 60L18 166H39L44 56L44 12Z','#526875')}${path('M77 12L82 34L99 44L111 68L129 23L98 0Z','#e3e9ea')}${path('M44 12Q60 31 77 12 M24 60L32 24 M95 60L82 34','none','#253b49',4)}${rect(21,154,77,6,'#e97c43')}${inkText(61,107,number,45,'#152935')}${path('M46 49H76 M40 124L80 119','none','#768b97',3)}</g>`;
}
function shooter(number){return `
  ${hoop()}${path('M43 355H580 M83 355L164 264H459L538 355 M205 354Q298 287 391 354','none','#324b5c',2)}
  ${path('M199 344L221 286L230 228L270 226L270 291L248 345L226 355Z','#a2b1bb')}
  ${path('M261 239L293 243L319 289L362 312L352 337L301 310L269 276Z','#cad4d9')}
  ${path('M200 337L230 345L223 358L179 365L159 361L159 351Z','#edf0f0')}${path('M350 312L372 312L391 334L387 348L348 338Z','#edf0f0')}
  ${path('M217 349L183 352 M357 325L375 336','none','#6b808b',3)}
  ${path('M239 148Q221 150 215 169L208 202L225 226L247 209L246 179L262 159Z','#b2c2cc')}
  ${path('M251 165L262 129L280 96L305 77L317 92L296 112L288 147L281 176Z','#dde3e7')}
  ${path('M294 155L302 118L318 78L337 46L352 52L340 85L329 131L318 165Z','#9aadb9')}
  ${path('M337 52L340 33L348 18L354 20L351 36L359 27L365 30L358 44L373 39L375 45L351 60Z','#d7e0e5')}
  ${path('M302 83L310 60L322 47L336 49L344 63L338 68L329 57L324 79L317 95Z','#edf0f0')}
  ${path('M252 155L272 149L282 155L302 145L321 162L302 191L305 225L261 241L227 226L237 189Z','#dbe3e7')}
  ${path('M235 187L248 195L239 226L269 232L264 244L226 230Z','#697f8d')}
  ${path('M231 224L265 235L304 223L311 260L280 268L267 250L256 275L222 257Z','#748d9e')}
  ${path('M226 250L254 264 M282 257L307 249','none','#e97c43',4)}
  ${path('M268 151L269 137L290 132L299 148L289 163Z','#c1cdd5')}
  ${path('M268 138L258 125L257 107L269 96L285 97L300 105L299 122L290 139Z','#d6e0e6')}
  ${path('M257 114L259 103Q266 88 286 96L299 103L300 112L282 106L273 111L271 127L266 123Z','#496473')}
  ${path('M290 116L299 119L290 123 M280 132L290 130','none','#5d7381',2)}
  ${inkText(279,204,number,29,'#38515f')}${path('M250 169L263 175 M301 159L293 179 M263 219L291 212','none','#91a5b0',3)}
  ${ball(355,24,21)}${path('M385 31Q439 -1 511 82','none','#71858f',2)}
`;}
function rebound(number){return `
  ${hoop()}${line(43,361,588,361,'#415b6b',2)}
  <g transform="translate(-34 37) rotate(-8 208 230)">
  ${path('M187 239L168 298L131 323L136 340L185 318L214 258 M220 253L230 314L254 345L268 336L251 301L251 238','#647c8c')}
  ${path('M176 145L159 123L179 87L224 66L231 79L197 100L186 143 M228 145L242 106L276 59L288 66L264 118L254 166','#7b929f')}
  ${path('M175 142L201 134L233 142L253 169L241 228L250 252L205 266L169 243L179 209L165 169Z','#4b6677')}
  ${circle(212,120,19,'#8099a8')}${path('M192 116Q196 87 220 99L231 112L214 107Z','#b4c3cc')}
  ${path('M131 321L143 334L137 348L104 349L99 341Z M257 333L268 338L287 350L281 359L254 354L248 344Z','#d1dce2')}
  ${inkText(211,191,'5',29,'#d5dfe4')}</g>
  ${path('M305 253L287 311L270 352L292 361L323 317L344 271Z','#d3dde2')}
  ${path('M345 244L371 271L411 304L395 326L354 301L325 271Z','#96afbe')}
  ${path('M268 348L294 354L290 367H246L234 360Z M395 309L410 304L430 321L434 334L419 340L394 325Z','#e5ecee')}
  ${path('M298 157L282 114L300 77L336 53L343 66L316 89L305 119L327 158Z','#c7d7df')}
  ${path('M345 155L359 121L375 89L374 48L388 43L398 84L383 130L377 169Z','#e6ecef')}
  ${path('M375 51L373 33L380 20L386 24L384 35L394 29L400 36L390 52Z M334 55L342 40L354 31L361 34L349 46L352 57L342 68Z','#ecf0f1')}
  ${path('M308 161L326 147L343 151L359 142L379 160L361 185L369 224L345 247L300 235L293 206Z','#dae3e8')}
  ${path('M294 202L310 219L305 235L344 242L331 255L296 239Z','#819baa')}
  ${path('M300 232L332 241L365 228L376 266L350 280L335 263L315 283L286 262Z','#98aebc')}
  ${path('M291 255L314 273 M354 270L372 258','none','#e97c43',4)}
  ${path('M322 155L320 139L340 133L350 146L338 161Z','#c7d5de')}
  ${circle(328,124,20,'#bccdd8')}${path('M309 124Q303 102 323 101L340 105L346 117L331 111L319 117L318 131Z','#3e5b6e')}
  ${path('M338 120L347 123L339 127 M329 139L341 136','none','#728d9e',2)}
  ${inkText(337,210,number,31,'#405f73')}${ball(365,27,24)}
`;}
function vision(){return `
  <g transform="rotate(-8 319 203)">${rect(160,39,305,329,'#4a6272')}${rect(172,51,281,305,'#c6d2da')}${rect(258,27,109,35,'#e5ebee')}${rect(278,27,67,16,'#788e9c')}
  ${rect(193,79,238,252,'none','#465f70',3)}${line(193,204,431,204,'#546c7c',2)}${circle(312,204,30,'none','#546c7c')}
  ${rect(268,79,89,66,'none','#546c7c')}${circle(312,145,22,'none','#546c7c')}${path('M209 79V107Q312 238 415 107V79 M209 331V303Q312 172 415 303V331','none','#546c7c',2)}
  ${circle(227,170,10,'#233c4e')}${circle(387,173,10,'#233c4e')}${circle(314,245,10,'#e97c43')}${circle(246,290,10,'#233c4e')}${circle(380,290,10,'#233c4e')}
  ${path('M314 233Q295 194 254 183 M259 194L250 182L265 180 M240 163Q253 126 291 113 M277 111L294 111L289 126','none','#e97c43',4)}
  ${path('M343 164L356 177 M356 164L343 177 M300 295L312 307 M312 295L300 307 M363 231L375 243 M375 231L363 243','none','#627d8e',3)}</g>
  ${path('M462 110L479 91L499 108L481 128Z','#e97c43')}${path('M463 113L481 127L427 269L409 256Z','#e4ebee')}${path('M409 256L427 269L401 290Z','#889dab')}${path('M401 290L406 275L413 281Z','#e8edef')}
`;}
function builder(number){return `
  ${path('M49 344L284 358L327 330L582 344','none','#4c6472',2)}
  <g transform="rotate(-8 178 207)">${rect(77,84,185,242,'#294455')}${rect(67,72,185,242,'#526f81')}${rect(57,60,185,242,'#b2c4d0')}${jersey(103,90,.8,number)}${rect(81,258,139,4,'#607c8d')}${rect(81,271,87,4,'#607c8d')}</g>
  <g transform="rotate(8 458 207)">${rect(394,84,185,242,'#294455')}${rect(384,72,185,242,'#526f81')}${rect(374,60,185,242,'#d7e1e8')}${jersey(420,90,.8,String(Number(number)+3))}${rect(398,258,139,4,'#607c8d')}${rect(398,271,87,4,'#607c8d')}</g>
  ${path('M265 161H364L347 145 M364 161L347 177 M368 226H270L287 210 M270 226L287 242','none','#e97c43',5)}
  ${circle(259,305,25,'#b8c9d4','#263f51',3)}${circle(259,305,18,'none','#627e91',2)}${inkText(259,311,'1',20,'#233e50')}
  ${circle(376,306,25,'#d6e1e7','#263f51',3)}${circle(376,306,18,'none','#627e91',2)}${inkText(376,312,'2',20,'#233e50')}
`;}
function finder(number){return `
  <g transform="rotate(-7 282 204)">${rect(109,67,284,257,'#456274')}${rect(125,53,284,257,'#819ba9')}${rect(141,39,284,257,'#c4d2dc')}${jersey(196,62,1.05,number)}
  ${rect(164,261,151,4,'#617d8e')}${rect(164,273,101,4,'#617d8e')}${rect(352,85,42,5,'#617d8e')}${rect(352,101,30,5,'#617d8e')}${rect(352,117,37,5,'#617d8e')}</g>
  ${path('M382 247L423 229L514 318L483 350Z','#687f8d')}${path('M398 250L419 244L506 327L492 337Z','#d5dfe6')}
  ${circle(350,190,93,'#1e394b','#a3b9c8',13)}${circle(350,190,77,'#516d80','#d9e3e8',3)}
  ${path('M298 173L323 151L350 163L376 151L401 173L387 199L376 193L383 244H318L324 193L313 199Z','#cbd9e2')}${inkText(350,220,number,40,'#243e50')}
  ${path('M289 172Q298 125 342 119','none','#eaf0f2',7)}${path('M406 208L414 190','none','#e97c43',5)}
`;}
function prospects(number){return `
  <g transform="rotate(-5 288 209)">${rect(101,50,299,296,'#526d7e')}${rect(118,37,299,296,'#b8cbd7')}${rect(139,58,152,175,'#345367')}
  ${circle(216,114,29,'#a2bbc9')}${path('M185 113Q180 77 212 77Q244 77 246 105L222 94L200 103L201 124Z','#192f40')}
  ${path('M163 216L170 177Q176 163 197 158L198 140L229 139L234 158Q259 165 265 185L272 216Z','#ccdbe5')}${path('M196 158L216 173L234 158L239 216H192Z','#708d9f')}${inkText(215,205,number,27,'#dce6ed')}
  ${rect(308,79,82,5,'#556f80')}${rect(308,98,61,5,'#556f80')}${rect(308,136,73,5,'#556f80')}${rect(308,155,82,5,'#556f80')}${rect(308,174,54,5,'#556f80')}
  ${rect(139,249,254,5,'#607c8e')}${rect(139,266,213,5,'#607c8e')}${rect(139,283,237,5,'#607c8e')}</g>
  ${path('M380 315L419 267L448 280L492 222L535 185','none','#e97c43',6)}${path('M512 188L537 183L535 209','none','#e97c43',5)}
  ${path('M432 106L442 82L452 106L479 108L458 125L465 151L442 136L419 151L426 125L405 108Z','#d0e0e8')}
`;}
const drawings={shooting:shooter,rebounding:rebound,vision,builder,finder,prospects};
const sourceCache=new Map();
function imageFrom(src){return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error(`Cannot load ${src.slice(0,70)}`));image.src=src;});}
async function sceneSource(scene){
  const key=`${scene}:${study.edition}`;
  if(sourceCache.has(key))return sourceCache.get(key);
  const number=String(1+(study.edition*7)%39);
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400"><rect width="640" height="400" fill="#000"/>${drawings[scene](number)}</svg>`;
  const image=await imageFrom(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
  const source=document.createElement('canvas');source.width=640;source.height=400;source.getContext('2d').drawImage(image,0,0);sourceCache.set(key,source);return source;
}
const bayer=[[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]];
function renderTreatment(source,target,style,photo=false){
  const ctx=target.getContext('2d'),w=target.width,h=target.height;
  const sampling=document.createElement('canvas');sampling.width=w;sampling.height=h;
  const sc=sampling.getContext('2d',{willReadFrequently:true});sc.drawImage(source,0,0,w,h);
  const data=sc.getImageData(0,0,w,h).data;
  const light=study.surface==='silver';
  const palette=light?['#edf0f1','#b1c0c8','#617c8d','#243e50']:['#111e28','#324e62','#789caf','#d2e2e9'];
  const accent=light?'#b24c2d':'#f39461';
  ctx.fillStyle=palette[0];ctx.fillRect(0,0,w,h);
  const sample=(x,y)=>{const i=(Math.min(h-1,Math.max(0,Math.floor(y)))*w+Math.min(w-1,Math.max(0,Math.floor(x))))*4;
    let lum=(data[i]*.2126+data[i+1]*.7152+data[i+2]*.0722)/255;
    if(photo){lum=Math.max(0,Math.min(1,(lum-.12)*1.35));if(light)lum=1-lum;}
    return {v:lum,a:data[i+3],accent:!photo&&data[i]>data[i+2]*1.4&&data[i]>100};};
  if(style==='dots'){
    const step=photo?3.6:4.2;
    for(let row=0,y=step/2;y<h;y+=step,row++)for(let x=step/2+(row%2)*step/2;x<w;x+=step){
      const s=sample(x,y);if(s.a<32||s.v<.045)continue;
      ctx.fillStyle=s.accent?accent:palette[3];ctx.beginPath();ctx.arc(x,y,step*.49*Math.sqrt(s.v),0,Math.PI*2);ctx.fill();
    }
  }else{
    const step=style==='pixels'?4:1;
    for(let y=0;y<h;y+=step)for(let x=0;x<w;x+=step){
      const s=sample(x+step/2,y+step/2);if(s.a<32)continue;
      const threshold=style==='pixels'?(bayer[(y/step)%4][(x/step)%4]/16-.5)*.28:0;
      const level=Math.max(0,Math.min(3,Math.round((s.v+threshold)*3)));
      ctx.fillStyle=s.accent?accent:palette[level];ctx.fillRect(x,y,step,step);
    }
  }
}
let renderVersion=0;
async function renderAll(){
  const version=++renderVersion;document.body.dataset.ready='false';document.body.classList.toggle('ink',study.surface==='ink');
  const [title,copy]=descriptions[study.style];document.querySelector('#direction-title').textContent=title;document.querySelector('#direction-copy').textContent=copy;
  document.querySelector('#sample-player').textContent=study.edition===2027?'Miles Okafor':study.edition===2040?'Adrian Voss':'Elian Mercer';
  await Promise.all([...document.querySelectorAll('[data-scene]')].map(async canvas=>{const source=await sceneSource(canvas.dataset.scene);if(version===renderVersion)renderTreatment(source,canvas,study.style);}));
  const photo=await imageFrom('assets/image-studies/eric-gordon-rebound.jpg');
  const source=document.createElement('canvas');source.width=320;source.height=480;
  const fit=Math.min(320/photo.width,480/photo.height);source.getContext('2d').drawImage(photo,(320-photo.width*fit)/2,0,photo.width*fit,photo.height*fit);
  if(version!==renderVersion)return;
  document.querySelectorAll('[data-photo]').forEach(canvas=>renderTreatment(source,canvas,canvas.dataset.photo,true));
  document.body.dataset.ready='true';
}
document.querySelector('#subjects').innerHTML=subjects.map(([id,title,description])=>`<article class="art-card"><canvas data-scene="${id}" width="640" height="400" role="img" aria-label="Original ${title.toLowerCase()} illustration"></canvas><header><h3>${title}</h3><button data-export="${id}" title="Download ${title} PNG" aria-label="Download ${title} PNG">↓</button></header><p>${description}</p></article>`).join('');
document.querySelectorAll('[data-style]').forEach(button=>button.addEventListener('click',()=>{study.style=button.dataset.style;document.querySelectorAll('[data-style]').forEach(tab=>tab.setAttribute('aria-selected',String(tab===button)));renderAll().catch(showError);}));
document.querySelector('#surface').addEventListener('change',event=>{study.surface=event.target.value;renderAll().catch(showError);});
document.querySelector('#edition').addEventListener('change',event=>{study.edition=Number(event.target.value);renderAll().catch(showError);});
document.querySelectorAll('[data-export]').forEach(button=>button.addEventListener('click',()=>{const canvas=button.closest('article').querySelector('canvas');const link=document.createElement('a');link.download=`${button.dataset.export}-${study.style}-${study.surface}.png`;link.href=canvas.toDataURL('image/png');link.click();}));
document.querySelectorAll('[data-replay]').forEach(button=>button.addEventListener('click',()=>{const sample=button.closest('article');sample.classList.remove('playing');void sample.offsetWidth;sample.classList.add('playing');}));
function showError(error){document.body.dataset.error=error.message;document.querySelector('#direction-copy').textContent=error.message;console.error(error);}
renderAll().catch(showError);
