# PREPARED ONLY. Install a reviewed, offline-source bundle after explicit approval.
# Does not create accounts, ACLs, firewall rules, tasks, Ollama processes or agent runs.
param([switch]$Approved,[Parameter(Mandatory=$true)][string]$UvExe)
$ErrorActionPreference='Stop'
if(-not $Approved){throw 'Explicit installation approval required'}
if($env:COMPUTERNAME -ne 'GAMER'){throw 'Approved GAMER machine only'}
$root='C:\JarvisHermesLab'
$source=Join-Path $root 'hermes-agent'
$pin='4959268e312a21a361f248e49030d5f5df3984d5'
$manifest=Join-Path $root 'source-manifest.json'
if(-not (Test-Path $manifest)){throw 'Reviewed source manifest required before installation'}
$m=Get-Content $manifest -Raw | ConvertFrom-Json
if($m.commit -ne $pin){throw 'Pinned Hermes source required'}
if(@($m.files).Count -eq 0){throw 'Complete source manifest required'}
# Every source file must be supplied by the reviewed Git archive and checked here.
foreach($file in $m.files) {
 $path=[IO.Path]::GetFullPath((Join-Path $source $file.path))
 if(-not $path.StartsWith($source+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source path escape'}
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -ne $file.sha256){throw 'Source checksum mismatch'}
}
if(Test-Path "$root\runtime"){throw 'Existing environment preserved; never overwrite'}
if((Get-PSDrive C).Free -lt 8GB){throw '8 GiB free required'}
if(-not (Test-Path -LiteralPath $UvExe)){throw 'Approved uv 0.13.8 executable must be staged first'}
if((& $UvExe --version) -notmatch '^uv 0\.13\.8\b'){throw 'Pinned uv required'}
$env:UV_CACHE_DIR="$root\staging\cache"
$env:UV_PYTHON_INSTALL_DIR="$root\python"
$env:UV_PROJECT_ENVIRONMENT="$root\runtime"
& $UvExe sync --project $source --locked --no-dev --extra mcp --extra sms --python 3.14.10
if($LASTEXITCODE -ne 0){throw 'Installation failed; preserve staging for diagnosis'}
& "$root\runtime\Scripts\python.exe" -I -S --version
# No shell tool, desktop, npm, setup wizard, automatic update, gateway start or task.
