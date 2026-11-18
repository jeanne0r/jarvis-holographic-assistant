#!/usr/bin/python3 -I
"""Idempotent installer for the on-demand supervisor (replaces ops/demand/commission.py).

Order is fixed and verified: account -> directories/permissions -> code release ->
config (fingerprints generated now, from the installed files) -> egress table +
policy -> unit -> verification AS the service UID. It never starts, enables or
stops the service unless --start is given, never creates a mission, never edits
`enabled`, never touches Windows, and refuses to run while the service is active.

The supervisor unit Requires= jarvis-hermes-private-boot.service, which runs code
from THIS release (ops/demand/start-private-queue.py loading the pinned coordinator
ops/pilot-network/install-system-pilot.py) and checks /etc/.../boot.json. Both files
ship in the release; the operator's coordinatorSha256 must match (never rewritten);
egressFileSha256/egressRulesSha256 are regenerated from what this installer loads.

Re-running with the same inputs changes nothing (report: "changed": []).
--check computes everything and writes nothing ("changed" = what WOULD change).
"""
import argparse, ast, hashlib, json, os, pwd, grp, secrets, shutil, subprocess, sys, time
from pathlib import Path

NAME = 'jarvis-hermes-supervisor'
ENTRYPOINTS = ['scripts/demand_supervisor.py', 'scripts/run_interactive_hermes.py', 'scripts/egress_selftest.py']
# Read (hashed against the per-host Windows bindings) but never imported.
# Run from /opt by jarvis-hermes-private-boot.service (required by the supervisor unit):
# the boot hook, and the coordinator it loads by path after checking coordinatorSha256.
BOOT_HOOK, COORDINATOR = 'ops/demand/start-private-queue.py', 'ops/pilot-network/install-system-pilot.py'
EXTRA_FILES = ['ops/phase4-run-hermes-windows.py', 'ops/phase4-run-ollama-windows.py',
               'memory_manager/phase4/job.py', 'ops/start-ollama-pilot.ps1', BOOT_HOOK, COORDINATOR]
NFT_TABLE = ['inet', 'jarvis_hermes_supervisor']
BIND_MOUNTS = ['docs', 'data']          # BindPaths targets in the unit; must exist before start
# State subdirectories the running code writes to (data/phase4: owned runtime/Ollama
# stop logs, pilot_phase4_windows.py and phase4/native_trial.py) or reads keys from.
# Created empty if missing; existing contents (SSH keys) are never touched.
STATE_DIRS = ['docs', 'data', 'data/phase4', 'ssh', 'ssh/hermes']
QUEUE = ['127.0.0.1', 8797]
WITNESS_PORT = 8792


class Layout:
    """All absolute locations, overridable only so tests can use a temporary root."""
    def __init__(self, base='/'):
        b = Path(base)
        self.opt = b / 'opt' / NAME
        self.etc = b / 'etc' / NAME
        self.state = b / 'var/lib' / NAME
        self.unit = b / 'etc/systemd/system' / (NAME + '.service')
        self.old_attestation_unit = b / 'etc/systemd/system/jarvis-hermes-confinement.service'
        self.boot_unit = b / 'etc/systemd/system/jarvis-hermes-private-boot.service'
        self.boot = self.etc / 'boot.json'
        self.config = self.etc / 'config.json'
        self.policy = self.etc / 'egress-policy.json'
        self.nft = self.etc / 'egress.nft'


# ---------- pure helpers (unit-tested without root) ----------

def sha(raw): return hashlib.sha256(raw).hexdigest()


def _resolve(src, module):
    parts = module.split('.')
    for cand in (src.joinpath(*parts).with_suffix('.py'), src.joinpath(*parts, '__init__.py')):
        if cand.is_file(): return cand
    return None


