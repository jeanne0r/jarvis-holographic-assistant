/* Live content previews. Reopen retained dialogs; never replay a tool or clone a player. */
(() => {
 const stage=document.querySelector('.command-stage');if(!stage)return;
 const rail=document.createElement('section');rail.className='workspace-screens';rail.setAttribute('aria-label','Fenêtres de Jarvis');stage.append(rail);
 const screens=new Map(),labels={radio:'RADIO',youtube:'VIDÉO',travel:'ITINÉRAIRE',web:'WEB',evolution:'CODEX'};
 const make=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls;if(text)el.textContent=text;return el;};
 function discard(kind){const screen=screens.get(kind);if(!screen)return;screen.observer.disconnect();screen.card.remove();screens.delete(kind);}
 document.addEventListener('jarvis:content-window',({detail:{kind,dialog}})=>{
  discard(kind);
  const card=make('article','workspace-screen');card.dataset.content=kind;
  const open=make('button','workspace-preview');open.type='button';
  const category=make('small','workspace-category',labels[kind]||'CONTENU'),title=make('strong','workspace-title'),summary=make('span','workspace-summary'),footer=make('span','workspace-open','Agrandir ↗');
  open.append(category,title,summary,footer);open.onclick=()=>window.jarvisCapabilities.openWindow(kind);
  const external=make('a','workspace-external','Nouvel onglet ↗');external.target='_blank';external.rel='noopener noreferrer';external.hidden=true;
  const dismiss=make('button','workspace-dismiss','×');dismiss.type='button';dismiss.setAttribute('aria-label','Retirer cet écran');dismiss.onclick=()=>window.jarvisCapabilities.closeWindow(kind);
  card.append(open,external,dismiss);rail.append(card);
  // Preview only actual text, status and validated links already present in the window.
  // No duplicate iframe, audio stream, Maps request or synthetic telemetry.
  const update=()=>{
   const heading=dialog.querySelector('h2')?.textContent||'Contenu';title.textContent=heading;open.setAttribute('aria-label','Agrandir : '+heading);
   const body=dialog.querySelector('.content-window-body');
   summary.textContent=[...(body?.querySelectorAll('p')||[])].filter(p=>!p.classList.contains('content-footnote')).map(p=>p.textContent).join(' · ').slice(0,240);
   const source=body?.querySelector('a[target="_blank"]');
   let href=null;try{const u=new URL(source?.href);if(['http:','https:'].includes(u.protocol)&&!u.username&&!u.password)href=u.href;}catch{}
   external.hidden=!href;if(href)external.href=href;else external.removeAttribute('href');
   external.setAttribute('aria-label','Ouvrir '+heading+' dans un nouvel onglet');
   if(!summary.textContent&&href)summary.textContent=new URL(href).hostname;

   card.dataset.active=String(dialog.open);
  };
  if(kind==='youtube'){card.append(dialog);window.jarvisCapabilities.dockWindow(kind);}
  const observer=new MutationObserver(update);observer.observe(dialog,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['open','href']});screens.set(kind,{card,observer});update();
 });
 document.addEventListener('jarvis:content-closed',e=>discard(e.detail.kind));
 document.addEventListener('jarvis:spacechange',()=>{for(const kind of [...screens.keys()])discard(kind);});
 window.addEventListener('pagehide',()=>{for(const kind of [...screens.keys()])discard(kind);});
})();
