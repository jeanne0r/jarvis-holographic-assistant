"""Prepared phase5 Windows trial: fresh canonical data, shared budget, real vector API.

prepare() is inert toward Windows. run() is invoked only by the explicitly
approved pilot lifecycle; it reuses phase4 Jobs, telemetry, tools and teardown.
"""
import json
import os
from pathlib import Path
import stat
import time
import uuid
from ..store import Memory,Principal
from ..phase2 import database as p2
from ..phase3 import lab
from ..phase4.native_trial import run as native_run
from . import database,vector,skills
from .api import extension
from .ssh_transport import CT205


def prepare(destination):
    folder=Path(destination).resolve();root=(lab.ROOT/'data/phase5').resolve()
    if not folder.is_relative_to(root) or folder==root:raise ValueError('New phase5 laboratory required')
    folder.mkdir(parents=True,mode=0o700,exist_ok=False)
    m=Memory(folder/'memory.sqlite',create=True)
    try:
        p2.migrate(m);database.migrate(m);ids=lab.seed(m)
        # Add explanatory synthetic text to the already corrected configuration.
        prior=m.history(lab.HOST,ids['configuration_memory_id'])[-1]
        m.ingest(lab.HOST,'semantic-description',{'kind':'user','ref':'synthetic://doselab/correction','observed_at':1700000300},[
            {'type':'knowledge','subject':'DoseLab X4','predicate':'load_cells','status':'user_confirmed',
             'content':{'capacities_kg':[1,1,1,1],'description':'Quatre cellules de pesée identiques, capacité un kilogramme chacune.'},
             'correction_of':ids['configuration_memory_id'],'expected_revision':prior['id']}])
        ids['current_revision']=m.history(lab.HOST,ids['configuration_memory_id'])[-1]['id']
    finally:m.close()
    manifest={'synthetic_only':True,'memory':ids,'runtime_started':False,
        'mission_1':'Analyse DoseLab X4 : recherche d’abord « masse nominale identique » via jarvis_memory_search, puis consulte l’historique. Explique la configuration actuelle et les anciennes valeurs remplacées, en citant les références synthetic://doselab/correction et synthetic://doselab/old. Utilise les outils réellement.',
        'mission_2':'Consulte l’expérience synthétique DoseLab X4 et propose une compétence candidate de diagnostic avec contrôle de fraîcheur et revue humaine. Aucune publication.'}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


def check_window(path,*,now=None):
    path=Path(path);info=path.lstat();now=time.time() if now is None else now
    if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_uid!=os.getuid():raise PermissionError('Owned private approval file required')
    value=json.loads(path.read_text())
    if value.get('closed') is not False or value.get('limits')!={'calls':16,'missions':3}:raise PermissionError('Explicit phase5 bounds required')
    start,end=value['started_at'],value['expires_at']
    if type(start) not in (int,float) or type(end) not in (int,float) or not 0<end-start<=1200 or not start<=now<end-90:raise PermissionError('Fresh 20-minute approval required')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    zone=ZoneInfo('Europe/Zurich')
    if datetime.fromtimestamp(start,zone).strftime('%Y-%m')!=datetime.fromtimestamp(end-1,zone).strftime('%Y-%m'):
        raise PermissionError('Do not cross the monthly accounting boundary')
    if any(type(value[k]) is not int or value[k]!=0 for k in ('calls','missions')):raise PermissionError('Never reuse an ambiguous earlier pilot')
    return value


def check_token_limit(limit):
    # Gate reserves the whole 64k context before each local dispatch. Never
    # replace that safety policy with an unverified tokenizer estimate.
    if type(limit) is not int or not 64000 <= limit <= 98304:
        raise PermissionError('64,000-token reservation requires a separately approved compatible shared quota (maximum 98,304)')
    return limit


def run(config,upstream,telemetry,*,folder,private_state,artifact,local_token_limit=50000):
    folder=Path(folder).resolve();root=(lab.ROOT/'data/phase5').resolve()
    if not folder.is_relative_to(root) or folder==root:raise PermissionError('Phase5 laboratory only')
    check_token_limit(local_token_limit)
    window=check_window(folder/'window.json')
    if window.get('local_token_limit',50000)!=local_token_limit:raise PermissionError('Token quota differs from approved window')
    queries=[]
    import threading
    local=threading.local()
    class TracedQdrant(vector.Qdrant):
        def hits(self,v,principal,artifact):
            hits=super().hits(v,principal,artifact)
            mm=Memory(folder/'memory.sqlite')
            try:
                rows={r['memory_id']:r for r in mm.current(principal)}
                queries.append({'query':getattr(local,'query',''),'at':time.time(),
                    'fts_count':len(mm.search(principal,getattr(local,'query',''))),
                    'canonical_references':[r['memory_id'] for r in hits if r.get('memory_id') in rows and rows[r['memory_id']]['id']==r.get('revision')]})
            finally:mm.close()
            return hits
    q=TracedQdrant(CT205('qdrant',private_state,identity='/home/user/.ssh/proxmox_codex',known_hosts='/home/user/.ssh/known_hosts'))
    base=vector.Embeddings(CT205('embedding',private_state,identity='/home/user/.ssh/proxmox_codex',known_hosts='/home/user/.ssh/known_hosts'),artifact)
    class Traced:
        artifact=base.artifact
        def __call__(self,text,*,kind='document',timeout=15):
            result=base(text,kind=kind,timeout=timeout)
            if kind=='query':local.query=text
            return result
    e=Traced();m=Memory(folder/'memory.sqlite')
    try:
        principal=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','indexer'}),'phase5-index-host')
        batches=[]
        for _ in range(20):
            batch=vector.index(m,principal,q,e,seconds=15);batches.append(batch)
            if batch['complete']:break
        else:raise TimeoutError('Initial synthetic index not complete')
    finally:m.close()
    retrieved=[]
    def observer(query,filters,rows):
        retrieved.append({'query':query,'type':filters.get('memory_type'),
                          'memory_ids':[r['memory_id'] for r in rows],
                          'sources':[r['source']['ref'] for r in rows]})
    result=native_run(config,upstream,telemetry,folder=folder,memory_extension=extension(q,e,observer=observer),
        local_token_limit=local_token_limit,shared_budget=True,skill_evaluator=skills.evaluate)
    result['phase5_index_batches']=batches;result['real_semantic_queries']=queries
    result['shared_token_limit']=local_token_limit
    result['retrieval_trace']=retrieved
    earlier={mid for mission in result.get('missions',[])[:-1] for mid in mission.get('experience_ids',[])}
    experience=any(row['type']=='episode' and earlier.intersection(row['memory_ids']) for row in retrieved)
    result['persisted_experience_returned']=experience
    if result.get('passed') and not experience:result['passed']=False
    configuration=json.loads((folder/'manifest.json').read_text())['memory']['configuration_memory_id']
    proven=any(r['fts_count']==0 and configuration in r['canonical_references'] for r in queries)
    result['semantic_without_fts_proven']=proven
    if result.get('passed') and not proven:result['passed']=False;result['missing_real_semantic_search']=True
    return result
