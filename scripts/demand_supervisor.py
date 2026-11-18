"""Fixed, non-root supervisor of the existing lifecycle; no model-provided commands."""
import argparse,hashlib,json,os,subprocess,time,uuid,base64,re,socket
from pathlib import Path
from memory_manager.phase2.local_model import PrivateHTTP
from scripts.egress_selftest import verify as verify_egress
CONFIG_MAX_BYTES=128*1024

class Supervisor:
    def __init__(self,transport,preflight,lifecycle,*,clock=time.time):
        self.http,self.preflight,self.lifecycle,self.clock=transport,preflight,lifecycle,clock
        self.next_check=0;self.stage='start';self.preflight_error=None
    def tick(self):
        if self.clock()<self.next_check:return {'state':'cooldown'}
        self.next_check=self.clock()+30
        self.stage='next';job=self.http('GET','/v1/queue/next').get('job')
        if not job:return {'state':'idle'}
        mid=job['mission_id']
        self.stage='preflight';self.preflight_error=None
        try:reason=self.preflight()
        except Exception as e:reason='preflight_failed';self.preflight_error=type(e).__name__+': '+str(e)[:160]
        if reason is not None:
            self.stage='defer';self.http('POST','/v1/queue/defer',{'mission_id':mid,'reason':reason})
            return {'state':'waiting','reason':reason,'mission_id':mid,**({'preflight_error':self.preflight_error} if self.preflight_error else {})}
        self.stage='reserve';lease=self.http('POST','/v1/queue/reserve',{'mission_id':mid})
        self.stage='lifecycle'
        # No retry once the server has reserved a lease. Lost replies require review.
        cleanup=False
        try:
            result=self.lifecycle(lease)
            cleanup=result.get('cleanup_verified') is True
            return {'state':'finished' if cleanup else 'uncertain'}
        finally:self.stage='finish';self.http('POST','/v1/queue/finish',{'lease':lease['lease'],'cleanup_ok':cleanup})

def private_json(path,*,max_bytes=16384):
    if type(max_bytes) is not int or not 1<=max_bytes<=CONFIG_MAX_BYTES:raise ValueError('Bounded private JSON limit')
    p=Path(path);st=p.lstat()
    if p.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_size>max_bytes:raise PermissionError('Private owned supervisor config')
    return json.loads(p.read_text())

def runtime_identity_check(expected,*,ssh=None,probe=None):
    if set(expected)!={'hermes.token','model.token','memory.token'} or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in expected.values()):raise PermissionError('Pinned identity digests required')
    if ssh is None:
        from memory_manager.phase4.native_trial import ssh_script
        ssh=ssh_script
    if probe is None:
        from scripts.pilot_phase4_windows import probe
    loader=probe("[pscustomobject]@{sha=(Get-FileHash -LiteralPath 'C:\\JarvisHermesLab\\app\\memory_manager\\phase4\\credentials.py' -Algorithm SHA256).Hash.ToLower()}|ConvertTo-Json -Compress")
    if loader.get('sha')!='56a87075e51c7aa2074c4c70ba7367dca33bbdee5639e55a72dc9d333584c684':raise PermissionError('Private credential loader drift')
    code="import sys,json,hashlib;from pathlib import Path;sys.path.insert(0,'C:/JarvisHermesLab/app');from memory_manager.phase4.credentials import load_token;print(json.dumps({n:hashlib.sha256(load_token(Path('C:/JarvisHermesLab/identity')/n).encode()).hexdigest() for n in ('hermes.token','model.token','memory.token')}))"
    statement="import base64;exec(compile(base64.b64decode('"+base64.b64encode(code.encode()).decode()+"'),'<read-only-identities>','exec'))"
    result=ssh("& 'C:\\JarvisHermesLab\\runtime\\Scripts\\python.exe' -I -S -B -c '"+statement.replace("'","''")+"'",timeout=25)
    if result.returncode or json.loads(result.stdout.decode('utf-8-sig'))!=expected:raise PermissionError('Windows identity/DACL mismatch')
    return True

def cleanup_verified(report,ports_closed):
    native=report.get('native_windows',{});cleanup=report.get('cleanup',{})
    return (ports_closed is True and native.get('owned_runtime_cleanup') is True
            and native.get('owned_tunnel_closed') is True
            and cleanup.get('listener_after',{}).get('listening') is False
            and cleanup.get('supervisor',{}).get('owned_process_stopped_after_close') is True)

