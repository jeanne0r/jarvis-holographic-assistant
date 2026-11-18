"""Explicit worker entrypoint. No installation, daemon or startup side effect."""
import argparse
import json
from pathlib import Path
import time
from ..store import Memory, Principal
from .bridge import Bridge
from .hermes import HermesRuns
from .local_model import PrivateHTTP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--loop', action='store_true')
    args = parser.parse_args()
    config_path = Path(args.config)
    if config_path.stat().st_mode & 0o077: raise SystemExit('Worker config requires 0600')
    config = json.loads(config_path.read_text())
    if config.get('enable_live') is not True:
        raise SystemExit('Live execution disabled; approve an isolated Hermes profile first')
    # This is an operator gate, not a substitute for OS/network enforcement.
    if not config.get('isolated_profile_reviewed') or not config.get('local_egress_only_reviewed'):
        raise SystemExit('Reviewed profile and network boundaries required')
    token_path = Path(config['token_file'])
    if token_path.stat().st_mode & 0o077: raise SystemExit('Token file requires 0600')
    client = HermesRuns(PrivateHTTP(config['hermes_base_url'], token_path.read_text().strip()), config['model'], allow_live=True)
    principal = Principal(config['owner'], frozenset(config['scopes']), frozenset({'reader', 'mission_worker'}), 'hermes-dispatch-worker')
    while True:
        memory = Memory(config['database'])
        try:
            bridge = Bridge(memory, principal)
            rows = memory.db.execute("SELECT o.mission_id FROM p2_outbox o JOIN mm_missions m ON m.id=o.mission_id WHERE m.owner=? AND o.state IN ('ready','submitting','submitted','cancel_requested') ORDER BY o.created LIMIT 10", (principal.name,)).fetchall()
            for row in rows:
                try: bridge.work(client, row[0])
                except Exception as error:
                    # No upstream text, credentials or model output in worker logs.
                    print('Mission worker stopped a tick: ' + type(error).__name__, flush=True)
        finally: memory.close()
        if not args.loop: break
        time.sleep(5)


if __name__ == '__main__': main()
