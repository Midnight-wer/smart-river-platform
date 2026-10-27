# 手持瓶微调后的自动发布流水线：
# 等训练退出 -> 通用门禁(eval_all_model) + 手持门禁(eval_handheld) -> 达标发布 -> ONNX 640 -> 重启服务 -> 自检
$ErrorActionPreference = 'Continue'
$root = 'd:\ZM\河道\river-admin\ai-training'
$logDir = Join-Path $root 'logs'
$runDir = Join-Path $root 'runs\detect\plastic-bottle-hand-v3'
$weights = Join-Path $runDir 'weights\best.pt'

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }
Log '等待手持瓶微调训练退出...'
while ($true) {
    $running = @(Get-CimInstance Win32_Process |
        Where-Object { ($_.Name -eq 'yolo.exe' -or $_.Name -eq 'python.exe') -and
                       $_.CommandLine -match 'train' -and $_.CommandLine -match 'yolo' }).Count
    if ($running -eq 0) { break }
    Start-Sleep -Seconds 45
}

if (-not (Test-Path $weights)) { Log "!! best.pt 不存在: $weights"; exit 1 }
Log ("训练完成，best.pt " + [math]::Round((Get-Item $weights).Length / 1MB, 2) + " MB")

Push-Location $root
Log '[1/4] 通用门禁评测（河面/跨场景/负样本）...'
python scripts/eval_all_model.py --weights $weights 2>&1 | Tee-Object -FilePath (Join-Path $logDir 'eval_hand_all.log')
$passAll = ($LASTEXITCODE -eq 0)

Log '[2/4] 手持瓶专项门禁（召回/IoU/负样本）...'
python scripts/eval_handheld.py --weights $weights 2>&1 | Tee-Object -FilePath (Join-Path $logDir 'eval_handheld.log')
$passHand = ($LASTEXITCODE -eq 0)
Pop-Location

if (-not ($passAll -and $passHand)) {
    Log "!! 门禁未达标（通用=$passAll 手持=$passHand），保留现有模型，不发布"
    Set-Content -Path (Join-Path $logDir 'pipeline-hand-done.flag') -Value 'FAIL: 门禁未达标（通用=$passAll 手持=$passHand）'
    exit 2
}

Log '[3/4] 门禁全部通过，发布新权重...'
Copy-Item (Join-Path $root 'models\plastic-bottle-near.pt') (Join-Path $root 'models\plastic-bottle-near-hand-pre.pt') -Force
Copy-Item $weights (Join-Path $root 'models\plastic-bottle-near.pt') -Force
Log '已发布（旧权重备份为 plastic-bottle-near-hand-pre.pt）'

Push-Location $root
python scripts/export_onnx.py --weights models/plastic-bottle-near.pt --imgsz 640 --output models/plastic-bottle-near.onnx 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'export_hand_onnx.log')
Log ("ONNX 导出 exit=" + $LASTEXITCODE)
Pop-Location

Log '[4/4] 重启检测服务...'
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'detect_server' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
Start-Process python -ArgumentList 'services/detect_server.py', '--port', '8000' `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'detect-server.log') `
    -RedirectStandardError (Join-Path $logDir 'detect-server.err.log') | Out-Null
$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 5
    try {
        $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10
        Log "服务健康: model=$($h.model) device=$($h.device)"
        $healthy = $true; break
    } catch { }
}
if (-not $healthy) { Log 'WARN: 服务未恢复健康' }

if ($healthy) {
    Set-Content -Path (Join-Path $logDir 'pipeline-hand-done.flag') -Value 'SUCCESS'
} else {
    Set-Content -Path (Join-Path $logDir 'pipeline-hand-done.flag') -Value 'FAIL: 服务未恢复健康'
}

Log 'PIPELINE DONE'
