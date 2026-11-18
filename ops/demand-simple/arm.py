#!/usr/bin/python3 -I
"""Arm (or disarm) execution in the private on-demand service: the last step of the
former ops/demand/commission.py (accord 3), alone and reviewable.

Only `onDemand` changes: executionEnabled=true plus the four fixed runtime identities
(Hermes, model, memory tokens + the supervisor's observer token). The profile logic is
commission.execution_profile() unchanged. Before any write: the supervisor is stopped
only if no lease exists, token SHA-256 must equal the supervisor's reviewed
runtimeIdentityHashes, scheduler identities must match, and the queue must hold no
uncertain execution. The private service restarts through the approved boot hook
(jarvis-hermes-private-boot -> coordinator.supervised_start). Secrets are never printed.

  arm.py --check                 read-only verdict
  arm.py --apply --backup DIR    backup, arm, restart through private-boot (auto-restore on failure)
  arm.py --disarm --backup DIR   restore the backed-up config, restart through private-boot
"""
import argparse, errno, hashlib, json, os, shutil, socket, sqlite3, subprocess, sys, time
from pathlib import Path

PILOT_CFG = Path('/var/lib/jarvis-hermes-pilot/config.json')
SUP_CFG = Path('/etc/jarvis-hermes-supervisor/config.json')
TOKENS_DIR = Path('/home/user/workspace/jarvis-2-memory/data/phase3/windows-20261114')
TOKEN_NAMES = ['hermes.token', 'model.token', 'memory.token']
SUPERVISOR, PILOT, BOOT = 'jarvis-hermes-supervisor.service', 'jarvis-hermes-pilot-system.service', 'jarvis-hermes-private-boot.service'
BACKUP_NAME = 'pilot-config.json'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def execution_profile(cfg, tokens, observer):
    """Verbatim logic of ops/demand/commission.py:execution_profile (reviewed, accord 3)."""
    p = cfg.get('onDemand', {})
    if (p.get('commissioned') is not True or p.get('accepting') is not True or p.get('executionEnabled') is not False
            or p.get('runtime') is not None or cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False
            or cfg.get('operations') != {'admissionEnabled': True, 'textEnabled': True, 'workerEnabled': False, 'voiceEnabled': False}
            or cfg.get('missionLimits') != {'calls': 6, 'tokens': 98304, 'seconds': 240, 'attempts': 1, 'remoteCostChf': 0}
            or set(tokens) != {'hermes.token', 'model.token', 'memory.token'}): raise PermissionError('Exact commissioned synthetic queue required')
    values = [cfg['bridgeToken'], p['schedulerToken'], observer, *tokens.values()]
    if any(not isinstance(v, str) or not 32 <= len(v) <= 256 or any(c.isspace() for c in v) for v in values) or len(set(values)) != 6: raise PermissionError('Distinct fixed identities required')
    return {**cfg, 'onDemand': {**p, 'executionEnabled': True, 'runtime': {'hermesToken': tokens['hermes.token'], 'modelToken': tokens['model.token'], 'memoryToken': tokens['memory.token'], 'supervisorToken': observer}}}


def private_file(path, *, uid=None):
    path = Path(path); st = path.lstat()
    if path.is_symlink() or st.st_mode & 0o077 or (uid is not None and st.st_uid != uid): raise PermissionError('Private file required: ' + str(path))
    return path.read_bytes()


def uncertain_executions(db_path):
    with sqlite3.connect('file:%s?mode=ro' % db_path, uri=True) as db:
        jobs = db.execute('SELECT count(*) FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0').fetchone()[0]
        out = db.execute("SELECT count(*) FROM p2_outbox WHERE state IN ('unknown','submitting','submitted','cancel_requested')").fetchone()[0]
    return jobs + out


def systemctl(*args):
    return subprocess.run(['systemctl', *args], capture_output=True, text=True, timeout=120)


def state(unit): return systemctl('show', unit, '-p', 'ActiveState', '--value').stdout.strip()


