"""Explicit, temporary native Windows pilot. No downloads, production data or paid provider."""
import argparse,base64,json,pathlib,subprocess,sys,time,threading,uuid
ROOT=pathlib.Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from scripts.pilot_existing_ollama import probe,LISTENER,SSH,HOST
from scripts.audit_gpu import collect
from memory_manager.phase2.local_model import ModelConfig,PrivateHTTP
from memory_manager.phase4.native_trial import run

def main(*,run_native=None,approval_path=None,setup_proof=None):
 p=argparse.ArgumentParser();p.add_argument('--approved',action='store_true',required=True);p.add_argument('--output',required=True);args=p.parse_args()
 destination=(ROOT/args.output).resolve()
 if destination.parent!=ROOT/'docs' or destination.exists() or destination.suffix!='.json':raise SystemExit('New docs JSON evidence only')
 if setup_proof:
  from scripts.egress_selftest import verify
  verify(setup_proof,mode='mission') # live egress proof in the worker's own cgroup
 elif not json.loads((ROOT/'data/phase4/admission.json').read_text()).get('passed'):raise SystemExit('Actual prechecks required')
 report={'started_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'downloads':0,'paid_api_calls':0,'samples':[],'cleanup':{}}
 process=None;stop=threading.Event();sampler=None;trial=uuid.uuid4().hex
 def admin(script):return probe(script)
 try:
  if admin(LISTENER)['listening']:raise RuntimeError('Pre-existing Ollama; defer without stopping it')
  report['baseline']=collect()
  # 18.11 (User): mining in parallel; VRAM decides.
  if not report['baseline'].get('available') or report['baseline']['free_mib']<8500:raise RuntimeError('GPU unavailable; defer')
  allowance=json.loads((pathlib.Path(approval_path) if approval_path else ROOT/'data/phase4/window.json').read_text())
  remaining=int(allowance['expires_at']-time.time())
  if remaining<90 or allowance.get('closed',False) is not False or allowance['missions']>=4:
   raise PermissionError('Approved pilot window closed, exhausted or insufficient')
  process=subprocess.Popen(SSH+[HOST,r'C:\JarvisHermesLab\runtime\Scripts\python.exe -I C:\JarvisHermesLab\app\ops\phase4-run-ollama-windows.py --approved --trial-id '+trial+' --seconds '+str(min(1800,remaining))],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  for _ in range(20):
   identity=admin(LISTENER)
   if identity['listening']:break
   if process.poll() is not None:raise RuntimeError('Owned Ollama supervisor exited')
   time.sleep(1)
  else:raise TimeoutError('Ollama listener unavailable')
  if identity['addresses']!=['127.0.0.1']:raise RuntimeError('Unexpected Ollama exposure')
  report['server_identity']=identity
  # Tunnel creation and teardown live inside run(); this outer owner outlives all native runs.
  config=ModelConfig('qwen3.5:4b','d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04',context_tokens=64000,max_output_tokens=768,timeout_seconds=60,min_free_mib=8500,think=False)
  http=PrivateHTTP('http://127.0.0.1:11435')
  def sample():
   while not stop.is_set():
    report['samples'].append(collect())
    try:
     rows=http('GET','/api/ps',timeout=2).get('models',[])
     if rows:report.setdefault('residency_samples',[]).append({'observed_at':time.time(),'models':[{k:r.get(k) for k in ('name','digest','size','size_vram','context_length')} for r in rows]})
    except Exception:pass
    stop.wait(2)
  sampler=threading.Thread(target=sample,daemon=True);sampler.start()
  report['configuration']=config.__dict__
  print(json.dumps({'event':'ollama-ready','trial_id':trial}),flush=True)
  report['native_windows']=(run_native or run)(config,http,collect)
  report['passed']=report['native_windows'].get('passed',False)
 except Exception as exc:
  report.update(passed=False,error_class=type(exc).__name__,error=str(exc))
 finally:
  stop.set()
  if sampler:sampler.join(timeout=10)
  if process:
   try:
    admin("[IO.File]::WriteAllText('C:\\JarvisHermesLab\\runs\\"+trial+"\\stop.requested','operator stop');[pscustomobject]@{requested=$true}|ConvertTo-Json -Compress")
    out,err=process.communicate(timeout=15);(ROOT/'data/phase4'/('ollama-'+trial+'.log')).write_bytes(out+b'\n'+err)
    report['cleanup']['supervisor']=admin("Get-Content -LiteralPath 'C:\\JarvisHermesLab\\runs\\"+trial+"\\supervisor-result.json' -Raw")
   except Exception as exc:report['cleanup']['error']=type(exc).__name__;report['passed']=False
  report['cleanup']['listener_after']=admin(LISTENER)
  report['cleanup']['gpu_after']=collect()
  report['finished_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'event':'finished','passed':report.get('passed',False),'report':str(destination)}),flush=True)
if __name__=='__main__':main()
