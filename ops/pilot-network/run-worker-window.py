"""One approved human-click window. Run ONLY from the administrator terminal.

Reuses installed controller, BPF coordinator and existing owned Windows lifecycle.
Never creates a mission, restarts the gateway or modifies a Windows installation.
"""
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import signal
import socket
import sqlite3
import subprocess
import time
import types
import shutil
import traceback
import tempfile

SRC=Path('/home/user/workspace/jarvis-2-memory')
ROOT=Path('/opt/jarvis-hermes-pilot')
STATE=Path('/var/lib/jarvis-hermes-pilot')
FLAG=Path('/home/user/gateway/data/hermes-panel-switch.json')
UNIT='jarvis-hermes-pilot-system.service'
BASE_SHA='34abd3ab6c1fe9fad12e3eecb2df77bde963335bd528837ecf91d6f438884ed2'
EFFECTIVE_SHA='347f2fed8d9c306f2b646cfba11c2f65973fd803e349e19f764e22d27c4f4c11'
INSTALLER_SHA='af5a3b8ad652727ac13e40cbe356b169ecfb6399bbd6735baf4f73b597c8393f'
COORDINATOR_SHA='3a33093c734a194aa12e63667a0f8640a7c944107738ba03bc902b51d1df9997'
HELPER_SHA='b19e6274c9f316d6217593cb324f286c69a51857238a8f1b2636d709b42bcbf6'
CREDENTIALS_SHA='56a87075e51c7aa2074c4c70ba7367dca33bbdee5639e55a72dc9d333584c684'
NAMES=('hermes.token','model.token','memory.token')
TEXT_REVIEW_SHA='23f9d1daa45c2842575e2abdc073f74584ea5b27a4b0e290c333070695f8a021'
TEXT_CONTRACT_SHA='9ddbdc612aaf2e750c826ca7890f5a580a3fe78cd77870025d6d0876dd5d48c3'
STEP='administrator-authentication'


def load(name,raw):
    m=types.ModuleType(name);exec(compile(raw,name,'exec'),m.__dict__);return m


def read_verified(path,expected):
    if path.is_symlink() or not path.is_file():raise PermissionError('Regular pinned file required')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise PermissionError('Pinned source drift')
    return raw


def credential_value(raw):
    # Match the previously validated credentials.load_token contract. Never
    # rewrite token files or compare file hashes as if they were bearer values.
    if not isinstance(raw,str):raise PermissionError('Private token text required')
    value=raw.strip()
    if not 32<=len(value)<=256 or any(c.isspace() for c in value):
        raise PermissionError('Invalid private runtime token')
    return value


def runtime_config(cfg,tokens,supervisor,*,now,text_enabled=False):
    if set(tokens)!=set(NAMES) or cfg.get('operations')!=dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'],False):
        raise PermissionError('Exact disabled starting profile required')
    values=[tokens[name] for name in NAMES]+[supervisor,cfg['bridgeToken']]
    if any(not isinstance(v,str) or not 32<=len(v)<=256 or any(c.isspace() for c in v) for v in values) or len(set(values))!=5:
        raise PermissionError('Distinct private identities required')
    end=now+300
    runtime=dict(zip(['hermesToken','modelToken','memoryToken'],[tokens[n] for n in NAMES]))
    runtime.update(supervisorToken=supervisor,expiresAt=end,maxMissions=1)
    armed={**cfg,'operations':{'admissionEnabled':True,'textEnabled':text_enabled is True,'workerEnabled':True,'voiceEnabled':False,'runtime':runtime}}
    window={'started_at':now,'expires_at':end,'closed':False,'calls':0,'missions':0,
            'limits':{'calls':6,'missions':1},'local_token_limit':98304}
    return armed,window


def validate_failed_window_receipt(saved,parent):
    # This authorization covers only the observed pre-supervisor BPF failure.
    ident='20261115T195459Z-a89456c1'
    if saved!={'window_id':ident,'backup':str(parent/('worker-'+ident))}:
        raise PermissionError('Unrecognized failed attempt; review required')
    return ident,parent/('worker-'+ident)


