# 🔧 CORRECTIONS NÉCESSAIRES - CLIENT MAUI VARIANTS

## ❌ PROBLÈME IDENTIFIÉ

Le client MAUI stocke et utilise le **stock du variant** au lieu du **stock du parent**.

**Fichier :** `Models/VarianteArticle.cs` (lignes 39-53, 88)

```csharp
// ❌ INCORRECT : Stock propre au variant
public int QuantiteStock { get; set; }

// ❌ INCORRECT : Vérifie le stock du variant
public bool EstEnStock => QuantiteStock > 0 && EstActif;
```

---

## ✅ SOLUTION : Utiliser le stock du parent

### Modification 1 : `VarianteArticle.cs`

**Remplacer :**
```csharp
/// <summary>Stock spécifique à cette variante</summary>
private int _quantiteStock;
public int QuantiteStock
{
    get => _quantiteStock;
    set
    {
        if (_quantiteStock != value)
        {
            _quantiteStock = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(EstEnStock));
        }
    }
}

/// <summary>Stock disponible</summary>
[Ignore]
public bool EstEnStock => QuantiteStock > 0 && EstActif;
```

**Par :**
```csharp
/// <summary>
/// Stock du PARENT (les variants n'ont pas de stock propre).
/// Ce champ est conservé pour compatibilité avec l'ancienne structure SQLite,
/// mais il n'est plus utilisé. Le stock vient toujours de ArticleParent.QuantiteStock.
/// </summary>
[Obsolete("Le stock est maintenant sur le parent uniquement")]
private int _quantiteStock;
public int QuantiteStock
{
    get => _quantiteStock;
    set
    {
        if (_quantiteStock != value)
        {
            _quantiteStock = value;
            OnPropertyChanged();
        }
    }
}

/// <summary>Stock disponible du PARENT</summary>
[Ignore]
public int StockDisponible => ArticleParent?.QuantiteStock ?? 0;

/// <summary>Vérifie si le parent a du stock</summary>
[Ignore]
public bool EstEnStock => StockDisponible > 0 && EstActif;
```

---

### Modification 2 : Synchronisation des variants

**Fichier :** `API/ArticleApiService.cs` (ou service de sync des variants)

Lors de la synchronisation des variants depuis Django, **ne plus mettre à jour `VarianteArticle.QuantiteStock`**.

**Avant :**
```csharp
variante.QuantiteStock = varianteData.quantite_stock;  // ❌ Stock du variant
```

**Après :**
```csharp
// Le stock vient du parent, pas besoin de le stocker sur le variant
// variante.QuantiteStock est obsolète et n'est plus utilisé
```

---

### Modification 3 : Affichage du stock dans l'UI

**Fichier :** ViewModels ou Views qui affichent les variants

**Avant :**
```csharp
// ❌ Affiche le stock du variant
stockLabel.Text = $"Stock: {variante.QuantiteStock}";
```

**Après :**
```csharp
// ✅ Affiche le stock du parent
stockLabel.Text = $"Stock: {variante.StockDisponible}";
// ou
stockLabel.Text = $"Stock: {variante.ArticleParent.QuantiteStock}";
```

---

### Modification 4 : Vérification du stock avant vente

