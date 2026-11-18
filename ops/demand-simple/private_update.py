#!/usr/bin/python3 -I
"""Targeted update of the PRIVATE service release (/opt/jarvis-hermes-pilot): only the files
listed in FILES, only when the installed copy is exactly the reviewed base version.

Prod 16.11: missions failed because the model-facing envelope (phase2/bridge.py) showed grant
names as `allowed_tools`; the model called `report` and the gate (phase3/model_gate.py) refused
with a bare 403. The fix lives in the private service, whose coordinator verifies every file
against deployment-files.json at each start. This tool:
  --check                  read-only: base hashes, exhaustive pin scan, candidate verify_manifest + imports
  --apply --backup DIR     backup, replace files + manifest entries (root, original modes),
                           restart through private-boot (ports awaited); auto-restore on failure
  --revert --backup DIR    restore the backed-up files and manifest, restart
Nothing else in the release changes; no secret is read or printed.
"""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('simple_arm', HERE / 'arm.py')
arm = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(arm)

PILOT_ROOT = Path('/opt/jarvis-hermes-pilot')
STATE = Path('/var/lib/jarvis-hermes-pilot')
# Stacked updates, oldest first: (backup sub-directory, commit installed as base, path -> base hash).
# Only the LAST step can be applied (its target is this checkout); revert undoes the latest
# applied step, so successive reverts walk back to the accord-3 release.
STEPS = [
    ('private-update', 'eb17c0c', {      # accord 3 release -> envelope fix (2e4859d), applied 16.11
        'memory_manager/phase2/bridge.py': 'd441c0c7ac696a0266a98f41f45a4aa63221630ec9d4c9eb4139517dd0de5e02',
        'memory_manager/phase3/model_gate.py': '6a0d114bd029102a3762a12ea210eb95cb686ee3226e1d8c6739d033b4c05fd4'}),
    ('private-update-2', '2e4859d', {    # envelope fix -> citation rule in the tool policy
        'memory_manager/phase2/bridge.py': '5e99e01ea0bb8b5059bed14e0d4e1a44f6b61c97dcb1a16488039113acbd7a35'}),
    ('private-update-3', '51167ec', {    # report quality: declare an unverifiable mission report, do not fail the answer
        'memory_manager/phase6/demand_queue.py': 'ec47a88dde5176688942444d7933c845980ae16a200de61cbe1799db630bfe7f'}),
    ('private-update-4', '72391f3', {    # 17.11 real sources: read-only HA + InfluxDB tools (None = new file)
        'memory_manager/missions.py': '78afe95552fd2d0fa6ca60b5a41147b9f4acabfed20d847408f19eaaecb0a6ab',
        'memory_manager/phase2/bridge.py': 'da78b2dd0920bb5da22d143c3ff3f3baac315ad55387c3418fa982f889174a03',
        'memory_manager/phase2/mcp.py': '75383b7c0d0acb3a5d73da33cdc9120a114807be104e3d028ed192b803e80adf',
        'memory_manager/phase3/mcp.py': 'f77e9d6d945041d7388aa66600e75bad8aff4b6a627c953e8011790113ad00f1',
        'memory_manager/phase3/model_gate.py': '224a358aa6f96e61a2966441b7b02d8fed6db61d8f778530cde54e4bfcbf8d37',
        'memory_manager/phase6/demand_queue.py': 'bd3b69da2decd81e1d9a6a57e615c3af3e9e139cb03c3b88c23434f79f89dd48',
        'memory_manager/phase6/demand_service.py': '12e8fb4ebf6d939f64a5d3e393fd157fd33be2545c3cbffb380db151fddf94c7',
        'memory_manager/phase6/operational.py': '94025dfe43581d325a4dda2d69e69f670220d62cc0ab2bcb3d4e93e9372f7430',
        'memory_manager/phase6d/evidence.py': '13194e2ff6daf92dbb1fc34ef6a87616febcbeea96e8a6dd742620c99c4b9ecc',
        'memory_manager/sources/__init__.py': None,
        'memory_manager/sources/readers.py': None,
        'memory_manager/sources/tools.py': None}),
    ('private-update-5', 'b9b86be', {    # 17.11 prod is InfluxDB 3 Core (not 2): InfluxQL reader, `database` instead of `bucket`
        'memory_manager/sources/__init__.py': '36b9539cec06c7af5ad645f104b4dab357f910b60a359c5eeea7e9309a76512e',
        'memory_manager/sources/readers.py': '4921c0e0688cb6a2f590405d05dcb01ec4880532e2b5c7ef227f9e99ade9965d',
        'memory_manager/sources/tools.py': '89c6d7b25e00f5271a98f38890f3aae81c61efcc8a787c508b0bed125e9d6753',
        'memory_manager/phase2/mcp.py': 'dc84ecac79075cecd608c9f1b57193c70b6629837cc4ff123551c0b0711de498'}),
    ('private-update-6', '588a30c', {    # 17.11 mission 88b5bd9b: wait (bounded) for a ready GPU between model turns; journal 400s; withheld category
        'memory_manager/phase2/bridge.py': '49eb677f09df80d6b237d0093fa1295d7f6ca8ca6ed6b923e33c1cf86ff5206e',
        'memory_manager/phase3/model_gate.py': 'c8afaa43eb4c8492cb5133103b3c94396df1a95eaf031a07ac8fc464c3d1e616',
        'memory_manager/phase6/operational.py': '5b8c955d5ca4a9d2aec97d50206b99aa9bd062f6b9ff5b45b0f672cdb791d71f'}),
    ('private-update-7', '7b654f1', {    # 17.11 mission 0d1c6c51: per-call token reservation; 30 s for source tool calls (MCP proxy)
        'memory_manager/phase3/model_gate.py': 'eac31513fc901d1c5ead72b79fd32f0eb70fe0004e1049548976ebc96998c67b',
        'memory_manager/phase2/mcp.py': '90737477050b2d4fe21c8b12fdeb22ae42311a65c6f1451a39a575d455811a75'}),
    ('private-update-8', 'b67eb23', {    # 18.11 mission a89250f9: 'Body limit' (64 kB) refused a ~15k-token history; measured-prefix context bound
        'memory_manager/phase3/model_gate.py': '14963dc6a4539bf746dc5042e9244805016f63597d0f292cc5989169f48aa11f'}),
    # private-update-9 (357fea3, model kept loaded) was applied then reverted on 18.11 (mission ceb84d46).
    ('private-update-10', 'ef15837', {   # 18.11 diagnosis only: journal why the GPU is judged busy (numbers, on change)
        'memory_manager/phase6/operational.py': 'acb378576212b2be9d0bfc71a81ec7a13423f3258ba2ae03e9251ce827f45983'}),
    ('private-update-11', '0769b2d', {   # 18.11 (User): mining in parallel; VRAM-only check in the gate and the heartbeat
        'memory_manager/phase3/model_gate.py': 'a88c4dcfb12d852053c2cd01369cacbe9d5bc90be4db90bb9516a1be9963667b',
        'memory_manager/phase6/operational.py': '3aa6393b2cab074d1d36d2af084b0b1eb405b13079dda0a737b159b7dddce388'}),
    ('private-update-12', '40e506e', {   # 18.11 mission b7bd602a: the phase4 worker tick still refused mining (gpu_unavailable)
        'memory_manager/phase4/worker.py': '2dfd4cfa71a3716faf1a28e26ecf50a1320bf27ef7c663624bca9d6e8c66769b'}),
    ('private-update-13', 'fe8b45a', {   # 18.11 ebd39223: our own loaded model's VRAM counts as available to it (diagnosed /api/ps)
        'memory_manager/phase3/model_gate.py': 'b8a5f56c55f2de859b1e6bf0be3f75e7fee9378a25a38ef115835b7242bf2470',
        'memory_manager/phase6/operational.py': '138aaae81665bc595b687d7ee5080b25dab62da31901f2e0b38a85771e8352bf'}),
]
CREATED = '.created-files.json'     # in a step backup: files that step added (revert deletes them)
BACKUP_SUB, BASE_COMMIT, FILES = STEPS[-1]


