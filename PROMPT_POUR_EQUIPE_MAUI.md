# 📢 PROMPT POUR L'ÉQUIPE MAUI - ISOLATION DES VENTES

## 🎯 OBJECTIF

Adapter l'application MAUI pour qu'elle fonctionne avec le système d'isolation des ventes par boutique implémenté dans Django.

---

## ⚡ CHANGEMENT CRITIQUE

### ❌ ANCIEN SYSTÈME (Ne fonctionne plus)
```csharp
// Gérer manuellement le boutique_id
var boutiqueId = await SecureStorage.GetAsync("boutique_id");
var url = $"/api/v2/simple/articles/?boutique_id={boutiqueId}";
```

### ✅ NOUVEAU SYSTÈME (Obligatoire)
```csharp
// Le numéro de série identifie automatiquement la boutique
// Configurer une seule fois dans MauiProgram.cs
builder.Services.AddHttpClient("DjangoAPI", client =>
{
    client.BaseAddress = new Uri("http://10.59.88.224:8000");
    
    #if ANDROID
    string numeroSerie = Android.OS.Build.Serial ?? Android.OS.Build.GetSerial();
    client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
    #endif
});

// Ensuite, tous les appels API sont automatiques
var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
```

---

## 🔧 MODIFICATIONS REQUISES

### 1. Configuration Globale (MauiProgram.cs)

**Remplacer:**
```csharp
builder.Services.AddSingleton<HttpClient>();
```

**Par:**
```csharp
builder.Services.AddHttpClient("DjangoAPI", client =>
{
    client.BaseAddress = new Uri("http://10.59.88.224:8000");
    
    #if ANDROID
    string numeroSerie = GetDeviceSerialNumber();
    client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
    #endif
    
    client.Timeout = TimeSpan.FromSeconds(30);
});

// Méthode helper
private static string GetDeviceSerialNumber()
{
    #if ANDROID
    try
    {
        string serial = Android.OS.Build.Serial;
        
        if (string.IsNullOrEmpty(serial) || serial == "unknown")
        {
            if (Android.OS.Build.VERSION.SdkInt >= Android.OS.BuildVersionCodes.O)
            {
                serial = Android.OS.Build.GetSerial();
            }
        }
        
        return serial;
    }
    catch
    {
        return Preferences.Get("device_serial", Guid.NewGuid().ToString());
    }
    #else
    return "MAUI-SIMULATOR";
    #endif
}
```

### 2. Modifier les Services

**ArticleService.cs:**
```csharp
public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;
    
    // Injecter IHttpClientFactory au lieu de HttpClient
    public ArticleService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }
    
    public async Task<List<Article>> GetArticlesAsync()
    {
        // SUPPRIMER tout code gérant boutique_id
        // Le header X-Device-Serial est automatiquement envoyé
        var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
        
        if (response.IsSuccessStatusCode)
        {
            var content = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<ArticlesResponse>(content);
            return result.Articles ?? new List<Article>();
        }
        
        return new List<Article>();
    }
}
```

**VenteService.cs:**
```csharp
public class VenteService : IVenteService
{
    private readonly HttpClient _httpClient;
    
    public VenteService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }
    
    public async Task<VenteResponse> CreerVenteAsync(List<LigneVenteRequest> lignes)
    {
        // Format MINIMAL - Django gère tout
        var vente = new { lignes = lignes };
        
        var json = JsonSerializer.Serialize(vente);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        // SUPPRIMER tout code gérant boutique_id ou numero_facture
        var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<VenteResponse>(result);
        }
        
        return null;
    }
}
```

### 3. Enregistrer les Services

**MauiProgram.cs:**
```csharp
// Enregistrer les services avec IHttpClientFactory
builder.Services.AddSingleton<IArticleService, ArticleService>();
builder.Services.AddSingleton<IVenteService, VenteService>();
builder.Services.AddSingleton<ICategorieService, CategorieService>();
```

---

## 📝 CHECKLIST DE MIGRATION

