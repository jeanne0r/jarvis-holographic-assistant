"""Review artifacts only; no deployment, backend execution or pilot replay."""
import difflib, hashlib, json, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/phase6c'; DEST.mkdir(exist_ok=True)
J=Path('/home/user/workspace/jarvis'); G=Path('/home/user/gateway')
def sha(b): return hashlib.sha256(b).hexdigest() if b is not None else None
libs=['jarvis-session-auth.mjs','hermes-server-auth.mjs','hermes-voice-tools.mjs','hermes-bridge-client.mjs','jarvis-hermes-experimental.mjs','hybrid-mission-admission.mjs','phase6-gateway.mjs']
changes=[(J/n,(ROOT/n).read_bytes()) for n in libs]
old=(G/'server.js').read_text()
new=old.replace("import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';", "import { handleJarvis } from '/home/user/workspace/jarvis/backend.mjs';\nimport { mountJarvisPhase6 } from '/home/user/workspace/jarvis/phase6-gateway.mjs';")
new=new.replace('const HOST = process.env.HOST','const handleSecureJarvis = await mountJarvisPhase6(handleJarvis);\n\nconst HOST = process.env.HOST').replace('return handleJarvis(req, res, url);','return handleSecureJarvis(req, res, url);')
assert old!=new
changes += [(J/n,(ROOT/n).read_bytes()) for n in ['backend.mjs','voice-memory.py','store.py']]
changes += [(G/'server.js',new.encode())]
changes += [(G/'public/jarvis'/n,(ROOT/'public'/n).read_bytes()) for n in ['index.html','hermes-missions.js','hermes-missions.css','voice-router.js']]
initial={p:p.read_bytes() if p.exists() else None for p,_ in changes}
files=[]
with tempfile.TemporaryDirectory(prefix='phase6c-review-') as tmp:
 overlay=Path(tmp)
 for p,b in initial.items():
  if b is not None:
   target=overlay/str(p).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
 for name,group in [('01-inert-libraries',changes[:7]),('02-incomplete-activation-review-NO-GO',changes[7:])]:
  diff=[]; entries=[]
  for p,after in group:
   before=initial[p]; rel=str(p).lstrip('/')
   diff.extend(difflib.unified_diff((before or b'').decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+rel if before is not None else '/dev/null',tofile='b/'+rel))
   entries.append({'target':str(p),'before_sha256':sha(before),'after_sha256':sha(after)})
  patch=DEST/(name+'.patch'); patch.write_text(''.join(diff))
  for opts in [[],['-R']]:
   result=subprocess.run(['patch','--batch',*opts,'-p1','-d',str(overlay),'-i',str(patch)],capture_output=True,text=True)
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
  files.append({'name':name,'sha256':sha(patch.read_bytes()),'files':entries,'forward_reverse_byte_verified':True})
  assert all((overlay/str(p).lstrip('/')).read_bytes()==b if b is not None else not (overlay/str(p).lstrip('/')).exists() for p,b in initial.items())
assert all((p.read_bytes() if p.exists() else None)==b for p,b in initial.items())
manifest={'mode':'review-only-not-deployed','production_activation':'NO-GO','reason':'global gateway routes, legacy compatibility and executor isolation incomplete','production_writes':0,'production_preimages_unchanged':True,'unique_targets':len(initial),'stages':files,'defaults':{k:'0' for k in ['JARVIS_SERVER_AUTH','JARVIS_HERMES_ENABLED','JARVIS_HERMES_HISTORY','JARVIS_HERMES_HYBRID','JARVIS_HERMES_NATIVE_LIVE']},'inert_prototypes':{n:sha((ROOT/n).read_bytes()) for n in ['public/hermes-canonical.js','memory_manager/phase6c/canonical_metadata.py']}}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
