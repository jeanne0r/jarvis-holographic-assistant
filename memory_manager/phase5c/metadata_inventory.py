"""C2 metadata only. No FTS, conversation bodies, model, or import reservation."""
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from .local_review import exclusive

ALLOWED = {
    'docs': {'id', 'space', 'title', 'kind', 'updated'},
    'conversation_sessions': {'id', 'space', 'created', 'channel'},
    'conversation_turns': {'session_id', 'turn', 'revision', 'updated', 'status'},
}
PROJECT = "(lower(d.title) LIKE '%s19%' OR lower(d.title) LIKE '%antminer%') AND (lower(d.title) LIKE '%hydro%' OR lower(d.title) LIKE '%refroid%')"


def authorize(action, table, column, *_):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if table in ALLOWED and (column in ALLOWED[table] or column == '') else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def inventory(database, folder):
    folder = Path(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    folder.chmod(0o700)
    c = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON'); c.execute('PRAGMA temp_store=MEMORY')
    c.set_authorizer(authorize); c.execute('BEGIN')
    try:
        # Titles are existing metadata, used only as a deterministic selector.
        # No title/excerpt is emitted. No search index or content column read.
        groups = [dict(r) for r in c.execute('SELECT d.kind,count(*) AS count FROM docs d WHERE d.space=? AND ' + PROJECT + ' GROUP BY d.kind', ('user',))]
        rows = [dict(r) for r in c.execute('''SELECT t.session_id,t.turn,t.revision,t.updated,t.status,
          s.space,s.created AS session_created,s.channel,d.id AS document_id
          FROM conversation_turns t JOIN conversation_sessions s ON s.id=t.session_id
          JOIN docs d ON d.id=('jarvis:'||t.session_id||':'||t.turn) AND d.space=s.space
          WHERE s.space=? AND ''' + PROJECT + '''
          ORDER BY t.updated DESC,t.session_id,t.turn LIMIT 20''', ('user',))]
        for row in rows:
            row['updated_utc'] = datetime.fromtimestamp(row['updated'], timezone.utc).isoformat()
            row['session_created_utc'] = datetime.fromtimestamp(row['session_created'], timezone.utc).isoformat()
        report = {'mode': 'metadata-inventory-only', 'project': 'S19 Hydro', 'maximum_proposed_turns': 20,
                  'metadata_match_groups': groups, 'proposed_turns': rows,
                  'selection_basis': 'Existing per-document title metadata: S19/Antminer AND Hydro/refroid; no body matching.',
                  'relevance': 'Provisional metadata match, not verified by reading the turns.',
                  'date_meaning': 'Turn update and session creation timestamps, not technical measurement dates.',
                  'content_reads': 0, 'fts_reads': 0, 'model_calls': 0, 'source_writes': 0,
                  'personal_transmissions': 0, 'content_read_authorized': False,
                  'old_c2_reservation_reused': False,
                  'caveat': 'Imported conversation documents have no normalized turn identifiers; never treat a whole export as one turn.'}
        exclusive(folder / 'inventory.json', report)
        lines = ['# Inventaire privé C2 — métadonnées uniquement', '',
                 'Aucun corps de tour lu. Sélection provisoire par titres existants uniquement ; titres non copiés.',
                 'Aucune autorisation de lecture du contenu. L’ancienne réserve C2 reste bloquée.', '',
                 '| session_id | turn | revision | Date mise à jour UTC | Espace | État |',
                 '|---|---:|---:|---|---|---|']
        for r in rows:
            lines.append(f"| {r['session_id']} | {r['turn']} | {r['revision']} | {r['updated_utc']} | {r['space']} | {r['status']} |")
        if not rows:
            lines += ['', '**Aucun tour normalisé identifiable par ces métadonnées. Aucune liste artificielle de vingt tours n’est proposée.**']
        lines += ['', 'Les dates sont celles du stockage, pas celles des mesures. Les exports documentaires ne fournissent pas de références de tours ; leur découpage exigerait un autre accord.']
        # Use the exclusive writer for private permissions, then render Markdown
        # without any source content. No files inside old C2 folders are touched.
        import os
        with os.fdopen(os.open(folder/'SELECTION.md',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w',encoding='utf-8') as f:
            f.write('\n'.join(lines)+'\n')
        return {'proposed_turns': len(rows), 'metadata_matched_documents': sum(r['count'] for r in groups),
                'private_selection': str(folder/'SELECTION.md'), 'content_reads': 0}
    finally:
        c.rollback(); c.close()
