"""Explicit C1 only: backed up five-file laboratory patch; never starts a runtime."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import time
import subprocess
import uuid
from scripts.pilot_existing_ollama import probe

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-c1',action='store_true',required=True)
    p.add_argument('--retry-contract',action='store_true',help='Separately approved minimal contract patch, preserving the original receipt')
    args=p.parse_args()
    manifest=json.loads((ROOT/('docs/JARVIS_2_PHASE5C_C1_THIRD_PATCH_MANIFEST.json' if args.retry_contract else 'docs/JARVIS_2_PHASE5C_PATCH_MANIFEST.json')).read_text())
    receipt=ROOT/('docs/JARVIS_2_PHASE5C_C1_THIRD_PATCH_REAL.json' if args.retry_contract else 'docs/JARVIS_2_PHASE5C_PATCH_REAL.json')
    if args.retry_contract and receipt.exists():raise FileExistsError('Never overwrite the contract deployment receipt')
    files=manifest['files']
    for row in files:
        raw=(ROOT/row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['new_sha256']:raise ValueError('Reviewed patch changed')
        compile(raw,row['path'],'exec')
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    backup=str(PureWindowsPath('C:/JarvisHermesLab/staging')/('phase5c-'+ident))
    records=[]
    # First back up and validate EVERY preimage, before any replacement.
    for i,row in enumerate(files):
        target=str(PureWindowsPath(manifest['windows_root'])/row['path'])
        old=row.get('observed_windows_base_sha256',row['base_sha256'])
        command=r"$ports=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in @(8643,11434)});if($ports.Count){throw 'Existing lab runtime; defer'};"
        if i==0:command+="New-Item -ItemType Directory -LiteralPath '"+backup+"' -ErrorAction Stop|Out-Null;"
        # New-Item supports -Path on Windows PowerShell; all paths here are fixed host-generated literals.
        command=command.replace('New-Item -ItemType Directory -LiteralPath','New-Item -ItemType Directory -Path')
        if old:
            command+="$p='"+target+"';if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '"+old+"'){throw 'Unexpected preimage'};Copy-Item -LiteralPath $p -Destination '"+backup+"\\"+str(i)+".before' -ErrorAction Stop;"
            command+="if((Get-FileHash -LiteralPath '"+backup+"\\"+str(i)+".before' -Algorithm SHA256).Hash.ToLower() -ne '"+old+"'){throw 'Backup mismatch'};"
        else:command+="if(Test-Path -LiteralPath '"+target+"'){throw 'New module already exists'};"
        command+="[pscustomobject]@{backup_verified=$true}|ConvertTo-Json -Compress"
        probe(command);records.append({'path':row['path'],'before_sha256':old,'target':target,'backup':backup+'\\'+str(i)+'.before' if old else None})
    completed=[]
    try:
        for row,record in zip(files,records):
            target=record['target'];temp=target+'.phase5c-'+ident
            # SFTP avoids Windows' command-line limit for encoded source payloads.
            probe("if(Test-Path -LiteralPath '"+temp+"'){throw 'Exclusive temporary path required'};[pscustomobject]@{free=$true}|ConvertTo-Json -Compress")
            transfer=subprocess.run(['scp','-q','-i','/home/user/.ssh/codex_gamer_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                str(ROOT/row['path']),'codexdiag@192.0.2.96:'+temp.replace('\\','/')],capture_output=True,timeout=20)
            if transfer.returncode:raise RuntimeError('Reviewed source SFTP failed; logs withheld')
            command="$p='"+target+"';$t='"+temp+"';"
            command+="if((Get-FileHash -LiteralPath $t -Algorithm SHA256).Hash.ToLower() -ne '"+row['new_sha256']+"'){throw 'Staged digest mismatch'};"
            if record['before_sha256']:
                command+="if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne '"+record['before_sha256']+"'){throw 'Concurrent source change'};[IO.File]::Replace($t,$p,'"+str(PureWindowsPath(backup)/('replaced-'+str(len(completed))+'.before'))+"');"
            else:command+="[IO.File]::Move($t,$p);"
            command+="[pscustomobject]@{sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()}|ConvertTo-Json -Compress"
            result=probe(command);completed.append(record)
            if result['sha256']!=row['new_sha256']:raise ValueError('Installed digest mismatch')
        report={'passed':True,'scope':'C1 reviewed lab patch only','id':ident,'backup_directory':backup,'files':records,'new_sha256':{r['path']:r['new_sha256'] for r in files},'runtime_started':False}
    except Exception:
        # No runtime was launched: restore only our replaced code, retaining failed sources.
        for record in reversed(completed):
            target=record['target'];failed=backup+'\\failed-'+str(records.index(record))+'.py'
            command="Move-Item -LiteralPath '"+target+"' -Destination '"+failed+"' -ErrorAction Stop;"
            if record['backup']:command+="Copy-Item -LiteralPath '"+record['backup']+"' -Destination '"+target+"' -ErrorAction Stop;"
            probe(command+"[pscustomobject]@{restored=$true}|ConvertTo-Json -Compress")
        raise
    receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'backup_directory':backup,'files':len(files),'runtime_started':False}))


if __name__=='__main__':main()
