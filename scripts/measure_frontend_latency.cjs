/* Observe real frontend playback; no GUI source changes or animation overrides. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const [url,base]=process.argv.slice(2),cases=JSON.parse(fs.readFileSync(path.join(base,'cases.json')));
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'no-preference'});
 await context.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
 const page=await context.newPage(),cdp=await context.newCDPSession(page);await cdp.send('Network.enable');
 let network={},active=false,report=[];const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 cdp.on('Network.requestWillBeSent',e=>{
   if(active && e.request.url.endsWith('/api/action/stream'))network={id:e.requestId,start:e.timestamp,wall:e.wallTime,chunks:[]};
 });
 cdp.on('Network.dataReceived',e=>{if(e.requestId===network.id)network.chunks.push({at:e.timestamp-network.start,bytes:e.dataLength});});
 cdp.on('Network.loadingFinished',e=>{if(e.requestId===network.id)network.finished=e.timestamp-network.start;});
 await page.goto(url);await page.waitForFunction(()=>state.teams.length>0&&!state.hydrating&&!state.busy,null,{timeout:60000});
 await page.evaluate(()=>{
   window.__latency={current:null};
   const parse=JSON.parse;
   JSON.parse=function(...a){const v=parse(...a),p=__latency.current;
     if(p&&v?.type==='progress')p.parsed.push({at:performance.now(),kind:v.event?.kind,date:v.event?.date});
     if(p&&v?.type==='result')p.parsedResult=performance.now();return v;};
   const display=displaySimulationProgress;
   displaySimulationProgress=async function(event){const p=__latency.current,t=performance.now();
     try{return await display(event);}finally{if(p)p.playback.push({kind:event.kind,date:event.date,start:t,end:performance.now()});}};
   const fetchOriginal=window.fetch;
   window.fetch=function(input,...a){const p=__latency.current;
     if(p&&String(input).endsWith('/api/action/stream'))p.requestStart=performance.now();
     return fetchOriginal.call(this,input,...a);};
   const actionOriginal=action;
   action=async function(name,...args){const p=__latency.current,t=performance.now();
     try{return await actionOriginal(name,...args);}finally{if(p)p.actions.push({name,start:t,end:performance.now()});}};
 });
 const runId=Date.now();
 const runs=process.env.LATENCY_RUNS?JSON.parse(process.env.LATENCY_RUNS):[['offday','first-use'],['offday','warm'],['game','warm'],['busy','first-market'],['busy','repeat'],['month','first-month'],['month','repeat']];
 for(let index=0;index<runs.length;index++){
   const [name,sample]=runs[index],item=cases[name],label=`${name}-${sample}`;
   const archive=fs.readFileSync(item.archive).toString('base64');
   await page.evaluate(async({archive,name})=>{
     __latency.current=null;
     const restored=await action('restore_save',{archive_base64:archive,save_name:name});
     // Match the normal restore/load flow: resolve the newly restored team
     // from the save list, rather than the previously selected career.
     await loadSaves();
     state.currentSave=restored.save_path;state.view='dashboard';state.dashboardTeam='';state.modal=null;
     clearViewCaches();await refreshHome();
   },{archive,name:`latency_${runId}_${index}`});
   await page.waitForFunction(()=>!state.hydrating&&!state.busy,null,{timeout:60000});
   if(await page.evaluate(()=>Boolean(state.tutorial)))await page.locator('[data-tutorial-action="skip"]').click();
   const ready=await page.evaluate(async()=>await ensureStartingFiveReadyForAdvance());
   if(!ready)throw Error('Starting five decision required; resolve with normal setup before timing');
   network={};active=true;
   const measured=await page.evaluate(async({target,label})=>{
     const p={label,clickStart:performance.now(),timeOrigin:performance.timeOrigin,parsed:[],playback:[],actions:[]};__latency.current=p;
     await advance({to_date:target,checkpoint_days:31});
     p.advanceReturned=performance.now();
     p.flagsAtAdvanceReturn={busy:state.busy,depth:state.busyDepth,hydrating:state.hydrating};
     await new Promise((resolve,reject)=>{const start=performance.now();const poll=()=>{
       if(!state.busy&&!state.hydrating&&!state.simulationRunning&&state.busyDepth===0)return resolve();
       if(performance.now()-start>60000)return reject(Error('Controls did not become usable: '+JSON.stringify({busy:state.busy,depth:state.busyDepth,hydrating:state.hydrating})));
       setTimeout(poll,10);
     };poll();});
     p.usable=performance.now();p.simulationIdSeen=null;
     p.finalDate=state.home?.save?.current_date;p.savePath=state.currentSave;p.flags={busy:state.busy,sim:state.simulationRunning,hydrating:state.hydrating,modal:state.modal?.kind||null};
     p.controls=[...document.querySelectorAll('[data-advance],button')].filter(b=>b.matches('[data-advance]')||b.textContent.includes('Sim to')).map(b=>({mode:b.dataset.advance||b.textContent.trim(),disabled:b.disabled,visible:b.getClientRects().length>0}));
     p.reducedMotion=GameSimulation.reducedMotion();__latency.current=null;return p;
   },{target:item.target,label});
   await page.waitForTimeout(100);
   const row={name,sample,frontend:measured,network,errors:[...errors]};report.push(row);
   fs.writeFileSync(path.join(base,'browser.json'),JSON.stringify(report,null,2));
   active=false;assert.equal(measured.finalDate,item.target,label);assert.equal(measured.flags.busy,false);assert.equal(measured.reducedMotion,false);
   console.log(JSON.stringify({label,requestToUsable:(measured.usable-measured.requestStart)/1000,preflight:(measured.requestStart-measured.clickStart)/1000,wire:network.finished,frames:measured.parsed.length,final:measured.finalDate}));
 }
 await page.screenshot({path:path.join(base,'final-dashboard.png')});
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