def sha(raw): return hashlib.sha256(raw).hexdigest()


def root_file(path, owner=0):
    st = path.lstat()
    if path.is_symlink() or st.st_uid != owner or st.st_mode & 0o022: raise PermissionError('Root-owned, non-writable file required: ' + str(path))
    return path.read_bytes(), st


def write_like(path, raw, st):
    tmp = path.parent / ('.' + path.name + '.upd-' + os.urandom(4).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    os.chown(tmp, st.st_uid, st.st_gid); os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, path)


PILOT_MANIFEST = 'docs/pilot-interactive/manifest.json'   # checked by the service itself (verify_manifest)
DEPLOY = 'deployment-files.json'                            # checked by the coordinator (verify_layout)
VERIFIER = 'scripts/prepare_interactive_pilot.py'


def allowed_pins(files=None):
    """Every place a pinned hash may appear (prod scan 16.11: exactly these; 5 for two files, 3 for one)."""
    pins = {(DEPLOY, '/' + PILOT_MANIFEST)}
    for f, base in (files or FILES).items():
        if base: pins |= {(DEPLOY, '/' + f), (PILOT_MANIFEST, '/files/' + f)}
    return pins


def journal_tail(unit, n=8):
    r = subprocess.run(['journalctl', '-u', unit, '-n', str(n), '--no-pager', '-o', 'cat'], capture_output=True, text=True, timeout=10)
    return ' | '.join(l.strip()[:200] for l in r.stdout.splitlines()[-n:])


