# 📚 INDEX DE LA DOCUMENTATION - Problème Stock Mode OFFLINE

**Date de création** : 4 novembre 2025  
**Statut** : Investigation en cours

---

## 🎯 RÉSUMÉ DU PROBLÈME

**Observation** : Le stock ne se met pas à jour après synchronisation des ventes en mode OFFLINE, alors qu'il fonctionne correctement en mode ONLINE.

**Cause identifiée** : Le code Django est correct (les deux endpoints décrément le stock). Le problème est probablement côté MAUI (ventes non envoyées, header manquant, ou erreur HTTP non gérée).

---

## 📁 DOCUMENTS CRÉÉS

### 🔴 PRIORITÉ 1 - Pour l'équipe MAUI

#### 1. **GUIDE_RESOLUTION_RAPIDE.md** ⭐ **COMMENCER ICI**
- **Objectif** : Résoudre le problème en 30 minutes
- **Contenu** : 
  - 7 étapes de vérification dans l'ordre
  - Logs à ajouter (code prêt à copier)
  - Tests rapides avec résultats attendus
  - Décisions rapides selon les logs
- **Pour qui** : Développeur MAUI qui doit corriger le bug
- **Temps** : 30 minutes

#### 2. **CHECKLIST_DEBUG_MAUI_OFFLINE.md** ✅
- **Objectif** : Checklist complète de debug
- **Contenu** :
  - Vérifications détaillées (URL, header, format, erreurs)
  - Code de test minimal
  - Comparaison ONLINE vs OFFLINE
  - Logs détaillés à activer
- **Pour qui** : Développeur MAUI qui veut comprendre en profondeur
- **Temps** : 1-2 heures

---

### 🟡 PRIORITÉ 2 - Pour comprendre le problème

#### 3. **DIAGNOSTIC_STOCK_ONLINE_VS_OFFLINE.md** 🔍
- **Objectif** : Comprendre pourquoi ça fonctionne en ONLINE mais pas en OFFLINE
- **Contenu** :
  - Analyse détaillée des deux modes
  - Comparaison du code Django
  - Hypothèses sur la cause
  - Vérifications à faire
- **Pour qui** : Équipe technique (MAUI + Backend)
- **Temps** : 15 minutes de lecture

#### 4. **COMPARAISON_ENDPOINTS_ONLINE_OFFLINE.md** 📊
- **Objectif** : Comparer en détail les deux endpoints Django
- **Contenu** :
  - Tableau comparatif complet
  - Code source des deux endpoints
  - Différences d'authentification
  - Format des données
  - Gestion des erreurs
- **Pour qui** : Développeurs qui veulent voir le code Django
- **Temps** : 20 minutes de lecture

---

### 🟢 PRIORITÉ 3 - Pour la coordination

#### 5. **RESUME_PROBLEME_STOCK_OFFLINE.md** 📋
- **Objectif** : Résumé exécutif pour les managers
- **Contenu** :
  - Problème en 2 phrases
  - Ce qui fonctionne / ne fonctionne pas
  - Hypothèses principales
  - Actions immédiates
  - Tests de validation
- **Pour qui** : Chef de projet, Product Owner
- **Temps** : 5 minutes de lecture

---

## 🚀 PAR OÙ COMMENCER ?

### Si vous êtes développeur MAUI et devez corriger le bug :
1. ⭐ **Lire** : `GUIDE_RESOLUTION_RAPIDE.md`
2. ✅ **Suivre** : Les 7 étapes dans l'ordre
3. 📝 **Copier** : Les logs fournis dans le guide
4. 🧪 **Tester** : Faire une vente OFFLINE et regarder les logs
5. 🎯 **Corriger** : Selon les résultats des logs

**Temps total : 30-60 minutes**

---

### Si vous voulez comprendre le problème en profondeur :
1. 📋 **Lire** : `RESUME_PROBLEME_STOCK_OFFLINE.md` (5 min)
2. 🔍 **Lire** : `DIAGNOSTIC_STOCK_ONLINE_VS_OFFLINE.md` (15 min)
3. 📊 **Lire** : `COMPARAISON_ENDPOINTS_ONLINE_OFFLINE.md` (20 min)
4. ✅ **Appliquer** : `CHECKLIST_DEBUG_MAUI_OFFLINE.md` (1-2h)

**Temps total : 2-3 heures**

---

### Si vous êtes manager et voulez un résumé :
1. 📋 **Lire** : `RESUME_PROBLEME_STOCK_OFFLINE.md` (5 min)
2. 🎯 **Vérifier** : Section "Actions immédiates"
3. 📞 **Coordonner** : Équipe MAUI + Backend

**Temps total : 10 minutes**

---

## 🔧 OUTILS FOURNIS

### Code prêt à l'emploi

