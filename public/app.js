const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const palette={'Intelligence artificielle':'#7cc6eb','Maison & énergie':'#8dacff','Création & projets':'#c29cf5','Exploration':'#efbb7f','Apprentissage':'#f29cba','Idées libres':'#a2bac9'};
const spaces={user:'User',amelie:'Amélie',malik:'Malik',theo:'Théo',commun:'Commun'};
let currentSpace='user',detailId=null,assistantOpen=true,pendingAction=null;let dialogue=[];let activeRequest=null,requestSerial=0;
window.jarvisHistory=()=>dialogue.slice(-4).map(m=>({role:m.role,text:m.text.slice(0,600)}));
document.addEventListener('jarvis:native-turn',event=>{const {user,assistant,space}=event.detail;if(space!==currentSpace)return;if(user){message('TOI',user,'user');remember('user',user,false);}if(assistant){message('JARVIS',assistant);remember('assistant',assistant,false);}});
window.jarvisBusy=()=>!!activeRequest;
window.jarvisCancelAsk=()=>cancelActiveAsk();
function cancelActiveAsk(){requestSerial++;const old=activeRequest;activeRequest=null;old?.controller.abort();if(old?.node)old.node.textContent='Réponse interrompue.';$('#askButton').disabled=false;document.dispatchEvent(new CustomEvent('jarvis:written-state',{detail:{busy:false}}));}
$('#newConversation').addEventListener('click',()=>{
 cancelActiveAsk();
 if(pendingAction)pendingAction.buttons.forEach(button=>button.disabled=true);
 pendingAction=null;
 document.dispatchEvent(new Event('jarvis:newconversation'));dialogue=[];
 window.jarvisArchive?.newConversation(currentSpace);
 $('#messages').replaceChildren();$('#liveTranscript').replaceChildren();
 $('#question').value='';$('#conversationResetStatus').textContent='Nouveau fil · souvenirs conservés.';
 $('#question').focus({preventScroll:true});
});
try{currentSpace=localStorage.getItem('jarvis-space')||'user'}catch{}
if(!spaces[currentSpace])currentSpace='user';
let docs=[],allDocs=[],currentView='chat',activeTopic='',searchTimer,loadSequence=0;
function el(tag,cls,text){let n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function notify(text,error=false){$('#notice').textContent=text;$('#notice').hidden=false;$('#notice').style.borderColor=error?'#874a49':'#425964'}
async function api(path,options={}){let r=await fetch('/api/jarvis/'+path+(path.includes('?')?'&':'?')+'space='+encodeURIComponent(currentSpace),options);let v=await r.json();if(!r.ok)throw Error(v.error||'La connexion a été interrompue.');return v}
const post=(path,data,signal)=>api(path,{signal,method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data)});
function date(d){return new Date(d*1000).toLocaleDateString('fr-CH',{day:'numeric',month:'short',year:'numeric'})}
function card(d){const b=el('button','memory-card');b.style.setProperty('--card-color',palette[d.topic]);const top=el('div','card-top');top.append(el('span','',d.kind.toUpperCase()),el('span','',date(d.updated)));const bottom=el('div','card-bottom');bottom.append(el('i'),el('span','',d.topic));b.append(top,el('h3','',d.title),el('p','',d.preview?.replace(/^#+\s*/,'')),bottom);b.onclick=()=>openDoc(d.id);return b}
function visible(){return docs.filter(d=>(!activeTopic||d.topic===activeTopic)&&(currentView!=='atelier'||d.kind==='Atelier'))}
async function load(){let seq=++loadSequence;try{const q=$('#search').value;const data=await api('docs?q='+encodeURIComponent(q));if(seq!==loadSequence)return;docs=data.docs;if(!q)allDocs=docs;$('#count').textContent=data.total;$('#navCount').textContent=data.total;$('#syncLabel').textContent=data.lastSync?'Actualisé à '+new Date(Number(data.lastSync)*1000).toLocaleTimeString('fr-CH',{hour:'2-digit',minute:'2-digit'}):'Première indexation en cours';$('#codexCount').textContent=(data.counts.Codex||0)+' conversations';$('#memoryCount').textContent=(data.counts['Mémoire']||0)+' fiches';$('#chatgptCount').textContent=(data.counts.ChatGPT||0)+' conversations importées';render()}catch(e){notify(e.message,true)}}
function render(){const list=visible();$('#cards').replaceChildren(...list.map(card));if(!list.length)$('#cards').append(el('div','empty',currentView==='atelier'?'Une idée en tête ? Garde-la avec « Une idée ».':'Aucun souvenir trouvé.'));$('#resultCount').textContent=list.length+' souvenirs';$('#topics').replaceChildren(...Object.entries(palette).map(([name,color])=>{let b=el('button','topic'+(activeTopic===name?' active':''));b.style.setProperty('--topic',color);b.append(el('i'),el('span','',name));b.onclick=()=>{activeTopic=activeTopic===name?'':name;render()};return b}));}
function view(v){if(['library','atelier','memory3d'].includes(v)&&window.jarvisOpenPanel)return window.jarvisOpenPanel(v);if(v==='galaxy')v='chat';if(!['chat','library','atelier','memory3d'].includes(v))return;if(v==='chat')assistantOpen=true;currentView=v;document.body.dataset.screen=v;activeTopic='';const titles={memory3d:['Mémoire 3D.','Explorer les vrais extraits Qdrant de cet espace et des souvenirs communs.'],library:['Mémoire accessible.','Retrouver une conversation, une décision, un détail oublié.'],atelier:['Une idée à garder.','Les projets prennent forme, la mémoire fait le lien.'],chat:['À votre service.','Votre voix. Votre maison. Votre mémoire.']};$('#title').textContent=titles[v][0];$('#subtitle').textContent=titles[v][1];$('#crumb').textContent={memory3d:'MÉMOIRE 3D',library:'MÉMOIRE',atelier:'IDÉES',chat:'CONSOLE'}[v];$$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===v));$('#libraryView').hidden=!['library','atelier'].includes(v);$('#memory3dView').hidden=v!=='memory3d';$('#chatView').hidden=!assistantOpen||v==='memory3d';$('.chat-intro').hidden=v!=='chat';$('.toolbar').hidden=v==='chat'||v==='memory3d';$('#listTitle').textContent=v==='atelier'?'Nos idées en mouvement':'Tous les souvenirs';render();document.dispatchEvent(new CustomEvent('jarvis:view',{detail:{view:v}}))}
window.jarvisLibraryMode=kind=>{currentView=kind;activeTopic='';$('#listTitle').textContent=kind==='atelier'?'Nos idées en mouvement':'Tous les souvenirs';render();load();};
window.jarvisLibraryClose=()=>{currentView='chat';};
async function openDoc(id){const requestedSpace=currentSpace;try{const d=await api('doc?id='+encodeURIComponent(id));if(requestedSpace!==currentSpace)return;detailId=id;$('#moveTarget').value=currentSpace;$('#moveError').textContent='';$('#detailKind').textContent=d.kind+' · '+d.status;$('#detailTitle').textContent=d.title;$('#detailMeta').textContent=d.topic+' · '+date(d.updated);$('#detailBody').textContent=d.body;$('#detailSource').textContent=d.source;$('#related').replaceChildren(...allDocs.filter(x=>x.topic===d.topic&&x.id!==d.id).slice(0,4).map(x=>{let b=el('button','related-btn',x.title);b.onclick=()=>openDoc(x.id);return b}));if(!$('#detail').open)$('#detail').showModal();$('#detail').scrollTop=0}catch(e){notify(e.message,true)}}
$$('.nav').forEach(n=>n.onclick=()=>view(n.dataset.view));$('#search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(load,250)};document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('dialog[open]')){e.preventDefault();view('library');$('#search').focus()}});
$$('.close').forEach(b=>b.onclick=()=>b.closest('dialog').close());$('#newNote').onclick=()=>$('#noteDialog').showModal();$('#mobileSources').onclick=$('#sourcesBtn').onclick=()=>$('#sourcesDialog').showModal();
$('#noteForm').onsubmit=async e=>{e.preventDefault();const b=$('#noteForm button');b.disabled=true;try{const values=Object.fromEntries(new FormData(e.target));await post('notes',values);e.target.reset();$('#noteDialog').close();$('#noteError').textContent='';$('#search').value='';await load();notify('Une nouvelle idée a rejoint notre mémoire.')}catch(e){$('#noteError').textContent=e.message}finally{b.disabled=false}};
$('#syncBtn').onclick=async()=>{const b=$('#syncBtn');b.disabled=true;b.textContent='Actualisation…';try{let r=await post('sync',{});await load();notify(r.changed+' fiches actualisées'+(r.failed?' · '+r.failed+' sources non lues.':'.'));$('#sourcesDialog').close()}catch(e){notify(e.message,true)}finally{b.disabled=false;b.textContent='Actualiser maintenant'}};
$('#importBtn').onclick=()=>$('#importFile').click();$('#importFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>3*1024*1024*1024){notify('La sauvegarde dépasse la limite de 3 Go.',true);return}const b=$('#importBtn'),size=file.size>=1024**3?(file.size/1024**3).toFixed(1)+' Go':(file.size/1024**2).toFixed(0)+' Mo';b.disabled=true;b.textContent='Import · '+size+'…';notify('Import de la sauvegarde ChatGPT en cours. Garde cette page ouverte.');try{let r=await api('import',{method:'POST',headers:{'content-type':'application/octet-stream'},body:file});$('#search').value='';await load();notify(r.imported+' conversations ajoutées ou mises à jour.')}catch(e){notify(e.message,true)}finally{b.disabled=false;b.textContent='↓ Importer ChatGPT';e.target.value=''}};
function renderAnswer(target,text){
 target.replaceChildren();const value=String(text||'');let at=0;
 for(const match of value.matchAll(/\[([^\]\n]{1,160})\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>\])]+)/g)){
  target.append(document.createTextNode(value.slice(at,match.index)));const href=match[2]||match[3];let safe=false;try{const u=new URL(href);safe=['http:','https:'].includes(u.protocol)&&!u.username&&!u.password;}catch{}
  if(safe){const a=el('a','answer-link',match[1]||href);a.href=href;a.target='_blank';a.rel='noopener noreferrer';target.append(a);}else target.append(document.createTextNode(match[0]));at=match.index+match[0].length;
 }
 target.append(document.createTextNode(value.slice(at)));
}
function message(who,text,cls=''){let m=el('div','message '+cls);const body=el('div');if(who==='JARVIS')renderAnswer(body,text);else body.textContent=text;m.append(el('small','',who),body);$('#messages').append(m);requestAnimationFrame(()=>{$('#messages').scrollTop=$('#messages').scrollHeight});return m}
async function executeAction(action){
 if(action.type==='capability'){const result=await window.jarvisCapabilities?.execute(action.effect,{space:currentSpace});if(result?.state==='error')throw Error(result.error);return result?.state==='closed'?'Fenêtre fermée.':null;}
 if(action.type==='switch_space'){await changeSpace(action.target);return 'Tu es dans l’espace '+spaces[action.target]+'. Que veux-tu faire ?'}
 if(action.type==='navigate'){view(action.target);return 'La vue demandée est ouverte.'}
 if(action.type==='search'){view('library');$('#search').value=action.text;await load();return docs.length+' souvenirs trouvés pour « '+action.text+' ». Tu peux ouvrir une fiche à l’écran.'}
 if(action.type==='save_note'){await post('notes',{title:action.title,body:action.body,status:'Idée'});await load();return 'L’idée « '+action.title+' » est enregistrée dans l’espace '+spaces[currentSpace]+'.'}
 if(action.type==='open_app'){
 const available={astro:['Astro','/astro/index.html'],allemand:['Allemand','/allemand/index.html'],verbes:['Verbes en poche','/verbes/index.html']};const app=available[action.target];if(!app)throw Error('Application inconnue.');
 $('#applicationTitle').textContent=app[0];$('#applicationFrame').src=app[1];$('#applicationView').hidden=false;return app[0]+' est ouvert ci-dessus. Ses commandes restent accessibles à la souris ou au toucher.';
 }
 return '';
}
function remember(role,text,archiveWritten=true){if(archiveWritten)window.jarvisArchive?.written(role,text,currentSpace);dialogue.push({role,text});dialogue=dialogue.slice(-12)}
function reply(text){const m=message('JARVIS',text);remember('assistant',text);return m}
async function confirmPending(yes){const staged=pendingAction;if(!staged)return;pendingAction=null;staged.buttons.forEach(b=>b.disabled=true);if(!yes){reply('D’accord, je ne sauvegarde pas cette idée.');return}if(staged.space!==currentSpace){reply('L’espace a changé. Redonne-moi l’idée dans le bon espace.');return}try{reply(await executeAction(staged.action))}catch(e){reply('La sauvegarde a échoué : '+e.message)}}
$('#closeApplication').onclick=()=>{$('#applicationFrame').src='about:blank';$('#applicationView').hidden=true;};
$('#question').addEventListener('keydown',e=>{
 if(e.key!=='Enter'||e.isComposing||e.keyCode===229)return;
 e.preventDefault();if(e.repeat)return;
 if(e.altKey){const field=e.currentTarget;if(field.value.length-(field.selectionEnd-field.selectionStart)+1>field.maxLength)return;field.setRangeText('\n',field.selectionStart,field.selectionEnd,'end');field.dispatchEvent(new Event('input',{bubbles:true}));return}
 if(!$('#askButton').disabled)$('#askForm').requestSubmit($('#askButton'));
});
window.jarvisAsk=async(question,options={})=>{
 const q=question.trim();if(!q||$('#askButton').disabled)return;
 options.signal?.throwIfAborted();
 const voice=options.channel==='voice',askSpace=currentSpace;
 const journal=voice?{...options.archive,space:askSpace,channel:'voice',user:q,assistant:''}:null;
 const record=(role,text)=>{remember(role,text,!voice);if(journal){if(role==='assistant')journal.assistant=text;window.jarvisArchive?.record({...journal,revision:role==='user'?1:2,status:role==='user'?'partial':'complete'});}};
 if(!voice)document.dispatchEvent(new Event('jarvis:writtenask'));message('TOI',q,'user');
 if(pendingAction&&/^(oui|oui merci|vas-y|confirme|enregistre|non|annule|annuler)[.! ]*$/i.test(q)){record('user',q);$('#question').value='';await confirmPending(!/^(non|annul)/i.test(q));return {answer:dialogue.at(-1)?.text||''};}
 if(pendingAction){pendingAction.buttons.forEach(b=>b.disabled=true);pendingAction=null}
 const history=dialogue.slice();record('user',q);const pending=message('JARVIS','Je réfléchis avec toi…');const answerText=pending.lastChild;const serial=++requestSerial,controller=new AbortController();activeRequest={controller,node:answerText};$('#askButton').disabled=true;document.dispatchEvent(new CustomEvent('jarvis:written-state',{detail:{busy:true}}));$('#question').value='';
 const abort=()=>controller.abort();options.signal?.addEventListener('abort',abort,{once:true});
 try{
 const r=await post('ask',{question:q,archive:voice?options.archive:window.jarvisArchive?.writtenRequest(askSpace),channel:voice?'voice':'written',history,view:currentView,application:$('#applicationView').hidden?null:$('#applicationTitle').textContent},controller.signal);if(serial!==requestSerial||askSpace!==currentSpace)return;renderAnswer(answerText,r.answer);record('assistant',r.answer);
 for(const source of r.sources){const b=el('button','', '▤ '+source.title);b.onclick=()=>openDoc(source.id);pending.append(b)}
 for(const effect of r.effects||[])await window.jarvisCapabilities?.execute(effect,{space:askSpace});
 if(r.action?.type==='save_note'){
 const preview=el('div','note-preview',r.action.title+'\n'+r.action.body);pending.append(preview);
 const yes=el('button','','Enregistrer dans '+spaces[currentSpace]),no=el('button','','Annuler');yes.onclick=()=>confirmPending(true);no.onclick=()=>confirmPending(false);pending.append(yes,no);pendingAction={action:r.action,space:currentSpace,buttons:[yes,no]};
 const prompt=r.answer+' Veux-tu enregistrer cette idée dans l’espace '+spaces[currentSpace]+' ?';answerText.textContent=prompt;
 }else if(r.action){activeRequest=null;$('#askButton').disabled=false;const outcome=await executeAction(r.action);if(outcome){message('JARVIS',outcome);record('assistant',outcome);r.answer=outcome;}if(r.action.type==='switch_space')$('#messages').prepend(el('div','message user','TOI : '+q));}
 else{const save=el('button','save-reflection','Garder');save.onclick=()=>{$('#noteForm [name=title]').value=q.slice(0,180);$('#noteForm [name=body]').value=r.answer;$('#noteDialog').showModal()};pending.append(save)}
 $('#question').value='';return r;
 }catch(e){if(e.name!=='AbortError'&&serial===requestSerial)answerText.textContent=e.message}finally{options.signal?.removeEventListener('abort',abort);if(serial===requestSerial){activeRequest=null;$('#askButton').disabled=false;document.dispatchEvent(new CustomEvent('jarvis:written-state',{detail:{busy:false}}))}}
};
$('#askForm').onsubmit=async event=>{event.preventDefault();await window.jarvisAsk($('#question').value);};
$$('.suggestions button').forEach(b=>b.onclick=()=>{$('#question').value=b.textContent;$('#question').focus()});
if(document.modelContext?.registerTool){const controller=new AbortController();for(const tool of [{name:'search_jarvis_memory',description:'Rechercher les souvenirs et afficher les résultats dans Jarvis.',inputSchema:{type:'object',properties:{query:{type:'string'}},required:['query'],additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},async execute(input){if(typeof input?.query!=='string'||input.query.length>2000)throw Error('Requête invalide');view('library');$('#search').value=input.query;await load();return {results:docs.map(({id,title,kind})=>({id,title,kind}))}}}]){try{Promise.resolve(document.modelContext.registerTool(tool,{signal:controller.signal})).catch(()=>{})}catch{}}window.addEventListener('pagehide',()=>controller.abort(),{once:true})}
function spaceLabels(){
 $('#spaceSelect').value=currentSpace;$('#profileName').textContent=spaces[currentSpace];$('.avatar').textContent=spaces[currentSpace][0];
 $('#importBtn').title='Importer les conversations dans l’espace '+spaces[currentSpace];
 $('#noteDialog h2').textContent='Une idée pour '+spaces[currentSpace]+'.';
}
async function changeSpace(target){
 document.dispatchEvent(new Event('jarvis:spacechange'));cancelActiveAsk();dialogue=[];if(pendingAction)pendingAction.buttons.forEach(b=>b.disabled=true);pendingAction=null;$('#closeApplication').click();currentSpace=target;try{localStorage.setItem('jarvis-space',currentSpace)}catch{}
 ++loadSequence;docs=[];allDocs=[];activeTopic='';$('#search').value='';$('#messages').replaceChildren();$('#question').value='';$('#notice').hidden=true;
 $('#count').textContent='—';$('#navCount').textContent='0';$('#noteForm').reset();spaceLabels();render();await load();
}
$('#spaceSelect').onchange=e=>changeSpace(e.target.value);
$('#moveForm').onsubmit=async e=>{e.preventDefault();const target=$('#moveTarget').value;const b=$('#moveForm button');b.disabled=true;try{await post('move',{id:detailId,target});$('#detail').close();await load();notify('Souvenir classé dans l’espace '+spaces[target]+'.')}catch(e){$('#moveError').textContent=e.message}finally{b.disabled=false}};
spaceLabels();view(new URLSearchParams(location.search).get('view')==='memory3d'?'memory3d':'chat');load();setInterval(()=>{if(!document.hidden&&!$('dialog[open]')&&currentView!=='chat')load()},60000);


document.addEventListener('jarvis:session-ready',()=>void load());
