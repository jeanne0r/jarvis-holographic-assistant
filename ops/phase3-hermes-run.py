"""Approved dedicated-host launcher. Pair with the OS limits in the runbook."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory_manager.phase3.lab import profile, trial_home
from memory_manager.phase2.hermes import HERMES_COMMIT


def wait_for_api_port(port=8643, seconds=60):
    deadline = time.monotonic() + seconds
    while True:
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
            return
        except OSError as exc:
            if exc.errno != 98:
                raise
            with socket.socket() as listener:
                listener.settimeout(1)
                if listener.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError('Existing API listener: leave it untouched') from exc
            if time.monotonic() >= deadline:
                raise RuntimeError('API port still in TIME_WAIT; retry in a new approved pilot') from exc
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved', required=True, action='store_true')
    parser.add_argument('--skill-candidate', action='store_true')
    parser.add_argument('--trial-id')
    args = parser.parse_args()
    if socket.gethostname().split('.')[0] != 'jarvis-lab':
        raise SystemExit('Dedicated jarvis-lab host required; never start on gateway host')
    lab = ROOT / 'data/phase3/prepared'
    if args.skill_candidate and not args.trial_id:
        raise SystemExit('Skill retry requires a fresh trial home; never resume the interrupted home')
    home = trial_home(lab, args.trial_id) if args.trial_id else lab / 'hermes-home'
    if not home.is_dir():
        raise SystemExit('Create the private Hermes home before applying OS write restrictions')
    source = ROOT / 'data/hermes-upstream'
    commit = subprocess.check_output(['git', '-c', 'safe.directory=' + str(source),
                                      '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != HERMES_COMMIT:
        raise SystemExit('Pinned Hermes commit required')
    expected = profile(lab, skill_candidate=args.skill_candidate)
    if json.loads((lab / ('config-skill.yaml' if args.skill_candidate else 'config.yaml')).read_text()) != expected:
        raise SystemExit('Profile changed: review required before startup')
    config = home / 'config.yaml'
    if config.exists():
        if json.loads(config.read_text()) != expected:
            raise SystemExit('Existing runtime profile differs; never overwrite it')
    else:
        with open(config, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
            json.dump(expected, out)
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HERMES_HOME': str(home),
           'PYTHONPATH': str(ROOT)}
    for variable, name in [('API_SERVER_KEY', 'hermes.token'), ('LAB_MODEL_TOKEN', 'model.token')]:
        path = lab / name
        if path.stat().st_mode & 0o077:
            raise SystemExit('Private token permissions required')
        value = path.read_text().strip()
        if len(value) < 32:
            raise SystemExit('Independent laboratory token required')
        env[variable] = value
    wait_for_api_port()
    binary = ROOT / 'data/phase3/install/venv/bin/hermes'
    os.chdir(source)
    os.execve(str(binary), [str(binary), 'gateway', 'run'], env)


if __name__ == '__main__':
    main()
