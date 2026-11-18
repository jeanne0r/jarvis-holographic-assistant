"""Actual browser -> private login/relay -> queue/SQLite -> existing Controller.
Hermes, GPU telemetry and model are synthetic; no Windows/production contacts.
"""
import hashlib,json,os,socket,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from contextlib import closing
from scripts.prepare_demand import prepare,ROOT
from scripts.prepare_interactive_pilot import prepare as seed_state
from scripts.demand_supervisor import Supervisor
from memory_manager.phase6.demand_service import Demand
from memory_manager.phase6.operational import Controller,DIGEST
from memory_manager.phase2.local_model import PrivateHTTP
from memory_manager.api import server
from memory_manager.store import Memory

class DemandHTTP(unittest.TestCase):
 def test_browser_queue_execution_citations_and_restart(self):
    processes=[];halt=threading.Event();models=[];creates=[];audits=[];gates=[]
    def free():
     with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
    def start(args,cwd):
     p=subprocess.Popen(args,cwd=cwd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);processes.append(p);return p
    def ready(p,url):
     import urllib.request,urllib.error
     for i in range(100):
      if p.poll() is not None:raise AssertionError(p.stderr.read().decode())
      try:
       with urllib.request.urlopen(url,timeout=.3):return
      except Exception:time.sleep(.1)
     raise AssertionError('Test host not ready')
    with tempfile.TemporaryDirectory() as tmp:
     tmp=Path(tmp);candidate=tmp/'package';prepare(candidate)
     front,bridge,public=free(),free(),free();origin='http://127.0.0.1:'+str(public)
     cfg=seed_state(tmp/'state',front=front,bridge=bridge,fixture=True)
     cfg.update(embeddedPanel={'enabled':True,'origin':origin},operations={'admissionEnabled':True,'textEnabled':True,'workerEnabled':False,'voiceEnabled':False},
       onDemand={'accepting':True,'executionEnabled':True,'schedulerToken':'Q'*43,'runtime':{'hermesToken':'H'*43,'modelToken':'M'*43,'memoryToken':'R'*43,'supervisorToken':'S'*43},'commissioned':True})
     (tmp/'state/config.json').write_text(json.dumps(cfg))
     memory_http=PrivateHTTP('http://127.0.0.1:'+str(bridge),'R'*43)
     observer=PrivateHTTP('http://127.0.0.1:'+str(bridge),'S'*43)
     class Native:
      def create(self,mid,payload):
       data=json.loads(payload);self.assertion=data.get('report_contract');creates.append(mid);return {'run_id':'fake-'+mid}
      def status(self,rid):
       report=memory_http('POST','/v1/tools/call',{'name':'memory.audit','arguments':{'q':'DoseLab'}})
       audits.append(report)
       out=engine.controller.call({'model':'qwen3.5:4b','messages':[{'role':'user','content':'Analyse synthétique avec sources.'}]})
       return {'status':'completed','output':out['choices'][0]['message']['content']}
      def stop(self,rid):pass
     native=Native()
     def upstream(method,path,data=None,**kw):
      if path=='/api/tags':return {'models':[{'name':'qwen3.5:4b','digest':DIGEST}]}
      models.append(data);return {'done':True,'done_reason':'stop','prompt_eval_count':90,'eval_count':50,'message':{'content':'Quatre cellules de 1 kg. Source : `synthetic://doselab/correction`. Ancienne version remplacée : `synthetic://doselab/old`.\n\nSources\n- synthetic://doselab/correction\n- synthetic://doselab/old'}}
     class GateServer:
      def __init__(self):self.stop=threading.Event();gates.append(self)
      def serve_forever(self):self.stop.wait()
      def shutdown(self):self.stop.set()
      def server_close(self):pass
     engine=Demand(tmp/'state/memory.sqlite',cfg,controller_factory=lambda path,cfg,**kw:Controller(path,cfg,client=native,upstream=upstream,endpoint_probe=lambda:True,**kw),gate_factory=lambda *args:GateServer())
     from memory_manager.phase3.lab import OWNER
     def identity(roles,actor):return {'name':OWNER,'scopes':['private'],'roles':roles,'actor_id':actor}
     clients={hashlib.sha256(token.encode()).hexdigest():identity(roles,actor) for token,roles,actor in [(cfg['bridgeToken'],['reader','mission_writer'],'interactive-panel'),('Q'*43,['queue_supervisor'],'on-demand-supervisor'),('R'*43,['reader'],'hermes-memory'),('S'*43,['worker_reporter'],'operational-supervisor')]}
     srv=server(tmp/'state/memory.sqlite',clients,bridge,extension=engine.handle);threading.Thread(target=srv.serve_forever,daemon=True).start()
     scheduler=PrivateHTTP('http://127.0.0.1:'+str(bridge),'Q'*43)
     import urllib.request,urllib.error
     def code(path,token=None,data=None):
      req=urllib.request.Request('http://127.0.0.1:'+str(bridge)+path,headers={'Authorization':'Bearer '+token} if token else {},data=json.dumps(data).encode() if data is not None else None)
      try:
       with urllib.request.urlopen(req,timeout=2) as r:return r.status
      except urllib.error.HTTPError as e:return e.code
     self.assertEqual(code('/v1/queue/next'),401)
     self.assertEqual(code('/v1/queue/next',cfg['bridgeToken']),403)
     self.assertEqual(code('/v1/queue/next','R'*43),403)
     self.assertEqual(code('/v1/missions','Q'*43),403)

     signal=tmp/'start.signal'
     def lifecycle(lease):
      sequence=0
      for _ in range(40):
       sequence+=1;observer('POST','/v1/workers/windows-hermes/observe',{'epoch':lease['epoch'],'sequence':sequence,'endpoint_ready':True,'gpu':{'observed_at':time.time(),'free_mib':10000,'utilization':0,'miner_running':False}})
       engine.step()
       with closing(Memory(tmp/'state/memory.sqlite')) as memory:
        if engine.queue(memory).status()['active'] and memory.db.execute('SELECT state FROM mm_missions WHERE id=?',(lease['mission_id'],)).fetchone()[0]=='completed':return {'cleanup_verified':True}
       time.sleep(.1)
      return {'cleanup_verified':False}
     supervisor=Supervisor(scheduler,lambda:None,lifecycle)
     def loop():
      while not halt.wait(.1):
       if signal.exists():
        try:supervisor.tick()
        except Exception as e:errors.append(type(e).__name__+': '+str(e));return
     errors=[];thread=threading.Thread(target=loop,daemon=True);thread.start()
     try:
      p=start(['node','ops/pilot-embedded.mjs',str(tmp/'state/config.json')],candidate/'private-release');ready(p,cfg['origin']+'/api/health')
      flag=tmp/'switch.json';flag.write_text('{"enabled":true,"admissionEnabled":true}');flag.chmod(0o600)
      ui=tmp/'ui.json';ui.write_text(json.dumps({'origin':origin,'upstreamPort':front,'frontend':str(candidate/'frontend'),'sourcePublic':'/home/user/workspace/jarvis/public','switchFile':str(flag),'simulatorStartSignal':str(signal)}))
      p=start(['node','ops/embedded-ui-lab.mjs',str(ui)],ROOT);ready(p,origin+'/jarvis/')
      result=subprocess.run(['node','test_hermes_demand_browser.cjs',str(ui),str(tmp/'state/operator.token')],cwd=ROOT,capture_output=True,text=True,timeout=50)
      self.assertEqual(result.returncode,0,result.stdout+result.stderr+'\n'+str(errors));self.assertEqual(errors,[]);print(result.stdout.strip())
      self.assertEqual(len(creates),1);self.assertEqual(len(models),1);self.assertEqual(len(audits),1);self.assertIsNotNone(native.assertion);self.assertTrue(gates[0].stop.is_set())
      restored=Demand(tmp/'state/memory.sqlite',cfg,controller_factory=lambda *a,**k:(_ for _ in ()).throw(AssertionError('No replay')))
      with closing(Memory(tmp/'state/memory.sqlite')) as memory:
       self.assertEqual(memory.db.execute("SELECT count(*) FROM mm_missions WHERE state='completed'").fetchone()[0],1)
       self.assertEqual(memory.db.execute('SELECT sum(actual_remote_micros) FROM p2_usage').fetchone()[0],0)
       self.assertEqual(memory.db.execute('SELECT cleanup_ok FROM p6q_jobs').fetchone()[0],1)
       quality=memory.db.execute("SELECT data FROM p2_events WHERE kind='report_quality'").fetchone();self.assertTrue(json.loads(quality[0])['model_cites_source_ref'])
       self.assertIsNone(restored.queue(memory).peek(__import__('memory_manager.store',fromlist=['Principal']).Principal(OWNER,frozenset({'private'}),frozenset({'queue_supervisor'}),'on-demand-supervisor')))
     finally:
      halt.set();thread.join(timeout=5);engine.close_gate()
      for p in processes:
       if p.poll() is None:p.terminate();p.wait(timeout=10)
       p.stderr.close()
      srv.shutdown();srv.server_close()
