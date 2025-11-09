// ═══════════════════════════════════════════════════════════════════════
// CODE C# MAUI - IMPLÉMENTATION COMPLÈTE
// Boutique de test : messie vanza
// Numéro de série : 0a1badae951f8473
// ═══════════════════════════════════════════════════════════════════════

using System.Net.Http;
using System.Text.Json;
using System.Text.Json.Serialization;

// ═══════════════════════════════════════════════════════════════════════
// ÉTAPE 1 : Configuration dans MauiProgram.cs
// ═══════════════════════════════════════════════════════════════════════

public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        
        builder
            .UseMauiApp<App>()
            .ConfigureFonts(fonts =>
            {
                fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
            });

        // Récupérer le numéro de série du terminal Android
        string numeroSerie = GetDeviceSerialNumber();
        
        Console.WriteLine($"📱 Numéro de série du terminal : {numeroSerie}");

        // Configurer HttpClient avec le header X-Device-Serial
        builder.Services.AddHttpClient("DjangoAPI", client =>
        {
            client.BaseAddress = new Uri("http://192.168.52.224:8000");
            client.Timeout = TimeSpan.FromSeconds(30);
            
            // ✅ HEADER CRITIQUE : Ajouter le numéro de série
            client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
            
            // Headers optionnels mais recommandés
            client.DefaultRequestHeaders.Add("Accept", "application/json");
            client.DefaultRequestHeaders.Add("User-Agent", "VenteMagazin-MAUI/1.0");
            
            Console.WriteLine($"✅ HttpClient configuré avec Serial: {numeroSerie}");
        });

        // Enregistrer les services
        builder.Services.AddSingleton<IArticleService, ArticleService>();
        builder.Services.AddSingleton<ICategorieService, CategorieService>();

        return builder.Build();
    }

    private static string GetDeviceSerialNumber()
    {
        #if ANDROID
        try
        {
            // Méthode 1 : Build.Serial (Android < 8)
            var serial = Android.OS.Build.Serial;
            if (!string.IsNullOrEmpty(serial) && serial != "unknown")
            {
                Console.WriteLine($"✅ Serial récupéré via Build.Serial: {serial}");
                return serial;
            }

            // Méthode 2 : Build.GetSerial() (Android >= 8)
            if (Android.OS.Build.VERSION.SdkInt >= Android.OS.BuildVersionCodes.O)
            {
                serial = Android.OS.Build.GetSerial();
                if (!string.IsNullOrEmpty(serial))
                {
                    Console.WriteLine($"✅ Serial récupéré via Build.GetSerial(): {serial}");
                    return serial;
                }
            }

            // Méthode 3 : Android ID (fallback)
            var androidId = Android.Provider.Settings.Secure.GetString(
                Android.App.Application.Context.ContentResolver,
                Android.Provider.Settings.Secure.AndroidId
            );
            
            Console.WriteLine($"⚠️ Utilisation Android ID comme fallback: {androidId}");
            return androidId;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur récupération serial: {ex.Message}");
            return "UNKNOWN_SERIAL";
        }
        #else
        // Pour les tests en développement
        return "0a1badae951f8473"; // Votre numéro de série de test
        #endif
    }
}

// ═══════════════════════════════════════════════════════════════════════
// ÉTAPE 2 : Service Articles
// ═══════════════════════════════════════════════════════════════════════

public interface IArticleService
{
    Task<ArticlesResponse> GetArticlesAsync();
    Task<List<Article>> LoadArticlesAsync();
}

public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<ArticleService> _logger;

    public ArticleService(IHttpClientFactory httpClientFactory, ILogger<ArticleService> logger)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
        _logger = logger;
    }

    public async Task<ArticlesResponse> GetArticlesAsync()
    {
        try
        {
            _logger.LogInformation("🔄 Début récupération articles...");
            
            // ✅ URL SIMPLE - Le header X-Device-Serial est déjà ajouté automatiquement
            var url = "/api/v2/simple/articles/";
            
            _logger.LogInformation($"📡 Requête GET: {_httpClient.BaseAddress}{url}");
            
            var response = await _httpClient.GetAsync(url);
            
            _logger.LogInformation($"📥 Réponse HTTP: {response.StatusCode}");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                _logger.LogInformation($"📦 Contenu reçu: {content.Substring(0, Math.Min(200, content.Length))}...");
                
                var result = JsonSerializer.Deserialize<ArticlesResponse>(content, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
                
                if (result != null && result.Success)
                {
                    _logger.LogInformation($"✅ {result.Count} articles récupérés pour {result.BoutiqueNom}");
                    return result;
                }
                else
                {
                    _logger.LogWarning("⚠️ Réponse API avec success=false");
                    return new ArticlesResponse { Success = false, Articles = new List<Article>() };
                }
            }
            else
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogError($"❌ Erreur HTTP {response.StatusCode}: {errorContent}");
                return new ArticlesResponse { Success = false, Articles = new List<Article>() };
            }
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Exception GetArticlesAsync: {ex.Message}");
            _logger.LogError($"Stack trace: {ex.StackTrace}");
            return new ArticlesResponse { Success = false, Articles = new List<Article>() };
        }
    }

    public async Task<List<Article>> LoadArticlesAsync()
    {
        var response = await GetArticlesAsync();
        return response.Success ? response.Articles : new List<Article>();
    }
}

// ═══════════════════════════════════════════════════════════════════════
// ÉTAPE 3 : Service Catégories
// ═══════════════════════════════════════════════════════════════════════

