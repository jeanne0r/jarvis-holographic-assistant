"""Authorized read-only private-service restoration; never arms a worker window."""
import sys
sys.dont_write_bytecode=True
import argparse, ast, hashlib, json, os, pwd, types, traceback, uuid
from pathlib import Path
SRC=Path('/home/user/workspace/jarvis-2-memory')
WRAPPER_SHA='21c3c82a77d554fb37f36eb70b21722dec5ab1e4e453bbc56f3e538fd6f38abf'

def validate_restart_tables(before,after):
    # Compare every canonical table exactly; accept only the precise register()
    # transition of the already-existing, synthetic Windows worker heartbeat.
    if set(before)!=set(after):raise PermissionError('Schema changed')
    for name in before:
        if name!='p6d_workers' and before[name]!=after[name]:
            raise PermissionError('Canonical table changed')
    old=[ast.literal_eval(row) for row in before.get('p6d_workers',[])]
    new=[ast.literal_eval(row) for row in after.get('p6d_workers',[])]
    if len(old)!=1 or len(new)!=1 or len(old[0])!=7 or len(new[0])!=7:
        raise PermissionError('Exact existing worker required')
    identity=('windows-hermes','phase3-synthetic','operational-controller')
    if old[0][:3]!=identity or new[0][:3]!=identity:
        raise PermissionError('Worker identity changed')
    epoch=new[0][3]
    if not isinstance(epoch,str) or str(uuid.UUID(epoch,version=4))!=epoch or uuid.UUID(epoch).version!=4 or epoch==old[0][3]:
        raise PermissionError('Fresh worker epoch required')
    if new[0][4:]!=(0,None,'unknown'):
        raise PermissionError('Worker must reset offline without observations')


def main():
    parser=argparse.ArgumentParser()
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--restore-readonly-approved',action='store_true')
    modes.add_argument('--diagnose-only',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0:raise PermissionError('Administrator terminal required')
    os.umask(0o077)
    path=SRC/'ops/pilot-network/run-worker-window.py'
    if path.is_symlink():raise PermissionError('Symlink refused')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=WRAPPER_SHA:raise PermissionError('Source drift')
    w=types.ModuleType('verified_worker_wrapper');exec(compile(raw,str(path),'exec'),w.__dict__)
    i=w.load('installer',w.read_verified(SRC/'ops/pilot-network/install-operational-panel.py',w.INSTALLER_SHA))
    c=w.load('coordinator',w.read_verified(SRC/'ops/pilot-network/install-system-pilot.py',w.COORDINATOR_SHA))
    c.verify_layout()
    app=pwd.getpwnam('jarvis-pilot');operator=pwd.getpwnam('user')
    i.regular(w.STATE/'config.json',app.pw_uid,True)
    i.regular(w.FLAG,operator.pw_uid,True)
    cfg=(w.STATE/'config.json').read_bytes();flag=w.FLAG.read_bytes()
    value=json.loads(cfg)
    if i.configuration(value)!=value or value.get('operations')!=i.OFF:raise PermissionError('Unarmed profile required')
    if json.loads(flag)!={'enabled':True}:raise PermissionError('Read-only panel required')
    receipt=Path('/var/backups/jarvis-hermes/first-operational-window-used.json')
    i.regular(receipt,0,True);receipt_before=receipt.read_bytes()
    if i.user_command('show','jarvis-hermes-pilot.service','-p','ActiveState','--value')!='inactive':raise PermissionError('Legacy pilot active')
    i.validate_synthetic(w.STATE/'memory.sqlite')
    before=i.tables(w.STATE/'memory.sqlite');gateway=i.gateway_alive()
    if args.diagnose_only:
        saved=json.loads(receipt_before)
        backup=Path(saved['backup'])
        parent=Path('/var/backups/jarvis-hermes')
        if backup.parent!=parent or not backup.name.startswith('worker-') or backup.is_symlink():
            raise PermissionError('Unexpected backup location')
        i.regular(backup/'snapshot.sqlite',0,True)
        original=i.tables(backup/'snapshot.sqlite')
        changed=sorted(name for name in set(original)|set(before) if original.get(name)!=before.get(name))
        print(json.dumps({'passed':True,'read_only':True,
            'changed_tables_since_window_backup':changed,
            'changed_table_counts':{name:{'before':len(original.get(name,[])), 'after':len(before.get(name,[]))} for name in changed},
            'gateway_pid':gateway,'all_operations_disabled':True,
            'service_state':i.command(['systemctl','show',w.UNIT,'-p','ActiveState','--value']),
            'service_started':False,'authorization_receipt_preserved':True}))
        return
    started=False
    try:
        confinement=c.supervised_start();started=True
        if (w.STATE/'config.json').read_bytes()!=cfg or w.FLAG.read_bytes()!=flag or receipt.read_bytes()!=receipt_before:
            raise PermissionError('Configuration or authorization changed')
        after=i.tables(w.STATE/'memory.sqlite')
        validate_restart_tables(before,after)
        if i.gateway_alive()!=gateway:raise PermissionError('Gateway changed')
        print(json.dumps({'passed':True,'readonly_service_restored':True,'all_operations_disabled':True,
            'authorization_receipt_preserved':True,'canonical_tables_unchanged':True,'worker_heartbeat_reset_verified':True,'gateway_pid_unchanged':True,
            'windows_started':False,'new_missions':0,'confinement':confinement}))
    except BaseException:
        if started:i.command(['systemctl','stop',w.UNIT])
        raise

if __name__=='__main__':
    try:main()
    except BaseException as error:
        frames=traceback.extract_tb(error.__traceback__);last=frames[-1] if frames else None
        print(json.dumps({'passed':False,'error_type':type(error).__name__,
            'function':last.name if last else None,'line':last.lineno if last else None,
            'no_automatic_retry':True}),file=sys.stderr)
        raise SystemExit(1)