**Fichier :** `ViewModels/VenteViewModel.cs` (ou logique d'ajout au panier)

**Avant :**
```csharp
if (variante.QuantiteStock < quantite)  // ❌ Vérifie le stock du variant
{
    await DisplayAlert("Stock insuffisant", $"Stock disponible: {variante.QuantiteStock}", "OK");
    return;
}
```

**Après :**
```csharp
if (variante.StockDisponible < quantite)  // ✅ Vérifie le stock du parent
{
    await DisplayAlert("Stock insuffisant", $"Stock disponible: {variante.StockDisponible}", "OK");
    return;
}
```

---

## 📊 EXEMPLE CONCRET

### Situation

**Article parent : Déodorant**
- ID Backend : 42
- Stock : 100 unités

**Variants :**
- Rouge (code 111)
- Bleu (code 222)
- Vert (code 333)

### Comportement ACTUEL (incorrect)

```csharp
// Sync depuis Django
varianteRouge.QuantiteStock = 30;  // ❌ Stock propre
varianteBleu.QuantiteStock = 40;   // ❌ Stock propre
varianteVert.QuantiteStock = 30;   // ❌ Stock propre

// Affichage
varianteRouge.EstEnStock => true (30 > 0)  // ❌ Utilise son propre stock
varianteBleu.EstEnStock => true (40 > 0)   // ❌ Utilise son propre stock

// Vente de 5 Rouge
if (varianteRouge.QuantiteStock >= 5)  // ❌ Vérifie le stock du variant
    // Envoie à Django avec variante_id = Rouge
    // Django décrémente le stock PARENT : 100 → 95
```

**Problème :** MAUI pense qu'il reste 30 Rouge, mais Django a décrémenté le parent (95 total).

### Comportement CORRIGÉ (correct)

```csharp
// Sync depuis Django
articleParent.QuantiteStock = 100;  // ✅ Stock sur le parent
varianteRouge.ArticleParent = articleParent;
varianteBleu.ArticleParent = articleParent;
varianteVert.ArticleParent = articleParent;

// Affichage
varianteRouge.StockDisponible => 100  // ✅ Stock du parent
varianteBleu.StockDisponible => 100   // ✅ Stock du parent
varianteVert.StockDisponible => 100   // ✅ Stock du parent

// Vente de 5 Rouge
if (varianteRouge.StockDisponible >= 5)  // ✅ Vérifie le stock du parent (100)
    // Envoie à Django avec variante_id = Rouge
    // Django décrémente le stock PARENT : 100 → 95

// Après sync
articleParent.QuantiteStock = 95;  // ✅ Mis à jour
varianteRouge.StockDisponible => 95  // ✅ Reflète le nouveau stock parent
varianteBleu.StockDisponible => 95   // ✅ Tous les variants voient le même stock
varianteVert.StockDisponible => 95   // ✅ Cohérent
```

---

## 🔍 FICHIERS À MODIFIER

1. **`Models/VarianteArticle.cs`**
   - Ajouter propriété `StockDisponible` qui retourne `ArticleParent.QuantiteStock`
   - Modifier `EstEnStock` pour utiliser `StockDisponible`
   - Marquer `QuantiteStock` comme obsolète

2. **`API/ArticleApiService.cs`** (ou service de sync)
   - Ne plus mettre à jour `VarianteArticle.QuantiteStock` lors de la sync
   - Mettre à jour uniquement `Article.QuantiteStock` (parent)

3. **ViewModels/Views** (tous les fichiers qui utilisent les variants)
   - Remplacer `variante.QuantiteStock` par `variante.StockDisponible`
   - Remplacer `variante.QuantiteStock` par `variante.ArticleParent.QuantiteStock`

4. **Tests**
   - Tester l'affichage du stock des variants
   - Tester la vente d'un variant
   - Vérifier que le stock parent est décrémenté
   - Vérifier que tous les variants du même parent voient le même stock

---

## ⚠️ MIGRATION DE DONNÉES

### Option 1 : Migration automatique (recommandé)

Au démarrage de l'application, après la sync :

```csharp
// Dans le service de synchronisation
public async Task MigrerStockVariantsVersParent()
{
    var variants = await _database.Table<VarianteArticle>().ToListAsync();
    
    foreach (var variant in variants)
    {
        // Charger le parent
        var parent = await _database.Table<Article>()
            .FirstOrDefaultAsync(a => a.Id == variant.ArticleParentId);
        
        if (parent != null)
        {
            // Le stock du variant est ignoré, on utilise celui du parent
            // Pas besoin de migration, juste s'assurer que ArticleParent est chargé
            variant.ArticleParent = parent;
        }
    }
    
    System.Diagnostics.Debug.WriteLine($"✅ Migration variants terminée : {variants.Count} variants");
}
```

### Option 2 : Laisser tel quel

Le champ `QuantiteStock` reste dans la base SQLite mais n'est plus utilisé. Pas de migration nécessaire.

---

## ✅ AVANTAGES DE LA CORRECTION

1. **Cohérence** : MAUI et Django utilisent la même logique
2. **Simplicité** : Un seul stock à gérer (le parent)
3. **Pas de désynchronisation** : Le stock est toujours cohérent
4. **Flexibilité** : Ajouter/supprimer des variants sans toucher au stock

---

## 📝 CHECKLIST DE DÉPLOIEMENT

- [ ] Modifier `Models/VarianteArticle.cs`
- [ ] Ajouter propriété `StockDisponible`
- [ ] Modifier `EstEnStock` pour utiliser `StockDisponible`
- [ ] Chercher tous les usages de `variante.QuantiteStock` dans le code
- [ ] Remplacer par `variante.StockDisponible` ou `variante.ArticleParent.QuantiteStock`
- [ ] Tester l'affichage des variants
- [ ] Tester la vente d'un variant
- [ ] Vérifier la synchronisation après vente
- [ ] Déployer sur les terminaux de test
- [ ] Valider en production

---

## 🎯 CONCLUSION

**Le client MAUI envoie correctement le `variante_id` à Django**, mais il utilise encore le **stock local du variant** au lieu du **stock du parent**.

**Modifications nécessaires :**
- ✅ Ajouter `StockDisponible` qui retourne le stock du parent
- ✅ Modifier `EstEnStock` pour utiliser `StockDisponible`
- ✅ Remplacer tous les usages de `variante.QuantiteStock` par `variante.StockDisponible`

**Après ces corrections, la logique sera 100% cohérente entre MAUI et Django ! 🚀**
