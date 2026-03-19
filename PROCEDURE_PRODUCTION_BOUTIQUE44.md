# 🚀 PROCÉDURE PRODUCTION - BOUTIQUE 44 (KMC KIMPESE 01)

## 🎯 OBJECTIF

Corriger la gestion des variants pour la boutique 44 en production sur Scalingo.

---

## ÉTAPE 1 : DIAGNOSTIC (OBLIGATOIRE)

### 1.1 Se connecter à Scalingo

```bash
# Se connecter à Scalingo
scalingo login

# Accéder au shell Django de votre application
scalingo --app votre-app-name run python manage.py shell
```

### 1.2 Exécuter le diagnostic

Dans le shell Django, copiez-collez ce code :

```python
from inventory.models import Article, VarianteArticle, Boutique
from django.db.models import Sum

print("\n" + "="*80)
print("🔍 DIAGNOSTIC VARIANTS - BOUTIQUE 44")
print("="*80 + "\n")

boutique = Boutique.objects.get(id=44)
print(f"✅ Boutique : {boutique.nom}\n")

articles_avec_variants = Article.objects.filter(
    boutique_id=44,
    variantes__isnull=False
).distinct().prefetch_related('variantes')

print(f"📦 Articles avec variants : {articles_avec_variants.count()}\n")

total_stock_parents = 0
total_stock_variants = 0

for article in articles_avec_variants:
    variants = article.variantes.filter(est_actif=True)
    if not variants.exists():
        continue
    
    stock_parent = article.quantite_stock
    somme_stock_variants = variants.aggregate(total=Sum('quantite_stock'))['total'] or 0
    
    print(f"📦 {article.nom} (ID: {article.id})")
    print(f"   ├─ Stock parent : {stock_parent}")
    
    for variant in variants:
        if variant.quantite_stock > 0:
            print(f"   │  ├─ {variant.nom_variante}: {variant.quantite_stock}")
    
    print(f"   ├─ Somme variants : {somme_stock_variants}")
    print(f"   └─ TOTAL : {stock_parent + somme_stock_variants}")
    
    if somme_stock_variants > 0:
        print(f"   ⚠️  À MIGRER : {somme_stock_variants} unités\n")
    else:
        print(f"   ✅ Déjà migré\n")
    
    total_stock_parents += stock_parent
    total_stock_variants += somme_stock_variants

print("="*80)
print(f"Stock parents : {total_stock_parents}")
print(f"Stock variants : {total_stock_variants}")
print(f"TOTAL : {total_stock_parents + total_stock_variants}")
print("="*80 + "\n")

if total_stock_variants > 0:
    print("⚠️  MIGRATION NÉCESSAIRE")
    print(f"   {total_stock_variants} unités à transférer")
else:
    print("✅ AUCUNE MIGRATION NÉCESSAIRE")
```

### 1.3 Interpréter le résultat

**CAS A : Stock sur les variants (migration nécessaire)**
```
📦 Déodorant (ID: 123)
   ├─ Stock parent : 0
   │  ├─ Rouge: 30
   │  ├─ Bleu: 40
   │  ├─ Vert: 30
   ├─ Somme variants : 100
   └─ TOTAL : 100
   ⚠️  À MIGRER : 100 unités

Stock variants : 100
⚠️  MIGRATION NÉCESSAIRE
```
→ **Passez à l'ÉTAPE 2**

**CAS B : Stock déjà sur le parent (pas de migration)**
```
📦 Déodorant (ID: 123)
   ├─ Stock parent : 100
   ├─ Somme variants : 0
   └─ TOTAL : 100
   ✅ Déjà migré

Stock variants : 0
✅ AUCUNE MIGRATION NÉCESSAIRE
```
→ **Passez directement à l'ÉTAPE 3**

---

## ÉTAPE 2 : MIGRATION DES STOCKS (si nécessaire)

### 2.1 Copier le fichier de migration sur Scalingo

```bash
# Depuis votre machine locale
scp inventory/management/commands/migrer_stocks_variants.py scalingo@ssh.osc-fr1.scalingo.com:~/app/inventory/management/commands/
```

Ou créez le fichier directement sur Scalingo via l'interface web.

### 2.2 Tester la migration (simulation)

```bash
# Sur Scalingo
scalingo --app votre-app-name run python manage.py migrer_stocks_variants --dry-run --boutique-id 44
```

**Vérifiez attentivement le résultat !**

### 2.3 Exécuter la migration réelle

```bash
# Sur Scalingo - MIGRATION RÉELLE
scalingo --app votre-app-name run python manage.py migrer_stocks_variants --boutique-id 44
```

**Résultat attendu :**
```
✅ MIGRATION TERMINÉE

📊 Résumé :
   ├─ Articles migrés : 15
   └─ Stock total transféré : 1250 unités

✅ Les stocks des variants ont été transférés aux parents
```

### 2.4 Vérifier après migration

Relancez le diagnostic (ÉTAPE 1.2) pour confirmer :
```
Stock variants : 0
✅ AUCUNE MIGRATION NÉCESSAIRE
```

---

## ÉTAPE 3 : DÉPLOYER LES MODIFICATIONS DJANGO

### 3.1 Déployer le code Django corrigé

