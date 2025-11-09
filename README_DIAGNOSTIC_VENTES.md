# 🔍 DIAGNOSTIC VENTES - GUIDE RAPIDE

## 🎯 Objectif

Identifier pourquoi les ventes synchronisées depuis MAUI n'apparaissent pas dans l'interface Django.

---

## 📁 Fichiers Fournis

### Scripts Python
1. **`verifier_ventes_backend.py`** - Diagnostic complet
2. **`corriger_ventes_orphelines.py`** - Correction automatique

### Documentation
3. **`DIAGNOSTIC_BACKEND_VENTES.md`** - Guide technique détaillé
4. **`RAPPORT_POUR_EQUIPE_DJANGO.md`** - Rapport d'analyse complet
5. **`RESUME_URGENT_EQUIPE_DJANGO.txt`** - Résumé visuel

---

## ⚡ Démarrage Rapide (5 minutes)

### Étape 1: Exécuter le diagnostic

```bash
cd C:\Users\PC\Documents\GestionMagazin
python verifier_ventes_backend.py
```

### Étape 2: Analyser les résultats

**Chercher ces lignes clés:**

```
📊 Total ventes en base: X
⚠️ VENTES ORPHELINES (sans boutique): Y
```

**Interprétation:**

| Résultat | Signification | Action |
|----------|---------------|--------|
| X = 0 | Ventes n'arrivent PAS à Django | Vérifier communication MAUI → Django |
| X > 0, Y = 0 | Ventes OK, problème d'affichage | Vérifier les vues Django |
| X > 0, Y > 0 | **PROBLÈME TROUVÉ!** Ventes sans boutique | Exécuter script de correction |

### Étape 3: Correction (si nécessaire)

```bash
python corriger_ventes_orphelines.py
```

---

## 🔴 Problèmes Fréquents

### Problème #1: Ventes orphelines (90% des cas)

**Symptôme:**
```
⚠️ VENTES ORPHELINES (sans boutique): 15
```

**Cause:** Terminal MAUI non associé à une boutique

**Solution rapide:**
```bash
python corriger_ventes_orphelines.py
```

**Solution manuelle:**
```python
python manage.py shell

from inventory.models import Client, Boutique

# Associer le terminal à une boutique
terminal = Client.objects.get(numero_serie="NUMERO_SERIE")
boutique = Boutique.objects.get(id=2)  # ID de la bonne boutique
terminal.boutique = boutique
terminal.save()
```

---

### Problème #2: Code API incorrect

**Vérifier:** `inventory/api_views_v2_simple.py` ligne ~1006

**Code attendu:**
```python
vente = Vente.objects.create(
    numero_facture=numero_facture,
    montant_total=0,
    mode_paiement=vente_data.get('mode_paiement', 'CASH'),
    paye=vente_data.get('paye', True),
    boutique=boutique,        # ✅ DOIT EXISTER
    client_maui=terminal,     # ✅ DOIT EXISTER
    # ...
)
```

**Si ces lignes manquent:** Les ajouter et redémarrer Django

---

### Problème #3: Terminal introuvable

**Symptôme:**
```
❌ Terminal non trouvé: 0a1badae951f8473
```

**Vérifier:**
```python
python manage.py shell

from inventory.models import Client

# Lister tous les terminaux
for t in Client.objects.all():
    print(f"{t.numero_serie} - {t.nom_terminal} - Actif: {t.est_actif}")
```

**Solution:** Créer ou activer le terminal manquant

---

## 📊 Checklist de Vérification

Après correction, vérifier que:

- [ ] `Total ventes en base > 0`
- [ ] `Ventes orphelines = 0`
- [ ] `Ventes sans terminal = 0`
- [ ] Chaque vente a une boutique
- [ ] Chaque vente a un terminal
- [ ] Ventes visibles dans `/commercant/dashboard/`
- [ ] Chiffre d'affaires correct

---

## 🆘 Support

### Si le problème persiste

**Envoyer:**
1. Résultat complet de `python verifier_ventes_backend.py`
2. Logs Django (dernières 50 lignes)
3. Numéro de série du terminal MAUI

### Informations système

```bash
# Version Django
python manage.py --version

# Migrations appliquées
python manage.py showmigrations inventory

# État de la base de données
python manage.py dbshell
SELECT COUNT(*) FROM inventory_vente;
SELECT COUNT(*) FROM inventory_vente WHERE boutique_id IS NULL;
```

---

## 📚 Documentation Complète

Pour plus de détails, consulter:

- **`DIAGNOSTIC_BACKEND_VENTES.md`** - Guide technique complet
- **`RAPPORT_POUR_EQUIPE_DJANGO.md`** - Analyse approfondie
- **`RESUME_URGENT_EQUIPE_DJANGO.txt`** - Vue d'ensemble visuelle

---

## ✅ Résolution Typique

**Temps estimé:** 5-10 minutes

**Étapes:**
1. Diagnostic → 2 min
2. Correction → 3 min
3. Vérification → 2 min

**Taux de succès:** 95% avec les scripts fournis

---

**Dernière mise à jour:** 5 novembre 2024  
**Version:** 1.0
