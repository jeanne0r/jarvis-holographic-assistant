"""Authorized, bounded root installation/start. No model, SSH or mission dispatch.
Run from an administrator terminal. Never overwrites an existing installation.
"""
import argparse,hashlib,importlib.util,json,os,pwd,grp,secrets,shutil,socket,sqlite3,stat,subprocess,threading,time,urllib.request,urllib.error
from pathlib import Path
SRC=Path('/home/user/workspace/jarvis-2-memory')
OLD=SRC/'data/phase6/pilot-interactive'
ROOT=Path('/opt/jarvis-hermes-pilot');STATE=Path('/var/lib/jarvis-hermes-pilot')
UNIT=Path('/etc/systemd/system/jarvis-hermes-pilot-system.service')
GATE=Path('/run/jarvis-pilot-network-gate');NAME=UNIT.name
EXTRA=['ops/pilot-network/check-system-filter.py','ops/pilot-network/startup-guard.py']
def run(args,**kw):return subprocess.run(args,check=True,capture_output=True,text=True,**kw).stdout.strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def user_show(name,prop):
 return run(['runuser','-u','user','--','env','XDG_RUNTIME_DIR=/run/user/1000','systemctl','--user','show',name,'-p',prop,'--value'])
def read_source(relative):
 p=SRC/relative
 if not p.resolve().is_relative_to(SRC) or p.is_symlink() or not p.is_file():raise PermissionError('Regular source within worktree required')
 return p.read_bytes()
def dump(db):
 with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as c:
  if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
  return list(c.iterdump())
def snapshot(a,b):
 if b.exists():raise FileExistsError('Never overwrite a database')
 with sqlite3.connect(f'file:{a}?mode=ro',uri=True) as src,sqlite3.connect(b) as dest:src.backup(dest)
 os.chmod(b,0o600)
def verify_layout():
 for p in [ROOT,UNIT,ROOT/'deployment-files.json']:
  st=p.lstat()
  if p.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise PermissionError('Root-owned installed release required')
 expected=json.loads((ROOT/'deployment-files.json').read_text())
 for name,h in expected.items():
  p=ROOT/name
  if p.is_symlink() or p.stat().st_uid!=0 or p.stat().st_mode&0o022 or sha(p)!=h:raise PermissionError('Installed source mismatch')
 if UNIT.read_bytes()!=(ROOT/'ops/pilot-network/jarvis-hermes-pilot-system.service').read_bytes():raise PermissionError('Installed unit differs')
 uid=pwd.getpwnam('jarvis-pilot').pw_uid
 if uid==0 or STATE.stat().st_uid!=uid or STATE.stat().st_mode&0o077:raise PermissionError('Private nonroot state required')
 for name in ['config.json','operator.token','memory.sqlite','audit.jsonl']:
  p=STATE/name
  if p.is_symlink() or not p.is_file() or p.stat().st_uid!=uid or p.stat().st_mode&0o077:raise PermissionError('Private application-owned state required')
