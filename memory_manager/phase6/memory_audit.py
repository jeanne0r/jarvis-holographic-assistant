"""Read-only, canonical audit. Similarity is a proposal, never a write authority."""
import hashlib,json,time,re

def audit(memory,principal,q,*,searcher=None,now=None):
    principal.require('reader')
    if not isinstance(q,str) or not 1<=len(q)<=200:raise ValueError('Bounded topic required')
    now=time.time() if now is None else now
    results=searcher(q) if searcher else memory.search(principal,q)
    ids=list(dict.fromkeys(r['memory_id'] for r in results))
    # Current search intentionally hides expired rows. Include authorized topical
    # historical hits for this read-only audit, then revalidate every ID below.
    words=re.findall(r'\w+',q)[:20];scopes=sorted(principal.scopes)
    if words and scopes:
        match=' OR '.join('"'+w+'"' for w in words)
        rows=memory.db.execute('SELECT DISTINCT m.id FROM mm_fts f JOIN mm_revisions r ON r.id=f.revision JOIN mm_memories m ON m.id=r.memory_id WHERE mm_fts MATCH ? AND (m.scope!=? OR m.owner=?) AND m.scope IN ('+','.join('?' for _ in scopes)+') LIMIT 21',(match,'private',principal.name,*scopes))
        ids=list(dict.fromkeys(ids+[r[0] for r in rows]))
    if len(ids)>20:raise ValueError('At most twenty canonical memories per audit')
    canonical={r['memory_id']:r for r in memory.current(principal,at=now)}
    items=[];proposals=[];pairs=[];revision_count=0
    for mid in ids:
        record=memory._row(principal,mid) # Qdrant/FTS suggestions never supply authority.
        revision_count+=memory.db.execute('SELECT count(*) FROM mm_revisions WHERE memory_id=?',(mid,)).fetchone()[0]
        if revision_count>200:raise ValueError('Bounded revision audit')
        for row in memory.history(principal,mid):
            item={k:row[k] for k in ['id','memory_id','type','subject','predicate','content','status','effective_status','observed','valid_from','valid_to','source']}
            item['is_current']=row['id']==record['current_revision']
            if item['is_current'] and mid in canonical:item['effective_status']=canonical[mid]['effective_status']
            item['valid_now']=row['valid_from']<=now and (row['valid_to'] is None or now<row['valid_to'])
            item['content_sha256']=hashlib.sha256(json.dumps(row['content'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            items.append(item)
            ref=row['source'].get('ref')
            if not isinstance(ref,str) or not ref:raise ValueError('Canonical source reference required')
            reasons=[]
            if not item['is_current']:reasons.append('historical_version_preserve')
            if not item['valid_now']:reasons.append('outside_validity_period')
            if row['status'] in {'inferred','disputed','observed'}:reasons.append('not_independently_verified')
            if not row['source'].get('kind') or not isinstance(row['source'].get('observed_at'),(float,int)):reasons.append('insufficient_source_metadata')
            if reasons:proposals.append({'kind':'review','reasons':reasons,'memory_ids':[mid],'source_refs':[ref],'action':'review_only_preserve_originals'})
    if len(items)>200:raise ValueError('Bounded revision audit')
    current=[r for r in items if r['is_current'] and r['valid_now']]
    for i,a in enumerate(current):
        for b in current[i+1:]:
            if (a['type'],a['subject'],a['predicate'])!=(b['type'],b['subject'],b['predicate']):continue
            same=a['content_sha256']==b['content_sha256']
            # Bounded, linear heuristic; never infer equality from word overlap.
            left=set(re.findall(r'\w+',json.dumps(a['content'],sort_keys=True).lower())[:512])
            right=set(re.findall(r'\w+',json.dumps(b['content'],sort_keys=True).lower())[:512])
            score=2*len(left&right)/(len(left)+len(right)) if left or right else 0
            if not same and score<.75:continue
            provenance_same=all(a[k]==b[k] for k in ['source','observed','valid_from','valid_to','status'])
            pairs.append({'kind':'exact_duplicate_candidate' if same and provenance_same else 'similarity_candidate',
                          'similarity_metric':'token_dice_512','content_equal':same,'provenance_equal':provenance_same,'similarity':score,
                          'memory_ids':[a['memory_id'],b['memory_id']],'source_refs':list(dict.fromkeys([a['source']['ref'],b['source']['ref']])),
                          'action':'review_only_preserve_originals'})
    # Existing conflict markers are re-read canonically, not inferred from topic overlap.
    contradictions=[]
    for mid in ids:
        row=memory.db.execute('SELECT current_revision FROM mm_memories WHERE id=?',(mid,)).fetchone()
        current_row=next(r for r in items if r['id']==row[0])
        if current_row['effective_status']=='disputed':contradictions.append({'kind':'unresolved','memory_ids':[mid],'source_refs':[current_row['source']['ref']]})
        old=[r for r in items if r['memory_id']==mid and not r['is_current']]
        if old:contradictions.append({'kind':'replaced_history_not_unresolved_conflict','memory_ids':[mid],'source_refs':list(dict.fromkeys([r['source']['ref'] for r in old]+[current_row['source']['ref']]))})
    return {'schema':'memory_audit.v1','read_only':True,'validation':'deterministic_review_not_fact_promotion','items':items,
            'current_revision_ids':[r['id'] for r in current],'contradictions':contradictions,'duplicate_candidates':pairs,'proposals':proposals,
            'source_refs':list(dict.fromkeys(r['source']['ref'] for r in items)),'mutations_performed':0}


def hybrid_searcher(driver,embeddings):
    """Reuse the existing read-only hybrid lookup; never index/delete/repair here.
    Inject only a host-reviewed transport. Unavailable vectors use its FTS fallback.
    """
    from ..phase5.vector import search
    return lambda memory,principal,q,**filters:search(memory,principal,q,driver,embeddings,**filters)
