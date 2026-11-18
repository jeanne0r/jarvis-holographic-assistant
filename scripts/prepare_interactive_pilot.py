"""Prepare a coherent isolated release; --install-approved requires new approval.
No Windows, provider, gateway or historical personal database paths are used.
"""
import argparse,hashlib,json,os,secrets,shutil,subprocess,time,uuid
from pathlib import Path
from memory_manager.store import Memory,snapshot
from memory_manager.phase2 import database
from memory_manager.phase3 import lab
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/pilot-interactive'
FILES=['ops/jarvis-hermes-pilot.service.in','memory_manager/__init__.py','memory_manager/phase6/__init__.py','memory_manager/phase2/__init__.py','memory_manager/phase3/__init__.py','memory_manager/phase2/hermes.py','ops/pilot-interactive.html','ops/pilot-interactive.mjs','memory_manager/phase6/interactive.py','scripts/prepare_interactive_pilot.py','public/jarvis-auth.js','public/hermes-missions.js','public/hermes-missions.css','public/hermes-canonical.js','gateway-security.mjs','gateway-security-mount.mjs','gateway-route-policy.mjs','phase6-gateway.mjs','jarvis-session-auth.mjs','hermes-server-auth.mjs','jarvis-hermes-experimental.mjs','hermes-bridge-client.mjs','hermes-voice-tools.mjs','hybrid-mission-admission.mjs','memory_manager/api.py','memory_manager/store.py','memory_manager/missions.py','memory_manager/schema.sql','memory_manager/phase2/http_bridge.py','memory_manager/phase2/bridge.py','memory_manager/phase2/schema.sql','memory_manager/phase2/database.py','memory_manager/phase2/memory_tools.py','memory_manager/phase2/validation.py','memory_manager/phase2/local_model.py','memory_manager/phase3/lab.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_manifest():
 m=json.loads((DEST/'manifest.json').read_text())
 if m['mode']!='synthetic-interactive-queue-only':raise PermissionError('Profile')
 if any(sha(ROOT/f)!=h for f,h in m['files'].items()):raise PermissionError('Source fingerprint mismatch')
 return True

def prepare(folder,source=None,*,front=8796,bridge=8797,fixture=False):
 folder=Path(folder).resolve()
 if folder.exists():raise PermissionError('Existing state never overwritten')
 if not fixture and not folder.is_relative_to(ROOT/'data/phase6'):raise PermissionError('Isolated state only')
 folder.mkdir(mode=0o700,parents=True);(folder/'empty-home').mkdir(mode=0o700)
 if source is not None:
  source=Path(source).resolve(strict=True)
  if not fixture and (source.name!='memory.sqlite' or not source.is_relative_to(ROOT/'data/phase6') or not source.parent.name.startswith(('p6-l1-','p6-l2-'))):raise PermissionError('Validated synthetic P6-L database only')
  before=sha(source);snapshot(source,folder/'memory.sqlite')
  if sha(source)!=before:raise PermissionError('Source changed during copy')
 else:
  if not fixture:raise PermissionError('Existing synthetic base required')
  m=Memory(folder/'memory.sqlite',create=True)
  try:database.migrate(m);lab.seed(m)
  finally:m.close()
 m=Memory(folder/'memory.sqlite')
 try:
  if any(r['owner']!=lab.OWNER or r['scope']!='private' for r in m.db.execute('SELECT owner,scope FROM mm_memories')):raise PermissionError('Synthetic ownership only')
  if any(not json.loads(r['source']).get('ref','').startswith(('synthetic://doselab/','mission://')) for r in m.db.execute('SELECT source FROM mm_events')):raise PermissionError('Synthetic sources only')
 finally:m.close()
 snapshot(folder/'memory.sqlite',folder/'memory.backup.sqlite')
 # Restore into a separate file and verify SQLite integrity and logical data.
 snapshot(folder/'memory.backup.sqlite',folder/'restore-check.sqlite')
 import sqlite3
 with sqlite3.connect(folder/'memory.sqlite') as db,sqlite3.connect(folder/'restore-check.sqlite') as restored:
  if list(db.iterdump())!=list(restored.iterdump()):raise ValueError('Restore differs')
 token=secrets.token_urlsafe(32);cfg={'syntheticOnly':True,'dispatchEnabled':False,'origin':'http://127.0.0.1:'+str(front),'frontPort':front,'bridgePort':bridge,'humanHash':hashlib.sha256(token.encode()).hexdigest(),'expiresAt':int((time.time()+30*86400)*1000),'bridgeToken':secrets.token_urlsafe(32),'missionLimits':{'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}}
 for name,raw in [('config.json',json.dumps(cfg)),('operator.token',token),('audit.jsonl','')]:
  fd=os.open(folder/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'w') as f:f.write(raw)
 return cfg

def main():
 p=argparse.ArgumentParser();p.add_argument('--install-approved',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args();verify_manifest()
 if not a.install_approved:
  print('Manifest verified; service not installed or started. Installation requires explicit approval.');return
 # This branch is prepared only; never invoked without the separate service approval.
 folder=ROOT/'data/phase6/pilot-interactive';unit=Path.home()/'.config/systemd/user/jarvis-hermes-pilot.service'
 if unit.exists() or folder.exists():raise PermissionError('Existing service/state: review before replacement')
 known=subprocess.run(['systemctl','--user','show','jarvis-hermes-pilot.service','-p','LoadState','--value'],capture_output=True,text=True)
 if known.stdout.strip()!='not-found':raise PermissionError('Existing or uncertain unit: never adopt or stop it')
 for port in (8796,8797):
  import socket
  with socket.socket() as probe:probe.bind(('127.0.0.1',port))
 source=ROOT/'data/phase6/p6-l2-20261115T061358Z-8c0c8df5/memory.sqlite'
 prepare(folder,source)
 unit.parent.mkdir(parents=True,exist_ok=True)
 raw=(ROOT/'ops/jarvis-hermes-pilot.service.in').read_text().replace('@ROOT@',str(ROOT))
 fd=os.open(unit,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:f.write(raw)
 try:
  subprocess.run(['systemctl','--user','daemon-reload'],check=True)
  subprocess.run(['systemctl','--user','start','jarvis-hermes-pilot.service'],check=True)
  import urllib.request
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));ready=False
  for _ in range(40):
   try:
    with opener.open('http://127.0.0.1:8796/api/health',timeout=1) as response:ready=response.status==200
    if ready:break
   except Exception:pass
   time.sleep(.25)
  if not ready:raise RuntimeError('Readiness failed; revert new unit only')
 except Exception:
  subprocess.run(['systemctl','--user','stop','jarvis-hermes-pilot.service'],check=False)
  unit.unlink();subprocess.run(['systemctl','--user','daemon-reload'],check=False)
  raise
 print('Pilot installed on loopback 8796; operator credential stays in the private state directory. No enable/autostart and no Windows process.')
if __name__=='__main__':main()