def install():
 if any(p.exists() or p.is_symlink() for p in [ROOT,STATE,UNIT,GATE]):raise PermissionError('Existing paths: never overwrite or adopt')
 try:pwd.getpwnam('jarvis-pilot')
 except KeyError:pass
 else:raise PermissionError('Existing account: refuse adoption')
 try:grp.getgrnam('jarvis-pilot')
 except KeyError:pass
 else:raise PermissionError('Existing group: refuse adoption')
 manifest_raw=read_source('docs/pilot-interactive/manifest.json');manifest=json.loads(manifest_raw)
 if manifest['mode']!='synthetic-interactive-queue-only':raise PermissionError('Synthetic profile only')
 files={}
 for name,h in manifest['files'].items():
  raw=read_source(name)
  if hashlib.sha256(raw).hexdigest()!=h:raise PermissionError('Pinned source mismatch')
  files[name]=raw
 files['docs/pilot-interactive/manifest.json']=manifest_raw
 for name in EXTRA+['ops/pilot-network/jarvis-hermes-pilot-system.service']:files[name]=read_source(name)
 expected=json.loads(read_source('docs/pilot-interactive/system-installation-files.json'))
 if any(hashlib.sha256(files[k]).hexdigest()!=v for k,v in expected.items()):raise PermissionError('Installation source mismatch')
 # No source changes or account operation before all source checks succeed.
 source_names=['config.json','operator.token','audit.jsonl','memory.sqlite','memory.backup.sqlite','restore-check.sqlite']
 before={n:sha(OLD/n) for n in source_names}
 for n in source_names:
  p=OLD/n
  if p.is_symlink() or not p.is_file() or p.stat().st_uid!=pwd.getpwnam('user').pw_uid or p.stat().st_mode&0o077:raise PermissionError('Private existing state required')
 cfg=json.loads((OLD/'config.json').read_text())
 if cfg['syntheticOnly'] is not True or cfg['dispatchEnabled'] is not False or cfg['frontPort']!=8796 or cfg['bridgePort']!=8797 or cfg['origin']!='http://127.0.0.1:8796':raise PermissionError('Pinned private topology required')
 if cfg['expiresAt']<=time.time()*1000:raise PermissionError('Expired operator credential; no automatic replacement')
 with sqlite3.connect(f'file:{OLD/"memory.sqlite"}?mode=ro',uri=True) as db:
  if db.execute("select count(*) from mm_memories where owner!='phase3-synthetic' or scope!='private'").fetchone()[0]:raise PermissionError('Synthetic memory only')
  for row in db.execute('select source from mm_events'):
   if not json.loads(row[0]).get('ref','').startswith(('synthetic://doselab/','mission://')):raise PermissionError('Synthetic provenance only')
 if dump(OLD/'memory.backup.sqlite')!=dump(OLD/'restore-check.sqlite'):raise ValueError('Existing backup restore mismatch')
 run(['useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','jarvis-pilot'])
 account=pwd.getpwnam('jarvis-pilot');ROOT.mkdir(mode=0o755);STATE.mkdir(mode=0o700)
 for name,raw in files.items():
  target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(0o444)
 installed={name:sha(ROOT/name) for name in files}
 (ROOT/'deployment-files.json').write_text(json.dumps(installed,indent=2)+'\n');(ROOT/'deployment-files.json').chmod(0o444)
 for name in ['config.json','operator.token','audit.jsonl']:
  (STATE/name).write_bytes((OLD/name).read_bytes());(STATE/name).chmod(0o600)
 snapshot(OLD/'memory.sqlite',STATE/'memory.sqlite')
 snapshot(STATE/'memory.sqlite',STATE/'memory.backup.sqlite');snapshot(STATE/'memory.backup.sqlite',STATE/'restore-check.sqlite')
 if dump(STATE/'memory.sqlite')!=dump(STATE/'restore-check.sqlite'):raise ValueError('Copied restore mismatch')
 (STATE/'empty-home').mkdir(mode=0o700)
 for p in [STATE,*STATE.iterdir()]:os.chown(p,account.pw_uid,account.pw_gid)
 if before!={n:sha(OLD/n) for n in source_names}:raise ValueError('Original state changed; abort')
 UNIT.write_bytes(files['ops/pilot-network/jarvis-hermes-pilot-system.service']);UNIT.chmod(0o644)
 run(['systemd-analyze','verify',str(UNIT)]);run(['systemctl','daemon-reload'])

def publish_approval(folder,payload):
 # Publish a complete root-owned, non-secret receipt atomically. The final
 # unprivileged guard must be able to read it even under caller umask 0077.
 staging=folder/('approval-'+secrets.token_hex(12)+'.tmp')
 fd=os.open(staging,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  with os.fdopen(fd,'w') as f:
   json.dump(payload,f);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o644)
  os.link(staging,folder/'approved.json',follow_symlinks=False)
 finally:
  staging.unlink()


