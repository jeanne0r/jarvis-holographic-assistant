"""Explicitly approved C1: replace exactly one UI asset, never touches services/flags."""
import argparse,datetime,grp,hashlib,json,os,pwd,secrets,shutil,ssl,stat,subprocess,tempfile,urllib.request,urllib.error
from pathlib import Path
ROOT=Path('/home/user/workspace/jarvis-2-memory')
GATEWAY=Path('/home/user/gateway')
TARGET=GATEWAY/'public/jarvis/hermes-embedded.js'
REVIEW=ROOT/'docs/HERMES_TEXT_MISSIONS_MANIFEST.json'
REVIEW_SHA='23f9d1daa45c2842575e2abdc073f74584ea5b27a4b0e290c333070695f8a021'
ORIGIN='https://192.0.2.16:8788'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def command(args):return subprocess.check_output(args,text=True,timeout=10).strip()
def safe(path):
    for p in [path,*path.parents]:
        st=p.lstat()
        if stat.S_ISLNK(st.st_mode) or st.st_mode&0o002:raise PermissionError('Unsafe path')
        if st.st_mode&0o020:
            users=set(grp.getgrgid(st.st_gid).gr_mem)|{x.pw_name for x in pwd.getpwall() if x.pw_gid==st.st_gid}
            if users!={pwd.getpwuid(st.st_uid).pw_name}:raise PermissionError('Shared writable path')
def pid(user,unit):
    args=['systemctl']+(['--user'] if user else [])+['show',unit,'-p','MainPID','-p','ActiveState']
    result=dict(x.split('=',1) for x in command(args).splitlines())
    if result.get('ActiveState')!='active' or int(result['MainPID'])<=0:raise RuntimeError('Expected active service')
    return result['MainPID']
