
(function(){
'use strict';
const panels = JSON.parse(document.getElementById('report-panels').textContent);
const dialog = document.getElementById('detail-sheet');
const tabs = [...document.querySelectorAll('[data-tab]')];
let lastTrigger=null;
function closeSheet(){ if(dialog.open) dialog.close(); }
function openSheet(key, trigger){
 const data=panels[key]; if(!data) return;
 lastTrigger=trigger;
 document.getElementById('sheet-title').textContent=data.title;
 document.getElementById('sheet-subtitle').textContent=data.subtitle;
 const content=document.getElementById('sheet-content');
 // Only curated, locally embedded report content is rendered here. No remote HTML is fetched.
 content.innerHTML='<span class="sheet-badge '+data.tone+'">'+data.status+'</span>'+data.body;
 document.body.style.overflow='hidden';
 if(!dialog.open) dialog.showModal();
 content.scrollTop=0;
 dialog.querySelector('.sheet-close').focus({preventScroll:true});
}
function setTab(key, focus){
 if(!['today','trend','evidence'].includes(key))return;
 closeSheet();
 tabs.forEach(tab=>{ const on=tab.dataset.tab===key; tab.setAttribute('aria-selected',String(on)); tab.tabIndex=on?0:-1; document.getElementById(tab.getAttribute('aria-controls')).hidden=!on; });
 window.scrollTo({top:0,behavior:'instant'});
 if(focus) document.querySelector('[data-tab="'+key+'"]').focus({preventScroll:true});
}
document.addEventListener('click',function(e){
 const opener=e.target.closest('[data-sheet]'); if(opener){openSheet(opener.dataset.sheet,opener);return;}
 const tab=e.target.closest('[data-tab]'); if(tab){setTab(tab.dataset.tab,false);return;}
 const go=e.target.closest('[data-go]'); if(go){setTab(go.dataset.go,true);return;}
 const ref=e.target.closest('[data-ref]'); if(ref){
  setTab('evidence',false);
  document.getElementById('sources-details').open=true;
  const target=document.getElementById('source-'+ref.dataset.ref);
  if(target) requestAnimationFrame(()=>{target.scrollIntoView({block:'center',behavior:'instant'});target.querySelector('a')?.focus({preventScroll:true});});
 }
});
dialog.querySelector('.sheet-close').addEventListener('click',closeSheet);
dialog.addEventListener('click',e=>{if(e.target!==dialog)return;const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeSheet();});
dialog.addEventListener('close',()=>{document.body.style.overflow='';if(lastTrigger && document.contains(lastTrigger))lastTrigger.focus({preventScroll:true});});
tabs.forEach((tab,i)=>tab.addEventListener('keydown',e=>{
 let index;if(e.key==='ArrowRight')index=(i+1)%tabs.length;else if(e.key==='ArrowLeft')index=(i+tabs.length-1)%tabs.length;else if(e.key==='Home')index=0;else if(e.key==='End')index=tabs.length-1;else return;
 e.preventDefault();setTab(tabs[index].dataset.tab,true);
}));
})();
