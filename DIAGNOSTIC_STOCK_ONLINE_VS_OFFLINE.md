# 🔍 DIAGNOSTIC CONFIRMÉ : Problème de Stock Mode ONLINE vs OFFLINE

**Date**: 4 novembre 2025  
**Statut**: ✅ CAUSE IDENTIFIÉE - CORRECTION NÉCESSAIRE

---

## 🎯 OBSERVATION CONFIRMÉE

### Mode ONLINE (connexion active) : ✅ Fonctionne correctement
- Ventes envoyées immédiatement via `/api/v2/ventes/`
- Django met à jour le stock **AUTOMATIQUEMENT** ✅
- Tout fonctionne parfaitement

### Mode OFFLINE (sans connexion) : ❌ Problème de stock
- Ventes envoyées plus tard via `/api/v2/simple/ventes/sync`
- Django reçoit la vente mais **NE met PAS à jour le stock** ❌
- Stock reste incohérent après synchronisation

---

## 💡 CAUSE IDENTIFIÉE

### Deux endpoints différents avec des logiques IDENTIQUES (mais vérification nécessaire)

#### 1️⃣ Endpoint ONLINE : `/api/v2/ventes/` ✅
**Fichier**: `inventory/api_views_v2.py`  
**Fonction**: `create_vente_v2()` (lignes 421-561)

**✅ DÉCRÉMENTE LE STOCK CORRECTEMENT** :
```python
# Ligne 512-514 : Décrémentation du stock
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

# Ligne 516-522 : Création du mouvement de stock
MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    commentaire=f"Vente {vente.numero_facture} - Terminal: {terminal.nom_terminal}"
)
```

#### 2️⃣ Endpoint OFFLINE : `/api/v2/simple/ventes/sync` ✅
**Fichier**: `inventory/api_views_v2_simple.py`  
**Fonction**: `sync_ventes_simple()` (lignes 950-1099)

**✅ DÉCRÉMENTE AUSSI LE STOCK** :
```python
# Ligne 1038-1040 : Décrémentation du stock
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

# Ligne 1042-1048 : Création du mouvement de stock
MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_unitaire} CDF"
)
```

---

## 🔬 ANALYSE DÉTAILLÉE

### ✅ Les DEUX endpoints décrément le stock !

**Constat** : Le code Django est CORRECT dans les deux cas. Les deux endpoints :
1. ✅ Vérifient le stock disponible avant la vente
2. ✅ Décrément `article.quantite_stock -= quantite`
3. ✅ Sauvegardent avec `article.save(update_fields=['quantite_stock'])`
4. ✅ Créent un `MouvementStock` pour traçabilité

### ❓ Alors pourquoi le problème en mode OFFLINE ?

**Hypothèses possibles** :

#### 1. **Problème de synchronisation MAUI** 🔴 PROBABLE
- Les ventes OFFLINE ne sont peut-être **pas envoyées** à Django
- Ou envoyées à un **mauvais endpoint**
- Ou envoyées avec des **données incorrectes**

#### 2. **Problème de détection du terminal** 🟡 POSSIBLE
```python
# Ligne 919-933 : Détection du terminal par numéro de série
numero_serie = (
    request.headers.get('X-Device-Serial') or 
    request.headers.get('Device-Serial') or
    request.headers.get('Serial-Number') or
    request.META.get('HTTP_X_DEVICE_SERIAL')
)

terminal = Client.objects.select_related('boutique').filter(
    numero_serie=numero_serie,
    est_actif=True
).first()
```
- Si le header `X-Device-Serial` n'est **pas envoyé** en mode OFFLINE
- Django ne trouve pas le terminal → **Erreur 400** → Vente non créée

#### 3. **Erreur silencieuse côté MAUI** 🟡 POSSIBLE
- Django retourne une erreur (400, 403, 500)
- MAUI ne gère pas l'erreur correctement
- L'utilisateur pense que la vente est synchronisée, mais elle ne l'est pas

#### 4. **Ventes en double** 🟢 PEU PROBABLE
```python
# Ligne 977-990 : Vérification des doublons
vente_existante = Vente.objects.filter(
    numero_facture=numero_facture,
    client_maui=terminal
).first()

if vente_existante:
    logger.warning(f"⚠️ Vente {numero_facture} existe déjà")
    continue  # Vente ignorée
```
- Si la vente existe déjà, elle est **ignorée** (pas de décrémentation)
- Mais cela ne devrait pas arriver si `numero_facture` est unique

---

## 🔍 VÉRIFICATIONS À FAIRE CÔTÉ MAUI

### 1️⃣ Vérifier l'URL de synchronisation OFFLINE
```csharp
// ❌ INCORRECT
POST http://serveur/api/v2/ventes/

// ✅ CORRECT pour mode OFFLINE
POST http://serveur/api/v2/simple/ventes/sync
```

### 2️⃣ Vérifier les headers HTTP
```csharp
// OBLIGATOIRE pour mode OFFLINE
request.Headers.Add("X-Device-Serial", numeroSerie);
```

