# 🔧 CORRECTION - Montants de Ventes à 0.00 CDF

## 🚨 Problème Identifié

Les ventes affichées dans l'historique ont des montants à **0.00 CDF** alors qu'elles contiennent des lignes avec des prix.

## 🔍 Cause

Les ventes ont été créées avec `montant_total = 0` et n'ont pas été mises à jour avec le montant calculé à partir des lignes de vente.

## ✅ Solution en 2 Étapes

### Étape 1 : Vérifier l'État Actuel

```bash
cd C:\Users\PC\Documents\GestionMagazin
python verifier_ventes.py
```

**Ce script va :**
- ✅ Afficher toutes les ventes
- ✅ Montrer le montant enregistré vs le montant calculé
- ✅ Identifier les ventes avec problème
- ✅ Afficher les détails de chaque ligne de vente

**Exemple de sortie :**
```
🧾 Vente: VENTE-2-20251029010000
   Date: 29/10/2025 01:00
   Boutique: Ma Boutique
   Terminal: Terminal Test
   Montant enregistré: 0.00 CDF
   
   📦 Lignes de vente (2):
      - Samsung S24
        Quantité: 1
        Prix unitaire: 100000.00 CDF
        Sous-total: 100000.00 CDF
      
      - iPhone 15
        Quantité: 2
        Prix unitaire: 150000.00 CDF
        Sous-total: 300000.00 CDF
   
   💰 Montant calculé: 400000.00 CDF
   ⚠️  PROBLÈME: Le montant enregistré (0.00) ne correspond pas au montant calculé (400000.00)
```

### Étape 2 : Corriger les Montants

```bash
cd C:\Users\PC\Documents\GestionMagazin
python corriger_montants_ventes.py
```

**Ce script va :**
- ✅ Recalculer le montant de chaque vente
- ✅ Mettre à jour la base de données
- ✅ Afficher les corrections effectuées

**Exemple de sortie :**
```
✅ Vente #VENTE-2-20251029010000 corrigée:
   Ancien montant: 0.00 CDF
   Nouveau montant: 400000.00 CDF
   Lignes: 2

RÉSUMÉ
✅ Ventes correctes: 0
🔧 Ventes corrigées: 5
📊 Total traité: 5

✨ Correction terminée avec succès!
```

### Étape 3 : Vérifier dans l'API

Après correction, testez l'API :

```bash
curl -H "X-Device-Serial: 0a1badae951f8473" \
     http://192.168.52.224:8000/api/v2/simple/ventes/historique/
```

**Vous devriez maintenant voir :**
```json
{
  "success": true,
  "ventes": [
    {
      "numero_facture": "VENTE-2-20251029010000",
      "montant_total": "400000.00",
      "lignes": [
        {
          "article_nom": "Samsung S24",
          "quantite": 1,
          "prix_unitaire": "100000.00",
          "sous_total": "100000.00"
        }
      ]
    }
  ]
}
```

## 🛡️ Prévention Future

Le code de création de vente a été corrigé pour calculer automatiquement le montant total :

```python
# inventory/api_views_v2_simple.py (lignes 536-538)
# Mettre à jour le montant total de la vente
vente.montant_total = montant_total
vente.save(update_fields=['montant_total'])
```

**Toutes les nouvelles ventes auront le bon montant automatiquement !** ✅

## 📊 Vérification Régulière

Pour vérifier périodiquement l'état des ventes :

```bash
# Vérification rapide
python verifier_ventes.py

# Si problème détecté
python corriger_montants_ventes.py
```

## 🔍 Détails Techniques

### Calcul du Montant

Le montant total d'une vente est calculé comme suit :

```
montant_total = Σ (prix_unitaire × quantite) pour chaque ligne
```

### Exemple de Calcul

```
Vente avec 3 lignes:
- Article A: 2 × 50000 = 100000 CDF
- Article B: 1 × 75000 = 75000 CDF
- Article C: 3 × 25000 = 75000 CDF
────────────────────────────────────
Total:                  250000 CDF
```

### Modèles Concernés

- **Vente** : Contient `montant_total` (DecimalField)
- **LigneVente** : Contient `prix_unitaire` et `quantite`
- **Relation** : Vente → LigneVente (1:N)

## ⚠️ Important

- ✅ **Sauvegarder la base** avant correction (optionnel)
- ✅ **Arrêter le serveur Django** pendant la correction
- ✅ **Vérifier les résultats** après correction
- ✅ **Tester l'API** pour confirmer

## 🎯 Résultat Attendu

Après correction :
- ✅ Tous les montants de ventes corrects
- ✅ Historique MAUI affiche les bons montants
- ✅ Statistiques CA correctes
- ✅ Nouvelles ventes créées avec bon montant

## 📞 En Cas de Problème

Si les scripts rencontrent une erreur :

1. **Vérifier que Django fonctionne** : `python manage.py check`
2. **Vérifier les migrations** : `python manage.py showmigrations`
3. **Consulter les logs** : Les scripts affichent les erreurs détaillées

---

**Les scripts sont prêts à l'emploi !** 🚀
