# 🔄 MIGRATION DES STOCKS VARIANTS → PARENT

## ⚠️ PROBLÈME IDENTIFIÉ

Actuellement, les stocks sont répartis sur les variants :
```
Article parent : Déodorant
├── Stock parent : 0 (ou valeur initiale)
└── Variants :
    ├── Rouge : 30 unités
    ├── Bleu  : 40 unités
    ├── Vert  : 30 unités
    └── Jaune : 30 unités
    TOTAL : 130 unités
```

**Avec la nouvelle logique, ces 130 unités doivent être transférées au parent !**

---

## 🎯 OBJECTIF

Transférer tous les stocks des variants vers le parent :
```
Article parent : Déodorant
├── Stock parent : 130 ✅ (somme des variants)
└── Variants : (identifiants uniquement, stock = 0)
```

---

## 📋 PROCÉDURE DE MIGRATION

### ÉTAPE 1 : Migration côté Django (SERVEUR)

#### 1.1 Simulation (recommandé d'abord)

```bash
# Tester la migration sans modifier la base
python manage.py migrer_stocks_variants --dry-run

# Pour une boutique spécifique (ex: boutique 44)
python manage.py migrer_stocks_variants --dry-run --boutique-id 44
```

**Résultat attendu :**
```
📍 Migration pour la boutique : Ma Boutique (ID: 44)
📦 15 articles avec variants trouvés

📦 Article: Déodorant (ID: 123)
   └─ Stock parent avant : 0
   └─ Variants (4) :
      ├─ Rouge: 30 unités
      ├─ Bleu: 40 unités
      ├─ Vert: 30 unités
      └─ Jaune: 30 unités
   └─ Somme stocks variants : 130
   └─ Stock parent après : 130
   🔍 Simulation - Aucune modification

📊 Résumé :
   ├─ Articles migrés : 15
   └─ Stock total transféré : 1250 unités
```

#### 1.2 Migration réelle

```bash
# Migrer TOUTES les boutiques
python manage.py migrer_stocks_variants

# Migrer UNE SEULE boutique (recommandé pour tester)
python manage.py migrer_stocks_variants --boutique-id 44
```

**Ce que fait la commande :**
1. ✅ Calcule la somme des stocks de tous les variants
2. ✅ Ajoute cette somme au stock du parent
3. ✅ Crée un mouvement de stock pour traçabilité
4. ✅ Met les stocks des variants à 0 (obsolètes)

---

### ÉTAPE 2 : Migration côté MAUI (CLIENT)

#### Option A : Réinitialisation complète (recommandé)

**Procédure :**
1. Déployer la nouvelle version MAUI
2. Dans l'app : Menu → Réinitialiser
3. Re-synchroniser tous les articles

**Avantages :**
- ✅ Simple
- ✅ Garantit la cohérence
- ✅ Télécharge les stocks déjà migrés depuis Django

**Inconvénient :**
- ⏱️ Re-téléchargement complet

#### Option B : Migration automatique au démarrage

**Code à ajouter dans MAUI** (dans `App.xaml.cs` ou service de démarrage) :

