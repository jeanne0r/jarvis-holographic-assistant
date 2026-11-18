"""Accord 3: provision the reviewed, synthetic on-demand executor. Root only.

No gateway restart, boot enablement, model download or mission creation. Starts
the existing Windows lifecycle only through the separately confined supervisor.
Unknown partial installations are never adopted automatically.
"""
import sys
sys.dont_write_bytecode=True
import argparse,base64,hashlib,json,os,pwd,secrets,shutil,sqlite3,stat,subprocess,time,traceback,types
from pathlib import Path,PureWindowsPath

SRC=Path('/home/user/workspace/jarvis-2-memory')
PACKAGE=SRC/'data/hermes-demand/deliverable'
PACKAGE_SHA='0b96327267a67ea05437342626a16428896be94a48a3b877230feb714927154e'
QUEUE_INSTALL_SHA='7902ff2367bc5c3fb9249a11a56f3ae6d5c9e403bbee9b96988cfd48724e726c'
PREVIOUS_EXECUTOR_SHA='e33e873273eb5e53fb0dca6a10899f70100557a42d7a8e48e44a27642a95379f'
EXECUTOR_SHA='359ce68a93afce63ada3ce7cce57c63191a138705ef886e06a2049ac55461033'
ROOT=Path('/opt/jarvis-hermes-supervisor');STATE=Path('/var/lib/jarvis-hermes-supervisor');CFG=Path('/etc/jarvis-hermes-supervisor')
DIRECTORY_FIX_BACKUP=Path('/var/backups/jarvis-hermes/executor-20261116T164844Z-0716bfb1')
APP=Path('/var/lib/jarvis-hermes-pilot');NAME='jarvis-hermes-supervisor'
TEMPLATES={
 'jarvis-hermes-supervisor.service.in':'588d06ea6b86574f86b86719dedd75a339197794fee7ba4fa5523f75e5735074',
 'jarvis-hermes-private-boot.service.in':'d4db0782aaafa208db4526bb32162c88ee53fb9065dc50be9d7801d91340dc33',
 'jarvis-hermes-confinement.service.in':'e3237fb1a85aef9d4560a871fbde1289cb7bc70ac448f9737cb3ae804ba1291d',
 'supervisor-egress.nft.in':'23bacdc00704b54697946e5d62b7a8420271d6dc6e5c3c2152703ddfbca49a62',
 'attest-confinement.py':'0cb2641f4a63e73beb586d029169adeb4e864540ef0800f148763fc10dc3f7fc',
 'start-private-queue.py':'be3cd5f979e3995f3669690287c686a16fde97c2954400d2d744dbe413953b29'}
STEP='administrator-authentication';BACKUP=None;PRIVATE_CHANGED=False;SUPERVISOR_ATTEMPTED=False;ORIGINAL=None
# Consume the private input BEFORE SSH starts: SSH may inherit and drain stdin.
WINDOWS_READONLY_PREFLIGHT="import json,sys;expected=json.load(sys.stdin);from scripts.audit_gpu import collect;from scripts.demand_supervisor import runtime_identity_check;sample=collect();runtime_identity_check(expected);print(json.dumps({'available':sample.get('available')}))"

def sha(raw):return hashlib.sha256(raw).hexdigest()
def command(args,*,timeout=60,input=None,cwd=None):
    return subprocess.run(args,check=True,capture_output=True,input=input,timeout=timeout,cwd=SRC if cwd is None else cwd).stdout
def module(path,expected):
    raw=path.read_bytes()
    if path.is_symlink() or sha(raw)!=expected:raise PermissionError('Administrative helper drift')
    m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m
def write(path,raw,uid=0,gid=0,mode=0o600):
    if path.exists() or path.is_symlink():raise FileExistsError('Never adopt existing provisioned state')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),uid,gid);os.fchmod(f.fileno(),mode)
def normalized(value):
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in {'handle','packets','bytes','metainfo'}}
    if isinstance(value,list):return [normalized(v) for v in value]
    return value

def application_access_code(root,config):
    return """import os,json,sys,traceback
stage='working-directory'
try:
 os.chdir(ROOT_PATH)
 stage='imports'
 from scripts import demand_supervisor as runtime
 private_json=runtime.private_json
 from memory_manager.phase6.demand_queue import Queue
 stage='configuration';c=private_json(CONFIG_PATH,**({'max_bytes':runtime.CONFIG_MAX_BYTES} if hasattr(runtime,'CONFIG_MAX_BYTES') else {}))
 stage='observer-identity';private_json(c['identityFile'])
 stage='windows-bindings';private_json(c['bindingsFile'])
 print(json.dumps({'passed':True,'stage':'complete'}))
except BaseException as e:
 print(json.dumps({'passed':False,'stage':stage,'error_type':type(e).__name__,'errno':getattr(e,'errno',None)}));sys.exit(3)
""".replace('ROOT_PATH',repr(str(root))).replace('CONFIG_PATH',repr(str(config)))

