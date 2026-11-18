"""Approved existing Windows lifecycle, waiting for ONE human UI admission.
Does not create a mission, copy SQLite, change mining or install anything.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from scripts import pilot_phase4_windows as lifecycle
from scripts.pilot_phase5_windows import read_only_preflight
from scripts.pilot_phase6b_panel import check_windows_patch
from memory_manager.phase2.local_model import PrivateHTTP
from memory_manager.phase4.native_trial import Runtime, IDENTITY
from memory_manager.phase4.windows import tunnel


def main():
    p = argparse.ArgumentParser(); p.add_argument('--approved-worker-window', action='store_true', required=True)
    p.add_argument('--egress-policy', required=True); p.add_argument('--bindings-file'); p.add_argument('--bindings-sha'); p.add_argument('--credentials', required=True); p.add_argument('--window', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); path = Path(args.credentials); st = path.lstat()
    if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size > 4096: raise PermissionError('Private supervisor identity required')
    creds = json.loads(path.read_text())
    if set(creds) != {'supervisorToken'}: raise PermissionError('Supervisor observes only; no operator/bridge credentials')
    window = Path(args.window); w = json.loads(window.read_text())
    if window.is_symlink() or window.stat().st_mode & 0o077 or w.get('closed') is not False or not 90 <= w['expires_at'] - time.time() <= 300 or w['limits'] != {'calls': 6, 'missions': 1} or w['local_token_limit'] != 98304:
        raise PermissionError('New approved bounded resource window required')
    bridge = PrivateHTTP('http://127.0.0.1:8797', creds['supervisorToken'])
    # Require the matching, independently armed service BEFORE any GPU startup.
    armed = bridge('GET', '/v1/workers/windows-hermes/epoch'); epoch = armed['epoch']
    if armed['expires_at'] != w['expires_at'] or armed.get('owned_model_gate_port') != 11436: raise PermissionError('Service/supervisor window mismatch')
    check_windows_patch(operational=True,binding_file=args.bindings_file,binding_sha=args.bindings_sha)
    read_only_preflight(owned_model_gate=lambda: bridge('GET', '/v1/workers/windows-hermes/epoch') == armed)
    deadline = w['expires_at']

    def execute(config, upstream, telemetry):
        owner = Runtime(); channel = None; sequence = 0; last = None; outcome={}
        def report(ready):
            nonlocal sequence
            sequence += 1
            return bridge('POST', '/v1/workers/windows-hermes/observe', {'epoch': epoch, 'sequence': sequence, 'endpoint_ready': ready, 'gpu': telemetry()})
        try:
            channel = subprocess.Popen(tunnel(key=IDENTITY / 'id_ed25519', known_hosts=IDENTITY / 'known_hosts', memory_port=8797), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(.5)
            if channel.poll() is not None: raise RuntimeError('Pinned tunnel failed; no adoption')
            owner.start(False)
            # Existing authenticated model gate is reached through Windows.
            # No Hermes token is copied to the observer; ready status is supplied
            # only after the owned process is running. Controller verifies API auth.
            print(json.dumps({'event': 'worker-window-open', 'expires_at': deadline, 'instruction': 'Create the DoseLab mission in Jarvis; no automatic admission.'}), flush=True)
            while time.time() < deadline - 20:
                if owner.process.poll() is not None or channel.poll() is not None: raise RuntimeError('Owned runtime/tunnel exited')
                last = report(True)
                if last.get('mission_state')=='cancelled' or last.get('executions_started') == 1 and last.get('mission_state') in {'completed', 'failed', 'paused', 'awaiting_approval'}: break
                time.sleep(2)
            outcome.update(passed=bool(last and last.get('mission_state') == 'completed'),one_human_admission_only=True,worker=last,remote_cost_chf=0)
            return outcome
        finally:
            try: report(False)
            finally:
                try:
                    owner.stop()
                    outcome['owned_runtime_cleanup']=owner.process is None and bool(owner.reports and owner.reports[-1].get('owned_process_stopped_after_close'))
                finally:
                    if channel: channel.terminate(); channel.wait(timeout=10)
                    outcome['owned_tunnel_closed']=channel is None or channel.poll() is not None

    old = sys.argv
    try:
        sys.argv = ['interactive-owned-lifecycle', '--approved', '--output', args.output]
        lifecycle.main(run_native=execute, approval_path=window,setup_proof=args.egress_policy)
    finally:
        sys.argv = old; w['closed'] = True
        with window.open('w') as f: json.dump(w, f); f.flush(); os.fsync(f.fileno())


if __name__ == '__main__': main()