def wait_ports(ports,seconds=75):
    until=time.monotonic()+seconds
    while True:
        try:
            for port in ports:
                with socket.socket() as s:s.bind(('127.0.0.1',port))
            return
        except OSError:
            if time.monotonic()>=until:raise PermissionError('Ports unavailable: no listener adopted or killed')
            time.sleep(.5)


PREFLIGHT=r'''
import base64,hashlib,json,sys
from scripts.pilot_phase6b_panel import check_windows_patch
from scripts.pilot_phase5_windows import read_only_preflight
from scripts import pilot_phase4_windows as lifecycle
from scripts.audit_gpu import collect
from memory_manager.phase2.local_model import gpu_available
from memory_manager.phase4.native_trial import ssh_script
expected=json.load(sys.stdin)
print(json.dumps({'event':'preflight-check','stage':'application'}),flush=True)
check_windows_patch(operational=True)
print(json.dumps({'event':'preflight-check','stage':'archive-and-firewall'}),flush=True)
read_only_preflight()
print(json.dumps({'event':'preflight-check','stage':'identities-and-dacl'}),flush=True)
# Attest the old loader before using it under the dedicated Windows identity.
loader=lifecycle.probe("[pscustomobject]@{sha=(Get-FileHash -LiteralPath 'C:\\JarvisHermesLab\\app\\memory_manager\\phase4\\credentials.py' -Algorithm SHA256).Hash.ToLower()}|ConvertTo-Json -Compress")
if loader.get('sha')!='56a87075e51c7aa2074c4c70ba7367dca33bbdee5639e55a72dc9d333584c684':raise PermissionError('Private credential loader drift')
code="import sys,json,hashlib;from pathlib import Path;sys.path.insert(0,'C:/JarvisHermesLab/app');from memory_manager.phase4.credentials import load_token;print(json.dumps({n:hashlib.sha256(load_token(Path('C:/JarvisHermesLab/identity')/n).encode()).hexdigest() for n in ('hermes.token','model.token','memory.token')}))"
statement="import base64;exec(compile(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'),'<read-only-identities>','exec'))"
r=ssh_script("& 'C:\\JarvisHermesLab\\runtime\\Scripts\\python.exe' -I -S -B -c '"+statement.replace("'","''")+"'",timeout=25)
if r.returncode:raise PermissionError('Private Windows token/DACL check refused')
remote=json.loads(r.stdout.decode('utf-8-sig'))
if remote!=expected:raise PermissionError('Named runtime identity mismatch')
print(json.dumps({'event':'preflight-check','stage':'ollama-listener'}),flush=True)
if lifecycle.probe(lifecycle.LISTENER).get('listening') is not False:raise PermissionError('Existing Ollama: no adoption')
print(json.dumps({'event':'preflight-check','stage':'gpu-read-only'}),flush=True)
gpu_available(collect(),8500)
print(json.dumps({'passed':True,'read_only':True,'identities_match':True}),flush=True)
'''

POSTFLIGHT=r'''
import json
from scripts import pilot_phase4_windows as l
r=l.probe("$n=@(8643,11434,8792,11436)|Where-Object{@(Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue).Count -gt 0};[pscustomobject]@{all_closed=($n.Count -eq 0)}|ConvertTo-Json -Compress")
if r.get('all_closed') is not True:raise PermissionError('Windows laboratory listener remains; no forced stop')
print(json.dumps({'passed':True,'windows_lab_listeners_closed':True}))
'''


def as_user(*args):
    return ['runuser','-u','user','--','env','PYTHONDONTWRITEBYTECODE=1',*args]


def public_progress(line):
    """Only approved metadata may cross the private diagnostic boundary."""
    try:data=json.loads(line)
    except (ValueError,UnicodeError):return None
    if not isinstance(data,dict):return None
    if data.get('event')=='source-batch-verified' and type(data.get('files')) is int and 0<=data['files']<=25615:
        return {'event':'source-batch-verified','files':data['files']}
    if data.get('event')=='preflight-check' and data.get('stage') in {
        'application','archive-and-firewall','identities-and-dacl','ollama-listener','gpu-read-only'}:
        return {'event':'preflight-check','stage':data['stage']}
    return None


