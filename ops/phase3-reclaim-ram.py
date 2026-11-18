"""Run on PVE via SSH stdin only after separate production-memory approval.

Default is read-only. Never stops an existing guest or changes its RAM maximum.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

MIB, GIB = 1024 ** 2, 1024 ** 3
BASE = Path('/mnt/hdd/jarvis-phase3')


def pve(path):
    return json.loads(subprocess.check_output(['pvesh', 'get', path, '--output-format', 'json']))


def qmp(vid, command, arguments):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(5)
        sock.connect(f'/var/run/qemu-server/{vid}.qmp')
        stream = sock.makefile('rwb', buffering=0)
        json.loads(stream.readline())
        for name, args in [('qmp_capabilities', {}), (command, arguments)]:
            stream.write((json.dumps({'execute': name, 'arguments': args, 'id': 'jarvis-ram'}) + '\n').encode())
            while True:
                reply = json.loads(stream.readline())
                if reply.get('id') == 'jarvis-ram':
                    if 'error' in reply:
                        raise RuntimeError('QMP operation refused')
                    break
        return reply['return']


def observe():
    result = {'host_available_bytes': pve('/nodes/pve/status')['memory']['available'], 'guests': {}}
    for vid, name, maximum in [(103, 'Codex-cli', 4096), (201, 'tailscale', 2048)]:
        cfg = pve(f'/nodes/pve/qemu/{vid}/config')
        if cfg.get('name') != name or int(cfg['memory']) != maximum:
            raise RuntimeError('Existing guest identity or maximum changed; review required')
        stats = qmp(vid, 'qom-get', {'path': '/machine/peripheral/balloon0', 'property': 'guest-stats'})
        available = stats.get('stats', {}).get('stat-available-memory', 2**64 - 1)
        if not 0 < available < 2**63 or not 0 <= time.time() - stats.get('last-update', 0) < 20:
            raise RuntimeError('Fresh guest memory availability required')
        result['guests'][str(vid)] = {'name': name, 'maximum_mib': maximum,
            'balloon_minimum_mib': cfg.get('balloon'), 'available_bytes': available,
            'shares': cfg.get('shares'),
            'actual_bytes': qmp(vid, 'query-balloon', {})['actual']}
    return result


def restore(folder):
    folder = Path(folder).resolve()
    if folder.parent != BASE or not folder.name.startswith('ram-'):
        raise ValueError('Known private RAM backup required')
    before = json.loads((folder / 'before.json').read_text())
    for vid, name, maximum in [(103, 'Codex-cli', 4096), (201, 'tailscale', 2048)]:
        cfg = pve(f'/nodes/pve/qemu/{vid}/config')
        if cfg.get('name') != name or int(cfg['memory']) != maximum:
            raise RuntimeError('Guest identity changed; rollback needs review')
    old = before['guests']['103']['balloon_minimum_mib']
    command = ['qm', 'set', '103', '--delete', 'balloon'] if old is None else ['qm', 'set', '103', '--balloon', str(int(old))]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    for vid in [103, 201]:
        original = before['guests'][str(vid)]
        if 'shares' in original:
            value = original['shares']
            current = pve(f'/nodes/pve/qemu/{vid}/config').get('shares')
            if value != current:
                command = ['qm', 'set', str(vid), '--delete', 'shares'] if value is None else ['qm', 'set', str(vid), '--shares', str(int(value))]
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    for vid, target in [(103, 4096), (201, 2048)]:
        qmp(vid, 'balloon', {'value': target * MIB})
    return {'restore_requested': True, 'backup': str(folder)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved', action='store_true')
    parser.add_argument('--restore')
    args = parser.parse_args()
    if args.restore:
        if not args.approved:
            raise SystemExit('Explicit approval required')
        print(json.dumps(restore(args.restore)))
        return
    before = observe()
    for vid, target, margin in [('103', 2816, GIB), ('201', 1024, GIB // 2)]:
        guest = before['guests'][vid]
        reduction = max(0, guest['actual_bytes'] - target * MIB)
        if guest['available_bytes'] - reduction < margin:
            raise RuntimeError('Insufficient projected guest headroom; no change allowed')
    print(json.dumps({'read_only': not args.approved, 'before': before,
                      'targets_mib': {'103': 2816, '201': 1024}}), flush=True)
    if not args.approved:
        return
    if before['guests']['103']['balloon_minimum_mib'] is not None or int(before['guests']['201']['balloon_minimum_mib'] or 0) != 1024:
        raise RuntimeError('Balloon configuration differs from the reviewed baseline')
    if not os.path.ismount(BASE.parent):
        raise RuntimeError('Reviewed HDD backup mount unavailable; no change allowed')
    BASE.mkdir(mode=0o700, exist_ok=True)
    folder = BASE / ('ram-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    folder.mkdir(mode=0o700)
    (folder / 'before.json').write_text(json.dumps(before, indent=2))
    hashes = {}
    for vid in [103, 201]:
        source = Path(f'/etc/pve/qemu-server/{vid}.conf')
        dest = folder / source.name
        shutil.copyfile(source, dest)
        os.chmod(dest, 0o600)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Guest configuration backup verification failed')
        hashes[str(vid)] = digest
    (folder / 'sha256.json').write_text(json.dumps(hashes))
    try:
        subprocess.run(['qm', 'set', '103', '--balloon', '2816'], check=True, stdout=subprocess.DEVNULL)
        for vid, target in [(103, 2816), (201, 1024)]:
            qmp(vid, 'balloon', {'value': target * MIB})
        for _ in range(20):
            time.sleep(2)
            after = observe()
            safe = after['guests']['103']['available_bytes'] >= GIB and after['guests']['201']['available_bytes'] >= GIB // 2
            if not safe:
                raise RuntimeError('Guest headroom below reviewed margin')
            if after['host_available_bytes'] >= 5 * GIB:
                report = {'reclaimed': True, 'backup': str(folder), 'after': after}
                (folder / 'after.json').write_text(json.dumps(report, indent=2))
                print(json.dumps(report), flush=True)
                return
        raise RuntimeError('Host did not reach 5 GiB available; laboratory must not start')
    except BaseException:
        restore(folder)
        raise


if __name__ == '__main__':
    main()
