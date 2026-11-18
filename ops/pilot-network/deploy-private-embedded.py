"""Lot R only. Run with sudo python3 -B; never writes/restarts the gateway.
No secrets on stdout, in arguments, environment or result records.
"""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,hmac,importlib.util,json,os,pwd,re,secrets,shutil,sqlite3,stat,subprocess,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
SRC=Path('/home/user/workspace/jarvis-2-memory')
ROOT=Path('/opt/jarvis-hermes-pilot');STATE=Path('/var/lib/jarvis-hermes-pilot')
OLD=SRC/'data/phase6/pilot-interactive';BUNDLE=SRC/'data/embedded-preparation/review-final'
UNIT=Path('/etc/systemd/system/jarvis-hermes-pilot-system.service');NAME=UNIT.name
BACKUPS=Path('/var/backups/jarvis-hermes');FLAG=Path('/home/user/gateway/data/hermes-panel-switch.json')
ORIGIN='https://192.0.2.16:8788';PREFIX='/api/jarvis/hermes-panel'
REVIEW_SHA='d0ceb86f8e813928b72b8f7182fd650f7fe1de11ee9656a1e585d087a0cf00c9'
COORDINATOR_SHA='dfb3a9e45734c8714837472274d9e3f19fe57e069a2f36529e8db2cbc8e7faa6'
STOPPED=False;BACKUP=None

def sha(raw):return hashlib.sha256(raw).hexdigest()
def command(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
def user_show(unit,prop):return command(['runuser','-u','user','--','env','XDG_RUNTIME_DIR=/run/user/1000','systemctl','--user','show',unit,'-p',prop,'--value'])
def regular(path,uid=None,private=False):
 st=path.lstat()
 if not stat.S_ISREG(st.st_mode) or path.is_symlink() or uid is not None and st.st_uid!=uid or st.st_mode&(0o077 if private else 0o022):raise PermissionError('Unsafe file metadata')
 return st

def tree_size(path,owners):
 total=0
 for p in [path,*path.rglob('*')]:
  s=p.lstat()
  if s.st_uid not in owners or p.is_symlink() or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('Unexpected tree entry')
  if stat.S_ISREG(s.st_mode):total+=s.st_size
 return total

def switch_off():
 if not FLAG.exists() and not FLAG.is_symlink():return True
 regular(FLAG,pwd.getpwnam('user').pw_uid,True)
 if FLAG.stat().st_size>128:raise PermissionError('Flag size')
 return json.loads(FLAG.read_text())=={'enabled':False}

def database_dump(path):
 with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
  if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
  return list(db.iterdump())

def snapshot(source,target):
 if target.exists():raise FileExistsError('Snapshot overwrite forbidden')
 with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as a,sqlite3.connect(target) as b:a.backup(b)
 target.chmod(0o600)

def fresh_access(cfg,human,bridge,now):
 if not re.fullmatch('[A-Za-z0-9_-]{43,128}',human) or not re.fullmatch('[A-Za-z0-9_-]{43,128}',bridge) or hmac.compare_digest(human,bridge):raise ValueError('Independent bounded access required')
 return {**cfg,'bridgeToken':bridge,'humanHash':sha(human.encode()),'expiresAt':int((now+30*86400)*1000),'embeddedPanel':{'enabled':True,'origin':ORIGIN}}

def replace_private(path,raw,uid,gid):
 if path.exists():regular(path,uid,True)
 temp=path.with_name('.'+path.name+'.R-'+secrets.token_hex(8))
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),uid,gid)
 os.replace(temp,path)

