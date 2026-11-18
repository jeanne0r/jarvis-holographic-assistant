"""Plan exact turns from approved structured METADATA only, never flattened text.

No file/database/network access. Source adapters and body extraction are deliberately
not wired: locating/opening personal structured exports needs a separate approval.
"""
import hashlib
import json

FIELDS = {'id','role','observed_at','revision'}


def plan(source, metadata, selected_user_ids):
    if set(source)!={'document_id','space','format','fingerprint','updated_at'}:
        raise ValueError('Exact source metadata required')
    if source['format'] not in {'chatgpt-active-branch-metadata-v1','codex-final-message-metadata-v1'}:
        raise ValueError('Flattened documents are ambiguous; structured provenance required')
    if not all(isinstance(source[k],str) and source[k] for k in ('document_id','space','fingerprint')):
        raise ValueError('Stable source revision and scope required')
    if source['updated_at'] is not None and (type(source['updated_at']) not in (int,float) or not 0<=source['updated_at']<1e12):
        raise ValueError('Invalid source storage date')
    if not isinstance(metadata,list) or len(metadata)>100000:
        raise ValueError('Bounded metadata list required')
    if not isinstance(selected_user_ids,list) or not 1<=len(selected_user_ids)<=20 or any(not isinstance(i,str) or not i for i in selected_user_ids) or len(set(selected_user_ids))!=len(selected_user_ids):
        raise ValueError('One approved set of at most twenty distinct user turns')
    ids=set(); turns=[]; current=None
    for m in metadata:
        if not isinstance(m,dict) or set(m)!=FIELDS:
            raise ValueError('Metadata only; text/content fields forbidden')
        if not isinstance(m['id'],str) or not m['id'] or m['id'] in ids or m['role'] not in {'user','assistant'}:
            raise ValueError('Unique native message IDs and authoritative roles required')
        if not isinstance(m['revision'],str) or not m['revision']:
            raise ValueError('Message revision required')
        # Missing message dates remain unknown; document dates are not substitutes.
        if m['observed_at'] is not None and (type(m['observed_at']) not in (int,float) or not 0<=m['observed_at']<1e12):
            raise ValueError('Invalid source date')
        ids.add(m['id'])
        if m['role']=='user':
            current={'user':dict(m),'assistant':[]};turns.append(current)
        elif current is not None:
            current['assistant'].append(dict(m))
        else:raise ValueError('Assistant without user: do not invent pairing')
    lookup={t['user']['id']:t for t in turns}
    if any(i not in lookup for i in selected_user_ids):raise ValueError('Selected turn absent from exact source revision')
    result=[]
    for ident in selected_user_ids:
        turn=lookup[ident]
        if not turn['assistant']:raise ValueError('Incomplete turn requires separate review; no automatic replacement')
        reference={'source_document_id':source['document_id'],'space':source['space'],
                   'source_fingerprint':source['fingerprint'],'user_message':turn['user'],
                   'assistant_messages':turn['assistant']}
        stable=hashlib.sha256(json.dumps(reference,sort_keys=True,allow_nan=False).encode()).hexdigest()
        result.append({'turn_reference':reference,'reference_digest':stable,
                       'read_authorized':False,'counts_toward_limit_even_if_excluded':True})
    manifest={'version':1,'source':dict(source),'turns':result,'maximum_turns':20,
              'content_reads':0,'import_authorized':False,'windows_transmission_authorized':False}
    manifest['approval_fingerprint']=hashlib.sha256(json.dumps(manifest,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return manifest