### Configuration
- [ ] Installer le package `Microsoft.Extensions.Http` si nécessaire
- [ ] Configurer `AddHttpClient` dans `MauiProgram.cs`
- [ ] Ajouter le header `X-Device-Serial` avec le numéro de série Android
- [ ] Vérifier que la base URL est correcte

### Services
- [ ] Modifier tous les services pour utiliser `IHttpClientFactory`
- [ ] Supprimer tout code gérant `boutique_id` manuellement
- [ ] Supprimer tout code générant `numero_facture`
- [ ] Utiliser uniquement les endpoints `/api/v2/simple/`

### Nettoyage
- [ ] Supprimer les variables `boutique_id` stockées dans `SecureStorage`
- [ ] Supprimer les méthodes de génération de `numero_facture`
- [ ] Supprimer les paramètres `boutique_id` des URLs

### Tests
- [ ] Tester la récupération d'articles
- [ ] Tester la création d'une vente
- [ ] Tester l'historique des ventes
- [ ] Vérifier les logs pour les erreurs 400/404

---

## 🧪 CODE DE TEST

Ajouter cette page de debug pour valider la configuration:

```csharp
public partial class DebugPage : ContentPage
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IArticleService _articleService;
    private readonly IVenteService _venteService;
    
    public DebugPage(
        IHttpClientFactory httpClientFactory,
        IArticleService articleService,
        IVenteService venteService)
    {
        InitializeComponent();
        _httpClientFactory = httpClientFactory;
        _articleService = articleService;
        _venteService = venteService;
    }
    
    private async void OnTestNumeroSerieClicked(object sender, EventArgs e)
    {
        var httpClient = _httpClientFactory.CreateClient("DjangoAPI");
        var serialHeader = httpClient.DefaultRequestHeaders
            .FirstOrDefault(h => h.Key == "X-Device-Serial");
        
        if (serialHeader.Value != null)
        {
            var numeroSerie = serialHeader.Value.FirstOrDefault();
            await DisplayAlert("✅ Succès", 
                $"Numéro de série configuré:\n{numeroSerie}", "OK");
        }
        else
        {
            await DisplayAlert("❌ Erreur", 
                "Header X-Device-Serial manquant!", "OK");
        }
    }
    
    private async void OnTestArticlesClicked(object sender, EventArgs e)
    {
        try
        {
            var articles = await _articleService.GetArticlesAsync();
            
            if (articles.Count > 0)
            {
                await DisplayAlert("✅ Succès", 
                    $"{articles.Count} articles récupérés", "OK");
            }
            else
            {
                await DisplayAlert("⚠️ Attention", 
                    "Aucun article trouvé pour cette boutique", "OK");
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("❌ Erreur", ex.Message, "OK");
        }
    }
    
    private async void OnTestVenteClicked(object sender, EventArgs e)
    {
        try
        {
            var articles = await _articleService.GetArticlesAsync();
            if (articles.Count == 0)
            {
                await DisplayAlert("❌ Erreur", 
                    "Aucun article disponible", "OK");
                return;
            }
            
            var article = articles[0];
            var lignes = new List<LigneVenteRequest>
            {
                new LigneVenteRequest
                {
                    ArticleId = article.Id,
                    Quantite = 1,
                    PrixUnitaire = article.PrixVente
                }
            };
            
            var result = await _venteService.CreerVenteAsync(lignes);
            
            if (result?.Success == true)
            {
                await DisplayAlert("✅ Succès", 
                    $"Vente créée:\n{result.Vente.NumeroFacture}\n" +
                    $"Montant: {result.Vente.MontantTotal} CDF", "OK");
            }
            else
            {
                await DisplayAlert("❌ Erreur", 
                    result?.Error ?? "Erreur inconnue", "OK");
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("❌ Erreur", ex.Message, "OK");
        }
    }
}
```

