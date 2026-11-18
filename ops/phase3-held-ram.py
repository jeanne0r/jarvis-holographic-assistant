"""Approved 30-minute PVE-only pilot; watchdog survives controller disconnect.

Install alongside phase3-reclaim-ram.py in a private HDD directory. Start watch
as a transient systemd unit with cleanup as ExecStopPost BEFORE apply.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

spec = importlib.util.spec_from_file_location('ram', Path(__file__).with_name('phase3-reclaim-ram.py'))
ram = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ram)


def margins(state, floor=ram.GIB):
    return (state['host_available_bytes'] >= floor
            and state['guests']['103']['available_bytes'] >= ram.GIB
            and state['guests']['201']['available_bytes'] >= ram.GIB // 2)


def load(folder):
    folder = Path(folder).resolve()
    if folder.parent != ram.BASE or not folder.name.startswith('ram-held-'):
        raise ValueError('Known private pilot folder required')
    data = json.loads((folder / 'pilot.json').read_text())
    if data['vmid'] != 102 or not data['tag'].startswith('codex-phase3-'):
        raise ValueError('Fixed laboratory identity required')
    hashes = json.loads((folder / 'sha256.json').read_text())
    for vid in [103, 201]:
        if hashlib.sha256((folder / f'{vid}.conf').read_bytes()).hexdigest() != hashes[str(vid)]:
            raise RuntimeError('Verified backup required')
    return folder, data


def reusable_lab(cfg, status, known_tag):
    if (cfg.get('name') != 'jarvis-lab' or status != 'stopped'
            or int(cfg.get('memory', 0)) != 4096 or int(cfg.get('onboot', 0)) != 0
            or not str(cfg.get('scsi0', '')).startswith('hdd:102/')
            or known_tag.lower() not in cfg.get('tags', '').lower().split(';')):
        raise RuntimeError('Known stopped 4 GiB laboratory required; refuse another guest')
    return known_tag.lower()


def prepare(reuse=None):
    state = ram.observe()
    for vid, target, margin in [('103', 2816, ram.GIB), ('201', 1024, ram.GIB // 2)]:
        guest = state['guests'][vid]
        if guest['available_bytes'] - max(0, guest['actual_bytes'] - target * ram.MIB) < margin:
            raise RuntimeError('Insufficient projected headroom')
    if state['guests']['103']['balloon_minimum_mib'] is not None or state['guests']['201']['balloon_minimum_mib'] != 1024:
        raise RuntimeError('Reviewed baseline changed')
    inventory = ram.pve('/cluster/resources')
    tag = None
    occupied = [row for row in inventory if row.get('vmid') == 102 or row.get('name') == 'jarvis-lab']
    if reuse:
        _, previous = load(reuse)
        if len(occupied) != 1 or occupied[0].get('vmid') != 102:
            raise RuntimeError('Exactly the known laboratory must exist for reuse')
        tag = reusable_lab(ram.pve('/nodes/pve/qemu/102/config'), occupied[0].get('status'), previous['tag'])
    elif occupied:
        raise RuntimeError('Reserved laboratory identity no longer free; explicit verified reuse required')
    if not os.path.ismount(ram.BASE.parent):
        raise RuntimeError('Backup HDD unavailable')
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    folder = ram.BASE / ('ram-held-' + stamp)
    folder.mkdir(mode=0o700)
    hashes = {}
    for vid in [103, 201]:
        source = Path(f'/etc/pve/qemu-server/{vid}.conf')
        dest = folder / source.name
        shutil.copyfile(source, dest)
        os.chmod(dest, 0o600)
        hashes[str(vid)] = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(dest.read_bytes()).hexdigest() != hashes[str(vid)]:
            raise RuntimeError('Backup verification failed')
    (folder / 'before.json').write_text(json.dumps(state))
    (folder / 'sha256.json').write_text(json.dumps(hashes))
    (folder / 'pilot.json').write_text(json.dumps({'vmid': 102, 'tag': tag or 'codex-phase3-' + stamp.lower(),
                                                  'reuses_guard_folder': str(reuse) if reuse else None}))
    return {'folder': str(folder), 'before': state}


def cleanup(folder):
    folder, data = load(folder)
    with open(folder / 'cleanup.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (folder / 'restored.json').exists():
            return
        inventory = ram.pve('/cluster/resources')
        existing = next((r for r in inventory if r.get('vmid') == data['vmid']), None)
        if existing:
            cfg = ram.pve('/nodes/pve/qemu/102/config')
            if cfg.get('name') != 'jarvis-lab' or data['tag'].lower() not in cfg.get('tags', '').lower().split(';'):
                raise RuntimeError('Unrecognized VM: do not stop or restore into uncertain capacity')
            if existing.get('status') == 'running':
                subprocess.run(['qm', 'shutdown', '102', '--timeout', '20'], timeout=25, check=False)
                status = ram.pve('/nodes/pve/qemu/102/status/current')
                if status['status'] != 'stopped':
                    subprocess.run(['qm', 'stop', '102'], check=True, timeout=30)
        ram.restore(folder)
        hashes = json.loads((folder / 'sha256.json').read_text())
        exact = {str(vid): hashlib.sha256(Path(f'/etc/pve/qemu-server/{vid}.conf').read_bytes()).hexdigest() == hashes[str(vid)] for vid in [103, 201]}
        if not all(exact.values()):
            raise RuntimeError('Rollback configuration verification failed')
        (folder / 'restored.json').write_text(json.dumps({'at': time.time(), 'configuration_exact': exact}))


def watch(folder):
    folder, _ = load(folder)
    deadline = time.time() + 1800
    with open(folder / 'watch.json', 'x') as out:
        json.dump({'deadline': deadline}, out)
    try:
        while time.time() < deadline and not (folder / 'restored.json').exists():
            state = ram.observe()
            with open(folder / 'observations.jsonl', 'a') as out:
                out.write(json.dumps({'at': time.time(), **state}) + '\n')
            if not margins(state):
                raise RuntimeError('Pilot memory margin breached')
            time.sleep(5)
    finally:
        cleanup(folder)


def apply(folder):
    folder, _ = load(folder)
    if (folder / 'restored.json').exists():
        raise RuntimeError('Pilot already closed')
    deadline = json.loads((folder / 'watch.json').read_text())['deadline']
    if not 60 < deadline - time.time() <= 1800:
        raise RuntimeError('Active independent guard required')
    original = json.loads((folder / 'before.json').read_text())
    state = ram.observe()
    if state['guests'] != original['guests']:
        # Telemetry fluctuates. Compare configuration and projected capacity independently.
        for vid in ['103', '201']:
            for key in ['maximum_mib', 'balloon_minimum_mib', 'shares']:
                if state['guests'][vid][key] != original['guests'][vid][key]:
                    raise RuntimeError('Guest settings changed since backup')
    for vid, target, margin in [('103', 2816, ram.GIB), ('201', 1024, ram.GIB // 2)]:
        g = state['guests'][vid]
        if g['available_bytes'] - max(0, g['actual_bytes'] - target * ram.MIB) < margin:
            raise RuntimeError('Projected margin no longer sufficient')
    try:
        subprocess.run(['qm', 'set', '103', '--balloon', '2816', '--shares', '0'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['qm', 'set', '201', '--shares', '0'], check=True, stdout=subprocess.DEVNULL)
        for vid, target in [(103, 2816), (201, 1024)]:
            ram.qmp(vid, 'balloon', {'value': target * ram.MIB})
        for _ in range(12):
            state = ram.observe()
            if not margins(state):
                raise RuntimeError('Guest margin breached')
            if margins(state, 5 * ram.GIB):
                (folder / 'ready.json').write_text(json.dumps(state))
                return {'ready': True, 'folder': str(folder), **state}
            time.sleep(2)
        raise RuntimeError('5 GiB capacity gate not reached')
    except BaseException:
        cleanup(folder)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved', required=True, action='store_true')
    parser.add_argument('action', choices=['prepare', 'watch', 'apply', 'cleanup'])
    parser.add_argument('folder', nargs='?')
    parser.add_argument('--reuse-lab', help='prepare only: verified previous guard folder, never recreate the VM')
    args = parser.parse_args()
    if os.uname().nodename.split('.')[0] != 'pve':
        raise SystemExit('Dedicated PVE host required')
    if args.reuse_lab and args.action != 'prepare':
        raise SystemExit('Reuse selection is preparation only')
    result = prepare(args.reuse_lab) if args.action == 'prepare' else globals()[args.action](args.folder)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
