"""Test-only HTTP/SQLite fixture. No Hermes, provider, production paths or tools."""
import hashlib,json,os,sys,threading
from pathlib import Path
from ..store import Memory,Principal
from ..phase2 import database
from ..api import server
from ..phase2.http_bridge import dispatch
from ..phase2.bridge import Bridge
from .worker import tick


def main():
    if sys.argv[1:]!=['--synthetic-only']:raise SystemExit('Explicit synthetic fixture flag required')
    root=Path(os.environ['PHASE6_FIXTURE_DIR']);path=root/'memory.sqlite'
    m=Memory(path,create=not path.exists());database.migrate(m);m.close()
    clients={}
    for suffix,roles,actor in [('WRITER',['reader','mission_writer'],'jarvis-server'),('HUMAN',['reader','human_approver'],'separate-human')]:
        token=os.environ['PHASE6_'+suffix]
        clients[hashlib.sha256(token.encode()).hexdigest()]={'name':'synthetic-owner','scopes':['private'],'roles':roles,'actor_id':actor}
    api=server(path,clients,0,extension=dispatch)
    threading.Thread(target=api.serve_forever,daemon=True).start()
    print(json.dumps({'port':api.server_address[1]}),flush=True)
    worker=Principal('synthetic-owner',frozenset({'private'}),frozenset({'reader','mission_writer','mission_worker','proposer'}),'fixture-worker')
    class FakeHermes:
        def create(self,*_):return {'run_id':'synthetic-fake-runtime'}
        def status(self,*_):return {'status':'completed','output':'Quatre cellules identiques de 1 kg. source.ref=synthetic://doselab/correction ; ancienne configuration remplacée : synthetic://doselab/old.','usage':{'total_tokens':0}}
    for line in sys.stdin:
        cmd=json.loads(line)
        with_memory=Memory(path);b=Bridge(with_memory,worker)
        try:
            if cmd['action']=='finish':
                mid=cmd['mission_id']
                telemetry=lambda:{'available':True,'observed_at':__import__('time').time(),'free_mib':9200,'utilization':0,'miner_running':False}
                for _ in range(3):tick(with_memory,worker,mid,FakeHermes(),telemetry,endpoint_ready=True,approved=True)
                result={'state':b.get(mid)['state'],'experiences':with_memory.db.execute("SELECT count(*) FROM mm_revisions WHERE type='episode' AND status='inferred'").fetchone()[0]}
            elif cmd['action']=='approval':
                a=b.request_approval(cmd['mission_id'],{'request_id':'synthetic-report-only','description':'Synthetic nonphysical review'},worker.actor)
                result={k:a[k] for k in ('id','fingerprint')}
            else:raise ValueError('Fixture command denied')
            print(json.dumps(result),flush=True)
        finally:with_memory.close()
    api.shutdown();api.server_close()

if __name__=='__main__':main()
