"""Opt-in private queue host. Reuses the existing Controller and authenticated API."""
import argparse,fcntl,hashlib,io,json,os,signal,subprocess,threading,time
from contextlib import closing
from pathlib import Path
from ..api import server
from ..store import Memory,Principal
from ..phase2.http_bridge import dispatch
from ..phase3.lab import OWNER
from ..phase3.model_gate import server as model_server
from .operational import Controller,extension as runtime_extension,options
from .demand_queue import Queue,migrate
PROVENANCE=('ha://','influx://','mission://','synthetic://doselab/')

class Demand:
    def __init__(self,path,cfg,*,clock=time.time,controller_factory=Controller,gate_factory=model_server,searcher=None,sources=None):
        self.path,self.cfg,self.clock=Path(path),cfg,clock
        self.profile=cfg['onDemand'];self.factory=controller_factory;self.gate_factory=gate_factory;self.searcher=searcher;self.sources=sources or {}
        if set(self.profile)!={'accepting','executionEnabled','schedulerToken','runtime','commissioned'} or self.profile['commissioned'] is not True or any(type(self.profile[k]) is not bool for k in ['accepting','executionEnabled']):raise PermissionError('Reviewed on-demand policy required')
        if cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False or cfg.get('missionLimits')!={'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}:raise PermissionError('Exact synthetic capabilities required')
        op=options(cfg)
        if op!={'admissionEnabled':self.profile['accepting'],'textEnabled':self.profile['accepting'],'workerEnabled':False,'voiceEnabled':False}:raise PermissionError('Queue acceptance separated from execution')
        runtime=self.profile['runtime']
        required={'hermesToken','modelToken','memoryToken','supervisorToken'}
        values=[cfg['bridgeToken'],self.profile['schedulerToken']]
        if self.profile['executionEnabled']:
            if not isinstance(runtime,dict) or set(runtime)!=required:raise PermissionError('Fixed runtime identities required')
            values+=list(runtime.values())
        elif runtime is not None:raise PermissionError('Queue-only profile has no runtime credentials')
        if any(not isinstance(v,str) or not 32<=len(v)<=256 for v in values) or len(set(values))!=len(values):raise PermissionError('Distinct service identities required')
        self.p=Principal(OWNER,frozenset({'private'}),frozenset({'reader','mission_writer','mission_worker','budget_admin','proposer','metered_caller','worker_supervisor','worker_reporter','evidence_writer'}),'operational-controller')
        self.lock=threading.RLock();self.controller=None;self.gate_server=None
        with closing(Memory(self.path)) as memory:
            from ..phase6d.database import migrate as migrate_base
            migrate_base(memory);migrate(memory)
            for table in ['mm_memories','mm_missions','mm_events']:
                if memory.db.execute("SELECT 1 FROM "+table+" WHERE owner!=? OR scope!='private' LIMIT 1",(OWNER,)).fetchone():raise PermissionError('Synthetic SQLite only')
            # Known provenance channels only: host-read measurements, mission reports, former lab records.
            if any(not json.loads(r[0]).get('ref','').startswith(PROVENANCE) for r in memory.db.execute('SELECT source FROM mm_events')):raise PermissionError('Unknown provenance channel')
            self.queue(memory).recover()
    def queue(self,memory):return Queue(memory,self.p,accepting=self.profile['accepting'],execution=self.profile['executionEnabled'],clock=self.clock)
    def close_gate(self):
        if self.controller:self.controller.gate=None
        if self.gate_server:self.gate_server.shutdown();self.gate_server.server_close();self.gate_server=None
    def reserve(self,memory,p,mid):
        with self.lock:
            lease=self.queue(memory).reserve(p,mid)
            try:
                runtime={**self.profile['runtime'],'expiresAt':lease['expires_at'],'maxMissions':1}
                cfg={**self.cfg,'operations':{'admissionEnabled':False,'textEnabled':False,'workerEnabled':True,'voiceEnabled':False,'runtime':runtime}}
                self.controller=self.factory(self.path,cfg,clock=self.clock,mission_id=mid,searcher=self.searcher,sources=self.sources)
                self.gate_server=self.gate_factory(self.controller,runtime['modelToken'],11436)
                threading.Thread(target=self.gate_server.serve_forever,daemon=True).start()
                return {**lease,'epoch':self.controller.epoch,'runtime_identity_sha256':{file:hashlib.sha256(runtime[key].encode()).hexdigest() for file,key in [('hermes.token','hermesToken'),('model.token','modelToken'),('memory.token','memoryToken')]}}
            except BaseException:
                self.close_gate();self.queue(memory).quarantine(mid);raise
    def step(self):
        with closing(Memory(self.path)) as memory:
            queue=self.queue(memory);queue.expire()
            if self.controller:
                if self.clock()>=self.controller.runtime['expiresAt']:
                    active=memory.db.execute('SELECT mission_id FROM p6q_jobs WHERE lease IS NOT NULL').fetchone()
                    if active:queue.quarantine(active[0])
                    self.close_gate();return
                try:self.controller.step()
                except Exception:
                    active=memory.db.execute('SELECT mission_id FROM p6q_jobs WHERE lease IS NOT NULL').fetchone()
                    if active:queue.quarantine(active[0])
                    self.close_gate()
    def handle(self,memory,p,request,url,query):
        with self.lock:
            queue=self.queue(memory);path,method=url.path,request.command
            def body():
                size=int(request.headers.get('Content-Length','0'))
                if request.headers.get('Transfer-Encoding') or not 0<size<=8000:raise ValueError('Bounded request')
                return json.loads(request.rfile.read(size))
            if path.startswith('/v1/queue/'):
                queue.supervisor(p)
                if query:raise ValueError('No query overrides')
                if path=='/v1/queue/next' and method=='GET':return 200,{'job':queue.peek(p)},'application/json'
                data=body() if method=='POST' else None
                if path=='/v1/queue/defer' and method=='POST' and set(data)=={'mission_id','reason'}:
                    queue.defer(p,data['mission_id'],data['reason']);return 200,{'deferred':True},'application/json'
                if path=='/v1/queue/reserve' and method=='POST' and set(data)=={'mission_id'}:return 200,self.reserve(memory,p,data['mission_id']),'application/json'
                if path=='/v1/queue/finish' and method=='POST' and set(data)=={'lease','cleanup_ok'}:
                    result=queue.finish(p,data['lease'],data['cleanup_ok'])
                    self.close_gate();self.controller=None
                    return 200,result,'application/json'
                raise PermissionError('Fixed scheduler operations only')
            if path=='/v1/workers/windows-hermes/status' and method=='GET':
                p.require('reader')
                if p.name!=OWNER or 'private' not in p.scopes:raise PermissionError('Owner/scope')
                status=queue.status();status.update(fresh=False,state='unknown',dispatch_allowed=False)
                if self.controller:status.update(self.controller.availability(memory))
                status['accepting']=self.profile['accepting'];return 200,status,'application/json'
            if p.actor in {'operational-supervisor','hermes-memory'}:
                if not self.controller:raise PermissionError('No active execution')
                return runtime_extension(self.controller,self.controller.flags)(memory,p,request,url,query)
            if p.actor!='interactive-panel':raise PermissionError('Panel or exact runtime identity required')
            if path=='/v1/missions' and method=='POST':return 202,queue.admit(p,request.headers.get('Idempotency-Key'),body()),'application/json'
            # Read/cancel and host-revalidated canonical receipts use the existing paths.
            if '/approvals' in path or path.endswith('/result'):raise PermissionError('No promotion or approval')
            if self.controller:return runtime_extension(self.controller,{'admissionEnabled':False})(memory,p,request,url,query)
            if path.endswith('/canonical'):
                from ..phase6d.evidence import metadata
                mid=path.split('/')[3]
                from ..phase2.bridge import Bridge
                Bridge(memory,p).get(mid)
                ids=[r[0] for r in memory.db.execute('SELECT id FROM p6d_receipts WHERE mission_id=? ORDER BY created DESC LIMIT 20',(mid,))]
                if not ids:return 403,{'error':'No authorized receipts'},'application/json'
                return 200,{'projection':metadata(memory,self.p,mid,ids),'validation':'unreviewed'},'application/json'
            if path=='/v1/health' and method=='GET':return 200,{'ready':True,'synthetic_only':False,'real_sources':sorted(self.sources),'dispatch_enabled':False},'application/json'
            return dispatch(memory,p,request,url,query)

def run(config):
    path=Path(config);st=path.lstat();folder=path.parent
    if path.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077:raise PermissionError('Private config')
    cfg=json.loads(path.read_text());db=folder/'memory.sqlite'
    if folder.stat().st_mode&0o077 or db.is_symlink() or db.stat().st_uid!=os.getuid() or db.stat().st_mode&0o077:raise PermissionError('Private synthetic state')
    if cfg['origin']!='http://127.0.0.1:'+str(cfg['frontPort']) or cfg['frontPort']==cfg['bridgePort'] or any(type(cfg[k]) is not int or not 1024<=cfg[k]<=65535 for k in ['frontPort','bridgePort']):raise PermissionError('Existing loopback topology')
    lock=os.open(folder/'worker.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Real sources (sources.json next to the config, 0600, owned by this service): optional.
    from ..sources.readers import load as load_sources
    src=folder/'sources.json';sources={}
    if src.exists():
        st=src.lstat()
        if src.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077:raise PermissionError('Private sources config')
        sources=load_sources(json.loads(src.read_text()))
    engine=Demand(db,cfg,sources=sources)
    clients={hashlib.sha256(cfg['bridgeToken'].encode()).hexdigest():{'name':OWNER,'scopes':['private'],'roles':['reader','mission_writer'],'actor_id':'interactive-panel'},
             hashlib.sha256(cfg['onDemand']['schedulerToken'].encode()).hexdigest():{'name':OWNER,'scopes':['private'],'roles':['queue_supervisor'],'actor_id':'on-demand-supervisor'}}
    if engine.profile['executionEnabled']:
        for key,roles,actor in [('memoryToken',['reader'],'hermes-memory'),('supervisorToken',['worker_reporter'],'operational-supervisor')]:
            clients[hashlib.sha256(engine.profile['runtime'][key].encode()).hexdigest()]={'name':OWNER,'scopes':['private'],'roles':roles,'actor_id':actor}
    http=server(db,clients,cfg['bridgePort'],extension=engine.handle)
    threading.Thread(target=http.serve_forever,daemon=True).start();stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    root=Path(__file__).resolve().parents[2]
    child=subprocess.Popen(['node',str(root/'ops/pilot-embedded.mjs'),str(path.resolve())],cwd=root,env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(folder/'empty-home')})
    try:
        while not stop.wait(.25):
            if child.poll() is not None:raise RuntimeError('Private panel stopped')
            engine.step()
    finally:
        # Closing a host process never authorizes a replay. Native Job Objects retain deadlines.
        with closing(Memory(db)) as memory:engine.queue(memory).recover()
        engine.close_gate()
        if child.poll() is None:child.terminate();child.wait(timeout=10)
        http.shutdown();http.server_close();os.close(lock)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
