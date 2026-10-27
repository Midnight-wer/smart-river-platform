# publish_v7.ps1 - publish v7 (gates already PASS) and restart local services.
$ErrorActionPreference = 'Continue'
$ai = Split-Path $PSScriptRoot -Parent
function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Write-Output $line
  Add-Content -Path (Join-Path $PSScriptRoot 'publish_v7.log') -Value $line -Encoding utf8
}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# 1) backup v6 weights + publish v7
Copy-Item (Join-Path $ai 'models\plastic-bottle-near.pt') (Join-Path $ai 'models\plastic-bottle-near-v6.pt') -Force
Copy-Item (Join-Path $ai 'runs\detect\handheld-v7\weights\best.pt') (Join-Path $ai 'models\plastic-bottle-near.pt') -Force
Log 'v7 best.pt published'

# 2) export ONNX (imgsz 640 baked into the file)
$code = 'from ultralytics import YOLO; m = YOLO(r"' + (Join-Path $ai 'models\plastic-bottle-near.pt') + '"); print("EXPORTED:", m.export(format="onnx", imgsz=640, simplify=True))'
$exp = & python -c $code 2>&1
$exp | ForEach-Object { Log ("export: " + $_) }

# 3) restart detect server on port 8000
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force; Log ("detect server killed pid=" + $conn.OwningProcess) }
Start-Sleep -Seconds 1
Start-Process -FilePath python -ArgumentList 'services\detect_server.py' -WorkingDirectory $ai -WindowStyle Hidden
Start-Sleep -Seconds 20
$health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10 -ErrorAction SilentlyContinue
Log ("health: " + ($health | ConvertTo-Json -Compress))

# 4) restart X-AnyLabeling so it loads the new ONNX
Get-Process -Name 'X-AnyLabeling' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Start-Process -FilePath (Join-Path $env:LOCALAPPDATA 'Programs\X-AnyLabeling\X-AnyLabeling.exe')
Start-Sleep -Seconds 15
Log 'X-AnyLabeling restarted'
exit 0
