"""Additive opt-in schema with a verified pre-migration SQLite backup."""
import time
from ..store import snapshot
from .evidence import SCHEMA as RECEIPTS
from .heartbeat import SCHEMA as WORKERS

def migrate(memory):
 tables={r[0] for r in memory.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 if {'p6d_receipts','p6d_workers'}<=tables:return {'changed':False}
 backup=snapshot(memory.path,memory.path.with_name(memory.path.name+'.before-phase6d-'+str(time.time_ns())))
 memory.db.executescript('BEGIN IMMEDIATE;'+RECEIPTS+WORKERS+'COMMIT;')
 if memory.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Schema integrity')
 return {'changed':True,'backup':backup}
