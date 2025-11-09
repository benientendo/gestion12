# ✅ CHECKLIST DE DEBUG - Mode OFFLINE MAUI

**Problème** : Le stock ne se met pas à jour après synchronisation des ventes OFFLINE  
**Cause probable** : Problème de synchronisation côté MAUI (le code Django est correct)

---

## 🔍 VÉRIFICATIONS PRIORITAIRES

### ✅ 1. Vérifier l'URL de synchronisation

**Code à vérifier** :
```csharp
// Dans votre service de synchronisation
private const string SYNC_URL = "/api/v2/simple/ventes/sync";  // ✅ CORRECT

// ❌ INCORRECT - Ne PAS utiliser ces URLs pour le mode OFFLINE
// "/api/v2/ventes/"           // URL pour mode ONLINE uniquement
// "/api/ventes/"              // Ancienne API
```

**Test rapide** :
```csharp
Console.WriteLine($"🔗 URL de sync: {SYNC_URL}");
// Doit afficher: /api/v2/simple/ventes/sync
```

---

### ✅ 2. Vérifier le header X-Device-Serial

**Code à vérifier** :
```csharp
// Le header DOIT être présent pour toutes les requêtes OFFLINE
var request = new HttpRequestMessage(HttpMethod.Post, SYNC_URL);
request.Headers.Add("X-Device-Serial", numeroSerie);

Console.WriteLine($"📋 Header X-Device-Serial: {numeroSerie}");
// Doit afficher votre numéro de série (ex: 0a1badae951f8473)
```

**⚠️ IMPORTANT** : Sans ce header, Django ne peut pas identifier le terminal !

---

### ✅ 3. Vérifier le format des données

**Format attendu par Django** :
```json
{
  "ventes": [
    {
      "numero_facture": "VENTE-OFFLINE-20251104-001",
      "mode_paiement": "CASH",
      "paye": true,
      "lignes": [
        {
          "article_id": 6,
          "quantite": 2,
          "prix_unitaire": 100000.00
        }
      ]
    }
  ]
}
```

**Code C# correspondant** :
```csharp
var syncData = new
{
    ventes = ventesOffline.Select(v => new
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
    }).ToList()
};

var json = JsonSerializer.Serialize(syncData);
Console.WriteLine($"📦 JSON envoyé: {json}");
```

---

### ✅ 4. Vérifier la gestion des erreurs HTTP

**❌ CODE DANGEREUX** (ignore les erreurs) :
```csharp
var response = await _httpClient.PostAsync(url, content);
// Pas de vérification du status code !
// La vente est marquée comme synchronisée même si erreur !
```

**✅ CODE CORRECT** (gère les erreurs) :
```csharp
var response = await _httpClient.PostAsync(url, content);

if (!response.IsSuccessStatusCode)
{
    var errorContent = await response.Content.ReadAsStringAsync();
    
    // Logger l'erreur
    Console.WriteLine($"❌ Erreur HTTP {response.StatusCode}");
    Console.WriteLine($"❌ Détails: {errorContent}");
    
    // NE PAS marquer la vente comme synchronisée
    throw new HttpRequestException(
        $"Erreur sync: {response.StatusCode} - {errorContent}"
    );
}

// Vérifier la réponse JSON
var responseContent = await response.Content.ReadAsStringAsync();
var result = JsonSerializer.Deserialize<SyncResponse>(responseContent);

if (!result.Success)
{
    Console.WriteLine($"❌ Synchronisation échouée: {result.Message}");
    throw new Exception($"Sync failed: {result.Message}");
}

Console.WriteLine($"✅ {result.VentesCrees} vente(s) synchronisée(s)");
```

---

### ✅ 5. Activer les logs détaillés

**Ajouter des logs à chaque étape** :
```csharp
public async Task<bool> SynchroniserVentesOffline()
{
    try
    {
        var ventesOffline = await GetVentesNonSynchronisees();
        Console.WriteLine($"📊 {ventesOffline.Count} vente(s) à synchroniser");
        
        if (ventesOffline.Count == 0)
        {
            Console.WriteLine("✅ Aucune vente à synchroniser");
            return true;
        }
        
        // Préparer les données
        var syncData = PrepareVentesData(ventesOffline);
        var json = JsonSerializer.Serialize(syncData);
        Console.WriteLine($"📦 Taille JSON: {json.Length} caractères");
        
        // Préparer la requête
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        var url = $"{_baseUrl}/api/v2/simple/ventes/sync";
        Console.WriteLine($"🔗 URL: {url}");
        Console.WriteLine($"📋 Header: X-Device-Serial = {_numeroSerie}");
        
        // Envoyer la requête
        Console.WriteLine($"📤 Envoi de la requête...");
        var response = await _httpClient.PostAsync(url, content);
        Console.WriteLine($"📥 Réponse HTTP: {response.StatusCode}");
        
        // Lire la réponse
        var responseContent = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"📄 Réponse: {responseContent}");
        
        if (!response.IsSuccessStatusCode)
        {
            Console.WriteLine($"❌ ERREUR: {response.StatusCode}");
            Console.WriteLine($"❌ Détails: {responseContent}");
            return false;
        }
        
        // Parser la réponse
        var result = JsonSerializer.Deserialize<SyncResponse>(responseContent);
        Console.WriteLine($"✅ Succès: {result.VentesCrees} vente(s) créée(s)");
        Console.WriteLine($"⚠️ Erreurs: {result.VentesErreurs} vente(s) en erreur");
        
        // Marquer les ventes comme synchronisées
        foreach (var vente in ventesOffline)
        {
            vente.EstSynchronisee = true;
            vente.DateSynchronisation = DateTime.Now;
            Console.WriteLine($"✅ Vente {vente.NumeroFacture} marquée comme synchronisée");
        }
        
        await _database.SaveChangesAsync();
        Console.WriteLine($"💾 Base de données locale mise à jour");
        
        return true;
    }
    catch (Exception ex)
    {
        Console.WriteLine($"❌ EXCEPTION: {ex.Message}");
        Console.WriteLine($"❌ StackTrace: {ex.StackTrace}");
        return false;
    }
}
```

