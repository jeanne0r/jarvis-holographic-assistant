"""Heartbeat gate around the existing approved controller, no new agent engine."""
from ..phase2.bridge import Bridge
from ..phase6.worker import tick as existing_tick
from .heartbeat import status

def tick(memory,principal,mission_id,worker,client,telemetry,*,approved=False):
 if approved is not True:raise PermissionError('Approved controller profile required')
 principal.require('mission_worker')
 bridge=Bridge(memory,principal);info=bridge.get(mission_id)
 availability=status(memory,principal,worker)
 # Unknown upstream submission is an immutable operational concern, never retry it.
 if info['dispatch_state']=='unknown':return {**info,'worker_availability':availability}
 if not availability['dispatch_allowed']:
    with memory.db:bridge.event(mission_id,'phase6d-worker-'+availability['state'],'deferred',{'reason':'worker_'+availability['state'],'automatic_replay':False})
    return {**info,'worker_availability':availability}
 # Keep existing independent GPU/Kryptex guard and model budgets. A ready
 # heartbeat alone never authorizes a GPU start or a physical action.
 return existing_tick(memory,principal,mission_id,client,telemetry,endpoint_ready=True,approved=True)
