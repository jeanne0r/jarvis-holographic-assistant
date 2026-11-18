"""Pure C-window contracts; no service, network, secret or GPU operations."""
import re


def gateway_expected(row,changed,review):
    old=row['after'] if row['target'] in changed else row['before']
    approved=review['gateway_assets']
    if row['target'] in approved:return approved[row['target']]
    return old


def result_provenance(projection,output,db):
    if projection.get('origin')!='sqlite' or projection.get('selection_origin')!='authenticated_host_tool_receipts':
        raise PermissionError('Authenticated canonical SQLite receipts required')
    items=projection.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=200:raise PermissionError('Bounded source receipts required')
    refs=[]
    for item in items:
        ref=item.get('source_ref','')
        if ref in {'synthetic://doselab/experience','synthetic://doselab/old','synthetic://doselab/correction'}:
            refs.append(ref);continue
        if not re.fullmatch(r'mission://[0-9a-f-]{36}',ref):raise PermissionError('Unexpected source reference')
        mid=ref.removeprefix('mission://')
        row=db.execute("SELECT 1 FROM mm_missions WHERE id=? AND owner='phase3-synthetic' AND scope='private' AND state='completed'",(mid,)).fetchone()
        event=db.execute("SELECT 1 FROM mm_events WHERE owner='phase3-synthetic' AND scope='private' AND event_key=?",('mission-result-'+mid,)).fetchone()
        if not row or not event:raise PermissionError('Unverified synthetic mission source')
        refs.append(ref)
    return refs,any(ref.startswith('synthetic://doselab/') and ref in output for ref in refs)
