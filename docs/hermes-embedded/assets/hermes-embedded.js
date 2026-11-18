// Generated from existing formatter, login and panel. See prepare_embedded_panel.py.
// Inert formatter, not wired into the panel until server-bound metadata is reviewed.
// Never parse model text into authority or replace dates inside it.
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
 const dialog=make('dialog',null,document.body);dialog.id='hermesAccountDialog';
 const close=make('button','Fermer',dialog);close.type='button';close.onclick=()=>dialog.close();
 const form=make('form',null,dialog);make('label','Code personnel',form);
 const input=make('input',null,form);input.type='password';input.autocomplete='one-time-code';input.setAttribute('aria-label','Code personnel');input.required=true;
 const submit=make('button','Se connecter',form);submit.type='submit';
 const status=make('p','',dialog);status.setAttribute('role','status');
 const logout=make('button','Déconnexion',dialog);logout.type='button';logout.hidden=true;
 function publish(id){identity=id;form.hidden=!!id;logout.hidden=!id;button.textContent=id?'Compte missions':'Connexion missions';button.hidden=false;document.dispatchEvent(new CustomEvent(id?'jarvis:hermes-session-ready':'jarvis:hermes-session-ended'));}
 async function request(path,options={}){
  const response=await fetch('/api/jarvis/hermes-panel/'+path,{...options,credentials:'same-origin'});
  let body;try{body=await response.json()}catch{throw Error('Réponse indisponible')}
  if(response.status===401&&identity)publish(null);
  if(!response.ok)throw Object.assign(Error(response.status===401?'Connexion requise':body.error||'Requête refusée'),{status:response.status});return body;
 }
 async function load(){try{const r=await fetch('/api/jarvis/hermes-panel/session',{credentials:'same-origin'});if(r.status===404)return null;if(r.ok){publish(await r.json());return identity}publish(null);return null}catch{publish(null);return null}}
 const open=async()=>{await readyPromise;if(identity){dialog.showModal();return identity}dialog.showModal();return new Promise(resolve=>pending.push(resolve))};
 button.onclick=()=>{void open()};
 dialog.addEventListener('close',()=>{input.value='';for(const resolve of pending.splice(0))resolve(identity)});
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{await request('session',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({token:input.value})});input.value='';await load();dialog.close()}catch(error){status.textContent=error.message;input.value=''}finally{submit.disabled=false}};
 logout.onclick=async()=>{try{await request('session',{method:'DELETE'});publish(null);dialog.close();location.reload()}catch(error){status.textContent=error.message}};
 globalThis.JarvisHermesAuth=Object.freeze({request,open,ready:()=>readyPromise,identity:()=>identity});
 readyPromise=load();
})();

