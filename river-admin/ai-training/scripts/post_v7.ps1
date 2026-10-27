# post_v7.ps1 - auto actions after v7 training pipeline finishes.
# Flow: wait pipeline exit -> check gates -> if PASS: convert latest labels,
#       backup JSONs, publish weights, export ONNX, restart detect server,
#       restart X-AnyLabeling. All paths derived from $PSScriptRoot (no CJK literals).
$ErrorActionPreference = 'Continue'
$ai = Split-Path $PSScriptRoot -Parent
$webcap = Join-Path $ai 'datasets\handheld-bottles\images\webcap'
function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Write-Output $line
  Add-Content -Path (Join-Path $PSScriptRoot 'post_v7.log') -Value $line -Encoding utf8
}
function Emit($title, $kind) {
  $ev = @{ t = (Get-Date -Format 'HH:mm:ss'); title = $title; kind = $kind } | ConvertTo-Json -Compress
  $logDir = Join-Path $ai 'logs'
  if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
  Add-Content -Path (Join-Path $logDir 'events-v7.jsonl') -Value $ev -Encoding utf8
}

# 1) wait for the v7 pipeline process to exit
Log 'waiting for v7 pipeline to finish...'
while (Get-Process -Id 20412 -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
Log 'pipeline exited'
Emit 'v7 train pipeline finished' 'info'

# 2) gates result (ASCII markers only)
$report = Join-Path $PSScriptRoot 'v7_gates_report.txt'
if (-not (Test-Path $report)) { Log 'gates report missing, abort'; Emit 'v7 gates report missing' 'error'; exit 1 }
$lines = Get-Content $report -Encoding utf8
$lines | ForEach-Object { Log ("gates: " + $_) }
$last = $lines | Select-Object -Last 1
if ($last -notmatch 'PASS') { Log 'gates FAILED, keep v6 weights'; Emit 'v7 gates FAILED, keep v6' 'error'; exit 1 }
Emit 'v7 gates PASSED, publishing' 'ok'

# 3) convert latest manual corrections + backup webcap JSONs
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$conv = & python (Join-Path $ai 'scripts\convert_xal_labels.py') 2>&1
$conv | ForEach-Object { Log ("convert: " + $_) }
$bk = Join-Path $ai 'datasets\handheld-bottles\json-backup-before-v7'
if (-not (Test-Path $bk)) {
  Copy-Item $webcap $bk -Recurse
  Log ("webcap JSONs backed up to " + $bk)
}

# 4) publish weights + export ONNX (imgsz=640 baked in)
Copy-Item (Join-Path $ai 'models\plastic-bottle-near.pt') (Join-Path $ai 'models\plastic-bottle-near-v6.pt') -Force
Copy-Item (Join-Path $ai 'runs\detect\handheld-v7\weights\best.pt') (Join-Path $ai 'models\plastic-bottle-near.pt') -Force
Log 'v7 best.pt published to models/plastic-bottle-near.pt'
$expCode = '
from ultralytics import YOLO
m = YOLO(r"' + (Join-Path $ai 'models\plastic-bottle-near.pt') + '")
print("EXPORTED:", m.export(format="onnx", imgsz=640, simplify=True))
'
$exp = & python -c $expCode 2>&1
$exp | ForEach-Object { Log ("export: " + $_) }
if (-not (Test-Path (Join-Path $ai 'models\plastic-bottle-near.onnx'))) { Log 'ONNX export missing, abort'; Emit 'v7 onnx export failed' 'error'; exit 1 }
Emit 'v7 weights + ONNX published' 'ok'

# 5) restart detect server (port 8000)
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force; Log ("old detect server killed pid=" + $conn.OwningProcess) }
Start-Sleep -Seconds 1
Start-Process -FilePath python -ArgumentList 'services\detect_server.py' -WorkingDirectory $ai -WindowStyle Hidden
Start-Sleep -Seconds 20
Log 'detect server restarted'
Emit 'v7 detect server restarted' 'ok'

# 6) restart X-AnyLabeling so it picks up the new ONNX
Get-Process -Name 'X-AnyLabeling' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Start-Process -FilePath (Join-Path $env:LOCALAPPDATA 'Programs\X-AnyLabeling\X-AnyLabeling.exe')
Start-Sleep -Seconds 15
Log 'X-AnyLabeling restarted'
Emit 'v7 deployed, X-AnyLabeling restarted' 'ok'
exit 0
