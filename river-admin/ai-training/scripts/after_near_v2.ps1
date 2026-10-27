# Tail job: wait for v2 fine-tune, evaluate -> publish -> export -> restart -> self-check
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

$runDir = Join-Path $root 'runs\detect\runs\plastic-bottle-water-v1'
$weights = Join-Path $runDir 'weights\best.pt'

Log 'Waiting for v2 fine-tune to finish...'
while ($true) {
    $running = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'yolo' -and $_.CommandLine -match 'train' }).Count
    if ($running -eq 0) { break }
    Start-Sleep -Seconds 45
}

if (-not (Test-Path $weights)) {
    Log "!! best.pt not found: $weights"
    exit 1
}
Log ("Training done. weights: " + [math]::Round((Get-Item $weights).Length / 1MB, 2) + " MB")

Push-Location $root
Log 'Evaluating v2 model...'
python scripts/eval_near_model.py --weights $weights 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'eval_v2.log')
Log "eval exit code: $LASTEXITCODE"

# 备份并发布新模型
$nearModel = Join-Path $root 'models\plastic-bottle-near.pt'
if (Test-Path $nearModel) {
    Copy-Item $nearModel (Join-Path $root 'models\plastic-bottle-near-v1.pt') -Force
}
Copy-Item $weights $nearModel -Force
Log ("Published v2 model -> " + $nearModel)

python scripts/export_onnx.py --weights $nearModel --imgsz 512 --output (Join-Path $root 'models\plastic-bottle-near.onnx') 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'export_v2_onnx.log')
Log "onnx export exit code: $LASTEXITCODE"
Pop-Location

Log 'Restarting detect server...'
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'detect_server' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
$proc = Start-Process python -ArgumentList 'services/detect_server.py', '--port', '8000' `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'detect-server.log') `
    -RedirectStandardError (Join-Path $logDir 'detect-server.err.log') -PassThru
Log "detect server pid=$($proc.Id)"

$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 5
    try {
        $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10
        Log "health ok: model=$($h.model) device=$($h.device)"
        $healthy = $true
        break
    } catch { }
}
if (-not $healthy) { Log 'WARN: detect server not healthy' }

Push-Location $root
Log 'Running self check...'
python scripts/self_check.py 2>&1 | Tee-Object -FilePath (Join-Path $logDir 'self_check.log')
Log "self_check exit code: $LASTEXITCODE"
Pop-Location

# browser check (dev server 应该在跑，没有就拉起)
$env:NODE_PATH = 'D:\Systemp\Temp\pwtest\node_modules'
$toolDir = Split-Path -Parent $env:NODE_PATH
if (Test-Path (Join-Path $env:NODE_PATH 'playwright-core')) {
    $devRunning = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -match 'vite' }).Count
    if ($devRunning -eq 0) {
        Log 'Starting Vite dev server...'
        Start-Process cmd -ArgumentList '/c', 'npm run dev' -WorkingDirectory (Join-Path $root '..') -WindowStyle Hidden
        Start-Sleep -Seconds 25
    }
    Log 'Running browser end-to-end check...'
    Copy-Item (Join-Path $root 'scripts\browser_check.mjs') (Join-Path $toolDir 'browser_check.mjs') -Force
    Push-Location $toolDir
    node (Join-Path $toolDir 'browser_check.mjs') 2>&1 |
        Tee-Object -FilePath (Join-Path $logDir 'browser_check.log')
    Pop-Location
    Log "browser_check exit code: $LASTEXITCODE"
}

Log 'ALL DONE'
