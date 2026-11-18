# PREPARED ONLY: dedicated account/profile and ACLs. Requires separate explicit approval.
param([switch]$Approved,[Parameter(Mandatory=$true)][string]$PublicKeyFile)
$ErrorActionPreference='Stop'
if(-not $Approved){throw 'Explicit account/ACL approval required'}
if($env:COMPUTERNAME -ne 'GAMER'){throw 'Approved GAMER machine only'}
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Provisioning requires an administrator'}
if(Get-LocalUser -Name hermeslab -ErrorAction SilentlyContinue){throw 'Existing account preserved; review required'}
$root='C:\JarvisHermesLab'
if(Test-Path $root){throw 'Existing laboratory preserved; review required'}
$key=Get-Content -LiteralPath $PublicKeyFile -Raw
if($key.Trim() -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?$'){throw 'Single reviewed public key required'}
# Ephemeral random password, never supplied as an argument, printed or saved. SSH key authentication only.
$bytes=New-Object byte[] 32
$rng=[Security.Cryptography.RandomNumberGenerator]::Create();$rng.GetBytes($bytes);$rng.Dispose()
$password=ConvertTo-SecureString ([Convert]::ToBase64String($bytes)+'!aA9') -AsPlainText -Force
[Array]::Clear($bytes,0,$bytes.Length)
$user=New-LocalUser -Name hermeslab -Password $password -Description 'JARVIS synthetic Hermes laboratory'
$users=(Get-LocalGroup -SID 'S-1-5-32-545').Name
if(-not (Get-LocalGroupMember -Group $users | Where-Object {$_.SID -eq $user.SID})) { Add-LocalGroupMember -Group $users -Member hermeslab }
$password.Dispose()
$sid=$user.SID.Value
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class JarvisProfile {
 [DllImport("userenv.dll", CharSet=CharSet.Unicode)]
 public static extern int CreateProfile(string sid,string user,StringBuilder path,uint size);
}
'@
$profile=New-Object Text.StringBuilder 260
if([JarvisProfile]::CreateProfile($sid,'hermeslab',$profile,260) -ne 0){throw 'Profile creation failed; preserve account for review'}
function PrivateAcl([string]$Path,[string]$Rights) {
 & icacls.exe $Path /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' ('*'+$sid+':(OI)(CI)'+$Rights) | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Laboratory ACL failure'}
}
New-Item -ItemType Directory $root | Out-Null
PrivateAcl $root 'RX'
foreach($name in @('app','hermes-agent','runtime-staging','identity','runs','staging')) {
 $folder=Join-Path $root $name
 New-Item -ItemType Directory $folder | Out-Null
 PrivateAcl $folder $(if($name -eq 'runs'){'M'}else{'RX'})
}
# The installer owns runtime/python/code; the model identity receives read/execute only.
$ssh=Join-Path $profile.ToString() '.ssh'
New-Item -ItemType Directory $ssh | Out-Null
PrivateAcl $ssh 'F'
$options='restrict,port-forwarding,permitopen="127.0.0.1:8643",permitopen="127.0.0.1:11434",permitlisten="127.0.0.1:8792",permitlisten="127.0.0.1:11436" '
[IO.File]::WriteAllText((Join-Path $ssh 'authorized_keys'),$options+$key.Trim()+[Environment]::NewLine,[Text.Encoding]::ASCII)
[pscustomobject]@{account='hermeslab';sid=$sid;profile=$profile.ToString();root=$root;autostart=$false} |
 ConvertTo-Json | Set-Content -LiteralPath "$root\provision-receipt.json" -Encoding UTF8
# No sshd restart/configuration, task, service, firewall, runtime, Ollama or miner action.