public interface ICategorieService
{
    Task<CategoriesResponse> GetCategoriesAsync();
}

public class CategorieService : ICategorieService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<CategorieService> _logger;

    public CategorieService(IHttpClientFactory httpClientFactory, ILogger<CategorieService> logger)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
        _logger = logger;
    }

    public async Task<CategoriesResponse> GetCategoriesAsync()
    {
        try
        {
            _logger.LogInformation("🔄 Début récupération catégories...");
            
            // ✅ URL SIMPLE - Le header X-Device-Serial est déjà ajouté automatiquement
            var url = "/api/v2/simple/categories/";
            
            var response = await _httpClient.GetAsync(url);
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<CategoriesResponse>(content, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
                
                if (result != null && result.Success)
                {
                    _logger.LogInformation($"✅ {result.Count} catégories récupérées");
                    return result;
                }
            }
            
            return new CategoriesResponse { Success = false, Categories = new List<Categorie>() };
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Exception GetCategoriesAsync: {ex.Message}");
            return new CategoriesResponse { Success = false, Categories = new List<Categorie>() };
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// ÉTAPE 4 : Modèles de Données
// ═══════════════════════════════════════════════════════════════════════

public class ArticlesResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("count")]
    public int Count { get; set; }
    
    [JsonPropertyName("boutique_id")]
    public int BoutiqueId { get; set; }
    
    [JsonPropertyName("boutique_nom")]
    public string BoutiqueNom { get; set; }
    
    [JsonPropertyName("terminal")]
    public TerminalInfo Terminal { get; set; }
    
    [JsonPropertyName("articles")]
    public List<Article> Articles { get; set; } = new List<Article>();
}

public class TerminalInfo
{
    [JsonPropertyName("numero_serie")]
    public string NumeroSerie { get; set; }
    
    [JsonPropertyName("nom_terminal")]
    public string NomTerminal { get; set; }
}

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
    
    [JsonPropertyName("prix_vente")]
    public string PrixVente { get; set; }
    
    [JsonPropertyName("prix_achat")]
    public string PrixAchat { get; set; }
    
    [JsonPropertyName("quantite_stock")]
    public int QuantiteStock { get; set; }
    
    [JsonPropertyName("categorie")]
    public CategorieInfo Categorie { get; set; }
    
    [JsonPropertyName("image_url")]
    public string ImageUrl { get; set; }
    
    [JsonPropertyName("qr_code_url")]
    public string QrCodeUrl { get; set; }
    
    [JsonPropertyName("est_actif")]
    public bool EstActif { get; set; }
    
    // Propriété calculée pour affichage
    public decimal PrixVenteDecimal => decimal.TryParse(PrixVente, out var prix) ? prix : 0;
}

public class CategorieInfo
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
}

public class CategoriesResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("count")]
    public int Count { get; set; }
    
    [JsonPropertyName("boutique_id")]
    public int BoutiqueId { get; set; }
    
    [JsonPropertyName("boutique_nom")]
    public string BoutiqueNom { get; set; }
    
    [JsonPropertyName("categories")]
    public List<Categorie> Categories { get; set; } = new List<Categorie>();
}

public class Categorie
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
    
    [JsonPropertyName("description")]
    public string Description { get; set; }
}

// ═══════════════════════════════════════════════════════════════════════
// ÉTAPE 5 : Utilisation dans un ViewModel
// ═══════════════════════════════════════════════════════════════════════

public class ArticlesViewModel : BaseViewModel
{
    private readonly IArticleService _articleService;
    private ObservableCollection<Article> _articles;
    private bool _isLoading;

    public ObservableCollection<Article> Articles
    {
        get => _articles;
        set => SetProperty(ref _articles, value);
    }

    public bool IsLoading
    {
        get => _isLoading;
        set => SetProperty(ref _isLoading, value);
    }

    public ArticlesViewModel(IArticleService articleService)
    {
        _articleService = articleService;
        Articles = new ObservableCollection<Article>();
    }

    public async Task LoadArticlesAsync()
    {
        try
        {
            IsLoading = true;
            
            Console.WriteLine("🔄 Chargement des articles...");
            
            var articles = await _articleService.LoadArticlesAsync();
            
            Articles.Clear();
            foreach (var article in articles)
            {
                Articles.Add(article);
            }
            
            Console.WriteLine($"✅ {Articles.Count} articles chargés dans la collection");
            
            if (Articles.Count == 0)
            {
                Console.WriteLine("⚠️ Aucun article récupéré - Vérifier les logs Django");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur LoadArticlesAsync: {ex.Message}");
        }
        finally
        {
            IsLoading = false;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// RÉSULTAT ATTENDU POUR VOTRE BOUTIQUE TEST
// ═══════════════════════════════════════════════════════════════════════

/*
Boutique : messie vanza (ID: 2)
Terminal : 0a1badae951f8473

Articles attendus :
1. battery iphone (Code: 009) - 40 000 CDF - Stock: 10
2. samsung s24 (Code: 0001) - 100 000 CDF - Stock: 5

Logs attendus :
📱 Numéro de série du terminal : 0a1badae951f8473
✅ HttpClient configuré avec Serial: 0a1badae951f8473
🔄 Début récupération articles...
📡 Requête GET: http://192.168.52.224:8000/api/v2/simple/articles/
📥 Réponse HTTP: OK
✅ 2 articles récupérés pour messie vanza
✅ 2 articles chargés dans la collection
*/
