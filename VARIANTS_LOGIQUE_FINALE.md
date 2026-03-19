# 🏷️ LOGIQUE VARIANTS - IMPLÉMENTATION FINALE

## 📋 LOGIQUE CHOISIE

**Stock et prix sur le PARENT uniquement - Variants = identifiants seulement**

### ✅ Principe

Les variants sont des **identifiants avec code-barres différents** pour le même produit :
- **Même produit** : Déodorant
- **Même prix** : 5000 FC
- **Même stock** : 100 unités
- **Variants différents** : Rouge (code 111), Bleu (code 222), Vert (code 333)

**Quand on scanne un variant :**
1. Le système identifie le variant par son code-barres
2. Le prix vient de l'article parent
3. Le stock est vérifié sur l'article parent
4. La vente décrémente le stock de l'article parent
5. Le mouvement de stock indique quel variant a été vendu

---

## 🔧 MODIFICATIONS APPORTÉES

### 1. Modèle `VarianteArticle` (models.py)

**Ajout d'une propriété `stock_disponible` :**

```python
@property
def stock_disponible(self):
    """
    Le stock est TOUJOURS sur le parent.
    Les variantes sont des identifiants uniquement (code-barres différents).
    """
    return self.article_parent.quantite_stock
```

**Note :** Le champ `quantite_stock` existe toujours dans la base de données mais **n'est plus utilisé**.

---

### 2. API Ventes (api_views_v2_simple.py)

#### Vérification du stock (ligne 1165-1168)

**AVANT :**
```python
if variante:
    if variante.quantite_stock < quantite:  # ❌ Stock du variant
        raise Exception(f'Stock insuffisant')
else:
    if article.quantite_stock < quantite:
        raise Exception(f'Stock insuffisant')
```

**APRÈS :**
```python
# Vérifier le stock disponible (TOUJOURS sur le parent, même si variant)
nom_article = variante.nom_complet if variante else article.nom
if article.quantite_stock < quantite:  # ✅ Toujours le stock du parent
    raise Exception(f'Stock insuffisant pour {nom_article}')
```

#### Décrémentation du stock (ligne 1225-1250)

**AVANT :**
```python
if variante:
    variante.quantite_stock -= quantite  # ❌ Décrémente le variant
    variante.save()
else:
    article.quantite_stock -= quantite
    article.save()
```

**APRÈS :**
```python
# Stock TOUJOURS sur le parent (variants = identifiants uniquement)
stock_avant = article.quantite_stock
article.quantite_stock -= quantite  # ✅ Toujours le parent
article.save(update_fields=['quantite_stock'])

# Log avec info variant si applicable
if variante:
    logger.info(f"🏷️ Vente variant {variante.nom_complet}: Stock parent {stock_avant} → {article.quantite_stock}")
    commentaire_stock = f"Vente #{vente.numero_facture} - Variante: {variante.nom_variante}"
else:
    commentaire_stock = f"Vente #{vente.numero_facture}"
```

---

### 3. API Variants (api_views_v2_simple.py ligne 862)

**AVANT :**
```python
'quantite_stock': variante.quantite_stock,  # ❌ Stock du variant
```

**APRÈS :**
```python
'quantite_stock': variante.article_parent.quantite_stock,  # ✅ Stock du parent
```

**Résultat :** L'API retourne le stock du parent pour tous les variants.

---

## 📊 EXEMPLE CONCRET

### Situation

**Article parent :**
- ID : 42
- Nom : Déodorant
- Prix : 5000 FC
- Stock : 100 unités

**Variants :**
- Variant 1 : Rouge (code-barres : 111)
- Variant 2 : Bleu (code-barres : 222)
- Variant 3 : Vert (code-barres : 333)

### Scénario de vente

**Client scanne le code-barres 222 (Bleu) :**

1. **Système identifie** : Variant "Bleu" de l'article "Déodorant"
2. **Prix** : 5000 FC (du parent)
3. **Stock disponible** : 100 (du parent)
4. **Vente de 2 unités** :
   - Stock parent : 100 → 98
   - Mouvement : "Vente #VENTE-001 - Variante: Bleu"

**Client scanne le code-barres 333 (Vert) :**

1. **Système identifie** : Variant "Vert" de l'article "Déodorant"
2. **Prix** : 5000 FC (du parent)
3. **Stock disponible** : 98 (du parent, déjà décrémenté)
4. **Vente de 3 unités** :
   - Stock parent : 98 → 95
   - Mouvement : "Vente #VENTE-002 - Variante: Vert"

**Résultat final :**
- Stock parent : 95 unités
- 2 Bleu vendus
- 3 Vert vendus
- Total vendu : 5 unités (du même stock parent)

---

## 📱 INTÉGRATION CLIENT MAUI

### Synchronisation des variants

