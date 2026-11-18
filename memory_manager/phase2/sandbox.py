"""Offline OS sandbox for trusted test execution; no Codex/model invocation."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile


def run(workspace, command, *, seconds=5):
    if not shutil.which('bwrap'): raise RuntimeError('OS isolation unavailable; execution denied')
    if not 0 < seconds <= 15 or not command or command[0] not in {'/usr/bin/python3', '/usr/bin/node', '/usr/bin/true'}:
        raise PermissionError('Offline executor command policy')
    root = Path(workspace).resolve()
    if not root.is_dir(): raise ValueError('Isolated workspace required')
    args = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
    for path in ['/usr', '/bin', '/lib', '/lib64']:
        if Path(path).exists(): args += ['--ro-bind', path, path]
    args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/home', '--dir', '/home/worker',
             '--bind', str(root), '/workspace', '--chdir', '/workspace', '--setenv', 'HOME', '/home/worker',
             '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8', '--', *command]
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    with tempfile.TemporaryFile() as output:
        process = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                 timeout=seconds, env={'PATH': '/usr/bin:/bin'}, preexec_fn=limits)
        output.seek(0)
        raw = output.read(65537)
        if len(raw) > 65536: raise ValueError('Executor output limit')
        return {'exit_code': process.returncode, 'output': raw.decode(errors='replace'), 'network': 'denied', 'home': 'isolated'}


def codex_proposal(mission_id, objective):
    if not isinstance(objective, str) or not 1 <= len(objective) <= 2000: raise ValueError('Development objective limit')
    return {'mission_id': mission_id, 'objective': objective, 'executor': 'codex-isolated',
            'state': 'awaiting_approval', 'remote_budget_chf': 0,
            'requirements': ['dedicated_checkout', 'isolated_home', 'no_production_secrets', 'brokered_model_access', 'explicit_api_budget'],
            'executed': False, 'production_deployment': False}
