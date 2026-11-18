#!/usr/bin/python3 -I
"""Targeted, stacked updates of the gateway's Hermes assets (public/jarvis/hermes-embedded.js/.css).

Steps, oldest first (--apply takes the step matching what is installed; run it again for the next;
revert undoes the latest applied one):
  frontend-update    17.11: report-quality message (patch of the installed file)
  frontend-update-2  17.11: Hermes missions UI v2 (ops/hermes-ui/ at 72391f3, whole files, pinned hashes)
  frontend-update-3  17.11: real sources: no consent box, read-only notice, ha:// / influx:// sources
  frontend-update-4  18.11: route 3, Jarvis hands history analyses to Hermes: panel delegate (hermes-embedded.js),
                     conversation hand-off and result (app.js), result read aloud when the voice is on (codex-voice.js)
  --check                  read-only: owner/mode/base hashes, candidate hashes
  --apply --backup DIR     backup, atomic replace (same owner and mode), HTTPS hash check of
                           every served file; restore automatically on any mismatch
  --revert --backup DIR    restore the latest applied step (only over its exact result)
  --pending --backup DIR   applied steps, latest first
No gateway restart (static assets). index.html is not touched. No secret is read.
"""
import argparse, hashlib, json, os, pwd, shutil, ssl, stat, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = Path('/home/user/gateway/public/jarvis')
OWNER = 'user'
ORIGIN = 'https://192.0.2.16:8788'
CERT = Path('/home/user/gateway/data/certs/gateway.crt')
JS, CSS = 'hermes-embedded.js', 'hermes-embedded.css'

# Step 1: one message, patched in place (base reproduced byte for byte from the preparation chain).
OLD = ("warning.textContent=quality.model_cites_source_ref===true?'Références retrouvées dans la mémoire ; réponse non vérifiée indépendamment.'"
       ":'Les sources ne sont pas correctement citées. Réponse à vérifier.'}")
NEW = ("const unread=Number.isInteger(quality.unverified_mission_sources_read)?quality.unverified_mission_sources_read:0;"
       "warning.textContent=(quality.model_cites_source_ref===true?'Références retrouvées dans la mémoire ; réponse non vérifiée indépendamment.'"
       ":quality.cites_unverified_source===true?'La réponse cite un compte rendu de mission non vérifié. Réponse à vérifier.'"
       ":'Les sources ne sont pas correctement citées. Réponse à vérifier.')"
       "+(unread===1?' 1 compte rendu de mission non vérifié a été consulté.':unread>1?' '+unread+' comptes rendus de mission non vérifiés ont été consultés.':'')}")


def sha(raw): return hashlib.sha256(raw).hexdigest()


def candidate(raw):
    s = raw.decode()
    if s.count(OLD) != 1: raise PermissionError('Report-quality message not found exactly once')
    return s.replace(OLD, NEW).encode()


def repo_file(rel):
    return lambda installed: (HERE.parents[1] / rel).read_bytes()


def git_file(commit, rel):
    # An earlier step keeps building exactly what it was reviewed with, whatever the checkout holds now.
    import subprocess
    return lambda installed: subprocess.run(['git', 'show', commit + ':' + rel], cwd=HERE.parents[1], capture_output=True, check=True, timeout=30).stdout


# Step 4 patches the conversation and voice scripts in place (prod serves main 2d40cc2 versions).
APP, VOICE = 'app.js', 'codex-voice.js'
APP_BASE = '80d5341134f7b2fd6777cdd72dd067ed96f6ffcdb9891f4c460990a114266814'      # public/app.js @ 2d40cc2
VOICE_BASE = '1d87f1da88313e123b05e6a539d4f8f3ee90d82e08894965ac9cdde268e2a31b'    # public/codex-voice.js @ 2d40cc2
ROUTE = HERE.parents[1] / 'ops' / 'hermes-ui' / 'route'
APP_PATCH, VOICE_PATCH = ROUTE / 'app.patch.json', ROUTE / 'codex-voice.patch.json'
JS4 = 'c4e74ce8dce6e58d5da327a82cd344a52e6bffca147d62ab078505f1c069abe8'      # ops/hermes-ui/hermes-embedded.js (delegate)
APP4 = 'b192bcf12032794f28a1fdc431016c4cf96a59ecffa736dd8e70252f4e15414b'     # app.js + route/app.patch.json
VOICE4 = '6da3fc994580991fbe8760c953f718ce72113bbc4d70037d3e9b440434ad5428'   # codex-voice.js + route/codex-voice.patch.json


