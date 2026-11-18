// Hermes missions UI v2 (17.11.2026). DOM-only rendering: never HTML, remote assets, model instructions or authority.
// Same API and contract as v1 (read, create, cancel, approve). Archiving is local to this browser:
// it hides a mission from the lists, never deletes or changes anything on the server.
(()=>{
 const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 const SOURCE=/^(synthetic|mission|ha|influx):\/\//;
 function sourceLabel(ref){if(ref.startsWith('mission://'))return 'ancienne mission '+ref.slice(10,18);const m=/^(ha|influx):\/\/(?:[^/]+\/)?([a-z_]+\.[a-z0-9_]+)\/(?:history\/)?([0-9]+[hd])/.exec(ref);if(m)return (m[1]==='ha'?'HA ':'Influx ')+m[2]+' · '+m[3];return ref.replace(/^(synthetic|ha|influx):\/\//,'').replace(/@.*$/,'')}
 function inline(parent,text){
  const pattern=/(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\s]+\)|\b(?:synthetic|mission|ha|influx):\/\/[A-Za-z0-9._\/@?=&-]*[A-Za-z0-9_\/])/g;let offset=0;
  for(const match of text.matchAll(pattern)){
   parent.append(document.createTextNode(text.slice(offset,match.index)));const token=match[0];
   const bare=token[0]==='`'?token.slice(1,-1):token;
   if(SOURCE.test(bare)&&(token[0]==='`'||token===bare)){
    const source=node('button',sourceLabel(bare));source.type='button';source.className='hermes-source-link';source.dataset.ref=bare;source.title='Voir la source '+bare;
    source.onclick=()=>document.dispatchEvent(new CustomEvent('jarvis:hermes-show-source',{detail:bare}));parent.append(source);
   }else if(token[0]==='`')parent.append(node('code',bare));
   else if(token.startsWith('**'))parent.append(node('strong',token.slice(2,-2)));
   else {const split=token.indexOf(']('),label=token.slice(1,split),target=token.slice(split+2,-1);let url;
    try{url=new URL(target)}catch{}
    if(url&&['https:','http:'].includes(url.protocol)&&!url.username&&!url.password){const a=node('a',label);a.href=url.href;a.rel='noopener noreferrer';a.target='_blank';parent.append(a)}
    else if(SOURCE.test(target)){const s=node('button',label);s.type='button';s.className='hermes-source-link';s.dataset.ref=target;s.onclick=()=>document.dispatchEvent(new CustomEvent('jarvis:hermes-show-source',{detail:target}));parent.append(s)}
    else parent.append(document.createTextNode(token));
   }
   offset=match.index+token.length;
  }
  parent.append(document.createTextNode(text.slice(offset)));
 }
 function markdown(text){
  const root=node('div');root.className='hermes-markdown';text=String(text);
  // Very large results remain available as literal text; never silently truncate.
  if(text.length>262144){root.append(node('pre',text));return root}
  const lines=text.replace(/\r\n?/g,'\n').split('\n');let list=null;
  for(let i=0;i<lines.length;i++){
   const line=lines[i];if(!line.trim()){list=null;continue}
   if(line.startsWith('```')){list=null;const code=[];while(++i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i]);const pre=node('pre');pre.append(node('code',code.join('\n')));root.append(pre);continue}
   if(i+1<lines.length&&line.includes('|')&&/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i+1])){
    list=null;const table=node('table'),head=node('thead'),body=node('tbody');
    const cells=row=>row.trim().replace(/^\||\|$/g,'').split('|');
    const tr=node('tr');for(const cell of cells(line)){const th=node('th');inline(th,cell.trim());tr.append(th)}head.append(tr);i++;
    while(i+1<lines.length&&lines[i+1].includes('|')&&lines[i+1].trim()){const row=node('tr');for(const cell of cells(lines[++i])){const td=node('td');inline(td,cell.trim());row.append(td)}body.append(row)}
    table.append(head,body);const scroll=node('div');scroll.className='hermes-table-scroll';scroll.append(table);root.append(scroll);continue;
   }
   const heading=/^(#{1,6})\s+(.*)$/.exec(line),bullet=/^\s*(?:[-*+] |\d+[.)] )(.*)$/.exec(line);
   if(bullet){const type=/^\s*\d/.test(line)?'OL':'UL';if(!list||list.tagName!==type){list=node(type.toLowerCase());root.append(list)}const li=node('li');inline(li,bullet[1]);list.append(li);continue}
   list=null;const block=node(heading?'h'+Math.min(heading[1].length+2,6):line.startsWith('> ')?'blockquote':'p');inline(block,heading?heading[2]:line.startsWith('> ')?line.slice(2):line);root.append(block);
  }
  return root;
 }
 const terminal=new Set(['completed','failed','cancelled']);
 const PREFIX=/^Demande explicite utilisateur \((?:données et outils synthétiques seulement|données réelles en lecture seule, aucune commande)\)\s*:\s*/u;
 // The fixed admission prefix says "synthétiques" for every text mission: judge the user's own text only.
 const demo=m=>m.synthetic===true||/synthétique|démonstration/iu.test(String(m.objective||m.definition?.objective||'').replace(PREFIX,''));
 function objectiveText(m){return String(m.objective||m.definition?.objective||'').replace(PREFIX,'')}
 function title(m){const value=objectiveText(m)||'Mission';return value.length>110?value.slice(0,107)+'…':value}
 function date(value){if(value==null||value==='')return null;const d=new Date(typeof value==='number'?(value<1e12?value*1000:value):value);return Number.isFinite(d.getTime())?d:null}
 function duration(m){const created=date(m.created),updated=date(m.updated);if(!terminal.has(m.state)||!created||!updated||updated<created)return null;const s=Math.round((updated-created)/1000);return s<60?s+' s':s<3600?Math.floor(s/60)+' min '+s%60+' s':Math.floor(s/3600)+' h '+Math.floor(s%3600/60)+' min'}
 function relative(d){const s=Math.round((Date.now()-d.getTime())/1000);if(s<45)return 'à l’instant';if(s<3600)return 'il y a '+Math.round(s/60)+' min';if(s<86400)return 'il y a '+Math.round(s/3600)+' h';if(s<7*86400)return 'il y a '+Math.round(s/86400)+' j';return d.toLocaleDateString('fr-CH',{dateStyle:'medium'})}
 function timing(m){const created=date(m.created);let text=created?created.toLocaleString('fr-CH',{dateStyle:'medium',timeStyle:'short'}):'Date non fournie';const d=duration(m);if(d)text+=' · Durée totale : '+d;return text}
 function visible(items,{history=false,hideDemos=false}={}){return items.filter(m=>(!hideDemos||!demo(m))&&(history||!['failed','cancelled'].includes(m.state))).sort((a,b)=>Number(terminal.has(a.state))-Number(terminal.has(b.state))||((date(b.created)?.getTime()||0)-(date(a.created)?.getTime()||0)))}
 function availability(worker){if(worker.reason||worker.state==='unavailable')return 'Exécution en pause · historique disponible.';if(!worker.fresh)return 'Hermes non disponible ou présence non confirmée · missions conservées.';return ({ready:'Prêt à travailler.',gpu_busy:'Carte graphique occupée · missions en attente.',uncertain:'État à vérifier · aucune relance automatique.',offline:'Hermes indisponible · missions conservées.'})[worker.state]||'Disponibilité à vérifier · historique conservé.'}
 function failure(error){return ({401:'Connecte-toi pour consulter tes missions.',403:'Ton compte ne permet pas cet accès.',404:'Les missions ne sont pas activées.',409:'Vérifie l’historique avant toute nouvelle demande.',503:'Les missions sont momentanément indisponibles. Jarvis reste utilisable.'})[error.status]||'Impossible d’actualiser les missions. Aucun nouvel envoi automatique.'}
 globalThis.JarvisMissionView=Object.freeze({markdown,demo,title,timing,visible,availability,failure,objectiveText,relative,duration,date,sourceLabel});
})();

