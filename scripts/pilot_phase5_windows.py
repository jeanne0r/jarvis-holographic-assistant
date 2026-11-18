"""B only, NOT authorized by A2: reuse the real Windows lifecycle with phase5 memory.

A new host-owned approval file is created only with --approved-b. No installation,
model download, mining action, or publication. Do not run until B is authorized.
"""
import argparse
import base64
import subprocess
import json
import os
from pathlib import Path
import sys
import time
import uuid
from memory_manager.phase5 import native_lab
from scripts import pilot_phase4_windows as lifecycle
from scripts.pilot_existing_ollama import remote_command
from memory_manager.phase5 import source_attestation


def read_only_preflight(*, owned_model_gate=None):
    # Refuse pre-existing controller listeners and any ambiguous Windows Hermes.
    import socket
    # Operational profile already owns its model gate. Only a trusted host
    # callback may attest that exact listener; all other bind guards remain.
    if owned_model_gate is not None and owned_model_gate() is not True:
        raise PermissionError('Existing model gate ownership not demonstrated')
    for port in ((8792,8643,11435) if owned_model_gate is not None else (8792,11436,8643,11435)):
        probe=socket.socket()
        try:probe.bind(('127.0.0.1',port))
        finally:probe.close()
    existing=lifecycle.probe("$p=@(Get-NetTCPConnection -LocalPort 8643 -State Listen -ErrorAction SilentlyContinue);[pscustomobject]@{listening=($p.Count -gt 0)}|ConvertTo-Json -Compress")
    if existing.get('listening') is not False:raise PermissionError('Existing Hermes listener: defer, never adopt or stop it')
    # Read-only revalidation of the existing Windows installation and network policy.
    checks=lifecycle.probe(r"""
$sid=(Get-LocalUser -Name hermeslab).SID.Value
$ok=$true
foreach($name in @('JarvisHermesLab-v4-egress','JarvisHermesLab-v6-egress')) {
 $r=Get-NetFirewallRule -Name $name -ErrorAction Stop
 $filter=$r|Get-NetFirewallSecurityFilter
 if($r.Enabled -ne 'True' -or $r.Action -ne 'Block' -or $r.Direction -ne 'Outbound' -or $r.Group -ne 'JarvisHermesLab-phase4' -or $filter.LocalUser -notmatch ([regex]::Escape($sid)+'[;) ]')) {$ok=$false}
}
$profiles=@(Get-NetFirewallProfile|Where-Object {$_.Enabled -ne $true})
$adapters=@(Get-NetAdapter -Physical|Where-Object {$_.Status -eq 'Up'})
$v6=@($adapters|ForEach-Object {Get-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6}|Where-Object {$_.Enabled})
[pscustomobject]@{firewall_rules_scoped=$ok;profiles_enabled=($profiles.Count -eq 0);physical_adapter_count=$adapters.Count;physical_ipv6_disabled=($v6.Count -eq 0)}|ConvertTo-Json -Compress
""")
    if (checks.get('firewall_rules_scoped') is not True or checks.get('profiles_enabled') is not True
            or checks.get('physical_adapter_count',0)<1 or checks.get('physical_ipv6_disabled') is not True):
        raise PermissionError('Fresh Windows checks differ from validated phase4; defer without changing settings')
    # Windows received a reviewed archive, not a Git checkout. Verify its pinned
    # manifest and every source file in-place without installing Git or writing files.
    source=Path(source_attestation.__file__).read_text().split("if __name__ == '__main__':")[0]
    batches=[]
    for start in range(0,25615,2500):
        code=source+"\nprint(json.dumps(verify(Path('C:/JarvisHermesLab/hermes-agent'),Path('C:/JarvisHermesLab/source-manifest.json').read_bytes(),start="+str(start)+",count=2500)))"
        encoded=base64.b64encode(code.encode()).decode()
        statement="import base64;exec(compile(base64.b64decode('"+encoded+"'),'<read-only-attestation>','exec'))"
        result=subprocess.run(remote_command(r"$ErrorActionPreference='Stop';& 'C:\JarvisHermesLab\runtime\Scripts\python.exe' -I -S -c "+"'"+statement.replace("'","''")+"'"),capture_output=True,timeout=60)
        if result.returncode:raise PermissionError('Pinned Windows archive verification failed; no runtime started')
        attestation=json.loads(result.stdout)
        if attestation.get('hermes_commit')!=source_attestation.PIN or attestation.get('total_files')!=25615 or attestation.get('source_files_verified')!=min(2500,25615-start):
            raise PermissionError('Pinned Windows source attestation incomplete')
        batches.append(attestation)
        print(json.dumps({'event':'source-batch-verified','files':sum(b['source_files_verified'] for b in batches)}),flush=True)
    checks['source_attestation']=batches
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-b',action='store_true',required=True)
    parser.add_argument('--private-state',required=True);parser.add_argument('--artifact',required=True)
    parser.add_argument('--local-token-limit',type=int,default=50000,help='Explicitly approved shared quota; default 50k cannot fit the 64k reservation')
    args=parser.parse_args()
    native_lab.check_token_limit(args.local_token_limit)
    checks=read_only_preflight()
    root=Path(__file__).resolve().parents[1];ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    folder=root/'data/phase5'/('windows-'+ident);native_lab.prepare(folder)
    (folder/'preflight.json').write_text(json.dumps(checks,indent=2)+'\n')
    window=folder/'window.json'
    now=time.time();value={'started_at':now,'expires_at':now+1200,'closed':False,'calls':0,'missions':0,'limits':{'calls':16,'missions':3},'local_token_limit':args.local_token_limit}
    with os.fdopen(os.open(window,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(value,f)
    native_lab.check_window(window)
    output='docs/JARVIS_2_PHASE5_B_WINDOWS_REAL_'+ident+'.json'
    old_args=sys.argv
    def run(config,upstream,telemetry):return native_lab.run(config,upstream,telemetry,folder=folder,private_state=args.private_state,artifact=args.artifact,local_token_limit=args.local_token_limit)
    try:
        sys.argv=['phase5-lifecycle','--approved','--output',output]
        lifecycle.main(run_native=run,approval_path=window)
    finally:
        sys.argv=old_args
        value=json.loads(window.read_text());value['closed']=True
        with window.open('w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())


if __name__=='__main__':main()
