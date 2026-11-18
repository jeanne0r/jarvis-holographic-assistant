"""Approved lot A only: two static assets. No services, flags, identities or SQLite."""
import argparse,grp,hashlib,json,os,pwd,secrets,shutil,ssl,stat,subprocess,time,urllib.request,urllib.error
from pathlib import Path
SRC=Path('/home/user/workspace/jarvis-2-memory');GW=Path('/home/user/gateway')
CANDIDATE=SRC/'data/big-boss/lot-a-ready'
REVIEW='cc73bed'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def directory(path):
    st=path.lstat();uid=os.getuid()
    if path.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid!=uid or st.st_mode&0o002:
        raise PermissionError('Unexpected directory')
    if st.st_mode&0o020:
        # A private owner group does not add another principal. Never chmod
        # production directories or accept a group containing another account.
        members=set(grp.getgrgid(st.st_gid).gr_mem)|{p.pw_name for p in pwd.getpwall() if p.pw_gid==st.st_gid}
        if members!={pwd.getpwuid(uid).pw_name}:raise PermissionError('Additional directory writer')
def exclusive(path,raw,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),mode)
def publish(target,raw,mode):
    temporary=target.with_name('.'+target.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        exclusive(temporary,raw,mode);os.replace(temporary,target)
        fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if temporary.exists():temporary.unlink()
def service(name,user=False):
    return subprocess.check_output(['systemctl']+(['--user'] if user else [])+['show',name,'-p','MainPID','-p','ActiveState'],text=True).strip()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--lot-a-approved',action='store_true',required=True);parser.parse_args()
    if os.getuid()!=1000:raise PermissionError('Existing unprivileged file owner required')
    pinned=json.loads(subprocess.check_output(['git','show',REVIEW+':docs/JARVIS_2_BIG_BOSS_MANIFEST.json'],cwd=SRC))['lots']['A']
    raw=(CANDIDATE/'manifest.json').read_bytes()
    if sha(raw)!=pinned['manifest_sha256']:raise PermissionError('Candidate manifest drift')
    manifest=json.loads(raw);targets=[GW/'public/jarvis/hermes-embedded.js',GW/'public/jarvis/hermes-embedded.css']
    if [Path(r['target']) for r in manifest['files']]!=targets:raise PermissionError('Exact two targets required')
    for p in [GW,GW/'public',GW/'public/jarvis',GW/'data']:directory(p)
    original={};revised={};modes={}
    for row in manifest['files']:
        target=Path(row['target']);st=target.lstat();artifact=CANDIDATE/row['artifact']
        if target.is_symlink() or artifact.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o022:
            raise PermissionError('Unexpected asset')
        original[target]=target.read_bytes();revised[target]=artifact.read_bytes();modes[target]=stat.S_IMODE(st.st_mode)
        if sha(original[target])!=row['before_sha256'] or sha(revised[target])!=row['after_sha256'] or (CANDIDATE/row['backup']).read_bytes()!=original[target]:raise PermissionError('Preimage mismatch')
    protected=[GW/'server.js',GW/'public/jarvis/app.js',GW/'public/jarvis/index.html',GW/'hermes-embedded-relay.mjs',GW/'hermes-embedded-contract.mjs',GW/'data/hermes-panel-switch.json']
    before={p:sha(p.read_bytes()) for p in protected}
    if json.loads((GW/'data/hermes-panel-switch.json').read_bytes())!={'enabled':True}:raise PermissionError('Read-only panel expected')
    services=[service('codex-gateway.service',True),service('jarvis-hermes-pilot-system.service')]
    if any('ActiveState=active' not in v for v in services):raise PermissionError('Services must already be active')
    if shutil.disk_usage(GW).free<16*1024*1024+sum(map(len,original.values()))*5:raise OSError('Disk reserve unavailable')
    parent=GW/'data/backups'
    if parent.exists():directory(parent)
    else:parent.mkdir(mode=0o700)
    backup=parent/('hermes-ui-A-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+secrets.token_hex(4));backup.mkdir(mode=0o700)
    exclusive(backup/'manifest.json',raw)
    for target,data in original.items():
        saved=backup/(target.name+'.before');exclusive(saved,data)
        restored=backup/(target.name+'.restore-check');exclusive(restored,saved.read_bytes())
        if restored.read_bytes()!=data:raise ValueError('Backup restore copy differs')
    context=ssl.create_default_context(cafile=str(GW/'data/certs/gateway.crt'))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):raise PermissionError('Redirect refused')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context),NoRedirect())
    def get(path):
        try:
            with opener.open('https://192.0.2.16:8788'+path,timeout=5) as r:return r.status,r.read(2*1024*1024)
        except urllib.error.HTTPError as e:return e.code,b''
    written=[]
    try:
        for target in targets:
            if target.is_symlink() or target.read_bytes()!=original[target]:raise PermissionError('Concurrent asset change')
            publish(target,revised[target],modes[target]);written.append(target)
        for target in targets:
            status,data=get('/jarvis/'+target.name)
            if target.read_bytes()!=revised[target] or status!=200 or data!=revised[target]:raise PermissionError('Served asset mismatch')
        if get('/jarvis/')[0]!=200:raise PermissionError('Holographic page unavailable')
        if any(get(p)[0]!=401 for p in ['/api/jarvis/hermes-panel/session','/api/jarvis/hermes-panel/hermes/missions?space=user']):raise PermissionError('Anonymous access not refused')
        status,data=get('/api/jarvis/live/status')
        if status!=200 or json.loads(data).get('engine')!='hybrid':raise PermissionError('Hybrid status differs')
        if any(sha(p.read_bytes())!=v for p,v in before.items()):raise PermissionError('Protected input changed')
        if services!=[service('codex-gateway.service',True),service('jarvis-hermes-pilot-system.service')]:raise PermissionError('Service changed')
        report={'passed':True,'lot':'A','backup':str(backup),'exactly_two_assets_updated':True,'backup_restore_copy_verified':True,'https_served_hashes_verified':True,'anonymous_401':True,'hybrid_unchanged':True,'protected_inputs_unchanged':True,'service_pids_unchanged':True,'flags_unchanged':True,'gateway_restarts':0,'windows_started':False,'new_missions':0,'remote_api_calls':0,'authenticated_production_browser':'not_tested_no_operator_credential_read'}
        exclusive(backup/'result.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))
    except BaseException as error:
        restored=True
        for target in reversed(written):
            if not target.is_symlink() and target.read_bytes()==revised[target]:publish(target,original[target],modes[target])
            else:restored=False
        report={'passed':False,'error_type':type(error).__name__,'backup':str(backup),'rollback_verified':restored and all(p.read_bytes()==data for p,data in original.items()),'no_automatic_retry':True}
        exclusive(backup/'result.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report));raise SystemExit(1)
if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'passed':False,'error_type':type(error).__name__,'no_automatic_retry':True}));raise SystemExit(1)
