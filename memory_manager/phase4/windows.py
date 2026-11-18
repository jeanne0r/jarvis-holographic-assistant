"""Inert Windows profile and private SSH topology, reusing the canonical bridge.

The existing Proxmox model gate remains authoritative for budgets. A local
Windows forwarding endpoint is not a second ledger or a memory database.
"""
import ipaddress
from pathlib import PureWindowsPath
import re
from ..phase3.lab import profile as base_profile

ROOT = PureWindowsPath('C:/JarvisHermesLab')


def profile(*, skill_candidate=False):
    cfg = base_profile(ROOT / 'identity', skill_candidate=skill_candidate)
    mcp = cfg['mcp_servers']['jarvis']
    mcp['args'][1] = 'memory_manager.phase4.mcp'
    mcp['command'] = str(ROOT / 'runtime/Scripts/python.exe')
    mcp['env']['PYTHONPATH'] = str(ROOT / 'app')
    mcp['env'].update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8:strict')
    cfg['security'] = {'allow_lazy_installs': False}
    return cfg


def tunnel(*, key, known_hosts, host='192.0.2.96', user='hermeslab', memory_port=8792):
    ip = ipaddress.ip_address(host)
    if ip.version != 4 or not ip in ipaddress.ip_network('192.0.2.0/24'):
        raise ValueError('Approved LAN host required')
    if user != 'hermeslab':
        raise PermissionError('Dedicated standard identity required')
    if not key or not known_hosts: raise ValueError('Explicit private key and pinned host key required')
    if memory_port not in (8792, 8797): raise ValueError('Existing lab or private bridge port only')
    return ['ssh', '-i', str(key), '-o', 'UserKnownHostsFile=' + str(known_hosts),
            '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
            '-o', 'ForwardAgent=no', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ConnectTimeout=4', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
            '-N', '-L', '127.0.0.1:8643:127.0.0.1:8643',
            '-L', '127.0.0.1:11435:127.0.0.1:11434',
            '-R', '127.0.0.1:8792:127.0.0.1:'+str(memory_port),
            '-R', '127.0.0.1:11436:127.0.0.1:11436', user + '@' + host]


def validate_home(value):
    path = PureWindowsPath(value)
    if path.parent != ROOT / 'runs' or not re.fullmatch(r'[a-f0-9]{32}', path.name):
        raise ValueError('Fresh host-generated Windows run home required')
    return path
