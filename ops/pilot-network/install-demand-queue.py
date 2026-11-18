"""Approved queue-only installation. No Windows, supervisor or mission creation.

Run once in the operator's authenticated administrator terminal. Fail closed;
never retry or roll back a live SQLite automatically.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import errno
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import sqlite3
import stat
import subprocess
import time
import traceback
import types

SRC = Path('/home/user/workspace/jarvis-2-memory')
ROOT = Path('/opt/jarvis-hermes-pilot')
STATE = Path('/var/lib/jarvis-hermes-pilot')
GATEWAY = Path('/home/user/gateway')
FLAG = GATEWAY/'data/hermes-panel-switch.json'
PACKAGE = SRC/'data/hermes-demand/deliverable'
PACKAGE_SHA = '0b96327267a67ea05437342626a16428896be94a48a3b877230feb714927154e'
HELPERS = {'install-operational-panel.py': 'af5a3b8ad652727ac13e40cbe356b169ecfb6399bbd6735baf4f73b597c8393f',
           'install-system-pilot.py': '3a33093c734a194aa12e63667a0f8640a7c944107738ba03bc902b51d1df9997',
           'deploy-private-embedded.py': 'b19e6274c9f316d6217593cb324f286c69a51857238a8f1b2636d709b42bcbf6'}
OFF = dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'],False)
BACKUP = None
MUTATED = False
STEP = 'administrator-authentication'
INTERRUPTED_BACKUP = Path('/var/backups/jarvis-hermes/demand-20261116T062635Z-dcab1f2a')
# Read-only baselines from the validated gateway patches. None is installed,
# imported or executed by this installer. server.js historically has mode 0664.
GATEWAY_BASELINES = {
    GATEWAY/'server.js': 'b6e95e20db96b1074ca8ddc5adb460ba916d5f06ba34f1152868b604c88cf9bf',
    GATEWAY/'hermes-embedded-relay.mjs': 'dbe9f1917fc73c6ef0ffa7a5d717bbc1a91d6d216b945b5de2c331ba45422d54',
    GATEWAY/'hermes-embedded-contract.mjs': 'ea886f48a9d4a65d4973278e08138316fdca200323584be4e411e815f88dab10',
    GATEWAY/'public/jarvis/index.html': 'db4cca2d3b8127d0bf5128ec6d273af280d673e2f76dfc0739dd443bcf2f6a1f',
    Path('/home/user/workspace/jarvis/backend.mjs'): 'd605e09029a9f1949d67dd1cc2689c1cc78d7e66ccdb710be3e8ddb93fe50c2c',
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def checked(path, expected=None, uid=None, private=False):
    for p in [path,*path.parents]:
        if p.is_symlink():raise PermissionError('Symlink refused')
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & (0o077 if private else 0o022):raise PermissionError('Unsafe file mode')
    if uid is not None and st.st_uid!=uid:raise PermissionError('Unexpected owner')
    raw=path.read_bytes()
    if expected is not None and sha(raw)!=expected:raise PermissionError('Fingerprint drift')
    return raw

def observed_gateway_file(path, expected, owner, *, allow_group_write=False):
    """Observe existing gateway code; never reuse for installation targets."""
    for p in [path,*path.parents]:
        if p.is_symlink():raise PermissionError('Observed gateway symlink')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno());mode=stat.S_IMODE(st.st_mode)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=owner.pw_uid or st.st_gid!=owner.pw_gid:raise PermissionError('Observed gateway ownership')
        if mode not in ({0o600,0o644,0o664} if allow_group_write else {0o600,0o644}):raise PermissionError('Observed gateway permissions')
        if mode&0o020:
            members=set(grp.getgrgid(st.st_gid).gr_mem)
            members.update(u.pw_name for u in pwd.getpwall() if u.pw_gid==st.st_gid)
            if members!={owner.pw_name}:raise PermissionError('Additional gateway write identity')
        raw=f.read();end=os.fstat(f.fileno())
    def identity(s):return (s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if sha(raw)!=expected or identity(st)!=identity(end) or identity(st)!=identity(path.lstat()):raise PermissionError('Observed gateway drift')
    return (expected,*identity(st))

def gateway_observation():
    owner=pwd.getpwnam('user')
    return {p:observed_gateway_file(p,digest,owner,allow_group_write=p==GATEWAY/'server.js') for p,digest in GATEWAY_BASELINES.items()}

def load(name):
    raw=checked(SRC/'ops/pilot-network'/name,HELPERS[name])
    m=types.ModuleType(name);m.__file__=str(SRC/'ops/pilot-network'/name)
    exec(compile(raw,m.__file__,'exec'),m.__dict__)
    return m

def replace_code(path, raw, uid, gid):
    if path.exists():checked(path,uid=uid)
    temp=path.with_name('.'+path.name+'.demand-'+secrets.token_hex(8))
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),uid,gid);os.fchmod(f.fileno(),0o644)
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def candidate():
    m=json.loads(checked(PACKAGE/'manifest.json',PACKAGE_SHA));files={}
    for name,digest in m['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise PermissionError('Artifact path')
        files[name]=checked(PACKAGE/name,digest)
    old=json.loads(checked(ROOT/'deployment-files.json',uid=0))
    for name,digest in old.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise PermissionError('Installed path')
        checked(ROOT/name,digest,0)
    for row in m['private_delta']:
        target=ROOT/row['path']
        if row['before'] is None:
            if target.exists() or target.is_symlink():raise PermissionError('New target exists')
        else:checked(target,row['before'],0)
    if m['frontend']['target']!=str(GATEWAY/'public/jarvis/hermes-embedded.js'):raise PermissionError('Frontend target')
    checked(Path(m['frontend']['target']),m['frontend']['before'],pwd.getpwnam('user').pw_uid)
    return m,files

def profile(cfg, scheduler, accepting):
    if cfg.get('operations')!=OFF or cfg.get('onDemand') is not None:raise PermissionError('Expected disabled original profile')
    if (cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False
        or cfg.get('frontPort')!=8796 or cfg.get('bridgePort')!=8797
        or cfg.get('origin')!='http://127.0.0.1:8796'
        or cfg.get('embeddedPanel')!={'enabled':True,'origin':'https://192.0.2.16:8788'}
        or cfg.get('expiresAt',0)<=time.time()*1000
        or cfg.get('missionLimits')!={'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}
        or not isinstance(scheduler,str) or len(scheduler)<43 or scheduler==cfg.get('bridgeToken')):raise PermissionError('Reviewed queue-only policy')
    return {**cfg,'operations':{**OFF,'admissionEnabled':accepting,'textEnabled':accepting},
            'onDemand':{'accepting':accepting,'executionEnabled':False,'schedulerToken':scheduler,'runtime':None,'commissioned':True}}

def wait_private_ports(*, ports=(8796,8797), seconds=75, clock=time.monotonic, sleep=time.sleep, socket_factory=socket.socket):
    """Retain the coordinator's exact raw-bind check; never set SO_REUSEADDR.
    TIME_WAIT after our prior HTTP checks can outlive the stopped service.
    An actual listener always refuses, rather than waiting for or stopping it.
    """
    deadline=clock()+seconds;announced=False
    while True:
        for table in ['/proc/net/tcp','/proc/net/tcp6']:
            for line in Path(table).read_text().splitlines()[1:]:
                cells=line.split()
                if int(cells[1].split(':')[1],16) in ports and cells[3]=='0A':raise PermissionError('Unexpected private-port listener')
        busy=False
        for port in ports:
            with socket_factory() as s:
                try:s.bind(('127.0.0.1',port))
                except OSError as e:
                    if e.errno!=errno.EADDRINUSE:raise
                    busy=True
        if not busy:return
        if clock()>=deadline:raise TimeoutError('Private ports did not quiesce')
        if not announced:
            print(json.dumps({'event':'waiting-for-private-port-release','maximum_seconds':seconds,'services_started':False}),flush=True);announced=True
        sleep(.25)

def validate_migrated_tables(before, after):
    if any(after.get(k)!=v for k,v in before.items()) or set(after)-set(before)!={'p6q_jobs','p6q_keys'}:raise PermissionError('Unexpected SQLite mutation')
    if after['p6q_jobs'] or after['p6q_keys']:raise PermissionError('No production mission permitted')

def resume_acceptance():
    """Only the known interrupted installation; no file reinstall or DB restore."""
    global BACKUP,MUTATED,STEP
    BACKUP=INTERRUPTED_BACKUP;STEP='resume-verified-installation'
    manifest=json.loads(checked(PACKAGE/'manifest.json',PACKAGE_SHA))
    for name,digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise PermissionError('Artifact path')
        checked(PACKAGE/name,digest)
    installed=json.loads(checked(ROOT/'deployment-files.json',sha(checked(PACKAGE/'private-release/deployment-files.json')),0))
    for name,digest in installed.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise PermissionError('Installed path')
        checked(ROOT/name,digest,0)
    helper=load('install-operational-panel.py');coordinator=load('install-system-pilot.py');writer=load('deploy-private-embedded.py')
    coordinator.verify_layout()
    account=pwd.getpwnam('jarvis-pilot');operator=pwd.getpwnam('user')
    checked(Path(manifest['frontend']['target']),manifest['frontend']['after'],operator.pw_uid)
    STEP='resume-known-backup-and-policy'
    st=BACKUP.lstat()
    if not stat.S_ISDIR(st.st_mode) or BACKUP.is_symlink() or st.st_uid!=0 or st.st_mode&0o077:raise PermissionError('Private root backup required')
    if (BACKUP/'resume-result.json').exists():raise PermissionError('Successful resume already recorded')
    old_cfg=json.loads(checked(BACKUP/'config.json',uid=0,private=True))
    cfg=json.loads(checked(STATE/'config.json',uid=account.pw_uid,private=True))
    scheduler=cfg.get('onDemand',{}).get('schedulerToken')
    if cfg!=profile(old_cfg,scheduler,True):raise PermissionError('Interrupted queue-only config drift')
    human=checked(STATE/'operator.token',uid=account.pw_uid,private=True).decode()
    if sha(human.encode())!=cfg.get('humanHash') or human in [scheduler,cfg.get('bridgeToken')]:raise PermissionError('Distinct private identities')
    if json.loads(checked(FLAG,uid=operator.pw_uid,private=True))!={'enabled':True,'admissionEnabled':False,'voiceEnabled':False}:raise PermissionError('Closed relay required')
    saved=json.loads(checked(BACKUP/'release/deployment-files.json',uid=0))
    for name,digest in saved.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise PermissionError('Backup path')
        checked(BACKUP/'release'/name,digest,0)
    checked(BACKUP/'frontend.js',manifest['frontend']['before'],0,private=True)
    STEP='resume-unchanged-sqlite'
    for name in ['memory.sqlite','restore-check.sqlite']:checked(BACKUP/name,uid=0,private=True)
    before=helper.tables(BACKUP/'memory.sqlite')
    if before!=helper.tables(BACKUP/'restore-check.sqlite'):raise PermissionError('Backup restore mismatch')
    after=helper.tables(STATE/'memory.sqlite');validate_migrated_tables(before,after)
    helper.validate_synthetic(STATE/'memory.sqlite')
    STEP='resume-stopped-service'
    if coordinator.run(['systemctl','show',coordinator.NAME,'-p','ActiveState','--value']) not in ['inactive','failed']:raise PermissionError('Private service must be stopped')
    for unit in ['jarvis-hermes-supervisor.service','jarvis-hermes-private-boot.service','jarvis-hermes-confinement.service']:
        if subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True).stdout.strip() not in ['inactive','failed','unknown']:raise PermissionError('Execution supervisor present')
    pid=helper.user_command('show','codex-gateway.service','-p','MainPID','--value');protected=gateway_observation()
    if not pid.isdigit() or int(pid)<=0:raise PermissionError('Active gateway required')
    STEP='resume-port-quiescence';wait_private_ports()
    STEP='resume-confinement';MUTATED=True
    confinement=coordinator.supervised_start()
    # Keep the gateway relay closed while checking human authentication/ACLs.
    STEP='resume-closed-relay-acceptance';public_acceptance(helper,human,False)
    if helper.tables(STATE/'memory.sqlite')!=after:raise PermissionError('Unexpected production write')
    STEP='resume-enable-queue-only'
    writer.replace_private(FLAG,b'{"enabled":true,"admissionEnabled":true,"voiceEnabled":false}\n',operator.pw_uid,operator.pw_gid)
    public_acceptance(helper,human,True)
    code,raw,_=helper.connect(helper.ORIGIN+'/jarvis/hermes-embedded.js')
    if code!=200 or sha(raw)!=manifest['frontend']['after']:raise PermissionError('HTTPS frontend mismatch')
    if helper.tables(STATE/'memory.sqlite')!=after:raise PermissionError('Unexpected production write')
    if helper.user_command('show','codex-gateway.service','-p','MainPID','--value')!=pid or gateway_observation()!=protected:raise PermissionError('Gateway changed')
    report={'passed':True,'resumed':True,'backup':str(BACKUP),'backup_restore_verified':True,'accepting':True,'executionEnabled':False,'new_missions':0,'windows_started':False,'supervisor_started':False,'gateway_restarts':0,'history_preserved':True,'https_frontend_verified':True,'real_auth_acl_checked':True,'confinement':confinement,'first_production_submission':'left_to_user','url':helper.ORIGIN+'/jarvis/'}
    with (BACKUP/'resume-result.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

def public_acceptance(helper, human, accepting):
    base=helper.ORIGIN+helper.PREFIX
    headers={'Origin':helper.ORIGIN,'x-jarvis-panel-origin':helper.ORIGIN}
    def req(path,method='GET',body=None,cookie=None):
        return helper.connect(base+path,method=method,body=body,headers={**headers,**({'Cookie':cookie} if cookie else {})})
    if req('/hermes/missions?space=user')[0]!=401:raise PermissionError('Anonymous history')
    code,_,reply=req('/session','POST',{'token':human})
    cookie=reply.get('Set-Cookie','')
    if code!=200 or not all(v in cookie for v in ['HttpOnly','Secure','SameSite=Strict','Path='+helper.PREFIX+';']):raise PermissionError('Human authentication')
    cookie=cookie.split(';')[0]
    try:
        for path,expected in [('/hermes/missions?space=user',200),('/hermes/missions?space=amelie',403)]:
            if req(path,cookie=cookie)[0]!=expected:raise PermissionError('Space ACL')
        code,raw,_=req('/hermes/config',cookie=cookie);cfg=json.loads(raw) if code==200 else {}
        if code!=200 or any(cfg.get(k) is not accepting for k in ['enabled','textEnabled']) or cfg.get('voiceEnabled') is not False:raise PermissionError('Queue flags')
        code,raw,_=req('/hermes/availability?space=user',cookie=cookie);state=json.loads(raw) if code==200 else {}
        if code!=200 or state.get('dispatch_allowed') is not False:raise PermissionError('Execution must remain off')
        if accepting and (state.get('accepting') is not True or state.get('execution_enabled') is not False):raise PermissionError('Queue-only state')
        # Rejected requests only. Never submit a valid production mission.
        for path in ['/hermes/missions?space=user','/hybrid/ask','/hermes/missions/test-id/approvals?space=user']:
            code,_,_=req(path,'POST',{'_probe':True},cookie)
            if code not in [400,403]:raise PermissionError('Forbidden operation accepted')
    finally:
        if req('/session','DELETE',cookie=cookie)[0] not in [200,204]:raise PermissionError('Probe session revocation')

def main():
    global BACKUP,MUTATED,STEP
    p=argparse.ArgumentParser();actions=p.add_mutually_exclusive_group(required=True)
    actions.add_argument('--install-and-accept-approved',action='store_true')
    actions.add_argument('--diagnose-only',action='store_true')
    actions.add_argument('--resume-acceptance-approved',action='store_true')
    args=p.parse_args()
    if os.geteuid()!=0:raise PermissionError('Administrator terminal required; no operation performed')
    os.umask(0o077)
    if args.resume_acceptance_approved:
        resume_acceptance();return
    STEP='verified-preimages';manifest,files=candidate()
    STEP='verified-installation-helpers'
    helper=load('install-operational-panel.py');coordinator=load('install-system-pilot.py');writer=load('deploy-private-embedded.py')
    STEP='existing-private-layout'
    coordinator.verify_layout()
    STEP='private-service-active'
    if coordinator.run(['systemctl','is-active','jarvis-hermes-pilot-system.service'])!='active':raise PermissionError('Private service not active')
    STEP='execution-supervisor-disabled'
    for unit in ['jarvis-hermes-supervisor.service','jarvis-hermes-private-boot.service','jarvis-hermes-confinement.service']:
        r=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True)
        if r.stdout.strip() not in ['inactive','unknown','failed']:raise PermissionError('Execution supervisor present')
    account=pwd.getpwnam('jarvis-pilot');operator=pwd.getpwnam('user')
    STEP='private-profile-and-identities'
    cfg_raw=checked(STATE/'config.json',uid=account.pw_uid,private=True);cfg=json.loads(cfg_raw)
    human=checked(STATE/'operator.token',uid=account.pw_uid,private=True).decode()
    if sha(human.encode())!=cfg.get('humanHash') or cfg.get('bridgeToken')==human:raise PermissionError('Distinct identities')
    STEP='initial-read-only-relay'
    old_flag=checked(FLAG,uid=operator.pw_uid,private=True)
    if json.loads(old_flag) not in [{'enabled':True},{'enabled':True,'admissionEnabled':False,'voiceEnabled':False}]:raise PermissionError('Initial read-only relay required')
    STEP='queue-only-profile-policy'
    scheduler=secrets.token_urlsafe(48);closed=profile(cfg,scheduler,False);opened=profile(cfg,scheduler,True)
    STEP='synthetic-sqlite-no-replay'
    helper.validate_synthetic(STATE/'memory.sqlite')
    for table in ['p6q_jobs','p6q_keys']:
        with sqlite3.connect('file:'+str(STATE/'memory.sqlite')+'?mode=ro',uri=True) as db:
            if db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():raise PermissionError('Queue already provisioned; no automatic retry')
    STEP='unchanged-gateway-inputs'
    pid=helper.user_command('show','codex-gateway.service','-p','MainPID','--value')
    protected=gateway_observation()
    if args.diagnose_only:
        print(json.dumps({'passed':True,'read_only':True,'local_prechecks_passed':True,'production_modified':False,'services_modified':False,'windows_started':False,'new_missions':0}))
        return
    STEP='disk-and-backup'
    required=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())+4*(STATE/'memory.sqlite').stat().st_size+32*1024**2
    backup_parent=Path('/var/backups/jarvis-hermes')
    for mount in [backup_parent,ROOT,STATE,GATEWAY]:
        if shutil.disk_usage(mount).free<required+256*1024**2:raise PermissionError('Insufficient backup/write margin')
    BACKUP=backup_parent/('demand-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+secrets.token_hex(4));BACKUP.mkdir(mode=0o700)
    shutil.copytree(ROOT,BACKUP/'release');(BACKUP/'config.json').write_bytes(cfg_raw);(BACKUP/'switch.json').write_bytes(old_flag)
    (BACKUP/'frontend.js').write_bytes(checked(Path(manifest['frontend']['target'])))
    writer.snapshot(STATE/'memory.sqlite',BACKUP/'memory.sqlite');writer.snapshot(BACKUP/'memory.sqlite',BACKUP/'restore-check.sqlite')
    before=helper.tables(STATE/'memory.sqlite')
    if before!=helper.tables(BACKUP/'restore-check.sqlite'):raise PermissionError('SQLite restore mismatch')
    # Reuse isolated synthetic tests; no provider and no production submission.
    STEP='isolated-queue-validation'
    subprocess.run(['runuser','-u','user','--','/usr/bin/python3','-B','-m','unittest','memory_manager.phase6.test_demand','-q'],cwd=SRC,check=True,capture_output=True,timeout=90)
    if cfg_raw!=checked(STATE/'config.json',uid=account.pw_uid,private=True) or before!=helper.tables(STATE/'memory.sqlite'):raise PermissionError('State changed before installation')
    candidate() # Recheck all mutable source bytes immediately before mutation.
    STEP='installation-disabled';MUTATED=True
    writer.replace_private(FLAG,b'{"enabled":true,"admissionEnabled":false,"voiceEnabled":false}\n',operator.pw_uid,operator.pw_gid)
    coordinator.run(['systemctl','stop','jarvis-hermes-pilot-system.service'])
    for row in manifest['private_delta']:
        target=ROOT/row['path'];target.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        replace_code(target,files['private-release/'+row['path']],0,0)
    writer.replace_private(STATE/'config.json',(json.dumps(closed)+'\n').encode(),account.pw_uid,account.pw_gid)
    target=Path(manifest['frontend']['target']);replace_code(target,files['frontend/hermes-embedded.js'],operator.pw_uid,operator.pw_gid)
    wait_private_ports();confinement=coordinator.supervised_start()
    STEP='installation-real-acceptance';public_acceptance(helper,human,False)
    after=helper.tables(STATE/'memory.sqlite')
    validate_migrated_tables(before,after)
    code,raw,_=helper.connect(helper.ORIGIN+'/jarvis/hermes-embedded.js')
    if code!=200 or sha(raw)!=manifest['frontend']['after']:raise PermissionError('HTTPS frontend mismatch')
    if helper.user_command('show','codex-gateway.service','-p','MainPID','--value')!=pid or gateway_observation()!=protected:raise PermissionError('Gateway changed')
    STEP='persistent-acceptance-only'
    coordinator.run(['systemctl','stop','jarvis-hermes-pilot-system.service'])
    writer.replace_private(STATE/'config.json',(json.dumps(opened)+'\n').encode(),account.pw_uid,account.pw_gid)
    wait_private_ports();confinement=coordinator.supervised_start()
    writer.replace_private(FLAG,b'{"enabled":true,"admissionEnabled":true,"voiceEnabled":false}\n',operator.pw_uid,operator.pw_gid)
    public_acceptance(helper,human,True)
    if helper.tables(STATE/'memory.sqlite')!=after:raise PermissionError('Unexpected production write')
    if helper.user_command('show','codex-gateway.service','-p','MainPID','--value')!=pid or gateway_observation()!=protected:raise PermissionError('Gateway changed')
    report={'passed':True,'backup':str(BACKUP),'installation_verified':True,'backup_restore_verified':True,'accepting':True,'executionEnabled':False,'supervisor_started':False,'windows_started':False,'new_missions':0,'paid_api_calls':0,'gateway_restarts':0,'history_preserved':True,'https_frontend_verified':True,'real_auth_acl_checked':True,'confinement':confinement,'first_production_submission':'left_to_user','url':helper.ORIGIN+'/jarvis/'}
    (BACKUP/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # No automatic retry/restart/DB replacement. Shut only this private host
        # if mutation began; close its public admission independently.
        if MUTATED:
            try:
                w=load('deploy-private-embedded.py');a=pwd.getpwnam('user')
                w.replace_private(FLAG,b'{"enabled":true,"admissionEnabled":false,"voiceEnabled":false}\n',a.pw_uid,a.pw_gid)
            finally:subprocess.run(['systemctl','stop','jarvis-hermes-pilot-system.service'],capture_output=True)
        frame=traceback.extract_tb(error.__traceback__)[-1]
        print(json.dumps({'passed':False,'step':STEP,'error_type':type(error).__name__,'errno':getattr(error,'errno',None),'function':frame.name,'line':frame.lineno,'backup':str(BACKUP) if BACKUP else None,'production_modified':MUTATED,'automatic_retry':False,'new_missions':0,'windows_started':False}),file=sys.stderr)
        raise SystemExit(1)
