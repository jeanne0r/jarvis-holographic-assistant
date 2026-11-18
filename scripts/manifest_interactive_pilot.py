"""New manifest; never rewrite P6-L proofs or overwrite verified source files."""
import hashlib,json,subprocess
from pathlib import Path
from scripts.prepare_interactive_pilot import ROOT,DEST,FILES,sha
REASONS={
 'jarvis-session-auth.mjs':'Session handles, live permission/revocation checks and reviewed /api cookie scope; eefa9a2 + 6bb7c4e.',
 'hermes-bridge-client.mjs':'Canonical provenance endpoint and bounded worker heartbeat transport; 520c2b6.',
 'jarvis-hermes-experimental.mjs':'Canonical metadata appended separately to the original model result; 520c2b6.',
 'phase6-gateway.mjs':'History consultation independent of admission; topology pinned while sessions can be revoked; eefa9a2.',
 'backend.mjs':'Per-human voice session ownership and trusted private HTTPS origin; 6bb7c4e + 7847655. Not imported by the pilot.',
 'public/index.html':'Standalone auth client and canonical formatter loaded before the missions panel; 6bb7c4e + 520c2b6. Full Jarvis page not served by this pilot.',
 'public/hermes-missions.js':'Auth decoupling, history without admission, canonical metadata, availability and prudent restart states; eefa9a2 + 6bb7c4e + 520c2b6.'}
def main():
 old=json.loads((ROOT/'docs/phase6b/patch-manifest.json').read_text());final={r['target']:r for s in old['stages'] for r in s['files']};diff=[]
 for target,row in final.items():
  p=Path(target);relative=('public/'+p.name if p.parent==Path('/home/user/gateway/public/jarvis') else p.name);source=ROOT/relative
  if not source.is_file() or p.name=='server.js' or sha(source)==row['after_sha256']:continue
  if relative not in REASONS:raise PermissionError('Unreviewed difference: '+relative)
  committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=ROOT)
  if committed!=source.read_bytes():raise PermissionError('Uncommitted change to audited source')
  origin=None
  for commit in subprocess.check_output(['git','rev-list','HEAD','--',relative],cwd=ROOT,text=True).splitlines():
   b=subprocess.run(['git','show',commit+':'+relative],cwd=ROOT,capture_output=True)
   if b.returncode==0 and hashlib.sha256(b.stdout).hexdigest()==row['after_sha256']:origin=commit;break
  if origin is None:raise PermissionError('Historical fingerprint not found in Git')
  diff.append({'file':relative,'historical_sha256':row['after_sha256'],'historical_source_commit':origin,'current_sha256':sha(source),'origin':REASONS[relative],'commits_since_p6_l2':subprocess.check_output(['git','log','--format=%h %s','c21e915..HEAD','--',relative],cwd=ROOT,text=True).splitlines(),'decision':'preserve current committed source'})
 if len(diff)!=7:raise PermissionError('Expected seven audited differences')
 DEST.mkdir(exist_ok=True)
 report={'mode':'synthetic-interactive-queue-only','audit_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'historical_manifest_sha256':sha(ROOT/'docs/phase6b/patch-manifest.json'),'historical_manifest_modified':False,'differences':diff,'files':{p:sha(ROOT/p) for p in FILES},'installation_authorized':False,'dispatch_enabled':False,'limits_per_mission':{'calls':6,'local_tokens':98304,'seconds':240,'attempts':1,'remote_cost_chf':0}}
 (DEST/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'audited_differences':len(diff),'pinned_runtime_files':len(FILES),'historical_manifest_modified':False}))
if __name__=='__main__':main()