def wait_private_ports(*, ports=(8796,8797), seconds=75, clock=time.monotonic, sleep=time.sleep, socket_factory=socket.socket):
    """Verbatim from ops/pilot-network/install-demand-queue.py (used by commission.py before
    every coordinator.supervised_start). The coordinator raw-binds 8796/8797 without
    SO_REUSEADDR: TIME_WAIT left by the stopped service must clear first (prod 16.11:
    arming failed exactly there). A real listener refuses instead of waiting."""
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


def boot_journal_tail(n=4):
    r = subprocess.run(['journalctl', '-u', BOOT, '-n', str(n), '--no-pager', '-o', 'cat'], capture_output=True, text=True, timeout=10)
    return ' | '.join(l.strip()[:200] for l in r.stdout.splitlines()[-n:])


def pilot_unit_optional():
    """Only the isolated dev rehearsal (no private service unit) may skip it; never prod."""
    return os.environ.get('JARVIS_DEV_NO_PILOT_UNIT') == '1' and socket.gethostname() == 'jarvis-dev'


class Arm:
    def __init__(self, pilot_cfg=PILOT_CFG, sup_cfg=SUP_CFG, tokens_dir=TOKENS_DIR, *, ctl=systemctl, unit_state=state, backup_owner=(0, 0),
                 wait_ports=wait_private_ports, journal=boot_journal_tail):
        self.pilot_cfg, self.sup_cfg, self.tokens_dir = Path(pilot_cfg), Path(sup_cfg), Path(tokens_dir)
        self.backup_owner = backup_owner   # root in production; the test user in unit tests
        self.last_error = None
        self.wait_ports, self.journal = wait_ports, journal
        self.ctl, self.state = ctl, unit_state

    def plan(self):
        """All reads and checks; returns (armed_config_bytes, report). Raises on any refusal."""
        st = self.pilot_cfg.lstat()
        original = json.loads(private_file(self.pilot_cfg, uid=st.st_uid))
        sup = json.loads(private_file(self.sup_cfg))
        identity = json.loads(private_file(sup['identityFile']))
        if set(identity) != {'schedulerToken', 'supervisorToken'}: raise PermissionError('Supervisor identity: scheduler and observer only')
        if identity['schedulerToken'] != original.get('onDemand', {}).get('schedulerToken'): raise PermissionError('Supervisor scheduler identity differs from the private service')
        tokens = {n: private_file(self.tokens_dir / n).decode().strip() for n in TOKEN_NAMES}
        hashes = {n: sha(v.encode()) for n, v in tokens.items()}
        if sup.get('runtimeIdentityHashes') != hashes: raise PermissionError('Runtime tokens differ from the supervisor runtimeIdentityHashes')
        if sup.get('remoteCostChf') != 0: raise PermissionError('Zero remote cost required')
        armed = execution_profile(original, tokens, identity['supervisorToken'])
        uncertain = uncertain_executions(self.pilot_cfg.parent / 'memory.sqlite')
        if uncertain: raise PermissionError('Uncertain execution in the queue: review, never replay (%d)' % uncertain)
        report = {'passed': True, 'pilot_config': str(self.pilot_cfg), 'executionEnabled_before': False,
                  'runtime_identities': sorted(armed['onDemand']['runtime']), 'tokens_match_supervisor_hashes': True,
                  'scheduler_identity_match': True, 'uncertain_executions': 0, 'changed_keys': ['onDemand.executionEnabled', 'onDemand.runtime'],
                  'supervisor_state': self.state(SUPERVISOR), 'private_service_state': self.state(PILOT)}
        return (json.dumps(armed) + '\n').encode(), report

    def _write_like(self, raw, st):
        tmp = self.pilot_cfg.parent / ('.config.json.arm-' + os.urandom(4).hex())
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        os.chown(tmp, st.st_uid, st.st_gid); os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, self.pilot_cfg)

    def _restart_private(self):
        """Stop the private service, then re-run the approved boot hook, which starts it."""
        self.ctl('stop', BOOT)
        try:
            if self.state(PILOT) != 'active': self.wait_ports()   # the coordinator will raw-bind 8796/8797
        except Exception as e:
            # Never start over a foreign listener or busy port: report failure so callers restore.
            self.last_error = type(e).__name__ + ': ' + str(e)[:160]; return False
        r = self.ctl('start', BOOT)
        pilot = self.state(PILOT)
        ok = r.returncode == 0 and self.state(BOOT) == 'active' and (pilot == 'active' or (pilot_unit_optional() and pilot in ('inactive', '')))
        return ok

    def _stop_supervisor_if_idle(self):
        if self.state(SUPERVISOR) in ('active', 'activating', 'reloading'):
            # plan() proved no lease/uncertain run exists: stopping cannot interrupt a mission.
            self.ctl('stop', SUPERVISOR)
        if self.state(SUPERVISOR) in ('active', 'activating', 'deactivating', 'reloading'): raise PermissionError('Supervisor still running')

    def apply(self, backup_dir):
        raw, report = self.plan()
        backup = Path(backup_dir) / BACKUP_NAME
        if backup.exists():
            # A failed attempt restored the original: keep its backup aside and retry. Anything else refuses.
            if backup.read_bytes() != self.pilot_cfg.read_bytes(): raise FileExistsError('Backup differs from the current config (armed before?): ' + str(backup))
            os.rename(backup, backup.with_name('pilot-config.failed-attempt-%d.json' % int(time.time())))
        st = self.pilot_cfg.lstat()
        self._stop_supervisor_if_idle()
        shutil.copy2(self.pilot_cfg, backup); os.chown(backup, *self.backup_owner); os.chmod(backup, 0o600)
        self.ctl('stop', PILOT)
        try:
            self._write_like(raw, st); ok = self._restart_private()
        except Exception as e:
            ok = False; self.last_error = type(e).__name__ + ': ' + str(e)[:160]
        if not ok:
            self._write_like(backup.read_bytes(), st); restored = self._restart_private()
            raise RuntimeError('Private service did not start armed; original config restored (%s). cause: %s. private-boot: %s' % ('restarted' if restored else 'NOT restarted', self.last_error or 'boot hook', self.journal()))
        after = json.loads(self.pilot_cfg.read_bytes())['onDemand']
        report.update(armed=after['executionEnabled'] is True and set(after['runtime']) == {'hermesToken', 'modelToken', 'memoryToken', 'supervisorToken'},
                      backup=str(backup), supervisor_state=self.state(SUPERVISOR), private_service_state=self.state(PILOT), private_boot_state=self.state(BOOT))
        return report

    def disarm(self, backup_dir):
        backup = Path(backup_dir) / BACKUP_NAME
        raw = private_file(backup, uid=self.backup_owner[0])
        if uncertain_executions(self.pilot_cfg.parent / 'memory.sqlite'): raise PermissionError('Uncertain execution in the queue: review before disarming')
        st = self.pilot_cfg.lstat()
        self._stop_supervisor_if_idle(); self.ctl('stop', PILOT)
        self._write_like(raw, st)
        ok = self._restart_private()
        return {'passed': ok, 'restored_from': str(backup), 'executionEnabled': json.loads(self.pilot_cfg.read_bytes())['onDemand']['executionEnabled'],
                'private_service_state': self.state(PILOT), 'supervisor_state': self.state(SUPERVISOR)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true'); g.add_argument('--apply', action='store_true'); g.add_argument('--disarm', action='store_true')
    p.add_argument('--backup'); p.add_argument('--tokens-dir', default=str(TOKENS_DIR))
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if (a.apply or a.disarm) and not a.backup: p.error('--backup DIR required')
    arm = Arm(tokens_dir=a.tokens_dir)
    try:
        out = arm.plan()[1] if a.check else arm.apply(a.backup) if a.apply else arm.disarm(a.backup)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:900]})); sys.exit(2)
    print(json.dumps(out, indent=1)); sys.exit(0 if out.get('passed') and out.get('armed', True) else 2)


if __name__ == '__main__':
    main()
