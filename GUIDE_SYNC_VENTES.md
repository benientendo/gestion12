# 🔄 GUIDE - Synchronisation de Ventes MAUI

## 📋 Vue d'Ensemble

L'endpoint `/api/v2/simple/ventes/sync/` permet de synchroniser plusieurs ventes en une seule requête depuis MAUI vers Django.

## 🎯 Endpoint

```
POST /api/v2/simple/ventes/sync/
```

## 🔑 Authentification

**Header requis :**
```
X-Device-Serial: 0a1badae951f8473
```

Le numéro de série identifie automatiquement :
- ✅ Le terminal MAUI
- ✅ La boutique associée
- ✅ Les articles disponibles

## 📤 Format de Requête

### Structure JSON

```json
[
  {
    "numero_facture": "VENTE-001",
    "mode_paiement": "CASH",
    "paye": true,
    "lignes": [
      {
        "article_id": 6,
        "quantite": 1,
        "prix_unitaire": 40000
      }
    ]
  },
  {
    "numero_facture": "VENTE-002",
    "mode_paiement": "MOBILE_MONEY",
    "paye": true,
    "lignes": [
      {
        "article_id": 7,
        "quantite": 2,
        "prix_unitaire": 25000
      }
    ]
  }
]
```

### Champs Vente

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `numero_facture` | string | Non* | Numéro de facture (généré auto si absent) |
| `mode_paiement` | string | Non | "CASH", "MOBILE_MONEY", "CARTE" (défaut: "CASH") |
| `paye` | boolean | Non | Statut de paiement (défaut: true) |
| `lignes` | array | **Oui** | Tableau des lignes de vente |

*Si absent, généré automatiquement : `VENTE-{boutique_id}-{timestamp}-{index}`

