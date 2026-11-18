"""CT205 A2 deployment; stdin JSON bundle, no installation or historical point writes.

Requires explicit --approved-a2. Backs up service/config metadata, stages a pinned
release, performs a no-model ASGI check, then one controlled embeddings restart.
An independent bounded watchdog restores a minimal read-only legacy service on
failure. All credentials stay in private CT205 files, never argv/stdout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path('/opt/jarvis-memory');DATA=Path('/var/lib/jarvis-memory');UNIT='jarvis-embeddings.service'
HIST='jarvis_memory_v1';EXP='jarvis_knowledge_experimental_v1'
OLD_SHA='542768af6a35b101cd41a37e2479469f4f7157613e98fc54ee6da0daa19864b1'
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(path,data,mode=0o600):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode),'w') as f:
        f.write(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    Path(path).chmod(mode)
def command(*args,timeout=20):return subprocess.run(list(args),capture_output=True,text=True,timeout=timeout,check=True).stdout.strip()
def available():return next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
def key():
    for line in Path('/etc/jarvis-memory.env').read_text().splitlines():
        if line.startswith('QDRANT__SERVICE__API_KEY='):return line.split('=',1)[1].strip().strip('"').strip("'")
    raise ValueError('Existing service credential unavailable')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise PermissionError('Redirect rejected')
def api(port,path,*,method='GET',body=None,headers=None,timeout=5):
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,method=method,headers={'Content-Type':'application/json',**(headers or {})},data=None if body is None else json.dumps(body).encode())
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=timeout) as response:return json.load(response)


ASGI_CHECK=r'''
import asyncio,json,sys,os,importlib.util
from pathlib import Path
from fastapi import FastAPI
from memory_manager.phase5.embedding_endpoint import attach
stage=Path(sys.argv[1]);token=(stage/'embedding.token').read_text().strip()
# Import/compile the candidate service without invoking its model lifespan.
os.environ['QDRANT__SERVICE__API_KEY']='synthetic-preflight'
spec=importlib.util.spec_from_file_location('phase5_staged_service',str(Path(sys.argv[2])/'service.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Stub:
 def embed(self,r):
  import time;time.sleep(.05)
  return {'synthetic':True}
app=FastAPI();attach(app,Stub(),enabled=True,token_file=stage/'embedding.token')
async def request(auth,raw=b'{"synthetic":true}'):
 out=[];sent=False
 async def receive():return {'type':'http.request','body':raw,'more_body':False}
 async def send(item):out.append(item)
 headers=[(b'content-length',str(len(raw)).encode()),(b'content-type',b'application/json')]
 if auth:headers.append((b'authorization',('Bearer '+token).encode()))
 await app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/v1/embeddings','raw_path':b'/v1/embeddings','root_path':'','query_string':b'','headers':headers,'client':('127.0.0.1',1),'server':('127.0.0.1',2)},receive,send)
 return next(i['status'] for i in out if i['type']=='http.response.start')
async def main():
 assert await request(False)==403
 assert await request(True)==200
 assert await request(True,b'invalid')==422
 statuses=await asyncio.gather(request(True),request(True));assert sorted(statuses)==[200,429]
 print(json.dumps({'passed':True,'no_model_instance_created':True,'unauthenticated':403,'authenticated':200,'malformed':422,'concurrent':sorted(statuses)}))
asyncio.run(main())
'''


WATCHDOG=r'''
import os,json,subprocess,time,urllib.request
from pathlib import Path
stage=Path(__file__).parent;state=json.loads((stage/'watchdog-state.json').read_text())
while time.time()<state['deadline'] and not (stage/'commit.json').exists() and not (stage/'rollback.request').exists():time.sleep(.5)
if (stage/'commit.json').exists():raise SystemExit(0)
# No retry loop. This legacy-only fallback contains no historical index writes.
def atomic(path,content):
 tmp=Path(str(path)+'.phase5-rollback');tmp.write_text(content);tmp.chmod(0o644);os.replace(tmp,path)
atomic('/opt/jarvis-memory/service.py',(stage/'fallback-service.py').read_text())
atomic(state['dropin'],state['fallback_dropin'])
subprocess.run(['systemctl','daemon-reload'],capture_output=True,timeout=15)
r=subprocess.run(['systemctl','restart','jarvis-embeddings.service'],capture_output=True,timeout=30)
key=None
for line in Path('/etc/jarvis-memory.env').read_text().splitlines():
 if line.startswith('QDRANT__SERVICE__API_KEY='):key=line.split('=',1)[1].strip().strip('"').strip("'")
healthy=False;deadline=time.time()+40
while time.time()<deadline:
 try:
  req=urllib.request.Request('http://127.0.0.1:6335/health',headers={'x-jarvis-key':key})
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=2) as f:healthy=json.load(f).get('ready') is True
 except Exception:pass
 if healthy:break
 time.sleep(1)
# Restore original restart policy only after a verified healthy fallback.
if healthy:
 Path(state['runtime_dropin']).unlink(missing_ok=True)
 subprocess.run(['systemctl','daemon-reload'],capture_output=True,timeout=15)
result={'rollback_attempted':True,'legacy_healthy':healthy,'restart_returncode':r.returncode,'experimental_enabled':False,'readonly_startup':True}
fd=os.open(stage/'rollback-result.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:json.dump(result,f)
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--approved-a2',action='store_true');args=p.parse_args()
    if not args.approved_a2:raise PermissionError('Explicit A2 authorization required')
    os.umask(0o077);bundle=json.load(sys.stdin)
    if available()<512*1024**2:raise PermissionError('CT memory reserve insufficient')
    if sha(ROOT/'service.py')!=OLD_SHA:raise PermissionError('Source changed since review')
    # A1 backup remains intact and hash-verified before any intervention.
    backup=json.loads((DATA/'phase5-backup/20261114T181811Z-3eb75693/manifest.json').read_text())
    if sha(backup['path'])!=backup['sha256']:raise ValueError('A1 backup integrity changed')
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    stage=ROOT/'phase5'/'releases'/ident;stage.mkdir(parents=True,mode=0o755)
    # Public sources, private state; dedicated token belongs to the existing service account.
    stage.parent.chmod(0o755);stage.parent.parent.chmod(0o755);stage.chmod(0o755)
    private=DATA/'phase5-a2'/ident;private.mkdir(parents=True,mode=0o700)
    account=pwd.getpwnam(command('systemctl','show',UNIT,'-p','User','--value'))
    # Service may traverse to its own 0600 token/manifest, but may not replace
    # root-owned rollback scripts or backups by renaming files in their parent.
    os.chown(private.parent,0,account.pw_gid);private.parent.chmod(0o710)
    os.chown(private,0,account.pw_gid);private.chmod(0o710)
    report={'id':ident,'scope':'A2 only','passed':False,'release':str(stage),'private_state':str(private),'started_at':time.time(),'a1_backup_verified':True,'no_model_download':True,'historical_point_writes':0,'windows_started':False}
    kh={'api-key':key()};before=api(6333,'/collections/'+HIST,headers=kh)['result'];report['historical_before']=before
    report['qdrant_pid_before']=int(command('systemctl','show','jarvis-qdrant','-p','MainPID','--value'))
    report['embedding_pid_before']=int(command('systemctl','show',UNIT,'-p','MainPID','--value'))
    original=(ROOT/'service.py').read_text();save(private/'original-service.py',original)
    fragment=Path(command('systemctl','show',UNIT,'-p','FragmentPath','--value'));save(private/'original-unit.service',fragment.read_text())
    save(private/'original-env.sha256',sha('/etc/jarvis-memory.env'))
    for name,source in bundle['files'].items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='memory_manager' or rel.suffix!='.py':raise ValueError('Package path rejected')
        target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        for parent in target.parents:
            if parent==stage:break
            parent.chmod(0o755)
        compile(source,str(target),'exec');save(target,source,0o644)
    compile(bundle['service'],str(stage/'service.py'),'exec');save(stage/'service.py',bundle['service'],0o644)
    runtime={'fastembed':'0.9.1','onnxruntime':'1.31.1','tokenizers':'0.23.3'}
    files={}
    for row in bundle['model_files']:
        path=Path(row['path'])
        if not path.resolve().is_relative_to(DATA/'models'):raise ValueError('Model path outside cache')
        if sha(path)!=row['sha256']:raise ValueError('Audited model artifact changed')
        files[str(path.resolve())]=row['sha256']
    artifact=digest({'model':MODEL,'files':files,'runtime':runtime,'preprocessing':'fastembed-document/query-v1;max128;no-truncation'})
    save(private/'manifest.json',{'files':files,'manifest_sha256':artifact});save(private/'embedding.token',secrets.token_hex(32))
    for name in ('manifest.json','embedding.token'):os.chown(private/name,account.pw_uid,account.pw_gid)
    report['pipeline_manifest_sha256']=artifact
    report['model_files_verified']=len(files)
    # All optional behavior is tested in the existing venv, without a second model.
    save(private/'asgi-check.py',ASGI_CHECK)
    check=subprocess.run(['systemd-run','--wait','--pipe','--quiet','--unit=jarvis-phase5-a2-preflight-'+ident.lower(),
        '--property=MemoryMax=268435456','--property=CPUQuota=50%','--property=RuntimeMaxSec=45',
        '--setenv=PYTHONPATH='+str(stage),str(ROOT/'venv/bin/python3'),str(private/'asgi-check.py'),str(private),str(stage)],capture_output=True,text=True,timeout=55)
    # ASGI check imports candidate service located next to its private state.
    if check.returncode:raise RuntimeError('ASGI preflight failed; existing service not modified')
    report['asgi_preflight']=json.loads(check.stdout.strip().splitlines()[-1])
    modelpath=next(str(Path(r['path']).parent) for r in bundle['model_files'] if r['path'].endswith('model_optimized.onnx'))
    dropdir=Path('/etc/systemd/system')/(UNIT+'.d');dropdir.mkdir(exist_ok=True)
    dropin=dropdir/'80-phase5-a2.conf';runtime_dropdir=Path('/run/systemd/system')/(UNIT+'.d');runtime_dropdir.mkdir(parents=True,exist_ok=True)
    runtime_dropin=runtime_dropdir/'90-phase5-a2-controlled.conf'
    if dropin.exists() or runtime_dropin.exists():raise PermissionError('Existing phase5 configuration requires review')
    def config(enabled):
        values={'PYTHONPATH':str(stage),'JARVIS_EMBEDDINGS_READONLY_STARTUP':'1','JARVIS_EXPERIMENTAL_EMBEDDINGS':str(int(enabled)),
          'JARVIS_EMBEDDINGS_MANIFEST_FILE':str(private/'manifest.json'),'JARVIS_EXPERIMENTAL_EMBEDDINGS_TOKEN_FILE':str(private/'embedding.token'),
          'JARVIS_EMBEDDINGS_MODEL_PATH':modelpath,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        return '[Service]\n'+''.join('Environment='+json.dumps(k+'='+v)+'\n' for k,v in values.items())
    # Minimal, dependency-independent legacy fallback preserves handlers and only skips startup writes.
    begin=original.index(" try:qdrant('/collections/'+COLLECTION)");end=original.index(' yield\n',begin)
    fallback=original[:begin]+" qdrant('/collections/'+COLLECTION)\n"+original[end:]
    fallback=fallback.replace("threads=2)","threads=2,local_files_only=True,specific_model_path="+repr(modelpath)+")",1)
    compile(fallback,'fallback-service.py','exec');save(private/'fallback-service.py',fallback)
    save(private/'watchdog.py',WATCHDOG)
    save(private/'watchdog-state.json',{'deadline':time.time()+90,'dropin':str(dropin),'runtime_dropin':str(runtime_dropin),'fallback_dropin':config(False)})
    save(dropin,config(True),0o644);save(runtime_dropin,'[Service]\nRestart=no\n',0o644)
    command('systemctl','daemon-reload')
    if command('systemctl','show',UNIT,'-p','Restart','--value')!='no':raise PermissionError('No-retry restart policy not effective')
    guard='jarvis-phase5-a2-rollback-'+ident.lower()
    command('systemd-run','--quiet','--unit='+guard,'--property=RuntimeMaxSec=140','--property=MemoryMax=67108864','--property=CPUQuota=10%',
            '/usr/bin/python3',str(private/'watchdog.py'))
    committed=False
    try:
        # Atomic replacement, preserving service account read access.
        temp=ROOT/('service.py.phase5-'+ident);save(temp,bundle['service'],0o644);os.replace(temp,ROOT/'service.py')
        command('systemctl','restart',UNIT,timeout=35)
        deadline=time.monotonic()+60;healthy=False
        while time.monotonic()<deadline:
            try:healthy=api(6335,'/health',headers={'x-jarvis-key':key()},timeout=2).get('ready') is True
            except Exception:pass
            if healthy:break
            if command('systemctl','show',UNIT,'-p','ActiveState','--value')=='failed':break
            time.sleep(.5)
        if not healthy:raise RuntimeError('Embeddings not healthy; rollback required')
        token=(private/'embedding.token').read_text().strip()
        vector=api(6335,'/v1/embeddings',method='POST',body={'model':MODEL,'kind':'query','input':'Quelle masse mesure le capteur synthétique ?'},headers={'Authorization':'Bearer '+token},timeout=15)
        if vector.get('artifact_sha256')!=artifact or vector.get('dimensions')!=384 or len(vector['data'][0]['embedding'])!=384:raise ValueError('Raw embedding contract mismatch')
        report['embedding_probe']={k:vector[k] for k in ('model','artifact_sha256','dimensions','kind','input_tokens')}
        save(private/'commit.json',{'healthy':True,'at':time.time()});committed=True
        subprocess.run(['systemctl','stop',guard],capture_output=True,timeout=15)
        runtime_dropin.unlink();command('systemctl','daemon-reload')
        report['restart_policy_restored']=command('systemctl','show',UNIT,'-p','Restart','--value')=='on-failure'
        report['embedding_pid_after']=int(command('systemctl','show',UNIT,'-p','MainPID','--value'))
        try:existing=api(6333,'/collections/'+EXP,headers=kh)['result'];report['collection_created']=False
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
            api(6333,'/collections/'+EXP,method='PUT',body={'vectors':{'size':384,'distance':'Cosine','on_disk':True},'on_disk_payload':True,
                'hnsw_config':{'on_disk':True},'optimizers_config':{'default_segment_number':2}},headers=kh,timeout=20)
            existing=api(6333,'/collections/'+EXP,headers=kh)['result'];report['collection_created']=True
        if existing['config']['params']['vectors'].get('size')!=384 or existing['config']['params']['vectors'].get('distance')!='Cosine':raise ValueError('Experimental schema mismatch')
        report['experimental_metadata']=existing
        report['passed']=True
    except Exception as exc:
        report['error_class']=type(exc).__name__
        if not committed:
            save(private/'rollback.request',{'at':time.time()})
            until=time.monotonic()+60
            while time.monotonic()<until and not (private/'rollback-result.json').exists():time.sleep(.5)
            if (private/'rollback-result.json').exists():report['rollback']=json.loads((private/'rollback-result.json').read_text())
    finally:
        report['historical_after']=api(6333,'/collections/'+HIST,headers=kh)['result']
        report['qdrant_pid_after']=int(command('systemctl','show','jarvis-qdrant','-p','MainPID','--value'))
        report['available_after']=available();report['finished_at']=time.time();report['source_sha256_after']=sha(ROOT/'service.py')
        save(private/'deployment-result.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:print(json.dumps({'passed':False,'predeployment_error_class':type(exc).__name__}),flush=True);raise SystemExit(1)