def services():return {'gateway':pid(True,'codex-gateway.service'),'private':pid(False,'jarvis-hermes-pilot-system.service')}
def no_worker():
    import re
    if re.search(r'127\.0\.0\.1:11436\s',command(['ss','-ltn'])):raise PermissionError('Model gate unexpectedly active')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-asset-only',action='store_true',required=True);parser.parse_args()
    os.umask(0o077)
    if sha(REVIEW.read_bytes())!=REVIEW_SHA:raise PermissionError('Reviewed manifest drift')
    review=json.loads(REVIEW.read_bytes());row=review['frontend']
    if row['target']!=str(TARGET):raise PermissionError('Only approved target allowed')
    candidate=ROOT/review['frontend_package']/row['artifact']
    for p in [TARGET,candidate,GATEWAY/'data/backups']:safe(p)
    before=TARGET.read_bytes();after=candidate.read_bytes();st=TARGET.stat()
    if st.st_uid!=os.getuid() or st.st_gid!=os.getgid() or stat.S_IMODE(st.st_mode)!=0o600:raise PermissionError('Expected owner/private mode')
    if sha(before)!=row['before_sha256'] or sha(after)!=row['after_sha256']:raise PermissionError('Asset preimage/candidate drift')
    subprocess.run(['node','--check',str(candidate)],check=True,capture_output=True,timeout=10)
    protected=[GATEWAY/'server.js',GATEWAY/'public/jarvis/app.js',GATEWAY/'public/jarvis/index.html',GATEWAY/'public/jarvis/hermes-embedded.css',GATEWAY/'data/hermes-panel-switch.json',Path('/opt/jarvis-hermes-pilot/deployment-files.json'),Path('/home/user/workspace/jarvis/backend.mjs')]
    observed={str(p):sha(p.read_bytes()) for p in protected};original_services=services()
    if json.loads((GATEWAY/'data/hermes-panel-switch.json').read_bytes())!={'enabled':True}:raise PermissionError('Read/cancel-only relay expected')
    no_worker()
    context=ssl.create_default_context(cafile=str(GATEWAY/'data/certs/gateway.crt'))
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
    def get(path):
        try:
            with opener.open(ORIGIN+path,timeout=10) as response:
                if response.geturl()!=ORIGIN+path:raise PermissionError('Redirect refused')
                raw=response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:raise ValueError('Response bound')
                return response.status,raw
        except urllib.error.HTTPError as error:return error.code,b''
    if get('/jarvis/')[0]!=200 or get('/api/jarvis/hermes-panel/session')[0]!=401 or get('/api/jarvis/hermes-panel/hermes/missions?space=user')[0]!=401:raise PermissionError('HTTPS/auth precheck')
    if shutil.disk_usage(GATEWAY/'data/backups').free<16*1024*1024+8*len(before):raise OSError('Disk reserve')
    backup=GATEWAY/'data/backups'/('hermes-text-C-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));backup.mkdir(mode=0o700)
    (backup/'hermes-embedded.js.before').write_bytes(before)
    (backup/'manifest.json').write_bytes(REVIEW.read_bytes())
    (backup/'restore-check.js').write_bytes((backup/'hermes-embedded.js.before').read_bytes())
    if sha((backup/'restore-check.js').read_bytes())!=row['before_sha256']:raise ValueError('Backup restoration check failed')
    def replace(raw):
        descriptor,name=tempfile.mkstemp(prefix='.hermes-text-',dir=TARGET.parent)
        try:
            with os.fdopen(descriptor,'wb') as out:
                os.fchmod(out.fileno(),stat.S_IMODE(st.st_mode));os.fchown(out.fileno(),st.st_uid,st.st_gid);out.write(raw);out.flush();os.fsync(out.fileno())
            os.replace(name,TARGET)
            fd=os.open(TARGET.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        finally:
            if os.path.exists(name):os.unlink(name)
    result={'passed':False,'lot':'C1','backup':str(backup),'gateway_restarts':0,'windows_started':False,'missions_created':0,'paid_api_calls':0,'private_configuration_read':False}
    installed=False
    try:
        if TARGET.read_bytes()!=before or services()!=original_services:raise PermissionError('Concurrent change')
        replace(after);installed=True
        if sha(TARGET.read_bytes())!=row['after_sha256']:raise ValueError('Installed bytes differ')
        code,served=get('/jarvis/hermes-embedded.js?lotC='+row['after_sha256'])
        if code!=200 or sha(served)!=row['after_sha256']:raise ValueError('HTTPS served bytes differ')
        if get('/jarvis/')[0]!=200 or get('/api/health')[0]!=200:raise ValueError('Jarvis health failure')
        code,status=get('/api/jarvis/live/status')
        if code!=200 or json.loads(status).get('engine')!='hybrid':raise ValueError('Hybrid changed')
        if get('/api/jarvis/hermes-panel/session')[0]!=401 or get('/api/jarvis/hermes-panel/hermes/missions?space=user')[0]!=401:raise PermissionError('Anonymous access')
        if services()!=original_services or any(sha(Path(p).read_bytes())!=h for p,h in observed.items()):raise PermissionError('Protected service/input changed')
        no_worker()
        result.update(passed=True,https_sha256=row['after_sha256'],backup_restore_verified=True,anonymous_denied=True,hybrid_unchanged=True,protected_files_unchanged=True,service_pids_unchanged=True,relay_admission_disabled=True,model_gate_absent=True,authentication_unchanged=True,only_production_asset_changed=True,authenticated_display='same_bytes_tested_offline; operator_session_not_read')
    except BaseException:
        if installed and sha(TARGET.read_bytes())==row['after_sha256']:
            replace((backup/'hermes-embedded.js.before').read_bytes())
            code,served=get('/jarvis/hermes-embedded.js?rollback='+secrets.token_hex(4))
            result['rollback_verified']=code==200 and sha(served)==row['before_sha256']
        (backup/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        raise
    (backup/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'docs/JARVIS_2_LOT_C1_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