def patched(patch_file):
    def build(installed):
        s = installed.decode()
        for old, new in json.loads(Path(patch_file).read_text()):
            if s.count(old) != 1: raise PermissionError('Patch anchor not found exactly once in ' + Path(patch_file).name)
            s = s.replace(old, new)
        return s.encode()
    return build



# (backup sub-directory, {published name: (base sha, result sha, builder(installed bytes) -> new bytes)})
STEPS = [
    ('frontend-update', {JS: ('da3d4290d64c5c044fc269a465f3e46c15b8d4a27e11b4076d3aca19b9ede588',
                              '11f68f1c2a80b07f1c282d696376cb58d1b9720494f6cb3a0924bd089d357a1a', candidate)}),
    ('frontend-update-2', {JS: ('11f68f1c2a80b07f1c282d696376cb58d1b9720494f6cb3a0924bd089d357a1a',
                                '8942c9721f9c4342986e0a6651d1607e3789ef451d0dc1ab11a23e2afc1d7032', git_file('72391f3', 'ops/hermes-ui/hermes-embedded.js')),
                           CSS: ('3b31da526267f3c9d1a7d53958d7f05d46d4653eb7a378fb4eac66b2db707f77',
                                 '3648961a42ec7d08d252daba4d96af10e089afe40c29b06c288e700ef9ab42f7', git_file('72391f3', 'ops/hermes-ui/hermes-embedded.css'))}),
    ('frontend-update-3', {JS: ('8942c9721f9c4342986e0a6651d1607e3789ef451d0dc1ab11a23e2afc1d7032',
                                'e656c1a46e77fa4574a02ab60a22df9c16a93ac14c976e97ff57d7406fee671f', git_file('b9b86be', 'ops/hermes-ui/hermes-embedded.js'))}),
    ('frontend-update-4', {JS: ('e656c1a46e77fa4574a02ab60a22df9c16a93ac14c976e97ff57d7406fee671f', JS4, repo_file('ops/hermes-ui/hermes-embedded.js')),
                           APP: (APP_BASE, APP4, patched(APP_PATCH)),
                           VOICE: (VOICE_BASE, VOICE4, patched(VOICE_PATCH))}),
]


def https_sha(name, origin=ORIGIN, cert=CERT):
    ctx = ssl.create_default_context(cafile=str(cert))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    with opener.open(origin + '/jarvis/' + name, timeout=10) as r:
        return r.status, sha(r.read())


