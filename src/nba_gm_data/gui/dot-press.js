const base='assets/dot-press/';
const revision='refined-edges-3';
const candidates=[
  {id:'curry',name:'Stephen Curry',category:'Shooting',note:'2017 Finals / In-game jumper',source:'curry-finals.jpg'},
  {id:'rodman-detroit',name:'Dennis Rodman',category:'Rebounding A',note:'Detroit / Airborne rebound',source:'rodman-detroit.jpg'},
  {id:'rodman-chicago',name:'Dennis Rodman',category:'Rebounding B',note:'Chicago / Airborne rebound',source:'rodman-white.png'},
  {id:'allen',name:'Ray Allen',category:'Shooting alternative',note:'Pre-game warmup / CC BY-SA 2.0',source:'allen.jpg'},
  {id:'builder',name:'Trade builder',category:'Retained',note:'Original exchange illustration'},
  {id:'finder',name:'Trade finder',category:'Retained',note:'Original market-search illustration'},
];
const preview={mode:'press',density:'press',surface:'silver',detail:null};
function asset(id,mode=preview.mode){return `${base}exports/${id}-${mode==='photo'?'photo':`${preview.density}-${preview.surface}`}.png?v=${revision}`;}
document.querySelector('#gallery').innerHTML=candidates.map(item=>`<article class="candidate"><header><h3>${item.name}</h3><span>${item.category}</span></header><button class="art-open" data-id="${item.id}" aria-label="Enlarge ${item.name} ${item.category}"><img data-art="${item.id}" alt="${item.name}, ${item.note}" width="1024" height="1024"></button><footer><p>${item.note}</p><a data-download="${item.id}" download>PNG ↓</a></footer></article>`).join('');
function render(){
  document.body.classList.toggle('ink',preview.surface==='ink');
  document.querySelectorAll('[data-art]').forEach(img=>img.src=asset(img.dataset.art));
  document.querySelectorAll('[data-download]').forEach(a=>a.href=asset(a.dataset.download));
  document.querySelectorAll('[data-small]').forEach(img=>img.src=asset(img.dataset.small));
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===preview.mode)));
  document.querySelectorAll('[data-surface]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.surface===preview.surface)));
  const item=candidates.find(item=>item.id===document.querySelector('#subject').value);
  document.querySelector('#original').src=base+'sources/'+item.source;
  document.querySelector('#cutout').src=asset(item.id,'photo');
  document.querySelector('#processed').src=asset(item.id,'press');
  document.querySelector('#edge-proof').src=`${base}proofs/${item.id}-edges.jpg?v=${revision}`;
  if(preview.detail){
    document.querySelector('#detail-image').src=asset(preview.detail);
    document.querySelector('#detail-download').href=asset(preview.detail);
  }
}
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{preview.mode=b.dataset.mode;render();}));
document.querySelectorAll('[data-surface]').forEach(b=>b.addEventListener('click',()=>{preview.surface=b.dataset.surface;render();}));
document.querySelector('#density').addEventListener('change',event=>{preview.density=event.target.value;render();});
document.querySelector('#subject').addEventListener('change',render);
document.querySelectorAll('.art-open').forEach(button=>button.addEventListener('click',()=>{
  preview.detail=button.dataset.id;
  const item=candidates.find(item=>item.id===preview.detail);
  document.querySelector('#detail-title').textContent=item.name+' / '+item.category;
  document.querySelector('#detail-image').alt=item.name+' '+item.category;
  render();document.querySelector('#detail').showModal();
}));
document.querySelector('#close').addEventListener('click',()=>document.querySelector('#detail').close());
document.querySelector('#detail').addEventListener('click',event=>{if(event.target.id==='detail'){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
render();
