"""Read-only host/guest telemetry; no service, cgroup or VM configuration writes.

Writes only a new private JSONL artifact after an explicit invocation. Reading
memory.peak does not reset it. An absent counter is null, never zero by default.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import time


def read(path):
    try:
        return path.read_text()[:1000000]
    except OSError:
        return None


def number(path):
    value = read(path)
    return int(value.strip()) if value and value.strip().isdigit() else None


def keyed(path):
    raw = read(path)
    if raw is None: return None
    result = {}
    for line in raw.splitlines():
        parts = line.replace(':', '').split()
        if len(parts) >= 2 and parts[1].isdigit():
            result[parts[0]] = int(parts[1]) * (1024 if parts[-1] == 'kB' else 1)
    return result


def pressure(path):
    raw = read(path)
    if raw is None: return None
    return {parts[0]: {k: float(v) for k, v in (p.split('=') for p in parts[1:])}
            for parts in (line.split() for line in raw.splitlines()) if parts}


def balloon_growth(root):
    """Read QMP allocation only; never send the mutating balloon command."""
    growth = 0
    try:
        for vid, name, maximum in ((103, 'Codex-cli', 4096), (201, 'tailscale', 2048)):
            raw = read(root / f'etc/pve/qemu-server/{vid}.conf')
            if raw is None: return None
            raw = raw.split('\n[')[0]
            cfg = dict(line.split(': ', 1) for line in raw.splitlines() if ': ' in line)
            if cfg.get('name') != name or cfg.get('memory') != str(maximum): return None
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(2)
                sock.connect(str(root / f'var/run/qemu-server/{vid}.qmp'))
                stream = sock.makefile('rwb', buffering=0)
                json.loads(stream.readline())
                for command in ('qmp_capabilities', 'query-balloon'):
                    stream.write((json.dumps({'execute': command, 'id': 'sizing-read'}) + '\n').encode())
                    for _ in range(100):
                        reply = json.loads(stream.readline())
                        if reply.get('id') == 'sizing-read': break
                    if 'error' in reply: return None
                actual = reply['return']['actual']
                if type(actual) is not int or not 0 < actual <= maximum * 1024**2: return None
                growth += maximum * 1024**2 - actual
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return growth


def snapshot(role, root=Path('/')):
    if role not in ('host', 'guest'): raise ValueError('Observation role')
    cg = root / 'sys/fs/cgroup' / ('qemu.slice/102.scope' if role == 'host' else 'system.slice/jarvis-phase3-hermes.service')
    memory = keyed(root / 'proc/meminfo') or {}
    vmstat = keyed(root / 'proc/vmstat') or {}
    pids = set()
    if cg.exists():
        for file in cg.rglob('cgroup.procs'):
            raw = read(file)
            if raw: pids.update(int(p) for p in raw.split() if p.isdigit())
    processes = []
    for pid in sorted(pids)[:512]:
        status = keyed(root / f'proc/{pid}/status')
        if status is not None:
            processes.append({'pid': pid, 'rss_bytes': status.get('VmRSS'), 'hwm_bytes': status.get('VmHWM')})
    psi = pressure(root / 'proc/pressure/memory')
    return {'at': time.time(), 'role': role, 'mem_available_bytes': memory.get('MemAvailable'),
            'balloon_growth_bytes': balloon_growth(root) if role == 'host' else None,
            'psi_full_avg10': psi.get('full', {}).get('avg10') if psi else None,
            'mem_total_bytes': memory.get('MemTotal'), 'swap_free_bytes': memory.get('SwapFree'),
            'pswpin': vmstat.get('pswpin'), 'pswpout': vmstat.get('pswpout'),
            'oom_kill_vmstat': vmstat.get('oom_kill'),
            'psi': psi, 'cgroup_present': cg.exists(),
            'cgroup_current_bytes': number(cg / 'memory.current'),
            'cgroup_peak_bytes': number(cg / 'memory.peak'),
            'cgroup_swap_bytes': number(cg / 'memory.swap.current'),
            'cgroup_events': keyed(cg / 'memory.events'),
            'cgroup_stat': keyed(cg / 'memory.stat'), 'processes': processes,
            'rss_sum_bytes': sum(p['rss_bytes'] or 0 for p in processes) if processes else None,
            'rss_note': 'Sampled sum may double-count shared pages; HWM is per process, not a simultaneous sum.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=['host', 'guest'], required=True)
    parser.add_argument('--count', type=int, default=60)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.count <= 1800 or not 0.5 <= args.interval <= 10 or args.count * args.interval > 1800:
        raise SystemExit('Observation duration limit')
    expected = 'pve' if args.role == 'host' else 'jarvis-lab'
    if socket.gethostname().split('.')[0] != expected:
        raise SystemExit('Dedicated observation host required')
    base = Path('/mnt/hdd/jarvis-phase3') if args.role == 'host' else Path('/home/user/workspace/jarvis-2-memory/data/phase3')
    path = Path(args.output).resolve()
    if not path.is_relative_to(base) or path == base:
        raise SystemExit('Private laboratory artifact path required')
    # Parent must already exist; never overwrite artifacts or change host settings.
    with open(path, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
        for index in range(args.count):
            out.write(json.dumps(snapshot(args.role), allow_nan=False) + '\n'); out.flush()
            if index + 1 < args.count: time.sleep(args.interval)


if __name__ == '__main__': main()
