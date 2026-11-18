"""Read-only diagnosis of the completed, named synthetic recovery window.
No service operations, admission, Windows connection or verdict replacement.
"""
import sys
sys.dont_write_bytecode=True
import argparse, hashlib, json, os, sqlite3, stat, urllib.request
from pathlib import Path
WINDOW='20261115T200950Z-29e0e47e'
STATE=Path('/var/lib/jarvis-hermes-pilot')
BACKUP=Path('/var/backups/jarvis-hermes')/('worker-'+WINDOW)
SRC=Path('/home/user/workspace/jarvis-2-memory')

def owned(path,uid):
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or st.st_mode&0o077:
        raise PermissionError('Private regular file required')
    return path.read_bytes()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.parse_args()
    if os.geteuid()!=0:raise PermissionError('Administrator terminal required')
    import pwd
    cfg=json.loads(owned(STATE/'config.json',pwd.getpwnam('jarvis-pilot').pw_uid))
    if cfg.get('operations')!=dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'],False):
        raise PermissionError('Operations must remain disabled')
    original_report=owned(BACKUP/'result.json',0)
    if json.loads(original_report).get('window_id')!=WINDOW:raise PermissionError('Window mismatch')
    with sqlite3.connect('file:'+str(BACKUP/'snapshot.sqlite')+'?mode=ro',uri=True) as old:
        old_ids={r[0] for r in old.execute('SELECT id FROM mm_missions')}
    with sqlite3.connect('file:'+str(STATE/'memory.sqlite')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        if db.execute("SELECT 1 FROM mm_missions WHERE owner!='phase3-synthetic' OR scope!='private' LIMIT 1").fetchone():
            raise PermissionError('Synthetic scope required')
        added={r[0] for r in db.execute('SELECT id FROM mm_missions')}-old_ids
        if len(added)!=1:raise PermissionError('Exactly one new mission required')
        mid=next(iter(added))
        mission=db.execute('SELECT state FROM mm_missions WHERE id=?',(mid,)).fetchone()
        calls,tokens,cost=db.execute('SELECT count(*),coalesce(sum(coalesce(used_tokens,reserved_tokens)),0),coalesce(sum(coalesce(actual_remote_micros,reserved_remote_micros)),0) FROM p2_usage WHERE mission_id=?',(mid,)).fetchone()
        terminal=db.execute("SELECT data FROM p2_events WHERE mission_id=? AND event_key='terminal'",(mid,)).fetchone()
        output=json.loads(terminal[0]).get('output','') if terminal else ''
        event=db.execute('SELECT source FROM mm_events WHERE event_key=? AND owner=? AND scope=?',('mission-result-'+mid,'phase3-synthetic','private')).fetchone()
        request=urllib.request.Request('http://127.0.0.1:8797/v1/missions/'+mid+'/canonical',headers={'Authorization':'Bearer '+cfg['bridgeToken']})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):raise PermissionError('Redirect refused')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=5) as response:
            raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:raise ValueError('Response bound')
            projection=json.loads(raw)['projection']
        refs=list(dict.fromkeys(item['source_ref'] for item in projection['items']))
        # Print only bounded synthetic references, never model output or credentials.
        if len(refs)>200 or any(not ref.startswith(('synthetic://doselab/','mission://')) for ref in refs):
            raise PermissionError('Unexpected source reference')
        if owned(BACKUP/'result.json',0)!=original_report:raise PermissionError('Historical report changed')
        print(json.dumps({'passed':True,'read_only':True,'window_id':WINDOW,'mission_id':mid,
            'historical_passed':json.loads(original_report)['passed'],'historical_report_sha256':hashlib.sha256(original_report).hexdigest(),
            'persisted_mission_state':mission[0],'calls':calls,'tokens':tokens,'remote_cost_micros':cost,
            'within_quotas':calls<=6 and tokens<=98304 and cost==0,
            'source_refs':refs,'host_receipts':projection.get('selection_origin')=='authenticated_host_tool_receipts',
            'sqlite_origin':projection.get('origin')=='sqlite',
            'cited_synthetic_refs':[ref for ref in refs if ref.startswith('synthetic://doselab/') and ref in output],
            'experience_saved':bool(event and json.loads(event[0]).get('ref')=='mission://'+mid),
            'original_prefix_check_would_pass':bool(refs) and all(ref.startswith('synthetic://doselab/') for ref in refs),
            'all_operations_disabled':True,'no_services_started':True}))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        print(json.dumps({'passed':False,'read_only':True,'error_type':type(error).__name__,'no_automatic_retry':True}),file=sys.stderr)
        raise SystemExit(1)
