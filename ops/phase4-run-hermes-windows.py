"""Prepared bounded pilot launcher. No account creation or automatic startup."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory_manager.phase4.windows import profile, validate_home
from memory_manager.phase4.credentials import load_token
from memory_manager.phase4.job import supervise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved', action='store_true', required=True)
    parser.add_argument('--trial-id', required=True)
    parser.add_argument('--skill-candidate', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt': raise SystemExit('Windows native pilot only')
    root = Path(r'C:\JarvisHermesLab')
    who = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/whoami.exe')
    account = subprocess.check_output([who, '/user', '/fo', 'csv', '/nh']).decode(errors='replace')
    groups = subprocess.check_output([who, '/groups', '/fo', 'csv', '/nh']).decode(errors='replace')
    name = next(csv.reader(io.StringIO(account)))[0].lower()
    if not name.endswith('\\hermeslab') or 'S-1-5-32-544' in groups:
        raise SystemExit('Dedicated non-administrator account required')
    home = Path(str(validate_home(str(root / 'runs' / args.trial_id))))
    home.mkdir(mode=0o700, exist_ok=False)  # Never auto-resume an old native session.
    (home / 'config.yaml').write_text(json.dumps(profile(skill_candidate=args.skill_candidate)), encoding='utf-8')
    env = {k: os.environ[k] for k in ('SystemRoot', 'USERPROFILE', 'LOCALAPPDATA', 'TEMP', 'TMP') if k in os.environ}
    env.update(PATH=str(root / 'runtime/Scripts') + ';' + str(Path(env['SystemRoot']) / 'System32'),
               HERMES_HOME=str(home), PYTHONPATH=str(root / 'app'), PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               HERMES_NONINTERACTIVE='1', HERMES_GATEWAY_INSTALL_START_ON_LOGIN='0', HERMES_SUPERVISED_CHILD='1')
    for key, filename in [('API_SERVER_KEY', 'hermes.token'), ('LAB_MODEL_TOKEN', 'model.token')]:
        env[key] = load_token(root / 'identity' / filename)
    # No detaching, gateway install, service creation, or inherited provider keys.
    report = supervise([str(root / 'runtime/Scripts/python.exe'), '-m', 'hermes_cli.main', 'gateway', 'run'],
                       env, root / 'hermes-agent', stop_requested=lambda: (home / 'stop.requested').exists())
    (home / 'supervisor-result.json').write_text(json.dumps(report), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__': main()
