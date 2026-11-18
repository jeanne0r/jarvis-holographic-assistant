"""Private token files: preserve POSIX checks, explicitly attest Windows DACLs."""
import json
import os
from pathlib import Path
import subprocess

ACL_SCRIPT = r'''
$ErrorActionPreference='Stop';$p=$env:JARVIS_TOKEN_PATH;
$f=Get-Item -LiteralPath $p;
$a=Get-Acl -LiteralPath $p;
[pscustomobject]@{
 protected=$a.AreAccessRulesProtected;
 reparse=[bool]($f.Attributes -band [IO.FileAttributes]::ReparsePoint);
 current_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;
 owner_sid=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value;
 allow_sids=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) |
 Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Value})
}|ConvertTo-Json -Compress
'''


def check_acl(value):
    trusted = {'S-1-5-18', 'S-1-5-32-544', value.get('current_sid')}
    if (not isinstance(value.get('current_sid'), str) or value.get('protected') is not True
            or value.get('reparse') is not False or value.get('owner_sid') not in trusted
            or not isinstance(value.get('allow_sids'), list) or not value['allow_sids']
            or any(sid not in trusted for sid in value['allow_sids'])):
        raise PermissionError('Private protected token DACL required')


def windows_acl(path):
    system = os.environ.get('SystemRoot', r'C:\Windows')
    env = {'SystemRoot': system, 'PATH': system + r'\System32', 'JARVIS_TOKEN_PATH': str(path)}
    command = [str(Path(system) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
               '-NoProfile', '-NonInteractive', '-Command',
               '& ([scriptblock]::Create([Console]::In.ReadToEnd()))']
    result = subprocess.run(command, input=ACL_SCRIPT.encode(), env=env,
                            capture_output=True, timeout=5)
    if result.returncode or len(result.stdout) > 64000:
        raise PermissionError('Token DACL verification unavailable')
    return json.loads(result.stdout.decode('utf-8'))


def load_token(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink(): raise PermissionError('Private regular token file required')
    if os.name == 'nt':
        check_acl(windows_acl(path))
    elif path.stat().st_mode & 0o077:
        raise PermissionError('Private token mode required')
    token = path.read_text().strip()
    if not 32 <= len(token) <= 512 or any(c.isspace() for c in token):
        raise ValueError('Invalid private token')
    return token