class Update:
    def __init__(self, src, root=PILOT_ROOT, state=STATE, *, restarter=None, import_check=True, owner=0, journal=journal_tail):
        self.owner = owner   # root in production; the test user in unit tests
        self.src, self.root, self.state = Path(src), Path(root), Path(state)
        self.arm = restarter or arm.Arm()
        self.import_check, self.journal = import_check, journal

    def _json(self, rel):
        raw, _ = root_file(self.root / rel, self.owner); return json.loads(raw), raw

    def scan(self, hashes):
        """(file, json key) of every occurrence of `hashes` in the release; text outside JSON keys -> '(text)'."""
        found = set()
        for d, _, names in os.walk(self.root):
            for n in names:
                p = Path(d) / n
                if p.is_symlink() or p.stat().st_size > 2_000_000: continue
                try: text = p.read_text(encoding='utf-8')
                except (UnicodeDecodeError, OSError): continue
                hits = [h for h in hashes if h in text]
                if not hits: continue
                rel = str(p.relative_to(self.root)); keys = []
                if rel.endswith('.json'):
                    def walk(o, k=''):
                        if isinstance(o, dict): [walk(v, k + '/' + a) for a, v in o.items()]
                        elif isinstance(o, list): [walk(v, k + '[%d]' % i) for i, v in enumerate(o)]
                        elif o in hits: keys.append(k)
                    try: walk(json.loads(text))
                    except ValueError: pass
                if len(keys) < sum(text.count(h) for h in hits): keys.append('(text)')
                found |= {(rel, k) for k in keys}
        return found

    def next_step(self, deploy):
        """The step whose bases are what deployment-files.json pins now (prod may be one step behind:
        apply it, then run again). Default: the last step, whose checks then explain the refusal."""
        last_sub, _, last_files = STEPS[-1]
        if all(deploy.get(n) == sha((self.src / n).read_bytes()) for n in last_files): raise PermissionError('Already updated (' + last_sub + ')')
        for sub, _, files in reversed(STEPS):
            if all(deploy.get(n) == b if b else n not in deploy for n, b in files.items()): return sub, files
        return last_sub, last_files

    def plan(self):
        deploy, _ = self._json(DEPLOY)
        pilot, pilot_raw = self._json(PILOT_MANIFEST)
        self.sub, FILES = self.next_step(deploy); self.files = FILES
        rows, contents = [], {}
        for name, base in FILES.items():
            if base is None:   # new file: absent everywhere, then pinned in both manifests like the others
                if (self.root / name).exists() or (self.root / name).is_symlink() or name in deploy or name in pilot.get('files', {}):
                    raise PermissionError('New file already present in the release: ' + name)
                new = (self.src / name).read_bytes(); contents[name] = new
                rows.append({'path': name, 'before': None, 'after': sha(new), 'changes': True}); continue
            installed, _ = root_file(self.root / name, self.owner)
            if sha(installed) != base: raise PermissionError('Installed file differs from reviewed base: ' + name)
            if deploy.get(name) != base: raise PermissionError('deployment-files.json entry differs from reviewed base: ' + name)
            if pilot.get('files', {}).get(name) != base: raise PermissionError(PILOT_MANIFEST + ' entry differs from reviewed base: ' + name)
            new = (self.src / name).read_bytes(); contents[name] = new
            rows.append({'path': name, 'before': base, 'after': sha(new), 'changes': sha(new) != base})
        if deploy.get(PILOT_MANIFEST) != sha(pilot_raw): raise PermissionError('deployment-files.json does not pin the installed ' + PILOT_MANIFEST)
        if not any(r['changes'] for r in rows): raise PermissionError('Nothing to update')
        pins = self.scan({h for h in FILES.values() if h} | {sha(pilot_raw)})
        if pins != allowed_pins(FILES): raise PermissionError('Unexpected pins (never updated blindly): ' + json.dumps(sorted(pins ^ allowed_pins(FILES))))
        # Cascade: code files -> service manifest -> coordinator manifest (nothing pins the latter).
        new_pilot = {**pilot, 'files': {**{k: (sha(contents[k]) if k in contents else v) for k, v in pilot['files'].items()},
                                        **{k: sha(contents[k]) for k, b in FILES.items() if b is None}}}
        contents[PILOT_MANIFEST] = (json.dumps(new_pilot, indent=2, ensure_ascii=False) + '\n').encode()
        new_deploy = {**{k: (sha(contents[k]) if k in contents else v) for k, v in deploy.items()},
                      **{k: sha(contents[k]) for k, b in FILES.items() if b is None}}
        contents[DEPLOY] = (json.dumps(new_deploy, indent=2) + '\n').encode()
        rows.append({'path': PILOT_MANIFEST, 'before': sha(pilot_raw), 'after': sha(contents[PILOT_MANIFEST]), 'changes': True})
        uncertain = arm.uncertain_executions(self.state / 'memory.sqlite')
        if uncertain: raise PermissionError('Uncertain execution in the queue: review, never replay (%d)' % uncertain)
        candidate = self._candidate_test(contents, new_pilot) if self.import_check else 'skipped'
        return contents, {'passed': True, 'step': self.sub, 'files': rows, 'pins_found': len(pins), 'candidate_test': candidate, 'uncertain_executions': 0,
                          'supervisor_state': self.arm.state(arm.SUPERVISOR), 'private_service_state': self.arm.state(arm.PILOT)}

    def _candidate_test(self, contents, new_pilot):
        """Candidate tree = installed files the service checks, with `contents` overlaid. Runs the
        release's OWN verify_manifest() (the check that refused prod 16.11) and imports the modules."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            shutil.copytree(self.root / 'memory_manager', d / 'memory_manager', ignore=shutil.ignore_patterns('__pycache__'))
            for rel in {*new_pilot['files'], VERIFIER, PILOT_MANIFEST}:
                if (d / rel).exists() or rel in contents: continue      # new files come from `contents` below
                (d / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(self.root / rel, d / rel)
            for rel, raw in contents.items():
                (d / rel).parent.mkdir(parents=True, exist_ok=True)
                if (d / rel).exists(): (d / rel).unlink()          # copies keep 0444
                (d / rel).write_bytes(raw)
            deploy = json.loads(contents[DEPLOY])
            for rel in contents:
                if rel != DEPLOY and sha((d / rel).read_bytes()) != deploy[rel]: raise RuntimeError('Candidate deployment-files.json mismatch: ' + rel)
            mods = [n[:-3].replace('/', '.') for n in self.files]
            code = ('import sys,importlib;sys.path.insert(0,sys.argv[1])\n'
                    'from scripts.prepare_interactive_pilot import verify_manifest;verify_manifest()\n'
                    'for m in sys.argv[2:]: importlib.import_module(m)')
            r = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(d), *mods], capture_output=True, text=True, timeout=60, cwd=d)
            if r.returncode: raise RuntimeError('Candidate refused (verify_manifest/import): ' + (r.stderr.strip().splitlines() or ['?'])[-1][:200])
        return 'verify_manifest ok, imports ok'

    def _write(self, contents):
        # Code first, coordinator manifest last. A new file takes the owner/mode of the package
        # marker next to it (or of memory_manager/__init__.py); a new directory those of memory_manager/.
        for rel in sorted(contents, key=lambda r: (r == DEPLOY, r == PILOT_MANIFEST, r)):
            target = self.root / rel
            if not target.exists():
                d_st = (self.root / 'memory_manager').stat()
                for d in reversed([q for q in target.relative_to(self.root).parents if q != Path('.')]):
                    if not (self.root / d).exists():
                        (self.root / d).mkdir(); os.chown(self.root / d, d_st.st_uid, d_st.st_gid); os.chmod(self.root / d, d_st.st_mode & 0o7777)
                _, st = root_file(self.root / 'memory_manager/__init__.py', self.owner)
            else:
                _, st = root_file(target, self.owner)
            write_like(target, contents[rel], st)

    def _remove(self, rels):
        for rel in sorted(rels, reverse=True):
            p = self.root / rel
            if p.exists() and not p.is_symlink(): p.unlink()
            for d in p.relative_to(self.root).parents:
                if d != Path('.') and (self.root / d).is_dir() and not any((self.root / d).iterdir()): (self.root / d).rmdir()

    def apply(self, backup_dir):
        contents, report = self.plan()
        dest = Path(backup_dir) / self.sub
        if dest.exists():
            # A failed attempt that was restored leaves a backup equal to what is installed: set it aside.
            saved = [q for q in dest.rglob('*') if q.is_file() and q.name != CREATED]
            if not saved or any((self.root / q.relative_to(dest)).read_bytes() != q.read_bytes() for q in saved):
                raise FileExistsError('Private update backup differs from the installed files (updated before?): ' + str(dest))
            os.rename(dest, dest.with_name(self.sub + '.failed-attempt-' + os.urandom(3).hex()))
        dest.mkdir(mode=0o700)
        created = sorted(r for r in contents if not (self.root / r).exists())
        for rel in contents:
            if rel in created: continue
            (dest / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(self.root / rel, dest / rel)
        (dest / CREATED).write_text(json.dumps(created))
        self.arm._stop_supervisor_if_idle(); self.arm.ctl('stop', arm.PILOT)
        try:
            self._write(contents); ok = self.arm._restart_private()
        except Exception as e:
            ok = False; self.arm.last_error = type(e).__name__ + ': ' + str(e)[:160]
        if not ok:
            # Journals of the FAILED attempt, captured before the restore restarts anything.
            failed = 'private-boot: %s || service: %s' % (self.journal(arm.BOOT), self.journal(arm.PILOT))
            self._write({rel: (dest / rel).read_bytes() for rel in contents if rel not in created}); self._remove(created)
            restored = self.arm._restart_private()
            raise RuntimeError('Private service did not start updated; previous files restored (%s). cause: %s. %s'
                               % ('restarted' if restored else 'NOT restarted', getattr(self.arm, 'last_error', None) or 'boot hook', failed))
        for rel, raw in contents.items():
            if (self.root / rel).read_bytes() != raw: raise RuntimeError('Post-update content mismatch: ' + rel)
        report.update(updated=True, step=self.sub, backup=str(dest), private_service_state=self.arm.state(arm.PILOT),
                      private_boot_state=self.arm.state(arm.BOOT), supervisor_state=self.arm.state(arm.SUPERVISOR))
        return report

    @staticmethod
    def pending(backup_dir):
        """Applied (not reverted) steps, latest first."""
        return [sub for sub, _, _ in reversed(STEPS) if (Path(backup_dir) / sub / DEPLOY).exists()]

    def revert(self, backup_dir):
        steps = self.pending(backup_dir)
        if not steps: raise FileNotFoundError('No private update backup in ' + str(backup_dir))
        sub = steps[0]; dest = Path(backup_dir) / sub
        if arm.uncertain_executions(self.state / 'memory.sqlite'): raise PermissionError('Uncertain execution in the queue: review before reverting')
        rels = [str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file() and p.name != CREATED]
        created = json.loads((dest / CREATED).read_text()) if (dest / CREATED).exists() else []
        self.arm._stop_supervisor_if_idle(); self.arm.ctl('stop', arm.PILOT)
        self._write({rel: (dest / rel).read_bytes() for rel in rels}); self._remove(created)
        ok = self.arm._restart_private()
        os.rename(dest, dest.with_name(sub + '.reverted-' + os.urandom(3).hex()))
        return {'passed': ok, 'step': sub, 'still_applied': self.pending(backup_dir), 'reverted_files': sorted(rels), 'removed_files': created, 'private_service_state': self.arm.state(arm.PILOT)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true'); g.add_argument('--apply', action='store_true'); g.add_argument('--revert', action='store_true')
    g.add_argument('--pending', action='store_true')
    p.add_argument('--backup'); p.add_argument('--source', default=str(HERE.parents[1]))
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if (a.apply or a.revert or a.pending) and not a.backup: p.error('--backup DIR required')
    if a.pending: print(' '.join(Update.pending(a.backup))); sys.exit(0)
    u = Update(a.source)
    try:
        out = u.plan()[1] if a.check else u.apply(a.backup) if a.apply else u.revert(a.backup)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:900]})); sys.exit(2)
    print(json.dumps(out, indent=1)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
