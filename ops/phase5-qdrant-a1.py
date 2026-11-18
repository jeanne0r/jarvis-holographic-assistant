"""Authorized A1 only: private snapshot and bounded isolated restore inside CT205.

Run via pct exec 205 with --approved-a1. No production point writes, collection
provision, embedding restart, model invocation or installation. Public output is
metadata only; private artifacts remain inside CT205.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import urllib.request
import uuid

BASE=Path('/var/lib/jarvis-memory')
COLLECTION='jarvis_memory_v1'
MEMMAX=256*1024*1024
GiB=1024**3
ISOLATED=None


def memory_available():
    return next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))


def free_disk():
    s=os.statvfs(BASE);return s.f_bavail*s.f_frsize


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())


def yaml_text(value,indent=0):
    out=[]
    for key,item in value.items():
        if not re.fullmatch(r'[a-z_]+',key):raise ValueError('Fixed YAML keys required')
        prefix=' '*indent+key+':'
        out.append(prefix+'\n'+yaml_text(item,indent+2) if isinstance(item,dict) else prefix+' '+json.dumps(item))
    return '\n'.join(out)


def api(port,key,method,path,body=None,timeout=20):
    # Writes are permitted only to the one snapshot endpoint in the main instance.
    if port==6333 and not (method=='GET' or (method=='POST' and path=='/collections/'+COLLECTION+'/snapshots')):
        raise PermissionError('Production mutation denied')
    if port not in (6333,16333):raise PermissionError('Fixed loopback ports required')
    if port==16333:
        if not ISOLATED or os.readlink('/proc/'+str(ISOLATED[0])+'/ns/net')!=ISOLATED[1]:raise PermissionError('Owned private network required')
        helper="""import sys,json,urllib.request,urllib.error
