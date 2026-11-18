"""Prepare staged review patches; reads production, writes only isolated artifacts."""
import difflib, hashlib, json, os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/phase6b'
J=Path('/home/user/workspace/jarvis');G=Path('/home/user/gateway')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def source(name):return (ROOT/name).read_bytes()
# The staged mount authenticates /ask but leaves synthetic delegation disabled.
foundation=source('phase6-gateway.mjs').replace(b"hybridEnabled:env.JARVIS_HERMES_HYBRID==='1'",b'hybridEnabled:false')
assert foundation!=source('phase6-gateway.mjs')
libs=['jarvis-session-auth.mjs','hermes-server-auth.mjs','hermes-voice-tools.mjs','hermes-bridge-client.mjs','jarvis-hermes-experimental.mjs','hybrid-mission-admission.mjs']
old=(G/'server.js').read_text()
new=old.replace("import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';", "import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';\nimport { mountJarvisPhase6 } from '/home/user/workspace/jarvis/phase6-gateway.mjs';")
new=new.replace('const HOST = process.env.HOST','const handleSecureJarvis = await mountJarvisPhase6(handleJarvis);\n\nconst HOST = process.env.HOST')
new=new.replace('return handleJarvis(req, res, url);','return handleSecureJarvis(req, res, url);')
assert old!=new and new.count('const handleSecureJarvis =')==1
stages=[
 ('01-inert-server-libraries',[(J/n,source(n)) for n in libs]+[(J/'phase6-gateway.mjs',foundation)]),
 ('02-authenticated-legacy-routes',[(J/n,source(n)) for n in ['backend.mjs','voice-memory.py','store.py']]+[(G/'server.js',new.encode())]),
 ('03-holographic-panel',[(G/'public/jarvis'/n,source('public/'+n)) for n in ['index.html','hermes-missions.js','hermes-missions.css','voice-router.js']]),
 ('04-hybrid-opt-in',[(J/'phase6-gateway.mjs',source('phase6-gateway.mjs'))]),
]
DEST.mkdir(exist_ok=True)
state={};initial={};report=[]
with tempfile.TemporaryDirectory(prefix='jarvis-6b-overlay-') as tmp:
 overlay=Path(tmp)
 for name,changes in stages:
  patch=[];files=[]
  for target,after in changes:
   if target not in state:
    initial[target]=target.read_bytes() if target.exists() else None
    state[target]=initial[target]
    if state[target] is not None:
     p=overlay/str(target).lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(state[target])
   before=state[target]
   if before==after:continue
   rel=str(target).lstrip('/')
   patch.extend(difflib.unified_diff((before or b'').decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+rel if before is not None else '/dev/null',tofile='b/'+rel))
   files.append({'target':str(target),'before_sha256':digest(before) if before is not None else None,'after_sha256':digest(after)})
   state[target]=after
  data=''.join(patch).encode();path=DEST/(name+'.patch');path.write_bytes(data)
  for opts in [['--dry-run'],[]]:
   result=subprocess.run(['patch','--batch',*opts,'-p1','-d',str(overlay),'-i',str(path)],capture_output=True,text=True)
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
  report.append({'stage':name,'patch_sha256':digest(data),'files':files,'forward_overlay_passed':True})
 assert all((overlay/str(p).lstrip('/')).read_bytes()==v for p,v in state.items())
 # Exercise the exact minimal patched backend against original untouched modules.
 # Copy source files only: never data/, .env, credentials or conversations.
 lab=overlay/str(J).lstrip('/')
 for baseline in [*J.glob('*.mjs'),*J.glob('*.py')]:
  target=lab/baseline.name
  if not target.exists():target.write_bytes(baseline.read_bytes())
 for name in ['test_phase6_hybrid.mjs','test_phase6_hybrid_loader.mjs']:
  (lab/name).write_bytes(source(name))
 env={'PATH':os.environ['PATH'],'HOME':str(overlay/'empty-home'),'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
 result=subprocess.run(['node','--experimental-loader',str(lab/'test_phase6_hybrid_loader.mjs'),str(lab/'test_phase6_hybrid.mjs')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
 if result.returncode:raise RuntimeError('Minimal hybrid overlay failed: '+result.stdout+result.stderr)
 overlay_test=json.loads(result.stdout.strip().splitlines()[-1])
 assert overlay_test['passed'] and overlay_test['actual_backend_ask']
 for item in reversed(report):
  result=subprocess.run(['patch','--batch','-R','-p1','-d',str(overlay),'-i',str(DEST/(item['stage']+'.patch'))],capture_output=True,text=True)
  if result.returncode:raise RuntimeError('Reverse rehearsal failed: '+result.stdout+result.stderr)
 assert all((overlay/str(p).lstrip('/')).read_bytes()==v if v is not None else not (overlay/str(p).lstrip('/')).exists() for p,v in initial.items())
 assert all((p.read_bytes() if p.exists() else None)==v for p,v in initial.items())
manifest={'mode':'prepared-not-deployed','stages':report,'unique_targets':len(initial),'production_writes':0,'forward_and_reverse_overlay_passed':True,'production_preimages_unchanged':True,'minimal_hybrid_overlay_test':overlay_test,'defaults':{'JARVIS_SERVER_AUTH':'0','JARVIS_HERMES_ENABLED':'0','JARVIS_HERMES_HYBRID':'0','JARVIS_HERMES_NATIVE_LIVE':'0'},'activation_requires_new_approval':True}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='stages'}))