def child_check(code,*,input=None,timeout=180,runner=as_user):
    global STEP
    outer_step=STEP
    # Unlinked, private temporary files avoid waiting for EOF from an inherited
    # pipe in a descendant. Input is still private stdin, never argv/environment.
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as errors:
        p=subprocess.Popen(runner('python3','-B','-u','-c',code),cwd=SRC,
            stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=out,stderr=errors,start_new_session=True)
        offset=0;buffer=b'';lines=[];last_notice=time.monotonic();until=last_notice+timeout
        def progress():
            nonlocal offset,buffer,last_notice
            # pread leaves the child output file offset untouched.
            raw=os.pread(out.fileno(),1024*1024+1,offset);offset+=len(raw)
            if offset>1024*1024:raise PermissionError('Read-only output bound exceeded')
            buffer+=raw
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1);lines.append(line)
                item=public_progress(line)
                if item:
                    globals()['STEP']=outer_step+':'+item.get('stage','source-batch')
                    print(json.dumps(item),flush=True);last_notice=time.monotonic()
        try:
            if p.stdin:
                p.stdin.write(input.encode());p.stdin.close()
            while p.poll() is None:
                progress()
                if time.monotonic()>=until:raise subprocess.TimeoutExpired('owned-readonly-check',timeout)
                if time.monotonic()-last_notice>=10:
                    print(json.dumps({'event':'preflight-waiting','check':STEP}),flush=True)
                    last_notice=time.monotonic()
                time.sleep(.1)
            progress()
            if buffer:lines.append(buffer)
            if p.returncode:raise PermissionError('Private read-only child check refused; no credentials printed')
            result=json.loads(lines[-1]) if lines else {}
            if not isinstance(result,dict) or result.get('passed') is not True:
                raise PermissionError('Read-only preflight not proven')
            STEP=outer_step
        finally:
            # Only our dedicated LOCAL read-only process group is owned here.
            # No Window process, miner, gateway or service is signalled.
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)


