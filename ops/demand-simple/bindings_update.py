#!/usr/bin/python3 -I
"""Supervisor side of the Hermes MCP proxy files: its own copies, their pins, the Windows bindings.

Before each session the supervisor checks (scripts/pilot_phase6b_panel.check_windows_patch):
  host_files    = its own release copies (/opt/jarvis-hermes-supervisor),
  windows_files = the copies in C:\\JarvisHermesLab\\app (Get-FileHash).
17.11 real sources: phase2/mcp.py and phase3/mcp.py advertise the read-only HA/Influx tools,
so, in one reversible operation (supervisor stopped):
  - /opt/jarvis-hermes-supervisor/<file>      replaced (owner/mode kept),
  - config.json sourceFiles[<file>]            new hash (checked by the supervisor at start),
  - windows-bindings.json host/windows_files   new hash, and config.json bindingsSha256.
Only these two names change; every other entry, owner and mode is kept.

  --check                  read-only: current entries, expected bases, new hashes
  --apply --backup DIR     backup bindings + config, rewrite both (supervisor must be stopped)
  --revert --backup DIR    restore both from the backup
Then the Windows copy of the same two files (the supervisor refuses any session until it matches).
No secret is read or printed (config.json is parsed for two keys and rewritten as is otherwise).
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = Path('/etc/jarvis-hermes-supervisor/config.json')
OPT = Path('/opt/jarvis-hermes-supervisor')
UNIT = 'jarvis-hermes-supervisor.service'
# Stacked steps, oldest first: (backup sub-directory, name -> host base). The step applied is the one
# whose bases are what the bindings pin now; its result is this checkout's file.
STEPS = [
    ('bindings-update', {     # 17.11 real sources: release eb17c0c -> MCP proxy with the HA/Influx tools
        'memory_manager/phase2/mcp.py': '75383b7c0d0acb3a5d73da33cdc9120a114807be104e3d028ed192b803e80adf',
        'memory_manager/phase3/mcp.py': 'f77e9d6d945041d7388aa66600e75bad8aff4b6a627c953e8011790113ad00f1'}),
    ('bindings-update-2', {   # 17.11 mission 0d1c6c51: 30 s timeout for source tool calls
        'memory_manager/phase2/mcp.py': '90737477050b2d4fe21c8b12fdeb22ae42311a65c6f1451a39a575d455811a75'}),
    ('bindings-update-3', {   # 18.11 (User): mining in parallel, VRAM-only GPU check (supervisor + Windows Ollama guard)
        'scripts/demand_supervisor.py': '85dafb947323ab3ce021c90b99af4de428562fb9f9607fbacf399b801172e921',
        'scripts/pilot_phase4_windows.py': '996d4a8904771c742ce53a061a34769c90ec1e99e1eb590fcf633e08deeca2ce',
        'ops/phase4-run-ollama-windows.py': '0825f6326a7e065b172cc266cc18b0e2c6b5f31e28917593ab3cb74945f7256c'}),
]
SUB, CHANGES = STEPS[-1]
NAMES = sorted({n for _, c in STEPS for n in c})


def sha(raw): return hashlib.sha256(raw).hexdigest()


def write_like(path, raw, st):
    tmp = path.with_name('.' + path.name + '.upd-' + os.urandom(4).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    os.chown(tmp, st.st_uid, st.st_gid); os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, path)


def regular(path):
    st = path.lstat()
    if path.is_symlink() or not path.is_file() or st.st_mode & 0o077: raise PermissionError('Private regular file required: ' + str(path))
    return path.read_bytes(), st


class Bindings:
    def __init__(self, src=HERE.parents[1], config=CONFIG, opt=OPT, *, unit_state=None):
        self.src, self.config, self.opt = Path(src), Path(config), Path(opt)
        self.unit_state = unit_state or (lambda: subprocess.run(['systemctl', 'is-active', UNIT], capture_output=True, text=True).stdout.strip())

    def plan(self):
        cfg_raw, _ = regular(self.config); cfg = json.loads(cfg_raw)
        path = Path(cfg.get('bindingsFile') or '')
        if not path.is_absolute(): raise PermissionError('bindingsFile absent from the supervisor config')
        raw, _ = regular(path)
        if sha(raw) != cfg.get('bindingsSha256'): raise PermissionError('Installed bindings differ from bindingsSha256: review first')
        b = json.loads(raw)
        sources0 = dict(cfg.get('sourceFiles') or {})
        def pinned(n):    # host-side pins of n: host_files and/or sourceFiles (a supervisor-only file has no binding);
            return [m[n] for m in (b['host_files'], sources0) if n in m]   # windows_files is overwritten, as before
        done = lambda n: pinned(n) and set(pinned(n)) == {sha((self.src / n).read_bytes())} and (n not in b['windows_files'] or b['windows_files'][n] == pinned(n)[0])
        if all(done(n) for n in NAMES if pinned(n)) and any(pinned(n) for n in NAMES): raise PermissionError('Already updated')
        self.sub, CHANGES = next(((s, c) for s, c in reversed(STEPS) if all(pinned(n) and set(pinned(n)) == {h} for n, h in c.items())), STEPS[-1])
        self.changes = CHANGES
        new = {n: sha((self.src / n).read_bytes()) for n in CHANGES}
        rows, sources = [], dict(cfg.get('sourceFiles') or {})
        for n, base in CHANGES.items():
            if not pinned(n) or set(pinned(n)) != {base}: raise PermissionError('Pins of %s are not the reviewed base (%s)' % (n, ','.join(h[:12] for h in pinned(n)) or 'none'))
            installed = self.opt / n
            if installed.is_symlink() or sha(installed.read_bytes()) != base: raise PermissionError('Supervisor copy of %s is not the reviewed base' % n)
            if n in sources:
                if sources[n] != base: raise PermissionError('sourceFiles[%s] is not the reviewed base' % n)
                sources[n] = new[n]
            rows.append({'file': n, 'before': base, 'after': new[n], 'in_host_files': n in b['host_files'], 'in_windows_files': n in b['windows_files'],
                         'in_sourceFiles': n in cfg.get('sourceFiles', {}), 'copy_to_windows': n in b['windows_files']})
        out = dict(b, host_files={**b['host_files'], **{n: h for n, h in new.items() if n in b['host_files']}},
                   windows_files={**b['windows_files'], **{n: h for n, h in new.items() if n in b['windows_files']}})
        new_raw = (json.dumps(out, indent=2) + '\n').encode()
        want = dict(cfg, bindingsSha256=sha(new_raw), **({'sourceFiles': sources} if 'sourceFiles' in cfg else {}))
        new_cfg = (json.dumps(want, indent=1, sort_keys=True) + '\n').encode()     # the installer's exact format
        changed = sorted(k for k in set(cfg) | set(want) if cfg.get(k) != want.get(k))
        if not set(changed) <= {'bindingsSha256', 'sourceFiles'}: raise RuntimeError('Config rewrite would change ' + ','.join(changed))
        return path, new_raw, new_cfg, {'passed': True, 'step': self.sub, 'bindings_file': str(path), 'files': rows, 'bindings_after': sha(new_raw),
                                        'config_keys_changed': changed, 'supervisor_state': self.unit_state()}

    def apply(self, backup):
        path, new_raw, new_cfg, report = self.plan()
        if report['supervisor_state'] in ('active', 'activating', 'reloading'): raise PermissionError(UNIT + ' must be stopped')
        dest = Path(backup) / self.sub
        if dest.exists(): raise FileExistsError('Bindings backup already exists: ' + str(dest))
        dest.mkdir(mode=0o700, parents=True)
        shutil.copy2(path, dest / 'windows-bindings.json'); shutil.copy2(self.config, dest / 'config.json')
        for n in self.changes: (dest / 'opt' / n).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(self.opt / n, dest / 'opt' / n)
        (dest / 'paths.json').write_text(json.dumps({'bindings': str(path), 'config': str(self.config), 'opt': str(self.opt)}))
        try:
            for n in self.changes: write_like(self.opt / n, (self.src / n).read_bytes(), (self.opt / n).lstat())
            write_like(path, new_raw, path.lstat()); write_like(self.config, new_cfg, self.config.lstat())
            cfg = json.loads(self.config.read_text())
            if sha(path.read_bytes()) != cfg['bindingsSha256'] or any(sha((self.opt / n).read_bytes()) != cfg.get('sourceFiles', {}).get(n, sha((self.opt / n).read_bytes())) for n in self.changes):
                raise RuntimeError('Post-write mismatch')
        except BaseException:
            self._restore(dest); raise
        report.update(updated=True, backup=str(dest)); return report

    @staticmethod
    def pending(backup):
        return [s for s, _ in reversed(STEPS) if (Path(backup) / s / 'paths.json').exists()]

    def revert(self, backup):
        steps = self.pending(backup)
        if not steps: raise FileNotFoundError('No bindings backup in ' + str(backup))
        sub = steps[0]; dest = Path(backup) / sub
        if self.unit_state() in ('active', 'activating', 'reloading'): raise PermissionError(UNIT + ' must be stopped')
        paths = self._restore(dest)
        os.rename(dest, dest.with_name(sub + '.reverted-' + os.urandom(3).hex()))
        return {'passed': True, 'step': sub, 'restored': list(paths.values()), 'still_applied': self.pending(backup)}

    def _restore(self, dest):
        paths = json.loads((dest / 'paths.json').read_text())
        for name, target in [('windows-bindings.json', Path(paths['bindings'])), ('config.json', Path(paths['config']))]:
            write_like(target, (dest / name).read_bytes(), target.lstat())
        for n in NAMES:
            if (dest / 'opt' / n).exists(): write_like(Path(paths['opt']) / n, (dest / 'opt' / n).read_bytes(), (Path(paths['opt']) / n).lstat())
        return paths


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    for a in ('check', 'apply', 'revert', 'pending'): g.add_argument('--' + a, action='store_true')
    p.add_argument('--backup'); p.add_argument('--source', default=str(HERE.parents[1]))
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if not a.check and not a.backup: p.error('--backup DIR required')
    if a.pending: print(' '.join(Bindings.pending(a.backup))); sys.exit(0)
    b = Bindings(a.source)
    try: out = b.plan()[3] if a.check else b.apply(a.backup) if a.apply else b.revert(a.backup)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:600]})); sys.exit(2)
    print(json.dumps(out, indent=1)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
