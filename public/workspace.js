/* Live content previews. Reopen retained dialogs; never replay a tool or clone a player. */
(() => {
 const stage=document.querySelector('.command-stage');if(!stage)return;
 const rail=document.createElement('section');rail.className='workspace-screens';rail.setAttribute('aria-label','Fenêtres de Jarvis');stage.append(rail);
 const syncSides=()=>{let index=0;for(const card of rail.children){if(card.classList.contains('workspace-floating'))continue;if(card.classList.contains('workspace-screen'))card.dataset.side=index%2?'right':'left';index++;}};
 const screens=new Map(),labels={radio:'RADIO',youtube:'VIDÉO',travel:'ITINÉRAIRE',web:'WEB',evolution:'CODEX'};
 const make=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls;if(text)el.textContent=text;return el;};
 function discard(kind){const screen=screens.get(kind);if(!screen)return;screen.observer.disconnect();screen.placeholder?.remove();screen.card.remove();screens.delete(kind);syncSides();stage.classList.toggle('has-workspace-screens',screens.size>0);}
 document.addEventListener('jarvis:content-window',({detail:{kind,dialog}})=>{
  discard(kind);
  const card=make('article','workspace-screen');card.dataset.content=kind;if(kind==='youtube')card.classList.add('workspace-video');
  const open=make('button','workspace-preview');open.type='button';
  const category=make('small','workspace-category',labels[kind]||'CONTENU'),title=make('strong','workspace-title'),summary=make('span','workspace-summary'),footer=make('span','workspace-open','Agrandir ↗');
  open.append(title,summary,footer);open.onclick=()=>window.jarvisCapabilities.openWindow(kind);
  const external=make('a','workspace-external','Nouvel onglet ↗');external.target='_blank';external.rel='noopener noreferrer';external.hidden=true;
  const dismiss=make('button','workspace-dismiss','×');dismiss.type='button';dismiss.setAttribute('aria-label','Retirer cet écran');dismiss.onclick=()=>window.jarvisCapabilities.closeWindow(kind);
  // Captured touch gestures do not consistently synthesize clicks in every
  // browser. Activate intentional taps once, while keeping native keyboard clicks.
  for(const button of [open,dismiss]){
   let tap=null,ignoreClickUntil=0;
   button.addEventListener('pointerdown',event=>{if(event.pointerType==='touch'&&event.isPrimary)tap={id:event.pointerId,x:event.clientX,y:event.clientY};});
   button.addEventListener('pointercancel',()=>{tap=null;});
   button.addEventListener('pointerup',event=>{const start=tap;tap=null;if(start?.id!==event.pointerId||Math.hypot(event.clientX-start.x,event.clientY-start.y)>10)return;button.click();ignoreClickUntil=performance.now()+600;});
   button.addEventListener('touchend',event=>{if(performance.now()<ignoreClickUntil)event.preventDefault();},{passive:false});
   button.addEventListener('click',event=>{if(event.isTrusted&&performance.now()<ignoreClickUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
  }
  const handle=make('button','workspace-drag','⠿ '+(labels[kind]||'CONTENU'));handle.type='button';handle.setAttribute('aria-label','Déplacer cet écran');handle.title='Glisser pour déplacer · flèches au clavier · Début pour réinitialiser';handle.setAttribute('aria-keyshortcuts','ArrowLeft ArrowRight ArrowUp ArrowDown Home');
  const resize=make('button','workspace-resize','◢');resize.type='button';resize.setAttribute('aria-label','Redimensionner cet écran');resize.title='Glisser pour redimensionner · flèches au clavier · Début pour réinitialiser';resize.setAttribute('aria-keyshortcuts','ArrowLeft ArrowRight ArrowUp ArrowDown Home');
  card.append(handle,open,external,dismiss,resize);rail.append(card);syncSides();
  // Pointer-only optical parallax: no camera permission, audio work or render loop.
  const tiltAllowed=matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
  let tiltFrame=0;
  const resetTilt=()=>{cancelAnimationFrame(tiltFrame);tiltFrame=0;for(const key of ['--pointer-x','--pointer-y','--light-x','--light-y'])card.style.removeProperty(key);};
  card.addEventListener('pointermove',event=>{
   if(!tiltAllowed.matches||event.pointerType!=='mouse'||card.contains(document.activeElement))return;
   const rect=card.getBoundingClientRect(),x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
   cancelAnimationFrame(tiltFrame);tiltFrame=requestAnimationFrame(()=>{tiltFrame=0;card.style.setProperty('--pointer-x',((.5-y)*5).toFixed(2)+'deg');card.style.setProperty('--pointer-y',((x-.5)*7).toFixed(2)+'deg');card.style.setProperty('--light-x',(x*100).toFixed(1)+'%');card.style.setProperty('--light-y',(y*100).toFixed(1)+'%');});
  });
  card.addEventListener('pointerleave',resetTilt);card.addEventListener('focusin',resetTilt);
  let drag=null;
  const bounds=()=>{const v=window.visualViewport;return {left:(v?.offsetLeft||0)+8,top:(v?.offsetTop||0)+8,width:(v?.width||innerWidth)-16,height:(v?.height||innerHeight)-16};};
  const place=(x,y)=>{const b=bounds(),w=card.offsetWidth,h=card.offsetHeight;card.style.left=Math.max(b.left,Math.min(b.left+b.width-w,x))+'px';card.style.top=Math.max(b.top,Math.min(b.top+b.height-h,y))+'px';card.dataset.side=parseFloat(card.style.left)+w/2<innerWidth/2?'left':'right';};
  const float=()=>{if(card.classList.contains('workspace-floating'))return;const r=card.getBoundingClientRect(),placeholder=make('div','workspace-placeholder');placeholder.style.width=r.width+'px';placeholder.style.height=r.height+'px';placeholder.setAttribute('aria-hidden','true');card.before(placeholder);screens.get(kind).placeholder=placeholder;card.style.width=Math.min(r.width,bounds().width)+'px';card.classList.add('workspace-floating');place(r.left,r.top);};
  const restore=()=>{const screen=screens.get(kind);screen?.placeholder?.remove();if(screen)screen.placeholder=null;card.classList.remove('workspace-floating','workspace-sized');for(const name of ['left','top','width','height'])card.style.removeProperty(name);syncSides();};
  handle.addEventListener('pointerdown',event=>{if(event.button!==0||!event.isPrimary)return;event.preventDefault();handle.focus({preventScroll:true});float();const r=card.getBoundingClientRect();drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:r.left,top:r.top};handle.setPointerCapture(event.pointerId);card.classList.add('workspace-dragging');});
  handle.addEventListener('pointermove',event=>{if(!drag||drag.id!==event.pointerId)return;event.preventDefault();place(drag.left+event.clientX-drag.x,drag.top+event.clientY-drag.y);});
  const release=event=>{if(drag?.id!==event.pointerId)return;drag=null;card.classList.remove('workspace-dragging');if(handle.hasPointerCapture(event.pointerId))handle.releasePointerCapture(event.pointerId);};
  handle.addEventListener('pointerup',release);handle.addEventListener('pointercancel',release);handle.addEventListener('lostpointercapture',release);handle.addEventListener('dblclick',restore);
  handle.addEventListener('keydown',event=>{if(event.key==='Home'){event.preventDefault();restore();return;}const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];if(!delta)return;event.preventDefault();float();const r=card.getBoundingClientRect(),step=event.shiftKey?40:12;place(r.left+delta[0]*step,r.top+delta[1]*step);});
  let sizing=null;
  const setSize=(width,height)=>{const b=bounds();card.classList.add('workspace-sized');card.style.width=Math.max(Math.min(240,b.width),Math.min(b.width,width))+'px';card.style.height=Math.max(Math.min(240,b.height),Math.min(b.height,height))+'px';place(parseFloat(card.style.left)||b.left,parseFloat(card.style.top)||b.top);};
  resize.addEventListener('pointerdown',event=>{if(event.button!==0||!event.isPrimary)return;resetTilt();resize.focus({preventScroll:true});float();card.classList.add('workspace-resizing');sizing={id:event.pointerId,x:event.clientX,y:event.clientY,width:card.offsetWidth,height:card.offsetHeight};setSize(sizing.width,sizing.height);resize.setPointerCapture(event.pointerId);});
  resize.addEventListener('pointermove',event=>{if(sizing?.id!==event.pointerId)return;setSize(sizing.width+event.clientX-sizing.x,sizing.height+event.clientY-sizing.y);});
  const endSize=event=>{if(sizing?.id!==event.pointerId)return;sizing=null;card.classList.remove('workspace-resizing');if(resize.hasPointerCapture(event.pointerId))resize.releasePointerCapture(event.pointerId);};
  resize.addEventListener('pointerup',endSize);resize.addEventListener('pointercancel',endSize);resize.addEventListener('lostpointercapture',endSize);resize.addEventListener('dblclick',restore);
  resize.addEventListener('keydown',event=>{if(event.key==='Home'){event.preventDefault();restore();return;}const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];if(!delta)return;event.preventDefault();float();const step=event.shiftKey?40:12;setSize(card.offsetWidth+delta[0]*step,card.offsetHeight+delta[1]*step);});
  card.addEventListener('pointerdown',()=>{for(const screen of screens.values())screen.card.classList.remove('workspace-front');card.classList.add('workspace-front');});
  card.jarvisClamp=()=>{if(card.classList.contains('workspace-floating')){const r=card.getBoundingClientRect();if(card.classList.contains('workspace-sized'))setSize(card.offsetWidth,card.offsetHeight);else{card.style.width=Math.min(card.offsetWidth,bounds().width)+'px';place(parseFloat(card.style.left)||r.left,parseFloat(card.style.top)||r.top);}}};

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
  card.append(dialog);if(kind==='youtube')window.jarvisCapabilities.dockWindow(kind);
  const observer=new MutationObserver(update);observer.observe(dialog,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['open','href']});screens.set(kind,{card,observer});stage.classList.add('has-workspace-screens');update();
 });
 window.addEventListener('resize',()=>{for(const screen of screens.values())screen.card.jarvisClamp();});
 window.visualViewport?.addEventListener('resize',()=>{for(const screen of screens.values())screen.card.jarvisClamp();});
 document.addEventListener('jarvis:content-closed',e=>discard(e.detail.kind));
 document.addEventListener('jarvis:spacechange',()=>{for(const kind of [...screens.keys()])discard(kind);});

 window.addEventListener('pagehide',()=>{for(const screen of screens.values())screen.observer.disconnect();screens.clear();});
})();
