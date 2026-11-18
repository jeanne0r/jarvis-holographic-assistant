PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS mm_schema(version INTEGER PRIMARY KEY, applied REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mm_events(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
 event_key TEXT NOT NULL, fingerprint TEXT NOT NULL, source TEXT NOT NULL,
 created REAL NOT NULL, UNIQUE(owner,scope,event_key)
);
CREATE TABLE IF NOT EXISTS mm_memories(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
 current_revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mm_revisions(
 id TEXT PRIMARY KEY, memory_id TEXT NOT NULL REFERENCES mm_memories(id),
 parent TEXT REFERENCES mm_revisions(id), event_id TEXT NOT NULL REFERENCES mm_events(id),
 type TEXT NOT NULL CHECK(type IN ('identity','knowledge','episode','project','skill','lesson')),
 subject TEXT NOT NULL, predicate TEXT NOT NULL, content TEXT NOT NULL,
 observed REAL NOT NULL, valid_from REAL NOT NULL, valid_to REAL,
 confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 status TEXT NOT NULL CHECK(status IN ('observed','inferred','user_confirmed','verified','disputed','superseded')),
 created REAL NOT NULL, CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE INDEX IF NOT EXISTS mm_subject ON mm_revisions(subject,predicate);
CREATE TABLE IF NOT EXISTS mm_relations(
 source TEXT NOT NULL REFERENCES mm_revisions(id), target TEXT NOT NULL REFERENCES mm_revisions(id),
 kind TEXT NOT NULL, PRIMARY KEY(source,target,kind)
);
CREATE VIRTUAL TABLE IF NOT EXISTS mm_fts USING fts5(revision UNINDEXED,subject,content);
CREATE TABLE IF NOT EXISTS mm_audit(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
 memory_id TEXT NOT NULL REFERENCES mm_memories(id), before_revision TEXT,
 after_revision TEXT NOT NULL REFERENCES mm_revisions(id), event_id TEXT NOT NULL,
 created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS mm_jobs(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL,
 event_key TEXT NOT NULL, state TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0,
 items TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL, max_seconds REAL NOT NULL,
 result TEXT NOT NULL DEFAULT '[]', created REAL NOT NULL, updated REAL NOT NULL,
 UNIQUE(owner,scope,kind,event_key)
);
CREATE TABLE IF NOT EXISTS mm_missions(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
 event_key TEXT NOT NULL, state TEXT NOT NULL, definition TEXT NOT NULL,
 created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(owner,scope,event_key)
);
CREATE TABLE IF NOT EXISTS mm_mission_events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL REFERENCES mm_missions(id),
 state TEXT NOT NULL, actor TEXT NOT NULL, evidence TEXT NOT NULL, created REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS mm_revision_no_update BEFORE UPDATE ON mm_revisions
BEGIN SELECT RAISE(ABORT,'immutable revision'); END;
CREATE TRIGGER IF NOT EXISTS mm_revision_no_delete BEFORE DELETE ON mm_revisions
BEGIN SELECT RAISE(ABORT,'immutable revision'); END;
CREATE TRIGGER IF NOT EXISTS mm_audit_no_update BEFORE UPDATE ON mm_audit
BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
CREATE TRIGGER IF NOT EXISTS mm_audit_no_delete BEFORE DELETE ON mm_audit
BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
CREATE TRIGGER IF NOT EXISTS mm_events_no_update BEFORE UPDATE ON mm_events
BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS mm_events_no_delete BEFORE DELETE ON mm_events
BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS mm_mission_events_no_update BEFORE UPDATE ON mm_mission_events
BEGIN SELECT RAISE(ABORT,'immutable mission event'); END;
CREATE TRIGGER IF NOT EXISTS mm_mission_events_no_delete BEFORE DELETE ON mm_mission_events
BEGIN SELECT RAISE(ABORT,'immutable mission event'); END;
