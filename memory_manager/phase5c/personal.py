"""Offline personal dry-run on explicitly selected rows only; no source DB access."""
import json
import os
from pathlib import Path
from ..phase5.import_plan import plan

PROJECT = 'Antminer S19 XP Hydro — refroidissement'


def reference(row):
    return tuple(row[k] for k in ('source_db', 'table', 'id'))


def dry_run(rows, selection, identities):
    if selection.get('project') != PROJECT or not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('One bounded project required')
    if len(json.dumps(rows, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 512000:
        raise ValueError('Partition private review below 512 KB')
    refs = [reference(r) for r in selection['sources']]
    if not 1 <= len(refs) <= 20 or len(set(refs)) != len(refs):
        raise ValueError('One to twenty distinct sources required')
    if any(reference(r) not in refs or r['subject'] != PROJECT for r in rows):
        raise PermissionError('Row outside reviewed project/source selection')
    result = plan(rows, identities)
    # Content is present ONLY in the private report, never public metrics.
    result.update(project=PROJECT, selected_sources=selection['sources'],
                  source_count=len(refs), import_authorized=False,
                  windows_transmission_authorized=False, private_index_authorized=False)
    result['proposals'] = [{'candidate': item, 'content': row['content'],
                            'type': row['type'], 'subject': row['subject'],
                            'predicate': row['predicate']} for item, row in zip(result.pop('items'), rows)]
    return result


def write_private(folder, result):
    """New directory only; no overwrite, no database mutation or network."""
    base = Path(__file__).resolve().parents[2] / 'data'
    root = base / 'phase5c'
    if root.is_symlink() or not root.resolve().is_relative_to(base.resolve()):
        raise PermissionError('Private root must remain in worktree data')
    root = root.resolve()
    folder = Path(folder)
    if folder.is_symlink() or not folder.resolve().is_relative_to(root) or folder.resolve() == root:
        raise PermissionError('Private worktree data/phase5c subdirectory required')
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    folder.chmod(0o700)
    path = folder / 'import-review.json'
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    return path
