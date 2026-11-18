"""Behavioural egress self-test, run as the supervisor UID inside its own unit.

Replaces the separate root attestation (attest-confinement.py + receipt).
It proves both sides on every start (ExecStartPre) and before every mission:

* ALLOWED  - the private queue answers (positive control: networking works);
             the Windows SSH endpoint is not blocked locally.
* FORBIDDEN - connections to our OWN live witness listeners (loopback on a
             non-allowed port, a non-loopback local address) never arrive,
             named destinations (gateway, HA, other Windows ports) never
             connect, and IPv6 is unusable.

A witness we own is always listening, so a refused/failed connection to it can
only mean filtering. Nothing here grants itself a policy, writes a receipt or
talks to a model. Exit status 0 only when every check passes.
"""
import argparse, errno, json, os, socket, sys
from pathlib import Path

POLICY_MAX_BYTES = 16384
LOCAL_BLOCK = {'refused', 'eperm'}       # nft reject -> ECONNREFUSED, cgroup BPF/EACCES -> eperm
ABSENT = {'timeout', 'unreachable'}       # remote host off/asleep: not a local filtering verdict


def load_policy(path):
    p = Path(path); st = p.lstat()
    # Root-written, world-readable, never writable by the supervisor itself.
    if p.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022 or st.st_size > POLICY_MAX_BYTES:
        raise PermissionError('Root-owned egress policy required')
    policy = json.loads(p.read_text())
    for key in ('queue', 'windows', 'witness_port', 'forbidden'):
        if key not in policy: raise ValueError('Incomplete egress policy: ' + key)
    return policy


def attempt(host, port, *, family=socket.AF_INET, timeout=1.0):
    """Classify one TCP connect without sending any payload."""
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
    except OSError:
        return 'no_socket'
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        return 'connected'
    except socket.timeout:
        return 'timeout'
    except ConnectionRefusedError:
        return 'refused'
    except PermissionError:
        return 'eperm'
    except OSError as e:
        if e.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH): return 'unreachable'
        if e.errno in (errno.EPERM, errno.EACCES): return 'eperm'
        return 'error'
    finally:
        s.close()


def local_address(probe_host):
    """Primary non-loopback source address (UDP connect sends no packet)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((probe_host, 9))
        return s.getsockname()[0]


def witness_check(host, port, connect=attempt):
    """Forbidden path to a listener we own: the connection must never arrive."""
    with socket.socket() as listener:
        listener.bind((host, int(port))); listener.listen(4); listener.setblocking(False)
        port = listener.getsockname()[1]
        outcome = connect(host, port)
        try:
            conn, _ = listener.accept(); conn.close(); arrived = True
        except (BlockingIOError, OSError):
            arrived = False
    return {'target': [host, int(port)], 'outcome': outcome, 'ok': outcome != 'connected' and not arrived}


def run(policy, *, mode='start', connect=attempt, witness=witness_check, address=local_address):
    """mode='start': Windows may be off; mode='mission': Windows must answer."""
    checks = []
    qh, qp = policy['queue']
    out = connect(qh, qp)
    checks.append({'kind': 'allowed', 'name': 'queue', 'target': [qh, qp], 'outcome': out, 'ok': out == 'connected'})
    wh, wp = policy['windows']
    out = connect(wh, wp)
    ok = out == 'connected' if mode == 'mission' else (out == 'connected' or out in ABSENT)
    checks.append({'kind': 'allowed', 'name': 'windows_ssh', 'target': [wh, wp], 'outcome': out, 'ok': ok})
    wport = policy['witness_port']
    checks.append({'kind': 'forbidden', 'name': 'witness_loopback', **witness('127.0.0.1', wport, connect)})
    lan = address('192.0.2.1')   # TEST-NET route: independent of the Windows address
    if lan.startswith('127.') or lan == wh:
        checks.append({'kind': 'forbidden', 'name': 'witness_lan', 'target': [lan, wport], 'outcome': 'no_independent_address', 'ok': False})
    else:
        checks.append({'kind': 'forbidden', 'name': 'witness_lan', **witness(lan, wport, connect)})
    for host, port in policy['forbidden']:
        out = connect(host, port)
        checks.append({'kind': 'forbidden', 'name': 'named', 'target': [host, port], 'outcome': out, 'ok': out != 'connected'})
    out = connect('::1', qp, family=socket.AF_INET6)
    checks.append({'kind': 'forbidden', 'name': 'ipv6', 'target': ['::1', qp], 'outcome': out, 'ok': out != 'connected'})
    passed = (os.geteuid() != 0 and all(c['ok'] for c in checks)
              and any(c['kind'] == 'allowed' for c in checks) and any(c['kind'] == 'forbidden' for c in checks))
    return {'passed': passed, 'mode': mode, 'uid': os.geteuid(), 'checks': checks}


def verify(policy_path, *, mode='mission'):
    """In-process gate for the supervisor preflight and the worker."""
    result = run(load_policy(policy_path), mode=mode)
    if not result['passed']:
        failed = [c['name'] for c in result['checks'] if not c['ok']]
        raise PermissionError('Egress self-test failed: ' + ','.join(failed) if failed else 'Egress self-test failed')
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--policy', required=True)
    p.add_argument('--mode', choices=['start', 'mission'], default='start')
    args = p.parse_args()
    result = run(load_policy(args.policy), mode=args.mode)
    print(json.dumps(result, sort_keys=True), flush=True)
    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
