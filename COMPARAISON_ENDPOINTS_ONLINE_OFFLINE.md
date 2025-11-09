# 🔄 COMPARAISON DÉTAILLÉE : Endpoints ONLINE vs OFFLINE

**Date**: 4 novembre 2025  
**Objectif**: Comprendre les différences entre les deux modes de vente

---

## 📊 VUE D'ENSEMBLE

| Caractéristique | Mode ONLINE ✅ | Mode OFFLINE ❌ |
|-----------------|----------------|-----------------|
| **Endpoint** | `/api/v2/ventes/` | `/api/v2/simple/ventes/sync` |
| **Fichier** | `api_views_v2.py` | `api_views_v2_simple.py` |
| **Fonction** | `create_vente_v2()` | `sync_ventes_simple()` |
| **Méthode HTTP** | POST | POST |
| **Authentification** | Token JWT | Header X-Device-Serial |
| **Format données** | 1 vente | N ventes (batch) |
| **Décrémente stock** | ✅ OUI | ✅ OUI (théoriquement) |
| **Crée MouvementStock** | ✅ OUI | ✅ OUI (théoriquement) |
| **Fonctionne** | ✅ OUI | ❌ NON (problème constaté) |

---

## 🔍 COMPARAISON DÉTAILLÉE DU CODE

### 1️⃣ AUTHENTIFICATION

#### Mode ONLINE
```python
# Fichier: api_views_v2.py, ligne 422
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # ← Authentification JWT
def create_vente_v2(request):
    # Récupération du terminal via l'utilisateur authentifié
    terminal = Client.objects.filter(
        compte_proprietaire=request.user,  # ← User Django
        boutique=boutique,
        est_actif=True
    ).first()
```

#### Mode OFFLINE
```python
# Fichier: api_views_v2_simple.py, ligne 919
# Pas de décorateur @permission_classes
def sync_ventes_simple(request):
    # Récupération du terminal via le numéro de série
    numero_serie = (
        request.headers.get('X-Device-Serial') or  # ← Header HTTP
        request.headers.get('Device-Serial') or
        request.headers.get('Serial-Number')
    )
    
    terminal = Client.objects.filter(
        numero_serie=numero_serie,  # ← Numéro de série
        est_actif=True
    ).first()
```

**⚠️ POINT D'ATTENTION** : Si le header `X-Device-Serial` n'est pas envoyé, le terminal ne sera pas trouvé !

---

### 2️⃣ FORMAT DES DONNÉES

#### Mode ONLINE (1 vente à la fois)
```json
{
  "boutique_id": 2,
  "numero_facture": "VENTE-001",
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
```

#### Mode OFFLINE (plusieurs ventes en batch)
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
    },
    {
      "numero_facture": "VENTE-OFFLINE-002",
      "mode_paiement": "CASH",
      "paye": true,
      "lignes": [...]
    }
  ]
}
```

**⚠️ POINT D'ATTENTION** : Le format est différent ! Mode OFFLINE = tableau de ventes.

---

### 3️⃣ DÉCRÉMENTATION DU STOCK

#### Mode ONLINE ✅
```python
# Fichier: api_views_v2.py, lignes 512-522

# Décrémenter le stock
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

# Enregistrer le mouvement de stock
MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    commentaire=f"Vente {vente.numero_facture} - Terminal: {terminal.nom_terminal}"
)
```

#### Mode OFFLINE ✅ (code identique !)
```python
# Fichier: api_views_v2_simple.py, lignes 1038-1048

# Mettre à jour le stock
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

# Créer un mouvement de stock
MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_unitaire} CDF"
)
```

**✅ CONSTAT** : Le code est **IDENTIQUE** dans les deux cas ! Les deux endpoints décrément bien le stock.

---

### 4️⃣ VÉRIFICATION DU STOCK

#### Mode ONLINE ✅
```python
# Fichier: api_views_v2.py, lignes 495-501

# Vérifier le stock disponible
if article.quantite_stock < quantite:
    vente.delete()
    return Response({
        'error': f'Stock insuffisant pour {article.nom}',
        'code': 'INSUFFICIENT_STOCK'
    }, status=status.HTTP_400_BAD_REQUEST)
```

#### Mode OFFLINE ✅
```python
# Fichier: api_views_v2_simple.py, lignes 1024-1027

# Vérifier le stock disponible
if article.quantite_stock < quantite:
    vente.delete()
    raise Exception(f'Stock insuffisant pour {article.nom}')
```

**✅ CONSTAT** : Les deux endpoints vérifient le stock avant la vente.

---

### 5️⃣ GESTION DES ERREURS

#### Mode ONLINE ✅
```python
# Fichier: api_views_v2.py, lignes 550-561

except ValidationError as e:
    return Response({
        'error': str(e),
        'code': 'ACCESS_DENIED'
    }, status=status.HTTP_403_FORBIDDEN)

