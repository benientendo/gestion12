# Script pour configurer Redis dans WSL et créer le port forwarding
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CONFIGURATION REDIS WSL → WINDOWS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Obtenir l'IP de WSL
Write-Host "`n[1/4] Obtention de l'IP WSL..." -ForegroundColor Yellow
$wslIp = (wsl hostname -I).Trim()
Write-Host "IP WSL: $wslIp" -ForegroundColor Green

# 2. Vérifier que Redis tourne dans WSL
Write-Host "`n[2/4] Verification de Redis dans WSL..." -ForegroundColor Yellow
$redisPing = wsl redis-cli ping
if ($redisPing -eq "PONG") {
    Write-Host "Redis fonctionne dans WSL!" -ForegroundColor Green
} else {
    Write-Host "ERREUR: Redis ne repond pas dans WSL" -ForegroundColor Red
    Write-Host "Demarrage de Redis..." -ForegroundColor Yellow
    wsl sudo service redis-server start
    Start-Sleep -Seconds 2
}

# 3. Créer le port forwarding (nécessite admin)
Write-Host "`n[3/4] Creation du port forwarding..." -ForegroundColor Yellow
Write-Host "Windows:6379 → WSL:6379" -ForegroundColor Cyan

# Supprimer les anciennes règles si elles existent
netsh interface portproxy delete v4tov4 listenport=6379 listenaddress=0.0.0.0 2>$null

# Créer la nouvelle règle
try {
    netsh interface portproxy add v4tov4 listenport=6379 listenaddress=0.0.0.0 connectport=6379 connectaddress=$wslIp
    Write-Host "Port forwarding cree avec succes!" -ForegroundColor Green
} catch {
    Write-Host "ERREUR: Impossible de creer le port forwarding" -ForegroundColor Red
    Write-Host "Relancez PowerShell en mode Administrateur" -ForegroundColor Yellow
    exit 1
}

# 4. Tester la connexion
Write-Host "`n[4/4] Test de connexion depuis Windows..." -ForegroundColor Yellow
$testResult = python test_redis.py

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  CONFIGURATION TERMINEE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nRedis est maintenant accessible sur:" -ForegroundColor White
Write-Host "  127.0.0.1:6379" -ForegroundColor Green
Write-Host "`nPour voir les port forwarding actifs:" -ForegroundColor White
Write-Host "  netsh interface portproxy show all" -ForegroundColor Cyan
