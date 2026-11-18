"""Generate/rehearse a reviewable patch in this worktree; NEVER applies production."""
import difflib,hashlib,json,subprocess,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/phase6';DEST.mkdir(exist_ok=True)
JARVIS=Path('/home/user/workspace/jarvis');GATEWAY=Path('/home/user/gateway')
JS=['backend.mjs','live.mjs','knowledge.mjs','voice-memory.mjs','voice-memory.py','store.py',
    'phase6-gateway.mjs','jarvis-session-auth.mjs','hermes-server-auth.mjs','hermes-voice-tools.mjs',
    'hermes-bridge-client.mjs','jarvis-hermes-experimental.mjs']
entries=[(ROOT/n,JARVIS/n) for n in JS]
entries += [(ROOT/'public'/n,GATEWAY/'public/jarvis'/n) for n in ('index.html','hermes-missions.js','hermes-missions.css')]
gateway=GATEWAY/'server.js';old_gateway=gateway.read_text()
new_gateway=old_gateway.replace("import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';", "import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';\nimport { mountJarvisPhase6 } from '/home/user/workspace/jarvis/phase6-gateway.mjs';")
new_gateway=new_gateway.replace('const HOST = process.env.HOST', 'const handleSecureJarvis = await mountJarvisPhase6(handleJarvis);\n\nconst HOST = process.env.HOST')
new_gateway=new_gateway.replace('return handleJarvis(req, res, url);','return handleSecureJarvis(req, res, url);')
assert old_gateway!=new_gateway and new_gateway.count('const handleSecureJarvis =')==1
records=[];patch=[];payloads=[]
for source,target in entries+[(None,gateway)]:
    before=target.read_bytes() if target.exists() else b''
    after=source.read_bytes() if source else new_gateway.encode()
    if before==after:continue
    rel=str(target).lstrip('/')
    patch.extend(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),
                                    fromfile='a/'+rel if before else '/dev/null',tofile='b/'+rel))
    records.append({'source':str(source.relative_to(ROOT)) if source else 'generated gateway mount',
                    'target':str(target),'before_sha256':hashlib.sha256(before).hexdigest() if before else None,
                    'after_sha256':hashlib.sha256(after).hexdigest(),'new_file':not target.exists()})
    payloads.append((rel,before,after))
text=''.join(patch);destination=DEST/'jarvis-phase6-production.patch';destination.write_text(text)
with tempfile.TemporaryDirectory(prefix='phase6-patch-rehearsal-') as temp:
    overlay=Path(temp)
    for rel,before,after in payloads:
        if before:
            p=overlay/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before)
    for mode in ('--dry-run',None):
        command=['patch','--batch','-p1','-d',str(overlay),'-i',str(destination)]
        if mode:command.insert(1,mode)
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Local overlay rehearsal failed: '+result.stdout+result.stderr)
    assert all((overlay/rel).read_bytes()==after for rel,_,after in payloads)
manifest={'mode':'prepared-not-authorized-not-deployed','files':records,'patch_sha256':hashlib.sha256(text.encode()).hexdigest(),
          'overlay_dry_run_passed':True,'overlay_apply_byte_exact':True,'production_writes':0,
          'controller_changes_already_in_isolated_worktree':['memory_manager/phase2/bridge.py','memory_manager/phase2/http_bridge.py','memory_manager/phase6/worker.py'],
          'features_default':{'JARVIS_SERVER_AUTH':'0','JARVIS_HERMES_ENABLED':'0','private_switch_enabled':False}}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'production_files':len(records),'overlay_rehearsal':True,'production_writes':0}))
