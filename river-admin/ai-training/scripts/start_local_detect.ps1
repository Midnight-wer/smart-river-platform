# 一键启动本地离线塑料瓶检测服务（不访问外网）
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/start_local_detect.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/start_local_detect.ps1 -Port 8000 -UseOnnx
param(
    [int]$Port = 8000,
    [switch]$UseOnnx
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$weights = if ($UseOnnx) {
    Join-Path $root 'models\plastic-bottle.onnx'
} else {
    Join-Path $root 'runs\plastic-bottle-yolov8n\weights\best.pt'
}

if (-not (Test-Path $weights)) {
    $fallback = Join-Path $root 'yolov8n.pt'
    if (-not (Test-Path $fallback)) {
        Write-Error "未找到模型权重：$weights`n请先训练（yolo train ...）或导出 ONNX（python scripts/export_onnx.py）"
    }
    $weights = $fallback
    Write-Host "未找到自训权重，回退使用官方权重：$weights" -ForegroundColor Yellow
}

Write-Host "启动本地离线检测服务..." -ForegroundColor Cyan
Write-Host "  权重: $weights"
Write-Host "  地址: http://127.0.0.1:$Port"
Write-Host "  前端通过 Vite 代理同源访问 /detect" -ForegroundColor DarkGray
Write-Host ""

python services/detect_server.py --port $Port --weights $weights
