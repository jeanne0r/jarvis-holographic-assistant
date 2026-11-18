"""Read-only Windows GPU telemetry over existing private SSH, never starts workloads."""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
READ_ONLY_PS = r'''$ProgressPreference='SilentlyContinue';$ErrorActionPreference='Stop';
$gpu=@(& 'C:\Windows\System32\nvidia-smi.exe' --query-gpu=name,memory.total,memory.used,driver_version,power.draw,utilization.gpu,temperature.gpu --format=csv,noheader,nounits);
$p=@(Get-Process|Where-Object{$_.Name -match '(?i)(miner|^kryptex_.+|t-rex|gminer|xmrig)'}|Select-Object -ExpandProperty Name -Unique);
[pscustomobject]@{gpu=$gpu;miner_names=$p}|ConvertTo-Json -Compress'''


def collect(host='192.0.2.96', user='codexdiag', key=None):
    key=key or os.environ.get('JARVIS_DIAGNOSTIC_KEY','/home/user/.ssh/codex_gamer_ed25519')
    address = ipaddress.ip_address(host)
    if not address.is_private or address.is_unspecified: raise ValueError('Private GPU host required')
    command = ['ssh', '-i', key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=4', '-o', 'StrictHostKeyChecking=yes',
               user + '@' + host, 'powershell.exe -NoProfile -EncodedCommand ' + base64.b64encode(READ_ONLY_PS.encode('utf-16le')).decode()]
    if os.environ.get('JARVIS_DIAGNOSTIC_KNOWN_HOSTS'):command[1:1]=['-o','UserKnownHostsFile='+os.environ['JARVIS_DIAGNOSTIC_KNOWN_HOSTS'],'-o','IdentitiesOnly=yes']
    try:
        result = subprocess.run(command, capture_output=True, timeout=8)
        if result.returncode: raise OSError('SSH probe failed')
        data = json.loads(result.stdout.decode('utf-8', errors='replace'))
        if len(data['gpu']) != 1: raise ValueError('One GPU required')
        name, total, used, driver, power, utilization, temperature = [v.strip() for v in data['gpu'][0].split(',')]
        if 'RTX 3080' not in name: raise ValueError('Unexpected GPU')
        total, used, power, utilization, temperature = map(float, (total, used, power, utilization, temperature))
        if not 0 <= used <= total <= 24576 or not 0 <= utilization <= 100 or not 0 <= power <= 500 or not 0 <= temperature <= 120: raise ValueError('Invalid GPU readings')
        return {'available': True, 'observed_at': time.time(), 'name': name, 'total_mib': total, 'used_mib': used,
                'free_mib': total - used, 'driver': driver, 'power_w': power, 'utilization': utilization,
                'temperature_c': temperature, 'miner_running': bool(data['miner_names'])}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return {'available': False, 'observed_at': time.time(), 'miner_running': None, 'error': 'ReadOnlyGPUProbeUnavailable'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--output', default='data/gpu-telemetry.json')
    args = parser.parse_args()
    destination = (ROOT / args.output).resolve()
    if not destination.is_relative_to(ROOT / 'data') or destination.suffix != '.json': raise SystemExit('Output must be a laboratory data/*.json file')
    destination.parent.mkdir(parents=True, exist_ok=True)
    while True:
        sample = collect()
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, delete=False) as out:
            os.chmod(out.name, 0o600); json.dump(sample, out)
        Path(out.name).replace(destination)
        print(json.dumps({'available': sample['available'], 'miner_running': sample['miner_running']}), flush=True)
        if not args.loop: break
        time.sleep(5)


if __name__ == '__main__': main()
