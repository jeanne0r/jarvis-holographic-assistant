"""Build only, from the verified installed release. Never changes live files."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
from .prepare_embedded_panel import assets, replace_once, ROOT

EXTRA = ['memory_manager/phase6/operational.py', 'memory_manager/phase6/worker.py',
    'memory_manager/phase4/__init__.py', 'memory_manager/phase4/worker.py',
    'memory_manager/phase6d/__init__.py', 'memory_manager/phase6d/heartbeat.py',
    'memory_manager/phase6d/database.py', 'memory_manager/phase6d/evidence.py',
    'memory_manager/phase6c/__init__.py', 'memory_manager/phase6c/canonical_metadata.py',
    'memory_manager/phase3/model_gate.py', 'memory_manager/phase3/mcp.py',
    'memory_manager/phase2/budgets.py', 'memory_manager/phase2/mcp.py',
    'memory_manager/phase2/skill_registry.py', 'memory_manager/hermes_mcp.py']
UPDATED = ['jarvis-session-auth.mjs', 'hermes-private-human-policy.mjs', 'hermes-human-delegation.mjs', 'hermes-mission-policy.mjs', 'hermes-embedded-api.mjs', 'hermes-embedded-contract.mjs', 'ops/pilot-embedded.mjs']
SUPERVISOR = ['scripts/run_interactive_hermes.py', 'scripts/pilot_phase4_windows.py',
    'scripts/pilot_phase5_windows.py', 'scripts/pilot_phase6b_panel.py',
    'scripts/pilot_existing_ollama.py', 'scripts/audit_gpu.py',
    'memory_manager/phase4/windows.py', 'memory_manager/phase4/native_trial.py',
    'memory_manager/phase4/allowance.py', 'memory_manager/phase4/job.py',
    'memory_manager/phase5/source_attestation.py',
    'ops/phase4-run-hermes-windows.py', 'ops/phase4-run-ollama-windows.py']


def operational_assets():
    js, css = assets()
    js = replace_once(js, "create.type='button';create.hidden=true;", """create.type='button';create.hidden=true;
 const objective=make('textarea','',content);objective.id='hermesExplicitObjective';objective.maxLength=2000;objective.placeholder='Demande explicite · outils et mémoire synthétiques seulement';objective.hidden=true;
 const submit=make('button','Soumettre cette demande',content);submit.type='button';submit.hidden=true;let textKey=null;
 submit.onclick=async()=>{if(!objective.value.trim()||objective.value.length>2000)return;submit.disabled=true;textKey??=crypto.randomUUID();try{await request(endpoint('missions'),{method:'POST',headers:{'content-type':'application/json','idempotency-key':textKey},body:JSON.stringify({objective:objective.value})});textKey=null;objective.value='';await refreshList()}catch(e){status.textContent=e.message+' Consulte l’historique avant de réessayer.'}finally{submit.disabled=false}};