def main():
    global STEP
    p=argparse.ArgumentParser();modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--approved-first-window',action='store_true')
    modes.add_argument('--approved-recovery-window',action='store_true')
    modes.add_argument('--approved-text-window',action='store_true')
    modes.add_argument('--diagnose-only',action='store_true')
    modes.add_argument('--diagnose-windows',action='store_true')
    args=p.parse_args()
    if os.geteuid()!=0:raise PermissionError('Administrator terminal required')
    os.umask(0o077)
    STEP='source-fingerprints'
    i=load('verified_installer',read_verified(SRC/'ops/pilot-network/install-operational-panel.py',INSTALLER_SHA))
    h=load('verified_utilities',read_verified(SRC/'ops/pilot-network/deploy-private-embedded.py',HELPER_SHA))
    c=load('verified_coordinator',read_verified(SRC/'ops/pilot-network/install-system-pilot.py',COORDINATOR_SHA))
    base=json.loads(read_verified(SRC/'docs/HERMES_OPERATIONAL_MANIFEST.json',BASE_SHA))
    effective=json.loads(read_verified(SRC/'docs/HERMES_OPERATIONAL_RECONCILED_MANIFEST.json',EFFECTIVE_SHA))
    if effective.get('base_manifest_sha256')!=BASE_SHA:raise PermissionError('Manifest base mismatch')
    read_verified(SRC/effective['bindings_file'],effective['bindings_sha256'])
    for name,expected in effective['supervisor_sources'].items():read_verified(SRC/name,expected)
    read_verified(SRC/'memory_manager/phase4/credentials.py',CREDENTIALS_SHA)
    for name,expected in base['files'].items():
        if name.startswith('pilot-release/'):read_verified(ROOT/name.removeprefix('pilot-release/'),expected)
    STEP='installed-layout'
    c.verify_layout()
    STEP='gateway-fingerprints'
    text_review=None;text_contract=None
    if args.approved_text_window:
        text_review=json.loads(read_verified(SRC/'docs/HERMES_TEXT_MISSIONS_MANIFEST.json',TEXT_REVIEW_SHA))
        text_contract=load('verified_text_contract',read_verified(SRC/'scripts/text_mission_window.py',TEXT_CONTRACT_SHA))
        if text_review.get('installed_release_manifest_sha256')!=hashlib.sha256((ROOT/'deployment-files.json').read_bytes()).hexdigest():
            raise PermissionError('C requires the unchanged installed private release')
    for row in base['gateway_patch']:
        expected=text_contract.gateway_expected(row,i.CHANGED,text_review) if text_review else row['after'] if row['target'] in i.CHANGED else row['before']
        read_verified(Path(row['target']),expected)
    for path,expected in i.UNCHANGED.items():read_verified(path,expected)
    STEP='service-states'
    if i.command(['systemctl','show',UNIT,'-p','ActiveState','--value'])!='active':raise PermissionError('Private service must be active')
    if i.user_command('show','jarvis-hermes-pilot.service','-p','ActiveState','--value')!='inactive':raise PermissionError('Legacy pilot active')
    STEP='root-authorization-receipt'
    parent=Path('/var/backups/jarvis-hermes')
    if parent.is_symlink() or parent.stat().st_uid!=0 or parent.stat().st_mode&0o077:raise PermissionError('Root-only backup parent required')
    previous_receipt=None
    consumed=parent/('text-operational-window-used.json' if args.approved_text_window else 'first-operational-window-used.json')
    if args.approved_recovery_window:
        i.regular(consumed,0,True)
        previous_receipt=consumed.read_bytes()
        previous_id,previous_backup=validate_failed_window_receipt(json.loads(previous_receipt),parent)
        if previous_backup.is_symlink():raise PermissionError('Backup symlink refused')
        i.regular(previous_backup/'snapshot.sqlite',0,True)
        i.regular(previous_backup/'original-config.json',0,True)
        previous_folder=SRC/'data/operational'/('window-'+previous_id)
        if previous_folder.is_symlink() or not previous_folder.is_dir():raise PermissionError('Missing failure evidence')
        # No Windows supervisor was launched in the failed BPF attempt.
        for forbidden in [previous_folder/'supervisor.log',previous_backup/'result.json',
                          SRC/'docs'/('HERMES_OPERATIONAL_WINDOW_'+previous_id+'.json')]:
            if forbidden.exists() or forbidden.is_symlink():raise PermissionError('Prior execution evidence requires review')
        consumed=parent/'first-operational-window-recovery-used.json'
    if consumed.exists() or consumed.is_symlink():raise PermissionError('Window already consumed; no automatic retry')
    STEP='gateway-health'
    gateway=i.gateway_alive()
    app,operator=pwd.getpwnam('jarvis-pilot'),pwd.getpwnam('user')
    STEP='private-file-permissions'
    for name in ['config.json','operator.token','memory.sqlite']:i.regular(STATE/name,app.pw_uid,True)
    i.regular(FLAG,operator.pw_uid,True)
    original_flag=FLAG.read_bytes()
    if json.loads(original_flag)!={'enabled':True}:raise PermissionError('Read-only panel expected')
    STEP='unarmed-configuration'
    cfg=json.loads((STATE/'config.json').read_bytes())
    if i.configuration(cfg)!=cfg or cfg.get('operations')!=i.OFF:raise PermissionError('Exact unarmed profile required')
    if previous_receipt is not None:
        if json.loads((previous_backup/'original-config.json').read_bytes())!=cfg:
            raise PermissionError('Configuration differs from failed window')
        saved_tables=i.tables(previous_backup/'snapshot.sqlite')
        current_tables=i.tables(STATE/'memory.sqlite')
        if set(saved_tables)!=set(current_tables) or any(saved_tables[n]!=current_tables[n]
                for n in saved_tables if n!='p6d_workers'):
            raise PermissionError('Canonical data changed since failed window')
    # A prior queued mission could run without a fresh click: refuse it.
    STEP='synthetic-sqlite-no-replay'
    i.validate_synthetic(STATE/'memory.sqlite')
    with sqlite3.connect(f'file:{STATE/"memory.sqlite"}?mode=ro',uri=True) as db:
        if db.execute("SELECT 1 FROM mm_missions WHERE state NOT IN ('completed','failed','cancelled') LIMIT 1").fetchone():
            raise PermissionError('Existing active/queued/uncertain mission: no replay')
        original_ids={r[0] for r in db.execute('SELECT id FROM mm_missions')}
    STEP='named-credential-permissions'
    credentials=SRC/'data/phase3/windows-20261114'
    if credentials.is_symlink() or credentials.stat().st_mode&0o077:raise PermissionError('Private credential directory required')
    tokens={}
    for name in NAMES:
        path=credentials/name;i.regular(path,operator.pw_uid,True)
        for user in ['jarvis-pilot','nobody']:
            if subprocess.run(['runuser','-u',user,'--','test','-r',str(path)],capture_output=True).returncode!=1:
                raise PermissionError('Unauthorized credential readability')
        tokens[name]=credential_value(path.read_text())
    STEP='distinct-runtime-identities'
    supervisor=secrets.token_urlsafe(40)
    runtime_config(cfg,tokens,supervisor,now=time.time(),text_enabled=args.approved_text_window) # validate without arming
    if args.diagnose_only:
        print(json.dumps({'passed':True,'read_only':True,'local_prechecks_passed':True,
            'windows_checked':False,'window_started':False,'services_modified':False}))
        return
    STEP='windows-read-only-preflight'
    print(json.dumps({'event':'read-only-preflight','window_started':False}),flush=True)
    child_check(PREFLIGHT,input=json.dumps({n:hashlib.sha256(v.encode()).hexdigest() for n,v in tokens.items()}))
    if args.diagnose_windows:
        print(json.dumps({'passed':True,'read_only':True,'windows_checked':True,
            'window_started':False,'services_modified':False}))
        return
    parent=Path('/var/backups/jarvis-hermes')
    if parent.is_symlink() or parent.stat().st_uid!=0 or parent.stat().st_mode&0o077:raise PermissionError('Root-only backup parent required')
    STEP='disk-and-backup'
    if shutil.disk_usage(parent).free<256*1024*1024+8*(STATE/'memory.sqlite').stat().st_size:raise OSError('Disk reserve unavailable')
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+secrets.token_hex(4)
    backup=parent/('worker-'+ident);backup.mkdir(mode=0o700)
    h.private_report(backup/'original-config.json',cfg)
    (backup/'original-switch.json').write_bytes(original_flag)
    h.snapshot(STATE/'memory.sqlite',backup/'snapshot.sqlite');h.snapshot(backup/'snapshot.sqlite',backup/'restore-check.sqlite')
    if i.tables(backup/'snapshot.sqlite')!=i.tables(backup/'restore-check.sqlite'):raise ValueError('Restore mismatch')
    folder=SRC/'data/operational'/('window-'+ident);folder.mkdir(mode=0o700);os.chown(folder,operator.pw_uid,operator.pw_gid)
    output=SRC/'docs'/('HERMES_OPERATIONAL_WINDOW_'+ident+'.json')
    log=folder/'supervisor.log'
    # Report paths contain no credentials. They allow the agent to observe later.
    report={'passed':False,'window_id':ident,'backup':str(backup),'supervisor_report':str(output),
            'gateway_restarts':0,'mission_created_by_script':False,'new_missions':0,'paid_api_calls':0}
    process=None;changed=False;armed=None;admitted=False;confinement=None
    def stop_signal(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
    try:
        STEP='single-use-authorization'
        # The application must not be able to remove its authorization receipt.
        fd=os.open(consumed,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as out:
            json.dump({'window_id':ident,'backup':str(backup),**({'previous_receipt_sha256':hashlib.sha256(previous_receipt).hexdigest()} if previous_receipt is not None else {})},out);out.flush();os.fsync(out.fileno())
        h.replace_private(FLAG,original_flag,operator.pw_uid,operator.pw_gid)
        STEP='private-stop-and-free-ports'
        i.command(['systemctl','stop',UNIT]);changed=True
        wait_ports([8796,8797,11436])
        STEP='private-window-arming'
        armed,window=runtime_config(cfg,tokens,supervisor,now=time.time(),text_enabled=args.approved_text_window)
        h.replace_private(folder/'observer.json',json.dumps({'supervisorToken':supervisor}).encode(),operator.pw_uid,operator.pw_gid)
        h.replace_private(folder/'window.json',json.dumps(window).encode(),operator.pw_uid,operator.pw_gid)
        h.replace_private(STATE/'config.json',json.dumps(armed).encode(),app.pw_uid,app.pw_gid)
        STEP='armed-BPF-start'
        confinement=c.supervised_start()
        # Root imports only the verified, root-owned installed HTTP client.
        sys.path.insert(0,str(ROOT))
        from memory_manager.phase2.local_model import PrivateHTTP
        observer=PrivateHTTP('http://127.0.0.1:8797',supervisor)
        reader=PrivateHTTP('http://127.0.0.1:8797',cfg['bridgeToken'])
        STEP='armed-epoch-and-model-gate'
        epoch=observer('GET','/v1/workers/windows-hermes/epoch')
        if epoch.get('expires_at')!=window['expires_at'] or epoch.get('owned_model_gate_port')!=11436:raise PermissionError('Armed epoch mismatch')
        gate=PrivateHTTP('http://127.0.0.1:11436',tokens['model.token'])
        models=gate('GET','/v1/models').get('data',[])
        if len(models)!=1 or models[0].get('id')!='qwen3.5:4b' or models[0].get('context_length')!=64000:
            raise PermissionError('Pinned model gate mismatch')
        # PrivateHTTP intentionally masks HTTP errors; use the existing status
        # checker here to prove an actual 401 rather than generic unavailability.
        if i.connect('http://127.0.0.1:11436/v1/models',headers={'Authorization':'Bearer not-authorized'})[0]!=401:
            raise PermissionError('Model gate did not reject invalid identity')
        STEP='owned-windows-supervisor'
        with log.open('xb') as sink:
            os.chown(log,operator.pw_uid,operator.pw_gid)
            process=subprocess.Popen(as_user('python3','-B','-m','scripts.run_interactive_hermes',
                '--approved-worker-window','--credentials',str(folder/'observer.json'),
                '--window',str(folder/'window.json'),'--output',str(output.relative_to(SRC))),
                cwd=SRC,stdout=sink,stderr=sink)
        print(json.dumps({'event':'worker-starting','window_id':ident,'status_file':str(folder/'status.json')}),flush=True)
        last={}
        while process.poll() is None and time.time()<window['expires_at']:
            last=reader('GET','/v1/workers/windows-hermes/status')
            if last.get('executions_started',0)>1:raise PermissionError('Multiple executions')
            if last.get('dispatch_allowed') is True and not admitted:
                if i.gateway_alive()!=gateway:raise PermissionError('Gateway changed')
                h.replace_private(FLAG,b'{"enabled":true,"admissionEnabled":true,"voiceEnabled":false}',operator.pw_uid,operator.pw_gid)
                admitted=True
                status={'event':'worker-ready-click-now','window_id':ident,'expires_at':window['expires_at'],
                        'seconds_left':int(window['expires_at']-time.time()),
                        'instruction':('Rédige une demande synthétique DoseLab dans Jarvis et confirme son envoi' if args.approved_text_window else 'Clique maintenant sur Retrouver les cellules DoseLab X4 dans Jarvis'),
                        'template':'doselab-current','textEnabled':args.approved_text_window,'voiceEnabled':False}
                h.replace_private(folder/'status.json',json.dumps(status).encode(),operator.pw_uid,operator.pw_gid)
                print(json.dumps(status),flush=True)
            if last.get('executions_started')==1:
                h.replace_private(FLAG,original_flag,operator.pw_uid,operator.pw_gid)
            time.sleep(.5)
        h.replace_private(FLAG,original_flag,operator.pw_uid,operator.pw_gid)
        process.wait(timeout=max(1,window['expires_at']-time.time()+40))
        if process.returncode or not output.exists():raise RuntimeError('Supervisor failed; inspect private report')
        STEP='result-and-owned-cleanup'
        lifecycle=json.loads(output.read_bytes())
        child_check(POSTFLIGHT,timeout=25)
        report['windows_lab_listeners_closed']=True
        with sqlite3.connect(f'file:{STATE/"memory.sqlite"}?mode=ro',uri=True) as db:
            ids={r[0] for r in db.execute('SELECT id FROM mm_missions')}-original_ids
            if len(ids)>1:raise PermissionError('More than one new mission')
            report['new_missions']=len(ids)
            if ids:
                mid=next(iter(ids));state=db.execute('SELECT state FROM mm_missions WHERE id=?',(mid,)).fetchone()[0]
                calls,used,cost=db.execute('SELECT count(*),coalesce(sum(coalesce(used_tokens,reserved_tokens)),0),coalesce(sum(coalesce(actual_remote_micros,reserved_remote_micros)),0) FROM p2_usage WHERE mission_id=?',(mid,)).fetchone()
                if calls>6 or used>98304 or cost!=0:raise PermissionError('Usage bound violated')
                canonical=reader('GET','/v1/missions/'+mid+'/canonical')
                refs=[r.get('source_ref','') for r in canonical['projection']['items']]
                if not args.approved_text_window and (not refs or any(not r.startswith('synthetic://doselab/') for r in refs)):raise PermissionError('Synthetic provenance missing')
                event=db.execute("SELECT data FROM p2_events WHERE mission_id=? AND event_key='terminal'",(mid,)).fetchone()
                output_text=json.loads(event[0]).get('output','') if event else ''
                if args.approved_text_window:refs,cited=text_contract.result_provenance(canonical['projection'],output_text,db)
                else:cited=any(ref in output_text for ref in refs)
                experience=db.execute('SELECT source FROM mm_events WHERE event_key=?',('mission-result-'+mid,)).fetchone()
                if not experience or json.loads(experience[0]).get('ref')!='mission://'+mid:raise PermissionError('Experience missing')
                report.update(mission_id=mid,mission_state=state,calls=calls,tokens=used,
                    provenance_verified=True,model_cites_source_ref=cited,experience_saved=True)
                report['passed']=state=='completed' and lifecycle.get('passed') is True and cited
    finally:
        if changed:
            h.replace_private(FLAG,original_flag,operator.pw_uid,operator.pw_gid)
            h.replace_private(folder/'status.json',json.dumps({'event':'admission-closed','worker_ready':False,
                'cleanup_pending':True}).encode(),operator.pw_uid,operator.pw_gid)
            # Let the existing lifecycle perform its owned cleanup; never kill miners.
            if process and process.poll() is None:
                try:process.wait(timeout=max(1,(armed['operations']['runtime']['expiresAt']-time.time())+45))
                except subprocess.TimeoutExpired:report['owned_cleanup_unconfirmed']=True
            i.command(['systemctl','stop',UNIT])
            if json.loads((STATE/'config.json').read_bytes())!=(armed if armed is not None else cfg):raise PermissionError('Config changed; leave private service stopped')
            h.replace_private(STATE/'config.json',json.dumps(cfg).encode(),app.pw_uid,app.pw_gid)
            wait_ports([8796,8797,11436])
            report['readonly_confinement']=c.supervised_start()
            if i.gateway_alive()!=gateway:raise PermissionError('Gateway changed')
            if 'mission_id' in report:
                with sqlite3.connect(f'file:{STATE/"memory.sqlite"}?mode=ro',uri=True) as db:
                    if db.execute('SELECT state FROM mm_missions WHERE id=?',(report['mission_id'],)).fetchone()[0]!=report['mission_state']:
                        raise PermissionError('Persistent mission state differs')
                report['mission_persisted_after_private_restart']=True
            report['admission_closed']=True
            report['armed_confinement']=confinement
            report['workerEnabled']=False
            h.private_report(backup/'result.json',report)
            h.replace_private(folder/'result.json',json.dumps(report).encode(),operator.pw_uid,operator.pw_gid)
            h.replace_private(folder/'status.json',json.dumps({'event':'window-closed','worker_ready':False,
                'cleanup_pending':False,'admissionEnabled':False,'workerEnabled':False}).encode(),operator.pw_uid,operator.pw_gid)
        print(json.dumps(report),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as error:
        frames=traceback.extract_tb(error.__traceback__)
        last=frames[-1] if frames else None
        # No exception text, source line, local variable, credential or SQL row.
        print(json.dumps({'passed':False,'error_type':type(error).__name__,'errno':getattr(error,'errno',None),
            'check':STEP,'function':last.name if last else None,'line':last.lineno if last else None,
            'no_automatic_retry':True,'mission_created_by_script':False}),file=sys.stderr)
        raise SystemExit(1)
