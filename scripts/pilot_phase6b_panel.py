"""One approved laboratory profile; defaults to L1, L2 uses its separate entry/flag."""
import argparse,hashlib,json,os,socket,sys,time,uuid
from pathlib import Path,PureWindowsPath
from scripts import pilot_phase4_windows as lifecycle
from scripts.pilot_phase5_windows import read_only_preflight
from scripts.pilot_phase5c_semantic import PATCH_FILES
from memory_manager.phase6 import panel_pilot
ROOT=panel_pilot.ROOT

OPERATIONAL_BINDINGS_SHA='965fd365c1b3fa3c23990fb19ba9af83ca65ed5408f8e0e4873c67078624c831'

def application_bindings(names,*,operational=False,binding_file=None,binding_sha=None):
    if not operational:return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    raw=Path(binding_file).read_bytes() if binding_file else (ROOT/'docs/HERMES_OPERATIONAL_WINDOWS_BINDINGS.json').read_bytes()
    if binding_file and (not binding_sha or Path(binding_file).is_symlink() or Path(binding_file).stat().st_mode&0o077):raise PermissionError('Private reviewed bindings required')
    if hashlib.sha256(raw).hexdigest()!=(binding_sha if binding_file else OPERATIONAL_BINDINGS_SHA):raise PermissionError('Pinned per-host bindings changed')
    bindings=json.loads(raw)
    if bindings.get('profile')!='operational-8797' or set(bindings['host_files'])!=set(names) or set(bindings['windows_files'])!=set(names):
        raise PermissionError('Exact application file set required')
    for name,expected in bindings['host_files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise PermissionError('Host application drift: '+name)
    return bindings['windows_files']

def check_windows_patch(*,operational=False,binding_file=None,binding_sha=None):
    names=(*PATCH_FILES,'ops/phase4-run-hermes-windows.py','ops/phase4-run-ollama-windows.py','memory_manager/phase4/job.py')
    expected_files=application_bindings(names,operational=operational,binding_file=binding_file,binding_sha=binding_sha)
    paths={name:str(PureWindowsPath('C:/JarvisHermesLab/app')/name) for name in names}
    query=','.join("'"+p+"'" for p in paths.values())
    hashes=lifecycle.probe("$out=@{};foreach($p in @("+query+")){$out[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()};$out|ConvertTo-Json -Compress")
    checked={}
    for name,path in paths.items():
        expected=expected_files[name]
        if hashes.get(path)!=expected:raise PermissionError('Existing Windows application differs: '+name+'; do not patch implicitly')
        checked[name]=expected
    return checked

def wait_local_ports(seconds=75):
    # Keep the original strict bind check. TIME_WAIT may outlive offline tests;
    # never adopt/kill a listener or weaken the bind with SO_REUSEADDR.
    deadline=time.monotonic()+seconds;announced=False
    while True:
        try:
            for port in (8792,11436,8643,11435):
                with socket.socket() as probe:probe.bind(('127.0.0.1',port))
            return
        except OSError:
            if time.monotonic()>=deadline:raise PermissionError('Local laboratory ports remain unavailable; no Windows startup')
            if not announced:print(json.dumps({'event':'waiting-for-local-ports','maximum_seconds':seconds}),flush=True);announced=True
            time.sleep(1)


def main(*,pilot="P6-L1"):

    parser=argparse.ArgumentParser(description=__doc__)
    if pilot not in {'P6-L1','P6-L2'}:raise PermissionError('Pilot profile')
    parser.add_argument('--approved-'+pilot.lower(),action='store_true',required=True)
    args=parser.parse_args()
    wait_local_ports();hashes=check_windows_patch();checks=read_only_preflight()
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    folder=ROOT/'data/phase6'/(pilot.lower()+'-'+ident);panel_pilot.prepare(folder)
    panel_pilot.private_json(folder/'preflight.json',{'windows':checks,'windows_application_sha256':hashes})
    # Open the single-use five-minute resource window only after all preparation.
    now=time.time();window=folder/'window.json'
    panel_pilot.private_json(window,{'started_at':now,'expires_at':now+300,'closed':False,'calls':0,'missions':0,'limits':{'calls':6,'missions':1},'local_token_limit':98304,'pilot':pilot})
    output='docs/JARVIS_2_PHASE6B_'+pilot.replace('-','_')+'_REAL_'+ident+'.json'
    old=sys.argv
    try:
        sys.argv=[pilot.lower()+'-lifecycle','--approved','--output',output]
        lifecycle.main(run_native=lambda c,u,t:panel_pilot.execute(c,u,t,folder=folder,pilot=pilot),approval_path=window)
    finally:
        sys.argv=old
        value=json.loads(window.read_text());value['closed']=True
        with window.open('w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
    result=json.loads((ROOT/output).read_text())
    result['pilot']=pilot;result['private_lab_path']=str(folder.relative_to(ROOT));result['allowance']={k:value[k] for k in ['calls','missions','closed','limits']}
    result['additional_remote_budget_chf']=0;result['p6_l2_authorized']=pilot=='P6-L2'
    listeners=lifecycle.probe("$out=@{};foreach($n in @(8643,11434,8792,11436)){$out[[string]$n]=(@(Get-NetTCPConnection -LocalPort $n -State Listen -ErrorAction SilentlyContinue).Count -gt 0)};$out|ConvertTo-Json -Compress")
    result['cleanup']['windows_lab_listeners_after']=listeners
    if any(listeners.values()):result['passed']=False
    manifest=json.loads((ROOT/'docs/phase6b/patch-manifest.json').read_text());seen=set();unchanged=True
    for stage in manifest['stages']:
        for row in stage['files']:
            path=Path(row['target'])
            if str(path) in seen:continue
            seen.add(str(path))
            if (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)!=row['before_sha256']:unchanged=False
    result['production_preimages_unchanged_after']=unchanged
    if not unchanged:result['passed']=False
    (ROOT/output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return 0 if result.get('passed') else 1
if __name__=='__main__':raise SystemExit(main())
