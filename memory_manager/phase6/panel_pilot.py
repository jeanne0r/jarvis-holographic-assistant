"""Approved P6-L1/P6-L2 controller: one real UI admission, existing Windows lifecycle and guards.

Only L2 enables /ask delegation. No Qdrant operation, personal data or production mutation.
"""
import hashlib,json,os,queue,secrets,shutil,subprocess,threading,time,urllib.request
from pathlib import Path
from ..store import Memory,Principal
from ..api import server as memory_server
from ..phase2 import database,budgets
from ..phase2.http_bridge import dispatch
from ..phase2.bridge import Bridge
from ..phase2.hermes import HermesRuns
from ..phase2.local_model import PrivateHTTP
from ..phase3 import lab
from ..phase3.model_gate import Gate,server as model_server
from ..phase4.allowance import consume
from ..phase4.native_trial import Runtime,IDENTITY,validate_advertised_tools,events_from_sse
from ..phase4.windows import tunnel as private_tunnel
from .worker import tick
ROOT=lab.ROOT

def private_json(path,data):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(data,f,ensure_ascii=False,indent=2)

def prepare(folder):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(ROOT/'data/phase6') or folder.exists():raise PermissionError('Fresh isolated phase6 folder required')
    folder.mkdir(parents=True,mode=0o700)
    manifest=json.loads((ROOT/'docs/phase6b/patch-manifest.json').read_text());seen=set()
    for stage in manifest['stages']:
        if hashlib.sha256((ROOT/'docs/phase6b'/ (stage['stage']+'.patch')).read_bytes()).hexdigest()!=stage['patch_sha256']:raise PermissionError('Patch integrity')
        for row in stage['files']:
            p=Path(row['target'])
            if str(p) not in seen:
                if (hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None)!=row['before_sha256']:raise PermissionError('Production preimage differs')
                seen.add(str(p))
    code=folder/'copy/server';public=folder/'copy/public';code.mkdir(parents=True);public.mkdir()
    for p in [*Path('/home/user/workspace/jarvis').glob('*.mjs'),*Path('/home/user/workspace/jarvis').glob('*.py')]:shutil.copyfile(p,code/p.name)
    for p in Path('/home/user/gateway/public/jarvis').iterdir():
        if p.is_file() and p.suffix in {'.js','.css','.html','.svg'}:shutil.copyfile(p,public/p.name)
    for stage in manifest['stages']:
        for row in stage['files']:
            p=Path(row['target']);target=None;source=None
            if p.parent==Path('/home/user/workspace/jarvis'):target=code/p.name;source=ROOT/p.name
            elif p.parent==Path('/home/user/gateway/public/jarvis'):target=public/p.name;source=ROOT/'public'/p.name
            if target:
                # Stage 01 phase6-gateway has an intermediate hash; final source
                # is checked against the final occurrence after all stages.
                shutil.copyfile(source,target)
    final={row['target']:row for stage in manifest['stages'] for row in stage['files']}
    hashes={}
    for path,row in final.items():
        p=Path(path);target=code/p.name if p.parent==Path('/home/user/workspace/jarvis') else public/p.name
        if p.name=='server.js':continue # production gateway is never executed
        h=hashlib.sha256(target.read_bytes()).hexdigest()
        if h!=row['after_sha256']:raise PermissionError('Staged source differs from approved patch')
        hashes[str(target.relative_to(folder))]=h
    (code/'data').mkdir();private_json(code/'data/core-engine.json',{'engine':'hybrid'})
    m=Memory(folder/'memory.sqlite',create=True)
    try:database.migrate(m);ids=lab.seed(m)
    finally:m.close()
    private_json(folder/'preparation.json',{'synthetic_only':True,'patch_source_hashes':hashes,'memory_ids':ids,'active_gateway_used':False})
    return ids


