# Guide Complet - Intégration des Ventes en USD

## Vue d'Ensemble

Ce guide explique comment le système gère les ventes en dollars américains (USD) avec une séparation complète des recettes quotidiennes par devise (CDF vs USD).

## Architecture de la Solution

### 1. Modèle de Données Django

#### Modèle `Vente`
```python
class Vente(models.Model):
    numero_facture = models.CharField(max_length=100, unique=True)
    date_vente = models.DateTimeField(default=timezone.now)
    
    # ⭐ Montants séparés par devise
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    montant_total_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # ⭐ Devise de la vente
    devise = models.CharField(
        max_length=3, 
        choices=[('CDF', 'Franc Congolais'), ('USD', 'Dollar US')], 
        default='CDF'
    )
    
    paye = models.BooleanField(default=False)
    mode_paiement = models.CharField(max_length=50, choices=[...])
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE)
    client_maui = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True)
```

#### Modèle `LigneVente`
```python
class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, related_name='lignes', on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    
    # ⭐ Prix par devise
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # ⭐ Devise de la ligne
    devise = models.CharField(
        max_length=3, 
        choices=[('CDF', 'Franc Congolais'), ('USD', 'Dollar US')], 
        default='CDF'
    )
```

### 2. API Django - Endpoint de Création de Vente

**URL:** `POST /api/v2/simple/ventes/`

**Headers:**
```
X-Device-Serial: <numero_serie_terminal>
Content-Type: application/json
```

**Body - Vente en CDF:**
```json
{
  "devise": "CDF",
  "mode_paiement": "CASH",
  "lignes": [
    {
      "article_id": 1,
      "quantite": 2,
      "prix_unitaire": 50000,
      "devise": "CDF"
    }
  ]
}
```

**Body - Vente en USD:**
```json
{
  "devise": "USD",
  "mode_paiement": "CASH",
  "lignes": [
    {
      "article_id": 2,
      "quantite": 1,
      "prix_unitaire": 0,
      "prix_unitaire_usd": 850.00,
      "devise": "USD"
    }
  ]
}
```

**Réponse Succès:**
```json
{
  "success": true,
  "vente": {
    "id": 123,
    "numero_facture": "VENTE-2-20260122040530",
    "devise": "USD",
    "montant_total": "0",
    "montant_total_usd": "850.00",
    "mode_paiement": "CASH",
    "date_vente": "2026-01-22T04:05:30+01:00",
    "lignes": [
      {
        "article_nom": "Samsung S24",
        "quantite": 1,
        "prix_unitaire": "0",
        "prix_unitaire_usd": "850.00",
        "devise": "USD",
        "sous_total": "0"
      }
    ]
  },
  "boutique_id": 2,
  "terminal_id": 1
}
```

### 3. Logique de Calcul des Montants

#### Dans l'API (`api_views_v2_simple.py`)

```python
# Déterminer la devise de la vente
devise_vente = vente_data.get('devise', 'CDF')

# Créer la vente
vente = Vente.objects.create(
    numero_facture=numero_facture,
    date_vente=date_vente,
    montant_total=0,
    montant_total_usd=0 if devise_vente == 'USD' else None,
    devise=devise_vente,
    mode_paiement=vente_data.get('mode_paiement', 'CASH'),
    boutique=boutique,
    client_maui=terminal
)

montant_total = 0
montant_total_usd = 0

# Traiter chaque ligne
for ligne_data in vente_data.get('lignes', []):
    prix_unitaire = ligne_data.get('prix_unitaire', article.prix_vente)
    prix_unitaire_usd = ligne_data.get('prix_unitaire_usd') or article.prix_vente_usd
    devise_ligne = ligne_data.get('devise', devise_vente)
    
    LigneVente.objects.create(
        vente=vente,
        article=article,
        quantite=quantite,
        prix_unitaire=prix_unitaire,
        prix_unitaire_usd=prix_unitaire_usd,
        devise=devise_ligne
    )
    
    # Accumuler les montants
    montant_total += prix_unitaire * quantite
    if prix_unitaire_usd:
        montant_total_usd += prix_unitaire_usd * quantite

# Sauvegarder les montants
vente.montant_total = montant_total
if devise_vente == 'USD' and montant_total_usd:
    vente.montant_total_usd = montant_total_usd
vente.save()
```

### 4. Dashboard - Séparation des Recettes

#### Calcul dans `views_commercant.py`

```python
# Recette du jour - Séparation CDF et USD
ventes_jour = Vente.objects.filter(
    client_maui__boutique__in=boutiques,
    date_vente__date=aujourd_hui,
    paye=True,
    est_annulee=False
)

# Recette CDF du jour
ventes_jour_cdf = ventes_jour.filter(devise='CDF')
ca_jour_cdf = ventes_jour_cdf.aggregate(total=Sum('montant_total'))['total'] or 0

# Recette USD du jour
ventes_jour_usd = ventes_jour.filter(devise='USD')
ca_jour_usd = ventes_jour_usd.aggregate(total=Sum('montant_total_usd'))['total'] or 0

# Nombre de ventes par devise
nb_ventes_jour_cdf = ventes_jour_cdf.count()
nb_ventes_jour_usd = ventes_jour_usd.count()
```

