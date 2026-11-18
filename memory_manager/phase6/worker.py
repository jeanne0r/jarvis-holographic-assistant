"""Explicit controller tick; no Windows startup, new canonical store, or model loop."""
import hashlib,json
from ..phase4.worker import tick as existing_tick
from ..phase2.bridge import Bridge
from ..phase2.memory_tools import MemoryTools


def tick(memory, principal, mission_id, client, telemetry, *, endpoint_ready, approved=False):
    if approved is not True:raise PermissionError('Approved controller profile required')
    principal.require('proposer')
    info=existing_tick(memory,principal,mission_id,client,telemetry,endpoint_ready=endpoint_ready)
    if info['state'] not in {'completed','failed'}:return info
    events=Bridge(memory,principal).events(mission_id)
    terminal=next((e for e in events if e['event_key']=='terminal'),None)
    if not terminal:return info
    data=json.loads(terminal['data']);output=data.get('output','')
    # Immutable canonical terminal event is the evidence of a REPORTED outcome,
    # never independent proof of facts or a source of new permissions.
    MemoryTools(memory,principal,mission_id).call('mission.result',{
        'state':info['state'],'terminal_event':f"bridge-event://{mission_id}/{terminal['seq']}",
        'output_sha256':hashlib.sha256(output.encode()).hexdigest(),'summary':output[:2000],
        'validation':'unreviewed_report_not_verified_fact'})
    return info
