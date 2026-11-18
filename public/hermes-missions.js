// Optional panel on the existing holographic UI. No microphone/audio changes.
(() => {
 const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(parent)parent.append(e);return e};
 const button=make('button','Connexion Jarvis');button.id='hermesMissionsButton';button.type='button';button.hidden=true;
 document.body.append(button);
 const dialog=make('dialog',null,document.body);dialog.id='hermesMissionsDialog';
 const close=make('button','Fermer',dialog);close.type='button';close.onclick=()=>dialog.close();
 make('h2','Missions Hermes',dialog);
 const status=make('p','',dialog);status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const content=make('section',null,dialog);content.hidden=true;
 make('p','Laboratoire synthétique · aucun équipement ni import personnel.',content);
 const create=make('button','Retrouver les cellules DoseLab X4',content);create.type='button';
 const refresh=make('button','Actualiser',content);refresh.type='button';
 const list=make('div',null,content);list.id='hermesMissionList';
 const detail=make('pre','',content);detail.id='hermesMissionResult';
 const canonical=make('pre','',content);canonical.id='hermesMissionCanonical';
 const availability=make('p','Disponibilité non mesurée',content);availability.id='hermesWorkerAvailability';
 const approvals=make('div',null,content);
 let identity=null,selected=null,timer=null,key=null,featureActive=false,admissionsEnabled=false;const seen=new Map();
 const states={queued:'En attente',running:'En cours',planning:'Planification',testing:'Évaluation',paused:'Suspendue',awaiting_approval:'Approbation requise',completed:'Terminée',failed:'Échec',cancelled:'Annulée',unknown:'Vérification nécessaire'};
 function space(){return document.querySelector('#spaceSelect')?.value||identity?.spaces?.[0]}
 async function request(path,options={}){return globalThis.JarvisAuth.request(path,options)}
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
  if(result.canonical){
   const p=result.canonical;
   if(p.mission_id===id&&p.selection_origin==='authenticated_host_tool_receipts'&&Array.isArray(p.receipt_ids)&&p.receipt_ids.length&&globalThis.JarvisCanonical){canonical.textContent=globalThis.JarvisCanonical.sections('',p).metadataText||''}
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
   try{const worker=await request(endpoint('availability'));availability.textContent=worker.fresh===true?'PC Gamer : '+worker.state:'PC Gamer indisponible ou présence non confirmée. Missions conservées.'}catch{availability.textContent='Disponibilité inconnue. Historique conservé.'}
   if(selected&&dialog.open)await inspect(selected);
  }catch(e){status.textContent=e.message}
 }
 async function bootstrap(){
  try{identity=await request('session')}catch(e){identity=null;button.textContent='Connexion Jarvis';button.hidden=e.status===404;return}
  const selector=document.querySelector('#spaceSelect');
  if(selector){for(const option of selector.options)option.disabled=!identity.spaces.includes(option.value);if(!identity.spaces.includes(selector.value)){selector.value=identity.spaces[0]}selector.dispatchEvent(new Event('change'))}
  try{const config=await request(endpoint('config'));admissionsEnabled=config.enabled===true;featureActive=admissionsEnabled||config.readEnabled===true;if(!featureActive){content.hidden=true;button.hidden=true;button.textContent='Compte Jarvis';status.textContent='Connecté. Missions Hermes désactivées.';return}}catch{button.hidden=true;return}
  content.hidden=false;button.hidden=false;button.textContent='Missions Hermes';
  create.disabled=!admissionsEnabled||!identity.roles.includes('missions.create');clearInterval(timer);timer=setInterval(()=>void refreshList(),5000);
 }
 button.onclick=async()=>{if(!identity){const id=await globalThis.JarvisAuth.open();if(!id)return;await bootstrap()}dialog.showModal();void refreshList()};
 dialog.addEventListener('close',()=>{detail.textContent='';canonical.textContent='';approvals.replaceChildren()});
 create.onclick=async()=>{if(!admissionsEnabled)return;create.disabled=true;key??=crypto.randomUUID();try{
  const result=await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':key},body:JSON.stringify({template:'doselab-current'})});
  key=null;selected=result.mission_id;await refreshList();
 }catch(e){status.textContent=e.message+' La même clé sera conservée en cas de nouvel envoi.'}finally{create.disabled=!admissionsEnabled||!identity?.roles.includes('missions.create')}};
 refresh.onclick=()=>void refreshList();
 document.addEventListener('jarvis:spacechange',()=>{selected=null;key=null;list.replaceChildren();detail.textContent='';canonical.textContent='';approvals.replaceChildren();void refreshList()});
 document.addEventListener('jarvis:session-ready',()=>void bootstrap());
 document.addEventListener('jarvis:session-ended',()=>{identity=null;featureActive=false;clearInterval(timer);content.hidden=true;list.replaceChildren();detail.textContent='';canonical.textContent='';approvals.replaceChildren();button.textContent='Connexion Jarvis'});
 globalThis.JarvisAuth?.ready().then(()=>bootstrap()).catch(()=>{});
})();