#### Affichage dans le Template

```html
<div class="col-4 mb-2">
    <div class="small-stat-number small-stat-number-success sensitive-amount">
        {{ recette_jour|floatformat:0|intcomma }} CDF
    </div>
    {% if recette_jour_usd %}
    <div class="small-stat-number sensitive-amount" style="font-size:0.8rem;">
        $ {{ recette_jour_usd|floatformat:2 }}
    </div>
    {% endif %}
    <div class="small-stat-label">Recette jour</div>
</div>
```

## Intégration Client MAUI

### 1. Modèles C# MAUI

#### Modèle Article (Mis à Jour)
```csharp
public class Article
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
    
    // ⭐ Devise de l'article
    [JsonPropertyName("devise")]
    public string Devise { get; set; }
    
    // ⭐ Prix dans les deux devises
    [JsonPropertyName("prix_vente")]
    public string PrixVente { get; set; }
    
    [JsonPropertyName("prix_vente_usd")]
    public string PrixVenteUsd { get; set; }
    
    // Propriété calculée pour affichage
    [JsonIgnore]
    public string PrixAffichage
    {
        get
        {
            if (Devise == "USD" && PrixVenteUsdDecimal > 0)
                return $"{PrixVenteUsdDecimal:N2} $";
            else
                return $"{PrixVenteDecimal:N0} FC";
        }
    }
}
```

#### Modèle LigneVenteRequest (Mis à Jour)
```csharp
public class LigneVenteRequest
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
    
    // ⭐ Support USD
    [JsonPropertyName("prix_unitaire_usd")]
    public decimal? PrixUnitaireUsd { get; set; }
    
    [JsonPropertyName("devise")]
    public string Devise { get; set; } = "CDF";
}
```

#### Modèle VenteRequest
```csharp
public class VenteRequest
{
    [JsonPropertyName("devise")]
    public string Devise { get; set; } = "CDF";
    
    [JsonPropertyName("mode_paiement")]
    public string ModePaiement { get; set; } = "CASH";
    
    [JsonPropertyName("lignes")]
    public List<LigneVenteRequest> Lignes { get; set; } = new();
}
```

### 2. Logique de Création de Vente en MAUI

```csharp
public async Task<VenteResponse> CreerVenteAsync(List<Article> articlesVendus)
{
    var lignes = new List<LigneVenteRequest>();
    string deviseVente = "CDF"; // Par défaut
    
    foreach (var article in articlesVendus)
    {
        var ligne = new LigneVenteRequest
        {
            ArticleId = article.Id,
            Quantite = article.QuantiteVendue,
            Devise = article.Devise
        };
        
        // ⭐ Définir les prix selon la devise de l'article
        if (article.Devise == "USD")
        {
            ligne.PrixUnitaire = 0; // Ou le prix CDF si disponible
            ligne.PrixUnitaireUsd = article.PrixVenteUsdDecimal;
            deviseVente = "USD"; // La vente devient USD si au moins un article USD
        }
        else
        {
            ligne.PrixUnitaire = article.PrixVenteDecimal;
            ligne.PrixUnitaireUsd = null;
        }
        
        lignes.Add(ligne);
    }
    
    var venteRequest = new VenteRequest
    {
        Devise = deviseVente,
        ModePaiement = "CASH",
        Lignes = lignes
    };
    
    var json = JsonSerializer.Serialize(venteRequest);
    var content = new StringContent(json, Encoding.UTF8, "application/json");
    
    var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
    
    if (response.IsSuccessStatusCode)
    {
        var result = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<VenteResponse>(result);
    }
    
    return new VenteResponse { Success = false };
}
```

### 3. Affichage du Panier avec Devise

```csharp
public class PanierViewModel : BaseViewModel
{
    private ObservableCollection<Article> _articles;
    
    // ⭐ Calculer le total selon la devise
    public string TotalPanier
    {
        get
        {
            // Vérifier si on a des articles USD
            bool hasUsd = _articles.Any(a => a.Devise == "USD");
            
            if (hasUsd)
            {
                // Calculer en USD
                decimal totalUsd = _articles
                    .Where(a => a.Devise == "USD")
                    .Sum(a => a.PrixVenteUsdDecimal * a.QuantiteVendue);
                return $"{totalUsd:N2} $";
            }
            else
            {
                // Calculer en CDF
                decimal totalCdf = _articles
                    .Sum(a => a.PrixVenteDecimal * a.QuantiteVendue);
                return $"{totalCdf:N0} FC";
            }
        }
    }
}
```

## Bonnes Pratiques

### 1. Validation des Données

✅ **Toujours vérifier la devise avant de créer une vente**
```csharp
if (article.Devise == "USD" && article.PrixVenteUsdDecimal <= 0)
{
    await DisplayAlert("Erreur", "Prix USD invalide pour cet article", "OK");
    return;
}
```