// Canonical metadata formatter (unchanged contract): SQLite projection only, never model text.
(() => {
 function sections(modelOutput,projection){
  if(typeof modelOutput!=='string')throw Error('Model text required');
  const result={modelText:modelOutput,modelLabel:'Réponse du modèle — non vérifiée',metadataText:null};
  if(projection===undefined||projection===null)return result;
  if(projection.schema!=='canonical_metadata.v1'||projection.origin!=='sqlite'||!Array.isArray(projection.items)||projection.items.length>200)throw Error('Canonical projection required');
  const lines=['Métadonnées issues de SQLite — horodatages UTC'];
  for(const row of projection.items){
   for(const key of ['memory_id','revision_id','source_ref','stored_validation_status','revision_status','observed_utc'])if(typeof row[key]!=='string')throw Error('Canonical field required');
   lines.push('Source : '+row.source_ref,'Mémoire : '+row.memory_id+' · Révision : '+row.revision_id,
    'Observation UTC : '+row.observed_utc,'État de révision : '+row.revision_status+' · Validation enregistrée : '+row.stored_validation_status,
    'Début de validité UTC : '+(row.valid_from_utc??'non précisé'),'Fin de validité UTC : '+(row.valid_to_utc??'non précisée'),'');
  }
  result.metadataText=lines.join('\n');return result;
 }
 globalThis.JarvisHermesCanonical=Object.freeze({sections});
})();

// Independent human login. No Hermes dependency, storage token, fetch monkeypatch or audio.
(()=>{
 let identity=null,readyPromise,pending=[];
 const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text)e.textContent=text;parent?.append(e);return e};
 const button=make('button','Connexion missions',document.body);button.id='hermesAccountButton';button.type='button';button.hidden=true;
 const dialog=make('dialog',null,document.body);dialog.id='hermesAccountDialog';dialog.className='hermes-account';
 const head=make('div',null,dialog);head.className='hermes-account-head';make('h2','Compte missions',head);
 const close=make('button','×',head);close.type='button';close.className='hermes-icon';close.setAttribute('aria-label','Fermer');close.onclick=()=>dialog.close();
 const form=make('form',null,dialog);const label=make('label','Code personnel',form);label.htmlFor='hermesAccountCode';
 const input=make('input',null,form);input.id='hermesAccountCode';input.type='password';input.autocomplete='one-time-code';input.setAttribute('aria-label','Code personnel');input.required=true;
 const submit=make('button','Se connecter',form);submit.type='submit';submit.className='hermes-primary';
 const status=make('p','',dialog);status.setAttribute('role','status');status.className='hermes-account-status';
 const logout=make('button','Déconnexion',dialog);logout.type='button';logout.hidden=true;logout.className='hermes-secondary';
 function publish(id){identity=id;form.hidden=!!id;logout.hidden=!id;status.textContent=id?'Connecté.':'';button.textContent=id?'Compte missions':'Connexion missions';button.hidden=false;document.dispatchEvent(new CustomEvent(id?'jarvis:hermes-session-ready':'jarvis:hermes-session-ended'));}
 async function request(path,options={}){
  const response=await fetch('/api/jarvis/hermes-panel/'+path,{...options,credentials:'same-origin'});
  let body;try{body=await response.json()}catch{throw Object.assign(Error('Réponse indisponible'),{status:response.status})}
  if(response.status===401&&identity)publish(null);
  if(!response.ok)throw Object.assign(Error(response.status===401?'Connexion requise':body.error||'Requête refusée'),{status:response.status});return body;
 }
 async function load(){try{const r=await fetch('/api/jarvis/hermes-panel/session',{credentials:'same-origin'});if(r.status===404)return null;if(r.ok){publish(await r.json());return identity}publish(null);return null}catch{publish(null);return null}}
 const open=async()=>{await readyPromise;if(identity){dialog.showModal();return identity}dialog.showModal();input.focus();return new Promise(resolve=>pending.push(resolve))};
 button.onclick=()=>{void open()};
 dialog.addEventListener('close',()=>{input.value='';for(const resolve of pending.splice(0))resolve(identity)});
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;status.textContent='Connexion…';try{await request('session',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({token:input.value})});input.value='';await load();dialog.close()}catch(error){status.textContent=error.message;input.value=''}finally{submit.disabled=false}};
 logout.onclick=async()=>{try{await request('session',{method:'DELETE'});publish(null);dialog.close();location.reload()}catch(error){status.textContent=error.message}};
 globalThis.JarvisHermesAuth=Object.freeze({request,open,ready:()=>readyPromise,identity:()=>identity});
 readyPromise=load();
})();