class Update:
    def __init__(self, public=PUBLIC, owner=OWNER, *, fetch=https_sha, steps=None):
        self.public, self.fetch, self.steps = Path(public), fetch, steps or STEPS
        self.pw = pwd.getpwnam(owner) if isinstance(owner, str) else owner
        self.modes = {}

    def _read(self, name):
        target = self.public / name
        for p in [target, *target.parents]:
            if p.is_symlink(): raise PermissionError('Symlink refused: ' + str(p))
        st = target.lstat()
        # Prod 17.11: the .js is 0644, the .css 0600 (the gateway runs as user). Both kept as they are.
        if not stat.S_ISREG(st.st_mode) or st.st_uid != self.pw.pw_uid or st.st_gid != self.pw.pw_gid or stat.S_IMODE(st.st_mode) not in (0o600, 0o644):
            raise PermissionError('%s must be a regular file owned by %s, mode 0600 or 0644' % (name, self.pw.pw_name))
        self.modes[name] = stat.S_IMODE(st.st_mode)
        return target.read_bytes()

    def _write(self, name, raw):
        target = self.public / name
        tmp = target.with_name('.' + name + '.upd-' + os.urandom(4).hex())
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno()); os.fchown(f.fileno(), self.pw.pw_uid, self.pw.pw_gid); os.fchmod(f.fileno(), self.modes.get(name, 0o644))
            os.replace(tmp, target)
        finally:
            if tmp.exists(): tmp.unlink()

    def pending(self, backup_dir):
        return [sub for sub, _ in reversed(self.steps) if (Path(backup_dir) / sub).is_dir() and any((Path(backup_dir) / sub).iterdir())]

    def plan(self):
        # The next step is the one whose bases are exactly what is installed (prod may still be
        # before step 2): apply it, then run again for the following one. Default: the last step.
        last_sub, last_files = self.steps[-1]
        if all(sha(self._read(n)) == after for n, (_, after, _) in last_files.items()): raise PermissionError('Already updated (' + last_sub + ')')
        sub, files = next(((s, f) for s, f in reversed(self.steps) if all(sha(self._read(n)) == base for n, (base, _, _) in f.items())), self.steps[-1])
        new, rows = {}, []
        installed = {name: self._read(name) for name in files}
        for name, (base, after, build) in files.items():
            if sha(installed[name]) != base: raise PermissionError('Installed %s differs from reviewed base (%s)' % (name, sha(installed[name])[:12]))
            raw = build(installed[name])
            if sha(raw) != after: raise PermissionError('Candidate %s differs from reviewed result (%s)' % (name, sha(raw)[:12]))
            new[name] = raw; rows.append({'file': name, 'before': base, 'after': after, 'changed_bytes': len(raw) - len(installed[name])})
        return new, {'passed': True, 'step': sub, 'files': rows}

    def _served(self, expected):
        bad = {}
        for name, want in expected.items():
            try: status, served = self.fetch(name)
            except Exception as e: status, served = None, type(e).__name__ + ': ' + str(e)[:80]
            if status != 200 or served != want: bad[name] = (status, str(served)[:64])
        return bad

    def apply(self, backup_dir):
        new, report = self.plan()
        sub = report['step']; dest = Path(backup_dir) / sub
        if dest.exists():
            saved = [q for q in dest.iterdir() if q.is_file()]
            if not saved or any((self.public / q.name).read_bytes() != q.read_bytes() for q in saved):
                raise FileExistsError('Frontend backup differs from the installed files: ' + str(dest))
            os.rename(dest, dest.with_name(sub + '.failed-attempt-' + os.urandom(3).hex()))
        dest.mkdir(mode=0o700)
        for name in new: shutil.copy2(self.public / name, dest / name)
        try:
            # styles first, then the panel script (defines the delegate), then the scripts that use it
            for name in sorted(new, key=lambda n: (n != CSS, n != JS)): self._write(name, new[name])
            mismatch = {n: 'disk' for n in new if self._read(n) != new[n]} or self._served({n: sha(r) for n, r in new.items()})
        except Exception as e:
            mismatch = {'error': type(e).__name__ + ': ' + str(e)[:120]}
        if mismatch:
            for name in new: self._write(name, (dest / name).read_bytes())
            raise RuntimeError('Served frontend does not match %s; previous files restored' % json.dumps(mismatch))
        report.update(updated=True, backup=str(dest), https_verified=sorted(new))
        return report

    def revert(self, backup_dir):
        steps = self.pending(backup_dir)
        if not steps: raise FileNotFoundError('No frontend update backup in ' + str(backup_dir))
        sub = steps[0]; files = dict(self.steps)[sub]; dest = Path(backup_dir) / sub
        for name, (base, after, _) in files.items():
            if sha(self._read(name)) != after: raise PermissionError('Installed %s is not the result of %s: nothing reverted' % (name, sub))
            if sha((dest / name).read_bytes()) != base: raise PermissionError('Backup of %s is not the reviewed base' % name)
        for name in files: self._write(name, (dest / name).read_bytes())
        os.rename(dest, dest.with_name(sub + '.reverted-' + os.urandom(3).hex()))
        bad = self._served({name: base for name, (base, _, _) in files.items()})
        return {'passed': all(sha(self._read(n)) == b for n, (b, _, _) in files.items()), 'step': sub, 'still_applied': self.pending(backup_dir),
                'https_verified': not bad, **({'https_mismatch': bad} if bad else {})}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    for a in ('check', 'apply', 'revert', 'pending'): g.add_argument('--' + a, action='store_true')
    p.add_argument('--backup')
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if not a.check and not a.backup: p.error('--backup DIR required')
    u = Update()
    if a.pending: print(' '.join(u.pending(a.backup))); sys.exit(0)
    try:
        out = u.plan()[1] if a.check else u.apply(a.backup) if a.apply else u.revert(a.backup)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:600]})); sys.exit(2)
    print(json.dumps(out, indent=1)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
