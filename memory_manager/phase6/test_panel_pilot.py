"""Offline real-browser exercise of P6-L1 wiring. Runtime/SSH are fakes."""
import json,secrets,shutil,time,unittest,uuid
from unittest.mock import patch
from . import panel_pilot as p
from ..phase2.local_model import ModelConfig

class Process:
    def __init__(self):self.code=None
    def poll(self):return self.code
    def terminate(self):self.code=0
    def wait(self,timeout=None):self.code=0;return 0
class Runtime:
    def __init__(self):self.process=None;self.reports=[]
    def start(self,*_):self.process=Process()
    def stop(self):self.reports=[{'owned_process_stopped_after_close':True}];self.process=None
class Client:
    def __init__(self,*_,**__):pass
    def create(self,*_):return {'run_id':'offline-only'}
    def status(self,*_):return {'status':'completed','output':'Quatre cellules de 1 kg. source.ref=synthetic://doselab/correction ; ancien : synthetic://doselab/old.','usage':{'total_tokens':0}}
    def stop(self,*_):return {}
class Response:
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self,*_):return b'data: {"event":"tool.completed","tool":"mcp__jarvis__jarvis_memory_search"}\n\n'
class Opener:
    def open(self,*_,**__):return Response()
class PanelTest(unittest.TestCase):
 def exercise(self,pilot):
    folder=p.ROOT/'data/phase6'/('offline-'+uuid.uuid4().hex)
    try:
        p.prepare(folder);credentials=folder/'credentials';credentials.mkdir()
        for n in ['memory.token','model.token','hermes.token']:(credentials/n).write_text(secrets.token_urlsafe(32))
        p.private_json(folder/'window.json',{'started_at':time.time(),'expires_at':time.time()+180,'closed':False,'calls':0,'missions':0,'limits':{'calls':6,'missions':1}})
        cfg=ModelConfig('qwen3.5:4b','d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04',context_tokens=64000,max_output_tokens=768,think=False)
        upstream=lambda *a,**k:{'models':[{'name':cfg.model,'digest':cfg.digest}]}
        telemetry=lambda:{'available':True,'observed_at':time.time(),'free_mib':9200,'utilization':0,'miner_running':False}
        popen=p.subprocess.Popen
        with patch.object(p,'Runtime',Runtime),patch.object(p,'HermesRuns',Client),patch.object(p,'PrivateHTTP',lambda *a,**k:lambda *a,**k:{}),patch.object(p.urllib.request,'build_opener',lambda *a:Opener()),patch.object(p.subprocess,'Popen',lambda args,**kw:Process() if args[0]=='ssh' else popen(args,**kw)):
            result=p.execute(cfg,upstream,telemetry,folder=folder,credentials_dir=credentials,pilot=pilot)
        self.assertNotIn('error_class',result,result)
        self.assertFalse(result['passed'])
        self.assertFalse(result['checks']['model_actually_called'])
        self.assertTrue(all(v for k,v in result['checks'].items() if k!='model_actually_called'),result)
        self.assertTrue(result['panel_stopped']);self.assertTrue(result['tunnel_stopped'])
        self.assertEqual(json.loads((folder/'window.json').read_text())['missions'],1)
    finally:shutil.rmtree(folder,ignore_errors=True)
 def test_real_panel_fake_runtime_is_not_real_model_proof(self):self.exercise('P6-L1')
 def test_real_ask_fake_runtime_is_not_real_model_proof(self):self.exercise('P6-L2')
if __name__=='__main__':unittest.main()
