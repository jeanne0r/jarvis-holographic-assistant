"""One authorized synthetic mission, SQLite read-only; private local export only.
No configuration/credentials, network, subprocess, service or model access.
"""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,pwd,sqlite3,stat
from pathlib import Path

SRC=Path('/home/user/workspace/jarvis-2-memory')
STATE=Path('/var/lib/jarvis-hermes-pilot')
WINDOW='20261115T214641Z-0f2a81f1'
MISSION='a573c225-1879-4458-9ca0-89407cb2cc5f'
OWNER='phase3-synthetic'
FOLDER=SRC/'data/operational'/('window-'+WINDOW)

def collect(db):
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    mission=db.execute('SELECT id,owner,scope,state,definition FROM mm_missions WHERE id=?',(MISSION,)).fetchone()
    if not mission or mission['owner']!=OWNER or mission['scope']!='private' or mission['state']!='completed':raise PermissionError('Exact completed synthetic mission required')
    terminal=db.execute("SELECT data FROM p2_events WHERE mission_id=? AND event_key='terminal'",(MISSION,)).fetchone()
    if not terminal:raise PermissionError('Terminal event missing')
    terminal=json.loads(terminal['data'])
    if terminal.get('output_withheld'):raise PermissionError('Sensitive output remains withheld')
    output=terminal.get('output','')
    # Preserve the recorded text exactly. No repair or citation insertion.
    fragments=db.execute("SELECT kind,data FROM p2_events WHERE mission_id=? AND kind IN ('result_part','result_complete','output_limit') ORDER BY seq",(MISSION,)).fetchall()
    receipt_rows=db.execute('SELECT id,actor,tool_actor,tool,refs,created FROM p6d_receipts WHERE mission_id=? ORDER BY created,id LIMIT 201',(MISSION,)).fetchall()
    if not 1<=len(receipt_rows)<=200:raise PermissionError('Bounded receipts required')
    receipts=[];revision_rows={}
    for row in receipt_rows:
        receipt=dict(row);receipt['refs']=json.loads(receipt['refs']);receipts.append(receipt)
        if not isinstance(receipt['refs'],list) or len(receipt['refs'])>200:raise PermissionError('Receipt bound')
        for ref in receipt['refs']:
            key=(ref['memory_id'],ref['revision_id'])
            if key in revision_rows:continue
            revision=db.execute('SELECT r.*,m.owner,m.scope,e.source FROM mm_revisions r JOIN mm_memories m ON m.id=r.memory_id JOIN mm_events e ON e.id=r.event_id WHERE r.id=? AND r.memory_id=?',(key[1],key[0])).fetchone()
            if not revision or revision['owner']!=OWNER or revision['scope']!='private':raise PermissionError('Non-synthetic receipt target')
            value=dict(revision);value['source']=json.loads(value['source']);value['content']=json.loads(value['content'])
            source=value['source'].get('ref','')
            if not source.startswith(('synthetic://doselab/','mission://')):raise PermissionError('Unexpected provenance')
            revision_rows[key]=value
    payload=db.execute('SELECT payload FROM p2_outbox WHERE mission_id=?',(MISSION,)).fetchone()
    return {'window_id':WINDOW,'mission_id':MISSION,'mission':dict(mission),'host_payload':json.loads(payload['payload']) if payload else None,
            'terminal':terminal,'terminal_output_sha256':hashlib.sha256(output.encode()).hexdigest(),
            'result_fragments':[{'kind':r['kind'],'data':json.loads(r['data'])} for r in fragments],
            'receipts':receipts,'receipt_revisions':list(revision_rows.values()),
            'limits_of_evidence':'Receipt IDs attest authorized returned revisions; tool arguments and full model request messages are not stored in this ledger. Revision rows are not a captured MCP wire transcript.'}

def private_regular(path,uid):
    for p in [path,*path.parents]:
        if p.is_symlink():raise PermissionError('Symlink refused')
    st=path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or st.st_mode&0o077:raise PermissionError('Private owned regular file required')

def main():
    p=argparse.ArgumentParser();p.add_argument('--read-only',action='store_true',required=True);p.parse_args()
    if os.geteuid()!=0:raise PermissionError('Administrator terminal required')
    os.umask(0o077)
    app=pwd.getpwnam('jarvis-pilot');operator=pwd.getpwnam('user')
    private_regular(STATE/'memory.sqlite',app.pw_uid)
    originals=[FOLDER/'result.json',SRC/'docs'/('HERMES_OPERATIONAL_WINDOW_'+WINDOW+'.json')]
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    before=hashes()
    with sqlite3.connect('file:'+str(STATE/'memory.sqlite')+'?mode=ro',uri=True) as db:data=collect(db)
    if before!=hashes():raise PermissionError('Historical evidence changed concurrently')
    data['historical_sha256']=before;data['historical_passed']=json.loads((FOLDER/'result.json').read_bytes())['passed']
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    if len(raw)>1024*1024:raise ValueError('Export bound exceeded')
    folder=FOLDER.stat()
    if FOLDER.is_symlink() or folder.st_uid!=operator.pw_uid or folder.st_mode&0o077:raise PermissionError('Private operator directory required')
    target=FOLDER/'citation-evidence.json'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as file:
        os.fchown(file.fileno(),operator.pw_uid,operator.pw_gid);file.write(raw);file.flush();os.fsync(file.fileno())
    print(json.dumps({'passed':True,'sqlite_read_only':True,'historical_evidence_unchanged':True,'export':str(target),'sha256':hashlib.sha256(raw).hexdigest(),'receipts':len(data['receipts']),'revisions':len(data['receipt_revisions']),'service_operations':0,'model_calls':0,'private_content_printed':False}))

if __name__=='__main__':main()
