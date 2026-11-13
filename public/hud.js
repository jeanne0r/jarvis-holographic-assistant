(() => {
  const states = {
    idle: ['EN VEILLE', 'Prêt quand vous l’êtes.', 'MICRO DÉSACTIVÉ'],
    muted: ['MICRO EN PAUSE', 'Touche le cœur pour reprendre.', 'MICRO EN PAUSE'],
    connecting: ['CONNEXION', 'Ouverture du canal vocal.', 'CONNEXION EN COURS'],
    listening: ['À VOTRE ÉCOUTE', 'Vous pouvez m’interrompre.', 'MICRO ACTIVÉ'],
    thinking: ['EN TRAITEMENT', 'Demande envoyée ou outil en cours.', 'RÉPONSE EN ATTENTE'],
    speaking: ['JE VOUS RÉPONDS', 'Interrompez-moi à tout moment.', 'CONVERSATION ACTIVE'],
    error: ['À VÉRIFIER', 'Consultez le message ci-dessous.', 'ATTENTION'],
  };
  document.querySelector('#hudMicShortcut').addEventListener('click', () => document.querySelector('#liveButton').click());
  document.addEventListener('visibilitychange', () => document.body.classList.toggle('hud-paused', document.hidden));
  let voice = 'idle', written = false;
  function update() {
    const state = written && voice === 'idle' ? 'thinking' : voice;
    const [label, hint, mode] = states[state] || states.idle;
    document.body.dataset.voice = state;
    document.querySelector('#hudState').textContent = label;
    const dictation=document.body.dataset.voiceMode==='dictation',muted=document.body.dataset.voiceMuted==='true';
    document.querySelector('#hudHint').textContent = muted?'Micro en pause · touche le cœur pour reprendre.':dictation&&state==='listening'?'Parle, puis marque une pause.':dictation&&['thinking','speaking'].includes(state)?'Micro en pause · réponse sans coupure.':hint;
    document.querySelector('#cinemaChannel').textContent = ({idle:'En veille',connecting:'Connexion…',listening:'À votre écoute',thinking:'En traitement',speaking:'Réponse vocale',error:'À vérifier',muted:'Micro en pause'})[state] || 'En veille';
    document.querySelector('#hudMode').textContent = written && voice === 'idle' ? 'RÉPONSE ÉCRITE' : muted?'MICRO EN PAUSE':mode;
  }
  document.addEventListener('jarvis:voice-mode',update);
  document.addEventListener('jarvis:voice-controls',update);
  document.addEventListener('jarvis:voice-state', event => {voice = event.detail.state; update();});
  document.addEventListener('jarvis:written-state', event => {written = event.detail.busy; update();});
  // live.js runs first; its initial state is also published on the body.
  voice = document.body.dataset.voice || 'idle'; update();
  const mirror = (source, target) => {
    const from = document.querySelector(source), to = document.querySelector(target);
    const sync = () => {to.textContent = from.textContent;};
    new MutationObserver(sync).observe(from, {childList:true,subtree:true,characterData:true}); sync();
  };
  mirror('#voiceDailyCost', '#cockpitDaily');mirror('#count', '#cockpitMemory');mirror('#voiceCreditBalance', '#cockpitCredit');
  mirror('#count', '#cinemaMemoryCount'); mirror('#profileName', '#cinemaPerson');
  function tick() {
    if (!document.hidden) document.querySelector('#cinemaTime').textContent = new Intl.DateTimeFormat('fr-CH', {timeZone:'Europe/Zurich',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());
  }
  const originalTick=tick;
  function referenceClock(){
    if(document.hidden)return;
    document.querySelector('#referenceTime').textContent = new Intl.DateTimeFormat('fr-CH',{timeZone:'Europe/Zurich',hour:'2-digit',minute:'2-digit'}).format(new Date());
    document.querySelector('#referenceDate').textContent = new Intl.DateTimeFormat('fr-CH',{timeZone:'Europe/Zurich',weekday:'long',day:'numeric',month:'long'}).format(new Date());
  }
  tick();referenceClock();setInterval(()=>{originalTick();referenceClock();},1000);
  const immersion = document.querySelector('#immersionButton');
  function immersive(on) {
    document.body.classList.toggle('immersive', on);
    immersion.setAttribute('aria-pressed',String(on));
    document.querySelector('#immersionLabel').textContent = on ? 'Quitter l’immersion' : 'Immersion';
  }
  immersion.addEventListener('click', () => {if(document.body.dataset.screen !== 'chat') document.querySelector('.nav[data-view="chat"]').click();immersive(!document.body.classList.contains('immersive'));});
  document.addEventListener('keydown', event => {if(event.key === 'Escape' && !document.querySelector('dialog[open]')) immersive(false);});
  const sheet = document.querySelector('#cockpitSheet'), content = document.querySelector('#cockpitSheetContent');
  let staged = [];
  const tabs=document.createElement('div');tabs.className='memory-popup-tabs';for(const [kind,label] of [['library','Mémoire'],['atelier','Idées']]){const button=document.createElement('button');button.type='button';button.id=kind==='library'?'libraryAllTab':'libraryIdeasTab';button.textContent=label;button.onclick=()=>window.jarvisOpenPanel(kind);tabs.append(button);}document.querySelector('.toolbar').prepend(tabs);

  function restorePanels() {for(const {node,anchor,hidden} of staged){node.hidden=hidden;anchor.replaceWith(node);}staged=[];window.jarvisLibraryClose?.();document.dispatchEvent(new CustomEvent('jarvis:view',{detail:{view:'chat'}}));sheet.classList.remove('memory-sheet','map-sheet');document.body.classList.remove('hud-sheet-open');}
  function closeSheet() {if(sheet.open){restorePanels();sheet.close();}}
  sheet.addEventListener('close', () => {if(!sheet.open)restorePanels();});
  sheet.addEventListener('cancel', event => {event.preventDefault();closeSheet();});
  function showSheet(kind) {
    if(sheet.open)return;
    const nodes = ['library','atelier'].includes(kind)?[document.querySelector('.toolbar'),document.querySelector('#libraryView')]:kind==='memory3d'?[document.querySelector('#memory3dView')]:kind === 'home' ? [document.querySelector('#homeVoicePanel')] : kind === 'write' ? [document.querySelector('.conversation-feed')] : [document.querySelector('.live-panel'),document.querySelector('.memory-state')];
    document.querySelector('#cockpitSheetTitle').textContent = kind==='library'?'Mémoire':kind==='atelier'?'Idées':kind==='memory3d'?'Mémoire 3D':kind === 'home' ? 'Maison' : kind === 'write' ? 'Conversation' : 'Usage & mémoire';
    for(const node of nodes){const anchor=document.createComment('cockpit-panel');const hidden=node.hidden;node.replaceWith(anchor);node.hidden=false;content.append(node);staged.push({node,anchor,hidden});}
    if(kind==='home')document.querySelector('#homeStartVoice').textContent=document.querySelector('#liveButton').getAttribute('aria-pressed')==='true'?'Revenir à la voix':'Ouvrir le micro';
    sheet.classList.toggle('memory-sheet',['library','atelier'].includes(kind));sheet.classList.toggle('map-sheet',kind==='memory3d');sheet.showModal();document.body.classList.add('hud-sheet-open');if(['library','atelier'].includes(kind))window.jarvisLibraryMode?.(kind);if(kind==='memory3d')document.dispatchEvent(new CustomEvent('jarvis:view',{detail:{view:'memory3d'}}));
    if(kind === 'write')document.querySelector('#question').focus({preventScroll:true});
  }
  document.querySelectorAll('[data-system]').forEach(button => button.addEventListener('click', () => {
    const kind=button.dataset.system;
    if(['library','atelier','memory3d'].includes(kind))showSheet(kind);else if(kind==='conversation')showSheet('write');
    else if(kind==='resources')showSheet('resources');
    else if(kind==='note')document.querySelector('#newNote').click();
    else if(kind==='home')showSheet('home');
  }));
  document.querySelector('#homeStartVoice').addEventListener('click',()=>{closeSheet();const mic=document.querySelector('#liveButton');if(mic.getAttribute('aria-pressed')!=='true')mic.click();});
  window.jarvisOpenPanel=kind=>{if(sheet.open)closeSheet();showSheet(kind);};
  document.querySelector('#cockpitWrite').addEventListener('click', () => showSheet('write'));
  document.querySelector('#cockpitResources').addEventListener('click', () => showSheet('resources'));
  document.querySelector('#cockpitSheetClose').addEventListener('click',closeSheet);
  sheet.addEventListener('click',event => {if(event.target===sheet){const r=sheet.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeSheet();}});
  const portrait = matchMedia('(max-width:760px)');
  portrait.addEventListener('change',closeSheet);
  document.addEventListener('jarvis:voice-caption',event=>{const text=event.detail.text||'';document.querySelector('#cockpitCaption').textContent=text.length>140?text.slice(-137)+'…':text;});
  const captions=document.querySelector('#liveTranscript');
  new MutationObserver(() => {
    const text=captions.lastElementChild?.textContent || '';
    document.querySelector('#cockpitCaption').textContent = text.length>140?text.slice(-137)+'…':text;
  }).observe(captions,{childList:true,characterData:true,subtree:true});
  const stage = document.querySelector('.command-stage');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const fine = matchMedia('(hover: hover) and (pointer: fine)');
  let pointerFrame = 0;
  stage.addEventListener('pointermove', event => {
    if (reduced.matches || !fine.matches || pointerFrame) return;
    const x=event.clientX,y=event.clientY;
    pointerFrame=requestAnimationFrame(() => {
      pointerFrame=0;const box=stage.getBoundingClientRect();
      stage.style.setProperty('--look-x',(((x-box.left)/box.width-.5)*8).toFixed(2)+'deg');
      stage.style.setProperty('--look-y',(-((y-box.top)/box.height-.5)*6).toFixed(2)+'deg');
    });
  });
  stage.addEventListener('pointerleave', () => {cancelAnimationFrame(pointerFrame);pointerFrame=0;stage.style.setProperty('--look-x','0deg');stage.style.setProperty('--look-y','0deg');});
})();
