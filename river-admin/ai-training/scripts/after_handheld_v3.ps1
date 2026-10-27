# after_handheld_v3.ps1 — 等 handheld-v3 训练退出 -> 双评测门禁 -> 发布 -> 导出 -> 重启服务 -> 自检
# 达标发布；任一门禁不达标 exit 2 保留现有 v1 模型
$ErrorActionPreference = 'Continue'
$root = 'd:\ZM\河道\river-admin\ai-training'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# 1) 等训练进程退出（python 跑 train_handheld_v3.py）
Write-Host "等待 handheld-v3 训练完成..."
while ($true) {
    Start-Sleep -Seconds 30
    $train = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_handheld_v3' }
    if (-not $train) { break }
    Write-Host ("  训练中 {0} (pid {1})" -f (Get-Date -Format HH:mm:ss), $train.ProcessId)
}
Write-Host "训练进程已退出"

# 2) 找 best.pt
$best = Get-ChildItem "$root\runs\detect\handheld-v3\weights\best.pt" -ErrorAction SilentlyContinue
if (-not $best) { Write-Host '✗ 未找到 best.pt'; exit 2 }
Write-Host "best.pt: $($best.LastWriteTime)"

# 3) 门禁 A：all 域全量评测
Write-Host '=== 门禁 A: eval_all_model ==='
python "$root\scripts\eval_all_model.py" --weights $best.FullName 2>&1 | Tee-Object "$root\logs\eval-v3-all.log"
if ($LASTEXITCODE -ne 0) { Write-Host '✗ 门禁 A 未通过，保留 v1'; exit 2 }

# 4) 门禁 B：手持专项评测
Write-Host '=== 门禁 B: eval_handheld ==='
python "$root\scripts\eval_handheld.py" --weights $best.FullName 2>&1 | Tee-Object "$root\logs\eval-v3-handheld.log"
if ($LASTEXITCODE -ne 0) { Write-Host '✗ 门禁 B 未通过，保留 v1'; exit 2 }

# 5) 发布：备份旧权重 -> 拷贝新权重
Copy-Item "$root\models\plastic-bottle-near.pt" "$root\models\plastic-bottle-handheld-v1.pt" -Force
Copy-Item $best.FullName "$root\models\plastic-bottle-near.pt" -Force
Write-Host "已发布 v3 权重（v1 备份为 plastic-bottle-handheld-v1.pt）"

# 6) 导出 ONNX（640）
python "$root\scripts\export_onnx.py" --weights "$root\models\plastic-bottle-near.pt" --imgsz 640 --output "$root\models\plastic-bottle-near.onnx" 2>&1 | Select-Object -Last 5
if ($LASTEXITCODE -ne 0) { Write-Host '✗ ONNX 导出失败'; exit 2 }

# 7) 重启检测服务
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
if (-not $ok) { Write-Host '✗ 检测服务重启失败'; exit 2 }
Write-Host '检测服务已重启'

# 8) 全量自检
python "$root\scripts\self_check.py" 2>&1 | Tee-Object "$root\logs\selfcheck-v3.log"
if ($LASTEXITCODE -ne 0) { Write-Host '✗ 自检未通过'; exit 2 }
Write-Host 'ALL PASS — v3 已上线'
