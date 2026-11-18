"""Finalization checks; never run historical Hermes pilots or paid providers."""
import json,os,subprocess,tempfile,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
commands=[['python3','scripts/prepare_phase6d_final.py'],['node','test_phase6d_final.mjs'],['python3','-m','unittest','memory_manager.phase6d.test_final','memory_manager.phase6d.test_security','-v'],['node','test_phase6_ui.cjs','--read-only','--final'],['node','test_phase6d_auth_ui.cjs'],['node','test_phase6d_security.mjs'],['node','test_phase6c_readiness.mjs'],['node','test_speech.mjs'],['node','test_phase6.mjs']]
out=ROOT/'docs/phase6d/final/test-results.json'
previous=json.loads(out.read_text()) if '--select' in sys.argv else None
if previous:
 selected=sys.argv[sys.argv.index('--select')+1];commands=[r['command'] for r in previous['checks'] if selected in r['command']]
results=[]
with tempfile.TemporaryDirectory(prefix='phase6d-final-home-') as home:
 env={'PATH':os.environ['PATH'],'HOME':home,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
 for command in commands:
  started=time.monotonic()
  try:
   p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
   r={'command':command,'exit_code':p.returncode,'seconds':round(time.monotonic()-started,3),'stdout':p.stdout,'stderr':p.stderr}
  except subprocess.TimeoutExpired:r={'command':command,'exit_code':124,'error':'timeout'}
  results.append(r);print(json.dumps({'command':command,'exit_code':r['exit_code']}),flush=True)
if previous:
 replacements={tuple(r['command']):r for r in results}
 results=[replacements.get(tuple(r['command']),r) for r in previous['checks']]
report={'mode':'synthetic-local-plus-real-namespaces-offline-cli-help','passed':all(r['exit_code']==0 for r in results),'gpu_calls':0,'real_inference_calls':0,'remote_api_cost_chf':0,'production_writes':0,'physical_actions':0,'historical_pilots_replayed':False,'checks':results}
out.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
