# Tail job: wait for the universal-bottle fine-tune, evaluate -> publish -> export -> restart -> self-check
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

$runName = 'plastic-bottle-all-v1'
$runDir = Join-Path $root "runs\detect\runs\$runName"
$weights = Join-Path $runDir 'weights\best.pt'

Log 'Waiting for the fine-tune process to finish...'
while ($true) {
    $running = @(Get-CimInstance Win32_Process |
        Where-Object { ($_.Name -match 'python|yolo') -and $_.CommandLine -match 'train' }).Count
    if ($running -eq 0) { break }
    Start-Sleep -Seconds 45
}

if (-not (Test-Path $weights)) {
    Log "!! best.pt not found: $weights"
    exit 1
}
Log ("Training done. weights: " + [math]::Round((Get-Item $weights).Length / 1MB, 2) + " MB")

Push-Location $root
Log 'Evaluating the universal model (gates: mAP50 / recall / IoU / cross-scene probes)...'
python scripts/eval_all_model.py --weights $weights 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'eval_all_v1.log')
$evalCode = $LASTEXITCODE
Log "eval exit code: $evalCode"
Pop-Location

if ($evalCode -ne 0) {
    Log 'Gates NOT met - keeping the current online model, stopping here.'
    exit 2
}

Push-Location $root
$nearModel = Join-Path $root 'models\plastic-bottle-near.pt'
if (Test-Path $nearModel) {
    Copy-Item $nearModel (Join-Path $root 'models\plastic-bottle-near-v2.pt') -Force
}
Copy-Item $weights $nearModel -Force
Log ("Published model -> " + $nearModel)

python scripts/export_onnx.py --weights $nearModel --imgsz 512 --output (Join-Path $root 'models\plastic-bottle-near.onnx') 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'export_all_v1_onnx.log')
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
        Log "health ok: model=$($h.model) backend=$($h.backend) device=$($h.device)"
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

Log 'ALL DONE'