// Missions panel v2. No microphone/audio changes.
(() => {
 const V=globalThis.JarvisMissionView;
 const make=(tag,text,parent,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;if(parent)parent.append(e);return e};
 const btn=(text,parent,cls,label)=>{const b=make('button',text,parent,cls);b.type='button';if(label){b.setAttribute('aria-label',label);b.title=label}return b};
 const states={queued:'En attente',running:'En cours',planning:'Planification',testing:'Évaluation',paused:'Suspendue',awaiting_approval:'Approbation requise',completed:'Terminée',failed:'Échec',cancelled:'Annulée',unknown:'À vérifier'};
 const terminal=new Set(['completed','failed','cancelled']);
 const stateOf=m=>m.dispatch_state==='unknown'?'unknown':m.state;

 // ---- shell ----
 const button=btn('Connexion missions',null,'hermes-launch');button.id='hermesMissionsButton';button.hidden=true;
 const badge=make('span','',button,'hermes-launch-badge');badge.hidden=true;
 (document.querySelector('.header-actions')||document.body).append(button);
 const dialog=make('dialog',null,document.body,'hermes-app');dialog.id='hermesMissionsDialog';dialog.setAttribute('aria-labelledby','hermesAppTitle');
 const header=make('header',null,dialog,'hermes-head');
 const brand=make('div',null,header,'hermes-brand');const h=make('h2','Missions Hermes',brand);h.id='hermesAppTitle';
 const availability=make('p','Disponibilité non mesurée',brand,'hermes-availability');availability.id='hermesWorkerAvailability';availability.dataset.level='unknown';
 const headActions=make('div',null,header,'hermes-head-actions');
 const refresh=btn('↻',headActions,'hermes-icon','Actualiser');
 const account=document.querySelector('#hermesAccountButton');if(account){account.classList.add('hermes-secondary');headActions.append(account)}
 const close=btn('×',headActions,'hermes-icon','Fermer');close.onclick=()=>dialog.close();
 const status=make('p','',dialog,'hermes-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const content=make('div',null,dialog,'hermes-body');content.hidden=true;content.dataset.view='list';

 // ---- left column: composer + list ----
 const side=make('section',null,content,'hermes-side');side.setAttribute('aria-label','Liste des missions');
 const composer=make('div',null,side,'hermes-composer');
 const objective=make('textarea','',composer);objective.id='hermesExplicitObjective';objective.maxLength=2000;objective.rows=3;objective.placeholder='Décrire une analyse, ex. : dois-je recalibrer le dosage du VSV d’après l’historique ?';objective.setAttribute('aria-label','Décrire une mission');objective.hidden=true;
 const composerFoot=make('div',null,composer,'hermes-composer-foot');
 const consentLabel=make('p','Lecture seule : Hermes consulte Home Assistant et InfluxDB, il ne commande jamais rien.',composerFoot,'hermes-consent');consentLabel.id='hermesReadOnlyNotice';consentLabel.hidden=true;
 const counter=make('span','',composerFoot,'hermes-counter');
 const submit=btn('Confier à Hermes',composerFoot,'hermes-primary');submit.hidden=true;
 const duplicate=make('p','',composer,'hermes-duplicate');duplicate.hidden=true;
 const create=btn('',document.createElement('div'),'hermes-link');create.hidden=true;   // DoseLab example removed 17.11 (laboratory deleted)
 const notice=make('p','',composer,'hermes-notice');notice.id='hermesMissionNotice';notice.setAttribute('role','status');

 const toolbar=make('div',null,side,'hermes-toolbar');
 const search=make('input',null,toolbar,'hermes-search');search.type='search';search.placeholder='Rechercher…';search.setAttribute('aria-label','Rechercher une mission');
 const tabs=make('div',null,toolbar,'hermes-tabs');tabs.setAttribute('role','tablist');
 const FILTERS=[['active','En cours'],['done','Terminées'],['archived','Archivées'],['all','Toutes']];const tabButtons={};
 for(const [k,label] of FILTERS){const t=btn(label,tabs,'hermes-tab');t.setAttribute('role','tab');t.dataset.filter=k;const c=make('span','',t,'hermes-count');tabButtons[k]={t,c};t.onclick=()=>{filter=k;renderList()}}
 const listTools=make('div',null,side,'hermes-list-tools');
 const demoLabel=make('label',null,listTools,'hermes-filter');const hideDemos=make('input',null,demoLabel);hideDemos.type='checkbox';demoLabel.append(document.createTextNode('Masquer les démonstrations'));
 const archiveAll=btn('Archiver les terminées',listTools,'hermes-link');archiveAll.hidden=true;
 const list=make('div',null,side,'hermes-list');list.id='hermesMissionList';list.setAttribute('role','list');

 // ---- right column: detail ----
 const main=make('section',null,content,'hermes-main');main.setAttribute('aria-label','Détail de la mission');
 const back=btn('← Missions',main,'hermes-back');back.onclick=()=>{content.dataset.view='list'};
 const empty=make('div',null,main,'hermes-empty');make('p','Sélectionne une mission pour voir sa réponse et ses sources.',empty);
 const detailBox=make('article',null,main,'hermes-detail');detailBox.hidden=true;
 const dHead=make('div',null,detailBox,'hermes-detail-head');
 const dBadge=make('span','',dHead,'hermes-badge');const dTitle=make('h3','',dHead);const dMeta=make('p','',dHead,'hermes-meta');
 const dActions=make('div',null,detailBox,'hermes-actions');
 const warning=make('p','',detailBox,'hermes-quality');warning.id='hermesResultWarning';warning.hidden=true;
 const detailNode=make('div','',detailBox,'hermes-answer');detailNode.id='hermesMissionResult';
 const sourcesBox=make('section',null,detailBox,'hermes-sources');sourcesBox.hidden=true;make('h4','Sources consultées',sourcesBox);
 const sourceList=make('div',null,sourcesBox,'hermes-source-list');
 const approvals=make('div',null,detailBox,'hermes-approvals');
 const sources=make('details',null,detailBox,'hermes-tech');sources.id='hermesSourcesDetails';make('summary','Détails techniques',sources);
 const techLabel=(t)=>make('h5',t,sources);
 techLabel('Métadonnées SQLite');const canonical=make('pre','',sources);canonical.id='hermesMissionCanonical';
 techLabel('Demande transmise');const objectiveProof=make('pre','',sources);objectiveProof.id='hermesMissionObjective';
 techLabel('Réponse brute du modèle');const modelProof=make('pre','',sources);modelProof.id='hermesOriginalResult';
 techLabel('Journal des événements');const eventsProof=make('pre','',sources);eventsProof.id='hermesMissionEvents';

 // ---- state ----
 let identity=null,selected=null,timer=null,key=null,featureActive=false,admissionsEnabled=false,textSubmissionEnabled=false,inspection=0,lastAvailability=null;
 let items=[],filter='active',listSignature='',detailSignature='',textAttempt=null,textBusy=false;const seen=new Map();
 function space(){return identity?.spaces?.[0]}
 async function request(path,options={}){return globalThis.JarvisHermesAuth.request(path,options)}
 const endpoint=path=>'hermes/'+path+'?space='+encodeURIComponent(space());

 // Local archive: ids only, per account and space, in this browser. Never sent to the server.
 const archiveKey=()=>'hermes-archive:v1:'+(identity?.subject||'-')+':'+(space()||'-');
 function archived(){try{const v=JSON.parse(localStorage.getItem(archiveKey())||'[]');return new Set(Array.isArray(v)?v.filter(x=>typeof x==='string'&&x.length<=128):[])}catch{return new Set()}}
 function setArchived(ids,on){const set=archived();for(const id of ids)on?set.add(id):set.delete(id);try{localStorage.setItem(archiveKey(),JSON.stringify([...set].slice(-2000)))}catch{status.textContent='Archivage impossible dans ce navigateur (stockage indisponible).'}}

 function textReady(){
  consentLabel.hidden=objective.hidden;composerFoot.hidden=objective.hidden;objective.disabled=textBusy||textAttempt!==null;
  counter.textContent=objective.value.length?objective.value.length+' / 2000':'';
  submit.disabled=!textSubmissionEnabled||!admissionsEnabled||!identity?.roles.includes('missions.create')||textBusy||!(textAttempt?.objective||objective.value).trim()||objective.value.length>2000;
  const text=objective.value.trim();const same=text&&items.find(m=>V.objectiveText(m).trim()===text);
  duplicate.replaceChildren();duplicate.hidden=!same;
  if(same){duplicate.append(document.createTextNode('Une mission identique existe déjà ('+(states[stateOf(same)]||same.state).toLowerCase()+'). Modifie le texte pour en créer une nouvelle, ou '));const o=btn('ouvre-la',duplicate,'hermes-link');o.onclick=()=>select(same.id);duplicate.append(document.createTextNode('.'))}
 }
 objective.addEventListener('input',textReady);
 objective.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)&&!submit.disabled)submit.click()});

 submit.onclick=async()=>{
  if(!textSubmissionEnabled||textBusy||objective.hidden||!admissionsEnabled||!identity?.roles.includes('missions.create'))return;
  if(!objective.value.trim()||objective.value.length>2000)return;
  textBusy=true;textReady();notice.textContent='Envoi…';
  try{
   if(!textAttempt){
    const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(objective.value));
    const hash=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
    const ticket='hermes-request-ticket:'+identity.subject+':'+space()+':'+hash;
    let saved=null;try{saved=sessionStorage.getItem(ticket)}catch{}
    const k=/^[A-Za-z0-9_-]{1,120}$/.test(saved||'')?saved:crypto.randomUUID();
    textAttempt={key:k,objective:objective.value,ticket};try{sessionStorage.setItem(ticket,k)}catch{}
   }
   const attempt=textAttempt;const known=new Set(items.map(m=>m.id));
   const result=await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':attempt.key},body:JSON.stringify({objective:attempt.objective})});
   if(typeof result.mission_id!=='string')throw Error('Enregistrement non confirmé');
   try{sessionStorage.removeItem(attempt.ticket)}catch{}
   notice.textContent=known.has(result.mission_id)?'Cette demande était déjà enregistrée : mission existante ouverte.':'Mission enregistrée. En attente de disponibilité.';
   textAttempt=null;objective.value='';submit.textContent='Confier à Hermes';filter='active';selected=result.mission_id;await refreshList();await select(result.mission_id);
  }catch(e){submit.textContent='Réessayer la même demande';notice.textContent=e.message+'. Vérifie l’historique : un nouvel envoi conservera exactement la même demande et sa clé.'}
  finally{textBusy=false;textReady()}
 };

 // ---- list ----
 function matches(m){const q=search.value.trim().toLowerCase();return !q||V.objectiveText(m).toLowerCase().includes(q)||m.id.startsWith(q)}
 function bucket(m,arch){if(arch.has(m.id))return 'archived';return terminal.has(m.state)?'done':'active'}
 function renderList(){
  const arch=archived();const pool=items.filter(m=>!hideDemos.checked||!V.demo(m)).filter(matches);
  const count={active:0,done:0,archived:0,all:pool.length};for(const m of pool)count[bucket(m,arch)]++;
  for(const [k,{t,c}] of Object.entries(tabButtons)){c.textContent=count[k]?String(count[k]):'';t.setAttribute('aria-selected',String(k===filter));t.classList.toggle('is-active',k===filter)}
  const shown=pool.filter(m=>filter==='all'||bucket(m,arch)===filter).sort((a,b)=>Number(terminal.has(a.state))-Number(terminal.has(b.state))||((V.date(b.created)?.getTime()||0)-(V.date(a.created)?.getTime()||0)));
  archiveAll.hidden=filter!=='done'||!count.done;
  list.replaceChildren();
  for(const m of shown){
   const row=make('div',null,list,'hermes-row');row.setAttribute('role','listitem');row.dataset.state=stateOf(m);if(m.id===selected)row.classList.add('is-selected');if(arch.has(m.id))row.classList.add('is-archived');
   const open=btn(null,row,'hermes-card');open.onclick=()=>void select(m.id);
   const top=make('span',null,open,'hermes-card-top');make('span',states[stateOf(m)]||'À vérifier',top,'hermes-badge').dataset.state=stateOf(m);
   const created=V.date(m.created);const when=make('small',created?V.relative(created):'',top,'hermes-when');if(created)when.title=created.toLocaleString('fr-CH');
   make('strong',V.title(m),open,'hermes-card-title');
   const meta=[];const d=V.duration(m);if(d)meta.push(d);if(V.demo(m))meta.push('démonstration');if(arch.has(m.id))meta.push('archivée');
   if(meta.length)make('small',meta.join(' · '),open,'hermes-card-meta');
   if(terminal.has(m.state)){const a=btn(arch.has(m.id)?'↩':'⌫',row,'hermes-icon hermes-row-action',(arch.has(m.id)?'Restaurer dans la liste : ':'Archiver : ')+V.title(m));a.onclick=()=>{setArchived([m.id],!arch.has(m.id));renderList();if(m.id===selected)renderActions()}}
  }
  if(!shown.length)make('p',items.length?({active:'Aucune mission en cours.',done:'Aucune mission terminée.',archived:'Aucune mission archivée. Archiver masque une mission de la liste sans rien effacer.',all:'Aucune mission ne correspond.'})[filter]:'Aucune mission pour l’instant. Décris une demande ci-dessus.',list,'hermes-list-empty');
  const active=items.filter(m=>!terminal.has(m.state)).length;badge.textContent=String(active);badge.hidden=!active;
 }
 archiveAll.onclick=()=>{const arch=archived();const ids=items.filter(m=>terminal.has(m.state)&&!arch.has(m.id)&&(!hideDemos.checked||!V.demo(m))&&matches(m)).map(m=>m.id);if(!ids.length||!confirm('Archiver '+ids.length+' mission(s) terminée(s) ? Elles restent consultables dans « Archivées », rien n’est effacé.'))return;setArchived(ids,true);renderList()};
 search.addEventListener('input',renderList);hideDemos.onchange=renderList;

 // ---- detail ----
 function current(){return items.find(m=>m.id===selected)}
 function renderActions(){
  const m=current();dActions.replaceChildren();if(!m)return;
  if(!terminal.has(m.state)){const c=btn('Annuler la mission',dActions,'hermes-danger');c.onclick=async()=>{if(!confirm('Annuler cette mission ? Elle ne sera pas relancée.'))return;try{await request(endpoint('missions/'+m.id+'/cancel'),{method:'POST',headers:{'content-type':'application/json'},body:'{}'});await refreshList()}catch(e){status.textContent=e.message}}}
  else{const arch=archived().has(m.id);const a=btn(arch?'Restaurer dans la liste':'Archiver',dActions,'hermes-secondary');a.onclick=()=>{setArchived([m.id],!arch);renderList();renderActions()}}
  if(modelProof.textContent){const c=btn('Copier la réponse',dActions,'hermes-secondary');c.onclick=async()=>{try{await navigator.clipboard.writeText(modelProof.textContent);c.textContent='Copiée ✓'}catch{c.textContent='Copie impossible'}}}
 }
 function quality(events){
  const q=(events||[]).find(e=>e.kind==='report_quality');if(!q){warning.hidden=true;return}
  let data;try{data=JSON.parse(q.data)}catch{warning.hidden=true;return}
  const unread=Number.isInteger(data.unverified_mission_sources_read)?data.unverified_mission_sources_read:0;
  const measured=Number.isInteger(data.measurements_read)?data.measurements_read:0;
   const level=data.model_cites_source_ref===true?(unread?'info':'ok'):'warn';
  warning.textContent=(data.model_cites_source_ref===true?(data.cites_measurement===true?'Réponse appuyée sur '+(measured>1?measured+' lectures réelles':'une lecture réelle')+' (Home Assistant / InfluxDB) faites pendant la mission ; raisonnement non vérifié indépendamment.':'Références retrouvées dans la mémoire ; réponse non vérifiée indépendamment.'):data.cites_unverified_source===true?'La réponse cite un compte rendu de mission non vérifié. Réponse à vérifier.':'Les sources ne sont pas correctement citées. Réponse à vérifier.')+(unread===1?' 1 compte rendu de mission non vérifié a été consulté.':unread>1?' '+unread+' comptes rendus de mission non vérifiés ont été consultés.':'');
  warning.dataset.level=level;warning.hidden=false;
 }
 function renderSources(projection,output){
  sourceList.replaceChildren();sourcesBox.hidden=true;
  if(!projection||!Array.isArray(projection.items))return;
  const byRef=new Map();for(const row of projection.items){if(typeof row.source_ref!=='string')continue;const r=byRef.get(row.source_ref)||[];r.push(row);byRef.set(row.source_ref,r)}
  for(const [ref,rows] of byRef){
   const card=make('div',null,sourceList,'hermes-source');card.dataset.sourceRef=ref;
   const cited=output.includes(ref);card.dataset.cited=String(cited);
   const top=make('div',null,card,'hermes-source-top');make('code',ref,top);make('span',cited?'citée':'consultée',top,'hermes-tag');
   for(const row of rows){const line=make('small',null,card);line.textContent=[row.revision_status||row.stored_validation_status,row.is_current_revision?'révision actuelle':'révision antérieure',row.observed_utc?'observée '+row.observed_utc.slice(0,10):null].filter(Boolean).join(' · ')}
  }
  sourcesBox.hidden=!byRef.size;
 }
 document.addEventListener('jarvis:hermes-show-source',e=>{
  const ref=String(e.detail);const card=[...sourceList.children].find(c=>c.dataset.sourceRef===ref);
  if(card){card.scrollIntoView({behavior:'smooth',block:'center'});card.classList.remove('is-flash');void card.offsetWidth;card.classList.add('is-flash')}
  else{sources.open=true;sources.scrollIntoView({behavior:'smooth'})}
 });
 async function select(id){selected=id;detailSignature='';content.dataset.view='detail';renderList();await inspect(id).catch(e=>status.textContent=V.failure(e))}
 async function inspect(id){
  const run=++inspection;const m=await request(endpoint('missions/'+id));
  if(run!==inspection||selected!==id)return;
  const result=await request(endpoint('missions/'+id+'/results'));
  if(run!==inspection||selected!==id)return;
  const sig=JSON.stringify([m.state,m.dispatch_state,m.updated,(result.events||[]).length,!!result.canonical,(m.approvals||[]).map(a=>a.state)]);
  if(sig===detailSignature)return;detailSignature=sig;
  const st=m.dispatch_state==='unknown'?'unknown':m.state;
  empty.hidden=true;detailBox.hidden=false;dBadge.textContent=states[st]||st;dBadge.dataset.state=st;
  dTitle.textContent=V.title(m);dTitle.title=V.objectiveText(m);dMeta.textContent=V.timing(m)+(V.demo(m)?' · démonstration, données fictives':'');
  notice.textContent=({queued:lastAvailability?.reason==='windows_offline'?'Mission enregistrée. Hermes est momentanément indisponible.':'Mission enregistrée. En attente de disponibilité.',running:'Hermes a pris en charge la mission.',completed:'Mission terminée. Résultat disponible.',failed:'La mission a échoué. Consulte les détails.',cancelled:'Mission annulée.',paused:'Cette mission nécessite une vérification. Elle ne sera pas relancée automatiquement.'})[m.state]||'État à vérifier.';
  objectiveProof.textContent=m.definition?.objective||'';eventsProof.textContent=JSON.stringify(result.events||[],null,2);
  let output='';const extra=[];
  for(const e of result.events||[]){if(['completed','failed','cancelled','deferred','reconciliation_required'].includes(e.kind)){
   let data;try{data=JSON.parse(e.data)}catch{continue}
   if(data.output)output=data.output;else if(data.reason)extra.push(data.reason);else if(e.kind==='reconciliation_required')extra.push('Reprise à vérifier, aucun rejeu automatique.');
  }}
  const fragments=[],manifests=[];
  for(const e of result.events||[]){if(['result_part','result_complete','output_limit'].includes(e.kind)){const row=JSON.parse(e.data);if(e.kind==='result_part')fragments.push(row);else if(e.kind==='result_complete')manifests.push(row);else extra.push('Résultat limité explicitement : '+row.reason)}}
  if(manifests.length===1){const manifest=manifests[0];fragments.sort((a,b)=>a.index-b.index);if(fragments.length!==manifest.parts||fragments.some((r,i)=>r.index!==i))throw Error('Résultat complet incomplet');const full=fragments.map(r=>r.output).join('');const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(full)))).map(v=>v.toString(16).padStart(2,'0')).join('');if(run!==inspection||selected!==id)return;if(hash!==manifest.sha256)throw Error('Empreinte du résultat invalide');output=full}
  modelProof.textContent=output;
  detailNode.replaceChildren();
  if(output)detailNode.append(V.markdown(output));
  else make('p',terminal.has(m.state)?(extra.length?'':'Aucune réponse enregistrée.'):'La réponse apparaîtra ici quand Hermes aura terminé.',detailNode,'hermes-placeholder');
  for(const x of extra)make('p',x,detailNode,'hermes-placeholder');
  quality(result.events);
  canonical.textContent='';let projection=null;
  if(result.canonicalUnavailable)canonical.textContent='Métadonnées canoniques indisponibles. Réponse du modèle non vérifiée.';
  if(result.canonical){
   const p=result.canonical;
   if(p.mission_id===id&&p.selection_origin==='authenticated_host_tool_receipts'&&Array.isArray(p.receipt_ids)&&p.receipt_ids.length&&globalThis.JarvisHermesCanonical){canonical.textContent=globalThis.JarvisHermesCanonical.sections('',p).metadataText||'';projection=p}
   else canonical.textContent='Provenance non liée : métadonnées non affichées.';
  }
  renderSources(projection,output);
  if(result.canonicalUnavailable&&terminal.has(m.state)){sourcesBox.hidden=false;sourceList.replaceChildren(make('p','Aucune source consultée n’a été enregistrée pour cette mission.',null,'hermes-placeholder'))}
  approvals.replaceChildren();
  for(const a of m.approvals||[]){if(a.state!=='pending')continue;
   let action;try{action=JSON.parse(a.action)}catch{action={description:'Demande à vérifier'}}
   make('p',action.description||'Demande à vérifier',approvals);
   if(!identity.roles.includes('missions.approve')){make('p','Un compte approbateur distinct est requis.',approvals);continue}
   for(const [choice,label] of [['once','Autoriser cette action une fois'],['deny','Refuser']]){
    const b=btn(label,approvals,choice==='once'?'hermes-primary':'hermes-secondary');b.onclick=async()=>{if(!confirm('Confirmer cette décision pour cette action précise ?'))return;
     try{await request(endpoint('missions/'+id+'/approvals'),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({approval_id:a.id,fingerprint:a.fingerprint,choice})});detailSignature='';await inspect(id)}catch(e){status.textContent=e.message}
    };
   }
  }
  renderActions();
 }
 function clearDetail(){++inspection;selected=null;detailSignature='';detailBox.hidden=true;empty.hidden=false;detailNode.replaceChildren();modelProof.textContent='';canonical.textContent='';objectiveProof.textContent='';eventsProof.textContent='';approvals.replaceChildren();sourceList.replaceChildren();warning.hidden=true;content.dataset.view='list'}

 // ---- refresh ----
 function availabilityText(worker){
  if(worker.active?.reason==='uncertain')return ['warn','Une mission nécessite une vérification.'];
  if(worker.fresh&&worker.state==='ready')return ['ok','Hermes est disponible.'];
  return [worker.reason==='windows_offline'?'off':'unknown',({windows_offline:'Hermes est momentanément indisponible. Les demandes restent enregistrées.',miner_active:'Carte graphique occupée. Les demandes restent en attente.',gpu_busy:'Carte graphique occupée. Les demandes restent en attente.',insufficient_vram:'Ressources momentanément insuffisantes. Les demandes restent en attente.'})[worker.reason]||'Disponibilité non confirmée. Les demandes restent enregistrées.'];
 }
 async function refreshList(){
  if(!identity||!featureActive||document.hidden)return;
  const sessionIdentity=identity;
  try{
   const config=await request(endpoint('config'));if(identity!==sessionIdentity||!featureActive)return;admissionsEnabled=config.enabled===true;
   create.hidden=!admissionsEnabled;create.disabled=!admissionsEnabled||!identity.roles.includes('missions.create');
   textSubmissionEnabled=config.textEnabled===true;objective.hidden=submit.hidden=!(config.readEnabled===true&&identity.roles.includes('missions.read'));
   globalThis.JarvisHermesVoiceEnabled=config.voiceEnabled===true;
   const data=await request(endpoint('missions'));if(identity!==sessionIdentity||!featureActive)return;
   items=Array.isArray(data.items)?data.items:[];
   for(const m of items){if(seen.has(m.id)&&['completed','failed','awaiting_approval'].includes(m.state)&&seen.get(m.id)!==m.state&&!dialog.open)button.dataset.attention='1';seen.set(m.id,m.state)}
   const sig=JSON.stringify(items.map(m=>[m.id,m.state,m.dispatch_state,m.updated]));if(sig!==listSignature){listSignature=sig;renderList()}
   textReady();
   status.textContent=admissionsEnabled?'':'Les nouvelles missions sont temporairement suspendues. Historique et annulation disponibles.';
   try{const worker=await request(endpoint('availability'));if(identity!==sessionIdentity||!featureActive)return;lastAvailability=worker;const [level,text]=availabilityText(worker);availability.textContent=text;availability.dataset.level=level}catch{availability.textContent='Disponibilité inconnue. Historique conservé.';availability.dataset.level='unknown'}
   if(selected&&dialog.open)await inspect(selected);
  }catch(e){if([401,403].includes(e.status)){items=[];listSignature='';list.replaceChildren();clearDetail()}create.disabled=true;objective.hidden=submit.hidden=true;textReady();globalThis.JarvisHermesVoiceEnabled=false;status.textContent=V.failure(e)}
 }
 async function bootstrap(){
  try{identity=await request('session')}catch(e){identity=null;button.firstChild.textContent='Connexion missions';button.hidden=e.status===404;return}
  try{const config=await request(endpoint('config'));admissionsEnabled=config.enabled===true;globalThis.JarvisHermesVoiceEnabled=config.voiceEnabled===true;textSubmissionEnabled=config.textEnabled===true;objective.hidden=submit.hidden=!(config.readEnabled===true&&identity.roles.includes('missions.read'));textReady();featureActive=admissionsEnabled||config.readEnabled===true;if(!featureActive){content.hidden=true;button.hidden=true;status.textContent='Connecté. Missions Hermes désactivées.';return}}catch{button.hidden=true;return}
  content.hidden=false;button.hidden=false;button.firstChild.textContent='Missions Hermes';
  create.hidden=!admissionsEnabled;create.disabled=!admissionsEnabled||!identity.roles.includes('missions.create');clearInterval(timer);timer=setInterval(()=>void refreshList(),5000);
 }
 button.onclick=async()=>{if(!identity){const id=await globalThis.JarvisHermesAuth.open();if(!id)return;await bootstrap()}delete button.dataset.attention;dialog.showModal();await refreshList();if(!selected){const first=items.find(m=>!terminal.has(m.state));if(first&&matchMedia('(min-width: 821px)').matches)void select(first.id)}};
 dialog.addEventListener('close',()=>{++inspection;detailSignature=''});
 create.onclick=async()=>{if(!admissionsEnabled)return;create.disabled=true;key??=crypto.randomUUID();try{
  const result=await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':key},body:JSON.stringify({template:'doselab-current'})});
  key=null;filter='active';await refreshList();await select(result.mission_id);
 }catch(e){status.textContent=e.message+' La même clé sera conservée en cas de nouvel envoi.'}finally{create.disabled=!admissionsEnabled||!identity?.roles.includes('missions.create')}};
 refresh.onclick=()=>{listSignature='';detailSignature='';void refreshList()};
 document.addEventListener('jarvis:hermes-spacechange',()=>{key=null;items=[];listSignature='';list.replaceChildren();clearDetail();void refreshList()});
 document.addEventListener('jarvis:hermes-session-ready',()=>void bootstrap());
 document.addEventListener('jarvis:hermes-refresh',()=>{if(identity)void refreshList().catch(()=>{})});
 document.addEventListener('jarvis:hermes-session-ended',()=>{identity=null;featureActive=false;globalThis.JarvisHermesVoiceEnabled=false;objective.value='';textAttempt=null;objective.hidden=submit.hidden=true;textReady();clearInterval(timer);content.hidden=true;items=[];listSignature='';list.replaceChildren();clearDetail();button.firstChild.textContent='Connexion missions';badge.hidden=true});
 globalThis.JarvisHermesAuth?.ready().then(()=>bootstrap()).catch(()=>{});
})();

