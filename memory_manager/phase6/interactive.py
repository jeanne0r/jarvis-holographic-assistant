"""Durable synthetic bridge/panel host. No worker, SSH, GPU or provider path."""
import argparse,hashlib,io,json,os,signal,stat,subprocess,threading,time
from pathlib import Path
from ..store import Memory,Principal
from ..api import server
from ..phase2.http_bridge import dispatch
from ..phase2.bridge import Bridge
from ..phase3 import lab
ROOT=Path(__file__).resolve().parents[2]
OBJECTIVE='DoseLab X4 synthétique : retrouve la configuration actuelle des quatre cellules de pesée et explique les modifications historiques avec leurs sources exactes.'
BUDGET={'tokens':0,'cost_micros':0,'local_tokens':98304,'seconds':240,'attempts':1}
LOCK=threading.Lock()
def extension(memory,principal,request,url,query):
 if url.path=='/v1/health' and request.command=='GET':return 200,{'ready':True,'synthetic_only':True,'dispatch_enabled':False},'application/json'
 if not url.path.startswith('/v1/missions'):return 403,{'error':'Pilot missions only'},'application/json'
 if '/approvals' in url.path or url.path.endswith('/result') or url.path.endswith('/canonical'):return 403,{'error':'Not commissioned'},'application/json'
 if url.path=='/v1/missions' and request.command=='POST':
  size=int(request.headers.get('Content-Length','0'))
  if request.headers.get('Transfer-Encoding') or not 0<size<=8000:raise ValueError('Bounded body')
  raw=request.rfile.read(size);data=json.loads(raw);d=data.get('definition',{})
  expected={'objective':OBJECTIVE,'trigger':'jarvis-experimental','priority':1,'memory_context':[],'plan':['retrieve','report'],'allowed_tools':['memory.search','memory.propose','report'],'budget':BUDGET}
  if data!={'scope':'private','definition':expected}:raise PermissionError('Exact synthetic template required')
  request.rfile=io.BytesIO(raw)
  with LOCK:
   # Allow an exact idempotent retry, but only one outstanding mission.
   prior=memory.db.execute('SELECT id FROM mm_missions WHERE owner=? AND scope=? AND event_key=?',(principal.name,'private',request.headers.get('Idempotency-Key',''))).fetchone()
   if not prior and memory.db.execute("SELECT 1 FROM mm_missions WHERE owner=? AND scope='private' AND state NOT IN ('completed','failed','cancelled') LIMIT 1",(principal.name,)).fetchone():return 409,{'error':'Une mission est déjà en attente ; annulez-la avant une autre admission.'},'application/json'
   return dispatch(memory,principal,request,url,query)
 return dispatch(memory,principal,request,url,query)

def run(config):
 path=Path(config);st=path.lstat()
 if path.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_size>131072 or st.st_uid!=os.getuid() or st.st_mode&0o077:raise PermissionError('Private owned config')
 cfg=json.loads(path.read_text());folder=path.parent.resolve()
 if cfg['syntheticOnly'] is not True or cfg['dispatchEnabled'] is not False or cfg.get('missionLimits')!={'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}:raise PermissionError('Queue only')
 database=folder/'memory.sqlite'
 if database.is_symlink() or database.stat().st_uid!=os.getuid() or database.stat().st_mode&0o077 or folder.stat().st_mode&0o077:raise PermissionError('Private synthetic database required')
 if any(type(cfg.get(k))!=int or not 1024<=cfg[k]<=65535 for k in ('frontPort','bridgePort')) or cfg['frontPort']==cfg['bridgePort'] or cfg['origin']!='http://127.0.0.1:'+str(cfg['frontPort']):raise PermissionError('Distinct loopback ports')
 memory=Memory(database)
 try:
  if any(r['owner']!=lab.OWNER or r['scope']!='private' for r in memory.db.execute('SELECT owner,scope FROM mm_memories')):raise PermissionError('Synthetic owner only')
  if any(not json.loads(r['source']).get('ref','').startswith(('synthetic://doselab/','mission://')) for r in memory.db.execute('SELECT source FROM mm_events')):raise PermissionError('Synthetic provenance only')
 finally:memory.close()
 clients={hashlib.sha256(cfg['bridgeToken'].encode()).hexdigest():{'name':lab.OWNER,'scopes':['private'],'roles':['reader','mission_writer'],'actor_id':'interactive-panel'}}
 bridge=server(database,clients,cfg['bridgePort'],extension=extension)
 stop=threading.Event();signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
 threading.Thread(target=bridge.serve_forever,daemon=True).start()
 child=None
 try:
  child=subprocess.Popen(['node',str(ROOT/'ops/pilot-interactive.mjs'),str(path.resolve())],cwd=ROOT,env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(folder/'empty-home')})
  while not stop.wait(.25):
   if child.poll() is not None:raise RuntimeError('Panel exited; no automatic restart/replay')
 finally:
  if child and child.poll() is None:
   child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait()
  bridge.shutdown();bridge.server_close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
 try:
  from scripts.prepare_interactive_pilot import verify_manifest
  verify_manifest();run(a.config)
 except Exception:print('Interactive pilot refused; no runtime/model started.',file=__import__('sys').stderr);raise SystemExit(1)
