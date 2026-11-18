"""Code-only on-demand package. No state, secrets, Windows calls or installation."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from .prepare_embedded_panel import ROOT,replace_once

FILES=['scripts/text_mission_window.py','memory_manager/phase6/demand_queue.py','memory_manager/phase6/demand_service.py','memory_manager/phase6/memory_audit.py','memory_manager/phase6/operational.py',
'memory_manager/phase2/bridge.py','memory_manager/phase2/mcp.py','memory_manager/phase2/memory_tools.py','memory_manager/phase3/mcp.py','memory_manager/phase6d/evidence.py']
SUPERVISOR=['scripts/demand_supervisor.py','scripts/run_interactive_hermes.py','scripts/pilot_phase6b_panel.py']
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def frontend(raw):
    s=raw.decode();s=replace_once(s,"objective.placeholder='Demande explicite · outils et mémoire synthétiques seulement';", "objective.placeholder='Décrire une mission';objective.setAttribute('aria-label','Décrire une mission');")
    s=s.replace("'Soumettre cette demande'","'Confier à Hermes'")
    s=s.replace('Envoi possible uniquement pendant une fenêtre autorisée ; sinon, prépare ton texte sans le transmettre.', 'Décris une analyse de données fictives. Ta demande sera conservée même si Hermes est indisponible.')
    s=s.replace('Exécuteur','Hermes').replace('exécuteur','Hermes').replace('Admission non confirmée','Enregistrement non confirmé')
    s=s.replace("'Consultation et annulation disponibles. Nouvelles missions désactivées.'", "'Les nouvelles missions sont temporairement suspendues. Historique et annulation disponibles.'")
    s=replace_once(s," const objective=make('textarea'", " const notice=make('p','',content);notice.id='hermesMissionNotice';notice.setAttribute('role','status');let lastAvailability=null;\n const objective=make('textarea'")
    old="  if(!textAttempt){if(!objective.value.trim()||objective.value.length>2000)return;textAttempt={key:crypto.randomUUID(),objective:objective.value}}\n  const attempt=textAttempt;textBusy=true;textReady();\n  try{const result=await request("
    new="""  if(!objective.value.trim()||objective.value.length>2000)return;
  textBusy=true;textReady();
  try{
   if(!textAttempt){
    const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(objective.value));
    const hash=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
    const ticket='hermes-request-ticket:'+identity.subject+':'+space()+':'+hash;
    let saved=null;try{saved=sessionStorage.getItem(ticket)}catch{}
    const key=/^[A-Za-z0-9_-]{1,120}$/.test(saved||'')?saved:crypto.randomUUID();
    textAttempt={key,objective:objective.value,ticket};try{sessionStorage.setItem(ticket,key)}catch{}
   }
   const attempt=textAttempt;const result=await request("""
    s=replace_once(s,old,new)
    s=replace_once(s,"   selected=result.mission_id;", "   try{sessionStorage.removeItem(attempt.ticket)}catch{}\n   selected=result.mission_id;")
    s=replace_once(s,'selected=result.mission_id;textAttempt=null;',"selected=result.mission_id;notice.textContent='Mission enregistrée. En attente de disponibilité.';textAttempt=null;")
    s=replace_once(s,"if(current!==inspection||selected!==id)return;objectiveProof.textContent", "if(current!==inspection||selected!==id)return;notice.textContent=({queued:lastAvailability?.reason==='windows_offline'?'Mission enregistrée. Hermes est momentanément indisponible.':'Mission enregistrée. En attente de disponibilité.',running:'Hermes a pris en charge ton analyse.',completed:'Mission terminée. Résultat disponible.',failed:'La mission a échoué. Consulte les détails.',cancelled:'Mission annulée.',paused:'Cette mission nécessite une vérification. Elle ne sera pas relancée automatiquement.'})[m.state]||'État à vérifier.';objectiveProof.textContent")
    s=replace_once(s,"availability.textContent=JarvisMissionView.availability(worker)", "lastAvailability=worker;availability.textContent=worker.active?.reason==='uncertain'?'Une mission nécessite une vérification. Historique disponible.':worker.fresh&&worker.state==='ready'?'Hermes est disponible.':({windows_offline:'Hermes est momentanément indisponible. Les demandes restent enregistrées.',miner_active:'Carte graphique occupée. Les demandes restent en attente.',gpu_busy:'Carte graphique occupée. Les demandes restent en attente.',insufficient_vram:'Ressources momentanément insuffisantes. Les demandes restent en attente.'})[worker.reason]||'Disponibilité non confirmée. Les demandes restent enregistrées.'")
    s=replace_once(s,"  const fragments=[],manifests=[];", "  const reportQuality=(result.events||[]).find(e=>e.kind==='report_quality');if(reportQuality){const quality=JSON.parse(reportQuality.data);warning.textContent=quality.model_cites_source_ref===true?'Références retrouvées dans la mémoire ; réponse non vérifiée indépendamment.':'Les sources ne sont pas correctement citées. Réponse à vérifier.'}\n  const fragments=[],manifests=[];")
    return s

def prepare(dest):
    dest=Path(dest)
    if dest.exists():raise FileExistsError('Never overwrite a package')
    installed=Path('/opt/jarvis-hermes-pilot');known=json.loads((installed/'deployment-files.json').read_text())
    for n,h in known.items():
        p=installed/n
        if p.is_symlink() or not p.resolve().is_relative_to(installed) or SHA(p)!=h:raise PermissionError('Installed release drift')
    dest.mkdir(parents=True);release=dest/'private-release';shutil.copytree(installed,release)
    for n in FILES:
        target=release/n;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():target.chmod(0o600)
        target.write_bytes((ROOT/n).read_bytes())
    # Keep the installed private-cookie mode, not the unactivated SSO worktree.
    api=release/'hermes-embedded-api.mjs';api.chmod(0o600);s=api.read_text()
    s=replace_once(s,'syntheticOnly:true,templates:','syntheticOnly:true,onDemand:features.queueEnabled===true,templates:')
    s=replace_once(s,'if(features.workerEnabled===true){','if(features.workerEnabled===true||features.queueEnabled===true){');api.write_text(s)
    op=release/'ops/pilot-embedded.mjs';op.chmod(0o600);s=op.read_text();s=replace_once(s,'const flags=c.operations||{};','const flags={...(c.operations||{}),queueEnabled:c.onDemand?.commissioned===true};');op.write_text(s)
    for p in [release/'docs/pilot-interactive/manifest.json',release/'deployment-files.json']:p.chmod(0o600)
    m=json.loads((release/'docs/pilot-interactive/manifest.json').read_text());m['files'].update({n:SHA(release/n) for n in FILES+['ops/pilot-embedded.mjs','hermes-embedded-api.mjs']});(release/'docs/pilot-interactive/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    (release/'deployment-files.json').write_text(json.dumps({str(p.relative_to(release)):SHA(p) for p in release.rglob('*') if p.is_file() and p.name!='deployment-files.json'},indent=2)+'\n')
    ui=dest/'frontend';ui.mkdir();active=Path('/home/user/gateway/public/jarvis')
    review=json.loads((ROOT/'docs/HERMES_TEXT_MISSIONS_MANIFEST.json').read_text())
    if SHA(active/'hermes-embedded.js')!=review['frontend']['after_sha256']:raise PermissionError('Deployed C composer drift')
    (ui/'hermes-embedded.js').write_text(frontend((active/'hermes-embedded.js').read_bytes()))
    for n in ['index.html','hermes-embedded.css']:shutil.copyfile(active/n,ui/n)
    supervisor=dest/'supervisor';shutil.copytree(release,supervisor)
    # Source-only dependency closure: tracked Python, never runtime data/config/keys.
    tracked=subprocess.check_output(['git','ls-files','--','scripts','memory_manager','ops'],cwd=ROOT,text=True).splitlines()
    supervisor_files=sorted(set(n for n in tracked if n.endswith('.py'))|set(SUPERVISOR)|set(n for n in FILES if n.endswith('.py')))
    for n in supervisor_files:
        target=supervisor/n;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():target.chmod(0o600)
        target.write_bytes((ROOT/n).read_bytes())
    shutil.copytree(ROOT/'ops/demand',supervisor/'ops/demand',dirs_exist_ok=True)
    old=json.loads((ROOT/'docs/HERMES_OPERATIONAL_WINDOWS_BINDINGS.json').read_text());host={n:SHA(ROOT/n) for n in old['host_files']}
    windows={n:(old['windows_files'][n] if h==old['host_files'][n] else h) for n,h in host.items()}
    bindings={'profile':'operational-8797','host_files':host,'windows_files':windows}
    (dest/'windows-bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
    rows=[]
    for p in release.rglob('*'):
        if p.is_file():
            n=str(p.relative_to(release));prior=installed/n
            if not prior.exists() or SHA(prior)!=SHA(p):rows.append({'path':n,'before':SHA(prior) if prior.exists() else None,'after':SHA(p)})
    before=dest/'before-private'
    for row in rows:
        if row['before'] is not None:
            target=before/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(installed/row['path'],target)
    shutil.copyfile(active/'hermes-embedded.js',dest/'frontend.before.js')
    templates=dest/'service-templates';shutil.copytree(ROOT/'ops/demand',templates)
    result={'production_modified':False,'private_delta':rows,'frontend':{'target':str(active/'hermes-embedded.js'),'before':SHA(active/'hermes-embedded.js'),'after':SHA(ui/'hermes-embedded.js')},
      'windows_delta':[{'path':n,'before':old['windows_files'][n],'after':windows[n]} for n in windows if windows[n]!=old['windows_files'][n]],'windows_bindings_sha256':SHA(dest/'windows-bindings.json'),'activation_authorized':False,
      'files':{str(p.relative_to(dest)):SHA(p) for p in dest.rglob('*') if p.is_file()}}
    (dest/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');args=p.parse_args();r=prepare(args.destination);print(json.dumps({'prepared':True,'private_changed_files':len(r['private_delta']),'production_modified':False}))
