param([switch]$Approved)
# REVIEWED TEMPLATE ONLY. Not executed during phase 2 development.
# Foreground process: no installation, scheduled task, service or mining changes.
if (-not $Approved) { throw 'Explicit approval is required before starting the GPU pilot.' }
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$binary = 'C:\Users\winuser\AppData\Local\Programs\Ollama\ollama.exe'
$models = 'C:\Users\winuser\.ollama\models'
if (-not (Test-Path $binary) -or -not (Test-Path $models)) { throw 'Existing Ollama binary/model directory is missing.' }
if (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue) { throw 'Port already occupied; do not replace the existing server.' }
$miners = @(Get-Process | Where-Object { $_.Name -match '(?i)(miner|^kryptex_.+|t-rex|gminer|xmrig)' })
if ($miners.Count -gt 0) { throw 'Mining process detected; pilot deferred without stopping it.' }
$gpu = @(& 'C:\Windows\System32\nvidia-smi.exe' --query-gpu=memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits)
if ($LASTEXITCODE -ne 0 -or $gpu.Count -ne 1) { throw 'GPU telemetry unavailable.' }
$values = $gpu[0].Split(',') | ForEach-Object { [double]::Parse($_.Trim(), [Globalization.CultureInfo]::InvariantCulture) }
if (($values[0] - $values[1]) -lt 8500 -or $values[2] -ge 20) { throw 'GPU occupied; pilot deferred.' }
# Process-local environment only. Keep the server private and reuse local weights.
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = $models
Remove-Item Env:OLLAMA_API_KEY -ErrorAction SilentlyContinue
& $binary serve
