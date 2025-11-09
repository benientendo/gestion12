# 📋 RÉSUMÉ EXÉCUTIF - Problème Stock Mode OFFLINE

**Date**: 4 novembre 2025  
**Priorité**: 🔴 HAUTE  
**Statut**: Investigation en cours

---

## 🎯 PROBLÈME

**Symptôme** : Le stock ne se met pas à jour après synchronisation des ventes en mode OFFLINE

**Impact** :
- ❌ Stock incohérent entre MAUI et Django
- ❌ Risque de vente d'articles en rupture
- ❌ Statistiques faussées

---

## ✅ CE QUI FONCTIONNE

### Mode ONLINE (connexion active)
- ✅ Ventes envoyées immédiatement via `/api/v2/ventes/`
- ✅ Stock mis à jour automatiquement
- ✅ MouvementStock créé pour traçabilité
- ✅ Aucun problème constaté

---

## ❌ CE QUI NE FONCTIONNE PAS

### Mode OFFLINE (sans connexion)
- ❌ Ventes synchronisées via `/api/v2/simple/ventes/sync`
- ❌ Stock ne se met pas à jour après synchronisation
- ❌ Incohérence entre MAUI et Django

---

## 🔍 INVESTIGATION

### ✅ Code Django vérifié

**Résultat** : Le code Django est **CORRECT** dans les deux cas !

#### Endpoint ONLINE : `/api/v2/ventes/`
```python
# Fichier: inventory/api_views_v2.py, lignes 512-522
article.quantite_stock -= quantite  # ✅ Décrémente le stock
article.save(update_fields=['quantite_stock'])  # ✅ Sauvegarde
MouvementStock.objects.create(...)  # ✅ Crée l'historique
```

#### Endpoint OFFLINE : `/api/v2/simple/ventes/sync`
```python
# Fichier: inventory/api_views_v2_simple.py, lignes 1038-1048
article.quantite_stock -= quantite  # ✅ Décrémente le stock
article.save(update_fields=['quantite_stock'])  # ✅ Sauvegarde
MouvementStock.objects.create(...)  # ✅ Crée l'historique
```

**Conclusion** : Les deux endpoints ont **exactement la même logique** de mise à jour du stock.

---

## 💡 HYPOTHÈSES

### 🔴 Hypothèse 1 : Ventes OFFLINE non envoyées (PROBABLE)
- Les ventes OFFLINE ne sont peut-être **pas envoyées** à Django
- Ou envoyées à un **mauvais endpoint** (`/api/v2/ventes/` au lieu de `/api/v2/simple/ventes/sync`)
- Ou envoyées avec des **données incorrectes**

### 🟡 Hypothèse 2 : Header manquant (POSSIBLE)
- Le header `X-Device-Serial` n'est pas envoyé en mode OFFLINE
- Django ne peut pas identifier le terminal → Erreur 400
- La vente n'est pas créée, donc pas de mise à jour du stock

### 🟡 Hypothèse 3 : Erreur HTTP non gérée (POSSIBLE)
- Django retourne une erreur (400, 403, 500)
- MAUI ne gère pas l'erreur correctement
- La vente est marquée comme "synchronisée" alors qu'elle ne l'est pas

### 🟢 Hypothèse 4 : Ventes en double (PEU PROBABLE)
- Si la vente existe déjà, Django l'ignore (pas de décrémentation)
- Mais cela ne devrait pas arriver si `numero_facture` est unique

---

## 🎯 ACTIONS IMMÉDIATES

### Pour l'équipe MAUI (PRIORITÉ 1) 🔴

1. **Activer les logs détaillés** pour le mode OFFLINE
   ```csharp
   Console.WriteLine($"📤 Synchronisation de {ventes.Count} vente(s)...");
   Console.WriteLine($"🔗 URL: {url}");
   Console.WriteLine($"📋 Headers: X-Device-Serial = {numeroSerie}");
   Console.WriteLine($"📦 Body: {jsonContent}");
   Console.WriteLine($"📥 Réponse: {response.StatusCode} - {responseContent}");
   ```

2. **Vérifier l'URL de synchronisation**
   ```csharp
   // ✅ CORRECT
   POST /api/v2/simple/ventes/sync
   
   // ❌ INCORRECT
   POST /api/v2/ventes/  // URL pour mode ONLINE uniquement
   ```

3. **Vérifier le header X-Device-Serial**
   ```csharp
   request.Headers.Add("X-Device-Serial", numeroSerie);
   ```

4. **Gérer les erreurs HTTP correctement**
   ```csharp
   if (!response.IsSuccessStatusCode)
   {
       // NE PAS marquer la vente comme synchronisée !
       throw new Exception($"Erreur: {response.StatusCode}");
   }
   ```