def execute(config,upstream,telemetry,*,folder,credentials_dir=None,pilot="P6-L1"):
    if pilot not in {'P6-L1','P6-L2'}:raise PermissionError('Explicit pilot profile required')
    folder=Path(folder);window=folder/'window.json';deadline=json.loads(window.read_text())['expires_at']
    credentials=Path(credentials_dir) if credentials_dir else ROOT/'data/phase3/windows-20261114'
    token=lambda name:(credentials/name).read_text().strip()
    operator=secrets.token_urlsafe(32);writer=secrets.token_urlsafe(32)
    private_json(folder/'bridge-private.json',{'token':writer})
    private_json(folder/'panel-private.json',{'pilot':pilot,'syntheticOnly':True,'humanToken':operator,'expiresAt':deadline})
    principal=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','proposer','mission_writer','mission_worker','budget_admin','metered_caller'}),pilot.lower()+'-controller')
    clients={hashlib.sha256(writer.encode()).hexdigest():{'name':lab.OWNER,'scopes':['private'],'roles':['reader','mission_writer'],'actor_id':pilot.lower()+'-jarvis'},
        hashlib.sha256(token('memory.token').encode()).hexdigest():{'name':lab.OWNER,'scopes':['private'],'roles':['reader'],'actor_id':pilot.lower()+'-runtime'}}
    report={'pilot':pilot,'synthetic_only':True,'provider':'real-ollama-rtx','runtime':'real-windows-hermes','model_requests':[],'memory_reads':[],'production_writes':0,'remote_cost_chf':0,'ask_calls':None}
    active=[None];mid=None;servers=[];tunnel=None;panel=None;owner=Runtime();messages=queue.Queue();last=None
    class Relay:
        cfg=config
        def call(self,body):
            consume(window,'calls')
            row={'at':time.time(),'tools':[t.get('function',{}).get('name') for t in body.get('tools',[])]};report['model_requests'].append(row)
            validate_advertised_tools(body,skill_mode=False)
            if time.time()>=deadline-15 or active[0] is None:raise PermissionError('Outside active P6-L1 mission')
            try:
                result=active[0].call(body);row['usage']=result['usage'];row['finish_reason']=result['choices'][0]['finish_reason'];return result
            except Exception as e:row['error_class']=type(e).__name__;raise
    def extension(memory,actor,req,url,query):
        if url.path=='/v1/missions' and req.command=='POST':consume(window,'missions')
        if req.command=='GET' and url.path in {'/v1/search','/v1/history'}:
            report['memory_reads'].append({'path':url.path,'memory_id':query.get('memory_id'),'query':query.get('q'),'actor':actor.actor})
        return dispatch(memory,actor,req,url,query)
    try:
        servers=[memory_server(folder/'memory.sqlite',clients,8792,extension=extension),model_server(Relay(),token('model.token'),11436)]
        for s in servers:threading.Thread(target=s.serve_forever,daemon=True).start()
        tunnel=subprocess.Popen(private_tunnel(key=IDENTITY/'id_ed25519',known_hosts=IDENTITY/'known_hosts'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(1)
        if tunnel.poll() is not None:raise RuntimeError('Pinned laboratory tunnel failed')
        native=PrivateHTTP('http://127.0.0.1:8643',token('hermes.token'));client=HermesRuns(native,config.model,allow_live=True)
        tags=upstream('GET','/api/tags')['models']
        if not any(t.get('name')==config.model and t.get('digest')==config.digest and not t.get('remote_host') and not t.get('remote_model') for t in tags):raise PermissionError('Pinned local model missing')
        report['installed_model_verified']=True
        owner.start(False)
        while time.time()<deadline-90:
            if owner.process.poll() is not None:raise RuntimeError('Owned Hermes startup exited')
            try:native('GET','/v1/models',timeout=2);break
            except Exception:time.sleep(1)
        else:raise TimeoutError('Hermes not ready in remaining allowance')
        env={'PATH':os.environ['PATH'],'HOME':str(folder/'empty-home'),'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
        stderr=(folder/'panel-stderr.log').open('wb')
        if pilot=='P6-L2':env['P6L2_LAB_COPY']=str(folder/'copy/server')
        command=['node']+(['--experimental-loader',str(ROOT/'ops/phase6b-hybrid-lab-loader.mjs')] if pilot=='P6-L2' else [])+[str(ROOT/'ops/phase6b-panel-lab.mjs'),str(folder)]
        panel=subprocess.Popen(command,env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=stderr,text=True)
        def read_panel():
            for line in panel.stdout:
                try:messages.put(json.loads(line))
                except Exception:messages.put({'event':'unparsed-panel-output'})
        threading.Thread(target=read_panel,daemon=True).start()
        while time.time()<deadline-20:
            try:
                while True:
                    message=messages.get_nowait()
                    if message['event']=='panel-admitted':
                        if mid is not None:raise PermissionError('Second panel admission forbidden')
                        if message['status']!=202 or message['state']!='queued':raise ValueError('Async admission failed')
                        mid=message['mission_id'];report['panel_admission']=message
                        memory=Memory(folder/'memory.sqlite')
                        try:
                            account=budgets.create(memory,principal,token_limit=98304)
                            active[0]=Gate(memory,principal,account,mid,config,upstream,telemetry,max_calls=6,seconds=min(180,deadline-time.time()-20))
                        finally:memory.close()
                    elif message['event']=='panel-result':report['panel']=message
                    elif message['event']=='panel-error':
                        report['panel_diagnostics']={'stage':message.get('stage'),'requests':message.get('requests',[])}
                        raise RuntimeError('Panel browser failed at '+message.get('stage','unknown')+': '+message.get('error_class','unknown'))
            except queue.Empty:pass
            if mid:
                memory=Memory(folder/'memory.sqlite')
                try:
                    last=tick(memory,principal,mid,client,telemetry,endpoint_ready=True,approved=True)
                    if last['state'] in {'completed','failed','cancelled','paused','awaiting_approval'}:
                        report['mission']=last;report['events']=Bridge(memory,principal).events(mid)
                        if last['upstream_id']:
                            report['native_status']=client.status(last['upstream_id'])
                            if 'native_events' not in report:
                                request=urllib.request.Request('http://127.0.0.1:8643/v1/runs/'+last['upstream_id']+'/events',headers={'Authorization':'Bearer '+token('hermes.token')})
                                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:
                                    report['native_events']=events_from_sse(response.read(256000).decode('utf-8'))
                        report['usage']=[dict(r) for r in memory.db.execute('SELECT * FROM p2_usage WHERE mission_id=?',(mid,))]
                        report['experiences']=[r['memory_id'] for r in memory.current(principal) if r['type']=='episode' and r['source']['ref'].startswith('mission://')]
                        if panel.poll() is not None:break
                finally:memory.close()
            if panel.poll() is not None:
                time.sleep(.1)
                try:
                    while True:
                        msg=messages.get_nowait()
                        if msg.get('event')=='panel-result':report['panel']=msg
                        elif msg.get('event')=='panel-error':report['panel_error']=msg.get('error_class')
                except queue.Empty:pass
                break
            time.sleep(.25)
        else:raise TimeoutError('P6-L1 safety cutoff')
        p=report.get('panel',{});native_output=report.get('native_status',{}).get('output','')
        report['ask_calls']=p.get('ask_requests')
        report['checks']={'no_ask_delegation':p.get('ask_requests')==0,'one_panel_admission':mid is not None and len(p.get('admissions',[]))==1,'runtime_completed':report.get('mission',{}).get('state')=='completed','current_source_visible':p.get('source_current_visible') is True,'old_source_visible':p.get('source_old_visible') is True,'result_matches_runtime':bool(native_output) and native_output in p.get('output',''),'experience_persisted':bool(report.get('experiences')),'no_automatic_approval':p.get('no_model_approval_button') is True,'model_actually_called':len(report['model_requests'])>0,'quota_respected':len(report['model_requests'])<=6 and sum(r.get('usage',{}).get('total_tokens',0) for r in report['model_requests'])<=98304}
        if pilot=='P6-L2':
            report['checks'].pop('no_ask_delegation')
            report['checks'].pop('one_panel_admission')
            report['checks']['one_hybrid_admission']=mid is not None and len(p.get('admissions',[]))==1 and p.get('ask_requests',0)>0
            report['checks']['no_direct_panel_creation']=p.get('direct_mission_posts')==0
            report['checks']['hybrid_security_and_routing']=bool(p.get('hybrid',{}).get('checks')) and all(p['hybrid']['checks'].values())
        report['passed']=all(report['checks'].values())
    except Exception as e:report.update(passed=False,error_class=type(e).__name__,error=str(e)[:240])
    finally:
        active[0]=None
        if mid:
            memory=Memory(folder/'memory.sqlite')
            try:
                b=Bridge(memory,principal);state=b.get(mid)
                if state['state'] not in {'completed','failed','cancelled'}:
                    b.cancel(mid)
                    if state['upstream_id']:
                        try:client.stop(state['upstream_id'])
                        except Exception:report['native_stop_uncertain']=True
            finally:memory.close()
        try:owner.stop();report['runtime_supervisors']=owner.reports
        except Exception as e:report.update(passed=False,runtime_cleanup_error=type(e).__name__)
        if panel:
            if panel.poll() is None:panel.terminate()
            try:panel.wait(timeout=10)
            except subprocess.TimeoutExpired:panel.kill();panel.wait();report['panel_forced_stop']=True
            panel.stdout.close();stderr.close()
        if (folder/'switch.json').exists():(folder/'switch.json').write_text('{"enabled":false}')
        if tunnel:tunnel.terminate();tunnel.wait(timeout=10)
        for s in servers:s.shutdown();s.server_close()
        report['panel_stopped']=panel is None or panel.poll() is not None
        report['tunnel_stopped']=tunnel is None or tunnel.poll() is not None
    private_json(folder/'trial-result.json',report)
    return report