---

### ✅ 6. Tester avec Postman

**Avant de débugger le code MAUI, tester l'API directement** :

1. **Ouvrir Postman**

2. **Créer une requête POST** :
   ```
   POST http://votre-serveur:8000/api/v2/simple/ventes/sync
   ```

3. **Ajouter le header** :
   ```
   X-Device-Serial: VOTRE_NUMERO_SERIE
   ```

4. **Ajouter le body (JSON)** :
   ```json
   {
     "ventes": [
       {
         "numero_facture": "TEST-POSTMAN-001",
         "mode_paiement": "CASH",
         "paye": true,
         "lignes": [
           {
             "article_id": 6,
             "quantite": 1,
             "prix_unitaire": 100000.00
           }
         ]
       }
     ]
   }
   ```

5. **Envoyer la requête**

6. **Vérifier** :
   - ✅ Status code 200 ou 201
   - ✅ Réponse JSON avec `success: true`
   - ✅ Stock de l'article 6 décrémenté dans Django
   - ✅ Vente visible dans l'interface Django

**Si Postman fonctionne mais pas MAUI** → Le problème est dans le code MAUI !

---

### ✅ 7. Comparer ONLINE vs OFFLINE

**Capturer les requêtes HTTP avec Fiddler ou Charles Proxy** :

1. **Faire une vente en mode ONLINE**
   - Capturer la requête HTTP
   - Noter : URL, headers, body

2. **Faire une vente en mode OFFLINE puis synchroniser**
   - Capturer la requête HTTP
   - Noter : URL, headers, body

3. **Comparer les deux requêtes**
   - URL différente ? → Vérifier le code
   - Header manquant ? → Ajouter le header
   - Body différent ? → Corriger le format

---

## 🎯 CHECKLIST RAPIDE

Cochez chaque point après vérification :

- [ ] URL de sync = `/api/v2/simple/ventes/sync`
- [ ] Header `X-Device-Serial` présent et correct
- [ ] Format JSON conforme (voir exemple ci-dessus)
- [ ] Gestion des erreurs HTTP implémentée
- [ ] Logs détaillés activés
- [ ] Test Postman réussi
- [ ] Comparaison ONLINE vs OFFLINE faite
- [ ] Ventes marquées comme synchronisées UNIQUEMENT si succès
- [ ] Base de données locale mise à jour après sync

---

## 🔧 CODE DE TEST MINIMAL

**Créer une page de test dans MAUI** :

```csharp
public async Task TestSyncManuel()
{
    try
    {
        Console.WriteLine("=== TEST SYNCHRONISATION MANUELLE ===");
        
        // 1. Vérifier la configuration
        Console.WriteLine($"🔗 Base URL: {_baseUrl}");
        Console.WriteLine($"📋 Numéro série: {_numeroSerie}");
        
        // 2. Créer une vente de test
        var venteTest = new
        {
            ventes = new[]
            {
                new
                {
                    numero_facture = $"TEST-{DateTime.Now:yyyyMMddHHmmss}",
                    mode_paiement = "CASH",
                    paye = true,
                    lignes = new[]
                    {
                        new
                        {
                            article_id = 6,  // Remplacer par un ID valide
                            quantite = 1,
                            prix_unitaire = 100000.00
                        }
                    }
                }
            }
        };
        
        var json = JsonSerializer.Serialize(venteTest);
        Console.WriteLine($"📦 JSON: {json}");
        
        // 3. Envoyer la requête
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        var url = $"{_baseUrl}/api/v2/simple/ventes/sync";
        
        Console.WriteLine($"📤 Envoi vers: {url}");
        var response = await _httpClient.PostAsync(url, content);
        
        // 4. Afficher la réponse
        var responseContent = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"📥 Status: {response.StatusCode}");
        Console.WriteLine($"📄 Réponse: {responseContent}");
        
        if (response.IsSuccessStatusCode)
        {
            Console.WriteLine("✅ TEST RÉUSSI !");
        }
        else
        {
            Console.WriteLine("❌ TEST ÉCHOUÉ !");
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"❌ ERREUR: {ex.Message}");
        Console.WriteLine($"❌ Stack: {ex.StackTrace}");
    }
}
```

---

## 📞 SUPPORT

Si après toutes ces vérifications le problème persiste :

1. **Envoyer les logs complets** :
   - Logs MAUI (console output)
   - Logs Django (fichier de log)
   - Capture Postman (requête + réponse)

2. **Informations à fournir** :
   - Version de l'app MAUI
   - Version de Django
   - Numéro de série du terminal
   - ID de la boutique
   - Exemple de vente qui ne synchronise pas

3. **Contacter l'équipe backend** avec ces informations

---

**Document créé pour faciliter le debug** 🚀  
**Suivez les étapes dans l'ordre pour identifier le problème rapidement** ✅
