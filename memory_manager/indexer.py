"""Injected Qdrant driver, disabled without explicit host-supplied transport.

No collection creation, deletion, prune or network configuration here. Tests
use an in-memory fake. Deployment must provision a separate collection first.
"""
import math
import uuid
from .consolidate import plan_index


def index(memory, principal, driver, embed, *, collection):
    if not collection.startswith('jarvis_knowledge_experimental_'):
        raise PermissionError('Dedicated experimental collection required')
    if driver.dimensions(collection) != 384:
        raise ValueError('Embedding dimensions mismatch')
    rows = plan_index(memory, principal)
    for row in rows:
        vector = list(embed(row['text']))
        if len(vector) != 384 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
            raise ValueError('Invalid embedding')
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, collection + ':' + row['memory_id'] + ':' + row['revision']))
        driver.upsert(collection, {'id': point_id, 'vector': vector, 'payload': row})
    # Old revisions may remain; mandatory canonical validation in search rejects
    # them. Garbage collection requires a separate reviewed retention policy.
    return {'upserted': len(rows), 'collection': collection, 'deleted': 0}
