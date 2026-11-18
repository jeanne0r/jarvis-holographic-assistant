import json,os,socket,subprocess,tempfile,time,unittest,urllib.error,urllib.request
from pathlib import Path
from scripts.prepare_interactive_pilot import prepare,verify_manifest,ROOT
from memory_manager.store import Memory
from memory_manager.phase3 import lab
class InteractiveTests(unittest.TestCase):
 def test_private_durable_queue_restart_auth_and_no_runtime(self):
  self.assertTrue(verify_manifest())
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'state'
   def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
   front,bridge=port(),port()
   while bridge==front:bridge=port()
   cfg=prepare(folder,front=front,bridge=bridge,fixture=True);token=(folder/'operator.token').read_text();self.assertGreater(cfg['expiresAt'],(time.time()+3600)*1000)
   env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   process=None
   def start():
    child=subprocess.Popen(['python3','-m','memory_manager.phase6.interactive','--config',str(folder/'config.json')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    for _ in range(80):
     if child.poll() is not None:raise AssertionError(child.stderr.read().decode())
     try:
      with opener.open(cfg['origin']+'/api/health',timeout=.5):return child
     except Exception:time.sleep(.1)
    child.terminate();child.wait();child.stderr.close();raise AssertionError('Readiness')
   def stop(child):child.terminate();child.wait(timeout=10);child.stderr.close();self.assertEqual(child.returncode,0)
   def call(path,body=None,auth=True,method=None,extra=None):
    headers={'Origin':cfg['origin'],**({'Authorization':'Bearer '+token} if auth else {}),**(extra or {})};raw=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(cfg['origin']+path,data=raw,method=method,headers=headers)
    try:
     with opener.open(req,timeout=3) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
   try:
    process=start()
    self.assertEqual(call('/api/jarvis/hermes/missions?space=user',auth=False)[0],401)
    self.assertEqual(call('/api/jarvis/hermes/missions?space=amelie')[0],403)
    self.assertEqual(call('/api/jarvis/ask',{'question':'anything'})[0],403)
    self.assertEqual(call('/api/jarvis/hermes/missions?space=user')[1]['items'],[])
    browser=subprocess.run(['node','test_pilot_interactive_browser.cjs',str(folder/'config.json'),str(folder/'operator.token')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    self.assertEqual(browser.returncode,0,browser.stdout+browser.stderr)
    items=call('/api/jarvis/hermes/missions?space=user')[1]['items'];self.assertEqual(len(items),1);mid=items[0]['mission_id'] if 'mission_id' in items[0] else items[0]['id'];self.assertEqual(items[0]['state'],'queued')
    self.assertEqual(call('/api/jarvis/hermes/missions?space=user',{'template':'free' },extra={'Idempotency-Key':'bad'})[0],400)
    self.assertEqual(call('/api/jarvis/hermes/missions?space=user',{'template':'doselab-current'},extra={'Idempotency-Key':'second'})[0],503) # Existing facade masks bridge denial; admission must stay refused.
    self.assertEqual(call('/api/jarvis/hermes/missions/'+mid+'/approvals?space=user',{})[0],403)
    self.assertFalse(call('/api/jarvis/hermes/availability?space=user')[1]['dispatch_allowed'])
    stop(process);process=None
    process=start();self.assertEqual(call('/api/jarvis/hermes/missions/'+mid+'?space=user')[1]['state'],'queued')
    self.assertEqual(call('/api/jarvis/hermes/missions/'+mid+'/cancel?space=user',{})[0],202)
    self.assertEqual(call('/api/jarvis/hermes/missions/'+mid+'?space=user')[1]['state'],'cancelled')
    m=Memory(folder/'memory.sqlite')
    try:self.assertEqual(m.db.execute('SELECT count(*) FROM p2_usage').fetchone()[0],0);self.assertTrue(m.current(lab.HOST))
    finally:m.close()
    fresh={**cfg,'humanHash':'0'*64};(folder/'config.json').write_text(json.dumps(fresh));self.assertEqual(call('/api/jarvis/hermes/missions?space=user')[0],401)
    self.assertEqual((folder/'config.json').stat().st_mode&0o777,0o600)
   finally:
    if process:stop(process)
if __name__=='__main__':unittest.main()