```csharp
/// <summary>
/// Migre les stocks des variants vers les parents (une seule fois)
/// </summary>
private async Task MigrerStocksVariantsVersParent()
{
    var preferences = Preferences.Default;
    var migrationEffectuee = preferences.Get("StockVariantsMigre", false);
    
    if (migrationEffectuee)
    {
        System.Diagnostics.Debug.WriteLine("✅ Migration stocks variants déjà effectuée");
        return;
    }
    
    System.Diagnostics.Debug.WriteLine("🔄 Début migration stocks variants vers parents...");
    
    try
    {
        var databaseService = ServiceHelper.GetService<DatabaseService>();
        
        // Récupérer tous les articles
        var articles = await databaseService.GetArticlesAsync();
        
        int articlesModifies = 0;
        int stockTotal = 0;
        
        foreach (var article in articles)
        {
            // Récupérer les variants de cet article
            var variants = await databaseService.GetVariantesByParentIdAsync(article.Id);
            
            if (variants == null || !variants.Any())
                continue;
            
            // Calculer la somme des stocks des variants
            int sommeStocksVariants = variants.Sum(v => v.QuantiteStock);
            
            if (sommeStocksVariants == 0)
                continue;
            
            // Transférer au parent
            int stockAvant = article.QuantiteStock;
            article.QuantiteStock += sommeStocksVariants;
            await databaseService.SaveArticleAsync(article);
            
            System.Diagnostics.Debug.WriteLine(
                $"📦 {article.Nom}: {stockAvant} + {sommeStocksVariants} = {article.QuantiteStock}");
            
            // Mettre les stocks des variants à 0
            foreach (var variant in variants)
            {
                variant.QuantiteStock = 0;
                await databaseService.SaveVarianteAsync(variant);
            }
            
            articlesModifies++;
            stockTotal += sommeStocksVariants;
        }
        
        // Marquer la migration comme effectuée
        preferences.Set("StockVariantsMigre", true);
        
        System.Diagnostics.Debug.WriteLine(
            $"✅ Migration terminée: {articlesModifies} articles, {stockTotal} unités transférées");
    }
    catch (Exception ex)
    {
        System.Diagnostics.Debug.WriteLine($"❌ Erreur migration: {ex.Message}");
    }
}
```

**Appeler cette méthode au démarrage de l'app :**

```csharp
protected override async void OnStart()
{
    base.OnStart();
    
    // Migration des stocks (une seule fois)
    await MigrerStocksVariantsVersParent();
}
```

---

## 📊 ORDRE D'EXÉCUTION RECOMMANDÉ

### Scénario 1 : Migration progressive (recommandé)

1. **Django (serveur) :**
   ```bash
   # Tester d'abord
   python manage.py migrer_stocks_variants --dry-run --boutique-id 44
   
   # Migrer une boutique pilote
   python manage.py migrer_stocks_variants --boutique-id 44
   ```

2. **MAUI (clients de la boutique 44) :**
   - Déployer la nouvelle version
   - Réinitialiser les terminaux
   - Re-synchroniser

3. **Validation (boutique 44) :**
   - Vérifier l'affichage des stocks
   - Tester des ventes avec variants
   - Valider pendant 1-2 jours

4. **Déploiement complet :**
   ```bash
   # Migrer toutes les boutiques
   python manage.py migrer_stocks_variants
   ```
   - Déployer MAUI sur tous les terminaux

### Scénario 2 : Migration complète d'un coup

1. **Django (toutes les boutiques) :**
   ```bash
   python manage.py migrer_stocks_variants --dry-run  # Simulation
   python manage.py migrer_stocks_variants            # Migration réelle
   ```

2. **MAUI (tous les terminaux) :**
   - Déployer la nouvelle version
   - Réinitialiser tous les terminaux
   - Re-synchroniser

---

## ⚠️ POINTS D'ATTENTION

### 1. Sauvegarde avant migration

```bash
# Sauvegarder la base de données avant migration
python manage.py dumpdata inventory.Article inventory.VarianteArticle > backup_avant_migration.json
```

### 2. Vérification après migration

**Django :**
```python
# Dans le shell Django
from inventory.models import Article, VarianteArticle
from django.db.models import Sum

# Vérifier un article
article = Article.objects.get(id=123)
print(f"Stock parent: {article.quantite_stock}")

variants = article.variantes.all()
print(f"Nombre de variants: {variants.count()}")
print(f"Somme stocks variants: {variants.aggregate(Sum('quantite_stock'))['quantite_stock__sum']}")
```

**Résultat attendu :**
```
Stock parent: 130
Nombre de variants: 4
Somme stocks variants: 0  ✅ (variants à 0 après migration)
```

### 3. Rollback si problème

