# Guide de Correction - Affichage des Devises dans MAUI

## Problème Résolu

Les articles avec devise USD récupérés depuis Django s'affichaient toujours en Franc Congolais (CDF) dans l'application MAUI.

## Cause du Problème

Le modèle `Article` dans le code MAUI ne contenait pas les champs nécessaires pour gérer les devises :
- Champ `devise` manquant
- Champs `prix_vente_usd` et `prix_achat_usd` manquants
- Logique d'affichage ne tenant pas compte de la devise

## Solution Implémentée

### 1. Modifications Backend Django (✅ Déjà fait)

**Fichier : `inventory/views_commercant.py`**
- Ajout du champ `devise` lors de la création d'articles via AJAX
- Ajout du champ `prix_achat_usd` lors de la création d'articles

**Fichier : `inventory/forms.py`**
- Ajout des champs `devise`, `prix_vente_usd`, `prix_achat`, `prix_achat_usd` dans `ArticleForm`

### 2. Modifications Client MAUI (À implémenter)

**Fichier : Votre modèle `Article.cs`**

Remplacez votre classe `Article` actuelle par celle-ci :

```csharp
public class Article
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("code")]
    public string Code { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
    
    [JsonPropertyName("description")]
    public string Description { get; set; }
    
    // ⭐ NOUVEAU: Champ devise
    [JsonPropertyName("devise")]
    public string Devise { get; set; }
    
    [JsonPropertyName("prix_vente")]
    public string PrixVente { get; set; }
    
    // ⭐ NOUVEAU: Prix en USD
    [JsonPropertyName("prix_vente_usd")]
    public string PrixVenteUsd { get; set; }
    
    [JsonPropertyName("prix_achat")]
    public string PrixAchat { get; set; }
    
    // ⭐ NOUVEAU: Prix d'achat en USD
    [JsonPropertyName("prix_achat_usd")]
    public string PrixAchatUsd { get; set; }
    
    [JsonPropertyName("quantite_stock")]
    public int QuantiteStock { get; set; }
    
    [JsonPropertyName("categorie_nom")]
    public string CategorieNom { get; set; }
    
    [JsonPropertyName("image_url")]
    public string ImageUrl { get; set; }
    
    [JsonPropertyName("qr_code_url")]
    public string QrCodeUrl { get; set; }
    
    [JsonPropertyName("est_actif")]
    public bool EstActif { get; set; }
    
    // Propriétés calculées pour conversion
    [JsonIgnore]
    public decimal PrixVenteDecimal => decimal.TryParse(PrixVente, out var prix) ? prix : 0;
    
    [JsonIgnore]
    public decimal PrixVenteUsdDecimal => decimal.TryParse(PrixVenteUsd, out var prix) ? prix : 0;
    
    // ⭐ PROPRIÉTÉ PRINCIPALE: Affiche le prix avec la bonne devise
    [JsonIgnore]
    public string PrixAffichage
    {
        get
        {
            if (Devise == "USD" && PrixVenteUsdDecimal > 0)
            {
                return $"{PrixVenteUsdDecimal:N2} $";
            }
            else if (Devise == "CDF" || string.IsNullOrEmpty(Devise))
            {
                return $"{PrixVenteDecimal:N0} FC";
            }
            // Fallback: afficher USD si disponible
            else if (PrixVenteUsdDecimal > 0)
            {
                return $"{PrixVenteUsdDecimal:N2} $";
            }
            return $"{PrixVenteDecimal:N0} FC";
        }
    }
    
    // ⭐ Symbole de devise
    [JsonIgnore]
    public string SymboleDevise => Devise == "USD" ? "$" : "FC";
}
```

### 3. Mise à Jour du XAML

**Dans vos fichiers XAML (ex: ArticlesPage.xaml, VentePage.xaml, etc.)**

**AVANT :**
```xml
<Label Text="{Binding PrixVente, StringFormat='{0} CDF'}" />
```

**APRÈS :**
```xml
<Label Text="{Binding PrixAffichage}" />
```

### 4. Exemple Complet d'Affichage

```xml
<!-- Carte d'article avec devise correcte -->
<Frame Margin="10,5" Padding="15" CornerRadius="12">
    <Grid ColumnDefinitions="70,*,Auto" RowDefinitions="Auto,Auto,Auto">
        
        <!-- Image -->
        <Frame Grid.RowSpan="3" CornerRadius="8">
            <Image Source="{Binding ImageUrl}" 
                   WidthRequest="70" 
                   HeightRequest="70"/>
        </Frame>
        
        <!-- Nom -->
        <Label Grid.Column="1" 
               Text="{Binding Nom}"
               FontSize="18"
               FontAttributes="Bold"/>
        
        <!-- Code -->
        <Label Grid.Column="1" Grid.Row="1"
               Text="{Binding Code, StringFormat='Code: {0}'}"
               FontSize="13"/>
        
        <!-- Stock -->
        <Label Grid.Column="1" Grid.Row="2"
               Text="{Binding QuantiteStock, StringFormat='Stock: {0}'}"
               FontSize="12"/>
        
        <!-- ⭐ Prix avec devise correcte -->
        <Label Grid.Column="2" Grid.RowSpan="3"
               Text="{Binding PrixAffichage}"
               FontSize="17"
               FontAttributes="Bold"
               TextColor="#007AFF"
               VerticalOptions="Center"/>
        
    </Grid>
</Frame>
```

