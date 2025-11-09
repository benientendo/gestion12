# 🚀 DÉMARRAGE RAPIDE - Synchronisation Ventes

## ✅ Modifications Effectuées

### 1. Fonction Créée
**Fichier :** `inventory/api_views_v2_simple.py`
- ✅ Fonction `sync_ventes_simple()` ajoutée (ligne 853)
- ✅ Gère la synchronisation de plusieurs ventes
- ✅ Validation automatique et rollback en cas d'erreur

### 2. Route Ajoutée
**Fichier :** `inventory/api_urls_v2_simple.py`
- ✅ Route `path('ventes/sync/', ...)` ajoutée (ligne 31)
- ✅ Endpoint : `POST /api/v2/simple/ventes/sync/`

## 🎯 Démarrage

### 1. Redémarrer Django

```powershell
cd C:\Users\PC\Documents\GestionMagazin
python manage.py runserver 10.28.176.224:8000
```

**Important :** Utilisez l'IP `10.28.176.224` (présente dans ALLOWED_HOSTS)

### 2. Tester l'Endpoint

#### Option A : Script Python (Recommandé)
```powershell
python test_sync_ventes.py
```

#### Option B : curl
```bash
curl -X POST http://10.28.176.224:8000/api/v2/simple/ventes/sync/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: 0a1badae951f8473" \
  -d '[{"numero_facture":"TEST-001","mode_paiement":"CASH","paye":true,"lignes":[{"article_id":6,"quantite":1,"prix_unitaire":40000}]}]'
```

## 📋 Format Minimal

```json
[
  {
    "lignes": [
      {
        "article_id": 6,
        "quantite": 1,
        "prix_unitaire": 40000
      }
    ]
  }
]
```

**Champs optionnels :**
- `numero_facture` - Généré auto si absent
- `mode_paiement` - Défaut : "CASH"
- `paye` - Défaut : true

## ✅ Réponse Attendue

```json
{
  "success": true,
  "message": "1 vente(s) synchronisée(s) avec succès",
  "boutique_id": 2,
  "boutique_nom": "messie vanza",
  "terminal": "Terminal messie vanza",
  "statistiques": {
    "total_envoyees": 1,
    "reussies": 1,
    "erreurs": 0
  },
  "ventes_creees": [
    {
      "numero_facture": "VENTE-2-20251029024500-0",
      "montant_total": "40000.00",
      "lignes": [...]
    }
  ]
}
```

## 🔍 Vérification

### 1. Vérifier les Logs Django
```
🔄 Synchronisation ventes pour boutique: messie vanza
📦 Nombre de ventes à synchroniser: 1
✅ Vente TEST-001 créée avec succès: 40000 CDF
```

### 2. Vérifier l'Historique
```bash
curl -H "X-Device-Serial: 0a1badae951f8473" \
     http://10.28.176.224:8000/api/v2/simple/ventes/historique/
```

## ❌ Résolution Erreurs

### Erreur 404
```
[29/Oct/2025 02:36:51] "POST /api/v2/simple/ventes/sync HTTP/1.1" 404
```

**Cause :** Route manquante (slash final)
**Solution :** Utiliser `/api/v2/simple/ventes/sync/` (avec slash final)

### Erreur 400 "Bad request syntax"
```
code 400, message Bad request syntax ('ef1')
```

**Cause :** Données JSON mal formées ou header manquant
**Solution :** 
1. Vérifier le JSON est valide
2. Ajouter header `Content-Type: application/json`
3. Ajouter header `X-Device-Serial: 0a1badae951f8473`

### Erreur "MISSING_SERIAL"
```json
{
  "error": "Numéro de série du terminal requis dans les headers",
  "code": "MISSING_SERIAL"
}
```

**Solution :** Ajouter le header `X-Device-Serial`

### Erreur "TERMINAL_NOT_FOUND"
```json
{
  "error": "Terminal non trouvé ou inactif",
  "code": "TERMINAL_NOT_FOUND"
}
```

**Solution :** Vérifier que le terminal existe et est actif dans la base de données

## 📚 Documentation Complète

- **Guide complet :** `GUIDE_SYNC_VENTES.md`
- **Script de test :** `test_sync_ventes.py`
- **Code MAUI :** Voir section "Intégration MAUI" dans le guide

## 🎉 Résultat

✅ Endpoint `/api/v2/simple/ventes/sync/` opérationnel
✅ Synchronisation par lots fonctionnelle
✅ Gestion automatique stock et montants
✅ Rollback en cas d'erreur
✅ Logs détaillés pour debug

**Prêt pour l'intégration MAUI !** 🚀
