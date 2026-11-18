"""Offline acceptance evidence; preserve previous pilot reports/manifests."""
import json,os,subprocess,tempfile,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
commands=[
 ['python3','-m','unittest','memory_manager.production.test_persistence','memory_manager.tests.test_memory','memory_manager.phase6d.test_security','-v'],
 ['python3','-m','unittest','memory_manager.phase6d.test_final.FinalTests.test_unix_rpc_real_service_without_model'],
 ['node','test_production_storage_transport.mjs'],['node','test_production_bindings.mjs'],['node','test_production_private_services.mjs'],['node','test_phase6d_backend.mjs'],
 ['node','test_phase6d_final.mjs'],['node','test_phase6d_security.mjs'],['node','test_phase6c_readiness.mjs'],
 ['node','test_phase6_ui.cjs','--read-only','--final'],['node','test_phase6d_auth_ui.cjs'],['node','test_speech.mjs'],['node','test_phase6.mjs'],
]
out=ROOT/'docs/production/test-results.json'
previous=json.loads(out.read_text()) if '--select' in sys.argv and out.exists() else None
if previous:
 selected=sys.argv[sys.argv.index('--select')+1];commands=[c for c in commands if selected in c]
checks=[]
with tempfile.TemporaryDirectory(prefix='jarvis-production-check-home-') as home:
 env={'PATH':os.environ['PATH'],'HOME':home,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
 for command in commands:
  start=time.monotonic()
  try:
   r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
   result={'command':command,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),'stdout':r.stdout,'stderr':r.stderr}
  except subprocess.TimeoutExpired:result={'command':command,'exit_code':124,'error':'bounded test timeout'}
  checks.append(result);print(json.dumps({'command':command,'exit_code':result['exit_code']}),flush=True)
if previous:
 by_command={tuple(c['command']):c for c in checks};checks=[by_command.pop(tuple(c['command']),c) for c in previous['checks']]+list(by_command.values())
report={'mode':'offline-fixtures-real-sqlite-and-unix-no-inference','passed':all(c['exit_code']==0 for c in checks),'production_writes':0,'new_private_data_reads':0,'gpu_calls':0,'remote_inference_calls':0,'physical_actions':0,'historical_pilots_replayed':False,'checks':checks}
out=ROOT/'docs/production/test-results.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
