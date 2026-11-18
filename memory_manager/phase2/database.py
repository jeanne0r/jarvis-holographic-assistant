import json
from pathlib import Path
import time
from ..store import snapshot, uid


def migrate(memory):
    """Explicit additive migration of a phase-1 LAB database, with verified backup."""
    exists = memory.db.execute("SELECT 1 FROM sqlite_master WHERE name='p2_schema'").fetchone()
    if exists and memory.db.execute('SELECT version FROM p2_schema').fetchone():
        return {'changed': False}
    backup = memory.path.with_name(memory.path.name + '.before-phase2-' + uid())
    report = snapshot(memory.path, backup)
    backup.with_suffix(backup.suffix + '.manifest.json').write_text(json.dumps(report, indent=2))
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        for sql in Path(__file__).with_name('schema.sql').read_text().split(';'):
            if sql.strip(): memory.db.execute(sql)
        memory.db.execute('INSERT OR IGNORE INTO p2_schema VALUES(1,?)', (time.time(),))
    return {'changed': True, 'backup': report}


def require(memory):
    if memory.db.execute('SELECT version FROM p2_schema').fetchone()[0] != 1:
        raise ValueError('Phase 2 migration required')