5. **Tester avec Postman**
   - Créer une requête POST vers `/api/v2/simple/ventes/sync`
   - Ajouter le header `X-Device-Serial`
   - Envoyer une vente de test
   - Vérifier que le stock est bien décrémenté

### Pour l'équipe Backend (PRIORITÉ 2) 🟡

1. **Ajouter plus de logs** dans `sync_ventes_simple()`
   ```python
   logger.info(f"📥 Réception de {len(ventes_data)} vente(s)")
   logger.info(f"🔑 Numéro de série: {numero_serie}")
   logger.info(f"🏪 Terminal: {terminal.nom_terminal}")
   logger.info(f"📦 Stock avant: {article.quantite_stock}")
   logger.info(f"📦 Stock après: {article.quantite_stock - quantite}")
   ```

2. **Vérifier les logs Django** pour les synchronisations récentes
   ```bash
   grep "sync_ventes_simple" /path/to/django.log
   ```

3. **Créer un endpoint de diagnostic** (optionnel)
   ```python
   @api_view(['GET'])
   def diagnostic_sync(request):
       numero_serie = request.headers.get('X-Device-Serial')
       terminal = Client.objects.filter(numero_serie=numero_serie).first()
       return Response({
           'terminal_trouve': bool(terminal),
           'boutique_id': terminal.boutique.id if terminal else None,
           'peut_synchroniser': bool(terminal and terminal.boutique)
       })
   ```

---

## 📊 TESTS DE VALIDATION

### Test 1 : Postman (MAUI)
```
POST http://serveur/api/v2/simple/ventes/sync
Header: X-Device-Serial: VOTRE_NUMERO_SERIE
Body: {
  "ventes": [{
    "numero_facture": "TEST-001",
    "mode_paiement": "CASH",
    "paye": true,
    "lignes": [{
      "article_id": 6,
      "quantite": 1,
      "prix_unitaire": 100000.00
    }]
  }]
}
```

**Résultat attendu** :
- ✅ Status 200/201
- ✅ Stock décrémenté de 1
- ✅ Vente visible dans Django

### Test 2 : Logs Django (Backend)
```bash
tail -f django.log | grep "sync_ventes_simple"
```

**Résultat attendu** :
- ✅ `Terminal trouvé: ...`
- ✅ `Vente créée: TEST-001`
- ✅ `Stock mis à jour pour article 6`

### Test 3 : Base de données (Backend)
```sql
-- Vérifier la vente
SELECT * FROM inventory_vente WHERE numero_facture = 'TEST-001';

-- Vérifier le mouvement de stock
SELECT * FROM inventory_mouvementstock WHERE commentaire LIKE '%TEST-001%';

-- Vérifier le stock
SELECT id, nom, quantite_stock FROM inventory_article WHERE id = 6;
```

---

## 📁 DOCUMENTS CRÉÉS

1. **DIAGNOSTIC_STOCK_ONLINE_VS_OFFLINE.md** 📄
   - Analyse détaillée du problème
   - Comparaison des deux endpoints
   - Hypothèses et vérifications

2. **CHECKLIST_DEBUG_MAUI_OFFLINE.md** ✅
   - Checklist complète pour l'équipe MAUI
   - Code de test minimal
   - Étapes de validation

3. **RESUME_PROBLEME_STOCK_OFFLINE.md** 📋 (ce document)
   - Résumé exécutif
   - Actions prioritaires
   - Tests de validation

---

## 🚀 PROCHAINES ÉTAPES

### Immédiat (Aujourd'hui)
1. ✅ Équipe MAUI : Activer les logs détaillés
2. ✅ Équipe MAUI : Tester avec Postman
3. ✅ Équipe Backend : Vérifier les logs Django

### Court terme (Cette semaine)
1. ✅ Identifier la cause exacte du problème
2. ✅ Corriger le code MAUI si nécessaire
3. ✅ Tester en conditions réelles

### Moyen terme (Après correction)
1. ✅ Ajouter des tests automatisés
2. ✅ Améliorer la gestion d'erreur
3. ✅ Documenter le processus de synchronisation

---

## 📞 CONTACTS

**Équipe MAUI** : Responsable de l'investigation côté application mobile  
**Équipe Backend** : Support et vérification des logs Django  
**Coordination** : Suivi quotidien jusqu'à résolution

---

## 🎯 OBJECTIF

**Résoudre le problème de synchronisation du stock en mode OFFLINE dans les 48h**

**Critère de succès** :
- ✅ Stock mis à jour correctement après synchronisation OFFLINE
- ✅ Logs détaillés pour tracer les problèmes futurs
- ✅ Tests automatisés pour éviter les régressions

---

**Document créé le 4 novembre 2025**  
**Dernière mise à jour : 4 novembre 2025**  
**Statut : En investigation** 🔍