#### 1. Logs de debug (dans GUIDE_RESOLUTION_RAPIDE.md)
```csharp
// Fonction complète avec tous les logs
public async Task<bool> SynchroniserVentesOffline()
{
    // ... code avec logs détaillés
}
```

#### 2. Code de test minimal (dans CHECKLIST_DEBUG_MAUI_OFFLINE.md)
```csharp
// Page de test pour vérifier la synchronisation
public async Task TestSyncManuel()
{
    // ... code de test
}
```

#### 3. Test Postman (dans tous les documents)
```
POST http://serveur/api/v2/simple/ventes/sync
Header: X-Device-Serial: NUMERO_SERIE
Body: { "ventes": [...] }
```

---

## 📊 RÉSULTATS ATTENDUS

### Après avoir suivi le GUIDE_RESOLUTION_RAPIDE.md :

#### ✅ Cas 1 : Problème identifié et corrigé
```
📊 SYNC: 1 vente(s) à synchroniser
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/simple/ventes/sync
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
📥 SYNC: Status = OK
✅ SYNC: 1 vente(s) créée(s)
💾 SYNC: Base de données mise à jour
```

→ **Stock mis à jour correctement** ✅

#### ❌ Cas 2 : Problème identifié mais nécessite correction
```
📊 SYNC: 1 vente(s) à synchroniser
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/ventes/  ← MAUVAISE URL
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
📥 SYNC: Status = NotFound
❌ SYNC: Erreur HTTP
```

→ **Corriger l'URL** → Retester

#### ❌ Cas 3 : Problème backend
```
📊 SYNC: 1 vente(s) à synchroniser
🔗 SYNC: URL = http://192.168.1.100:8000/api/v2/simple/ventes/sync
📋 SYNC: Header X-Device-Serial = 0a1badae951f8473
📥 SYNC: Status = InternalServerError
❌ SYNC: Erreur HTTP
```

→ **Contacter équipe backend** avec les logs

---

## 🎯 CRITÈRES DE SUCCÈS

### Le problème est résolu quand :

1. ✅ Les ventes OFFLINE sont synchronisées sans erreur
2. ✅ Le stock est décrémenté correctement après synchronisation
3. ✅ Les logs montrent "Status = OK" et "ventes_creees > 0"
4. ✅ Le stock dans Django correspond au stock dans MAUI
5. ✅ Les MouvementStock sont créés pour traçabilité

### Test de validation final :

1. **Vérifier le stock initial** dans Django (ex: Article 6 = 10 unités)
2. **Faire une vente OFFLINE** dans MAUI (ex: 2 unités de l'article 6)
3. **Synchroniser** les ventes
4. **Vérifier le stock final** dans Django (doit être 8 unités)
5. **Vérifier le MouvementStock** dans Django (doit avoir une entrée -2)

---

## 📞 SUPPORT

### Si le problème persiste après avoir suivi tous les guides :

#### Informations à fournir :

1. **Logs MAUI complets** (copier toute la sortie console)
2. **Test Postman** (copier la requête et la réponse)
3. **Informations système** :
   - Version app MAUI
   - Version Django
   - Numéro de série du terminal
   - ID de la boutique
4. **Exemple de vente** qui ne synchronise pas (JSON)

#### Contacter :

- **Équipe Backend** : Si Postman ne fonctionne pas
- **Équipe MAUI** : Si Postman fonctionne mais pas MAUI

---

## 📝 HISTORIQUE

| Date | Action | Résultat |
|------|--------|----------|
| 4 nov 2025 | Observation du problème | Mode OFFLINE ne met pas à jour le stock |
| 4 nov 2025 | Analyse du code Django | Code correct dans les deux endpoints |
| 4 nov 2025 | Création documentation | 5 documents créés pour investigation |
| 4 nov 2025 | En attente | Tests côté MAUI avec logs détaillés |

---

## 🔄 PROCHAINES ÉTAPES

1. ✅ **Équipe MAUI** : Ajouter les logs et tester (30 min)
2. ⏳ **Analyse des logs** : Identifier la cause exacte (15 min)
3. ⏳ **Correction** : Appliquer le fix (30 min)
4. ⏳ **Tests** : Valider que le problème est résolu (15 min)
5. ⏳ **Documentation** : Mettre à jour ce document avec la solution

**Temps total estimé : 1h30**

---

## 🎉 CONCLUSION

**Documentation complète créée** pour faciliter l'investigation et la résolution du problème.

**Point de départ recommandé** : `GUIDE_RESOLUTION_RAPIDE.md`

**Objectif** : Résoudre le problème en moins de 2 heures.

---

**Créé le** : 4 novembre 2025  
**Dernière mise à jour** : 4 novembre 2025  
**Statut** : 📖 Documentation prête - En attente des tests MAUI
