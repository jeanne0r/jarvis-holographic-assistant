"""Host-only receipts for authorized reads; no model-supplied provenance list."""
import json,time
from ..store import encode,uid
from ..phase2.bridge import Bridge
from ..phase2.memory_tools import MemoryTools
from ..phase6c.canonical_metadata import project

SCHEMA='''CREATE TABLE IF NOT EXISTS p6d_receipts(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES mm_missions(id),actor TEXT NOT NULL,tool_actor TEXT NOT NULL,tool TEXT NOT NULL,refs TEXT NOT NULL,created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS p6d_receipts_immutable_update BEFORE UPDATE ON p6d_receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
CREATE TRIGGER IF NOT EXISTS p6d_receipts_immutable_delete BEFORE DELETE ON p6d_receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;'''


class ObservedTools:
 def __init__(self,memory,host,caller,mission_id,*,searcher=None,sources=None):
    host.require('evidence_writer');host.require('mission_worker')
    Bridge(memory,host).get(mission_id);Bridge(memory,caller).get(mission_id)
    self.m,self.host,self.caller,self.mid=memory,host,caller,mission_id
    self.tools=MemoryTools(memory,caller,mission_id,searcher=searcher)
    # Real sources: host-side readers; each read is ingested as a citable measurement (sources/tools.py).
    from ..sources.tools import SourceTools,TOOLS as SOURCE_TOOLS
    self.source_names=set(SOURCE_TOOLS)
    self.sources=SourceTools(memory,caller.name,sources or {})
 def call(self,name,args):
    if name in self.source_names:result=self.sources.call(name,args)
    else:result=self.tools.call(name,args)
    if name not in self.source_names and name not in {'memory.search','memory.knowledge','memory.history','memory.project','memory.experiences','memory.contradictions','memory.audit'}:return result,None
    rows=result.get('items') if name=='memory.audit' else result
    if not isinstance(rows,list) or len(rows)>200:raise ValueError('Bounded read receipt required')
    refs=[]
    for row in rows:
        mid=row.get('memory_id');rid=row.get('revision_id',row.get('id'))
        if not mid or not rid:raise ValueError('Canonical returned IDs required')
        self.m._row(self.caller,mid)
        exists=self.m.db.execute('SELECT 1 FROM mm_revisions WHERE id=? AND memory_id=?',(rid,mid)).fetchone()
        if not exists:raise ValueError('Canonical revision mismatch')
        refs.append({'memory_id':mid,'revision_id':rid})
    receipt=uid()
    with self.m.db:self.m.db.execute('INSERT INTO p6d_receipts VALUES(?,?,?,?,?,?,?)',(receipt,self.mid,self.host.actor,self.caller.actor,name,encode(refs),time.time()))
    return result,receipt

def metadata(memory,principal,mission_id,receipt_ids):
 principal.require('reader');Bridge(memory,principal).get(mission_id)
 if not isinstance(receipt_ids,list) or not 1<=len(receipt_ids)<=20 or len(set(receipt_ids))!=len(receipt_ids):raise ValueError('Bounded receipts required')
 refs=[]
 for receipt_id in receipt_ids:
    row=memory.db.execute('SELECT * FROM p6d_receipts WHERE id=? AND mission_id=?',(receipt_id,mission_id)).fetchone()
    if not row:raise PermissionError('Receipt mission binding denied')
    refs+=json.loads(row['refs'])
 if not refs:raise ValueError('No retrieved references')
 mids=list(dict.fromkeys(r['memory_id'] for r in refs))
 principal.require('mission_worker')
 data=project(memory,principal,mission_id,mids)
 observed={(r['memory_id'],r['revision_id']) for r in refs}
 data['items']=[r for r in data['items'] if (r['memory_id'],r['revision_id']) in observed]
 data['selection_origin']='authenticated_host_tool_receipts'
 data['receipt_ids']=receipt_ids
 data['proof_limit']='authorized_tool_response_not_proof_of_correct_model_reasoning'
 return data
