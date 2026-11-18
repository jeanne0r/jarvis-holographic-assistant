"""Produce review patches, hashes and byte-exact copy rollback. No active writes."""
import difflib,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/production';DEST.mkdir(exist_ok=True);BASE='7fda6ae'
def digest(b):return hashlib.sha256(b).hexdigest()
groups={
 '01-persistence':['ops/production-storage-migrate.py','gateway-persistent-client.mjs','gateway-account-bindings.mjs','gateway-fridge-format.mjs']+[str(p.relative_to(ROOT)) for p in sorted((ROOT/'memory_manager/production').glob('*.py')) if not p.name.startswith(('test','fixture'))],
 '02-broker-ipc':['memory_manager/phase6d/broker/main.py','memory_manager/phase6d/broker/transport.py'],
 '03-power':['s9-power-service.mjs','s9-power-main.mjs'],
 '04-entry':['gateway-production-entry.mjs','gateway-production-main.mjs','gateway-service-transport.mjs','gateway-compatibility-service.mjs','gateway-business.mjs','gateway-hybrid-authorized.mjs','gateway-tool-authority.mjs','gateway-security.mjs','backend.mjs','core-settings.mjs'],
 '05-service-templates':[str(p.relative_to(ROOT)) for p in sorted((ROOT/'security/production').glob('*.in'))],
}
lots=[]
with tempfile.TemporaryDirectory(prefix='jarvis-install-review-') as temp:
 root=Path(temp)
 for name,names in groups.items():
  chunks=[];files=[];initial={}
  for n in names:
   p=ROOT/n;after=p.read_bytes();old=subprocess.run(['git','show',BASE+':'+n],cwd=ROOT,capture_output=True)
   before=old.stdout if old.returncode==0 else None;initial[n]=before
   target=root/n;target.parent.mkdir(parents=True,exist_ok=True)
   if before is not None:target.write_bytes(before)
   chunks.extend(difflib.unified_diff((before or b'').decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+n if before is not None else '/dev/null',tofile='b/'+n,n=3))
   files.append({'source':n,'release_target':'/opt/jarvis-2/release/'+n,'before_sha256':digest(before) if before is not None else None,'after_sha256':digest(after)})
  patch=DEST/(name+'.patch');patch.write_text(''.join(chunks))
  for reverse in [False,True]:
   p=subprocess.run(['patch','--batch',*(['-R'] if reverse else []),'-p1','-d',str(root),'-i',str(patch)],capture_output=True,text=True)
   if p.returncode:raise RuntimeError(p.stdout+p.stderr)
  assert all((root/n).read_bytes()==b if b is not None else not(root/n).exists() for n,b in initial.items())
  lots.append({'lot':name,'patch_sha256':digest(patch.read_bytes()),'files':files,'copy_apply_reverse_verified':True})
sources={}
for name,path in [('gateway','/home/user/gateway/server.js'),('legacy_store',str(ROOT/'store.py')),('voice_facts',str(ROOT/'voice-memory.py')),('german_ai','/home/user/workspace/allemand-en-poche/ai.mjs')]:sources[name]={'source_path':path,'sha256':digest(Path(path).read_bytes())}
# The complete previous code release remains a dependency. A delta is not an installer.
manifest={'baseline_commit':BASE,'mode':'review-only-never-applied-to-active-paths','lots':lots,'code_contract_sources':sources,'production_activation_ready':False,'blockers':['dedicated Codex authentication/provider not validated','complete isolated auxiliary service hosts and image inference path not composed','independent physical approval transport and single-writer migration not commissioned','real ownership mapping, OS identities, IPC and network policies unapproved'],'production_writes':0,'default_flags':{'history':False,'admission':False,'hybrid':False,'remote_api_budget_chf':0}}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'lots':len(lots),'files':sum(len(l['files']) for l in lots),'copy_rollback_verified':True,'production_activation_ready':False}))