// Used by the existing jarvisAsk path, never touches microphone/audio transport.
globalThis.JarvisHermesHybrid=Object.freeze({request(data){
 if(!/herm[eèéê]s/iu.test(data.question.normalize('NFKC')))return undefined;
 const denied=answer=>({answer,speech:answer,sources:[],sourceIds:[],action:null});
 if(globalThis.JarvisHermesVoiceEnabled!==true)return Promise.resolve(denied('La délégation Hermes n’est pas activée. Utilise le panneau des missions.'));
 const identity=globalThis.JarvisHermesAuth.identity();
 if(!identity?.roles?.includes('missions.create'))return Promise.resolve(denied('Connexion et autorisation de mission requises.'));
 return globalThis.JarvisHermesAuth.request('hybrid/ask?space='+encodeURIComponent(identity.spaces[0]),{method:'POST',headers:{'content-type':'application/json'},signal:data.signal,body:JSON.stringify({question:data.question,archive:data.archive})});
}});

// 18.11 route 3: Jarvis hands an analysis of the measurement history to Hermes. The browser creates the
// mission through this panel's authenticated session (same POST as the text form, read-only grant set by
// the private service), follows it, and gives back the final text. Never a command, never a replay:
// one idempotency key per handed-off question; a lost answer is looked up again, not resubmitted.
globalThis.JarvisHermesDelegate=Object.freeze({
 async submit(question,{key}={}){
  const auth=globalThis.JarvisHermesAuth,identity=auth?.identity?.();
  if(!identity?.roles?.includes('missions.create'))throw Error('connecte-toi au panneau Missions (« Connexion missions ») pour que Hermes puisse prendre la demande');
  if(typeof question!=='string'||!question.trim()||question.length>2000)throw Error('demande vide ou trop longue');
  const k=/^[A-Za-z0-9_-]{1,120}$/.test(key||'')?key:'jarvis-route-'+crypto.randomUUID();
  const space=identity.spaces[0];
  const r=await auth.request('hermes/missions?space='+encodeURIComponent(space),{method:'POST',headers:{'content-type':'application/json','idempotency-key':k},body:JSON.stringify({objective:question})});
  if(typeof r.mission_id!=='string')throw Error('enregistrement non confirmé');
  document.dispatchEvent(new Event('jarvis:hermes-refresh'));
  return {id:r.mission_id,space,key:k};
 },
 async wait(id,space,{progress=()=>{},signal,every=10000,limit=45*60000}={}){
  const auth=globalThis.JarvisHermesAuth,end=Date.now()+limit,q='?space='+encodeURIComponent(space);
  const terminal=new Set(['completed','failed','cancelled']);let m,lastState='';
  for(;;){
   signal?.throwIfAborted();
   try{m=await auth.request('hermes/missions/'+encodeURIComponent(id)+q);if(m.state!==lastState){lastState=m.state;progress(m.dispatch_state==='unknown'?'unknown':m.state)}}catch(e){if(e.status===401||e.status===403)throw e}
   if(m&&(terminal.has(m.state)||m.dispatch_state==='unknown'))break;
   if(Date.now()>end)return {state:'timeout',output:'',reasons:['Toujours en cours après 45 min : suis-la dans le panneau Missions.']};
   await new Promise((resolve,reject)=>{const t=setTimeout(resolve,every);signal?.addEventListener('abort',()=>{clearTimeout(t);reject(signal.reason)},{once:true})});
  }
  const result=await auth.request('hermes/missions/'+encodeURIComponent(id)+'/results'+q);
  let output='';const reasons=[],parts=[],manifests=[];let quality=null;
  for(const e of result.events||[]){let d;try{d=JSON.parse(e.data)}catch{continue}
   if(['completed','failed','cancelled','deferred','reconciliation_required'].includes(e.kind)){if(d.output)output=d.output;else if(d.reason)reasons.push(d.reason)}
   else if(e.kind==='result_part')parts.push(d);else if(e.kind==='result_complete')manifests.push(d);else if(e.kind==='report_quality')quality=d;
  }
  if(manifests.length===1&&parts.length===manifests[0].parts){parts.sort((a,b)=>a.index-b.index);const full=parts.map(p=>p.output).join('');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(full)))).map(v=>v.toString(16).padStart(2,'0')).join('');if(hash===manifests[0].sha256)output=full}
  return {state:m.dispatch_state==='unknown'?'unknown':m.state,output,reasons,measurements:Number.isInteger(quality?.measurements_read)?quality.measurements_read:null};
 },
});