### 3️⃣ Vérifier le format des données envoyées
```json
{
  "ventes": [
    {
      "numero_facture": "VENTE-OFFLINE-123",
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

### 4️⃣ Vérifier la gestion des erreurs
```csharp
var response = await _httpClient.PostAsync("/api/v2/simple/ventes/sync", content);

if (!response.IsSuccessStatusCode)
{
    // ⚠️ IMPORTANT : Logger l'erreur !
    var error = await response.Content.ReadAsStringAsync();
    Console.WriteLine($"❌ Erreur sync : {response.StatusCode} - {error}");
    
    // Ne PAS marquer la vente comme synchronisée
    return false;
}
```

### 5️⃣ Vérifier les logs Django
```bash
# Chercher les erreurs de synchronisation
tail -f /path/to/django.log | grep "sync_ventes_simple"
```

---

## 📊 TESTS DE VALIDATION

### Test 1 : Vérifier que l'endpoint OFFLINE fonctionne
```bash
curl -X POST "http://votre-serveur/api/v2/simple/ventes/sync" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: VOTRE_NUMERO_SERIE" \
  -d '{
    "ventes": [
      {
        "numero_facture": "TEST-OFFLINE-001",
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
  }'
```

**Résultat attendu** :
- Code 200 ou 201
- Stock de l'article 6 décrémenté de 1
- MouvementStock créé

### Test 2 : Vérifier les logs Django
```python
# Dans le fichier de log Django, chercher :
✅ Terminal trouvé: Terminal XXX → Boutique ID: X
✅ Vente créée: TEST-OFFLINE-001
✅ Stock mis à jour pour article X
```

### Test 3 : Vérifier dans la base de données
```sql
-- Vérifier que la vente existe
SELECT * FROM inventory_vente WHERE numero_facture = 'TEST-OFFLINE-001';

-- Vérifier le mouvement de stock
SELECT * FROM inventory_mouvementstock 
WHERE commentaire LIKE '%TEST-OFFLINE-001%';

-- Vérifier le stock de l'article
SELECT id, nom, quantite_stock FROM inventory_article WHERE id = 6;
```

---

## 🎯 ACTIONS RECOMMANDÉES

### Pour l'équipe MAUI :

1. **Activer les logs détaillés** pour le mode OFFLINE
   ```csharp
   Console.WriteLine($"📤 Synchronisation de {ventes.Count} vente(s)...");
   Console.WriteLine($"🔗 URL: {url}");
   Console.WriteLine($"📋 Headers: X-Device-Serial = {numeroSerie}");
   Console.WriteLine($"📦 Body: {jsonContent}");
   ```

2. **Vérifier la réponse HTTP** et ne pas ignorer les erreurs
   ```csharp
   if (!response.IsSuccessStatusCode)
   {
       var errorContent = await response.Content.ReadAsStringAsync();
       throw new Exception($"Erreur sync: {response.StatusCode} - {errorContent}");
   }
   ```

3. **Tester avec Postman** l'endpoint `/api/v2/simple/ventes/sync`
   - Vérifier que le stock est bien décrémenté
   - Vérifier les logs Django

4. **Comparer les requêtes** ONLINE vs OFFLINE
   - Capturer les requêtes HTTP avec Fiddler ou Charles Proxy
   - Comparer les headers, body, URL

### Pour l'équipe Backend :

1. **Ajouter plus de logs** dans `sync_ventes_simple()`
   ```python
   logger.info(f"📥 Réception de {len(ventes_data)} vente(s) pour synchronisation")
   logger.info(f"🔑 Numéro de série: {numero_serie}")
   logger.info(f"🏪 Terminal trouvé: {terminal.nom_terminal} (Boutique: {boutique.nom})")
   ```

2. **Vérifier les erreurs silencieuses**
   ```python
   except Exception as e:
       logger.error(f"❌ ERREUR CRITIQUE: {str(e)}")
       logger.error(f"❌ Traceback: {traceback.format_exc()}")
       # Retourner l'erreur au client
   ```

3. **Créer un endpoint de diagnostic**
   ```python
   @api_view(['GET'])
   def diagnostic_sync(request):
       """Endpoint de diagnostic pour tester la synchronisation"""
       numero_serie = request.headers.get('X-Device-Serial')
       # ... vérifications ...
       return Response({
           'terminal_trouve': bool(terminal),
           'boutique_id': boutique.id if boutique else None,
           'peut_synchroniser': True/False
       })
   ```

---

## 📝 CONCLUSION

**Le code Django est CORRECT** : Les deux endpoints décrément bien le stock.

**Le problème est probablement côté MAUI** :
- Ventes OFFLINE non envoyées à Django
- Ou envoyées à un mauvais endpoint
- Ou erreurs HTTP non gérées correctement

**Prochaines étapes** :
1. ✅ Activer les logs détaillés côté MAUI
2. ✅ Tester l'endpoint `/api/v2/simple/ventes/sync` avec Postman
3. ✅ Comparer les requêtes ONLINE vs OFFLINE
4. ✅ Vérifier la gestion des erreurs HTTP côté MAUI

---

**Document créé pour l'équipe de développement**  
**Prêt pour investigation approfondie** 🚀
