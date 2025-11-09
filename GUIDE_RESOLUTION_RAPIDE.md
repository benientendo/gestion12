# ⚡ GUIDE DE RÉSOLUTION RAPIDE - Stock Mode OFFLINE

**Pour l'équipe MAUI** | **Temps estimé : 30 minutes**

---

## 🎯 OBJECTIF

Identifier et corriger le problème de synchronisation du stock en mode OFFLINE en suivant ces étapes dans l'ordre.

---

## ✅ ÉTAPE 1 : Vérifier que les ventes sont envoyées (5 min)

### Action
Ajouter des logs dans votre fonction de synchronisation :

```csharp
public async Task<bool> SynchroniserVentesOffline()
{
    var ventesOffline = await GetVentesNonSynchronisees();
    
    // ⭐ AJOUTER CE LOG
    Console.WriteLine($"📊 SYNC: {ventesOffline.Count} vente(s) à synchroniser");
    
    if (ventesOffline.Count == 0)
    {
        Console.WriteLine("✅ SYNC: Aucune vente à synchroniser");
        return true;
    }
    
    // ... reste du code
}
```

### Test
1. Faire une vente en mode OFFLINE
2. Activer la synchronisation
3. Regarder les logs

### Résultat attendu
```
📊 SYNC: 1 vente(s) à synchroniser
```

### ❌ Si vous voyez "0 vente(s)"
→ **Problème** : Les ventes ne sont pas récupérées de la base locale  
→ **Solution** : Vérifier la fonction `GetVentesNonSynchronisees()`

---

## ✅ ÉTAPE 2 : Vérifier l'URL (2 min)

### Action
```csharp
var url = $"{_baseUrl}/api/v2/simple/ventes/sync";

// ⭐ AJOUTER CE LOG
Console.WriteLine($"🔗 SYNC: URL = {url}");
```

### Résultat attendu
```
🔗 SYNC: URL = http://192.168.x.x:8000/api/v2/simple/ventes/sync
```

### ❌ Si l'URL est différente
```
❌ http://192.168.x.x:8000/api/v2/ventes/  ← INCORRECT (mode ONLINE)
❌ http://192.168.x.x:8000/api/ventes/     ← INCORRECT (ancienne API)
```

→ **Solution** : Corriger l'URL
```csharp
private const string SYNC_ENDPOINT = "/api/v2/simple/ventes/sync";
```

---

## ✅ ÉTAPE 3 : Vérifier le header (2 min)

### Action
```csharp
var request = new HttpRequestMessage(HttpMethod.Post, url);
request.Headers.Add("X-Device-Serial", _numeroSerie);

// ⭐ AJOUTER CE LOG
Console.WriteLine($"📋 SYNC: Header X-Device-Serial = {_numeroSerie}");
```

### Résultat attendu
```
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
```

### ❌ Si le numéro de série est vide ou null
```
📋 SYNC: Header X-Device-Serial = 
```

→ **Solution** : Récupérer le numéro de série
```csharp
#if ANDROID
_numeroSerie = Android.OS.Build.Serial ?? Android.OS.Build.GetSerial();
#endif
```

---

## ✅ ÉTAPE 4 : Vérifier le format JSON (3 min)

### Action
```csharp
var json = JsonSerializer.Serialize(syncData);

// ⭐ AJOUTER CE LOG
Console.WriteLine($"📦 SYNC: JSON = {json}");
```

### Résultat attendu
```json
{
  "ventes": [
    {
      "numero_facture": "VENTE-OFFLINE-001",
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

### ❌ Si le format est différent
- Pas de clé `"ventes"` → Ajouter l'enveloppe
- Pas de `"lignes"` → Vérifier la structure
- `article_id` manquant → Vérifier le mapping

---

## ✅ ÉTAPE 5 : Vérifier la réponse HTTP (5 min)

### Action
```csharp
var response = await _httpClient.PostAsync(url, content);

// ⭐ AJOUTER CES LOGS
Console.WriteLine($"📥 SYNC: Status = {response.StatusCode}");

