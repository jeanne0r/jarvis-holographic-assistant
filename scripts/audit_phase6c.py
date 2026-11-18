"""Read-only production code/status audit; no private DB/content or remote host access."""
import hashlib,json,re,subprocess,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];J=Path('/home/user/workspace/jarvis');G=Path('/home/user/gateway')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((ROOT/'docs/phase6b/patch-manifest.json').read_text());rows={}
    for stage in manifest['stages']:
        for row in stage['files']:
            if row['target'] not in rows:rows[row['target']]={**row,'prepared_final_sha256':row['after_sha256']}
            else:rows[row['target']]['prepared_final_sha256']=row['after_sha256']
    targets=[]
    for name,row in rows.items():
        p=Path(name);actual=sha(p) if p.exists() else None
        targets.append({'path':name,'active_sha256':actual,'matches_reviewed_preimage':actual==row['before_sha256'],'phase6b_final_sha256':row['prepared_final_sha256'],'installed':actual==row['prepared_final_sha256'],'mtime_utc':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat() if p.exists() else None})
    extra=[J/n for n in ['ai.mjs','hybrid-brain.mjs','codex-worker.mjs','tools-server.mjs','speech.mjs','core-settings.mjs','memory-map.mjs']]+[G/'public/jarvis'/n for n in ['app.js','codex-voice.js','live.js','archive.js']]
    code=(G/'server.js').read_text()
    routes=sorted(set(re.findall(r'url\.pathname\s*===\s*[\'"]([^\'"]+)',code)))
    api=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    observations=[]
    for route,fields in [('voice/status',['engine','speechOnly','configured','transcriptionModel','synthesisModel']),('session',[])]:
        try:
            with api.open('http://127.0.0.1:8787/api/jarvis/'+route,timeout=3) as response:
                status=response.status;data=json.loads(response.read(65536))
        except urllib.error.HTTPError as e:status=e.code;data={}
        observations.append({'route':'/api/jarvis/'+route,'status':status,'credential_sent':False,'safe_fields':{k:data[k] for k in fields if k in data}})
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'production_writes':0,'windows_operations':0,'private_conversations_read':False,'service':subprocess.check_output(['systemctl','--user','show','codex-gateway.service','--property=ActiveState,MainPID,ExecMainStartTimestamp'],text=True).splitlines(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'configured_engine':json.loads((J/'data/core-engine.json').read_text()).get('engine'),'status_observations':observations,'reviewed_targets':targets,'additional_code_hashes':{str(p):sha(p) for p in extra},'gateway_literal_routes':routes,'all_reviewed_preimages_unchanged':all(r['matches_reviewed_preimage'] for r in targets)}
    (ROOT/'docs/JARVIS_2_PHASE6C_ACTIVE_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'reviewed_targets':len(targets),'all_reviewed_preimages_unchanged':result['all_reviewed_preimages_unchanged'],'status_observations':observations,'production_writes':0,'windows_operations':0}))
if __name__=='__main__':main()