def application_access_probe(cwd):
    args=['runuser','-u',NAME,'--','env','-i','PATH=/usr/bin:/bin','HOME='+str(STATE),'PYTHONDONTWRITEBYTECODE=1','python3','-B','-c',application_access_code(ROOT,CFG/'config.json')]
    result=subprocess.run(args,cwd=cwd,capture_output=True,timeout=30)
    # Tracebacks/stderr can contain source or private values: never export them.
    try:
        value=json.loads(result.stdout) if len(result.stdout)<=4096 else {}
        if not isinstance(value,dict) or set(value)-{'passed','stage','error_type','errno'}:raise ValueError('Unexpected diagnostic')
        if value.get('stage') not in {'working-directory','imports','configuration','observer-identity','windows-bindings','complete'}:raise ValueError('Unexpected stage')
        if value.get('error_type') is not None and (not isinstance(value['error_type'],str) or not value['error_type'].isidentifier()):raise ValueError('Unexpected exception')
        if value.get('errno') is not None and type(value['errno']) is not int:raise ValueError('Unexpected errno')
        return {**value,'passed':value.get('passed') is True and result.returncode==0,'returncode':result.returncode}
    except (ValueError,TypeError):return {'passed':False,'stage':'python-startup','returncode':result.returncode}

def diagnose_application_access():
    queue=module(SRC/'ops/pilot-network/install-demand-queue.py',QUEUE_INSTALL_SHA)
    if sha(queue.checked(ROOT/'scripts/demand_supervisor.py',uid=0)) not in {PREVIOUS_EXECUTOR_SHA,EXECUTOR_SHA}:raise PermissionError('Installed executor differs')
    for n,h in TEMPLATES.items():queue.checked(ROOT/'ops/demand'/n,h,0)
    # Both executions are read-only, with no runtime object or network call.
    old=application_access_probe(SRC);installed=application_access_probe(ROOT)
    print(json.dumps({'read_only':True,'previous_working_directory':old,'installed_working_directory':installed,'services_modified':False,'private_execution_was_modified':False,'gpu_started':False}))

def code_directory_policy(root,gid,*,apply=False,owner_uid=0):
    """Non-secret code only: root writes; dedicated service group reads/traverses.
    State, SSH keys and configuration files are never traversed or chmodded.
    Explicit chmod is necessary because the administrative umask is 0077.
    """
    directories=[]
    for p in [root,*root.rglob('*')]:
        st=p.lstat()
        if p.is_symlink() or st.st_uid!=owner_uid or not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):raise PermissionError('Unsafe code tree')
        if st.st_mode&0o022:raise PermissionError('Writable code tree refused')
        if stat.S_ISDIR(st.st_mode):directories.append(p)
    if apply:
        for p in directories:os.chown(p,owner_uid,gid);p.chmod(0o750)
    return [{'path':str(p.relative_to(root)),'mode':stat.S_IMODE(p.stat().st_mode),'gid':p.stat().st_gid} for p in directories]

def updated_reader_config(cfg):
    bindings=cfg.get('sourceFiles')
    if not isinstance(bindings,dict) or bindings.get('scripts/demand_supervisor.py') not in {PREVIOUS_EXECUTOR_SHA,EXECUTOR_SHA}:raise PermissionError('Pinned source binding required')
    return {**cfg,'sourceFiles':{**bindings,'scripts/demand_supervisor.py':EXECUTOR_SHA}}

def repair_config_reader(queue,writer,user,expected):
    target=ROOT/'scripts/demand_supervisor.py';old=queue.checked(target,uid=0)
    if sha(old) not in {PREVIOUS_EXECUTOR_SHA,EXECUTOR_SHA}:raise PermissionError('Unknown executor source')
    raw=queue.checked(CFG/'config.json',uid=user.pw_uid,private=True);cfg=json.loads(raw)
    if not 16384<len(raw)<=128*1024:raise PermissionError('Recovery covers only the observed bounded config-size failure')
    expected_bindings={n:sha(data) for n,data in expected.items() if Path(n).suffix in {'.py','.mjs','.cjs'}}
    # Full manifest retained: only its executor entry is allowed to change.
    if cfg.get('sourceFiles') not in [expected_bindings,{**expected_bindings,'scripts/demand_supervisor.py':PREVIOUS_EXECUTOR_SHA},{**expected_bindings,'scripts/demand_supervisor.py':EXECUTOR_SHA}]:raise PermissionError('Generated source manifest differs')
    before_source=BACKUP/'reader-size-executor-before.py';before_config=BACKUP/'reader-size-config-before.json'
    if before_source.exists() or before_config.exists():
        queue.checked(before_source,PREVIOUS_EXECUTOR_SHA,0,private=True)
        original=json.loads(queue.checked(before_config,uid=0,private=True))
        if cfg not in [original,updated_reader_config(original)]:raise PermissionError('Config drift since reader repair')
    else:
        if sha(old)!=PREVIOUS_EXECUTOR_SHA:raise PermissionError('Unknown prior reader update')
        write(before_source,old);write(before_config,raw)
    new_source=queue.checked(SRC/'scripts/demand_supervisor.py',EXECUTOR_SHA)
    queue.replace_code(target,new_source,0,0)
    new=updated_reader_config(cfg)
    writer.replace_private(CFG/'config.json',(json.dumps(new)+'\n').encode(),user.pw_uid,user.pw_gid)
    queue.checked(target,EXECUTOR_SHA,0)
    if json.loads(queue.checked(CFG/'config.json',uid=user.pw_uid,private=True))!=new:raise PermissionError('Reader repair failed integrity check')