```csharp
// L'API retourne le stock du parent pour chaque variant
var response = await httpClient.GetAsync(
    $"{baseUrl}/api/v2/simple/variantes/?boutique_id={boutiqueId}"
);

// Exemple de réponse
{
  "variantes": [
    {
      "id": 1,
      "article_parent_id": 42,
      "code_barre": "111",
      "nom_variante": "Rouge",
      "quantite_stock": 100,  // ✅ Stock du parent
      "prix_vente": "5000.00"
    },
    {
      "id": 2,
      "article_parent_id": 42,
      "code_barre": "222",
      "nom_variante": "Bleu",
      "quantite_stock": 100,  // ✅ Même stock (parent)
      "prix_vente": "5000.00"
    }
  ]
}
```

### Affichage dans l'UI MAUI

**Option 1 : Afficher le stock global**
```
Déodorant - Rouge
Stock : 100 unités (global)
Prix : 5000 FC
```

**Option 2 : Regrouper les variants**
```
Déodorant
Stock : 100 unités
Variants : Rouge, Bleu, Vert
Prix : 5000 FC
```

### Vente avec variant

```csharp
// Quand le client scanne un code-barres
var variant = await db.Variants
    .Include(v => v.ArticleParent)
    .FirstOrDefaultAsync(v => v.CodeBarre == codeBarre);

if (variant != null)
{
    // Afficher le nom complet
    var nomComplet = $"{variant.ArticleParent.Nom} - {variant.NomVariante}";
    
    // Prix du parent
    var prix = variant.ArticleParent.PrixVente;
    
    // Stock du parent
    var stock = variant.ArticleParent.QuantiteStock;
    
    // Envoyer la vente avec variante_id
    var vente = new {
        lignes = new[] {
            new {
                article_id = variant.ArticleParentId,
                variante_id = variant.Id,  // ✅ Inclure le variant
                quantite = 2,
                prix_unitaire = prix
            }
        }
    };
}
```

---

## 🔍 AVANTAGES DE CETTE LOGIQUE

### ✅ Simplicité de gestion

- **Un seul stock à gérer** (le parent)
- Pas de risque de désynchronisation entre variants
- Pas besoin de répartir le stock entre variants

### ✅ Flexibilité

- Ajouter/supprimer des variants sans toucher au stock
- Changer les codes-barres facilement
- Les variants sont juste des "alias" du même produit

### ✅ Traçabilité

- On sait quel variant a été vendu (mouvement de stock)
- On peut faire des statistiques par variant
- Le stock global reste cohérent

### ✅ Exemple d'usage

**Cas d'usage typique :**
- Produit : Savon
- Variants : Parfum Rose, Parfum Citron, Parfum Lavande
- Même prix, même stock
- Le client choisit son parfum préféré
- Le commerçant gère un seul stock global

---

## ⚠️ CHAMP `quantite_stock` DU VARIANT

### Status actuel

Le champ `VarianteArticle.quantite_stock` existe toujours dans la base de données mais **n'est plus utilisé**.

### Options pour le futur

**Option 1 : Laisser tel quel (recommandé)**
- Pas de migration nécessaire
- Compatibilité avec données existantes
- Le champ est ignoré par le code

**Option 2 : Supprimer le champ (optionnel)**
```python
# Migration Django à créer
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField(
            model_name='variantearticle',
            name='quantite_stock',
        ),
    ]
```

**Recommandation :** Laisser le champ pour l'instant. Si vous voulez le supprimer plus tard, créez une migration Django.

---

## 📊 RÉSUMÉ TECHNIQUE

| Aspect | Implémentation |
|--------|----------------|
| **Stock** | Sur le parent uniquement |
| **Prix** | Sur le parent uniquement |
| **Variant** | Identifiant avec code-barres unique |
| **Vérification stock** | Toujours sur `article.quantite_stock` |
| **Décrémentation** | Toujours sur `article.quantite_stock` |
| **API variants** | Retourne `article_parent.quantite_stock` |
| **Mouvement stock** | Indique le variant vendu en commentaire |
| **Traçabilité** | Via `LigneVente.variante` et mouvement stock |

---

## ✅ FICHIERS MODIFIÉS

1. **`inventory/models.py`** (ligne 305-311)
   - Ajout propriété `stock_disponible`

2. **`inventory/api_views_v2_simple.py`** (lignes 1165-1168, 1225-1250, 862)
   - Vérification stock sur parent
   - Décrémentation stock sur parent
   - API retourne stock parent

---

## 🚀 DÉPLOIEMENT

### Aucune migration nécessaire

Les modifications sont **uniquement dans le code**, pas dans la structure de la base de données.

### Déploiement sur Scalingo

```bash
git add .
git commit -m "Fix: Variants use parent stock only"
git push scalingo master
```

**Effet immédiat :**
- Les nouvelles ventes décrémentent le stock parent
- L'API retourne le stock parent
- Aucune donnée perdue

---

## 💡 CONCLUSION

**Logique finale implémentée :**
- ✅ Stock sur le parent uniquement
- ✅ Prix sur le parent uniquement
- ✅ Variants = identifiants (code-barres différents)
- ✅ Scanner un variant → décrémenter le stock parent
- ✅ Traçabilité complète via mouvements de stock

**Prêt pour la production ! 🎉**
