# 🚀 GUIDE D'INTÉGRATION MAUI - ISOLATION DES VENTES PAR BOUTIQUE

## 📋 CONTEXTE

Le backend Django a été configuré pour **isoler complètement les ventes par boutique**. Chaque vente est automatiquement liée à la boutique du terminal MAUI qui l'a créée.

### Architecture Django (100% Opérationnelle)

```
Commerçant
    ├── Boutique 1
    │   ├── Terminal MAUI A (numero_serie: XXX)
    │   │   └── Ventes du terminal A
    │   └── Terminal MAUI B (numero_serie: YYY)
    │       └── Ventes du terminal B
    │
    └── Boutique 2
        └── Terminal MAUI C (numero_serie: ZZZ)
            └── Ventes du terminal C
```

### Garanties Django

✅ **Chaque vente est automatiquement liée à UNE SEULE boutique**  
✅ **Le champ `boutique_id` est assigné automatiquement par l'API**  
✅ **Impossible de créer une vente sans boutique**  
✅ **Impossible de voir les ventes d'une autre boutique**

---

## 🔑 PRINCIPE FONDAMENTAL

**L'isolation se fait via le numéro de série du terminal MAUI.**

```
Numéro de Série → Terminal MAUI → Boutique → Ventes
```

Le backend Django utilise le **numéro de série** envoyé dans les headers HTTP pour :
1. Identifier le terminal MAUI
2. Récupérer la boutique associée au terminal
3. Assigner automatiquement cette boutique à toutes les ventes créées

---

## 🛠️ IMPLÉMENTATION MAUI

### 1. Configuration du HttpClient (CRITIQUE)

Le numéro de série **DOIT** être envoyé dans **TOUS** les headers HTTP.

#### ✅ Configuration Correcte

```csharp
// Dans MauiProgram.cs ou App.xaml.cs
public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        
        // Configuration du HttpClient avec headers par défaut
        builder.Services.AddHttpClient("DjangoAPI", client =>
        {
            // URL de base de votre serveur Django
            client.BaseAddress = new Uri("http://10.59.88.224:8000");
            
            // ⭐ CRITIQUE: Ajouter le numéro de série dans TOUS les headers
            #if ANDROID
            string numeroSerie = GetDeviceSerialNumber();
            client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
            #endif
            
            // Timeout
            client.Timeout = TimeSpan.FromSeconds(30);
        });
        
        // Enregistrer les services
        builder.Services.AddSingleton<IArticleService, ArticleService>();
        builder.Services.AddSingleton<IVenteService, VenteService>();
        builder.Services.AddSingleton<ICategorieService, CategorieService>();
        
        return builder.Build();
    }
    
    private static string GetDeviceSerialNumber()
    {
        #if ANDROID
        try
        {
            // Méthode 1: Build.Serial (API < 26)
            string serial = Android.OS.Build.Serial;
            
            // Méthode 2: Build.GetSerial() (API >= 26)
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
            // Fallback: Utiliser un identifiant unique
            return Preferences.Get("device_serial", Guid.NewGuid().ToString());
        }
        #else
        return "MAUI-SIMULATOR-" + Guid.NewGuid().ToString();
        #endif
    }
}
```

---

### 2. Services MAUI Simplifiés

Avec le numéro de série dans les headers par défaut, vos services n'ont **PLUS BESOIN** de gérer le `boutique_id`.

#### ✅ Service Articles

```csharp
public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;
    
    public ArticleService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }
    
    public async Task<List<Article>> GetArticlesAsync()
    {
        try
        {
            // ⭐ PAS BESOIN de boutique_id !
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
        catch (Exception ex)
        {
            Debug.WriteLine($"Erreur GetArticles: {ex.Message}");
            return new List<Article>();
        }
    }
}
```

#### ✅ Service Ventes

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
        try
        {
            // ⭐ Format MINIMAL - Django gère tout automatiquement
            var vente = new { lignes = lignes };
            
            var json = JsonSerializer.Serialize(vente);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            // ⭐ PAS BESOIN de boutique_id !
            // Le header X-Device-Serial identifie automatiquement la boutique
            var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
            
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<VenteResponse>(result);
            }
            
            // Gérer les erreurs
            var error = await response.Content.ReadAsStringAsync();
            Debug.WriteLine($"Erreur création vente: {error}");
            return null;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Exception création vente: {ex.Message}");
            return null;
        }
    }
    
    public async Task<List<Vente>> GetHistoriqueVentesAsync(int limit = 50)
    {
        try
        {
            // ⭐ PAS BESOIN de boutique_id !
            var response = await _httpClient.GetAsync($"/api/v2/simple/ventes/historique/?limit={limit}");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<HistoriqueResponse>(content);
                return result.Ventes ?? new List<Vente>();
            }
            
            return new List<Vente>();
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Erreur historique: {ex.Message}");
            return new List<Vente>();
        }
    }
}
```

---

### 3. Modèles C# (Inchangés)

```csharp
public class LigneVenteRequest
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
}