**Django :**
```bash
# Restaurer la sauvegarde
python manage.py loaddata backup_avant_migration.json
```

**MAUI :**
- Réinstaller l'ancienne version
- Réinitialiser les terminaux

---

## 🧪 TESTS DE VALIDATION

### Test 1 : Vérification du stock total

**Avant migration :**
```sql
-- Stock total = stock parent + somme stocks variants
SELECT 
    a.id,
    a.nom,
    a.quantite_stock as stock_parent,
    COALESCE(SUM(v.quantite_stock), 0) as stock_variants,
    a.quantite_stock + COALESCE(SUM(v.quantite_stock), 0) as stock_total
FROM inventory_article a
LEFT JOIN inventory_variantearticle v ON v.article_parent_id = a.id
WHERE a.id = 123
GROUP BY a.id;
```

**Après migration :**
```sql
-- Stock total = stock parent uniquement
SELECT 
    a.id,
    a.nom,
    a.quantite_stock as stock_parent,
    COALESCE(SUM(v.quantite_stock), 0) as stock_variants
FROM inventory_article a
LEFT JOIN inventory_variantearticle v ON v.article_parent_id = a.id
WHERE a.id = 123
GROUP BY a.id;
```

**Résultat attendu :**
- Stock parent : 130 ✅
- Stock variants : 0 ✅

### Test 2 : Vente avec variant

1. Vendre 5 unités du variant Rouge
2. Vérifier que le stock parent passe de 130 à 125
3. Vérifier que tous les variants affichent 125

---

## 📝 CHECKLIST DE MIGRATION

### Préparation
- [ ] Sauvegarder la base de données Django
- [ ] Tester la commande en mode `--dry-run`
- [ ] Compiler la nouvelle version MAUI

### Migration Django
- [ ] Exécuter `migrer_stocks_variants` sur une boutique pilote
- [ ] Vérifier les logs de migration
- [ ] Vérifier les mouvements de stock créés
- [ ] Valider les stocks dans l'admin Django

### Migration MAUI
- [ ] Déployer la nouvelle version sur terminaux pilotes
- [ ] Réinitialiser les terminaux
- [ ] Re-synchroniser les articles
- [ ] Vérifier l'affichage des stocks

### Validation
- [ ] Tester une vente avec variant
- [ ] Vérifier que le stock parent est décrémenté
- [ ] Vérifier que tous les variants affichent le même stock
- [ ] Valider pendant 1-2 jours

### Déploiement complet
- [ ] Migrer toutes les boutiques Django
- [ ] Déployer MAUI sur tous les terminaux
- [ ] Surveiller les premiers jours

---

## 🎯 RÉSULTAT FINAL

**Avant migration :**
```
Déodorant
├── Stock parent : 0
└── Variants :
    ├── Rouge : 30
    ├── Bleu  : 40
    ├── Vert  : 30
    └── Jaune : 30
TOTAL : 130 unités (répartis)
```

**Après migration :**
```
Déodorant
├── Stock parent : 130 ✅
└── Variants :
    ├── Rouge : 0 (identifiant uniquement)
    ├── Bleu  : 0 (identifiant uniquement)
    ├── Vert  : 0 (identifiant uniquement)
    └── Jaune : 0 (identifiant uniquement)
TOTAL : 130 unités (centralisé sur parent)
```

**Vente de 5 Rouge :**
```
Déodorant
├── Stock parent : 125 ✅ (décrémenté)
└── Tous les variants affichent : 125 ✅
```

---

## 💡 RECOMMANDATION FINALE

**Ordre d'exécution :**

1. **Tester d'abord** : `--dry-run` sur boutique 44
2. **Migrer Django** : boutique 44 uniquement
3. **Déployer MAUI** : terminaux de la boutique 44
4. **Valider** : 1-2 jours de tests
5. **Déployer partout** : toutes les boutiques + tous les terminaux

**Cette approche garantit une migration sûre et progressive ! 🚀**