```bash
# Depuis votre machine locale
git add .
git commit -m "Fix: Stock variants sur parent uniquement (boutique 44)"
git push scalingo master
```

**Fichiers modifiés :**
- `inventory/api_views_v2_simple.py` (vente décrémente parent)
- `inventory/models.py` (propriété stock_disponible)
- `inventory/views_commercant.py` (verifier_code_barre corrigé)

### 3.2 Vérifier le déploiement

```bash
# Vérifier les logs
scalingo --app votre-app-name logs --lines 100
```

---

## ÉTAPE 4 : DÉPLOYER MAUI (CLIENTS)

### 4.1 Compiler la nouvelle version MAUI

Sur votre machine de développement :

```bash
cd c:\Users\PC\Documents\Gestion_et_ventes\VenteMagazin
dotnet build -c Release
```

### 4.2 Déployer sur les terminaux de la boutique 44

**Option A : Mise à jour simple (recommandé)**
1. Installer la nouvelle version MAUI sur les terminaux
2. Redémarrer l'application
3. L'application utilisera automatiquement le stock du parent

**Option B : Avec réinitialisation (plus sûr)**
1. Installer la nouvelle version MAUI
2. Menu → Réinitialiser
3. Re-synchroniser les articles

### 4.3 Tester sur un terminal

1. Synchroniser les articles
2. Chercher un article avec variants
3. Vérifier que le stock affiché est correct
4. Vendre un variant
5. Vérifier que le stock parent est décrémenté

---

## ÉTAPE 5 : VALIDATION

### 5.1 Tests à effectuer

**Test 1 : Affichage du stock**
- [ ] Chercher un article avec variants
- [ ] Vérifier que tous les variants affichent le même stock (celui du parent)

**Test 2 : Vente avec variant**
- [ ] Vendre 5 unités d'un variant (ex: Rouge)
- [ ] Vérifier que le stock parent est décrémenté de 5
- [ ] Vérifier que tous les variants affichent le nouveau stock

**Test 3 : Synchronisation**
- [ ] Faire une vente sur un terminal
- [ ] Synchroniser
- [ ] Vérifier que le stock est mis à jour sur Django
- [ ] Synchroniser un autre terminal
- [ ] Vérifier que le stock est cohérent

### 5.2 Vérification Django

Dans l'admin Django ou le shell :

```python
from inventory.models import Article, MouvementStock

# Vérifier les mouvements de stock récents
mouvements = MouvementStock.objects.filter(
    article__boutique_id=44
).order_by('-date_mouvement')[:10]

for m in mouvements:
    print(f"{m.date_mouvement} | {m.article.nom} | {m.type_mouvement} | {m.quantite} | Stock: {m.stock_avant} → {m.stock_apres}")
```

---

## 🚨 ROLLBACK EN CAS DE PROBLÈME

### Si problème côté Django

```bash
# Restaurer l'ancienne version
git revert HEAD
git push scalingo master
```

### Si problème côté MAUI

1. Réinstaller l'ancienne version MAUI
2. Réinitialiser les terminaux
3. Re-synchroniser

---

## 📋 CHECKLIST COMPLÈTE

### Préparation
- [ ] Sauvegarder la base de données Scalingo
- [ ] Prévenir les utilisateurs de la boutique 44
- [ ] Planifier une fenêtre de maintenance (si possible)

### Diagnostic
- [ ] Exécuter le diagnostic en production
- [ ] Noter le nombre d'articles avec variants
- [ ] Noter le stock total à migrer

### Migration (si nécessaire)
- [ ] Tester avec `--dry-run`
- [ ] Exécuter la migration réelle
- [ ] Vérifier les logs de migration
- [ ] Re-exécuter le diagnostic pour confirmer

### Déploiement Django
- [ ] Pousser le code corrigé sur Scalingo
- [ ] Vérifier les logs de déploiement
- [ ] Tester l'API depuis Postman/curl

### Déploiement MAUI
- [ ] Compiler la nouvelle version
- [ ] Déployer sur 1 terminal pilote
- [ ] Tester le terminal pilote
- [ ] Déployer sur tous les terminaux de la boutique 44

### Validation
- [ ] Test affichage stock
- [ ] Test vente avec variant
- [ ] Test synchronisation
- [ ] Surveiller pendant 24-48h

---

## 🎯 RÉSUMÉ RAPIDE

**Si le diagnostic montre que les stocks sont sur les variants :**
```bash
# 1. Migrer les stocks
scalingo run python manage.py migrer_stocks_variants --boutique-id 44

# 2. Déployer Django
git push scalingo master

# 3. Déployer MAUI
# Installer nouvelle version + réinitialiser terminaux
```

**Si le diagnostic montre que les stocks sont déjà sur le parent :**
```bash
# 1. Déployer Django
git push scalingo master

# 2. Déployer MAUI
# Installer nouvelle version (pas besoin de réinitialiser)
```

---

## 💡 SUPPORT

En cas de problème, vérifiez :
1. Les logs Scalingo : `scalingo logs`
2. Les logs MAUI : Menu → Logs
3. Les mouvements de stock dans l'admin Django

**Tout devrait fonctionner correctement après ces étapes ! 🚀**
