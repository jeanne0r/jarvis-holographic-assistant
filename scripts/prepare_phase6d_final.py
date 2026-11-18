"""Review-only finalization lots. Preserve all earlier manifests and pilot proofs."""
import difflib,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/phase6d/final';DEST.mkdir(exist_ok=True);J=Path('/home/user/workspace/jarvis');G=Path('/home/user/gateway')
def sha(b):return hashlib.sha256(b).hexdigest() if b is not None else None
matrix=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import {routeMatrix} from './gateway-route-policy.mjs';console.log(JSON.stringify(routeMatrix))"],cwd=ROOT,text=True))
(DEST/'route-matrix.json').write_text(json.dumps(matrix,indent=2)+'\n')
# These are independently reviewable source packages. No bootstrap of active
# server.js is generated while real service bindings/ownership are unapproved.
groups=[
 ('01-policy',[(J/n,ROOT/n) for n in ['hermes-server-auth.mjs','jarvis-session-auth.mjs','gateway-route-policy.mjs','gateway-security.mjs','gateway-security-mount.mjs','voice-session-owner.mjs']]),
 ('02-business',[(J/n,ROOT/n) for n in ['gateway-business.mjs','gateway-project-files.mjs','gateway-tool-authority.mjs','gateway-hybrid-authorized.mjs']]),
 ('03-codex-transport',[(J/n,ROOT/n) for n in ['codex-broker-client.mjs','codex-tool-proxy.mjs','codex-tools-broker.mjs']]),
 ('04-runtime',[(Path('/opt/jarvis-2/review')/p.relative_to(ROOT),p) for p in sorted((ROOT/'memory_manager').rglob('*')) if p.is_file() and p.suffix in {'.py','.sql'} and not p.name.startswith('test')]),
 ('05-hermes-composition',[(J/n,ROOT/n) for n in ['gateway-final-compose.mjs','phase6-gateway.mjs','hybrid-mission-admission.mjs','hermes-voice-tools.mjs','hermes-bridge-client.mjs','jarvis-hermes-experimental.mjs']]),
 ('06-ui-assets',[(G/'public/jarvis'/n,ROOT/'public'/n) for n in ['jarvis-auth.js','hermes-missions.js','hermes-missions.css','hermes-canonical.js','voice-router.js']]),
]
# Reuse unchanged baseline memory code: list its immutable hashes rather than
# duplicating it in the delta patch. Provisioning this release is still explicit.
baseline=[];delta=[]
for target,source in groups[3][1]:
 relative=str(source.relative_to(ROOT))
 original=subprocess.run(['git','show','6bb7c4e:'+relative],cwd=ROOT,capture_output=True)
 if original.returncode==0 and original.stdout==source.read_bytes():baseline.append({'source':relative,'target':str(target),'sha256':sha(original.stdout)})
 else:delta.append((target,source))
groups[3]=(groups[3][0],delta)
(DEST/'baseline-runtime-manifest.json').write_text(json.dumps({'commit':'6bb7c4e','files':baseline,'installation_authorized':False},indent=2)+'\n')
initial={p:p.read_bytes() if p.exists() else None for _,changes in groups for p,_ in changes};reports=[]
with tempfile.TemporaryDirectory(prefix='phase6d-final-overlay-') as tmp:
 root=Path(tmp)
 for name,changes in groups:
  chunks=[];files=[]
  for target,source in changes:
   before=initial[target];after=source.read_bytes();rel=str(target).lstrip('/')
   if before==after:continue
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
   if before is not None:p.write_bytes(before)
   chunks.extend(difflib.unified_diff((before or b'').decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+rel if before is not None else '/dev/null',tofile='b/'+rel,n=0))
   files.append({'source':str(source.relative_to(ROOT)),'target':str(target),'before_sha256':sha(before),'after_sha256':sha(after)})
  patch=DEST/(name+'.patch');patch.write_text(''.join(chunks))
  for reverse in [False,True]:
   result=subprocess.run(['patch','--batch',*(['-R'] if reverse else []),'-p1','-d',str(root),'-i',str(patch)],capture_output=True,text=True)
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
  assert all((root/str(p).lstrip('/')).read_bytes()==initial[p] if initial[p] is not None else not (root/str(p).lstrip('/')).exists() for p,_ in changes)
  reports.append({'lot':name,'patch_sha256':sha(patch.read_bytes()),'files':files,'forward_reverse_copy_verified':True})
assert all((p.read_bytes() if p.exists() else None)==b for p,b in initial.items())
manifest={'mode':'review-only-source-packages-not-activation','active_entry_patch_ready':False,'reason':'real service bindings, historical ownership and distinct OS identities not provisioned/validated','route_method_pairs':len(matrix),'unchanged_baseline_files':len(baseline),'lots':reports,'production_writes':0,'preimages_unchanged':True,'dependencies':{'02-business':['01-policy'],'03-codex-transport':['01-policy'],'04-runtime':['distinct approved service identities and storage paths'],'05-hermes-composition':['01-policy','02-business','03-codex-transport','04-runtime'],'06-ui-assets':['01-policy','05-hermes-composition for Hermes panel']},'default_flags':{'history':False,'admission':False,'hybrid':False,'remote_budget_chf':0}}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'source_lots':len(reports),'files':sum(len(r['files']) for r in reports),'copy_restore_verified':True,'active_entry_patch_ready':False,'production_writes':0}))
