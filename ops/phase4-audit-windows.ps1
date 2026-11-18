# READ ONLY: no installation, service control, ACL, firewall or registry writes.
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$os=Get-CimInstance Win32_OperatingSystem
$computer=Get-CimInstance Win32_ComputerSystem
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
$commands=@()
foreach($name in @('python.exe','python3.exe','py.exe','uv.exe','git.exe','ssh.exe','hermes.exe')) {
 $c=Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
 if($c) {
  $ver=$null
  if($name -in @('git.exe','uv.exe') -and $c.Source -and $c.Source -notmatch '\\WindowsApps\\') {
   try { $ver=(& $c.Source --version 2>$null | Select-Object -First 1) } catch { $ver='probe_failed' }
  }
  $commands+=@{name=$name;path=$c.Source;version=$ver;store_alias=($c.Source -match '\\WindowsApps\\')}
 }
}
$models=@()
$store='C:\Users\winuser\.ollama\models'
if(Test-Path "$store\manifests") {
 foreach($file in Get-ChildItem "$store\manifests" -File -Recurse) {
  $manifest=Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
  $bytes=0L;$missing=0
  foreach($layer in @($manifest.layers)+@($manifest.config)) {
   if($layer.digest -match '^sha256:[a-f0-9]{64}$') {
    $blob=Join-Path "$store\blobs" ($layer.digest -replace ':','-')
    if(Test-Path -LiteralPath $blob){$bytes+=(Get-Item -LiteralPath $blob).Length}else{$missing++}
   } else {$missing++}
  }
  $models+=@{manifest=$file.FullName.Substring(($store+'\manifests\').Length);digest=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower();blob_bytes=$bytes;missing_blobs=$missing}
 }
}
$exe='C:\Users\winuser\AppData\Local\Programs\Ollama\ollama.exe'
$ollama=$null
if(Test-Path $exe){$item=Get-Item $exe;$ollama=@{path=$exe;file_version=$item.VersionInfo.FileVersion;cli_version=(& $exe --version 2>$null | Out-String).Trim()}}
$sshd=Get-Service sshd -ErrorAction SilentlyContinue
$groups=@($identity.Groups | ForEach-Object {$_.Value})
$processes=@(Get-Process | Select-Object -ExpandProperty Name)
$kryptexInstalled=(Test-Path 'C:\Program Files\Kryptex') -or (Test-Path 'C:\Users\winuser\AppData\Local\Programs\kryptex-app')
$sshdConfig='C:\ProgramData\ssh\sshd_config'
$sshPolicy=@()
try { $sshPolicy=@(Get-Content $sshdConfig | Where-Object {$_ -match '^\s*(Match|AllowTcpForwarding|GatewayPorts|PermitOpen|PermitListen|PasswordAuthentication|PubkeyAuthentication|AllowUsers|DenyUsers)\b'} | ForEach-Object {$_ -replace '(?i)(AllowUsers|DenyUsers|Match User).*','$1 [redacted]'}) } catch {$sshPolicy=@('unreadable')}
[pscustomobject]@{
 observed_at_utc=[DateTime]::UtcNow.ToString('o')
 windows=@{caption=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}
 ram=@{physical_bytes=[int64]$computer.TotalPhysicalMemory;available_bytes=[int64]$os.FreePhysicalMemory*1024;visible_bytes=[int64]$os.TotalVisibleMemorySize*1024}
 disks=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {@{drive=$_.DeviceID;size_bytes=[int64]$_.Size;free_bytes=[int64]$_.FreeSpace}})
 account=@{elevated_admin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);admin_group_in_token=($groups -contains 'S-1-5-32-544');hermeslab_account_exists=[bool](Get-LocalUser -Name hermeslab -ErrorAction SilentlyContinue)}
 openssh=@{present=[bool]$sshd;status=if($sshd){[string]$sshd.Status}else{$null};policy_lines=$sshPolicy}
 commands=$commands;ollama=$ollama;model_store=$store;models=$models
 listeners=@(Get-NetTCPConnection -State Listen | Where-Object {$_.LocalPort -in @(11434,8643,11436,8792)} | ForEach-Object {@{address=$_.LocalAddress;port=$_.LocalPort}})
 gpu=@(& 'C:\Windows\System32\nvidia-smi.exe' --query-gpu=name,memory.total,memory.used,driver_version,power.draw,utilization.gpu,temperature.gpu --format=csv,noheader,nounits)
 kryptex=@{installed_path_detected=$kryptexInstalled;ui_running=[bool]($processes -match '^kryptex$');miners=@($processes | Where-Object {$_ -match '(?i)(miner|^kryptex_.+|t-rex|gminer|xmrig)'} | Select-Object -Unique)}
} | ConvertTo-Json -Depth 8 -Compress