**XAML correspondant:**
```xml
<?xml version="1.0" encoding="utf-8" ?>
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml"
             x:Class="VotreApp.Pages.DebugPage"
             Title="Tests API">
    
    <VerticalStackLayout Padding="20" Spacing="15">
        <Label Text="Tests d'Intégration API" 
               FontSize="24" 
               FontAttributes="Bold"
               HorizontalOptions="Center"/>
        
        <Button Text="Test 1: Vérifier Numéro de Série"
                Clicked="OnTestNumeroSerieClicked"
                BackgroundColor="#007AFF"/>
        
        <Button Text="Test 2: Récupérer Articles"
                Clicked="OnTestArticlesClicked"
                BackgroundColor="#34C759"/>
        
        <Button Text="Test 3: Créer Vente de Test"
                Clicked="OnTestVenteClicked"
                BackgroundColor="#FF9500"/>
    </VerticalStackLayout>
</ContentPage>
```

---

## 🚨 ERREURS COURANTES

### Erreur 1: "Terminal non trouvé"
```json
{
    "error": "Terminal non trouvé ou sans boutique",
    "code": "TERMINAL_NOT_FOUND"
}
```

**Cause:** Le header `X-Device-Serial` n'est pas envoyé ou le terminal n'existe pas dans Django.

**Solution:**
1. Vérifier que le header est bien configuré dans `AddHttpClient`
2. Vérifier que le terminal existe dans Django Admin
3. Vérifier que le terminal est lié à une boutique

### Erreur 2: "Article non trouvé dans cette boutique"
```json
{
    "error": "Article X non trouvé dans cette boutique",
    "code": "ARTICLE_NOT_FOUND"
}
```

**Cause:** Vous essayez de vendre un article qui n'appartient pas à votre boutique.

**Solution:** Utiliser UNIQUEMENT les articles retournés par `GET /api/v2/simple/articles/`

### Erreur 3: Aucun article affiché
**Cause:** La boutique n'a pas d'articles ou les articles ne sont pas actifs.

**Solution:** Vérifier dans Django Admin que la boutique a des articles avec `est_actif=True`

---

## 📊 VALIDATION FINALE

Une fois les modifications effectuées:

1. **Lancer l'app MAUI**
2. **Aller sur la page de debug**
3. **Exécuter les 3 tests:**
   - ✅ Test 1: Numéro de série doit s'afficher
   - ✅ Test 2: Articles doivent être récupérés
   - ✅ Test 3: Vente doit être créée

4. **Vérifier dans le backend Django:**
   - Se connecter en tant que commerçant
   - Aller sur "Historique des ventes"
   - La vente de test doit être visible
   - Se connecter avec un autre commerçant
   - La vente NE DOIT PAS être visible

---

## 💡 RÉSUMÉ POUR L'ÉQUIPE

### Ce qui change:
1. ❌ **Plus de gestion manuelle de `boutique_id`**
2. ✅ **Le numéro de série identifie automatiquement la boutique**
3. ✅ **Configuration une seule fois dans `MauiProgram.cs`**
4. ✅ **Tous les appels API sont simplifiés**

### Avantages:
- ✅ Code plus simple
- ✅ Moins d'erreurs
- ✅ Isolation garantie par Django
- ✅ Pas de gestion de `boutique_id` côté MAUI

### Format de vente simplifié:
```json
{
    "lignes": [
        {
            "article_id": 1,
            "quantite": 2,
            "prix_unitaire": 1000.00
        }
    ]
}
```

**Django gère automatiquement:**
- ✅ `boutique_id`
- ✅ `numero_facture`
- ✅ `montant_total`
- ✅ Mise à jour du stock
- ✅ Création de l'historique

---

## 📞 SUPPORT

Si vous rencontrez des problèmes:

1. **Vérifier les logs Django** pour voir les requêtes reçues
2. **Utiliser la page de debug** pour tester chaque fonctionnalité
3. **Vérifier que le numéro de série est bien envoyé** dans les headers
4. **Contacter l'équipe backend** avec les logs d'erreur

---

**Date:** 30 Octobre 2025  
**Version:** 1.0  
**Statut:** ✅ Prêt pour implémentation
