# Tail job: wait for the training pipeline to finish, then run the full self-check
$ErrorActionPreference = 'Continue'
# 用脚本自身位置推导根目录，避免脚本文件内出现中文路径被按 GBK 解析
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

Log 'Waiting for the training pipeline (auto_train_pipeline.py) and service switch to finish...'
while ($true) {
    $python = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'auto_train_pipeline' }).Count
    $switch = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -match 'await_training_and_switch' }).Count
    if ($python -eq 0 -and $switch -eq 0) { break }
    Start-Sleep -Seconds 60
}
Log 'Pipeline finished. Waiting for detect server health...'

# The pipeline restarts detect_server; wait until it answers /health
$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10
        Log "health ok: model=$($h.model) offline=$($h.offline)"
        $healthy = $true
        break
    } catch {
        Start-Sleep -Seconds 5
    }
}
if (-not $healthy) { Log 'WARN: detect server not healthy before self-check' }
Log 'Running self-check...'

Push-Location $root
python scripts/self_check.py 2>&1 | Tee-Object -FilePath (Join-Path $logDir 'self_check.log')
$selfCheckExit = $LASTEXITCODE
Pop-Location

Log "self_check.py exit code: $selfCheckExit"

# Browser end-to-end check (ESM 不认 NODE_PATH，需把脚本放到含 node_modules 的目录再执行)
$env:NODE_PATH = 'D:\Systemp\Temp\pwtest\node_modules'
$toolDir = Split-Path -Parent $env:NODE_PATH
if (Test-Path (Join-Path $env:NODE_PATH 'playwright-core')) {
    Log 'Running browser end-to-end check...'
    $checkScript = Join-Path $toolDir 'browser_check.mjs'
    Copy-Item (Join-Path $root 'scripts\browser_check.mjs') $checkScript -Force
    Push-Location $toolDir
    node $checkScript 2>&1 |
        Tee-Object -FilePath (Join-Path $logDir 'browser_check.log')
    Pop-Location
    Log "browser_check.mjs exit code: $LASTEXITCODE"
} else {
    Log 'playwright-core not found, skip browser check'
}

Log 'ALL DONE'
