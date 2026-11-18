"""Read-only/offline readiness. Does not start any service or authorize a pilot."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=json.loads((ROOT/'docs/phase6b/patch-manifest.json').read_text())
 seen=set();checks=[]
 for stage in manifest['stages']:
  checks.append({'check':stage['stage']+' patch integrity','passed':sha(ROOT/'docs/phase6b'/ (stage['stage']+'.patch'))==stage['patch_sha256']})
  for item in stage['files']:
   p=Path(item['target'])
   if str(p) in seen:continue
   seen.add(str(p));checks.append({'check':'production preimage '+str(p),'passed':(sha(p) if p.exists() else None)==item['before_sha256']})
 for name in ['codex-voice.js','app.js','live.js']:
  checks.append({'check':'unchanged conversation/audio '+name,'passed':sha(ROOT/'public'/name)==sha(Path('/home/user/gateway/public/jarvis')/name)})
 engine=json.loads(Path('/home/user/workspace/jarvis/data/core-engine.json').read_text()).get('engine')
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
 checks.extend([{'check':'active hybrid configuration','passed':engine=='hybrid'},{'check':'isolated worktree branch','passed':branch=='codex/jarvis-2-memory-20261113'}])
 passed=all(row['passed'] for row in checks)
 result={'passed':passed,'checks':checks,'pilot_authorized':False,'windows_started':False,'production_writes':0,'private_content_read':False,'additional_remote_budget_chf':0}
 (ROOT/'docs/JARVIS_2_PHASE6B_PREFLIGHT_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':passed,'checks':len(checks),'pilot_authorized':False,'windows_started':False,'production_writes':0}))
 return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