def import_closure(src, entrypoints=ENTRYPOINTS, extras=EXTRA_FILES):
    """Repo-local modules reachable from the entrypoints, including imports inside
    functions. Computed at deploy time: nothing is frozen in a config template."""
    src = Path(src).resolve(); seen = set(); todo = [src / e for e in entrypoints]
    while todo:
        path = todo.pop()
        if path in seen: continue
        if not path.is_file(): raise FileNotFoundError(str(path.relative_to(src)))
        seen.add(path)
        rel = path.relative_to(src)
        # parent package __init__ files are executed on import
        for parent in rel.parents:
            init = src / parent / '__init__.py'
            if parent != Path('.') and init.is_file(): todo.append(init)
        pkg = list(rel.parent.parts) if rel.name == '__init__.py' else list(rel.parent.parts)
        for node in ast.walk(ast.parse(path.read_bytes(), str(rel))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    anchor = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                    base = '.'.join(anchor + ([base] if base else []))
                names = [base] + [base + '.' + a.name for a in node.names if a.name != '*']
            for module in names:
                if module and module.split('.')[0] in ('scripts', 'memory_manager'):
                    hit = _resolve(src, module)
                    if hit: todo.append(hit)
    found = {str(p.relative_to(src)) for p in seen}
    for extra in extras:
        if not (src / extra).is_file(): raise FileNotFoundError(extra)
        found.add(extra)
    return sorted(found)


def render(template, **values):
    out = template
    for k, v in values.items(): out = out.replace('@' + k + '@', str(v))
    if '@' in ''.join(l for l in out.splitlines() if not l.lstrip().startswith('#')):
        raise ValueError('Unrendered template placeholder')
    return out


def egress_policy(windows_host, extra_forbidden=()):
    forbidden = [['127.0.0.1', 8788], ['127.0.0.1', 8787],          # gateway: route to HA/actuators
                 [windows_host, 3389], [windows_host, 445], [windows_host, 8643]]
    forbidden += [[h, int(p)] for h, p in extra_forbidden]
    return {'queue': QUEUE, 'windows': [windows_host, 22], 'witness_port': WITNESS_PORT, 'forbidden': forbidden}


def merged_config(existing, manifest, policy_path):
    """Keep every operator value (identities, bindings, `enabled`) untouched; only the
    generated fields change. The old receipt key disappears with the attestation."""
    if not isinstance(existing, dict): raise ValueError('Config object required')
    cfg = {k: v for k, v in existing.items() if k != 'confinementReceipt'}
    cfg['sourceFiles'] = dict(sorted(manifest.items()))
    cfg['egressPolicy'] = str(policy_path)
    return cfg


def rules_digest(nft_json):
    """Same normalisation as ops/demand/start-private-queue.py (egressRulesSha256):
    runtime-only fields (handles, counters, metainfo) are ignored."""
    def normalized(value):
        if isinstance(value, dict): return {k: normalized(v) for k, v in value.items() if k not in {'handle', 'packets', 'bytes', 'metainfo'}}
        if isinstance(value, list): return [normalized(v) for v in value]
        return value
    return sha(json.dumps(normalized(json.loads(nft_json)), sort_keys=True).encode())


def check_boot(boot, manifest):
    """The operator-approved coordinator pin is never rewritten: a release whose
    coordinator differs would make private-boot (and so the supervisor) refuse."""
    if not isinstance(boot, dict): raise ValueError('Boot policy object required')
    want, got = boot.get('coordinatorSha256'), manifest.get(COORDINATOR)
    if want != got: raise PermissionError('Release coordinator differs from boot.json coordinatorSha256: %s != %s' % (got, want))
    return True


def merged_boot(existing, nft_raw, rules_sha):
    """Only the two pins this installer controls change; every other key is kept."""
    return {**existing, 'egressFileSha256': sha(nft_raw), 'egressRulesSha256': rules_sha}


def check_bindings(path, manifest):
    """The per-host Windows bindings pin host-side copies of the MCP/runtime files.
    A release that differs would make EVERY mission preflight refuse: fail now,
    before the code swap, with the exact names. Missing file -> not checked (dev VM)."""
    if not path or not Path(path).exists(): return False
    host = json.loads(Path(path).read_text()).get('host_files', {})
    drift = sorted(n for n, h in host.items() if manifest.get(n) != h)
    if drift: raise PermissionError('Release differs from per-host Windows bindings: ' + ','.join(drift))
    return True


def dumps(value): return (json.dumps(value, indent=1, sort_keys=True) + '\n').encode()


# ---------- effects ----------

class Installer:
    def __init__(self, src, layout, *, windows_host, extra_forbidden=(), initial_config=None,
                 run=None, log=print, dry=False):
        self.src, self.L, self.host, self.dry = Path(src).resolve(), layout, windows_host, dry
        self.extra, self.initial = list(extra_forbidden), initial_config
        self.run = run or (lambda args, **kw: subprocess.run(args, check=True, capture_output=True, text=True, timeout=60, **kw))
        self.changed, self.log, self.steps = [], log, []

    # file primitive: compare, then atomic write with final owner/mode set BEFORE rename
    def put(self, path, raw, uid, gid, mode):
        path = Path(path)
        if path.is_symlink(): raise PermissionError('Refusing symlink: ' + str(path))
        if path.exists():
            st = path.stat()
            if path.read_bytes() == raw and (st.st_uid, st.st_gid, st.st_mode & 0o7777) == (uid, gid, mode):
                return False
        if self.dry: self.changed.append(str(path)); return True
        tmp = path.parent / ('.' + path.name + '.' + secrets.token_hex(4))
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        os.chown(tmp, uid, gid); os.chmod(tmp, mode); os.replace(tmp, path)
        self.changed.append(str(path)); return True

    def mkdir(self, path, uid, gid, mode):
        path = Path(path)
        if path.is_symlink(): raise PermissionError('Refusing symlink: ' + str(path))
        if not path.exists():
            self.changed.append(str(path))
            if self.dry: return
            path.mkdir(parents=False)
        st = path.stat()
        if (st.st_uid, st.st_gid, st.st_mode & 0o7777) != (uid, gid, mode):
            if not self.dry: os.chown(path, uid, gid); os.chmod(path, mode)
            if str(path) not in self.changed: self.changed.append(str(path) + ' (perms)')

    def step(self, name): self.steps.append(name)

    def refuse_if_active(self):
        r = subprocess.run(['systemctl', 'is-active', NAME + '.service'], capture_output=True, text=True)
        self.active_state = r.stdout.strip()
        if self.dry: return
        if r.stdout.strip() in ('active', 'activating', 'deactivating', 'reloading'):
            raise PermissionError('Service is running: stop it deliberately first (a mission may hold a lease)')

    def account(self):
        self.step('account')
        missing = []
        try: grp.getgrnam(NAME)
        except KeyError: missing.append('group')
        try: pwd.getpwnam(NAME)
        except KeyError: missing.append('user')
        if self.dry and missing: raise FileNotFoundError('--check needs the existing service account (missing: %s)' % ','.join(missing))
        if 'group' in missing: self.run(['groupadd', '--system', NAME]); self.changed.append('group ' + NAME)
        if 'user' in missing:
            self.run(['useradd', '--system', '--gid', NAME, '--no-create-home', '--home-dir', str(self.L.state),
                      '--shell', '/usr/sbin/nologin', NAME]); self.changed.append('user ' + NAME)
        acct = pwd.getpwnam(NAME)
        if acct.pw_uid == 0 or acct.pw_gid == 0: raise PermissionError('Service identity must be non-root')
        others = [p.pw_name for p in pwd.getpwall() if p.pw_uid == acct.pw_uid and p.pw_name != NAME]
        if others: raise PermissionError('UID shared with ' + ','.join(others))
        self.uid, self.gid = acct.pw_uid, acct.pw_gid

    def directories(self):
        self.step('directories')
        self.mkdir(self.L.etc, 0, self.gid, 0o750)
        self.mkdir(self.L.state, self.uid, self.gid, 0o700)
        for m in STATE_DIRS: self.mkdir(self.L.state / m, self.uid, self.gid, 0o700)

    def release(self):
        self.step('release')
        files = import_closure(self.src)
        manifest = {f: sha((self.src / f).read_bytes()) for f in files}
        self.bindings_checked = check_bindings(self._operator_config().get('bindingsFile'), manifest)
        self.boot_checked = check_boot(self._boot_policy(), manifest)   # before any code swap
        current = self.L.opt
        if current.is_dir() and not current.is_symlink():
            installed = {str(p.relative_to(current)): sha(p.read_bytes()) for p in current.rglob('*')
                         if p.is_file() and not any(part in BIND_MOUNTS for part in p.relative_to(current).parts[:1])}
            if installed == manifest and self._release_perms_ok(current, files):
                self.manifest = manifest; return
        else: installed = {}
        if self.dry:
            self.release_diff = {'added': sorted(set(manifest) - set(installed)),
                                 'modified': sorted(f for f in manifest if f in installed and installed[f] != manifest[f]),
                                 'removed (kept in .previous)': len(set(installed) - set(manifest))}
            self.changed.append(str(current) + ' (release swap)'); self.manifest = manifest; return
        staging = current.parent / ('.' + NAME + '.staging-' + secrets.token_hex(4))
        staging.mkdir(mode=0o700)
        try:
            for f in files:
                target = staging / f
                for d in reversed([p for p in target.relative_to(staging).parents if p != Path('.')]):
                    (staging / d).mkdir(exist_ok=True)
                shutil.copyfile(self.src / f, target)
            for m in BIND_MOUNTS: (staging / m).mkdir(exist_ok=True)
            # permissions on EVERY path before the release becomes visible
            for p in [staging] + sorted(staging.rglob('*')):
                os.chown(p, 0, self.gid); os.chmod(p, 0o750 if p.is_dir() else 0o640)
            check = {f: sha((staging / f).read_bytes()) for f in files}
            if check != manifest: raise RuntimeError('Staged release differs from source')
            if current.exists():
                previous = current.parent / (NAME + '.previous')
                if previous.exists(): shutil.rmtree(previous)
                os.rename(current, previous); self.changed.append(str(previous) + ' (kept for rollback)')
            os.rename(staging, current); self.changed.append(str(current))
        except BaseException:
            if staging.exists(): shutil.rmtree(staging)
            raise
        self.manifest = manifest

    def _release_perms_ok(self, root, files):
        for p in [root] + [root / f for f in files] + [root / m for m in BIND_MOUNTS]:
            if not p.exists() or p.is_symlink(): return False
            st = p.stat()
            if (st.st_uid, st.st_gid, st.st_mode & 0o7777) != (0, self.gid, 0o750 if p.is_dir() else 0o640): return False
        for d in {(root / f).parent for f in files}:
            st = d.stat()
            if (st.st_uid, st.st_gid, st.st_mode & 0o7777) != (0, self.gid, 0o750): return False
        return True

    def _boot_policy(self):
        b = self.L.boot
        if not b.exists(): raise FileNotFoundError('No %s: operator-approved boot policy required (private-boot reads it)' % b)
        st = b.lstat()
        if b.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022: raise PermissionError('Root-owned, non-writable boot policy required')
        return json.loads(b.read_text())

    def _operator_config(self):
        if self.L.config.exists():
            if self.L.config.is_symlink(): raise PermissionError('Config symlink')
            return json.loads(self.L.config.read_text())
        if self.initial: return json.loads(Path(self.initial).read_text())
        raise FileNotFoundError('No existing config and no --initial-config (operator-provided)')

    def config(self):
        self.step('config')
        cfg = merged_config(self._operator_config(), self.manifest, self.L.policy)
        raw = dumps(cfg)
        if len(raw) > 128 * 1024: raise ValueError('Config exceeds the supervisor reader bound')
        # Owned by the service UID, 0600: matches scripts.demand_supervisor.private_json.
        self.put(self.L.config, raw, self.uid, self.gid, 0o600)

    def network(self):
        self.step('network')
        self.put(self.L.policy, dumps(egress_policy(self.host, self.extra)), 0, 0, 0o644)
        self.put(self.L.nft, self._rendered_nft(), 0, 0, 0o644)
        if self.dry: return
        self.run(['nft', '-c', '-f', str(self.L.nft)])   # syntax/semantic check
        self.run(['nft', '-f', str(self.L.nft)])         # protect the UID immediately (idempotent)

    def boot_policy(self):
        """Re-pin what private-boot checks to what was just written AND loaded."""
        self.step('boot-policy')
        old = self._boot_policy(); nft_raw = self.L.nft.read_bytes() if self.L.nft.exists() else b''
        if self.dry:
            self.boot_diff = {'egressFileSha256 changes': old.get('egressFileSha256') != sha(self._rendered_nft()),
                              'egressRulesSha256': 'recomputed after load', 'coordinatorSha256': 'kept (checked)'}
            return
        loaded = self.run(['nft', '-j', 'list', 'table', *NFT_TABLE]).stdout
        mode = self.L.boot.stat().st_mode & 0o7777 & ~0o022
        self.put(self.L.boot, dumps(merged_boot(old, nft_raw, rules_digest(loaded))), 0, 0, mode)

    def _rendered_nft(self):
        template = (self.src / 'ops/demand-simple/supervisor-egress.nft.in').read_text()
        return render(template, SUPERVISOR_UID=self.uid, WINDOWS_HOST=self.host).encode()

    def unit(self):
        self.step('unit')
        raw = (self.src / 'ops/demand-simple/jarvis-hermes-supervisor.service.in').read_bytes()
        unit_changed = self.put(self.L.unit, raw, 0, 0, 0o644)
        boot_raw = (self.src / 'ops/demand/jarvis-hermes-private-boot.service.in').read_bytes()
        unit_changed = self.put(self.L.boot_unit, boot_raw, 0, 0, 0o644) or unit_changed
        old = self.L.old_attestation_unit
        if old.exists() and self.dry: self.changed.append(str(old) + ' (would be removed)')
        elif old.exists():
            subprocess.run(['systemctl', 'reset-failed', old.name], capture_output=True)
            old.unlink(); self.changed.append(str(old) + ' (removed: replaced by ExecStartPre)')
            unit_changed = True
        if unit_changed and not self.dry: self.run(['systemctl', 'daemon-reload'])

    def verify_as_service(self):
        """The CHDIR/permission failure class, caught before any start: the service UID
        must enter the code dir, import the executor and read its config."""
        self.step('verify')
        code = ("import json,os;os.chdir(%r);import sys;sys.path.insert(0,%r);"
                "from scripts.demand_supervisor import private_json,CONFIG_MAX_BYTES;"
                "from scripts.egress_selftest import load_policy;"
                "c=private_json(%r,max_bytes=CONFIG_MAX_BYTES);load_policy(%r);"
                "print(json.dumps({'config_keys':len(c),'source_files':len(c['sourceFiles'])}))"
                % (str(self.L.opt), str(self.L.opt), str(self.L.config), str(self.L.policy)))
        r = self.run(['setpriv', '--reuid', str(self.uid), '--regid', str(self.gid), '--clear-groups',
                      '/usr/bin/python3', '-I', '-B', '-c', code], cwd='/')
        return json.loads(r.stdout)

    def install(self, *, start=False):
        if os.geteuid() != 0: raise PermissionError('Root installer')
        os.umask(0o077)
        self.refuse_if_active()
        self.account(); self.directories(); self.release(); self.config(); self.network(); self.boot_policy(); self.unit()
        if self.dry:
            return {'passed': True, 'check_only': True, 'nothing_written': True, 'service_state': self.active_state,
                    'would_change': self.changed, 'release': getattr(self, 'release_diff', 'unchanged'),
                    'boot_policy': self.boot_diff, 'windows_bindings_checked': self.bindings_checked,
                    'coordinator_checked': self.boot_checked, 'source_files': len(self.manifest),
                    'release_sha256': sha(dumps(self.manifest)), 'windows_host': self.host,
                    'enabled_in_config': self._operator_config().get('enabled')}
        verified = self.verify_as_service()
        report = {'passed': True, 'changed': self.changed, 'windows_bindings_checked': self.bindings_checked,
                  'coordinator_checked': self.boot_checked, 'steps': self.steps, 'verified_as_service': verified,
                  'source_files': len(self.manifest), 'release_sha256': sha(dumps(self.manifest)),
                  'windows_host': self.host, 'started': False, 'enabled_at_boot': False, 'missions_created': 0}
        if start:
            self.step('start')
            subprocess.run(['systemctl', 'start', NAME + '.service'], capture_output=True, text=True, timeout=60)
            report['started'] = True
            report['active_state'] = subprocess.run(['systemctl', 'show', NAME + '.service', '-p', 'ActiveState',
                                                     '-p', 'Result', '-p', 'ExecMainStatus'], capture_output=True, text=True).stdout.split()
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--source', default=str(Path(__file__).resolve().parents[2]))
    p.add_argument('--windows-host', default='192.0.2.96')
    p.add_argument('--forbid', action='append', default=[], metavar='HOST:PORT', help='extra destination that must never connect (e.g. HA:8123)')
    p.add_argument('--initial-config', help='only used when no config exists yet')
    p.add_argument('--start', action='store_true', help='start once after a verified install (never enables at boot)')
    p.add_argument('--check', action='store_true', help='compute and report what would change; write nothing')
    args = p.parse_args()
    if args.check and args.start: p.error('--check never starts')
    extra = [tuple(x.rsplit(':', 1)) for x in args.forbid]
    inst = Installer(args.source, Layout('/'), windows_host=args.windows_host, extra_forbidden=extra,
                     initial_config=args.initial_config, dry=args.check)
    try:
        report = inst.install(start=args.start)
    except Exception as e:
        print(json.dumps({'passed': False, 'step': inst.steps[-1] if inst.steps else 'preconditions',
                          'error_type': type(e).__name__, 'error': str(e)[:300], 'changed': inst.changed}))
        sys.exit(2)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