v=json.load(sys.stdin)
try:
 req=urllib.request.Request('http://127.0.0.1:16333'+v['path'],method=v['method'],headers={'api-key':v['key'],'Content-Type':'application/json'},data=None if v['body'] is None else json.dumps(v['body']).encode())
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=v['timeout']) as r:print(json.dumps({'ok':True,'value':json.load(r)}))
except urllib.error.HTTPError as exc:print(json.dumps({'ok':False,'status':exc.code}))
except Exception:print(json.dumps({'ok':False}))
"""
        r=subprocess.run(['nsenter','--target',str(ISOLATED[0]),'--net','--','/usr/bin/python3','-c',helper],
            input=json.dumps({'key':key,'method':method,'path':path,'body':body,'timeout':timeout}),capture_output=True,text=True,timeout=timeout+3)
        if r.returncode:raise PermissionError('Private network query unavailable')
        result=json.loads(r.stdout)
        if not result['ok']:
            if result.get('status') in (401,403):raise PermissionError('Private endpoint denied identity')
            raise OSError('Private endpoint not ready')
        return result['value']
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,method=method,
        headers={'api-key':key,'Content-Type':'application/json'},data=None if body is None else json.dumps(body).encode())
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(req,timeout=timeout) as r:return json.load(r)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise PermissionError('Redirect denied')


def properties(unit):
    names=['ActiveState','SubState','Result','MainPID','ControlGroup','MemoryMax','MemorySwapMax','CPUQuotaPerSecUSec',
           'RuntimeMaxUSec','MemoryCurrent','MemoryPeak','CPUUsageNSec','OOMPolicy']
    raw=subprocess.check_output(['systemctl','show',unit,*['--property='+n for n in names]],text=True)
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)


def limits(unit,maximum=600):
    return ['systemd-run','--quiet','--unit='+unit,'--property=MemoryMax='+str(MEMMAX),
        '--property=PrivateNetwork=yes','--property=MemorySwapMax=0','--property=CPUQuota=50%','--property=RuntimeMaxSec='+str(maximum),
        '--property=TimeoutStopSec=10','--property=MemoryAccounting=yes','--property=CPUAccounting=yes',
        '--property=OOMPolicy=stop','--property=KillMode=control-group','--property=TasksMax=64','--property=UMask=0077']


def check_cgroup(p):
    cg=Path('/sys/fs/cgroup')/p['ControlGroup'].lstrip('/')
    mem=(cg/'memory.max').read_text().strip();swap=(cg/'memory.swap.max').read_text().strip()
    quota,period=(cg/'cpu.max').read_text().split()
    if mem!=str(MEMMAX) or swap!='0' or quota=='max' or int(quota)/int(period)>.5:
        raise PermissionError('Effective resource limits not enforced')
    if p['RuntimeMaxUSec'] not in {'10min','600000000'} and p['RuntimeMaxUSec']!='1min':raise PermissionError('Runtime limit missing')
    net=os.readlink('/proc/'+p['MainPID']+'/ns/net')
    if net==os.readlink('/proc/self/ns/net'):raise PermissionError('Private network isolation not effective')
    return {'private_network':True,'memory_max':int(mem),'swap_max':int(swap),'cpu_max':quota+' '+period,
            'memory_events':dict(line.split() for line in (cg/'memory.events').read_text().splitlines())}


def stop(unit):
    subprocess.run(['systemctl','stop',unit],capture_output=True,timeout=15)


def main():
    global ISOLATED
    parser=argparse.ArgumentParser();parser.add_argument('--approved-a1',action='store_true');parser.add_argument('--reuse-manifest');args=parser.parse_args()
    if not args.approved_a1:raise PermissionError('A1 authorization required')
    os.umask(0o077)
    if memory_available()<512*1024**2:raise PermissionError('CT available memory below 512 MiB')
    size=sum(p.stat().st_size for p in (BASE/'qdrant').rglob('*') if p.is_file())
    if free_disk()<4*size+GiB:raise PermissionError('Snapshot/restore disk reserve unavailable')
    socket_probe=socket.socket()
    try:socket_probe.bind(('127.0.0.1',16333))
    finally:socket_probe.close()
    binary='/usr/local/bin/qdrant'
    pid=int(subprocess.check_output(['systemctl','show','jarvis-qdrant','-p','MainPID','--value'],text=True).strip())
    if Path('/proc/'+str(pid)+'/exe').resolve()!=Path(binary):raise PermissionError('Unexpected binary')
    version=subprocess.check_output([binary,'--version'],text=True).strip()
    if not re.search(r'\b1\.20\.0\b',version):raise PermissionError('Expected Qdrant 1.20.0')
    env={}
    for line in Path('/etc/jarvis-memory.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);env[k.strip()]=v.strip().strip('\"').strip("'")
    key=env['QDRANT__SERVICE__API_KEY']
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    backup=BASE/'phase5-backup'/ident;restored=BASE/'phase5-restore'/ident
    backup.mkdir(parents=True,mode=0o700);restored.mkdir(parents=True,mode=0o700)
    report={'a1_id':ident,'scope':'A1 only','version':version,'binary_sha256':sha(binary),'production_pid_before':pid,
        'production_point_writes':0,'personal_payloads_exported':False,'hermes_ollama_started':False,
        'backup_directory':str(backup),'restore_directory':str(restored),'started_at':time.time(),'passed':False}
    unit='jarvis-phase5-restore-'+ident.lower();probeunit='jarvis-phase5-cgroup-'+ident.lower()
    try:
        # A harmless bounded process proves actual controller availability before snapshot.
        subprocess.run(limits(probeunit,60)+['/usr/bin/sleep','30'],check=True,capture_output=True,timeout=10)
        try:
            pre=properties(probeunit);report['cgroup_preflight']=check_cgroup(pre)
        finally:stop(probeunit)
        before=api(6333,key,'GET','/collections/'+COLLECTION)['result'];report['before']=before
        report['disk_free_before']=free_disk();report['memory_available_before']=memory_available()
        if args.reuse_manifest:
            existing=Path(args.reuse_manifest).resolve()
            if not existing.is_relative_to(BASE/'phase5-backup') or existing.name!='manifest.json':raise PermissionError('Existing private backup manifest required')
            manifest=json.loads(existing.read_text());target=Path(manifest['path']).resolve()
            if not target.is_relative_to(existing.parent) or target.stat().st_size!=manifest['bytes'] or sha(target)!=manifest['sha256']:
                raise ValueError('Existing backup verification failed')
            report['reused_manifest']=str(existing);report['snapshot']=manifest['snapshot']
            report['backup']={k:manifest[k] for k in ('path','sha256','bytes')}
        else:
            snap=api(6333,key,'POST','/collections/'+COLLECTION+'/snapshots',timeout=120)['result']
            name=snap['name']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.snapshot',name):raise ValueError('Unexpected snapshot filename')
            report['snapshot']=snap
            length=int(snap['size'])
            if free_disk()<length+2*size+GiB:raise PermissionError('Post-snapshot disk reserve unavailable')
            target=backup/name
            req=urllib.request.Request('http://127.0.0.1:6333/collections/'+COLLECTION+'/snapshots/'+name,headers={'api-key':key})
            op=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with op.open(req,timeout=60) as src,os.fdopen(os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as dst:
                total=0
                while True:
                    b=src.read(65536)
                    if not b:break
                    total+=len(b)
                    if total>length or free_disk()<GiB:raise PermissionError('Backup bound exceeded')
                    dst.write(b)
                dst.flush();os.fsync(dst.fileno())
            if total!=length:raise ValueError('Backup size mismatch')
            # Restrict only the newly created original snapshot, never existing artifacts.
            originals=list((BASE/'snapshots').rglob(name))
            if len(originals)==1:
                original=originals[0];original.chmod(0o600)
                if sha(original)!=sha(target):raise ValueError('Downloaded snapshot hash mismatch')
            else:raise ValueError('Snapshot source path could not be verified')
            manifest={'snapshot':snap,'path':str(target),'sha256':sha(target),'bytes':total,'version':version,
                      'source_collection':COLLECTION,'source_metadata':before,'created_at':time.time()}
            save(backup/'manifest.json',manifest);report['backup']={k:manifest[k] for k in ('path','sha256','bytes')}
            after_snapshot=api(6333,key,'GET','/collections/'+COLLECTION)['result']
            report['snapshot_source_count_stable']=before['points_count']==after_snapshot['points_count']
            if not report['snapshot_source_count_stable']:raise ValueError('Concurrent count change; require snapshot-time review')
        expected=manifest['source_metadata']
        if memory_available()<512*1024**2 or free_disk()<2*size+GiB:raise PermissionError('Restore resource reserve unavailable')
        for child in ('storage/collections','snapshots'):(restored/child).mkdir(parents=True,mode=0o700)
        isolatedkey=secrets.token_hex(32)
        config={'log_level':'WARN','telemetry_disabled':True,'cluster':{'enabled':False},
            'storage':{'storage_path':str(restored/'storage'),'snapshots_path':str(restored/'snapshots'),
                       'temp_path':None,'performance':{'max_search_threads':1}},
            'service':{'host':'127.0.0.1','http_port':16333,'grpc_port':None,'api_key':isolatedkey,'max_workers':1}}
        configpath=restored/'config.yaml'
        with os.fdopen(os.open(configpath,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:f.write(yaml_text(config)+'\n')
        command=limits(unit)+['--property=WorkingDirectory='+str(restored),'--property=NoNewPrivileges=yes',
            '--property=ProtectSystem=strict','--property=ReadWritePaths='+str(restored),
            '--property=InaccessiblePaths='+str(BASE/'qdrant')+' /etc/jarvis-memory.env',
            '/usr/bin/env','-i','PATH=/usr/bin:/bin','HOME='+str(restored),
            'QDRANT__SERVICE__HOST=127.0.0.1','QDRANT__SERVICE__HTTP_PORT=16333','QDRANT__TELEMETRY_DISABLED=true',
            binary,'--config-path',str(configpath),'--snapshot',str(target)+':'+COLLECTION]
        report['restore_command_redacted']=command # No credentials in argv.
        subprocess.run(command,check=True,capture_output=True,timeout=15)
        started=time.monotonic();report['samples']=[];ready=None
        while time.monotonic()-started<560:
            state=properties(unit)
            if state.get('ActiveState') not in ('activating','active'):raise RuntimeError('Isolated verifier exited')
            effective=check_cgroup(state)
            ISOLATED=(int(state['MainPID']),os.readlink('/proc/'+state['MainPID']+'/ns/net'))
            available=memory_available();disk=free_disk()
            cg=Path('/sys/fs/cgroup')/state['ControlGroup'].lstrip('/')
            peak=(cg/'memory.peak').read_text().strip() if (cg/'memory.peak').exists() else state.get('MemoryPeak')
            status=Path('/proc/'+state['MainPID']+'/status')
            rss=next((int(l.split()[1])*1024 for l in status.read_text().splitlines() if l.startswith('VmRSS:')),None) if status.exists() else None
            report['samples'].append({'elapsed':round(time.monotonic()-started,3),'available_bytes':available,
                'disk_free_bytes':disk,'memory_current':state.get('MemoryCurrent'),'memory_peak':peak,'process_rss_bytes':rss,
                'cpu_usage_nsec':state.get('CPUUsageNSec'),'cgroup':effective})
            if available<256*1024**2 or disk<GiB:raise PermissionError('Verifier reserve guard triggered')
            if int(effective['memory_events'].get('oom_kill','0')):raise RuntimeError('Verifier OOM; do not increase cap')
            try:ready=api(16333,isolatedkey,'GET','/collections/'+COLLECTION,timeout=2)['result']
            except (OSError,ValueError):time.sleep(1);continue
            break
        if ready is None:raise TimeoutError('Isolated restoration deadline')
        report['restored_metadata']=ready
        root=api(16333,isolatedkey,'GET','/');report['restored_version']=root.get('version')
        count=api(16333,isolatedkey,'POST','/collections/'+COLLECTION+'/points/count',{'exact':True})['result']['count']
        query=api(16333,isolatedkey,'POST','/collections/'+COLLECTION+'/points/query',
                  {'query':[1.0]+[0.0]*383,'limit':3,'with_payload':False,'with_vector':False})['result']['points']
        report['query']={'synthetic_vector':True,'returned':len(query),'payloads_requested':False,'vectors_requested':False,
                         'finite_scores':all(math.isfinite(p['score']) for p in query)}
        auth_denied=False
        try:api(16333,'','GET','/collections')
        except PermissionError:auth_denied=True
        report['checks']={'unauthenticated_denied':auth_denied,'version':root.get('version')=='1.20.0','count':count==expected['points_count'],
            'vectors':ready['config']['params']['vectors']==expected['config']['params']['vectors'],
            'payload_indexes':ready.get('payload_schema')==expected.get('payload_schema'),
            'query':len(query)==min(count,3) and report['query']['finite_scores'],'backup_hash':sha(target)==manifest['sha256']}
        report['exact_restored_count']=count;report['final_unit_properties']=properties(unit)
        report['passed']=all(report['checks'].values())
    except Exception as exc:
        # Never echo exception text: library errors can include private URLs/keys.
        report['error_class']=type(exc).__name__
    finally:
        try:
            state=properties(unit);report['unit_before_stop']=state
        except Exception:pass
        stop(unit)
        after_stop=properties(unit)
        report['unit_after_stop']=after_stop
        report['verifier_stopped']=after_stop.get('MainPID')=='0' and after_stop.get('ActiveState') not in ('active','activating','deactivating')
        try:
            s=socket.socket();s.settimeout(1);report['temporary_port_closed']=s.connect_ex(('127.0.0.1',16333))!=0;s.close()
        except OSError:report['temporary_port_closed']=False
        current=int(subprocess.check_output(['systemctl','show','jarvis-qdrant','-p','MainPID','--value'],text=True).strip())
        report['production_pid_after']=current;report['production_not_restarted']=current==pid
        report['services_after']={n:subprocess.run(['systemctl','is-active',n],capture_output=True,text=True).stdout.strip() for n in ('jarvis-qdrant','jarvis-embeddings')}
        try:report['production_metadata_after']=api(6333,key,'GET','/collections/'+COLLECTION)['result']
        except Exception:report['production_metadata_after']=None
        report['finished_at']=time.time();report['disk_free_after']=free_disk();report['memory_available_after']=memory_available()
        report['passed']=report['passed'] and report['verifier_stopped'] and report['temporary_port_closed'] and report['production_not_restarted'] and all(s=='active' for s in report['services_after'].values())
        save(backup/'a1-result.json',report)
        print(json.dumps(report),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:print(json.dumps({'passed':False,'preflight_error_class':type(exc).__name__}),flush=True);raise SystemExit(1)
