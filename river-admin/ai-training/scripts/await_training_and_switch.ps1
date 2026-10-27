# 守望：等待训练 -> 自动评估/续训 -> 导出 ONNX -> 切换本地服务 -> 冒烟验证
$ErrorActionPreference = 'Continue'
$root = 'd:\ZM\河道\river-admin\ai-training'
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 训练输出目录探测（ultralytics 会按 project/task 嵌套）
$runDirs = @(
    (Join-Path $root 'runs\plastic-bottle-yolov8n-640'),
    (Join-Path $root 'runs\detect\runs\plastic-bottle-yolov8n-640'),
    (Join-Path $root 'runs\plastic-bottle-yolov8n-640\runs\plastic-bottle-yolov8n-640')
)
$weights = $null
foreach ($d in $runDirs) {
    $p = Join-Path $d 'weights\best.pt'
    if (Test-Path $p) { $weights = $p; break }
}

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

Log '进入自动训练流水线（评估 -> 不达标自动续训 -> 达标导出 ONNX）'
Push-Location $root
python scripts/auto_train_pipeline.py --target-map50 0.70 --target-precision 0.70 --max-rounds 3 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir 'auto_train_pipeline.log')
Pop-Location

if (-not $weights) {
    foreach ($d in $runDirs) {
        $p = Join-Path $d 'weights\best.pt'
        if (Test-Path $p) { $weights = $p; break }
    }
}
if (-not $weights) {
    Log "!! 未找到自训权重，终止切换"
    exit 1
}
Log "自训权重: $weights ($([math]::Round((Get-Item $weights).Length / 1MB, 2)) MB)"

# 重启检测服务（自动优先加载自训权重）
Log '重启本地检测服务 ...'
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'detect_server' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
$proc = Start-Process python -ArgumentList 'services/detect_server.py', '--port', '8000' `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'detect-server.log') `
    -RedirectStandardError (Join-Path $logDir 'detect-server.err.log') -PassThru
Log "检测服务已启动 (pid=$($proc.Id))"
Start-Sleep -Seconds 20

# 冒烟验证
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 20
    Log "health: model=$($health.model) offline=$($health.offline)"
} catch {
    Log "!! 健康检查失败: $($_.Exception.Message)"
}

$img = Join-Path $root 'assets\probe-bottle-hand.jpg'
if (Test-Path $img) {
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($img))
    $body = @{ image = $b64; conf = 0.25 } | ConvertTo-Json -Compress
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/detect' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 90
        Log "detect: model=$($r.model) elapsed=$($r.elapsed)ms 目标数=$($r.items.Count)"
        foreach ($i in $r.items) { Log ("  {0} conf={1} center=({2},{3}) size={4}x{5}" -f $i.target, $i.confidence, $i.x, $i.y, $i.width, $i.height) }
    } catch {
        Log "!! 检测失败: $($_.Exception.Message)"
    }
}
Log '全部完成'
