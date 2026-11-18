#!/usr/bin/python3 -I
"""Close an UNCERTAIN on-demand mission (quarantined: "À vérifier") without ever replaying it.

A quarantined job blocks the whole queue (peek) and every private update, by design. Once the
operator has checked that nothing of it still runs (supervisor stopped; its Windows window is
bounded to 300 s and owned processes are killed by their Job Object), this tool:
  - marks the mission `failed` (never completed, never re-queued) and its outbox `failed`,
  - releases the queue row (lease NULL, cleanup_ok=1, reason 'reconciled'),
  - APPENDS an event `operator-reconciled` with the previous states; nothing is deleted or rewritten.
Writes run as the database owner (the private service account), private service stopped.

  --check                                   read-only: uncertain jobs and what blocks the queue
  --close MID --windows-idle-confirmed      close it (type the confirmation word shown by --check)
"""
import argparse, importlib.util, json, os, sqlite3, sys, time, uuid
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = Path('/var/lib/jarvis-hermes-pilot/memory.sqlite')
OPEN_OUTBOX = ('unknown', 'submitting', 'submitted', 'cancel_requested')


def uncertain(db_path):
    with closing(sqlite3.connect('file:%s?mode=ro' % db_path, uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute('''SELECT q.mission_id, q.reason, q.lease, q.cleanup_ok, m.state AS mission_state, o.state AS outbox_state
                             FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id LEFT JOIN p2_outbox o ON o.mission_id=q.mission_id
                             WHERE q.lease IS NOT NULL OR q.cleanup_ok=0 OR o.state IN (%s)''' % ','.join('?' * len(OPEN_OUTBOX)), OPEN_OUTBOX).fetchall()
        out = []
        for r in rows:
            kinds = [e[0] for e in db.execute('SELECT kind FROM p2_events WHERE mission_id=? ORDER BY seq DESC LIMIT 6', (r['mission_id'],))]
            out.append({**dict(r), 'last_events': kinds, 'confirm_word': 'FERMER-' + r['mission_id'][:8]})
        return out


def close(db_path, mid, *, now=time.time):
    """Runs as the database owner. Appends, never deletes."""
    with closing(sqlite3.connect(db_path, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        with db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT m.state AS mission_state, o.state AS outbox_state, q.reason, q.lease, q.cleanup_ok
                                FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id LEFT JOIN p2_outbox o ON o.mission_id=q.mission_id
                                WHERE q.mission_id=?''', (mid,)).fetchone()
            if not row: raise KeyError('Unknown queued mission')
            if row['lease'] is None and row['cleanup_ok'] == 1 and row['outbox_state'] not in OPEN_OUTBOX: raise PermissionError('Mission is not uncertain')
            previous = dict(row)
            if row['mission_state'] not in ('completed', 'failed', 'cancelled'):
                db.execute("UPDATE mm_missions SET state='failed',updated=? WHERE id=?", (now(), mid))
            if row['outbox_state'] in OPEN_OUTBOX:
                db.execute("UPDATE p2_outbox SET state='failed',lease_until=0 WHERE mission_id=?", (mid,))
            db.execute("UPDATE p6q_jobs SET lease=NULL,cleanup_ok=1,reason='reconciled' WHERE mission_id=?", (mid,))
            cols = [c[1] for c in db.execute('PRAGMA table_info(p2_events)')]
            values = {'mission_id': mid, 'event_key': 'operator-reconciled-' + uuid.uuid4().hex[:8], 'kind': 'reconciliation_closed',
                      'data': json.dumps({'automatic_replay': False, 'closed_as': 'failed', 'previous': previous, 'windows_idle_confirmed_by_operator': True}),
                      'created': now()}
            if set(values) - set(cols): raise RuntimeError('Unexpected p2_events schema')
            db.execute('INSERT INTO p2_events(%s) VALUES(%s)' % (','.join(values), ','.join('?' * len(values))), list(values.values()))
    return {'passed': True, 'mission_id': mid, 'previous': previous, 'now': 'failed (not replayed)'}


def as_owner(path, fn):
    st = Path(path).stat()
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([]); os.setgid(st.st_gid); os.setuid(st.st_uid)
            print(json.dumps(fn(), ensure_ascii=False)); os._exit(0)
        except BaseException as e:
            print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:300]})); os._exit(2)
    return os.waitpid(pid, 0)[1] == 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true'); g.add_argument('--close', metavar='MISSION_ID')
    p.add_argument('--windows-idle-confirmed', action='store_true'); p.add_argument('--confirm', default='')
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    if a.check:
        print(json.dumps({'uncertain': uncertain(DB)}, indent=1)); return
    if not a.windows_idle_confirmed: sys.exit('--windows-idle-confirmed required (check that no Hermes run remains on Windows)')
    if a.confirm != 'FERMER-' + a.close[:8]: sys.exit('--confirm FERMER-' + a.close[:8] + ' required')
    spec = importlib.util.spec_from_file_location('simple_arm', HERE / 'arm.py')
    arm = importlib.util.module_from_spec(spec); spec.loader.exec_module(arm)
    r = arm.Arm(); r._stop_supervisor_if_idle(); r.ctl('stop', arm.PILOT)
    ok = as_owner(DB, lambda: close(DB, a.close))
    restarted = r._restart_private()
    print(json.dumps({'closed': ok, 'private_service_state': r.state(arm.PILOT), 'restarted': bool(restarted),
                      'still_uncertain': len(uncertain(DB))}, indent=1))
    sys.exit(0 if ok and restarted else 2)


if __name__ == '__main__':
    main()
