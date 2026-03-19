# Script PowerShell pour arrêter tous les services
# Usage: .\scripts\stop_all.ps1

Write-Host "🛑 Arrêt de tous les services..." -ForegroundColor Yellow

# Arrêter Daphne
Write-Host "`n🌐 Arrêt du serveur Daphne..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like "*daphne*"} | Stop-Process -Force
Write-Host "✅ Daphne arrêté" -ForegroundColor Green

# Arrêter Celery workers
Write-Host "`n⚙️ Arrêt des workers Celery..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like "*celery*"} | Stop-Process -Force
Write-Host "✅ Workers Celery arrêtés" -ForegroundColor Green

# Arrêter Flower
Write-Host "`n📊 Arrêt de Flower..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.CommandLine -like "*flower*"} | Stop-Process -Force
Write-Host "✅ Flower arrêté" -ForegroundColor Green

Write-Host "`n✅ Tous les services sont arrêtés!" -ForegroundColor Green
