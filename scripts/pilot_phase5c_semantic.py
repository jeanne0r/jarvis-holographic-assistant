"""PREPARED ONLY. Requires separate C1 approval and reviewed Windows patch first."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import time
import uuid
from scripts import pilot_phase4_windows as lifecycle
from scripts.pilot_phase5_windows import read_only_preflight
from memory_manager.phase3 import lab
from memory_manager.phase4.native_trial import run as native_run
from memory_manager.phase5 import native_lab, vector
from memory_manager.phase5.ssh_transport import CT205
from memory_manager.phase5c import semantic
from memory_manager.store import Memory, Principal

PATCH_FILES=('memory_manager/mcp_utf8.py','memory_manager/phase2/mcp.py',
             'memory_manager/phase2/memory_tools.py','memory_manager/phase3/mcp.py',
             'memory_manager/phase4/windows.py')


def execute(config,upstream,telemetry,*,folder,private_state,artifact):
    principal=Principal(lab.OWNER,frozenset({'private'}),lab.HOST.roles|{'indexer'})
    transport=lambda service:CT205(service,private_state,identity='/home/user/.ssh/proxmox_codex',known_hosts='/home/user/.ssh/known_hosts')
    q=vector.Qdrant(transport('qdrant'));e=vector.Embeddings(transport('embedding'),artifact)
    m=Memory(folder/'memory.sqlite')
    try:
        if m.search(principal,semantic.QUERY,memory_type='knowledge'):
            raise ValueError('Fixed query overlaps FTS; stop before inference')
        for _ in range(10):
            if vector.index(m,principal,q,e,seconds=15)['complete']:break
        else:raise TimeoutError('Synthetic index unfinished')
    finally:m.close()
    traces=[];history_traces=[]
    def searcher(memory,actor,query,**filters):
        if filters.get('memory_type')=='knowledge':
            # One active mission; binding comes from canonical server state, not tool arguments.
            ids=[r[0] for r in memory.db.execute("SELECT id FROM mm_missions WHERE state='running'")]
            if len(ids)!=1:raise PermissionError('One host-bound active mission required')
            rows,trace=semantic.observe(memory,actor,query,q,e,mission_id=ids[0]);traces.append(trace);return rows
        return vector.search(memory,actor,query,q,e,**filters)
    from memory_manager.phase2.http_bridge import dispatch
    def api(memory,actor,request,url,query):
        if request.command=='GET' and url.path=='/v1/history':
            ids=[r[0] for r in memory.db.execute("SELECT id FROM mm_missions WHERE state='running'")]
            if len(ids)!=1:raise PermissionError('One host-bound active mission required')
            trace={'mission_id':ids[0],'memory_id':query.get('memory_id'),'accepted':False}
            history_traces.append(trace)
            # Same canonical reader and ACL as the normal route; never resolve
            # a source URI or revision as a substitute stable memory identifier.
            rows=memory.history(actor,query['memory_id'])
            trace.update(accepted=True,sources=[r['source']['ref'] for r in rows])
            return 200,{'items':rows},'application/json'
        return dispatch(memory,actor,request,url,query,searcher=searcher)
    result=native_run(config,upstream,telemetry,folder=folder,memory_extension=api,
                      local_token_limit=98304,shared_budget=True,mission_numbers=(1,),
                      required_search_tool='jarvis_memory_knowledge')
    manifest=json.loads((folder/'manifest.json').read_text());missions=result.get('missions',[])
    passed=False;history_verified=False
    if len(missions)==1:
        mission=missions[0]
        passed=any(semantic.verify(t,mission_id=mission['mission_id'],native_status=mission.get('native_status',{}).get('status'),
            successful_tools=mission.get('successful_native_tools',[]),output=mission.get('native_status',{}).get('output',''),
            expected_id=manifest['memory']['configuration_memory_id'],expected_revision=manifest['memory']['current_revision'],
            expected_source='synthetic://doselab/correction') for t in traces)
        history_verified=any(t['mission_id']==mission['mission_id'] and t['accepted']
            and t['memory_id']==manifest['memory']['configuration_memory_id']
            and {'synthetic://doselab/correction','synthetic://doselab/old'}<=set(t.get('sources',[]))
            for t in history_traces)
    result.update(semantic_traces=traces,history_traces=history_traces,
                  strict_semantic_verified=passed,stable_history_id_verified=history_verified)
    result['passed']=bool(result.get('passed') and passed and history_verified)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--approved-c1',action='store_true',required=True)
    p.add_argument('--private-state',required=True);p.add_argument('--artifact',required=True)
    args=p.parse_args();checks=read_only_preflight()
    root=Path(__file__).resolve().parents[1]
    expected={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in PATCH_FILES}
    # Hash fixed application files only. No private content, credentials or arbitrary path selection.
    remote_paths={name:str(PureWindowsPath('C:/JarvisHermesLab/app')/name) for name in PATCH_FILES}
    paths=','.join("'"+path+"'" for path in remote_paths.values())
    actual=lifecycle.probe("$out=@{};foreach($p in @("+paths+")){$out[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()};$out|ConvertTo-Json -Compress")
    for name,digest in expected.items():
        path=remote_paths[name]
        if actual.get(path)!=digest:raise PermissionError('Reviewed C1 Windows patch missing or different; never install implicitly')
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    folder=root/'data/phase5'/('phase5c-'+ident);manifest=native_lab.prepare(folder)
    manifest['mission_1']=semantic.OBJECTIVE+' Consulte aussi jarvis_memory_history et cite la source antérieure synthetic://doselab/old.'
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (folder/'preflight.json').write_text(json.dumps({'windows':checks,'patch_sha256':expected},indent=2)+'\n')
    window=folder/'window.json';now=time.time()
    value={'started_at':now,'expires_at':now+300,'closed':False,'calls':0,'missions':0,'limits':{'calls':6,'missions':1},'local_token_limit':98304}
    with os.fdopen(os.open(window,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(value,f)
    argv=sys.argv
    try:
        sys.argv=['phase5c','--approved','--output','docs/JARVIS_2_PHASE5C_SEMANTIC_REAL_'+ident+'.json']
        lifecycle.main(run_native=lambda c,u,t:execute(c,u,t,folder=folder,private_state=args.private_state,artifact=args.artifact),approval_path=window)
    finally:
        sys.argv=argv;value=json.loads(window.read_text());value['closed']=True
        with window.open('w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())


if __name__=='__main__':main()