var responseContent = await response.Content.ReadAsStringAsync();
Console.WriteLine($"📄 SYNC: Réponse = {responseContent}");
```

### Résultat attendu (succès)
```
📥 SYNC: Status = OK (200)
📄 SYNC: Réponse = {"success":true,"ventes_creees":1,...}
```

### ❌ Si status ≠ 200
```
📥 SYNC: Status = BadRequest (400)
📄 SYNC: Réponse = {"error":"Paramètre manquant",...}
```

→ **Analyser l'erreur** et corriger selon le message

---

## ✅ ÉTAPE 6 : Gérer les erreurs correctement (5 min)

### ❌ Code DANGEREUX (à corriger)
```csharp
var response = await _httpClient.PostAsync(url, content);

// ❌ Pas de vérification !
// La vente est marquée comme synchronisée même si erreur
foreach (var vente in ventesOffline)
{
    vente.EstSynchronisee = true;  // ❌ DANGEREUX
}
```

### ✅ Code CORRECT
```csharp
var response = await _httpClient.PostAsync(url, content);

// ✅ Vérifier le status code
if (!response.IsSuccessStatusCode)
{
    var error = await response.Content.ReadAsStringAsync();
    Console.WriteLine($"❌ SYNC: Erreur {response.StatusCode} - {error}");
    
    // NE PAS marquer comme synchronisée
    return false;
}

// ✅ Vérifier la réponse JSON
var responseContent = await response.Content.ReadAsStringAsync();
var result = JsonSerializer.Deserialize<SyncResponse>(responseContent);

if (!result.Success)
{
    Console.WriteLine($"❌ SYNC: Échec - {result.Message}");
    return false;
}

// ✅ Marquer comme synchronisée UNIQUEMENT si succès
Console.WriteLine($"✅ SYNC: {result.VentesCrees} vente(s) synchronisée(s)");
foreach (var vente in ventesOffline)
{
    vente.EstSynchronisee = true;
    vente.DateSynchronisation = DateTime.Now;
}
```

---

## ✅ ÉTAPE 7 : Tester avec Postman (5 min)

### Pourquoi ?
Pour vérifier que l'API Django fonctionne correctement, indépendamment du code MAUI.

### Comment ?
1. Ouvrir Postman
2. Créer une requête POST : `http://votre-serveur:8000/api/v2/simple/ventes/sync`
3. Ajouter le header : `X-Device-Serial: VOTRE_NUMERO_SERIE`
4. Ajouter le body (JSON) :
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
5. Envoyer la requête
6. Vérifier dans Django que le stock a été décrémenté

### ✅ Si Postman fonctionne mais pas MAUI
→ Le problème est dans le code MAUI (URL, header, format, gestion erreur)

