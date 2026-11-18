"""Pure bounded dry-run planner. Never reads a live database or writes knowledge."""
from collections import Counter
import math
from ..store import digest, SECRET


def plan(rows, identities):
    """Rows are host-selected structured candidates, not arbitrary conversation text.

    identities: trusted legacy-space -> (owner, canonical-scope) mapping. Keeping
    row IDs/hashes private still matters: this result must not be published as a
    personal-memory export. Original statements are never independently verified.
    """
    if not isinstance(rows, list) or len(rows) > 500: raise ValueError('Partition import')
    items, seen, groups = [], {}, {}
    for row in rows:
        if set(row) != {'source_db','table','id','space','observed_at','type','subject','predicate','content','speaker','replaces'}:
            raise ValueError('Explicit source mapping required')
        if row['space'] not in identities: raise PermissionError('No trusted identity mapping')
        owner, scope = identities[row['space']]
        if not owner or scope not in {'private','shared'}: raise ValueError('Identity mapping')
        if row['speaker'] not in {'user','assistant','measurement','document'}: raise ValueError('Source class')
        if type(row['observed_at']) not in (int,float) or not math.isfinite(row['observed_at']) or row['observed_at'] <= 0:
            raise ValueError('Original timestamp required')
        if not isinstance(row['content'],dict) or not row['content']: raise ValueError('Structured candidate required')
        if SECRET.search(str(row)): raise ValueError('Secret excluded')
        content_hash = digest({k:row[k] for k in ('type','subject','predicate','content')})
        key = (owner, scope, content_hash)
        source = {k:row[k] for k in ('source_db','table','id','observed_at','speaker')}
        item = {'candidate_id': digest({'source':source,'owner':owner,'scope':scope,'content_hash':content_hash}),
                'source':source,'owner':owner,'scope':scope,'content_hash':content_hash,
                'proposed_status':'inferred','requires_review':True,
                'source_class': 'user_statement' if row['speaker']=='user' else 'untrusted_assertion',
                'replaces_claim':row['replaces'],'automatic_supersession':False,
                'duplicate_of':seen.get(key),'contradicts':[]}
        seen.setdefault(key,item['candidate_id'])
        groupkey = (owner,scope,row['type'],row['subject'],row['predicate'])
        for other in groups.setdefault(groupkey,[]):
            if other['content_hash'] != content_hash:
                other['contradicts'].append(item['candidate_id']);item['contradicts'].append(other['candidate_id'])
        groups[groupkey].append(item);items.append(item)
    return {'mode':'dry-run','writes':0,'items':items,'counts':dict(Counter(
        'duplicate' if i['duplicate_of'] else 'candidate' for i in items)),
        'contradiction_candidates':sum(bool(i['contradicts']) for i in items)}
