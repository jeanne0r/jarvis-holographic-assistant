"""Approved installation only: no admission, runtime, voice patch or provider startup.

Run from an authenticated administrator terminal after closing the voice UI.
Never retries a deployment or performs a second gateway restart automatically.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import sqlite3
import ssl
import stat
import subprocess
import time
import urllib.error
import urllib.request

SRC = Path('/home/user/workspace/jarvis-2-memory')
BUNDLE = SRC / 'data/operational/final'
ROOT = Path('/opt/jarvis-hermes-pilot')
STATE = Path('/var/lib/jarvis-hermes-pilot')
GATEWAY = Path('/home/user/gateway')
FLAG = GATEWAY / 'data/hermes-panel-switch.json'
UNIT = Path('/etc/systemd/system/jarvis-hermes-pilot-system.service')
ORIGIN = 'https://192.0.2.16:8788'
PREFIX = '/api/jarvis/hermes-panel'
MANIFEST_SHA = '34abd3ab6c1fe9fad12e3eecb2df77bde963335bd528837ecf91d6f438884ed2'
HELPER_SHA = 'b19e6274c9f316d6217593cb324f286c69a51857238a8f1b2636d709b42bcbf6'
COORDINATOR_SHA = 'dfb3a9e45734c8714837472274d9e3f19fe57e069a2f36529e8db2cbc8e7faa6'
OFF = dict.fromkeys(['admissionEnabled', 'textEnabled', 'workerEnabled', 'voiceEnabled'], False)
CHANGED = [str(GATEWAY / p) for p in ['hermes-embedded-relay.mjs',
           'hermes-embedded-contract.mjs', 'public/jarvis/hermes-embedded.js']]
UNCHANGED = {
    GATEWAY / 'server.js': 'b6e95e20db96b1074ca8ddc5adb460ba916d5f06ba34f1152868b604c88cf9bf',
    Path('/home/user/workspace/jarvis/backend.mjs'): 'd605e09029a9f1949d67dd1cc2689c1cc78d7e66ccdb710be3e8ddb93fe50c2c',
}
BACKUP = None
PRIVATE_STOPPED = False
MUTATED = False
RESTARTS = 0
STEP = 'preflight'
FAILED_BACKUP = Path('/var/backups/jarvis-hermes/operational-20261115T185027Z-37511961')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, uid=None, private=False, observed_only=False):
    # Reject symlinks in every ancestor, including writable source directories.
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise PermissionError('Symlink path refused')
    st = path.lstat()
    mask = 0o077 if private else 0o002 if observed_only else 0o022
    if not stat.S_ISREG(st.st_mode) or st.st_mode & mask:
        raise PermissionError('Unsafe regular file')
    if uid is not None and st.st_uid != uid:
        raise PermissionError('Unexpected owner')
    return st


def verified(path, expected, uid=None, observed_only=False):
    regular(path, uid, observed_only=observed_only)
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise PermissionError('Fingerprint mismatch: ' + str(path))
    return raw


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def user_command(*args):
    return command(['runuser', '-u', 'user', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
                    'systemctl', '--user', *args])


def load_module(name, raw):
    # Execute only verified bytes; never reopen a mutable source during import.
    import types
    module = types.ModuleType(name)
    exec(compile(raw, name, 'exec'), module.__dict__)
    return module


def candidate():
    manifest = json.loads(verified(SRC / 'docs/HERMES_OPERATIONAL_MANIFEST.json', MANIFEST_SHA))
    verified(BUNDLE / 'manifest.json', MANIFEST_SHA)
    files = {}
    for name, expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise PermissionError('Invalid artifact path')
        files[name] = verified(BUNDLE / name, expected)
    for name, expected in manifest['supervisor_sources'].items():
        verified(SRC / name, expected)
    selected = [row for row in manifest['gateway_patch'] if row['target'] in CHANGED]
    if len(selected) != 3 or {r['target'] for r in selected} != set(CHANGED):
        raise PermissionError('Exact three-file gateway patch required')
    for row in manifest['gateway_patch']:
        verified(Path(row['target']), row['before'], pwd.getpwnam('user').pw_uid)
        if sha(files[row['artifact']]) != row['after']:
            raise PermissionError('Artifact/patch mismatch')
    for path, expected in UNCHANGED.items():
        verified(path, expected, pwd.getpwnam('user').pw_uid, observed_only=True)
    return manifest, files, selected


def configuration(cfg):
    if (cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False
            or cfg.get('frontPort') != 8796 or cfg.get('bridgePort') != 8797
            or cfg.get('origin') != 'http://127.0.0.1:8796'
            or cfg.get('missionLimits') != dict(calls=6, tokens=98304, seconds=240, attempts=1, remoteCostChf=0)
            or cfg.get('embeddedPanel') != dict(enabled=True, origin=ORIGIN)
            or cfg.get('expiresAt', 0) <= time.time()*1000
            or ('operations' in cfg and cfg['operations'] != OFF)):
        raise PermissionError('Existing private profile differs or expired')
    return {**cfg, 'operations': dict(OFF)}


def connect(url, *, method='GET', body=None, headers=None):
    context = ssl.create_default_context(cafile=str(GATEWAY / 'data/certs/gateway.crt'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPSHandler(context=context))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            raise PermissionError('Redirect refused')
    opener.add_handler(NoRedirect())
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
        headers={**({'Content-Type': 'application/json'} if data is not None else {}), **(headers or {})})
    try:
        with opener.open(req, timeout=4) as response:
            raw = response.read(1024*1024+1)
            if len(raw) > 1024*1024:
                raise ValueError('Response bound')
            return response.status, raw, response.headers
    except urllib.error.HTTPError as error:
        return error.code, b'', error.headers


def idle():
    if user_command('show', 'codex-gateway.service', '-p', 'ActiveState', '--value') != 'active':
        raise PermissionError('Gateway not active')
    status, raw, _ = connect('http://127.0.0.1:8787/api/runs')
    # Never persist or print run metadata; conservatively require an empty registry.
    if status != 200 or json.loads(raw).get('runs') != []:
        raise PermissionError('Gateway runs present or unknown')
    pid = user_command('show', 'codex-gateway.service', '-p', 'MainPID', '--value')
    cg = user_command('show', 'codex-gateway.service', '-p', 'ControlGroup', '--value')
    processes = set()
    for file in (Path('/sys/fs/cgroup') / cg.lstrip('/')).rglob('cgroup.procs'):
        processes.update(file.read_text().split())
    if processes != {pid}:
        raise PermissionError('Gateway child task or unknown cgroup')
    return pid


def tables(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity failed')
        result = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = '"' + name.replace('"', '""') + '"'
            result[name] = sorted(repr(row) for row in db.execute('SELECT * FROM ' + quoted))
        return result


def validate_synthetic(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        for table in ['mm_memories', 'mm_missions']:
            if db.execute(f"SELECT count(*) FROM {table} WHERE owner!='phase3-synthetic' OR scope!='private'").fetchone()[0]:
                raise PermissionError('Non-synthetic state')
        if db.execute("SELECT count(*) FROM p2_outbox WHERE state IN ('submitting','submitted','cancel_requested','unknown')").fetchone()[0]:
            raise PermissionError('Uncertain mission: reconcile separately')
        for (source,) in db.execute('SELECT source FROM mm_events'):
            if not json.loads(source).get('ref', '').startswith(('synthetic://doselab/', 'mission://')):
                raise PermissionError('Unexpected provenance')


def accept(base, human):
    headers = {'Origin': ORIGIN, 'x-jarvis-panel-origin': ORIGIN}
    def request(path, *, cookie=None, body=None):
        return connect(base + PREFIX + path, body=body,
                       method='POST' if body is not None else 'GET',
                       headers={**headers, **({'Cookie': cookie} if cookie else {})})
    if request('/hermes/missions?space=user')[0] != 401:
        raise PermissionError('Anonymous access accepted')
    status, _, reply = request('/session', body={'token': human})
    cookie = reply.get('Set-Cookie', '')
    if status != 200 or not all(x in cookie for x in ['HttpOnly', 'Secure', 'SameSite=Strict', 'Path='+PREFIX+';']):
        raise PermissionError('Secure human session failed')
    cookie = cookie.split(';')[0]
    for path, expected in [('/hermes/missions?space=user', 200),
                            ('/hermes/missions?space=amelie', 403)]:
        if request(path, cookie=cookie)[0] != expected:
            raise PermissionError('History/space ACL failed')
    status, raw, _ = request('/hermes/config', cookie=cookie)
    config = json.loads(raw) if status == 200 else {}
    if status != 200 or any(config.get(k) is not False for k in ['enabled', 'textEnabled', 'voiceEnabled']):
        raise PermissionError('Admission/text/voice not disabled')
    # Deliberately invalid payloads cannot create a mission even if a flag drifts.
    for path, body in [('/hermes/missions?space=user', {'_probe': True}),
                       ('/hybrid/ask', {'_probe': True}),
                       ('/hermes/missions/test-id/approvals?space=user', {})]:
        if request(path, cookie=cookie, body=body)[0] != 403:
            raise PermissionError('Forbidden operation accepted')
    # Expire only this acceptance session, never revoke other human sessions.
    if connect(base + PREFIX + '/session', method='DELETE', headers={**headers, 'Cookie': cookie})[0] not in [200, 204]:
        raise PermissionError('Acceptance session logout failed')


def main():
    global BACKUP, PRIVATE_STOPPED, MUTATED, RESTARTS
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--install-approved', action='store_true')
    modes.add_argument('--resume-approved', action='store_true')
    modes.add_argument('--verify-installed', action='store_true')
    parser.add_argument('--voice-closed', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or not (args.install_approved or args.resume_approved or args.verify_installed) or not args.voice_closed:
        raise PermissionError('Administrator terminal, approved lot and closed voice UI required')
    if args.verify_installed:
        return verify_installed()
    if args.resume_approved:
        return resume_install()
    helper = load_module('verified_R_utilities', verified(SRC / 'ops/pilot-network/deploy-private-embedded.py', HELPER_SHA))
    coordinator_raw = verified(SRC / 'ops/pilot-network/install-system-pilot.py', COORDINATOR_SHA)
    manifest, files, selected = candidate()
    coordinator = load_module('verified_start_coordinator', coordinator_raw)
    coordinator.verify_layout()
    if sha((ROOT / 'deployment-files.json').read_bytes()) != manifest['installed_manifest_sha256']:
        raise PermissionError('Installed release drift or already deployed')
    if (BUNDLE / 'pilot-release/ops/pilot-network/jarvis-hermes-pilot-system.service').read_bytes() != UNIT.read_bytes():
        raise PermissionError('Unit changes prohibited')
    if user_command('show', 'jarvis-hermes-pilot.service', '-p', 'ActiveState', '--value') != 'inactive':
        raise PermissionError('Legacy pilot active')
    account, human_account = pwd.getpwnam('jarvis-pilot'), pwd.getpwnam('user')
    marker = STATE / 'operational-install-result.json'
    if marker.exists() or marker.is_symlink():
        raise PermissionError('Prior attempt exists: no blind retry')
    regular(FLAG, human_account.pw_uid, True)
    original_flag = FLAG.read_bytes()
    if json.loads(original_flag) != {'enabled': True}:
        raise PermissionError('Expected existing read-only panel switch')
    regular(STATE / 'config.json', account.pw_uid, True)
    regular(STATE / 'operator.token', account.pw_uid, True)
    cfg = json.loads((STATE / 'config.json').read_bytes())
    fresh = configuration(cfg)
    human = (STATE / 'operator.token').read_text()
    if sha(human.encode()) != cfg.get('humanHash'):
        raise PermissionError('Operator consistency failed')
    # Metadata only: no reading or copying these future runtime secrets.
    credentials = SRC / 'data/phase3/windows-20261114'
    for name in ['hermes.token', 'model.token', 'memory.token']:
        p = credentials / name
        regular(p, human_account.pw_uid, True)
        if credentials.is_symlink() or credentials.stat().st_mode & 0o077:
            raise PermissionError('Private lab credential directory required')
        for identity in ['jarvis-pilot', 'nobody']:
            if subprocess.run(['runuser', '-u', identity, '--', 'test', '-r', str(p)], capture_output=True).returncode != 1:
                raise PermissionError('Lab credential accessible by another identity')
    for port in [8643, 11435, 11436]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    validate_synthetic(STATE / 'memory.sqlite')
    gateway_pid = idle()
    before = tables(STATE / 'memory.sqlite')
    sizes = helper.tree_size(ROOT, {0}) + helper.tree_size(STATE, {0, account.pw_uid})
    need = 4*sizes + sum(map(len, files.values())) + 32*1024*1024
    parent = Path('/var/backups/jarvis-hermes')
    if parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o077:
        raise PermissionError('Root-only backup directory required')
    if shutil.disk_usage(parent).free < need + 256*1024*1024:
        raise OSError('Insufficient disk reserve; no purge')
    if os.stat(ROOT.parent).st_dev != os.stat(parent).st_dev:
        raise OSError('Atomic release move requires same filesystem')
    # First explicit write occurs after all preconditions and disk reserve checks.
    BACKUP = parent / ('operational-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + secrets.token_hex(4))
    BACKUP.mkdir(mode=0o700)
    helper.private_report(BACKUP / 'plan.json', {'manifest_sha256': MANIFEST_SHA, 'gateway_files': [
        {**row, 'mode': stat.S_IMODE(Path(row['target']).stat().st_mode),
         'uid': Path(row['target']).stat().st_uid, 'gid': Path(row['target']).stat().st_gid,
         'original': 'gateway-' + str(index)} for index, row in enumerate(selected)],
        'voice_closed_operator_attestation': True, 'max_gateway_restarts': 1,
        'rollback': 'Switch false immediately; retain latest SQLite and credentials. Restore saved code only after review; second gateway restart needs separate approval.'})
    (BACKUP / 'coordinator.py').write_bytes(coordinator_raw)
    (BACKUP / 'coordinator.py').chmod(0o400)
    (BACKUP / 'unit.service').write_bytes(UNIT.read_bytes())
    for index, row in enumerate(selected):
        path = Path(row['target'])
        raw = verified(path, row['before'], human_account.pw_uid)
        target = BACKUP / ('gateway-' + str(index))
        target.write_bytes(raw)
        target.chmod(0o600)
        if target.read_bytes() != raw:
            raise ValueError('Gateway backup verification failed')
    (BACKUP / 'switch.json').write_bytes(original_flag)
    (BACKUP / 'switch.json').chmod(0o600)
    # Stage only already verified in-memory artifacts; no executable source TOCTOU.
    stage = ROOT.with_name('.jarvis-operational-' + secrets.token_hex(8))
    stage.mkdir(mode=0o755)
    for name, raw in files.items():
        if not name.startswith('pilot-release/'):
            continue
        path = stage / name.removeprefix('pilot-release/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o444)
    for path in stage.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
    helper.replace_private(FLAG, b'{"enabled":false}\n', human_account.pw_uid, human_account.pw_gid)
    MUTATED = True
    command(['systemctl', 'stop', UNIT.name])
    PRIVATE_STOPPED = True
    if command(['systemctl', 'show', UNIT.name, '-p', 'ActiveState', '--value']) != 'inactive':
        raise RuntimeError('Private service did not stop')
    validate_synthetic(STATE / 'memory.sqlite')
    if before != tables(STATE / 'memory.sqlite'):
        raise PermissionError('State changed during preflight')
    shutil.copytree(STATE, BACKUP / 'state')
    helper.snapshot(STATE / 'memory.sqlite', BACKUP / 'snapshot.sqlite')
    helper.snapshot(BACKUP / 'snapshot.sqlite', BACKUP / 'restore-check.sqlite')
    if before != tables(BACKUP / 'restore-check.sqlite') or before != tables(BACKUP / 'state/memory.sqlite'):
        raise ValueError('SQLite restore verification failed')
    if (BACKUP / 'state/config.json').read_bytes() != (STATE / 'config.json').read_bytes():
        raise ValueError('Configuration backup mismatch')
    helper.private_report(marker, {'passed': False, 'status': 'in_progress', 'backup': str(BACKUP)})
    os.rename(ROOT, BACKUP / 'release')
    os.rename(stage, ROOT)
    helper.replace_private(STATE / 'config.json', (json.dumps(fresh)+'\n').encode(), account.pw_uid, account.pw_gid)
    finish_install(helper, coordinator, files, selected, before, fresh, human,
                   original_flag, human_account, gateway_pid, marker)


def resume_state(marker, plan, cfg, old_cfg, human, old_human, before, snapshot, restored):
    """Pure validation: resume only the exact pre-start checkpoint, not a replay."""
    if marker != {'passed': False, 'status': 'in_progress', 'backup': str(FAILED_BACKUP)}:
        raise PermissionError('Unexpected installation checkpoint')
    if plan.get('manifest_sha256') != MANIFEST_SHA or plan.get('max_gateway_restarts') != 1:
        raise PermissionError('Unexpected saved plan')
    fresh = configuration(old_cfg)
    if cfg != fresh or human != old_human or sha(human.encode()) != cfg.get('humanHash'):
        raise PermissionError('State or renewed credentials changed')
    if before != snapshot or snapshot != restored:
        raise PermissionError('SQLite checkpoint/restore differs')
    return fresh


def resume_install():
    global BACKUP, MUTATED, PRIVATE_STOPPED, STEP
    STEP = 'resume-read-only-preflight'
    helper = load_module('verified_R_utilities', verified(SRC / 'ops/pilot-network/deploy-private-embedded.py', HELPER_SHA))
    manifest, files, selected = candidate()
    st = FAILED_BACKUP.lstat()
    if FAILED_BACKUP.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError('Existing root-private backup required')
    for name in ['resume-requested.json', 'gateway-restart-requested.json', 'result.json']:
        if (FAILED_BACKUP / name).exists() or (FAILED_BACKUP / name).is_symlink():
            raise PermissionError('Previous resume/restart/result: review required')
    coordinator_raw = verified(FAILED_BACKUP / 'coordinator.py', COORDINATOR_SHA, 0)
    coordinator = load_module('verified_resume_coordinator', coordinator_raw)
    coordinator.verify_layout()
    if command(['systemctl', 'show', UNIT.name, '-p', 'ActiveState', '--value']) != 'inactive':
        raise PermissionError('Private service must remain stopped')
    if user_command('show', 'jarvis-hermes-pilot.service', '-p', 'ActiveState', '--value') != 'inactive':
        raise PermissionError('Legacy pilot must remain stopped')
    for name, expected in manifest['files'].items():
        if name.startswith('pilot-release/'):
            verified(ROOT / name.removeprefix('pilot-release/'), expected, 0)
    verified(FAILED_BACKUP / 'release/deployment-files.json', manifest['installed_manifest_sha256'], 0)
    saved_map = json.loads((FAILED_BACKUP / 'release/deployment-files.json').read_bytes())
    for name, expected in saved_map.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise PermissionError('Saved layout path denied')
        verified(FAILED_BACKUP / 'release' / name, expected, 0)
    account, human_account = pwd.getpwnam('jarvis-pilot'), pwd.getpwnam('user')
    marker = STATE / 'operational-install-result.json'
    for path, uid in [(marker, 0), (STATE/'config.json', account.pw_uid),
                      (STATE/'operator.token', account.pw_uid), (FLAG, human_account.pw_uid)]:
        regular(path, uid, True)
    cfg = json.loads((STATE/'config.json').read_bytes())
    old_cfg = json.loads((FAILED_BACKUP/'state/config.json').read_bytes())
    human = (STATE/'operator.token').read_text()
    plan = json.loads((FAILED_BACKUP/'plan.json').read_bytes())
    before = tables(STATE/'memory.sqlite')
    fresh = resume_state(json.loads(marker.read_bytes()), plan, cfg, old_cfg, human,
        (FAILED_BACKUP/'state/operator.token').read_text(), before,
        tables(FAILED_BACKUP/'snapshot.sqlite'), tables(FAILED_BACKUP/'restore-check.sqlite'))
    if json.loads(FLAG.read_bytes()) != {'enabled': False}:
        raise PermissionError('Fail-closed panel switch required')
    original_flag = (FAILED_BACKUP/'switch.json').read_bytes()
    if json.loads(original_flag) != {'enabled': True}:
        raise PermissionError('Saved read-only switch differs')
    for index, row in enumerate(selected):
        verified(FAILED_BACKUP/('gateway-'+str(index)), row['before'], 0)
    validate_synthetic(STATE/'memory.sqlite')
    for port in [8796,8797,8643,11435,11436]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',port))
    gateway_pid = idle()
    # No credential content reused; revalidate metadata before proceeding.
    credentials = SRC/'data/phase3/windows-20261114'
    if credentials.is_symlink() or credentials.stat().st_mode & 0o077:
        raise PermissionError('Private lab credential directory required')
    for name in ['hermes.token','model.token','memory.token']:
        regular(credentials/name, human_account.pw_uid, True)
        for identity in ['jarvis-pilot','nobody']:
            if subprocess.run(['runuser','-u',identity,'--','test','-r',str(credentials/name)],capture_output=True).returncode != 1:
                raise PermissionError('Lab credential accessible by another identity')
    need = 256*1024*1024 + 4*(STATE/'memory.sqlite').stat().st_size + sum(map(len,files.values()))
    if shutil.disk_usage(FAILED_BACKUP).free < need:
        raise OSError('Insufficient disk reserve')
    # First write: durable single-use resume record, after verifying the checkpoint.
    BACKUP = FAILED_BACKUP
    fd = os.open(BACKUP/'resume-requested.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,'w') as out:
        json.dump({'requested':True,'verified_checkpoint':True,'gateway_pid':gateway_pid},out)
        out.flush()
        os.fsync(out.fileno())
    MUTATED = True
    PRIVATE_STOPPED = True
    finish_install(helper, coordinator, files, selected, before, fresh, human,
                   original_flag, human_account, gateway_pid, marker)


def gateway_alive(previous_pid=None):
    """Post-start health is distinct from the pre-maintenance idle requirement.

    Jarvis schedules sync two seconds after import. Do not confuse its existing
    child processes with failure of the newly started gateway. No task is killed.
    """
    if user_command('show', 'codex-gateway.service', '-p', 'ActiveState', '--value') != 'active':
        raise PermissionError('Gateway inactive')
    pid = user_command('show', 'codex-gateway.service', '-p', 'MainPID', '--value')
    if not pid.isdecimal() or int(pid) == 0 or pid == previous_pid:
        raise PermissionError('Gateway PID not valid or unchanged')
    status, raw, _ = connect(ORIGIN+'/api/health')
    if status != 200 or json.loads(raw).get('ok') is not True:
        raise PermissionError('Gateway HTTPS health failed')
    return pid


def verify_installed():
    """Finish only the already deployed checkpoint; NO gateway write or restart."""
    global BACKUP, MUTATED, PRIVATE_STOPPED, RESTARTS, STEP
    STEP = 'installed-checkpoint-preflight'
    helper = load_module('verified_R_utilities', verified(SRC/'ops/pilot-network/deploy-private-embedded.py', HELPER_SHA))
    st = FAILED_BACKUP.lstat()
    if FAILED_BACKUP.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError('Root-private checkpoint required')
    for name in ['result.json','verification-requested.json']:
        if (FAILED_BACKUP/name).exists() or (FAILED_BACKUP/name).is_symlink():
            raise PermissionError('Prior result/verification: inspect, never repeat blindly')
    manifest = json.loads(verified(SRC/'docs/HERMES_OPERATIONAL_MANIFEST.json', MANIFEST_SHA))
    files = {name: verified(BUNDLE/name, expected) for name,expected in manifest['files'].items()}
    for name,expected in manifest['supervisor_sources'].items():
        verified(SRC/name,expected)
    selected = [row for row in manifest['gateway_patch'] if row['target'] in CHANGED]
    if len(selected) != 3 or {row['target'] for row in selected} != set(CHANGED):
        raise PermissionError('Exact installed patch required')
    account, operator = pwd.getpwnam('jarvis-pilot'), pwd.getpwnam('user')
    for row in manifest['gateway_patch']:
        verified(Path(row['target']),row['after'] if row['target'] in CHANGED else row['before'],operator.pw_uid)
    for path,expected in UNCHANGED.items():
        verified(path,expected,operator.pw_uid,observed_only=True)
    for name,expected in manifest['files'].items():
        if name.startswith('pilot-release/'):
            verified(ROOT/name.removeprefix('pilot-release/'),expected,0)
    coordinator = load_module('verified_final_coordinator', verified(FAILED_BACKUP/'coordinator.py',COORDINATOR_SHA,0))
    coordinator.verify_layout()
    if command(['systemctl','show',UNIT.name,'-p','ActiveState','--value']) != 'inactive':
        raise PermissionError('Private service must be stopped')
    if user_command('show','jarvis-hermes-pilot.service','-p','ActiveState','--value') != 'inactive':
        raise PermissionError('Legacy pilot must remain stopped')
    for p in [FLAG, STATE/'config.json', STATE/'operator.token']:
        regular(p, operator.pw_uid if p == FLAG else account.pw_uid,True)
    marker = STATE/'operational-install-result.json'
    regular(marker,0,True)
    if json.loads(marker.read_bytes()) != {'passed':False,'status':'in_progress','backup':str(FAILED_BACKUP)}:
        raise PermissionError('Unexpected checkpoint state')
    regular(FAILED_BACKUP/'gateway-restart-requested.json',0,True)
    restart = json.loads((FAILED_BACKUP/'gateway-restart-requested.json').read_bytes())
    if restart.get('requested') is not True:
        raise PermissionError('Recorded restart required')
    gateway_pid = gateway_alive(restart.get('prior_pid'))
    if json.loads(FLAG.read_bytes()) != {'enabled':False}:
        raise PermissionError('Panel must remain fail-closed before verification')
    cfg = json.loads((STATE/'config.json').read_bytes())
    old = json.loads((FAILED_BACKUP/'state/config.json').read_bytes())
    if cfg != configuration(old):
        raise PermissionError('Private configuration changed')
    human = (STATE/'operator.token').read_text()
    if human != (FAILED_BACKUP/'state/operator.token').read_text() or sha(human.encode()) != cfg.get('humanHash'):
        raise PermissionError('Private identity changed')
    before = tables(FAILED_BACKUP/'snapshot.sqlite')
    if before != tables(FAILED_BACKUP/'restore-check.sqlite'):
        raise PermissionError('Restore proof differs')
    current = tables(STATE/'memory.sqlite')
    if any(current.get(name) != rows for name,rows in before.items()):
        raise PermissionError('Canonical tables changed')
    if set(current)-set(before)-{'p6d_workers','p6d_receipts'}:
        raise PermissionError('Unexpected schema additions')
    validate_synthetic(STATE/'memory.sqlite')
    original_flag = (FAILED_BACKUP/'switch.json').read_bytes()
    if json.loads(original_flag) != {'enabled':True}:
        raise PermissionError('Saved read-only switch differs')
    for port in [8796,8797,8643,11435,11436]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',port))
    if shutil.disk_usage(FAILED_BACKUP).free < 256*1024*1024+4*(STATE/'memory.sqlite').stat().st_size:
        raise OSError('Disk reserve unavailable')
    # The only writes are a one-shot receipt, private supervised restart and switch.
    BACKUP = FAILED_BACKUP
    fd = os.open(BACKUP/'verification-requested.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:
        json.dump({'gateway_pid':gateway_pid,'additional_gateway_restarts':0},out)
        out.flush();os.fsync(out.fileno())
    MUTATED = True;PRIVATE_STOPPED = True;RESTARTS = 1
    STEP = 'verification-private-BPF-start'
    confinement = coordinator.supervised_start()
    for port in [8643,11435,11436]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',port))
    STEP = 'verification-private-auth-ACL'
    accept('http://127.0.0.1:8796',human)
    STEP = 'verification-existing-gateway'
    if gateway_alive() != gateway_pid:
        raise PermissionError('Gateway PID changed during verification')
    for path in ['/jarvis/','/jarvis/hermes-embedded.js','/api/jarvis/voice/status','/api/jarvis/live/status']:
        status,raw,_ = connect(ORIGIN+path)
        if status != 200:
            raise PermissionError('Jarvis read-only status failed')
        if path.endswith('/live/status') and json.loads(raw).get('engine') != 'hybrid':
            raise PermissionError('Hybrid engine differs')
    STEP = 'verification-panel-auth-ACL'
    helper.replace_private(FLAG,original_flag,operator.pw_uid,operator.pw_gid)
    accept(ORIGIN,human)
    STEP = 'verification-canonical-state'
    current = tables(STATE/'memory.sqlite')
    if any(current.get(name) != rows for name,rows in before.items()):
        raise PermissionError('Canonical tables changed during verification')
    if json.loads((STATE/'config.json').read_bytes()) != cfg or gateway_alive() != gateway_pid:
        raise PermissionError('State changed during verification')
    report = dict(passed=True,backup=str(BACKUP),gateway_restarts=1,additional_gateway_restarts=0,
        panel_read_cancel_only=True,auth_acl_checked=True,backup_restore_verified=True,
        canonical_tables_unchanged=True,hybrid_unchanged=True,**OFF,
        windows_started=False,new_missions=0,paid_api_calls=0,runtime_credentials_reused=False,
        confinement={k:confinement[k] for k in ['effective_bpf_hooks','controls_before','controls_after',
            'receiver_witness','runtime_uid_nonroot','gateway_secrets_hidden']})
    helper.private_report(BACKUP/'result.json',report)
    helper.private_report(marker,report)
    print(json.dumps(report))


def finish_install(helper, coordinator, files, selected, before, fresh, human,
                   original_flag, human_account, gateway_pid, marker):
    global RESTARTS, STEP
    STEP = 'private-supervised-BPF-start'
    confinement = coordinator.supervised_start()
    for port in [8643, 11435, 11436]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    STEP = 'private-read-only-acceptance'
    accept('http://127.0.0.1:8796', human)
    for name, rows in before.items():
        if tables(STATE / 'memory.sqlite').get(name) != rows:
            raise ValueError('Existing canonical table changed')
    # A changed workload aborts BEFORE replacing files or the one gateway restart.
    if idle() != gateway_pid:
        raise PermissionError('Gateway changed during private installation')
    candidate()  # Recheck active preimages immediately before writes.
    for row in selected:
        path = Path(row['target'])
        mode = regular(path, human_account.pw_uid).st_mode & 0o777
        raw = files[row['artifact']]
        temp = path.with_name('.' + path.name + '.operational-' + secrets.token_hex(6))
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
            os.fchown(out.fileno(), human_account.pw_uid, human_account.pw_gid)
        os.replace(temp, path)
    STEP = 'gateway-restart'
    once = BACKUP / 'gateway-restart-requested.json'
    fd = os.open(once, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump({'requested': True, 'prior_pid': gateway_pid}, out)
        out.flush()
        os.fsync(out.fileno())
    RESTARTS = 1  # Mark BEFORE invoking: never retry even on timeout.
    user_command('restart', 'codex-gateway.service')
    STEP = 'gateway-health-and-read-only-acceptance'
    for attempt in range(40):
        try:
            status, raw, _ = connect(ORIGIN + '/api/health')
            if status == 200 and json.loads(raw).get('ok') is True:
                break
        except OSError:
            pass
        time.sleep(.25)
    else:
        raise RuntimeError('Gateway health unavailable')
    STEP = 'gateway-running-pid'
    gateway_alive(gateway_pid)
    STEP = 'gateway-installed-fingerprints'
    for row in selected:
        verified(Path(row['target']), row['after'], human_account.pw_uid)
    for path, expected in UNCHANGED.items():
        verified(path, expected, human_account.pw_uid, observed_only=True)
    STEP = 'gateway-static-and-hybrid'
    for path in ['/jarvis/', '/jarvis/hermes-embedded.js', '/api/jarvis/voice/status', '/api/jarvis/live/status']:
        status, raw, _ = connect(ORIGIN + path)
        if status != 200:
            raise RuntimeError('Jarvis status/static acceptance failed')
        if path.endswith('/live/status') and json.loads(raw).get('engine') != 'hybrid':
            raise RuntimeError('Hybrid engine differs')
        if path.endswith('hermes-embedded.js') and sha(raw) != selected[2]['after']:
            raise RuntimeError('Served asset differs')
    helper.replace_private(FLAG, original_flag, human_account.pw_uid, human_account.pw_gid)
    STEP = 'gateway-panel-auth-ACL'
    accept(ORIGIN, human)
    if json.loads((STATE / 'config.json').read_bytes()) != fresh:
        raise PermissionError('Private flags changed')
    after = tables(STATE / 'memory.sqlite')
    if any(after.get(name) != rows for name, rows in before.items()):
        raise ValueError('Existing canonical state changed')
    report = dict(passed=True, backup=str(BACKUP), gateway_restarts=RESTARTS,
        backup_restore_verified=True, canonical_tables_unchanged=True,
        auth_acl_checked=True, panel_read_cancel_only=True, hybrid_unchanged=True,
        **OFF, runtime_credentials_reused=False, lab_credentials_metadata_checked=True,
        credential_same_uid_limitation='user-readable; no reuse in this installation',
        windows_started=False, new_missions=0, paid_api_calls=0,
        confinement={k: confinement[k] for k in ['effective_bpf_hooks', 'controls_before',
            'controls_after', 'receiver_witness', 'runtime_uid_nonroot', 'gateway_secrets_hidden']})
    helper.private_report(BACKUP / 'result.json', report)
    helper.private_report(marker, report)
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never display exception data possibly containing credentials or response bodies.
        if MUTATED:
            try:
                uid = pwd.getpwnam('user')
                helper = load_module('failure_utilities', verified(SRC / 'ops/pilot-network/deploy-private-embedded.py', HELPER_SHA))
                helper.replace_private(FLAG, b'{"enabled":false}\n', uid.pw_uid, uid.pw_gid)
            except Exception:
                print('WARNING: verify panel switch false manually', file=sys.stderr)
        if PRIVATE_STOPPED:
            subprocess.run(['systemctl', 'stop', UNIT.name], capture_output=True, timeout=60)
        print(json.dumps(dict(passed=False, error_type=type(error).__name__,
            errno=getattr(error, 'errno', None), step=STEP,
            backup=str(BACKUP) if BACKUP else None, gateway_restarts=RESTARTS,
            switch_disable_requested=MUTATED, automatic_retry=False)), file=sys.stderr)
        raise SystemExit(1)
