# 🔍 DEBUG - Montants à 0.00 CDF

## 🚨 Problème Observé

Les nouvelles ventes créées depuis MAUI affichent `0.00 CDF` dans l'historique backend, même après la correction.

**Exemple :**
- `VENTE-2-20251029031032` : **0.00 CDF** ❌
- Ventes corrigées : Montants OK ✅

## 🔍 Diagnostic

### Hypothèse 1 : MAUI utilise le mauvais endpoint

**Vérification :**
Regardez les logs Django quand vous créez une vente depuis MAUI :

```
[29/Oct/2025 03:10:32] "POST /api/v2/simple/ventes/ HTTP/1.1" 201
```

**Si vous voyez `/ventes/` :** MAUI utilise le bon endpoint
**Si vous voyez `/ventes/sync` :** MAUI utilise l'endpoint de synchronisation

### Hypothèse 2 : Les données envoyées sont incorrectes

**Vérification dans les logs Django :**

Cherchez ces lignes dans la console Django :
```
📦 Données vente reçues: {...}
✅ Vente créée: VENTE-2-20251029031032
💰 Montant total calculé: XXXXX CDF
```

Si vous ne voyez pas ces logs, le problème est dans le code.

### Hypothèse 3 : Le montant n'est pas sauvegardé

**Test rapide :**

1. Créez une vente depuis MAUI
2. Notez le numéro de facture (ex: `VENTE-2-20251029031032`)
3. Lancez le script de vérification :

```powershell
python verifier_ventes.py
```

4. Regardez si cette vente a :
   - `montant_total` = 0 dans la base ❌
   - Mais des lignes avec des prix ✅

## 🔧 Solutions

### Solution 1 : Ajouter des Logs de Debug

Ajoutez des logs dans `create_vente_simple()` pour voir ce qui se passe :

```python
# Ligne 537-538
logger.info(f"💰 Calcul montant_total: {montant_total}")
vente.montant_total = montant_total
vente.save(update_fields=['montant_total'])
logger.info(f"✅ Montant sauvegardé: {vente.montant_total}")
```

### Solution 2 : Vérifier que MAUI envoie bien les lignes

Dans MAUI, vérifiez que la requête POST contient :

```json
{
  "lignes": [
    {
      "article_id": 6,
      "quantite": 1,
      "prix_unitaire": 40000
    }
  ]
}
```

**Si `lignes` est vide ou absent :** Le montant sera 0 !

### Solution 3 : Forcer le recalcul après chaque vente

Modifiez le code pour recalculer le montant même si déjà défini :

```python
# Après la création de toutes les lignes
montant_total = sum(
    ligne.prix_unitaire * ligne.quantite 
    for ligne in vente.lignes.all()
)
vente.montant_total = montant_total
vente.save(update_fields=['montant_total'])
```

## 🧪 Test Immédiat

### Test 1 : Créer une vente via curl

```bash
curl -X POST http://10.28.176.224:8000/api/v2/simple/ventes/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: 0a1badae951f8473" \
  -d '{
    "lignes": [
      {
        "article_id": 6,
        "quantite": 1,
        "prix_unitaire": 40000
      }
    ]
  }'
```

**Résultat attendu :**
```json
{
  "success": true,
  "vente": {
    "montant_total": 40000.00,  // ✅ Doit être 40000, pas 0
    ...
  }
}
```

### Test 2 : Vérifier dans la base

Après le test curl, vérifiez immédiatement :

```powershell
python verifier_ventes.py
```

La dernière vente doit avoir le bon montant.

## 📋 Checklist de Vérification

- [ ] Les logs Django montrent le montant calculé
- [ ] Les logs Django montrent le montant sauvegardé
- [ ] Le test curl retourne le bon montant
- [ ] Le script `verifier_ventes.py` confirme le montant
- [ ] L'historique MAUI affiche le bon montant
- [ ] L'interface backend affiche le bon montant

## 🎯 Action Immédiate

**Lancez ce test maintenant :**

```powershell
# Terminal 1 : Regardez les logs Django
# Vous devriez voir les logs de création de vente

# Terminal 2 : Créez une vente de test
curl -X POST http://10.28.176.224:8000/api/v2/simple/ventes/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: 0a1badae951f8473" \
  -d '{"lignes":[{"article_id":6,"quantite":1,"prix_unitaire":40000}]}'
```

**Regardez les logs Django et dites-moi ce que vous voyez !**
