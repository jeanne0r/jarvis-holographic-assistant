"""Lot A: derive two existing frontend assets; no gateway/service/state writes."""
import argparse,difflib,hashlib,json
from pathlib import Path
from .prepare_operational_hermes import operational_assets
from .prepare_embedded_panel import ROOT,replace_once

def human_assets(*,unified=False):
    js,css=operational_assets()
    helper=(ROOT/'public/hermes-mission-view.js').read_text()
    js=helper+'\n'+js
    js=replace_once(js," const detail=make('pre','',content);detail.id='hermesMissionResult';", """ const detailNode=make('div','',content);detailNode.id='hermesMissionResult';
 const warning=make('p','Réponse de l’assistant à vérifier. Les sources et leur statut restent consultables.',content);warning.id='hermesResultWarning';
 let rawResult='';const detail={get textContent(){return rawResult},set textContent(value){rawResult=String(value);detailNode.replaceChildren(JarvisMissionView.markdown(rawResult));if(typeof modelProof!=='undefined')modelProof.textContent=rawResult}};""")
    js=replace_once(js," const canonical=make('pre','',content);canonical.id='hermesMissionCanonical';", """ const sources=make('details',null,content);sources.id='hermesSourcesDetails';make('summary','Sources et détails techniques',sources);
 const canonical=make('pre','',sources);canonical.id='hermesMissionCanonical';
 const modelProof=make('pre','',sources);modelProof.id='hermesOriginalResult';
 const objectiveProof=make('pre','',sources);objectiveProof.id='hermesMissionObjective';
 const eventsProof=make('pre','',sources);eventsProof.id='hermesMissionEvents';""")
    js=replace_once(js," const list=make('div',null,content);list.id='hermesMissionList';", """ const controls=make('div',null,content);
 const historyLabel=make('label',null,controls);historyLabel.className='hermes-filter';const history=make('input',null,historyLabel);history.type='checkbox';historyLabel.append(document.createTextNode('Tout l’historique'));
 const demoLabel=make('label',null,controls);demoLabel.className='hermes-filter';const hideDemos=make('input',null,demoLabel);hideDemos.type='checkbox';demoLabel.append(document.createTextNode('Masquer les démonstrations'));
 history.onchange=hideDemos.onchange=()=>void refreshList();
 const list=make('div',null,content);list.id='hermesMissionList';""")
    js=replace_once(js,'  selected=id;const m=await request', '  selected=id;const current=++inspection;const m=await request')
    js=replace_once(js,"  detail.textContent=(", "  if(current!==inspection||selected!==id)return;objectiveProof.textContent=m.definition?.objective||'';\n  detail.textContent=(")
    js=replace_once(js,"  const result=await request(endpoint('missions/'+id+'/results'));", "  const result=await request(endpoint('missions/'+id+'/results'));\n  if(current!==inspection||selected!==id)return;eventsProof.textContent=JSON.stringify(result.events||[],null,2);")
    js=replace_once(js," let identity=null,selected=null,timer=null,key=null,featureActive=false,admissionsEnabled=false;", " let identity=null,selected=null,timer=null,key=null,featureActive=false,admissionsEnabled=false,inspection=0;")
    old="   for(const m of data.items||[]){const row=make('button',(m.dispatch_state==='unknown'?states.unknown:(states[m.state]||m.state))+' · '+m.objective,list);row.type='button';row.onclick=()=>inspect(m.id).catch(e=>status.textContent=e.message)}"
    new="""   const visible=JarvisMissionView.visible(data.items||[],{history:history.checked,hideDemos:hideDemos.checked});
   for(const m of visible){const row=make('button',null,list);row.type='button';row.className='hermes-card';row.dataset.state=m.state;
    const state=m.dispatch_state==='unknown'?states.unknown:(states[m.state]||'État à vérifier');
    make('strong',state+' · '+JarvisMissionView.title(m),row);make('small',JarvisMissionView.timing(m),row);
    if(JarvisMissionView.demo(m))make('small','Démonstration · données fictives',row);
    if(m.summary)make('span',String(m.summary),row);
    row.onclick=()=>inspect(m.id).catch(e=>status.textContent=JarvisMissionView.failure(e));
   }
   if(!visible.length&&data.items?.length)make('p','Aucune mission dans cette vue. L’historique est conservé.',list);"""
    js=replace_once(js,old,new)
    js=replace_once(js,"+'\\n'+(m.definition?.objective||'');approvals.replaceChildren();", "+'\\n'+JarvisMissionView.title(m);approvals.replaceChildren();")
    js=replace_once(js,"if(['completed','failed','awaiting_approval'].includes(m.state)&&seen.get(m.id)!==m.state)","if(seen.has(m.id)&&['completed','failed','awaiting_approval'].includes(m.state)&&seen.get(m.id)!==m.state)")
    js=replace_once(js,"if(hash!==manifest.sha256)throw Error('Empreinte du résultat invalide');", "if(current!==inspection||selected!==id)return;if(hash!==manifest.sha256)throw Error('Empreinte du résultat invalide');")
    # Refresh flags without reloading the page; errors keep creation disabled.
    js=replace_once(js,"   const data=await request(endpoint('missions'));list.replaceChildren();", """   const config=await request(endpoint('config'));admissionsEnabled=config.enabled===true;
   create.hidden=!admissionsEnabled;create.disabled=!admissionsEnabled||!identity.roles.includes('missions.create');
   objective.hidden=submit.hidden=!(config.textEnabled===true&&admissionsEnabled&&identity.roles.includes('missions.create'));
   globalThis.JarvisHermesVoiceEnabled=config.voiceEnabled===true;
   const data=await request(endpoint('missions'));list.replaceChildren();""")
    js=replace_once(js,"availability.textContent=worker.fresh===true?'PC Gamer : '+worker.state:'Exécution Hermes désactivée. Historique disponible.'", "availability.textContent=JarvisMissionView.availability(worker)")
    js=replace_once(js,"  }catch(e){status.textContent=e.message}\n }\n async function bootstrap", "  }catch(e){create.disabled=true;objective.hidden=submit.hidden=true;globalThis.JarvisHermesVoiceEnabled=false;status.textContent=JarvisMissionView.failure(e)}\n }\n async function bootstrap")
    js=replace_once(js,"dialog.addEventListener('close',()=>{detail.textContent='';canonical.textContent='';approvals.replaceChildren()});", "dialog.addEventListener('close',()=>{++inspection;detail.textContent='';canonical.textContent='';objectiveProof.textContent='';eventsProof.textContent='';approvals.replaceChildren()});")
    js=replace_once(js,"identity=null;featureActive=false;globalThis.JarvisHermesVoiceEnabled=false;", "identity=null;++inspection;selected=null;featureActive=false;globalThis.JarvisHermesVoiceEnabled=false;objectiveProof.textContent='';eventsProof.textContent='';")
    js=replace_once(js,"  if(!identity||!featureActive||document.hidden)return;\n  try{", "  if(!identity||!featureActive||document.hidden)return;\n  const sessionIdentity=identity;\n  try{")
    js=replace_once(js,"   const config=await request(endpoint('config'));admissionsEnabled=", "   const config=await request(endpoint('config'));if(identity!==sessionIdentity||!featureActive)return;admissionsEnabled=")
    js=replace_once(js,"   const data=await request(endpoint('missions'));list.replaceChildren();", "   const data=await request(endpoint('missions'));if(identity!==sessionIdentity||!featureActive)return;list.replaceChildren();")
    js=replace_once(js,"try{const worker=await request(endpoint('availability'));availability.textContent=", "try{const worker=await request(endpoint('availability'));if(identity!==sessionIdentity||!featureActive)return;availability.textContent=")
    js=replace_once(js,"}catch(e){create.disabled=true;objective.hidden=submit.hidden=true;", "}catch(e){if([401,403].includes(e.status)){++inspection;selected=null;list.replaceChildren();detail.textContent='';canonical.textContent='';objectiveProof.textContent='';eventsProof.textContent=''}create.disabled=true;objective.hidden=submit.hidden=true;")
    if unified:
        # Reuse the already-tested common registry/client ONLY in the isolated
        # variant. This cannot consume the private panel's separate cookie.
        start=js.index('// Independent human login.')
        end=js.index('// Optional panel on the existing holographic UI.',start)
        common=(ROOT/'public/jarvis-auth.js').read_text()
        js=js[:start]+common+'\n'+'''const commonAuth=globalThis.JarvisAuth;
globalThis.JarvisHermesAuth=Object.freeze({ready:commonAuth.ready,open:commonAuth.open,identity:commonAuth.identity,
 request:(path,options)=>commonAuth.request(path==='session'?'session':'hermes-panel/'+path,options)});
'''+js[end:]
        js=js.replace('#hermesAccountButton','#jarvisAccountButton').replace('jarvis:hermes-session-','jarvis:session-')
        js=replace_once(js,"const account=document.querySelector('#jarvisAccountButton');if(account)dialog.append(account);",'')
    css+='\n'+(ROOT/'public/hermes-mission-view.css').read_text()
    return js,css

