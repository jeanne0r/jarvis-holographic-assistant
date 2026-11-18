"""Read-only diagnosis of the one failed approved installation; starts no service.

Only non-secret booleans and OS errno are printed. TCP probes bind and close
unconnected sockets; no packets, network listener, command or model call.
"""
import sys
sys.dont_write_bytecode = True
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import subprocess
import types

SRC = Path('/home/user/workspace/jarvis-2-memory')
ROOT = Path('/opt/jarvis-hermes-pilot')
STATE = Path('/var/lib/jarvis-hermes-pilot')
BACKUP = Path('/var/backups/jarvis-hermes/operational-20261115T185027Z-37511961')
PIN = '34abd3ab6c1fe9fad12e3eecb2df77bde963335bd528837ecf91d6f438884ed2'
COORDINATOR = 'dfb3a9e45734c8714837472274d9e3f19fe57e069a2f36529e8db2cbc8e7faa6'


def attempt(fn):
    try:
        return {'ok': True, 'value': fn()}
    except Exception as error:
        code = getattr(error, 'errno', None)
        return {'ok': False, 'error_type': type(error).__name__, 'errno': code,
                'errno_name': errno.errorcode.get(code)}


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise PermissionError('Regular file required')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_digest(path):
    # Only table fingerprints in memory; no source text or credentials are output.
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Integrity check failed')
        result = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = '"' + name.replace('"', '""') + '"'
            result[name] = hashlib.sha256(repr(sorted(repr(row) for row in db.execute('SELECT * FROM '+quoted))).encode()).hexdigest()
        return result


def bind(host, port):
    with socket.socket() as s:
        s.bind((host, port))
    return True


def main():
    if os.geteuid() != 0 or sys.argv[1:] != ['--read-only']:
        raise PermissionError('Administrator terminal and --read-only required')
    if BACKUP.is_symlink() or BACKUP.stat().st_uid != 0 or stat.S_IMODE(BACKUP.stat().st_mode) != 0o700:
        raise PermissionError('Expected root-private backup required')
    manifest_path = SRC / 'docs/HERMES_OPERATIONAL_MANIFEST.json'
    if digest(manifest_path) != PIN:
        raise PermissionError('Manifest drift')
    manifest = json.loads(manifest_path.read_bytes())
    raw = (BACKUP / 'coordinator.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != COORDINATOR:
        raise PermissionError('Coordinator drift')
    module = types.ModuleType('diagnostic_coordinator')
    exec(compile(raw, 'verified-coordinator', 'exec'), module.__dict__)
    cfg = json.loads((STATE / 'config.json').read_bytes())
    flags = cfg.get('operations', {})
    report = {
        'read_only': True,
        'new_release_matches': all(digest(ROOT / name.removeprefix('pilot-release/')) == expected
            for name, expected in manifest['files'].items() if name.startswith('pilot-release/')),
        'old_release_saved': (BACKUP / 'release/deployment-files.json').is_file(),
        'gateway_preimages_unchanged': all(digest(Path(row['target'])) == row['before'] for row in manifest['gateway_patch']),
        'all_operations_off': flags == dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'], False),
        'runtime_not_provisioned': 'runtime' not in flags,
        'layout_validation': attempt(module.verify_layout),
        'snapshot_restored_equal': attempt(lambda: table_digest(BACKUP/'snapshot.sqlite') == table_digest(BACKUP/'restore-check.sqlite')),
        'active_sqlite_matches_snapshot': attempt(lambda: table_digest(STATE/'memory.sqlite') == table_digest(BACKUP/'snapshot.sqlite')),
        'startup_fixture_absent': not Path('/run/jarvis-pilot-network-gate').exists(),
        'loopback_binds': {str(port): attempt(lambda port=port: bind('127.0.0.1',port)) for port in [8796,8797,8643,11435,11436]},
        'services_started': False,
    }
    route = json.loads(subprocess.run(['ip','-j','route','get','192.0.2.1'], check=True,
                            capture_output=True,text=True).stdout)[0]
    report['local_address_bind'] = attempt(lambda: bind(route['prefsrc'],0))
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'read_only':True,'passed':False,'error_type':type(error).__name__,
            'errno':getattr(error,'errno',None),'services_started':False}),file=sys.stderr)
        raise SystemExit(1)
