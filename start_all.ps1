# ============================================================
# 智慧河长协同治理平台 · 一键启动脚本
# 功能：1) 启动本地 AI 检测服务 (127.0.0.1:8000，OpenVINO 离线推理)
#       2) 启动前端开发服务器 (http://localhost:5173，/detect 同源代理)
#       3) 健康自检：确认两个服务均就绪后才提示访问入口
# 用法：powershell -ExecutionPolicy Bypass -File start_all.ps1
#       已在运行的服务会自动跳过，不会重复启动
# ============================================================

$ErrorActionPreference = 'Stop'
# 脚本所在目录 = 项目根目录 d:\ZM\河道
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$aiDir = Join-Path $root 'river-admin\ai-training'
$feDir = Join-Path $root 'river-admin'

# ---------- 第 1 步：本地 AI 检测服务 (端口 8000) ----------
$health = $null
try {
    # 已有服务在跑就直接复用，避免端口冲突
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
} catch { }

if ($health) {
    Write-Host "[OK] AI 检测服务已在运行 -> 后端 $($health.backend) / 设备 $($health.device) / 离线 $($health.offline)" -ForegroundColor Green
} else {
    # 新开独立窗口启动检测服务，日志同时落盘到 ai-training\logs
    Write-Host '[..] 正在启动 AI 检测服务 (端口 8000)...'
    Start-Process -FilePath 'powershell' -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$aiDir'; python services/detect_server.py --port 8000 *>&1 | Tee-Object -FilePath logs\detect-server.log -Append"
    ) | Out-Null

    # 轮询健康检查，最多等 30 秒（模型加载需要几秒）
    $ready = $false
    foreach ($i in 1..60) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
            $ready = $true
            break
        } catch { }
    }
    if ($ready) {
        Write-Host "[OK] AI 检测服务已就绪 -> 后端 $($health.backend) / 设备 $($health.device) / 模型 $($health.weights)" -ForegroundColor Green
    } else {
        Write-Host '[FAIL] AI 检测服务 30 秒内未就绪，请查看 ai-training\logs\detect-server.log' -ForegroundColor Red
        exit 1
    }
}

# ---------- 第 2 步：前端开发服务器 (端口 5173) ----------
$feConn = Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue
if ($feConn) {
    Write-Host '[OK] 前端已在运行 -> http://localhost:5173' -ForegroundColor Green
} else {
    Write-Host '[..] 正在启动前端开发服务器 (端口 5173)...'
    Start-Process -FilePath 'powershell' -ArgumentList @(
        '-NoExit', '-Command',
        "cd '$feDir'; npm run dev"
    ) | Out-Null

    # 轮询端口监听，最多等 30 秒
    $feReady = $false
    foreach ($i in 1..60) {
        Start-Sleep -Milliseconds 500
        $feConn = Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue
        if ($feConn) { $feReady = $true; break }
    }
    if ($feReady) {
        Write-Host '[OK] 前端已启动 -> http://localhost:5173' -ForegroundColor Green
    } else {
        Write-Host '[FAIL] 前端 30 秒内未就绪，请检查是否已执行 npm install' -ForegroundColor Red
        exit 1
    }
}

# ---------- 第 3 步：启动完成，输出访问入口 ----------
Write-Host ''
Write-Host '================ 平台已就绪 ================' -ForegroundColor Cyan
Write-Host '  管理后台 : http://localhost:5173'
Write-Host '  AI 目标检测 : http://localhost:5173/ai/detection'
Write-Host '  数据大屏 : http://localhost:5173/large-screen'
Write-Host '============================================' -ForegroundColor Cyan
