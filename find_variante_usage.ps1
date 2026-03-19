# Script pour trouver les usages de variante.QuantiteStock
$searchPath = "c:\Users\PC\Documents\Gestion_et_ventes\VenteMagazin"
$excludeDirs = @("obj", "bin")

Write-Host "Recherche des usages de variante.QuantiteStock..." -ForegroundColor Cyan

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
        
        # Chercher "variante" ou "variant" suivi de "QuantiteStock"
        if ($content -match "(variante|variant)[^;]*QuantiteStock" -and $file.Name -ne "VarianteArticle.cs") {
            $lines = Get-Content $file.FullName
            $lineNumber = 0
            
            foreach ($line in $lines) {
                $lineNumber++
                if ($line -match "(variante|variant)[^;]*QuantiteStock" -or ($line -match "QuantiteStock" -and $lines[$lineNumber-2] -match "variante")) {
                    Write-Host "`n$($file.FullName):$lineNumber" -ForegroundColor Yellow
                    Write-Host "  $line" -ForegroundColor White
                }
            }
        }
    }

Write-Host "`nRecherche terminée." -ForegroundColor Green