### Champs Ligne de Vente

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `article_id` | integer | **Oui** | ID de l'article |
| `quantite` | integer | Non | Quantité (défaut: 1) |
| `prix_unitaire` | decimal | Non | Prix unitaire (défaut: prix_vente de l'article) |

## 📥 Format de Réponse

### Succès (201 Created)

```json
{
  "success": true,
  "message": "2 vente(s) synchronisée(s) avec succès",
  "boutique_id": 2,
  "boutique_nom": "Ma Boutique",
  "terminal": "Terminal messie vanza",
  "statistiques": {
    "total_envoyees": 2,
    "reussies": 2,
    "erreurs": 0
  },
  "ventes_creees": [
    {
      "numero_facture": "VENTE-001",
      "montant_total": "40000.00",
      "lignes": [
        {
          "article_nom": "Samsung S24",
          "quantite": 1,
          "prix_unitaire": "40000.00",
          "sous_total": "40000.00"
        }
      ]
    }
  ],
  "ventes_erreurs": null
}
```

### Succès Partiel (201 Created)

```json
{
  "success": true,
  "message": "1 vente(s) synchronisée(s) avec succès",
  "statistiques": {
    "total_envoyees": 2,
    "reussies": 1,
    "erreurs": 1
  },
  "ventes_creees": [...],
  "ventes_erreurs": [
    {
      "index": 2,
      "numero_facture": "VENTE-002",
      "erreur": "Stock insuffisant pour Article X"
    }
  ]
}
```

### Erreurs

#### 400 - Numéro de série manquant
```json
{
  "error": "Numéro de série du terminal requis dans les headers",
  "code": "MISSING_SERIAL",
  "header_required": "X-Device-Serial"
}
```

#### 400 - Format invalide
```json
{
  "error": "Format invalide: un tableau de ventes est attendu",
  "code": "INVALID_FORMAT"
}
```

#### 404 - Terminal non trouvé
```json
{
  "error": "Terminal non trouvé ou inactif",
  "code": "TERMINAL_NOT_FOUND"
}
```

## 🔧 Fonctionnalités Automatiques

### 1. Génération Numéro de Facture
Si `numero_facture` est absent, il est généré automatiquement :
```
VENTE-{boutique_id}-{timestamp}-{index}
Exemple: VENTE-2-20251029024500-0
```

### 2. Détection de Doublons
Si une vente avec le même `numero_facture` existe déjà :
- ✅ La vente est ignorée
- ✅ Ajoutée dans `ventes_erreurs`
- ✅ Les autres ventes continuent d'être traitées

### 3. Mise à Jour Stock
Pour chaque ligne de vente :
- ✅ Stock décrémenté automatiquement
- ✅ Vérification stock disponible
- ✅ Création MouvementStock pour traçabilité

### 4. Calcul Montant Total
Le montant total est calculé automatiquement :
```
montant_total = Σ (prix_unitaire × quantite)
```

### 5. Rollback en Cas d'Erreur
Si une ligne échoue :
- ✅ La vente entière est supprimée
- ✅ Le stock n'est pas modifié
- ✅ Erreur retournée dans `ventes_erreurs`

## 🧪 Tests

### Test avec curl

```bash
curl -X POST http://10.28.176.224:8000/api/v2/simple/ventes/sync/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: 0a1badae951f8473" \
  -d '[
    {
      "numero_facture": "TEST-001",
      "mode_paiement": "CASH",
      "paye": true,
      "lignes": [
        {
          "article_id": 6,
          "quantite": 1,
          "prix_unitaire": 40000
        }
      ]
    }
  ]'
```

### Test avec Python

```bash
cd C:\Users\PC\Documents\GestionMagazin
python test_sync_ventes.py
```

## 💻 Intégration MAUI

### Code C# Exemple

```csharp
public class VenteSyncService
{
    private readonly HttpClient _httpClient;
    
    public async Task<SyncResponse> SynchroniserVentesAsync(List<VenteLocal> ventes)
    {
        var url = "/api/v2/simple/ventes/sync/";
        
        // Convertir les ventes locales au format API
        var ventesData = ventes.Select(v => new
        {
            numero_facture = v.NumeroFacture,
            mode_paiement = v.ModePaiement,
            paye = v.Paye,
            lignes = v.Lignes.Select(l => new
            {
                article_id = l.ArticleId,
                quantite = l.Quantite,
                prix_unitaire = l.PrixUnitaire
            }).ToList()
        }).ToList();
        
        var json = JsonSerializer.Serialize(ventesData);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync(url, content);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<SyncResponse>(result);
        }
        
        throw new Exception($"Erreur sync: {response.StatusCode}");
    }
}
```

### Modèles C#

```csharp
public class SyncResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("message")]
    public string Message { get; set; }
    
    [JsonPropertyName("statistiques")]
    public SyncStatistiques Statistiques { get; set; }
    
    [JsonPropertyName("ventes_creees")]
    public List<VenteCreee> VentesCreees { get; set; }
    
    [JsonPropertyName("ventes_erreurs")]
    public List<VenteErreur> VentesErreurs { get; set; }
}

public class SyncStatistiques
{
    [JsonPropertyName("total_envoyees")]
    public int TotalEnvoyees { get; set; }
    
    [JsonPropertyName("reussies")]
    public int Reussies { get; set; }
    
    [JsonPropertyName("erreurs")]
    public int Erreurs { get; set; }
}
```

## 🎯 Cas d'Usage

### 1. Synchronisation Périodique

```csharp
// Synchroniser toutes les 5 minutes
var timer = new PeriodicTimer(TimeSpan.FromMinutes(5));
while (await timer.WaitForNextTickAsync())
{
    var ventesNonSync = await _db.GetVentesNonSynchroniseesAsync();
    if (ventesNonSync.Any())
    {
        var result = await _syncService.SynchroniserVentesAsync(ventesNonSync);
        await _db.MarquerVentesSynchroniseesAsync(result.VentesCreees);
    }
}
```

### 2. Synchronisation au Démarrage

```csharp
// Synchroniser au lancement de l'app
protected override async void OnStart()
{
    var ventesNonSync = await _db.GetVentesNonSynchroniseesAsync();
    if (ventesNonSync.Any())
    {
        await SynchroniserAsync(ventesNonSync);
    }
}
```

### 3. Synchronisation Manuelle

```csharp
// Bouton "Synchroniser" dans l'interface
private async void OnSyncButtonClicked(object sender, EventArgs e)
{
    var ventesNonSync = await _db.GetVentesNonSynchroniseesAsync();
    
    if (!ventesNonSync.Any())
    {
        await DisplayAlert("Info", "Aucune vente à synchroniser", "OK");
        return;
    }
    
    var result = await _syncService.SynchroniserVentesAsync(ventesNonSync);
    
    await DisplayAlert("Succès", 
        $"{result.Statistiques.Reussies} vente(s) synchronisée(s)", 
        "OK");
}
```

## 🔍 Logs Django

Les logs détaillés sont disponibles dans la console Django :

```
🔄 Synchronisation ventes pour boutique: Ma Boutique (Terminal: Terminal messie vanza)
📦 Nombre de ventes à synchroniser: 2
✅ Vente TEST-001 créée avec succès: 40000 CDF
⚠️ Vente TEST-002 existe déjà, ignorée
```

## ⚠️ Points d'Attention

### 1. Gestion des Doublons
- ✅ Utiliser des `numero_facture` uniques
- ✅ Vérifier `ventes_erreurs` dans la réponse
- ✅ Marquer les ventes synchronisées localement

### 2. Gestion du Stock
- ✅ Le stock est décrémenté immédiatement
- ✅ Vérifier le stock avant de créer la vente
- ✅ En cas d'erreur, la vente est annulée (rollback)

### 3. Performance
- ✅ Limiter à 50-100 ventes par requête
- ✅ Synchroniser par lots si nécessaire
- ✅ Gérer les timeouts réseau

### 4. Gestion d'Erreur
- ✅ Toujours vérifier `statistiques.erreurs`
- ✅ Logger les `ventes_erreurs` localement
- ✅ Réessayer les ventes en erreur

## 📊 Monitoring

### Vérifier les Ventes Synchronisées

```bash
# Via l'API historique
curl -H "X-Device-Serial: 0a1badae951f8473" \
     http://10.28.176.224:8000/api/v2/simple/ventes/historique/
```

### Vérifier les Statistiques

```bash
# Via l'API statistiques
curl -H "X-Device-Serial: 0a1badae951f8473" \
     http://10.28.176.224:8000/api/v2/simple/statistiques/
```

## 🚀 Résumé

✅ **Endpoint créé** : `/api/v2/simple/ventes/sync/`
✅ **Synchronisation par lots** : Plusieurs ventes en une requête
✅ **Gestion automatique** : Stock, montants, doublons
✅ **Rollback sécurisé** : Annulation en cas d'erreur
✅ **Logs détaillés** : Traçabilité complète
✅ **Réponse complète** : Succès et erreurs détaillés

**L'endpoint est prêt pour l'intégration MAUI !** 🎉