✅ **Ne pas mélanger les devises dans une même vente**
```csharp
var devises = articlesVendus.Select(a => a.Devise).Distinct().ToList();
if (devises.Count > 1)
{
    await DisplayAlert("Attention", 
        "Impossible de mélanger CDF et USD dans une même vente", "OK");
    return;
}
```

### 2. Affichage des Montants

✅ **Format CDF:** `125 000 FC` (sans décimales, avec espaces)
✅ **Format USD:** `850.50 $` (2 décimales, avec point)

```csharp
// CDF
string montantCdf = $"{montant:N0} FC";

// USD
string montantUsd = $"{montant:N2} $";
```

### 3. Gestion du Taux de Change

Le taux de change est stocké dans le modèle `Commercant`:
```python
class Commercant(models.Model):
    taux_dollar = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=2500,
        help_text="Taux de change 1 USD = X CDF"
    )
```

**Envoi au client MAUI:**
```json
{
  "success": true,
  "taux_dollar": "2650.00",
  "articles": [...]
}
```

**Utilisation dans MAUI:**
```csharp
// Convertir USD en CDF pour affichage informatif
decimal montantCdf = montantUsd * tauxDollar;
```

## Rapports et Statistiques

### 1. Rapport Quotidien

Le dashboard affiche:
- **Recette CDF du jour:** Somme des ventes en CDF
- **Recette USD du jour:** Somme des ventes en USD
- **Nombre de ventes CDF:** Compteur des ventes en CDF
- **Nombre de ventes USD:** Compteur des ventes en USD

### 2. Rapport Mensuel

```python
# Recette mensuelle CDF
ventes_mois_cdf = Vente.objects.filter(
    boutique=boutique,
    date_vente__month=mois,
    date_vente__year=annee,
    devise='CDF',
    paye=True,
    est_annulee=False
).aggregate(total=Sum('montant_total'))['total'] or 0

# Recette mensuelle USD
ventes_mois_usd = Vente.objects.filter(
    boutique=boutique,
    date_vente__month=mois,
    date_vente__year=annee,
    devise='USD',
    paye=True,
    est_annulee=False
).aggregate(total=Sum('montant_total_usd'))['total'] or 0
```

## Tests et Validation

### 1. Test Backend Django

```python
# Test création vente USD
response = client.post('/api/v2/simple/ventes/', {
    'devise': 'USD',
    'mode_paiement': 'CASH',
    'lignes': [
        {
            'article_id': 1,
            'quantite': 1,
            'prix_unitaire': 0,
            'prix_unitaire_usd': 850.00,
            'devise': 'USD'
        }
    ]
}, headers={'X-Device-Serial': 'TEST123'})

assert response.status_code == 201
assert response.json()['vente']['devise'] == 'USD'
assert response.json()['vente']['montant_total_usd'] == '850.00'
```

### 2. Test Client MAUI

```csharp
[Test]
public async Task CreerVenteUsd_Success()
{
    // Arrange
    var article = new Article 
    { 
        Id = 1, 
        Devise = "USD", 
        PrixVenteUsd = "850.00" 
    };
    
    // Act
    var result = await _venteService.CreerVenteAsync(new List<Article> { article });
    
    // Assert
    Assert.IsTrue(result.Success);
    Assert.AreEqual("USD", result.Vente.Devise);
    Assert.IsNotNull(result.Vente.MontantTotalUsd);
}
```

## Résumé des Modifications

### ✅ Backend Django
1. Modèles `Vente` et `LigneVente` avec support USD complet
2. API `/api/v2/simple/ventes/` gère les ventes USD
3. Dashboard avec séparation CDF/USD
4. Réponses API incluent `devise`, `montant_total_usd`

### ✅ Client MAUI
1. Modèle `Article` avec champs `devise`, `prix_vente_usd`
2. Modèle `LigneVenteRequest` avec `prix_unitaire_usd`, `devise`
3. Logique de création de vente selon la devise
4. Affichage des prix avec la bonne devise

### 📋 À Implémenter dans MAUI
1. Interface de sélection de devise lors de la vente
2. Affichage du total du panier avec la bonne devise
3. Validation pour éviter le mélange de devises
4. Historique des ventes avec indication de la devise

## Support et Dépannage

### Problème: Vente USD créée mais montant_total_usd = null
**Cause:** Le champ `prix_unitaire_usd` n'est pas envoyé dans la requête  
**Solution:** Vérifier que `LigneVenteRequest.PrixUnitaireUsd` est bien renseigné

### Problème: Dashboard n'affiche pas les recettes USD
**Cause:** Les ventes USD ont `montant_total_usd = null`  
**Solution:** Recréer les ventes ou mettre à jour manuellement via Django Admin

### Problème: Article USD s'affiche en CDF dans MAUI
**Cause:** Le modèle `Article` MAUI ne récupère pas le champ `devise`  
**Solution:** Mettre à jour le modèle avec les champs `devise` et `prix_vente_usd`

---

**Date de création:** 22 janvier 2026  
**Version:** 1.0  
**Statut:** ✅ Backend Complet | 📱 Client MAUI À Mettre à Jour