except Exception as e:
    logger.error(f"Erreur lors de la création de la vente: {str(e)}")
    return Response({
        'error': 'Erreur interne du serveur',
        'code': 'INTERNAL_ERROR'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

#### Mode OFFLINE ✅
```python
# Fichier: api_views_v2_simple.py, lignes 1080-1086

except Exception as e:
    logger.error(f"❌ Erreur création vente {index + 1}: {str(e)}")
    ventes_erreurs.append({
        'index': index + 1,
        'numero_facture': vente_data.get('numero_facture', 'N/A'),
        'erreur': str(e)
    })
```

**⚠️ DIFFÉRENCE** : 
- Mode ONLINE : Retourne une erreur HTTP (400, 403, 500)
- Mode OFFLINE : Continue le traitement et retourne un résumé avec erreurs

---

## 🎯 ANALYSE DES DIFFÉRENCES

### ✅ Ce qui est IDENTIQUE
1. **Décrémentation du stock** : `article.quantite_stock -= quantite`
2. **Sauvegarde** : `article.save(update_fields=['quantite_stock'])`
3. **Création MouvementStock** : Même logique dans les deux cas
4. **Vérification stock** : Les deux vérifient avant la vente

### ⚠️ Ce qui est DIFFÉRENT
1. **Authentification** : JWT vs Header X-Device-Serial
2. **Format données** : 1 vente vs N ventes (batch)
3. **Gestion erreurs** : HTTP error vs résumé avec erreurs
4. **Logs** : Plus détaillés en mode OFFLINE

---

## 💡 POURQUOI LE PROBLÈME EN MODE OFFLINE ?

### Hypothèse 1 : Ventes non envoyées 🔴 PROBABLE
```
MAUI (OFFLINE) → ❌ Ne synchronise pas → Django ne reçoit rien
```

**Comment vérifier** :
```csharp
// Dans le code MAUI, ajouter des logs
Console.WriteLine($"📤 Synchronisation de {ventes.Count} vente(s)");
Console.WriteLine($"🔗 URL: {url}");
Console.WriteLine($"📦 Body: {json}");
```

### Hypothèse 2 : Header manquant 🟡 POSSIBLE
```
MAUI (OFFLINE) → Envoie sans header → Django ne trouve pas le terminal → Erreur 400
```

**Comment vérifier** :
```csharp
// Vérifier que le header est bien ajouté
request.Headers.Add("X-Device-Serial", numeroSerie);
Console.WriteLine($"📋 Header: X-Device-Serial = {numeroSerie}");
```

### Hypothèse 3 : Erreur HTTP non gérée 🟡 POSSIBLE
```
MAUI (OFFLINE) → Envoie → Django retourne erreur → MAUI ignore l'erreur
```

**Comment vérifier** :
```csharp
// Vérifier le status code
if (!response.IsSuccessStatusCode)
{
    Console.WriteLine($"❌ Erreur: {response.StatusCode}");
    var error = await response.Content.ReadAsStringAsync();
    Console.WriteLine($"❌ Détails: {error}");
    // NE PAS marquer comme synchronisée !
    return false;
}
```

### Hypothèse 4 : Mauvaise URL 🟡 POSSIBLE
```
MAUI (OFFLINE) → Envoie vers /api/v2/ventes/ → Mauvais endpoint
```

**Comment vérifier** :
```csharp
// Vérifier l'URL utilisée
const string SYNC_URL = "/api/v2/simple/ventes/sync";  // ✅ CORRECT
Console.WriteLine($"🔗 URL: {SYNC_URL}");
```

---

## 🧪 TEST DE VALIDATION

### Test avec curl (simule MAUI OFFLINE)

```bash
curl -X POST "http://votre-serveur:8000/api/v2/simple/ventes/sync" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: VOTRE_NUMERO_SERIE" \
  -d '{
    "ventes": [
      {
        "numero_facture": "TEST-CURL-001",
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
```json
{
  "success": true,
  "message": "1 vente(s) synchronisée(s) avec succès",
  "ventes_creees": 1,
  "ventes_erreurs": 0,
  "details": {
    "creees": [
      {
        "numero_facture": "TEST-CURL-001",
        "status": "created",
        "boutique_id": 2,
        "montant_total": "100000.00"
      }
    ]
  }
}
```

**Vérification dans Django** :
```python
# Vérifier que le stock a été décrémenté
article = Article.objects.get(id=6)
print(f"Stock actuel: {article.quantite_stock}")

# Vérifier le mouvement de stock
mouvement = MouvementStock.objects.filter(
    article=article,
    commentaire__contains='TEST-CURL-001'
).first()
print(f"Mouvement: {mouvement}")
```

---

## 📋 CHECKLIST DE VÉRIFICATION

### Côté MAUI
- [ ] URL correcte : `/api/v2/simple/ventes/sync`
- [ ] Header `X-Device-Serial` présent
- [ ] Format JSON correct (tableau de ventes)
- [ ] Gestion des erreurs HTTP
- [ ] Logs détaillés activés
- [ ] Ventes marquées synchronisées UNIQUEMENT si succès

### Côté Django
- [ ] Endpoint `/api/v2/simple/ventes/sync` accessible
- [ ] Logs détaillés activés
- [ ] Vérifier les erreurs dans les logs
- [ ] Tester avec curl/Postman

---

## 🎯 CONCLUSION

**Le code Django est CORRECT** : Les deux endpoints décrément bien le stock avec la même logique.

**Le problème est probablement côté MAUI** :
- Ventes non envoyées
- Header manquant
- Erreur HTTP non gérée
- Mauvaise URL

**Prochaine étape** : Activer les logs côté MAUI et tester avec Postman pour identifier la cause exacte.

---

**Document créé pour faciliter la comparaison et le debug** 🚀
