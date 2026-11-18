"""Bounded offline readiness checks; never runs completed hardware pilots."""
import json, os, subprocess, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
commands=[['python3','-m','unittest','memory_manager.phase6c.test_readiness','-v'],['node','test_phase6c_readiness.mjs'],['node','test_phase6_ui.cjs','--read-only'],['node','test_speech.mjs'],['node','test_phase6.mjs']]
results=[]
with tempfile.TemporaryDirectory(prefix='phase6c-home-') as home:
 env={'PATH':os.environ['PATH'],'HOME':home,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
 for cmd in commands:
  start=time.monotonic()
  try:
   p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
   item={'command':cmd,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3),'stdout':p.stdout,'stderr':p.stderr}
  except subprocess.TimeoutExpired:
   item={'command':cmd,'exit_code':124,'seconds':round(time.monotonic()-start,3),'error':'timeout'}
  results.append(item)
  print(json.dumps({'command':cmd,'exit_code':item['exit_code']}),flush=True)
report={'mode':'offline-synthetic','gpu_calls':0,'windows_starts':0,'production_writes':0,'remote_api_cost_chf':0,'completed_pilots_replayed':False,'passed':all(x['exit_code']==0 for x in results),'checks':results}
(ROOT/'docs/JARVIS_2_PHASE6C_TEST_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
