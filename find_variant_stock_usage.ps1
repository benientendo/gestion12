# Script pour trouver tous les usages de QuantiteStock dans le code MAUI
$searchPath = "c:\Users\PC\Documents\Gestion_et_ventes\VenteMagazin"
$excludeDirs = @("obj", "bin")

Write-Host "Recherche des usages de QuantiteStock dans les fichiers .cs..." -ForegroundColor Cyan

Get-ChildItem -Path $searchPath -Recurse -Filter "*.cs" | 
    Where-Object { 
        $exclude = $false
        foreach ($dir in $excludeDirs) {
            if ($_.FullName -like "*\$dir\*") {
                $exclude = $true
                break
            }
        }
        -not $exclude
    } |
    ForEach-Object {
        $file = $_
        $content = Get-Content $file.FullName -Raw
        
        # Chercher "QuantiteStock" mais pas dans VarianteArticle.cs (déjà modifié)
        if ($content -match "QuantiteStock" -and $file.Name -ne "VarianteArticle.cs") {
            $lines = Get-Content $file.FullName
            $lineNumber = 0
            
            foreach ($line in $lines) {
                $lineNumber++
                if ($line -match "QuantiteStock") {
                    Write-Host "`n$($file.FullName):$lineNumber" -ForegroundColor Yellow
                    Write-Host "  $line" -ForegroundColor White
                }
            }
        }
    }

Write-Host "`nRecherche terminée." -ForegroundColor Green
