"""B review artifacts, never installs, creates credentials or touches active state."""
import argparse,hashlib,json
from pathlib import Path
from .prepare_mission_policy import prepare
from .prepare_embedded_panel import ROOT

PRIVATE=['hermes-human-delegation.mjs','hermes-private-human-policy.mjs','hermes-mission-policy.mjs',
         'hermes-embedded-api.mjs','jarvis-session-auth.mjs','ops/pilot-embedded.mjs']
GATEWAY=['hermes-human-delegation.mjs','hermes-human-gateway.mjs','hermes-human-mount.mjs',
         'hermes-embedded-relay.mjs','hermes-embedded-contract.mjs','jarvis-session-auth.mjs','hermes-server-auth.mjs',
         'gateway-production-main.mjs']
def build(destination):
    dest=Path(destination)
    if dest.exists():raise FileExistsError('Never overwrite a preparation')
    dest.mkdir(parents=True)
    private=prepare(dest/'private',source_files=PRIVATE)
    gateway=dest/'gateway-review';gateway.mkdir()
    rows=[]
    for name in GATEWAY:
        source=ROOT/name;raw=source.read_bytes();(gateway/name).write_bytes(raw)
        active=Path('/home/user/gateway')/name
        rows.append({'artifact':'gateway-review/'+name,'after_sha256':hashlib.sha256(raw).hexdigest(),
                     'active_library_sha256':hashlib.sha256(active.read_bytes()).hexdigest() if active.is_file() else None})
    result={'production_modified':False,'purpose':'single human session reviewed against two independent policies',
            'activation':'NO-GO until secured entry services, identity enrollment and executor isolation verified',
            'private_delta':private['files'],'gateway_libraries':rows,
            'active_server_replaced':False,'server_patch_ready':False,'new_keys_created':False,'private_memory_read':False}
    (dest/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');args=p.parse_args();r=build(args.destination)
    print(json.dumps({'prepared':True,'private_changed_files':len(r['private_delta']),'production_modified':False,'activation':r['activation']}))
