#!/usr/bin/python3 -I
"""Definitive removal of the DoseLab laboratory memory (decision User, 17.11.2026).

The private service's memory.sqlite only holds the DoseLab lab: synthetic records,
reports of test missions, their receipts and queue rows. Receipts are immutable by
design (triggers), so the lab is not purged row by row: the database is replaced by
a fresh one with the same schema (every existing migration applied, table set
checked), owned and moded like the old one. The old file, its WAL/SHM and the
same-folder copies (memory.backup.sqlite, restore-check.sqlite, memory.sqlite.before-*)
are deleted. Copies elsewhere (e.g. /var/backups/jarvis-hermes) are only LISTED.

  --check                          read-only: what would be deleted, row counts, blockers
  --apply --confirm SUPPRIMER-DOSELAB  replace the database (private service must be stopped)
Irreversible by request. No secret is read; no network; no service is started or stopped.
"""
import argparse, gc, json, os, sqlite3, subprocess, sys, tempfile
from contextlib import closing
from pathlib import Path

STATE = Path('/var/lib/jarvis-hermes-pilot')
APP = Path('/opt/jarvis-hermes-pilot')
PILOT = 'jarvis-hermes-pilot-system.service'
BACKUP_ROOTS = [Path('/var/backups/jarvis-hermes')]
WORD = 'SUPPRIMER-DOSELAB'


def tables(path):
    with closing(sqlite3.connect('file:%s?mode=ro' % path, uri=True)) as db:
        return sorted(r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'mm_fts_%'"))


def counts(path):
    with closing(sqlite3.connect('file:%s?mode=ro' % path, uri=True)) as db:
        out = {t: db.execute('SELECT count(*) FROM "%s"' % t).fetchone()[0] for t in ('mm_events', 'mm_memories', 'mm_missions', 'p6d_receipts', 'p6q_jobs')
               if db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone()}
        refs = {}
        for (src,) in db.execute('SELECT source FROM mm_events'):
            ref = json.loads(src).get('ref', '')
            key = ref.split('/')[0] + '//' + (ref.split('/')[2] if ref.startswith('synthetic://') else '')
            refs[key] = refs.get(key, 0) + 1
        uncertain = db.execute('SELECT count(*) FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0').fetchone()[0] if 'p6q_jobs' in out else 0
        uncertain += db.execute("SELECT count(*) FROM p2_outbox WHERE state IN ('unknown','submitting','submitted','cancel_requested')").fetchone()[0]
    return out, refs, uncertain


def same_folder_copies(state):
    names = ['memory.sqlite-wal', 'memory.sqlite-shm', 'memory.backup.sqlite', 'restore-check.sqlite']
    return [state / n for n in names if (state / n).exists()] + sorted(state.glob('memory.sqlite.before-*'))


def elsewhere(roots):
    return sorted(str(p) for root in roots if root.is_dir() for p in root.rglob('*.sqlite'))


def fresh(target_dir, app):
    """New database with every migration of the installed release, in target_dir (same filesystem)."""
    sys.path.insert(0, str(app))
    import importlib
    from memory_manager.store import Memory
    # Only the migrations the INSTALLED release has (prod 17.11: no phase5 in /opt/jarvis-hermes-pilot).
    migrations = []
    for name in ('memory_manager.phase2.database', 'memory_manager.phase5.database', 'memory_manager.phase6d.database', 'memory_manager.phase6.demand_queue'):
        if (Path(app) / (name.replace('.', '/') + '.py')).is_file(): migrations.append(importlib.import_module(name).migrate)
    fd, name = tempfile.mkstemp(prefix='.memory-fresh-', suffix='.sqlite', dir=target_dir); os.close(fd); os.unlink(name)
    m = Memory(Path(name), create=True)
    try:
        for migrate in migrations: migrate(m)
        if m.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise RuntimeError('Fresh database integrity')
    finally:
        m.close()
    gc.collect()   # store.snapshot() (used by migrations) leaves read-only connections to the GC
    with closing(sqlite3.connect(name)) as db: db.execute('PRAGMA journal_mode=DELETE')   # no WAL left beside the new file
    for p in Path(target_dir).glob(Path(name).name + '*'):
        if p != Path(name): p.unlink()          # migration snapshots of the empty database
    return Path(name)


def referenced(table, app):
    """True if any Python/SQL file of the installed release names this table."""
    for f in list(Path(app).rglob('*.py')) + list(Path(app).rglob('*.sql')):
        try:
            if table in f.read_text(encoding='utf-8', errors='ignore'): return True
        except OSError: continue
    return False


def active(unit):
    return subprocess.run(['systemctl', 'is-active', unit], capture_output=True, text=True).stdout.strip()


def check(state=STATE, roots=BACKUP_ROOTS, unit_state=None):
    db = state / 'memory.sqlite'
    c, refs, uncertain = counts(db)
    st = db.stat()
    blockers = []
    if (unit_state or active(PILOT)) not in ('inactive', 'failed', 'unknown'): blockers.append(PILOT + ' must be stopped')
    if uncertain: blockers.append('%d uncertain execution(s) in the queue: review first' % uncertain)
    return {'database': str(db), 'owner_uid': st.st_uid, 'mode': oct(st.st_mode & 0o777), 'rows': c, 'provenance': refs,
            'deleted_with_it': [str(p) for p in same_folder_copies(state)], 'copies_elsewhere_not_deleted': elsewhere(roots),
            'blockers': blockers, 'passed': not blockers}


def apply(confirm, state=STATE, app=APP, roots=BACKUP_ROOTS, unit_state=None):
    if confirm != WORD: raise PermissionError('Type --confirm ' + WORD)
    report = check(state, roots, unit_state)
    if report['blockers']: raise PermissionError('; '.join(report['blockers']))
    db = state / 'memory.sqlite'; st = db.stat(); before = tables(db)
    new = fresh(state, app)
    try:
        missing = sorted(set(before) - set(tables(new)))
        used = [t for t in missing if referenced(t, app)]
        if used: raise RuntimeError('Fresh schema lacks tables used by the installed release: ' + ', '.join(used))
        os.chown(new, st.st_uid, st.st_gid); os.chmod(new, st.st_mode & 0o777)
        for p in same_folder_copies(state): p.unlink()
        os.replace(new, db)
    finally:
        if new.exists(): new.unlink()
    with closing(sqlite3.connect('file:%s?mode=ro' % db, uri=True)) as d:
        events = d.execute('SELECT count(*) FROM mm_events').fetchone()[0]
    return {'passed': events == 0, 'database': str(db), 'mm_events': events, 'tables': len(tables(db)), 'dropped_unused_tables': missing,
            'removed': report['deleted_with_it'] + [str(db) + ' (old)'], 'copies_elsewhere_not_deleted': report['copies_elsewhere_not_deleted']}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true'); g.add_argument('--apply', action='store_true')
    p.add_argument('--before-stop', action='store_true', help='check only: the service is stopped later by the caller')
    p.add_argument('--confirm', default='')
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    try: out = check(unit_state='inactive' if a.before_stop else None) if a.check else apply(a.confirm)
    except Exception as e:
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:600]})); sys.exit(2)
    print(json.dumps(out, indent=1, ensure_ascii=False)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
