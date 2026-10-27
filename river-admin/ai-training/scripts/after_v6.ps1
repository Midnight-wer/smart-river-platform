# after_v6.ps1 — 等 v6 训练退出 -> 双门禁 -> 达标发布 -> 导出 -> 重启服务 -> 自检
# 门禁策略（用户明确手持优先）：手持召回>=0.85 硬门禁；河面 mAP50>=0.80 且误报<=10，河面召回仅报告
$ErrorActionPreference = 'Continue'
$root = 'd:\ZM\河道\river-admin\ai-training'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Write-Host "等待 v6 训练完成..."
while ($true) {
    Start-Sleep -Seconds 30
    $train = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_handheld_v6' }
    if (-not $train) { break }
    Write-Host ("  训练中 {0}" -f (Get-Date -Format HH:mm:ss))
}
Write-Host "训练进程已退出"

$best = Get-ChildItem "$root\runs\detect\handheld-v6\weights\best.pt" -ErrorAction SilentlyContinue
if (-not $best) { Write-Host 'FAIL: no best.pt' | Set-Content "$root\logs\gate-v6.txt"; exit 2 }

Write-Host '=== 门禁A: eval_all_model（河面回归）==='
python "$root\scripts\eval_all_model.py" --weights $best.FullName > "$root\logs\eval-v6-all.log" 2>&1
Get-Content "$root\logs\eval-v6-all.log" -Tail 8
$gateA = $LASTEXITCODE

Write-Host '=== 门禁B: eval_handheld（手持专项）==='
python "$root\scripts\eval_handheld.py" --weights $best.FullName > "$root\logs\eval-v6-handheld.log" 2>&1
Get-Content "$root\logs\eval-v6-handheld.log" -Tail 6
$gateB = $LASTEXITCODE

$allLog = Get-Content "$root\logs\eval-v6-all.log" -Raw -ErrorAction SilentlyContinue
$mapOk = $allLog -match 'mAP50=0\.[89]'
$fpVal = if ($allLog -match '误报 (\d+)/699') { [int]$Matches[1] } else { 99 }
if ($gateA -ne 0 -and -not ($mapOk -and $fpVal -le 10)) {
    Write-Host "FAIL: gateA (mAP50门禁/误报=$fpVal)" | Set-Content "$root\logs\gate-v6.txt"
    exit 2
}
if ($gateB -ne 0) {
    Write-Host 'FAIL: gateB 手持召回<0.85' | Set-Content "$root\logs\gate-v6.txt"
    exit 2
}

Copy-Item "$root\models\plastic-bottle-near.pt" "$root\models\plastic-bottle-handheld-v1.pt" -Force
Copy-Item $best.FullName "$root\models\plastic-bottle-near.pt" -Force
Write-Host "已发布 v6 权重"

python "$root\scripts\export_onnx.py" --weights "$root\models\plastic-bottle-near.pt" --imgsz 640 --output "$root\models\plastic-bottle-near.onnx" > "$root\logs\export-v6.log" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host 'FAIL: export' | Set-Content "$root\logs\gate-v6.txt"; exit 2 }

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'detect_server' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
Start-Process python -ArgumentList 'services/detect_server.py','--port','8000' -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput "$root\logs\detect-server.log" -RedirectStandardError "$root\logs\detect-server.err.log"
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 4
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 8 | Out-Null; $ok = $true; break } catch { }
}
if (-not $ok) { Write-Host 'FAIL: restart' | Set-Content "$root\logs\gate-v6.txt"; exit 2 }

python "$root\scripts\self_check.py" > "$root\logs\selfcheck-v6.log" 2>&1
Get-Content "$root\logs\selfcheck-v6.log" -Tail 5
Set-Content "$root\logs\gate-v6.txt" 'SUCCESS: v6 已发布上线'
Write-Host 'ALL DONE'