def supervised_start():
 verify_layout()
 if run(['systemctl','show',NAME,'-p','ActiveState','--value']) not in ['inactive','failed']:raise PermissionError('Existing active unit never restarted')
 if GATE.exists():raise PermissionError('Existing startup gate; refuse adoption')
 for port in [8796,8797]:
  with socket.socket() as s:s.bind(('127.0.0.1',port))
 spec=importlib.util.spec_from_file_location('probe',ROOT/EXTRA[0]);probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
 route=json.loads(run(['ip','-j','route','get','192.0.2.1']))[0];ip=route['prefsrc']
 if ip.startswith('127.'):raise PermissionError('Non-loopback witness required')
 sockets=[];accepted=set();lock=threading.Lock();stop=threading.Event();child=None;success=False
 def serve(s):
  s.settimeout(.2)
  while not stop.is_set():
   try:
    c,peer=s.accept()
    with lock:accepted.add((s.getsockname()[0],peer[0],peer[1]))
    c.close()
   except socket.timeout:pass
   except OSError:break
 try:
  for host in ['127.0.0.1',ip]:
   s=socket.socket();s.bind((host,0 if not sockets else sockets[0].getsockname()[1]));s.listen(4);sockets.append(s)
   threading.Thread(target=serve,args=(s,),daemon=True).start()
  port=sockets[0].getsockname()[1]
  def controls():
   keys=[]
   for host in ['127.0.0.1',ip]:
    with socket.create_connection((host,port),timeout=1) as c:keys.append((host,*c.getsockname()))
   for _ in range(30):
    with lock:
     if all(k in accepted for k in keys):return True
    time.sleep(.02)
   return False
  before=controls()
  if not before:raise RuntimeError('Fixture unavailable')
  GATE.mkdir(mode=0o755)
  # The caller uses umask 0077 for secrets; this root-owned, non-secret
  # rendezvous must remain traversable by the final unprivileged unit.
  GATE.chmod(0o755)
  session=secrets.token_hex(24)
  (GATE/'fixture.json').write_text(json.dumps({'ip':ip,'port':port,'session':session,'expires':time.time()+40}));(GATE/'fixture.json').chmod(0o644)
  request=STATE/'startup-network.json'
  if request.exists():request.unlink()
  child=subprocess.Popen(['systemctl','start',NAME],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  deadline=time.time()+25;data=None
  while time.time()<deadline:
   if request.exists():
    try:data=json.loads(request.read_text())
    except json.JSONDecodeError:pass
    if data and data.get('session')==session:break
   if child.poll() is not None:raise RuntimeError('Unit pre-start gate failed')
   time.sleep(.1)
  if not data or data.get('session')!=session:raise RuntimeError('No fresh unit probe')
  cg=run(['systemctl','show',NAME,'-p','ControlGroup','--value'])
  if not cg.startswith('/system.slice/'):raise PermissionError('System cgroup required')
  attached=json.loads(run(['/usr/sbin/bpftool','-j','cgroup','show','/sys/fs/cgroup'+cg,'effective']))
  hooks={r.get('attach_type') for r in attached};observed=data['network'];after=controls()
  with lock:witness={'loopback_seen':('127.0.0.1','127.0.0.1',observed['loopback']['local_port']) in accepted,'non_loopback_seen':(ip,ip,observed['non_loopback']['local_port']) in accepted}
  if not probe.verdict(observed,hooks,before and after,witness):raise PermissionError('Final cgroup network validation failed')
  # Root writes the approval only after tests in the actual final cgroup passed.
  publish_approval(GATE,{'nonce':data['nonce'],'session':session,'expires':time.time()+10})
  child.communicate(timeout=15)
  if child.returncode:raise RuntimeError('Unit start failed')
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));origin='http://127.0.0.1:8796';token=(STATE/'operator.token').read_text()
  def call(path,auth=True):
   req=urllib.request.Request(origin+path,headers={'Origin':origin,**({'Authorization':'Bearer '+token} if auth else {})})
   try:
    with opener.open(req,timeout=2) as r:return r.status,json.load(r)
   except urllib.error.HTTPError as e:return e.code,{}
  for _ in range(30):
   try:
    if call('/api/health',False)[0]==200:break
   except OSError:pass
   time.sleep(.2)
  if call('/api/jarvis/hermes/missions?space=user',False)[0]!=401:raise PermissionError('Anonymous access not refused')
  if call('/api/jarvis/hermes/missions?space=user')[0]!=200:raise PermissionError('Authenticated history unavailable')
  if call('/api/jarvis/hermes/missions?space=amelie')[0]!=403:raise PermissionError('Space boundary failed')
  if call('/api/jarvis/ask')[0]!=403:raise PermissionError('Legacy route not refused')
  status,availability=call('/api/jarvis/hermes/availability?space=user')
  if status!=200 or availability.get('dispatch_allowed') is not False:raise PermissionError('Worker must stay disabled')
  account=pwd.getpwnam('jarvis-pilot');pid=int(run(['systemctl','show',NAME,'-p','MainPID','--value']))
  proc=Path('/proc')/str(pid)
  uid_line=next(l for l in (proc/'status').read_text().splitlines() if l.startswith('Uid:'))
  if any(int(x)!=account.pw_uid for x in uid_line.split()[1:]):raise PermissionError('Wrong runtime UID')
  if (proc/'root/home/user/gateway/.env').exists():raise PermissionError('Gateway secrets visible')
  enabled=subprocess.run(['systemctl','is-enabled',NAME],capture_output=True,text=True)
  if enabled.stdout.strip() not in ['static','disabled']:raise PermissionError('Autostart must stay off')
  report={'passed':True,'unit':NAME,'private_url':origin,'effective_bpf_hooks':sorted(hooks),'network':observed,'controls_before':before,'controls_after':after,'receiver_witness':witness,'auth_401':True,'history_200':True,'cross_space_403':True,'legacy_route_403':True,'dispatch_enabled':False,'runtime_uid_nonroot':True,'gateway_secrets_hidden':True,'autostart':False,'new_missions':0}
  (STATE/'installation-result.json').write_text(json.dumps(report,indent=2)+'\n');(STATE/'installation-result.json').chmod(0o600)
  success=True;return report
 finally:
  if not success:subprocess.run(['systemctl','stop',NAME],capture_output=True)
  if child and child.poll() is None:child.communicate(timeout=10)
  stop.set()
  for s in sockets:s.close()
  if GATE.exists():shutil.rmtree(GATE)

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--install-approved',action='store_true');g.add_argument('--start-approved',action='store_true');a=p.parse_args()
 if os.geteuid()!=0:raise SystemExit('Administrator terminal required; no operation performed')
 if user_show('jarvis-hermes-pilot.service','ActiveState')!='inactive':raise PermissionError('Old pilot must stay stopped')
 gateway=user_show('codex-gateway.service','MainPID')
 if a.install_approved:install()
 result=supervised_start()
 if user_show('codex-gateway.service','MainPID')!=gateway:
  run(['systemctl','stop',NAME]);raise RuntimeError('Gateway PID changed; pilot stopped')
 result['gateway_pid_unchanged']=True;print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except Exception as e:
  print('NO-GO: '+type(e).__name__+': '+str(e)+'; inspect prepared unit/state. No retry or weaker policy.',file=__import__('sys').stderr)
  raise SystemExit(1)