def resume_directory_fix():
    global STEP,BACKUP,PRIVATE_CHANGED,SUPERVISOR_ATTEMPTED,ORIGINAL
    BACKUP=DIRECTORY_FIX_BACKUP;STEP='resume-known-directory-failure'
    queue=module(SRC/'ops/pilot-network/install-demand-queue.py',QUEUE_INSTALL_SHA)
    helper=queue.load('install-operational-panel.py');coordinator=queue.load('install-system-pilot.py');writer=queue.load('deploy-private-embedded.py')
    st=BACKUP.lstat()
    if BACKUP.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077:raise PermissionError('Known private root backup required')
    if (BACKUP/'directory-fix-result.json').exists():raise PermissionError('Completed recovery never repeated')
    user=pwd.getpwnam(NAME);app=pwd.getpwnam('jarvis-pilot')
    if user.pw_uid==0 or user.pw_gid in [0,app.pw_gid,pwd.getpwnam('user').pw_gid]:raise PermissionError('Dedicated nonprivileged identity required')
    ORIGINAL=json.loads(queue.checked(BACKUP/'config.json',uid=0,private=True))
    if json.loads(queue.checked(APP/'config.json',uid=app.pw_uid,private=True))!=ORIGINAL:raise PermissionError('Queue-only rollback not confirmed')
    for unit in [NAME+'.service','jarvis-hermes-confinement.service']:
        if command(['systemctl','show',unit,'-p','ActiveState','--value']).decode().strip() not in ['inactive','failed']:raise PermissionError('Stopped failed units required')
    if command(['systemctl','show',NAME+'.service','-p','ExecMainStatus','--value']).decode().strip()!='200':raise PermissionError('Recovery only covers observed CHDIR failure')
    STEP='resume-pinned-code-and-units'
    manifest=json.loads(queue.checked(PACKAGE/'manifest.json',PACKAGE_SHA));expected={}
    for n,h in manifest['files'].items():
        if Path(n).is_absolute() or '..' in Path(n).parts:raise PermissionError('Artifact path')
        raw=queue.checked(PACKAGE/n,h)
        if n.startswith('supervisor/'):expected[n.removeprefix('supervisor/')]=raw
    for n,h in TEMPLATES.items():expected['ops/demand/'+n]=queue.checked(SRC/'ops/demand'/n,h)
    queue.checked(SRC/'scripts/demand_supervisor.py',EXECUTOR_SHA)
    installed_executor=queue.checked(ROOT/'scripts/demand_supervisor.py',uid=0)
    if sha(installed_executor) not in {PREVIOUS_EXECUTOR_SHA,EXECUTOR_SHA}:raise PermissionError('Unknown installed executor')
    expected['scripts/demand_supervisor.py']=installed_executor
    for n,raw in expected.items():queue.checked(ROOT/n,sha(raw),0)
    for p in ROOT.rglob('*'):
        if p.is_file() and str(p.relative_to(ROOT)) not in expected:raise PermissionError('Unexpected installed code')
    for n,h in TEMPLATES.items():
        if n.endswith('.service.in'):queue.checked(Path('/etc/systemd/system')/n.removesuffix('.in'),h,0)
    coordinator.verify_layout()
    boot=json.loads(queue.checked(CFG/'boot.json',uid=0,private=True));queue.checked(CFG/'egress.nft',boot['egressFileSha256'],0,private=True)
    loaded=json.loads(command(['nft','-j','list','table','inet','jarvis_hermes_supervisor']))
    if sha(json.dumps(normalized(loaded),sort_keys=True).encode())!=boot['egressRulesSha256']:raise PermissionError('Dedicated egress policy changed')
    if (CFG/'confinement.json').exists():raise PermissionError('Unexpected prior confinement proof')
    STEP='resume-identities-and-history'
    cfg=json.loads(queue.checked(CFG/'config.json',uid=user.pw_uid,private=True));identities=json.loads(queue.checked(CFG/'identity.json',uid=user.pw_uid,private=True))
    if set(identities)!={'schedulerToken','supervisorToken'} or identities['schedulerToken']!=ORIGINAL['onDemand']['schedulerToken']:raise PermissionError('Supervisor identity differs')
    tokens={n:queue.checked(SRC/'data/phase3/windows-20261114'/n,uid=pwd.getpwnam('user').pw_uid,private=True).decode().strip() for n in ['hermes.token','model.token','memory.token']}
    armed=execution_profile(ORIGINAL,tokens,identities['supervisorToken']);hashes={n:sha(v.encode()) for n,v in tokens.items()}
    if cfg.get('runtimeIdentityHashes')!=hashes or cfg.get('remoteCostChf')!=0 or cfg.get('enabled') is not True:raise PermissionError('Reviewed resource/identity policy differs')
    queue.checked(CFG/'windows-bindings.json',sha((PACKAGE/'windows-bindings.json').read_bytes()),user.pw_uid,private=True)
    windows=windows_inventory(manifest['windows_delta']);paths=windows_paths(manifest['windows_delta'])
    if windows.get('idle') is not True or any(windows['hashes'].get(paths[r['path']])!=r['after'] for r in manifest['windows_delta']):raise PermissionError('Reviewed Windows code or runtime differs')
    helper.validate_synthetic(APP/'memory.sqlite')
    before=helper.tables(APP/'memory.sqlite');saved=helper.tables(BACKUP/'memory.sqlite')
    if saved!=helper.tables(BACKUP/'restore-check.sqlite'):raise PermissionError('Backup restoration mismatch')
    mutable={'mm_missions','p2_outbox','p2_events','p6q_jobs','p6q_keys','p6d_workers'}
    if any(before.get(n)!=v for n,v in saved.items() if n not in mutable):raise PermissionError('Canonical history changed')
    with sqlite3.connect('file:'+str(APP/'memory.sqlite')+'?mode=ro',uri=True) as db:
        if db.execute('SELECT 1 FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0 OR attempts!=0 LIMIT 1').fetchone():raise PermissionError('No uncertain execution may be resumed')
    pid=helper.user_command('show','codex-gateway.service','-p','MainPID','--value');gateway=queue.gateway_observation()
    STEP='resume-code-directory-access'
    metadata_file=BACKUP/'directory-metadata-before.json'
    for folder,uid,gid in [(STATE,user.pw_uid,user.pw_gid),(CFG,0,user.pw_gid)]:
        st=folder.lstat()
        modes={0o700,0o750} if folder==CFG and metadata_file.exists() else {0o700}
        if folder.is_symlink() or st.st_uid!=uid or st.st_gid!=gid or stat.S_IMODE(st.st_mode) not in modes:raise PermissionError('Known private directory metadata differs')
    previous=code_directory_policy(ROOT,user.pw_gid)
    if metadata_file.exists():
        recorded=json.loads(queue.checked(metadata_file,uid=0,private=True))
        if {r['path'] for r in recorded}!={r['path'] for r in previous}:raise PermissionError('Directory set changed since recorded recovery')
        for r in previous:
            old=next(v for v in recorded if v['path']==r['path'])
            if (r['mode'],r['gid']) not in {(old['mode'],old['gid']),(0o750,user.pw_gid)}:raise PermissionError('Unexpected directory metadata change')
    else:write(metadata_file,json.dumps(previous).encode())
    code_directory_policy(ROOT,user.pw_gid,apply=True);CFG.chmod(0o750)
    STEP='resume-bounded-config-reader'
    repair_config_reader(queue,writer,user,expected)
    STEP='resume-application-access'
    # Confirm actual nonroot access before enabling any execution.
    result=application_access_probe(ROOT)
    if result.get('passed') is not True:
        print(json.dumps({'event':'application-access-refused','diagnostic':result}),flush=True)
        raise PermissionError('Application access not demonstrated')
    if before!=helper.tables(APP/'memory.sqlite'):raise PermissionError('Queue changed during recovery; review before starting')
    STEP='resume-private-execution';PRIVATE_CHANGED=True
    coordinator.run(['systemctl','stop',coordinator.NAME]);writer.replace_private(APP/'config.json',(json.dumps(armed)+'\n').encode(),app.pw_uid,app.pw_gid)
    queue.wait_private_ports();confinement=coordinator.supervised_start()
    STEP='resume-independent-confinement';SUPERVISOR_ATTEMPTED=True
    command(['systemctl','start',NAME+'.service'],timeout=110)
    proof=json.loads(queue.checked(CFG/'confinement.json',uid=0))
    if proof.get('probe_passed') is not True:raise PermissionError('Independent confinement not demonstrated')
    if helper.user_command('show','codex-gateway.service','-p','MainPID','--value')!=pid or gateway!=queue.gateway_observation():raise PermissionError('Gateway changed')
    report={'passed':True,'resumed':True,'backup':str(BACKUP),'supervisor_active':True,'executionEnabled':True,'confinement_proved':True,'gateway_restarts':0,'mission_created_by_installer':False,'boot_autostart':False,'private_confinement':confinement,'note':'Queued authorized work may now execute; inspect its own result.'}
    write(BACKUP/'directory-fix-result.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))
def execution_profile(cfg,tokens,observer):
    p=cfg.get('onDemand',{})
    if (p.get('commissioned') is not True or p.get('accepting') is not True or p.get('executionEnabled') is not False
        or p.get('runtime') is not None or cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False
        or cfg.get('operations')!={'admissionEnabled':True,'textEnabled':True,'workerEnabled':False,'voiceEnabled':False}
        or cfg.get('missionLimits')!={'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}
        or set(tokens)!={'hermes.token','model.token','memory.token'}):raise PermissionError('Exact commissioned synthetic queue required')
    values=[cfg['bridgeToken'],p['schedulerToken'],observer,*tokens.values()]
    if any(not isinstance(v,str) or not 32<=len(v)<=256 or any(c.isspace() for c in v) for v in values) or len(set(values))!=6:raise PermissionError('Distinct fixed identities required')
    return {**cfg,'onDemand':{**p,'executionEnabled':True,'runtime':{'hermesToken':tokens['hermes.token'],'modelToken':tokens['model.token'],'memoryToken':tokens['memory.token'],'supervisorToken':observer}}}
def remote(script):
    encoded=base64.b64encode(("$ProgressPreference='SilentlyContinue';$ErrorActionPreference='Stop';"+script).encode('utf-16le')).decode()
    args=['runuser','-u','user','--','ssh','-i','/home/user/.ssh/codex_gamer_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=4','codexdiag@192.0.2.96','powershell.exe -NoProfile -NonInteractive -EncodedCommand '+encoded]
    return json.loads(command(args,timeout=45).decode('utf-8-sig'))
def windows_paths(rows):
    allowed={'memory_manager/phase2/mcp.py','memory_manager/phase2/memory_tools.py','memory_manager/phase3/mcp.py'}
    if len(rows)!=3 or {r['path'] for r in rows}!=allowed:raise PermissionError('Exact reviewed Windows patch only')
    return {r['path']:str(PureWindowsPath('C:/JarvisHermesLab/app')/r['path']) for r in rows}
def windows_inventory(rows):
    paths=windows_paths(rows)
    script="$p=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in @(8643,11434,8792,11436)});$out=@{};"
    script+='foreach($n in @('+','.join("'"+p+"'" for p in paths.values())+")){$out[$n]=(Get-FileHash -LiteralPath $n -Algorithm SHA256).Hash.ToLower()};"
    return remote(script+'[pscustomobject]@{idle=($p.Count -eq 0);hashes=$out}|ConvertTo-Json -Compress')
def patch_windows(rows,files,ident):
    paths=windows_paths(rows);inventory=windows_inventory(rows)
    if inventory.get('idle') is not True or any(inventory['hashes'].get(paths[r['path']])!=r['before'] for r in rows):raise PermissionError('Windows runtime or source drift')
    folder='C:\\JarvisHermesLab\\staging\\demand-'+ident
    # Verify every preimage/ACL and every backup before replacing any file.
    script="New-Item -ItemType Directory -Path '"+folder+"' -ErrorAction Stop|Out-Null;"
    for i,r in enumerate(rows):
        target=paths[r['path']];copy=folder+'\\'+str(i)+'.before'
        script+="$p='"+target+"';if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '"+r['before']+"'){throw 'Preimage drift'};"
        script+="Copy-Item -LiteralPath $p -Destination '"+copy+"' -ErrorAction Stop;if((Get-FileHash -LiteralPath '"+copy+"' -Algorithm SHA256).Hash.ToLower() -ne '"+r['before']+"'){throw 'Backup mismatch'};"
        script+="[IO.File]::WriteAllText('"+folder+'\\'+str(i)+".sddl',(Get-Acl -LiteralPath $p).Sddl);"
    remote(script+'[pscustomobject]@{backups_verified=$true}|ConvertTo-Json -Compress')
    for i,r in enumerate(rows):
        target=paths[r['path']];temp=target+'.demand-'+ident
        local=BACKUP/('windows-'+str(i)+'.py');write(local,files['supervisor/'+r['path']])
        # A private source staging file must be traversable only by its operator.
        transfer=SRC/'data'/('demand-transfer-'+ident+'-'+str(i)+'.py')
        write(transfer,local.read_bytes(),pwd.getpwnam('user').pw_uid,pwd.getpwnam('user').pw_gid)
        try:
            command(['runuser','-u','user','--','scp','-q','-i','/home/user/.ssh/codex_gamer_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',str(transfer),'codexdiag@192.0.2.96:'+temp.replace('\\','/')],timeout=30)
        finally:transfer.unlink()
        script="$p='"+target+"';$t='"+temp+"';if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '"+r['before']+"' -or (Get-FileHash -LiteralPath $t -Algorithm SHA256).Hash.ToLower() -ne '"+r['after']+"'){throw 'Concurrent source drift'};"
        script+="[IO.File]::Replace($t,$p,'"+folder+'\\'+str(i)+".replaced');if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '"+r['after']+"' -or (Get-Acl -LiteralPath $p).Sddl -ne [IO.File]::ReadAllText('"+folder+'\\'+str(i)+".sddl')){throw 'Installed source or ACL mismatch'};[pscustomobject]@{verified=$true}|ConvertTo-Json -Compress"
        remote(script)
    return folder

def main():
    global STEP,BACKUP,PRIVATE_CHANGED,SUPERVISOR_ATTEMPTED,ORIGINAL
    p=argparse.ArgumentParser();actions=p.add_mutually_exclusive_group(required=True)
    actions.add_argument('--accord-3-approved',action='store_true');actions.add_argument('--resume-directory-fix-approved',action='store_true');actions.add_argument('--diagnose-application-access',action='store_true');args=p.parse_args()
    if os.geteuid()!=0:raise PermissionError('Authenticated administrator terminal required')
    os.umask(0o077)
    if args.diagnose_application_access:
        diagnose_application_access();return
    if args.resume_directory_fix_approved:
        resume_directory_fix();return
    queue=module(SRC/'ops/pilot-network/install-demand-queue.py',QUEUE_INSTALL_SHA)
    helper=queue.load('install-operational-panel.py');coordinator=queue.load('install-system-pilot.py');writer=queue.load('deploy-private-embedded.py')
    STEP='pinned-artifacts';manifest=json.loads(queue.checked(PACKAGE/'manifest.json',PACKAGE_SHA));files={}
    for n,h in manifest['files'].items():
        if Path(n).is_absolute() or '..' in Path(n).parts:raise PermissionError('Artifact path')
        files[n]=queue.checked(PACKAGE/n,h)
    templates={n:queue.checked(SRC/'ops/demand'/n,h) for n,h in TEMPLATES.items()}
    executor=queue.checked(SRC/'scripts/demand_supervisor.py',EXECUTOR_SHA)
    coordinator.verify_layout();queue.gateway_observation()
    installed=json.loads(queue.checked(coordinator.ROOT/'deployment-files.json',sha(files['private-release/deployment-files.json']),0))
    for n,h in installed.items():queue.checked(coordinator.ROOT/n,h,0)
    STEP='queue-policy-and-identities'
    app=pwd.getpwnam('jarvis-pilot');operator=pwd.getpwnam('user')
    ORIGINAL=json.loads(queue.checked(APP/'config.json',uid=app.pw_uid,private=True))
    human=queue.checked(APP/'operator.token',uid=app.pw_uid,private=True).decode()
    if sha(human.encode())!=ORIGINAL.get('humanHash'):raise PermissionError('Human identity drift')
    observer=secrets.token_urlsafe(48);tokens={}
    for n in ['hermes.token','model.token','memory.token']:
        path=SRC/'data/phase3/windows-20261114'/n
        tokens[n]=queue.checked(path,uid=operator.pw_uid,private=True).decode().strip()
        for account in ['jarvis-pilot','nobody']:
            if subprocess.run(['runuser','-u',account,'--','test','-r',str(path)],capture_output=True).returncode!=1:raise PermissionError('Runtime source readable by unauthorized identity')
    armed=execution_profile(ORIGINAL,tokens,observer)
    if human in [observer,*tokens.values(),ORIGINAL['bridgeToken'],ORIGINAL['onDemand']['schedulerToken']]:raise PermissionError('Shared human/service identity')
    if json.loads(queue.checked(queue.FLAG,uid=operator.pw_uid,private=True))!={'enabled':True,'admissionEnabled':True,'voiceEnabled':False}:raise PermissionError('Exact synthetic relay required')
    STEP='no-replay-or-partial-installation'
    helper.validate_synthetic(APP/'memory.sqlite')
    with sqlite3.connect('file:'+str(APP/'memory.sqlite')+'?mode=ro',uri=True) as db:
        if db.execute('SELECT 1 FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0 OR attempts!=0 LIMIT 1').fetchone():raise PermissionError('Existing/uncertain execution requires review')
        if db.execute("SELECT 1 FROM mm_missions m LEFT JOIN p6q_jobs q ON q.mission_id=m.id WHERE m.state NOT IN ('completed','cancelled','failed') AND (q.mission_id IS NULL OR m.state!='queued') LIMIT 1").fetchone():raise PermissionError('Ambiguous legacy mission')
    for path in [ROOT,STATE,CFG,*[Path('/etc/systemd/system')/n.removesuffix('.in') for n in TEMPLATES if n.endswith('.service.in')]]:
        if path.exists() or path.is_symlink():raise PermissionError('Partial installation exists; never adopt')
    try:pwd.getpwnam(NAME)
    except KeyError:pass
    else:raise PermissionError('Existing OS identity refused')
    if subprocess.run(['nft','list','table','inet','jarvis_hermes_supervisor'],capture_output=True).returncode==0:raise PermissionError('Dedicated network table already exists')
    STEP='private-ssh-preimages'
    diagnostic=queue.checked(Path('/home/user/.ssh/codex_gamer_ed25519'),uid=operator.pw_uid,private=True)
    identity=SRC/'data/phase4/controller-identity'
    hermes_key=queue.checked(identity/'id_ed25519',uid=operator.pw_uid,private=True);hermes_hosts=queue.checked(identity/'known_hosts',uid=operator.pw_uid,private=True)
    # Copy only the pinned host entry, never a whole HOME or unrelated hosts.
    queue.checked(Path('/home/user/.ssh/known_hosts'),uid=operator.pw_uid,private=True)
    host_raw=command(['ssh-keygen','-F','192.0.2.96','-f','/home/user/.ssh/known_hosts'])
    known_hosts=b'\n'.join(line for line in host_raw.splitlines() if line and not line.startswith(b'#'))+b'\n'
    if not known_hosts.strip():raise PermissionError('Pinned diagnostic host key missing')
    STEP='windows-read-only-preflight'
    inventory=windows_inventory(manifest['windows_delta']);paths=windows_paths(manifest['windows_delta'])
    if inventory.get('idle') is not True or any(inventory['hashes'].get(paths[r['path']])!=r['before'] for r in manifest['windows_delta']):raise PermissionError('Windows code/runtime differs')
    # Existing telemetry/identity attestation. No Windows process is started here.
    expected={n:sha(v.encode()) for n,v in tokens.items()}
    STEP='windows-runtime-identity-preflight'
    result=command(['runuser','-u','user','--','python3','-B','-c',WINDOWS_READONLY_PREFLIGHT],input=json.dumps(expected).encode(),timeout=60)
    if json.loads(result).get('available') is not True:raise PermissionError('Windows telemetry unavailable')
    STEP='disk-backup-and-restoration'
    needed=sum(len(v) for n,v in files.items() if n.startswith('supervisor/'))+4*(APP/'memory.sqlite').stat().st_size+64*1024**2
    for path in ['/opt','/etc','/var/lib','/var/backups/jarvis-hermes']:
        if shutil.disk_usage(path).free<needed+256*1024**2:raise PermissionError('Insufficient disk margin')
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+secrets.token_hex(4)
    BACKUP=Path('/var/backups/jarvis-hermes')/('executor-'+ident);BACKUP.mkdir(mode=0o700)
    write(BACKUP/'config.json',json.dumps(ORIGINAL).encode());write(BACKUP/'switch.json',queue.FLAG.read_bytes())
    writer.snapshot(APP/'memory.sqlite',BACKUP/'memory.sqlite');writer.snapshot(BACKUP/'memory.sqlite',BACKUP/'restore-check.sqlite')
    if helper.tables(BACKUP/'memory.sqlite')!=helper.tables(BACKUP/'restore-check.sqlite'):raise PermissionError('Backup restoration mismatch')
    before=helper.tables(APP/'memory.sqlite');pid=helper.user_command('show','codex-gateway.service','-p','MainPID','--value');gateway=queue.gateway_observation()
    STEP='dedicated-linux-identity'
    command(['useradd','--system','--user-group','--no-create-home','--home-dir',str(STATE),'--shell','/usr/sbin/nologin',NAME])
    user=pwd.getpwnam(NAME)
    if user.pw_uid==0 or user.pw_gid in [0,operator.pw_gid,app.pw_gid]:raise PermissionError('Distinct unprivileged UID/GID required')
    ROOT.mkdir(mode=0o755);STATE.mkdir(mode=0o700);os.chown(STATE,user.pw_uid,user.pw_gid);CFG.mkdir(mode=0o750);os.chown(CFG,0,user.pw_gid)
    for n,raw in files.items():
        if n.startswith('supervisor/'):
            dest=ROOT/n.removeprefix('supervisor/');dest.parent.mkdir(parents=True,exist_ok=True,mode=0o755);write(dest,raw,mode=0o644)
    for n,raw in templates.items():
        dest=ROOT/'ops/demand'/n
        if dest.exists():dest.unlink() # Only this new, root-owned code tree.
        write(dest,raw,mode=0o644)
    (ROOT/'scripts/demand_supervisor.py').unlink()
    write(ROOT/'scripts/demand_supervisor.py',executor,mode=0o644)
    for n in ['docs','data','data/phase4','ssh','ssh/hermes']:
        dest=STATE/n;dest.mkdir(parents=True,exist_ok=True,mode=0o700);os.chown(dest,user.pw_uid,user.pw_gid)
    # The lifecycle's doc manifest is read through the dedicated state mount.
    shutil.copytree(ROOT/'docs',STATE/'docs',dirs_exist_ok=True)
    for dest in (STATE/'docs').rglob('*'):
        os.chown(dest,user.pw_uid,user.pw_gid);dest.chmod(0o700 if dest.is_dir() else 0o600)
    for n,raw in [('diagnostic.key',diagnostic),('diagnostic.known_hosts',known_hosts),('hermes/id_ed25519',hermes_key),('hermes/known_hosts',hermes_hosts)]:write(STATE/'ssh'/n,raw,user.pw_uid,user.pw_gid)
    write(CFG/'identity.json',json.dumps({'schedulerToken':ORIGINAL['onDemand']['schedulerToken'],'supervisorToken':observer}).encode(),user.pw_uid,user.pw_gid)
    write(CFG/'windows-bindings.json',files['windows-bindings.json'],user.pw_uid,user.pw_gid)
    STEP='dedicated-network-policy'
    rules=templates['supervisor-egress.nft.in'].decode().replace('@SUPERVISOR_UID@',str(user.pw_uid)).encode();write(CFG/'egress.nft',rules)
    command(['nft','--check','--file',str(CFG/'egress.nft')]);command(['nft','--file',str(CFG/'egress.nft')])
    loaded=json.loads(command(['nft','-j','list','table','inet','jarvis_hermes_supervisor']))
    boot={'coordinatorSha256':sha((ROOT/'ops/pilot-network/install-system-pilot.py').read_bytes()),'egressFileSha256':sha(rules),'egressRulesSha256':sha(json.dumps(normalized(loaded),sort_keys=True).encode())}
    write(CFG/'boot.json',json.dumps(boot).encode())
    conf=json.loads((SRC/'ops/demand/supervisor-config.example.json').read_text());conf.update(enabled=True,bindingsSha256=sha(files['windows-bindings.json']),runtimeIdentityHashes=expected,sourceFiles={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in ROOT.rglob('*') if p.is_file() and p.suffix in ['.py','.mjs','.cjs']})
    write(CFG/'config.json',json.dumps(conf).encode(),user.pw_uid,user.pw_gid)
    code_directory_policy(ROOT,user.pw_gid,apply=True);CFG.chmod(0o750)
    STEP='windows-reviewed-three-file-patch'
    windows_backup=patch_windows(manifest['windows_delta'],files,ident)
    write(BACKUP/'windows-backup.json',json.dumps({'path':windows_backup,'files':manifest['windows_delta']}).encode())
    STEP='systemd-units-staged'
    units=[]
    for n,raw in templates.items():
        if n.endswith('.service.in'):
            dest=Path('/etc/systemd/system')/n.removesuffix('.in');write(dest,raw,mode=0o644);units.append(str(dest))
    command(['systemd-analyze','verify','--man=no',*units]);command(['systemctl','daemon-reload'])
    if before!=helper.tables(APP/'memory.sqlite') or gateway!=queue.gateway_observation():raise PermissionError('State changed during provisioning')
    STEP='private-execution-profile';PRIVATE_CHANGED=True
    coordinator.run(['systemctl','stop',coordinator.NAME])
    writer.replace_private(APP/'config.json',(json.dumps(armed)+'\n').encode(),app.pw_uid,app.pw_gid)
    queue.wait_private_ports();confinement=coordinator.supervised_start()
    STEP='supervisor-start-with-independent-root-proof';SUPERVISOR_ATTEMPTED=True
    # ExecStartPost runs the independent root probe before this start succeeds.
    command(['systemctl','start',NAME+'.service'],timeout=110)
    proof=json.loads(queue.checked(CFG/'confinement.json',uid=0))
    if proof.get('probe_passed') is not True:raise PermissionError('Independent root confinement proof failed')
    if helper.user_command('show','codex-gateway.service','-p','MainPID','--value')!=pid or gateway!=queue.gateway_observation():raise PermissionError('Gateway changed')
    report={'passed':True,'backup':str(BACKUP),'supervisor_active':True,'accepting':True,'executionEnabled':True,'boot_autostart':False,'windows_code_files':3,'windows_backup':windows_backup,'gateway_restarts':0,'mission_created_by_installer':False,'remote_budget_chf':0,'confinement_proved':True,'private_confinement':confinement,'note':'Queued authorized work may now execute; completion requires its own report.'}
    write(BACKUP/'commission-result.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never replay, delete a queue row, restore an old DB, or stop unrelated jobs.
        # A failed start leaves partial provisioning for explicit diagnosis.
        if SUPERVISOR_ATTEMPTED:subprocess.run(['systemctl','stop',NAME+'.service'],capture_output=True,timeout=370)
        if PRIVATE_CHANGED:
            try:
                queue=module(SRC/'ops/pilot-network/install-demand-queue.py',QUEUE_INSTALL_SHA);writer=queue.load('deploy-private-embedded.py');coordinator=queue.load('install-system-pilot.py');app=pwd.getpwnam('jarvis-pilot')
                subprocess.run(['systemctl','stop',coordinator.NAME],capture_output=True,timeout=30)
                writer.replace_private(APP/'config.json',(json.dumps(ORIGINAL)+'\n').encode(),app.pw_uid,app.pw_gid)
                queue.wait_private_ports();coordinator.supervised_start()
            except Exception:pass # Service remains stopped if confinement cannot be proved.
        frame=traceback.extract_tb(error.__traceback__)[-1]
        print(json.dumps({'passed':False,'step':STEP,'error_type':type(error).__name__,'errno':getattr(error,'errno',None),'function':frame.name,'line':frame.lineno,'backup':str(BACKUP) if BACKUP else None,'automatic_retry':False,'mission_created_by_installer':False,'private_execution_was_modified':PRIVATE_CHANGED}),file=sys.stderr)
        raise SystemExit(1)
