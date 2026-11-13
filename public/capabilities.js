(() => {
 const $=s=>document.querySelector(s),seen=new Map(),windows=new Map();
 const audio=document.createElement('audio');audio.id='jarvisRadio';audio.preload='none';audio.hidden=true;document.body.append(audio);
 let configPromise,ytPromise,mapsPromise,player,volume=.65,duck=false,playing=false,mediaKind='radio',mediaSerial=0,routeSerial=0,poll=0,mediaStatus=null;
 const space=()=>$('#spaceSelect')?.value||'member1';
 const note=(node,text)=>{if(node)node.textContent=text;};
 const node=(tag,text,className)=>{const el=document.createElement(tag);if(text)el.textContent=text;if(className)el.className=className;return el;};
 async function api(path,data,selectedSpace=space()){
  const r=await fetch('/api/jarvis/'+path+(path.includes('?')?'&':'?')+'space='+encodeURIComponent(selectedSpace),data?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data)}:{});const out=await r.json();if(!r.ok)throw Error(out.error||'Action indisponible.');return out;
 }
 const config=()=>configPromise??=api('capabilities').catch(e=>{configPromise=null;throw e});
 function link(text,url,hosts){const u=new URL(url);if(u.protocol!=='https:'||!hosts.includes(u.hostname)||u.username||u.password)throw Error('Lien non autorisé.');const a=node('a',text);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}
 function syncOverlay(){document.body.classList.toggle('hud-sheet-open',!!document.querySelector('dialog[open]:not(.content-docked)'));}
 function contentWindow(kind,title){
  const old=$('#cockpitSheet');if(old?.open)old.close();
  for(const win of windows.values())if(win.dialog.open&&!win.dialog.classList.contains('content-docked'))hideWindow(win);
  const previous=windows.get(kind);previous?.dialog.remove();
  const dialog=node('dialog',null,'content-window');dialog.dataset.content=kind;dialog.id='jarvis-window-'+kind;
  const header=node('header',null,'content-window-header'),heading=node('h2',title),close=node('button','×','content-close');heading.id=dialog.id+'-title';dialog.setAttribute('aria-labelledby',heading.id);close.type='button';close.setAttribute('aria-label','Fermer');close.onclick=()=>dialog.close();header.append(heading,close);
  const body=node('div',null,'content-window-body');dialog.append(header,body);document.body.append(dialog);
  const win={dialog,body,heading,internalCloses:0};windows.set(kind,win);
  {const shrink=node('button','Réduire','content-minimize');shrink.type='button';shrink.onclick=()=>dockWindow(kind);header.insertBefore(shrink,close);}
  dialog.addEventListener('close',()=>{if(win.internalCloses){win.internalCloses--;return;}if(windows.get(kind)===win)closeWindow(kind);syncOverlay();});
  document.dispatchEvent(new CustomEvent('jarvis:content-window',{detail:{kind,dialog}}));if(!dialog.open)dialog.showModal();syncOverlay();return win;
 }
 function button(text,action){const b=node('button',text);b.type='button';b.onclick=()=>Promise.resolve(action()).catch(error=>note(mediaStatus,error.message));return b;}
 function applyVolume(){audio.volume=volume*(duck?.15:1);try{player?.setVolume(volume*(duck?.15:1)*100);}catch{}}
 document.addEventListener('jarvis:live-diagnostics',e=>{const next=e.detail.transport==='ready';if(next!==duck){duck=next;applyVolume();}});
 audio.addEventListener('playing',()=>{playing=true;if(mediaKind==='radio')note(mediaStatus,'En direct');});
 audio.addEventListener('pause',()=>{if(mediaKind==='radio'){playing=false;note(mediaStatus,'En pause');}});
 audio.addEventListener('error',()=>{if(mediaKind==='radio')note(mediaStatus,'Le flux radio ne répond pas. Réessaie dans un instant.');});
 const playAudio=async()=>{const serial=mediaSerial;try{await audio.play();return {state:serial===mediaSerial?'playing':'cancelled'};}catch{if(serial!==mediaSerial)return {state:'cancelled'};note(mediaStatus,'Appuie sur Lecture pour autoriser le son.');return {state:'needs_gesture'};}};
 function radioControls(body){
  const controls=node('div',null,'content-controls');controls.append(button('Lecture',()=>playAudio()),button('Pause',()=>media({action:'pause'})),button('Arrêter',()=>media({action:'arreter'})));
  const label=node('label','Volume','content-volume'),range=node('input');range.type='range';range.min=0;range.max=100;range.value=Math.round(volume*100);range.oninput=()=>{volume=Number(range.value)/100;applyVolume();};label.append(range);body.append(controls,label);
 }
 async function youtube(){
  if(window.YT?.Player)return;
  if(!ytPromise)ytPromise=new Promise((resolve,reject)=>{const timer=setTimeout(()=>{ytPromise=null;reject(Error('YouTube ne répond pas ; ouvre le lien vidéo.'));},15000);const old=window.onYouTubeIframeAPIReady;window.onYouTubeIframeAPIReady=()=>{clearTimeout(timer);old?.();resolve();};const script=document.createElement('script');script.src='https://www.youtube.com/iframe_api';script.onerror=()=>{clearTimeout(timer);ytPromise=null;reject(Error('YouTube bloqué par le navigateur ou un bloqueur.'));};document.head.append(script);});
  await ytPromise;
 }
 async function media(effect){
  const action=effect.action;if(!['radio','youtube','pause','reprendre','arreter','volume'].includes(action))throw Error('Commande média inconnue.');
  if(action==='volume'){if(!Number.isFinite(effect.volume)||effect.volume<0||effect.volume>1)throw Error('Volume invalide.');volume=effect.volume;document.querySelectorAll('.content-volume input').forEach(input=>input.value=Math.round(volume*100));applyVolume();return {state:'volume_set',volume};}
  if(action==='pause'||action==='arreter'){audio.pause();player?.pauseVideo?.();if(action==='arreter'){player?.stopVideo?.();audio.removeAttribute('src');audio.load();}if(mediaKind==='radio')playing=false;note(mediaStatus,action==='pause'?'En pause':'Lecture arrêtée');return {state:mediaKind==='youtube'?(action==='pause'?'pause_requested':'stop_requested'):action==='pause'?'paused':'stopped'};}
  if(action==='reprendre'){if(mediaKind==='youtube'&&player){player.playVideo();return {state:player.getPlayerState()===1?'playing':'play_requested'};}return playAudio();}
  const serial=++mediaSerial;
  if(action==='radio'){
   const stream=new URL(effect.url);if(stream.protocol!=='https:'||stream.username||stream.password)throw Error('Flux radio non autorisé.');const station={name:effect.title||effect.radio?.name||'Radio',url:stream.href};if(serial!==mediaSerial)return {state:'cancelled'};
   player?.pauseVideo?.();mediaKind='radio';playing=false;const win=contentWindow('radio',station.name);win.body.append(node('div','RADIO · EN DIRECT','content-eyebrow'));mediaStatus=node('p','Connexion…','content-status');mediaStatus.id='radioStatus';win.body.append(mediaStatus);radioControls(win.body);
   audio.src=station.url;applyVolume();return playAudio();
  }
  const external=effect.search?link('Voir les résultats sur YouTube ↗',effect.search,['www.youtube.com']):link('Ouvrir sur YouTube ↗','https://www.youtube.com/watch?v='+effect.videoId,['www.youtube.com']);
  if(effect.search&&new URL(effect.search).pathname!=='/results')throw Error('Recherche YouTube invalide.');
  if(!effect.search&&!/^[\w-]{11}$/.test(effect.videoId||''))throw Error('Vidéo YouTube invalide.');
  audio.pause();player?.destroy?.();player=null;mediaKind='youtube';playing=false;
  const win=contentWindow('youtube',effect.title||'YouTube');mediaStatus=node('p',effect.search?'Choisis une vidéo dans les résultats.':'Ouverture de la vidéo…','content-status');mediaStatus.id='youtubeStatus';win.body.append(mediaStatus);
  if(effect.search){win.body.append(external);return {state:'search_ready',playing:false};}
  const mount=node('div',null,'content-video');mount.id='youtubeMount';win.body.prepend(mount);const target=node('div');mount.append(target);win.body.append(external);
  await youtube();if(serial!==mediaSerial)return {state:'cancelled'};
  const status=mediaStatus;
  player=new YT.Player(target,{width:'100%',height:'250',videoId:effect.videoId,playerVars:{playsinline:1,origin:location.origin,autoplay:1},events:{onReady:event=>{if(serial!==mediaSerial||windows.get('youtube')!==win){event.target.destroy();return;}applyVolume();event.target.playVideo();},onStateChange:event=>{if(serial!==mediaSerial)return;playing=event.data===1;note(status,playing?'':event.data===2?'En pause':'Appuie sur la vidéo pour démarrer.');},onAutoplayBlocked:()=>{if(serial!==mediaSerial)return;note(status,'Appuie sur la vidéo pour autoriser le son.');},onError:()=>note(status,'Cette vidéo ne peut pas être lue ici. Utilise « Ouvrir sur YouTube ».')}});
  return {state:'player_ready',playing:false,hint:'Attendre l’événement de lecture ; Safari ou l’auteur peut bloquer la lecture intégrée.'};
 }
 async function loadMaps(key){
  if(window.google?.maps?.importLibrary)return;
  if(!mapsPromise)mapsPromise=new Promise((resolve,reject)=>{const timer=setTimeout(()=>{mapsPromise=null;reject(Error('Google Maps ne répond pas. Vérifie la clé et les services Maps.'));},20000);window.jarvisMapsReady=()=>{clearTimeout(timer);resolve();};window.gm_authFailure=()=>{clearTimeout(timer);mapsPromise=null;reject(Error('Google refuse la clé Maps ou cette adresse Jarvis. Vérifie les restrictions de sites et les API autorisées.'));};const s=document.createElement('script');s.src='https://maps.googleapis.com/maps/api/js?'+new URLSearchParams({key,loading:'async',callback:'jarvisMapsReady',v:'weekly',language:'fr'});s.onerror=()=>{clearTimeout(timer);mapsPromise=null;reject(Error('Google Maps bloqué ou indisponible.'));};document.head.append(s);});
  await mapsPromise;
 }
 async function travel(effect){
  const googleLink=link('Google Maps ↗',effect.maps,['www.google.com']),wazeLink=link('Waze ↗',effect.waze,['waze.com']);
  const serial=++routeSerial,win=contentWindow('travel',effect.title||'Trajet'),info=node('p','Calcul du trajet avec la circulation…','content-status'),mapBox=node('div',null,'content-map');info.id='travelStatus';mapBox.id='travelMap';mapBox.setAttribute('aria-label','Carte du trajet');win.body.append(info,mapBox);
  const controls=node('div',null,'content-controls');controls.append(googleLink,wazeLink,button('Actualiser',()=>travel({...effect,id:undefined})));win.body.append(controls);
  const c=await config();if(serial!==routeSerial)return {state:'cancelled'};
  if(!c.maps.configured){note(info,'Itinéraire disponible dans Google Maps.');if(effect.embed){const u=new URL(effect.embed);if(u.origin!=='https://embed.waze.com'||!u.pathname.endsWith('/iframe'))throw Error('Carte non autorisée.');const frame=node('iframe');frame.src=u.href;frame.title='Circulation Waze';frame.referrerPolicy='strict-origin-when-cross-origin';mapBox.append(frame);}return {state:'links_ready',eta:null};}
  win.body.append(node('small','Google Maps · frais éventuels distincts de Gemini','content-footnote'));
  try{
   await loadMaps(c.maps.key);if(serial!==routeSerial)return {state:'cancelled'};
   const [{Map,TrafficLayer},{Route},{LatLngBounds}]=await Promise.all([google.maps.importLibrary('maps'),google.maps.importLibrary('routes'),google.maps.importLibrary('core')]);
   let origin=effect.routeOrigin;
   if(!origin){origin=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(p=>resolve({lat:p.coords.latitude,lng:p.coords.longitude}),()=>reject(Error('Position non autorisée. Demande le trajet depuis la maison.')),{timeout:10000,maximumAge:60000}));}
   if(serial!==routeSerial)return {state:'cancelled'};
   const {routes}=await Route.computeRoutes({origin,destination:effect.routeDestination,travelMode:({driving:'DRIVING',walking:'WALKING',bicycling:'BICYCLING',transit:'TRANSIT'})[effect.mode]||'DRIVING',...(effect.mode==='driving'?{routingPreference:'TRAFFIC_AWARE'}:{}),fields:['path','durationMillis','distanceMeters']});
   if(serial!==routeSerial)return {state:'cancelled'};const route=routes?.[0];if(!route)throw Error('Aucun trajet trouvé par Google Maps.');
   const map=new Map(mapBox,{center:route.path?.[0]||{lat:46.8,lng:8.2},zoom:10,mapTypeControl:false,streetViewControl:false,fullscreenControl:true});new TrafficLayer().setMap(map);route.createPolylines().forEach(p=>p.setMap(map));const bounds=new LatLngBounds();route.path?.forEach(p=>bounds.extend(p));map.fitBounds(bounds,30);
   const minutes=Math.round(route.durationMillis/60000),km=Math.round(route.distanceMeters/100)/10;
   note(info,(Number.isFinite(minutes)?minutes+' min':'Durée indisponible')+' · '+km+' km · circulation actuelle');return {state:'route_displayed',durationMinutes:minutes,distanceKm:km,source:'Google Maps',checkedAt:new Date().toISOString(),trafficAware:effect.mode==='driving'};
  }catch(error){const message=/^(Google|Aucun|Position|Clé|Le |La )/.test(error.message)?error.message:'Le service Google Maps n’a pas pu calculer ce trajet.';note(info,message+' Le lien Google Maps reste disponible.');return {state:'map_error',error:message,eta:null};}
 }
 async function evolution(effect,selectedSpace){
  if(!/^[a-f0-9-]{36}$/.test(effect.jobId||''))throw Error('Préparation inconnue.');
  clearTimeout(poll);const win=contentWindow('evolution','Évolution de Jarvis'),info=node('p','Chargement…','content-status'),output=node('p'),details=node('details'),patch=node('pre');info.id='evolutionStatus';details.id='evolutionDiff';details.hidden=true;details.append(node('summary','Voir les modifications'),patch);win.body.append(info,output,details);win.body.append(node('small','Version préparée séparément. Revue et essais nécessaires avant installation.','content-footnote'));
  const refresh=async()=>{if(space()!==selectedSpace||windows.get('evolution')!==win)return;try{const job=await api('evolution/status?id='+encodeURIComponent(effect.jobId),null,selectedSpace);if(windows.get('evolution')!==win)return;note(info,({queued:'Demande enregistrée',running:'Codex prépare les modifications…',ready:'Proposition prête · non installée',failed:'Préparation non validée',interrupted:'Préparation interrompue'})[job.status]||job.status);note(output,[job.request,job.summary,job.diffStat,job.limitations,job.message].filter(Boolean).join('\n\n'));if(job.status==='ready'){const data=await api('evolution/diff?id='+effect.jobId,null,selectedSpace);details.hidden=false;note(patch,data.patch);}else if(['queued','running'].includes(job.status)&&win.dialog.open)poll=setTimeout(refresh,4000);}catch(e){note(info,e.message);}};
  win.onReopen=refresh;await refresh();return {state:'draft_requested',installed:false};
 }
 function webLink(label,value,site=false){
  const u=new URL(value);if(!(site?['http:','https:'].includes(u.protocol):u.protocol==='https:')||u.username||u.password||(!site&&(!u.hostname.includes('.')||/(^|\.)(localhost|local|internal|invalid|test)$/.test(u.hostname)||/^[\d.]+$/.test(u.hostname))))throw Error('Adresse du site non autorisée.');return link(label,u.href,[u.hostname]);
 }
 async function webContent(effect){
  if(!['site','search','sources'].includes(effect.kind))throw Error('Contenu web inconnu.');
  const external=effect.kind==='site'?webLink('Ouvrir dans un onglet ↗',effect.url,true):null;
  const sources=(effect.sources||[]).slice(0,8).map(source=>({...source,anchor:webLink(source.title||'Source',source.url)}));
  const win=contentWindow('web',effect.title||'Web');win.dialog.dataset.webKind=effect.kind;
  if(effect.kind==='site'){
   if(effect.embed){const frame=node('iframe',null,'content-site');frame.src=external.href;frame.title=effect.title||'Site demandé';frame.setAttribute('sandbox','allow-scripts allow-forms allow-same-origin');frame.setAttribute('allow',"autoplay; fullscreen; encrypted-media; picture-in-picture; camera 'none'; microphone 'none'; geolocation 'none'");frame.referrerPolicy='no-referrer';win.body.append(frame);win.body.append(node('p','Si le site refuse l’affichage intégré, utilise le lien ci-dessous.','content-footnote'));}
   else win.body.append(node('p','Ce site est à ouvrir directement dans le navigateur.'));
   win.body.append(external);return {state:effect.embed?'frame_requested':'external_link_ready',opened:false};
  }
  if(effect.kind==='search'){
   if(effect.googleUrl){const google=link('Ouvrir les résultats Google ↗',effect.googleUrl,['www.google.com']);if(new URL(google.href).pathname!=='/search')throw Error('Recherche Google invalide.');win.body.append(google);if(effect.openResults){const tab=window.open('about:blank','_blank');if(tab){tab.opener=null;tab.location.replace(google.href);}else win.body.append(node('p','Appuie sur « Ouvrir les résultats Google » pour ouvrir la recherche dans ton navigateur.','content-status'));}}
   const paragraph=node('p'),answer=String(effect.answer||'');let cursor=0;
   for(const support of [...(effect.supports||[])].sort((a,b)=>a.segment?.endIndex-b.segment?.endIndex)){
    const end=support.segment?.endIndex;if(!Number.isInteger(end)||end<cursor||end>answer.length)continue;paragraph.append(document.createTextNode(answer.slice(cursor,end)));cursor=end;
    for(const index of support.groundingChunkIndices||[]){const source=sources.find(s=>s.index===index);if(source)paragraph.append(webLink(' ['+(index+1)+']',source.url));}
   }
   paragraph.append(document.createTextNode(answer.slice(cursor)));win.body.append(paragraph);
  }
  if(sources.length){const refs=node('div',null,'content-web-sources');for(const source of sources)refs.append(source.anchor);win.body.append(refs);}
  if(effect.searchSuggestions){const suggestions=node('iframe',null,'content-search-suggestions');suggestions.title='Suggestions Google Search';suggestions.setAttribute('sandbox','allow-popups allow-popups-to-escape-sandbox');suggestions.referrerPolicy='no-referrer';suggestions.srcdoc=String(effect.searchSuggestions);win.body.append(suggestions);}
  return {state:'sources_displayed',sourceCount:sources.length};
 }
 async function execute(effect,context={}){
  if(effect?.type==='interface'&&effect.action==='close'){const targets=effect.target==='toutes'?[...document.querySelectorAll('dialog[open]')]:[document.querySelector('.content-window[open]:not(.content-docked)')||document.querySelector('dialog[open]:not(.content-docked)')||document.querySelector('.content-docked[open]')].filter(Boolean);for(const dialog of targets)dialog.close();syncOverlay();return {state:'closed',count:targets.length};}
  if(!effect||!['media','travel','evolution','web'].includes(effect.type))throw Error('Action inconnue.');
  const selectedSpace=context.space||space();if(selectedSpace!==space())return {state:'cancelled'};
  if(effect.id&&seen.has(effect.id))return seen.get(effect.id);
  const promise=(async()=>{try{return effect.type==='media'?await media(effect):effect.type==='travel'?await travel(effect):effect.type==='web'?await webContent(effect):await evolution(effect,selectedSpace);}catch(error){note(effect.type==='media'?mediaStatus:windows.get(effect.type)?.body.querySelector('.content-status'),error.message);return {state:'error',error:error.message};}})();
  if(effect.id){seen.set(effect.id,promise);if(seen.size>100)seen.delete(seen.keys().next().value);}return promise;
 }
 function reset(){mediaSerial++;routeSerial++;clearTimeout(poll);seen.clear();audio.pause();player?.destroy?.();player=null;playing=false;for(const win of windows.values()){if(win.dialog.open)win.dialog.close();win.dialog.remove();}windows.clear();mediaStatus=null;syncOverlay();}
 document.addEventListener('jarvis:spacechange',reset);
 window.addEventListener('pagehide',reset);
 function hideWindow(win){if(win.dialog.open){win.internalCloses++;win.dialog.close();}}
 function dockWindow(kind){const win=windows.get(kind);if(!win)return false;hideWindow(win);win.dialog.classList.add('content-docked');win.dialog.show();syncOverlay();return true;}
 function closeWindow(kind){
  const win=windows.get(kind);if(!win)return false;windows.delete(kind);
  if(kind==='radio'){audio.pause();audio.removeAttribute('src');audio.load();}
  if(kind==='youtube'){player?.stopVideo?.();player?.destroy?.();player=null;}
  if(kind===mediaKind){mediaSerial++;playing=false;mediaStatus=null;}
  if(kind==='evolution')clearTimeout(poll);
  hideWindow(win);win.dialog.remove();document.dispatchEvent(new CustomEvent('jarvis:content-closed',{detail:{kind}}));syncOverlay();return true;
 }
 function openWindow(kind){
  const win=windows.get(kind);if(!win?.dialog.isConnected)return false;
  for(const other of windows.values())if(other!==win&&other.dialog.open&&!other.dialog.classList.contains('content-docked'))hideWindow(other);
  const sheet=$('#cockpitSheet');if(sheet?.open)sheet.close();
  if(win.dialog.classList.contains('content-docked')){hideWindow(win);win.dialog.classList.remove('content-docked');}
  if(!win.dialog.open)win.dialog.showModal();syncOverlay();win.onReopen?.();return true;
 }
 window.jarvisCapabilities={execute,openWindow,dockWindow,closeWindow,get state(){return {mediaKind,playing,volume,ducked:duck};}};
})();