// Optional panel on the existing holographic UI. No microphone/audio changes.
(() => {
 const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(parent)parent.append(e);return e};
 const button=make('button','Connexion missions');button.id='hermesMissionsButton';button.type='button';button.hidden=true;
 (document.querySelector('.header-actions')||document.body).append(button);
 const dialog=make('dialog',null,document.body);dialog.id='hermesMissionsDialog';
 const close=make('button','Fermer',dialog);close.type='button';close.onclick=()=>dialog.close();
 make('h2','Missions Hermes',dialog);const account=document.querySelector('#hermesAccountButton');if(account)dialog.append(account);
 const status=make('p','',dialog);status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const content=make('section',null,dialog);content.hidden=true;
 make('p','Laboratoire synthétique · réponses du modèle non vérifiées. Aucun équipement ni import personnel.',content);
 const create=make('button','Retrouver les cellules DoseLab X4',content);create.type='button';create.hidden=true;
 const refresh=make('button','Actualiser',content);refresh.type='button';
 const list=make('div',null,content);list.id='hermesMissionList';
 const detail=make('pre','',content);detail.id='hermesMissionResult';
 const canonical=make('pre','',content);canonical.id='hermesMissionCanonical';
 const availability=make('p','Disponibilité non mesurée',content);availability.id='hermesWorkerAvailability';
 const approvals=make('div',null,content);
 let identity=null,selected=null,timer=null,key=null,featureActive=false,admissionsEnabled=false;const seen=new Map();
 const states={queued:'En attente',running:'En cours',planning:'Planification',testing:'Évaluation',paused:'Suspendue',awaiting_approval:'Approbation requise',completed:'Terminée',failed:'Échec',cancelled:'Annulée',unknown:'Vérification nécessaire'};
 function space(){return identity?.spaces?.[0]}
 async function request(path,options={}){return globalThis.JarvisHermesAuth.request(path,options)}
 const endpoint=path=>'hermes/'+path+'?space='+encodeURIComponent(space());
 async function inspect(id){
  selected=id;const m=await request(endpoint('missions/'+id));
  detail.textContent=(states[m.state]||m.state)+'\n'+(m.definition?.objective||'');approvals.replaceChildren();
  const result=await request(endpoint('missions/'+id+'/results'));
  for(const e of result.events||[]){if(['completed','failed','cancelled','deferred','reconciliation_required'].includes(e.kind)){
   let data;try{data=JSON.parse(e.data)}catch{continue}
   detail.textContent+='\n'+(data.output||data.reason||(e.kind==='reconciliation_required'?'Reprise à vérifier, aucun rejeu automatique.':''));
  }}
  canonical.textContent='';
  if(result.canonicalUnavailable)canonical.textContent='Métadonnées canoniques indisponibles. Réponse du modèle non vérifiée.';
  if(result.canonical){
   const p=result.canonical;
   if(p.mission_id===id&&p.selection_origin==='authenticated_host_tool_receipts'&&Array.isArray(p.receipt_ids)&&p.receipt_ids.length&&globalThis.JarvisHermesCanonical){canonical.textContent=globalThis.JarvisHermesCanonical.sections('',p).metadataText||''}
   else canonical.textContent='Provenance non liée : métadonnées non affichées.';
  }
  if(!['completed','failed','cancelled'].includes(m.state)){
   const cancel=make('button','Annuler cette mission',approvals);cancel.type='button';cancel.onclick=async()=>{try{await request(endpoint('missions/'+id+'/cancel'),{method:'POST',headers:{'content-type':'application/json'},body:'{}'});await refreshList()}catch(e){status.textContent=e.message}};
  }
  for(const a of m.approvals||[]){if(a.state!=='pending')continue;
   let action;try{action=JSON.parse(a.action)}catch{action={description:'Demande à vérifier'}}
   make('p',action.description||'Demande à vérifier',approvals);
   if(!identity.roles.includes('missions.approve')){make('p','Un compte approbateur distinct est requis.',approvals);continue}
   for(const [choice,label] of [['once','Autoriser cette action une fois'],['deny','Refuser']]){
    const b=make('button',label,approvals);b.type='button';b.onclick=async()=>{if(!confirm('Confirmer cette décision pour cette action précise ?'))return;
     try{await request(endpoint('missions/'+id+'/approvals'),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({approval_id:a.id,fingerprint:a.fingerprint,choice})});await inspect(id)}catch(e){status.textContent=e.message}
    };
   }
  }
 }
 async function refreshList(){
  if(!identity||!featureActive||document.hidden)return;
  try{
   const data=await request(endpoint('missions'));list.replaceChildren();
   for(const m of data.items||[]){if(['completed','failed','awaiting_approval'].includes(m.state)&&seen.get(m.id)!==m.state)button.textContent='Missions · '+(states[m.state]||m.state);seen.set(m.id,m.state)}
   for(const m of data.items||[]){const row=make('button',(states[m.state]||m.state)+' · '+m.objective,list);row.type='button';row.onclick=()=>inspect(m.id).catch(e=>status.textContent=e.message)}
   if(!data.items?.length)make('p','Aucune mission.',list);
   status.textContent=admissionsEnabled?'Historique conservé sur Proxmox. Un PC indisponible laisse les missions en attente.':'Consultation et annulation disponibles. Nouvelles missions désactivées.';
   try{const worker=await request(endpoint('availability'));availability.textContent=worker.fresh===true?'PC Gamer : '+worker.state:'Exécution Hermes désactivée. Historique disponible.'}catch{availability.textContent='Disponibilité inconnue. Historique conservé.'}
   if(selected&&dialog.open)await inspect(selected);
  }catch(e){status.textContent=e.message}
 }
 async function bootstrap(){
  try{identity=await request('session')}catch(e){identity=null;button.textContent='Connexion missions';button.hidden=e.status===404;return}
  try{const config=await request(endpoint('config'));admissionsEnabled=config.enabled===true;featureActive=admissionsEnabled||config.readEnabled===true;if(!featureActive){content.hidden=true;button.hidden=true;button.textContent='Compte Jarvis';status.textContent='Connecté. Missions Hermes désactivées.';return}}catch{button.hidden=true;return}
  content.hidden=false;button.hidden=false;button.textContent='Missions Hermes';
  create.disabled=!admissionsEnabled||!identity.roles.includes('missions.create');clearInterval(timer);timer=setInterval(()=>void refreshList(),5000);
 }
 button.onclick=async()=>{if(!identity){const id=await globalThis.JarvisHermesAuth.open();if(!id)return;await bootstrap()}dialog.showModal();void refreshList()};
 dialog.addEventListener('close',()=>{detail.textContent='';canonical.textContent='';approvals.replaceChildren()});
 create.onclick=async()=>{if(!admissionsEnabled)return;create.disabled=true;key??=crypto.randomUUID();try{
  const result=await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':key},body:JSON.stringify({template:'doselab-current'})});
  key=null;selected=result.mission_id;await refreshList();
 }catch(e){status.textContent=e.message+' La même clé sera conservée en cas de nouvel envoi.'}finally{create.disabled=!admissionsEnabled||!identity?.roles.includes('missions.create')}};
 refresh.onclick=()=>void refreshList();
 document.addEventListener('jarvis:hermes-spacechange',()=>{selected=null;key=null;list.replaceChildren();detail.textContent='';canonical.textContent='';approvals.replaceChildren();void refreshList()});
 document.addEventListener('jarvis:hermes-session-ready',()=>void bootstrap());
 document.addEventListener('jarvis:hermes-session-ended',()=>{identity=null;featureActive=false;clearInterval(timer);content.hidden=true;list.replaceChildren();detail.textContent='';canonical.textContent='';approvals.replaceChildren();button.textContent='Connexion missions'});
 globalThis.JarvisHermesAuth?.ready().then(()=>bootstrap()).catch(()=>{});
})();