""")
    js = replace_once(js, 'admissionsEnabled=config.enabled===true;', "admissionsEnabled=config.enabled===true;globalThis.JarvisHermesVoiceEnabled=config.voiceEnabled===true;objective.hidden=submit.hidden=!(config.textEnabled===true&&admissionsEnabled&&identity.roles.includes('missions.create'));")
    js = replace_once(js, "  create.disabled=!admissionsEnabled", "  create.hidden=!admissionsEnabled;create.disabled=!admissionsEnabled")
    js = replace_once(js, "identity=null;featureActive=false;", "identity=null;featureActive=false;globalThis.JarvisHermesVoiceEnabled=false;objective.value='';objective.hidden=submit.hidden=true;")
    js = js.replace('states[m.state]||m.state', "m.dispatch_state==='unknown'?states.unknown:(states[m.state]||m.state)")
    js = replace_once(js, "  canonical.textContent='';", """  const fragments=[],manifests=[];
  for(const e of result.events||[]){if(['result_part','result_complete','output_limit'].includes(e.kind)){const row=JSON.parse(e.data);if(e.kind==='result_part')fragments.push(row);else if(e.kind==='result_complete')manifests.push(row);else detail.textContent+='\\nRésultat limité explicitement : '+row.reason}}
  if(manifests.length===1){const manifest=manifests[0];fragments.sort((a,b)=>a.index-b.index);if(fragments.length!==manifest.parts||fragments.some((r,i)=>r.index!==i))throw Error('Résultat complet incomplet');const output=fragments.map(r=>r.output).join('');const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(output)))).map(v=>v.toString(16).padStart(2,'0')).join('');if(hash!==manifest.sha256)throw Error('Empreinte du résultat invalide');detail.textContent=(states[m.state]||m.state)+'\\n'+output;}
  canonical.textContent='';""")
    js += '''
// Used by the existing jarvisAsk path, never touches microphone/audio transport.
globalThis.JarvisHermesHybrid=Object.freeze({request(data){
 if(!/herm[eèéê]s/iu.test(data.question.normalize('NFKC')))return undefined;
 const denied=answer=>({answer,speech:answer,sources:[],sourceIds:[],action:null});
 if(globalThis.JarvisHermesVoiceEnabled!==true)return Promise.resolve(denied('La délégation Hermes n’est pas activée. Utilise le panneau des missions.'));
 const identity=globalThis.JarvisHermesAuth.identity();
 if(!identity?.roles?.includes('missions.create'))return Promise.resolve(denied('Connexion et autorisation de mission requises.'));
 return globalThis.JarvisHermesAuth.request('hybrid/ask?space='+encodeURIComponent(identity.spaces[0]),{method:'POST',headers:{'content-type':'application/json'},signal:data.signal,body:JSON.stringify({question:data.question,archive:data.archive})});
}});
'''
    return js, css


def prepare(destination, *, installed=Path('/opt/jarvis-hermes-pilot'), gateway=Path('/home/user/gateway'), source=Path('/home/user/workspace/jarvis')):
    dest = Path(destination)
    if dest.exists(): raise FileExistsError('Never overwrite a preparation')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    installed = Path(installed)
    known = json.loads((installed / 'deployment-files.json').read_text())
    if any(sha(installed / n) != h for n, h in known.items()): raise PermissionError('Installed code drift')
    dest.mkdir(parents=True); release = dest / 'pilot-release'; shutil.copytree(installed, release)
    for name in EXTRA + UPDATED:
        target = release / name; target.parent.mkdir(parents=True, exist_ok=True)
        # Installed files are read-only. Modify the candidate, preserving originals.
        if target.exists(): target.chmod(0o600)
        shutil.copyfile(ROOT / name, target)
    entry = release / 'memory_manager/phase6/interactive.py'; entry.chmod(0o600)
    text = entry.read_text()
    text = replace_once(text, " cfg=json.loads(path.read_text());folder=path.parent.resolve()", " cfg=json.loads(path.read_text());folder=path.parent.resolve()\n if cfg.get('operations') is not None:\n  from .operational import run as operational_run\n  return operational_run(config)")
    entry.write_text(text)
    prior = release / 'docs/pilot-interactive/manifest.json'; prior.chmod(0o600)
    manifest = json.loads(prior.read_text()); names = sorted(set(manifest['files']) | set(EXTRA) | set(UPDATED))
    manifest['files'] = {n: sha(release / n) for n in names}
    manifest['purpose'] = 'Operational composition; all new flags default false; synthetic memory only'
    prior.write_text(json.dumps(manifest, indent=2) + '\n')
    deployment = release / 'deployment-files.json'; deployment.chmod(0o600)
    deployment.write_text(json.dumps({str(p.relative_to(release)): sha(p) for p in sorted(release.rglob('*')) if p.is_file() and p != deployment}, indent=2) + '\n')
    frontend = dest / 'frontend'; frontend.mkdir(); js, css = operational_assets()
    shutil.copyfile(gateway / 'public/jarvis/index.html', frontend / 'index.html')
    (frontend / 'hermes-embedded.js').write_text(js); (frontend / 'hermes-embedded.css').write_text(css)
    old = (gateway / 'public/jarvis/app.js').read_text()
    if old != (source / 'public/app.js').read_text(): raise PermissionError('Served/source app differ')
    anchor = " const r=await post('ask',{question:q,archive:voice?options.archive:window.jarvisArchive?.writtenRequest(askSpace),"
    revised = replace_once(old, anchor, " const requestArchive=voice?options.archive:window.jarvisArchive?.writtenRequest(askSpace);const delegated=window.JarvisHermesHybrid?.request({question:q,archive:requestArchive,signal:controller.signal});\n const r=await (delegated??post('ask',{question:q,archive:requestArchive,")
    revised = replace_once(revised, "},controller.signal);if(serial!==requestSerial", "},controller.signal));if(serial!==requestSerial")
    (frontend / 'app.js').write_text(revised)
    (dest / 'hybrid-client.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True), revised.splitlines(True), fromfile='a/public/app.js', tofile='b/public/app.js')))
    gw = dest / 'gateway'; gw.mkdir()
    for name in ['hermes-embedded-relay.mjs', 'hermes-embedded-contract.mjs', 'hermes-human-delegation.mjs']: shutil.copyfile(ROOT / name, gw / name)
    targets = {gateway / n: gw / n for n in ['hermes-embedded-relay.mjs', 'hermes-embedded-contract.mjs', 'hermes-human-delegation.mjs']}
    targets.update({gateway / 'public/jarvis' / n: frontend / n for n in ['hermes-embedded.js', 'hermes-embedded.css', 'app.js']})
    targets[source / 'public/app.js'] = frontend / 'app.js'
    result = {'installed_manifest_sha256': sha(installed / 'deployment-files.json'), 'flags_default': {'enabled': True, 'admissionEnabled': False, 'voiceEnabled': False},
        'supervisor_sources': {n: sha(ROOT / n) for n in SUPERVISOR},
        'gateway_patch': [{'target': str(p), 'before': sha(p) if p.exists() else None, 'artifact': str(a.relative_to(dest)), 'after': sha(a)} for p, a in targets.items()],
        'files': {str(p.relative_to(dest)): sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}, 'production_modified': False}
    (dest / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('destination'); args = p.parse_args()
    result = prepare(args.destination); print(json.dumps({'prepared': True, 'files': len(result['files']), 'production_modified': False}))