def prepare(destination,gateway=Path('/home/user/gateway'),*,unified=False):
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Never overwrite evidence or previous preparations')
    js,css=human_assets(unified=unified);destination.mkdir(parents=True)
    rows=[]
    for name,data in [('hermes-embedded.js',js),('hermes-embedded.css',css)]:
        target=Path(gateway)/'public/jarvis'/name
        if target.is_symlink():raise PermissionError('Active asset symlink requires separate review')
        old=target.read_bytes();raw=data.encode();(destination/name).write_bytes(raw)
        patch=''.join(difflib.unified_diff(old.decode().splitlines(True),data.splitlines(True),fromfile='a/public/jarvis/'+name,tofile='b/public/jarvis/'+name))
        (destination/(name+'.patch')).write_text(patch)
        # Apply the unified diff in memory via git on a disposable copy in tests;
        # exact old/new bytes also make rollback verifiable without running services.
        saved=destination/(name+'.before');saved.write_bytes(old)
        if saved.read_bytes()!=old:raise ValueError('Backup verification failed')
        rows.append({'target':str(target),'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(raw).hexdigest(),'artifact':name,'backup':saved.name})
    manifest={'production_modified':False,'lot':'B-laboratory-only' if unified else 'A','gateway_restart_required':False,'private_service_modified':False,'permissions_changed':False,'flags_changed':False,'files':rows}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');p.add_argument('--unified-laboratory',action='store_true');args=p.parse_args();prepare(args.destination,unified=args.unified_laboratory)
    print('Two isolated frontend assets prepared. No deployment or model call.')
