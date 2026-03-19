# Script PowerShell pour démarrer tous les services
# Usage: .\scripts\start_all.ps1

Write-Host "🚀 Démarrage de tous les services..." -ForegroundColor Green

# Vérifier que Redis fonctionne
Write-Host "`n📡 Vérification de Redis..." -ForegroundColor Yellow
try {
    $redisTest = python -c "import redis; r = redis.Redis(); print('OK' if r.ping() else 'KO')"
    if ($redisTest -eq "OK") {
        Write-Host "✅ Redis est actif" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis ne répond pas" -ForegroundColor Red
        Write-Host "Démarrez Redis avec: docker run -d -p 6379:6379 redis:latest" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Erreur lors de la vérification de Redis" -ForegroundColor Red
    exit 1
}

# Démarrer Daphne (serveur ASGI avec WebSocket)
Write-Host "`n🌐 Démarrage du serveur Django avec WebSocket (Daphne)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; daphne -b 0.0.0.0 -p 8000 gestion_magazin.asgi:application"
Start-Sleep -Seconds 2

# Démarrer les workers Celery
Write-Host "`n⚙️ Démarrage des workers Celery..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; celery -A gestion_magazin worker --loglevel=info --concurrency=4 --pool=solo"
Start-Sleep -Seconds 2

# Démarrer Flower (monitoring)
Write-Host "`n📊 Démarrage de Flower (monitoring)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; celery -A gestion_magazin flower --port=5555"
Start-Sleep -Seconds 2

Write-Host "`n✅ Tous les services sont démarrés!" -ForegroundColor Green
Write-Host "`n📍 URLs disponibles:" -ForegroundColor Cyan
Write-Host "   - Django/WebSocket: http://localhost:8000" -ForegroundColor White
Write-Host "   - Flower (monitoring): http://localhost:5555" -ForegroundColor White
Write-Host "`n💡 Pour arrêter tous les services, fermez les fenêtres PowerShell" -ForegroundColor Yellow
