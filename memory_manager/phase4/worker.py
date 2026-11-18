"""One host-authorized tick. Offline/occupied Windows does not consume a mission."""
from ..phase2.bridge import Bridge
from ..phase2.local_model import Busy


def tick(memory, principal, mission_id, client, telemetry, *, endpoint_ready):
    principal.require('mission_worker')
    bridge = Bridge(memory, principal)
    info = bridge.get(mission_id)
    if info['dispatch_state'] == 'ready':
        reason = None
        if endpoint_ready is not True:
            reason = 'windows_offline'
        else:
            try:
                # 18.11 (User): mining in parallel; VRAM and freshness decide (same check as the gate).
                from ..phase3.model_gate import vram_available
                vram_available(telemetry(), 8500)
            except Busy:
                reason = 'gpu_unavailable'
        if reason:
            with memory.db:
                bridge.event(mission_id, 'deferred-' + reason, 'deferred', {'reason': reason})
            return bridge.get(mission_id)
        with memory.db:
            # Server-selected key, INSERT OR IGNORE: a reconnect cannot reset it.
            bridge.event(mission_id, 'phase4-execution-started', 'execution_started', {})
    # Existing/unknown runs are polled or reconciled, never blindly recreated.
    return bridge.work(client, mission_id)