public class VenteResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("vente")]
    public VenteDetail Vente { get; set; }
    
    [JsonPropertyName("error")]
    public string Error { get; set; }
}

public class VenteDetail
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; }
    
    [JsonPropertyName("montant_total")]
    public decimal MontantTotal { get; set; }
    
    [JsonPropertyName("date_vente")]
    public DateTime DateVente { get; set; }
}
```

---

## 🔍 ENDPOINTS API DJANGO

### Base URL
```
http://10.59.88.224:8000/api/v2/simple/
```

### 1. GET /articles/
**Récupérer les articles de la boutique**

**Headers requis:**
```
X-Device-Serial: {numero_serie_du_terminal}
```

**Réponse:**
```json
{
    "success": true,
    "articles": [
        {
            "id": 1,
            "code": "ART001",
            "nom": "Article 1",
            "prix_vente": 1000.00,
            "quantite_stock": 50
        }
    ]
}
```

### 2. POST /ventes/
**Créer une vente**

**Headers requis:**
```
X-Device-Serial: {numero_serie_du_terminal}
Content-Type: application/json
```

**Body (MINIMAL):**
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

**Réponse:**
```json
{
    "success": true,
    "vente": {
        "id": 123,
        "numero_facture": "VENTE-2-20251030210530",
        "montant_total": 2000.00,
        "date_vente": "2025-10-30T21:05:30Z"
    }
}
```

### 3. GET /ventes/historique/
**Récupérer l'historique des ventes**

**Headers requis:**
```
X-Device-Serial: {numero_serie_du_terminal}
```

**Paramètres optionnels:**
- `limit`: Nombre de ventes (défaut: 50)
- `date_debut`: Date de début (format: YYYY-MM-DD)
- `date_fin`: Date de fin (format: YYYY-MM-DD)

**Réponse:**
```json
{
    "success": true,
    "statistiques": {
        "total_ventes": 15,
        "chiffre_affaires": "150000.00"
    },
    "ventes": [
        {
            "id": 123,
            "numero_facture": "VENTE-2-20251030210530",
            "montant_total": 2000.00,
            "date_vente": "2025-10-30T21:05:30Z",
            "lignes": [...]
        }
    ]
}
```

---

## 🧪 TESTS DE VALIDATION

### Test 1: Vérifier le Numéro de Série

```csharp
// Dans votre page de debug ou settings
public async Task TestNumeroSerie()
{
    var httpClient = _httpClientFactory.CreateClient("DjangoAPI");
    
    // Vérifier que le header est bien présent
    var headers = httpClient.DefaultRequestHeaders;
    var serialHeader = headers.FirstOrDefault(h => h.Key == "X-Device-Serial");
    
    if (serialHeader.Value != null)
    {
        var numeroSerie = serialHeader.Value.FirstOrDefault();
        await DisplayAlert("Numéro de Série", $"Serial: {numeroSerie}", "OK");
    }
    else
    {
        await DisplayAlert("Erreur", "Header X-Device-Serial manquant!", "OK");
    }
}
```

### Test 2: Tester la Récupération d'Articles

```csharp
public async Task TestArticles()
{
    try
    {
        var articles = await _articleService.GetArticlesAsync();
        
        if (articles.Count > 0)
        {
            await DisplayAlert("Succès", $"{articles.Count} articles récupérés", "OK");
        }
        else
        {
            await DisplayAlert("Attention", "Aucun article trouvé", "OK");
        }
    }
    catch (Exception ex)
    {
        await DisplayAlert("Erreur", ex.Message, "OK");
    }
}
```

### Test 3: Créer une Vente de Test

```csharp
public async Task TestCreerVente()
{
    try
    {
        // Récupérer un article
        var articles = await _articleService.GetArticlesAsync();
        if (articles.Count == 0)
        {
            await DisplayAlert("Erreur", "Aucun article disponible", "OK");
            return;
        }
        
        var article = articles[0];
        
        // Créer une ligne de vente
        var lignes = new List<LigneVenteRequest>
        {
            new LigneVenteRequest
            {
                ArticleId = article.Id,
                Quantite = 1,
                PrixUnitaire = article.PrixVente
            }
        };
        
        // Créer la vente
        var result = await _venteService.CreerVenteAsync(lignes);
        
        if (result?.Success == true)
        {
            await DisplayAlert("Succès", 
                $"Vente créée: {result.Vente.NumeroFacture}\nMontant: {result.Vente.MontantTotal} CDF", 
                "OK");
        }
        else
        {
            await DisplayAlert("Erreur", result?.Error ?? "Erreur inconnue", "OK");
        }
    }
    catch (Exception ex)
    {
        await DisplayAlert("Erreur", ex.Message, "OK");
    }
}
```

---

## 🔧 DÉPANNAGE

### Problème 1: "Terminal non trouvé"

**Erreur:**
```json
{
    "error": "Terminal non trouvé ou sans boutique",
    "code": "TERMINAL_NOT_FOUND"
}
```

**Causes possibles:**
1. Le numéro de série n'est pas envoyé dans les headers
2. Le terminal n'existe pas dans la base Django
3. Le terminal n'est pas lié à une boutique

**Solutions:**
```csharp
// Vérifier que le header est bien envoyé
var httpClient = _httpClientFactory.CreateClient("DjangoAPI");
Debug.WriteLine($"Headers: {string.Join(", ", httpClient.DefaultRequestHeaders)}");