## Logique de la Propriété `PrixAffichage`

La propriété `PrixAffichage` fonctionne selon cette logique :

1. **Si `Devise == "USD"` ET `PrixVenteUsd > 0`** → Affiche `"XX.XX $"`
2. **Si `Devise == "CDF"` OU `Devise` est vide** → Affiche `"XXXXX FC"`
3. **Sinon, si `PrixVenteUsd > 0`** → Affiche `"XX.XX $"` (fallback)
4. **Sinon** → Affiche `"XXXXX FC"` (fallback par défaut)

## Formatage des Prix

- **USD** : Format avec 2 décimales → `1250.50 $`
- **CDF** : Format sans décimales → `125 000 FC`

## Vérification

### Backend Django
```bash
# Vérifier qu'un article USD existe
python manage.py shell
>>> from inventory.models import Article
>>> Article.objects.filter(devise='USD').values('nom', 'devise', 'prix_vente_usd')
```

### Client MAUI
```csharp
// Dans votre code de debug
foreach (var article in articles)
{
    Console.WriteLine($"Article: {article.Nom}");
    Console.WriteLine($"  Devise: {article.Devise}");
    Console.WriteLine($"  Prix CDF: {article.PrixVente}");
    Console.WriteLine($"  Prix USD: {article.PrixVenteUsd}");
    Console.WriteLine($"  Affichage: {article.PrixAffichage}");
}
```

## Exemple de Résultat Attendu

### Article en CDF
```
Nom: Battery iPhone
Devise: CDF
Prix Vente: 40000
Prix Affichage: "40 000 FC"
```

### Article en USD
```
Nom: Samsung S24
Devise: USD
Prix Vente USD: 850.00
Prix Affichage: "850.00 $"
```

## Points Importants

1. **Compatibilité ascendante** : Les articles existants sans devise continueront à s'afficher en CDF
2. **Null safety** : La propriété gère les cas où `PrixVenteUsd` est null ou vide
3. **Binding XAML** : Utilisez `{Binding PrixAffichage}` partout où vous affichez un prix
4. **Synchronisation** : Après mise à jour du modèle, synchronisez les articles depuis Django

## Fichiers à Modifier dans Votre Projet MAUI

1. **Models/Article.cs** - Ajouter les nouveaux champs
2. **Pages/ArticlesPage.xaml** - Utiliser `PrixAffichage`
3. **Pages/VentePage.xaml** - Utiliser `PrixAffichage`
4. **ViewModels/PanierViewModel.cs** - Utiliser `PrixAffichage` pour le calcul du total
5. Tout autre fichier affichant des prix d'articles

## Test de Validation

1. Créer un article en USD dans Django
2. Synchroniser les articles dans MAUI
3. Vérifier que l'article s'affiche avec `$` et non `FC`
4. Créer une vente avec cet article
5. Vérifier que le montant total est correct

## Support Multi-Devise dans les Ventes

Si vous voulez supporter les ventes en USD, ajoutez également :

```csharp
// Dans votre LigneVenteRequest
[JsonPropertyName("devise")]
public string Devise { get; set; }

[JsonPropertyName("prix_unitaire_usd")]
public decimal? PrixUnitaireUsd { get; set; }
```

Et lors de la création d'une vente :

```csharp
var ligne = new LigneVenteRequest
{
    ArticleId = article.Id,
    Quantite = quantite,
    Devise = article.Devise,
    PrixUnitaire = article.PrixVenteDecimal,
    PrixUnitaireUsd = article.PrixVenteUsdDecimal > 0 ? article.PrixVenteUsdDecimal : null
};
```

## Résumé des Changements

### ✅ Backend (Déjà fait)
- Champ `devise` ajouté lors de la création d'articles
- Formulaire mis à jour avec tous les champs de devise

### 📱 Client MAUI (À faire)
- Mettre à jour le modèle `Article` avec les nouveaux champs
- Utiliser `PrixAffichage` dans tous les XAML
- Tester avec des articles USD et CDF

---

**Date de création** : 22 janvier 2026  
**Statut** : Backend ✅ | Client MAUI ⏳
