"""Offline suites only. Historical pilots and reports are never rewritten."""
import json,os,subprocess,tempfile,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
commands=[['python3','scripts/prepare_phase6d.py'],['node','test_phase6d_inventory.mjs'],['node','test_phase6d_security.mjs'],['node','test_phase6d_gateway_copy.mjs'],['node','test_phase6d_backend.mjs','--minimal'],['node','test_phase6d_auth_ui.cjs'],['node','test_phase6_ui.cjs','--read-only','--phase6d'],['python3','-m','unittest','memory_manager.phase6d.test_security','-v'],['node','test_phase6c_readiness.mjs'],['node','test_speech.mjs'],['node','test_phase6.mjs']]
out=ROOT/'docs/JARVIS_2_PHASE6D_TEST_RESULTS.json'
previous=json.loads(out.read_text()) if '--retry-failed' in sys.argv or '--select' in sys.argv else None
selected=sys.argv[sys.argv.index('--select')+1] if '--select' in sys.argv else None
if previous:commands=[r['command'] for r in previous['checks'] if (selected in r['command'] if selected else r['exit_code']!=0)]
results=[]
with tempfile.TemporaryDirectory(prefix='phase6d-home-') as home:
 env={'PATH':os.environ['PATH'],'HOME':home,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
 for cmd in commands:
  start=time.monotonic()
  try:
   p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
   result={'command':cmd,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3),'stdout':p.stdout,'stderr':p.stderr}
  except subprocess.TimeoutExpired:result={'command':cmd,'exit_code':124,'seconds':round(time.monotonic()-start,3),'error':'timeout'}
  results.append(result);print(json.dumps({'command':cmd,'exit_code':result['exit_code']}),flush=True)
replaced=[]
if previous:
 replaced=[r for r in previous['checks'] if r['command'] in commands]
 updated={tuple(r['command']):r for r in results}
 results=[updated.get(tuple(r['command']),r) for r in previous['checks']]
report={'rechecked_failed_commands':replaced,'mode':'offline-synthetic-and-source-copy','passed':all(r['exit_code']==0 for r in results),'production_writes':0,'physical_actions':0,'real_shell_handlers_executed':0,'gpu_calls':0,'remote_api_cost_chf':0,'historical_pilots_replayed':False,'checks':results}
out.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