def local_ports_available(ports=(8792,8643,11435,11436)):
    # A stopped tunnel may still have TIME_WAIT sockets. Defer before reserving
    # work instead of consuming its only attempt or weakening the bind guard.
    for port in ports:
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',port))
            except OSError:return False
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);args=p.parse_args();cfg=private_json(args.config,max_bytes=CONFIG_MAX_BYTES)
    if cfg.get('enabled') is not True or cfg.get('remoteCostChf')!=0:raise PermissionError('Approved supervisor activation required')
    # Explicit root-reviewed code location, identities, bindings, no inherited HOME.
    root=Path(__file__).resolve().parent.parent
    bindings=private_json(cfg['bindingsFile'])
    raw=Path(cfg['bindingsFile']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=cfg['bindingsSha256']:raise PermissionError('Reviewed bindings drift')
    for name,expected in cfg['sourceFiles'].items():
        target=root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise PermissionError('Supervisor source drift')
    identity=private_json(cfg['identityFile'])
    if set(identity)!={'schedulerToken','supervisorToken'}:raise PermissionError('Scheduler and observer only')
    http=PrivateHTTP('http://127.0.0.1:8797',identity['schedulerToken'])
    state=Path(cfg['stateDirectory']);st=state.stat()
    if state.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077:raise PermissionError('Private supervisor state')
    for key,envkey in [('diagnosticKey','JARVIS_DIAGNOSTIC_KEY'),('diagnosticKnownHosts','JARVIS_DIAGNOSTIC_KNOWN_HOSTS'),('hermesIdentity','JARVIS_HERMES_IDENTITY')]:
        target=Path(cfg[key]);st=target.lstat()
        if target.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077:raise PermissionError('Private dedicated SSH paths required')
        os.environ[envkey]=str(target)
    from scripts.audit_gpu import collect
    from scripts import pilot_phase4_windows as existing
    from scripts.pilot_phase6b_panel import check_windows_patch
    def preflight():
        verify_egress(cfg['egressPolicy'],mode='start') # live allowed+forbidden proof, every mission
        if not local_ports_available():return 'preflight_failed'
        sample=collect() # Existing pinned SSH diagnostics; no GPU workload.
        if not sample.get('available'):return 'windows_offline'
        verify_egress(cfg['egressPolicy'],mode='mission') # Windows reachable through the allowed path only
        # 18.11 (User): mining runs in parallel; only fresh telemetry and free VRAM decide.
        free=sample.get('free_mib')
        if type(free) not in (int,float) or not 0<=time.time()-sample.get('observed_at',0)<=15:return 'gpu_busy'
        if free<8500:return 'insufficient_vram'
        check_windows_patch(operational=True,binding_file=cfg['bindingsFile'],binding_sha=cfg['bindingsSha256'])
        runtime_identity_check(cfg['runtimeIdentityHashes'])
        if existing.probe(existing.LISTENER).get('listening') is not False:return 'preflight_failed'
        return None
    def lifecycle(lease):
        if lease.get('runtime_identity_sha256')!=cfg['runtimeIdentityHashes']:raise PermissionError('Private service identity mismatch')
        token=uuid.uuid4().hex;folder=state/token;folder.mkdir(mode=0o700)
        observer=folder/'observer.json';observer.write_text(json.dumps({'supervisorToken':identity['supervisorToken']}));observer.chmod(0o600)
        window=folder/'window.json';window.write_text(json.dumps({'started_at':time.time(),'expires_at':lease['expires_at'],'closed':False,'calls':0,'missions':0,'limits':{'calls':6,'missions':1},'local_token_limit':98304}));window.chmod(0o600)
        output=root/'docs'/('DEMAND_RUN_'+token+'.json')
        with (folder/'supervisor.log').open('xb') as log:
            env={k:os.environ[k] for k in ['PATH','LANG','HOME','JARVIS_DIAGNOSTIC_KEY','JARVIS_DIAGNOSTIC_KNOWN_HOSTS','JARVIS_HERMES_IDENTITY'] if k in os.environ};env['PYTHONDONTWRITEBYTECODE']='1'
            process=subprocess.run(['python3','-B','-m','scripts.run_interactive_hermes','--approved-worker-window','--credentials',str(observer),'--window',str(window),'--output',str(output.relative_to(root)),'--bindings-file',cfg['bindingsFile'],'--bindings-sha',cfg['bindingsSha256'],'--egress-policy',cfg['egressPolicy']],cwd=root,env=env,stdout=log,stderr=log,timeout=max(1,lease['expires_at']-time.time()+45))
        if process.returncode or not output.exists():return {'cleanup_verified':False}
        report=json.loads(output.read_text())
        closed=existing.probe("$n=@(8643,11434,8792,11436)|Where-Object{@(Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue).Count -gt 0};[pscustomobject]@{all_closed=($n.Count -eq 0)}|ConvertTo-Json -Compress").get('all_closed')
        return {'cleanup_verified':cleanup_verified(report,closed)}
    supervisor=Supervisor(http,preflight,lifecycle)
    run_loop(supervisor)

def log(event):
    # Journal line: states, stages and exception types only; never tokens or bodies.
    print(json.dumps(event,sort_keys=True),flush=True)

def run_loop(supervisor,*,sleep=time.sleep,ticks=None):
    last=None;done=0
    log({'event':'supervisor-started'})
    while True:
        try:
            result=supervisor.tick()
            if result.get('state') not in ('idle','cooldown'):
                key=(result.get('state'),result.get('reason'),result.get('mission_id'),result.get('preflight_error'))
                if key!=last:log({'event':'supervisor-tick',**result});last=key
            elif result.get('state')=='idle' and last is not None:log({'event':'supervisor-idle'});last=None
        except Exception as e:
            # Unknown reservation/cleanup is quarantined by the queue; never reset it.
            key=('error',supervisor.stage,type(e).__name__)
            if key!=last:log({'event':'supervisor-error','stage':supervisor.stage,'error_type':type(e).__name__,'error':str(e)[:200]});last=key
            sleep(30)
        done+=1
        if ticks is not None and done>=ticks:return
        sleep(2)
if __name__=='__main__':main()