def private_report(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def main():
 global STOPPED,BACKUP
 p=argparse.ArgumentParser();p.add_argument('--lot-r-approved',action='store_true');args=p.parse_args()
 if not args.lot_r_approved or os.geteuid()!=0:raise PermissionError('Explicit lot R approval and administrator terminal required; no operation performed')
 account=pwd.getpwnam('jarvis-pilot');uid,gid=account.pw_uid,account.pw_gid
 if not uid or STATE.is_symlink() or STATE.stat().st_uid!=uid or STATE.stat().st_mode&0o077:raise PermissionError('Private existing account/state required')
 marker=STATE/'lot-R-result.json'
 if marker.exists() or marker.is_symlink():raise PermissionError('Prior R attempt exists; inspect it, never repeat blindly')
 if not switch_off():raise PermissionError('Gateway switch must remain off')
 if user_show('jarvis-hermes-pilot.service','ActiveState')!='inactive':raise PermissionError('Old user pilot must stay stopped')
 gateway_pid=user_show('codex-gateway.service','MainPID')
 if user_show('codex-gateway.service','ActiveState')!='active':raise PermissionError('Gateway must already be active')
 reviewed=(SRC/'docs/hermes-embedded/manifest.json').read_bytes()
 if sha(reviewed)!=REVIEW_SHA:raise PermissionError('Reviewed release manifest drift')
 review=json.loads(reviewed)
 gateway_inputs={Path('/home/user/gateway/server.js'):review['gateway_input_sha256'],Path('/home/user/gateway/public/jarvis/index.html'):review['html_input_sha256']}
 for file,expected in gateway_inputs.items():
  if sha(file.read_bytes())!=expected:raise PermissionError('Gateway input drift; no operation')
 regular(ROOT/'deployment-files.json',0)
 if sha((ROOT/'deployment-files.json').read_bytes())!=review['installed_pilot_manifest_sha256']:raise PermissionError('Installed release drift')
 for name,expected in review['installed_pilot_code_before'].items():
  file=ROOT/name;regular(file,0)
  if sha(file.read_bytes())!=expected:raise PermissionError('Installed code drift')
 regular(UNIT,0)
 if UNIT.read_bytes()!=(ROOT/'ops/pilot-network/jarvis-hermes-pilot-system.service').read_bytes():raise PermissionError('System unit drift')
 files={}
 for name,expected in review['files'].items():
  if not name.startswith('pilot-release/'):continue
  relative=name.removeprefix('pilot-release/');file=BUNDLE/name
  if file.is_symlink() or not file.resolve().is_relative_to(BUNDLE.resolve()):raise PermissionError('Candidate path')
  raw=file.read_bytes()
  if sha(raw)!=expected:raise PermissionError('Candidate code fingerprint mismatch')
  files[relative]=raw
 coordinator=(SRC/'ops/pilot-network/install-system-pilot.py').read_bytes()
 if sha(coordinator)!=COORDINATOR_SHA:raise PermissionError('Supervised coordinator drift')
 for name in ['config.json','operator.token','memory.sqlite','audit.jsonl']:regular(STATE/name,uid,True)
 for name in ['config.json','operator.token']:regular(OLD/name,pwd.getpwnam('user').pw_uid,True)
 old_original={n:(OLD/n).read_bytes() for n in ['config.json','operator.token']}
 oldcfg=json.loads(old_original['config.json']);cfg=json.loads((STATE/'config.json').read_bytes());oldhuman=(STATE/'operator.token').read_text()
 if cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False or cfg.get('frontPort')!=8796 or cfg.get('bridgePort')!=8797 or cfg.get('origin')!='http://127.0.0.1:8796':raise PermissionError('Synthetic loopback topology required')
 if cfg.get('missionLimits')!={'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0} or cfg.get('embeddedPanel') is not None:raise PermissionError('Existing profile differs')
 if sha(old_original['operator.token'])!=oldcfg.get('humanHash'):raise PermissionError('Historical operator/hash mismatch')
 if sha(oldhuman.encode())!=cfg.get('humanHash'):raise PermissionError('Existing private operator/hash mismatch')
 comparisons={'bridge_shared':hmac.compare_digest(oldcfg['bridgeToken'],cfg['bridgeToken']),'human_shared':hmac.compare_digest(old_original['operator.token'],oldhuman.encode()),'private_human_hash_consistent':True}
 code_bytes=tree_size(ROOT,{0});state_bytes=tree_size(STATE,{0,uid});dbbytes=(STATE/'memory.sqlite').stat().st_size
 free=shutil.disk_usage('/var/backups').free
 need=2*code_bytes+2*state_bytes+4*dbbytes+sum(map(len,files.values()))+16*1024*1024
 if free<need+256*1024*1024:raise OSError('Insufficient space and reserve; no write or purge')
 if os.stat(ROOT.parent).st_dev!=os.stat('/var/backups').st_dev:raise OSError('Cross-filesystem atomic release move not approved')
 if BACKUPS.exists():
  st=BACKUPS.lstat()
  if not stat.S_ISDIR(st.st_mode) or BACKUPS.is_symlink() or st.st_uid!=0 or st.st_mode&0o077:raise PermissionError('Root-only backup parent required')
 # All preconditions and the disk check precede the first explicit write.
 BACKUPS.mkdir(mode=0o700,exist_ok=True)
 stamp=datetime.now(ZoneInfo('Europe/Zurich')).strftime('%Y%m%dT%H%M%S%z')+'-'+secrets.token_hex(4)
 BACKUP=BACKUPS/('R-'+stamp);BACKUP.mkdir(mode=0o700)
 (BACKUP/'coordinator.py').write_bytes(coordinator);(BACKUP/'coordinator.py').chmod(0o400)
 (BACKUP/'unit.service').write_bytes(UNIT.read_bytes());(BACKUP/'unit.service').chmod(0o600)
 command(['systemctl','stop',NAME]);STOPPED=True
 if command(['systemctl','show',NAME,'-p','ActiveState','--value'])!='inactive':raise RuntimeError('Pilot did not stop')
 with sqlite3.connect(f'file:{STATE/"memory.sqlite"}?mode=ro',uri=True) as db:
  if db.execute("SELECT count(*) FROM mm_memories WHERE owner!='phase3-synthetic' OR scope!='private'").fetchone()[0]:raise PermissionError('Non-synthetic memory')
  if db.execute("SELECT count(*) FROM mm_missions WHERE owner!='phase3-synthetic' OR scope!='private'").fetchone()[0]:raise PermissionError('Non-synthetic mission')
  for row in db.execute('SELECT source FROM mm_events'):
   if not json.loads(row[0]).get('ref','').startswith(('synthetic://doselab/','mission://')):raise PermissionError('Unexpected provenance')
 shutil.copytree(STATE,BACKUP/'state',symlinks=False)
 if any((STATE/n).read_bytes()!=(BACKUP/'state'/n).read_bytes() for n in ['config.json','operator.token']):raise ValueError('Private backup differs')
 snapshot(STATE/'memory.sqlite',BACKUP/'sqlite-snapshot.sqlite');snapshot(BACKUP/'sqlite-snapshot.sqlite',BACKUP/'sqlite-restore-check.sqlite')
 before=database_dump(STATE/'memory.sqlite')
 if before!=database_dump(BACKUP/'sqlite-restore-check.sqlite') or before!=database_dump(BACKUP/'state/memory.sqlite'):raise ValueError('Backup/restore mismatch')
 private_report(marker,{'passed':False,'status':'in_progress','backup':str(BACKUP),'gateway_modified':False})
 candidate=ROOT.with_name('.jarvis-hermes-pilot-R-'+stamp);candidate.mkdir(mode=0o755)
 for relative,raw in files.items():
  target=candidate/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(0o444)
 for name,expected in json.loads((candidate/'deployment-files.json').read_text()).items():
  if sha((candidate/name).read_bytes())!=expected:raise PermissionError('Staged layout mismatch')
 if (candidate/'ops/pilot-network/jarvis-hermes-pilot-system.service').read_bytes()!=UNIT.read_bytes():raise PermissionError('Unit change not allowed in R')
 os.rename(ROOT,BACKUP/'release')
 os.rename(candidate,ROOT)
 for name,expected in review['installed_pilot_code_before'].items():
  if sha((BACKUP/'release'/name).read_bytes())!=expected:raise ValueError('Release backup mismatch')
 human=secrets.token_urlsafe(32);bridge=secrets.token_urlsafe(32)
 while human in [oldhuman,old_original['operator.token'].decode()]:human=secrets.token_urlsafe(32)
 while bridge in [cfg['bridgeToken'],oldcfg['bridgeToken'],human]:bridge=secrets.token_urlsafe(32)
 fresh=fresh_access(cfg,human,bridge,time.time())
 replace_private(STATE/'operator.token',human.encode(),uid,gid)
 replace_private(STATE/'config.json',(json.dumps(fresh)+'\n').encode(),uid,gid)
 spec=importlib.util.spec_from_file_location('lot_R_coordinator',BACKUP/'coordinator.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 result=mod.supervised_start()
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def call(path,*,token=None,body=None,cookie=None,embedded=False):
  headers={'Origin':ORIGIN if embedded else 'http://127.0.0.1:8796'}
  if token is not None:headers['Authorization']='Bearer '+token
  if cookie:headers['Cookie']=cookie
  if embedded:headers['x-jarvis-panel-origin']=ORIGIN
  if body is not None:headers['Content-Type']='application/json'
  raw=None if body is None else json.dumps(body).encode()
  req=urllib.request.Request(('http://127.0.0.1:8797' if path.startswith('/v1/') else 'http://127.0.0.1:8796')+path,data=raw,headers=headers)
  try:
   with opener.open(req,timeout=3) as response:return response.status,json.load(response),response.headers.get('Set-Cookie')
  except urllib.error.HTTPError as error:return error.code,{},None
 for token in {cfg['bridgeToken'],oldcfg['bridgeToken']}:
  if call('/v1/missions',token=token)[0]!=401:raise PermissionError('Retired bridge credential accepted')
 if call('/v1/missions',token=bridge)[0]!=200:raise PermissionError('New bridge identity denied')
 for token in {oldhuman,old_original['operator.token'].decode()}:
  if call('/api/jarvis/hermes/missions?space=user',token=token)[0]!=401 or call(PREFIX+'/session',body={'token':token},embedded=True)[0]!=401:raise PermissionError('Retired human credential accepted')
 status,_,cookie=call(PREFIX+'/session',body={'token':human},embedded=True)
 if status!=200 or not cookie or 'Secure' not in cookie or 'HttpOnly' not in cookie or 'Path='+PREFIX not in cookie:raise PermissionError('Private embedded session failed')
 cookie=cookie.split(';')[0]
 checks={
  'embedded_anonymous_401':call(PREFIX+'/hermes/missions?space=user',embedded=True)[0]==401,
  'embedded_history_200':call(PREFIX+'/hermes/missions?space=user',cookie=cookie,embedded=True)[0]==200,
  'embedded_cross_space_403':call(PREFIX+'/hermes/missions?space=amelie',cookie=cookie,embedded=True)[0]==403,
  'admission_403':call(PREFIX+'/hermes/missions?space=user',body={'template':'doselab-current'},cookie=cookie,embedded=True)[0]==403,
  'approval_403':call(PREFIX+'/hermes/missions/test-id/approvals?space=user',body={},cookie=cookie,embedded=True)[0]==403,
  'standalone_frontend_404':call('/')[0]==404,
 }
 if not all(checks.values()):raise PermissionError('Embedded ACL or frontend check failed')
 for name in ['config.json','operator.token']:
  regular(STATE/name,uid,True)
  if subprocess.run(['runuser','-u','user','--','test','-r',str(STATE/name)],capture_output=True).returncode!=1:raise PermissionError('Fresh access readable by Codex OS identity')
 if before!=database_dump(STATE/'memory.sqlite'):raise ValueError('Read-only acceptance changed canonical SQLite')
 if any(old_original[n]!=(OLD/n).read_bytes() for n in old_original):raise ValueError('Historical access files changed')
 if any(sha(p.read_bytes())!=expected for p,expected in gateway_inputs.items()) or user_show('codex-gateway.service','MainPID')!=gateway_pid or not switch_off():raise PermissionError('Gateway state changed; stop private pilot')
 report={'passed':True,'lot':'R','backup':str(BACKUP),'disk_checked_before_writes':True,'backup_restore_verified':True,'credential_comparison':comparisons,'retired_access_rejected':True,'fresh_access_unreadable_by_codex_uid':True,'operator_code_file':str(STATE/'operator.token'),'operator_code_printed':False,'origin':ORIGIN,'embedded_read_cancel_only':True,**checks,'sqlite_unchanged':True,'gateway_modified':False,'gateway_restarted':False,'gateway_pid_unchanged':True,'gateway_switch_effectively_off':True,'G_executed':False,'windows_started':False,'new_missions':0,'paid_api_calls':0,'confinement':{k:result[k] for k in ['effective_bpf_hooks','controls_before','controls_after','receiver_witness','runtime_uid_nonroot','gateway_secrets_hidden']}}
 private_report(marker,report);private_report(BACKUP/'result.json',report)
 print(json.dumps(report))
if __name__=='__main__':
 try:main()
 except Exception as error:
  if STOPPED:
   subprocess.run(['systemctl','stop',NAME],capture_output=True)
   if BACKUP:
    try:private_report(BACKUP/'failure.json',{'passed':False,'lot':'R','pilot_stopped':True,'error_type':type(error).__name__,'no_automatic_retry':True})
    except Exception:pass
  print(json.dumps({'passed':False,'lot':'R','pilot_stop_requested':STOPPED,'error_type':type(error).__name__,'reason':str(error),'backup':str(BACKUP) if BACKUP else None,'G_executed':False}),file=sys.stderr)
  raise SystemExit(1)
