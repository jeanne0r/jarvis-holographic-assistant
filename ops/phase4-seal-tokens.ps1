# PREPARED ONLY: apply to the THREE new laboratory tokens after explicit ACL approval.
param([switch]$Approved)
$ErrorActionPreference='Stop'
if(-not $Approved){throw 'Explicit laboratory token ACL approval required'}
if($env:COMPUTERNAME -ne 'GAMER'){throw 'Approved GAMER machine only'}
$sid=(Get-LocalUser -Name hermeslab).SID.Value
foreach($name in @('memory.token','model.token','hermes.token')) {
 $p=Join-Path 'C:\JarvisHermesLab\identity' $name
 if(-not (Test-Path -LiteralPath $p -PathType Leaf)){throw 'Staged laboratory token required'}
 & icacls.exe $p /setowner '*S-1-5-32-544' | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Token ownership failure'}
 & icacls.exe $p /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' ('*'+$sid+':R') | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Token ACL failure'}
}
# No production credentials belong in this directory.
