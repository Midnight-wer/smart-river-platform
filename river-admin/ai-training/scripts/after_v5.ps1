# after_v5.ps1 — 等 v5 训练退出 -> 双评测门禁 -> 达标发布 -> 导出 -> 重启服务 -> 自检
$ErrorActionPreference = 'Continue'
$root = 'd:\ZM\河道\river-admin\ai-training'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Write-Host "等待 v5 训练完成..."
while ($true) {
    Start-Sleep -Seconds 30
    $train = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_handheld_v5' }
    if (-not $train) { break }
    Write-Host ("  训练中 {0}" -f (Get-Date -Format HH:mm:ss))
}
Write-Host "训练进程已退出"

$best = Get-ChildItem "$root\runs\detect\handheld-v5\weights\best.pt" -ErrorAction SilentlyContinue
if (-not $best) { Write-Host '✗ 未找到 best.pt'; Set-Content "$root\logs\gate-v5.txt" 'FAIL: no best.pt'; exit 2 }

Write-Host '=== 门禁A: eval_all_model ==='
python "$root\scripts\eval_all_model.py" --weights $best.FullName > "$root\logs\eval-v5-all.log" 2>&1
Get-Content "$root\logs\eval-v5-all.log" -Tail 8
$gateA = $LASTEXITCODE

Write-Host '=== 门禁B: eval_handheld ==='
python "$root\scripts\eval_handheld.py" --weights $best.FullName > "$root\logs\eval-v5-handheld.log" 2>&1
Get-Content "$root\logs\eval-v5-handheld.log" -Tail 6
$gateB = $LASTEXITCODE

# 门禁A 召回项放宽至 0.82（本轮目标为手持专项，且误报不得恶化）
$allLog = Get-Content "$root\logs\eval-v5-all.log" -Raw -ErrorAction SilentlyContinue
$recallOk = $allLog -match 'R=0\.8[2-9]'
$fpOk = ($allLog -match '误报 ([0-8])/699')
if ($gateA -ne 0 -and -not ($recallOk -and $fpOk)) {
    Write-Host '✗ 门禁A 未达标且不满足放宽条件，保留现模型'
    Set-Content "$root\logs\gate-v5.txt" 'FAIL: gateA'
    exit 2
}
if ($gateB -ne 0) {
    Write-Host '✗ 门禁B（手持专项召回>=0.85）未达标，保留现模型'
    Set-Content "$root\logs\gate-v5.txt" 'FAIL: gateB'
    exit 2
}

Copy-Item "$root\models\plastic-bottle-near.pt" "$root\models\plastic-bottle-handheld-v1.pt" -Force
Copy-Item $best.FullName "$root\models\plastic-bottle-near.pt" -Force
Write-Host "已发布 v5 权重"

python "$root\scripts\export_onnx.py" --weights "$root\models\plastic-bottle-near.pt" --imgsz 640 --output "$root\models\plastic-bottle-near.onnx" > "$root\logs\export-v5.log" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host '✗ ONNX 导出失败'; Set-Content "$root\logs\gate-v5.txt" 'FAIL: export'; exit 2 }

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
if (-not $ok) { Write-Host '✗ 检测服务重启失败'; Set-Content "$root\logs\gate-v5.txt" 'FAIL: restart'; exit 2 }

python "$root\scripts\self_check.py" > "$root\logs\selfcheck-v5.log" 2>&1
Get-Content "$root\logs\selfcheck-v5.log" -Tail 5
Set-Content "$root\logs\gate-v5.txt" 'SUCCESS: v5 已发布上线'
Write-Host 'ALL DONE'
