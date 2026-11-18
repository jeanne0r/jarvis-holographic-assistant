import hashlib,json,os,socket,subprocess,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
from scripts.prepare_embedded_panel import prepare,ROOT
from scripts.prepare_interactive_pilot import prepare as state_prepare
from memory_manager.store import Memory,Principal
from memory_manager.phase3 import lab
from memory_manager.phase2.bridge import Bridge
from memory_manager.phase6.interactive import OBJECTIVE,BUDGET
class EmbeddedTests(unittest.TestCase):
 def test_packaged_private_service_bridge_ui_and_restart(self):
  before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('/home/user/gateway/server.js'),Path('/home/user/gateway/public/jarvis/index.html'),ROOT/'docs/pilot-interactive/manifest.json']}
  env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));children=[]
  def port():
   with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
  ports=set()
  while len(ports)<3:ports.add(port())
  public,front,bridge=ports;origin='http://127.0.0.1:'+str(public)
  def call(path,body=None,cookie=None):
   headers={'Origin':origin,**({'Cookie':cookie} if cookie else {})};raw=json.dumps(body).encode() if body is not None else None
   req=urllib.request.Request(origin+path,data=raw,headers=headers)
   try:
    with opener.open(req,timeout=4) as r:return r.status,json.load(r),r.headers.get('Set-Cookie')
   except urllib.error.HTTPError as e:return e.code,{},None
  def start(args,cwd):
   p=subprocess.Popen(args,cwd=cwd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);children.append(p);return p
  def ready(p,url):
   for _ in range(100):
    if p.poll() is not None:raise AssertionError(p.stderr.read().decode())
    try:
     with opener.open(url,timeout=.3):return
    except Exception:time.sleep(.1)
   raise AssertionError('Lab readiness timeout')
  def stop(p):
   if p.poll() is None:p.terminate();p.wait(timeout=10)
   p.stderr.close();children.remove(p);self.assertEqual(p.returncode,0)
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);bundle=tmp/'bundle';prepare(bundle)
   state=tmp/'state';cfg=state_prepare(state,front=front,bridge=bridge,fixture=True)
   cfg['embeddedPanel']={'enabled':True,'origin':origin};(state/'config.json').write_text(json.dumps(cfg))
   m=Memory(state/'memory.sqlite');writer=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','mission_writer'}),'fixture-admission');host=Bridge(m,writer)
   definition={'objective':OBJECTIVE,'trigger':'jarvis-experimental','priority':1,'memory_context':[],'plan':['retrieve','report'],'allowed_tools':['memory.search','memory.propose','report'],'budget':BUDGET}
   complete=host.submit('fixture-completed',definition);queued=host.submit('fixture-queued',definition)
   other=Principal('other-synthetic',frozenset({'private'}),frozenset({'reader','mission_writer'}),actor_id='other-fixture')
   foreign=Bridge(m,other).submit('fixture-other-owner',definition)
   with m.db:
    host.event(complete,'synthetic-result','completed',{'output':'Fixture: source.ref=synthetic://doselab/correction; date erronée 2099-01-01 <img src=x onerror=window.PWNED=true>'})
    m.db.execute("UPDATE mm_missions SET state='completed' WHERE id=?",(complete,));m.db.execute("UPDATE p2_outbox SET state='completed' WHERE mission_id=?",(complete,))
   m.close()
   labcfg={'origin':origin,'upstreamPort':front,'frontend':str(bundle/'frontend'),'sourcePublic':'/home/user/workspace/jarvis/public'}
   (tmp/'ui.json').write_text(json.dumps(labcfg))
   try:
    private=start(['/usr/bin/python3','-m','memory_manager.phase6.interactive','--config',str(state/'config.json')],bundle/'pilot-release')
    ready(private,'http://127.0.0.1:'+str(front)+'/api/health')
    with self.assertRaises(urllib.error.HTTPError) as hidden:opener.open('http://127.0.0.1:'+str(front)+'/',timeout=2)
    self.assertEqual(hidden.exception.code,404)
    gateway=start(['node','ops/embedded-ui-lab.mjs',str(tmp/'ui.json')],ROOT);ready(gateway,origin+'/jarvis/')
    pfx='/api/jarvis/hermes-panel'
    self.assertEqual(call(pfx+'/hermes/missions?space=user')[0],401)
    status,_,cookie=call(pfx+'/session',{'token':(state/'operator.token').read_text()});self.assertEqual(status,200);cookie=cookie.split(';')[0]
    items=call(pfx+'/hermes/missions?space=user',cookie=cookie)[1]['items'];self.assertEqual(len(items),2)
    self.assertNotIn(foreign,[x['id'] for x in items]);self.assertEqual(call(pfx+'/hermes/missions/'+foreign+'?space=user',cookie=cookie)[0],403)
    browser=subprocess.run(['node','test_hermes_embedded_browser.cjs',str(tmp/'ui.json'),str(state/'operator.token')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    self.assertEqual(browser.returncode,0,browser.stdout+browser.stderr)
    print(browser.stdout.strip())
    stop(private)
    self.assertEqual(call(pfx+'/hermes/missions?space=user',cookie=cookie)[0],503)
    self.assertEqual(call('/api/jarvis/voice/status')[0],200)
    private=start(['/usr/bin/python3','-m','memory_manager.phase6.interactive','--config',str(state/'config.json')],bundle/'pilot-release');ready(private,'http://127.0.0.1:'+str(front)+'/api/health')
    self.assertEqual(call(pfx+'/hermes/missions?space=user',cookie=cookie)[0],401)
    status,_,cookie=call(pfx+'/session',{'token':(state/'operator.token').read_text()});self.assertEqual(status,200);cookie=cookie.split(';')[0]
    self.assertEqual(call(pfx+'/hermes/missions/'+queued+'?space=user',cookie=cookie)[1]['state'],'cancelled')
    m=Memory(state/'memory.sqlite')
    try:self.assertEqual(m.db.execute('SELECT count(*) FROM p2_usage').fetchone()[0],0)
    finally:m.close()
   finally:
    for child in list(children):stop(child)
  for name,h in before.items():self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(),h)
if __name__=='__main__':unittest.main()