### ❌ Si Postman ne fonctionne pas non plus
→ Le problème est côté Django (contacter l'équipe backend)

---

## 🎯 RÉCAPITULATIF DES LOGS À AJOUTER

```csharp
public async Task<bool> SynchroniserVentesOffline()
{
    try
    {
        // 1. Récupération des ventes
        var ventesOffline = await GetVentesNonSynchronisees();
        Console.WriteLine($"📊 SYNC: {ventesOffline.Count} vente(s) à synchroniser");
        
        if (ventesOffline.Count == 0) return true;
        
        // 2. Préparation des données
        var syncData = PrepareVentesData(ventesOffline);
        var json = JsonSerializer.Serialize(syncData);
        Console.WriteLine($"📦 SYNC: JSON length = {json.Length} chars");
        
        // 3. Préparation de la requête
        var url = $"{_baseUrl}/api/v2/simple/ventes/sync";
        Console.WriteLine($"🔗 SYNC: URL = {url}");
        Console.WriteLine($"📋 SYNC: Header X-Device-Serial = {_numeroSerie}");
        
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        // 4. Envoi de la requête
        Console.WriteLine($"📤 SYNC: Envoi de la requête...");
        var response = await _httpClient.PostAsync(url, content);
        Console.WriteLine($"📥 SYNC: Status = {response.StatusCode}");
        
        // 5. Lecture de la réponse
        var responseContent = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"📄 SYNC: Réponse = {responseContent}");
        
        // 6. Vérification du succès
        if (!response.IsSuccessStatusCode)
        {
            Console.WriteLine($"❌ SYNC: Erreur HTTP");
            return false;
        }
        
        var result = JsonSerializer.Deserialize<SyncResponse>(responseContent);
        
        if (!result.Success)
        {
            Console.WriteLine($"❌ SYNC: Échec - {result.Message}");
            return false;
        }
        
        // 7. Mise à jour des ventes
        Console.WriteLine($"✅ SYNC: {result.VentesCrees} vente(s) créée(s)");
        foreach (var vente in ventesOffline)
        {
            vente.EstSynchronisee = true;
            vente.DateSynchronisation = DateTime.Now;
            Console.WriteLine($"✅ SYNC: Vente {vente.NumeroFacture} marquée");
        }
        
        await _database.SaveChangesAsync();
        Console.WriteLine($"💾 SYNC: Base de données mise à jour");
        
        return true;
    }
    catch (Exception ex)
    {
        Console.WriteLine($"❌ SYNC: EXCEPTION - {ex.Message}");
        Console.WriteLine($"❌ SYNC: StackTrace - {ex.StackTrace}");
        return false;
    }
}
```

---

## 📊 EXEMPLE DE LOGS ATTENDUS (Succès)

```
📊 SYNC: 2 vente(s) à synchroniser
📦 SYNC: JSON length = 456 chars
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/simple/ventes/sync
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
📤 SYNC: Envoi de la requête...
📥 SYNC: Status = OK
📄 SYNC: Réponse = {"success":true,"ventes_creees":2,"ventes_erreurs":0,...}
✅ SYNC: 2 vente(s) créée(s)
✅ SYNC: Vente VENTE-OFFLINE-001 marquée
✅ SYNC: Vente VENTE-OFFLINE-002 marquée
💾 SYNC: Base de données mise à jour
```

---

## 📊 EXEMPLE DE LOGS ATTENDUS (Erreur)

```
📊 SYNC: 1 vente(s) à synchroniser
📦 SYNC: JSON length = 234 chars
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/simple/ventes/sync
📋 SYNC: Header X-Device-Serial = 
❌ SYNC: Header vide ! Impossible de synchroniser
```

Ou :

```
📊 SYNC: 1 vente(s) à synchroniser
📦 SYNC: JSON length = 234 chars
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/simple/ventes/sync
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
📤 SYNC: Envoi de la requête...
📥 SYNC: Status = BadRequest
📄 SYNC: Réponse = {"error":"Terminal non trouvé","code":"TERMINAL_NOT_FOUND"}
❌ SYNC: Erreur HTTP
```

---

## 🎯 DÉCISION RAPIDE

Après avoir ajouté les logs et fait un test :

### ✅ Si vous voyez "Status = OK" et "ventes_creees > 0"
→ **La synchronisation fonctionne !**  
→ Le problème est ailleurs (peut-être que les ventes ne sont pas récupérées ?)

### ❌ Si vous voyez "Status = BadRequest (400)"
→ Analyser le message d'erreur dans la réponse  
→ Corriger selon le message (header manquant, format incorrect, etc.)

### ❌ Si vous voyez "Status = NotFound (404)"
→ L'URL est incorrecte  
→ Vérifier que c'est bien `/api/v2/simple/ventes/sync`

### ❌ Si vous voyez "Status = InternalServerError (500)"
→ Erreur côté Django  
→ Contacter l'équipe backend avec les logs

---

## 📞 BESOIN D'AIDE ?

Si après avoir suivi toutes ces étapes le problème persiste :

1. **Copier tous les logs** générés par votre application
2. **Faire un test Postman** et copier la requête/réponse
3. **Contacter l'équipe backend** avec ces informations

---

**Temps total estimé : 30 minutes**  
**Résolution attendue : 95% des cas** 🚀
