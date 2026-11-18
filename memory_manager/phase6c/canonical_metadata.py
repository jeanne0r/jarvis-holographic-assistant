"""Read-only metadata projection, selected by the controller, never by model text.

Not an HTTP endpoint. Tool-use attestation/mission binding must be supplied by
its future host integration. Projection is not proof that Hermes read a source.
"""
from datetime import datetime, timezone
import math
import re
import time
from ..phase2.bridge import Bridge


def utc(value):
    if value is None:return None
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite canonical timestamp required')
    try:return datetime.fromtimestamp(value,timezone.utc).isoformat().replace('+00:00','Z')
    except (ValueError,OverflowError,OSError):raise ValueError('Canonical timestamp out of range') from None


def project(memory,principal,mission_id,observed_memory_ids,*,at=None):
    principal.require('mission_worker')
    Bridge(memory,principal).get(mission_id) # same canonical owner/scope ACL
    if not isinstance(observed_memory_ids,list) or not 1<=len(observed_memory_ids)<=20:raise ValueError('One to twenty distinct stable IDs')
    if any(not isinstance(mid,str) or not re.fullmatch(r'[a-fA-F0-9-]{36}',mid) for mid in observed_memory_ids):raise ValueError('Stable memory IDs required')
    if len(set(observed_memory_ids))!=len(observed_memory_ids):raise ValueError('Distinct stable IDs required')
    at=time.time() if at is None else at;utc(at)
    rows=[];count=0
    for mid in observed_memory_ids:
        record=memory._row(principal,mid)
        count+=memory.db.execute('SELECT count(*) FROM mm_revisions WHERE memory_id=?',(mid,)).fetchone()[0]
        if count>200:raise ValueError('Metadata revision bound exceeded')
        for row in memory.history(principal,mid):
            source=row['source']
            rows.append({'memory_id':mid,'revision_id':row['id'],'parent_revision_id':row['parent'],
                'is_current_revision':row['id']==record['current_revision'],
                'valid_now':row['valid_from']<=at and (row['valid_to'] is None or at<row['valid_to']),
                'stored_validation_status':row['status'],'revision_status':row['effective_status'],
                'source_ref':source['ref'],'source_kind':source['kind'],
                'observed_unix_seconds':row['observed'],'observed_utc':utc(row['observed']),
                'valid_from_utc':utc(row['valid_from']),'valid_to_utc':utc(row['valid_to']),
                'confidence':row['confidence']})
    return {'schema':'canonical_metadata.v1','origin':'sqlite','mission_id':mission_id,
        'selection_origin':'controller_supplied_ids_not_proof_of_tool_use',
        'promotion_performed':False,'contradiction_resolution':'not_performed','items':rows}