// Vérifier le numéro de série
#if ANDROID
string serial = Android.OS.Build.Serial;
Debug.WriteLine($"Numéro de série: {serial}");
#endif
```

### Problème 2: "Aucun article trouvé"

**Causes possibles:**
1. La boutique n'a pas d'articles
2. Le terminal n'est pas lié à une boutique
3. Les articles ne sont pas actifs

**Solution:**
Vérifier dans Django Admin:
1. Que le terminal existe et est actif
2. Que le terminal est lié à une boutique
3. Que la boutique a des articles actifs

### Problème 3: Erreur 400 lors de la création de vente

**Erreur:**
```json
{
    "error": "Article X non trouvé dans cette boutique",
    "code": "ARTICLE_NOT_FOUND"
}
```

**Cause:**
L'article n'appartient pas à la boutique du terminal.

**Solution:**
Utiliser uniquement les articles retournés par `GET /articles/` qui sont garantis d'appartenir à la boutique.

---

## ✅ CHECKLIST D'INTÉGRATION

### Configuration
- [ ] HttpClient configuré avec `X-Device-Serial` dans les headers par défaut
- [ ] Numéro de série récupéré correctement sur Android
- [ ] Base URL correcte (`http://10.59.88.224:8000`)

### Services
- [ ] ArticleService utilise `/api/v2/simple/articles/`
- [ ] VenteService utilise `/api/v2/simple/ventes/`
- [ ] Aucun `boutique_id` n'est envoyé manuellement
- [ ] Les headers sont automatiquement ajoutés

### Tests
- [ ] Test de récupération d'articles réussi
- [ ] Test de création de vente réussi
- [ ] Test d'historique de ventes réussi
- [ ] Vérification que le numéro de série est bien envoyé

### Validation
- [ ] Les articles affichés sont ceux de la boutique
- [ ] Les ventes créées sont visibles dans le backend
- [ ] Les ventes ne sont visibles que pour la bonne boutique
- [ ] Aucune erreur 400/404 dans les logs

---

## 📊 FLUX COMPLET D'UNE VENTE

```
1. MAUI: Utilisateur scanne un article
   └─> GET /api/v2/simple/articles/
       Header: X-Device-Serial: XXX
   
2. Django: Identifie le terminal via le numéro de série
   └─> Récupère la boutique du terminal
   └─> Retourne UNIQUEMENT les articles de cette boutique

3. MAUI: Utilisateur ajoute au panier et finalise
   └─> POST /api/v2/simple/ventes/
       Header: X-Device-Serial: XXX
       Body: { "lignes": [...] }

4. Django: Identifie le terminal via le numéro de série
   └─> Récupère la boutique du terminal
   └─> Assigne automatiquement vente.boutique = boutique
   └─> Vérifie que les articles appartiennent à la boutique
   └─> Crée la vente avec isolation garantie

5. MAUI: Affiche le reçu
   └─> Vente enregistrée avec boutique_id correct
   └─> Visible uniquement pour cette boutique dans le backend
```

---

## 🎯 RÉSUMÉ POUR L'ÉQUIPE MAUI

### Ce que Django gère automatiquement:
✅ Identification du terminal via le numéro de série  
✅ Récupération de la boutique associée  
✅ Assignment automatique de `boutique_id` aux ventes  
✅ Filtrage des articles par boutique  
✅ Validation que les articles appartiennent à la boutique  
✅ Isolation complète des données  

### Ce que MAUI doit faire:
1. **Envoyer le numéro de série dans TOUS les headers HTTP** (`X-Device-Serial`)
2. **Utiliser les endpoints `/api/v2/simple/`**
3. **NE PAS gérer le `boutique_id` manuellement**
4. **Utiliser uniquement les articles retournés par l'API**

### Format minimal d'une vente:
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

**C'est tout !** Django gère le reste automatiquement. 🚀

---

**Date:** 30 Octobre 2025  
**Version API:** v2 Simple  
**Statut:** ✅ Production Ready
