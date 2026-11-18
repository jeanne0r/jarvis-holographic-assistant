#!/usr/bin/python3 -I
"""Route 3 of the Jarvis classifier (18.11.2026): history analyses go to Hermes.

Replaces ONE file of the prod Jarvis backend, /home/user/workspace/jarvis/hybrid-brain.mjs (imported by
~/gateway/server.js through backend.mjs), only when it is exactly the reviewed base (main 2d40cc2). The
server only answers "route hermes"; the browser creates the mission through the missions panel. So the
browser side must be served FIRST (frontend-update-4: app.js handles `hermes`), else the hand-off would be
announced and never made: --apply refuses until https://…/jarvis/app.js is that version.
  --check                  read-only: base, candidate, served app.js
  --apply --backup DIR     backup + atomic replace (owner/mode kept). The GATEWAY RESTART is separate.
  --revert --backup DIR    restore the base (then restart the gateway again)
No secret is read; nothing is started or stopped.
"""
import argparse, hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path('/home/user/workspace/jarvis/hybrid-brain.mjs')
BASE = '713635b9b47eb9e8d021a4a4bb92b2007a39c0f2fc9cd6830f5897b58b3b7b4f'
SUB = 'route-update'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def frontend():
    spec = importlib.util.spec_from_file_location('simple_frontend_update', HERE / 'frontend_update.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class Route:
    def __init__(self, target=TARGET, source=HERE.parents[1] / 'hybrid-brain.mjs', *, served_app=None, base=BASE):
        self.target, self.source, self.base = Path(target), Path(source), base
        self.served_app = served_app or (lambda: frontend().https_sha('app.js'))

    def _read(self):
        if self.target.is_symlink() or not self.target.is_file(): raise PermissionError('Regular file required: ' + str(self.target))
        return self.target.read_bytes()

    def plan(self):
        new = self.source.read_bytes(); installed = self._read()
        if sha(installed) == sha(new): raise PermissionError('Already updated')
        if sha(installed) != self.base: raise PermissionError('Installed hybrid-brain.mjs is not the reviewed base (%s)' % sha(installed)[:12])
        status, served = self.served_app(); want = frontend().APP4
        return new, {'passed': True, 'step': SUB, 'before': self.base, 'after': sha(new), 'served_app_js': served,
                     'frontend_ready': status == 200 and served == want}

    def apply(self, backup):
        new, report = self.plan()
        if not report['frontend_ready']: raise PermissionError('Serve frontend-update-4 first (app.js must handle the Hermes route)')
        dest = Path(backup) / SUB
        if dest.exists(): raise FileExistsError('Backup already exists: ' + str(dest))
        dest.mkdir(mode=0o700, parents=True); shutil.copy2(self.target, dest / self.target.name)
        st = self.target.lstat(); tmp = self.target.with_name('.' + self.target.name + '.upd-' + os.urandom(4).hex())
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(new); f.flush(); os.fsync(f.fileno()); os.fchown(f.fileno(), st.st_uid, st.st_gid); os.fchmod(f.fileno(), st.st_mode & 0o7777)
        os.replace(tmp, self.target)
        if sha(self._read()) != report['after']: shutil.copy2(dest / self.target.name, self.target); raise RuntimeError('Post-write mismatch; restored')
        report.update(updated=True, backup=str(dest), next='restart the gateway (the new route is loaded at start)'); return report

    def revert(self, backup):
        dest = Path(backup) / SUB; saved = dest / self.target.name
        if not saved.is_file() or sha(saved.read_bytes()) != self.base: raise FileNotFoundError('No reviewed backup in ' + str(dest))
        if sha(self._read()) != sha(self.source.read_bytes()): raise PermissionError('Installed file is not the route update: nothing reverted')
        st = self.target.lstat(); shutil.copyfile(saved, self.target); os.chown(self.target, st.st_uid, st.st_gid); os.chmod(self.target, st.st_mode & 0o7777)
        os.rename(dest, dest.with_name(SUB + '.reverted-' + os.urandom(3).hex()))
        return {'passed': sha(self._read()) == self.base, 'step': SUB, 'next': 'restart the gateway'}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    for a in ('check', 'apply', 'revert'): g.add_argument('--' + a, action='store_true')
    p.add_argument('--backup')
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if not a.check and not a.backup: p.error('--backup DIR required')
    r = Route()
    try: out = r.plan()[1] if a.check else r.apply(a.backup) if a.apply else r.revert(a.backup)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:600]})); sys.exit(2)
    print(json.dumps(out, indent=1)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
